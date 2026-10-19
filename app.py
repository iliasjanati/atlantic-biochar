import math

import pandas as pd
import pulp
import streamlit as st

st.set_page_config(page_title="Atlantic Biochar", page_icon="🌱", layout="wide")
COSTS = ["cout_achat_dh_t", "cout_collecte_dh_t", "cout_preparation_dh_t", "cout_stockage_dh_t", "cout_transport_dh_t"]
QUANTITIES = ["quantite_theorique_t_an", "quantite_recuperable_t_an", "quantite_mobilisable_t_an"]
REQUIRED = ["id_gisement", "biomasse", "region", "annee", *QUANTITIES, *COSTS, "statut_donnee"]
COORDINATES = ["latitude", "longitude"]

st.title("🌱 Atlantic Biochar")
st.caption("Système d’aide à la décision pour l’approvisionnement en biomasse")
with st.sidebar:
    st.header("Données")
    upload = st.file_uploader("Importer les données (CSV ou Excel)", type=["csv", "xlsx"])
    st.caption("Les CSV à séparateur virgule ou point-virgule et les classeurs Excel sont acceptés.")
    st.caption("Sans import, le prototype utilise son jeu fictif de démonstration.")
    st.divider()
    st.header("Hypothèses de scénario")
    availability = st.slider("Part mobilisable conservée (%)", 0, 100, 100, 5) / 100
    transport_change = st.slider("Variation du coût de transport (%)", -50, 200, 0, 10)
    other_change = st.slider("Variation des autres coûts (%)", -50, 200, 0, 10)


def load_frame(file):
    if file is None:
        return pd.read_csv("data/demo_gisements.csv"), True

    if file.name.lower().endswith(".xlsx"):
        return pd.read_excel(file, sheet_name=0), False

    sample = file.getvalue()[:8192].decode("utf-8-sig", errors="replace")
    separator = ";" if sample.count(";") > sample.count(",") else ","
    file.seek(0)
    decimal = "," if separator == ";" else "."
    return pd.read_csv(file, sep=separator, decimal=decimal, encoding="utf-8-sig"), False


def validate(frame):
    missing = [name for name in REQUIRED if name not in frame.columns]
    if missing:
        return ["Colonnes obligatoires absentes : " + ", ".join(missing)]
    errors = []
    for name in ["annee", *QUANTITIES, *COSTS]:
        original = frame[name].copy()
        frame[name] = pd.to_numeric(frame[name], errors="coerce")
        if (original.notna() & frame[name].isna()).any():
            errors.append(f"{name} contient une valeur non numérique.")
    for name in COORDINATES:
        if name in frame.columns:
            original = frame[name].copy()
            frame[name] = pd.to_numeric(frame[name], errors="coerce")
            if (original.notna() & frame[name].isna()).any():
                errors.append(f"{name} contient une coordonnée non numérique.")
    for name in [*QUANTITIES, *COSTS]:
        if (frame[name].dropna() < 0).any():
            errors.append(f"{name} contient une valeur négative.")
    complete = frame[QUANTITIES].notna().all(axis=1)
    invalid = complete & ((frame[QUANTITIES[1]] > frame[QUANTITIES[0]]) | (frame[QUANTITIES[2]] > frame[QUANTITIES[1]]))
    if invalid.any():
        errors.append(f"{int(invalid.sum())} ligne(s) incohérentes : mobilisable ≤ récupérable ≤ théorique attendu.")
    for name in ["id_gisement", "biomasse", "region"]:
        missing_text = frame[name].isna() | frame[name].astype(str).str.strip().eq("")
        if missing_text.any():
            errors.append(f"{name} doit être renseigné pour chaque gisement.")
    if frame["id_gisement"].duplicated().any():
        errors.append("Les identifiants de gisement doivent être uniques.")
    if "latitude" in frame.columns and ((frame["latitude"].dropna().abs() > 90).any()):
        errors.append("Les latitudes doivent être comprises entre -90 et 90.")
    if "longitude" in frame.columns and ((frame["longitude"].dropna().abs() > 180).any()):
        errors.append("Les longitudes doivent être comprises entre -180 et 180.")
    return errors


