# Tableau de bord d'aide à la décision : salles de classe et enseignants (primaire)

Public visé : directeur régional. Une question par écran, la carte au centre, des réglages en clair, la source et le statut de chaque valeur.

## Lancer en local
Prérequis : Python 3.11 ou plus. Le dossier DASHBOARD doit rester dans `04_CODE/`, à côté de `02_DONNEES/` (les chemins sont relatifs à cette arborescence).

| Je veux | Windows | Linux / macOS |
|---|---|---|
| Ouvrir le tableau de bord | `lancer_dashboard.bat` | `bash lancer_dashboard.sh` |
| Tout rejouer sans l'application (tests, ré-entraînement, graphiques) | `lancer_pipeline.bat` | `bash lancer_pipeline.sh` |

Ces scripts créent un environnement `.venv`, installent `requirements_dashboard.txt` puis lancent le calcul. À la main :
```
pip install -r requirements_dashboard.txt
streamlit run app.py                       # l'application
python tests/test_modele.py                # 4 contrôles
python tests/test_distance_communes.py     # 4 contrôles : distances réelles et communes
python scripts/entrainer_modele.py         # ré-entraîne et compare les méthodes -> modeles_entraines/, sorties/comparaison_methodes.csv
python scripts/exporter_graphiques.py      # cartes et graphiques en HTML -> sorties/graphiques/
```
Pendant le développement, le rechargement automatique est coupé (`fileWatcherType = "none"` dans `.streamlit/config.toml`) : après une modification d'un fichier de `dashboard_lib/`, relancer l'application.
Aucun chemin absolu, aucune clé, aucun tirage aléatoire (graine 42 pour les profils). Le dossier `sorties/` et le cache `cache_modele/` se régénèrent : on peut les supprimer.

## Ce que fait le modèle
1. **Demande 2030** : population de 6 à 11 ans projetée (INSD) × taux brut de scolarisation visé, dans le public.
2. **Affectation des enseignants** : programmation linéaire en deux étapes (PuLP, solveur CBC) : on maximise la couverture minimale, puis on minimise le manque et le coût des déplacements.
3. **Salles** : même principe, avec une capacité de construction réglable.
Chaque réglage relance le calcul et le solveur ; le statut « Optimal » est contrôlé. Un cache sur disque évite de recalculer un réglage déjà résolu.

Le code d'analyse (`modele/`) est celui du Rôle 2, importé sans modification ; `dashboard_lib/modele.py` ne fait que lui passer des réglages libres.

## Interface
Barre de filtres en haut (année, niveau, provinces, niveau de charge, profil, provinces à rouvrir) : elle limite la carte, les indicateurs et les graphiques à une sélection de provinces. Panneaux latéraux (réglages, résultats) repliables pour agrandir la carte.

La carte est cliquable : un clic sur une province filtre tout le tableau de bord sur elle. Le menu « Couches » permet d'ajouter les centroïdes des provinces (le point d'où partent les distances) et un fond satellite.

## Fond satellite (optionnel)
Images Esri World Imagery chargées depuis internet au moment de l'affichage. Sans connexion, le fond reste blanc : la carte colorée, les chiffres et les centroïdes s'affichent quand même. Les limites sont converties de kilomètres en longitude et latitude par une transformation ajustée sur 20 points de contrôle (écart moyen 0,8 km, maximum 1,8 km, fichier `donnees_carte/projection_km_vers_lonlat.json`). Sur ce fond, les points jaunes se survolent mais ne se cliquent pas : le filtre se fait par la liste « Provinces ». Aucune donnée du concours n'est envoyée aux serveurs d'images, qui ne reçoivent que des demandes de tuiles.

## Année visée
Le réglage « Année visée » (2026 à 2035, projections INSD de la population de 6 à 11 ans) remplace l'horizon fixe de 2030. Le niveau de scolarisation du scénario est atteint à cette année ; les recrutements annuels s'accumulent depuis 2025 et les départs sont comptés sur la durée. 2030 reste la valeur par défaut et donne les mêmes résultats qu'avant. La « tendance apprise » n'existe que pour 2030. Dans le code, les colonnes appelées « 2030 » (héritage du Rôle 2) valent l'année choisie. Un graphique montre l'évolution des besoins année par année.

## Où affecter, où construire
- **Distances réelles** (réglage « Choix des provinces d'envoi », simulation) : si des enseignants doivent être déplacés, le modèle choisit les provinces les plus proches (km à vol d'oiseau entre centres de provinces, `dashboard_lib/allocation_distance.py`). Le code du Rôle 2 n'est pas modifié ; la variante reprend sa logique en deux étapes avec un autre coût (hypothèse : 1 unité fixe + 1 unité par 100 km ; une recrue coûte 0,5). Le tableau de bord affiche les deux calculs côte à côte. Les totaux (recrues, enseignants déplacés, manque restant) sont identiques dans les trois scénarios prédéfinis ; seule la répartition change. Si les recrutements suffisent, rien n'est déplacé et le choix ne change rien.
- **Communes à examiner** (`dashboard_lib/communes.py`) : pour chaque province où il faut construire, trois communes à regarder en premier. Il n'y a ni population par commune ni données par école : c'est un indice, pas un emplacement. Le classement (densité d'écoles OpenStreetMap la plus faible d'abord) n'est proposé que dans les provinces où OpenStreetMap est jugé exploitable ; ailleurs, liste alphabétique sans classement. Position d'une commune = son chef-lieu (COD-AB).

## Modèle appris (`dashboard_lib/entrainement.py`)
Projection des effectifs par province apprise sur 2017-2018 → 2024-2025, testée sur des années non vues. Résultat : la méthode des scénarios (taux de 2024 × population projetée) reste la meilleure testée (environ 10 % d'écart sur les élèves) ; le modèle appris ne la bat pas. Il est proposé comme hypothèse étiquetée (« Tendance apprise »), pas comme prévision. Détail dans l'onglet « Données et méthode ».

## Limites à lire
- Normes (50 élèves par enseignant, 50 par salle), départs, constructions : hypothèses, affichées comme telles.
- 3 887 recrutements par an : à revérifier.
- Soum et Tapoa : chiffres non divisibles, un seul polygone sur la carte (45 polygones, 47 lignes dans les tableaux).
- Loroum : 112 élèves par enseignant, valeur de l'annuaire non corrigée, signalée.
- Distances à vol d'oiseau, pas par la route. Pas de coût réel de déplacement ni de construction.
- Primaire uniquement ; régions et post-primaire/secondaire non traités faute de données.

## Sources
Annuaires statistiques DGESS (MENAPLN), projections démographiques INSD (RGPH 2019), limites OCHA/IGB (geoBoundaries), routes et villes Natural Earth. Liste complète dans l'onglet « Données et méthode ».
