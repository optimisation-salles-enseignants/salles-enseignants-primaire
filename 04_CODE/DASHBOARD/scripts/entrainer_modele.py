"""Ré-entraîne le modèle d'effectifs, le compare aux autres méthodes et enregistre les résultats.

Lancer depuis le dossier DASHBOARD :   python scripts/entrainer_modele.py
Écrit : modeles_entraines/modele_effectifs_v4.json (modèle + métriques) et sorties/comparaison_methodes.csv.
Aucun tirage aléatoire : deux exécutions sur les mêmes données donnent le même modèle.
"""
import json
import sys
from pathlib import Path

import pandas as pd

RACINE_DASHBOARD = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE_DASHBOARD))
from dashboard_lib import entrainement  # noqa: E402


def main() -> None:
    m = entrainement.entrainer()
    entrainement.enregistrer(m)
    c = m.metriques["comparaison_methodes"]
    lignes = [{"methode": k, "erreur_moyenne_pct": round(100 * v, 1), "erreur_maximale_pct": round(100 * c["erreur_maximale"][k], 1)}
              for k, v in c["erreur_moyenne"].items()]
    lignes.append({"methode": "modele_appris", "erreur_moyenne_pct": round(100 * m.metriques["modele"]["erreur_provinces_pct_eleves"], 1),
                   "erreur_maximale_pct": None})
    sortie = RACINE_DASHBOARD / "sorties"
    sortie.mkdir(exist_ok=True)
    pd.DataFrame(lignes).to_csv(sortie / "comparaison_methodes.csv", sep=";", index=False, encoding="utf-8")
    print(json.dumps({"candidat": m.metriques["candidat_retenu"], "lambda": m.lam, "coefficients": m.metriques["coefficients"],
                      "bat_le_statu_quo": m.metriques["bat_le_statu_quo"], "empreinte_donnees": m.empreinte_donnees}, ensure_ascii=False, indent=1))
    print(pd.DataFrame(lignes).to_string(index=False))


if __name__ == "__main__":
    main()
