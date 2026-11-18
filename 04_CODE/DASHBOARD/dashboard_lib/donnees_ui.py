"""Données affichées par le tableau de bord (lecture seule des CSV du projet)."""
from __future__ import annotations

from functools import lru_cache

import numpy as np
import pandas as pd

from .chemins import ANALYSE, RACINE, trouver

SEP = ";"
CLE = "code_province_ancien"


@lru_cache(maxsize=1)
def diagnostic47() -> pd.DataFrame:
    """Diagnostic 2024-2025 (public), 47 lignes. Soum et Tapoa : chiffres non divisibles, signalés."""
    d = pd.read_csv(trouver(ANALYSE, "*diagnostic-provinces-2024-2025-public_v1.csv"), sep=SEP, encoding="utf-8-sig", dtype={CLE: str})
    d["eleves_plus_3km"] = d.pct_plus_de_3_km / 100 * d.nb_eleves_base_distance
    return d


@lru_cache(maxsize=1)
def diagnostic45() -> pd.DataFrame:
    """Une ligne par ancienne province : sert aux totaux et à la carte (rien n'est compté deux fois)."""
    return diagnostic47().drop_duplicates(CLE).set_index(CLE, drop=False)


@lru_cache(maxsize=1)
def panel47() -> pd.DataFrame:
    """Panel annuel complet du public : une ligne par province (47) et par année scolaire, de 2017-2018 à 2024-2025."""
    return pd.read_csv(trouver(ANALYSE, "*panel-provinces-annee-public_v1.csv"), sep=SEP, encoding="utf-8-sig", dtype={CLE: str})


def annees() -> list:
    return sorted(panel47().annee_scolaire.unique())


@lru_cache(maxsize=16)
def diagnostic_annee(an: str) -> pd.DataFrame:
    """Diagnostic d'une année scolaire quelconque, 47 lignes, mêmes colonnes que diagnostic47().
    Pour la dernière année : le fichier du Rôle 2 tel quel. Pour les autres : recalcul avec les mêmes définitions
    (élèves ÷ enseignants tenant classe ; part à plus de 3 km = 100 − part à moins de 3 km), vérifiées sur 2024-2025."""
    P, K = panel47(), ["code_province_ancien", "code_province_nouveau"]
    d = diagnostic47().copy() if an == annees()[-1] else P[P.annee_scolaire == an].copy()
    if an != annees()[-1]:
        d["eleves_par_maitre"] = d.nb_eleves / d.enseignants_tenant_classe
        d["pct_plus_de_3_km"] = 100 - d.pct_eleves_moins_de_3_km
        d["eleves_plus_3km"] = d.pct_plus_de_3_km / 100 * d.nb_eleves_base_distance
        ref = P[P.annee_scolaire == "2020-2021"].set_index(K).taux_brut_scolarisation
        ratio = d.set_index(K).taux_brut_scolarisation / ref.reindex(d.set_index(K).index).values
        d["a_rouvrir"] = (ratio < 0.6).fillna(False).astype(int).values      # même règle que le Rôle 2 : taux sous 60 % de celui de 2020
        d["groupe"] = np.nan
    # évolution des effectifs sur 3 ans (ou depuis le début de la série si elle est plus courte)
    an_ref = annees()[max(0, annees().index(an) - 3)]
    e0 = P[P.annee_scolaire == an_ref].drop_duplicates(CLE).set_index(CLE).nb_eleves
    e0 = e0.where(e0 > 0)
    d["evol_eleves"] = (d.nb_eleves / d[CLE].map(e0) - 1) * 100 if an_ref != an else np.nan
    d.attrs["annee_reference_evolution"] = an_ref
    return d


def diagnostic_annee45(an: str) -> pd.DataFrame:
    return diagnostic_annee(an).drop_duplicates(CLE).set_index(CLE, drop=False)


INDICATEURS_SERIE = {
    "Élèves par enseignant": ("ratio", "nb_eleves", "enseignants_tenant_classe", "élèves"),
    "Élèves par salle": ("ratio", "nb_eleves", "nb_salles_classe", "élèves"),
    "Effectifs (indice 100 en 2017-2018)": ("indice", "nb_eleves", None, "indice"),
    "Élèves à plus de 3 km (%)": ("part3", None, None, "%"),
    "Taux brut de scolarisation (%)": ("taux", "nb_eleves", "population_6_11", "%"),
}


def serie(indicateur: str) -> tuple[pd.DataFrame, pd.Series]:
    """Valeurs par année (lignes) et ancienne province (colonnes), plus la série nationale (somme sur somme, provinces renseignées)."""
    kind, a, b, _ = INDICATEURS_SERIE[indicateur]
    P = panel47().drop_duplicates([CLE, "annee_scolaire"]).copy()
    P["_v"] = {"ratio": lambda: P[a] / P[b], "indice": lambda: P[a], "taux": lambda: P[a] / P[b] * 100,
               "part3": lambda: 100 - P.pct_eleves_moins_de_3_km}[kind]()
    M = P.pivot(index="annee_scolaire", columns=CLE, values="_v").replace([np.inf, -np.inf], np.nan)
    if kind == "indice":
        M = M.where(M > 0) / M.iloc[0].where(M.iloc[0] > 0) * 100
        tot = P.groupby("annee_scolaire").nb_eleves.sum()
        nat = tot / tot.iloc[0] * 100
    elif kind in ("ratio", "taux"):
        ok = P.dropna(subset=[a, b]).query(f"{b} > 0")
        g = ok.groupby("annee_scolaire")
        nat = g[a].sum() / g[b].sum() * (100 if kind == "taux" else 1)
    else:
        ok = P.dropna(subset=["pct_eleves_moins_de_3_km", "nb_eleves_base_distance"])
        g = ok.groupby("annee_scolaire")
        nat = 100 - (ok.pct_eleves_moins_de_3_km * ok.nb_eleves_base_distance).groupby(ok.annee_scolaire).sum() / g.nb_eleves_base_distance.sum()
    return M, nat


def besoin(d: pd.DataFrame, norme: int, colonne_eleves="nb_eleves", colonne_offre="enseignants_tenant_classe") -> pd.Series:
    return np.ceil(d[colonne_eleves] / norme) - d[colonne_offre]


@lru_cache(maxsize=1)
def profils() -> dict:
    """Libellés clairs des groupes (typologie K-Means du Rôle 2, graine 42) selon la charge moyenne en élèves par maître."""
    t = pd.read_csv(trouver(ANALYSE, "*profils-groupes-public_v1.csv"), sep=SEP, encoding="utf-8-sig")
    t = t.sort_values("eleves_par_maitre")
    noms = {}
    n = len(t)
    for rang, g in enumerate(t.groupe):
        noms[float(g)] = "Provinces les moins chargées" if rang == 0 else ("Provinces les plus chargées" if rang == n - 1 else "Provinces à charge intermédiaire")
    return noms


@lru_cache(maxsize=1)
def sources() -> pd.DataFrame:
    p = RACINE / "02_DONNEES" / "01_collecte" / "REGISTRE_SOURCES_v4.csv"
    if not p.exists():
        return pd.DataFrame(columns=["id_source", "producteur", "publication", "annee", "usage", "limites"])
    return pd.read_csv(p, sep=SEP, encoding="utf-8-sig", dtype=str).fillna("")


def fmt(n, d=0) -> str:
    if n is None or (isinstance(n, float) and np.isnan(n)):
        return "n.d."
    s = f"{n:,.{d}f}".replace(",", " ").replace(".", ",")
    return s


def pct(x, d=0) -> str:
    return fmt(x * 100, d) + " %"
