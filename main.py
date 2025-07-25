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
    st.session_state["search_triggered"] = False
if "user_coords" not in st.session_state:
    st.session_state["user_coords"] = None

# --- 3. Load and Prepare Data ---
@st.cache_data
def load_data(path="flattened_denormalized_v2.csv"): # <-- Make sure this matches the name of your new CSV file
    """
    Loads the final FLAT denormalized hospital data with pre-calculated totals.
    """
    try:
        df = pd.read_csv(path)
        # Rename columns to be more user-friendly
        df.rename(columns={
            'id': 'ID',
            'rs': 'Hospital Name',
            'statut': 'Status',
            'ville': 'City',
            'latitude': 'latitude',
            'longitude': 'longitude',
            'revision_surgeries_n': 'Revision Surgeries (N)',
            'revision_surgeries_pct': 'Revision Surgeries (%)'
        }, inplace=True)

        # Robustly clean coordinate data
        df['latitude'] = pd.to_numeric(df['latitude'], errors='coerce')
        df['longitude'] = pd.to_numeric(df['longitude'], errors='coerce')
        df.dropna(subset=['latitude', 'longitude'], inplace=True)
        df = df[df['latitude'].between(-90, 90)]
        df = df[df['longitude'].between(-180, 180)]
        
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
            
            filtered_df = temp_df.sort_values('Distance (km)')
        else:
            st.error("Address not found. Please try a different address or format.")
    else:
        st.warning("Please enter an address to start a search.")
else:
    st.info("Enter your address in the sidebar and click 'Search Hospitals' to begin.")

# --- 7. Display Results ---
if not filtered_df.empty:
    unique_hospitals_df = filtered_df.drop_duplicates(subset=['ID']).copy()

    data_2024 = filtered_df[filtered_df['annee'] == 2024].drop_duplicates(subset=['ID'])
    total_2024 = data_2024.set_index('ID')['total_procedures_year']
    unique_hospitals_df['Total Procedures (2024)'] = unique_hospitals_df['ID'].map(total_2024).fillna(0).astype(int)
    unique_hospitals_df.rename(columns={'total_procedures_period': 'Total Procedures (2020-2024)'}, inplace=True)

    st.header(f"🗺️ Map of {len(unique_hospitals_df)} Found Hospitals")
    
    m = folium.Map(location=st.session_state["user_coords"], zoom_start=9)
    folium.Marker(
        location=st.session_state["user_coords"], popup="Your Location",
        icon=folium.Icon(icon="user", prefix="fa", color="red")
    ).add_to(m)
    marker_cluster = MarkerCluster().add_to(m)

    for idx, row in unique_hospitals_df.iterrows():
        popup_html = f"<b>{row['Hospital Name']}</b><br><b>City:</b> {row['City']}<br><b>Status:</b> {row['Status']}<br><b>Distance:</b> {row['Distance (km)']:.1f} km"
        folium.Marker(
            location=[row['latitude'], row['longitude']],
            popup=folium.Popup(popup_html, max_width=300),
            icon=folium.Icon(icon="hospital-o", prefix="fa", color="blue")
        ).add_to(marker_cluster)
    st_folium(m, width="100%", height=500, center=st.session_state["user_coords"], zoom=9)

    st.header("📋 Hospital Details")
    display_cols = ['Hospital Name', 'City', 'Status', 'Distance (km)', 'Total Procedures (2024)', 'Total Procedures (2020-2024)']
    
    st.dataframe(
        unique_hospitals_df[display_cols], 
        hide_index=True
    )

    st.header("📊 Detailed Annual Procedure Data")
    hospital_to_view = st.selectbox(
        "Select a hospital to view its annual data",
        options=unique_hospitals_df['Hospital Name'].tolist()
    )

    if hospital_to_view:
        selected_hospital_details = unique_hospitals_df[unique_hospitals_df['Hospital Name'] == hospital_to_view].iloc[0]
        
        st.subheader("Revision Surgery Statistics (2020-2024)")
        col1, col2 = st.columns(2)
        col1.metric("Total Revision Surgeries", f"{selected_hospital_details['Revision Surgeries (N)']:.0f}")
        col2.metric("Revision Surgery Rate", f"{selected_hospital_details['Revision Surgeries (%)']:.1f}%")
        
        # --- NEW VISUALIZATION SECTION ---
        # Prepare the data for the selected hospital
        hospital_annual_data = filtered_df[filtered_df['Hospital Name'] == hospital_to_view].copy()
        hospital_annual_data.set_index('annee', inplace=True)
        hospital_annual_data.sort_index(ascending=False, inplace=True)

        # 1. Bariatric Procedures Chart
        st.subheader("Bariatric Procedures by Year")
        bariatric_cols = ['ABL', 'ANN', 'BPG', 'REV', 'SLE']
        bariatric_df = hospital_annual_data[bariatric_cols]
        
        if not bariatric_df.empty and bariatric_df.sum().sum() > 0:
            st.bar_chart(bariatric_df)
        else:
            st.info("No bariatric procedure data available for this hospital.")

        # 2. Surgical Approaches Chart
        st.subheader("Surgical Approaches by Year")
        approach_cols = ['COE', 'LAP', 'ROB']
        approach_df = hospital_annual_data[approach_cols]
        
        if not approach_df.empty and approach_df.sum().sum() > 0:
            st.bar_chart(approach_df)
        else:
            st.info("No surgical approach data available for this hospital.")
        # --- END OF NEW VISUALIZATION SECTION ---

elif st.session_state["search_triggered"]:
    st.warning("No hospitals found matching your criteria. Try increasing the search radius or changing filters.")
