"""Carte SVG des provinces (limites : geoBoundaries ; voisins, routes, villes, cours d'eau : Natural Earth).

La carte porte les 45 anciennes provinces : les calculs du Rôle 2 portent sur ces 45 unités. Soum et Tapoa, qui se
scindent en deux nouvelles provinces, restent un seul polygone, marqué « chiffres non divisibles ». Les valeurs sont écrites
sur chaque province : la couleur n'est jamais seule à porter le sens.
"""
from __future__ import annotations

import html
import json
from functools import lru_cache

from .chemins import CARTE

PROVINCES_NON_DIVISIBLES = ("BF4804", "BF5207")  # remplacé à la volée par les codes du fichier de correspondance


@lru_cache(maxsize=1)
def geo() -> dict:
    return json.loads((CARTE / "geo_burkina.json").read_text(encoding="utf-8"))


def _path(rings) -> str:
    return "".join("M" + "L".join(f"{x:.1f} {y:.1f}" for x, y in r) + "Z" for r in rings)


def _line(pts) -> str:
    return "M" + "L".join(f"{x:.1f} {y:.1f}" for x, y in pts)


def _centroide(rings):
    """Centroïde de l'anneau le plus grand (position de l'étiquette)."""
    def aire(r):
        return sum(r[i][0] * r[(i + 1) % len(r)][1] - r[(i + 1) % len(r)][0] * r[i][1] for i in range(len(r))) / 2
    r = max(rings, key=lambda q: abs(aire(q)))
    a = aire(r)
    if abs(a) < 1e-6:
        return r[0]
    cx = sum((r[i][0] + r[(i + 1) % len(r)][0]) * (r[i][0] * r[(i + 1) % len(r)][1] - r[(i + 1) % len(r)][0] * r[i][1]) for i in range(len(r))) / (6 * a)
    cy = sum((r[i][1] + r[(i + 1) % len(r)][1]) * (r[i][0] * r[(i + 1) % len(r)][1] - r[(i + 1) % len(r)][0] * r[i][1]) for i in range(len(r))) / (6 * a)
    return cx, cy


def _boite(rings, marge=0.06):
    xs = [p[0] for r in rings for p in r]
    ys = [p[1] for r in rings for p in r]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    mx, my = (x1 - x0) * marge, (y1 - y0) * marge
    return x0 - mx, y0 - my, x1 - x0 + 2 * mx, y1 - y0 + 2 * my


def distance_km(code1: str, code2: str) -> float:
    """Distance à vol d'oiseau entre les centres de deux provinces (1 unité de la carte = 1 km)."""
    prov, c2k = geo()["prov"], code_vers_cle()
    (ax, ay), (bx, by) = (_centroide(prov[c2k[c]]["rings"]) for c in (code1, code2))
    return ((ax - bx) ** 2 + (ay - by) ** 2) ** 0.5


def code_vers_cle() -> dict:
    return {v["code"]: k for k, v in geo()["prov"].items()}


COUCHES = {"limites": "Limites de province", "regions": "Limites de région", "noms": "Noms des provinces", "villes": "Villes principales", "centroides": "Centroïdes des provinces",
           "routes": "Routes", "rivieres": "Cours d'eau"}


def _pays_rings(g) -> list:
    """Contour du pays sous forme de liste d'anneaux."""
    c = g["country"][0] if g["country"] and isinstance(g["country"][0][0], list) else g["country"]
    return [c] if isinstance(c[0][0], (int, float)) else c


