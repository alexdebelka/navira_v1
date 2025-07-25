import streamlit as st
import pandas as pd
import folium
from folium.plugins import MarkerCluster
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
from streamlit_folium import st_folium

# --- 1. App Configuration ---
st.set_page_config(
    page_title="Navira - Hospital Explorer",
    page_icon="🏥",
    layout="wide"
)

# --- 2. Session State Initialization ---
if "search_triggered" not in st.session_state:
    st.session_state.search_triggered = False
if "selected_hospital_id" not in st.session_state:
    st.session_state.selected_hospital_id = None
if "address" not in st.session_state:
    st.session_state.address = ""

# --- MAPPING DICTIONARIES FOR READABILITY ---
BARIATRIC_PROCEDURE_NAMES = {
    'ABL': 'Gastric Banding',
    'ANN': 'Ring Adjustment',
    'BPG': 'Bypass Gastric',
    'REV': 'Revision Surgery',
    'SLE': 'Sleeve'
}

SURGICAL_APPROACH_NAMES = {
    'COE': 'Coelioscopy',
    'LAP': 'Laparoscopy',
    'ROB': 'Robotic'
}

# --- 3. Load and Prepare Data ---
@st.cache_data
def load_data(path="flattened_v3.csv"): # UPDATED: Using the new flattened file
    """
    Loads and cleans the final FLAT denormalized hospital data with robust type conversion.
    """
    try:
        df = pd.read_csv(path)
        # Rename columns for consistency and readability
        df.rename(columns={
            'id': 'ID', 'rs': 'Hospital Name', 'statut': 'Status', 'ville': 'City',
            'revision_surgeries_n': 'Revision Surgeries (N)',
            'revision_surgeries_pct': 'Revision Surgeries (%)'
        }, inplace=True)

        # Define all columns that should be numeric
        numeric_int_cols = [
            'Revision Surgeries (N)', 'total_procedures_period', 'annee',
            'total_procedures_year', 'university', 'cso', 'LAB_SOFFCO'
        ] + list(BARIATRIC_PROCEDURE_NAMES.keys()) + list(SURGICAL_APPROACH_NAMES.keys())
        
        numeric_float_cols = ['latitude', 'longitude', 'Revision Surgeries (%)']

        # Clean and convert integer columns
        for col in numeric_int_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(int)
        
        # Clean and convert float columns
        for col in numeric_float_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        
        # Ensure geographic text columns are strings
        for col in ['lib_dep', 'lib_reg']:
             if col in df.columns:
                df[col] = df[col].astype(str)

        df.drop_duplicates(subset=['ID', 'annee'], keep='first', inplace=True)
        
        df.dropna(subset=['latitude', 'longitude'], inplace=True)
        df = df[df['latitude'].between(-90, 90) & df['longitude'].between(-180, 180)]
        return df
    except FileNotFoundError:
        st.error(f"Fatal Error: The data file '{path}' was not found. Please make sure it's in the same directory.")
        return pd.DataFrame()

df = load_data()

# --- 4. Sidebar for User Input and Filters ---
with st.sidebar:
    st.header("🔍 Search Controls")
    address_input = st.text_input(
        "📍 Enter your address or postal code",
        value=st.session_state.address,
        placeholder="e.g., 75019 or Paris"
    )
    radius_km = st.slider("📏 Search Radius (km)", min_value=5, max_value=500, value=50, step=5)

    st.header("⚙️ Filter Results")
    unique_statuses = ['All'] + sorted(df['Status'].dropna().unique().tolist())
    selected_status = st.selectbox("Filter by Hospital Status", unique_statuses)

    if st.button("🔎 Search Hospitals"):
        if address_input:
            st.session_state.address = address_input
            st.session_state.search_triggered = True
            st.session_state.selected_hospital_id = None
            st.rerun()
        else:
            st.warning("Please enter an address first.")
            st.session_state.search_triggered = False

    if st.button("🔄 Reset Search"):
        st.session_state.search_triggered = False
        st.session_state.selected_hospital_id = None
        st.session_state.address = ""
        st.rerun()

# --- 5. Main Page UI ---
st.title("🏥 Navira - French Hospital Explorer")
st.markdown("Find specialized hospitals based on your location and chosen criteria. Created in collaboration with Avicenne Hospital, Bobigny.")
st.markdown("---")

# --- 6. Geocoding and Filtering Logic ---
@st.cache_data(show_spinner="Geocoding address...")
def geocode_address(address):
    if not address: return None
    try:
        geolocator = Nominatim(user_agent="navira_streamlit_app_v15")
        location = geolocator.geocode(f"{address.strip()}, France", timeout=10)
        return (location.latitude, location.longitude) if location else None
    except Exception as e:
        st.error(f"Geocoding failed: {e}")
        return None

filtered_df = pd.DataFrame()
user_coords = None

