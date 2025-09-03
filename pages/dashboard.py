# pages/Hospital_Dashboard.py
import streamlit as st
import pandas as pd
import altair as alt
import folium
from folium.plugins import HeatMap
import os
import requests
import branca.colormap as cm
from navira.competitor_layers import (
    AllocationMode,
    build_cp_to_insee,
    competitor_choropleth_df,
    get_top_competitors,
)
from navira.geojson_loader import load_communes_geojson, detect_insee_key
from streamlit_folium import st_folium
import plotly.express as px
import plotly.graph_objects as go
from navira.data_loader import get_dataframes, get_all_dataframes
from auth_wrapper import add_auth_to_page
from navigation_utils import handle_navigation_request
handle_navigation_request()

# Add authentication check
add_auth_to_page()

# --- Page Configuration ---
st.set_page_config(
    page_title="Hospital Dashboard",
    page_icon="📊",
    layout="wide"
)

# --- Cache Control ---
if st.button("♻️ Clear cache"):
    try:
        st.cache_data.clear()
    except Exception:
        pass
    try:
        st.cache_resource.clear()
    except Exception:
        pass
    st.success("Cache cleared. Reloading…")
    try:
        st.rerun()
    except Exception:
        try:
            st.experimental_rerun()
        except Exception:
            pass

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


# --- MAPPING DICTIONARIES ---
BARIATRIC_PROCEDURE_NAMES = {
    'SLE': 'Sleeve Gastrectomy', 'BPG': 'Gastric Bypass', 'ANN': 'Gastric Banding',
    'REV': 'Other', 'ABL': 'Band Removal', 'DBP': 'Bilio-pancreatic Diversion', 'GVC': 'Calibrated Vertical Gastroplasty', 'NDD': 'Not Defined',
}
SURGICAL_APPROACH_NAMES = {
    'LAP': 'Open Surgery', 'COE': 'Coelioscopy', 'ROB': 'Robotic'
}

# --- Load Data (Parquet) ---
try:
    establishments, annual = get_dataframes()
    # Load additional datasets
    all_data = get_all_dataframes()
    competitors = all_data.get('competitors', pd.DataFrame())
    complications = all_data.get('complications', pd.DataFrame())
    procedure_details = all_data.get('procedure_details', pd.DataFrame())
    recruitment = all_data.get('recruitment', pd.DataFrame())
    cities = all_data.get('cities', pd.DataFrame())
except Exception:
    st.error("Parquet data not found. Please run: make parquet")
    st.stop()

# Navigation is now handled by the sidebar


# --- Safely check for selected hospital and data ---
if "selected_hospital_id" not in st.session_state or st.session_state.selected_hospital_id is None:
    st.warning("Please select a hospital from the Home page first.", icon="👈")
    st.stop()

# --- Load data and averages from session state ---
filtered_df = st.session_state.get('filtered_df', pd.DataFrame())
selected_hospital_id = st.session_state.selected_hospital_id
national_averages = st.session_state.get('national_averages', {})

# --- Helper: robust complications lookup by hospital id ---
@st.cache_data(show_spinner=False)
def _get_hospital_complications(complications_df: pd.DataFrame, hospital_id: str) -> pd.DataFrame:
    try:
        if complications_df is None or complications_df.empty:
            return pd.DataFrame()
        df = complications_df.copy()
        if 'hospital_id' not in df.columns:
            return pd.DataFrame()
        # Normalize types/strings
        df['hospital_id'] = df['hospital_id'].astype(str).str.strip()
        hid = str(hospital_id).strip()
        # Exact string match first
        exact = df[df['hospital_id'] == hid]
        if not exact.empty:
            return exact
        # Try zero-pad to 9 digits (common FINESS length)
        if hid.isdigit():
            pad9 = hid.zfill(9)
            pad_match = df[df['hospital_id'].str.zfill(9) == pad9]
            if not pad_match.empty:
                return pad_match
        # Remove non-digits and compare numeric-only identifiers
        import re
        df['_hid_digits'] = df['hospital_id'].apply(lambda s: re.sub(r'\D+', '', s))
        hid_digits = re.sub(r'\D+', '', hid)
        digit_match = df[df['_hid_digits'] == hid_digits]
        if not digit_match.empty:
            return digit_match.drop(columns=['_hid_digits'])
        # Fallback: case-insensitive compare
        ci = df[df['hospital_id'].str.lower() == hid.lower()]
        if not ci.empty:
            return ci
        return pd.DataFrame()
    except Exception:
        return pd.DataFrame()

# Establishment details and annual series
est_row = establishments[establishments['id'] == str(selected_hospital_id)]
if est_row.empty:
    st.error("Could not find data for the selected hospital.")
    st.stop()
selected_hospital_details = est_row.iloc[0]
selected_hospital_all_data = annual[annual['id'] == str(selected_hospital_id)]

# --- (The rest of your dashboard page code follows here) ---
# I'm including the rest of the file for completeness.
st.title("📊 Hospital Details Dashboard")
st.markdown(f"## {selected_hospital_details['name']}")
col1, col2, col3 = st.columns(3)
col1.markdown(f"**City:** {selected_hospital_details['ville']}")
col2.markdown(f"**Status:** {selected_hospital_details['statut']}")
if 'Distance (km)' in selected_hospital_details:
    col3.markdown(f"**Distance:** {selected_hospital_details['Distance (km)']:.1f} km")
st.markdown("---")
metric_col1, metric_col2 = st.columns(2)
with metric_col1:
    st.markdown("#### Surgery Statistics (2020-2024)")
    total_proc_hospital = float(selected_hospital_all_data.get('total_procedures_year', pd.Series(dtype=float)).sum())
    total_rev_hospital = int(selected_hospital_details.get('revision_surgeries_n', 0))
    hospital_revision_pct = (total_rev_hospital / total_proc_hospital) * 100 if total_proc_hospital > 0 else 0
    # National reference values from session
    avg_total_proc = national_averages.get('total_procedures_period', 0)
    national_revision_pct = national_averages.get('revision_pct_avg', 0)
    delta_total = total_proc_hospital - avg_total_proc
    m1, m2 = st.columns(2)
    with m1:
        st.metric(
            label="Hospital Total Surgeries",
            value=f"{int(round(total_proc_hospital)):,}",
            delta=f"{int(round(delta_total)):+,} vs National",
            delta_color="normal"
        )
        st.metric(
            label="Hospital Revision Surgeries",
            value=f"{int(round(total_rev_hospital)):,}",
            delta=f"{hospital_revision_pct:.1f}% of total",
            delta_color="normal"
        )
    with m2:
        volume_vs_nat_pct = (total_proc_hospital / avg_total_proc * 100) if avg_total_proc > 0 else 0
        st.metric(
            label="Volume vs National Avg",
            value=f"{volume_vs_nat_pct:.0f}%"
        )
        # st.metric(
        #     label="National Avg Revision %",
        #     value=f"{national_revision_pct:.1f}%"
        # )

    # Procedure mix metrics (2020-2024): Sleeve, Bypass, Other
    try:
        proc_cols_present = [c for c in BARIATRIC_PROCEDURE_NAMES.keys() if c in selected_hospital_all_data.columns]
        sleeve_total = int(selected_hospital_all_data.get('SLE', pd.Series(dtype=float)).sum()) if 'SLE' in proc_cols_present else 0
        bypass_total = int(selected_hospital_all_data.get('BPG', pd.Series(dtype=float)).sum()) if 'BPG' in proc_cols_present else 0
        other_codes = [c for c in proc_cols_present if c not in ['SLE', 'BPG']]
        other_total = int(selected_hospital_all_data[other_codes].sum().sum()) if other_codes else 0
        st.markdown("#### Procedure Mix (2020-2024)")
        p1, p2, p3 = st.columns(3)
        p1.metric("Sleeve", f"{sleeve_total:,}")
        p2.metric("Gastric Bypass", f"{bypass_total:,}")
        p3.metric("Other", f"{other_total:,}")
    except Exception:
        pass
with metric_col2:
    st.markdown("#### Labels & Affiliations")
    if selected_hospital_details.get('university') == 1: st.success("🎓 University Hospital")
    else: st.warning("➖ No University Affiliation")
    if selected_hospital_details.get('LAB_SOFFCO') == 1: st.success("✅ Centre of Excellence (SOFFCO)")
    else: st.warning("➖ No SOFFCO Centre Label")
    if selected_hospital_details.get('cso') == 1: st.success("✅ Centre of Excellence (Health Ministry)")
    else: st.warning("➖ No Health Ministry Centre Label")
    
    # Robotic share trend chart moved from Annual Statistics
    if 'ROB' in selected_hospital_all_data.columns:
        rob_df = selected_hospital_all_data[['annee', 'ROB', 'total_procedures_year']].dropna()
        if not rob_df.empty:
            rob_df = rob_df.assign(rob_pct=lambda d: (d['ROB'] / d['total_procedures_year'] * 100))
            spark2 = px.line(rob_df, x='annee', y='rob_pct', markers=True)
            spark2.update_layout(height=120, margin=dict(l=20, r=20, t=10, b=10),
                                 xaxis_title=None, yaxis_title=None, plot_bgcolor='rgba(0,0,0,0)',
                                 paper_bgcolor='rgba(0,0,0,0)')
            spark2.update_xaxes(showgrid=False)
            spark2.update_yaxes(showgrid=False)
            st.markdown("##### Robotic Share Trend (%)")
            st.plotly_chart(spark2, use_container_width=True)

    
# --- New Tabbed Layout: Activity, Complications, Geography ---
st.markdown("---")
st.markdown(
    """
    <style>
      /* Enlarge the top navigation tabs for better visibility */
      div[data-testid="stTabs"] div[role="tablist"] { gap: 14px; }
      div[data-testid="stTabs"] button[role="tab"] {
        font-size: 1.10rem;
        padding: 12px 20px;
      }
      div[data-testid="stTabs"] button[role="tab"] p { font-size: 1.10rem; }
    </style>
    """,
    unsafe_allow_html=True,
)
tab_activity, tab_complications, tab_geo = st.tabs(["📈 Activity", "🧪 Complications", "🗺️ Geography"])

