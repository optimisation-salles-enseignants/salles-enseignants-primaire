"""Carte sur fond satellite (images Esri World Imagery, chargées depuis internet) avec les centroïdes des provinces.

Les limites de la carte du tableau de bord sont dessinées en kilomètres ; `projection_km_vers_lonlat.json` donne la
transformation vers longitude/latitude (ajustée sur 20 points de contrôle, écart moyen 0,8 km, maximum 1,8 km).
Chaque centroïde est un point cliquable qui porte le code de sa province (jointure par code, jamais par nom).
Sans connexion, le fond reste blanc : la carte colorée, les chiffres et les centroïdes s'affichent quand même.
"""
from __future__ import annotations

import html
import json
from functools import lru_cache

import numpy as np

from .carte import _centroide, _pays_rings, code_vers_cle, geo
from .chemins import CARTE

TUILES = "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
ATTRIBUTION = "Imagerie : Esri, Maxar, Earthstar Geographics et la communauté des utilisateurs SIG"


@lru_cache(maxsize=1)
def _projection():
    p = json.loads((CARTE / "projection_km_vers_lonlat.json").read_text(encoding="utf-8"))
    return np.array(p["A"], dtype=float), np.array(p["offset"], dtype=float)


def lonlat(x: float, y: float) -> tuple[float, float]:
    """Carte en km -> (longitude, latitude)."""
    a, off = _projection()
    lon, lat = np.linalg.solve(a, np.array([x, y]) - off)
    return float(lon), float(lat)


def _anneau(r) -> tuple[list, list]:
    ll = [lonlat(x, y) for x, y in r]
    return [p[0] for p in ll] + [ll[0][0]], [p[1] for p in ll] + [ll[0][1]]


def _rgba(hex_: str, alpha: float) -> str:
    h = hex_.lstrip("#")
    return f"rgba({int(h[0:2], 16)},{int(h[2:4], 16)},{int(h[4:6], 16)},{alpha})"


def figure_carte(valeurs: dict, couleur_de, texte_de, infobulle_de, selection=None, non_divisibles=(), hauteur=540, noms_visibles=(), surligner=None,
                 texte_sur=None, **autres):
    """Même appel que `carte.figure_carte` (les options propres à la carte dessinée en km sont ignorées)."""
    import plotly.graph_objects as go

    g = geo()
    c2k = code_vers_cle()
    fig = go.Figure()
    cx, cy, cc, ct, tip, noms = [], [], [], [], [], []
    for k, v in g["prov"].items():
        code = v["code"]
        val = valeurs.get(code)
        lon, lat = [], []
        for r in v["rings"]:
            a, b = _anneau(r)
            lon += a + [None]; lat += b + [None]
        gris = val is None
        fig.add_trace(go.Scattermap(lon=lon, lat=lat, mode="lines", fill="toself", fillcolor="rgba(120,130,140,.25)" if gris else _rgba(couleur_de(val), 0.72),
                                    line=dict(color="rgba(255,255,255,.95)", width=1.2), hoverinfo="skip", showlegend=False))
        if gris:
            continue
        x, y = lonlat(*_centroide(v["rings"]))
        cx.append(x); cy.append(y); cc.append(code); noms.append(v["n"])
        ct.append(f"{texte_de(val)}{'*' if code in non_divisibles else ''}")
        tip.append(html.escape(infobulle_de(code)).replace("\n", "<br>"))
    # contour du pays
    for r in _pays_rings(g):
        a, b = _anneau(r)
        fig.add_trace(go.Scattermap(lon=a, lat=b, mode="lines", line=dict(color="#FFFFFF", width=2.2), hoverinfo="skip", showlegend=False))
    if selection is not None and selection in c2k:                       # province sélectionnée : contour épais jaune
        for r in g["prov"][c2k[selection]]["rings"]:
            a, b = _anneau(r)
            fig.add_trace(go.Scattermap(lon=a, lat=b, mode="lines", line=dict(color="#FCD116", width=4), hoverinfo="skip", showlegend=False))
    # chiffres : blanc sur fond foncé, sombre sur fond clair (même règle que la carte principale)
    for coul in ("#FFFFFF", "#1F2933"):
        idx = [i for i, c in enumerate(cc) if (texte_sur(valeurs[c]) if texte_sur else "#1F2933") == coul]
        if idx:
            fig.add_trace(go.Scattermap(lon=[cx[i] for i in idx], lat=[cy[i] + 0.11 for i in idx], mode="text", text=[ct[i] for i in idx],
                                        textfont=dict(size=13, color=coul), hoverinfo="skip", showlegend=False))
    for coul in ("#FFFFFF", "#1F2933"):                                  # noms des provinces les plus préoccupantes, même contraste que les chiffres
        pick = [i for i, c in enumerate(cc) if c in set(noms_visibles) and (texte_sur(valeurs[c]) if texte_sur else "#1F2933") == coul]
        if pick:
            fig.add_trace(go.Scattermap(lon=[cx[i] for i in pick], lat=[cy[i] - 0.14 for i in pick], mode="text", text=[noms[i] for i in pick],
                                        textfont=dict(size=12, color=coul), hoverinfo="skip", showlegend=False))
    # centroïdes : points cliquables
    same = dict(marker=dict(size=11, color="#FCD116", opacity=1))
    fig.add_trace(go.Scattermap(lon=cx, lat=cy, mode="markers", marker=dict(size=11, color="#FCD116"), customdata=cc, text=tip, hoverinfo="text",
                                selected=same, unselected=same, showlegend=False))
    if selection is not None and selection in c2k:
        lon0, lat0 = lonlat(*_centroide(g["prov"][c2k[selection]]["rings"]))
        centre, zoom = dict(lon=lon0, lat=lat0), 7.2
    else:
        centre, zoom = dict(lon=-1.6, lat=12.3), 5.85
    fig.update_layout(height=hauteur, margin=dict(l=0, r=0, t=0, b=0), paper_bgcolor="#fff", showlegend=False, clickmode="event+select", dragmode="pan",
                      map=dict(style="white-bg", center=centre, zoom=zoom,
                               layers=[dict(sourcetype="raster", source=[TUILES], below="traces", sourceattribution=ATTRIBUTION)]))
    return fig
