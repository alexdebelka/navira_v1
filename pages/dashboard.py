# pages/Hospital_Dashboard.py
import streamlit as st
import pandas as pd
import numpy as np
import folium
from folium.plugins import HeatMap
import requests
import branca.colormap as cm
from navira.competitors import (
    get_top_competitors,
    get_competitor_names,
    competitor_choropleth_df
)
from streamlit_folium import st_folium
import plotly.express as px
import plotly.graph_objects as go
from navira.data_loader import get_dataframes, get_all_dataframes
from auth_wrapper import add_auth_to_page
from navigation_utils import handle_navigation_request
from charts import (
    create_procedure_mix_chart, 
    create_surgical_approaches_chart, 
    create_volume_trend_chart,
    create_revision_rate_chart,
    create_robotic_surgery_chart,
    create_complications_rate_chart,
    create_complications_grade_chart,
    create_los_distribution_chart,
    create_extended_los_chart,
    create_never_events_chart
)
from navira.sections.activity import render_activity as render_activity_section
from navira.sections.complication import render_complications as render_complications_section
handle_navigation_request()

# Identify this page early to avoid redirect loops for limited users
st.session_state.current_page = "hospital"
st.session_state._on_hospital_dashboard = True

# Add authentication check
add_auth_to_page()

# --- Page Configuration ---
st.set_page_config(
    page_title="Hospital Dashboard",
    page_icon="📊",
    layout="wide"
)

# Build/version indicator to verify redeploys
try:
    _build_id = None
    with open('deploy_trigger.txt', 'r') as _f:
        _build_id = _f.read().strip()[:64]
    if _build_id:
        st.caption(f"Build: {_build_id}")
