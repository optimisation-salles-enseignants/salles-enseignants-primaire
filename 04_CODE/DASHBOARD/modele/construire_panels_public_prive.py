"""Construit deux panels province x annee scolaire : un pour le public, un pour le prive (primaire).

Pourquoi : l'Etat ne peut construire des ecoles et affecter des enseignants que dans le public.
Les variables sont les memes que dans le panel total (construire_panel_provinces.py), calculees
statut par statut a partir des series publiees par statut (Public / Prive).

Regles (identiques au panel total) :
- calculs sur les 45 anciennes provinces ; passage aux 47 nouvelles provinces avec Soum et Tapoa
  dupliquees (chiffres_non_divisibles = 1) ;
- les valeurs absentes de la source restent vides ;
- la population 6-11 ans n'existe pas par statut : c'est celle de la province entiere ;
  taux_brut_scolarisation d'un statut = eleves du statut / population 6-11 ans (part du taux total).
- les colonnes OSM ne sont pas reprises (OSM n'a pas de statut).

Controles integres :
1. la meme methode, appliquee au total (Public+Prive), redonne exactement le panel total v2 ;
2. public + prive = total pour chaque variable additive, sur les 376 lignes.

Lancement : python construire_panels_public_prive.py <racine> <dossier_sortie>
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from construire_panel_provinces import (ANNEES, CLE, SEP, construire, en_nombre,
                                        indicateurs_provinciaux, lire, trouver)

PREFIXE = "EQ_04-analyse_D3_analyst_"
# modalite de la source selon le theme, pour chaque statut
MODALITES = {
    "Public": dict(ecoles="Public", enseignants="Public", distance="Public", salles="Public"),
    "Privé": dict(ecoles="Privé", enseignants="Privé", distance="Privé", salles="Privé"),
    "Total": dict(ecoles="Total", enseignants="Public+Privé", distance="Public+Privé", salles="Public+Privé"),
}
ADDITIVES = ["nb_ecoles", "nb_salles_classe", "nb_groupes_pedagogiques", "nb_eleves", "total_enseignants",
             "enseignants_tenant_classe", "enseignants_femmes", "fonction_directeur", "fonction_suppleant",
             "murs_etat_mauvais", "toiture_etat_mauvais", "nb_eleves_base_distance"]
TAUX_ABSENT = "population_non_disponible_avant_2020"


def table_statut(racine: Path, statut: str) -> pd.DataFrame:
    """Une ligne par province (ancienne) et par annee, pour un statut (Public, Prive ou Total)."""
    m = MODALITES[statut]
    tr = racine / "02_DONNEES" / "03_transformation"
    principale = lire(trouver(tr, "primaire-province-annee"))
    series = lire(trouver(tr / "reserve", "series-provinciales-primaire"))
    compl = lire(trouver(tr / "reserve", "series-complementaires-primaire"))
    corresp = lire(trouver(tr, "correspondance-ancien-nouveau"))
    n_avant = len(principale)

    ids = ["annee_scolaire", "code_region_ancienne", "nom_region_ancienne", CLE, "nom_province_ancien",
           "relation_ancien_nouveau", "chiffres_non_divisibles", "population_6_11", "statut_taux_brut"]
    t = principale[ids].copy()
    t["statut_etablissement"] = statut

    def ajouter(t, df, theme, modalite, source_ind, noms, sexe=None):
        x = indicateurs_provinciaux(df, theme, modalite, source_ind, sexe).rename(columns=noms)
        avant = len(t)
        t = t.merge(x, on=[CLE, "annee_scolaire"], how="left", validate="one_to_one")
        assert len(t) == avant, f"la jointure {theme} a change le nombre de lignes"
        return t

    t = ajouter(t, series, "ecoles-salles-maitres", m["ecoles"],
                ["nb_ecoles", "nb_salles_classe", "nb_groupes_pedagogiques", "nb_eleves", "ratio_eleves_par_maitre"],
                {"ratio_eleves_par_maitre": "ratio_eleves_par_maitre_publie"})
    t = ajouter(t, series, "enseignants", m["enseignants"],
                ["total_enseignants", "dont_tenant_classe", "fonction_directeur", "fonction_suppleant"],
                {"dont_tenant_classe": "enseignants_tenant_classe"}, "Total")
    t = ajouter(t, series, "enseignants", m["enseignants"], ["total_enseignants"],
                {"total_enseignants": "enseignants_femmes"}, "Femmes")
    t = ajouter(t, series, "distance-ecole", m["distance"],
                ["pct_moins_de_3_km", "pct_3_a_5_km", "pct_plus_de_5_km", "nb_eleves"],
                {"pct_moins_de_3_km": "pct_eleves_moins_de_3_km", "pct_3_a_5_km": "pct_eleves_3_a_5_km",
                 "pct_plus_de_5_km": "pct_eleves_plus_de_5_km", "nb_eleves": "nb_eleves_base_distance"})
    t = ajouter(t, compl, "salles-nature-etat", m["salles"], ["murs_etat_mauvais", "toiture_etat_mauvais"], {})
    assert len(t) == n_avant

    t["population_6_11"] = en_nombre(t.population_6_11)
    t["annee_debut"] = t.annee_scolaire.str[:4].astype(int)
    t["eleves_par_salle"] = (t.nb_eleves / t.nb_salles_classe).round(1)
    t["eleves_par_maitre_tenant_classe"] = (t.nb_eleves / t.enseignants_tenant_classe).round(1)
    t["taux_brut_scolarisation"] = (t.nb_eleves / t.population_6_11).round(6)

    # passage aux 47 nouvelles provinces (comme le panel total)
    g = corresp[[CLE, "codes_province_nouveau", "noms_province_nouveau", "codes_region_nouveau", "noms_region_nouveau"]].copy()
    g["code_province_nouveau"] = g.codes_province_nouveau.str.split("|")
    g["nom_province_nouveau"] = g.noms_province_nouveau.str.split("|")
    g = g.rename(columns={"codes_region_nouveau": "code_region_nouveau", "noms_region_nouveau": "nom_region_nouveau"})
    g = g.drop(columns=["codes_province_nouveau", "noms_province_nouveau"])
    t = t.merge(g, on=CLE, how="left").explode(["code_province_nouveau", "nom_province_nouveau"])
    t = t[t.annee_scolaire.isin(ANNEES)]
    return t.sort_values(["code_province_nouveau", "annee_debut"]).reset_index(drop=True)


def controles(pub: pd.DataFrame, pri: pd.DataFrame, tot: pd.DataFrame, panel_total: pd.DataFrame) -> None:
    """Controle 1 : le total reconstruit = panel total v2. Controle 2 : public + prive = total."""
    cles = ["code_province_nouveau", "annee_scolaire"]
    commun = [c for c in tot.columns if c in panel_total.columns and c not in cles + ["population_6_11", "statut_taux_brut"]
              and c not in ("statut_etablissement",)]
    a = tot.set_index(cles); b = panel_total.set_index(cles)
    nb_ecarts = 0
    for c in commun:
        x, y = pd.to_numeric(a[c], errors="coerce"), pd.to_numeric(b.loc[a.index, c], errors="coerce")
        if x.notna().any() or y.notna().any():
            d = (x - y).abs()
            tol = 1e-3 if c in ("eleves_par_salle", "eleves_par_maitre_tenant_classe", "taux_brut_scolarisation") else 0.0
            # valeurs vides : doivent l'etre des deux cotes
            assert (x.isna() == y.isna()).all(), f"valeurs vides differentes pour {c}"
            nb_ecarts += int((d > tol + 1e-9).sum())
            assert (d.fillna(0) <= tol + 1e-9).all(), f"ecart avec le panel total pour {c}"
    print(f"controle 1 : methode appliquee au total = panel total v2 ({len(commun)} colonnes comparees, {nb_ecarts} ecart)")
    p, q, t = pub.set_index(cles), pri.set_index(cles), tot.set_index(cles)
    for c in ADDITIVES:
        s = pd.to_numeric(p[c], errors="coerce") + pd.to_numeric(q[c], errors="coerce")
        d = (s - pd.to_numeric(t[c], errors="coerce")).abs()
        assert (d.dropna() == 0).all(), f"public + prive different du total pour {c}"
        assert (s.isna() == t[c].isna()).all(), f"valeurs vides incoherentes pour {c}"
    print(f"controle 2 : public + prive = total sur {len(ADDITIVES)} variables additives, {len(pub)} lignes")


if __name__ == "__main__":
    racine = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    sortie = Path(sys.argv[2]) if len(sys.argv) > 2 else racine / "02_DONNEES" / "04_analyse"
    pub, pri, tot = (table_statut(racine, s) for s in ("Public", "Privé", "Total"))
    assert all(len(x) == 376 and x.code_province_nouveau.nunique() == 47 for x in (pub, pri, tot))
    controles(pub, pri, tot, construire(racine))
    sortie.mkdir(parents=True, exist_ok=True)
    for x, nom in ((pub, "public"), (pri, "prive")):
        f = sortie / f"{PREFIXE}panel-provinces-annee-{nom}_v1.csv"
        x.to_csv(f, sep=SEP, index=False, encoding="utf-8")
        print("ecrit :", f.name, x.shape, "| valeurs vides :", int(x.isna().sum().sum()))
