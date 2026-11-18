"""Tableau de bord d'aide à la décision : répartition des salles de classe et des enseignants (primaire, public).

Lancement (depuis 04_CODE/DASHBOARD) :  streamlit run app.py
Chaque scénario est calculé par le modèle d'optimisation du dossier modele/ ; rien n'est inventé.
"""
import base64
import time
from dataclasses import replace

import streamlit as st

st.set_page_config(page_title="Répartition des salles de classe et des enseignants", page_icon=None, layout="wide",
                   initial_sidebar_state="collapsed")
# Message affiché tout de suite : au premier lancement, la lecture des gros paquets (plotly, scikit-learn) peut prendre du temps.
_attente = st.empty()
_attente.markdown("<div style='font:16px sans-serif;color:#4B5563;padding:48px 8px'>Chargement du tableau de bord… "
                  "le premier lancement est plus long (quelques minutes au plus) ; les suivants sont rapides.</div>", unsafe_allow_html=True)

import pandas as pd  # noqa: E402  (imports lourds après le message d'attente)
import plotly.express as px  # noqa: E402
import plotly.graph_objects as go  # noqa: E402

from dashboard_lib import allocation_distance as ad, carte, carte_interactive, carte_satellite, communes as comm, donnees_ui as du, graphiques as graph, indicateurs as ind  # noqa: E402
from dashboard_lib.chemins import CARTE  # noqa: E402
from dashboard_lib.modele import HORIZONS, Parametres, SCENARIOS_PREDEFINIS, calculer, en_47  # noqa: E402
from dashboard_lib.style import CSS  # noqa: E402

st.markdown(CSS, unsafe_allow_html=True)

fmt, pct = du.fmt, du.pct
ARM = base64.b64encode((CARTE / "armoiries.png").read_bytes()).decode()
ANNEES = du.annees()
AN = st.session_state.get("an", ANNEES[-1])
if AN not in ANNEES:
    AN = ANNEES[-1]
D47 = du.diagnostic_annee(AN)                      # année choisie en haut de la page
D45 = D47.drop_duplicates("code_province_ancien").set_index("code_province_ancien", drop=False)
D47_RECENT = du.diagnostic47()
NOMS47 = D47_RECENT.drop_duplicates("code_province_nouveau").set_index("nom_province_nouveau").code_province_ancien.to_dict()
NON_DIV = tuple(D47_RECENT[D47_RECENT.chiffres_non_divisibles == 1].code_province_ancien.unique())
_attente.empty()
DEF = dict(qt=0.5, scen="Statu quo", taux=95, nm=50, ns=50, att=0.0, rec=3887, cons=50, prive="part_constante", cout="priorite", hor=2030)
SCEN = {"Statu quo": "S0_statu_quo", "Retour à 2020": "S1_retour_2020", "Accès à 95 %": "S2_acces_95", "Personnalisé": "personnalise", "Tendance apprise": "tendance_apprise"}


@st.cache_data(show_spinner=False)
def resoudre(p: Parametres):
    t = time.perf_counter()
    r = calculer(p)
    return r, time.perf_counter() - t


def reinit():
    for k, v in DEF.items():
        st.session_state[k] = v


def enregistrer():
    ss = st.session_state
    p = Parametres(scenario=SCEN[ss.scen], taux_cible=(ss.taux or 95) / 100, norme_maitre=ss.nm, norme_salle=ss.ns, attrition=ss.att / 100,
                   recrues_par_an=ss.rec, part_construction=ss.cons / 100, hypothese_prive=ss.prive, quantile_tendance=ss.qt, cout_deplacement=ss.cout, horizon=ss.hor)
    lib = f"Personnalisé à {ss.taux or 95} %" if ss.scen == "Personnalisé" else ss.scen
    ss.sauves.append((f"n° {len(ss.sauves) + 1} · {lib} · {ss.nm}/{ss.ns} · {ss.cons} % de salles · {ss.hor}", p))
    st.toast(f"Scénario n° {len(ss.sauves)} enregistré : il apparaît dans la comparaison, sous la carte.")


for k, v in DEF.items():
    st.session_state.setdefault(k, v)
st.session_state.setdefault("sauves", [])

# ------------------------------------------------------------------ bandeau unique : identité, niveau, année
st.markdown('<div class="tri"></div>', unsafe_allow_html=True)
st.markdown(f"""<div class="bandeau"><div class="brand"><img alt="Armoiries du Burkina Faso" src="data:image/png;base64,{ARM}"><div>
<div class="min">Burkina Faso · Ministère de l'Enseignement de base, de l'Alphabétisation et de la Promotion des langues nationales</div>
<h1>Où manquent des salles de classe et des enseignants ?</h1></div></div></div>""", unsafe_allow_html=True)

CHARGES = ["Dans la norme", "Jusqu'à 10 % au-dessus", "Plus de 10 % au-dessus"]
PROFIL = D47_RECENT.drop_duplicates("code_province_ancien").set_index("code_province_ancien").groupe.map(du.profils())
NOMS_PROFILS = sorted(PROFIL.dropna().unique())


def _noms_de(code):
    """Noms de province (nouveaux) qui correspondent à un code ancien (2 pour Soum et Tapoa)."""
    return sorted(n for n, c in NOMS47.items() if c == code)


def _au_clic_carte():
    """Un clic sur la carte filtre sur la province cliquée ; un second clic sur la même province annule."""
    code = carte_interactive.code_clique(st.session_state.get(f"carte_plane_{st.session_state.get('carte_n', 0)}"))
    if code is None:
        return
    st.session_state.f_prov = [] if st.session_state.get("f_prov") == _noms_de(code) else _noms_de(code)
    st.session_state.carte_n = st.session_state.get("carte_n", 0) + 1


def _reset_filtres():
    for k in ("f_prov", "f_charge", "f_profil"):
        st.session_state[k] = []
    st.session_state.f_rouvrir = False


with st.container(key="filtres"):
    f = st.columns([1.45, 1.55, 1.9, 1.7, 1.5, 1.5, 0.95], gap="small", vertical_alignment="bottom")
    f[0].selectbox("Année scolaire", ANNEES, index=len(ANNEES) - 1, key="an", format_func=lambda x: x)
    niveau = f[1].selectbox("Niveau", ["Primaire · 6 à 11 ans", "Post-primaire · 12 à 15 ans", "Secondaire · 16 à 18 ans"], key="niv")
    f_prov = f[2].multiselect("Provinces", sorted(NOMS47), key="f_prov", placeholder="Toutes les provinces")
    f_charge = f[3].multiselect("Niveau de charge", CHARGES, key="f_charge", placeholder="Tous les niveaux", help="Élèves par enseignant comparés à la norme de référence des réglages (50 par défaut, hypothèse).")
    f_profil = f[4].multiselect("Type de province", NOMS_PROFILS, key="f_profil", placeholder="Tous les profils")
    f_rouvrir = f[5].toggle("Provinces à rouvrir", key="f_rouvrir", help="Provinces dont le taux de scolarisation est tombé sous 60 % de celui de 2020.")
    f[6].button("Réinitialiser", key="bt_reset_f", on_click=_reset_filtres, use_container_width=True, help="Retirer tous les filtres.")

# sélection de provinces issue des filtres (la norme de référence vient des réglages)
_nm = st.session_state.get("nm", 50)
_r = D45.eleves_par_maitre
_classe = pd.Series(pd.cut(_r, [-1, _nm, _nm * 1.1, 1e9], labels=CHARGES), index=D45.index).astype(object)
_codes = set(D45.index)
if f_prov:
    _codes &= {NOMS47[n] for n in f_prov}
if f_charge:
    _codes &= set(_classe[_classe.isin(f_charge)].index)
if f_profil:
    _codes &= set(PROFIL[PROFIL.isin(f_profil)].index)
if f_rouvrir:
    _codes &= set(D45[D45.a_rouvrir == 1].index)
