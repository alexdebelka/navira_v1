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
# This helps manage the app's state, like whether a search has been performed.
if "search_triggered" not in st.session_state:
    st.session_state["search_triggered"] = False
if "user_coords" not in st.session_state:
    st.session_state["user_coords"] = None

# --- 3. Load and Prepare Data ---
@st.cache_data # Cache the data to avoid reloading on every interaction
def load_data(path="denormalized_data.csv"):
    """
    Loads the denormalized hospital data and performs basic cleaning.
    """
    try:
        df = pd.read_csv(path)
        # Rename columns for better readability in the UI
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
        # Ensure coordinates are numeric, dropping rows where they are invalid
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
    # Filter by hospital status (public/private)
    unique_statuses = ['All'] + sorted(df['Status'].dropna().unique().tolist())
    selected_status = st.selectbox("Filter by Hospital Status", unique_statuses)

    # Button to trigger the search
    if st.button("🔎 Search Hospitals"):
        st.session_state["search_triggered"] = True
        st.session_state["user_coords"] = None # Reset coords on new search

    # Button to reset the search
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
    """
    Converts a string address to geographic coordinates (latitude, longitude).
    Caches results to avoid repeated API calls for the same address.
    """
    if not address:
        return None
    try:
        geolocator = Nominatim(user_agent="navira_streamlit_app")
        # Handle French postal codes correctly
        enriched_address = address.strip()
        if enriched_address.isdigit() and len(enriched_address) == 5:
            enriched_address += ", France"
        
        location = geolocator.geocode(enriched_address, timeout=10)
        return (location.latitude, location.longitude) if location else None
    except Exception:
        return None

# Perform search only when the button is pressed and an address is provided
if st.session_state["search_triggered"]:
    if address:
        if not st.session_state["user_coords"]:
             st.session_state["user_coords"] = geocode_address(address)

        if st.session_state["user_coords"]:
            # Filter the main dataframe based on distance and sidebar filters
            filtered_df = df.copy()
            
            # Calculate distance from user
            filtered_df['Distance (km)'] = filtered_df.apply(
                lambda row: geodesic(st.session_state["user_coords"], (row['latitude'], row['longitude'])).km,
                axis=1
            )
            # Apply filters
            filtered_df = filtered_df[filtered_df['Distance (km)'] <= radius_km]
            if selected_status != 'All':
                filtered_df = filtered_df[filtered_df['Status'] == selected_status]

            filtered_df = filtered_df.sort_values('Distance (km)')

        else:
            st.error("Address not found. Please try a different address or format (e.g., 'City, Country').")
            filtered_df = pd.DataFrame()
    else:
        st.warning("Please enter an address to start a search.")
        filtered_df = pd.DataFrame()
else:
    # Default view before search
    st.info("Enter your address in the sidebar and click 'Search Hospitals' to begin.")
    filtered_df = pd.DataFrame()


# --- 7. Display Results ---
if not filtered_df.empty:
    st.header(f"🗺️ Map of {len(filtered_df)} Found Hospitals")
    
    # Create the map centered on the user's location
    m = folium.Map(location=st.session_state["user_coords"], zoom_start=9)
    
    # Add a marker for the user's location
    folium.Marker(
        location=st.session_state["user_coords"],
        popup="Your Location",
        icon=folium.Icon(icon="user", prefix="fa", color="red")
    ).add_to(m)

    # Use MarkerCluster for performance with many points
    marker_cluster = MarkerCluster().add_to(m)

    # Add a marker for each hospital
    for idx, row in filtered_df.iterrows():
        popup_html = f"""
        <b>{row['Hospital Name']}</b><br>
        <b>City:</b> {row['City']}<br>
        <b>Status:</b> {row['Status']}<br>
        <b>Distance:</b> {row['Distance (km)']:.1f} km<br>
        <b>Redo Surgeries:</b> {row['Redo Surgeries (N)']} ({row['Redo Surgeries (%)']:.1f}%)
        """
        folium.Marker(
            location=[row['latitude'], row['longitude']],
            popup=folium.Popup(popup_html, max_width=300),
            icon=folium.Icon(icon="hospital-o", prefix="fa", color="blue")
        ).add_to(marker_cluster)

    # Display the map in Streamlit
    st_folium(m, width="100%", height=500, center=st.session_state["user_coords"], zoom=9)

    # --- Display Data Table ---
    st.header("📋 Hospital Details")
    display_cols = ['Hospital Name', 'City', 'Status', 'Distance (km)', 'Redo Surgeries (N)', 'Redo Surgeries (%)']
    st.dataframe(filtered_df[display_cols].style.format({'Distance (km)': "{:.1f}", 'Redo Surgeries (%)': "{:.1f}"}))

    # --- Display Detailed Annual Stats ---
    st.header("📊 Detailed Annual Procedure Data")
    hospital_to_view = st.selectbox(
        "Select a hospital to view its annual data",
        options=filtered_df['Hospital Name'].tolist()
    )

    if hospital_to_view:
        # Get the selected hospital's data
        hospital_data = filtered_df[filtered_df['Hospital Name'] == hospital_to_view].iloc[0]
        
        # Find all columns related to yearly data
        yearly_cols = [col for col in df.columns if 'yearly_data' in col]
        
        # Extract and clean up the yearly data for display
        annual_stats = hospital_data[yearly_cols].dropna()
        if not annual_stats.empty:
            # Reshape the data for better viewing
            annual_df = pd.DataFrame([annual_stats.to_dict()])
            # Rename columns by removing the prefix
            annual_df.columns = [c.replace('yearly_data.', '').capitalize() for c in annual_df.columns]
            st.table(annual_df.set_index('Annee'))
        else:
            st.info(f"No detailed annual data available for {hospital_to_view}.")

elif st.session_state["search_triggered"]:
    st.warning("No hospitals found matching your criteria. Try increasing the search radius or changing filters.")

