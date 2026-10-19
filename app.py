import math

import pandas as pd
import pulp
import streamlit as st

st.set_page_config(page_title="Atlantic Biochar", page_icon="🌱", layout="wide")
COSTS = ["cout_achat_dh_t", "cout_collecte_dh_t", "cout_preparation_dh_t", "cout_stockage_dh_t", "cout_transport_dh_t"]
QUANTITIES = ["quantite_theorique_t_an", "quantite_recuperable_t_an", "quantite_mobilisable_t_an"]
REQUIRED = ["id_gisement", "biomasse", "region", "annee", *QUANTITIES, *COSTS, "statut_donnee"]
COORDINATES = ["latitude", "longitude"]

with st.sidebar:
    st.header("Sources de données")
    upload = st.file_uploader("Importer les données (CSV ou Excel)", type=["csv", "xlsx"])
    st.caption("CSV et Excel acceptés. Sans import, des données de démonstration sont utilisées.")
    with st.expander("Hypothèses de scénario"):
        availability = st.slider("Disponibilité conservée (%)", 0, 100, 100, 5) / 100
        transport_change = st.slider("Variation du transport (%)", -50, 200, 0, 10)
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
    for name in ["humidite_pct", "carbone_biomasse_pct_ms"]:
        if name in frame.columns:
            original = frame[name].copy()
            frame[name] = pd.to_numeric(frame[name], errors="coerce")
            if (original.notna() & frame[name].isna()).any():
                errors.append(f"{name} contient une valeur non numérique.")
            if ((frame[name].dropna() < 0) | (frame[name].dropna() > 100)).any():
                errors.append(f"{name} doit être compris entre 0 et 100 %.")
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
    frame["depense_reference_dh_an"] = (
        frame["cout_base_dh_t"] * frame["quantite_mobilisable_t_an"]
    )
    frame["depense_scenario_dh_an"] = (
        frame["cout_scenario_dh_t"] * frame["volume_scenario_t_an"]
    )
    return frame


def stable_carbon_factor(source, biochar_yield, char_carbon_pct, stable_fraction_pct):
    """tC stable estimate per tonne of as-received biomass."""
    moisture = source.get("humidite_pct")
    if pd.isna(moisture):
        return None
    return (1 - moisture / 100) * biochar_yield * char_carbon_pct / 100 * stable_fraction_pct / 100


def solve_supply(frame, demand, char_params, objective, budget=None):
    eligible = frame[frame["cout_complet"] & frame["volume_scenario_t_an"].notna() & (frame["volume_scenario_t_an"] > 0)].copy()
    eligible = eligible.dropna(subset=["humidite_pct"])
    eligible["carbone_stable_par_t_entree_tC"] = eligible.apply(
        lambda row: stable_carbon_factor(row, *char_params[row["biomasse"]]), axis=1
    )
    eligible = eligible.dropna(subset=["carbone_stable_par_t_entree_tC"])
    available = float(eligible["volume_scenario_t_an"].sum())
    theoretical_max = float((eligible["volume_scenario_t_an"] * eligible["carbone_stable_par_t_entree_tC"]).sum())
    if available + 1e-8 < demand:
        return None, available, theoretical_max
    model = pulp.LpProblem("plan_approvisionnement", pulp.LpMinimize if objective == "Minimiser le coût" else pulp.LpMaximize)
    x = {i: pulp.LpVariable(f"q_{i}", lowBound=0, upBound=row["volume_scenario_t_an"]) for i, row in eligible.iterrows()}
    total_cost = pulp.lpSum(x[i] * row["cout_scenario_dh_t"] for i, row in eligible.iterrows())
    captured = pulp.lpSum(x[i] * eligible.loc[i, "carbone_stable_par_t_entree_tC"] for i in eligible.index)
    model += total_cost if objective == "Minimiser le coût" else captured
    model += pulp.lpSum(x.values()) == demand
    if objective != "Minimiser le coût":
        model += total_cost <= budget
    status = model.solve(pulp.PULP_CBC_CMD(msg=False))
    if pulp.LpStatus[status] != "Optimal":
        return None, available, theoretical_max
    eligible["quantite_a_approvisionner_t_an"] = [x[i].value() or 0 for i in eligible.index]
    plan = eligible[eligible["quantite_a_approvisionner_t_an"] > 1e-6].copy()
    plan["cout_annuel_dh"] = plan["quantite_a_approvisionner_t_an"] * plan["cout_scenario_dh_t"]
    plan["carbone_stable_estime_tC_an"] = plan["quantite_a_approvisionner_t_an"] * plan["carbone_stable_par_t_entree_tC"]
    plan["stockage_brut_estime_tCO2e_an"] = plan["carbone_stable_estime_tC_an"] * 44 / 12
    return plan, available, theoretical_max

