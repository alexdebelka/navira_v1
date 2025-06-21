# app.py
import streamlit as st
import pandas as pd
import folium
from folium.plugins import MarkerCluster
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
from streamlit_folium import st_folium

# --- 1. App Configuration ---
st.set_page_config(page_title="Navira", layout="wide")

# --- 2. Data Loading ---
@st.cache_data
def load_data(path="navira_test_hospitals_bariatric.csv"):
    df = pd.read_csv(path)
    assert {"activity","address","latitude","longitude","group","name","category"}.issubset(df.columns)
    return df
df = load_data()

# --- 3. Sidebar Inputs ---
st.sidebar.header("🔍 Recherche")
address = st.sidebar.text_input("Votre adresse ou code postal")
pathology = st.sidebar.selectbox("Type de pathologie", df['group'].unique())
radius_km = st.sidebar.slider("Rayon de recherche (km)", min_value=1, max_value=1000, value=50)

@st.cache_data(show_spinner=False)
def geocode_address(address):
    geolocator = Nominatim(user_agent="navira_app")
    return geolocator.geocode(address, timeout=5)

# --- 4. Geocode User Address ---
user_coords = None
if address:
    try:
        # Add context if input is just a postal code
        enriched_address = address.strip()
        if enriched_address.isdigit() and len(enriched_address) == 5:
            enriched_address += ", France"
        
        # First attempt using cached function
        loc = geocode_address(enriched_address)
        
        # Fallback
        if not loc:
            loc = geocode_address(f"{address}, France")

        if loc:
            user_coords = (loc.latitude, loc.longitude)
        else:
            st.sidebar.error("❗ Adresse introuvable.")
            
    except Exception as e:
        st.sidebar.error(f"❗ Erreur de géocodage : {str(e)}")



        
# 5. Filter & Compute Proximity
if user_coords:
    filtered = df[df['group'] == pathology].copy()
    filtered['distance_km'] = filtered.apply(
        lambda r: geodesic(user_coords, (r['latitude'], r['longitude'])).km,
        axis=1
    )
    filtered = filtered[filtered['distance_km'] <= radius_km].sort_values('distance_km')


# 6. Create the Map
if user_coords and not filtered.empty:
    m = folium.Map(location=user_coords, zoom_start=10)
    cluster = MarkerCluster().add_to(m)
    
    for _, r in filtered.iterrows():
        folium.Marker(
            location=[r['latitude'], r['longitude']],
            popup=folium.Popup(
                f"<b>{r['name']}</b><br>"
                f"{r['address']}<br>"
                f"Distance: {r['distance_km']:.1f} km<br>"
                f"Activity: {r['activity']}<br>"
                f"Category: {r['category']}",
                max_width=300
            ),
            icon=folium.Icon(icon="hospital-o", prefix="fa", color="blue")
        ).add_to(cluster)
    
    st_data = st_folium(m, width=800, height=600, center=user_coords, zoom=10)
    st.sidebar.markdown(f"### 🏥 {len(filtered)} établissements trouvés")
    st.sidebar.dataframe(filtered[['name','address','distance_km','activity','category']])
elif user_coords:
    st.warning("Aucun hôpital trouvé dans ce rayon.")
else:
    st.info("Veuillez entrer votre adresse pour lancer la recherche.")
