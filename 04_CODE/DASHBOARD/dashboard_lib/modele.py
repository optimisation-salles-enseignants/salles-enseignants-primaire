"""Modèle de simulation du tableau de bord.

Principe : on appelle les fonctions du Rôle 2 (modele/projection_et_allocation.py) SANS les modifier.
Seuls les paramètres changent d'un scénario à l'autre : taux de scolarisation visé, normes, départs, recrutements,
capacité de construction, hypothèse sur le privé. Chaque scénario est résolu par le solveur (programmation linéaire,
PuLP/CBC) ; son statut (réalisable ou non) est conservé. Aucun chiffre n'est estimé à la main.

Il n'y a rien à entraîner : on résout l'optimisation à chaque réglage. Un cache sur disque garde les résultats déjà résolus,
identifiés par une empreinte des paramètres et des fichiers d'entrée.
"""
from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import asdict, dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

from .chemins import ANALYSE, CACHE, MODELE_ANALYSE, TRANSFORMATION, trouver

sys.path.insert(0, str(MODELE_ANALYSE))
import projection_et_allocation as pea  # noqa: E402  (code du Rôle 2, importé tel quel)

CLE = pea.CLE
SCENARIOS_PREDEFINIS = {
    "S0_statu_quo": "Statu quo : le taux de scolarisation de 2024 est maintenu",
    "S1_retour_2020": "Retour au niveau de 2020",
    "S2_acces_95": "Accès élargi : au moins 95 % des enfants de 6 à 11 ans",
    "tendance_apprise": "Tendance apprise sur l'historique 2017-2025 (expérimental : ne bat pas le statu quo à la validation)",
}


@dataclass(frozen=True)
class Parametres:
    """Tous les réglages d'un scénario. Les valeurs sans source officielle sont des hypothèses."""
    scenario: str = "S0_statu_quo"        # un des SCENARIOS_PREDEFINIS, ou "personnalise"
    taux_cible: float = 0.95              # utilisé seulement si scenario == "personnalise" (taux brut visé, public + privé)
    norme_maitre: int = 50                # élèves par maître (hypothèse de référence : 50)
    norme_salle: int = 50                 # élèves par salle (hypothèse de référence : 50)
    attrition: float = 0.0                # départs annuels de maîtres (inconnu : testé à 0 et 2 %)
    recrues_par_an: int = 3887            # recrutements annuels (PSEF action 8.1.2, à revérifier)
    part_construction: float = 0.5        # part du besoin national en salles constructible d'ici 2030
    hypothese_prive: str = "part_constante"
    quantile_tendance: float = 0.5        # utilisé seulement si scenario == "tendance_apprise" : 0.1 bas, 0.5 central, 0.9 haut
    horizon: int = 2030                   # année visée (2026 à 2035, projections INSD) ; le niveau de scolarisation du scénario est atteint à cette date
    cout_deplacement: str = "priorite"    # "priorite" (modèle du Rôle 2 : 1 même région, 3 autre région) ou "distance" (km entre centres de provinces)

    def empreinte(self) -> str:
        d = asdict(self)
        if d["cout_deplacement"] == "priorite":
            del d["cout_deplacement"]          # les résultats déjà en cache (avant l'option) restent valides
        if d["horizon"] == 2030:
            del d["horizon"]
        return hashlib.sha256(json.dumps(d, sort_keys=True).encode()).hexdigest()[:16]


@dataclass
class Resultat:
    parametres: Parametres
    provinces: pd.DataFrame          # une ligne par ancienne province (45), maîtres et salles
    synthese: dict
    flux: list                       # (de, vers, maîtres)
    realisable: bool
    message: str


class Donnees:
    """Entrées lues une seule fois : unités de calcul (45 provinces) et population 2030."""

    def __init__(self):
        self.panel_public = trouver(ANALYSE, "*panel-provinces-annee-public_v1.csv")
        self.panel_total = trouver(ANALYSE, "*analyst_panel-provinces-annee_v2.csv")
        self.population = trouver(TRANSFORMATION / "reserve", "*population-locale-groupes-age_v2.csv")
        self.u = pea.unites_base(self.panel_public, self.panel_total)
        self.pop2030 = pea.population_2030(self.population, self.u.index)
        h = hashlib.sha256()
        for p in (self.panel_public, self.panel_total, self.population):
            h.update(p.read_bytes())
        h.update(Path_bytes(pea))
        self.empreinte = h.hexdigest()[:16]


def Path_bytes(module) -> bytes:
    return Path(module.__file__).read_bytes()


HORIZONS = tuple(range(2026, 2036))     # années pour lesquelles l'INSD publie une projection de la population de 6 à 11 ans


