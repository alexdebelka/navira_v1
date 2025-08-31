import streamlit as st
import pandas as pd
import folium
from folium.plugins import MarkerCluster
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
from streamlit_folium import st_folium
from streamlit_option_menu import option_menu
from navira.data_loader import get_dataframes
from auth_wrapper import add_auth_to_page
import os

# Add authentication check
add_auth_to_page()

# Handle navigation requests
handle_navigation_request()
navigate_to = st.session_state.get('navigate_to')
if navigate_to:
    from navigation_utils import navigate_to_page
    navigate_to_page(navigate_to)
    st.session_state.navigate_to = None

# --- 1. App Configuration ---
st.set_page_config(
    page_title="Navira - Hospital Explorer",
    page_icon="🏥",
    layout="wide"
)

# --- HIDE THE DEFAULT SIDEBAR ---
st.markdown("""
    <style>
        [data-testid="stSidebarNav"] {
            display: none;
        }
    </style>
""", unsafe_allow_html=True)

# --- 2. Session State Initialization ---
if "selected_hospital_id" not in st.session_state:
    st.session_state.selected_hospital_id = None
if "address" not in st.session_state:
    st.session_state.address = ""
if "filtered_df" not in st.session_state:
    st.session_state.filtered_df = pd.DataFrame()

# --- MAPPING DICTIONARIES ---
BARIATRIC_PROCEDURE_NAMES = {
    'SLE': 'Sleeve Gastrectomy',
    'BPG': 'Gastric Bypass',
    'ANN': 'Gastric Banding',
    'REV': 'Other',
    'ABL': 'Band Removal',
    'DBP': 'Bilio-pancreatic Diversion',
    'GVC': 'Calibrated Vertical Gastroplasty',
    'NDD': 'Not Defined',
}
SURGICAL_APPROACH_NAMES = {
    'LAP': 'Open Surgery', 'COE': 'Coelioscopy', 'ROB': 'Robotic'
}

# --- 3. Load Data (Parquet) ---
try:
    establishments, annual = get_dataframes()
except Exception as e:
    st.error("Parquet data not found. Please run: make parquet")
    st.stop()

# Minimal schema checks (allow soft recovery on id; hard-require name/lat/lon)
required_est_cols = {"name", "latitude", "longitude"}
required_ann_cols = {"id", "annee", "total_procedures_year"}
missing_est = required_est_cols - set(establishments.columns)
missing_ann = required_ann_cols - set(annual.columns)
if missing_est or missing_ann or ('id' not in establishments.columns):
    if 'id' not in establishments.columns:
        st.warning("Establishments missing 'id'; attempting soft recovery from raw CSV. If map works, you can ignore this warning.")
    st.error(
        f"Parquet schema invalid. Missing columns -> establishments: {sorted(list(required_est_cols - set(establishments.columns)))}; annual: {sorted(missing_ann)}.\n"
        "If this persists after reload, please rebuild: make parquet"
    )
    if missing_ann:
        st.stop()

# Filter establishments to those that have data in annual (ensures details always resolve)
if 'id' in establishments.columns and 'id' in annual.columns:
    valid_ids = set(annual['id'].astype(str).unique())
    establishments = establishments[establishments['id'].astype(str).isin(valid_ids)].copy()
    # Drop duplicates on id to avoid multiple markers per site
    establishments = establishments.drop_duplicates(subset=['id'], keep='first')

# --- Function to Calculate National Averages (from annual table) ---
@st.cache_data(show_spinner=False)
def calculate_national_averages(annual_df: pd.DataFrame):
    dataf_clean = annual_df.drop_duplicates(subset=['id', 'annee'], keep='first')
    dataf_eligible = dataf_clean[dataf_clean['total_procedures_year'] >= 25]
    # Average per hospital across years for procedures and approaches
    proc_aggs = {proc: 'mean' for proc in BARIATRIC_PROCEDURE_NAMES.keys() if proc in dataf_eligible.columns}
    appr_aggs = {app: 'mean' for app in SURGICAL_APPROACH_NAMES.keys() if app in dataf_eligible.columns}
    hospital_averages = dataf_eligible.groupby('id').agg({**proc_aggs, **appr_aggs})
    averages = hospital_averages.mean().to_dict()
    # Total surgeries per period (sum of yearly totals)
    totals_per_hospital = dataf_eligible.groupby('id')['total_procedures_year'].sum()
    averages['total_procedures_period'] = float(totals_per_hospital.mean()) if not totals_per_hospital.empty else 0.0
    # Approach mix percentages
    total_approaches = sum(averages.get(app, 0) for app in SURGICAL_APPROACH_NAMES.keys())
    averages['approaches_pct'] = {}
    if total_approaches > 0:
        for app_code, app_name in SURGICAL_APPROACH_NAMES.items():
            avg_count = averages.get(app_code, 0)
            averages['approaches_pct'][app_name] = (avg_count / total_approaches) * 100 if total_approaches else 0
    # Revision percentage average: use establishments if available
    try:
        from navira.data_loader import get_dataframes as _get
        est, _ = _get()
        if {'id','revision_surgeries_n'}.issubset(est.columns):
            # Revisions per hospital (ensure one value per id)
            rev_by_id = (
                est.assign(id=est['id'].astype(str))
                   .groupby('id')['revision_surgeries_n']
                   .sum()
            )
            # Total surgeries per hospital from annual
            totals = annual_df.assign(id=annual_df['id'].astype(str)).groupby('id')['total_procedures_year'].sum()
            common = rev_by_id.index.intersection(totals.index)
            if len(common) > 0:
                pct_series = (rev_by_id.loc[common] / totals.loc[common] * 100).replace([pd.NA], 0).fillna(0)
                averages['revision_pct_avg'] = float(pct_series.mean()) if not pct_series.empty else 0.0
            else:
                averages['revision_pct_avg'] = 0.0
        else:
            averages['revision_pct_avg'] = 0.0
    except Exception:
        averages['revision_pct_avg'] = 0.0
    return averages

