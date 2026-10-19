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

Le modèle linéaire minimise les coûts d’approvisionnement pour couvrir une demande de biomasse dans une région donnée. Il respecte les quantités mobilisables et exclut les gisements dont un des cinq postes de coût est manquant.

### Choix du site

Le modèle linéaire en nombres entiers mixtes choisit un site candidat au Maroc et les flux de biomasse à mobiliser. Il respecte les disponibilités, la capacité de traitement et une cible de production de biochar définie par l’utilisateur. Son objectif additionne le coût fixe annuel du site et les coûts variables d’approvisionnement et de transport estimé.

Les rendements préremplis depuis `data/demo_rendements.csv` et les sites de `data/demo_sites.csv` sont fictifs et modifiables. Le transport est estimé à partir de la distance à vol d’oiseau multipliée par un facteur de détour routier et un tarif en DH/t/km. Le coût de transport présent dans le fichier des gisements n’est pas repris dans cette optimisation, car il ne dépend pas du site choisi.

Les rendements de démonstration préremplis proviennent de `data/demo_rendements.csv` et restent modifiables dans l’interface.

Ces résultats sont des estimations de prototype, pas des recommandations d’investissement. Les coûts de transformation, les itinéraires routiers réels, les effets de saisonnalité, la qualité des matières, les émissions et les contraintes réglementaires ne sont pas encore modélisés.

## Données des gisements

Importer un fichier CSV ou Excel (.xlsx). Pour Excel, la première feuille est lue. Le CSV peut utiliser une virgule ou un point-virgule comme séparateur. Les en-têtes obligatoires sont :

- `id_gisement`, `biomasse`, `region`, `annee`, `statut_donnee`
- `quantite_theorique_t_an`, `quantite_recuperable_t_an`, `quantite_mobilisable_t_an`
- `cout_achat_dh_t`, `cout_collecte_dh_t`, `cout_preparation_dh_t`, `cout_stockage_dh_t`, `cout_transport_dh_t`

Les colonnes `latitude` et `longitude` sont facultatives pour l’exploration, mais nécessaires à l’optimisation du site. Le modèle CSV complet est téléchargeable dans **Données**. Les postes de coût peuvent être vides dans le fichier, mais les gisements incomplets ne sont pas admissibles aux calculs qui en ont besoin.

## Données des sites candidats

Dans **Optimiser → Choix du site d’implantation**, importer un CSV avec les colonnes :

`id_site`, `nom_site`, `latitude`, `longitude`, `cout_fixe_dh_an`, `capacite_traitement_t_an`

Le logiciel permet de télécharger un modèle CSV vide.

## Principes

- Les valeurs manquantes restent manquantes ; elles ne sont pas remplacées par zéro.
- Toute donnée fictive ou hypothèse de démonstration doit être remplacée par une donnée vérifiée avant une étude réelle.
- Les résultats dépendent des sources, des unités et des hypothèses saisies.