def add_scenario(frame):
    frame = frame.copy()
    frame["cout_complet"] = frame[COSTS].notna().all(axis=1)
    frame["cout_base_dh_t"] = frame[COSTS].sum(axis=1, min_count=len(COSTS))
    non_transport = (
        frame["cout_achat_dh_t"] + frame["cout_collecte_dh_t"]
        + frame["cout_preparation_dh_t"] + frame["cout_stockage_dh_t"]
    )
    frame["cout_scenario_dh_t"] = (
        non_transport * (1 + other_change / 100)
        + frame["cout_transport_dh_t"] * (1 + transport_change / 100)
    )
    frame["volume_scenario_t_an"] = frame["quantite_mobilisable_t_an"] * availability
    return frame


def solve_supply(frame, demand):
    eligible = frame[frame["cout_complet"] & frame["volume_scenario_t_an"].notna() & (frame["volume_scenario_t_an"] > 0)].copy()
    available = eligible["volume_scenario_t_an"].sum()
    if available + 1e-8 < demand:
        return None, available
    model = pulp.LpProblem("plan_approvisionnement", pulp.LpMinimize)
    x = {i: pulp.LpVariable(f"q_{i}", lowBound=0, upBound=row["volume_scenario_t_an"]) for i, row in eligible.iterrows()}
    model += pulp.lpSum(x[i] * row["cout_scenario_dh_t"] for i, row in eligible.iterrows())
    model += pulp.lpSum(x.values()) >= demand
    status = model.solve(pulp.PULP_CBC_CMD(msg=False))
    if pulp.LpStatus[status] != "Optimal":
        return None, available
    eligible["quantite_a_approvisionner_t_an"] = [x[i].value() or 0 for i in eligible.index]
    plan = eligible[eligible["quantite_a_approvisionner_t_an"] > 1e-6].copy()
    plan["cout_annuel_dh"] = plan["quantite_a_approvisionner_t_an"] * plan["cout_scenario_dh_t"]
    return plan, available


def distance_km(lat1, lon1, lat2, lon2):
    """Distance geodesique a vol d'oiseau entre deux coordonnees."""
    earth_radius_km = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    haversine = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    )
    return 2 * earth_radius_km * math.asin(math.sqrt(haversine))


try:
    data, demo = load_frame(upload)
except Exception as exc:
    st.error(f"Lecture du fichier impossible : {exc}")
    st.stop()
errors = validate(data)
if errors:
    st.error("Corrige les erreurs suivantes dans le fichier :")
    for error in errors:
        st.write(f"• {error}")
    st.stop()
data = add_scenario(data)
if demo:
    st.warning("Démonstration : toutes les valeurs sont fictives et ne décrivent pas les ressources réelles du Maroc.")
else:
    st.success("Fichier importé. Les résultats dépendent de l’exactitude des données fournies.")

home, map_tab, site_tab, compare, optimize, quality_tab = st.tabs(["Tableau de bord", "Carte", "Proximité d’un site", "Comparer les régions", "Plan d’approvisionnement", "Qualité des données"])
with home:
    st.subheader("Vue d’ensemble")
    a, b, c, d = st.columns(4)
    a.metric("Gisements", f"{len(data):,}")
    b.metric("Biomasses", f"{data['biomasse'].nunique():,}")
    c.metric("Régions", f"{data['region'].nunique():,}")
    d.metric("Coûts complets", f"{int(data['cout_complet'].sum())} / {len(data)}")
    biomass_summary = data.groupby("biomasse", as_index=False).agg(volume_t_an=("volume_scenario_t_an", "sum"), gisements=("id_gisement", "count")).sort_values("volume_t_an", ascending=False)
    st.bar_chart(biomass_summary.set_index("biomasse")["volume_t_an"])
    st.dataframe(biomass_summary, use_container_width=True, hide_index=True)
    st.caption("Les volumes agrégés ne garantissent pas une disponibilité contractuelle pour une usine.")

