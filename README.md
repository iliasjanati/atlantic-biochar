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