def _add_recruitment_zones_to_map(folium_map, hospital_id, recruitment_df, cities_df):
    try:
        # Normalize types to ensure join works
        df_rec = recruitment_df.copy()
        df_rec['hospital_id'] = df_rec['hospital_id'].astype(str)
        # Normalize codes to improve join hit-rate
        df_rec['city_code'] = (
            df_rec['city_code']
            .astype(str)
            .str.strip()
            .str.upper()
            .str.zfill(5)
        )
        df_cities = cities_df.copy()
        if 'city_code' in df_cities.columns:
            df_cities['city_code'] = (
                df_cities['city_code']
                .astype(str)
                .str.strip()
                .str.upper()
                .str.zfill(5)
            )
        
        hosp_recr = df_rec[df_rec['hospital_id'] == str(hospital_id)]
        if hosp_recr.empty:
            st.info("No recruitment data found for this hospital.")
            return
        
        # Sort by patient count and take top N zones for heatmap (broader view)
        hosp_recr = hosp_recr.sort_values('patient_count', ascending=False).head(60)
            
        if df_cities.empty:
            st.info("No city coordinate data available.")
            return
            
        # Try to match recruitment data with city coordinates
        df = hosp_recr.merge(df_cities[['city_code','latitude','longitude','city_name','postal_code']], on='city_code', how='left')
        missing_coords = df[df['latitude'].isna() | df['longitude'].isna()].copy()
        
        # Show diagnostic info
        st.caption(f"Top 5 recruitment zones: {len(hosp_recr)} | With coords: {len(df.dropna(subset=['latitude','longitude']))} | Missing coords: {len(missing_coords)}")
        
        # If we have missing coordinates, optionally attempt a very small geocoding fallback
        if not missing_coords.empty:
            st.info("Top recruitment zones found but some city coordinates are missing.")
            try:
                limited = missing_coords.head(8)
                from geopy.geocoders import Nominatim
                geolocator = Nominatim(user_agent="navira_hospital_dashboard_geography")
                filled = 0
                for _, row in limited.iterrows():
                    city_code = str(row['city_code'])
                    try:
                        q = f"{city_code}, France"
                        loc = geolocator.geocode(q, timeout=2)
                        if loc:
                            df.loc[df['city_code'] == city_code, 'latitude'] = df.loc[df['city_code'] == city_code, 'latitude'].fillna(loc.latitude)
                            df.loc[df['city_code'] == city_code, 'longitude'] = df.loc[df['city_code'] == city_code, 'longitude'].fillna(loc.longitude)
                            filled += 1
                    except Exception:
                        continue
                if filled:
                    st.success(f"Filled coordinates for {filled} zones via quick geocoding.")
            except Exception:
                pass
            
            # Show unresolved cities for debugging
            unresolved = df[df['latitude'].isna() | df['longitude'].isna()][['city_code','city_name','postal_code']].drop_duplicates()
            if not unresolved.empty:
                with st.expander("Unmatched towns (no coordinates)"):
                    st.dataframe(unresolved.head(10), use_container_width=True, hide_index=True)
        
        # Filter to only cities with coordinates
        df = df.dropna(subset=['latitude','longitude'])
        if df.empty:
            st.warning("No cities with coordinates found. Recruitment zones cannot be displayed.")
            return
            
        # Render heat map of recruitment zones (weights by patient_count)
        st.success(f"Rendering recruitment heatmap from {len(df)} zones")
        max_pat = float(df['patient_count'].max() or 1)
        heat_points = [
            [float(r['latitude']), float(r['longitude']), float(r['patient_count']) / max_pat]
            for _, r in df.iterrows()
        ]
        if heat_points:
            HeatMap(
                heat_points,
                radius=20,
                blur=15,
                max_zoom=12,
                min_opacity=0.05
            ).add_to(folium_map)
            
    except Exception as e:
        st.error(f"Error rendering recruitment zones: {str(e)}")


@st.cache_data(show_spinner=False)
def _get_fr_departments_geojson():
    try:
        url = "https://france-geojson.gregoiredavid.fr/repo/departements.geojson"
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


def _dept_code_from_insee(code: str) -> str:
    c = str(code).strip().upper()
    if c.startswith('97') or c.startswith('98'):
        return c[:3]
    if c.startswith('2A') or c.startswith('2B'):
        return c[:2]
    return c[:2]


def _add_recruitment_choropleth_to_map(folium_map, hospital_id, recruitment_df):
    try:
        df_rec = recruitment_df.copy()
        df_rec['hospital_id'] = df_rec['hospital_id'].astype(str)
        df_rec = df_rec[df_rec['hospital_id'] == str(hospital_id)]
        if df_rec.empty:
            st.info("No recruitment data for this hospital.")
            return
        df_rec['city_code'] = (
            df_rec['city_code'].astype(str).str.strip().str.upper().str.zfill(5)
        )
        df_rec['dept_code'] = df_rec['city_code'].apply(_dept_code_from_insee)
        dep = df_rec.groupby('dept_code', as_index=False)['patient_count'].sum()
        if dep.empty:
            st.info("No recruitment data to render.")
            return
        gj = _get_fr_departments_geojson()
        if not gj:
            st.warning("Department boundaries unavailable. Choropleth cannot be displayed.")
            return
        folium.Choropleth(
            geo_data=gj,
            name='Recruitment (dept)',
            data=dep,
            columns=['dept_code', 'patient_count'],
            key_on='feature.properties.code',
            fill_color='YlGn',
            fill_opacity=0.7,
            line_opacity=0.2,
            nan_fill_opacity=0,
            legend_name='Patients (department sum)'
        ).add_to(folium_map)
    except Exception as e:
        st.error(f"Error rendering choropleth: {str(e)}")


@st.cache_data(show_spinner=False)
def _get_fr_regions_geojson():
    try:
        url = "https://france-geojson.gregoiredavid.fr/repo/regions.geojson"
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


def _infer_geojson_code_key(gj, candidates: list[str]) -> str | None:
    try:
        feats = gj.get('features', [])
        if not feats:
            return None
        props = feats[0].get('properties', {})
        for k in candidates:
            if k in props:
                return k
        return None
    except Exception:
        return None


@st.cache_data(show_spinner=False)
def _build_dept_to_region_map() -> dict[str, str]:
    gj = _get_fr_departments_geojson()
    if not gj:
        return {}
    mapping: dict[str, str] = {}
    for f in gj.get('features', []):
        props = f.get('properties', {})
        dept = str(props.get('code', '')).strip()
        # Try multiple property names for region code
        reg = (
            props.get('code_region')
            or props.get('codeRegion')
            or props.get('region')
            or props.get('reg_code')
            or props.get('code_reg')
        )
        if dept and reg is not None:
            mapping[str(dept)] = str(reg)
    return mapping


def _add_recruitment_choropleth_region_to_map(folium_map, hospital_id, recruitment_df):
    try:
        df_rec = recruitment_df.copy()
        df_rec['hospital_id'] = df_rec['hospital_id'].astype(str)
        df_rec = df_rec[df_rec['hospital_id'] == str(hospital_id)]
        if df_rec.empty:
            st.info("No recruitment data for this hospital.")
            return
        df_rec['city_code'] = (
            df_rec['city_code'].astype(str).str.strip().str.upper().str.zfill(5)
        )
        df_rec['dept_code'] = df_rec['city_code'].apply(_dept_code_from_insee)
        d2r = _build_dept_to_region_map()
        if not d2r:
            st.warning("Could not map departments to regions.")
            return
        df_rec['region_code'] = df_rec['dept_code'].map(d2r)
        reg = df_rec.dropna(subset=['region_code']).groupby('region_code', as_index=False)['patient_count'].sum()
        if reg.empty:
            st.info("No recruitment data to render.")
            return
        gj = _get_fr_regions_geojson()
        if not gj:
            st.warning("Region boundaries unavailable. Choropleth cannot be displayed.")
            return
        code_key = _infer_geojson_code_key(gj, ['code','code_insee','codeRegion','code_region','code_reg'])
        if not code_key:
            st.warning("Could not infer region code key in GeoJSON.")
            return
        # Normalize keys to strings
        reg['region_code'] = reg['region_code'].astype(str)
        folium.Choropleth(
            geo_data=gj,
            name='Recruitment (region)',
            data=reg,
            columns=['region_code', 'patient_count'],
            key_on=f'feature.properties.{code_key}',
            fill_color='YlOrRd',
            fill_opacity=0.7,
            line_opacity=0.2,
            nan_fill_opacity=0,
            legend_name='Patients (region sum)'
        ).add_to(folium_map)
    except Exception as e:
        st.error(f"Error rendering regional choropleth: {str(e)}")


@st.cache_data(show_spinner=False)
def _get_fr_communes_geojson():
    try:
        url = "https://france-geojson.gregoiredavid.fr/repo/communes.geojson"
        r = requests.get(url, timeout=25)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


