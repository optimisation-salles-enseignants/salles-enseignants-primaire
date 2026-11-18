"""Contrôles du tableau de bord. Lancer depuis le dossier DASHBOARD :  python -m pytest tests -q   (ou  python tests/test_modele.py)."""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dashboard_lib import carte, entrainement, modele  # noqa: E402
from dashboard_lib.chemins import ANALYSE, trouver  # noqa: E402


def test_jointure_carte_45_sur_45():
    codes = {v["code"] for v in carte.geo()["prov"].values()}
    assert len(codes) == 45 and codes == set(modele.donnees().u.index)


def test_scenarios_realisables_et_conservation():
    for s in ("S0_statu_quo", "S1_retour_2020", "S2_acces_95", "personnalise", "tendance_apprise"):
        r = modele.calculer(modele.Parametres(scenario=s), utiliser_cache=False)
        assert r.realisable, (s, r.message)
        p = r.provinces
        assert p.m_redeploye_sortant.sum() == p.m_redeploye_entrant.sum()          # déplacements équilibrés
        assert (p.s_salles_2030 >= p.salles_2024).all()                           # on ne détruit pas de salles


def test_reproduit_les_resultats_du_role_2():
    """Pour chaque scénario du Rôle 2 (normes 50, 0 % de départs), le modèle redonne, province par province, ses besoins,
    recrues affectées et manques restants. Le fichier doit exister : sinon le test échoue au lieu de passer à vide."""
    f = [x for x in ANALYSE.rglob("*allocation-maitres-45unites-public_v1.csv")]
    assert f, "fichier de référence du Rôle 2 introuvable"
    ref = pd.read_csv(f[0], sep=";")
    ref = ref[(ref.norme_maitre == 50) & (ref.attrition == 0) & (ref.hypothese_prive == "part_constante")]
    assert ref.scenario.nunique() == 3
    for sc, g in ref.groupby("scenario"):
        r = modele.calculer(modele.Parametres(scenario=sc), utiliser_cache=False).provinces
        g = g.set_index("code_province_ancien").loc[r.index]
        assert (r.besoin_maitres == g.besoin_maitres).all(), sc
        assert (r.m_recrues_affectees == g.recrues_affectees).all(), sc
        assert (r.m_manque_restant == g.manque_restant).all(), sc


def test_modele_appris_deterministe():
    a, b = entrainement.entrainer(), entrainement.entrainer()
    assert a.coef == b.coef and a.metriques["modele"] == b.metriques["modele"]


if __name__ == "__main__":
    for nom, f in list(globals().items()):
        if nom.startswith("test_"):
            f(); print("OK ", nom)
