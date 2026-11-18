#!/usr/bin/env bash
# Lance le tableau de bord en local (Linux / macOS) : bash lancer_dashboard.sh
cd "$(dirname "$0")"
[ -d .venv ] || python3 -m venv .venv
. .venv/bin/activate
python -m pip install -q -r requirements_dashboard.txt
echo 'Premier lancement : lecture des paquets, peut durer quelques minutes. Suivi ci-dessous.'
python scripts/mesurer_demarrage.py
python -m streamlit run app.py
