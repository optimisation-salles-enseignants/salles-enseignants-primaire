"""Projection 2030 et allocation des maitres tenant classe (primaire) par programmation lineaire (PuLP).

Calculs sur les 45 anciennes provinces (une ligne par code_province_ancien), restitues pour les 47
nouvelles provinces (Soum et Tapoa : valeurs communes aux deux moities, signalees).

Etape 1 - Projection : eleves 2030 = population 6-11 ans 2030 (projection) x taux brut de scolarisation du scenario.
Etape 2 - Allocation : on cherche la repartition 2030 des maitres qui
   (a) maximise la couverture minimale des provinces (equite), puis
   (b) minimise le manque total et le cout de deplacement (recrues d'abord, redeploiement ensuite).

Parametres : tous modifiables ci-dessous. Chaque valeur porte son statut (source ou hypothese).

Usage : total   : python projection_et_allocation.py <panel.csv> <population.csv> <dossier_sortie>
        public  : python projection_et_allocation.py <panel_public.csv> <population.csv> <dossier_sortie> public <panel_total.csv> [part_constante|prive_constant]
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pulp

from diagnostic_provincial import CLE, CLE47, SEUIL_FERMEE, charger

# ------------------------------------------------------------------ PARAMETRES
ANNEE_BASE = "2024-2025"          # derniere annee observee
ANNEE_REF_TAUX = "2020-2021"
HORIZON = 2030
NORME_REFERENCE = 50              # norme de reference (maitres et salles) ; source officielle non trouvee
NORMES_MAITRE = (50, 45, 40)      # 50 = reference ; 45 et 40 = normes secondaires, a choisir dans le tableau de bord
NORMES_SALLE = (50, 45, 40)       # eleves par salle : meme logique (reference 50), modifiable ici
statut_norme = lambda n: "reference" if n == NORME_REFERENCE else "secondaire"
ATTRITIONS = (0.0, 0.02)          # departs annuels : INCONNU, teste a 0 et 2 % (hypothese)
RECRUTEMENTS_AN = 3887            # PSEF action 8.1.2 (primaire, par an) - valeur reprise du premier modele, a reverifier
N_ANNEES = HORIZON - int(ANNEE_BASE[:4])   # 2025 a 2030 = 6 recrutements annuels
COUT_RECRUE, COUT_DEPL_MEME_REGION, COUT_DEPL_AUTRE_REGION = 0.5, 1.0, 3.0   # hypotheses de priorite (pas des couts reels)
CAPACITES_SALLES = (0.25, 0.50, 0.75, 1.00)   # salles constructibles d'ici 2030, en part du besoin national : valeurs de TEST (hypotheses, pas de budget connu)
POIDS_MANQUE = 1000.0
DELAI_MAX_S = 120
SCENARIOS = {                     # taux brut de scolarisation vise en 2030 (hypotheses issues du premier modele)
    "S0_statu_quo": lambda t24, t20: t24,
    "S1_retour_2020": lambda t24, t20: max(t24, min(t20, 1.0)),
    "S2_acces_95": lambda t24, t20: max(t24, 0.95),
}
HYPOTHESE_PRIVE = "part_constante"   # public seul : comment le prive evolue d'ici 2030 (hypothese, a discuter)
#   "part_constante" : la part du public dans les effectifs de chaque province reste celle de 2024 ;
#   "prive_constant" : le taux de scolarisation du prive reste celui de 2024, le public absorbe tout le reste.
SEP = ";"
PREFIXE = "EQ_04-analyse_D3_scientist_"


# ------------------------------------------------------------------ DONNEES
def unites_base(panel: Path, panel_total: Path = None) -> pd.DataFrame:
    """45 unites de calcul pour l'annee de base. `panel` = panel du statut etudie (public) ou du total ;
    `panel_total` = panel total, necessaire pour viser le taux de scolarisation TOTAL (public + prive)."""
    pop = lambda g: pd.to_numeric(g.population_6_11, errors="coerce")
    par_province = lambda p, an: charger(p).drop_duplicates([CLE, "annee_scolaire"]).query("annee_scolaire == @an").set_index(CLE)
    b = par_province(panel, ANNEE_BASE); g20 = par_province(panel, ANNEE_REF_TAUX)
    tb = par_province(panel_total, ANNEE_BASE) if panel_total else b
    t20 = par_province(panel_total, ANNEE_REF_TAUX) if panel_total else g20
    out = pd.DataFrame({"nom_province_ancien": b.nom_province_ancien, "code_region_nouveau": b.code_region_nouveau,
                        "nom_region_nouveau": b.nom_region_nouveau, "eleves_2024": b.nb_eleves, "salles_2024": b.nb_salles_classe,
                        "maitres_2024": b.enseignants_tenant_classe, "salles_mauvais_etat_2024": b.murs_etat_mauvais + b.toiture_etat_mauvais})
    # taux (exacts, non arrondis) : total = ce que vise le scenario ; statut = part du statut dans ce taux
    out["taux_2024"] = tb.nb_eleves / pop(tb); out["taux_2020"] = t20.nb_eleves / pop(t20)
    out["part_statut_2024"] = b.nb_eleves / tb.nb_eleves
    out["taux_prive_2024"] = (tb.nb_eleves - b.nb_eleves) / pop(tb)
    taux_statut_24, taux_statut_20 = b.nb_eleves / pop(b), g20.nb_eleves / pop(g20)
    out["a_rouvrir"] = (taux_statut_24 / taux_statut_20 < SEUIL_FERMEE).astype(int)   # fermeture mesuree sur le statut etudie
    assert len(out) == 45 and out[["eleves_2024", "maitres_2024", "taux_2024", "taux_2020", "part_statut_2024"]].notna().all().all()
    return out


def population_2030(chemin: Path, codes) -> pd.Series:
    """Population 6-11 ans projetee en HORIZON, par ancienne province (ensemble des sexes)."""
    p = pd.read_csv(chemin, sep=SEP, dtype=str)
    p = p[(p.niveau == "province") & (p.sexe == "ensemble") & (p.groupe_age == "6-11") & (p.annee == str(HORIZON))]
    s = p.set_index("code_ancien").effectif.astype(float)
    assert s.index.is_unique and set(codes) == set(s.index), "les codes de population ne couvrent pas les 45 provinces"
    return s.loc[list(codes)]


def projeter(u: pd.DataFrame, pop: pd.Series) -> pd.DataFrame:
    """Une ligne par province et scenario : eleves 2030 et besoins en maitres / salles."""
    lignes = []
    for sc, f in SCENARIOS.items():
        for code, r in u.iterrows():
            taux_total = f(r.taux_2024, r.taux_2020)                      # taux de scolarisation vise (public + prive)
            if HYPOTHESE_PRIVE == "part_constante":
                taux = taux_total * r.part_statut_2024                    # le statut garde sa part de 2024
            else:
                taux = max(0.0, taux_total - r.taux_prive_2024) if r.part_statut_2024 < 1 else taux_total
            e30 = pop[code] * taux
            l = {CLE: code, "scenario": sc, "population_6_11_2030": int(pop[code]), "taux_cible_total_2030": round(taux_total, 4),
                 "taux_cible_statut_2030": round(taux, 4), "part_statut_2024": round(r.part_statut_2024, 4),
                 "eleves_2030": int(round(e30)), "a_rouvrir": int(r.a_rouvrir)}
            for n in NORMES_MAITRE:
                l[f"besoin_maitres_{n}"] = int(np.ceil(e30 / n))
            for n in NORMES_SALLE:
                l[f"besoin_salles_{n}"] = int(np.ceil(e30 / n))
                l[f"salles_a_ajouter_{n}"] = max(0, int(np.ceil(e30 / n)) - int(r.salles_2024))
            lignes.append(l)
    return pd.DataFrame(lignes)


# ------------------------------------------------------------------ OPTIMISATION
def allouer(cur: pd.Series, besoin: pd.Series, region: pd.Series, recrues: int):
    """Resout l'allocation en deux etapes. Retourne un tableau par province et des indicateurs."""
    prov = list(cur.index)
    exces = {i: max(0, int(cur[i] - besoin[i])) for i in prov}          # maitres au-dela du besoin : deplacables
    manque = {i: max(0, int(besoin[i] - cur[i])) for i in prov}         # maitres a ajouter pour couvrir le besoin
    src = [i for i in prov if exces[i] > 0]; dst = [i for i in prov if manque[i] > 0]
    arcs = [(i, j) for i in src for j in dst]

    def construire(entiers: bool, plancher=None):
        """Modele : deplacements y (de i vers j), recrues r, couverture minimale z."""
        cat = "Integer" if entiers else "Continuous"
        m = pulp.LpProblem("allocation", pulp.LpMinimize)
        y = {a: pulp.LpVariable(f"y_{a[0]}_{a[1]}", 0, None, cat=cat) for a in arcs}
        r = {j: pulp.LpVariable(f"r_{j}", 0, None, cat=cat) for j in dst}
        z = pulp.LpVariable("z", 0, 1)
        for i in src: m += pulp.lpSum(y[(i, j)] for j in dst) <= exces[i]       # on ne descend pas sous le besoin
        entrant = {j: pulp.lpSum(y[(i, j)] for i in src) + r[j] for j in dst}
        for j in dst:
            m += entrant[j] <= manque[j]                                         # on ne depasse pas le besoin
            if plancher is None: m += cur[j] + entrant[j] >= z * besoin[j]       # etape 1 : couverture minimale
            else: m += entrant[j] >= max(0, plancher[j] - cur[j])                # etape 2 : plancher entier
        m += pulp.lpSum(r.values()) <= recrues
        return m, y, r, z, entrant

    solveur = pulp.PULP_CBC_CMD(msg=0, timeLimit=DELAI_MAX_S)
    # etape 1 (relaxation continue, rapide) : plus grande couverture minimale possible
    m, y, r, z, entrant = construire(False)
    m.setObjective(-z); m.solve(solveur); statut1 = pulp.LpStatus[m.status]; zstar = pulp.value(z) if dst else 1.0
    # etape 2 (entiers) : plancher = partie entiere de z* x besoin, puis minimiser manque et deplacements
    plancher = {j: int(np.floor(zstar * besoin[j] + 1e-9)) for j in dst}
    m, y, r, z, entrant = construire(True, plancher)
    cout = lambda i, j: COUT_DEPL_MEME_REGION if region[i] == region[j] else COUT_DEPL_AUTRE_REGION
    m.setObjective(POIDS_MANQUE * pulp.lpSum(manque[j] - entrant[j] for j in dst)
                   + pulp.lpSum(cout(i, j) * y[(i, j)] for (i, j) in arcs) + COUT_RECRUE * pulp.lpSum(r.values()))
    m.solve(solveur); statut2 = pulp.LpStatus[m.status]
    assert statut1 == "Optimal" and statut2 == "Optimal", f"solveur : {statut1} / {statut2}"
    val = lambda v: int(round(v.value() or 0))
    t = pd.DataFrame(index=prov)
    t["maitres_apres_departs"] = cur; t["besoin_maitres"] = besoin
    t["redeploye_sortant"] = [sum(val(y[(i, j)]) for j in dst) if i in src else 0 for i in prov]
    t["redeploye_entrant"] = [sum(val(y[(i, j)]) for i in src) if j in dst else 0 for j in prov]
    t["recrues_affectees"] = [val(r[j]) if j in dst else 0 for j in prov]
    t["maitres_2030"] = t.maitres_apres_departs - t.redeploye_sortant + t.redeploye_entrant + t.recrues_affectees
    t["manque_restant"] = (t.besoin_maitres - t.maitres_2030).clip(lower=0)
    t["couverture"] = (t.maitres_2030 / t.besoin_maitres).round(4)
    flux = [(i, j, val(y[(i, j)])) for (i, j) in arcs if val(y[(i, j)]) > 0]
    return t, {"statut_etape1": statut1, "statut_etape2": statut2, "couverture_minimale_theorique": round(zstar, 4), "flux": flux}