with map_tab:
    st.subheader("Carte des gisements")
    st.caption("Les points de démonstration sont fictifs et indicatifs ; ils ne montrent pas l’emplacement réel de gisements.")
    if not all(name in data.columns for name in COORDINATES):
        st.info("Ce fichier ne contient pas encore les colonnes latitude et longitude. Télécharge le modèle CSV dans l’onglet Qualité des données.")
    else:
        map_biomasses = sorted(data["biomasse"].dropna().unique())
        map_regions = sorted(data["region"].dropna().unique())
        selected_map_biomasses = st.multiselect("Biomasses sur la carte", map_biomasses, default=map_biomasses, key="map_biomasses")
        selected_map_regions = st.multiselect("Régions sur la carte", map_regions, default=map_regions, key="map_regions")
        mapped = data[
            data["biomasse"].isin(selected_map_biomasses)
            & data["region"].isin(selected_map_regions)
            & data["latitude"].notna()
            & data["longitude"].notna()
        ].copy()
        if mapped.empty:
            st.info("Aucun gisement sélectionné n’a de coordonnées complètes.")
        else:
            volume = mapped["volume_scenario_t_an"].fillna(0)
            spread = volume.max() - volume.min()
            mapped["taille_point"] = 12 if spread == 0 else 12 + 36 * (volume - volume.min()) / spread
            st.map(mapped, latitude="latitude", longitude="longitude", size="taille_point")
            st.caption("La taille des points représente le volume mobilisable simulé. Le niveau de précision dépend des coordonnées fournies.")
            map_columns = ["id_gisement", "biomasse", "region", "latitude", "longitude", "volume_scenario_t_an", "statut_donnee"]
            st.dataframe(mapped[map_columns], use_container_width=True, hide_index=True)

with site_tab:
    st.subheader("Proximité d’un site candidat")
    st.write("Saisis les coordonnées d’un site d’usine candidat pour examiner sa proximité avec les gisements localisés.")
    st.warning("Les distances calculées sont à vol d’oiseau. Elles ne représentent ni les trajets routiers ni un coût de transport.")
    site_name = st.text_input("Nom du site candidat", placeholder="Ex. Site A")
    site_col1, site_col2 = st.columns(2)
    with site_col1:
        site_lat_text = st.text_input("Latitude du site", placeholder="Ex. 31.93")
    with site_col2:
        site_lon_text = st.text_input("Longitude du site", placeholder="Ex. -4.42")
    if not all(name in data.columns for name in COORDINATES):
        st.info("Le fichier chargé ne contient pas de coordonnées de gisements.")
    elif not site_lat_text.strip() or not site_lon_text.strip():
        st.info("Entre la latitude et la longitude du site pour afficher les distances.")
    else:
        try:
            site_lat, site_lon = float(site_lat_text), float(site_lon_text)
            if not (-90 <= site_lat <= 90 and -180 <= site_lon <= 180):
                raise ValueError("Coordonnées hors limites.")
        except ValueError:
            st.error("Entre des coordonnées numériques valides : latitude de -90 à 90 et longitude de -180 à 180.")
        else:
            located = data[data["latitude"].notna() & data["longitude"].notna()].copy()
            if located.empty:
                st.info("Aucun gisement n’a de coordonnées complètes.")
            else:
                located["distance_a_vol_doiseau_km"] = located.apply(
                    lambda row: distance_km(site_lat, site_lon, row["latitude"], row["longitude"]),
                    axis=1,
                )
                located = located.sort_values("distance_a_vol_doiseau_km")
                if site_name.strip():
                    st.caption(f"Distances depuis : {site_name.strip()}")
                nearest = located.iloc[0]
                k1, k2 = st.columns(2)
                k1.metric("Gisement le plus proche", str(nearest["id_gisement"]))
                k2.metric("Distance à vol d’oiseau", f"{nearest['distance_a_vol_doiseau_km']:.1f} km")
                radius_text = st.text_input("Rayon de comparaison facultatif (km)", placeholder="Laisse vide pour ne pas filtrer")
                if radius_text.strip():
                    try:
                        radius = float(radius_text)
                        if radius <= 0:
                            raise ValueError("Le rayon doit être positif.")
                        in_radius = located[located["distance_a_vol_doiseau_km"] <= radius]
                        st.metric(f"Volume mobilisable dans {radius:g} km à vol d’oiseau", f"{in_radius['volume_scenario_t_an'].sum():,.0f} t/an")
                    except ValueError:
                        st.error("Saisis un rayon positif en kilomètres.")
                distance_columns = ["id_gisement", "biomasse", "region", "distance_a_vol_doiseau_km", "volume_scenario_t_an", "cout_scenario_dh_t"]
                st.dataframe(located[distance_columns], use_container_width=True, hide_index=True)