def _ecarter(pts, w, h, maxd, tours=60):
    """Écarte les étiquettes qui se chevauchent (boîtes de demi-taille w × h), sans les éloigner de plus de maxd de leur province."""
    org = [list(p) for p in pts]
    cur = [list(p) for p in pts]
    for _ in range(tours):
        bouge = False
        for i in range(len(cur)):
            for j in range(i + 1, len(cur)):
                dx, dy = cur[j][0] - cur[i][0], cur[j][1] - cur[i][1]
                ox, oy = 2 * w - abs(dx), 2 * h - abs(dy)
                if ox > 0 and oy > 0:                                  # chevauchement : on pousse selon l'axe où il est le plus faible
                    bouge = True
                    if oy <= ox:
                        d = (oy / 2 + 0.5) * (1 if dy >= 0 else -1)
                        cur[i][1] -= d; cur[j][1] += d
                    else:
                        d = (ox / 2 + 0.5) * (1 if dx >= 0 else -1)
                        cur[i][0] -= d; cur[j][0] += d
        for c, o in zip(cur, org):                                     # rappel vers la province d'origine
            c[0] = min(max(c[0], o[0] - maxd), o[0] + maxd); c[1] = min(max(c[1], o[1] - maxd), o[1] + maxd)
        if not bouge:
            break
    return [tuple(c) for c in cur]


def _pastille(fig, x, y, nom, taille, gras):
    """Nom de province : texte foncé sur pastille blanche semi-opaque, lisible quelle que soit la couleur dessous."""
    t = html.escape(nom)
    fig.add_annotation(x=x, y=y, xref="x", yref="y", text=f"<b>{t}</b>" if gras else t, showarrow=False, font=dict(size=taille, color="#1F2933"),
                       bgcolor="rgba(255,255,255,.88)", borderpad=1, bordercolor="rgba(0,0,0,0)")


def _y_noms(lx, ly, idx, w, h, decal):
    """Hauteur du nom de chaque province : au-dessus du chiffre, ou en dessous si le dessus chevauche le chiffre d'une autre province."""
    out = {}
    for i in idx:
        meilleur, n_min = ly[i] + decal, 10**6
        for dec in (decal, -decal, 1.6 * decal, -1.6 * decal, 2.3 * decal, -2.3 * decal):
            y = ly[i] + dec
            n = sum(1 for j in range(len(lx)) if j != i and abs(lx[j] - lx[i]) < w and abs(ly[j] - y) < h)       # chiffres recouverts par le nom
            if n < n_min:
                meilleur, n_min = y, n
            if n == 0:
                break
        out[i] = meilleur
    return [out.get(i, ly[i] + decal) for i in range(len(lx))]