def executer(u: pd.DataFrame, proj: pd.DataFrame):
    detail, synthese, flux_tous = [], [], []
    for sc in SCENARIOS:
        p = proj[proj.scenario == sc].set_index(CLE)
        for n in NORMES_MAITRE:
            for att in ATTRITIONS:
                cur = np.floor(u.maitres_2024 * (1 - att) ** N_ANNEES).astype(int)
                t, info = allouer(cur, p[f"besoin_maitres_{n}"], u.code_region_nouveau, RECRUTEMENTS_AN * N_ANNEES)
                # controles de coherence
                assert t.maitres_2030.sum() == cur.sum() + t.recrues_affectees.sum(), "conservation des maitres"
                assert t.redeploye_sortant.sum() == t.redeploye_entrant.sum(), "deplacements non equilibres"
                assert (t.recrues_affectees.sum() <= RECRUTEMENTS_AN * N_ANNEES)
                assert (t.maitres_2030 >= np.minimum(cur, t.besoin_maitres)).all(), "une province est descendue sous son besoin"
                cle = dict(scenario=sc, norme_maitre=n, statut_norme=statut_norme(n), attrition=att)
                d = t.reset_index().rename(columns={"index": CLE}); d.insert(1, "nom_province_ancien", d[CLE].map(u.nom_province_ancien))
                for k, v in reversed(list(cle.items())): d.insert(1, k, v)
                detail.append(d)
                reg = u.code_region_nouveau
                nb_inter = sum(q for (i, j, q) in info["flux"] if reg[i] != reg[j])
                synthese.append({**cle, "eleves_2030": int(p.eleves_2030.sum()), "besoin_maitres_total": int(t.besoin_maitres.sum()),
                                 "maitres_apres_departs": int(cur.sum()), "recrues_disponibles": RECRUTEMENTS_AN * N_ANNEES,
                                 "recrues_affectees": int(t.recrues_affectees.sum()), "maitres_redeployes": int(t.redeploye_sortant.sum()),
                                 "dont_entre_regions": int(nb_inter), "manque_restant_total": int(t.manque_restant.sum()),
                                 "nb_provinces_non_couvertes": int((t.manque_restant > 0).sum()),
                                 "couverture_minimale_obtenue": float(t.couverture.min()), "couverture_minimale_theorique": info["couverture_minimale_theorique"], "statut_etape1": info["statut_etape1"],
                                 "statut_etape2": info["statut_etape2"]})
                flux_tous += [{**cle, "de": i, "vers": j, "maitres": q} for (i, j, q) in info["flux"]]
    return pd.concat(detail, ignore_index=True), pd.DataFrame(synthese), pd.DataFrame(flux_tous)


