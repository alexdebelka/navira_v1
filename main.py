import streamlit as st
import pandas as pd
import folium
from folium.plugins import MarkerCluster
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
from streamlit_folium import st_folium
from streamlit_option_menu import option_menu

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
    'SLE': 'Sleeve Gastrectomy', 'BPG': 'Gastric Bypass', 'ANN': 'Band Removal',
    'REV': 'Other', 'ABL': 'Gastric Banding'
}
SURGICAL_APPROACH_NAMES = {
    'LAP': 'Open Surgery', 'COE': 'Coelioscopy', 'ROB': 'Robotic'
}

# --- 3. Load and Prepare Data ---
@st.cache_data
def load_data(path="data/flattened_v3.csv"):
    try:
        df = pd.read_csv(path)
        df.rename(columns={
            'id': 'ID', 'rs': 'Hospital Name', 'statut': 'Status', 'ville': 'City',
            'revision_surgeries_n': 'Revision Surgeries (N)', 'revision_surgeries_pct': 'Revision Surgeries (%)'
        }, inplace=True)
        df['Status'] = df['Status'].astype(str).str.strip().str.lower()
        status_mapping = {'private not-for-profit': 'private-non-profit', 'public': 'public', 'private for profit': 'private-for-profit'}
        df['Status'] = df['Status'].map(status_mapping)
        numeric_cols = [
            'Revision Surgeries (N)', 'total_procedures_period', 'annee', 'total_procedures_year',
            'university', 'cso', 'LAB_SOFFCO', 'latitude', 'longitude', 'Revision Surgeries (%)'
        ] + list(BARIATRIC_PROCEDURE_NAMES.keys()) + list(SURGICAL_APPROACH_NAMES.keys())
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        df.dropna(subset=['latitude', 'longitude'], inplace=True)
        df = df[df['latitude'].between(-90, 90) & df['longitude'].between(-180, 180)]
        return df
    except FileNotFoundError:
        st.error(f"Fatal Error: Data file '{path}' not found.")
        st.stop()

# --- Function to Calculate National Averages ---
@st.cache_data
def calculate_national_averages(dataf):
    hospital_sums = dataf.groupby('ID').agg({
         'total_procedures_period': 'first', 'Revision Surgeries (N)': 'first',
         **{proc: 'sum' for proc in BARIATRIC_PROCEDURE_NAMES.keys()},
         **{app: 'sum' for app in SURGICAL_APPROACH_NAMES.keys()}
    })
    averages = hospital_sums.mean().to_dict()
    total_approaches = sum(averages.get(app, 0) for app in SURGICAL_APPROACH_NAMES.keys())
    averages['approaches_pct'] = {}
    if total_approaches > 0:
        for app_code, app_name in SURGICAL_APPROACH_NAMES.items():
            avg_count = averages.get(app_code, 0)
            averages['approaches_pct'][app_name] = (avg_count / total_approaches) * 100 if total_approaches else 0
    return averages

# <<< FIX: Moved this block down, after load_data() is defined >>>
df = load_data()
st.session_state.df = df

if 'national_averages' not in st.session_state:
    st.session_state.national_averages = calculate_national_averages(df)
# <<< END OF FIX

# --- TOP NAVIGATION HEADER ---
selected = option_menu(
    menu_title=None,
    options=["Home", "Hospital Dashboard"],
    icons=["house", "clipboard2-data"],
    menu_icon="cast",
    default_index=0,
    orientation="horizontal",
)

if selected == "Hospital Dashboard":
    if st.session_state.selected_hospital_id:
        st.switch_page("pages/Hospital_Dashboard.py")
    else:
        st.warning("Please select a hospital from the map or list below before viewing the dashboard.")

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
        temp_df = df.copy()
        temp_df['Distance (km)'] = temp_df.apply(lambda row: geodesic(user_coords, (row['latitude'], row['longitude'])).km, axis=1)
        temp_df = temp_df[temp_df['Distance (km)'] <= radius_km]
        selected_statuses = []
        if is_public_non_profit: selected_statuses.extend(['public', 'private-non-profit'])
        if is_private_for_profit: selected_statuses.append('private-for-profit')
        temp_df = temp_df[temp_df['Status'].isin(selected_statuses)]
        if is_university: temp_df = temp_df[temp_df['university'] == 1]
        if is_soffco: temp_df = temp_df[temp_df['LAB_SOFFCO'] == 1]
        if is_health_ministry: temp_df = temp_df[temp_df['cso'] == 1]
        filtered_df = temp_df.sort_values('Distance (km)')
        st.session_state.filtered_df = filtered_df
    else:
        if st.session_state.address: st.error("Address not found. Please try a different address.")
        st.session_state.search_triggered = False

# --- Display Results: Map and List ---
if st.session_state.get('search_triggered', False) and not st.session_state.filtered_df.empty:
    unique_hospitals_df = st.session_state.filtered_df.drop_duplicates(subset=['ID']).copy()
    st.header(f"Found {len(unique_hospitals_df)} Hospitals")
    m = folium.Map(location=user_coords, zoom_start=9, tiles="CartoDB positron")
    folium.Marker(location=user_coords, popup="Your Location", icon=folium.Icon(icon="user", prefix="fa", color="red")).add_to(m)
    marker_cluster = MarkerCluster().add_to(m)
    for idx, row in unique_hospitals_df.iterrows():
        color = "blue" if row['Status'] == 'public' else "lightblue" if row['Status'] == 'private-non-profit' else "green"
        folium.Marker(location=[row['latitude'], row['longitude']], popup=f"<b>{row['Hospital Name']}</b>", icon=folium.Icon(icon="hospital-o", prefix="fa", color=color)).add_to(marker_cluster)
    map_data = st_folium(m, width="100%", height=500, key="folium_map")
    if map_data and map_data.get("last_object_clicked"):
        clicked_coords = (map_data["last_object_clicked"]["lat"], map_data["last_object_clicked"]["lng"])
        distances = unique_hospitals_df.apply(lambda row: geodesic(clicked_coords, (row['latitude'], row['longitude'])).km, axis=1)
        if distances.min() < 0.1:
            st.session_state.selected_hospital_id = unique_hospitals_df.loc[distances.idxmin()]['ID']
            st.switch_page("pages/Hospital_Dashboard.py")
    st.subheader("Hospital List")
    for idx, row in unique_hospitals_df.iterrows():
        col1, col2, col3 = st.columns([4, 2, 2])
        col1.markdown(f"**{row['Hospital Name']}** ({row['City']})")
        col2.markdown(f"*{row['Distance (km)']:.1f} km*")
        if col3.button("View Details", key=f"details_{row['ID']}"):
            st.session_state.selected_hospital_id = row['ID']
            st.switch_page("pages/Hospital_Dashboard.py")
elif st.session_state.get('search_triggered', False):
    st.warning("No hospitals found matching your criteria. Try increasing the search radius or changing filters.")
