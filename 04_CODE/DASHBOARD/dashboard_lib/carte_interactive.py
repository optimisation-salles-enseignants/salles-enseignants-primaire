"""Carte cliquable : la carte de `carte.py` + une couche de points invisibles qui capte le clic.

Pourquoi des points ? Streamlit ne remonte une sélection que pour des points (marqueurs) ; un clic sur l'intérieur d'un
polygone (`hoveron="fills"`) ne produit aucun événement. On pose donc, au-dessus de la carte, une grille de marqueurs
transparents à l'intérieur de chaque province. Chaque marqueur porte le code de sa province (jointure par code, jamais par nom).
"""
from __future__ import annotations

import html
from functools import lru_cache

from . import carte
from .carte import _centroide, code_vers_cle, geo

PAS_KM = 14          # écart entre deux points invisibles (1 unité de la carte = 1 km)
TAILLE_PX = 22       # taille d'un point invisible : doit couvrir un pas de grille


@lru_cache(maxsize=1)
def _points_par_province() -> dict:
    """{code: [(x, y), ...]} : points de grille situés dans la province, plus son centroïde."""
    from matplotlib.path import Path
    import numpy as np

    res = {}
    for v in geo()["prov"].values():
        rings = v["rings"]
        xs = [p[0] for r in rings for p in r]
        ys = [p[1] for r in rings for p in r]
        gx, gy = np.meshgrid(np.arange(min(xs), max(xs) + PAS_KM, PAS_KM), np.arange(min(ys), max(ys) + PAS_KM, PAS_KM))
        grille = np.column_stack([gx.ravel(), gy.ravel()])
        dedans = np.zeros(len(grille), dtype=bool)
        for r in rings:
            dedans |= Path(np.array(r)).contains_points(grille)
        pts = [tuple(p) for p in grille[dedans]]
        pts.append(tuple(_centroide(rings)))
        res[v["code"]] = pts
    return res


def figure_carte(valeurs: dict, couleur_de, texte_de, infobulle_de, selection=None, hachure_de=None, non_divisibles=(), hauteur=620,
                 couches=None, mesure=None, noms_visibles=(), surligner=None, **autres):
    """Même signature que `carte.figure_carte` ; la figure renvoyée est cliquable (un clic = une province)."""
    import plotly.graph_objects as go

    fig = carte.figure_carte(valeurs, couleur_de, texte_de, infobulle_de, selection=selection, hachure_de=hachure_de,
                             non_divisibles=non_divisibles, hauteur=hauteur, couches=couches, mesure=mesure,
                             noms_visibles=noms_visibles, surligner=surligner, **autres)
    x, y, code, tip = [], [], [], []
    for c, pts in _points_par_province().items():
        t = html.escape(infobulle_de(c)).replace("\n", "<br>") if c in valeurs else ""
        for px, py in pts:
            x.append(px); y.append(py); code.append(c); tip.append(t)
    invisible = dict(opacity=0)
    fig.add_trace(go.Scatter(x=x, y=y, mode="markers", marker=dict(size=TAILLE_PX, color="rgba(0,0,0,0)", line=dict(width=0)), customdata=code,
                             text=tip, hoverinfo="text", showlegend=False, selected=dict(marker=invisible), unselected=dict(marker=invisible)))
    fig.update_layout(clickmode="event+select", dragmode="pan")
    return fig


def code_clique(etat) -> str | None:
    """Code de la province cliquée, lu dans l'état renvoyé par `st.plotly_chart(..., on_select=...)` ; None si rien."""
    try:
        points = etat["selection"]["points"]
    except (KeyError, TypeError):
        return None
    for p in points:
        cd = p.get("customdata")
        c = cd[0] if isinstance(cd, (list, tuple)) else cd
        if c in code_vers_cle():
            return c
    return None