def allouer_salles(salles: pd.Series, besoin: pd.Series, capacite: int):
    """Repartit `capacite` salles de classe a construire entre provinces.
    Etape 1 : plus grande couverture minimale (salles / besoin) ; etape 2 : plancher entier, puis manque minimal."""
    ecart = (besoin - salles).clip(lower=0).astype(int)
    dst = [j for j in salles.index if ecart[j] > 0]

    def construire(entiers, plancher=None):
        m = pulp.LpProblem("salles", pulp.LpMinimize)
        x = {j: pulp.LpVariable(f"x_{j}", 0, int(ecart[j]), cat="Integer" if entiers else "Continuous") for j in dst}
        z = pulp.LpVariable("z", 0, 1)
        m += pulp.lpSum(x.values()) <= capacite
        for j in dst:
            if plancher is None: m += salles[j] + x[j] >= z * besoin[j]
            else: m += x[j] >= max(0, plancher[j] - salles[j])
        return m, x, z

    solveur = pulp.PULP_CBC_CMD(msg=0, timeLimit=DELAI_MAX_S)
    m, x, z = construire(False); m.setObjective(-z); m.solve(solveur)
    s1 = pulp.LpStatus[m.status]; zstar = pulp.value(z) if dst else 1.0
    plancher = {j: int(np.floor(zstar * besoin[j] + 1e-9)) for j in dst}
    m, x, z = construire(True, plancher)
    m.setObjective(pulp.lpSum((ecart[j] - x[j]) / besoin[j] for j in dst)); m.solve(solveur)
    s2 = pulp.LpStatus[m.status]
    assert s1 == "Optimal" and s2 == "Optimal", f"solveur salles : {s1} / {s2}"
    t = pd.DataFrame(index=salles.index)
    t["salles_2024"] = salles; t["besoin_salles"] = besoin
    t["salles_a_construire"] = [int(round(x[j].value() or 0)) if j in x else 0 for j in t.index]
    t["salles_2030"] = t.salles_2024 + t.salles_a_construire
    t["manque_restant"] = (t.besoin_salles - t.salles_2030).clip(lower=0)
    t["couverture"] = (t.salles_2030 / t.besoin_salles).round(4)
    return t, round(zstar, 4)


