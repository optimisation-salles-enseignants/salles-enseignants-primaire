"""Diagnostic provincial du primaire sur les 47 nouvelles provinces : ratios, ecarts a la norme,
typologie K-Means, provinces a rouvrir.

Entree : panel province x annee (construire_panel_provinces.py), 47 provinces x 8 annees.
Sorties (dossier de sortie) : tables CSV et graphiques PNG.

Parametres modifiables en tete de fichier. Les normes sont des hypotheses affichees :
- NORME_MAITRE = 50 eleves par maitre tenant classe (norme de reference retenue, source officielle non trouvee) ;
- CIBLES_MAITRE = 45 et 40 : objectifs a atteindre, pas des normes ;
- NORME_SALLE = 45 eleves par salle : hypothese, aucune norme officielle trouvee pour le primaire.

Les annuaires ne donnent des chiffres que pour les 45 anciennes provinces. Soum et Tapoa se scindent chacune
en deux nouvelles provinces : leurs chiffres ne sont pas divisibles. Les deux nouvelles provinces portent donc
la meme valeur (colonne chiffres_non_divisibles = 1) et les totaux et la typologie sont calcules sur une seule
ligne par ancienne province, pour ne rien compter deux fois. Les valeurs absentes restent vides.

Lancement : python diagnostic_provincial.py <panel.csv> <dossier_sortie>
"""
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

# ---- PARAMETRES (modifiables) ----
ANNEE_BASE = "2024-2025"
ANNEE_REF_TAUX = "2020-2021"
NORME_MAITRE = 50
CIBLES_MAITRE = (45, 40)
NORME_SALLE = 45
NORME_SALLE_REF = 50     # seuil affiche sur le graphique eleves par salle (reference 50 ; 45 et 40 en pointilles)
CIBLES_SALLE = (45, 40)
SEUIL_FERMEE = 0.6       # taux 2024-25 / taux 2020-21 en dessous : province a rouvrir
GRAINE = 42
K_MIN, K_MAX = 2, 6
SEP = ";"
ETIQUETTE = ""          # "", "public" ou "prive" : suffixe des fichiers et mention dans les titres
VERSION = "v2"
SUF, MENTION = "", ""
CLE = "code_province_ancien"
CLE47 = "code_province_nouveau"
NUM = ["nb_eleves", "nb_salles_classe", "enseignants_tenant_classe", "total_enseignants",
       "fonction_suppleant", "taux_brut_scolarisation", "pct_eleves_3_a_5_km",
       "pct_eleves_plus_de_5_km", "murs_etat_mauvais", "toiture_etat_mauvais"]


def charger(chemin: Path) -> pd.DataFrame:
    """Lit le panel (47 provinces x annees) et convertit les colonnes numeriques."""
    d = pd.read_csv(chemin, sep=SEP, dtype=str, keep_default_na=False)
    for c in NUM:
        d[c] = pd.to_numeric(d[c], errors="coerce")
    d["annee_debut"] = d.annee_scolaire.str[:4].astype(int)
    d["eleves_par_maitre"] = d.nb_eleves / d.enseignants_tenant_classe
    d["eleves_par_salle"] = d.nb_eleves / d.nb_salles_classe
    return d


def unites_de_calcul(d: pd.DataFrame) -> pd.DataFrame:
    """Une ligne par ancienne province et par annee (evite de compter Soum et Tapoa deux fois)."""
    return d.drop_duplicates([CLE, "annee_scolaire"])


def diagnostic_base(d: pd.DataFrame) -> pd.DataFrame:
    """Diagnostic de l'annee de base pour les 47 provinces : ecarts a la norme, besoins, taux, fermeture."""
    b = d[d.annee_scolaire == ANNEE_BASE].copy()
    for n in (NORME_MAITRE,) + tuple(CIBLES_MAITRE):
        besoin = b.nb_eleves / n
        b[f"maitres_manquants_{n}"] = (besoin - b.enseignants_tenant_classe).clip(lower=0).round(0)
        b[f"maitres_en_surplus_{n}"] = (b.enseignants_tenant_classe - besoin).clip(lower=0).round(0)
    b[f"salles_manquantes_{NORME_SALLE}"] = (b.nb_eleves / NORME_SALLE - b.nb_salles_classe).clip(lower=0).round(0)
    b["ecart_maitre_vs_norme"] = (b.eleves_par_maitre - NORME_MAITRE).round(1)
    t0 = d[d.annee_scolaire == ANNEE_REF_TAUX].drop_duplicates(CLE).set_index(CLE).taux_brut_scolarisation
    b["taux_2020_2021"] = b[CLE].map(t0)
    b["rapport_taux_2024_sur_2020"] = (b.taux_brut_scolarisation / b.taux_2020_2021).round(3)
    b["a_rouvrir"] = (b.rapport_taux_2024_sur_2020 < SEUIL_FERMEE).where(b.rapport_taux_2024_sur_2020.notna()).astype("Int64")   # vide si taux 2020 absent ou nul
    b["pct_plus_de_3_km"] = (b.pct_eleves_3_a_5_km + b.pct_eleves_plus_de_5_km).round(2)
    return b


