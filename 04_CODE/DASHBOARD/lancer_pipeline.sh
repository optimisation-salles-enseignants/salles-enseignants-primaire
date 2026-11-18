#!/usr/bin/env bash
# Rejoue tout le calcul sans l'application : contrôles, ré-entraînement du modèle, export des graphiques.
set -e
cd "$(dirname "$0")"
[ -d .venv ] || python3 -m venv .venv
. .venv/bin/activate
python -m pip install -q -r requirements_dashboard.txt
python tests/test_modele.py && python scripts/entrainer_modele.py && python scripts/exporter_graphiques.py
