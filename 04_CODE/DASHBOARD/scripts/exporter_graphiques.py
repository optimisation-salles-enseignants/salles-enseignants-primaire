"""Régénère hors de l'application les graphiques et cartes du tableau de bord (fichiers HTML autonomes).

Lancer depuis le dossier DASHBOARD :   python scripts/exporter_graphiques.py [année_scolaire]
Écrit dans sorties/graphiques/ : une carte par indicateur du diagnostic, le classement, la tendance nationale
et les trajectoires des 5 provinces les plus chargées. Même code que l'application (dashboard_lib), mêmes chiffres.
"""
import sys
from pathlib import Path

RACINE_DASHBOARD = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE_DASHBOARD))
from dashboard_lib import carte, donnees_ui as du, graphiques as graph, indicateurs  # noqa: E402

NORME_MAITRE, NORME_SALLE = 50, 50          # hypothèses de travail, modifiables dans l'application
INDICATEURS = ["Élèves par enseignant", "Élèves par salle", "Évolution des effectifs", "Élèves à plus de 3 km", "Taux brut de scolarisation"]


def main(an: str | None = None) -> None:
    an = an or du.annees()[-1]
    out = RACINE_DASHBOARD / "sorties" / "graphiques"
    out.mkdir(parents=True, exist_ok=True)
    d47 = du.diagnostic_annee(an)
    d45 = du.diagnostic_annee45(an)
    noms = d47.set_index("code_province_ancien")["province"].to_dict() if "province" in d47 else {}
    cfg = {"displaylogo": False}
    for nom in INDICATEURS:
        i = indicateurs.construire("diag", nom, d45, norme_maitre=NORME_MAITRE, norme_salle=NORME_SALLE)
        tip = lambda c, i=i: f"{noms.get(c, c)} : {i.texte(i.valeurs[c]) if c in i.valeurs else 'non disponible'} {i.unite}"
        fig = carte.figure_carte(i.valeurs, i.couleur, i.texte, tip, hachure_de=i.hachure)
        fig.write_html(out / f"carte_{nom.lower().replace(' ', '_').replace('é', 'e').replace('è', 'e').replace('à', 'a')}_{an}.html", config=cfg)
    graph.classement_charge(d45, NORME_MAITRE).write_html(out / f"classement_{an}.html", config=cfg)
    graph.tendance_nationale(NORME_MAITRE, NORME_SALLE, an).write_html(out / "tendance_nationale.html", config=cfg)
    pires = d47.sort_values("eleves_par_maitre", ascending=False).head(5)
    cn = [(r.code_province_ancien, noms.get(r.code_province_ancien, r.code_province_ancien)) for r in pires.itertuples()]
    graph.trajectoires(cn, "Élèves par enseignant", an, NORME_MAITRE).write_html(out / "trajectoires_plus_chargees.html", config=cfg)
    print(f"{len(list(out.glob('*.html')))} graphiques écrits dans {out.relative_to(RACINE_DASHBOARD)}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
