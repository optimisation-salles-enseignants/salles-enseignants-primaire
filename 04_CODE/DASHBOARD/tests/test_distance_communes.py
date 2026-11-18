"""Contrôles de la variante « distances réelles » et des communes à examiner.
Lancer depuis le dossier DASHBOARD :  python tests/test_distance_communes.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dashboard_lib import allocation_distance as ad, communes, modele  # noqa: E402


def test_priorite_inchangee():
    """Le modèle d'origine donne les mêmes résultats qu'avant l'ajout de l'option (statu quo : 9 057 recrues, 4 006 salles)."""
    s = modele.calculer(modele.Parametres(), utiliser_cache=False).synthese
    assert s["recrues_affectees"] == 9057 and s["salles_construites"] == 4006 and s["manque_maitres_apres"] == 0


def test_distance_memes_totaux_moins_de_km():
    for sc in ("S0_statu_quo", "S1_retour_2020", "S2_acces_95"):
        a = modele.calculer(modele.Parametres(scenario=sc), utiliser_cache=False)
        b = modele.calculer(modele.Parametres(scenario=sc, cout_deplacement="distance"), utiliser_cache=False)
        assert a.realisable and b.realisable
        for k in ("recrues_affectees", "maitres_redeployes", "manque_maitres_apres", "salles_construites"):
            assert a.synthese[k] == b.synthese[k], (sc, k)
        assert b.synthese["maitres_km"] <= a.synthese["maitres_km"] + 1e-6, sc        # la variante distance ne peut pas faire pire en km
        assert abs(ad.km_total_flux(b.flux) - b.synthese["maitres_km"]) < 1


def test_communes_toutes_rattachees():
    c = communes.communes()
    assert len(c) == 351 and c.code_province_ancien.notna().all() and c.code_province_ancien.nunique() == 45
    assert c[["lat", "lon", "km_chef_lieu", "superficie_km2"]].notna().all().all()


def test_communes_couvrent_toutes_les_salles():
    for sc in ("S0_statu_quo", "S2_acces_95"):
        sa = modele.calculer(modele.Parametres(scenario=sc)).provinces.s_salles_a_construire
        t = communes.tableau_priorites(sa)
        assert t.code_province_ancien.nunique() == int((sa > 0).sum())
        assert int(t.drop_duplicates("code_province_ancien").salles_a_construire_province.sum()) == int(sa.sum())
        assert (t.fiabilite.isin(["correcte", "faible"])).all()


def test_horizon():
    """2030 = comportement d'origine ; plus loin, plus d'élèves et plus de recrues cumulées ; la tendance apprise reste limitée à 2030."""
    a = modele.calculer(modele.Parametres(), utiliser_cache=False).synthese
    b = modele.calculer(modele.Parametres(horizon=2030), utiliser_cache=False).synthese
    assert a == b
    s26 = modele.calculer(modele.Parametres(horizon=2026), utiliser_cache=False).synthese
    s35 = modele.calculer(modele.Parametres(horizon=2035), utiliser_cache=False).synthese
    assert s26["eleves_2030"] < a["eleves_2030"] < s35["eleves_2030"]
    assert (s26["recrues_disponibles"], s35["recrues_disponibles"]) == (2 * 3887, 11 * 3887)
    assert not modele.calculer(modele.Parametres(scenario="tendance_apprise", horizon=2028), utiliser_cache=False).realisable


if __name__ == "__main__":
    for nom, f in list(globals().items()):
        if nom.startswith("test_"):
            f()
            print("OK ", nom)
