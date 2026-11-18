"""Style du tableau de bord, repris de la maquette v6 : fond crème, bandeau vert, cartes blanches, contrastes élevés."""

CSS = """
<style>
:root{--bg:#FFFFFF;--card:#FFFFFF;--ink:#1F2933;--ink2:#4B5563;--line:#D5DBE1;--g:#1B6B45;--gsoft:#E3F0E4;--hd2:#1D5A3C;
--a:#E9A20F;--asoft:#FCEFC8;--aink:#664300;--r:#B3261E;--rsoft:#FBE4E1;--blue:#2B6CB0;--soft:#F7F8FA;--focus:#0B57D0}
.stApp{background:var(--bg);color:var(--ink)}
#MainMenu,footer,header[data-testid="stHeader"],[data-testid="stToolbar"],[data-testid="stDecoration"]{display:none!important}
.block-container{padding:0 24px 32px 24px!important;max-width:100%!important}
.stApp, .stApp p, .stApp label, .stApp span, .stApp div{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",system-ui,Roboto,"Helvetica Neue",Arial,sans-serif}
.num{font-variant-numeric:tabular-nums}
/* bandeau unique : identité + filtres (v6 : bandeau vert, filet tricolore) */
.st-key-subbar{background:var(--hd2);padding:8px 24px 10px!important;margin:0 -24px;width:auto!important;max-width:none!important;box-sizing:border-box}
.st-key-subbar [data-testid="stHorizontalBlock"]{align-items:center;gap:16px}
.tri{margin:-22px -24px 0 -24px;height:5px;background:linear-gradient(#EF2B2D 0 50%,#009E49 50% 100%)}
.bandeau{background:var(--hd2);margin:-26px -24px 0 -24px;padding:8px 24px;box-sizing:border-box}
.brand{display:flex;gap:14px;align-items:center}
.brand img{height:44px;width:auto;background:#fff;border-radius:4px;padding:2px}
.brand .min{display:block;font-size:12px;letter-spacing:.02em;color:#D6E8DC;line-height:1.3;max-width:none}
.brand h1{margin:2px 0 0;font-size:22px;line-height:1.2;font-weight:700;color:#fff;padding:0}
.st-key-subbar label p{color:#D6E8DC!important;font-size:12px!important}
.st-key-subbar [data-baseweb="select"]>div{background:#27694A!important;border-color:#7FA891!important;color:#fff!important;min-height:40px}
.st-key-subbar [data-baseweb="select"] *{color:#fff!important}
.st-key-subbar svg{fill:#fff!important}
h1 a,h2 a,h3 a,[data-testid="stHeaderActionElements"]{display:none!important}
ul.flux{margin:4px 0 8px 0;padding-left:18px;font-size:14px;line-height:1.6}
/* barre de filtres */
.st-key-filtres{background:#fff;border-bottom:1px solid var(--line);margin:0 -24px;padding:10px 24px 10px!important;width:auto!important;max-width:none!important;box-sizing:border-box}
.st-key-filtres label p{font-size:12.5px!important;font-weight:600;color:var(--ink2)}
.st-key-filtres [data-baseweb="select"]>div{min-height:40px;max-height:76px;overflow:auto}
.st-key-filtres [data-baseweb="tag"]{height:26px;font-size:12.5px;background:var(--gsoft)!important;color:var(--g)!important}
.st-key-filtres [data-baseweb="tag"] *{color:var(--g)!important}
.st-key-filtres [data-testid="stHorizontalBlock"]{gap:12px}
.filtre-etat{background:var(--gsoft);color:var(--ink);padding:7px 24px;margin:0 -24px;font-size:13.5px;border-bottom:1px solid var(--line)}
/* onglets */
.stTabs [data-baseweb="tab-list"]{background:#fff;border-bottom:1px solid var(--line);padding:0 24px;gap:8px;margin:0 -24px}
.stTabs [data-baseweb="tab"]{height:44px;font-weight:600;color:var(--ink2)}
.stTabs [aria-selected="true"]{color:var(--ink)!important}
.stTabs [data-baseweb="tab-highlight"]{background:var(--g)!important;height:3px}
.stTabs [data-baseweb="tab-panel"]{padding:14px 0 0 0}
/* icônes Material : si la police d'icônes n'est pas chargée, on masque le texte de repli (« expand_more ») */
[data-testid="stPopover"] [data-testid="stIconMaterial"]{display:none!important}
/* cartes */
.st-key-panel,.st-key-cartecard,.st-key-affect,.st-key-compare,.st-key-communes,.st-key-horizons,.st-key-reco,.st-key-diagcard,.st-key-graph1,.st-key-graph2,.st-key-dataA,.st-key-dataB,.st-key-dataC,.st-key-dataD,.st-key-dataF,.st-key-dataG,.st-key-dataH,
.st-key-dataE{
 background:var(--card);border:1px solid var(--line);border-radius:10px;padding:16px!important}
.eyebrow{margin:0;font-size:13px;color:var(--ink2)}
h2.t{margin:2px 0 8px;font-size:19px;font-weight:700;color:var(--ink)}
h3.t{margin:0 0 8px;font-size:16px;font-weight:700;color:var(--ink)}
.tiles{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin:8px 0 12px}
.tile{background:var(--soft);border-radius:6px;padding:8px 10px}
.tile b{font-size:19px;display:block;line-height:1.1;white-space:nowrap}
.tile span{font-size:12px;color:var(--ink2)}
.tag{font-size:12px;font-weight:600;padding:1px 7px;border-radius:10px;background:var(--asoft);color:var(--aink);margin-left:6px}
.tag.p{background:var(--gsoft);color:var(--g)}
.hint{font-size:13px;color:var(--ink2);margin:2px 0 10px}
.alert{background:var(--soft);border:1px solid var(--line);border-radius:6px;padding:8px 12px;margin:8px 0 0;font-size:13.5px}
.alert.e,.alert.i{background:var(--card)}
.alert strong{margin-right:6px}
.kpi{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:10px 16px;margin-bottom:8px;height:92px;box-sizing:border-box;
 display:flex;justify-content:space-between;align-items:center;gap:16px;overflow:hidden}
.kpi .k-l{min-width:0}
.kpi .k-l b{display:block;font-size:14.5px;line-height:1.25}
.kpi .k-l span{display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;font-size:12.5px;line-height:1.35;color:var(--ink2);margin-top:2px}
.kpi .k-v{flex:none;font-size:30px;font-weight:700;line-height:1.1;color:var(--ink);white-space:nowrap;text-align:right}
.kpi .k-v small{font-size:13px;font-weight:600;color:var(--ink2);margin-left:4px}
.kpi .k-v .arr{color:var(--ink2);font-size:20px}
.kpihd{display:flex;justify-content:space-between;align-items:baseline;gap:8px;margin:0 0 6px}
.kpihd h2.t{margin:0}
.chip{display:inline-block;background:var(--gsoft);color:var(--g);font-weight:700;font-size:13px;padding:3px 10px;border-radius:12px}
.kpisub{font-size:13px;color:var(--ink2);margin:0 0 8px}
.good{color:#116033}.bad{color:var(--r)}.mid{color:var(--aink)}
.legend{display:flex;flex-wrap:wrap;gap:3px 11px;margin:6px 0 0;font-size:12px;line-height:1.3}
.legend i{display:inline-block;width:14px;height:11px;border-radius:2px;border:1px solid #14231CA6;vertical-align:-1px;margin-right:4px}
.legend i.h{background:repeating-linear-gradient(45deg,#7A1519,#7A1519 2px,#fff 2px,#fff 4px)}
table.t{width:100%;border-collapse:collapse;font-size:13.5px}
table.t th{text-align:left;font-weight:700;padding:7px 8px;border-bottom:2px solid var(--line);color:var(--ink2);font-size:13px}
table.t td{padding:7px 8px;border-bottom:1px solid var(--line)}
table.t td.n,table.t th.n{text-align:right;font-variant-numeric:tabular-nums}
table.t tr.sel td{background:var(--gsoft);font-weight:600}
ol.reco{margin:6px 0 0 0;padding-left:0;list-style:none}
ol.reco li{display:flex;gap:10px;margin-bottom:10px;font-size:14px}
.badge{flex:none;min-width:26px;height:26px;border-radius:13px;background:var(--g);color:#fff;font-weight:700;display:inline-flex;align-items:center;justify-content:center;font-size:13px}
.state{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:28px;text-align:center}
.foot{padding:14px 0;color:var(--ink2);font-size:12.5px}
.stButton>button{min-height:40px;border-radius:6px;font-weight:600}
.stDownloadButton>button{min-height:40px;border-radius:6px;font-weight:600}
[data-testid="stButtonGroup"] button{min-height:40px}
[data-testid="stSelectbox"] [data-baseweb="select"]>div{min-height:40px}
.st-key-cartecard{padding:12px 14px!important}
.st-key-cartecard [data-testid="stHorizontalBlock"]{gap:10px;align-items:center}
.st-key-outils [data-testid="stHorizontalBlock"]{gap:8px;align-items:center;flex-wrap:wrap}
.st-key-outils .stButton>button,.st-key-outils [data-testid="stPopover"]>button{min-height:36px;padding:0 12px;font-size:13.5px}
.st-key-outils label p{font-size:13.5px}
:focus-visible{outline:3px solid var(--focus)!important;outline-offset:2px}
@media (max-width:1100px){
 .st-key-mainrow>[data-testid="stLayoutWrapper"]>[data-testid="stHorizontalBlock"],.st-key-mainrow [data-testid="stHorizontalBlock"]:has(>[data-testid="stColumn"] .st-key-cartecard){flex-wrap:wrap}
 .st-key-mainrow [data-testid="stColumn"]{min-width:100%!important;flex:1 1 100%!important}
 [data-testid="stColumn"]:has(.st-key-cartecard){order:1}[data-testid="stColumn"]:has(.st-key-kpis){order:2}[data-testid="stColumn"]:has(.st-key-panel){order:3}
 .brand .min{display:none}.brand h1{font-size:18px}
 .st-key-filtres [data-testid="stHorizontalBlock"]{flex-wrap:wrap;row-gap:8px}
 .st-key-filtres [data-testid="stColumn"]{flex:1 1 30%!important;min-width:200px!important}
}
.st-key-selrow{min-height:44px;display:flex;align-items:center}
.st-key-selrow .stButton button{min-height:34px}
.st-key-cartecard{position:relative}
.stApp[data-test-script-state="running"] .st-key-cartecard [data-testid="stPlotlyChart"]{opacity:.4;transition:opacity .15s .25s}
.stApp[data-test-script-state="running"] .st-key-cartecard::after{content:"Mise à jour…";position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);background:#fff;border:1px solid var(--line);border-radius:8px;padding:6px 14px;font-weight:600;color:var(--ink2);opacity:0;animation:apparait .2s .5s forwards}
@keyframes apparait{to{opacity:1}}
.legend{margin-bottom:2px}
@media (min-width:1700px){.st-key-cartecard [data-testid="stPlotlyChart"]{max-width:780px;margin:0 auto}}
.stButton button,[data-testid="stToggle"] label{min-height:34px}
</style>
"""
