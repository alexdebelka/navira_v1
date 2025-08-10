import streamlit as st
import pandas as pd
import folium
from folium.plugins import MarkerCluster
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
from streamlit_folium import st_folium
import altair as alt

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

# --- MAPPING DICTIONARIES ---
# CHANGE: Updated the Bariatric Procedure names as requested
BARIATRIC_PROCEDURE_NAMES = {
    'SLE': 'Sleeve Gastrectomy',
    'BPG': 'Gastric Bypass',
    'ANN': 'Band Removal',
    'REV': 'Other', # Was 'Revision Surgery'
    'ABL': 'Gastric Banding' # Kept for completeness
}

# CHANGE: Updated the Surgical Approach names
SURGICAL_APPROACH_NAMES = {
    'COE': 'Coelioscopy',
    'LAP': 'Open Surgery', # Was 'Laparoscopy'
    'ROB': 'Robotic'
}

# --- 3. Load and Prepare Data ---
@st.cache_data
def load_data(path="flattened_v3.csv"):
    """
    Loads and cleans the final FLAT denormalized hospital data with robust type conversion.
    """
    try:
        df = pd.read_csv(path)
        # Rename original columns for clarity
        df.rename(columns={
            'id': 'ID', 'rs': 'Hospital Name', 'statut': 'Status', 'ville': 'City',
            'revision_surgeries_n': 'Revision Surgeries (N)',
            'revision_surgeries_pct': 'Revision Surgeries (%)'
        }, inplace=True)

        # Define status mapping
        status_mapping = {
            'Privé non lucratif': 'private-non-profit',
            'Public': 'public',
            'Privé': 'private-for-profit'
        }
        df['Status'] = df['Status'].map(status_mapping)

        # Robustly convert all numeric columns
        numeric_cols = [
            'Revision Surgeries (N)', 'total_procedures_period', 'annee',
            'total_procedures_year', 'university', 'cso', 'LAB_SOFFCO',
            'latitude', 'longitude', 'Revision Surgeries (%)'
        ] + list(BARIATRIC_PROCEDURE_NAMES.keys()) + list(SURGICAL_APPROACH_NAMES.keys())

        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

        # Ensure text columns are strings
        for col in ['lib_dep', 'lib_reg']:
            if col in df.columns:
                df[col] = df[col].astype(str).fillna('N/A')

        df.drop_duplicates(subset=['ID', 'annee'], keep='first', inplace=True)
        df.dropna(subset=['latitude', 'longitude'], inplace=True)
        df = df[df['latitude'].between(-90, 90) & df['longitude'].between(-180, 180)]
        return df
    except FileNotFoundError:
        st.error(f"Fatal Error: The data file '{path}' was not found. Please make sure it's in the same directory as the script.")
        st.stop()
    except Exception as e:
        st.error(f"An error occurred while loading the data: {e}")
        st.stop()

df = load_data()

# --- 4. Main Page UI & Search Controls ---
st.title("🏥 Navira - French Hospital Explorer")
st.markdown("Find specialized hospitals based on your location and chosen criteria. Created in collaboration with Avicenne Hospital, Bobigny.")

_, center_col, _ = st.columns([1, 2, 1])
with center_col:
    with st.form(key="search_form"):
        address_input = st.text_input(
            "📍 Enter your address or postal code",
            value=st.session_state.address,
            placeholder="e.g., 75019 or Paris"
        )
        
        with st.expander("Advanced Filters"):
            # CHANGE: Radius slider max value reduced to 300km
            radius_km = st.slider("📏 Search Radius (km)", min_value=5, max_value=300, value=50, step=5)

            # CHANGE: Status filter updated to group public and non-profit
            st.markdown("**Establishment Type**")
            col1, col2 = st.columns(2)
            with col1:
                is_public_non_profit = st.checkbox("Public / Non-Profit", value=True)
            with col2:
                is_private_for_profit = st.checkbox("Private For-Profit", value=True)

            st.markdown("**Labels & Affiliations**")
            # CHANGE: Added new advanced filters for affiliations
            col3, col4, col5 = st.columns(3)
            with col3:
                is_university = st.checkbox("University Hospital")
            with col4:
                is_soffco = st.checkbox("SOFFCO Centre")
            with col5:
                is_health_ministry = st.checkbox("Health Ministry Centre")
        
        search_col, reset_col = st.columns(2)
        with search_col:
            submitted = st.form_submit_button("🔎 Search Hospitals", use_container_width=True)
        with reset_col:
            reset_clicked = st.form_submit_button("🔄 Reset", use_container_width=True)

        if submitted:
            if address_input:
                st.session_state.address = address_input
                st.session_state.search_triggered = True
                st.session_state.selected_hospital_id = None
            else:
                st.warning("Please enter an address first.")
                st.session_state.search_triggered = False
        
        if reset_clicked:
            st.session_state.search_triggered = False
            st.session_state.selected_hospital_id = None
            st.session_state.address = ""

