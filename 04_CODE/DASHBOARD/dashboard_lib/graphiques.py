"""Graphiques Plotly du diagnostic et de la simulation. Chaque graphique a son tableau équivalent ailleurs dans l'application."""
from __future__ import annotations

from functools import lru_cache

import pandas as pd
import plotly.graph_objects as go

from .chemins import ANALYSE, trouver

BLEU, AMBRE, ROUGE = "#2B6CB0", "#E9A20F", "#B3261E"
from .indicateurs import couleur_charge  # noqa: E402


def _mise_en_page(fig, hauteur):
    fig.update_layout(height=hauteur, margin=dict(l=10, r=10, t=10, b=10), paper_bgcolor="#fff", plot_bgcolor="#fff",
                      font=dict(family="-apple-system, Segoe UI, Roboto, Arial, sans-serif", size=13, color="#1E2620"),
                      hoverlabel=dict(bgcolor="#fff"), legend=dict(orientation="h", y=-0.2))
    fig.update_xaxes(gridcolor="#DDE1E6", zerolinecolor="#DDE1E6")
    fig.update_yaxes(gridcolor="#DDE1E6", zerolinecolor="#DDE1E6")
    return fig


def classement_charge(d45: pd.DataFrame, norme: int) -> go.Figure:
    """Barres : élèves par enseignant, 45 provinces, de la plus chargée à la moins chargée. Couleur et valeur écrite."""
    d = d45.sort_values("eleves_par_maitre")
    coul = [couleur_charge(v, norme) for v in d.eleves_par_maitre]          # mêmes classes et mêmes couleurs que la carte
    fig = go.Figure(go.Bar(x=d.eleves_par_maitre, y=d.nom_province_ancien, orientation="h", marker_color=coul,
                           text=[f"{v:.0f}" for v in d.eleves_par_maitre], textposition="outside", cliponaxis=False,
                           hovertemplate="%{y} : %{x:.1f} élèves par enseignant<extra></extra>"))
    fig.add_vline(x=norme, line_dash="dot", line_color="#14231C", annotation_text=f"norme {norme} (hypothèse)", annotation_position="bottom right")
    fig.update_yaxes(tickfont=dict(size=10), dtick=1)
    fig.update_xaxes(title="Élèves par enseignant (public)")
    return _mise_en_page(fig, 760)


@lru_cache(maxsize=1)
def tendance() -> pd.DataFrame:
    """Ratios nationaux par année scolaire (public) : somme des élèves sur somme des enseignants / salles, provinces complètes."""
    p = pd.read_csv(trouver(ANALYSE, "*panel-provinces-annee-public_v1.csv"), sep=";", encoding="utf-8-sig", dtype={"code_province_ancien": str})
    p = p.drop_duplicates(["code_province_ancien", "annee_scolaire"])
    out = []
    for an, g in p.groupby("annee_scolaire"):
        a = g.dropna(subset=["nb_eleves", "enseignants_tenant_classe"])
        b = g.dropna(subset=["nb_eleves", "nb_salles_classe"])
        out.append({"annee": an, "eleves_par_enseignant": a.nb_eleves.sum() / a.enseignants_tenant_classe.sum(), "provinces_enseignants": len(a),
                    "eleves_par_salle": b.nb_eleves.sum() / b.nb_salles_classe.sum(), "provinces_salles": len(b)})
    return pd.DataFrame(out)


def tendance_nationale(norme_maitre: int, norme_salle: int, annee_sel: str | None = None) -> go.Figure:
    t = tendance()
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=t.annee, y=t.eleves_par_enseignant, mode="lines+markers+text", name="Élèves par enseignant",
                             text=[f"{v:.0f}" for v in t.eleves_par_enseignant], textposition="top center", line=dict(color=BLEU, width=3),
                             hovertemplate="%{x} : %{y:.1f} élèves par enseignant<extra></extra>"))
    fig.add_trace(go.Scatter(x=t.annee, y=t.eleves_par_salle, mode="lines+markers+text", name="Élèves par salle",
                             text=[f"{v:.0f}" for v in t.eleves_par_salle], textposition="bottom center", line=dict(color=ROUGE, width=3, dash="dash"),
                             marker=dict(symbol="square"), hovertemplate="%{x} : %{y:.1f} élèves par salle<extra></extra>"))
    fig.add_hline(y=norme_maitre, line_dash="dot", line_color="#14231C", annotation_text=f"norme {norme_maitre} (hypothèse)", annotation_position="bottom right")
    bas = float(min(t.eleves_par_enseignant.min(), t.eleves_par_salle.min(), norme_maitre)); haut = float(max(t.eleves_par_enseignant.max(), t.eleves_par_salle.max(), norme_maitre))
    fig.update_yaxes(title="Élèves (public, national)", range=[bas - 6, haut + 6])
    fig.update_xaxes(title="Année scolaire")
    if annee_sel:
        fig.add_vline(x=annee_sel, line_color="#14231C", line_width=1, opacity=0.35)
    return _mise_en_page(fig, 380)


