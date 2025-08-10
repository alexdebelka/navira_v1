import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import os
from haversine import haversine, Unit

# --- Page Configuration ---
st.set_page_config(
    page_title="Navira - French Hospital Explorer",
    page_icon="🏥",
    layout="wide",
)

# <<< FIX: Navigation logic moved to the top of the script >>>
# This checks if a hospital was selected on the previous run.
# If so, it switches to the dashboard page immediately.
if "selected_hospital_id" in st.session_state and st.session_state.selected_hospital_id is not None:
    # We clear the state after switching to prevent getting stuck on the dashboard page
    # A better approach would be for the dashboard to have a "back" button that clears this.
    st.switch_page("pages/dashboard.py")


# --- Data Loading Function ---
@st.cache_data
def load_data(path):
    try:
        df = pd.read_csv(path, sep=',')
        df.rename(columns={
            'id': 'ID', 'rs': 'Hospital Name', 'statut': 'Status', 'ville': 'City',
            'revision_surgeries_n': 'Revision Surgeries (N)',
            'revision_surgeries_pct': 'Revision Surgeries (%)'
        }, inplace=True)
        
        # Aggregate data to have one row per hospital, keeping the latest year's info
        # for display but summing up totals over the period.
        agg_functions = {
            'Hospital Name': 'first', 'Status': 'first', 'City': 'first',
            'latitude': 'first', 'longitude': 'first', 'lib_dep': 'first', 'lib_reg': 'first',
            'total_procedures_period': 'first',  # This seems to be a static total
            'Revision Surgeries (N)': 'first', # This also seems static
            'Revision Surgeries (%)': 'first',
            'university': 'max', 'cso': 'max', 'LAB_SOFFCO': 'max'
        }
        
        hospital_df = df.groupby('ID').agg(agg_functions).reset_index()
        return df, hospital_df

    except FileNotFoundError:
        st.error(f"Fatal Error: Data file not found at '{path}'. Please ensure the file is in the 'data' directory.")
        st.stop()
    except Exception as e:
        st.error(f"An error occurred loading data: {e}")
        st.stop()

# --- Build Correct File Path ---
script_dir = os.path.dirname(os.path.abspath(__file__))
file_path = os.path.join(script_dir, 'data', 'flattened_v3.csv')

# --- Load Data ---
full_df, hospitals_df = load_data(file_path)

# Store the full dataframe in session state so the dashboard page can access it
st.session_state.df = full_df

# --- UI ---
st.title("🏥 Navira - French Hospital Explorer")
st.markdown("Find and compare bariatric surgery centers across France.")

# --- Sidebar Filters ---
with st.sidebar:
    st.header("Search & Filter")

    # User Location Input
    st.subheader("Your Location")
    user_address = st.text_input("Enter your address (e.g., 'Eiffel Tower, Paris')", "")
    
    # Use a geocoding service (if available) or let user input lat/lon manually for now
    # This is a placeholder for a real geocoding implementation
    user_lat = st.number_input("Or enter your Latitude", value=48.8584, format="%.4f")
    user_lon = st.number_input("Or enter your Longitude", value=2.2945, format="%.4f")
    user_location = (user_lat, user_lon) if user_lat and user_lon else None
    
    radius = st.slider("Search Radius (km)", 10, 500, 100, 10)

    # Other Filters
    st.subheader("Hospital Filters")
    regions = ['All'] + sorted(hospitals_df['lib_reg'].unique().tolist())
    selected_region = st.selectbox("Region", regions)

    departments = ['All']
    if selected_region != 'All':
        departments += sorted(hospitals_df[hospitals_df['lib_reg'] == selected_region]['lib_dep'].unique().tolist())
    selected_department = st.selectbox("Department", departments)

    statuses = ['All'] + sorted(hospitals_df['Status'].unique().tolist())
    selected_status = st.selectbox("Status", statuses)

    # Label Filters
    st.subheader("Label Filters")
    uni_hosp = st.checkbox("🎓 University Hospital")
    soffco_label = st.checkbox("✅ SOFFCO Centre of Excellence")
    cso_label = st.checkbox("✅ Health Ministry Centre of Excellence")

# --- Filtering Logic ---
filtered_hospitals = hospitals_df.copy()

if selected_region != 'All':
    filtered_hospitals = filtered_hospitals[filtered_hospitals['lib_reg'] == selected_region]
if selected_department != 'All':
    filtered_hospitals = filtered_hospitals[filtered_hospitals['lib_dep'] == selected_department]
if selected_status != 'All':
    filtered_hospitals = filtered_hospitals[filtered_hospitals['Status'] == selected_status]
if uni_hosp:
    filtered_hospitals = filtered_hospitals[filtered_hospitals['university'] == 1]
if soffco_label:
    filtered_hospitals = filtered_hospitals[filtered_hospitals['LAB_SOFFCO'] == 1]
if cso_label:
    filtered_hospitals = filtered_hospitals[filtered_hospitals['cso'] == 1]

# Location-based filtering
if user_location:
    filtered_hospitals['Distance (km)'] = filtered_hospitals.apply(
        lambda row: haversine(user_location, (row['latitude'], row['longitude'])),
        axis=1
    )
    hospitals_to_display = filtered_hospitals[filtered_hospitals['Distance (km)'] <= radius].sort_values('Distance (km)')
else:
    hospitals_to_display = filtered_hospitals
    hospitals_to_display['Distance (km)'] = None

st.session_state.filtered_df = hospitals_to_display

# --- Main Page Display ---
map_col, list_col = st.columns([2, 3])

with map_col:
    st.subheader("Hospital Map")
    if user_location:
        m = folium.Map(location=[user_lat, user_lon], zoom_start=8)
        folium.Marker([user_lat, user_lon], popup="Your Location", icon=folium.Icon(color='red')).add_to(m)
    else:
        m = folium.Map(location=[46.603354, 1.888334], zoom_start=5) # Center of France

    for idx, row in hospitals_to_display.iterrows():
        folium.Marker(
            location=[row['latitude'], row['longitude']],
            popup=f"<b>{row['Hospital Name']}</b><br>{row['City']}"
        ).add_to(m)
    st_folium(m, width=700, height=500)

with list_col:
    st.subheader(f"Found {len(hospitals_to_display)} Hospitals")
    
    if hospitals_to_display.empty:
        st.warning("No hospitals match your criteria. Try expanding your search radius or adjusting filters.")
    else:
        for index, row in hospitals_to_display.iterrows():
            col1, col2, col3, col4 = st.columns([3, 2, 2, 2])
            with col1:
                st.markdown(f"**{row['Hospital Name']}**")
                st.caption(f"{row['City']} ({row['lib_dep']})")
            with col2:
                total_proc = row.get('total_procedures_period', 0)
                st.metric("Total Surgeries", f"{int(total_proc):,}")
            with col3:
                if row['Distance (km)'] is not None:
                    st.metric("Distance", f"{row['Distance (km)']:.1f} km")
            with col4:
                hospital_id = row['ID']
                # <<< FIX: The button now only sets the session state and reruns the app >>>
                if st.button("View Details", key=f"details_{hospital_id}"):
                    st.session_state.selected_hospital_id = hospital_id
                    st.rerun()
            st.markdown("---")
