# Système d’aide à la décision pour Atlantic Biochar

Prototype étudiant visant à comparer, à l’échelle nationale du Maroc, les ressources en résidus agricoles pouvant alimenter de futures unités de production de biochar.

## Objectif

Le logiciel aidera à examiner, par biomasse et par zone géographique, les quantités de résidus mobilisables et leurs coûts d’approvisionnement. Il devra rendre visibles les sources, les hypothèses et les données manquantes afin de soutenir la décision sans présenter une estimation comme une certitude.

Les données réelles seront fournies ultérieurement par l’entreprise. Pendant le développement, le prototype pourra utiliser des jeux de données fictifs clairement identifiés, uniquement pour tester son fonctionnement.

## Périmètre initial

Le prototype prévoit de prendre en charge les filières suivantes :

- Résidus du palmier dattier : palmes, rachis, régimes et noyaux.
- Coques d’amande.
- Résidus de la filière argan.
- Tiges de tomate.
- Sarments de vigne.
- Balles de riz.
- Pulpes de betterave.
- Résidus d’agrumes.
- Autres biomasses pertinentes, ajoutées lorsqu’elles sont documentées.

La précision géographique dépendra des données disponibles. Le logiciel ne devra pas afficher une précision communale ou cartographique si les données ne la justifient pas.

## Fonctions prévues pour le MVP

- Importer et consulter des données de gisements depuis un fichier tabulaire.
- Distinguer les quantités théoriques, récupérables et mobilisables.
- Comparer les quantités mobilisables par biomasse et par région ou province.
- Calculer les coûts d’approvisionnement lorsque les postes nécessaires sont renseignés.
- Signaler les champs manquants, les incohérences et les unités utilisées.
- Indiquer la provenance et le statut de chaque donnée : entreprise, fictive ou hypothèse à confirmer.
- Présenter des tableaux et graphiques comparatifs, puis exporter une synthèse.

## Principes de données

- Une valeur inconnue reste vide ou signalée comme manquante ; elle n’est pas remplacée par zéro.
- Les données fictives ne sont jamais présentées comme des statistiques réelles du Maroc.
- Chaque donnée importante doit conserver sa source, son année et son unité.
- Les quantités théoriques ne sont pas assimilées automatiquement à une ressource disponible pour l’usine.
- Les résultats dépendent des hypothèses et de la qualité des données fournies.

## Calculs prévus

Lorsque les coûts sont disponibles et exprimés dans des unités compatibles :

```text
Coût d’approvisionnement (DH/t)
  = achat + collecte + préparation + stockage + transport

Coût annuel estimé (DH/an)
  = quantité mobilisable (t/an) × coût d’approvisionnement (DH/t)
```

Si un poste nécessaire manque, le logiciel devra signaler que le coût est partiel ou impossible à calculer.

## Technologies envisagées

Le choix technique initial est volontairement simple : Python pour les calculs, Streamlit pour l’interface, Pandas pour la manipulation des tableaux et des fichiers Excel ou CSV pour l’échange de données. Ces choix pourront évoluer selon les besoins du prototype.

## Limites du prototype

Le MVP ne constitue pas une étude de faisabilité industrielle. Le classement de sites, l’optimisation complète des flux, l’analyse de cycle de vie complète, la validation des performances de pyrolyse et les vérifications foncières ou réglementaires nécessiteront des données et des travaux complémentaires.

## État du projet

Le projet est au stade de cadrage. La prochaine étape de développement consiste à préparer un modèle de données et un jeu fictif explicitement marqué comme données de test, puis à créer l’importation et les contrôles de cohérence.

## Lancer le prototype

1. Ouvre ce dossier dans Visual Studio Code.
2. Dans le terminal intégré, installe les dépendances :

   ```bash
   pip install -r requirements.txt
   ```

3. Lance l’application :

   ```bash
   streamlit run app.py
   ```

L’application s’ouvre dans un navigateur. Sans import de fichier, elle utilise `data/demo_gisements.csv`, un jeu fictif de démonstration.

## Format CSV attendu

Le fichier importé doit contenir les colonnes suivantes. Les cinq colonnes de coût doivent exister, mais leurs cellules peuvent rester vides si l’information n’est pas connue.

- `id_gisement`, `biomasse`, `region`, `annee`
- `quantite_theorique_t_an`, `quantite_recuperable_t_an`, `quantite_mobilisable_t_an`
- `cout_achat_dh_t`, `cout_collecte_dh_t`, `cout_preparation_dh_t`, `cout_stockage_dh_t`, `cout_transport_dh_t`
- `statut_donnee`

Le fichier de démonstration comprend aussi des colonnes complémentaires telles que la province, l’humidité, la saison, la source et la fiabilité. Les coûts sont additionnés uniquement lorsque les cinq postes sont renseignés.

## Fonctions de décision du prototype

L’application comprend quatre vues :

- **Tableau de bord** : volumes simulés, nombre de gisements et graphiques par biomasse.
- **Comparer les régions** : comparaison des volumes et des coûts moyens pondérés, avec un graphique de compromis entre coût et disponibilité.
- **Plan d’approvisionnement** : pour une région candidate et un besoin annuel, un modèle linéaire répartit l’approvisionnement entre les gisements admissibles afin de minimiser le coût total.
- **Qualité des données** : champs manquants, coûts incomplets et téléchargement d’un modèle CSV vide.

Les contrôles de scénario permettent de réduire les volumes mobilisables et de faire varier séparément les coûts de transport et les autres coûts. Les gisements dont un poste de coût manque sont exclus de l’optimisation.

### Limites du calcul d’approvisionnement

Le modèle choisit les quantités par gisement pour couvrir un besoin annuel au coût estimé le plus faible, sous la limite des volumes simulés disponibles. Il suppose que les volumes indiqués sont accessibles. Dans cette version, la région sert à sélectionner les gisements ; les distances routières, la saisonnalité détaillée, le stockage, les contraintes de mélange et l’emplacement précis de l’usine ne sont pas modélisés. Le résultat est une estimation de prototype, pas une recommandation d’investissement.

La comparaison régionale permet également de choisir un besoin annuel commun et de calculer, pour chaque région sélectionnée, si ce besoin est faisable avec les coûts renseignés et quel serait le coût minimal estimé.

## Carte interactive

L’onglet **Carte** affiche les gisements qui possèdent une latitude et une longitude valides. Les points de démonstration portent des coordonnées indicatives fictives et ne représentent pas les emplacements réels des gisements. Pour des données d’entreprise, saisir les coordonnées réellement fournies. Le modèle CSV téléchargeable inclut maintenant les colonnes `latitude` et `longitude`.
