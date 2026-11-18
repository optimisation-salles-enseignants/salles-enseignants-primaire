"""Modèle appris : projection des effectifs d'élèves par province, à partir de l'historique 2017-2018 → 2024-2025.

Constat sur les données : deux régimes. Des provinces stables (+1 à 3 % par an) et des provinces touchées par la crise
(écoles fermées, effectifs tombés presque à zéro, puis reprise). Une simple tendance ne sait pas décrire cela.

Modèle (commun aux 45 provinces, régression ridge, résolution exacte, aucun tirage aléatoire) :
    Δy(t+1) = a + b · écart(t) + c · Δy(t)          avec y = log(effectif + 1000)
    écart(t) = plus haut niveau déjà observé − niveau actuel   (« retour vers le niveau d'avant la crise »)
    a = croissance courante ; b = vitesse de retour vers le niveau d'avant ; c = inertie de la dernière variation.
Le modèle apprend a, b, c sur toutes les transitions passées de toutes les provinces. La force de régularisation (λ)
est choisie par validation à origine glissante : on n'apprend qu'avec le passé, on prévoit des années non vues, puis on
compare à la référence « les effectifs restent ceux de la dernière année ».

Limite à dire : 8 années seulement, un choc en 2022-2023. Les intervalles sont donc larges et l'horizon 2030 est une extrapolation.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .chemins import ANALYSE, DASHBOARD, trouver

SORTIE = DASHBOARD / "modeles_entraines"
NOM = "modele_effectifs_v4"
PLANCHER = 1000.0                    # effectif nul = écoles fermées ; le log est calculé sur effectif + 1000
GRILLE_LAMBDA = (0.01, 0.1, 1.0, 10.0)
HORIZON_CIBLE = 6                    # 2024-2025 → 2030-2031, comme le reste du modèle (N_ANNEES = 6)


def historique() -> pd.DataFrame:
    """Province × année des effectifs totaux. Les moitiés d'une province éclatée portent le même chiffre : on garde une ligne."""
    t = pd.read_csv(trouver(ANALYSE, "*analyst_panel-provinces-annee_v2.csv"), sep=";")
    t = t.drop_duplicates(["annee_scolaire", "code_province_ancien"])
    return t.pivot(index="code_province_ancien", columns="annee_scolaire", values="nb_eleves").sort_index(axis=1)


def _y(H: pd.DataFrame) -> np.ndarray:
    return np.log(H.to_numpy(float) + PLANCHER)


def _comble(Y: np.ndarray) -> np.ndarray:
    """Une valeur manquante isolée (2022-2023 pour une province) est remplacée par la moyenne de ses voisines."""
    Y = Y.copy()
    for i, j in zip(*np.where(np.isnan(Y))):
        Y[i, j] = np.nanmean([Y[i, j - 1] if j > 0 else np.nan, Y[i, j + 1] if j + 1 < Y.shape[1] else np.nan])
    return Y


def _lignes(Y: np.ndarray):
    """Une ligne par transition (province, t→t+1) : variables (écart, variation précédente) et cible (variation suivante)."""
    X, c = [], []
    pic = np.maximum.accumulate(Y, axis=1)
    for t in range(1, Y.shape[1] - 1):
        X.append(np.column_stack([pic[:, t] - Y[:, t], Y[:, t] - Y[:, t - 1]]))
        c.append(Y[:, t + 1] - Y[:, t])
    return np.vstack(X), np.concatenate(c)


CANDIDATS = {                      # nom → variables utilisées (a = croissance, b = retour vers le pic, c = inertie)
    "croissance_commune": (1, 0, 0),
    "croissance_et_reprise": (1, 1, 0),
    "croissance_reprise_inertie": (1, 1, 1),
}


def apprendre(Y: np.ndarray, lam: float, masque=(1, 1, 1)) -> np.ndarray:
    """Coefficients (a, b, c) par ridge, sans pénaliser la constante ; les variables hors masque valent 0."""
    X, c = _lignes(Y)
    A = np.column_stack([np.ones(len(X)), X])
    P = lam * np.eye(3); P[0, 0] = 0.0
    m = np.array(masque, bool)
    coef = np.zeros(3)
    coef[m] = np.linalg.solve(A[:, m].T @ A[:, m] + P[np.ix_(m, m)] * len(A), A[:, m].T @ c)
    return coef


