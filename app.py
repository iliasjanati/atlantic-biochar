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
    upload = st.file_uploader("Importer les données (CSV)", type=["csv"])
    st.caption("Sans import, le prototype utilise son jeu fictif de démonstration.")
    st.divider()
    st.header("Hypothèses de scénario")
    availability = st.slider("Part mobilisable conservée (%)", 0, 100, 100, 5) / 100
    transport_change = st.slider("Variation du coût de transport (%)", -50, 200, 0, 10)
    other_change = st.slider("Variation des autres coûts (%)", -50, 200, 0, 10)


def load_frame(file):
    return (pd.read_csv(file), False) if file else (pd.read_csv("data/demo_gisements.csv"), True)


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
    if frame["id_gisement"].isna().any() or frame["id_gisement"].duplicated().any():
        errors.append("Les identifiants doivent être renseignés et uniques.")
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


try:
    data, demo = (pd.read_csv(upload), False) if upload else (pd.read_csv("data/demo_gisements.csv"), True)
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

home, map_tab, compare, optimize, quality_tab = st.tabs(["Tableau de bord", "Carte", "Comparer les régions", "Plan d’approvisionnement", "Qualité des données"])
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
    source_missing = int(data["source"].isna().sum()) if "source" in data.columns else len(data)
    quality = pd.DataFrame({
        "Indicateur": ["Quantité mobilisable manquante", "Coût incomplet", "Source absente", "Données fictives"],
        "Lignes": [int(data["quantite_mobilisable_t_an"].isna().sum()), int((~data["cout_complet"]).sum()), source_missing, int(data["statut_donnee"].astype(str).str.contains("fictif|demo", case=False, regex=True).sum())],
    })
    st.dataframe(quality, use_container_width=True, hide_index=True)
    st.caption("Les cellules inconnues restent manquantes ; elles ne sont pas remplacées par zéro.")
    st.dataframe(data, use_container_width=True, hide_index=True)
    template = pd.DataFrame(columns=REQUIRED + ["province", "latitude", "longitude", "source", "niveau_fiabilite"])
    st.download_button("Télécharger un modèle CSV vide", template.to_csv(index=False).encode("utf-8-sig"), "modele_gisements.csv", "text/csv")