def dispersion_regions(u: pd.DataFrame, col: str) -> dict:
    """H1 : part de la variance entre provinces expliquee par la region actuelle (eta carre)."""
    x = u[[col, "code_region_nouveau"]].dropna()
    total = ((x[col] - x[col].mean()) ** 2).sum()
    entre = sum(len(g) * (g[col].mean() - x[col].mean()) ** 2 for _, g in x.groupby("code_region_nouveau"))
    return {"variable": col, "part_variance_entre_regions": round(float(entre / total), 3),
            "part_variance_dans_regions": round(float(1 - entre / total), 3)}


def typologie(b: pd.DataFrame):
    """K-Means sur 45 unites (une par ancienne province), indicateurs standardises, k par silhouette.
    Les groupes sont ensuite reportes sur les 47 provinces."""
    u = b.drop_duplicates(CLE).copy()
    u["part_suppleants"] = u.fonction_suppleant / u.total_enseignants
    u["part_murs_mauvais"] = u.murs_etat_mauvais / u.nb_salles_classe
    cols = ["eleves_par_maitre", "eleves_par_salle", "taux_brut_scolarisation",
            "pct_plus_de_3_km", "part_suppleants", "part_murs_mauvais"]
    x = u[cols].dropna()
    z = StandardScaler().fit_transform(x)
    scores = {}
    for k in range(K_MIN, K_MAX + 1):
        km = KMeans(n_clusters=k, n_init=10, random_state=GRAINE).fit(z)
        scores[k] = round(float(silhouette_score(z, km.labels_)), 3)
    k_opt = max(scores, key=scores.get)
    km = KMeans(n_clusters=k_opt, n_init=10, random_state=GRAINE).fit(z)
    u.loc[x.index, "groupe"] = km.labels_
    profil = u.groupby("groupe")[cols].mean().round(2)
    profil["nb_unites_calcul"] = u.groupby("groupe").size()
    b = b.merge(u[[CLE, "groupe", "part_suppleants", "part_murs_mauvais"]], on=CLE, how="left")
    return b, profil, scores, k_opt