@lru_cache(maxsize=None)
def pop_annee(annee: int) -> pd.Series:
    """Population de 6 à 11 ans par ancienne province pour une année quelconque (mêmes filtres et mêmes contrôles que le Rôle 2)."""
    if annee == pea.HORIZON:
        return donnees().pop2030
    t = pd.read_csv(donnees().population, sep=pea.SEP, dtype=str)
    t = t[(t.niveau == "province") & (t.sexe == "ensemble") & (t.groupe_age == "6-11") & (t.annee == str(annee))]
    s = t.set_index("code_ancien").effectif.astype(float)
    assert s.index.is_unique and set(donnees().u.index) == set(s.index), "les codes de population ne couvrent pas les 45 provinces"
    return s.loc[list(donnees().u.index)]


@lru_cache(maxsize=1)
def donnees() -> Donnees:
    return Donnees()


def _taux_total(u: pd.DataFrame, p: Parametres) -> pd.Series:
    if p.scenario == "tendance_apprise":
        # Modèle appris sur l'historique (voir entrainement.py). Le taux est plafonné à max(1, taux 2024) : un taux brut très
        # supérieur à 100 % ne se justifie pas par l'historique.
        from . import entrainement
        e30 = entrainement.charger().projeter_effectifs(p.quantile_tendance).reindex(u.index)
        pop = pd.Series(pea.population_2030(donnees().population, u.index), index=u.index)
        return np.minimum(e30 / pop, np.maximum(1.0, u.taux_2024))
    if p.scenario == "personnalise":
        return np.maximum(u.taux_2024, p.taux_cible)       # on ne vise jamais moins que le taux de 2024
    f = pea.SCENARIOS[p.scenario]
    return pd.Series({c: f(r.taux_2024, r.taux_2020) for c, r in u.iterrows()})


def projeter(d: Donnees, p: Parametres) -> pd.DataFrame:
    """Élèves 2030 et besoins, mêmes formules que projeter() du Rôle 2, avec des normes libres."""
    u = d.u
    t = _taux_total(u, p)
    if p.hypothese_prive == "part_constante":
        taux = t * u.part_statut_2024
    else:
        taux = pd.Series({c: (max(0.0, t[c] - u.taux_prive_2024[c]) if u.part_statut_2024[c] < 1 else t[c]) for c in u.index})
    pop = pop_annee(p.horizon)
    e30 = pop * taux            # colonnes nommées « 2030 » par héritage du Rôle 2 : elles valent l'année de l'horizon choisi
    out = pd.DataFrame({CLE: u.index, "nom_province_ancien": u.nom_province_ancien.values,
                        "population_6_11_2030": pop.astype(int).values, "taux_cible_total_2030": t.round(4).values,
                        "eleves_2030": e30.round().astype(int).values}, index=u.index)
    out["besoin_maitres"] = np.ceil(e30 / p.norme_maitre).astype(int)
    out["besoin_salles"] = np.ceil(e30 / p.norme_salle).astype(int)
    return out


