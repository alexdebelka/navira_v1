import streamlit as st
import pandas as pd
import folium
from folium.plugins import MarkerCluster
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
from streamlit_folium import st_folium
from navira.data_loader import get_dataframes, get_all_dataframes
from auth_wrapper import add_auth_to_page
from navigation_utils import handle_navigation_request
handle_navigation_request()

# Add authentication check
add_auth_to_page()

# --- Page Configuration ---
st.set_page_config(
    page_title="Hospital Explorer",
    page_icon="🏥",
    layout="wide"
)

# --- HIDE THE DEFAULT STREAMLIT NAVIGATION ---
st.markdown("""
    <style>
        [data-testid="stSidebarNav"] {
            display: none;
        }
        [data-testid="stPageNav"] {
            display: none;
        }
    </style>
""", unsafe_allow_html=True)

# --- Load Data ---
try:
    establishments, annual = get_dataframes()
    # Load additional datasets
    all_data = get_all_dataframes()
    recruitment_zones = all_data.get('recruitment', pd.DataFrame())
    cities = all_data.get('cities', pd.DataFrame())
    
    # Filter establishments to only include hospitals with actual data
    # First, get hospitals that have data in the annual dataset
    hospitals_with_data = annual['id'].unique()
    
    # Filter establishments to only include hospitals with data
    establishments = establishments[establishments['id'].isin(hospitals_with_data)]
    
    # Apply minimum intervention threshold (25 procedures per year)
    # Get hospitals that meet the threshold
    hospital_volumes = annual.groupby('id')['total_procedures_year'].sum()
    eligible_hospitals = hospital_volumes[hospital_volumes >= 25].index
    
    # Filter establishments to only include eligible hospitals
    establishments = establishments[establishments['id'].isin(eligible_hospitals)]
    
    # Store in session state for other pages
    st.session_state.establishments = establishments
    st.session_state.annual = annual

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
    
    # --- Function to Calculate National Averages ---
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
        # Revision percentage average
        try:
            import numpy as np
            revision_counts = establishments['revision_surgeries_n'].fillna(0).astype(float)
            total_procedures = establishments['total_procedures_year'].fillna(0).astype(float)
            revision_pcts = (revision_counts / total_procedures * 100).replace([np.inf, -np.inf], 0)
            averages['revision_pct_avg'] = float(revision_pcts.mean()) if not revision_pcts.empty else 0.0
        except:
            averages['revision_pct_avg'] = 0.0
        return averages
    
    if 'national_averages' not in st.session_state:
        st.session_state.national_averages = calculate_national_averages(annual)
    
    # --- Session State Initialization ---
    if "selected_hospital_id" not in st.session_state:
        st.session_state.selected_hospital_id = None
    if "address" not in st.session_state:
        st.session_state.address = ""
    if "filtered_df" not in st.session_state:
        st.session_state.filtered_df = pd.DataFrame()
    
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
        else:
            if st.session_state.address: st.error("Address not found. Please try a different address.")
            st.session_state.search_triggered = False

    # --- Function to add recruitment zones to map ---
    def add_recruitment_zones_to_map(folium_map, hospital_id, recruitment_df, cities_df):
        """Add patient recruitment zones as heatmap/circles to the map"""
        if recruitment_df.empty or cities_df.empty:
            return
            
        # Get recruitment data for this hospital
        hospital_recruitment = recruitment_df[recruitment_df['hospital_id'] == str(hospital_id)]
        
        if hospital_recruitment.empty:
            return
            
        # Merge with cities to get coordinates
        recruitment_with_coords = hospital_recruitment.merge(
            cities_df[['city_code', 'latitude', 'longitude', 'city_name']], 
            on='city_code', 
            how='left'
        )
        
        # Filter out rows without coordinates
        recruitment_with_coords = recruitment_with_coords.dropna(subset=['latitude', 'longitude'])
        
        if recruitment_with_coords.empty:
            return
            
        # Add circles for recruitment zones - size based on patient count
        max_patients = recruitment_with_coords['patient_count'].max()
        min_patients = recruitment_with_coords['patient_count'].min()
        
        for _, zone in recruitment_with_coords.iterrows():
            # Scale radius based on patient count (between 500m and 5000m)
            if max_patients > min_patients:
                normalized_size = (zone['patient_count'] - min_patients) / (max_patients - min_patients)
            else:
                normalized_size = 0.5
            radius = 500 + (normalized_size * 4500)  # 500m to 5000m
            
            # Color intensity based on percentage
            opacity = min(0.8, zone['percentage'] / 100 * 3)  # Cap at 0.8 opacity
            
            folium.Circle(
                location=[zone['latitude'], zone['longitude']],
                radius=radius,
                popup=f"<b>{zone.get('city_name', 'Unknown City')}</b><br>Patients: {zone['patient_count']}<br>Percentage: {zone['percentage']:.1f}%",
                color='orange',
                fillColor='orange',
                opacity=0.6,
                fillOpacity=opacity
            ).add_to(folium_map)
    
    # --- Display Results: Map and List ---
    if st.session_state.get('search_triggered', False) and not st.session_state.filtered_df.empty:
        unique_hospitals_df = st.session_state.filtered_df.drop_duplicates(subset=['id']).copy()
        st.header(f"Found {len(unique_hospitals_df)} Hospitals")
        
        # Add toggle for recruitment zones
        show_recruitment = st.toggle("Show Patient Recruitment Zones", value=False)
        if show_recruitment:
            selected_hospital_for_recruitment = st.selectbox(
                "Select hospital to show recruitment zones:",
                options=unique_hospitals_df['id'].tolist(),
                format_func=lambda x: unique_hospitals_df[unique_hospitals_df['id']==x]['name'].iloc[0] if not unique_hospitals_df[unique_hospitals_df['id']==x].empty else x,
                key="recruitment_hospital_selector"
            )
        
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
        
        # Add recruitment zones if toggled on
        if show_recruitment and 'selected_hospital_for_recruitment' in locals():
            add_recruitment_zones_to_map(m, selected_hospital_for_recruitment, recruitment_zones, cities)
            
        map_data = st_folium(m, width="100%", height=500, key="folium_map")
        if map_data and map_data.get("last_object_clicked"):
            clicked_coords = (map_data["last_object_clicked"]["lat"], map_data["last_object_clicked"]["lng"])
            distances = unique_hospitals_df.apply(lambda row: geodesic(clicked_coords, (row['latitude'], row['longitude'])).km, axis=1)
            if distances.min() < 0.1:
                st.session_state.selected_hospital_id = unique_hospitals_df.loc[distances.idxmin()]['id']
                st.switch_page("pages/dashboard.py")
        
        st.subheader("Hospital List")
        for idx, row in unique_hospitals_df.iterrows():
            col1, col2, col3 = st.columns([4, 2, 2])
            col1.markdown(f"**{row['name']}** ({row['ville']})")
            col2.markdown(f"*{row['Distance (km)']:.1f} km*")
            # Create a unique key using index and hospital name to avoid duplicates
            unique_key = f"details_{idx}_{row['name'].replace(' ', '_').replace('-', '_')}_{row['id']}"
            if col3.button("View Details", key=unique_key):
                st.session_state.selected_hospital_id = row['id']
                st.switch_page("pages/dashboard.py")
            st.markdown("---")
    elif st.session_state.get('search_triggered', False):
        st.warning("No hospitals found matching your criteria. Try increasing the search radius or changing filters.")

except Exception as e:
    st.error(f"Error loading hospital explorer: {e}")
    st.info("Please make sure all required data files are available.")