# Store references in session for other pages
st.session_state.establishments = establishments
st.session_state.annual = annual
if 'national_averages' not in st.session_state:
    st.session_state.national_averages = calculate_national_averages(annual)

# --- TOP NAVIGATION HEADER ---
selected = option_menu(
    menu_title=None,
    options=["User Dashboard", "Hospital Explorer", "Hospital Dashboard", "National Overview"],
    icons=["person-circle", "house", "clipboard2-data", "globe2"],
    menu_icon="cast",
    default_index=1,
    orientation="horizontal",
)

if selected == "User Dashboard":
    st.session_state.navigate_to = "dashboard"
    st.rerun()
elif selected == "Hospital Dashboard":
    if st.session_state.selected_hospital_id:
        st.session_state.navigate_to = "hospital"
        st.rerun()
    else:
        st.warning("Please select a hospital from the map or list below before viewing the dashboard.")
elif selected == "National Overview":
    st.session_state.navigate_to = "national"
    st.rerun()

# --- Main Page UI ---
st.title("🏥 Navira - French Hospital Explorer")

_, center_col, _ = st.columns([1, 2, 1])
with center_col:
    with st.form(key="search_form"):
        address_input = st.text_input("📍 Enter your address or postal code", value=st.session_state.address, placeholder="e.g., 75019 or Paris")
        with st.expander("Advanced Filters"):
            radius_km = st.slider("📏 Search Radius (km)", 5, 300, 50, 5)
            st.markdown("**Establishment Type**")
            col1, col2 = st.columns(2)
            is_public_non_profit = col1.checkbox("Public / Non-Profit", True)
            is_private_for_profit = col2.checkbox("Private For-Profit", True)
            st.markdown("**Labels & Affiliations**")
            col3, col4, col5 = st.columns(3)
            is_university = col3.checkbox("University Hospital")
            is_soffco = col4.checkbox("Centre of Excellence (SOFFCO)")
            is_health_ministry = col5.checkbox("Centre of Excellence (Health Ministry)")
        
        search_col, reset_col = st.columns(2)
        submitted = search_col.form_submit_button("🔎 Search Hospitals", use_container_width=True)
        reset_clicked = reset_col.form_submit_button("🔄 Reset", use_container_width=True)

        if submitted and address_input:
            # Track hospital search
            try:
                from analytics_integration import track_search
                track_search(address_input, 0)  # Will update count after filtering
            except Exception as e:
                print(f"Analytics tracking error: {e}")
            
            st.session_state.address = address_input
            st.session_state.search_triggered = True
            st.session_state.selected_hospital_id = None
        elif submitted:
            st.warning("Please enter an address first.")
            st.session_state.search_triggered = False
        if reset_clicked:
            st.session_state.search_triggered = False
            st.session_state.selected_hospital_id = None
            st.session_state.address = ""
            st.session_state.filtered_df = pd.DataFrame()
st.markdown("---")

# --- Geocoding and Filtering Logic ---
@st.cache_data(show_spinner="Geocoding address...")
def geocode_address(address):
    if not address: return None
    try:
        geolocator = Nominatim(user_agent="navira_streamlit_app_v26")
        location = geolocator.geocode(f"{address.strip()}, France", timeout=10)
        return (location.latitude, location.longitude) if location else None
    except Exception as e:
        st.error(f"Geocoding failed: {e}")
        return None
        