def executer_salles(u: pd.DataFrame, proj: pd.DataFrame):
    detail, synthese = [], []
    for sc in SCENARIOS:
        p = proj[proj.scenario == sc].set_index(CLE)
        for n in NORMES_SALLE:
            ecart_total = int((p[f"besoin_salles_{n}"] - u.salles_2024).clip(lower=0).sum())
            for part in CAPACITES_SALLES:
                cap = int(round(part * ecart_total))
                t, zs = allouer_salles(u.salles_2024.astype(int), p[f"besoin_salles_{n}"], cap)
                assert t.salles_a_construire.sum() <= cap and (t.salles_a_construire >= 0).all()
                assert (t.salles_2030 >= t.salles_2024).all() and (t.salles_2030 <= np.maximum(t.besoin_salles, t.salles_2024)).all()
                cle = dict(scenario=sc, norme_salle=n, statut_norme=statut_norme(n), capacite_part_du_besoin=part, capacite_salles=cap)
                d = t.reset_index().rename(columns={"index": CLE}); d.insert(1, "nom_province_ancien", d[CLE].map(u.nom_province_ancien))
                for k, v in reversed(list(cle.items())): d.insert(1, k, v)
                d["salles_mauvais_etat_2024"] = d[CLE].map(u.salles_mauvais_etat_2024).values
                d["a_rouvrir"] = d[CLE].map(u.a_rouvrir).values
                detail.append(d)
                synthese.append({**cle, "besoin_salles_a_ajouter_total": ecart_total, "salles_construites": int(t.salles_a_construire.sum()),
                                 "manque_restant_total": int(t.manque_restant.sum()), "nb_provinces_non_couvertes": int((t.manque_restant > 0).sum()),
                                 "couverture_minimale_obtenue": float(t.couverture.min()), "couverture_minimale_theorique": zs})
    return pd.concat(detail, ignore_index=True), pd.DataFrame(synthese)


