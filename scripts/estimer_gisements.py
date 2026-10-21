"""Estime des gisements à partir de la production agricole et de coefficients publiés.

Les résultats sont des ordres de grandeur provisoires, pas des mesures.
Les postes de coûts restent vides : ils doivent être renseignés par l'entreprise.

Depuis la racine du projet :
    python scripts/estimer_gisements.py
"""

from __future__ import annotations

import csv
import re
import unicodedata
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "data" / "raw" / "production_vegetale_maroc_normalisee.csv"
COEFFICIENTS = ROOT / "data" / "coefficients_estimations.csv"
OUTPUT = ROOT / "data" / "gisements_estimes_web.csv"

OUTPUT_FIELDS = [
    "id_gisement", "biomasse", "region", "annee", "quantite_theorique_t_an",
    "quantite_recuperable_t_an", "quantite_mobilisable_t_an", "cout_achat_dh_t",
    "cout_collecte_dh_t", "cout_preparation_dh_t", "cout_stockage_dh_t",
    "cout_transport_dh_t", "statut_donnee", "source", "niveau_fiabilite",
    "campagne", "coefficient_utilise", "unite_coefficient", "methode", "note_limite",
]


def key(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text or "")
    return "".join(char for char in normalized if not unicodedata.combining(char)).casefold().strip()


def read_semicolon_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as source:
        return list(csv.DictReader(source, delimiter=";"))


def campaign_year(campaign: str) -> int:
    match = re.search(r"\d{4}", campaign)
    if not match:
        raise ValueError(f"Campagne agricole non reconnue : {campaign!r}")
    return int(match.group())


def main() -> None:
    if not INPUT.exists():
        raise SystemExit(f"Données agricoles absentes : {INPUT}. Lancez d'abord scripts/collecte_open_data_maroc.py")
    production_rows = read_semicolon_csv(INPUT)
    coefficient_rows = read_semicolon_csv(COEFFICIENTS)
    output_rows: list[dict[str, str | int | float]] = []

    for coefficient in coefficient_rows:
        selected: dict[str, list[dict[str, str]]] = defaultdict(list)
        for row in production_rows:
            if key(row.get("filiere", "")) != key(coefficient["filiere"]):
                continue
            target_product = coefficient["produit"].strip()
            if target_product != "*" and key(row.get("produit", "")) != key(target_product):
                continue
            selected[row["campagne"]].append(row)

        for campaign, matches in sorted(selected.items()):
            indicator = coefficient["indicateur"]
            base_total = 0.0
            for match in matches:
                raw_value = match.get(indicator, "")
                if raw_value:
                    base_total += float(raw_value)
            if base_total <= 0:
                continue

            theoretical = base_total * float(coefficient["coefficient"])
            recoverable = theoretical * float(coefficient["taux_recuperation"])
            estimate_key = key(coefficient["biomasse"]).replace(" ", "-")
            method_input = "superficie agricole" if indicator == "superficie_ha" else "production agricole"
            note = (
                f"Calcul : {method_input} × coefficient publié. {coefficient['limite']} "
                "Le volume mobilisable est un proxy bibliographique : les usages concurrents, "
                "les contraintes de retour au sol et les coûts réels ne sont pas déduits."
            )
            output_rows.append(
                {
                    "id_gisement": f"WEB-{estimate_key[:24]}-{campaign_year(campaign)}",
                    "biomasse": coefficient["biomasse"],
                    "region": "National",
                    "annee": campaign_year(campaign),
                    "quantite_theorique_t_an": round(theoretical, 3),
                    "quantite_recuperable_t_an": round(recoverable, 3),
                    "quantite_mobilisable_t_an": round(recoverable, 3),
                    "cout_achat_dh_t": "",
                    "cout_collecte_dh_t": "",
                    "cout_preparation_dh_t": "",
                    "cout_stockage_dh_t": "",
                    "cout_transport_dh_t": "",
                    "statut_donnee": "Estimation bibliographique provisoire",
                    "source": coefficient["source"],
                    "niveau_fiabilite": coefficient["fiabilite"],
                    "campagne": campaign,
                    "coefficient_utilise": coefficient["coefficient"],
                    "unite_coefficient": coefficient["unite_coefficient"],
                    "methode": f"{method_input} × coefficient; récupérable = théorique × {coefficient['taux_recuperation']}",
                    "note_limite": note,
                }
            )

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", encoding="utf-8-sig", newline="") as destination:
        writer = csv.DictWriter(destination, fieldnames=OUTPUT_FIELDS, delimiter=";")
        writer.writeheader()
        writer.writerows(output_rows)
    print(f"Estimations créées : {OUTPUT}")
    print(f"Nombre de lignes : {len(output_rows)}")
    print("Les coûts sont volontairement vides et les volumes restent des estimations provisoires.")


if __name__ == "__main__":
    main()
