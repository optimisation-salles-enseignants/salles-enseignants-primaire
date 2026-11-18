@echo off
rem Lance le tableau de bord en local (Windows). Double-clic, ou depuis ce dossier : lancer_dashboard.bat
cd /d "%~dp0"
if not exist .venv (python -m venv .venv)
call .venv\Scripts\activate.bat
python -m pip install -q -r requirements_dashboard.txt
echo Premier lancement : lecture des paquets, peut durer quelques minutes. Suivi ci-dessous.
python scripts\mesurer_demarrage.py
python -m streamlit run app.py