def carbon_in_dry_feedstock(as_received_t, source):
    """Tonnes of carbon entering with dry feedstock; not a carbon-removal estimate."""
    carbon_pct = source.get("carbone_biomasse_pct_ms")
    moisture_pct = source.get("humidite_pct")
    if pd.isna(carbon_pct) or pd.isna(moisture_pct):
        return None
    dry_matter_t = as_received_t * (1 - moisture_pct / 100)
    return dry_matter_t * carbon_pct / 100


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


def solve_location(frame, sites, char_params, demand, transport_rate, road_factor, allowed_biomasses,
                   objective, budget=None, other_change=0, transport_change=0):
    """Choose one facility site and feedstock flows for cost or stable-carbon objective."""
    eligible = frame[
        frame["biomasse"].isin(allowed_biomasses)
        & frame[COSTS[:-1]].notna().all(axis=1)
        & frame["volume_scenario_t_an"].notna()
        & (frame["volume_scenario_t_an"] > 0)
        & frame["latitude"].notna()
        & frame["longitude"].notna()
        & frame["humidite_pct"].notna()
    ].copy()
    candidates = sites.dropna(subset=["latitude", "longitude", "cout_fixe_dh_an", "capacite_traitement_t_an"]).copy()
    candidates = candidates[(candidates["capacite_traitement_t_an"] > 0) & (candidates["cout_fixe_dh_an"] >= 0)]
    eligible = eligible[eligible["biomasse"].isin(char_params)].copy()
    if eligible.empty or candidates.empty:
        return None, 0, "Aucun gisement ou site candidat ne possède les données requises."
    eligible["rendement_biochar"] = eligible["biomasse"].map(lambda b: char_params[b][0])
    eligible["carbone_stable_par_t_entree_tC"] = eligible.apply(
        lambda row: stable_carbon_factor(row, *char_params[row["biomasse"]]), axis=1
    )
    theoretical_max = min(
        float(candidates["capacite_traitement_t_an"].max()),
        float((eligible["volume_scenario_t_an"] * eligible["rendement_biochar"] * (1 - eligible["humidite_pct"] / 100)).sum()),
    )
    model = pulp.LpProblem("choix_site_et_approvisionnement", pulp.LpMinimize if objective == "Minimiser le coût" else pulp.LpMaximize)
    choose = {j: pulp.LpVariable(f"site_{j}", cat="Binary") for j in candidates.index}
    flow, unit_cost = {}, {}
    for i, source in eligible.iterrows():
        non_transport = sum(source[name] for name in COSTS[:-1]) * (1 + other_change / 100)
        for j, site in candidates.iterrows():
            key = (i, j)
            flow[key] = pulp.LpVariable(f"flux_{i}_{j}", lowBound=0)
            km = distance_km(source["latitude"], source["longitude"], site["latitude"], site["longitude"])
            unit_cost[key] = non_transport + km * road_factor * transport_rate * (1 + transport_change / 100)
    fixed_cost = pulp.lpSum(candidates.loc[j, "cout_fixe_dh_an"] * choose[j] for j in candidates.index)
    variable_cost = pulp.lpSum(unit_cost[key] * variable for key, variable in flow.items())
    total_cost = fixed_cost + variable_cost
    stable_carbon = pulp.lpSum(
        eligible.loc[i, "carbone_stable_par_t_entree_tC"] * variable for (i, j), variable in flow.items()
    )
    model += total_cost if objective == "Minimiser le coût" else stable_carbon
    model += pulp.lpSum(choose.values()) == 1
    for i, source in eligible.iterrows():
        model += pulp.lpSum(flow[(i, j)] for j in candidates.index) <= source["volume_scenario_t_an"]
    for j, site in candidates.iterrows():
        model += pulp.lpSum(flow[(i, j)] for i in eligible.index) <= site["capacite_traitement_t_an"] * choose[j]
    model += pulp.lpSum(
        (1 - eligible.loc[i, "humidite_pct"] / 100) * eligible.loc[i, "rendement_biochar"] * flow[(i, j)]
        for i in eligible.index for j in candidates.index
    ) >= demand
    if objective != "Minimiser le coût":
        model += total_cost <= budget
    status = model.solve(pulp.PULP_CBC_CMD(msg=False))
    if pulp.LpStatus[status] != "Optimal":
        return None, float(theoretical_max), "Aucune solution faisable. Vérifie le budget, la cible de biochar et les disponibilités."
    selected = next(j for j in candidates.index if (choose[j].value() or 0) > 0.5)
    rows = []
    for i, source in eligible.iterrows():
        amount = flow[(i, selected)].value() or 0
        if amount > 1e-6:
            km = distance_km(source["latitude"], source["longitude"], candidates.loc[selected, "latitude"], candidates.loc[selected, "longitude"])
            char_t = amount * (1 - source["humidite_pct"] / 100) * char_params[source["biomasse"]][0]
            stable_tc = amount * source["carbone_stable_par_t_entree_tC"]
            rows.append({
                "id_gisement": source["id_gisement"], "biomasse": source["biomasse"],
                "quantite_matiere_t_an": amount,
                "biochar_estime_t_an": char_t,
                "carbone_biochar_pct_ms": char_params[source["biomasse"]][1],
                "fraction_carbone_stable_pct": char_params[source["biomasse"]][2],
                "carbone_stable_estime_tC_an": stable_tc,
                "stockage_brut_estime_tCO2e_an": stable_tc * 44 / 12,
                "distance_routiere_estimee_km": km * road_factor,
                "cout_unitaire_estime_dh_t": unit_cost[(i, selected)],
                "cout_annuel_estime_dh": amount * unit_cost[(i, selected)],
            })
    plan = pd.DataFrame(rows)
    return {"site": candidates.loc[selected], "plan": plan,
            "cout_total": float(pulp.value(total_cost)),
            "cout_fixe": float(candidates.loc[selected, "cout_fixe_dh_an"])}, float(plan["biochar_estime_t_an"].sum()), None