with compare:
    st.subheader("Comparer les régions")
    biomasses = sorted(data["biomasse"].dropna().unique())
    regions = sorted(data["region"].dropna().unique())
    bs = st.multiselect("Biomasses", biomasses, default=biomasses, key="compare_b")
    rs = st.multiselect("Régions", regions, default=regions, key="compare_r")
    subset = data[data["biomasse"].isin(bs) & data["region"].isin(rs)].copy()
    if subset.empty:
        st.info("Sélectionne au moins une biomasse et une région.")
    else:
        summary = subset.groupby("region", as_index=False).agg(gisements=("id_gisement", "count"), volume_scenario_t_an=("volume_scenario_t_an", "sum"))
        cost = subset[subset["cout_complet"]].copy()
        cost["cout_volume"] = cost["cout_scenario_dh_t"] * cost["volume_scenario_t_an"]
        weighted = cost.groupby("region").agg(total=("cout_volume", "sum"), volume=("volume_scenario_t_an", "sum"))
        weighted["cout_moyen_pondere_dh_t"] = weighted["total"] / weighted["volume"].where(weighted["volume"] > 0)
        summary = summary.merge(weighted[["cout_moyen_pondere_dh_t"]], left_on="region", right_index=True, how="left")
        st.dataframe(summary, use_container_width=True, hide_index=True)
        st.markdown("#### Compromis entre volume et coût")
        plot = summary.dropna(subset=["cout_moyen_pondere_dh_t"])
        if not plot.empty:
            st.scatter_chart(plot, x="cout_moyen_pondere_dh_t", y="volume_scenario_t_an", color="region")
        st.caption("Le coût moyen couvre seulement les gisements aux coûts complets. Ce n’est pas un classement absolu de sites.")

        st.markdown("#### Coût minimal pour un même besoin annuel")
        common_demand = st.number_input("Besoin à comparer (t/an)", min_value=1, value=100, step=10)
        if st.button("Comparer la faisabilité et le coût par région"):
            comparisons = []
            for candidate in rs:
                candidate_pool = subset[subset["region"] == candidate]
                plan, available = solve_supply(candidate_pool, float(common_demand))
                comparisons.append({
                    "region": candidate,
                    "besoin_t_an": common_demand,
                    "volume_eligible_t_an": available,
                    "faisable": plan is not None,
                    "cout_annuel_minimal_dh": plan["cout_annuel_dh"].sum() if plan is not None else None,
                    "cout_moyen_dh_t": (
                        plan["cout_annuel_dh"].sum() / plan["quantite_a_approvisionner_t_an"].sum()
                        if plan is not None else None
                    ),
                })
            comparison = pd.DataFrame(comparisons).sort_values(
                ["faisable", "cout_annuel_minimal_dh"], ascending=[False, True], na_position="last"
            )
            st.dataframe(comparison, use_container_width=True, hide_index=True)
            st.caption("Une région est faisable si ses gisements aux coûts complets peuvent couvrir le besoin. Le coût minimal est calculé séparément pour chaque région.")