def accueil_conjoint(detail_salles: pd.DataFrame, detail_maitres: pd.DataFrame, proj: pd.DataFrame) -> pd.DataFrame:
    """Indicateur a posteriori : eleves accueillis = min(eleves, salles x norme, maitres x norme), norme salle = norme maitre.
    Les deux allocations restent calculees separement (hypothese de travail)."""
    lignes = []
    for (sc, n, part, cap), g in detail_salles.groupby(["scenario", "norme_salle", "capacite_part_du_besoin", "capacite_salles"]):
        if n not in NORMES_MAITRE: continue
        e = proj[proj.scenario == sc].set_index(CLE).eleves_2030
        dm = detail_maitres[(detail_maitres.scenario == sc) & (detail_maitres.norme_maitre == n)]
        for att, h in dm.groupby("attrition"):
            h = h.set_index(CLE); g2 = g.set_index(CLE)
            par_salles, par_maitres = g2.salles_2030 * n, h.maitres_2030 * n
            accueil = pd.concat([e, par_salles, par_maitres], axis=1).min(axis=1)
            lignes.append({"scenario": sc, "norme": n, "statut_norme": statut_norme(n), "attrition": att,
                           "capacite_salles": cap, "capacite_part_du_besoin": part, "eleves_2030": int(e.sum()),
                           "eleves_accueillis": int(accueil.sum()), "part_accueillie": round(accueil.sum() / e.sum(), 4),
                           "provinces_limitees_par_les_salles": int((par_salles < np.minimum(e, par_maitres)).sum()),
                           "provinces_limitees_par_les_maitres": int((par_maitres < np.minimum(e, par_salles)).sum())})
    return pd.DataFrame(lignes)