try:
    data, demo = load_frame(upload)
except Exception as exc:
    st.error(f"Impossible de lire le fichier : {exc}")
    st.stop()

errors = validate(data)
if errors:
    st.error("Le fichier contient des erreurs à corriger :")
    for error in errors:
        st.write(f"- {error}")
    st.stop()
data = add_scenario(data)

st.title("🌱 Atlantic Biochar")
st.caption("Aide à la décision pour les ressources en biomasse au Maroc")
if demo:
    st.info("Démo : toutes les valeurs sont fictives. Elles servent uniquement à essayer le logiciel.")
else:
    st.caption("Données importées. Vérifie leur source, leur année et leurs unités avant d’interpréter les résultats.")

home_tab, explore_tab, optimize_tab, data_tab = st.tabs(["Accueil", "Explorer", "Optimiser", "Données"])

with home_tab:
    st.subheader("Synthèse nationale")
    col1, col2, col3 = st.columns(3)
    col1.metric("Gisements", f"{len(data):,}")
    col2.metric("Types de biomasse", f"{data['biomasse'].nunique():,}")
    col3.metric("Volume mobilisable", f"{data['volume_scenario_t_an'].sum(min_count=1):,.0f} t/an")
    biomass_summary = data.groupby("biomasse", as_index=False).agg(
        volume_t_an=("volume_scenario_t_an", "sum"),
        gisements=("id_gisement", "count"),
    ).sort_values("volume_t_an", ascending=False)
    st.markdown("#### Ressources par biomasse")
    st.bar_chart(biomass_summary.set_index("biomasse")["volume_t_an"])
    st.caption("Les estimations ne garantissent pas une disponibilité contractuelle pour une usine.")

