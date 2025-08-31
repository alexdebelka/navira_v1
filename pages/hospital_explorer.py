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
    # Keep an unfiltered copy of establishments for cross-referencing flows
    establishments_full = all_data.get('establishments', establishments)
    
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
    
    # Helper to find nearest city with data from given coordinates (reusable)
    def _find_nearest_city_with_data(coords, cities_with_data, max_distance_km=50):
        if not coords or cities_with_data.empty:
            return None
        distances = cities_with_data.apply(
            lambda row: geodesic(coords, (row['latitude'], row['longitude'])).km, 
            axis=1
        )
        min_distance_idx = distances.idxmin()
        min_distance = distances[min_distance_idx]
        for threshold in (max_distance_km, 100, 150, 200):
            if min_distance <= threshold:
                return cities_with_data.loc[min_distance_idx], min_distance
        return None

    # Extract a 5-digit postal code from a freeform address
    def _extract_postal_code(address: str | None) -> str | None:
        try:
            if not address:
                return None
            import re
            m = re.search(r"\b\d{5}\b", str(address))
            return m.group(0) if m else None
        except Exception:
            return None

    @st.cache_data(show_spinner=False)
    def _reverse_postal_from_coords(coords):
        try:
            if not coords:
                return None
            geolocator = Nominatim(user_agent="navira_streamlit_app_v26")
            location = geolocator.reverse(coords, timeout=10, language='en')
            if location and isinstance(location.raw, dict):
                addr = location.raw.get('address', {})
                pc = addr.get('postcode')
                return str(pc) if pc else None
        except Exception:
            return None
        return None

    def _choose_city_for_address(coords, address_text, cities_with_data, max_distance_km):
        """Prefer exact postal code match (from address or reverse geocode). Otherwise pick nearest within tightening thresholds."""
        if cities_with_data.empty:
            return None
        postal = _extract_postal_code(address_text)
        if not postal:
            postal = _reverse_postal_from_coords(coords)
        # Try exact postal code
        if postal and 'postal_code' in cities_with_data.columns:
            same_pc = cities_with_data[cities_with_data['postal_code'] == str(postal)]
            if not same_pc.empty:
                chosen = _find_nearest_city_with_data(coords, same_pc, max_distance_km=max_distance_km)
                if chosen:
                    return chosen
        # Try progressively closer distances to ensure actual closeness
        for threshold in (10, 20, 30, 50, 100, 150, 200):
            chosen = _find_nearest_city_with_data(coords, cities_with_data, max_distance_km=threshold)
            if chosen:
                return chosen
        return None
            
    if st.session_state.get('search_triggered', False):
        user_coords = geocode_address(st.session_state.address)
        if user_coords:
            # Persist user coordinates for neighbor flow visualization
            st.session_state.user_address_coords = user_coords
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
            # Auto-select neighbor flow city from main search
            try:
                available_cities = recruitment_zones['city_code'].unique()
                cities_with_names = cities[cities['city_code'].isin(available_cities)]
                cities_with_names = cities_with_names[cities_with_names['city_name'].notna()]
                chosen = _choose_city_for_address(user_coords, st.session_state.address, cities_with_names, max_distance_km=radius_km)
                if chosen:
                    nearest_city, nf_distance = chosen
                    st.session_state.neighbor_flow_city_code = nearest_city['city_code']
                    st.session_state.neighbor_flow_city_name = nearest_city['city_name']
            except Exception:
                pass
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
    
    # --- Function to show where neighbors go ---
    def add_neighbor_flow_to_map(folium_map, origin_city_code, recruitment_df, cities_df, establishments_df, user_address_coords=None, distance_limit_km=None):
        """Show where patients from a specific neighborhood go to hospitals"""
        if recruitment_df.empty or cities_df.empty:
            st.warning("No recruitment or cities data available")
            return
            
        # Get all recruitment data for the origin city
        origin_recruitment = recruitment_df[recruitment_df['city_code'] == str(origin_city_code)]
        
        if origin_recruitment.empty:
            st.warning(f"No patient flow data found for city code: {origin_city_code}")
            return
            
        # Get origin city coordinates
        origin_city = cities_df[cities_df['city_code'] == str(origin_city_code)]
        if origin_city.empty:
            st.warning(f"City coordinates not found for city code: {origin_city_code}")
            return
            
        origin_lat = origin_city['latitude'].iloc[0]
        origin_lon = origin_city['longitude'].iloc[0]
        origin_name = origin_city['city_name'].iloc[0]
        
        # If user provided their address coordinates, show the connection
        if user_address_coords:
            user_lat, user_lon = user_address_coords
            
            # Add user's address marker (red point)
            folium.Marker(
                location=[user_lat, user_lon],
                popup=f"<b>Your Address</b><br>Nearest city with data: {origin_name}",
                icon=folium.Icon(icon="user", prefix="fa", color="red")
            ).add_to(folium_map)
            
            # Add connection line from user's address to the nearest city with data
            folium.PolyLine(
                locations=[[user_lat, user_lon], [origin_lat, origin_lon]],
                weight=3,
                color='red',
                opacity=0.7,
                popup=f"<b>Connection</b><br>Your address → {origin_name}<br>Distance: {geodesic((user_lat, user_lon), (origin_lat, origin_lon)).km:.1f} km"
            ).add_to(folium_map)
            
            # Add a small info circle at the midpoint
            mid_lat = (user_lat + origin_lat) / 2
            mid_lon = (user_lon + origin_lon) / 2
            folium.Circle(
                location=[mid_lat, mid_lon],
                radius=2000,
                popup=f"<b>Nearest City with Data</b><br>{origin_name}<br>Patient flow data available here",
                color='orange',
                fillColor='orange',
                opacity=0.3,
                fillOpacity=0.2
            ).add_to(folium_map)
        
        # Add origin marker with blue shading (more prominent like in the image)
        folium.Circle(
            location=[origin_lat, origin_lon],
            radius=3000,  # 3km radius for origin area (more visible)
            popup=f"<b>Origin: {origin_name}</b><br>Patients from this area",
            color='blue',
            fillColor='blue',
            opacity=0.4,
            fillOpacity=0.3
        ).add_to(folium_map)
        
        # Add a smaller, darker center point for better visibility
        folium.Circle(
            location=[origin_lat, origin_lon],
            radius=500,  # 500m radius for center point
            popup=f"<b>Origin: {origin_name}</b><br>Patients from this area",
            color='darkblue',
            fillColor='darkblue',
            opacity=0.8,
            fillOpacity=0.6
        ).add_to(folium_map)
        
        # Get destination hospitals and their coordinates
        destination_hospitals = origin_recruitment.merge(
            establishments_df[['id', 'name', 'latitude', 'longitude']], 
            left_on='hospital_id', 
            right_on='id', 
            how='left'
        )
        
        # Filter out rows without coordinates and invalid coordinates
        destination_hospitals = destination_hospitals.dropna(subset=['latitude', 'longitude'])
        destination_hospitals = destination_hospitals[
            (destination_hospitals['latitude'] != 0) & 
            (destination_hospitals['longitude'] != 0) &
            (destination_hospitals['latitude'].between(-90, 90)) & 
            (destination_hospitals['longitude'].between(-180, 180))
        ]
        
        if destination_hospitals.empty:
            st.warning("No destination hospitals found with valid coordinates")
            return
            
        # If we know the user's location, compute distances and prefer closest destinations
        if user_address_coords:
            destination_hospitals['distance_km'] = destination_hospitals.apply(
                lambda r: geodesic(user_address_coords, (r['latitude'], r['longitude'])).km, axis=1
            )
            if distance_limit_km is not None:
                destination_hospitals = destination_hospitals[destination_hospitals['distance_km'] <= float(distance_limit_km)]
            if not destination_hospitals.empty:
                destination_hospitals = destination_hospitals.sort_values('distance_km', ascending=True)
        else:
            # Fall back to patient popularity when no user location
            destination_hospitals = destination_hospitals.sort_values('patient_count', ascending=False)
        
        # Debug: Show what we're about to visualize
        st.success(f"Creating {len(destination_hospitals)} patient flow arrows from {origin_name}")
        
        # Add flow lines to hospitals
        max_patients = destination_hospitals['patient_count'].max()
        min_patients = destination_hospitals['patient_count'].min()
        
        for _, dest in destination_hospitals.iterrows():
            # Calculate line width based on patient count
            if max_patients > min_patients:
                normalized_width = (dest['patient_count'] - min_patients) / (max_patients - min_patients)
            else:
                normalized_width = 0.5
            line_width = 2 + (normalized_width * 8)  # 2 to 10 pixels
            
            # Calculate opacity based on percentage
            opacity = min(0.8, dest['percentage'] / 100 * 2)  # Cap at 0.8 opacity
            
            # Create flow line from origin to hospital with arrowheads
            # Note: Folium doesn't support arrow_style, arrow_size, arrow_color parameters
            # We'll use a regular PolyLine with thicker weight to make it more visible
            start_lat = user_address_coords[0] if user_address_coords else origin_lat
            start_lon = user_address_coords[1] if user_address_coords else origin_lon
            folium.PolyLine(
                locations=[[start_lat, start_lon], [dest['latitude'], dest['longitude']]],
                weight=line_width,
                color='blue',
                opacity=opacity,
                popup=f"<b>{dest['name']}</b><br>Patients: {dest['patient_count']}<br>Percentage: {dest['percentage']:.1f}%"
            ).add_to(folium_map)
            
            # Add a small arrow marker at the end to show direction
            # Calculate a point near the destination to place the arrow
            import math
            lat1, lon1 = (user_address_coords if user_address_coords else (origin_lat, origin_lon))
            lat2, lon2 = dest['latitude'], dest['longitude']
            
            # Calculate midpoint for arrow placement (80% towards destination)
            arrow_lat = lat1 + 0.8 * (lat2 - lat1)
            arrow_lon = lon1 + 0.8 * (lon2 - lon1)
            
            # Calculate angle for arrow direction
            angle = math.atan2(lat2 - lat1, lon2 - lon1) * 180 / math.pi
            
            # Add arrow marker
            folium.RegularPolygonMarker(
                location=[arrow_lat, arrow_lon],
                number_of_sides=3,
                radius=8,
                rotation=angle,
                color='blue',
                fill_color='blue',
                fill_opacity=opacity,
                popup=f"→ {dest['name']}"
            ).add_to(folium_map)
            
            # Add destination marker to show patient concentration
            folium.Circle(
                location=[dest['latitude'], dest['longitude']],
                radius=400 + (normalized_width * 800),  # 400m to 1200m radius (more visible)
                popup=f"<b>{dest['name']}</b><br>Patients from {origin_name}: {dest['patient_count']}<br>Percentage: {dest['percentage']:.1f}%",
                color='blue',
                fillColor='blue',
                opacity=0.7,
                fillOpacity=opacity * 0.6
            ).add_to(folium_map)
            
            # Add hospital name label
            folium.Tooltip(
                f"{dest['name']}<br>{dest['patient_count']} patients",
                permanent=False
            ).add_to(folium.Circle(
                location=[dest['latitude'], dest['longitude']],
                radius=1,  # Invisible circle just for the tooltip
                color='transparent',
                fillColor='transparent'
            ).add_to(folium_map))
    
    # --- Display Results: Map and List ---
    if st.session_state.get('search_triggered', False) and not st.session_state.filtered_df.empty:
        unique_hospitals_df = st.session_state.filtered_df.drop_duplicates(subset=['id']).copy()
        st.header(f"Found {len(unique_hospitals_df)} Hospitals")
        
        # Add visualization options
        st.markdown("#### 🗺️ Map Visualization Options")
        
        # Create tabs for different visualization modes
        viz_tab1, viz_tab2 = st.tabs(["🏥 Hospital Recruitment Zones", "👥 Where My Neighbors Go"])
        
        with viz_tab1:
            show_recruitment = st.toggle("Show Patient Recruitment Zones", value=False)
            if show_recruitment:
                selected_hospital_for_recruitment = st.selectbox(
                    "Select hospital to show recruitment zones:",
                    options=unique_hospitals_df['id'].tolist(),
                    format_func=lambda x: unique_hospitals_df[unique_hospitals_df['id']==x]['name'].iloc[0] if not unique_hospitals_df[unique_hospitals_df['id']==x].empty else x,
                    key="recruitment_hospital_selector"
                )
        
        with viz_tab2:
            show_neighbor_flow = st.toggle("Show Where My Neighbors Go", value=False)
            if show_neighbor_flow:
                st.markdown("**Enter your address or search for your neighborhood to see where patients from your area go for treatment:**")
                
                # Get available cities from recruitment data that have city information
                available_cities = recruitment_zones['city_code'].unique()
                cities_with_names = cities[cities['city_code'].isin(available_cities)]
                
                # Filter out cities without names (shouldn't happen but just in case)
                cities_with_names = cities_with_names[cities_with_names['city_name'].notna()]
                
                if not cities_with_names.empty:
                    # Unified search system
                    search_method = st.radio(
                        "Choose search method:",
                        ["Use Main Search Address", "🔍 Manual City Search"],
                        horizontal=True,
                        key="search_method"
                    )
                    
                    selected_city_code = None
                    selected_city_name = None
                    
                    if search_method == "Use Main Search Address":
                        # Reuse address from main search; no extra input field
                        address_input = st.session_state.address
                    elif search_method == "🔍 Manual City Search":
                        address_input = None
                    
                    # Use helpers defined above: geocode_address and _find_nearest_city_with_data
                    
                    # Process address input
                    if search_method == "Use Main Search Address":
                        if not st.session_state.address:
                            st.warning("Use the main search bar first to enter your address.")
                        else:
                            # Reuse cached coords or geocode once
                            user_coords = st.session_state.get('user_address_coords')
                            if not user_coords:
                                user_coords = geocode_address(st.session_state.address)
                                if user_coords:
                                    st.session_state.user_address_coords = user_coords
                            if user_coords:
                                nearest_city_data = _choose_city_for_address(user_coords, st.session_state.address, cities_with_names, max_distance_km=radius_km)
                                if nearest_city_data:
                                    nearest_city, distance = nearest_city_data
                                    selected_city_code = nearest_city['city_code']
                                    selected_city_name = nearest_city['city_name']
                                    st.session_state.neighbor_flow_city_code = selected_city_code
                                    st.session_state.neighbor_flow_city_name = selected_city_name
                                    st.success(f"Using your main address ({st.session_state.address}). Nearest city with data: {selected_city_name} ({distance:.1f} km)")
                                else:
                                    st.warning("No nearby cities with patient flow data found. Switch to Manual City Search.")
                    
                    elif search_method == "🔍 Manual City Search":
                        # Manual city selection
                        st.markdown("**🔍 Search for a specific city:**")
                    
                    # Add search functionality
                    search_term = st.text_input(
                        "🔍 Search for your city:",
                        placeholder="Type part of your city name...",
                        key="city_search"
                    )
                    
                    # Filter cities based on search
                    if search_term:
                        # First, try exact matches
                        exact_matches = cities_with_names[
                            cities_with_names['city_name'].str.lower() == search_term.lower()
                        ]
                        
                        # Then, try starts with matches
                        starts_with_matches = cities_with_names[
                            cities_with_names['city_name'].str.lower().str.startswith(search_term.lower())
                        ]
                        
                        # Finally, try contains matches
                        contains_matches = cities_with_names[
                            cities_with_names['city_name'].str.contains(search_term, case=False, na=False)
                        ]
                        
                        # Combine and prioritize: exact matches first, then starts with, then contains
                        filtered_cities = pd.concat([exact_matches, starts_with_matches, contains_matches]).drop_duplicates()
                        
                        if not filtered_cities.empty:
                            # Auto-select the best match (first one after prioritization)
                            best_match = filtered_cities.iloc[0]
                            selected_city_code = best_match['city_code']
                            selected_city_name = best_match['city_name']
                            
                            # Store in session state for map rendering
                            st.session_state.neighbor_flow_city_code = selected_city_code
                            st.session_state.neighbor_flow_city_name = selected_city_name
                            
                            # Show what was auto-selected
                            st.success(f"""
                            **📍 Auto-selected: {selected_city_name}**
                            - **Postal code**: {best_match['postal_code']}
                            - **City code**: {selected_city_code}
                            - **Other matches**: {len(filtered_cities)} cities found
                            """)
                            
                            # If there are multiple matches, show them for reference
                            if len(filtered_cities) > 1:
                                with st.expander(f"🔍 See all {len(filtered_cities)} matching cities"):
                                    for idx, city in filtered_cities.head(10).iterrows():
                                        st.markdown(f"• **{city['city_name']}** ({city['postal_code']}) - {city['city_code']}")
                                    if len(filtered_cities) > 10:
                                        st.markdown(f"... and {len(filtered_cities) - 10} more")
                        else:
                            st.warning(f"No cities found matching '{search_term}'. Try a different search term.")
                            selected_city_code = None
                            selected_city_name = None
                    else:
                        # No search term entered
                        selected_city_code = None
                        selected_city_name = None
                            
                    # Unified display section - show selected city info regardless of search method
                    if selected_city_code and selected_city_name:
                        st.markdown("---")
                        st.markdown("**📊 Selected Region Information:**")
                        
                        # Get flow data for the selected city
                        city_flow = recruitment_zones[recruitment_zones['city_code'] == selected_city_code]
                        if not city_flow.empty:
                            total_patients = city_flow['patient_count'].sum()
                            unique_hospitals = len(city_flow)
                            
                            col1, col2, col3 = st.columns(3)
                            with col1:
                                st.metric("Selected City", selected_city_name)
                            with col2:
                                st.metric("Total Patients", f"{total_patients:,}")
                            with col3:
                                st.metric("Destination Hospitals", unique_hospitals)
                            
                            # Show top destinations in a more detailed format
                            st.markdown("**🏥 Top Destination Hospitals:**")
                            top_hospitals = city_flow.nlargest(5, 'patient_count')
                            
                            for idx, row in top_hospitals.iterrows():
                                hospital_data = establishments_full[establishments_full['id'] == row['hospital_id']]
                                if not hospital_data.empty:
                                    hospital_name = hospital_data['name'].iloc[0]
                                    hospital_city = hospital_data['ville'].iloc[0]
                                    
                                    col1, col2, col3 = st.columns([3, 2, 1])
                                    with col1:
                                        st.markdown(f"**{hospital_name}**")
                                        st.caption(f"📍 {hospital_city}")
                                    with col2:
                                        st.metric("Patients", f"{row['patient_count']:,}")
                                    with col3:
                                        percentage = row.get('percentage', 0)
                                        st.metric("Share", f"{percentage:.1f}%")
                                    
                                    st.markdown("---")
                        else:
                            st.warning(f"No patient flow data available for {selected_city_name}.")
                    else:
                        if search_term:
                            st.warning(f"No cities found matching '{search_term}'. Try a different search term.")
                        else:
                            st.warning("No cities available for selection.")
                    
                    # Show help information
                    with st.expander("ℹ️ How to use this feature"):
                        st.markdown(f"""
                        **This feature shows where patients from your neighborhood go for bariatric surgery treatment.**
                        
                        **Available data:**
                        - 📊 **{len(cities_with_names)} cities** with patient flow data available
                        - 🏥 **{len(recruitment_zones['hospital_id'].unique())} hospitals** receiving patients
                        - 👥 **{recruitment_zones['patient_count'].sum():,} total patient movements** recorded
                        
                        **How it works:**
                        1. **Search for your city** using the search box above
                        2. **Auto-selection** of the best matching neighborhood
                        3. **View the map** showing patient flow lines to hospitals
                        4. **Explore the analysis** below the map for detailed insights
                        
                        **What you'll see:**
                        - 🔵 **Blue shaded area**: Your neighborhood (origin)
                        - 🔵 **Blue lines**: Patient flow paths to hospitals
                        - 🔵 **Blue circles**: Patient concentration at destination hospitals
                        
                        **Note**: Only cities with recorded patient flow data are available. If your city isn't listed, it may not have sufficient patient data in the system.
                        """)
                else:
                    st.error("No city data available for neighbor flow visualization. Please check your data files.")
        
        # Filter out hospitals without valid coordinates
        hospitals_with_coords = unique_hospitals_df.dropna(subset=['latitude', 'longitude'])
        hospitals_with_coords = hospitals_with_coords[
            (hospitals_with_coords['latitude'] != 0) & 
            (hospitals_with_coords['longitude'] != 0) &
            (hospitals_with_coords['latitude'].between(-90, 90)) & 
            (hospitals_with_coords['longitude'].between(-180, 180))
        ]
        
        if hospitals_with_coords.empty:
            st.error("No hospitals with valid coordinates found. Please check your data.")
            st.stop()
        
        # Use the first hospital with valid coordinates as map center if user coords are invalid
        if user_coords and all(pd.notna(coord) for coord in user_coords):
            map_center = user_coords
        else:
            map_center = [hospitals_with_coords['latitude'].iloc[0], hospitals_with_coords['longitude'].iloc[0]]
        
        m = folium.Map(location=map_center, zoom_start=9, tiles="CartoDB positron")
        
        # Add user location marker if coordinates are valid
        if user_coords and all(pd.notna(coord) for coord in user_coords):
            folium.Marker(location=user_coords, popup="Your Location", icon=folium.Icon(icon="user", prefix="fa", color="red")).add_to(m)
        
        marker_cluster = MarkerCluster().add_to(m)
        
        for idx, row in hospitals_with_coords.iterrows():
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
        
        # Add neighbor flow if toggled on
        if show_neighbor_flow and st.session_state.get('neighbor_flow_city_code'):
            try:
                city_code_to_use = st.session_state.neighbor_flow_city_code
                
                # Debug: Show what city we're trying to visualize
                city_info = cities[cities['city_code'] == city_code_to_use]
                if not city_info.empty:
                    st.info(f"Visualizing patient flow from: {city_info['city_name'].iloc[0]} ({city_code_to_use})")
                
                # Get user coordinates if available
                user_coords = st.session_state.get('user_address_coords')
                
                add_neighbor_flow_to_map(m, city_code_to_use, recruitment_zones, cities, establishments_full, user_coords, distance_limit_km=radius_km)
                
                # Add legend for the neighbor flow visualization
                legend_html = '''
                <div style="position: fixed; 
                            bottom: 50px; left: 50px; width: 220px; height: 160px; 
                            background-color: rgba(255, 255, 255, 0.9); border:2px solid #333; z-index:9999; 
                            font-size:14px; padding: 10px; border-radius: 5px; box-shadow: 0 2px 10px rgba(0,0,0,0.3)">
                <p style="margin: 0 0 8px 0; font-weight: bold; color: #333; border-bottom: 1px solid #ccc; padding-bottom: 5px;">Patient Flow Legend</p>
                <p style="margin: 5px 0; color: #333;"><span style="color: red; font-size: 16px;">📍</span> Your address</p>
                <p style="margin: 5px 0; color: #333;"><span style="color: red; font-size: 16px;">—</span> Connection to nearest city</p>
                <p style="margin: 5px 0; color: #333;"><span style="color: blue; font-size: 16px;">●</span> Origin area (with data)</p>
                <p style="margin: 5px 0; color: #333;"><span style="color: blue; font-size: 16px;">→</span> Patient flow (thicker = more patients)</p>
                <p style="margin: 5px 0; color: #333;"><span style="color: blue; font-size: 16px;">●</span> Destination hospitals</p>
                </div>
                '''
                m.get_root().html.add_child(folium.Element(legend_html))
                
            except Exception as e:
                st.error(f"Error displaying neighbor flow: {e}")
                st.info("Please try selecting a different city or check if the data is available.")
            
        map_data = st_folium(m, width="100%", height=500, key="folium_map")
        if map_data and map_data.get("last_object_clicked"):
            clicked_coords = (map_data["last_object_clicked"]["lat"], map_data["last_object_clicked"]["lng"])
            distances = unique_hospitals_df.apply(lambda row: geodesic(clicked_coords, (row['latitude'], row['longitude'])).km, axis=1)
            if distances.min() < 0.1:
                st.session_state.selected_hospital_id = unique_hospitals_df.loc[distances.idxmin()]['id']
                st.switch_page("pages/dashboard.py")
        
        # Show detailed neighbor flow analysis if enabled
        if show_neighbor_flow and st.session_state.get('neighbor_flow_city_code'):
            st.markdown("---")
            st.markdown("#### 📊 Detailed Neighbor Flow Analysis")
            
            # Get flow data for selected city
            city_flow = recruitment_zones[recruitment_zones['city_code'] == st.session_state.neighbor_flow_city_code]
            if not city_flow.empty:
                # Merge with hospital and city data for display
                flow_with_details = city_flow.merge(
                    establishments_full[['id', 'name', 'ville', 'statut']], 
                    left_on='hospital_id', 
                    right_on='id', 
                    how='left'
                ).merge(
                    cities[['city_code', 'city_name']], 
                    left_on='city_code', 
                    right_on='city_code', 
                    how='left'
                )
                
                # Sort by patient count
                flow_with_details = flow_with_details.sort_values('patient_count', ascending=False)
                
                # Show summary metrics
                col1, col2, col3 = st.columns(3)
                with col1:
                    total_patients = flow_with_details['patient_count'].sum()
                    st.metric("Total Patients", f"{total_patients:,}")
                
                with col2:
                    unique_hospitals = len(flow_with_details)
                    st.metric("Destination Hospitals", f"{unique_hospitals}")
                
                with col3:
                    avg_patients = total_patients / unique_hospitals if unique_hospitals > 0 else 0
                    st.metric("Avg Patients per Hospital", f"{avg_patients:.1f}")
                
                # Show top destinations
                st.markdown("##### 🏆 Top Hospital Destinations")
                
                for idx, row in flow_with_details.head(10).iterrows():
                    col1, col2, col3, col4 = st.columns([3, 2, 2, 1])
                    
                    with col1:
                        hospital_name = row.get('name', 'Unknown Hospital')
                        hospital_city = row.get('ville', 'Unknown City')
                        st.markdown(f"**{hospital_name}**")
                        st.caption(f"📍 {hospital_city}")
                    
                    with col2:
                        hospital_status = row.get('statut', 'Unknown')
                        status_color = {
                            'public': '🔵',
                            'private for profit': '🟢',
                            'private not-for-profit': '🔷'
                        }.get(hospital_status.lower() if isinstance(hospital_status, str) else '', '⚪')
                        st.markdown(f"{status_color} {hospital_status}")
                    
                    with col3:
                        patient_count = int(row.get('patient_count', 0))
                        st.metric("Patients", f"{patient_count:,}")
                    
                    with col4:
                        percentage = row.get('percentage', 0)
                        st.metric("Share", f"{percentage:.1f}%")
                    
                    st.markdown("---")
                
                # Show geographic distribution
                st.markdown("##### 📍 Geographic Distribution")
                
                # Calculate distance from origin to each hospital
                origin_city_data = cities[cities['city_code'] == st.session_state.neighbor_flow_city_code]
                if not origin_city_data.empty:
                    origin_lat = origin_city_data['latitude'].iloc[0]
                    origin_lon = origin_city_data['longitude'].iloc[0]
                    
                    # Add distance calculation
                    flow_with_details['distance_km'] = flow_with_details.apply(
                        lambda row: geodesic((origin_lat, origin_lon), (row['latitude'], row['longitude'])).km 
                        if pd.notna(row['latitude']) and pd.notna(row['longitude']) else None, 
                        axis=1
                    )
                    
                    # Show distance vs patient count
                    distance_data = flow_with_details[flow_with_details['distance_km'].notna()].copy()
                    if not distance_data.empty:
                        fig = px.scatter(
                            distance_data,
                            x='distance_km',
                            y='patient_count',
                            size='patient_count',
                            color='statut',
                            hover_data=['name', 'ville'],
                            title="Patient Flow vs Distance from Origin"
                        )
                        fig.update_layout(
                            xaxis_title="Distance (km)",
                            yaxis_title="Number of Patients",
                            height=400
                        )
                        st.plotly_chart(fig, use_container_width=True)
                        
                        # Distance statistics
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            avg_distance = distance_data['distance_km'].mean()
                            st.metric("Average Distance", f"{avg_distance:.1f} km")
                        
                        with col2:
                            max_distance = distance_data['distance_km'].max()
                            st.metric("Farthest Hospital", f"{max_distance:.1f} km")
                        
                        with col3:
                            min_distance = distance_data['distance_km'].min()
                            st.metric("Closest Hospital", f"{min_distance:.1f} km")
        
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
