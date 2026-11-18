"""Variante B de l'affectation des enseignants : le coût d'un déplacement est la distance réelle (à vol d'oiseau)
entre les centres de deux provinces, au lieu des coûts de priorité 1 (même région) et 3 (autre région).

Le code du Rôle 2 (modele/projection_et_allocation.py) n'est PAS modifié. Cette fonction reprend sa logique en deux étapes
(1. couverture minimale la plus haute possible ; 2. minimiser manque, déplacements et recrues) et ne change que le coût
des arcs. Les contraintes sont les mêmes : on ne descend pas sous le besoin d'une province, on ne dépasse pas le besoin
d'une province receveuse, les recrues sont limitées. Les totaux (manque, recrues) restent donc comparables.

Hypothèse de calage (non officielle) : un déplacement coûte 1 unité fixe (comme « même région » dans le modèle de priorité)
plus 1 unité par tranche de 100 km ; une recrue coûte 0,5, comme dans le modèle d'origine. On garde ainsi la règle du modèle
d'origine : recrues d'abord, redéploiement ensuite ; la distance sert à choisir les déplacements les plus courts.
"""
from __future__ import annotations

from functools import lru_cache

import numpy as np
import pandas as pd
import pulp

from . import carte
from .modele import pea

KM_PAR_UNITE = 100.0          # hypothèse : 100 km = 1 unité de coût
COUT_FIXE_DEPL = 1.0          # hypothèse : coût fixe d'un déplacement (même valeur que « même région » du modèle d'origine)


@lru_cache(maxsize=1)
def _centres() -> dict:
    """Centre de chaque province (45 anciennes), en km sur la carte."""
    prov, c2k = carte.geo()["prov"], carte.code_vers_cle()
    return {c: carte._centroide(prov[k]["rings"]) for c, k in c2k.items()}


def km(i: str, j: str) -> float:
    (ax, ay), (bx, by) = _centres()[i], _centres()[j]
    return float(((ax - bx) ** 2 + (ay - by) ** 2) ** 0.5)


def km_total_flux(flux) -> float:
    """Somme (maîtres × km) d'une liste de flux (de, vers, maîtres), quel que soit le modèle qui l'a produite."""
    return float(sum(q * km(i, j) for (i, j, q) in flux))


def allouer_distance(cur: pd.Series, besoin: pd.Series, recrues: int):
    """Même sortie que pea.allouer, avec le coût = km / KM_PAR_UNITE."""
    prov = list(cur.index)
    exces = {i: max(0, int(cur[i] - besoin[i])) for i in prov}
    manque = {i: max(0, int(besoin[i] - cur[i])) for i in prov}
    src = [i for i in prov if exces[i] > 0]
    dst = [i for i in prov if manque[i] > 0]
    arcs = [(i, j) for i in src for j in dst]

    def construire(entiers: bool, plancher=None):
        cat = "Integer" if entiers else "Continuous"
        m = pulp.LpProblem("allocation_distance", pulp.LpMinimize)
        y = {a: pulp.LpVariable(f"y_{a[0]}_{a[1]}", 0, None, cat=cat) for a in arcs}
        r = {j: pulp.LpVariable(f"r_{j}", 0, None, cat=cat) for j in dst}
        z = pulp.LpVariable("z", 0, 1)
        for i in src:
            m += pulp.lpSum(y[(i, j)] for j in dst) <= exces[i]
        entrant = {j: pulp.lpSum(y[(i, j)] for i in src) + r[j] for j in dst}
        for j in dst:
            m += entrant[j] <= manque[j]
            if plancher is None:
                m += cur[j] + entrant[j] >= z * besoin[j]
            else:
                m += entrant[j] >= max(0, plancher[j] - cur[j])
        m += pulp.lpSum(r.values()) <= recrues
        return m, y, r, z, entrant

    solveur = pulp.PULP_CBC_CMD(msg=0, timeLimit=pea.DELAI_MAX_S)
    m, y, r, z, entrant = construire(False)
    m.setObjective(-z)
    m.solve(solveur)
    statut1 = pulp.LpStatus[m.status]
    zstar = pulp.value(z) if dst else 1.0
    plancher = {j: int(np.floor(zstar * besoin[j] + 1e-9)) for j in dst}
    m, y, r, z, entrant = construire(True, plancher)
    m.setObjective(pea.POIDS_MANQUE * pulp.lpSum(manque[j] - entrant[j] for j in dst)
                   + pulp.lpSum((COUT_FIXE_DEPL + km(i, j) / KM_PAR_UNITE) * y[(i, j)] for (i, j) in arcs)
                   + pea.COUT_RECRUE * pulp.lpSum(r.values()))
    m.solve(solveur)
    statut2 = pulp.LpStatus[m.status]
    assert statut1 == "Optimal" and statut2 == "Optimal", f"solveur : {statut1} / {statut2}"
    val = lambda v: int(round(v.value() or 0))
    t = pd.DataFrame(index=prov)
    t["maitres_apres_departs"] = cur
    t["besoin_maitres"] = besoin
    t["redeploye_sortant"] = [sum(val(y[(i, j)]) for j in dst) if i in src else 0 for i in prov]
    t["redeploye_entrant"] = [sum(val(y[(i, j)]) for i in src) if j in dst else 0 for j in prov]
    t["recrues_affectees"] = [val(r[j]) if j in dst else 0 for j in prov]
    t["maitres_2030"] = t.maitres_apres_departs - t.redeploye_sortant + t.redeploye_entrant + t.recrues_affectees
    t["manque_restant"] = (t.besoin_maitres - t.maitres_2030).clip(lower=0)
    t["couverture"] = (t.maitres_2030 / t.besoin_maitres).round(4)
    flux = [(i, j, val(y[(i, j)])) for (i, j) in arcs if val(y[(i, j)]) > 0]
    return t, {"statut_etape1": statut1, "statut_etape2": statut2, "couverture_minimale_theorique": round(zstar, 4), "flux": flux}