FILTRE_ACTIF = bool(f_prov or f_charge or f_profil or f_rouvrir)
VIDE = FILTRE_ACTIF and not _codes
SCOPE = list(D45.index) if (VIDE or not _codes) else [c for c in D45.index if c in _codes]
if FILTRE_ACTIF:
    _txt = (f"<b>{len(SCOPE)} province{'s' if len(SCOPE) > 1 else ''} sur {len(D45)}</b> {'correspondent' if len(SCOPE) > 1 else 'correspond'} aux filtres : la carte, les indicateurs, les classements et les tableaux portent sur cette sélection."
            if not VIDE else "<b>Aucune province ne correspond à ces filtres.</b> Tous les chiffres sont affichés ; modifiez ou réinitialisez les filtres.")
    st.markdown(f"<div class='filtre-etat'>{_txt}</div>", unsafe_allow_html=True)

t1, t2, t3 = st.tabs(["Tableau de bord", "Analyse des provinces", "Données et méthode"])


def _sur_mode():
    """En simulation, les réglages s'ouvrent d'eux-mêmes ; en diagnostic, la carte garde toute la place."""
    st.session_state.cache_g = st.session_state.get("mode") != "Simulation"


def _basculer(cle):
    st.session_state[cle] = not st.session_state[cle]