with explore_tab:
    st.subheader("Explorer les ressources")
    regions = sorted(data["region"].dropna().unique())
    biomasses = sorted(data["biomasse"].dropna().unique())
    col1, col2 = st.columns(2)
    with col1:
        selected_regions = st.multiselect("Régions", regions, default=regions, key="explore_regions")
    with col2:
        selected_biomasses = st.multiselect("Biomasses", biomasses, default=biomasses, key="explore_biomasses")
    subset = data[data["region"].isin(selected_regions) & data["biomasse"].isin(selected_biomasses)].copy()
    if subset.empty:
        st.info("Choisis au moins une région et une biomasse.")
    else:
        group_label = st.radio("Afficher par", ["Région", "Biomasse"], horizontal=True)
        group_key = "region" if group_label == "Région" else "biomasse"
        summary = subset.groupby(group_key, as_index=False).agg(
            volume_mobilisable_t_an=("volume_scenario_t_an", "sum"),
            nombre_gisements=("id_gisement", "count"),
        ).sort_values("volume_mobilisable_t_an", ascending=False)
        st.bar_chart(summary.set_index(group_key)["volume_mobilisable_t_an"])
        st.dataframe(summary, use_container_width=True, hide_index=True)

        with st.expander("Carte des gisements"):
            if not all(name in data.columns for name in COORDINATES):
                st.info("Le fichier n’a pas de colonnes de coordonnées.")
            else:
                mapped = subset.dropna(subset=COORDINATES).copy()
                if mapped.empty:
                    st.info("Aucun gisement sélectionné n’a de coordonnées complètes.")
                else:
                    mapped["taille_point"] = 18
                    st.map(mapped, latitude="latitude", longitude="longitude", size="taille_point")
                    st.caption("Les positions dépendent de la précision des coordonnées saisies. Les points de démo sont fictifs.")

        with st.expander("Comparer les coûts entre régions"):
            cost_rows = subset[subset["cout_complet"] & subset["volume_scenario_t_an"].notna()].copy()
            if cost_rows.empty:
                st.info("Aucun coût complet dans cette sélection.")
            else:
                cost_rows["depense_estimee_dh_an"] = cost_rows["cout_scenario_dh_t"] * cost_rows["volume_scenario_t_an"]
                comparison = cost_rows.groupby("region", as_index=False).agg(
                    volume_t_an=("volume_scenario_t_an", "sum"),
                    depense_dh_an=("depense_estimee_dh_an", "sum"),
                )
                comparison["cout_moyen_dh_t"] = comparison["depense_dh_an"] / comparison["volume_t_an"].where(comparison["volume_t_an"] > 0)
                st.dataframe(comparison, use_container_width=True, hide_index=True)
                st.caption("Estimation sur les volumes complets en coût ; ce n’est pas le coût d’un plan d’usine.")

        with st.expander("Distances indicatives depuis un point"):
            if not all(name in data.columns for name in COORDINATES):
                st.info("Les coordonnées des gisements sont nécessaires.")
            else:
                coord1, coord2 = st.columns(2)
                lat = coord1.number_input("Latitude", min_value=-90.0, max_value=90.0, value=31.63, format="%.4f")
                lon = coord2.number_input("Longitude", min_value=-180.0, max_value=180.0, value=-7.99, format="%.4f")
                located = subset.dropna(subset=COORDINATES).copy()
                if not located.empty:
                    located["distance_directe_km"] = located.apply(
                        lambda row: distance_km(lat, lon, row["latitude"], row["longitude"]), axis=1
                    )
                    located = located.sort_values("distance_directe_km")
                    st.dataframe(
                        located[["id_gisement", "biomasse", "region", "distance_directe_km", "volume_scenario_t_an"]],
                        use_container_width=True,
                        hide_index=True,
                    )
                    st.caption("Distance à vol d’oiseau, sans calcul d’itinéraire ni de coût routier.")

