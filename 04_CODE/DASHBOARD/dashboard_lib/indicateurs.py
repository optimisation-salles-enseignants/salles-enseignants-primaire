"""Indicateurs de la carte : valeurs par ancienne province, classes, couleurs, hachures, légende."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

import numpy as np

BLEU, AMBRE, ROUGE = "#2B6CB0", "#E9A20F", "#B3261E"         # conservés pour les graphiques à barres simples (avant / après)

# Palette « charge par rapport à la norme » : du plus clair (dans la norme) au plus sombre (très au-dessus).
# La luminosité décroît à chaque classe : l'ordre se lit même sans voir les couleurs. Mesurée : écart de couleur (ΔE) d'au moins 19 entre classes
# voisines en vision normale, protanopie, deutéranopie et tritanopie ; texte sombre ≥ 6,7:1 sur les 3 premières, texte blanc ≥ 4,6:1 sur les 2 dernières.
PAL = ["#D7E4EE", "#F8D9A0", "#EE9C4F", "#CC4B2C", "#7A1519"]
TEXTE_SUR = ["#1F2933", "#1F2933", "#1F2933", "#FFFFFF", "#FFFFFF"]       # couleur du chiffre écrit sur la province, selon sa classe
GRIS_ABSENT = "#D3D7DC"
PAS_CHARGE = (1.15, 1.30, 1.60)                                           # seuils au-dessus de la norme : +15 %, +30 %, +60 %


def classe_charge(v: float, norme: float) -> int:
    """0 = dans la norme ; 1 à 4 = de plus en plus au-dessus."""
    return int(sum(v > norme * t for t in (1.0, *PAS_CHARGE)))


def couleur_charge(v: float, norme: float) -> str:
    return PAL[classe_charge(v, norme)]
SEQ = ["#EEF3F8", "#BCD2E6", "#7DAAD0", "#3E7DB6", "#1A4E80"]   # une seule teinte : le sens passe par la luminosité


@dataclass
class Indicateur:
    nom: str
    valeurs: dict
    couleur: Callable
    texte: Callable
    legende: list = field(default_factory=list)      # (couleur, libellé, hachuré)
    hachure: Callable | None = None
    unite: str = ""
    pire_haut: bool = True                          # True : les valeurs les plus hautes sont les plus préoccupantes
    texte_sur: Callable | None = None               # valeur -> couleur du chiffre écrit sur la province (contraste suffisant avec son fond)


def _ratio_norme(valeurs: dict, norme: int, nom: str, unite: str) -> Indicateur:
    """Élèves par enseignant ou par salle, comparé à la norme (hypothèse réglable). 5 classes ; chiffre écrit sur chaque province."""
    b = [norme * t for t in (1.0, *PAS_CHARGE)]
    n = [0] * 5
    for v in valeurs.values():
        if v is not None and v == v:
            n[classe_charge(v, norme)] += 1
    noms = [f"Dans la norme (jusqu'à {norme})", f"Jusqu'à 15 % au-dessus ({norme} à {b[1]:.0f})", f"15 à 30 % au-dessus ({b[1]:.0f} à {b[2]:.0f})",
            f"30 à 60 % au-dessus ({b[2]:.0f} à {b[3]:.0f})", f"Plus de 60 % au-dessus (plus de {b[3]:.0f})"]
    leg = [(PAL[i], f"{noms[i]} : {n[i]}", False) for i in range(5)]
    if any(v is not None and v == v and v > 2 * norme for v in valeurs.values()):
        leg.append((PAL[4], f"Valeur à vérifier (plus du double de la norme)", True))
    ind = Indicateur(nom, valeurs, lambda v: couleur_charge(v, norme), lambda v: f"{v:.0f}", leg, lambda v: v > 2 * norme, unite)
    ind.texte_sur = lambda v: TEXTE_SUR[classe_charge(v, norme)]
    return ind


def _couverture(valeurs: dict, nom: str) -> Indicateur:
    """Part du besoin couverte : même rampe de couleurs, le plus sombre = le moins couvert."""
    def classe(v):
        return 0 if v >= 0.9995 else 1 if v >= 0.9 else 2 if v >= 0.75 else 3 if v >= 0.5 else 4
    noms = ["Besoin couvert (100 % ou plus)", "90 à 99 % couvert", "75 à 89 % couvert", "50 à 74 % couvert", "Moins de 50 % couvert"]
    n = [0] * 5
    for v in valeurs.values():
        if v is not None and v == v:
            n[classe(v)] += 1
    ind = Indicateur(nom, valeurs, lambda v: PAL[classe(v)], lambda v: f"{min(v, 9.99) * 100:.0f}",
                     [(PAL[i], f"{noms[i]} : {n[i]}", False) for i in range(5)], None, "%", pire_haut=False)
    ind.texte_sur = lambda v: TEXTE_SUR[classe(v)]
    return ind


def _sequentiel(valeurs: dict, nom: str, unite: str, decimales=0, fmt_leg=None, pire_haut=True) -> Indicateur:
    v = np.array([x for x in valeurs.values() if x is not None and not np.isnan(x)], dtype=float)
    q = np.unique(np.quantile(v, [0.2, 0.4, 0.6, 0.8])) if len(v) else np.array([])
    cl = lambda x: SEQ[int(np.searchsorted(q, x, side="right"))] if len(q) else SEQ[0]
    bornes = [v.min() if len(v) else 0, *q, v.max() if len(v) else 0]
    f = fmt_leg or (lambda x: f"{x:.{decimales}f}")
    leg = []
    for i in range(len(bornes) - 1):
        leg.append((SEQ[min(i, 4)], f"{f(bornes[i])} à {f(bornes[i + 1])}", False))
    ind = Indicateur(nom, valeurs, cl, lambda x: f"{x:.{decimales}f}", leg, None, unite, pire_haut)
    ind.texte_sur = lambda x: "#FFFFFF" if SEQ.index(cl(x)) >= 3 else "#1F2933"
    return ind


DIV = [("#B35806", "Baisse de plus de 20 %", True), ("#F1A340", "Baisse de 5 à 20 %", False), ("#EEEEEE", "Stable (−5 % à +5 %)", False),
       ("#8073AC", "Hausse de 5 à 20 %", False), ("#542788", "Hausse de plus de 20 %", False)]


def _divergent(valeurs: dict, nom: str) -> Indicateur:
    """Variation en % : palette orange–violet (sûre pour le daltonisme, évite le rouge–vert), valeur signée écrite sur la province."""
    def classe(x):
        return 0 if x < -20 else 1 if x < -5 else 2 if x <= 5 else 3 if x <= 20 else 4
    ind = Indicateur(nom, valeurs, lambda x: DIV[classe(x)][0], lambda x: f"{x:+.0f}".replace("-", "−"), list(DIV),
                     lambda x: classe(x) == 0, "%", pire_haut=False)
    ind.texte_sur = lambda x: "#FFFFFF" if classe(x) in (0, 3, 4) else "#1F2933"
    return ind


def construire(mode: str, choix: str, d45, sim=None, norme_maitre=50, norme_salle=50, vue="apres", annee=2030) -> Indicateur:
    """mode : 'diag' ou 'sim'. d45 : diagnostic une ligne par ancienne province. sim : résultat du modèle."""
    if mode == "diag":
        if choix == "Élèves par enseignant":
            return _ratio_norme(d45.eleves_par_maitre.to_dict(), norme_maitre, choix, "élèves")
        if choix == "Élèves par salle":
            return _ratio_norme((d45.nb_eleves / d45.nb_salles_classe).to_dict(), norme_salle, choix, "élèves")
        if choix == "Évolution des effectifs":
            return _divergent(d45.evol_eleves.to_dict(), f"Évolution des effectifs depuis {d45.attrs.get('annee_reference_evolution', '')} (%)")
        if choix == "Élèves à plus de 3 km":
            return _sequentiel(d45.pct_plus_de_3_km.to_dict(), choix, "%", 1)
        return _sequentiel((d45.taux_brut_scolarisation * 100).to_dict(), "Taux brut de scolarisation (public)", "%", 0, pire_haut=False)
    p = sim.provinces
    if choix == "Couverture en enseignants":
        v = (p.m_maitres_apres_departs / p.besoin_maitres) if vue == "avant" else p.m_couverture
        return _couverture(v.to_dict(), f"Couverture en enseignants {annee} ({'avant' if vue == 'avant' else 'après'})")
    if choix == "Couverture en salles":
        v = (p.salles_2024 / p.besoin_salles) if vue == "avant" else p.s_couverture
        return _couverture(v.to_dict(), f"Couverture en salles {annee} ({'avant' if vue == 'avant' else 'après'})")
    if choix == "Salles à construire":
        return _sequentiel((p.s_salles_a_construire if vue == "apres" else p.s_salles_a_construire * 0).to_dict(), "Salles à construire", "salles", 0)
    v = (p.m_recrues_affectees + p.m_redeploye_entrant) if vue == "apres" else p.m_recrues_affectees * 0
    return _sequentiel(v.to_dict(), "Enseignants reçus (recrues et redéployés)", "enseignants", 0)