def figure_carte(valeurs: dict, couleur_de, texte_de, infobulle_de, selection=None, hachure_de=None, non_divisibles=(), hauteur=620,
                 couches=None, mesure=None, noms_visibles=(), surligner=None, texte_sur=None):
    """Carte Plotly des 45 provinces (coordonnées projetées de la source : plan x/y, y vers le bas).
    valeurs : {code: valeur} ; couleur_de(valeur) -> couleur ; texte_de(valeur) -> texte écrit sur la province ;
    infobulle_de(code) -> texte du survol ; selection : code de la province zoomée ; hachure_de(valeur) -> bool."""
    import plotly.graph_objects as go
    couches = set(couches if couches is not None else COUCHES)
    g = geo()
    prov = g["prov"]
    c2k = code_vers_cle()

    def xy(rings):
        xs, ys = [], []
        for r in rings:
            xs += [p[0] for p in r] + [r[0][0], None]
            ys += [p[1] for p in r] + [r[0][1], None]
        return xs, ys

    fig = go.Figure()
    for n in g["nb"]:                                   # pays voisins
        x, y = xy(n["rings"])
        fig.add_trace(go.Scatter(x=x, y=y, mode="lines", fill="toself", fillcolor="rgba(0,0,0,0)", line=dict(color="#C9D0D8", width=1, dash="dot"),
                                 hoverinfo="skip", showlegend=False))
    for k, v in prov.items():                           # provinces : couleur, hachures, infobulle
        code = v["code"]
        val = valeurs.get(code)
        x, y = xy(v["rings"])
        fond = couleur_de(val) if val is not None else "#D3D7DC"
        dim = (selection is not None and code != selection) or (surligner is not None and code not in surligner)
        kw = dict(fillcolor=fond)
        if hachure_de and val is not None and hachure_de(val):          # motif léger, réservé aux valeurs à vérifier : le sens ne passe jamais par la couleur seule
            kw = dict(fillpattern=dict(shape="/", bgcolor=fond, fgcolor="#FFFFFF", size=9, solidity=0.12))
        fig.add_trace(go.Scatter(x=x, y=y, mode="lines", fill="toself", line=dict(color="#FFFFFF", width=1.2 if "limites" in couches else 0), opacity=0.35 if dim else 1,
                                 hoveron="fills", text=infobulle_de(code).replace(chr(10), "<br>"), hoverinfo="text", showlegend=False, **kw))
    pays_c = g["country"][0] if g["country"] and isinstance(g["country"][0][0], list) else g["country"]
    if pays_c and isinstance(pays_c[0][0], (int, float)):             # contour du pays : un trait fin et sombre, qui détache la carte du fond
        pays_c = [pays_c]
    for r in pays_c:
        fig.add_trace(go.Scatter(x=[p[0] for p in r] + [r[0][0]], y=[p[1] for p in r] + [r[0][1]], mode="lines", line=dict(color="#4B5563", width=1.4),
                                 hoverinfo="skip", showlegend=False))
    if selection in c2k:                                              # province sélectionnée : contour net
        x, y = xy(prov[c2k[selection]]["rings"])
        fig.add_trace(go.Scatter(x=x, y=y, mode="lines", line=dict(color="#1F2933", width=3), hoverinfo="skip", showlegend=False))
    for r in (g["rv"] if "rivieres" in couches else []):
        fig.add_trace(go.Scatter(x=[p[0] for p in r["p"]], y=[p[1] for p in r["p"]], mode="lines", line=dict(color="#7FB3D8", width=1.2), hoverinfo="skip", showlegend=False))
    for r in (g["rn"] if "routes" in couches else []):
        fig.add_trace(go.Scatter(x=[p[0] for p in r], y=[p[1] for p in r], mode="lines", line=dict(color="rgba(255,255,255,.9)", width=1.6), hoverinfo="skip", showlegend=False))
    for v in (g["reg"].values() if "regions" in couches else []):                         # limites des régions (anciennes), plus épaisses
        x, y = xy(v["rings"])
        fig.add_trace(go.Scatter(x=x, y=y, mode="lines", line=dict(color="#14231C", width=2.2), hoverinfo="skip", showlegend=False))
    lx, ly, lt, ln, lc = [], [], [], [], []                     # valeurs écrites : la couleur ne porte jamais seule le sens
    for k, v in prov.items():
        code = v["code"]
        val = valeurs.get(code)
        if val is None:
            continue
        cx, cy = _centroide(v["rings"])
        lx.append(cx); ly.append(cy - 13 if 'centroides' in couches else cy)            # avec les centroïdes affichés, le chiffre passe au-dessus du point
        lt.append(f"<b>{html.escape(texte_de(val))}{'*' if code in non_divisibles else ''}</b>")
        ln.append(v["n"]); lc.append(code)
    bx0, by0, bw, bh = _boite(_pays_rings(g), 0.03)
    pos = _ecarter(list(zip(lx, ly)), w=0.027 * bw, h=0.019 * bh, maxd=0.035 * bw)       # étiquettes de chiffres écartées entre elles
    lx, ly = [q[0] for q in pos], [q[1] for q in pos]
    tcol = [(texte_sur(valeurs[c]) if texte_sur else "#1F2933") for c in lc]        # chiffre sombre sur fond clair, blanc sur fond foncé (contraste mesuré)
    fig.add_trace(go.Scatter(x=lx, y=ly, mode="text", text=lt, textfont=dict(size=13, color=tcol), hoverinfo="skip", showlegend=False))
    if "noms" in couches:                               # tous les noms (couche à activer)
        yn = _y_noms(lx, ly, range(len(lx)), 0.075 * bw, 0.028 * bh, 26)
        for i in range(len(lx)):
            _pastille(fig, lx[i], yn[i], ln[i], 11, False)
    elif noms_visibles:                                 # sinon : le nom des provinces les plus préoccupantes, sur pastille blanche (lisible même au-dessus d'une province voisine)
        pick = [i for i, c in enumerate(lc) if c in set(noms_visibles)]
        yn = _y_noms(lx, ly, pick, 0.075 * bw, 0.028 * bh, 26)
        for i in pick:
            _pastille(fig, lx[i], yn[i], ln[i], 12, True)
    if "centroides" in couches:                         # un point par province, à son centroïde (c'est de là que partent les distances)
        cen = [_centroide(v["rings"]) for v in prov.values() if v["code"] in valeurs and valeurs[v["code"]] is not None]
        fig.add_trace(go.Scatter(x=[c[0] for c in cen], y=[c[1] for c in cen], mode="markers", marker=dict(size=6, color="#FCD116", line=dict(color="#1F2933", width=1.2)),
                                 hoverinfo="skip", showlegend=False))
    vil = [c for c in g["ct"] if c[4] or c[3] >= 100000] if "villes" in couches else []
    fig.add_trace(go.Scatter(x=[c[1] for c in vil], y=[c[2] for c in vil], mode="markers+text", text=[c[0] for c in vil], textposition="top right",
                             marker=dict(size=7, color="#fff", line=dict(color="#14231C", width=1.5)), textfont=dict(size=11, color="#14231C"),
                             hovertext=[f"{c[0]}" for c in vil], hoverinfo="text", showlegend=False))
    nbx, nby, nbt = [], [], []                         # noms des pays voisins (gris clair) ; ramenés dans la vue pour ne jamais être coupés
    for n in g["nb"]:
        if not (by0 <= n["c"][1] <= by0 + bh):          # pays dont le centre est hors de la vue : pas d'étiquette (elle chevaucherait la carte)
            continue
        nbx.append(min(max(n["c"][0], bx0 + 0.13 * bw), bx0 + 0.87 * bw)); nby.append(n["c"][1]); nbt.append(n["n"])
    fig.add_trace(go.Scatter(x=nbx, y=nby, mode="text", text=nbt, textfont=dict(size=12, color="rgba(75,85,99,.7)"), hoverinfo="skip", showlegend=False))
    pays = g["country"][0] if g["country"] and isinstance(g["country"][0][0], list) else g["country"]
    if mesure and all(m in c2k for m in mesure):
        (ax, ay), (bx, by) = (_centroide(prov[c2k[m]]["rings"]) for m in mesure)
        km = ((ax - bx) ** 2 + (ay - by) ** 2) ** 0.5
        fig.add_trace(go.Scatter(x=[ax, bx], y=[ay, by], mode="lines+markers+text", line=dict(color="#0B57D0", width=3, dash="dash"), marker=dict(size=9, color="#0B57D0"),
                                 text=["", f"<b>{km:.0f} km</b>"], textposition="top center", textfont=dict(size=14, color="#0B57D0"),
                                 hoverinfo="skip", showlegend=False))
    if selection and selection in c2k:
        x0, y0, w, h = _boite(prov[c2k[selection]]["rings"], 0.45)
    else:
        x0, y0, w, h = _boite([pays] if isinstance(pays[0][0], (int, float)) else pays, 0.03)
    long = 100 if w > 400 else (50 if w > 150 else 10)        # échelle : 1 unité de la carte = 1 km (source des limites)
    sx, sy = x0 + w * 0.97 - long, y0 + h * 0.965
    fig.add_trace(go.Scatter(x=[sx, sx + long], y=[sy, sy], mode="lines+text", line=dict(color="#4B5563", width=3), text=["", f"{long} km"],
                             textposition="top left", textfont=dict(size=12, color="#14231C"), hoverinfo="skip", showlegend=False))
    fig.add_annotation(x=0.02, y=0.97, xref="paper", yref="paper", text="<b>N</b><br>↑", showarrow=False, font=dict(size=15, color="#4B5563"))
    fig.update_xaxes(range=[x0, x0 + w], visible=False, constrain="domain")
    fig.update_yaxes(range=[y0 + h, y0], visible=False, scaleanchor="x", scaleratio=1)   # y vers le bas, échelle 1:1
    fig.update_layout(height=hauteur, margin=dict(l=0, r=0, t=0, b=0), paper_bgcolor="#FFFFFF", plot_bgcolor="#FFFFFF", dragmode="pan",
                      hoverlabel=dict(bgcolor="#fff", font=dict(size=13, color="#1E2620")))
    return fig