# ------------------------------------------------------------------ onglet 1
with t1:
    if not niveau.startswith("Primaire"):
        st.markdown(f"""<div class="state"><h2 class="t">Données non disponibles pour ce niveau</h2>
<p>Le travail porte d'abord sur le primaire. Le {niveau.split(' · ')[0].lower()} sera ajouté si les données le permettent.</p></div>""", unsafe_allow_html=True)
    else:
        st.session_state.setdefault("cache_g", True)            # réglages repliés par défaut (la carte d'abord)
        st.session_state.setdefault("cache_d", False)
        if st.session_state.cache_g:
            st.markdown("<style>div[data-testid='stColumn']:has(.st-key-panel){display:none!important}</style>", unsafe_allow_html=True)
        if st.session_state.cache_d:
            st.markdown("<style>div[data-testid='stColumn']:has(.st-key-kpis){display:none!important}</style>", unsafe_allow_html=True)
        with st.container(key="mainrow"):
            gl, gc, gr = st.columns([1, 2.35, 1.5], gap="medium")
        with gc:
            cartecard = st.container(key="cartecard")
            with cartecard:
                r1, r2 = st.columns([1.2, 1.6])
                mode_lbl = r1.segmented_control("Fonction de la carte", ["Diagnostic", "Simulation"], default="Diagnostic", key="mode", selection_mode="single",
                                                label_visibility="collapsed", on_change=_sur_mode) or "Diagnostic"
                mode = "diag" if mode_lbl == "Diagnostic" else "sim"
                opts = (["Élèves par enseignant", "Élèves par salle", "Élèves à plus de 3 km", "Taux brut de scolarisation", "Évolution des effectifs"] if mode == "diag"
                        else ["Salles à construire", "Enseignants reçus", "Couverture en salles", "Couverture en enseignants"])
                choix = r2.selectbox("Indicateur affiché sur la carte", opts, key=f"ind_{mode}", label_visibility="collapsed")
                carte_slot = st.container()
                outils = st.container(key="outils")
        # ---- outils sous la carte : relief, couches, mesure, panneaux, avant/après
        with outils:
            o = st.columns([0.95, 1.35, 1.35, 1.05, 1.05], vertical_alignment="center")
            with o[0].popover("Couches"):
                couches = [k for k, l in carte.COUCHES.items() if st.checkbox(l, value=k == "limites", key=f"couche_{k}")]
                satellite = st.checkbox("Fond satellite (internet requis)", value=False, key="couche_satellite",
                                        help="Images Esri chargées depuis internet. Sans connexion, le fond reste blanc ; la carte colorée et les chiffres restent affichés. Les points jaunes sont les centroïdes des provinces ; survolez-les pour lire les chiffres. Sur ce fond, le filtre se fait par la liste « Provinces ».")
            with o[1].popover("Mesurer une distance"):
                nm_liste = sorted(NOMS47)
                m1 = st.selectbox("De", nm_liste, index=nm_liste.index("Kadiogo") if "Kadiogo" in nm_liste else 0, key="mes1")
                m2 = st.selectbox("À", nm_liste, index=0, key="mes2")
                km = carte.distance_km(NOMS47[m1], NOMS47[m2])
                st.markdown(f"**{km:.0f} km** à vol d'oiseau, d'un centre de province à l'autre.")
                trace = st.checkbox("Tracer sur la carte", value=False, key="mes_trace")
            vue = "apres"
            if mode == "sim":
                vue_lbl = o[2].segmented_control("Situation affichée", ["Avant", "Après"], default="Après", key="vue", selection_mode="single", label_visibility="collapsed") or "Après"
                vue = "avant" if vue_lbl == "Avant" else "apres"
            o[3].button("Afficher les réglages" if st.session_state.cache_g else "Masquer les réglages", key="bt_g", on_click=_basculer, args=("cache_g",), use_container_width=True,
                        type="secondary" if st.session_state.cache_g else "primary", help="Afficher ou masquer les réglages (normes, hypothèses 2030).")
            o[4].button("Afficher les indicateurs" if st.session_state.cache_d else "Masquer les indicateurs", key="bt_d", on_click=_basculer, args=("cache_d",), use_container_width=True,
                        type="secondary" if st.session_state.cache_d else "primary", help="Afficher ou masquer la colonne des indicateurs pour agrandir la carte.")
        # ---- panneau de réglages
        with gl:
            with st.container(key="panel"):
                st.markdown("<h2 class='t'>Réglages</h2>", unsafe_allow_html=True)
                if mode == "sim":
                    st.markdown("**Année visée** <span class='tag'>Hypothèse</span>", unsafe_allow_html=True)
                    hor = st.select_slider("Année visée", options=list(HORIZONS), key="hor", label_visibility="collapsed",
                                           help="Les besoins évoluent avec la population : choisissez l'année à regarder (2026 à 2035). Le niveau de scolarisation du scénario est atteint à cette date, et les recrutements sont comptés depuis 2025.")
                    st.markdown(f"**Hypothèse de scolarisation en {hor}** <span class='tag'>Hypothèse</span>", unsafe_allow_html=True)
                    scen = st.segmented_control("Scénario", list(SCEN), key="scen", selection_mode="single", label_visibility="collapsed") or DEF["scen"]
                    taux = st.slider("Taux brut visé (public + privé)", 50, 100, key="taux", format="%d %%") if scen == "Personnalisé" else None
                    if scen == "Tendance apprise":
                        if hor != 2030:
                            st.markdown("<div class='hint'><b>Cette tendance n'existe que pour 2030.</b> Choisissez 2030 ci-dessus ou un autre scénario.</div>", unsafe_allow_html=True)
                        st.radio("Variante de la tendance", [0.1, 0.5, 0.9], key="qt", horizontal=True,
                                 format_func=lambda x: {0.1: "Basse", 0.5: "Centrale", 0.9: "Haute"}[x])
                        st.markdown("<div class='hint'>Modèle appris sur 2017-2025. À la validation il fait moins bien que « les effectifs restent ceux de 2024 » "
                                    "(voir l'onglet Données et méthode) : à lire comme une hypothèse, pas comme une prévision.</div>", unsafe_allow_html=True)
                st.markdown("**Norme : élèves par enseignant** <span class='tag'>Hypothèse</span>", unsafe_allow_html=True)
                nm = st.slider("Élèves par enseignant", 30, 60, key="nm", label_visibility="collapsed",
                               help="50 est la valeur de référence : aucune norme officielle n'a été trouvée. 45 et 40 sont des objectifs.")
                st.markdown("**Norme : élèves par salle** <span class='tag'>Hypothèse</span>", unsafe_allow_html=True)
                ns = st.slider("Élèves par salle", 30, 60, key="ns", label_visibility="collapsed")
                if mode == "sim":
                    with st.expander("Réglages avancés"):
                        st.markdown("**Départs d'enseignants par an** <span class='tag'>Hypothèse</span>", unsafe_allow_html=True)
                        att = st.slider("Départs par an", 0.0, 5.0, step=0.5, key="att", format="%.1f %%", label_visibility="collapsed")
                        st.markdown("**Recrutements par an** <span class='tag'>À revérifier</span>", unsafe_allow_html=True)
                        rec = st.slider("Recrutements par an", 0, 10000, step=100, key="rec", label_visibility="collapsed")
                        st.markdown("<div class='hint'>3 887 : valeur du plan sectoriel (action 8.1.2), à revérifier.</div>", unsafe_allow_html=True)
                        st.markdown("**Choix des provinces d'envoi** <span class='tag'>Hypothèse</span>", unsafe_allow_html=True)
                        cout = st.segmented_control("Choix des provinces d'envoi", ["priorite", "distance"], key="cout", selection_mode="single", label_visibility="collapsed",
                                                    format_func=lambda x: {"priorite": "Priorités du modèle", "distance": "Distances réelles"}[x]) or DEF["cout"]
                        st.markdown("<div class='hint'>Si des enseignants doivent être déplacés, « Distances réelles » choisit les provinces les plus proches (km à vol d'oiseau entre centres de provinces). "
                                    "Les totaux ne changent pas, seule la répartition change.</div>", unsafe_allow_html=True)
                        st.markdown(f"**Salles constructibles d'ici {hor}** <span class='tag'>Hypothèse</span>", unsafe_allow_html=True)
                        cons = st.slider("Part du besoin en salles", 0, 100, step=5, key="cons", format="%d %% du besoin", label_visibility="collapsed")
                        prive = st.radio("Évolution du privé", ["part_constante", "prive_constant"], key="prive",
                                         format_func=lambda x: "La part du public reste celle de 2024" if x == "part_constante" else "Le privé reste au niveau de 2024")
                    if AN != ANNEES[-1]:
                        st.markdown(f"<div class='hint'>La simulation part toujours de {ANNEES[-1]}, quelle que soit l'année choisie en haut.</div>", unsafe_allow_html=True)
                    st.button("Enregistrer ce scénario", on_click=enregistrer, key="save", type="primary")
                else:
                    st.markdown(f"<div class='hint'>La carte montre la situation de {AN}. Passez à la simulation pour voir une année à venir.</div>", unsafe_allow_html=True)
                    scen, taux, att, rec, cons, prive, cout, hor = (st.session_state[k] for k in ("scen", "taux", "att", "rec", "cons", "prive", "cout", "hor"))
                st.button("Réinitialiser les paramètres", on_click=reinit, key="reset")
        qt = st.session_state.qt
        params = Parametres(scenario=SCEN[scen], taux_cible=(taux or 95) / 100, norme_maitre=nm, norme_salle=ns, attrition=att / 100,
                            recrues_par_an=rec, part_construction=cons / 100, hypothese_prive=prive, quantile_tendance=qt, cout_deplacement=cout, horizon=hor)
        res, secondes = resoudre(params)
        # ---- carte
        sim = res if mode == "sim" else None
        sel = SCOPE[0] if len(SCOPE) == 1 else None
        if mode == "sim" and not res.realisable:
            carte_slot.markdown(f"<div class='state'><h2 class='t'>Scénario non résolu</h2><p>{res.message}</p></div>", unsafe_allow_html=True)
        else:
            i = ind.construire(mode, choix, D45, sim, nm, ns, vue, annee=hor)

            def tip(code):
                r = D45.loc[code]
                s = f"{r.nom_province_ancien}" + (" (chiffres non divisibles : Soum/Tapoa se scindent en deux provinces)" if code in NON_DIV else "")
                s += f"\n{r.eleves_par_maitre:.0f} élèves par enseignant · {r.nb_eleves / r.nb_salles_classe:.0f} élèves par salle"
                v = i.valeurs.get(code)
                if v is not None and not i.nom.startswith("Élèves par"):          # les deux ratios sont déjà écrits plus haut
                    s += f"\n{i.nom} : {i.texte(v)} {i.unite}".rstrip()
                return s
            valeurs = {c: v for c, v in i.valeurs.items()}
            utiles = {c: v for c, v in valeurs.items() if v is not None and v == v}
            a_nommer = sorted((c for c in utiles if c in SCOPE), key=lambda c: utiles[c], reverse=i.pire_haut)[:5]          # les 5 provinces les plus préoccupantes
            tout = st.session_state.cache_g and st.session_state.cache_d
            HC = 600 if tout else 490
            fig = (carte_satellite if satellite else carte_interactive).figure_carte(valeurs, i.couleur, i.texte, tip, hauteur=HC, selection=sel, hachure_de=i.hachure, non_divisibles=NON_DIV, couches=couches,
                                     mesure=(NOMS47[m1], NOMS47[m2]) if trace else None, noms_visibles=a_nommer, texte_sur=i.texte_sur, surligner=set(SCOPE) if (FILTRE_ACTIF and not VIDE) else None)
            leg = "".join(f"<span><i class='{'h' if h else ''}' style='background:{c}'></i>{l}</span>" for c, l, h in i.legende)
            leg += "<span><i style='background:#D3D7DC'></i>Pas de valeur</span>"
            with carte_slot:
                st.markdown(f"<div class='legend'><b>{i.nom} · {AN if mode == 'diag' else hor}</b>{leg}</div>", unsafe_allow_html=True)
                with st.container(key="selrow"):                                    # hauteur réservée : la carte ne bouge plus quand on choisit une province
                    if st.session_state.get("f_prov"):
                        st.button("✕ Désélectionner la province", key="bt_desel", on_click=lambda: st.session_state.update(f_prov=[]))
                    else:
                        st.markdown("<div class='hint' style='margin:0'>" + ("Fond satellite : survolez un point jaune (centroïde) pour lire les chiffres de la province ; filtrez avec la liste « Provinces »." if satellite
                                    else "Cliquez sur une province pour voir ses chiffres.") + "</div>", unsafe_allow_html=True)
                st.plotly_chart(fig, use_container_width=True, key=f"carte_plane_{st.session_state.get('carte_n', 0)}",
                                on_select=_au_clic_carte, selection_mode="points",
                                config={"scrollZoom": True, "displaylogo": False, "modeBarButtonsToRemove": ["select2d", "lasso2d", "autoScale2d"],
                                        "toImageButtonOptions": {"filename": "carte_provinces", "format": "png"}})
            carte_slot.markdown(f"<div class='hint'>Le nombre écrit sur chaque province est la valeur de l'indicateur ; les 5 provinces les plus préoccupantes sont nommées. "
                                f"Les filtres du haut limitent la carte et tous les chiffres à une sélection de provinces. * Soum et Tapoa : chiffres non divisibles (ils se scindent en deux provinces). "
                                f"Limites : geoBoundaries ; routes et villes : Natural Earth.</div>", unsafe_allow_html=True)
            louches = D45[D45.eleves_par_maitre > 100]
            if len(louches):
                carte_slot.markdown("<div class='alert'><strong>À vérifier :</strong>" + ", ".join(f"{r.nom_province_ancien} : {r.eleves_par_maitre:.0f} élèves par enseignant" for r in louches.itertuples())
                                    + " (valeur de l'annuaire, non corrigée, très au-dessus des autres provinces).</div>", unsafe_allow_html=True)
        # ---- indicateurs (colonne de droite)
        with gr:
            with st.container(key="kpis"):
                sc = D45.loc[SCOPE]
                unique = len(SCOPE) == 1
                if FILTRE_ACTIF and not VIDE:
                    etiq = f"Province : {sc.iloc[0].nom_province_ancien}" if unique else f"Sélection : {len(SCOPE)} provinces"
                    st.markdown(f"<div class='kpihd'><span class='chip'>{etiq}</span><span class='hint' style='margin:0'>{AN if mode == 'diag' else hor}</span></div>", unsafe_allow_html=True)
                else:
                    titre = "Indicateurs" if mode == "diag" else f"Résultats en {hor}"
                    st.markdown(f"<div class='kpihd'><h2 class='t'>{titre}</h2><span class='hint' style='margin:0'>{AN if mode == 'diag' else 'après affectation'}</span></div>", unsafe_allow_html=True)
                els = sc["nb_eleves"].sum(); mt = sc["enseignants_tenant_classe"].sum()
                st.markdown(f"<div class='kpisub'>{fmt(len(sc))} province{'s' if len(sc) > 1 else ''} · {fmt(els / 1e6, 2) + ' M' if els >= 1e6 else fmt(els)} élèves · {fmt(mt)} enseignants en classe ({AN})</div>", unsafe_allow_html=True)
                if mode == "diag":
                    rat = sc.nb_eleves.sum() / sc.enseignants_tenant_classe.sum()
                    nat = D45.nb_eleves.sum() / D45.enseignants_tenant_classe.sum()
                    pire = sc.sort_values("eleves_par_maitre").iloc[-1]
                    mm = du.besoin(sc, nm).clip(lower=0).sum(); ms = du.besoin(sc, ns, "nb_eleves", "nb_salles_classe").clip(lower=0).sum()
                    e3 = sc.eleves_plus_3km.sum(); b3 = sc.nb_eleves_base_distance.sum()
                    ro = sc[sc.a_rouvrir == 1]
                    suspect = " (valeur à vérifier)" if pire.eleves_par_maitre > 100 else ""
                    kp = [("Élèves par enseignant", f"{rat:.0f}<small>{'dans la province' if unique else 'moyenne'}</small>",
                           (f"Moyenne du pays : {nat:.0f}. Norme retenue : {nm} (hypothèse)." if unique else f"Plus chargée : {pire.nom_province_ancien} ({pire.eleves_par_maitre:.0f}){suspect}. Norme retenue : {nm} (hypothèse).")),
                          ("Enseignants manquants", fmt(mm), f"Pour atteindre {nm} élèves par enseignant (hypothèse)."),
                          ("Salles de classe manquantes", fmt(ms), f"Pour atteindre {ns} élèves par salle (hypothèse)."),
                          ("Élèves à plus de 3 km d'une école", fmt(e3), (f"Soit {e3 / b3 * 100:.1f} % des élèves ayant déclaré leur distance (annuaire, public)." if b3 else "Distance non renseignée.")),
                          (("Province à rouvrir ?", "Oui" if len(ro) else "Non", "Taux de scolarisation sous 60 % de celui de 2020.") if unique else
                           ("Provinces à rouvrir", fmt(len(ro)), ("Taux sous 60 % de celui de 2020 : " + ", ".join(ro.nom_province_ancien.head(4)) + ("…" if len(ro) > 4 else "")) if len(ro) else "Aucune province sous le seuil de 60 % du taux de 2020."))]
                else:
                    kp = []
                    if res.realisable:
                        p = res.provinces.loc[SCOPE]
                        av_m = (p.besoin_maitres - p.m_maitres_apres_departs).clip(lower=0).sum(); ap_m = p.m_manque_restant.sum()
                        av_s = (p.besoin_salles - p.salles_2024).clip(lower=0).sum(); ap_s = p.s_manque_restant.sum()
                        acc = p.eleves_accueillis.sum() / p.eleves_2030.sum()
                        cm, cs = p.m_couverture.min(), p.s_couverture.min()
                        kp = [("Salles à construire", fmt(p.s_salles_a_construire.sum()), f"Salles manquantes : {fmt(av_s)} avant, {fmt(ap_s)} après construction."),
                              ("Enseignants à recruter", fmt(p.m_recrues_affectees.sum()), f"{fmt(p.m_redeploye_sortant.sum())} redéployés entre provinces. Manquants : {fmt(av_m)} avant, {fmt(ap_m)} après."),
                              ("Élèves accueillis", pct(acc, 0), f"Élèves ayant à la fois une salle et un enseignant, sur {fmt(p.eleves_2030.sum())}."),
                              ("Province la moins couverte" if not unique else "Couverture de la province", f"{min(cm, cs) * 100:.0f}<small>%</small>", f"Enseignants : {cm * 100:.0f} %. Salles : {cs * 100:.0f} %."),
                              (f"Élèves du public en {hor}", fmt(p.eleves_2030.sum()), f"Population INSD {hor} × taux visé ({scen.lower()}).")]
                for l, v, dsc in kp:
                    st.markdown(f"<div class='kpi' title=\"{dsc}\"><div class='k-l'><b>{l}</b><span>{dsc}</span></div><div class='k-v num'>{v}</div></div>", unsafe_allow_html=True)
        # ---- bas : affectation et comparaison (simulation)
        if mode == "sim" and res.realisable:
            ga, gb = st.columns(2, gap="medium")
            with ga:
                with st.container(key="affect"):
                    p = res.provinces.loc[SCOPE].copy()
                    p["recu"] = p.m_recrues_affectees + p.m_redeploye_entrant
                    top = p.sort_values("recu", ascending=False).head(8)
                    st.markdown("<h2 class='t'>Où vont les enseignants</h2><table class='t'><thead><tr><th>Province</th><th class='n'>Recrues</th><th class='n'>Redéployés reçus</th><th class='n'>Redéployés partis</th><th class='n'>Couverture</th></tr></thead><tbody>"
                                + "".join(f"<tr><td>{r.nom_province_ancien}</td><td class='n'>{fmt(r.m_recrues_affectees)}</td><td class='n'>{fmt(r.m_redeploye_entrant)}</td><td class='n'>{fmt(r.m_redeploye_sortant)}</td><td class='n'>{r.m_couverture * 100:.0f} %</td></tr>" for r in top.itertuples())
                                + "</tbody></table>", unsafe_allow_html=True)
                    nom45 = res.provinces.nom_province_ancien
                    flux = sorted([f for f in res.flux if f[0] in SCOPE or f[1] in SCOPE], key=lambda f: -f[2])
                    if flux:
                        st.markdown("<div class='hint' style='margin-top:10px'><b>Déplacements d'enseignants les plus importants</b></div><ul class='flux'>"
                                    + "".join(f"<li>{nom45[i]} → {nom45[j]} : <b>{fmt(q)}</b> enseignants, {ad.km(i, j):.0f} km</li>" for i, j, q in flux[:5]) + "</ul>", unsafe_allow_html=True)
                        autre = "distance" if params.cout_deplacement == "priorite" else "priorite"
                        res_b, _ = resoudre(replace(params, cout_deplacement=autre))
                        km_a, km_b = res.synthese["maitres_km"], res_b.synthese["maitres_km"]
                        nom_a, nom_b = ("coûts de priorité", "distances réelles") if params.cout_deplacement == "priorite" else ("distances réelles", "coûts de priorité")
                        egal = all(res.synthese[k] == res_b.synthese[k] for k in ("recrues_affectees", "maitres_redeployes", "manque_maitres_apres"))
                        memes = "Mêmes totaux (recrues, enseignants déplacés, manque restant) : seule la répartition change." if egal else "Les totaux ne sont pas identiques entre les deux calculs : voir les chiffres ci-dessus."
                        st.markdown(f"<div class='hint'>Avec les {nom_a} : {fmt(res.synthese['maitres_redeployes'])} enseignants déplacés, {fmt(km_a)} enseignants·km au total ({res.synthese['km_moyen_par_maitre']:.0f} km en moyenne). "
                                    f"Avec les {nom_b} : {fmt(km_b)} enseignants·km ({res_b.synthese['km_moyen_par_maitre']:.0f} km en moyenne). {memes} Distances à vol d'oiseau entre centres de provinces.</div>", unsafe_allow_html=True)
                    else:
                        st.markdown("<div class='hint' style='margin-top:10px'>Aucun enseignant n'est déplacé dans ce scénario : les recrutements suffisent à couvrir les besoins, donc le choix des provinces d'envoi ne change rien.</div>", unsafe_allow_html=True)
            with gb:
                with st.container(key="compare"):
                    lignes = []
                    for nom, code in SCEN.items():
                        if (code == "personnalise" and scen != "Personnalisé") or (code == "tendance_apprise" and scen != "Tendance apprise"):
                            continue
                        pp = Parametres(scenario=code, taux_cible=(taux or 95) / 100, norme_maitre=nm, norme_salle=ns, attrition=att / 100,
                                        recrues_par_an=rec, part_construction=cons / 100, hypothese_prive=prive, quantile_tendance=qt, cout_deplacement=cout, horizon=hor)
                        rr, _ = resoudre(pp)
                        q = rr.provinces.loc[SCOPE]
                        lignes.append((nom, nom == scen, q.eleves_2030.sum(), q.m_manque_restant.sum(), q.s_manque_restant.sum(), q.eleves_accueillis.sum() / q.eleves_2030.sum()))
                    for nom_s, p_s in st.session_state.sauves:
                        rr, _ = resoudre(p_s)
                        q = rr.provinces.loc[SCOPE]
                        lignes.append((nom_s, False, q.eleves_2030.sum(), q.m_manque_restant.sum(), q.s_manque_restant.sum(), q.eleves_accueillis.sum() / q.eleves_2030.sum()))
                    st.markdown(f"<h2 class='t'>Comparaison de scénarios</h2><table class='t'><thead><tr><th>Scénario</th><th class='n'>Élèves {hor}</th><th class='n'>Enseignants manquants</th><th class='n'>Salles manquantes</th><th class='n'>Élèves accueillis</th></tr></thead><tbody>"
                                + "".join(f"<tr class='{'sel' if s else ''}'><td>{n}</td><td class='n'>{fmt(e)}</td><td class='n'>{fmt(m)}</td><td class='n'>{fmt(sa)}</td><td class='n'>{a * 100:.0f} %</td></tr>" for n, s, e, m, sa, a in lignes)
                                + "</tbody></table><div class='hint'>Les lignes sans numéro reprennent les normes, départs, recrutements et constructions des réglages. Chaque ligne est un calcul du modèle.</div>", unsafe_allow_html=True)
                    if st.session_state.sauves:
                        with st.expander(f"Scénarios enregistrés ({len(st.session_state.sauves)})"):
                            st.button("Effacer les scénarios enregistrés", on_click=lambda: st.session_state.sauves.clear(), key="clear_sauves")
            with st.container(key="communes"):
                st.markdown("<h2 class='t'>Où construire dans chaque province ?</h2>", unsafe_allow_html=True)
                tp = comm.tableau_priorites(res.provinces.loc[SCOPE].s_salles_a_construire, n=3)
                if tp.empty:
                    st.markdown("<div class='hint'>Aucune salle à construire dans la sélection.</div>", unsafe_allow_html=True)
                else:
                    st.markdown("<div class='hint'>Le modèle dit <b>combien</b> de salles construire par province. À l'intérieur d'une province, nous n'avons ni population par commune ni données par école : "
                                "les communes ci-dessous sont des <b>pistes à examiner</b>, pas des emplacements. Elles sont classées par faible densité d'écoles connues (OpenStreetMap) seulement là où cette source est assez complète. "
                                "Ailleurs, elles sont listées par ordre alphabétique : le choix revient aux services locaux.</div>", unsafe_allow_html=True)
                    rows = []
                    for code, g in tp.groupby("code_province_ancien", sort=False):
                        fiable = (g.fiabilite == "correcte").all()
                        liste = "<br>".join(f"{r.nom_commune_nouveau} <span class='hint' style='margin:0'>({r.ecoles_osm} {"école" if r.ecoles_osm <= 1 else "écoles"} OSM, {r.km_chef_lieu:.0f} km du chef-lieu)</span>" for r in g.itertuples())
                        rows.append(f"<tr><td>{nom45[code]}</td><td class='n'>{fmt(g.salles_a_construire_province.iloc[0])}</td><td>{liste}</td>"
                                    f"<td>{'Classement indicatif (densité d’écoles OSM la plus faible en premier)' if fiable else 'Pas de classement : OpenStreetMap trop incomplet dans cette province'}</td></tr>")
                    entete = "<table class='t'><thead><tr><th>Province</th><th class='n'>Salles à construire</th><th>Communes à examiner</th><th>Fiabilité</th></tr></thead><tbody>"
                    st.markdown(entete + "".join(rows[:8]) + "</tbody></table>", unsafe_allow_html=True)
                    if len(rows) > 8:
                        with st.expander(f"Voir les {len(rows) - 8} autres provinces"):
                            st.markdown(entete + "".join(rows[8:]) + "</tbody></table>", unsafe_allow_html=True)
                    st.markdown("<div class='hint'>Sources : limites et chefs-lieux COD-AB v03 ; écoles OpenStreetMap (environ un tiers des écoles de l'annuaire 2024-2025) ; position d'une commune = son chef-lieu. "
                                "Trois communes par province, au plus. Distances à vol d'oiseau.</div>", unsafe_allow_html=True)
            with st.container(key="horizons"):
                st.markdown("<h2 class='t'>Comment les besoins évoluent selon l'année visée</h2>", unsafe_allow_html=True)
                if params.scenario == "tendance_apprise":
                    st.markdown("<div class='hint'>Non disponible avec la tendance apprise, qui est calculée pour 2030 seulement.</div>", unsafe_allow_html=True)
                else:
                    pts = []
                    for h in HORIZONS:
                        rh, _ = resoudre(replace(params, horizon=h))
                        if rh.realisable:
                            qh = rh.provinces.loc[SCOPE]
                            pts.append((h, int(qh.besoin_maitres.sum()), int(qh.m_manque_restant.sum()), int(qh.besoin_salles.sum()), int(qh.s_manque_restant.sum())))
                    hx = [x[0] for x in pts]
                    gx, gy = st.columns(2, gap="medium")
                    for col, titre_g, k_besoin, k_manque, couleur in ((gx, "Enseignants", 1, 2, "#B3261E"), (gy, "Salles de classe", 3, 4, "#B3261E")):
                        fg = go.Figure()
                        fg.add_trace(go.Scatter(x=hx, y=[x[k_besoin] for x in pts], mode="lines+markers", name="Besoin", line=dict(color="#2B6CB0", width=2), marker=dict(symbol="circle", size=6)))
                        fg.add_trace(go.Scatter(x=hx, y=[x[k_manque] for x in pts], mode="lines+markers", name="Manque restant après affectation" if k_besoin == 1 else "Manque restant après construction",
                                                line=dict(color=couleur, width=2, dash="dash"), marker=dict(symbol="diamond", size=7)))
                        fg.add_shape(type="line", x0=hor, x1=hor, y0=0, y1=1, yref="paper", line=dict(dash="dot", color="#6B7785", width=1.5))
                        fg.add_annotation(x=hor, y=1.02, yref="paper", text=f"année choisie : {hor}", showarrow=False, font=dict(size=12, color="#46515E"))
                        fg.update_layout(title=dict(text=titre_g, font=dict(size=15)), height=330, margin=dict(l=10, r=10, t=50, b=10), paper_bgcolor="#fff", plot_bgcolor="#fff",
                                         legend=dict(orientation="h", y=-0.18), yaxis=dict(title="Nombre", tickformat=","), xaxis=dict(title="Année visée", dtick=1))
                        col.plotly_chart(fg, use_container_width=True, key=f"hor_{titre_g}", config={"displaylogo": False})
                    st.markdown("<div class='hint'>Chaque point est un calcul complet du modèle, avec vos réglages et la sélection de provinces en cours. "
                                "Le besoin suit la population de 6 à 11 ans (projection INSD) et le niveau de scolarisation du scénario ; les recrutements s'accumulent depuis 2025. "
                                "Les départs d'enseignants sont comptés sur la durée.</div>", unsafe_allow_html=True)
            st.markdown(f"<div class='hint'>Scénario résolu en {secondes:.2f} s · {res.message}</div>", unsafe_allow_html=True)

        # ---- bas : points d'attention et graphiques
        b1, b2 = st.columns([1.15, 1.05], gap="medium")
        with gr:                                  # les points d'attention remplissent la colonne de droite, sous les indicateurs
            with st.container(key="reco"):
                if mode == "diag":
                    top5 = sc.sort_values("eleves_par_maitre", ascending=False).head(5)
                    st.markdown("<h2 class='t'>Points d'attention</h2><ol class='reco'>" + "".join(
                        f"<li><span class='badge'>{n + 1}</span><span><b>{r.nom_province_ancien}</b> : {r.eleves_par_maitre:.0f} élèves par enseignant et {r.nb_eleves / r.nb_salles_classe:.0f} par salle.</span></li>"
                        for n, r in enumerate(top5.itertuples())) + "</ol>", unsafe_allow_html=True)
                elif res.realisable:
                    q = res.provinces.loc[SCOPE]
                    q = q[(q.m_manque_restant > 0) | (q.s_manque_restant > 0)].sort_values(["m_manque_restant", "s_manque_restant"], ascending=False).head(5)

                    def manque(r):
                        parts = [f"{fmt(r.m_manque_restant)} enseignants" if r.m_manque_restant > 0 else "", f"{fmt(r.s_manque_restant)} salles" if r.s_manque_restant > 0 else ""]
                        return " et ".join(x for x in parts if x)
                    corps = ("<ol class='reco'>" + "".join(f"<li><span class='badge'>{n + 1}</span><span><b>{r.nom_province_ancien}</b> : il manquera encore {manque(r)}.</span></li>"
                                                         for n, r in enumerate(q.itertuples())) + "</ol><div class='hint'>Classement par enseignants manquants, puis par salles manquantes, après affectation.</div>"
                             ) if len(q) else f"<div class='hint'>Avec ces réglages, aucune province ne manque d'enseignants ni de salles en {hor}.</div>"
                    st.markdown("<h2 class='t'>Où agir en priorité</h2>" + corps, unsafe_allow_html=True)
        if mode == "diag":
            with b1:
                with st.container(key="graph1"):
                    st.markdown("<h2 class='t'>Quelles provinces sont les plus chargées ?</h2>", unsafe_allow_html=True)
                    st.plotly_chart(graph.classement_charge(D45.loc[SCOPE], nm), use_container_width=True, key="g_rang", config={"displaylogo": False})
            with b2:
                with st.container(key="graph2"):
                    if sel is not None:
                        nom_sel = D45.loc[sel, "nom_province_ancien"]
                        st.markdown(f"<h2 class='t'>{nom_sel} depuis 2017-2018</h2>", unsafe_allow_html=True)
                        st.plotly_chart(graph.trajectoires([(sel, nom_sel)], "Élèves par enseignant", AN, nm), use_container_width=True, key="g_traj", config={"displaylogo": False})
                        st.markdown("<div class='hint'>Élèves par enseignant dans la province (trait plein) et dans le pays (pointillé). Autres indicateurs et comparaison de provinces : onglet Analyse des provinces.</div>", unsafe_allow_html=True)
                    else:
                        st.markdown("<h2 class='t'>Comment la charge a-t-elle évolué ?</h2>", unsafe_allow_html=True)
                        st.plotly_chart(graph.tendance_nationale(nm, ns, AN), use_container_width=True, key="g_tend", config={"displaylogo": False})
                        t_ = graph.tendance()
                        manque = [f"{r.annee} ({r.provinces_enseignants} provinces)" for r in t_.itertuples() if r.provinces_enseignants < 45]
                        st.markdown("<div class='hint'>Ratios nationaux du public ; le trait vertical marque l'année choisie."
                                    + (" Années calculées sur les provinces renseignées : " + ", ".join(manque) + "." if manque else "") + "</div>", unsafe_allow_html=True)
        elif res.realisable:
            q = res.provinces.loc[SCOPE].copy()
            q["cm_avant"] = q.m_maitres_apres_departs / q.besoin_maitres
            q["cs_avant"] = q.salles_2024 / q.besoin_salles
            with b1:
                with st.container(key="graph1"):
                    st.markdown("<h2 class='t'>Enseignants : couverture avant et après</h2>", unsafe_allow_html=True)
                    st.plotly_chart(graph.avant_apres(q, "cm_avant", "m_couverture", "Besoin en enseignants couvert"), use_container_width=True, key="g_cm", config={"displaylogo": False})
                    st.markdown("<div class='hint'>Les 15 provinces les moins couvertes après affectation.</div>", unsafe_allow_html=True)
            with b2:
                with st.container(key="graph2"):
                    st.markdown("<h2 class='t'>Salles : couverture avant et après</h2>", unsafe_allow_html=True)
                    st.plotly_chart(graph.avant_apres(q, "cs_avant", "s_couverture", "Besoin en salles couvert"), use_container_width=True, key="g_cs", config={"displaylogo": False})
                    st.markdown("<div class='hint'>Les 15 provinces les moins couvertes après construction.</div>", unsafe_allow_html=True)