if st.session_state.search_triggered:
    user_coords = geocode_address(st.session_state.address)
    if user_coords:
        temp_df = df.copy()
        temp_df['Distance (km)'] = temp_df.apply(
            lambda row: geodesic(user_coords, (row['latitude'], row['longitude'])).km, axis=1
        )
        temp_df = temp_df[temp_df['Distance (km)'] <= radius_km]
        if selected_status != 'All':
            temp_df = temp_df[temp_df['Status'] == selected_status]
        
        filtered_df = temp_df.sort_values('Distance (km)')
    else:
        if st.session_state.address:
            st.error("Address not found. Please try a different address or format (e.g., 'City, Postal Code').")
        st.session_state.search_triggered = False

# --- 7. Display Results ---
if not filtered_df.empty:
    unique_hospitals_df = filtered_df.drop_duplicates(subset=['ID']).copy()

    st.header(f"🗺️ Map of {len(unique_hospitals_df)} Found Hospitals")
    st.info("Click on a blue hospital marker on the map to see its detailed statistics below.")
    
    m = folium.Map(location=user_coords, zoom_start=9)
    folium.Marker(location=user_coords, popup="Your Location", icon=folium.Icon(icon="user", prefix="fa", color="red")).add_to(m)
    
    marker_cluster = MarkerCluster().add_to(m)
    for idx, row in unique_hospitals_df.iterrows():
        popup_content = f"<b>{row['Hospital Name']}</b><br>City: {row['City']}"
        folium.Marker(
            location=[row['latitude'], row['longitude']],
            popup=folium.Popup(popup_content, max_width=300),
            icon=folium.Icon(icon="hospital-o", prefix="fa", color="blue")
        ).add_to(marker_cluster)
        
    map_data = st_folium(m, width="100%", height=500)

    if map_data and map_data.get("last_object_clicked"):
        clicked_coords = (map_data["last_object_clicked"]["lat"], map_data["last_object_clicked"]["lng"])
        distances = unique_hospitals_df.apply(
            lambda row: geodesic(clicked_coords, (row['latitude'], row['longitude'])).km, axis=1
        )
        if distances.min() < 0.1:
            st.session_state.selected_hospital_id = unique_hospitals_df.loc[distances.idxmin()]['ID']

    if st.session_state.selected_hospital_id and st.session_state.selected_hospital_id not in filtered_df['ID'].values:
        st.session_state.selected_hospital_id = None

    if st.session_state.selected_hospital_id:
        selected_hospital_all_data = filtered_df[filtered_df['ID'] == st.session_state.selected_hospital_id]
        
        if not selected_hospital_all_data.empty:
            selected_hospital_details = selected_hospital_all_data.iloc[0]

            st.header(f"📊 Detailed Data for: {selected_hospital_details['Hospital Name']}")

            st.subheader("Hospital Information")
            col1, col2, col3 = st.columns(3)
            col1.metric("City", selected_hospital_details['City'])
            col2.metric("Status", selected_hospital_details['Status'])
            col3.metric("Distance from you", f"{selected_hospital_details['Distance (km)']:.1f} km")
            
            # --- NEW: Display Labels and Geographic Info ---
            st.subheader("Labels & Affiliations")
            labels_col, geo_col = st.columns(2)

            with labels_col:
                if selected_hospital_details['LAB_SOFFCO'] == 1:
                    st.success("✅ Centre of Excellence (Bariatric French Society)")
                if selected_hospital_details['cso'] == 1:
                    st.success("✅ Centre of Excellence (Health Ministry)")
                if selected_hospital_details['university'] == 1:
                    st.info("🎓 Academic Affiliation")

            with geo_col:
                st.write(f"**Department:** {selected_hospital_details['lib_dep']} ({selected_hospital_details['code_dep']})")
                st.write(f"**Region:** {selected_hospital_details['lib_reg']} ({selected_hospital_details['code_reg']})")

            st.markdown("---")
            
            st.subheader("Revision Surgery Statistics (2020-2024)")
            col1, col2 = st.columns(2)
            col1.metric("Total Revision Surgeries", f"{selected_hospital_details['Revision Surgeries (N)']:.0f}")
            col2.metric("Revision Surgery Rate", f"{selected_hospital_details['Revision Surgeries (%)']:.1f}%")
            
            hospital_annual_data = selected_hospital_all_data.set_index('annee').sort_index(ascending=False)

            st.subheader("Bariatric Procedures by Year")
            bariatric_df = hospital_annual_data[BARIATRIC_PROCEDURE_NAMES.keys()].rename(columns=BARIATRIC_PROCEDURE_NAMES)
            if not bariatric_df.empty and bariatric_df.sum().sum() > 0:
                st.bar_chart(bariatric_df)
                st.dataframe(bariatric_df)
            else:
                st.info("No bariatric procedure data available for this hospital.")

            st.subheader("Surgical Approaches by Year")
            approach_df = hospital_annual_data[SURGICAL_APPROACH_NAMES.keys()].rename(columns=SURGICAL_APPROACH_NAMES)
            if not approach_df.empty and approach_df.sum().sum() > 0:
                st.bar_chart(approach_df)
                st.dataframe(approach_df)
            else:
                st.info("No surgical approach data available for this hospital.")

elif st.session_state.search_triggered:
    st.warning("No hospitals found matching your criteria. Try increasing the search radius or changing filters.")
else:
    st.info("Enter your address in the sidebar and click 'Search Hospitals' to begin.")