def calculer(p: Parametres, utiliser_cache: bool = True) -> Resultat:
    d = donnees()
    cle = f"{d.empreinte}_{p.empreinte()}"
    if utiliser_cache and (CACHE / f"{cle}.json").exists():
        return _lire_cache(cle, p)
    proj = projeter(d, p)
    u = d.u
    if p.scenario == "tendance_apprise" and p.horizon != pea.HORIZON:
        return Resultat(p, pd.DataFrame(), {}, [], False, "La tendance apprise est calculée pour 2030 seulement : choisir 2030 ou un autre scénario.")
    n_annees = p.horizon - int(pea.ANNEE_BASE[:4])      # 2030 : 6 années de recrutement, comme le Rôle 2
    cur = np.floor(u.maitres_2024 * (1 - p.attrition) ** n_annees).astype(int)
    recrues = int(p.recrues_par_an) * n_annees
    try:
        if p.cout_deplacement == "distance":
            from . import allocation_distance as ad
            tm, info = ad.allouer_distance(cur, proj.besoin_maitres, recrues)
        else:
            tm, info = pea.allouer(cur, proj.besoin_maitres, u.code_region_nouveau, recrues)
        ecart_total = int((proj.besoin_salles - u.salles_2024).clip(lower=0).sum())
        cap = int(round(p.part_construction * ecart_total))
        ts, zs = pea.allouer_salles(u.salles_2024.astype(int), proj.besoin_salles, cap)
    except AssertionError as e:      # le solveur n'a pas fini en « Optimal » : scénario non réalisable
        return Resultat(p, pd.DataFrame(), {}, [], False, f"Scénario non résolu par le solveur : {e}")
    assert tm.maitres_2030.sum() == cur.sum() + tm.recrues_affectees.sum(), "conservation des maîtres"
    assert tm.redeploye_sortant.sum() == tm.redeploye_entrant.sum(), "déplacements non équilibrés"
    assert (ts.salles_a_construire.sum() <= cap) and (ts.salles_2030 >= ts.salles_2024).all()

    prov = proj.join(tm.drop(columns=["besoin_maitres"]).add_prefix("m_")).join(ts.drop(columns=["besoin_salles"]).add_prefix("s_"))
    prov["maitres_2024"] = u.maitres_2024
    prov["salles_2024"] = u.salles_2024
    prov["a_rouvrir"] = u.a_rouvrir
    prov["code_region_nouveau"] = u.code_region_nouveau
    prov["nom_region_nouveau"] = u.nom_region_nouveau
    acc = pd.concat([prov.eleves_2030, ts.salles_2030 * p.norme_salle, tm.maitres_2030 * p.norme_maitre], axis=1).min(axis=1)
    prov["eleves_accueillis"] = acc.astype(int)
    reg = u.code_region_nouveau
    inter = sum(q for (i, j, q) in info["flux"] if reg[i] != reg[j])
    s = {
        "eleves_2030": int(proj.eleves_2030.sum()),
        "besoin_maitres": int(proj.besoin_maitres.sum()), "maitres_2024": int(u.maitres_2024.sum()),
        "maitres_apres_departs": int(cur.sum()), "recrues_disponibles": recrues,
        "recrues_affectees": int(tm.recrues_affectees.sum()), "maitres_redeployes": int(tm.redeploye_sortant.sum()),
        "dont_entre_regions": int(inter), "maitres_km": round(_km_flux(info["flux"])),
        "km_moyen_par_maitre": round(_km_flux(info["flux"]) / max(1, int(tm.redeploye_sortant.sum())), 1), "manque_maitres_avant": int((proj.besoin_maitres - cur).clip(lower=0).sum()),
        "manque_maitres_apres": int(tm.manque_restant.sum()), "provinces_maitres_non_couvertes": int((tm.manque_restant > 0).sum()),
        "couverture_maitres_min": float(tm.couverture.min()),
        "besoin_salles": int(proj.besoin_salles.sum()), "salles_2024": int(u.salles_2024.sum()),
        "salles_a_ajouter_besoin": ecart_total, "capacite_salles": cap, "salles_construites": int(ts.salles_a_construire.sum()),
        "manque_salles_avant": int((proj.besoin_salles - u.salles_2024).clip(lower=0).sum()),
        "manque_salles_apres": int(ts.manque_restant.sum()), "provinces_salles_non_couvertes": int((ts.manque_restant > 0).sum()),
        "couverture_salles_min": float(ts.couverture.min()),
        "eleves_accueillis": int(acc.sum()), "part_accueillie": round(float(acc.sum() / proj.eleves_2030.sum()), 4),
        "statut_maitres": f"{info['statut_etape1']}/{info['statut_etape2']}", "statut_salles": "Optimal/Optimal",
    }
    r = Resultat(p, prov, s, info["flux"], True, "Résolu : solveur « Optimal » aux deux étapes.")
    if utiliser_cache:
        _ecrire_cache(cle, r)
    return r


def _km_flux(flux) -> float:
    from . import allocation_distance as ad
    return ad.km_total_flux(flux)


def en_47(prov: pd.DataFrame) -> pd.DataFrame:
    """Restitution à 47 provinces avec la fonction du Rôle 2 (Soum et Tapoa : valeur non divisible, signalée)."""
    t = pea.vers_47(prov.reset_index(drop=True), donnees().panel_public)
    return t


def _ecrire_cache(cle: str, r: Resultat) -> None:
    CACHE.mkdir(parents=True, exist_ok=True)
    r.provinces.to_csv(CACHE / f"{cle}.csv", index=False, sep=";", encoding="utf-8")
    (CACHE / f"{cle}.json").write_text(json.dumps({"parametres": asdict(r.parametres), "synthese": r.synthese, "flux": r.flux,
                                                    "message": r.message}, ensure_ascii=False), encoding="utf-8")


def _lire_cache(cle: str, p: Parametres) -> Resultat:
    j = json.loads((CACHE / f"{cle}.json").read_text(encoding="utf-8"))
    prov = pd.read_csv(CACHE / f"{cle}.csv", sep=";", dtype={CLE: str, "code_region_nouveau": str})
    prov.index = prov[CLE].values
    return Resultat(p, prov, j["synthese"], [tuple(x) for x in j["flux"]], True, j["message"])
