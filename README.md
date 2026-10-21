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

Le modèle choisit les gisements pour une quantité annuelle de biomasse fixée et un budget maximal. Il effectue deux calculs : il détermine d’abord la capture stable maximale réalisable sous budget, puis minimise le coût tout en conservant la part de cette capture choisie par l’utilisateur (curseur de 50 à 100 %). La quantité de biomasse est fixée exactement afin que le modèle ne sélectionne pas tout le volume mobilisable par défaut.

### Choix du site

Le modèle linéaire en nombres entiers mixtes choisit un seul site candidat et les flux de biomasse. Il respecte la disponibilité des gisements, la capacité de traitement, une cible minimale de production de biochar et un budget annuel maximal comprenant le coût fixe du site, l’approvisionnement et le transport estimé. Il calcule d’abord le carbone stable maximal réalisable, puis minimise le coût en maintenant la part de capture choisie par l’utilisateur (50 à 100 %).

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

## Collecter des données agricoles ouvertes

Un premier collecteur récupère le jeu **Production végétale 2010-2022** du portail officiel [data.gov.ma](https://data.gov.ma/data/dataset/api_dataset/production-vegetale-2010-2022). Il passe par l’API du catalogue pour retrouver la ressource Excel, télécharge le fichier original dans `data/raw/`, produit un CSV nettoyé avec une ligne par campagne et produit, et enregistre un fichier `.metadata.json` avec la source, la licence et la date de collecte.

Depuis un terminal ouvert à la racine du projet :

```bash
python scripts/collecte_open_data_maroc.py
```

Le jeu couvre la production et les superficies agricoles par produit pour 2010-2022. Il ne contient pas directement les tonnages de palmes, noyaux, coques ou autres résidus. Le CSV nettoyé sert de base de calcul; il n’est pas directement importable comme gisement dans l’application, car la conversion en résidus doit encore être faite. Pour cela, il faut relier chaque culture à un coefficient de résidus documenté, puis appliquer des hypothèses de collecte et de disponibilité. Les résultats calculés doivent être signalés comme estimations et garder la référence de leurs coefficients. La licence publiée pour le jeu est ODbL : vérifier ses conditions avant de redistribuer une base dérivée.

## Coefficients de gisement : sources et limites

Le fichier [`data/references_coefficients_gisements.csv`](data/references_coefficients_gisements.csv) recense les coefficients trouvés, leur unité, leur source et leurs limites. Les coefficients sont des références de recherche, pas des mesures de l’entreprise. Certains ne s’appliquent pas directement aux champs du fichier Open Data : par exemple, les coques d’amande dépendent de la forme sous laquelle la production est comptabilisée; les balles de riz sont un coproduit d’une rizerie; la pulpe de betterave dépend du tonnage traité en sucrerie; et l’arganier n’apparaît pas dans le jeu agricole téléchargé.

Le jeu officiel est national : il ne donne pas de région ou de province pour chaque production. Il permet donc de commencer une estimation nationale par campagne, mais pas de localiser les gisements pour calculer les distances ou attribuer les quantités aux régions. Les coefficients qui proviennent d’études méditerranéennes ou de variétés hors Maroc sont signalés comme des références à valider.

Les résidus de palmier dattier disposent d’une mesure marocaine par arbre et par an, mais le jeu agricole ne donne pas le nombre de palmiers. Il faut récupérer l’effectif régional/national des pieds avant d’en tirer un tonnage. De même, la pulpe de betterave doit être estimée à partir des données des sucreries, pas seulement de la production agricole.

## Générer un premier CSV de gisements estimés

Après avoir collecté et normalisé le fichier agricole, lancer :

```bash
python scripts/estimer_gisements.py
```

Le script applique les coefficients de `data/coefficients_estimations.csv` aux surfaces ou aux productions agricoles par campagne et crée `data/gisements_estimes_web.csv`. Ce fichier respecte les colonnes d’import des gisements de l’application et garde, en colonnes supplémentaires, la campagne, le coefficient, la source et les limites. Il couvre pour l’instant les résidus de tomate, l’élagage des agrumes, les sarments de vigne et les balles de riz.

Les volumes calculés sont des estimations bibliographiques nationales. Le volume dit mobilisable est un proxy qui ne déduit pas encore les usages concurrents, la matière à laisser au sol ni les contraintes logistiques. Les cinq coûts sont vides : l’application pourra afficher les gisements, mais l’optimisation économique ne pourra pas utiliser ces lignes avant que les coûts soient renseignés. Les estimations ne sont pas ventilées par région et ne permettent pas encore une optimisation géographique fiable.

## Principes

- Les valeurs manquantes restent manquantes ; elles ne sont pas remplacées par zéro.
- Toute donnée fictive ou hypothèse de démonstration doit être remplacée par une donnée vérifiée avant une étude réelle.
- Les résultats dépendent des sources, des unités et des hypothèses saisies.