def _add_recruitment_choropleth_commune_to_map(folium_map, hospital_id, recruitment_df, max_communes: int = 300):
    try:
        df_rec = recruitment_df.copy()
        df_rec['hospital_id'] = df_rec['hospital_id'].astype(str)
        df_rec = df_rec[df_rec['hospital_id'] == str(hospital_id)]
        if df_rec.empty:
            st.info("No recruitment data for this hospital.")
            return
        df_rec['city_code'] = (
            df_rec['city_code'].astype(str).str.strip().str.upper().str.zfill(5)
        )
        # Treat codes primarily as postal codes (dataset uses postal codes)
        df_rec['postal'] = df_rec['city_code'].str.replace(r'\D+', '', regex=True).str.zfill(5)
        agg = (
            df_rec[df_rec['postal'].str.len() == 5]
            .groupby('postal', as_index=False)['patient_count'].sum()
            .sort_values('patient_count', ascending=False)
            .head(max_communes)
        )
        codes = set(agg['postal'].astype(str))
        gj_all = _get_fr_communes_geojson()
        if not gj_all:
            st.warning("Commune boundaries unavailable. Choropleth cannot be displayed.")
            return
        feats = gj_all.get('features', [])
        # Build per-commune (INSEE code) sums by matching postal codes to feature 'codesPostaux'
        rows = []
        filtered = []
        for f in feats:
            props = f.get('properties', {})
            insee = str(props.get('code', '')).strip()
            postals = props.get('codesPostaux') or props.get('codes_postaux') or []
            try:
                if isinstance(postals, str):
                    postals = [p.strip() for p in postals.split(',') if p.strip()]
            except Exception:
                postals = []
            matched = [p for p in postals if p in codes]
            if matched:
                # Sum patient counts for all matched postals to this commune
                s = float(agg[agg['postal'].isin(matched)]['patient_count'].sum())
                if s > 0:
                    rows.append({"insee": insee, "patient_count": s})
                    filtered.append(f)
        if not rows:
            st.info("No commune polygons matched the recruitment codes.")
            return
        gj = {"type": "FeatureCollection", "features": filtered}
        data_df = pd.DataFrame(rows)
        folium.Choropleth(
            geo_data=gj,
            name='Recruitment (commune)',
            data=data_df,
            columns=['insee', 'patient_count'],
            key_on='feature.properties.code',
            fill_color='YlOrRd',
            fill_opacity=0.75,
            line_opacity=0.2,
            nan_fill_opacity=0,
            legend_name='Patients (commune sum)'
        ).add_to(folium_map)
        st.caption(f"Commune choropleth rendered from top {len(agg)} postal zones (mapped to communes).")
    except Exception as e:
        st.error(f"Error rendering commune choropleth: {str(e)}")

