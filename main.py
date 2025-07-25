import streamlit as st
import pandas as pd
import folium
from folium.plugins import MarkerCluster
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
from streamlit_folium import st_folium

# --- 1. App Configuration ---
st.set_page_config(
    page_title="Navira - Where Care Finds Its Path",
    page_icon="🏥",
    layout="wide"
)

# --- 2. Session State Initialization ---
if "search_triggered" not in st.session_state:
    st.session_state["search_triggered"] = False
if "user_coords" not in st.session_state:
    st.session_state["user_coords"] = None

# --- 3. Load and Prepare Data ---
@st.cache_data
def load_data(path="flat_denormalized_data.csv"):
    """
    Loads the new FLAT denormalized hospital data.
    """
    try:
        df = pd.read_csv(path)
        df.rename(columns={
            'id': 'ID',
            'rs': 'Hospital Name',
            'statut': 'Status',
            'ville': 'City',
            'latitude': 'latitude',
            'longitude': 'longitude',
            'redo_n': 'Redo Surgeries (N)',
            'redo_pct': 'Redo Surgeries (%)'
        }, inplace=True)
        df['latitude'] = pd.to_numeric(df['latitude'], errors='coerce')
        df['longitude'] = pd.to_numeric(df['longitude'], errors='coerce')
        df.dropna(subset=['latitude', 'longitude'], inplace=True)
        return df
    except FileNotFoundError:
        st.error(f"Fatal Error: The data file '{path}' was not found. Please make sure it's in the same directory as the script.")
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
        st.session_state["search_triggered"] = True
        st.session_state["user_coords"] = None

    if st.button("🔄 Reset Search"):
        st.session_state["search_triggered"] = False
        st.session_state["user_coords"] = None
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
        geolocator = Nominatim(user_agent="navira_streamlit_app")
        enriched_address = address.strip()
        if enriched_address.isdigit() and len(enriched_address) == 5:
            enriched_address += ", France"
        location = geolocator.geocode(enriched_address, timeout=10)
        return (location.latitude, location.longitude) if location else None
    except Exception:
        return None

filtered_df = pd.DataFrame()
if st.session_state["search_triggered"]:
    if address:
        if not st.session_state["user_coords"]:
             st.session_state["user_coords"] = geocode_address(address)

        if st.session_state["user_coords"]:
            temp_df = df.copy()
            temp_df['Distance (km)'] = temp_df.apply(
                lambda row: geodesic(st.session_state["user_coords"], (row['latitude'], row['longitude'])).km,
                axis=1
            )
            temp_df = temp_df[temp_df['Distance (km)'] <= radius_km]
            if selected_status != 'All':
                temp_df = temp_df[temp_df['Status'] == selected_status]
            
            # Since the data is flat, we now have duplicates. We'll handle this for display.
            filtered_df = temp_df.sort_values('Distance (km)')
        else:
            st.error("Address not found. Please try a different address or format.")
    else:
        st.warning("Please enter an address to start a search.")
else:
    st.info("Enter your address in the sidebar and click 'Search Hospitals' to begin.")

# --- 7. Display Results ---
if not filtered_df.empty:
    # Create a new dataframe with unique hospitals for the map and main list
    unique_hospitals_df = filtered_df.drop_duplicates(subset=['ID']).copy()

    st.header(f"🗺️ Map of {len(unique_hospitals_df)} Found Hospitals")
    
    m = folium.Map(location=st.session_state["user_coords"], zoom_start=9)
    folium.Marker(
        location=st.session_state["user_coords"],
        popup="Your Location",
        icon=folium.Icon(icon="user", prefix="fa", color="red")
    ).add_to(m)
    marker_cluster = MarkerCluster().add_to(m)

    for idx, row in unique_hospitals_df.iterrows():
        popup_html = f"""
        <b>{row['Hospital Name']}</b><br>
        <b>City:</b> {row['City']}<br>
        <b>Status:</b> {row['Status']}<br>
        <b>Distance:</b> {row['Distance (km)']:.1f} km
        """
        folium.Marker(
            location=[row['latitude'], row['longitude']],
            popup=folium.Popup(popup_html, max_width=300),
            icon=folium.Icon(icon="hospital-o", prefix="fa", color="blue")
        ).add_to(marker_cluster)

    st_folium(m, width="100%", height=500, center=st.session_state["user_coords"], zoom=9)

    st.header("📋 Hospital Details")
    display_cols = ['Hospital Name', 'City', 'Status', 'Distance (km)', 'Redo Surgeries (N)', 'Redo Surgeries (%)']
    st.dataframe(unique_hospitals_df[display_cols].style.format({'Distance (km)': "{:.1f}", 'Redo Surgeries (%)': "{:.1f}"}))

    st.header("📊 Detailed Annual Procedure Data")
    hospital_to_view = st.selectbox(
        "Select a hospital to view its annual data",
        options=unique_hospitals_df['Hospital Name'].tolist()
    )

    if hospital_to_view:
        # Get all rows for the selected hospital from the ORIGINAL filtered dataframe
        hospital_annual_data = filtered_df[filtered_df['Hospital Name'] == hospital_to_view].copy()
        
        annual_cols = ['annee', 'ABL', 'ANN', 'BPG', 'REV', 'SLE', 'COE', 'LAP', 'ROB']
        display_annual = hospital_annual_data[annual_cols].rename(columns={'annee': 'Year'}).set_index('Year')
        
        st.table(display_annual)

elif st.session_state["search_triggered"]:
    st.warning("No hospitals found matching your criteria. Try increasing the search radius or changing filters.")