with optimize_tab:
    st.subheader("Optimiser")
    method = st.radio("Choisis le type de calcul", ["Choix du site d’implantation", "Approvisionnement d’une région"], horizontal=True)
    objective_options = ["Maximiser le carbone durable estimé", "Minimiser le coût"]
    if method == "Approvisionnement d’une région":
        st.write("Pour une quantité annuelle donnée, choisir les gisements qui maximisent le carbone stable estimé dans le biochar ou minimisent le coût.")
        region = st.selectbox("Région", regions, key="supply_region")
        allowed = st.multiselect("Biomasses", biomasses, default=biomasses, key="supply_biomasses")
        pool = data[(data["region"] == region) & data["biomasse"].isin(allowed)]
        max_supply = pool.loc[pool["cout_complet"], "volume_scenario_t_an"].sum()
        max_value = max(1, int(max_supply) if pd.notna(max_supply) else 1)
        demand = st.number_input("Quantité de biomasse à approvisionner (t/an)", min_value=1, max_value=max_value, value=min(100, max_value), step=10)
        try:
            yield_data = pd.read_csv("data/demo_rendements.csv").set_index("biomasse")
        except Exception:
            yield_data = pd.DataFrame()
        with st.expander("Paramètres du biochar"):
            defaults = {"rendement_biochar_pct": 30, "carbone_biochar_pct_ms": 65, "fraction_carbone_stable_pct": 80}
            rows = []
            for biomass in biomasses:
                row = yield_data.loc[biomass] if biomass in yield_data.index else pd.Series(dtype=object)
                rows.append({"Biomasse": biomass,
                    "Rendement biochar (%)": float(row.get("rendement_biochar_pct", defaults["rendement_biochar_pct"])),
                    "Carbone du biochar (%)": float(row.get("carbone_biochar_pct_ms", defaults["carbone_biochar_pct_ms"])),
                    "Fraction stable (%)": float(row.get("fraction_carbone_stable_pct", defaults["fraction_carbone_stable_pct"]))})
            char_table = st.data_editor(pd.DataFrame(rows), disabled=["Biomasse"], hide_index=True, use_container_width=True, key="supply_char_params")
        char_params = {r["Biomasse"]: (float(r["Rendement biochar (%)"])/100, float(r["Carbone du biochar (%)"]), float(r["Fraction stable (%)"])) for _, r in char_table.iterrows()}
        objective = st.radio("Objectif", objective_options, horizontal=True, key="supply_objective")
        budget = st.number_input("Budget maximal annuel (DH/an)", min_value=0.0, value=2_000_000.0, step=100_000.0, key="supply_budget") if objective == objective_options[0] else None
        if st.button("Calculer le plan", type="primary"):
            plan, available, max_carbon = solve_supply(pool, float(demand), char_params, "Minimiser le coût" if objective == objective_options[1] else "Maximiser le carbone", budget)
            if plan is None:
                st.error(f"Aucune solution faisable. Volume admissible : {available:,.0f} t/an ; carbone stable théorique maximal : {max_carbon:,.1f} tC/an. Vérifie le budget.")
            else:
                stable_tc = plan["carbone_stable_estime_tC_an"].sum()
                c1, c2, c3 = st.columns(3)
                c1.metric("Carbone stable estimé", f"{stable_tc:,.2f} tC/an")
                c2.metric("Stockage brut estimé", f"{stable_tc * 44 / 12:,.2f} tCO₂e/an")
                c3.metric("Coût annuel", f"{plan['cout_annuel_dh'].sum():,.0f} DH/an")
                st.dataframe(plan, use_container_width=True, hide_index=True)
                st.download_button("Télécharger le plan CSV", plan.to_csv(index=False).encode("utf-8-sig"), "plan_approvisionnement.csv", "text/csv")
                st.caption("Estimation du carbone stable stocké dans le biochar ; ce n’est pas un bilan net des émissions du cycle de vie.")
    else:
        st.write("Choisis un site et des gisements pour atteindre une production cible tout en maximisant le carbone stable, sous budget.")
        site_upload = st.file_uploader("Sites candidats (CSV)", type=["csv"], key="site_candidates_upload")
        if site_upload is None:
            sites = pd.read_csv("data/demo_sites.csv")
            st.caption("Sites fictifs chargés pour la démonstration.")
        else:
            try:
                sample = site_upload.getvalue()[:8192].decode("utf-8-sig", errors="replace")
                separator = ";" if sample.count(";") > sample.count(",") else ","
                site_upload.seek(0)
                sites = pd.read_csv(site_upload, sep=separator, decimal="," if separator == ";" else ".", encoding="utf-8-sig")
            except Exception as exc:
                st.error(f"Impossible de lire les sites candidats : {exc}")
                sites = pd.DataFrame()
        site_columns = ["id_site", "nom_site", "latitude", "longitude", "cout_fixe_dh_an", "capacite_traitement_t_an"]
        st.download_button("Télécharger le modèle des sites", pd.DataFrame(columns=site_columns).to_csv(index=False).encode("utf-8-sig"), "modele_sites_candidats.csv", "text/csv")
        if not set(site_columns).issubset(sites.columns):
            st.error("Le CSV doit contenir les colonnes du modèle téléchargé.")
        elif not all(name in data.columns for name in COORDINATES):
            st.error("Les gisements doivent avoir des coordonnées pour estimer le transport.")
        else:
            for name in ["latitude", "longitude", "cout_fixe_dh_an", "capacite_traitement_t_an"]:
                sites[name] = pd.to_numeric(sites[name], errors="coerce")
            invalid_sites = (sites.empty or sites[site_columns[2:]].isna().any().any() or sites["id_site"].duplicated().any() or (sites["cout_fixe_dh_an"] < 0).any() or (sites["capacite_traitement_t_an"] <= 0).any() or (sites["latitude"].abs() > 90).any() or (sites["longitude"].abs() > 180).any())
            if invalid_sites:
                st.error("Vérifie les coordonnées, les identifiants, les coûts fixes et les capacités des sites.")
            else:
                biomass_names = sorted(data["biomasse"].dropna().unique())
                try:
                    yield_data = pd.read_csv("data/demo_rendements.csv").set_index("biomasse")
                except Exception:
                    yield_data = pd.DataFrame()
                with st.expander("Paramètres du biochar"):
                    st.caption("Les valeurs de démonstration sont fictives et doivent être remplacées par des données validées.")
                    params_rows = []
                    for biomass in biomass_names:
                        row = yield_data.loc[biomass] if biomass in yield_data.index else pd.Series(dtype=object)
                        params_rows.append({"Biomasse": biomass,
                            "Rendement biochar (%)": float(row.get("rendement_biochar_pct", 30)),
                            "Carbone du biochar (%)": float(row.get("carbone_biochar_pct_ms", 65)),
                            "Fraction stable (%)": float(row.get("fraction_carbone_stable_pct", 80))})
                    char_table = st.data_editor(pd.DataFrame(params_rows), disabled=["Biomasse"], hide_index=True, use_container_width=True, key="location_char_params")
                char_params = {r["Biomasse"]: (float(r["Rendement biochar (%)"])/100, float(r["Carbone du biochar (%)"]), float(r["Fraction stable (%)"])) for _, r in char_table.iterrows()}
                c1, c2, c3, c4 = st.columns(4)
                target = c1.number_input("Production visée (t biochar/an)", min_value=1.0, value=100.0, step=10.0)
                rate = c2.number_input("Transport (DH/t/km)", min_value=0.0, value=0.8, step=0.1)
                road_factor = c3.number_input("Facteur de détour routier", min_value=1.0, value=1.3, step=0.1)
                objective = c4.selectbox("Objectif", objective_options, key="location_objective")
                budget = st.number_input("Budget maximal annuel (DH/an)", min_value=0.0, value=2_000_000.0, step=100_000.0, key="location_budget") if objective == objective_options[0] else None
                selected_biomass = st.multiselect("Biomasses admissibles", biomass_names, default=biomass_names, key="location_biomasses")
                st.caption("Le modèle utilise la matière sèche, le rendement en biochar, le carbone du biochar et la fraction supposée stable. Le coût inclut le site et l’approvisionnement/transport estimé.")
                with st.expander("Voir les sites candidats"):
                    st.dataframe(sites, use_container_width=True, hide_index=True)
                if st.button("Lancer l’optimisation", type="primary"):
                    solution, max_output, issue = solve_location(data, sites, char_params, target, rate, road_factor, selected_biomass,
                        "Minimiser le coût" if objective == objective_options[1] else "Maximiser le carbone", budget,
                        other_change=other_change, transport_change=transport_change)
                    if solution is None:
                        st.error(f"Aucune solution réalisable. {issue} Production maximale indicative : {max_output:,.1f} t/an.")
                    else:
                        plan, site = solution["plan"], solution["site"]
                        stable_tc = plan["carbone_stable_estime_tC_an"].sum()
                        r1, r2, r3, r4 = st.columns(4)
                        r1.metric("Site choisi", str(site["nom_site"]))
                        r2.metric("Biochar estimé", f"{max_output:,.1f} t/an")
                        r3.metric("Carbone stable estimé", f"{stable_tc:,.2f} tC/an")
                        r4.metric("Stockage brut estimé", f"{stable_tc*44/12:,.2f} tCO₂e/an")
                        st.metric("Coût annuel modélisé", f"{solution['cout_total']:,.0f} DH/an")
                        st.dataframe(plan, use_container_width=True, hide_index=True)
                        st.download_button("Télécharger le plan optimisé", plan.to_csv(index=False).encode("utf-8-sig"), "plan_optimisation_site.csv", "text/csv")
                        st.caption("Stockage brut estimé dans le biochar, pas un retrait net : les émissions de séchage, pyrolyse, transport et les usages concurrents ne sont pas soustraits.")