with tab_activity:
    st.subheader("Activity Overview")
    # Total surgeries and quick mix charts
    col1, col2 = st.columns([2, 1])  # Hospital graphs larger (2), National graphs smaller (1)
    
    with col1:
        st.markdown("#### Hospital: Total Surgeries per Year")
        hosp_year = selected_hospital_all_data[['annee','total_procedures_year']].dropna()
        if not hosp_year.empty:
            fig = px.line(hosp_year, x='annee', y='total_procedures_year', markers=True, title='Hospital Total Surgeries')
            fig.update_layout(height=300, plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)')
            st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.markdown("#### National: Average Surgeries per Hospital")
        if national_averages:
            # Create national trend data
            nat_data = []
            for year in range(2020, 2025):
                year_data = annual[annual['annee'] == year]
                if not year_data.empty:
                    avg_procedures = year_data['total_procedures_year'].mean()
                    nat_data.append({'Year': year, 'Avg Procedures': avg_procedures})
            
            if nat_data:
                nat_df = pd.DataFrame(nat_data)
                fig = px.line(nat_df, x='Year', y='Avg Procedures', markers=True, title='National Average')
                fig.update_layout(height=300, plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)')
                st.plotly_chart(fig, use_container_width=True)
    # Procedure share (3 buckets)
    proc_codes = [c for c in BARIATRIC_PROCEDURE_NAMES.keys() if c in selected_hospital_all_data.columns]
    if proc_codes:
        col1, col2 = st.columns([2, 1])  # Hospital graphs larger (2), National graphs smaller (1)
        
        with col1:
            st.markdown("#### Hospital: Procedure Mix (share %)")
            proc_df = selected_hospital_all_data[['annee']+proc_codes].copy()
            proc_long = []
            for _, r in proc_df.iterrows():
                total = max(1, sum(r[c] for c in proc_codes))
                sleeve = r.get('SLE',0); bypass = r.get('BPG',0)
                other = total - sleeve - bypass
                for label,val in [("Sleeve",sleeve),("Gastric Bypass",bypass),("Other",other)]:
                    proc_long.append({'annee':int(r['annee']),'Procedures':label,'Share':val/total*100})
            pl = pd.DataFrame(proc_long)
            if not pl.empty:
                st.plotly_chart(px.bar(pl, x='annee', y='Share', color='Procedures', barmode='stack').update_layout(height=360, plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)'), use_container_width=True)
        
        with col2:
            st.markdown("#### National: Procedure Mix (share %)")
            # Create national procedure mix data
            nat_proc_data = []
            for year in range(2020, 2025):
                year_data = annual[annual['annee'] == year]
                if not year_data.empty:
                    total_sleeve = year_data['SLE'].sum() if 'SLE' in year_data.columns else 0
                    total_bypass = year_data['BPG'].sum() if 'BPG' in year_data.columns else 0
                    total_other = year_data[proc_codes].sum().sum() - total_sleeve - total_bypass
                    total_all = total_sleeve + total_bypass + total_other
                    
                    if total_all > 0:
                        for label, val in [("Sleeve", total_sleeve), ("Gastric Bypass", total_bypass), ("Other", total_other)]:
                            nat_proc_data.append({'Year': year, 'Procedures': label, 'Share': (val / total_all) * 100})
            
            if nat_proc_data:
                nat_proc_df = pd.DataFrame(nat_proc_data)
                st.plotly_chart(px.bar(nat_proc_df, x='Year', y='Share', color='Procedures', barmode='stack').update_layout(height=360, plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)'), use_container_width=True)
    # Approaches share
    appr_codes = [c for c in SURGICAL_APPROACH_NAMES.keys() if c in selected_hospital_all_data.columns]
    if appr_codes:
        col1, col2 = st.columns([2, 1])  # Hospital graphs larger (2), National graphs smaller (1)
        
        with col1:
            st.markdown("#### Hospital: Surgical Approaches (share %)")
            appr_df = selected_hospital_all_data[['annee']+appr_codes].copy()
            appr_long = []
            for _, r in appr_df.iterrows():
                total = max(1, sum(r[c] for c in appr_codes))
                for code,name in SURGICAL_APPROACH_NAMES.items():
                    if code in r:
                        appr_long.append({'annee':int(r['annee']),'Approach':name,'Share':r[code]/total*100})
            al = pd.DataFrame(appr_long)
            if not al.empty:
                st.plotly_chart(px.bar(al, x='annee', y='Share', color='Approach', barmode='stack').update_layout(height=360, plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)'), use_container_width=True)
        
        with col2:
            st.markdown("#### National: Surgical Approaches (share %)")
            # Create national surgical approach data
            nat_appr_data = []
            for year in range(2020, 2025):
                year_data = annual[annual['annee'] == year]
                if not year_data.empty:
                    total_robotic = year_data['ROB'].sum() if 'ROB' in year_data.columns else 0
                    total_coelio = year_data['COE'].sum() if 'COE' in year_data.columns else 0
                    total_open = year_data['LAP'].sum() if 'LAP' in year_data.columns else 0
                    total_all = total_robotic + total_coelio + total_open
                    
                    if total_all > 0:
                        for code, name in SURGICAL_APPROACH_NAMES.items():
                            if code in year_data.columns:
                                total_val = year_data[code].sum()
                                nat_appr_data.append({'Year': year, 'Approach': name, 'Share': (total_val / total_all) * 100})
            
            if nat_appr_data:
                nat_appr_df = pd.DataFrame(nat_appr_data)
                st.plotly_chart(px.bar(nat_appr_df, x='Year', y='Share', color='Approach', barmode='stack').update_layout(height=360, plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)'), use_container_width=True)
    


with tab_complications:
    st.subheader("Complications")
    hosp_comp = _get_hospital_complications(complications, str(selected_hospital_id)).sort_values('quarter_date')
    if not hosp_comp.empty:
        tot_proc = int(hosp_comp['procedures_count'].sum())
        tot_comp = int(hosp_comp['complications_count'].sum())
        rate = (tot_comp / tot_proc * 100) if tot_proc>0 else 0
        c1, c2, c3 = st.columns(3)
        c1.metric("Total Procedures", f"{tot_proc:,}")
        c2.metric("Total Complications", f"{tot_comp:,}")
        c3.metric("Overall Rate", f"{rate:.1f}%")
        
        # Calculate national averages for comparison
        @st.cache_data(show_spinner=False)
        def calculate_national_complication_averages():
            if complications.empty:
                return pd.DataFrame()
            
            # Calculate national averages by quarter
            national_avg = complications.groupby('quarter_date').agg({
                'complications_count': 'sum',
                'procedures_count': 'sum'
            }).reset_index()
            
            national_avg['national_rate'] = (national_avg['complications_count'] / national_avg['procedures_count'] * 100)
            national_avg['quarter'] = national_avg['quarter_date'].dt.strftime('%YQ%q')
            
            return national_avg
        
        national_avg_data = calculate_national_complication_averages()

        # 6‑month (semester) aggregation for hospital and national
        def _to_semester(df: pd.DataFrame) -> pd.DataFrame:
            if df.empty or 'quarter_date' not in df.columns:
                return pd.DataFrame()
            d = df.copy()
            d = d.dropna(subset=['quarter_date']).sort_values('quarter_date')
            d['year'] = d['quarter_date'].dt.year
            d['half'] = ((d['quarter_date'].dt.quarter - 1) // 2 + 1)
            sem = (
                d.groupby(['year','half'], as_index=False)
                  .agg({'complications_count':'sum','procedures_count':'sum'})
            )
            sem['rate_pct'] = sem.apply(lambda r: (r['complications_count']/r['procedures_count']*100) if r['procedures_count']>0 else 0.0, axis=1)
            sem['label'] = sem['year'].astype(int).astype(str) + ' H' + sem['half'].astype(int).astype(str)
            return sem.sort_values(['year','half'])

        hosp_sem = _to_semester(hosp_comp)
        nat_sem = _to_semester(complications)

        # Display latest 6‑month metrics and comparison
        if not hosp_sem.empty:
            latest_sem = hosp_sem.iloc[-1]
            sem_key = (int(latest_sem['year']), int(latest_sem['half']))
            nat_row = nat_sem[(nat_sem['year']==sem_key[0]) & (nat_sem['half']==sem_key[1])]
            nat_val = float(nat_row['rate_pct'].iloc[0]) if not nat_row.empty else 0.0
            st.markdown("#### Latest 6‑Month Data")
            l1, l2 = st.columns(2)
            with l1:
                st.metric("Hospital 6‑month rate", f"{float(latest_sem['rate_pct']):.1f}%")
            with l2:
                st.metric("National 6‑month rate", f"{nat_val:.1f}%")

            # Bar comparison for the latest semester
            comp_df = pd.DataFrame({
                'Metric': ['Hospital','National'],
                'Rate (%)': [float(latest_sem['rate_pct']), nat_val]
            })
            fig_bar = px.bar(comp_df, x='Metric', y='Rate (%)', title=f"6‑Month Comparison ({latest_sem['label']})",
                             color='Metric', color_discrete_map={'Hospital':'#1f77b4','National':'#ff7f0e'})
            fig_bar.update_layout(height=300, plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)')
            st.plotly_chart(fig_bar, use_container_width=True)
        
        # Removed Quarterly Rate vs National chart due to unreliable hospital quarterly data
    else:
        st.info("No complications data available for this hospital.")
    # Kaplan–Meier style survival curve by 6‑month intervals
    try:
        st.markdown("#### Kaplan–Meier (approx.) — 6‑month complication‑free probability")
        km_src = _get_hospital_complications(complications, str(selected_hospital_id)).copy()
        if not km_src.empty and 'quarter_date' in km_src.columns:
            km_src = km_src.sort_values('quarter_date')
            km_src['year'] = km_src['quarter_date'].dt.year
            km_src['half'] = ((km_src['quarter_date'].dt.quarter - 1) // 2 + 1)
            km_src['semester'] = km_src['year'].astype(str) + ' H' + km_src['half'].astype(int).astype(str)
            sem = km_src.groupby(['year','half','semester'], as_index=False).agg(
                events=('complications_count','sum'),
                total=('procedures_count','sum')
            ).sort_values(['year','half'])
            sem['hazard'] = sem.apply(lambda r: (r['events']/r['total']) if r['total']>0 else 0.0, axis=1)
            sem['survival'] = (1 - sem['hazard']).cumprod()
            if not sem.empty:
                x = []
                y = []
                prev_s = 1.0
                for _, r in sem.iterrows():
                    label = f"{int(r['year'])} H{int(r['half'])}"
                    x.append(label); y.append(prev_s)
                    prev_s = float(r['survival'])
                    x.append(label); y.append(prev_s)
                import plotly.graph_objects as go
                fig_km = go.Figure()
                fig_km.add_trace(go.Scatter(x=x, y=[v*100 for v in y], mode='lines', name='KM (approx.)', line=dict(shape='hv', width=3, color='#1f77b4')))
                fig_km.update_layout(height=300, yaxis_title='Complication‑free probability (%)', xaxis_title='6‑month interval', plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)')
                st.plotly_chart(fig_km, use_container_width=True)
                with st.expander('Method (approximation)'):
                    st.markdown("This curve approximates a Kaplan–Meier survival function using aggregate 6‑month intervals. For each interval, hazard = events / total procedures, and survival multiplies (1 − hazard) across intervals. It uses hospital‑level aggregates (not patient‑level times).")
            else:
                st.info('Not enough data to compute 6‑month Kaplan–Meier curve.')
        else:
            st.info('Complication data unavailable for Kaplan–Meier computation.')
    except Exception:
        pass

with tab_geo:
    st.subheader("Recruitment Zone and Competitors (Top-5 Choropleths)")
    allocation = "even_split"
    # Map
    try:
        center = [float(selected_hospital_details.get('latitude')), float(selected_hospital_details.get('longitude'))]
        if any(pd.isna(center)):
            raise ValueError
    except Exception:
        center = [48.8566, 2.3522]
    m = folium.Map(location=center, zoom_start=10, tiles="CartoDB positron")
    # Ensure choropleths stay below markers even when toggled
    try:
        folium.map.Pane('choropleth', z_index=400).add_to(m)
        folium.map.Pane('markers', z_index=650).add_to(m)
    except Exception:
        pass

    # Add recruitment layer
    # Build competitor layers
    try:
        data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
    except Exception:
        data_dir = os.path.join(os.path.dirname(__file__), "..", "data")
    rec_path = os.path.join(data_dir, "11_recruitement_zone.csv")
    comp_path = os.path.join(data_dir, "13_main_competitors.csv")
    communes_csv = os.path.join(data_dir, "COMMUNES_FRANCE_INSEE.csv")

    # Competitors
    top5 = get_top_competitors(comp_path, str(selected_hospital_id))
    if not top5:
        st.info("No competitors found for this hospital.")
    # Postal → INSEE map
    cp_map = build_cp_to_insee(communes_csv)
    # Competitor name mapping from establishments
    comp_name_map = {}
    try:
        if not establishments.empty and {'id','name'}.issubset(establishments.columns):
            em = establishments[['id','name']].drop_duplicates().copy()
            em['id'] = em['id'].astype(str)
            comp_name_map = dict(zip(em['id'], em['name']))
    except Exception:
        comp_name_map = {}
    # GeoJSON
    # Try to filter GeoJSON to only needed INSEE codes to reduce payload
    needed_insee = []
    try:
        prelim = []
        for comp_id in top5:
            df_layer, _ = competitor_choropleth_df(rec_path, comp_id, cp_map, allocation=allocation)
            prelim.append(df_layer)
        if prelim:
            import pandas as _pd
            needed_insee = _pd.concat(prelim)["insee5"].dropna().astype(str).unique().tolist()
    except Exception:
        needed_insee = []
    try:
        from navira.geojson_loader import load_communes_geojson_filtered
        gj = load_communes_geojson_filtered(needed_insee or [])
    except Exception:
        gj = load_communes_geojson(None)
    insee_key = detect_insee_key(gj) if gj else None

    diagnostics_rows = []
    if gj and insee_key:
        from folium.features import GeoJson, GeoJsonTooltip
        glb_min = None
        glb_max = None
        for idx, comp_id in enumerate(top5):
            df_layer, diag = competitor_choropleth_df(rec_path, comp_id, cp_map, allocation=allocation)  # type: ignore[arg-type]
            diagnostics_rows.append((comp_id, diag))
            if df_layer.empty:
                continue
            try:
                vmin = float(df_layer["value"].min())
                vmax = float(df_layer["value"].max())
                glb_min = vmin if glb_min is None else min(glb_min, vmin)
                glb_max = vmax if glb_max is None else max(glb_max, vmax)
            except Exception:
                pass
            try:
                label_name = comp_name_map.get(str(comp_id), str(comp_id))
                if isinstance(label_name, str) and len(label_name) > 28:
                    label_name = label_name[:27] + '…'
                # Build value lookup for styling
                val_map = dict(zip(df_layer['insee5'].astype(str), df_layer['value'].astype(float)))
                # Create FeatureGroup per competitor
                grp = folium.FeatureGroup(name=f"C{idx+1} {label_name}", show=True if idx == 0 else False)
                # Define style function using global colormap set below
                def _style_fn(feat):
                    code = str(feat.get('properties', {}).get(insee_key, '')).zfill(5)
                    v = val_map.get(code)
                    if v is None:
                        return {"fillOpacity": 0.0, "weight": 0.0, "color": "#00000000"}
                    color = colormap(v) if 'colormap' in globals() else '#e34a33'
                    return {"fillColor": color, "color": "#444444", "weight": 0.4, "fillOpacity": 0.5}
                folium.GeoJson(gj, name=f"geojson_{idx}", style_function=_style_fn, pane='choropleth').add_to(grp)
                grp.add_to(m)
            except Exception:
                continue
        try:
            folium.LayerControl(collapsed=True).add_to(m)
        except Exception:
            pass
        # Add single shared legend
        try:
            if glb_min is not None and glb_max is not None and glb_max > glb_min:
                colormap = cm.linear.YlOrRd_09.scale(glb_min, glb_max)
                colormap.caption = "Patients recruited"
                colormap.add_to(m)
        except Exception:
            pass
    else:
        st.warning("Commune polygons unavailable. Configure COMMUNES_GEOJSON_PATH or secrets.")
    # Hospital marker on top
    try:
        folium.CircleMarker(
            location=[selected_hospital_details['latitude'], selected_hospital_details['longitude']],
            radius=16,
            color='#d62728',
            fill=True,
            fill_color='#d62728',
            fill_opacity=0.95,
            popup=f"<b>{selected_hospital_details['name']}</b><br><i>Selected hospital</i>",
            pane='markers'
        ).add_to(m)
    except Exception:
        pass

    # Hospital marker (added AFTER layers to ensure it stays on top)
    try:
        folium.CircleMarker(
            location=[selected_hospital_details['latitude'], selected_hospital_details['longitude']],
            radius=16,
            color='#d62728',
            fill=True,
            fill_color='#d62728',
            fill_opacity=0.95,
            popup=f"<b>{selected_hospital_details['name']}</b><br><i>Selected hospital</i>"
        ).add_to(m)
    except Exception:
        pass

    # Add top-5 competitors as ranked markers
    try:
        hosp_competitors = competitors[competitors['hospital_id'] == str(selected_hospital_id)]
        if not hosp_competitors.empty:
            comp_named = hosp_competitors.merge(
                establishments[['id','name','ville','statut','latitude','longitude']].copy(),
                left_on='competitor_id', right_on='id', how='left'
            )
            comp_named = comp_named.dropna(subset=['latitude','longitude'])
            comp_named = comp_named.sort_values('competitor_patients', ascending=False).head(5).reset_index(drop=True)
            # Size by rank (smaller to reduce clutter)
            size_by_rank = {0:12, 1:10, 2:8, 3:7, 4:6}
            color = '#1f77b4'
            for idx, r in comp_named.iterrows():
                radius = size_by_rank.get(idx, 8)
                name = r.get('name', 'Competitor')
                pts = int(r.get('competitor_patients', 0) or 0)
                popup = f"<b>{name}</b><br>Rank: {idx+1}<br>Patients: {pts:,}"
                folium.CircleMarker(
                    location=[float(r['latitude']), float(r['longitude'])],
                    radius=radius,
                    color=color,
                    fill=True,
                    fill_color=color,
                    fill_opacity=0.75,
                    popup=popup,
                    pane='markers'
                ).add_to(m)
    except Exception:
        pass

    st_folium(m, width="100%", height=460, key="folium_map_dashboard")

    # Competitors list
    st.markdown("#### Nearby/Competitor Hospitals")
    hosp_competitors = competitors[competitors['hospital_id'] == str(selected_hospital_id)]
    if not hosp_competitors.empty:
        comp_named = hosp_competitors.merge(establishments[['id','name','ville','statut']], left_on='competitor_id', right_on='id', how='left')
        comp_named = comp_named.sort_values('competitor_patients', ascending=False)
        for _, r in comp_named.head(5).iterrows():
            c1, c2, c3 = st.columns([3,2,1])
            c1.markdown(f"**{r.get('name','Unknown')}**")
            c1.caption(f"📍 {r.get('ville','')} ")
            c2.markdown(r.get('statut',''))
            c3.metric("Patients", f"{int(r.get('competitor_patients',0)):,}")
    else:
        st.info("No competitor data available.")

# Stop here to avoid rendering legacy sections below while we transition to the tabbed layout
st.stop()

# Get competitors for this hospital
hospital_competitors = competitors[competitors['hospital_id'] == str(selected_hospital_id)]

if not hospital_competitors.empty:
    st.markdown("#### Top 5 Competitors (Same Territory)")
    st.caption("These hospitals recruit patients from the same geographic areas")
    
    # Create columns for competitor display
    competitors_with_names = hospital_competitors.merge(
        establishments[['id', 'name', 'ville', 'statut']], 
        left_on='competitor_id', 
        right_on='id', 
        how='left'
    )
    
    # Sort by competitor patient count (descending)
    competitors_with_names = competitors_with_names.sort_values('competitor_patients', ascending=False)
    
    # Display top 5 competitors
    for idx, competitor in competitors_with_names.head(5).iterrows():
        col1, col2, col3, col4 = st.columns([3, 2, 2, 1])
        
        with col1:
            competitor_name = competitor.get('name', 'Unknown Hospital')
            competitor_city = competitor.get('ville', 'Unknown City')
            st.markdown(f"**{competitor_name}**")
            st.caption(f"📍 {competitor_city}")
        
        with col2:
            competitor_status = competitor.get('statut', 'Unknown')
            status_color = {
                'public': '🔵',
                'private for profit': '🟢',
                'private not-for-profit': '🔷'
            }.get(competitor_status.lower() if isinstance(competitor_status, str) else '', '⚪')
            st.markdown(f"{status_color} {competitor_status}")
        
        with col3:
            competitor_patients = int(competitor.get('competitor_patients', 0))
            st.metric("Patients", f"{competitor_patients:,}")
        
        with col4:
            # Calculate market share in shared territory
            total_shared = competitor.get('hospital_patients', 0) + competitor_patients
            if total_shared > 0:
                market_share = (competitor_patients / total_shared) * 100
                st.metric("Share", f"{market_share:.1f}%")
        
        st.markdown("---")
    
    # Show summary metrics
    col1, col2, col3 = st.columns(3)
    
    with col1:
        total_competitor_patients = competitors_with_names['competitor_patients'].sum()
        st.metric("Total Competitor Patients", f"{total_competitor_patients:,}")
    
    with col2:
        hospital_patients_in_shared_territory = competitors_with_names['hospital_patients'].iloc[0] if not competitors_with_names.empty else 0
        st.metric("Hospital Patients (Shared Territory)", f"{int(hospital_patients_in_shared_territory):,}")
    
    with col3:
        if hospital_patients_in_shared_territory > 0:
            competitive_intensity = (total_competitor_patients / hospital_patients_in_shared_territory) * 100
            st.metric("Competitive Intensity", f"{competitive_intensity:.1f}%")
    
    # Add visualization of competitive landscape
    if len(competitors_with_names) > 1:
        st.markdown("#### Competitive Landscape")
        
        # Prepare data for visualization
        chart_data = []
        
        # Add hospital itself
        chart_data.append({
            'Hospital': selected_hospital_details['name'],
            'Patients': int(hospital_patients_in_shared_territory),
            'Type': 'Selected Hospital'
        })
        
        # Add competitors
        for _, comp in competitors_with_names.head(5).iterrows():
            chart_data.append({
                'Hospital': comp.get('name', 'Unknown')[:20] + ('...' if len(comp.get('name', '')) > 20 else ''),
                'Patients': int(comp.get('competitor_patients', 0)),
                'Type': 'Competitor'
            })
        
        chart_df = pd.DataFrame(chart_data)
        
        if not chart_df.empty:
            fig = px.bar(
                chart_df,
                x='Patients',
                y='Hospital',
                color='Type',
                orientation='h',
                title="Patient Volume in Shared Territory",
                color_discrete_map={
                    'Selected Hospital': '#1f77b4',
                    'Competitor': '#ff7f0e'
                }
            )
            
            fig.update_layout(
                height=300,
                yaxis={'categoryorder': 'total ascending'},
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)'
            )
            
            st.plotly_chart(fig, use_container_width=True)

else:
    st.info("No competitor data available for this hospital.")

# --- Complications Statistics Section ---
st.markdown("---")
st.header("📊 Complications Statistics")
# Get complications data for this hospital
hospital_complications = _get_hospital_complications(complications, str(selected_hospital_id))
if not hospital_complications.empty:
    # Sort by quarter date
    hospital_complications = hospital_complications.sort_values('quarter_date')
    
    # Calculate overall statistics
    col1, col2, col3 = st.columns(3)
    
    with col1:
        total_procedures = hospital_complications['procedures_count'].sum()
        st.metric("Total Procedures", f"{int(total_procedures):,}")
    
    with col2:
        total_complications = hospital_complications['complications_count'].sum()
        st.metric("Total Complications", f"{int(total_complications):,}")
    
    with col3:
        if total_procedures > 0:
            overall_rate = (total_complications / total_procedures) * 100
            st.metric("Overall Complication Rate", f"{overall_rate:.1f}%")
    
    # Show recent trend (last 4 quarters)
    recent_data = hospital_complications.tail(4)
    if not recent_data.empty:
        st.markdown("#### Recent Trend (Last 4 Quarters)")
        
        # Create trend visualization
        fig = go.Figure()
        
        # Add hospital rolling rate
        fig.add_trace(go.Scatter(
            x=recent_data['quarter'],
            y=recent_data['rolling_rate'] * 100,  # Convert to percentage
            mode='lines+markers',
            name='Hospital (12-month rolling)',
            line=dict(color='#1f77b4', width=3),
            marker=dict(size=8)
        ))
        
        # Add national average
        fig.add_trace(go.Scatter(
            x=recent_data['quarter'],
            y=recent_data['national_average'] * 100,  # Convert to percentage
            mode='lines+markers',
            name='National Average',
            line=dict(color='#ff7f0e', width=2, dash='dash'),
            marker=dict(size=6)
        ))
        
        # Add confidence intervals if available
        if 'confidence_low' in recent_data.columns and 'confidence_high' in recent_data.columns:
            fig.add_trace(go.Scatter(
                x=recent_data['quarter'].tolist() + recent_data['quarter'].tolist()[::-1],
                y=(recent_data['confidence_high'] * 100).tolist() + (recent_data['confidence_low'] * 100).tolist()[::-1],
                fill='toself',
                fillcolor='rgba(31, 119, 180, 0.2)',
                line=dict(color='rgba(255,255,255,0)'),
                name='Confidence Interval',
                showlegend=True
            ))
        
        fig.update_layout(
            title="Complication Rate Trend",
            xaxis_title="Quarter",
            yaxis_title="Complication Rate (%)",
            height=400,
            hovermode='x unified',
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)'
        )
        
        st.plotly_chart(fig, use_container_width=True)
    
    # Show quarterly details
    st.markdown("#### Quarterly Details")
    
    # Prepare data for table
    display_data = hospital_complications[['quarter', 'procedures_count', 'complications_count', 'complication_rate', 'rolling_rate', 'national_average']].copy()
    display_data['complication_rate'] = (display_data['complication_rate'] * 100).round(1)
    display_data['rolling_rate'] = (display_data['rolling_rate'] * 100).round(1)
    display_data['national_average'] = (display_data['national_average'] * 100).round(1)
    
    # Rename columns for display
    display_data = display_data.rename(columns={
        'quarter': 'Quarter',
        'procedures_count': 'Procedures',
        'complications_count': 'Complications',
        'complication_rate': 'Rate (%)',
        'rolling_rate': '12-Month Rolling (%)',
        'national_average': 'National Avg (%)'
    })
    
    # Show last 8 quarters
    st.dataframe(display_data.tail(8), use_container_width=True, hide_index=True)
    
    # Performance analysis
    if not recent_data.empty:
        latest_quarter = recent_data.iloc[-1]
        latest_rolling = latest_quarter['rolling_rate'] * 100
        latest_national = latest_quarter['national_average'] * 100
        
        st.markdown("#### Performance Analysis")
        
        if latest_rolling < latest_national:
            st.success(f"🟢 **Better than National Average**: Hospital's 12-month rolling rate ({latest_rolling:.1f}%) is below the national average ({latest_national:.1f}%)")
        elif latest_rolling > latest_national:
            st.warning(f"🟡 **Above National Average**: Hospital's 12-month rolling rate ({latest_rolling:.1f}%) is above the national average ({latest_national:.1f}%)")
        else:
            st.info(f"🟦 **At National Average**: Hospital's 12-month rolling rate ({latest_rolling:.1f}%) matches the national average")
        
        # Trend analysis
        if len(recent_data) >= 2:
            trend_change = recent_data['rolling_rate'].iloc[-1] - recent_data['rolling_rate'].iloc[-2]
            if abs(trend_change) > 0.001:  # More than 0.1% change
                trend_direction = "improving" if trend_change < 0 else "worsening"
                st.info(f"📈 **Recent Trend**: Complication rate is {trend_direction} (change of {trend_change*100:.1f} percentage points from previous quarter)")

else:
    st.info("No complications statistics available for this hospital.")

st.markdown("---")
st.header("Annual Statistics")
hospital_annual_data = selected_hospital_all_data.set_index('annee')
# Tooltip helpers (shared style)
st.markdown(
    """
    <style>
      .nv-info-wrap { display:inline-flex; align-items:center; gap:8px; }
      .nv-info-badge { width:18px; height:18px; border-radius:50%; background:#444; color:#fff; font-weight:600; font-size:12px; display:inline-flex; align-items:center; justify-content:center; cursor:help; }
      .nv-tooltip { position:relative; display:inline-block; }
      .nv-tooltip .nv-tooltiptext { visibility:hidden; opacity:0; transition:opacity .15s ease; position:absolute; z-index:9999; top:22px; left:50%; transform:translateX(-50%); width:min(420px, 80vw); background:#2b2b2b; color:#fff; border:1px solid rgba(255,255,255,.1); border-radius:6px; padding:10px 12px; box-shadow:0 4px 14px rgba(0,0,0,.35); text-align:left; font-size:0.9rem; line-height:1.25rem; }
      .nv-tooltip:hover .nv-tooltiptext { visibility:visible; opacity:1; }
      .nv-h3 { font-weight:600; font-size:1.05rem; margin:0; }
    </style>
    """,
    unsafe_allow_html=True,
)

# Small sparkline trends for key metrics
try:
    # Total surgeries per year: Hospital vs National (dots only, hide Y axis)
    total_series = selected_hospital_all_data[['annee', 'total_procedures_year']].dropna()
    nat_df_ = annual.copy()
    if 'total_procedures_year' in nat_df_.columns:
        nat_df_ = nat_df_[nat_df_['total_procedures_year'] >= 25]
    nat_series = (
        nat_df_
        .groupby('annee', as_index=False)['total_procedures_year']
        .sum()
        .dropna()
    )
    if not total_series.empty:
        # Info header + tooltip
        st.markdown(
            """
            <div class="nv-info-wrap">
              <div class="nv-h3">Total Surgeries — Hospital</div>
              <div class="nv-tooltip"><span class="nv-info-badge">i</span>
                <div class="nv-tooltiptext">
                  <b>Understanding this chart:</b><br/>
                  Annual total surgeries performed at the selected hospital (2020–2024).
                </div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        fig_hosp = go.Figure(
            go.Scatter(
                x=total_series['annee'].astype(str),
                y=total_series['total_procedures_year'],
                mode='lines+markers',
                name='Hospital',
                marker=dict(size=8),
                hovertemplate='Year: %{x}<br>Total surgeries: %{y:,}<extra></extra>'
            )
        )
        fig_hosp.update_layout(
            height=300,
            margin=dict(l=20, r=20, t=10, b=10),
            xaxis_title=None,
            yaxis_title=None,
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            hovermode='x unified',
            showlegend=False
        )
        fig_hosp.update_xaxes(showgrid=False)
        st.plotly_chart(fig_hosp, use_container_width=True)
        try:
            # Key findings
            ts = total_series.copy()
            ts = ts.sort_values('annee')
            peak_row = ts.loc[ts['total_procedures_year'].idxmax()]
            last_row = ts.iloc[-1]
            with st.expander("What to look for and key findings"):
                st.markdown(
                    f"""
                    **What to look for:**
                    - Year‑to‑year changes in volume
                    - Peak year vs recent year
                    - Direction of the latest trend

                    **Key findings:**
                    - Peak year: **{int(peak_row['annee'])}** with **{int(peak_row['total_procedures_year']):,}** surgeries
                    - 2024 value: **{int(last_row['total_procedures_year']):,}**
                    """
                )
        except Exception:
            pass

    if not nat_series.empty:
        st.markdown(
            """
            <div class="nv-info-wrap">
              <div class="nv-h3">Total Surgeries — National</div>
              <div class="nv-tooltip"><span class="nv-info-badge">i</span>
                <div class="nv-tooltiptext">
                  <b>Understanding this chart:</b><br/>
                  Sum of annual surgeries across all eligible hospitals (≥25 surgeries/year) for each year.
                </div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        fig_nat = go.Figure(
            go.Scatter(
                x=nat_series['annee'].astype(str),
                y=nat_series['total_procedures_year'],
                mode='lines+markers',
                name='National',
                marker=dict(size=8),
                hovertemplate='Year: %{x}<br>Total surgeries: %{y:,}<extra></extra>'
            )
        )
        fig_nat.update_layout(
            height=300,
            margin=dict(l=20, r=20, t=10, b=10),
            xaxis_title=None,
            yaxis_title=None,
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            hovermode='x unified',
            showlegend=False
        )
        fig_nat.update_xaxes(showgrid=False)
        st.plotly_chart(fig_nat, use_container_width=True)
        try:
            ns = nat_series.copy().sort_values('annee')
            pk = ns.loc[ns['total_procedures_year'].idxmax()]
            with st.expander("What to look for and key findings"):
                st.markdown(
                    f"""
                    **What to look for:**
                    - Overall national trend
                    - How 2024 compares to the peak year

                    **Key findings:**
                    - National peak year: **{int(pk['annee'])}** with **{int(pk['total_procedures_year']):,}** surgeries
                    """
                )
        except Exception:
            pass
    else:
        st.info("No total surgeries data available to plot.")
except Exception:
    pass
st.markdown("#### Bariatric Procedures by Year")
st.caption("📊 Hospital chart shows stacked shares by year (bars sum to 100%). National reference available in the tabs.")
bariatric_df = hospital_annual_data[[key for key in BARIATRIC_PROCEDURE_NAMES.keys() if key in hospital_annual_data.columns]].rename(columns=BARIATRIC_PROCEDURE_NAMES)
bariatric_summary = bariatric_df.sum()
summary_texts = []
# Build three-category summary: Sleeve, Bypass, Other
try:
    sleeve_count = int(bariatric_summary.get('Sleeve Gastrectomy', 0))
    bypass_count = int(bariatric_summary.get('Gastric Bypass', 0))
    other_count = int(bariatric_summary.sum() - sleeve_count - bypass_count)
    sleeve_avg_nat = float(national_averages.get('SLE', 0))
    bypass_avg_nat = float(national_averages.get('BPG', 0))
    other_avg_nat = float(sum(national_averages.get(code, 0) for code in BARIATRIC_PROCEDURE_NAMES.keys() if code not in ['SLE', 'BPG']))
    summary_texts.append(f"**Sleeve**: {sleeve_count} total ({sleeve_count/5:.1f}/year) <span style='color:grey; font-style: italic;'>(National Avg: {sleeve_avg_nat:.1f}/year)</span>")
    summary_texts.append(f"**Gastric Bypass**: {bypass_count} total ({bypass_count/5:.1f}/year) <span style='color:grey; font-style: italic;'>(National Avg: {bypass_avg_nat:.1f}/year)</span>")
    summary_texts.append(f"**Other**: {other_count} total ({other_count/5:.1f}/year) <span style='color:grey; font-style: italic;'>(National Avg: {other_avg_nat:.1f}/year)</span>")
    st.markdown(" | ".join(summary_texts), unsafe_allow_html=True)
except Exception:
    pass
bariatric_df_melted = bariatric_df.reset_index().melt('annee', var_name='Procedure', value_name='Count')
# Collapse procedures into three categories: Sleeve, Gastric Bypass, Other
if not bariatric_df_melted.empty:
    def _proc_cat(name: str) -> str:
        if name.lower().startswith('sleeve'):
            return 'Sleeve'
        if name.lower().startswith('gastric bypass'):
            return 'Gastric Bypass'
        return 'Other'
    bariatric_df_melted['Procedures'] = bariatric_df_melted['Procedure'].map(_proc_cat)
    bariatric_df_melted = (bariatric_df_melted
                           .groupby(['annee', 'Procedures'], as_index=False)['Count']
                           .sum())

if not bariatric_df_melted.empty and bariatric_df_melted['Count'].sum() > 0:
    left, right = st.columns([2, 1])
    with left:
        # Consistent color palette across all bariatric charts
        PROC_COLORS = {
            'Sleeve': '#ffae91',          # pink
            'Gastric Bypass': '#60a5fa',  # blue
            'Other': '#fbbf24'            # amber
        }
        # Compute share per year explicitly to avoid barnorm dependency
        _totals = bariatric_df_melted.groupby('annee')['Count'].sum().replace(0, 1)
        bariatric_share = bariatric_df_melted.copy()
        bariatric_share['Share'] = bariatric_share['Count'] / bariatric_share['annee'].map(_totals) * 100
        st.markdown(
            """
            <div class=\"nv-info-wrap\">
              <div class=\"nv-h3\">Bariatric Procedures by Year (share %)</div>
              <div class=\"nv-tooltip\"><span class=\"nv-info-badge\">i</span>
                <div class=\"nv-tooltiptext\">
                  <b>Understanding this chart:</b><br/>
                  Stacked shares of procedure types within the hospital for each year. Each bar sums to 100%.
                </div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        fig = px.bar(
            bariatric_share,
            x='annee',
            y='Share',
            color='Procedures',
            color_discrete_map=PROC_COLORS,
            category_orders={'Procedures': ['Sleeve', 'Gastric Bypass', 'Other']},
            title='Bariatric Procedures by Year (share %)',
            barmode='stack'
        )
        fig.update_layout(
        xaxis_title='Year',
        yaxis_title='Share of procedures (%)',
        hovermode='x unified',
        height=400,
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)'
        )
        # Round hover values to whole percentages
        fig.update_traces(hovertemplate='Year: %{x}<br>%{fullData.name}: %{y:.0f}%<extra></extra>')
        fig.update_yaxes(range=[0, 100], tick0=0, dtick=20)

        st.plotly_chart(fig, use_container_width=True)
        with st.expander("What to look for and key findings"):
            st.markdown(
                """
                **What to look for:**
                - Changes in procedure mix over time
                - Stability vs shifts between Sleeve and Bypass
                - Size of the Other category

                **Key findings:**
                - Bars sum to 100%; compare shares year over year
                """
            )

    # Right column: National analytics in tabs (won't overshadow hospital charts)
    with right:
        tabs = st.tabs(["National over time", "2024 mix"])
        with tabs[0]:
            try:
                nat_df = annual.copy()
                if 'total_procedures_year' in nat_df.columns:
                    nat_df = nat_df[nat_df['total_procedures_year'] >= 25]
                proc_codes = [c for c in BARIATRIC_PROCEDURE_NAMES.keys() if c in nat_df.columns]
                nat_year = nat_df.groupby('annee')[proc_codes].sum().reset_index()
                nat_long = []
                for _, r in nat_year.iterrows():
                    total = max(1, sum(r[c] for c in proc_codes))
                    sleeve = r.get('SLE', 0)
                    bypass = r.get('BPG', 0)
                    other = sum(r[c] for c in proc_codes if c not in ['SLE', 'BPG'])
                    for label, val in [("Sleeve", sleeve), ("Gastric Bypass", bypass), ("Other", other)]:
                        nat_long.append({'annee': int(r['annee']), 'Procedures': label, 'Share': val/total*100})
                nat_share_df = pd.DataFrame(nat_long)
                if not nat_share_df.empty:
                    nat_fig = px.bar(
                        nat_share_df,
                        x='annee',
                        y='Share',
                        color='Procedures',
                        title='National procedures (share %)',
                        barmode='stack',
                        color_discrete_map=PROC_COLORS,
                        category_orders={'Procedures': ['Sleeve', 'Gastric Bypass', 'Other']}
                    )
                    nat_fig.update_layout(height=360, xaxis_title='Year', yaxis_title='% of procedures', plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)')
                    nat_fig.update_traces(opacity=0.95, hovertemplate='Year: %{x}<br>%{fullData.name}: %{y:.0f}%<extra></extra>')
                    nat_fig.update_yaxes(range=[0, 100], tick0=0, dtick=20)
                    st.plotly_chart(nat_fig, use_container_width=True)
            except Exception:
                pass
        with tabs[1]:
            try:
                year_2024 = selected_hospital_all_data[selected_hospital_all_data['annee'] == 2024]
                hosp_counts = {}
                for code, name in BARIATRIC_PROCEDURE_NAMES.items():
                    if code in year_2024.columns:
                        hosp_counts[name] = int(year_2024[code].sum())
                hosp_total = sum(hosp_counts.values()) or 1
                # Collapse to three categories
                hosp_sleeve = hosp_counts.get('Sleeve Gastrectomy', 0)
                hosp_bypass = hosp_counts.get('Gastric Bypass', 0)
                hosp_other = hosp_total - hosp_sleeve - hosp_bypass
                hosp_pct3 = {
                    'Sleeve': hosp_sleeve / hosp_total * 100,
                    'Gastric Bypass': hosp_bypass / hosp_total * 100,
                    'Other': hosp_other / hosp_total * 100
                }

                nat_2024 = annual[annual['annee'] == 2024]
                if 'total_procedures_year' in nat_2024.columns:
                    nat_2024 = nat_2024[nat_2024['total_procedures_year'] >= 25]
                nat_counts = {}
                for code, name in BARIATRIC_PROCEDURE_NAMES.items():
                    if code in nat_2024.columns:
                        nat_counts[name] = int(nat_2024[code].sum())
                nat_total = sum(nat_counts.values()) or 1
                # Collapse to three categories
                nat_sleeve = nat_counts.get('Sleeve Gastrectomy', 0)
                nat_bypass = nat_counts.get('Gastric Bypass', 0)
                nat_other = nat_total - nat_sleeve - nat_bypass
                nat_pct3 = {
                    'Sleeve': nat_sleeve / nat_total * 100,
                    'Gastric Bypass': nat_bypass / nat_total * 100,
                    'Other': nat_other / nat_total * 100
                }

                # Build custom grouped horizontal bars with light/dark procedure colors
                PROC_ORDER = ['Sleeve', 'Gastric Bypass', 'Other']
                LIGHT = {
                    'Sleeve': '#ffae91',
                    'Gastric Bypass': '#60a5fa',
                    'Other': '#fbbf24'
                }
                DARK = {
                    'Sleeve': '#CC8B74',
                    'Gastric Bypass': '#4C84C8',
                    'Other': '#C8981C'
                }

                mix_fig = go.Figure()
                for proc in PROC_ORDER:
                    mix_fig.add_trace(
                        go.Bar(
                            y=[proc], x=[hosp_pct3.get(proc, 0)], name='Hospital %',
                            orientation='h', marker=dict(color=LIGHT[proc]),
                            hovertemplate=f'Procedure: {proc}<br>Hospital: %{{x:.0f}}%<extra></extra>'
                        )
                    )
                    mix_fig.add_trace(
                        go.Bar(
                            y=[proc], x=[nat_pct3.get(proc, 0)], name='National %',
                            orientation='h', marker=dict(color=DARK[proc]),
                            hovertemplate=f'Procedure: {proc}<br>National: %{{x:.0f}}%<extra></extra>'
                        )
                    )

                mix_fig.update_layout(
                    barmode='group', height=360, title='2024 Procedure Mix: Hospital vs National',
                    xaxis_title='% of procedures', yaxis_title=None,
                    plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)'
                )
                st.plotly_chart(mix_fig, use_container_width=True)
                st.markdown(f"National mix — Sleeve: {nat_pct3['Sleeve']:.1f}%, Gastric Bypass: {nat_pct3['Gastric Bypass']:.1f}%, Other: {nat_pct3['Other']:.1f}%")
            except Exception:
                pass
else:
    st.info("No bariatric procedure data available.")
st.markdown("---")
st.markdown("#### Surgical Approaches by Year")
approach_df = hospital_annual_data[[key for key in SURGICAL_APPROACH_NAMES.keys() if key in hospital_annual_data.columns]].rename(columns=SURGICAL_APPROACH_NAMES)
approach_summary = approach_df.sum()
total_approaches = approach_summary.sum()
summary_texts_approach = []
avg_approaches_pct = national_averages.get('approaches_pct', {})
if total_approaches > 0:
    for name, count in approach_summary.items():
        if count > 0:
            percentage = (count / total_approaches) * 100
            avg_pct = avg_approaches_pct.get(name, 0)
            summary_texts_approach.append(f"**{name}**: {int(count)} ({percentage:.1f}%) <span style='color:grey; font-style: italic;'>(National Average: {avg_pct:.1f}%)</span>")
if summary_texts_approach: st.markdown(" | ".join(summary_texts_approach), unsafe_allow_html=True)
approach_df_melted = approach_df.reset_index().melt('annee', var_name='Approach', value_name='Count')
if not approach_df_melted.empty and approach_df_melted['Count'].sum() > 0:
    left2, right2 = st.columns([2, 1])
    with left2:
        # Compute share per year explicitly
        _tot2 = approach_df_melted.groupby('annee')['Count'].sum().replace(0, 1)
        approach_share = approach_df_melted.copy()
        approach_share['Share'] = approach_share['Count'] / approach_share['annee'].map(_tot2) * 100
        APPROACH_COLORS = {
            'Robotic': '#FF7518',
            'Coelioscopy': '#50C878',
            'Open Surgery': '#8e4585'
        }
        fig2 = px.bar(
            approach_share,
            x='annee',
            y='Share',
            color='Approach',
            title='Surgical Approaches by Year (share %)',
            barmode='stack',
            color_discrete_map=APPROACH_COLORS,
            category_orders={'Approach': ['Sleeve', 'Gastric Bypass', 'Other']} # placeholder to ensure consistent legend order if mapped names appear elsewhere
        )
        fig2.update_layout(
            xaxis_title='Year',
            yaxis_title='Share of surgeries (%)',
            hovermode='x unified',
            height=400,
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)'
        )
        # Removed dashed national overlays per request

        st.plotly_chart(fig2, use_container_width=True)
        with st.expander("What to look for and key findings"):
            st.markdown(
                """
                **What to look for:**
                - Mix shifts among approaches over time
                - Robotic share relative to Coelioscopy and Open Surgery
                - Sudden changes in any year

                **Key findings:**
                - Bars sum to 100%; compare within each year
                """
            )

    with right2:
        tabs2 = st.tabs(["National over time", "2024 mix"])
        with tabs2[0]:
            try:
                nat_df2 = annual.copy()
                if 'total_procedures_year' in nat_df2.columns:
                    nat_df2 = nat_df2[nat_df2['total_procedures_year'] >= 25]
                appr_codes = [c for c in SURGICAL_APPROACH_NAMES.keys() if c in nat_df2.columns]
                nat_y = nat_df2.groupby('annee')[appr_codes].sum().reset_index()
                nat_long2 = []
                for _, r in nat_y.iterrows():
                    total = max(1, sum(r[c] for c in appr_codes))
                    for code, name in SURGICAL_APPROACH_NAMES.items():
                        if code in r:
                            nat_long2.append({'annee': int(r['annee']), 'Approach': name, 'Share': r[code]/total*100})
                nat_share2 = pd.DataFrame(nat_long2)
                if not nat_share2.empty:
                    nat_fig2 = px.bar(nat_share2, x='annee', y='Share', color='Approach', title='National approaches (share %)', barmode='stack', color_discrete_map=APPROACH_COLORS)
                    nat_fig2.update_layout(height=360, xaxis_title='Year', yaxis_title='% of surgeries', plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)')
                    nat_fig2.update_traces(opacity=0.85)
                    st.plotly_chart(nat_fig2, use_container_width=True)
            except Exception:
                pass

        with tabs2[1]:
            try:
                year_2024 = selected_hospital_all_data[selected_hospital_all_data['annee'] == 2024]
                h_counts = {}
                for code, name in SURGICAL_APPROACH_NAMES.items():
                    if code in year_2024.columns:
                        h_counts[name] = int(year_2024[code].sum())
                h_tot = sum(h_counts.values()) or 1
                h_pct = {k: (v / h_tot * 100) for k, v in h_counts.items()}

                nat_2024 = annual[annual['annee'] == 2024]
                if 'total_procedures_year' in nat_2024.columns:
                    nat_2024 = nat_2024[nat_2024['total_procedures_year'] >= 25]
                n_counts = {}
                for code, name in SURGICAL_APPROACH_NAMES.items():
                    if code in nat_2024.columns:
                        n_counts[name] = int(nat_2024[code].sum())
                n_tot = sum(n_counts.values()) or 1
                n_pct = {k: (v / n_tot * 100) for k, v in n_counts.items()}

                # Build custom grouped bars with light/dark approach colors
                ORDER = ['Robotic', 'Coelioscopy', 'Open Surgery']
                LIGHT = {
                    'Robotic': '#FF7518',      # hospital
                    'Coelioscopy': '#50C878',
                    'Open Surgery': '#8e4585'
                }
                DARK = {
                    'Robotic': '#d47e30',      # national (slightly darker pastel)
                    'Coelioscopy': '#2c5f34',
                    'Open Surgery': '#722F37'
                }

                mix2 = go.Figure()
                for appr in ORDER:
                    mix2.add_trace(
                        go.Bar(
                            y=[appr], x=[h_pct.get(appr, 0)], name='Hospital %', orientation='h',
                            marker=dict(color=LIGHT[appr]),
                            hovertemplate=f'Approach: {appr}<br>Hospital: %{{x:.0f}}%<extra></extra>'
                        )
                    )
                    mix2.add_trace(
                        go.Bar(
                            y=[appr], x=[n_pct.get(appr, 0)], name='National %', orientation='h',
                            marker=dict(color=DARK[appr]),
                            hovertemplate=f'Approach: {appr}<br>National: %{{x:.0f}}%<extra></extra>'
                        )
                    )
                mix2.update_layout(
                    barmode='group', height=360, title='2024 Approach Mix: Hospital vs National',
                    xaxis_title='% of surgeries', yaxis_title=None,
                    plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)'
                )
                st.plotly_chart(mix2, use_container_width=True)
                # National mix text
                try:
                    open_pct = n_pct.get('Open Surgery', 0)
                    coel_pct = n_pct.get('Coelioscopy', 0)
                    rob_pct = n_pct.get('Robotic', 0)
                    st.markdown(f"National mix — Open: {open_pct:.1f}%, Coelioscopy: {coel_pct:.1f}%, Robotic: {rob_pct:.1f}%")
                except Exception:
                    pass
            except Exception:
                pass
else:
    st.info("No surgical approach data available.")

# --- Detailed Procedure Analysis Section ---
st.markdown("---")
st.header("🔬 Detailed Procedure Analysis")

# Get procedure details for this hospital
hospital_procedure_details = procedure_details[procedure_details['hospital_id'] == str(selected_hospital_id)]

if not hospital_procedure_details.empty:
    st.markdown("#### Procedure-Specific Robotic Rates")
    
    # Calculate robotic rates by procedure type
    robotic_by_procedure = hospital_procedure_details[
        hospital_procedure_details['surgical_approach'] == 'ROB'
    ].groupby(['procedure_type', 'year'])['procedure_count'].sum().reset_index()
    
    total_by_procedure = hospital_procedure_details.groupby(['procedure_type', 'year'])['procedure_count'].sum().reset_index()
    total_by_procedure = total_by_procedure.rename(columns={'procedure_count': 'total_count'})
    
    # Merge to calculate percentages
    robotic_rates = robotic_by_procedure.merge(
        total_by_procedure, 
        on=['procedure_type', 'year'], 
        how='right'
    ).fillna(0)
    robotic_rates['robotic_rate'] = (robotic_rates['procedure_count'] / robotic_rates['total_count'] * 100)
    
    # Show current year (2024) robotic rates
    current_year_rates = robotic_rates[robotic_rates['year'] == 2024]
    if not current_year_rates.empty:
        st.markdown("##### 2024 Robotic Adoption by Procedure Type")
        
        # Map procedure codes to names
        procedure_names = {
            'SLE': 'Sleeve Gastrectomy',
            'BPG': 'Gastric Bypass', 
            'ANN': 'Gastric Banding',
            'REV': 'Revision Surgery',
            'ABL': 'Band Removal',
            'DBP': 'Bilio-pancreatic Diversion',
            'GVC': 'Gastroplasty',
            'NDD': 'Not Defined'
        }
        
        for _, row in current_year_rates.iterrows():
            procedure_name = procedure_names.get(row['procedure_type'], row['procedure_type'])
            col1, col2, col3 = st.columns([2, 1, 1])
            
            with col1:
                st.markdown(f"**{procedure_name}**")
            with col2:
                st.metric("Total Procedures", f"{int(row['total_count']):,}")
            with col3:
                if row['total_count'] > 0:
                    st.metric("Robotic Rate", f"{row['robotic_rate']:.1f}%")
                else:
                    st.metric("Robotic Rate", "N/A")
    
    # Primary vs Revisional Surgery Analysis
    st.markdown("#### Primary vs Revisional Surgery")
    
    primary_revision = hospital_procedure_details.groupby(['is_revision', 'surgical_approach', 'year'])['procedure_count'].sum().reset_index()
    
    # Show 2024 data
    current_pr = primary_revision[primary_revision['year'] == 2024]
    if not current_pr.empty:
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("##### Primary Procedures (2024)")
            primary_2024 = current_pr[current_pr['is_revision'] == 0]
            if not primary_2024.empty:
                total_primary = primary_2024['procedure_count'].sum()
                robotic_primary = primary_2024[primary_2024['surgical_approach'] == 'ROB']['procedure_count'].sum()
                robotic_rate_primary = (robotic_primary / total_primary * 100) if total_primary > 0 else 0
                
                st.metric("Total Primary", f"{int(total_primary):,}")
                st.metric("Robotic Primary", f"{int(robotic_primary):,}")
                st.metric("Robotic Rate", f"{robotic_rate_primary:.1f}%")
        
        with col2:
            st.markdown("##### Revision Procedures (2024)")
            revision_2024 = current_pr[current_pr['is_revision'] == 1]
            if not revision_2024.empty:
                total_revision = revision_2024['procedure_count'].sum()
                robotic_revision = revision_2024[revision_2024['surgical_approach'] == 'ROB']['procedure_count'].sum()
                robotic_rate_revision = (robotic_revision / total_revision * 100) if total_revision > 0 else 0
                
                st.metric("Total Revision", f"{int(total_revision):,}")
                st.metric("Robotic Revision", f"{int(robotic_revision):,}")
                st.metric("Robotic Rate", f"{robotic_rate_revision:.1f}%")
    
    # Temporal trend of robotic adoption
    st.markdown("#### Robotic Adoption Trends by Year")
    
    yearly_robotic = hospital_procedure_details[
        hospital_procedure_details['surgical_approach'] == 'ROB'
    ].groupby('year')['procedure_count'].sum().reset_index()
    
    yearly_total = hospital_procedure_details.groupby('year')['procedure_count'].sum().reset_index()
    yearly_total = yearly_total.rename(columns={'procedure_count': 'total_count'})
    
    yearly_trends = yearly_robotic.merge(yearly_total, on='year', how='right').fillna(0)
    yearly_trends['robotic_percentage'] = (yearly_trends['procedure_count'] / yearly_trends['total_count'] * 100)
    
    if not yearly_trends.empty:
        fig = go.Figure()
        
        fig.add_trace(go.Scatter(
            x=yearly_trends['year'],
            y=yearly_trends['robotic_percentage'],
            mode='lines+markers',
            name='Robotic Adoption Rate',
            line=dict(color='#FF7518', width=3),
            marker=dict(size=8)
        ))
        
        fig.update_layout(
            title="Robotic Surgery Adoption Over Time",
            xaxis_title="Year",
            yaxis_title="Robotic Procedures (%)",
            height=300,
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)'
        )
        
        st.plotly_chart(fig, use_container_width=True)
    
    # Detailed breakdown table
    st.markdown("#### Complete Procedure Breakdown")
    
    # Create summary table
    summary_table = hospital_procedure_details.groupby(['year', 'procedure_type', 'surgical_approach']).agg({
        'procedure_count': 'sum',
        'is_revision': 'first'  # Just to keep track of primary vs revision
    }).reset_index()
    
    # Pivot table for better display
    pivot_table = summary_table.pivot_table(
        index=['year', 'procedure_type'],
        columns='surgical_approach',
        values='procedure_count',
        fill_value=0
    ).reset_index()
    
    # Add total column
    approach_cols = [col for col in pivot_table.columns if col in ['COE', 'LAP', 'ROB']]
    if approach_cols:
        pivot_table['Total'] = pivot_table[approach_cols].sum(axis=1)
        
        # Add robotic percentage
        if 'ROB' in approach_cols:
            pivot_table['Robotic %'] = (pivot_table['ROB'] / pivot_table['Total'] * 100).round(1)
    
    # Show only recent years (2022-2024)
    recent_table = pivot_table[pivot_table['year'] >= 2022]
    if not recent_table.empty:
        st.dataframe(recent_table, use_container_width=True, hide_index=True)

else:
    st.info("No detailed procedure data available for this hospital.")
    
    # Show what metrics we can calculate from other data
    st.markdown("#### Available Metrics from Annual Data")
    
    st.markdown("""
    **What we CAN analyze from existing data:**
    - Overall robotic surgery trends (available above)
    - Total procedure volumes by type (SLE, BPG, etc.)
    - Surgical approach distribution (Coelioscopy, Open, Robotic)
    
    **What we CANNOT analyze without detailed data:**
    - Procedure-specific robotic rates (e.g., % of gastric sleeves done robotically)
    - Primary vs revisional robotic procedures breakdown
    - Detailed temporal trends by procedure type and approach
    """)