GRIS = "#6B7280"
PALETTE_LIGNES = ["#2B6CB0", "#B3261E", "#1B6B45", "#7A4E9E", "#B26A00", "#0E7C86"]     # teintes distinctes par la forme du marqueur aussi
MARQUEURS = ["circle", "square", "diamond", "triangle-up", "x", "cross"]


def trajectoires(codes_noms: list, indicateur: str, annee_sel: str | None = None, norme: float | None = None) -> go.Figure:
    """Lignes par province sur toute la série, plus la référence nationale en pointillé gris. Étiquettes en bout de ligne
    (pas de légende à décoder) et marqueurs de forme différente : la couleur n'est jamais seule."""
    from . import donnees_ui as du
    M, nat = du.serie(indicateur)
    unite = du.INDICATEURS_SERIE[indicateur][3]
    fig = go.Figure()
    fins = []
    fig.add_trace(go.Scatter(x=nat.index, y=nat.values, mode="lines+markers", name="National", line=dict(color=GRIS, width=2, dash="dot"), marker=dict(size=5, color=GRIS),
                             hovertemplate="National, %{x} : %{y:.1f}<extra></extra>"))
    for i, (code, nom) in enumerate(codes_noms):
        if code not in M.columns:
            continue
        y = M[code]
        c, m = PALETTE_LIGNES[i % len(PALETTE_LIGNES)], MARQUEURS[i % len(MARQUEURS)]
        fig.add_trace(go.Scatter(x=y.index, y=y.values, mode="lines+markers", name=nom, connectgaps=False, line=dict(color=c, width=3), marker=dict(size=8, symbol=m, color=c),
                                 hovertemplate=nom + ", %{x} : %{y:.1f}<extra></extra>"))
        ok = y.dropna()
        if len(ok):
            fins.append((ok.index[-1], float(ok.iloc[-1]), nom, c))
    # étiquettes en bout de ligne, écartées entre elles pour rester lisibles
    if fins:
        tous = [v for _, v, _, _ in fins] + [float(x) for x in nat.dropna().tail(1)]
        pas = (max(tous) - min(tous) or 1) * 0.07
        pos, dernier = [], None
        for x, v, nom, c in sorted(fins, key=lambda f: f[1]):
            yy = v if dernier is None or v - dernier >= pas else dernier + pas
            pos.append((x, v, yy, nom, c)); dernier = yy
        for x, v, yy, nom, c in pos:
            fig.add_annotation(x=x, y=yy, text=f"<b>{nom}</b> {v:.0f}", showarrow=False, xanchor="left", xshift=8, font=dict(color=c, size=12))
    if norme is not None:
        fig.add_hline(y=norme, line_dash="dash", line_color="#14231C", line_width=1, annotation_text=f"norme {norme:.0f} (hypothèse)", annotation_position="top left")
    if annee_sel:
        fig.add_vline(x=annee_sel, line_color="#14231C", line_width=1, opacity=0.35)
    fig.update_yaxes(title=unite if unite != "indice" else "Indice (100 = 2017-2018)")
    fig.update_xaxes(title="Année scolaire")
    fig.update_layout(showlegend=False, margin=dict(l=10, r=150, t=10, b=10))
    return _mise_en_page(fig, 400)


def avant_apres(prov: pd.DataFrame, colonne_avant: str, colonne_apres: str, titre: str, n: int = 15) -> go.Figure:
    """Barres : couverture avant et après pour les provinces les moins couvertes après action."""
    d = prov.sort_values(colonne_apres).head(n).iloc[::-1]
    fig = go.Figure()
    fig.add_trace(go.Bar(y=d.nom_province_ancien, x=d[colonne_avant] * 100, orientation="h", name="Avant", marker_color="#9AA19A",
                         text=[f"{v * 100:.0f}" for v in d[colonne_avant]], textposition="outside", cliponaxis=False))
    fig.add_trace(go.Bar(y=d.nom_province_ancien, x=d[colonne_apres] * 100, orientation="h", name="Après", marker_color=BLEU,
                         text=[f"{v * 100:.0f}" for v in d[colonne_apres]], textposition="outside", cliponaxis=False))
    fig.add_vline(x=100, line_dash="dot", line_color="#14231C", annotation_text="besoin couvert", annotation_position="top")
    fig.update_layout(barmode="group")
    fig.update_xaxes(title=titre + " (%)", range=[0, max(115, float((d[[colonne_avant, colonne_apres]].max().max()) * 100) + 12)])
    return _mise_en_page(fig, 520)