def prevoir(Y: np.ndarray, coef: np.ndarray, horizon: int) -> np.ndarray:
    """Prévision récursive du log-effectif à `horizon` années après la dernière colonne."""
    y, prev = Y[:, -1].copy(), Y[:, -1] - Y[:, -2]
    pic = Y.max(axis=1)
    for _ in range(horizon):
        d = coef[0] + coef[1] * (pic - y) + coef[2] * prev
        y, prev = y + d, d
        pic = np.maximum(pic, y)
    return y


def _evaluer(Y: np.ndarray, lam: float | None, masque=(1, 1, 1)):
    """Erreurs de toutes les prévisions à origine glissante. lam=None → référence « statu quo »."""
    n, sorties = Y.shape[1], []
    for origine in range(4, n):
        coef = None if lam is None else apprendre(Y[:, :origine], lam, masque)
        for h in range(1, n - origine + 1):
            prev = Y[:, origine - 1] if coef is None else prevoir(Y[:, :origine], coef, h)
            sorties.append((origine, h, prev, Y[:, origine - 1 + h]))
    return sorties


def _scores(sorties, H_brut: np.ndarray) -> dict:
    err = np.concatenate([np.abs(p - c) for _, _, p, c in sorties])
    # erreur sur le total national, en effectifs (ce que lit un décideur)
    nat = [abs((np.exp(p) - PLANCHER).sum() - (np.exp(c) - PLANCHER).sum()) / (np.exp(c) - PLANCHER).sum() for _, _, p, c in sorties]
    # erreur pondérée en effectifs : somme des écarts provinciaux ÷ total observé (lisible : « on se trompe de x % des élèves »)
    wape = [np.abs((np.exp(p) - PLANCHER) - (np.exp(c) - PLANCHER)).sum() / (np.exp(c) - PLANCHER).sum() for _, _, p, c in sorties]
    return {"erreur_provinces_pct_eleves": round(float(np.mean(wape)), 4), "erreur_nationale_moyenne": round(float(np.mean(nat)), 4),
            "erreur_log_moyenne": round(float(err.mean()), 4)}


@dataclass
class ModeleEffectifs:
    coef: list
    lam: float
    annees: list
    metriques: dict = field(default_factory=dict)
    ecarts_par_horizon: dict = field(default_factory=dict)
    empreinte_donnees: str = ""

    def projeter_effectifs(self, quantile: float = 0.5) -> pd.Series:
        """Effectifs prévus en 2030-2031. quantile : 0.1 (bas), 0.5 (central), 0.9 (haut) ; interpolé entre les deux."""
        H = historique()
        Y = _comble(_y(H))
        centre = prevoir(Y, np.array(self.coef), HORIZON_CIBLE)
        bas, med, haut = self.ecarts_cibles()
        decal = float(np.interp(quantile, [0.1, 0.5, 0.9], [bas, med, haut]))
        return pd.Series(np.maximum(np.exp(centre + decal) - PLANCHER, 0.0), index=H.index)

    def ecarts_cibles(self) -> tuple[float, float, float]:
        """Dispersion des erreurs apprise à l'horizon testé le plus long, élargie à l'horizon cible (racine du temps)."""
        h = max(int(k) for k in self.ecarts_par_horizon)
        a, b, c = self.ecarts_par_horizon[str(h)]
        f = (HORIZON_CIBLE / h) ** 0.5
        return a * f, b * f, c * f


def _empreinte(H: pd.DataFrame) -> str:
    return hashlib.sha256(H.to_numpy(float).tobytes()).hexdigest()[:16]


