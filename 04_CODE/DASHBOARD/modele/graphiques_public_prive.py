"""Compare le public et le prive : ratios nationaux sur 8 ans (eleves par maitre, eleves par salle).

Entrees : les tables ratios-province-annee des deux statuts (sorties de diagnostic_provincial.py).
Les sommes sont faites sur une ligne par ancienne province (pas de double compte).

Lancement : python graphiques_public_prive.py <ratios_public.csv> <ratios_prive.csv> <dossier_sortie>
"""
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

CLE = "code_province_ancien"


def national(chemin: Path) -> pd.DataFrame:
    d = pd.read_csv(chemin, sep=";", dtype=str, keep_default_na=False)
    for c in ("nb_eleves", "nb_salles_classe", "enseignants_tenant_classe"):
        d[c] = pd.to_numeric(d[c], errors="coerce")
    u = d.drop_duplicates([CLE, "annee_scolaire"])
    g = u.groupby("annee_scolaire")[["nb_eleves", "nb_salles_classe", "enseignants_tenant_classe"]].sum()
    g["maitre"] = g.nb_eleves / g.enseignants_tenant_classe
    g["salle"] = g.nb_eleves / g.nb_salles_classe
    return g


if __name__ == "__main__":
    pub, pri, sortie = national(Path(sys.argv[1])), national(Path(sys.argv[2])), Path(sys.argv[3])
    sortie.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(1, 2, figsize=(11, 4.2), sharex=True)
    for a, col, titre in ((ax[0], "maitre", "Élèves par maître tenant classe"), (ax[1], "salle", "Élèves par salle de classe")):
        a.plot(pub.index, pub[col], "o-", color="#1f4e79", label="Public")
        a.plot(pri.index, pri[col], "s--", color="#c77700", label="Privé")
        a.axhline(50, color="black", lw=1, ls=":", label="référence 50 (hypothèse)")
        a.set_title(titre, fontsize=10, loc="left"); a.tick_params(axis="x", rotation=40, labelsize=8); a.grid(alpha=0.25); a.legend(fontsize=8)
    fig.suptitle("Public et privé : ratios nationaux, 2017-2018 à 2024-2025", fontsize=11)
    fig.text(0.01, -0.02, "Source : annuaires statistiques du primaire (DGESS). Sommes des anciennes provinces avant division.", fontsize=7, color="#6b6b6b")
    fig.tight_layout(); fig.savefig(sortie / "graphique_comparaison-public-prive_ratios.png", dpi=140, bbox_inches="tight"); plt.close(fig)
    print("ecrit : graphique_comparaison-public-prive_ratios.png")