if st.session_state.get('search_triggered', False):
    user_coords = geocode_address(st.session_state.address)
    if user_coords:
        temp_df = establishments.copy()
        temp_df['Distance (km)'] = temp_df.apply(lambda row: geodesic(user_coords, (row['latitude'], row['longitude'])).km, axis=1)
        temp_df = temp_df[temp_df['Distance (km)'] <= radius_km]
        # Normalize and map status values for filtering
        temp_df['statut_norm'] = temp_df['statut'].astype(str).str.strip().str.lower()
        selected_statuses = []
        if is_public_non_profit: selected_statuses.extend(['public', 'private not-for-profit'])
        if is_private_for_profit: selected_statuses.append('private for profit')
        temp_df = temp_df[temp_df['statut_norm'].isin([s.lower() for s in selected_statuses])]
        if is_university: temp_df = temp_df[temp_df['university'] == 1]
        if is_soffco: temp_df = temp_df[temp_df['LAB_SOFFCO'] == 1]
        if is_health_ministry: temp_df = temp_df[temp_df['cso'] == 1]
        filtered_df = temp_df.sort_values('Distance (km)')
        st.session_state.filtered_df = filtered_df
        
        # Update search tracking with results count
        try:
            from analytics_integration import track_user_action
            track_user_action("search_results", "hospital_explorer", {
                "search_term": st.session_state.address,
                "results_count": len(filtered_df),
                "radius_km": radius_km,
                "filters_applied": {
                    "public_non_profit": is_public_non_profit,
                    "private_for_profit": is_private_for_profit,
                    "university": is_university,
                    "soffco": is_soffco,
                    "health_ministry": is_health_ministry
                }
            })
        except Exception as e:
            print(f"Analytics tracking error: {e}")
    else:
        if st.session_state.address: st.error("Address not found. Please try a different address.")
        st.session_state.search_triggered = False

# --- Display Results: Map and List ---
if st.session_state.get('search_triggered', False) and not st.session_state.filtered_df.empty:
    unique_hospitals_df = st.session_state.filtered_df.drop_duplicates(subset=['id']).copy()
    st.header(f"Found {len(unique_hospitals_df)} Hospitals")
    m = folium.Map(location=user_coords, zoom_start=9, tiles="CartoDB positron")
    folium.Marker(location=user_coords, popup="Your Location", icon=folium.Icon(icon="user", prefix="fa", color="red")).add_to(m)
    marker_cluster = MarkerCluster().add_to(m)
    for idx, row in unique_hospitals_df.iterrows():
        statut_norm = str(row.get('statut', '')).strip().lower()
        if statut_norm == 'public':
            color = "blue"
        elif statut_norm == 'private not-for-profit':
            color = "lightblue"
        else:
            color = "green"
        folium.Marker(location=[row['latitude'], row['longitude']], popup=f"<b>{row['name']}</b>", icon=folium.Icon(icon="hospital-o", prefix="fa", color=color)).add_to(marker_cluster)
    map_data = st_folium(m, width="100%", height=500, key="folium_map")
    if map_data and map_data.get("last_object_clicked"):
        clicked_coords = (map_data["last_object_clicked"]["lat"], map_data["last_object_clicked"]["lng"])
        distances = unique_hospitals_df.apply(lambda row: geodesic(clicked_coords, (row['latitude'], row['longitude'])).km, axis=1)
        if distances.min() < 0.1:
            selected_hospital = unique_hospitals_df.loc[distances.idxmin()]
            st.session_state.selected_hospital_id = selected_hospital['id']
            
            # Track hospital selection from map
            try:
                from analytics_integration import track_user_action
                track_user_action("hospital_selected", "hospital_explorer", {
                    "selection_method": "map_click",
                    "hospital_id": selected_hospital['id'],
                    "hospital_name": selected_hospital['name'],
                    "hospital_city": selected_hospital['ville'],
                    "distance_km": selected_hospital['Distance (km)']
                })
            except Exception as e:
                print(f"Analytics tracking error: {e}")
            
            st.session_state.navigate_to = "hospital"
            st.rerun()
    st.subheader("Hospital List")
    for idx, row in unique_hospitals_df.iterrows():
        col1, col2, col3 = st.columns([4, 2, 2])
        col1.markdown(f"**{row['name']}** ({row['ville']})")
        col2.markdown(f"*{row['Distance (km)']:.1f} km*")
        if col3.button("View Details", key=f"details_{row['id']}"):
            # Track hospital selection from list
            try:
                from analytics_integration import track_user_action
                track_user_action("hospital_selected", "hospital_explorer", {
                    "selection_method": "list_button",
                    "hospital_id": row['id'],
                    "hospital_name": row['name'],
                    "hospital_city": row['ville'],
                    "distance_km": row['Distance (km)']
                })
            except Exception as e:
                print(f"Analytics tracking error: {e}")
            
            st.session_state.selected_hospital_id = row['id']
            st.session_state.navigate_to = "hospital"
            st.rerun()
        st.markdown("---")
elif st.session_state.get('search_triggered', False):
    st.warning("No hospitals found matching your criteria. Try increasing the search radius or changing filters.")