with data_tab:
    st.subheader("Données et qualité")
    source_missing = (
        data["source"].isna() | data["source"].astype(str).str.strip().eq("")
        if "source" in data.columns else pd.Series(True, index=data.index)
    )
    coordinates_missing = (
        data[COORDINATES].isna().any(axis=1)
        if all(name in data.columns for name in COORDINATES) else pd.Series(True, index=data.index)
    )
    carbon_missing = (
        data[["carbone_biomasse_pct_ms", "humidite_pct"]].isna().any(axis=1)
        if all(name in data.columns for name in ["carbone_biomasse_pct_ms", "humidite_pct"])
        else pd.Series(True, index=data.index)
    )
    checks = {
        "Source absente": source_missing,
        "Quantité mobilisable absente": data["quantite_mobilisable_t_an"].isna(),
        "Coordonnées absentes": coordinates_missing,
        "Coûts incomplets": ~data["cout_complet"],
        "Carbone ou humidité absent pour le calcul carbone": carbon_missing,
    }
    report = pd.DataFrame({
        "Contrôle": list(checks),
        "Lignes concernées": [int(mask.sum()) for mask in checks.values()],
    })
    st.dataframe(report, use_container_width=True, hide_index=True)
    issue_rows = pd.DataFrame({"id_gisement": data["id_gisement"]})
    issue_rows["a_completer"] = ""
    for label, mask in checks.items():
        issue_rows.loc[mask, "a_completer"] += label + "; "
    issue_rows = issue_rows[issue_rows["a_completer"] != ""]
    if not issue_rows.empty:
        st.download_button("Télécharger le rapport qualité", issue_rows.to_csv(index=False).encode("utf-8-sig"), "rapport_qualite_donnees.csv", "text/csv")
    st.download_button(
        "Télécharger le modèle des gisements",
        pd.DataFrame(columns=REQUIRED + ["province", "latitude", "longitude", "humidite_pct", "carbone_biomasse_pct_ms", "source", "niveau_fiabilite"]).to_csv(index=False).encode("utf-8-sig"),
        "modele_gisements.csv",
        "text/csv",
    )
    with st.expander("Afficher les lignes importées"):
        st.dataframe(data, use_container_width=True, hide_index=True)