# ------------------------------------------------------------------ onglet 2
with t2:
    d = D47[D47.code_province_ancien.isin(SCOPE)].copy()
    d["groupe"] = d.code_province_ancien.map(D47_RECENT.drop_duplicates("code_province_ancien").set_index("code_province_ancien").groupe)   # profils calculés sur 2024-2025
    d["profil"] = d.groupe.map(du.profils())
    d["eleves_par_salle_c"] = d.nb_eleves / d.nb_salles_classe
    if FILTRE_ACTIF and not VIDE:
        st.markdown(f"<div class='hint'>Filtres actifs : {len(SCOPE)} provinces sur {len(D45)} (barre du haut).</div>", unsafe_allow_html=True)
    p1, p2 = st.columns([1, 2.2], gap="medium")
    with p1:
        with st.container(key="diagcard"):
            st.markdown("<p class='eyebrow'>Analyse des provinces</p><h2 class='t'>Où sont les déséquilibres ?</h2>", unsafe_allow_html=True)
            filtre = st.segmented_control("Profil", ["Toutes"] + sorted(d.profil.dropna().unique()), default="Toutes", key="profil", selection_mode="single") or "Toutes"
            masque = d if filtre == "Toutes" else d[d.profil == filtre]
            st.markdown("<h3 class='t'>Les 5 provinces les plus chargées</h3>", unsafe_allow_html=True)
            top = masque.drop_duplicates("code_province_ancien").sort_values("eleves_par_maitre", ascending=False).head(5)
            st.markdown("<ol class='reco'>" + "".join(f"<li><span class='badge'>{n + 1}</span><span><b>{r.nom_province_ancien}</b> : {r.eleves_par_maitre:.0f} élèves par enseignant</span></li>"
                                                      for n, r in enumerate(top.itertuples())) + "</ol>", unsafe_allow_html=True)
            st.markdown("<div class='hint'>Les profils viennent d'un regroupement automatique (K-Means, graine 42) sur les ratios, la scolarisation, la distance et l'état des murs.</div>", unsafe_allow_html=True)
    with p2:
        with st.container(key="dataA"):
            u = masque.drop_duplicates("code_province_ancien")
            fig = px.scatter(u, x="eleves_par_salle_c", y="eleves_par_maitre", size="nb_eleves", color="profil", hover_name="nom_province_ancien",
                             labels={"eleves_par_salle_c": "Élèves par salle", "eleves_par_maitre": "Élèves par enseignant", "profil": "Profil", "nb_eleves": "Élèves"},
                             color_discrete_map={"Provinces les moins chargées": "#2B6CB0", "Provinces à charge intermédiaire": "#E9A20F", "Provinces les plus chargées": "#B3261E"}, size_max=34)
            u = u.assign(etiq="")
            _top = u.sort_values("eleves_par_maitre", ascending=False).head(5).index
            u.loc[_top, "etiq"] = u.nom_province_ancien
            _pos = dict(zip(_top, ["middle left", "top center", "top right", "middle right", "top left"]))     # positions alternées : pas de chevauchement
            fig.update_traces(text=None)
            for tr in fig.data:
                pts = u[u.profil == tr.name]
                tr.text = pts.etiq.tolist(); tr.mode = "markers+text"; tr.textposition = [_pos.get(ix, "top center") for ix in pts.index]; tr.textfont = dict(size=12, color="#1F2933")
            fig.add_hline(y=50, line_dash="dot", annotation_text="norme de référence : 50 (hypothèse)")
            fig.add_vline(x=50, line_dash="dot")
            fig.update_layout(height=450, margin=dict(l=10, r=10, t=30, b=10), paper_bgcolor="#fff", plot_bgcolor="#fff", legend_title_text="", legend=dict(orientation="h", y=-0.18, x=0))
            _hors = u[(u.eleves_par_maitre > 95) | (u.eleves_par_salle_c > 95)]                 # valeurs extrêmes : hors échelle, signalées plutôt que d'écraser le nuage
            _dans = u.drop(_hors.index)
            if len(_hors) and len(_dans):
                _xm = float(max(_dans.eleves_par_salle_c.max(), 60)) + 8; _ym = float(max(_dans.eleves_par_maitre.max(), 60)) + 8
                fig.update_xaxes(range=[max(float(_dans.eleves_par_salle_c.min()) - 6, 0), _xm]); fig.update_yaxes(range=[max(float(_dans.eleves_par_maitre.min()) - 6, 0), _ym])
                for r in _hors.itertuples():
                    fig.add_annotation(x=min(max(r.eleves_par_salle_c, 0), _xm - 4), y=_ym, yref="y", xref="x", ax=0, ay=30, showarrow=True, arrowhead=2,
                                       text=f"{r.nom_province_ancien} : {r.eleves_par_maitre:.0f} (hors échelle, valeur à vérifier)", font=dict(size=12, color="#7A1519"), xanchor="right", yanchor="bottom")
            st.plotly_chart(fig, use_container_width=True)
            st.markdown("<div class='hint'>Chaque bulle est une province ; sa taille est proportionnelle au nombre d'élèves. Les 5 provinces les plus chargées sont nommées.</div>", unsafe_allow_html=True)
    with st.container(key="dataG"):
        st.markdown("<p class='eyebrow'>Série 2017-2018 → 2024-2025</p><h3 class='t'>Comment chaque province a-t-elle évolué ?</h3>", unsafe_allow_html=True)
        ind_s = st.segmented_control("Indicateur", list(du.INDICATEURS_SERIE), default="Élèves par enseignant", key="ind_serie", selection_mode="single") or "Élèves par enseignant"
        noms45 = D45.sort_values("nom_province_ancien")
        defaut = list(D45.sort_values("eleves_par_maitre", ascending=False).nom_province_ancien.head(3))
        choisis = st.multiselect("Provinces à comparer (6 au plus)", list(noms45.nom_province_ancien), default=defaut, max_selections=6, key="prov_serie")
        paires = [(noms45.index[noms45.nom_province_ancien == n][0], n) for n in choisis]
        st.plotly_chart(graph.trajectoires(paires, ind_s, AN, 50 if ind_s == "Élèves par enseignant" else (50 if ind_s == "Élèves par salle" else None)),
                        use_container_width=True, key="g_serie", config={"displaylogo": False})
        M_, nat_ = du.serie(ind_s)
        tb = pd.DataFrame({n: M_[c] for c, n in paires}); tb.insert(0, "National", nat_)
        st.dataframe(tb.round(1).rename_axis("Année scolaire").reset_index(), use_container_width=True, hide_index=True)
        st.markdown("<div class='hint'>Le trait vertical marque l'année choisie en haut de la page. Une case vide veut dire que l'annuaire ne donne pas la valeur. "
                    "Les 2 années 2022-2023 et 2023-2024 reflètent surtout la fermeture puis la réouverture d'écoles dans les provinces touchées.</div>", unsafe_allow_html=True)
    with st.container(key="dataB"):
        st.markdown("<h3 class='t'>Les 47 provinces en détail</h3>", unsafe_allow_html=True)
        tab = masque[["nom_province_nouveau", "nom_province_ancien", "eleves_par_maitre", "eleves_par_salle_c", "taux_brut_scolarisation", "pct_plus_de_3_km", "a_rouvrir", "profil", "chiffres_non_divisibles"]].copy()
        tab.columns = ["Province", "Ancienne province (calcul)", "Élèves par enseignant", "Élèves par salle", "Taux brut (public)", "Élèves à plus de 3 km (%)", "À rouvrir", "Profil", "Chiffres non divisibles"]
        tab["À rouvrir"] = tab["À rouvrir"].map({1: "Oui", 0: "Non"}); tab["Chiffres non divisibles"] = tab["Chiffres non divisibles"].map({1: "Oui", 0: ""})
        st.dataframe(tab.round(1), use_container_width=True, hide_index=True)

