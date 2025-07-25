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
    page_icon="�",
    layout="wide"
)

# --- 2. Session State Initialization ---
# This will store the ID of the hospital clicked on the map
if "selected_hospital_id" not in st.session_state:
    st.session_state.selected_hospital_id = None

if "search_triggered" not in st.session_state:
    st.session_state.search_triggered = False

# --- 3. Load and Prepare Data ---
@st.cache_data
def load_data(path="final_flat_data.csv"):
    """
    Loads the final FLAT denormalized hospital data with pre-calculated totals.
    """
    try:
        df = pd.read_csv(path)
        df.rename(columns={
            'id': 'ID', 'rs': 'Hospital Name', 'statut': 'Status', 'ville': 'City',
            'latitude': 'latitude', 'longitude': 'longitude',
            'revision_surgeries_n': 'Revision Surgeries (N)',
            'revision_surgeries_pct': 'Revision Surgeries (%)'
        }, inplace=True)
        df['latitude'] = pd.to_numeric(df['latitude'], errors='coerce')
        df['longitude'] = pd.to_numeric(df['longitude'], errors='coerce')
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
    address = st.text_input("📍 Enter your address or postal code", placeholder="e.g., 75019 or Paris")
    radius_km = st.slider("📏 Search Radius (km)", min_value=5, max_value=500, value=50, step=5)

    st.header("⚙️ Filter Results")
    unique_statuses = ['All'] + sorted(df['Status'].dropna().unique().tolist())
    selected_status = st.selectbox("Filter by Hospital Status", unique_statuses)

    if st.button("🔎 Search Hospitals"):
        if address:
            st.session_state.search_triggered = True
            st.session_state.selected_hospital_id = None # Reset selection on new search
        else:
            st.warning("Please enter an address first.")
            st.session_state.search_triggered = False

    if st.button("🔄 Reset Search"):
        st.session_state.search_triggered = False
        st.session_state.selected_hospital_id = None
        st.experimental_rerun()

# --- 5. Main Page UI ---
st.title("🏥 Navira - French Hospital Explorer")
st.markdown("Find specialized hospitals based on your location and chosen criteria. Created in collaboration with Avicenne Hospital, Bobigny.")
st.markdown("---")

# --- 6. Geocoding and Filtering Logic ---
@st.cache_data(show_spinner="Geocoding address...")
def geocode_address(address):
    if not address: return None
    try:
        geolocator = Nominatim(user_agent="navira_streamlit_app_v5")
        location = geolocator.geocode(f"{address.strip()}, France", timeout=10)
        return (location.latitude, location.longitude) if location else None
    except Exception:
        return None

filtered_df = pd.DataFrame()
user_coords = None
if st.session_state.search_triggered:
    user_coords = geocode_address(address)
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
        if address: # Only show error if an address was actually entered
            st.error("Address not found. Please try a different address or format.")
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
        
    map_data = st_folium(m, width="100%", height=500, center=user_coords, zoom=9)

    # --- NEW, ROBUST LOGIC ---
    # Check if a marker was clicked by looking at the returned coordinates
    if map_data and map_data.get("last_object_clicked"):
        clicked_coords = (
            map_data["last_object_clicked"]["lat"],
            map_data["last_object_clicked"]["lng"]
        )
        
        # Find the hospital in our unique list that is closest to the clicked point
        distances = unique_hospitals_df.apply(
            lambda row: geodesic(clicked_coords, (row['latitude'], row['longitude'])).km,
            axis=1
        )
        # Get the ID of the hospital with the minimum distance (this will be the one clicked)
        st.session_state.selected_hospital_id = unique_hospitals_df.loc[distances.idxmin()]['ID']

    # --- Display details only for the selected hospital ---
    if st.session_state.selected_hospital_id:
        selected_hospital_all_data = filtered_df[filtered_df['ID'] == st.session_state.selected_hospital_id]
        selected_hospital_details = selected_hospital_all_data.drop_duplicates(subset=['ID']).iloc[0]

        st.header(f"📊 Detailed Data for: {selected_hospital_details['Hospital Name']}")

        st.subheader("Revision Surgery Statistics (2020-2024)")
        col1, col2 = st.columns(2)
        col1.metric("Total Revision Surgeries", f"{selected_hospital_details['Revision Surgeries (N)']:.0f}")
        col2.metric("Revision Surgery Rate", f"{selected_hospital_details['Revision Surgeries (%)']:.1f}%")
        
        hospital_annual_data = selected_hospital_all_data.set_index('annee').sort_index(ascending=False)

        st.subheader("Bariatric Procedures by Year")
        bariatric_cols = ['ABL', 'ANN', 'BPG', 'REV', 'SLE']
        bariatric_df = hospital_annual_data[bariatric_cols]
        if not bariatric_df.empty and bariatric_df.sum().sum() > 0:
            st.bar_chart(bariatric_df)
            st.dataframe(bariatric_df)
        else:
            st.info("No bariatric procedure data available for this hospital.")

        st.subheader("Surgical Approaches by Year")
        approach_cols = ['COE', 'LAP', 'ROB']
        approach_df = hospital_annual_data[approach_cols]
        if not approach_df.empty and approach_df.sum().sum() > 0:
            st.bar_chart(approach_df)
            st.dataframe(approach_df)
        else:
            st.info("No surgical approach data available for this hospital.")

elif st.session_state.search_triggered:
    st.warning("No hospitals found matching your criteria. Try increasing the search radius or changing filters.")
else:
    st.info("Enter your address in the sidebar and click 'Search Hospitals' to begin.")
