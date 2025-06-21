import streamlit as st
import pandas as pd
import folium
from folium.plugins import MarkerCluster
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
from streamlit_folium import st_folium

# --- 1. App Configuration ---
st.set_page_config(page_title="Navira", layout="wide")

# --- 2. Session State Initialization ---
if "search_triggered" not in st.session_state:
    st.session_state["search_triggered"] = False

# --- 3. Load Data ---
@st.cache_data
def load_data(path="navira_test_hospitals_bariatric.csv"):
    df = pd.read_csv(path)
    assert {"activity", "address", "latitude", "longitude", "group", "name", "category"}.issubset(df.columns)
    return df

df = load_data()

# --- 4. Main UI ---
st.markdown("## 🔍 Recherche d’hôpitaux")
st.markdown("Trouvez les établissements spécialisés en fonction de votre pathologie et de votre localisation.")

col1, col2, col3 = st.columns([3, 2, 2])

with col1:
    address = st.text_input("📍 Votre adresse ou code postal", placeholder="ex: 75019 ou Paris")

with col2:
    pathology = st.selectbox("🦠 Type de pathologie", df['group'].unique())

with col3:
    radius_km = st.slider("📏 Rayon de recherche (km)", min_value=1, max_value=1000, value=50)

# Trigger search
if st.button("🔎 Lancer la recherche"):
    st.session_state["search_triggered"] = True

st.markdown("---")

# --- 5. Geocoding Function ---
@st.cache_data(show_spinner=False)
def geocode_address(address):
    geolocator = Nominatim(user_agent="navira_app")
    return geolocator.geocode(address, timeout=5)

# --- 6. Processing Logic ---
user_coords = None
filtered = pd.DataFrame()

if st.session_state["search_triggered"] and address:
    try:
        enriched_address = address.strip()
        if enriched_address.isdigit() and len(enriched_address) == 5:
            enriched_address += ", France"

        loc = geocode_address(enriched_address) or geocode_address(f"{address}, France")

        if loc:
            user_coords = (loc.latitude, loc.longitude)
            filtered = df[df['group'] == pathology].copy()
            filtered['distance_km'] = filtered.apply(
                lambda r: geodesic(user_coords, (r['latitude'], r['longitude'])).km,
                axis=1
            )
            filtered = filtered[filtered['distance_km'] <= radius_km].sort_values('distance_km')
        else:
            st.error("❗ Adresse introuvable.")
    except Exception as e:
        st.error(f"❗ Erreur de géocodage : {str(e)}")

# --- 7. Display Results ---
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

    st_data = st_folium(m, width="100%", height=600, center=user_coords, zoom=10)

    st.markdown(f"### 🏥 {len(filtered)} établissements trouvés")
    st.dataframe(filtered[['name', 'address', 'distance_km', 'activity', 'category']])

    if st.button("🔄 Nouvelle recherche"):
        st.session_state["search_triggered"] = False
        st.experimental_rerun()

elif st.session_state["search_triggered"] and user_coords and filtered.empty:
    st.warning("Aucun hôpital trouvé dans ce rayon.")
    if st.button("🔄 Nouvelle recherche"):
        st.session_state["search_triggered"] = False
        st.experimental_rerun()
elif st.session_state["search_triggered"] and not user_coords:
    st.info("❗ Adresse invalide ou introuvable. Essayez un autre format.")
    if st.button("🔄 Nouvelle recherche"):
        st.session_state["search_triggered"] = False
        st.experimental_rerun()
else:
    st.info("Veuillez entrer votre adresse et appuyer sur « Lancer la recherche ».")