# ------------------------------------------------------------------ onglet 3
with t3:
    st.markdown("<p class='eyebrow'>Données et méthode</p><h2 class='t'>D'où viennent les chiffres ?</h2>", unsafe_allow_html=True)
    st.markdown("<div class='kpisub' style='font-size:14.5px;color:var(--ink)'><ul style='margin:0 0 8px 18px;padding:0'>"
                "<li><b>Qui produit les chiffres :</b> les annuaires statistiques de la DGESS (ministère), pour 2017-2018 à 2024-2025 ; les projections de population de l'INSD pour 2030.</li>"
                "<li><b>Ce qui est observé :</b> le diagnostic (carte, indicateurs, évolution). <b>Ce qui est simulé :</b> la situation en 2030, selon des hypothèses que vous réglez.</li>"
                "<li><b>Ce qui est une hypothèse :</b> les normes, les départs, les recrutements, les constructions. Elles sont listées ci-dessous, avec leur statut.</li></ul></div>", unsafe_allow_html=True)
    cols = st.columns(2, gap="medium")
    with cols[0]:
        with st.container(key="dataD"):
            st.markdown("<h3 class='t'>Hypothèses utilisées</h3><table class='t'><thead><tr><th>Élément</th><th class='n'>Valeur</th><th>Statut</th></tr></thead><tbody>"
                        "<tr><td>Élèves par enseignant</td><td class='n'>50 (45 et 40 en objectif)</td><td>Hypothèse : aucune norme officielle trouvée</td></tr>"
                        "<tr><td>Élèves par salle</td><td class='n'>50</td><td>Hypothèse</td></tr>"
                        "<tr><td>Départs d'enseignants par an</td><td class='n'>0 à 5 %</td><td>Inconnu : à tester</td></tr>"
                        "<tr><td>Recrutements par an</td><td class='n'>3 887</td><td>Plan sectoriel, action 8.1.2 : à revérifier</td></tr>"
                        "<tr><td>Salles constructibles d'ici 2030</td><td class='n'>0 à 100 % du besoin</td><td>Hypothèse : aucun budget connu</td></tr>"
                        "<tr><td>Coûts de déplacement (priorité)</td><td class='n'>0,5 / 1 / 3</td><td>Hypothèse de priorité, pas des coûts réels</td></tr>"
                        "<tr><td>Évolution du privé</td><td class='n'>2 hypothèses</td><td>À discuter</td></tr></tbody></table>", unsafe_allow_html=True)
    with cols[1]:
        with st.container(key="dataE"):
            st.markdown("<h3 class='t'>À savoir avant de décider</h3><ul>"
                        "<li>Le modèle porte sur les <b>écoles publiques</b> : l'État ne construit et n'affecte que dans le public.</li>"
                        "<li>Les calculs portent sur <b>45 anciennes provinces</b>, restitués pour 47. <b>Soum</b> et <b>Tapoa</b> se scindent en deux : leurs chiffres ne sont pas divisibles, les deux moitiés portent la même valeur.</li>"
                        "<li>Les <b>régions</b> ne sont pas encore affichées : les anciennes (13) et les nouvelles (17) ne se recoupent pas.</li>"
                        "<li>La <b>distance à l'école</b> vient d'un tableau de l'annuaire, rempli par les écoles : elle est déclarative.</li>"
                        "<li>Chaque scénario est résolu par un programme d'optimisation (PuLP, solveur CBC) en deux étapes : on maximise d'abord la couverture de la province la moins bien servie, puis on minimise le manque total et les déplacements.</li>"
                        "<li>Le post-primaire et le secondaire seront ajoutés si les données le permettent.</li></ul>", unsafe_allow_html=True)
    with st.container(key="dataF"):
        from dashboard_lib import entrainement
        mm = entrainement.charger().metriques
        cm = mm['comparaison_methodes']
        pc = lambda x: f"{x * 100:.1f} %".replace(".", ",")
        st.markdown("<h3 class='t'>Modèle appris : effectifs d'élèves par province</h3>"
                    "<p class='hint'>Le modèle apprend sur 2017-2018 → 2024-2025 la croissance courante et le retour vers le niveau d'avant la crise. "
                    "Il est testé sur des années qu'il n'a pas vues et comparé aux autres façons de projeter. "
                    "La méthode des scénarios (taux de 2024 × population projetée) est la meilleure testée ; le modèle appris ne la bat pas : il reste une hypothèse, pas une prévision.</p>"
                    "<table class='t'><thead><tr><th>Méthode</th><th class='n'>Erreur moyenne</th><th class='n'>Erreur maximale</th></tr></thead><tbody>"
                    + "".join(f"<tr{' style=\"background:#E3F0E4;font-weight:600\"' if k == 'taux_constant' else ''}><td>{lib}</td><td class='n'>{pc(cm['erreur_moyenne'][k])}</td><td class='n'>{pc(cm['erreur_maximale'][k])}</td></tr>"
                              for k, lib in (("taux_constant", "Taux de 2024 × population projetée (scénarios)"), ("taux_moyen_2_ans", "Taux moyen sur 2 ans × population projetée"), ("effectifs_constants", "Effectifs de la dernière année maintenus")))
                    + f"</tbody></table><div class='hint'>Erreur = écart par province, en % du total d'élèves, sur {cm['nb_previsions']} prévisions de {cm['periode'][0]} à {cm['periode'][1]}. "
                    "Un écart d'environ 10 % reste possible : les chocs de sécurité ne se prévoient pas avec 5 années d'historique.</div>"
                    "<p class='hint'>Modèle appris sur 2017-2025 (croissance et retour vers le niveau d'avant la crise) :</p>"
                    "<table class='t'><thead><tr><th>Modèle</th><th class='n'>Erreur sur les provinces</th><th class='n'>Erreur sur le total national</th></tr></thead><tbody>"
                    f"<tr><td>Référence : effectifs de 2024 maintenus</td><td class='n'>{pc(mm['reference_statu_quo']['erreur_provinces_pct_eleves'])}</td><td class='n'>{pc(mm['reference_statu_quo']['erreur_nationale_moyenne'])}</td></tr>"
                    f"<tr><td>Modèle appris ({mm['candidat_retenu'].replace('_', ' ')})</td><td class='n'>{pc(mm['modele']['erreur_provinces_pct_eleves'])}</td><td class='n'>{pc(mm['modele']['erreur_nationale_moyenne'])}</td></tr>"
                    f"</tbody></table><div class='hint'>{mm['nb_previsions_testees']} prévisions testées, au moins 4 années d'apprentissage. "
                    "Seulement 8 années d'historique et un choc en 2022-2023 : les écarts sont larges.</div>", unsafe_allow_html=True)
    with st.expander("Pour les spécialistes : sources détaillées"):
        with st.container(key="dataC"):
            st.markdown("<h3 class='t'>Sources</h3>", unsafe_allow_html=True)
            s = du.sources()
            if len(s):
                st.markdown("<table class='t'><thead><tr><th>Donnée</th><th>Producteur</th><th>Période</th><th>Usage</th></tr></thead><tbody>" + "".join(
                    f"<tr><td>{r.publication}</td><td>{r.producteur}</td><td>{r.annee}</td><td>{r.usage}</td></tr>" for r in s.itertuples()) + "</tbody></table>", unsafe_allow_html=True)
    with st.expander("Pour les spécialistes : reproduire et vérifier"):
        with st.container(key="dataH"):
            import importlib.metadata as _md
            from dashboard_lib import modele as _mod
            _d = _mod.donnees()
            ver = ", ".join(f"{n} {_md.version(n)}" for n in ("streamlit", "plotly", "pandas", "numpy", "scikit-learn", "PuLP", "shapely"))
            st.markdown("<h3 class='t'>Reproduire et vérifier</h3>"
                        "<table class='t'><tbody>"
                        f"<tr><td>Empreinte des données d'entrée et du code d'analyse</td><td><code>{_d.empreinte}</code></td></tr>"
                        f"<tr><td>Empreinte des données du modèle appris</td><td><code>{entrainement.charger().empreinte_donnees}</code></td></tr>"
                        f"<tr><td>Versions des outils</td><td>{ver}</td></tr>"
                        "<tr><td>Aléatoire</td><td>aucun tirage dans le calcul ; regroupement en profils : graine 42</td></tr>"
                        "<tr><td>Relancer</td><td><code>streamlit run app.py</code> ; contrôles : <code>python tests/test_modele.py</code></td></tr>"
                        "</tbody></table><div class='hint'>Deux calculs avec les mêmes empreintes et les mêmes réglages donnent les mêmes résultats. "
                        "Chaque scénario est résolu par le solveur et son statut est affiché sous les tableaux.</div>", unsafe_allow_html=True)
    if st.session_state.get("mode_dernier") is None:
        pass
    st.markdown("<div class='foot'>Reproduction : voir README_DASHBOARD.md. Les résultats se régénèrent depuis les tables du dossier 02_DONNEES.</div>", unsafe_allow_html=True)
    if niveau.startswith("Primaire"):
        e47 = en_47(res.provinces) if (niveau.startswith('Primaire') and res.realisable) else None
        if e47 is not None:
            st.download_button("Télécharger le scénario en cours (47 provinces, CSV)", e47.to_csv(sep=";", index=False).encode("utf-8-sig"),
                               file_name="scenario_en_cours_47provinces.csv", mime="text/csv")
        st.download_button(f"Télécharger le diagnostic {AN} (47 provinces, CSV)", D47.to_csv(sep=";", index=False).encode("utf-8-sig"),
                           file_name=f"diagnostic_{AN}_47provinces.csv", mime="text/csv")

st.markdown(f"<div class='foot'>Sources : annuaires statistiques DGESS (MENAPLN), projections démographiques INSD (RGPH 2019), limites geoBoundaries · année affichée : {AN}. Détail et hypothèses : onglet « Données et méthode ».</div>", unsafe_allow_html=True)