def vers_47(detail: pd.DataFrame, panel: Path) -> pd.DataFrame:  # detail : une ligne par ancienne province et combinaison
    """Restitution en 47 provinces : Soum et Tapoa portent la valeur de l'ancienne province (signalee)."""
    d = charger(panel).drop_duplicates([CLE, CLE47])[[CLE, CLE47, "nom_province_nouveau", "chiffres_non_divisibles"]]
    t = detail.merge(d, on=CLE, how="left", validate="many_to_many")
    assert len(t) == len(detail) + 2 * len(detail) // 45, "47 provinces attendues par combinaison"
    t["statut_valeur"] = np.where(t.chiffres_non_divisibles.astype(str) == "1", "valeur_de_l_ancienne_province_non_divisible", "ok")
    return t.drop(columns="chiffres_non_divisibles")


def main(panel: Path, population: Path, sortie: Path, statut: str = "", panel_total: Path = None):
    """statut : "" (total, comme avant) ou "public" ; avec "public", panel_total est obligatoire."""
    assert statut == "" or panel_total is not None, "le panel total est necessaire pour un statut"
    sortie.mkdir(parents=True, exist_ok=True)
    suf = f"-{statut}" if statut else ""
    u = unites_base(panel, panel_total)
    pop = population_2030(population, u.index)
    proj = projeter(u, pop)
    detail, synthese, flux = executer(u, proj)
    proj.insert(1, "nom_province_ancien", proj[CLE].map(u.nom_province_ancien))
    ecrire = lambda df, nom: df.assign(statut_etablissement=statut or "total", hypothese_prive=HYPOTHESE_PRIVE if statut else "sans_objet").to_csv(
        sortie / f"{PREFIXE}{nom}{suf}_v1.csv", sep=SEP, index=False, encoding="utf-8-sig")
    ecrire(proj, "projection-2030-45unites"); ecrire(detail, "allocation-maitres-45unites")
    ecrire(vers_47(detail, panel), "allocation-maitres-47provinces"); ecrire(synthese, "allocation-synthese-scenarios")
    ecrire(flux, "allocation-flux-redeploiement")
    ds, ss = executer_salles(u, proj)
    ecrire(ds, "allocation-salles-45unites"); ecrire(vers_47(ds, panel), "allocation-salles-47provinces")
    ecrire(ss, "allocation-salles-synthese"); ecrire(accueil_conjoint(ds, detail, proj), "accueil-conjoint-salles-maitres")
    print(ss.to_string(index=False))
    print(synthese.drop(columns=["statut_etape1"]).to_string(index=False))


if __name__ == "__main__":
    # python projection_et_allocation.py <panel> <population> <sortie> [public <panel_total> [part_constante|prive_constant]]
    args = sys.argv[1:]
    if len(args) > 5:
        HYPOTHESE_PRIVE = args[5]
        assert HYPOTHESE_PRIVE in ("part_constante", "prive_constant")
    main(Path(args[0]), Path(args[1]), Path(args[2]), args[3] if len(args) > 3 else "", Path(args[4]) if len(args) > 4 else None)
