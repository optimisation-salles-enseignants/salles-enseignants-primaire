"""Chemins relatifs au dépôt (aucun chemin absolu)."""
from pathlib import Path

DASHBOARD = Path(__file__).resolve().parents[1]
RACINE = DASHBOARD.parents[1]                      # racine du projet : contient 02_DONNEES et 04_CODE
ANALYSE = RACINE / "02_DONNEES" / "04_analyse"
TRANSFORMATION = RACINE / "02_DONNEES" / "03_transformation"
CARTE = DASHBOARD / "donnees_carte"
CACHE = DASHBOARD / "cache_modele"
MODELE_ANALYSE = DASHBOARD / "modele"              # scripts du Rôle 2, importés sans modification


def trouver(dossier: Path, motif: str) -> Path:
    """Retrouve un fichier par motif (dernière version), message clair s'il manque."""
    trouves = sorted(dossier.glob(motif))
    if not trouves:
        raise FileNotFoundError(f"fichier introuvable : {motif} dans {dossier.name}")
    return trouves[-1]