with optimize:
    st.subheader("Plan d’approvisionnement au coût minimal")
    st.write("Le modèle répartit le besoin entre les gisements d’une région, sans dépasser les volumes simulés disponibles. Les coûts incomplets sont exclus.")
    regions = sorted(data["region"].dropna().unique())
    region = st.selectbox("Région candidate", regions)
    biomasses = sorted(data["biomasse"].dropna().unique())
    allowed = st.multiselect("Biomasses autorisées", biomasses, default=biomasses, key="opt_b")
    pool = data[(data["region"] == region) & data["biomasse"].isin(allowed)]
    max_supply = pool.loc[pool["cout_complet"], "volume_scenario_t_an"].sum()
    maximum = max(1, int(max_supply) if pd.notna(max_supply) else 1)
    demand = st.number_input("Besoin annuel de l’usine (t/an)", min_value=1, max_value=maximum, value=min(100, maximum), step=10)
    if st.button("Calculer le plan", type="primary"):
        plan, supply = solve_supply(pool, float(demand))
        if plan is None:
            st.error(f"Approvisionnement impossible avec les données complètes. Volume disponible : {supply:,.0f} t/an ; besoin : {demand:,.0f} t/an.")
        else:
            qty = plan["quantite_a_approvisionner_t_an"].sum()
            total_cost = plan["cout_annuel_dh"].sum()
            m1, m2, m3 = st.columns(3)
            m1.metric("Besoin couvert", f"{qty:,.0f} t/an")
            m2.metric("Coût annuel estimé", f"{total_cost:,.0f} DH/an")
            m3.metric("Coût moyen", f"{total_cost / qty:,.0f} DH/t")
            cols = ["id_gisement", "biomasse", "quantite_a_approvisionner_t_an", "cout_scenario_dh_t", "cout_annuel_dh"]
            st.dataframe(plan[cols], use_container_width=True, hide_index=True)
            st.download_button("Télécharger le plan CSV", plan[cols].to_csv(index=False).encode("utf-8-sig"), "plan_approvisionnement.csv", "text/csv")
            st.caption("Optimisation linéaire du coût avec les données et hypothèses saisies. Distances routières, stocks et saisons ne sont pas encore modélisés.")

with quality_tab:
    st.subheader("Qualité et traçabilité")
    def missing_column(name):
        if name not in data.columns:
            return pd.Series(True, index=data.index)
        values = data[name]
        return values.isna() | values.astype(str).str.strip().eq("")

    check_fields = {
        "Année de référence": missing_column("annee"),
        "Source documentaire": missing_column("source"),
        "Niveau de fiabilité": missing_column("niveau_fiabilite"),
        "Statut de la donnée": missing_column("statut_donnee"),
        "Quantité mobilisable": missing_column("quantite_mobilisable_t_an"),
        "Coordonnées (facultatives)": (
            missing_column("latitude") | missing_column("longitude")
        ),
    }
    issues = pd.DataFrame({"id_gisement": data["id_gisement"]})
    issues["informations_a_completer"] = ""
    quality_rows = []
    for label, mask in check_fields.items():
        count = int(mask.sum())
        quality_rows.append({"Contrôle": label, "Lignes à compléter": count})
        issues.loc[mask, "informations_a_completer"] += label + "; "

    incomplete_costs = ~data["cout_complet"]
    quality_rows.append({"Contrôle": "Au moins un poste de coût manquant", "Lignes à compléter": int(incomplete_costs.sum())})
    issues.loc[incomplete_costs, "informations_a_completer"] += "Coûts incomplets; "
    quality = pd.DataFrame(quality_rows)
    st.dataframe(quality, use_container_width=True, hide_index=True)
    st.caption("Les cellules inconnues restent manquantes ; elles ne sont pas remplacées par zéro.")
    report = issues[issues["informations_a_completer"] != ""].copy()
    if report.empty:
        st.success("Aucune information manquante parmi les contrôles affichés.")
    else:
        st.markdown("#### Lignes à vérifier")
        st.dataframe(report, use_container_width=True, hide_index=True)
        st.download_button(
            "Télécharger le rapport des lignes à compléter",
            report.to_csv(index=False).encode("utf-8-sig"),
            "rapport_qualite_donnees.csv",
            "text/csv",
        )
    st.dataframe(data, use_container_width=True, hide_index=True)
    template = pd.DataFrame(columns=REQUIRED + ["province", "latitude", "longitude", "source", "niveau_fiabilite"])
    st.download_button("Télécharger un modèle CSV vide", template.to_csv(index=False).encode("utf-8-sig"), "modele_gisements.csv", "text/csv")