def entrainer() -> ModeleEffectifs:
    H = historique()
    Y = _comble(_y(H))
    Hb = H.to_numpy(float)
    ref = _evaluer(Y, None)
    sr = _scores(ref, Hb)
    essais = []                                      # (erreur, candidat, lambda)
    for nom, masque in CANDIDATS.items():
        for lam in GRILLE_LAMBDA:
            essais.append((_scores(_evaluer(Y, lam, masque), Hb)["erreur_provinces_pct_eleves"], nom, lam))
    essais.sort()
    erreur, nom, lam = essais[0]
    masque = CANDIDATS[nom]
    mod = _evaluer(Y, lam, masque)
    sm = _scores(mod, Hb)
    coef = apprendre(Y, lam, masque)
    bat = sm["erreur_provinces_pct_eleves"] < sr["erreur_provinces_pct_eleves"]
    par_h = {}
    for _, h, p, c in mod:
        par_h.setdefault(h, []).append(c - p)
    ecarts = {str(h): [float(np.quantile(np.concatenate(v), q)) for q in (0.1, 0.5, 0.9)] for h, v in par_h.items()}
    metriques = {
        "candidat_retenu": nom, "lambda_choisi": lam,
        "bat_le_statu_quo": bool(bat),
        "modele": sm, "reference_statu_quo": sr,
        "gain_erreur_provinces": round(1 - sm["erreur_provinces_pct_eleves"] / sr["erreur_provinces_pct_eleves"], 4),
        "nb_previsions_testees": int(len(mod)), "nb_annees_apprentissage_min": 4,
        "classement": [[round(e, 4), n, l] for e, n, l in essais[:8]],
        "coefficients": {"a_croissance": round(float(coef[0]), 4), "b_retour_vers_pic": round(float(coef[1]), 4), "c_inertie": round(float(coef[2]), 4)},
        "lecture": "erreur_provinces_pct_eleves : somme des écarts par province, en % du total d'élèves, sur des années que le modèle n'avait pas vues",
    }
    metriques["comparaison_methodes"] = comparer_methodes()
    return ModeleEffectifs([float(x) for x in coef], lam, list(H.columns), metriques, ecarts, _empreinte(H))


def comparer_methodes() -> dict:
    """Compare, sur des années non vues (2021-2022 → 2024-2025, population connue), les façons de projeter les effectifs.
    Chaque méthode prévoit l'effectif d'une province à h années ; l'erreur est la somme des écarts par province en % du total d'élèves."""
    t = pd.read_csv(trouver(ANALYSE, "*analyst_panel-provinces-annee_v2.csv"), sep=";").drop_duplicates(["annee_scolaire", "code_province_annee" if False else "code_province_ancien"])
    E = t.pivot(index="code_province_ancien", columns="annee_scolaire", values="nb_eleves")
    P = t.pivot(index="code_province_ancien", columns="annee_scolaire", values="population_6_11")
    ans = [c for c in E.columns if P[c].notna().all()]
    E, P = E[ans], P[ans]
    T = E / P
    erreurs = {"effectifs_constants": [], "taux_constant": [], "taux_moyen_2_ans": []}
    for o in range(1, len(ans)):
        for h in range(1, len(ans) - o):
            obs, pop = E.iloc[:, o + h].to_numpy(float), P.iloc[:, o + h].to_numpy(float)
            prev = {"effectifs_constants": E.iloc[:, o].to_numpy(float),
                    "taux_constant": T.iloc[:, o].to_numpy(float) * pop,
                    "taux_moyen_2_ans": T.iloc[:, max(0, o - 1):o + 1].mean(axis=1).to_numpy(float) * pop}
            for k, v in prev.items():
                ok = ~(np.isnan(v) | np.isnan(obs))
                erreurs[k].append(float(np.abs(v[ok] - obs[ok]).sum() / obs[ok].sum()))
    return {"periode": [ans[0], ans[-1]], "nb_previsions": len(erreurs["taux_constant"]),
            "erreur_moyenne": {k: round(float(np.mean(v)), 4) for k, v in erreurs.items()},
            "erreur_maximale": {k: round(float(np.max(v)), 4) for k, v in erreurs.items()}}


def enregistrer(m: ModeleEffectifs) -> None:
    SORTIE.mkdir(exist_ok=True)
    (SORTIE / f"{NOM}.json").write_text(json.dumps(m.__dict__, ensure_ascii=False, indent=1), encoding="utf-8")


def charger() -> ModeleEffectifs:
    """Charge le modèle enregistré ; le ré-entraîne si les données d'entrée ont changé."""
    f = SORTIE / f"{NOM}.json"
    if f.exists():
        m = ModeleEffectifs(**json.loads(f.read_text(encoding="utf-8")))
        if m.empreinte_donnees == _empreinte(historique()):
            return m
    m = entrainer()
    enregistrer(m)
    return m


if __name__ == "__main__":
    m = entrainer()
    enregistrer(m)
    print(json.dumps({"lambda": m.lam, "coef": m.coef, **m.metriques}, ensure_ascii=False, indent=1))
    print("écarts par horizon (10/50/90 %):", {h: [round(x, 3) for x in v] for h, v in m.ecarts_par_horizon.items()})
    tot = lambda q: int(m.projeter_effectifs(q).sum())
    print("Total 2030 bas/central/haut :", tot(0.1), tot(0.5), tot(0.9), "| 2024 :", int(historique().iloc[:, -1].sum()))