except Exception:
    _build_id = None

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
        /* Lightweight cards and pills for metrics */
        .nv-card { border: 1px solid rgba(255,255,255,.12); border-radius: 10px; padding: 12px 14px; background: rgba(255,255,255,.03); }
        .nv-card.small { padding: 8px 10px; }
        .nv-metric-title { font-weight: 600; font-size: 0.95rem; color: #cfcfcf; text-align: center; margin-bottom: 6px; }
        .nv-metric-value { font-weight: 700; font-size: 2rem; text-align: center; }
        .nv-center-label { font-weight:600; text-align:center; color:#cfcfcf; padding-top:16px; }
        .nv-pill { display:inline-block; border-radius:9999px; padding: 3px 10px; font-weight:600; font-size: .8rem; color:#fff; }
        .nv-pill.green { background:#16a34a; }
        .nv-pill.red { background:#ef4444; }
        .nv-row-gap { height: 10px; }
        /* Round percentage bubbles */
        .nv-bubble { width: 100px; height: 100px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: 700; font-size: 1.6rem; color: #fff; margin: 6px auto; }
        .nv-bubble.teal { background:#0b7285; }
        .nv-bubble.purple { background:#7e22ce; }
        .nv-bubble.blue { background:#0b4f6c; }
        .nv-bubble.peach { background:#f2a777; }
        .nv-bubble.green { background:#16a34a; }
        .nv-bubble.pink { background:#d946ef; }
        .nv-bubble-label { text-align:center; font-weight:600; margin-top:6px; }
        /* Section cards — elevated, soft gradient, accent left bar */
        .nv-section {
          position: relative;
          border: 1px solid rgba(255,255,255,.10);
          border-left: 4px solid #7c3aed; /* accent */
          border-radius: 14px;
          padding: 16px 18px;
          background: linear-gradient(180deg, rgba(255,255,255,.06) 0%, rgba(255,255,255,.03) 100%);
          box-shadow: 0 10px 26px rgba(0,0,0,.28);
          backdrop-filter: blur(2px);
          margin: 16px 0 22px;
        }
        .nv-section:hover { box-shadow: 0 14px 30px rgba(0,0,0,.34); }
        .nv-section-title {
          font-weight: 800;
          font-size: 1.08rem;
          color: #eef;
          margin: 0 0 10px 0;
          letter-spacing: .2px;
          display: flex;
          align-items: center;
          gap: 10px;
        }
        .nv-section-title::before {
          content: "";
          display: inline-block;
          width: 10px; height: 10px;
          border-radius: 50%;
          background: #7c3aed;
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

# Activity-only data mode: do not load any CSV/Parquet here; rely on session_state or no-op
ONLY_ACTIVITY_DATA = True

# --- Load Data (from session or fallback to direct loading) ---
establishments = st.session_state.get('establishments', pd.DataFrame())
annual = st.session_state.get('annual', pd.DataFrame())
competitors = st.session_state.get('competitors', pd.DataFrame())
complications = st.session_state.get('complications', pd.DataFrame())
procedure_details = st.session_state.get('procedure_details', pd.DataFrame())
los_90 = st.session_state.get('los_90', pd.DataFrame())
clavien = st.session_state.get('clavien', pd.DataFrame())

# Fallback: Load essential data if session state is empty
if establishments.empty:
    try:
        from navira.csv_data_loader import load_establishments_from_csv
        establishments = load_establishments_from_csv()
        st.session_state.establishments = establishments
    except Exception as e:
        st.error(f"Could not load establishments data: {e}")
        st.stop()

# Navigation is now handled by the sidebar


# --- Safely check for selected hospital and data ---
# In limited mode, we force Avicenne selection upstream
if "selected_hospital_id" not in st.session_state or st.session_state.selected_hospital_id is None:
    if st.session_state.get('_limited_user'):
        st.session_state.selected_hospital_id = '930100037'
    else:
        st.warning("Please select a hospital from the Home page first.", icon="👈")
        st.stop()

# --- Load data and averages from session state ---
filtered_df = st.session_state.get('filtered_df', pd.DataFrame())
selected_hospital_id = st.session_state.selected_hospital_id
national_averages = st.session_state.get('national_averages', {})

# Fallback: compute national averages locally if missing (when landing directly here)
@st.cache_data(show_spinner=False)
def _compute_national_averages_fallback(annual_df: pd.DataFrame) -> dict:
    try:
        if annual_df is None or annual_df.empty:
            return {}
        df = annual_df.copy()
        # Keep hospitals with sufficient volume if column exists
        if 'total_procedures_year' in df.columns:
            eligible = df[df['total_procedures_year'] >= 25]
        else:
            eligible = df
        # Average per hospital across years for procedures and approaches
        avg = {}
        for col in ['SLE','BPG','ANN','REV','ABL','DBP','GVC','NDD','LAP','COE','ROB']:
            if col in eligible.columns:
                avg[col] = float(eligible.groupby('id')[col].mean().mean())
        # Total surgeries per period per hospital, then mean across hospitals
        if 'total_procedures_year' in eligible.columns:
            totals = eligible.groupby('id')['total_procedures_year'].sum()
            avg['total_procedures_period'] = float(totals.mean()) if not totals.empty else 0.0
        # Approach mix percentages
        total_approaches = sum(avg.get(c, 0) for c in ['LAP','COE','ROB'])
        avg['approaches_pct'] = {}
        if total_approaches > 0:
            for code, name in {'LAP':'Open Surgery','COE':'Coelioscopy','ROB':'Robotic'}.items():
                avg['approaches_pct'][name] = (avg.get(code, 0) / total_approaches) * 100
        return avg
    except Exception:
        return {}

if not national_averages:
    national_averages = _compute_national_averages_fallback(annual)
    st.session_state.national_averages = national_averages

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

# Establishment details and annual series (robust to missing data)
try:
    if establishments is None or establishments.empty or ('id' not in establishments.columns):
        est_row = pd.DataFrame()
    else:
        est_row = establishments[establishments['id'].astype(str) == str(selected_hospital_id)]
except Exception:
    est_row = pd.DataFrame()

if est_row.empty:
    # Fallback minimal details without blocking the page
    selected_hospital_details = pd.Series({
        'id': str(selected_hospital_id),
        'name': f"Hospital {selected_hospital_id}",
        'city': '',
        'code_postal': '',
        'adresse': '',
        'status': ''
    })
    selected_hospital_all_data = pd.DataFrame(columns=['annee', 'total_procedures_year'])
else:
    selected_hospital_details = est_row.iloc[0]
    try:
        if annual is not None and not annual.empty and ('id' in annual.columns):
            selected_hospital_all_data = annual[annual['id'].astype(str) == str(selected_hospital_id)]
        else:
            selected_hospital_all_data = pd.DataFrame(columns=['annee', 'total_procedures_year'])
    except Exception:
        selected_hospital_all_data = pd.DataFrame(columns=['annee', 'total_procedures_year'])

if selected_hospital_all_data.empty:
    # Create empty DataFrame with expected columns
    selected_hospital_all_data = pd.DataFrame(columns=['annee', 'total_procedures_year'])

# Do NOT load additional CSV complications here (Activity-only mode)
if complications is None or isinstance(complications, type(None)):
    complications = pd.DataFrame()

# Year helpers for dynamic 2025 inclusion (YTD)
try:
    # Try both column names for compatibility
    year_col = 'year' if 'year' in annual.columns else 'annee'
    _years_all = sorted(pd.to_numeric(annual.get(year_col, pd.Series(dtype=float)), errors='coerce').dropna().astype(int).unique().tolist())
    latest_year_activity = max([y for y in _years_all if y <= 2025]) if _years_all else 2024
except Exception:
    latest_year_activity = 2025
years_window = [y for y in _years_all if 2020 <= y <= latest_year_activity] if '_years_all' in locals() else list(range(2020, 2026))
is_ytd_2025 = (latest_year_activity == 2025)
ytd_suffix = " (YTD)" if is_ytd_2025 else ""

# --- (The rest of your dashboard page code follows here) ---
# I'm including the rest of the file for completeness.
st.title("📊 Hospital Details Dashboard")

# Hospital header with name and address
st.markdown(f"## 🏥 {selected_hospital_details['name']}")

# Address section
if 'adresse' in selected_hospital_details and pd.notna(selected_hospital_details['adresse']):
    # Format postal code as integer (remove decimals)
    postal = str(int(float(selected_hospital_details['code_postal']))) if pd.notna(selected_hospital_details.get('code_postal')) else ''
    address_line = f"📍 {selected_hospital_details['adresse']}, {postal} {selected_hospital_details['city']}"
    st.markdown(f"**Address:** {address_line}")
else:
    postal = str(int(float(selected_hospital_details['code_postal']))) if pd.notna(selected_hospital_details.get('code_postal')) else ''
    st.markdown(f"**Address:** {postal} {selected_hospital_details['city']}")

st.markdown("---")

# Hospital details in columns
col1, col2, col3 = st.columns(3)
col1.markdown(f"**City:** {selected_hospital_details['city']}")
col2.markdown(f"**Status:** {selected_hospital_details['status']}")
if 'Distance (km)' in selected_hospital_details:
    col3.markdown(f"**Distance:** {selected_hospital_details['Distance (km)']:.1f} km")
st.markdown("---")

# --- New SUMMARY (layout inspired by slide) ---
st.markdown("### Summary")

# Load data from new CSV sources for Summary
@st.cache_data(show_spinner=False)
def _load_summary_data():
    """Load all data needed for Summary section from new_data CSVs."""
    from pathlib import Path
    
    # Find new_data directory
    candidates = []
    try:
        candidates.append(Path.cwd() / "new_data")
    except Exception:
        pass
    try:
        candidates.append(Path(__file__).parent.parent / "new_data")
    except Exception:
        pass
    candidates.append(Path("/Users/alexdebelka/Downloads/navira/new_data"))
    
    base_dir = None
    for c in candidates:
        if c.is_dir():
            base_dir = c
            break
    
    if base_dir is None:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    
    # Load volume data
    try:
        vol_hop = pd.read_csv(base_dir / "ACTIVITY" / "TAB_VOL_HOP_YEAR.csv", dtype={'finessGeoDP': str})
        vol_hop['finessGeoDP'] = vol_hop['finessGeoDP'].astype(str).str.strip()
        vol_hop['annee'] = pd.to_numeric(vol_hop['annee'], errors='coerce')
        vol_hop['n'] = pd.to_numeric(vol_hop['n'], errors='coerce')
    except Exception:
        vol_hop = pd.DataFrame()
    
    # Load trend data
    try:
        trend_hop = pd.read_csv(base_dir / "ACTIVITY" / "TAB_TREND_HOP.csv", dtype={'finessGeoDP': str})
        trend_hop['finessGeoDP'] = trend_hop['finessGeoDP'].astype(str).str.strip()
        trend_hop['diff_pct'] = pd.to_numeric(trend_hop['diff_pct'], errors='coerce')
    except Exception:
        trend_hop = pd.DataFrame()
    
    # Load TCN data for procedure mix
    try:
        tcn_hop = pd.read_csv(base_dir / "ACTIVITY" / "TAB_TCN_HOP_12M.csv", dtype={'finessGeoDP': str})
        tcn_hop['finessGeoDP'] = tcn_hop['finessGeoDP'].astype(str).str.strip()
        tcn_hop['n'] = pd.to_numeric(tcn_hop.get('n', 0), errors='coerce')
    except Exception:
        tcn_hop = pd.DataFrame()
    
    # Load approach data (for robotic share bar)
    try:
        app_hop = pd.read_csv(base_dir / "ACTIVITY" / "TAB_APP_HOP_YEAR.csv", dtype={'finessGeoDP': str})
        app_hop['finessGeoDP'] = app_hop['finessGeoDP'].astype(str).str.strip()
        app_hop['annee'] = pd.to_numeric(app_hop.get('annee', 0), errors='coerce')
        app_hop['n'] = pd.to_numeric(app_hop.get('n', 0), errors='coerce')
    except Exception:
        app_hop = pd.DataFrame()
    
    # Load revisional data
    try:
        rev_hop = pd.read_csv(base_dir / "ACTIVITY" / "TAB_REV_HOP_12M.csv", dtype={'finessGeoDP': str})
        rev_hop['finessGeoDP'] = rev_hop['finessGeoDP'].astype(str).str.strip()
        rev_hop['PCT_rev'] = pd.to_numeric(rev_hop.get('PCT_rev', 0), errors='coerce')
    except Exception:
        rev_hop = pd.DataFrame()
    
    # Load complications data
    try:
        compl_hop = pd.read_csv(base_dir / "COMPLICATIONS" / "TAB_COMPL_HOP_ROLL12.csv", dtype={'finessGeoDP': str})
        compl_hop['finessGeoDP'] = compl_hop['finessGeoDP'].astype(str).str.strip()
        compl_hop['COMPL_pct'] = pd.to_numeric(compl_hop.get('COMPL_pct', 0), errors='coerce')
    except Exception:
        compl_hop = pd.DataFrame()
    
    return vol_hop, trend_hop, tcn_hop, app_hop, rev_hop, compl_hop

vol_hop_summary, trend_hop_summary, tcn_hop_summary, app_hop_summary, rev_hop_summary, compl_hop_summary = _load_summary_data()

# Calculate metrics from CSV data
# 1. Number of procedures 2021-2024
period_total = 0
if not vol_hop_summary.empty:
    hosp_vol = vol_hop_summary[vol_hop_summary['finessGeoDP'] == str(selected_hospital_id)]
    period_data = hosp_vol[(hosp_vol['annee'] >= 2021) & (hosp_vol['annee'] <= 2024)]
    period_total = int(period_data['n'].fillna(0).sum())

# 2. Number of procedures ongoing year (2025)
ongoing_total = 0
ongoing_year_display = 2025
if not vol_hop_summary.empty:
    hosp_vol = vol_hop_summary[vol_hop_summary['finessGeoDP'] == str(selected_hospital_id)]
    ongoing_data = hosp_vol[hosp_vol['annee'] == 2025]
    ongoing_total = int(ongoing_data['n'].fillna(0).sum())

# 3. Expected trend from TREND file
yoy_text = "—"
if not trend_hop_summary.empty:
    hosp_trend = trend_hop_summary[trend_hop_summary['finessGeoDP'] == str(selected_hospital_id)]
    if not hosp_trend.empty and 'diff_pct' in hosp_trend.columns:
        diff_val = hosp_trend.iloc[0]['diff_pct']
        if pd.notna(diff_val):
            yoy_text = f"{float(diff_val):+.1f}%"

# 4. Revisional rate from REV file
hospital_revision_pct = 0.0
if not rev_hop_summary.empty:
    hosp_rev = rev_hop_summary[rev_hop_summary['finessGeoDP'] == str(selected_hospital_id)]
    if not hosp_rev.empty and 'PCT_rev' in hosp_rev.columns:
        rev_val = hosp_rev.iloc[0]['PCT_rev']
        if pd.notna(rev_val):
            hospital_revision_pct = float(rev_val)

# 5. Complication rate from COMPL file
complication_rate = None
if not compl_hop_summary.empty:
    hosp_compl = compl_hop_summary[compl_hop_summary['finessGeoDP'] == str(selected_hospital_id)]
    if not hosp_compl.empty and 'COMPL_pct' in hosp_compl.columns:
        compl_val = hosp_compl.iloc[0]['COMPL_pct']
        if pd.notna(compl_val):
            complication_rate = float(compl_val)

# First row: Left labels + three headline metrics
left, m1, m2, m3 = st.columns([1.3, 1, 1, 1.05])
with left:
    st.markdown("#### Labels & Affiliations")
    
    # University/Academic status
    if selected_hospital_details.get('university') == 1:
        st.success("🎓 University Hospital")
    else:
        st.info("➖ No University Affiliation")
    
    # SOFFCO label (French Bariatric Society)
    if selected_hospital_details.get('LAB_SOFFCO') == 1:
        st.success("✅ Centre of Excellence (SOFFCO)")
    else:
        st.info("➖ No SOFFCO Centre Label")
    
    # Health Ministry label
    if selected_hospital_details.get('cso') == 1:
        st.success("✅ Centre of Excellence (Health Ministry)")
    else:
        st.info("➖ No Health Ministry Centre Label")

with m1:
    st.metric(label="Nb procedures (2021–2024)", value=f"{period_total:,}")
with m2:
    _suffix = f"{ongoing_year_display}"
    if ongoing_year_display == 2025:
        _suffix = f"{ongoing_year_display} — until July"
    st.metric(label=f"Nb procedures ongoing year ({_suffix})", value=f"{ongoing_total:,}")
with m3:
    _suffix_t = f"{ongoing_year_display}"
    if ongoing_year_display == 2025:
        _suffix_t = f"{ongoing_year_display} — until July"
    st.metric(label=f"Expected trend for ongoing year ({_suffix_t})", value=yoy_text)

# Second row: Type of procedures, robotic share, rates
# Second row: Type of procedures, robotic share, rates
c_donut, c_robot, c_rates = st.columns([1.2, 1.2, 1.5])

with c_donut:
    st.markdown("##### Type of procedures")
    # Use TCN data for procedure casemix (last 12 months)
    if not tcn_hop_summary.empty and 'baria_t' in tcn_hop_summary.columns:
        hosp_tcn = tcn_hop_summary[tcn_hop_summary['finessGeoDP'] == str(selected_hospital_id)]
        if not hosp_tcn.empty:
            # Map to three categories
            PROC_MAP = {'SLE': 'Sleeve', 'BPG': 'Gastric Bypass'}
            totals = {'Sleeve': 0.0, 'Gastric Bypass': 0.0, 'Other': 0.0}
            for _, r in hosp_tcn.iterrows():
                code = str(r['baria_t']).upper().strip()
                label = PROC_MAP.get(code, 'Other')
                totals[label] += float(r.get('n', 0))
            
            data_rows = [{'Procedure': k, 'Count': v} for k, v in totals.items() if v > 0]
            if data_rows:
                d = pd.DataFrame(data_rows)
                fig = px.pie(d, values='Count', names='Procedure', hole=0.45, color='Procedure', 
                            color_discrete_map={'Sleeve':'#1f77b4','Gastric Bypass':'#ff7f0e','Other':'#2ca02c'})
                fig.update_traces(textposition='inside', textinfo='percent+label')
                fig.update_layout(height=240, margin=dict(l=10, r=10, t=10, b=10), showlegend=False, 
                                paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                st.plotly_chart(fig, use_container_width=True, key=f"summary_proc_pie_{selected_hospital_id}")
            else:
                st.info("No procedure data available.")
        else:
            st.info("No procedure data for this hospital.")
    else:
        st.info("Procedure mix unavailable.")

with c_robot:
    st.markdown("##### Robotic share")
    # Use APP data for approach shares (latest year with data - 2024)
    if not app_hop_summary.empty and 'vda' in app_hop_summary.columns:
        hosp_app = app_hop_summary[app_hop_summary['finessGeoDP'] == str(selected_hospital_id)]
        if not hosp_app.empty:
            latest_yr = 2024 if (hosp_app['annee'] == 2024).any() else hosp_app['annee'].max()
            hosp_app_yr = hosp_app[hosp_app['annee'] == latest_yr]
            
            # Calculate shares by approach
            totals = {}
            for _, r in hosp_app_yr.iterrows():
                approach = str(r.get('vda', '')).upper().strip()
                count = float(r.get('n', 0))
                totals[approach] = totals.get(approach, 0.0) + count
            
            total_all = sum(totals.values())
            if total_all > 0:
                # Map to display names
                approach_map = {'ROB': 'Robotic', 'COE': 'Coelioscopy', 'LAP': 'Open Surgery'}
                df_bar = pd.DataFrame([
                    {'Year': str(int(latest_yr)), 'Approach': approach_map.get(k, k), 'Share': (v / total_all * 100)}
                    for k, v in totals.items()
                ])
                figb = px.bar(df_bar, x='Year', y='Share', color='Approach', barmode='stack', 
                             color_discrete_map={'Open Surgery':'#A23B72','Coelioscopy':'#2E86AB','Robotic':'#F7931E'},
                             category_orders={'Approach': ['Robotic', 'Coelioscopy', 'Open Surgery']})
                figb.update_layout(height=240, yaxis=dict(range=[0,100], title=''), xaxis_title=None, 
                                 paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                figb.update_traces(hovertemplate='Approach: %{fullData.name}<br>%{y:.1f}%<extra></extra>')
                st.plotly_chart(figb, use_container_width=True, key=f"summary_rob_bar_{selected_hospital_id}")
            else:
                st.info("No approach data for selected year.")
        else:
            st.info("No approach data for this hospital.")
    else:
        st.info("Robotic share unavailable.")

with c_rates:
    r1, r2 = st.columns(2)
    with r1:
        st.markdown(f"<div class='nv-bubble teal'>{hospital_revision_pct:.0f}%</div>", unsafe_allow_html=True)
        st.markdown("<div class='nv-bubble-label'>Revisional rate</div>", unsafe_allow_html=True)
    with r2:
        pct = f"{complication_rate:.1f}%" if complication_rate is not None else "N/A"
        st.markdown(f"<div class='nv-bubble purple'>{pct}</div>", unsafe_allow_html=True)
        st.markdown("<div class='nv-bubble-label'>Complication rate</div>", unsafe_allow_html=True)


# --- New Tabbed Layout: Activity, Complications, Geography ---
st.markdown("---")
st.markdown(
    """
    <style>
      /* Make navigation tabs much bigger and more prominent */
      div[data-testid="stTabs"] {
        margin: 20px 0 30px 0;
      }
      div[data-testid="stTabs"] div[role="tablist"] { 
        gap: 20px; 
        border-bottom: 3px solid #808080; 
        padding-bottom: 5px;
      }
      div[data-testid="stTabs"] button[role="tab"] {
        font-size: 1.1rem !important;
        font-weight: 600 !important;
        padding: 20px 35px !important;
        margin: 0 5px !important;
        border-radius: 12px 12px 0 0 !important;
        border: none !important;
        background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%) !important;
        color: #495057 !important;
        transition: all 0.3s ease !important;
        box-shadow: 0 2px 8px rgba(0,0,0,0.1) !important;
      }
      div[data-testid="stTabs"] button[role="tab"]:hover {
        background: linear-gradient(135deg, #e9ecef 0%, #dee2e6 100%) !important;
        transform: translateY(-2px) !important;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15) !important;
      }
      div[data-testid="stTabs"] button[role="tab"][aria-selected="true"] {
        background: linear-gradient(135deg, #007bff 0%, #0056b3 100%) !important;
        color: white !important;
        font-weight: 700 !important;
        box-shadow: 0 4px 15px rgba(0,123,255,0.3) !important;
      }
      div[data-testid="stTabs"] button[role="tab"] p { 
        font-size: 1.8rem !important;
        font-weight: 600 !important;
        margin: 0 !important;
      }
      /* Make the active tab indicator more prominent */
      div[data-testid="stTabs"] button[role="tab"][aria-selected="true"]::after {
        content: '';
        position: absolute;
        bottom: -8px;
        left: 50%;
        transform: translateX(-50%);
        width: 80%;
        height: 4px;
        background: #007bff;
        border-radius: 2px;
        box-shadow: 0 2px 8px rgba(0,123,255,0.4);
      }
    </style>
    """,
    unsafe_allow_html=True,
)
user_ctx = st.session_state.get('user') or {}
username_ctx = (user_ctx or {}).get('username', '')
_limited = bool(st.session_state.get('_limited_user'))
# Pilot override: enable Geography for pilot users even if limited
pilot_users = ['andrea.lazzati', 'federica.papini', 'sergio.carandina', 'claire.blanchard', 'thomas.auguste', 'laurent.genser']
_pilot_geo_override = username_ctx in pilot_users
show_geography = ((not _limited) or _pilot_geo_override) and (not ONLY_ACTIVITY_DATA)

if show_geography:
    tab_activity, tab_complications, tab_geo = st.tabs(["📈 Activity", "🧪 Complications", "🗺️ Geography"])
else:
    tab_activity, tab_complications = st.tabs(["📈 Activity", "🧪 Complications"])  # Hide geography for limited


with tab_activity:
    render_activity_section(str(selected_hospital_id))
    
    # Activity section rendered via sections/activity.py


with tab_complications:
    render_complications_section(str(selected_hospital_id))

if show_geography:
    with tab_geo:
        st.subheader("Recruitment Zone and Competitors (Top-5 Choropleths)")
        
        # UI Controls
        col1, col2 = st.columns(2)
        with col1:
            allocation = "even_split"
        with col2:
            max_competitors = st.slider("Max Competitors", 1, 5, 5, help="Number of competitor layers to show")
        
        # Import the new functionality
        try:
            from navira.map_renderer import create_recruitment_map, render_map_diagnostics
            from navira.competitors import get_competitor_names
            from navira.geo import get_geojson_summary, load_communes_geojson
            
            # Prepare hospital info
            hospital_info = {
                'name': selected_hospital_details.get('name', 'Unknown Hospital'),
                'latitude': selected_hospital_details.get('latitude'),
                'longitude': selected_hospital_details.get('longitude')
            }
            
            # Create the recruitment map
            with st.spinner("🗺️ Generating recruitment zone choropleths..."):
                recruitment_map, diagnostics = create_recruitment_map(
                    hospital_finess=str(selected_hospital_id),
                    hospital_info=hospital_info,
                    establishments_df=establishments,
                    allocation=allocation,
                    max_competitors=max_competitors
                )
            
            # Render the map
            st.markdown("### 🗺️ Interactive Recruitment Zone Map")
            
            try:
                map_data = st_folium(
                    recruitment_map,
                    width=None,
                    height=600,
                    key="recruitment_choropleth_map",
                    use_container_width=True
                )
            except Exception as e:
                st.error(f"Error rendering choropleth map: {e}")
                st.info("Falling back to coordinate display...")
                st.markdown(f"""
                **Hospital Location:**
                - **Name:** {hospital_info['name']}
                - **Coordinates:** {hospital_info.get('latitude', 'N/A')}, {hospital_info.get('longitude', 'N/A')}
                """)
                
        except ImportError as e:
            st.error(f"Import error: {e}")
            st.info("Using fallback simple map...")
            
            # Fallback to simple map if new modules not available
            try:
                center = [float(selected_hospital_details.get('latitude')), float(selected_hospital_details.get('longitude'))]
                if any(pd.isna(center)):
                    raise ValueError
            except Exception:
                center = [48.8566, 2.3522]
            
            simple_map = folium.Map(location=center, zoom_start=10, tiles="OpenStreetMap")
            folium.Marker(
                location=center,
                popup=f"<b>{selected_hospital_details.get('name', 'Selected Hospital')}</b>",
                icon=folium.Icon(color='red', icon='hospital-o', prefix='fa')
            ).add_to(simple_map)
            
            try:
                st_folium(simple_map, width=None, height=500, key="fallback_simple_map", use_container_width=True)
            except Exception as e:
                st.error(f"Fallback map also failed: {e}")
        
        # Competitors list
        st.markdown("#### Nearby/Competitor Hospitals")
        hosp_competitors = competitors[competitors['hospital_id'] == str(selected_hospital_id)]
        if not hosp_competitors.empty:
            comp_named = hosp_competitors.merge(establishments[['id','name','city','status']], left_on='competitor_id', right_on='id', how='left')
            comp_named = comp_named.sort_values('competitor_patients', ascending=False)
            for _, r in comp_named.head(5).iterrows():
                c1, c2, c3 = st.columns([3,2,1])
                c1.markdown(f"**{r.get('name','Unknown')}**")
                c1.caption(f"📍 {r.get('city','')} ")
                c2.markdown(r.get('status',''))
                c3.metric("Patients", f"{int(r.get('competitor_patients',0)):,}")
        else:
            st.info("No competitor data available.")

# Stop here to avoid rendering legacy sections below while we transition to the tabbed layout
st.stop()
