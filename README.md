# Atlantic Biochar

Prototype Streamlit d’aide à la décision pour étudier l’approvisionnement en biomasse et le choix d’un site de production de biochar au Maroc.

## Utilisation

Dans un terminal ouvert à la racine du projet :

```bash
pip install -r requirements.txt
streamlit run app.py
```

Sans import, l’application charge des données de démonstration fictives. Les fichiers de démonstration ne décrivent pas les ressources réelles du Maroc.

Le jeu par défaut contient 42 lignes de gisements dans plusieurs régions et filières. Il comprend volontairement quelques valeurs manquantes pour essayer les contrôles qualité et comparer la faisabilité selon les coûts disponibles. Les sites candidats et rendements ont également des valeurs fictives pour tester l’optimisation.

## Parcours dans l’application

- **Accueil** : quelques indicateurs nationaux et le volume mobilisable par type de biomasse.
- **Explorer** : filtres par région et biomasse, comparaison des volumes, carte, comparaison indicative des coûts et distances à vol d’oiseau.
- **Optimiser** : choix entre un plan d’approvisionnement régional et l’optimisation nationale du site.
- **Données** : contrôles de complétude, téléchargement du rapport qualité et modèles CSV.

Les hypothèses de scénario sont regroupées dans la barre latérale. Elles règlent la disponibilité et les variations de coûts pour les analyses concernées.

## Optimisations

### Approvisionnement régional

Le modèle choisit les gisements pour une quantité annuelle de biomasse fixée. Par défaut, il **maximise le carbone stable estimé dans le biochar** sous un budget annuel. Le mode « minimiser le coût » reste disponible pour comparer. La demande est fixée exactement afin que le modèle ne sélectionne pas tout le volume mobilisable par défaut.

### Choix du site

Le modèle linéaire en nombres entiers mixtes choisit un seul site candidat et les flux de biomasse. Il respecte la disponibilité des gisements, la capacité de traitement et une cible minimale de production de biochar. L’objectif par défaut maximise le carbone stable estimé sous un budget qui comprend le coût fixe annualisé du site, les coûts variables d’approvisionnement et le transport estimé. Le mode « minimiser le coût » permet une comparaison.

Pour un gisement `g`, avec `x_g` tonnes de biomasse entrante/an, humidité `H_g`, rendement de biochar sur matière sèche `Y_g`, carbone du biochar `C_g` et fraction stable `P_g`, le stockage brut estimé est :

`Carbone stable (tC/an) = Σ_g x_g × (1 − H_g/100) × Y_g × (C_g/100) × (P_g/100)`

`Stockage brut (tCO₂e/an) = Carbone stable (tC/an) × 44/12`

Le modèle traite le rendement comme un pourcentage de la matière sèche. La fraction stable représente la part supposée du carbone du biochar qui reste stockée sur l’horizon considéré. Ces trois paramètres sont modifiables dans l’interface.

Ce résultat est un **stockage brut potentiel dans le biochar**, pas un retrait net de CO₂. Le logiciel ne soustrait pas encore les émissions de séchage, pyrolyse, transport ou les émissions de référence et ne modélise pas les usages concurrents. Tous les paramètres des fichiers de démonstration sont fictifs et illustratifs, à remplacer par des mesures ou références validées avant toute conclusion réelle.

Le transport du modèle de localisation est estimé depuis la distance à vol d’oiseau, multipliée par un facteur de détour routier et un tarif en DH/t/km. Le coût de transport fourni au niveau du gisement n’est pas repris dans cette optimisation, car le transport est recalculé selon le site choisi.

## Données des gisements

Importer un fichier CSV ou Excel (.xlsx). Pour Excel, la première feuille est lue. Le CSV peut utiliser une virgule ou un point-virgule comme séparateur. Les en-têtes obligatoires sont :

- `id_gisement`, `biomasse`, `region`, `annee`, `statut_donnee`
- `quantite_theorique_t_an`, `quantite_recuperable_t_an`, `quantite_mobilisable_t_an`
- `cout_achat_dh_t`, `cout_collecte_dh_t`, `cout_preparation_dh_t`, `cout_stockage_dh_t`, `cout_transport_dh_t`

Les colonnes `latitude` et `longitude` sont facultatives pour l’exploration, mais nécessaires à l’optimisation du site. Le modèle CSV complet est téléchargeable dans **Données**. Les postes de coût peuvent être vides dans le fichier, mais les gisements incomplets ne sont pas admissibles aux calculs qui en ont besoin.

Pour optimiser le carbone stocké dans le biochar, renseigner `humidite_pct` pour chaque gisement. Le carbone brut de la biomasse (`carbone_biomasse_pct_ms`) peut rester comme donnée descriptive, mais il ne détermine pas directement le carbone capturé par le biochar. Les paramètres de rendement, carbone du biochar et fraction stable sont modifiables dans **Optimiser → Paramètres du biochar**. Les valeurs par défaut sont fictives.

Les résultats affichent le carbone stable estimé en tC/an et sa conversion en stockage brut tCO₂e/an. Ce n’est pas un bilan net du cycle de vie.

## Données des sites candidats

Dans **Optimiser → Choix du site d’implantation**, importer un CSV avec les colonnes :

`id_site`, `nom_site`, `latitude`, `longitude`, `cout_fixe_dh_an`, `capacite_traitement_t_an`

Le logiciel permet de télécharger un modèle CSV vide.

## Principes

- Les valeurs manquantes restent manquantes ; elles ne sont pas remplacées par zéro.
- Toute donnée fictive ou hypothèse de démonstration doit être remplacée par une donnée vérifiée avant une étude réelle.
- Les résultats dépendent des sources, des unités et des hypothèses saisies.
