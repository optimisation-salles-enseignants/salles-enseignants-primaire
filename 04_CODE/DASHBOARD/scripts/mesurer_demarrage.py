"""Chronomètre le démarrage : dit quelle étape est lente sur CETTE machine. Réchauffe aussi les caches.

Lancer depuis le dossier DASHBOARD :   python scripts/mesurer_demarrage.py
Aucune écriture hors de cache_modele/ ; aucun chiffre n'est modifié.
"""
import platform
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
_t = time.perf_counter()


def etape(nom: str) -> None:
    global _t
    now = time.perf_counter()
    print(f"{now - _t:7.1f} s   {nom}", flush=True)
    _t = now


print(f"Python {platform.python_version()} sur {platform.system()} ; premier lancement : les paquets sont lus et compilés une fois.", flush=True)
import numpy, pandas  # noqa: E401,E402
etape("numpy + pandas")
import plotly.graph_objects  # noqa: E402,F401
etape("plotly")
import sklearn.cluster  # noqa: E402,F401
etape("scikit-learn")
import pulp  # noqa: E402
etape("PuLP")
import streamlit  # noqa: E402,F401
etape("streamlit")
from dashboard_lib import carte, donnees_ui as du, entrainement, modele  # noqa: E402
etape("code du tableau de bord")
modele.donnees()
etape("lecture des données")
du.diagnostic47(); carte.geo()
etape("diagnostic et carte")
entrainement.charger()
etape("modèle appris (chargement)")
r = modele.calculer(modele.Parametres(), utiliser_cache=False)
etape(f"un scénario complet avec le solveur (réalisable : {r.realisable})")
cbc = pulp.PULP_CBC_CMD(msg=0)
print(f"Solveur CBC : {'trouvé' if cbc.available() else 'ABSENT'} ({getattr(cbc, 'path', '?')})")
print("Terminé. Si une ligne dépasse 60 s, c'est elle qui ralentit le lancement (souvent l'antivirus sur le premier import).")
