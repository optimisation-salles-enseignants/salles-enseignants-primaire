"""Construit le panel province x annee scolaire (2017-2018 a 2024-2025) pour la modelisation.

Entrees (lues, jamais modifiees) : tables de 02_DONNEES/03_transformation (version v2).
Sortie : un CSV (separateur ;, UTF-8) avec une ligne par nouvelle province et par annee scolaire.

Regles :
- calculs sur les 45 anciennes provinces (code_province_ancien) ;
- passage aux 47 nouvelles provinces : Soum et Tapoa donnent chacune deux lignes avec la meme
  valeur, marquees chiffres_non_divisibles = 1 (aucune division des chiffres) ;
- les valeurs absentes de la source restent vides, aucune n'est comblee.

Lancement (depuis la racine du projet) :
    python construire_panel_provinces.py [racine] [dossier_sortie]
"""
import sys
from pathlib import Path

import pandas as pd

SEP = ";"
CLE = "code_province_ancien"
ANNEES = [f"{a}-{a + 1}" for a in range(2017, 2025)]


def lire(chemin: Path) -> pd.DataFrame:
    """Lit un CSV en texte, sans transformer les valeurs vides."""
    return pd.read_csv(chemin, sep=SEP, dtype=str, keep_default_na=False)


def trouver(dossier: Path, description: str) -> Path:
    """Retrouve une table v2 par sa description (nom de fichier sans le prefixe)."""
    trouves = sorted(dossier.glob(f"*_{description}_v2.csv"))
    if not trouves:
        raise FileNotFoundError(f"table introuvable : {description} dans {dossier}")
    return trouves[-1]


def en_nombre(serie: pd.Series) -> pd.Series:
    return pd.to_numeric(serie, errors="coerce")


def indicateurs_provinciaux(df, theme, modalite, indicateurs, sexe=None):
    """Extrait des indicateurs de la serie longue (niveau province) en table large."""
    x = df[(df.niveau == "province") & (df.theme == theme)
           & (df.modalite == modalite) & (df.indicateur.isin(indicateurs))]
    if sexe:
        x = x[x.sexe == sexe]
    x = x.assign(v=en_nombre(x.valeur))
    large = x.pivot_table(index=["code_ancien", "annee_scolaire"], columns="indicateur",
                          values="v", aggfunc="first").reset_index()
    return large.rename(columns={"code_ancien": CLE})


def construire(racine: Path) -> pd.DataFrame:
    tr = racine / "02_DONNEES" / "03_transformation"
    principale = lire(trouver(tr, "primaire-province-annee"))
    series = lire(trouver(tr / "reserve", "series-provinciales-primaire"))
    compl = lire(trouver(tr / "reserve", "series-complementaires-primaire"))
    corresp = lire(trouver(tr, "correspondance-ancien-nouveau"))

    n_avant = len(principale)
    enseignants = indicateurs_provinciaux(series, "enseignants", "Public+Privé",
                                          ["fonction_suppleant", "fonction_directeur"], "Total")
    salles = indicateurs_provinciaux(compl, "salles-nature-etat", "Public+Privé",
                                     ["murs_etat_mauvais", "toiture_etat_mauvais"])

    t = principale.drop(columns=["nb_maitres", "eleves_par_salle_calcule", "codes_province_nouveau"])
    t = t.merge(enseignants, on=[CLE, "annee_scolaire"], how="left")
    t = t.merge(salles, on=[CLE, "annee_scolaire"], how="left")
    assert len(t) == n_avant, "la jointure a change le nombre de lignes"

    for c in ["nb_eleves", "nb_salles_classe", "enseignants_tenant_classe"]:
        t[c] = en_nombre(t[c])
    t["annee_debut"] = t.annee_scolaire.str[:4].astype(int)
    t["eleves_par_salle"] = (t.nb_eleves / t.nb_salles_classe).round(1)
    t["eleves_par_maitre_tenant_classe"] = (t.nb_eleves / t.enseignants_tenant_classe).round(1)

    # passage aux nouvelles provinces (une ancienne province peut en donner deux)
    g = corresp[[CLE, "codes_province_nouveau", "noms_province_nouveau",
                 "codes_region_nouveau", "noms_region_nouveau"]].copy()
    g["code_province_nouveau"] = g.codes_province_nouveau.str.split("|")
    g["nom_province_nouveau"] = g.noms_province_nouveau.str.split("|")
    g = g.drop(columns=["codes_province_nouveau", "noms_province_nouveau"])
    g = g.rename(columns={"codes_region_nouveau": "code_region_nouveau",
                          "noms_region_nouveau": "nom_region_nouveau"})
    t = t.drop(columns=["codes_region_nouveau"])
    t = t.merge(g, on=CLE, how="left")
    t = t.explode(["code_province_nouveau", "nom_province_nouveau"])

    t = t[t.annee_scolaire.isin(ANNEES)]
    return t.sort_values(["code_province_nouveau", "annee_debut"]).reset_index(drop=True)


def controles(panel: pd.DataFrame, racine: Path) -> None:
    """Verifie la taille et recalcule les totaux nationaux contre la serie publiee."""
    assert panel.code_province_nouveau.nunique() == 47, "47 nouvelles provinces attendues"
    assert panel.groupby("annee_scolaire").size().eq(47).all(), "47 lignes par annee attendues"
    series = lire(trouver(racine / "02_DONNEES" / "03_transformation" / "reserve",
                          "series-provinciales-primaire"))
    nat = series[(series.niveau == "national") & (series.theme == "ecoles-salles-maitres")
                 & (series.indicateur == "nb_eleves") & (series.modalite == "Total")]
    publie = en_nombre(nat.set_index("annee_scolaire").valeur)
    # somme sur les anciennes provinces (une ligne par ancienne province)
    base = panel.drop_duplicates([CLE, "annee_scolaire"])
    somme = base.groupby("annee_scolaire").nb_eleves.sum()
    for annee in ANNEES:
        assert somme[annee] == publie[annee], f"ecart sur le total national en {annee}"
    print("controles : 47 provinces x 8 annees =", len(panel), "lignes ; totaux nationaux identiques")


if __name__ == "__main__":
    racine = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    sortie = Path(sys.argv[2]) if len(sys.argv) > 2 else racine / "02_DONNEES" / "04_analyse"
    panel = construire(racine)
    controles(panel, racine)
    sortie.mkdir(parents=True, exist_ok=True)
    fichier = sortie / "EQ_04-analyse_D3_analyst_panel-provinces-annee_v2.csv"
    panel.to_csv(fichier, sep=SEP, index=False, encoding="utf-8")
    print("ecrit :", fichier.name, panel.shape)
