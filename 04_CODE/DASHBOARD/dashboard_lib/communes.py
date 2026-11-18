"""Variante A : communes à examiner en priorité dans chaque province où il faut construire des salles.

Ce que ce module fait, et ne fait pas
- Il part du résultat du modèle (salles à construire par ancienne province) et liste les communes de la province.
- Il n'y a PAS de population par commune ni de données par école : on ne peut donc ni mesurer la demande locale ni nommer
  une école. Le classement est un INDICE, jamais un résultat chiffré.
- Seul indice disponible : la densité d'écoles OpenStreetMap (objets de type école pour 100 km²). OpenStreetMap ne couvre
  qu'environ un tiers des écoles : le classement n'est donc proposé que dans les provinces où la couverture est jugée
  « exploitable » (colonne statut_osm de couverture-osm-provinces). Ailleurs, les communes sont listées sans classement.
- La distance au chef-lieu de la province est donnée à titre d'information (logistique), à vol d'oiseau.

Sources : COD-AB v03 (limites administratives, chefs-lieux), OpenStreetMap (écoles), annuaires DGESS 2024-2025.
Les coordonnées d'une commune sont celles de son chef-lieu (les centres de surface ne sont pas renseignés dans le fichier).
"""
from __future__ import annotations

from functools import lru_cache

import numpy as np
import pandas as pd

from .chemins import RACINE, TRANSFORMATION, trouver



def _haversine(lat1, lon1, lat2, lon2) -> np.ndarray:
    p = np.pi / 180
    a = np.sin((lat2 - lat1) * p / 2) ** 2 + np.cos(lat1 * p) * np.cos(lat2 * p) * np.sin((lon2 - lon1) * p / 2) ** 2
    return 12742 * np.arcsin(np.sqrt(a))


@lru_cache(maxsize=1)
def communes() -> pd.DataFrame:
    """Une ligne par commune (351) : ancienne province, surface, position, écoles OSM, distance au chef-lieu de province."""
    c = pd.read_csv(trouver(TRANSFORMATION, "*correspondance-geo-communes_v2.csv"), sep=None, engine="python")
    ref = pd.read_csv(trouver(TRANSFORMATION, "*correspondance-ancien-nouveau_v2.csv"), sep=None, engine="python")
    o = pd.read_csv(trouver(TRANSFORMATION, "*ecoles-osm-localisees_v2.csv"), sep=None, engine="python")
    cov = pd.read_csv(trouver(TRANSFORMATION, "*couverture-osm-provinces_v2.csv"), sep=None, engine="python")
    # chefs-lieux propres (02_nettoyage) : niveau 2 = chefs-lieux de province, niveau 3 = communes
    k = pd.read_csv(trouver(RACINE / "02_DONNEES" / "02_nettoyage", "*chefs-lieux-propres*.csv"), sep=";",
                    usecols=["niveau", "longitude", "latitude", "code_province", "code_commune"], encoding="utf-8-sig")
    com = k[k.niveau == 3].drop_duplicates("code_commune").set_index("code_commune")
    prov = k[k.niveau == 2].drop_duplicates("code_province").set_index("code_province")
    com = com.rename(columns={"longitude": "x_coord", "latitude": "y_coord"})
    prov = prov.rename(columns={"longitude": "x_coord", "latitude": "y_coord"})

    ancien = {}
    for r in ref.itertuples():
        for n in str(r.codes_province_nouveau).split("|"):
            ancien[n.strip()] = r.code_province_ancien
    c["code_province_ancien"] = c.code_province_nouveau.map(ancien)
    c["lon"] = c.code_commune_nouveau.map(com.x_coord)
    c["lat"] = c.code_commune_nouveau.map(com.y_coord)
    c["lon_cl"] = c.code_province_nouveau.map(prov.x_coord)
    c["lat_cl"] = c.code_province_nouveau.map(prov.y_coord)
    c["km_chef_lieu"] = _haversine(c.lat, c.lon, c.lat_cl, c.lon_cl).round(0)
    ecoles = o[o.type_osm == "ecole"].groupby("code_commune_nouveau").id_site.nunique()
    sans_site = o[(o.type_osm == "ecole") & o.id_site.isna()].groupby("code_commune_nouveau").size()
    c["ecoles_osm"] = c.code_commune_nouveau.map(ecoles.add(sans_site, fill_value=0)).fillna(0).astype(int)   # sites (objets à moins de 200 m regroupés)
    c["densite_ecoles_100km2"] = (100 * c.ecoles_osm / c.superficie_km2).round(2)
    c["statut_osm"] = c.code_province_ancien.map(cov.set_index("code_province_ancien").statut_osm)
    return c[["code_commune_nouveau", "nom_commune_nouveau", "code_province_ancien", "code_province_nouveau", "nom_province_nouveau",
              "superficie_km2", "lon", "lat", "km_chef_lieu", "ecoles_osm", "densite_ecoles_100km2", "statut_osm"]]


def candidates(code_province_ancien: str, n: int = 5) -> pd.DataFrame:
    """Communes d'une ancienne province. Classées par densité d'écoles OSM croissante seulement si OSM est exploitable ;
    sinon dans l'ordre alphabétique, avec la colonne « fiabilite » à « faible »."""
    c = communes()
    c = c[c.code_province_ancien == code_province_ancien].copy()
    if c.empty:
        return c
    fiable = (c.statut_osm == "exploitable").all()
    c["fiabilite"] = "correcte" if fiable else "faible"
    if fiable:
        c = c.sort_values(["densite_ecoles_100km2", "superficie_km2"], ascending=[True, False])
    else:
        c = c.sort_values("nom_commune_nouveau")
    return c.head(n)


def tableau_priorites(salles_par_province: pd.Series, n: int = 3) -> pd.DataFrame:
    """Pour chaque province avec des salles à construire : les n premières communes à examiner. Une ligne par commune."""
    lignes = []
    for code, nb in salles_par_province[salles_par_province > 0].sort_values(ascending=False).items():
        t = candidates(code, n)
        t.insert(0, "salles_a_construire_province", int(nb))
        lignes.append(t)
    return pd.concat(lignes, ignore_index=True) if lignes else pd.DataFrame()
