@echo off
rem Rejoue tout le calcul sans l'application : contrôles, ré-entraînement du modèle, export des graphiques.
cd /d "%~dp0"
if not exist .venv (python -m venv .venv)
call .venv\Scripts\activate.bat
python -m pip install -q -r requirements_dashboard.txt
python tests\test_modele.py && python scripts\entrainer_modele.py && python scripts\exporter_graphiques.py