def graphiques(d, b, sortie: Path):
    s = b.sort_values("eleves_par_maitre")
    fig, ax = plt.subplots(figsize=(8, 11))
    non_div = s.chiffres_non_divisibles == "1"
    couleurs = ["#c0392b" if v > NORME_MAITRE else "#2c7fb8" for v in s.eleves_par_maitre]
    barres = ax.barh(s.nom_province_nouveau, s.eleves_par_maitre, color=couleurs)
    for bar, nd in zip(barres, non_div):
        if nd:
            bar.set_hatch("//"); bar.set_edgecolor("white")
    for nom, v in zip(s.nom_province_nouveau, s.eleves_par_maitre):
        if pd.isna(v):
            ax.text(0.5, nom, "aucune école ou donnée absente", va="center", fontsize=6, color="gray")
    ax.axvline(NORME_MAITRE, color="black", lw=1.2, label=f"Norme ({NORME_MAITRE})")
    for c in CIBLES_MAITRE:
        ax.axvline(c, color="gray", lw=0.8, ls="--")
    ax.set_xlabel("Élèves par maître tenant classe, 2024-2025")
    ax.set_title(f"Élèves par maître{MENTION}, 47 provinces (rouge : au-dessus de la norme ;\nhachuré : valeur de l'ancienne province, non divisible)", fontsize=10)
    ax.tick_params(axis="y", labelsize=7); ax.legend(); fig.tight_layout()
    fig.savefig(sortie / f"graphique_ratio_maitre_2024-2025{SUF}.png", dpi=130); plt.close(fig)


    sl = b.sort_values("eleves_par_salle")
    fig, ax = plt.subplots(figsize=(8, 11))
    couleurs = ["#c0392b" if v > NORME_SALLE_REF else "#2c7fb8" for v in sl.eleves_par_salle]
    barres = ax.barh(sl.nom_province_nouveau, sl.eleves_par_salle, color=couleurs)
    for bar, nd in zip(barres, sl.chiffres_non_divisibles == "1"):
        if nd:
            bar.set_hatch("//"); bar.set_edgecolor("white")
    for nom, v in zip(sl.nom_province_nouveau, sl.eleves_par_salle):
        if pd.isna(v):
            ax.text(0.5, nom, "aucune école ou donnée absente", va="center", fontsize=6, color="gray")
    ax.axvline(NORME_SALLE_REF, color="black", lw=1.2, label=f"Référence ({NORME_SALLE_REF})")
    for c in CIBLES_SALLE:
        ax.axvline(c, color="gray", lw=0.8, ls="--")
    ax.set_xlabel("Élèves par salle de classe, 2024-2025 (50 = hypothèse de référence ; 45 et 40 en pointillés)")
    ax.set_title(f"Élèves par salle{MENTION}, 47 provinces (rouge : au-dessus de la référence ;\nhachuré : valeur de l'ancienne province, non divisible)", fontsize=10)
    ax.tick_params(axis="y", labelsize=7); ax.legend(); fig.tight_layout()
    fig.savefig(sortie / f"graphique_ratio_salle_2024-2025{SUF}.png", dpi=130); plt.close(fig)

    u = unites_de_calcul(d)
    g = u.groupby("annee_scolaire").agg(el=("nb_eleves", "sum"), mt=("enseignants_tenant_classe", "sum"),
                                         sa=("nb_salles_classe", "sum")).reset_index()
    g["maitre"] = g.el / g.mt; g["salle"] = g.el / g.sa
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.plot(g.annee_scolaire, g.maitre, marker="o", label="Élèves par maître tenant classe")
    ax.plot(g.annee_scolaire, g.salle, marker="s", label="Élèves par salle")
    ax.axhline(NORME_MAITRE, color="black", lw=1, ls=":")
    ax.set_title(f"Ratios nationaux{MENTION} (sommes avant division, sans double compte)")
    ax.tick_params(axis="x", rotation=40); ax.legend(); fig.tight_layout()
    fig.savefig(sortie / f"graphique_tendance_nationale{SUF}.png", dpi=130); plt.close(fig)

    fig, ax = plt.subplots(figsize=(7.5, 5.5))
    ax.scatter(b.eleves_par_salle, b.eleves_par_maitre, c=b.groupe, cmap="tab10", s=55)
    for _, r in b.iterrows():
        if pd.notna(r.groupe) and (r.eleves_par_maitre > 60 or r.eleves_par_maitre < 41):
            ax.annotate(r.nom_province_nouveau, (r.eleves_par_salle, r.eleves_par_maitre), fontsize=6)
    ax.set_xlabel("Élèves par salle"); ax.set_ylabel("Élèves par maître tenant classe")
    ax.set_title(f"Typologie K-Means des provinces{MENTION} (2024-2025)")
    fig.tight_layout(); fig.savefig(sortie / f"graphique_groupes_kmeans{SUF}.png", dpi=130); plt.close(fig)


if __name__ == "__main__":
    panel, sortie = Path(sys.argv[1]), Path(sys.argv[2])
    if len(sys.argv) > 3:                       # diagnostic d'un statut : python diagnostic_provincial.py panel sortie public
        ETIQUETTE, VERSION = sys.argv[3], "v1"
        SUF, MENTION = f"-{ETIQUETTE}", f" ({'public' if ETIQUETTE == 'public' else 'privé'})"
    sortie.mkdir(parents=True, exist_ok=True)
    d = charger(panel)
    assert d[CLE47].nunique() == 47 and len(d) == 47 * 8, "panel 47 provinces x 8 annees attendu"
    b = diagnostic_base(d)
    u = b.drop_duplicates(CLE)
    print("controle 2024-25 (une ligne par ancienne province) :", int(u.nb_eleves.sum()), "eleves,",
          int(u.nb_salles_classe.sum()), "salles,", int(u.enseignants_tenant_classe.sum()), "maitres tenant classe")
    b, profil, scores, k_opt = typologie(b)
    print("silhouette par k :", scores, "-> k =", k_opt)
    print(dispersion_regions(u, "eleves_par_maitre"), dispersion_regions(u, "eleves_par_salle"))
    graphiques(d, b, sortie)
    b.to_csv(sortie / f"EQ_04-analyse_D3_analyst_diagnostic-provinces-2024-2025{SUF}_{VERSION}.csv", sep=SEP, index=False)
    profil.to_csv(sortie / f"EQ_04-analyse_D3_analyst_profils-groupes{SUF}_{VERSION}.csv", sep=SEP)
    d.to_csv(sortie / f"EQ_04-analyse_D3_analyst_ratios-province-annee{SUF}_{VERSION}.csv", sep=SEP, index=False)
    print(profil.to_string())