st.markdown("---")

# --- 5. Geocoding and Filtering Logic ---
@st.cache_data(show_spinner="Geocoding address...")
def geocode_address(address):
    if not address: return None
    try:
        geolocator = Nominatim(user_agent="navira_streamlit_app_v24")
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

        # CHANGE: Apply new filter logic
        selected_statuses = []
        if is_public_non_profit:
            selected_statuses.extend(['public', 'private-non-profit'])
        if is_private_for_profit:
            selected_statuses.append('private-for-profit')
        temp_df = temp_df[temp_df['Status'].isin(selected_statuses)]

        if is_university:
            temp_df = temp_df[temp_df['university'] == 1]
        if is_soffco:
            temp_df = temp_df[temp_df['LAB_SOFFCO'] == 1]
        if is_health_ministry:
            temp_df = temp_df[temp_df['cso'] == 1]
        
        filtered_df = temp_df.sort_values('Distance (km)')
    else:
        if st.session_state.address:
            st.error("Address not found. Please try a different address or format (e.g., 'City, Postal Code').")
        st.session_state.search_triggered = False

# --- 6. Display Results ---
if st.session_state.search_triggered and not filtered_df.empty:
    unique_hospitals_df = filtered_df.drop_duplicates(subset=['ID']).copy()

    st.header(f"Found {len(unique_hospitals_df)} Hospitals")
    st.info("Click a hospital on the map to view its detailed statistics.")

    map_col, details_col = st.columns([6, 4])

    with map_col:
        st.subheader("🗺️ Map of Hospitals")

        # CHANGE: Map tile changed to 'CartoDB positron' for softer colors
        m = folium.Map(location=user_coords, zoom_start=9, tiles="CartoDB positron")

        folium.Marker(
            location=user_coords,
            popup="Your Location",
            icon=folium.Icon(icon="user", prefix="fa", color="red")
        ).add_to(m)

        marker_cluster = MarkerCluster().add_to(m)
        for idx, row in unique_hospitals_df.iterrows():
            # CHANGE: Added status to the popup for clarity
            popup_content = f"<b>{row['Hospital Name']}</b><br>City: {row['City']}<br>Status: {row['Status']}"
            
            # CHANGE: Icon color is now conditional
            color = "blue"
            if row['Status'] == 'private-non-profit':
                color = "lightblue"
            elif row['Status'] == 'private-for-profit':
                color = "green"

            folium.Marker(
                location=[row['latitude'], row['longitude']],
                popup=folium.Popup(popup_content, max_width=300),
                icon=folium.Icon(icon="hospital-o", prefix="fa", color=color)
            ).add_to(marker_cluster)

        map_data = st_folium(m, width="100%", height=500, key="folium_map")

        if map_data and map_data.get("last_object_clicked"):
            clicked_coords = (map_data["last_object_clicked"]["lat"], map_data["last_object_clicked"]["lng"])
            distances = unique_hospitals_df.apply(
                lambda row: geodesic(clicked_coords, (row['latitude'], row['longitude'])).km, axis=1
            )
            if distances.min() < 0.1:
                st.session_state.selected_hospital_id = unique_hospitals_df.loc[distances.idxmin()]['ID']

    with details_col:
        st.subheader("📊 Hospital Details")

        if not st.session_state.selected_hospital_id:
            st.info("Click a hospital marker on the map to see its data here.")
        else:
            if st.session_state.selected_hospital_id not in filtered_df['ID'].values:
                st.session_state.selected_hospital_id = None
                st.warning("The previously selected hospital is no longer in the filtered list.")
            else:
                selected_hospital_all_data = filtered_df[filtered_df['ID'] == st.session_state.selected_hospital_id]
                selected_hospital_details = selected_hospital_all_data.iloc[0]

                st.markdown(f"#### {selected_hospital_details['Hospital Name']}")
                st.markdown(f"**City:** {selected_hospital_details['City']}")
                st.markdown(f"**Status:** {selected_hospital_details['Status']}")
                st.markdown(f"**Distance:** {selected_hospital_details['Distance (km)']:.1f} km")
                st.markdown("---")
                
                # --- General & Revision Surgery Stats ---
                # CHANGE: Display total surgeries first, then revision surgeries
                st.markdown("**Surgery Statistics (2020-2024)**")
                total_proc = selected_hospital_details.get('total_procedures_period', 0)
                st.metric("Total Surgeries (All Types)", f"{total_proc:.0f}")
                st.metric("Total Revision Surgeries", f"{selected_hospital_details['Revision Surgeries (N)']:.0f}")

                st.markdown("---")

                # --- Labels & Affiliations ---
                st.markdown("**Labels & Affiliations**")
                if selected_hospital_details.get('university') == 1:
                    st.success("🎓 University Hospital (Academic Affiliation)")
                if selected_hospital_details.get('LAB_SOFFCO') == 1:
                    st.success("✅ Centre of Excellence (SOFFCO)")
                if selected_hospital_details.get('cso') == 1:
                    st.success("✅ Centre of Excellence (Health Ministry)")
                
                st.markdown("---")
                
                # Prepare annual data for charts
                hospital_annual_data = selected_hospital_all_data.set_index('annee').sort_index()

                # --- Bariatric Procedures Chart ---
                # CHANGE: Using Altair for more control (horizontal labels, better names)
                st.markdown("**Bariatric Procedures by Year**")
                bariatric_df = hospital_annual_data[list(BARIATRIC_PROCEDURE_NAMES.keys())].rename(columns=BARIATRIC_PROCEDURE_NAMES)
                bariatric_df_melted = bariatric_df.reset_index().melt('annee', var_name='Procedure', value_name='Count')
                
                if not bariatric_df_melted.empty and bariatric_df_melted['Count'].sum() > 0:
                    bariatric_chart = alt.Chart(bariatric_df_melted).mark_bar().encode(
                        x=alt.X('annee:O', title='Year', axis=alt.Axis(labelAngle=0)),
                        y=alt.Y('Count:Q', title='Number of Procedures'),
                        color='Procedure:N',
                        tooltip=['annee', 'Procedure', 'Count']
                    ).interactive()
                    st.altair_chart(bariatric_chart, use_container_width=True)
                else:
                    st.info("No bariatric procedure data available.")

                # --- Surgical Approaches Chart ---
                # CHANGE: Using Altair to add percentage labels
                st.markdown("**Surgical Approaches by Year**")
                approach_df = hospital_annual_data[list(SURGICAL_APPROACH_NAMES.keys())].rename(columns=SURGICAL_APPROACH_NAMES)
                approach_df_melted = approach_df.reset_index().melt('annee', var_name='Approach', value_name='Count')

                if not approach_df_melted.empty and approach_df_melted['Count'].sum() > 0:
                    # Calculate percentages
                    total_per_year = approach_df_melted.groupby('annee')['Count'].transform('sum')
                    approach_df_melted['Percentage'] = (approach_df_melted['Count'] / total_per_year * 100)

                    bar = alt.Chart(approach_df_melted).mark_bar().encode(
                        x=alt.X('annee:O', title='Year', axis=alt.Axis(labelAngle=0)),
                        y=alt.Y('Count:Q', title='Number of Surgeries'),
                        color='Approach:N',
                        tooltip=['annee', 'Approach', 'Count', alt.Tooltip('Percentage:Q', format='.1f')]
                    )
                    text = bar.mark_text(
                        align='center', baseline='bottom', dy=-4, color='black'
                    ).encode(
                        text=alt.Text('Percentage:Q', format='.1f', formatType='number')
                    )
                    st.altair_chart(bar + text, use_container_width=True)
                else:
                    st.info("No surgical approach data available.")


elif st.session_state.search_triggered:
    st.warning("No hospitals found matching your criteria. Try increasing the search radius or changing filters.")
