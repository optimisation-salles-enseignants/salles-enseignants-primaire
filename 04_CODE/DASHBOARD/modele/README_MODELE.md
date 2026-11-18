# DASHBOARD/modele : panels, diagnostics, projection 2030 et allocation (primaire)

Scripts a lancer dans l'ordre, depuis ce dossier. Chemins relatifs, graine aleatoire 42 (K-Means). Dependances : `requirements_modele.txt` (PuLP en version 3.3.0).
Les sorties vont dans `02_DONNEES/04_analyse` (tables) et `02_DONNEES/04_analyse/graphiques` (images).

| Ordre | Script | Entree | Sortie |
|---|---|---|---|
| 1 | `construire_panel_provinces.py <racine> <sortie>` | tables de `03_transformation` | panel total province x annee (v2) |
| 2 | `construire_panels_public_prive.py <racine> <sortie>` | tables de `03_transformation` | panels public et prive (v1) ; controles : public + prive = total |
| 3 | `diagnostic_provincial.py <panel> <sortie> [public\|prive]` | un panel | diagnostic 2024-2025, ratios, profils, 3 graphiques ; sans 3e argument : total |
| 4 | `graphiques_public_prive.py <ratios_public> <ratios_prive> <sortie>` | deux tables de ratios | comparaison public / prive |
| 5 | `projection_et_allocation.py <panel_public> <population> <sortie> public <panel_total> [part_constante\|prive_constant]` | panel public, panel total, population 6-11 ans | projection 2030 et allocation des maitres et des salles (public seul) |

## Regles et hypotheses
- Calculs sur 45 anciennes provinces, restitues pour 47 nouvelles provinces (Soum et Tapoa : meme valeur, colonne `chiffres_non_divisibles` ou `statut_valeur`). Valeurs absentes laissees vides.
- L'Etat ne construit et n'affecte des enseignants que dans le public : le modele d'allocation porte sur le public. Le prive n'intervient que dans l'hypothese sur sa part (`hypothese_prive`).
- Normes (parametres en tete de scripts) : 50 eleves par maitre et par salle = reference, sans source officielle trouvee ; 45 et 40 = normes secondaires.
- Hypotheses non sourcees : taux de departs (0 % et 2 %), 3 887 recrutements par an (PSEF action 8.1.2, a reverifier), couts de deplacement (0,5 / 1 / 3), capacites de construction de salles (25, 50, 75, 100 % du besoin), scenarios S1 et S2.
- Le mode total de `projection_et_allocation.py` (sans l'argument `public`) redonne les premiers resultats sur toutes les ecoles.

## Emplacement
Depuis le 17/11/2026, ces scripts sont dans `04_CODE/DASHBOARD/modele/` (ils étaient dans `04_CODE/02_modele/`). Aucun script n'a été modifié. Les deux anciens scripts `modele_besoins_2030.py` et `allocation_enseignants.py` (ancien modèle, anciennes tables) sont dans `04_CODE/_ARCHIVE/`.
