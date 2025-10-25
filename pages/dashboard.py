# pages/Hospital_Dashboard.py
import streamlit as st
import pandas as pd
import altair as alt
import numpy as np
import folium
from folium.plugins import HeatMap
import os
import requests
import branca.colormap as cm
from navira.competitors import (
    get_top_competitors,
    get_competitor_names,
    competitor_choropleth_df
)
from navira.data_loaders import build_postal_to_insee_mapping
from navira.geo import load_communes_geojson, detect_insee_key
from streamlit_folium import st_folium
import plotly.express as px
import plotly.graph_objects as go
from navira.data_loader import get_dataframes, get_all_dataframes
from auth_wrapper import add_auth_to_page
from navigation_utils import handle_navigation_request
from typing import List, Optional, Tuple, Dict
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
    los_90 = all_data.get('los_90', pd.DataFrame())
    clavien = all_data.get('clavien', pd.DataFrame())
except Exception:
    st.error("Parquet data not found. Please run: make parquet")
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

# Establishment details and annual series
est_row = establishments[establishments['id'] == str(selected_hospital_id)]
if est_row.empty:
    st.error("Could not find data for the selected hospital.")
    st.stop()
selected_hospital_details = est_row.iloc[0]
selected_hospital_all_data = annual[annual['id'] == str(selected_hospital_id)]

# Debug: Check data structure
if selected_hospital_all_data.empty:
    st.warning(f"No annual data found for hospital {selected_hospital_id}")
    # Create empty DataFrame with expected columns
    selected_hospital_all_data = pd.DataFrame(columns=['annee', 'total_procedures_year'])

# Year helpers for dynamic 2025 inclusion (YTD)
try:
    _years_all = sorted(pd.to_numeric(annual.get('annee', pd.Series(dtype=float)), errors='coerce').dropna().astype(int).unique().tolist())
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
    address_line = f"📍 {selected_hospital_details['adresse']}, {selected_hospital_details['code_postal']} {selected_hospital_details['city']}"
    st.markdown(f"**Address:** {address_line}")
else:
    st.markdown(f"**Address:** {selected_hospital_details['code_postal']} {selected_hospital_details['city']}")

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

# Helper to load monthly data for YoY estimate (YTD)
@st.cache_data(show_spinner=False)
def _load_monthly_volumes_summary(path: str = "data/export_TAB_VOL_MOIS_TCN_HOP.csv", cache_buster: str = "") -> pd.DataFrame:
    try:
        df = pd.read_csv(path, dtype={'finessGeoDP': str, 'annee': int, 'mois': int})
        df['finessGeoDP'] = df['finessGeoDP'].astype(str).str.strip()
        return df
    except Exception:
        return pd.DataFrame()

# Read VDA file that includes ongoing year (e.g., 2025) totals and approach split
@st.cache_data(show_spinner=False)
def _load_vda_year_totals_summary(path: str = "data/export_TAB_VDA_HOP.csv", cache_buster: str = "") -> pd.DataFrame:
    try:
        df = pd.read_csv(path, dtype={'finessGeoDP': str, 'annee': int})
        df['finessGeoDP'] = df['finessGeoDP'].astype(str).str.strip()
        # Ensure numeric
        for c in ['VOL','TOT','PCT']:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors='coerce')
        return df
    except Exception:
        return pd.DataFrame()

# Core aggregates
if 'total_procedures_year' in selected_hospital_all_data.columns:
    total_proc_hospital = float(selected_hospital_all_data['total_procedures_year'].sum())
else:
    total_proc_hospital = 0.0
total_rev_hospital = int(selected_hospital_details.get('revision_surgeries_n', 0))
hospital_revision_pct = (total_rev_hospital / total_proc_hospital) * 100 if total_proc_hospital > 0 else 0.0

# Period totals (2021–2024)
if 'annee' in selected_hospital_all_data.columns:
    _period_mask = (selected_hospital_all_data['annee'] >= 2021) & (selected_hospital_all_data['annee'] <= 2024)
    period_21_24 = selected_hospital_all_data[_period_mask]
else:
    period_21_24 = selected_hospital_all_data
if 'total_procedures_year' in period_21_24.columns:
    period_total = int(pd.to_numeric(period_21_24['total_procedures_year'], errors='coerce').fillna(0).sum())
else:
    period_total = 0

# Ongoing year total
ongoing_year = int(latest_year_activity)
if 'annee' in selected_hospital_all_data.columns:
    ongoing_data = selected_hospital_all_data[selected_hospital_all_data['annee'] == ongoing_year]
    if 'total_procedures_year' in ongoing_data.columns:
        ongoing_total = int(pd.to_numeric(ongoing_data['total_procedures_year'], errors='coerce').fillna(0).sum())
    else:
        ongoing_total = 0
else:
    ongoing_total = 0
ongoing_year_display = int(ongoing_year)

# Expected trend (YoY YTD vs same months last year)
yoy_text = "—"
try:
    mv = _load_monthly_volumes_summary(cache_buster=str(_build_id or ""))
    if not mv.empty:
        hosp_mv = mv[mv['finessGeoDP'] == str(selected_hospital_id)]
        if not hosp_mv.empty and (ongoing_year in hosp_mv['annee'].unique()) and ((ongoing_year-1) in hosp_mv['annee'].unique()):
            last_m = int(hosp_mv[hosp_mv['annee'] == ongoing_year]['mois'].max())
            cur = pd.to_numeric(hosp_mv[(hosp_mv['annee'] == ongoing_year) & (hosp_mv['mois'] <= last_m)]['TOT_month'], errors='coerce').fillna(0).sum()
            prev = pd.to_numeric(hosp_mv[(hosp_mv['annee'] == ongoing_year-1) & (hosp_mv['mois'] <= last_m)]['TOT_month'], errors='coerce').fillna(0).sum()
            if prev > 0:
                yoy = (cur / prev - 1.0) * 100.0
                yoy_text = f"{yoy:+.0f}%"
except Exception:
    pass

# Override ongoing year metrics using VDA (includes 2025)
try:
    vda = _load_vda_year_totals_summary(cache_buster=str(_build_id or ""))
    if not vda.empty:
        hosp_vda = vda[vda['finessGeoDP'] == str(selected_hospital_id)].copy()
        if not hosp_vda.empty:
            # Aggregate to year totals using TOT (once per year; take max to avoid duplicates across approaches)
            year_totals = hosp_vda.groupby('annee', as_index=False)['TOT'].max().dropna()
            if (year_totals['annee'] == 2025).any():
                ongoing_year_display = 2025
                ongoing_total = int(pd.to_numeric(year_totals[year_totals['annee'] == 2025]['TOT'], errors='coerce').fillna(0).iloc[0])
                if (year_totals['annee'] == 2024).any():
                    prev_total = float(pd.to_numeric(year_totals[year_totals['annee'] == 2024]['TOT'], errors='coerce').fillna(0).iloc[0])
                    if prev_total > 0:
                        yoy = (ongoing_total / prev_total - 1.0) * 100.0
                        yoy_text = f"{yoy:+.0f}%"
except Exception:
    pass

# Prefer YTD trend using monthly data: compare 2025 YTD to 2024 YTD through same month
try:
    mv_pref = _load_monthly_volumes_summary()
    if not mv_pref.empty:
        mv_h = mv_pref[mv_pref['finessGeoDP'] == str(selected_hospital_id)]
        if not mv_h.empty and (2025 in mv_h['annee'].unique()) and (2024 in mv_h['annee'].unique()):
            m_cut = int(pd.to_numeric(mv_h[mv_h['annee'] == 2025]['mois'], errors='coerce').max())
            cur = pd.to_numeric(mv_h[(mv_h['annee'] == 2025) & (mv_h['mois'] <= m_cut)]['TOT_month'], errors='coerce').fillna(0).sum()
            prev = pd.to_numeric(mv_h[(mv_h['annee'] == 2024) & (mv_h['mois'] <= m_cut)]['TOT_month'], errors='coerce').fillna(0).sum()
            if prev > 0:
                yoy_monthly = (cur / prev - 1.0) * 100.0
                yoy_text = f"{yoy_monthly:+.0f}%"
except Exception:
    pass

# First row: Left labels + three headline metrics
left, m1, m2, m3 = st.columns([1.3, 1, 1, 1.05])
with left:
    st.markdown("#### Labels & Affiliations")
    if selected_hospital_details.get('university') == 1:
        st.success("🎓 University Hospital")
    else:
        st.warning("➖ No University Affiliation")
    if selected_hospital_details.get('LAB_SOFFCO') == 1:
        st.success("✅ Centre of Excellence (SOFFCO)")
    else:
        st.warning("➖ No SOFFCO Centre Label")
    if selected_hospital_details.get('cso') == 1:
        st.success("✅ Centre of Excellence (Health Ministry)")
    else:
        st.warning("➖ No Health Ministry Centre Label")

with m1:
    st.metric(label="Number of procedures (2021–2024)", value=f"{period_total:,}")
with m2:
    _suffix = f"{ongoing_year_display}"
    if ongoing_year_display == 2025:
        _suffix = f"{ongoing_year_display} — until July"
    st.metric(label=f"Number procedures ongoing year ({_suffix})", value=f"{ongoing_total:,}")
with m3:
    _suffix_t = f"{ongoing_year_display}"
    if ongoing_year_display == 2025:
        _suffix_t = f"{ongoing_year_display} — until July"
    st.metric(label=f"Expected trend for ongoing year ({_suffix_t})", value=yoy_text)

# Second row: spacer under labels + donut, single-year robotic share bar, and two bubbles
c_donut, c_robot, c_rates = st.columns([1.2, 1.2, 1.5])

with c_donut:
    try:
        st.markdown("##### Type of procedures")
        proc_cols_present = [c for c in BARIATRIC_PROCEDURE_NAMES.keys() if c in selected_hospital_all_data.columns]
        # Use 2021–2024 window to match headline period
        if 'annee' in selected_hospital_all_data.columns:
            dfp = selected_hospital_all_data[(selected_hospital_all_data['annee'] >= 2021) & (selected_hospital_all_data['annee'] <= 2024)]
        else:
            dfp = selected_hospital_all_data
        sleeve_total = int(pd.to_numeric(dfp.get('SLE', 0), errors='coerce').fillna(0).sum()) if 'SLE' in proc_cols_present else 0
        bypass_total = int(pd.to_numeric(dfp.get('BPG', 0), errors='coerce').fillna(0).sum()) if 'BPG' in proc_cols_present else 0
        other_codes = [c for c in proc_cols_present if c not in ['SLE', 'BPG']]
        other_total = int(pd.to_numeric(dfp[other_codes].sum().sum(), errors='coerce')) if other_codes else 0
        data_rows = []
        if sleeve_total > 0: data_rows.append({'Procedure': 'Sleeve', 'Count': sleeve_total})
        if bypass_total > 0: data_rows.append({'Procedure': 'Gastric Bypass', 'Count': bypass_total})
        if other_total > 0: data_rows.append({'Procedure': 'Other', 'Count': other_total})
        if data_rows:
            d = pd.DataFrame(data_rows)
            fig = px.pie(d, values='Count', names='Procedure', hole=0.45, color='Procedure', color_discrete_map={'Sleeve':'#1f77b4','Gastric Bypass':'#ff7f0e','Other':'#2ca02c'})
            fig.update_traces(textposition='inside', textinfo='percent+label')
            fig.update_layout(height=240, margin=dict(l=10, r=10, t=10, b=10), showlegend=False, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No procedure data available.")
    except Exception:
        st.info("Procedure mix unavailable.")

with c_robot:
    try:
        st.markdown("##### Robotic share")
        bar_year = 2024 if is_ytd_2025 else latest_year_activity
        if 'annee' in selected_hospital_all_data.columns:
            row = selected_hospital_all_data[selected_hospital_all_data['annee'] == bar_year]
        else:
            row = selected_hospital_all_data
        if not row.empty:
            v_lap = float(pd.to_numeric(row.get('LAP', 0), errors='coerce').fillna(0).sum())
            v_coe = float(pd.to_numeric(row.get('COE', 0), errors='coerce').fillna(0).sum())
            v_rob = float(pd.to_numeric(row.get('ROB', 0), errors='coerce').fillna(0).sum())
            total = max(1.0, v_lap + v_coe + v_rob)
            df_bar = pd.DataFrame({
                'Year': [str(bar_year)]*3,
                'Approach': ['Open Surgery','Coelioscopy','Robotic'],
                'Share': [v_lap/total*100, v_coe/total*100, v_rob/total*100]
            })
            figb = px.bar(df_bar, x='Year', y='Share', color='Approach', barmode='stack', color_discrete_map={'Open Surgery':'#A23B72','Coelioscopy':'#2E86AB','Robotic':'#F7931E'})
            figb.update_layout(height=240, yaxis=dict(range=[0,100], title=''), xaxis_title=None, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
            figb.update_traces(hovertemplate='Approach: %{fullData.name}<br>%{y:.1f}%<extra></extra>')
            st.plotly_chart(figb, use_container_width=True)
        else:
            st.info("No approach data for selected year.")
    except Exception:
        st.info("Robotic share unavailable.")

with c_rates:
    try:
        r1, r2 = st.columns(2)
        with r1:
            st.markdown(f"<div class='nv-bubble teal'>{hospital_revision_pct:.0f}%</div>", unsafe_allow_html=True)
            st.markdown("<div class='nv-bubble-label'>Revisional rate</div>", unsafe_allow_html=True)
        with r2:
            comp_df = _get_hospital_complications(complications, str(selected_hospital_id))
            comp_rate = None
            if not comp_df.empty:
                if 'quarter_date' in comp_df.columns:
                    comp_df = comp_df.dropna(subset=['quarter_date']).copy()
                    comp_df['year'] = comp_df['quarter_date'].dt.year
                if 'year' in comp_df.columns:
                    sub = comp_df[(comp_df['year'] >= 2021) & (comp_df['year'] <= 2024)]
                else:
                    sub = comp_df
                if {'complications_count','procedures_count'}.issubset(set(sub.columns)):
                    num = pd.to_numeric(sub['complications_count'], errors='coerce').fillna(0).sum()
                    den = pd.to_numeric(sub['procedures_count'], errors='coerce').fillna(0).sum()
                    if den > 0:
                        comp_rate = float(num/den*100.0)
            pct = f"{comp_rate:.1f}%" if comp_rate is not None else "N/A"
            st.markdown(f"<div class='nv-bubble purple'>{pct}</div>", unsafe_allow_html=True)
            st.markdown("<div class='nv-bubble-label'>Complication rate</div>", unsafe_allow_html=True)
    except Exception:
        pass


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
# Pilot override: enable Geography for pilot user even if limited
_pilot_geo_override = username_ctx == 'andrea.lazzati'
show_geography = (not _limited) or _pilot_geo_override

if show_geography:
    tab_activity, tab_complications, tab_geo = st.tabs(["📈 Activity", "🧪 Complications", "🗺️ Geography"])
else:
    tab_activity, tab_complications = st.tabs(["📈 Activity", "🧪 Complications"])  # Hide geography for limited

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
    # Show YTD note and available years for quick diagnostics
    try:
        if is_ytd_2025:
            st.caption("Note: 2025 figures are year‑to‑date through July.")
        yrs_avail = sorted(pd.to_numeric(selected_hospital_all_data.get('annee', pd.Series(dtype=float)), errors='coerce').dropna().astype(int).unique().tolist())
        if yrs_avail:
            st.caption(f"Available years for this hospital: {yrs_avail[0]}–{yrs_avail[-1]}")
            if 2025 not in yrs_avail and is_ytd_2025:
                st.info("2025 activity is not present in the current dataset. If you recently added 2025 activity CSVs, please rebuild parquet with: make parquet, then reload.")
    except Exception:
        pass
    
    # Load monthly volume data helper function
    @st.cache_data(show_spinner=False)
    def _load_monthly_volumes(path: str = "data/export_TAB_VOL_MOIS_TCN_HOP.csv") -> pd.DataFrame:
        try:
            df = pd.read_csv(path, dtype={'finessGeoDP': str, 'annee': int, 'mois': int})
            df['finessGeoDP'] = df['finessGeoDP'].astype(str).str.strip()
            return df
        except Exception:
            return pd.DataFrame()
    
    # Total surgeries and quick mix charts (MOVED TO TOP)
    col1, col2 = st.columns([2, 1])  # Hospital graphs larger (2), National graphs smaller (1)
    
    # with col1:
    #     # Combined chart: Total Surgeries line + Procedure Mix bars
    #     st.markdown("#### Hospital: Total Surgeries & Procedure Mix")
        
    #     # Load monthly volume data for more granular visualization
    #     monthly_vol = _load_monthly_volumes()
        
    #     # Get procedure data for the combined chart - Filter out 2020
    #     proc_codes = [c for c in BARIATRIC_PROCEDURE_NAMES.keys() if c in selected_hospital_all_data.columns]
    #     hosp_year = selected_hospital_all_data[['annee','total_procedures_year']].dropna()
    #     hosp_year = hosp_year[hosp_year['annee'] > 2020]  # Remove 2020 data
        
    #     if not hosp_year.empty and proc_codes:
    #         # Use monthly volume data if available, otherwise fall back to annual data
    #         if not monthly_vol.empty and 'finessGeoDP' in monthly_vol.columns and 'baria_t' in monthly_vol.columns:
    #             hosp_monthly_vol = monthly_vol[monthly_vol['finessGeoDP'] == str(selected_hospital_id)].copy()
    #             hosp_monthly_vol = hosp_monthly_vol[hosp_monthly_vol['annee'] > 2020]  # Filter out 2020
                
    #             if not hosp_monthly_vol.empty:
    #                 # Aggregate monthly data by year and procedure type
    #                 proc_long = []
    #                 for year in sorted(hosp_monthly_vol['annee'].unique()):
    #                     year_data = hosp_monthly_vol[hosp_monthly_vol['annee'] == year]
    #                     # Map baria_t codes to our display names
    #                     sleeve_total = year_data[year_data['baria_t'] == 'SLE']['TOT_year_tcn'].iloc[0] if not year_data[year_data['baria_t'] == 'SLE'].empty else 0
    #                     bypass_total = year_data[year_data['baria_t'] == 'BPG']['TOT_year_tcn'].iloc[0] if not year_data[year_data['baria_t'] == 'BPG'].empty else 0
    #                     # Other procedures
    #                     other_codes = year_data[~year_data['baria_t'].isin(['SLE', 'BPG'])]
    #                     other_total = other_codes['TOT_year_tcn'].sum() if not other_codes.empty else 0
                        
    #                     total = max(1, sleeve_total + bypass_total + other_total)
    #                     for label, val in [("Sleeve", sleeve_total), ("Gastric Bypass", bypass_total), ("Other", other_total)]:
    #                         proc_long.append({'annee': int(year), 'Procedures': label, 'Share': val / total * 100})
    #                 pl = pd.DataFrame(proc_long)
    #             else:
    #                 # Fallback to annual data
    #                 proc_df = selected_hospital_all_data[selected_hospital_all_data['annee'] > 2020][['annee']+proc_codes].copy()
    #                 proc_long = []
    #                 for _, r in proc_df.iterrows():
    #                     total = max(1, sum(r[c] for c in proc_codes))
    #                     sleeve = r.get('SLE',0); bypass = r.get('BPG',0)
    #                     other = total - sleeve - bypass
    #                     for label,val in [("Sleeve",sleeve),("Gastric Bypass",bypass),("Other",other)]:
    #                         proc_long.append({'annee':int(r['annee']),'Procedures':label,'Share':val/total*100})
    #                 pl = pd.DataFrame(proc_long)
    #         else:
    #             # Fallback to annual data
    #             proc_df = selected_hospital_all_data[selected_hospital_all_data['annee'] > 2020][['annee']+proc_codes].copy()
    #             proc_long = []
    #             for _, r in proc_df.iterrows():
    #                 total = max(1, sum(r[c] for c in proc_codes))
    #                 sleeve = r.get('SLE',0); bypass = r.get('BPG',0)
    #                 other = total - sleeve - bypass
    #                 for label,val in [("Sleeve",sleeve),("Gastric Bypass",bypass),("Other",other)]:
    #                     proc_long.append({'annee':int(r['annee']),'Procedures':label,'Share':val/total*100})
    #             pl = pd.DataFrame(proc_long)
            
    #         if not pl.empty:
    #             # Create the combined chart
    #             fig = go.Figure()
                
    #             # Add stacked bar chart for procedure mix with different colors for 2025
    #             colors_regular = {'Sleeve': '#FF6B6B', 'Gastric Bypass': '#4ECDC4', 'Other': '#FFE66D'}  # Coral, Teal, Yellow
    #             colors_2025 = {'Sleeve': '#C92A2A', 'Gastric Bypass': '#0C8599', 'Other': '#E8B923'}  # Darker/more saturated for 2025
                
    #             for procedure in pl['Procedures'].unique():
    #                 data = pl[pl['Procedures'] == procedure]
    #                 # Split data into 2025 and non-2025
    #                 data_before_2025 = data[data['annee'] < 2025]
    #                 data_2025 = data[data['annee'] == 2025]
                    
    #                 # Add bars for years before 2025
    #                 if not data_before_2025.empty:
    #                     fig.add_trace(go.Bar(
    #                         x=data_before_2025['annee'],
    #                         y=data_before_2025['Share'],
    #                         name=procedure,
    #                         marker_color=colors_regular.get(procedure, '#cccccc'),
    #                         yaxis='y',
    #                         opacity=0.7,
    #                         legendgroup=procedure,
    #                         showlegend=True
    #                     ))
                    
    #                 # Add bars for 2025 with different color
    #                 if not data_2025.empty:
    #                     fig.add_trace(go.Bar(
    #                         x=data_2025['annee'],
    #                         y=data_2025['Share'],
    #                         name=f"{procedure} (2025 YTD)",
    #                         marker_color=colors_2025.get(procedure, '#888888'),
    #                         yaxis='y',
    #                         opacity=0.85,
    #                         legendgroup=procedure,
    #                         showlegend=True
    #                     ))
                
    #             # Add line chart for total surgeries using annual data (on secondary y-axis)
    #             hosp_year_clean = hosp_year.dropna()
    #             fig.add_trace(go.Scatter(
    #                 x=hosp_year_clean['annee'],
    #                 y=hosp_year_clean['total_procedures_year'],
    #                 mode='lines+markers',
    #                 name='Total Surgeries',
    #                 line=dict(color='#961316', width=4),
    #                 marker=dict(size=8, color='#961316'),
    #                 yaxis='y2',
    #                 hovertemplate='<b>Total Surgeries</b><br>Year: %{x}<br>Count: %{y}<extra></extra>'
    #             ))
                
    #             # Update layout with dual y-axes
    #             max_y2 = max(hosp_year_clean['total_procedures_year']) * 1.1 if not hosp_year_clean.empty else 100
    #             fig.update_layout(
    #                 height=450,
    #                 plot_bgcolor='rgba(0,0,0,0)',
    #                 paper_bgcolor='rgba(0,0,0,0)',
    #                 barmode='stack',
    #                 title='Total Surgeries & Procedure Mix Overlay',
    #                 xaxis_title='Year',
    #                 yaxis=dict(
    #                     title='Procedure Share (%)',
    #                     side='left',
    #                     range=[0, 100]
    #                 ),
    #                 yaxis2=dict(
    #                     title='Total Surgeries Count',
    #                     side='right',
    #                     overlaying='y',
    #                     range=[0, max_y2]
    #                 ),
    #                 legend=dict(
    #                     orientation="h",
    #                     yanchor="bottom",
    #                     y=-0.35,
    #                     xanchor="center",
    #                     x=0.5
    #                 ),
    #                 xaxis=dict(automargin=True),
    #                 margin=dict(b=140, t=60)
    #             )
                
    #             # Update bar hover templates
    #             fig.update_traces(
    #                 selector=dict(type="bar"),
    #                 hovertemplate='<b>%{fullData.name}</b><br>Year: %{x}<br>Share: %{y:.1f}%<extra></extra>'
    #             )
                
    #             st.plotly_chart(fig, use_container_width=True)
                
    #             # Add summary metrics below the chart
    #             st.markdown("**Chart Explanation:**")
    #             st.markdown("- **Colored bars** show the percentage share of each procedure type per year (2021-2025)")
    #             st.markdown("- **Darker/saturated colors** represent 2025 data (Year-to-Date through July)")
    #             st.markdown("- **Dark red line** shows the total number of surgeries performed per year")
    #             st.markdown("- **Left y-axis** shows procedure share percentages")
    #             st.markdown("- **Right y-axis** shows total surgery counts")
    #             if 2025 in pl['annee'].values:
    #                 st.info("📅 **Note:** 2025 data is year-to-date through July only.")
    
    # with col2:
    #     # Combined chart: National Average Surgeries line + National Procedure Mix bars
    #     st.markdown("#### National: Average Surgeries & Procedure Mix")
        
    #     if national_averages and proc_codes:
    #         # Filter years_window to exclude 2020
    #         years_window_filtered = [y for y in years_window if y > 2020]
            
    #         # Create national trend data
    #         nat_data = []
    #         for year in years_window_filtered:
    #             year_data = annual[annual['annee'] == year]
    #             if not year_data.empty:
    #                 avg_procedures = year_data['total_procedures_year'].mean()
    #                 nat_data.append({'Year': year, 'Avg Procedures': avg_procedures})
            
    #         # Create national procedure mix data
    #         nat_proc_data = []
    #         for year in years_window_filtered:
    #             year_data = annual[annual['annee'] == year]
    #             if not year_data.empty:
    #                 total_sleeve = year_data['SLE'].sum() if 'SLE' in year_data.columns else 0
    #                 total_bypass = year_data['BPG'].sum() if 'BPG' in year_data.columns else 0
    #                 total_other = year_data[proc_codes].sum().sum() - total_sleeve - total_bypass
    #                 total_all = total_sleeve + total_bypass + total_other
                    
    #                 if total_all > 0:
    #                     for label, val in [("Sleeve", total_sleeve), ("Gastric Bypass", total_bypass), ("Other", total_other)]:
    #                         nat_proc_data.append({'Year': year, 'Procedures': label, 'Share': (val / total_all) * 100})
            
    #         if nat_data and nat_proc_data:
    #             nat_df = pd.DataFrame(nat_data)
    #             nat_proc_df = pd.DataFrame(nat_proc_data)
                
    #             # Create the combined national chart
    #             fig_nat = go.Figure()
                
    #             # Add stacked bar chart for national procedure mix with different colors for 2025
    #             colors_regular = {'Sleeve': '#FF6B6B', 'Gastric Bypass': '#4ECDC4', 'Other': '#FFE66D'}  # Coral, Teal, Yellow
    #             colors_2025 = {'Sleeve': '#C92A2A', 'Gastric Bypass': '#0C8599', 'Other': '#E8B923'}  # Darker/more saturated for 2025
                
    #             for procedure in nat_proc_df['Procedures'].unique():
    #                 data = nat_proc_df[nat_proc_df['Procedures'] == procedure]
    #                 # Split data into 2025 and non-2025
    #                 data_before_2025 = data[data['Year'] < 2025]
    #                 data_2025 = data[data['Year'] == 2025]
                    
    #                 # Add bars for years before 2025
    #                 if not data_before_2025.empty:
    #                     fig_nat.add_trace(go.Bar(
    #                         x=data_before_2025['Year'],
    #                         y=data_before_2025['Share'],
    #                         name=procedure,
    #                         marker_color=colors_regular.get(procedure, '#cccccc'),
    #                         yaxis='y',
    #                         opacity=0.7,
    #                         legendgroup=procedure,
    #                         showlegend=True
    #                     ))
                    
    #                 # Add bars for 2025 with different color
    #                 if not data_2025.empty:
    #                     fig_nat.add_trace(go.Bar(
    #                         x=data_2025['Year'],
    #                         y=data_2025['Share'],
    #                         name=f"{procedure} (2025 YTD)",
    #                         marker_color=colors_2025.get(procedure, '#888888'),
    #                         yaxis='y',
    #                         opacity=0.85,
    #                         legendgroup=procedure,
    #                         showlegend=True
    #                 ))
                
    #             # Add line chart for national average surgeries (on secondary y-axis)
    #             fig_nat.add_trace(go.Scatter(
    #                 x=nat_df['Year'],
    #                 y=nat_df['Avg Procedures'],
    #                 mode='lines+markers',
    #                 name='National Average',
    #                 line=dict(color='#961316', width=4),
    #                 marker=dict(size=8, color='#961316'),
    #                 yaxis='y2',
    #                 hovertemplate='<b>National Average</b><br>Year: %{x}<br>Avg Count: %{y:.1f}<extra></extra>'
    #             ))
                
    #             # Update layout with dual y-axes
    #             max_nat_y2 = max(nat_df['Avg Procedures']) * 1.1 if not nat_df.empty else 100
    #             fig_nat.update_layout(
    #                 height=450,
    #                 plot_bgcolor='rgba(0,0,0,0)',
    #                 paper_bgcolor='rgba(0,0,0,0)',
    #                 barmode='stack',
    #                 title='National Average & Procedure Mix Overlay',
    #                 xaxis_title='Year',
    #                 yaxis=dict(
    #                     title='Procedure Share (%)',
    #                     side='left',
    #                     range=[0, 100]
    #                 ),
    #                 yaxis2=dict(
    #                     title='Average Surgeries per Hospital',
    #                     side='right',
    #                     overlaying='y',
    #                     range=[0, max_nat_y2]
    #                 ),
    #                 legend=dict(
    #                     orientation="h",
    #                     yanchor="bottom",
    #                     y=-0.35,
    #                     xanchor="center",
    #                     x=0.5
    #                 ),
    #                 xaxis=dict(automargin=True),
    #                 margin=dict(b=140, t=60)
    #             )
                
    #             # Update bar hover templates
    #             fig_nat.update_traces(
    #                 selector=dict(type="bar"),
    #                 hovertemplate='<b>%{fullData.name}</b><br>Year: %{x}<br>Share: %{y:.1f}%<extra></extra>'
    #             )
                
    #             st.plotly_chart(fig_nat, use_container_width=True)
                
    #             # Add summary metrics below the chart
    #             st.markdown("**Chart Explanation:**")
    #             st.markdown("- **Colored bars** show the national percentage share of each procedure type per year (2021-2025)")
    #             st.markdown("- **Darker/saturated colors** represent 2025 data (Year-to-Date through July)")
    #             st.markdown("- **Dark red line** shows the national average surgeries per hospital per year")
    #             st.markdown("- **Left y-axis** shows procedure share percentages")
    #             st.markdown("- **Right y-axis** shows average surgery counts")
    #             if 2025 in nat_proc_df['Year'].values:
    #                 st.info("📅 **Note:** 2025 data is year-to-date through July only.")
    
    # --- Big hospital chart: Number of procedures per year ---
    try:
        st.markdown("""
        <div class='nv-section'>
          <div class='nv-section-title'>Hospital — Number of procedures per year</div>
        """, unsafe_allow_html=True)
        # Build yearly totals for the selected hospital (2021+)
        hosp_year_counts = (
            selected_hospital_all_data[['annee','total_procedures_year']]
            .dropna().copy()
        )
        hosp_year_counts = hosp_year_counts[hosp_year_counts['annee'] >= 2021]
        # If 2025 (or any year) is missing from parquet, augment from VDA CSV (YTD)
        try:
            vda_h = _load_vda_year_totals_summary()
            if not vda_h.empty:
                vda_h = vda_h[vda_h['finessGeoDP'] == str(selected_hospital_id)]
                if not vda_h.empty:
                    add_rows = (
                        vda_h.groupby('annee', as_index=False)['TOT']
                        .max().rename(columns={'TOT':'total_procedures_year'})
                    )
                    add_rows = add_rows[add_rows['annee'] >= 2021]
                    for _, r in add_rows.iterrows():
                        yr = int(r['annee'])
                        if hosp_year_counts[hosp_year_counts['annee'] == yr].empty:
                            hosp_year_counts = pd.concat([
                                hosp_year_counts,
                                pd.DataFrame({'annee':[yr], 'total_procedures_year':[float(r['total_procedures_year'])]})
                            ], ignore_index=True)
        except Exception:
            pass
        hosp_year_counts = hosp_year_counts.sort_values('annee')
        if not hosp_year_counts.empty:
            years = hosp_year_counts['annee'].astype(int).tolist()
            vals = hosp_year_counts['total_procedures_year'].tolist()
            colors = []
            for y in years:
                if y == 2025:
                    colors.append('#1f4e79')  # darker blue for YTD 2025
                else:
                    colors.append('#4e79a7')  # regular blue
            b1, b2 = st.columns([4, 1])
            with b1:
                years_str = [str(y) for y in years]
                fig_h_big = go.Figure(go.Bar(x=years_str, y=vals, marker_color=colors))
                fig_h_big.update_layout(height=340, xaxis_title='Year', yaxis_title='Number of procedures', plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', xaxis=dict(type='category'))
                fig_h_big.update_traces(hovertemplate='Year: %{x}<br>Procedures: %{y:,}<extra></extra>')
                st.plotly_chart(fig_h_big, use_container_width=True)
                st.caption('Yearly total surgeries at the selected hospital. If 2025 is present, values are year‑to‑date.')
            with b2:
                # Reuse previously computed yoy_text (2025 YTD vs 2024 from monthly data if available)
                if 'yoy_text' in locals() or 'yoy_text' in globals():
                    st.markdown(f"<div class='nv-bubble teal' style='width:90px;height:90px;font-size:1.2rem'>{yoy_text}</div>", unsafe_allow_html=True)
                    st.caption('2025 YTD (until July)')
        else:
            st.info('No annual totals available to plot.')
    except Exception:
        pass
    st.markdown("</div>", unsafe_allow_html=True)

    # --- National, Regional, Same-Category comparisons (average surgeries per hospital) ---
    try:
        st.markdown("""
        <div class='nv-section'>
          <div class='nv-section-title'>National, Regional and Similar-Category Comparisons</div>
        """, unsafe_allow_html=True)

        # Helper to extract region value from establishment details
        def _extract_region_from_details(row) -> str | None:
            try:
                for key in ['lib_reg', 'region', 'code_reg', 'region_name']:
                    if key in row and pd.notna(row[key]) and str(row[key]).strip():
                        return str(row[key]).strip()
            except Exception:
                return None
            return None

        # Build base annual dataframe with eligibility filter similar to national
        annual_base = annual.copy()
        if 'total_procedures_year' in annual_base.columns:
            annual_base = annual_base[annual_base['total_procedures_year'] >= 25]

        # Resolve region for the selected hospital
        region_value = _extract_region_from_details(selected_hospital_details)

        # Compute National avg per year (reuse if available)
        nat_avg = (
            annual_base.groupby('annee', as_index=False)['total_procedures_year']
            .mean().rename(columns={'total_procedures_year': 'avg'})
        ) if 'total_procedures_year' in annual_base.columns else pd.DataFrame()

        # Compute Regional avg per year
        if region_value is not None:
            # Join establishments' region to annual if missing
            if 'lib_reg' not in annual_base.columns and 'region' not in annual_base.columns and 'code_reg' not in annual_base.columns:
                reg_map = establishments[['id'] + [c for c in ['lib_reg','region','code_reg','region_name'] if c in establishments.columns]].copy()
                annual_base = annual_base.merge(reg_map, left_on='id', right_on='id', how='left')
            # Build boolean mask across possible region columns
            reg_cols = [c for c in ['lib_reg','region','code_reg','region_name'] if c in annual_base.columns]
            reg_mask = False
            for c in reg_cols:
                reg_mask = reg_mask | (annual_base[c].astype(str).str.strip() == str(region_value))
            regional_df = annual_base[reg_mask]
            reg_avg = (
                regional_df.groupby('annee', as_index=False)['total_procedures_year']
                .mean().rename(columns={'total_procedures_year': 'avg'})
            ) if not regional_df.empty else pd.DataFrame()
        else:
            reg_avg = pd.DataFrame()

        # Compute Same-category avg per year (status + labels match)
        try:
            status_val = str(selected_hospital_details.get('status', '')).strip()
            def _flag(v):
                try:
                    return int(v) if pd.notna(v) else 0
                except Exception:
                    return 0
            uni = _flag(selected_hospital_details.get('university', 0))
            soffco = _flag(selected_hospital_details.get('LAB_SOFFCO', 0))
            cso_val = _flag(selected_hospital_details.get('cso', 0))
            est_cat = establishments.copy()
            for c in ['university','LAB_SOFFCO','cso']:
                if c not in est_cat.columns:
                    est_cat[c] = 0
            cat_ids = est_cat[
                (est_cat.get('statut','').astype(str).str.strip() == status_val)
                & (est_cat['university'].fillna(0).astype(int) == uni)
                & (est_cat['LAB_SOFFCO'].fillna(0).astype(int) == soffco)
                & (est_cat['cso'].fillna(0).astype(int) == cso_val)
            ]['id'].astype(str).unique().tolist()
            cat_df = annual_base[annual_base['id'].astype(str).isin(cat_ids)] if cat_ids else pd.DataFrame()
            cat_avg = (
                cat_df.groupby('annee', as_index=False)['total_procedures_year']
                .mean().rename(columns={'total_procedures_year': 'avg'})
            ) if not cat_df.empty else pd.DataFrame()
        except Exception:
            cat_avg = pd.DataFrame()

        # Helper: YoY bubble from VDA for a set of ids (average per hospital)
        def _yoy_bubble_for_group(id_list: list[str]) -> str | None:
            try:
                vda_df = _load_vda_year_totals_summary()
                if vda_df.empty or not id_list:
                    return None
                sub = vda_df[vda_df['finessGeoDP'].astype(str).isin([str(i) for i in id_list])]
                if sub.empty:
                    return None
                per_hosp_year = sub.groupby(['finessGeoDP','annee'], as_index=False)['TOT'].max()
                avg_by_year = per_hosp_year.groupby('annee', as_index=False)['TOT'].mean()
                v2024 = float(avg_by_year[avg_by_year['annee'] == 2024]['TOT'].iloc[0]) if (avg_by_year['annee'] == 2024).any() else None
                v2025 = float(avg_by_year[avg_by_year['annee'] == 2025]['TOT'].iloc[0]) if (avg_by_year['annee'] == 2025).any() else None
                if v2024 and v2025 is not None and v2024 > 0:
                    return f"{((v2025 / v2024 - 1.0) * 100.0):+.0f}%"
            except Exception:
                return None
            return None

        # Collect ids for groups
        all_ids = establishments['id'].astype(str).unique().tolist() if 'id' in establishments.columns else []
        reg_ids = (
            establishments[establishments.get('lib_reg', establishments.get('region', '')).astype(str).str.strip() == str(region_value)]['id'].astype(str).unique().tolist()
            if region_value is not None and 'id' in establishments.columns else []
        )
        est_cat_ids = [
            i for i in cat_ids
        ] if 'cat_ids' in locals() else []

        # Helper: Augment avg-per-year DataFrame with 2025 YTD from VDA when parquet lacks 2025
        def _augment_avg_with_vda(avg_df: pd.DataFrame, ids: list[str]) -> pd.DataFrame:
            try:
                vda_df = _load_vda_year_totals_summary()
                if vda_df.empty or not ids:
                    return avg_df
                sub = vda_df[vda_df['finessGeoDP'].astype(str).isin([str(i) for i in ids])]
                if sub.empty:
                    return avg_df
                per_hosp_year = sub.groupby(['finessGeoDP','annee'], as_index=False)['TOT'].max()
                avg_by_year = per_hosp_year.groupby('annee', as_index=False)['TOT'].mean().rename(columns={'TOT':'avg'})
                if (avg_by_year['annee'] == 2025).any():
                    v2025 = float(avg_by_year[avg_by_year['annee'] == 2025]['avg'].iloc[0])
                    # Insert or update 2025 row
                    if (avg_df['annee'] == 2025).any():
                        avg_df.loc[avg_df['annee'] == 2025, 'avg'] = v2025
                    else:
                        avg_df = pd.concat([avg_df, pd.DataFrame({'annee':[2025], 'avg':[v2025]})], ignore_index=True)
                return avg_df.sort_values('annee')
            except Exception:
                return avg_df

        # Apply augmentation
        if not nat_avg.empty:
            nat_avg = _augment_avg_with_vda(nat_avg, all_ids)
        if not reg_avg.empty:
            reg_avg = _augment_avg_with_vda(reg_avg, reg_ids)
        if not cat_avg.empty:
            cat_avg = _augment_avg_with_vda(cat_avg, est_cat_ids)

        c_nat, c_reg, c_cat = st.columns(3)
        with c_nat:
            if not nat_avg.empty:
                s1, s2 = st.columns([4, 1])
                with s1:
                    nat_avg_plot = nat_avg[nat_avg['annee'] >= 2021].copy()
                    nat_avg_plot['annee'] = nat_avg_plot['annee'].astype(int).astype(str)
                    fig_nat_small = px.bar(nat_avg_plot, x='annee', y='avg', title='National — Avg surgeries per hospital', color_discrete_sequence=['#E9A23B'])
                    fig_nat_small.update_layout(height=260, xaxis_title='Year', yaxis_title='Avg surgeries', plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', xaxis=dict(type='category'))
                    st.plotly_chart(fig_nat_small, use_container_width=True)
                    st.caption('Average number of surgeries per hospital across France, by year. Use as a national baseline.')
                with s2:
                    val = _yoy_bubble_for_group(all_ids)
                    if val is not None:
                        st.markdown(f"<div class='nv-bubble' style='background:#E9A23B;width:90px;height:90px;font-size:1.2rem'>{val}</div>", unsafe_allow_html=True)
                        st.caption('2025 YTD (until July)')
            else:
                st.info('National data unavailable.')

        with c_reg:
            if not reg_avg.empty:
                s1, s2 = st.columns([4, 1])
                with s1:
                    reg_avg_plot = reg_avg[reg_avg['annee'] >= 2021].copy()
                    reg_avg_plot['annee'] = reg_avg_plot['annee'].astype(int).astype(str)
                    fig_reg = px.bar(reg_avg_plot, x='annee', y='avg', title='Regional — Avg surgeries per hospital', color_discrete_sequence=['#4ECDC4'])
                    fig_reg.update_layout(height=260, xaxis_title='Year', yaxis_title='Avg surgeries', plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', xaxis=dict(type='category'))
                    st.plotly_chart(fig_reg, use_container_width=True)
                    st.caption('Average number of surgeries per hospital in your region, by year. Compares regional peers.')
                with s2:
                    val = _yoy_bubble_for_group(reg_ids)
                    if val is not None:
                        st.markdown(f"<div class='nv-bubble' style='background:#4ECDC4;width:90px;height:90px;font-size:1.2rem'>{val}</div>", unsafe_allow_html=True)
                        st.caption('2025 YTD (until July)')
            else:
                st.info('Regional data unavailable for this hospital.')

        with c_cat:
            if not cat_avg.empty:
                s1, s2 = st.columns([4, 1])
                with s1:
                    cat_avg_plot = cat_avg[cat_avg['annee'] >= 2021].copy()
                    cat_avg_plot['annee'] = cat_avg_plot['annee'].astype(int).astype(str)
                    fig_cat = px.bar(cat_avg_plot, x='annee', y='avg', title='Same category — Avg surgeries per hospital', color_discrete_sequence=['#A78BFA'])
                    fig_cat.update_layout(height=260, xaxis_title='Year', yaxis_title='Avg surgeries', plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', xaxis=dict(type='category'))
                    st.plotly_chart(fig_cat, use_container_width=True)
                    st.caption('Average number of surgeries per hospital for institutions with similar status/labels.')
                with s2:
                    val = _yoy_bubble_for_group(est_cat_ids)
                    if val is not None:
                        st.markdown(f"<div class='nv-bubble' style='background:#A78BFA;width:90px;height:90px;font-size:1.2rem'>{val}</div>", unsafe_allow_html=True)
                        st.caption('2025 YTD (until July)')
            else:
                st.info('No matching category group could be formed for this hospital.')
    except Exception as e:
        st.caption(f"Comparison charts unavailable: {e}")
    st.markdown("</div>", unsafe_allow_html=True)
    
    # --- Lollipop chart: distribution across hospitals (highlight selected) ---
    try:
        st.markdown("""
        <div class='nv-section'>
          <div class='nv-section-title'>Lollipop — Number of procedures per hospital (latest year)</div>
        """, unsafe_allow_html=True)

        def _extract_region_from_details(row) -> str | None:
            try:
                for key in ['lib_reg', 'region', 'code_reg', 'region_name']:
                    if key in row and pd.notna(row[key]) and str(row[key]).strip():
                        return str(row[key]).strip()
            except Exception:
                return None
            return None

        region_value2 = _extract_region_from_details(selected_hospital_details)
        ids_all = establishments['id'].astype(str).unique().tolist() if 'id' in establishments.columns else []
        ids_reg = (
            establishments[establishments.get('lib_reg', establishments.get('region', '')).astype(str).str.strip() == str(region_value2)]['id'].astype(str).unique().tolist()
            if region_value2 is not None and 'id' in establishments.columns else []
        )
        try:
            status_val2 = str(selected_hospital_details.get('status', '')).strip()
            def _flag(v):
                try:
                    return int(v) if pd.notna(v) else 0
                except Exception:
                    return 0
            uni2 = _flag(selected_hospital_details.get('university', 0))
            soffco2 = _flag(selected_hospital_details.get('LAB_SOFFCO', 0))
            cso2 = _flag(selected_hospital_details.get('cso', 0))
            est_cat2 = establishments.copy()
            for c in ['university','LAB_SOFFCO','cso']:
                if c not in est_cat2.columns:
                    est_cat2[c] = 0
            ids_cat = est_cat2[
                (est_cat2.get('statut','').astype(str).str.strip() == status_val2)
                & (est_cat2['university'].fillna(0).astype(int) == uni2)
                & (est_cat2['LAB_SOFFCO'].fillna(0).astype(int) == soffco2)
                & (est_cat2['cso'].fillna(0).astype(int) == cso2)
            ]['id'].astype(str).unique().tolist()
        except Exception:
            ids_cat = []

        scope = st.radio("Compare against", ["National", "Regional", "Same category"], horizontal=True, index=0, key=f"lollipop_scope_{selected_hospital_id}")
        if scope == "Regional":
            id_filter = ids_reg
        elif scope == "Same category":
            id_filter = ids_cat
        else:
            id_filter = ids_all

        def _get_group_year_totals(year: int, ids: list[str]) -> pd.DataFrame:
            df_a = annual[annual['annee'] == year][['id','total_procedures_year']].copy() if 'annee' in annual.columns else pd.DataFrame()
            if not df_a.empty:
                df_a['id'] = df_a['id'].astype(str)
                df_a = df_a.groupby('id', as_index=False)['total_procedures_year'].sum()
            df_v = _load_vda_year_totals_summary()
            if not df_v.empty:
                df_v = df_v[df_v['annee'] == year].groupby('finessGeoDP', as_index=False)['TOT'].max().rename(columns={'finessGeoDP':'id','TOT':'vda_total'})
                df_v['id'] = df_v['id'].astype(str)
            merged = pd.merge(df_v, df_a, on='id', how='outer') if (not (df_v is None or df_v.empty)) else df_a
            if merged is None or merged.empty:
                return pd.DataFrame(columns=['id','total'])
            merged['total'] = merged.get('total_procedures_year').fillna(merged.get('vda_total'))
            out = merged[['id','total']].dropna()
            if ids:
                out = out[out['id'].astype(str).isin([str(i) for i in ids])]
            return out

        # Choose the latest year with the largest coverage (hospitals with data)
        candidate_years = [2025, 2024, 2023, 2022, 2021]
        best_year = None
        best_grp = pd.DataFrame()
        for y in candidate_years:
            g = _get_group_year_totals(y, id_filter)
            g = g.copy()
            g['total'] = pd.to_numeric(g.get('total', 0), errors='coerce').fillna(0)
            g = g[g['total'] > 0]
            if best_year is None or len(g) > len(best_grp):
                best_year = y
                best_grp = g
            # stop early if we already have a large set
            if len(best_grp) >= 200:
                break
        year_candidate = best_year if best_year is not None else 2024
        grp = best_grp

        grp = grp.copy()
        grp['total'] = pd.to_numeric(grp['total'], errors='coerce').fillna(0)
        grp = grp[grp['total'] > 0]
        if not grp.empty:
            names_map = establishments.set_index('id')['name'].to_dict() if 'name' in establishments.columns else {}
            grp['name'] = grp['id'].map(lambda i: names_map.get(i, str(i)))
            grp = grp.sort_values('total').reset_index(drop=True)
            # Optional limit for readability
            max_hosp = st.slider("Max hospitals to display", 10, max(10, len(grp)), len(grp), key=f"lollipop_limit_{scope}")
            grp = grp.tail(max_hosp)
            x_pos = list(range(1, len(grp) + 1))
            colors = ['#FF8C00' if str(i) == str(selected_hospital_id) else '#5DA5DA' for i in grp['id']]
            fig_ll = go.Figure()
            # Stems
            for xi, yi, col in zip(x_pos, grp['total'], colors):
                fig_ll.add_trace(go.Scatter(x=[xi, xi], y=[0, yi], mode='lines', line=dict(color=col, width=2), showlegend=False, hoverinfo='skip'))
            # Heads
            fig_ll.add_trace(go.Scatter(x=x_pos, y=grp['total'], mode='markers', marker=dict(color=colors, size=8), showlegend=False, hovertemplate='%{text}<br>Procedures: %{y:,}<extra></extra>', text=grp['name']))
            # Pseudo-legend using dummy markers
            fig_ll.add_trace(go.Scatter(x=[None], y=[None], mode='markers', marker=dict(color='#FF8C00', size=8), name='Selected hospital'))
            fig_ll.add_trace(go.Scatter(x=[None], y=[None], mode='markers', marker=dict(color='#5DA5DA', size=8), name='Other hospitals'))
            fig_ll.update_layout(height=360, xaxis_title='Hospitals', yaxis_title='Number of procedures', plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', xaxis=dict(showticklabels=False))
            st.plotly_chart(fig_ll, use_container_width=True)
            st.caption('Each dot is a hospital; stems show procedure volume. Orange highlights this hospital.')
            if year_candidate == 2025:
                st.caption('2025 YTD (until July)')
        else:
            st.info('No hospital totals available for this scope.')
    except Exception as e:
        st.caption(f"Lollipop chart unavailable: {e}")
    st.markdown("</div>", unsafe_allow_html=True)
    
    # --- Scatter: Sleeve vs Bypass share (%) ---
    try:
        st.markdown("""
        <div class='nv-section'>
          <div class='nv-section-title'>Sleeve & Bypass share (%)</div>
        """, unsafe_allow_html=True)

        # Build grouping ids (national, regional, same status across France)
        def _extract_region_from_details(row) -> str | None:
            try:
                for key in ['lib_reg', 'region', 'code_reg', 'region_name']:
                    if key in row and pd.notna(row[key]) and str(row[key]).strip():
                        return str(row[key]).strip()
            except Exception:
                return None
            return None

        region_val3 = _extract_region_from_details(selected_hospital_details)
        ids_all3 = establishments['id'].astype(str).unique().tolist() if 'id' in establishments.columns else []
        ids_reg3 = (
            establishments[establishments.get('lib_reg', establishments.get('region', '')).astype(str).str.strip() == str(region_val3)]['id'].astype(str).unique().tolist()
            if region_val3 is not None and 'id' in establishments.columns else []
        )
        status_val3 = str(selected_hospital_details.get('status', '')).strip()
        ids_status3 = (
            establishments[establishments.get('status','').astype(str).str.strip() == status_val3]['id'].astype(str).unique().tolist()
            if 'status' in establishments.columns else []
        )

        scope_sc = st.radio("Compare against", ["National", "Regional", "Same status"], horizontal=True, index=0, key=f"scatter_scope_{selected_hospital_id}")
        if scope_sc == "Regional":
            ids_scope = ids_reg3
        elif scope_sc == "Same status":
            ids_scope = ids_status3
        else:
            ids_scope = ids_all3

            # Use ALL years 2021–2025 (stacked points), filter scope
            proc_cols = [c for c in BARIATRIC_PROCEDURE_NAMES.keys() if c in annual.columns]
            base = annual[(annual.get('annee') >= 2021) & (annual.get('annee') <= 2025)].copy()
            if ids_scope:
                base = base[base['id'].astype(str).isin([str(i) for i in ids_scope])]
            if base.empty:
                best_df = pd.DataFrame()
            else:
                totals = base[proc_cols].sum(axis=1) if proc_cols else pd.Series([0]*len(base))
                best_df = base.assign(_total=totals)
                best_df = best_df[best_df['_total'] > 0]
        if best_df.empty:
            st.info('No data to compute sleeve/bypass shares for the selected scope.')
        else:
            # Compute shares
            for c in ['SLE','BPG']:
                if c not in best_df.columns:
                    best_df[c] = 0
            best_df['_total_all'] = best_df[proc_cols].sum(axis=1)
            best_df = best_df[best_df['_total_all'] > 0]
            best_df['_sleeve_pct'] = best_df['SLE'] / best_df['_total_all'] * 100.0
            best_df['_bypass_pct'] = best_df['BPG'] / best_df['_total_all'] * 100.0
            # Selected hospital rows (all years) and others
            sel_all = best_df[best_df['id'].astype(str) == str(selected_hospital_id)].copy()
            others = best_df[best_df['id'].astype(str) != str(selected_hospital_id)].copy()
            # Names for hover
            name_map = establishments.set_index('id')['name'].to_dict() if 'name' in establishments.columns else {}
            others['name'] = others['id'].map(lambda i: name_map.get(i, str(i)))
            sel_all['name'] = sel_all['id'].map(lambda i: name_map.get(i, str(i)))

            fig_sc = go.Figure()
            # Others (dots)
            fig_sc.add_trace(go.Scatter(
                x=others['_sleeve_pct'], y=others['_bypass_pct'], mode='markers',
                marker=dict(color='#60a5fa', size=6, opacity=0.7),
                name='Other hospitals',
                hovertemplate='%{text}<br>Sleeve: %{x:.0f}%<br>Bypass: %{y:.0f}%<extra></extra>',
                text=others['name']
            ))
            # Selected hospital (single average point across 2021–2025)
            if not sel_all.empty:
                # Volume-weighted average via summed counts
                total_all = sel_all[proc_cols].sum().sum()
                sum_sle = float(sel_all.get('SLE', 0).sum()) if 'SLE' in sel_all.columns else 0.0
                sum_bpg = float(sel_all.get('BPG', 0).sum()) if 'BPG' in sel_all.columns else 0.0
                if total_all > 0:
                    x_avg = (sum_sle / total_all) * 100.0
                    y_avg = (sum_bpg / total_all) * 100.0
                    name_map = establishments.set_index('id')['name'].to_dict() if 'name' in establishments.columns else {}
                    sel_name = name_map.get(str(selected_hospital_id), str(selected_hospital_id))
                    fig_sc.add_trace(go.Scatter(
                        x=[x_avg], y=[y_avg], mode='markers',
                        marker=dict(color='#FF8C00', size=12, line=dict(color='white', width=1)),
                        name='Selected hospital (avg)',
                        hovertemplate=f'{sel_name}<br>Sleeve: %{{x:.0f}}%<br>Bypass: %{{y:.0f}}%<extra></extra>'
                    ))
            fig_sc.update_layout(
                height=380,
                xaxis_title='Sleeve rate (%)', yaxis_title='Bypass rate (%)',
                xaxis=dict(range=[0, 100]), yaxis=dict(range=[0, 100]),
                plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)'
            )
            st.plotly_chart(fig_sc, use_container_width=True)
            st.caption('Sleeve share (x) vs bypass share (y) across hospitals/years. Orange dot is this hospital’s 2021–2025 average.')
    except Exception as e:
        st.caption(f"Scatter unavailable: {e}")
    st.markdown("</div>", unsafe_allow_html=True)
    
    # Monthly procedure volume trends
    try:
        st.markdown("""
        <div class='nv-section'>
          <div class='nv-section-title'>Monthly Procedure Volume Trends</div>
        """, unsafe_allow_html=True)
        @st.cache_data(show_spinner=False)
        def _load_monthly_volumes(path: str = "data/export_TAB_VOL_MOIS_TCN_HOP.csv") -> pd.DataFrame:
            try:
                df = pd.read_csv(path, dtype={'finessGeoDP': str, 'annee': int, 'mois': int})
                df['finessGeoDP'] = df['finessGeoDP'].astype(str).str.strip()
                return df
            except Exception:
                return pd.DataFrame()
        
        monthly_vol = _load_monthly_volumes()
        if not monthly_vol.empty and 'finessGeoDP' in monthly_vol.columns:
            hosp_monthly = monthly_vol[monthly_vol['finessGeoDP'] == str(selected_hospital_id)].copy()
            if not hosp_monthly.empty:
                # Title shown in section header
                
                # Create date column for proper time series
                hosp_monthly['date'] = pd.to_datetime(hosp_monthly['annee'].astype(str) + '-' + hosp_monthly['mois'].astype(str).str.zfill(2) + '-01')
                
                # Aggregate by month (sum across procedure types)
                monthly_totals = hosp_monthly.groupby('date', as_index=False)['TOT_month'].first().sort_values('date')
                
                # Create monthly trend chart
                fig_monthly = go.Figure()
                fig_monthly.add_trace(go.Scatter(
                    x=monthly_totals['date'],
                    y=monthly_totals['TOT_month'],
                    mode='lines+markers',
                    name='Monthly Total',
                    line=dict(color='#1f77b4', width=2),
                    marker=dict(size=4),
                    hovertemplate='%{x|%b %Y}<br>Procedures: %{y}<extra></extra>'
                ))
                
                # Add 12-month rolling average
                if len(monthly_totals) >= 12:
                    monthly_totals['rolling_avg'] = monthly_totals['TOT_month'].rolling(window=12, center=False).mean()
                    fig_monthly.add_trace(go.Scatter(
                        x=monthly_totals['date'],
                        y=monthly_totals['rolling_avg'],
                        mode='lines',
                        name='12-month Average',
                        line=dict(color='#ff7f0e', width=3, dash='dash'),
                        hovertemplate='%{x|%b %Y}<br>12-mo Avg: %{y:.1f}<extra></extra>'
                    ))
                
                fig_monthly.update_layout(
                    height=400,
                    xaxis_title='Month',
                    yaxis_title='Number of Procedures',
                    hovermode='x unified',
                    plot_bgcolor='rgba(0,0,0,0)',
                    paper_bgcolor='rgba(0,0,0,0)',
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                )
                
                st.plotly_chart(fig_monthly, use_container_width=True)
                st.caption('Monthly procedure totals with a 12‑month rolling average for trend context.')
                
                # Show procedure-specific monthly trends
                with st.expander("📊 View by Procedure Type"):
                    # Get procedure volumes by type
                    proc_monthly = hosp_monthly.groupby(['date', 'baria_t'], as_index=False).agg({'TOT_month_tcn': 'first'})
                    
                    # Filter to main procedures
                    main_procs = proc_monthly[proc_monthly['baria_t'].isin(['SLE', 'BPG'])].copy()
                    
                    if not main_procs.empty:
                        fig_by_proc = go.Figure()
                        
                        proc_colors = {'SLE': '#60a5fa', 'BPG': '#f97316'}
                        proc_names = {'SLE': 'Sleeve Gastrectomy', 'BPG': 'Gastric Bypass'}
                        
                        for proc_type in main_procs['baria_t'].unique():
                            proc_data = main_procs[main_procs['baria_t'] == proc_type].sort_values('date')
                            fig_by_proc.add_trace(go.Scatter(
                                x=proc_data['date'],
                                y=proc_data['TOT_month_tcn'],
                                mode='lines+markers',
                                name=proc_names.get(proc_type, proc_type),
                                line=dict(color=proc_colors.get(proc_type, '#cccccc'), width=2),
                                marker=dict(size=4),
                                hovertemplate='%{x|%b %Y}<br>' + proc_names.get(proc_type, proc_type) + ': %{y}<extra></extra>'
                            ))
                        
                        fig_by_proc.update_layout(
                            height=350,
                            xaxis_title='Month',
                            yaxis_title='Number of Procedures',
                            hovermode='x unified',
                            plot_bgcolor='rgba(0,0,0,0)',
                            paper_bgcolor='rgba(0,0,0,0)'
                        )
                        
                        st.plotly_chart(fig_by_proc, use_container_width=True)
                        st.caption('Monthly volumes split by procedure type for the selected hospital.')
    except Exception as e:
        st.warning(f"Could not load monthly volume data: {e}")
    st.markdown("</div>", unsafe_allow_html=True)
    
    # --- Procedure Casemix (Donut charts) ---
    try:
        st.markdown("""
        <div class='nv-section'>
          <div class='nv-section-title'>Procedure casemix</div>
        """, unsafe_allow_html=True)
        mode = st.radio(
            "View",
            ["2021–2025", "Last 12 months"],
            index=0,
            horizontal=True,
            key=f"casemix_mode_{selected_hospital_id}"
        )

        # Helper: get group ids
        def _extract_region_from_details(row) -> str | None:
            try:
                for key in ['lib_reg', 'region', 'code_reg', 'region_name']:
                    if key in row and pd.notna(row[key]) and str(row[key]).strip():
                        return str(row[key]).strip()
            except Exception:
                return None
            return None

        region_val = _extract_region_from_details(selected_hospital_details)
        ids_all = establishments['id'].astype(str).unique().tolist() if 'id' in establishments.columns else []
        ids_reg = (
            establishments[establishments.get('lib_reg', establishments.get('region', '')).astype(str).str.strip() == str(region_val)]['id'].astype(str).unique().tolist()
            if region_val is not None and 'id' in establishments.columns else []
        )
        # Same category
        try:
            status_val = str(selected_hospital_details.get('status', '')).strip()
            def _flag(v):
                try:
                    return int(v) if pd.notna(v) else 0
                except Exception:
                    return 0
            uni = _flag(selected_hospital_details.get('university', 0))
            soffco = _flag(selected_hospital_details.get('LAB_SOFFCO', 0))
            cso_val = _flag(selected_hospital_details.get('cso', 0))
            est_cat = establishments.copy()
            for c in ['university','LAB_SOFFCO','cso']:
                if c not in est_cat.columns:
                    est_cat[c] = 0
            ids_cat = est_cat[
                (est_cat.get('statut','').astype(str).str.strip() == status_val)
                & (est_cat['university'].fillna(0).astype(int) == uni)
                & (est_cat['LAB_SOFFCO'].fillna(0).astype(int) == soffco)
                & (est_cat['cso'].fillna(0).astype(int) == cso_val)
            ]['id'].astype(str).unique().tolist()
        except Exception:
            ids_cat = []

        PROC_COLORS = {'Sleeve': '#1f77b4', 'Gastric Bypass': '#ff7f0e', 'Other': '#2ca02c'}

        @st.cache_data(show_spinner=False)
        def _load_monthly_for_casemix(path: str = "data/export_TAB_VOL_MOIS_TCN_HOP.csv") -> pd.DataFrame:
            try:
                df = pd.read_csv(path, dtype={'finessGeoDP': str, 'annee': int, 'mois': int})
                df['finessGeoDP'] = df['finessGeoDP'].astype(str).str.strip()
                df['date'] = pd.to_datetime(df['annee'].astype(str) + '-' + df['mois'].astype(str).str.zfill(2) + '-01')
                return df
            except Exception:
                return pd.DataFrame()

        def _casemix_period(ids: list[str] | None) -> dict:
            # Aggregate from annual (2021–2025)
            df = annual.copy()
            if ids:
                df = df[df['id'].astype(str).isin([str(i) for i in ids])]
            df = df[(df.get('annee', 0) >= 2021) & (df.get('annee', 0) <= 2025)]
            if df.empty:
                return {'Sleeve': 0, 'Gastric Bypass': 0, 'Other': 0}
            sleeve = int(pd.to_numeric(df.get('SLE', 0), errors='coerce').fillna(0).sum()) if 'SLE' in df.columns else 0
            bypass = int(pd.to_numeric(df.get('BPG', 0), errors='coerce').fillna(0).sum()) if 'BPG' in df.columns else 0
            other = 0
            for c in [c for c in df.columns if c in BARIATRIC_PROCEDURE_NAMES and c not in ['SLE','BPG']]:
                other += int(pd.to_numeric(df[c], errors='coerce').fillna(0).sum())
            return {'Sleeve': sleeve, 'Gastric Bypass': bypass, 'Other': other}

        def _casemix_last12(ids: list[str] | None) -> dict:
            mv = _load_monthly_for_casemix()
            if mv.empty:
                return _casemix_period(ids)
            if ids:
                mv = mv[mv['finessGeoDP'].isin([str(i) for i in ids])]
            if mv.empty:
                return _casemix_period(ids)
            max_date = mv['date'].max()
            start = (max_date - pd.DateOffset(months=11)).normalize()
            m12 = mv[(mv['date'] >= start) & (mv['date'] <= max_date)].copy()
            if m12.empty:
                return _casemix_period(ids)
            def _sum_code(code: str) -> float:
                sub = m12[m12.get('baria_t') == code]
                return float(pd.to_numeric(sub.get('TOT_month_tcn', 0), errors='coerce').fillna(0).sum())
            sleeve = _sum_code('SLE')
            bypass = _sum_code('BPG')
            other = float(pd.to_numeric(m12[~m12['baria_t'].isin(['SLE','BPG'])].get('TOT_month_tcn', 0), errors='coerce').fillna(0).sum())
            return {'Sleeve': sleeve, 'Gastric Bypass': bypass, 'Other': other}

        def _plot_donut(title: str, data: dict, height: int = 260):
            total = sum(data.values())
            if total <= 0:
                st.info(f"No data for {title}.")
                return
            dfp = pd.DataFrame({'Procedure': list(data.keys()), 'Count': list(data.values())})
            figp = px.pie(dfp, values='Count', names='Procedure', hole=0.55, color='Procedure', color_discrete_map=PROC_COLORS)
            figp.update_traces(textposition='inside', textinfo='percent+label')
            figp.update_layout(title=title, height=height, showlegend=False, plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)')
            st.plotly_chart(figp, use_container_width=True)

        use_last12 = (mode == "Last 12 months")
        # Compute sets
        cas_h = _casemix_last12([selected_hospital_id]) if use_last12 else _casemix_period([selected_hospital_id])
        cas_n = _casemix_last12(ids_all) if use_last12 else _casemix_period(ids_all)
        cas_r = _casemix_last12(ids_reg) if use_last12 else _casemix_period(ids_reg)
        cas_c = _casemix_last12(ids_cat) if use_last12 else _casemix_period(ids_cat)

        # Top row: center the hospital donut and make it larger
        _sp_l, _center, _sp_r = st.columns([1, 1, 1])
        with _center:
            _plot_donut('Hospital', cas_h, height=320)
            st.caption('Share of procedures at the hospital (2021–2025 or last 12 months, depending on selection).')

        # Second row: three donuts below (National, Regional, Same category)
        c2, c3, c4 = st.columns(3)
        with c2:
            _plot_donut('National', cas_n)
            st.caption('National procedure mix over the same period to benchmark against the hospital.')
        with c3:
            _plot_donut('Regional', cas_r)
            st.caption('Regional procedure mix over the same period to compare with nearby peers.')
        with c4:
            _plot_donut('Same category', cas_c)
            st.caption('Procedure mix for institutions with similar status/labels over the same period.')
        if use_last12:
            st.caption("Last 12 months based on monthly data; if unavailable, falls back to 2021–2025 aggregate.")
    except Exception as e:
        st.caption(f"Casemix section unavailable: {e}")
    st.markdown("</div>", unsafe_allow_html=True)

    # --- Robot share scatter (procedures vs robotic share) ---
    try:
        st.markdown("""
        <div class='nv-section'>
          <div class='nv-section-title'>Robot share</div>
        """, unsafe_allow_html=True)
        scope_rb = st.radio(
            "Compare against",
            ["National", "Regional", "Same status"],
            horizontal=True,
            index=0,
            key=f"robot_scope_{selected_hospital_id}"
        )
        use_2025_rb = st.toggle("Show 2025 (YTD)", value=False, key=f"robot_2025_{selected_hospital_id}")

        def _extract_region_from_details(row) -> str | None:
            try:
                for key in ['lib_reg', 'region', 'code_reg', 'region_name']:
                    if key in row and pd.notna(row[key]) and str(row[key]).strip():
                        return str(row[key]).strip()
            except Exception:
                return None
            return None

        # Build scope id sets (same status across all France)
        region_val_rb = _extract_region_from_details(selected_hospital_details)
        ids_all_rb = establishments['id'].astype(str).unique().tolist() if 'id' in establishments.columns else []
        ids_reg_rb = (
            establishments[establishments.get('lib_reg', establishments.get('region', '')).astype(str).str.strip() == str(region_val_rb)]['id'].astype(str).unique().tolist()
            if region_val_rb is not None and 'id' in establishments.columns else []
        )
        status_val_rb = str(selected_hospital_details.get('status', '')).strip()
        ids_status_rb = (
            establishments[establishments.get('status','').astype(str).str.strip() == status_val_rb]['id'].astype(str).unique().tolist()
            if 'status' in establishments.columns else []
        )

        if scope_rb == "Regional":
            ids_scope = ids_reg_rb
        elif scope_rb == "Same status":
            ids_scope = ids_status_rb
        else:
            ids_scope = ids_all_rb

        # Builders
        def _robot_share_from_annual(ids: list[str]) -> tuple[pd.DataFrame, int]:
            df = annual.copy()
            if ids:
                df = df[df['id'].astype(str).isin([str(i) for i in ids])]
            df = df[(df.get('annee', 0) >= 2021) & (df.get('annee', 0) <= 2024)].copy()
            if df.empty:
                return pd.DataFrame(), 2024
            # choose year with most hospitals having valid approach totals and totals>0
            best_year = None
            best = pd.DataFrame()
            for y in [2024, 2023, 2022, 2021]:
                dy = df[df['annee'] == y].copy()
                if dy.empty:
                    continue
                cols = [c for c in ['ROB','COE','LAP'] if c in dy.columns]
                if not cols:
                    continue
                agg = dy.groupby('id', as_index=False)[cols + (['total_procedures_year'] if 'total_procedures_year' in dy.columns else [])].sum()
                agg['_approach_tot'] = agg[cols].sum(axis=1)
                if 'total_procedures_year' not in agg.columns:
                    agg['total_procedures_year'] = 0
                agg = agg[(agg['_approach_tot'] > 0)]
                if best_year is None or len(agg) > len(best):
                    best_year = y
                    best = agg
            if best.empty:
                return pd.DataFrame(), 2024
            best['_robot_share'] = (best.get('ROB', 0) / best['_approach_tot']) * 100.0
            best = best.rename(columns={'id':'hid'}).assign(hid=lambda d: d['hid'].astype(str))
            return best[['hid','total_procedures_year','_robot_share']], int(best_year or 2024)

        def _robot_share_from_vda_2025(ids: list[str]) -> pd.DataFrame:
            vda = _load_vda_year_totals_summary()
            if vda.empty:
                return pd.DataFrame()
            sub = vda[vda['annee'] == 2025].copy()
            if ids:
                sub = sub[sub['finessGeoDP'].astype(str).isin([str(i) for i in ids])]
            if sub.empty:
                return pd.DataFrame()
            # sum VOL per approach and take max TOT per hospital
            piv = sub.pivot_table(index='finessGeoDP', columns='vda', values='VOL', aggfunc='sum').fillna(0)
            piv.columns = [str(c) for c in piv.columns]
            piv = piv.rename(columns={'COE':'COE', 'LAP':'LAP', 'ROB':'ROB'})
            tot = sub.groupby('finessGeoDP', as_index=False)['TOT'].max().rename(columns={'finessGeoDP':'hid','TOT':'total_procedures_year'})
            piv = piv.reset_index().rename(columns={'finessGeoDP':'hid'})
            merged = tot.merge(piv, on='hid', how='left')
            for c in ['ROB','COE','LAP']:
                if c not in merged.columns:
                    merged[c] = 0
            merged['_approach_tot'] = merged[['ROB','COE','LAP']].sum(axis=1)
            merged['_robot_share'] = (merged['ROB'] / merged['_approach_tot'].replace({0: pd.NA})) * 100.0
            merged = merged.dropna(subset=['_robot_share'])
            merged['hid'] = merged['hid'].astype(str)
            return merged[['hid','total_procedures_year','_robot_share']]

        if use_2025_rb:
            df_rb = _robot_share_from_vda_2025(ids_scope)
            year_used = 2025
        else:
            df_rb, year_used = _robot_share_from_annual(ids_scope)

        if df_rb is None or df_rb.empty:
            st.info('No data available to compute robot share for the selected scope.')
        else:
            # Attach names and split selected vs others
            name_map = establishments.set_index('id')['name'].to_dict() if 'name' in establishments.columns else {}
            df_rb['name'] = df_rb['hid'].map(lambda i: name_map.get(i, str(i)))
            sel = df_rb[df_rb['hid'] == str(selected_hospital_id)]
            others = df_rb[df_rb['hid'] != str(selected_hospital_id)]
            fig_rbs = go.Figure()
            # others
            fig_rbs.add_trace(go.Scatter(
                x=others['total_procedures_year'],
                y=others['_robot_share'],
                mode='markers',
                marker=dict(color='#60a5fa', size=6, opacity=0.75),
                name='Other hospitals',
                hovertemplate='%{text}<br>Procedures: %{x:,}<br>Robot share: %{y:.0f}%<extra></extra>',
                text=others['name']
            ))
            # selected
            if not sel.empty:
                fig_rbs.add_trace(go.Scatter(
                    x=sel['total_procedures_year'],
                    y=sel['_robot_share'],
                    mode='markers',
                    marker=dict(color='#FF8C00', size=10, line=dict(color='white', width=1)),
                    name='Selected hospital',
                    hovertemplate='%{text}<br>Procedures: %{x:,}<br>Robot share: %{y:.0f}%<extra></extra>',
                    text=sel['name']
                ))
            fig_rbs.update_layout(
                height=380,
                xaxis_title='Number of procedures per year (any approach)',
                yaxis_title='Robot share (%)',
                yaxis=dict(range=[0, 100]),
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)'
            )
            st.plotly_chart(fig_rbs, use_container_width=True)
            if use_2025_rb:
                st.caption('2025 YTD (until July)')
            else:
                st.caption(f'Year used: {year_used}')
    except Exception as e:
        st.caption(f"Robot share scatter unavailable: {e}")
    st.markdown("</div>", unsafe_allow_html=True)
    
    # --- Revisional rate (bubble quartet) ---
    try:
        st.markdown("""
        <div class='nv-section'>
          <div class='nv-section-title'>Revisional rate</div>
        """, unsafe_allow_html=True)
        ytd_rev = st.toggle("Show 2025 only (data through July)", value=False, key=f"rev_toggle_{selected_hospital_id}")

        def _sum_rev_from_details(ids: list[str] | None, years: list[int]) -> tuple[float, float]:
            # Use detailed procedures to compute revisional share robustly
            df = procedure_details.copy()
            if df is None or df.empty:
                return 0.0, 0.0
            df['hospital_id'] = df['hospital_id'].astype(str)
            df['year'] = pd.to_numeric(df.get('year'), errors='coerce')
            df = df[df['year'].isin(years)]
            if ids:
                df = df[df['hospital_id'].isin([str(i) for i in ids])]
            if df.empty or 'procedure_count' not in df.columns:
                return 0.0, 0.0
            total = float(pd.to_numeric(df['procedure_count'], errors='coerce').fillna(0).sum())
            rev = 0.0
            if 'is_revision' in df.columns:
                rev = float(pd.to_numeric(df[df['is_revision'] == 1]['procedure_count'], errors='coerce').fillna(0).sum())
            else:
                # Fallback: revision not tagged
                rev = 0.0
            return rev, total

        def _sum_rev_from_vda_2025(ids: list[str] | None) -> tuple[float, float]:
            # Numerator from REDO file, denominator from VDA TOT
            try:
                redo = pd.read_csv('data/export_TAB_REDO_HOP.csv', dtype={'finessGeoDP': str, 'annee': int})
            except Exception:
                redo = pd.DataFrame()
            vda = _load_vda_year_totals_summary()
            if vda.empty or redo.empty:
                return 0.0, 0.0
            r = redo[redo['annee'] == 2025].copy()
            d = vda[vda['annee'] == 2025].copy()
            if ids:
                ids_s = [str(i) for i in ids]
                r = r[r['finessGeoDP'].astype(str).isin(ids_s)]
                d = d[d['finessGeoDP'].astype(str).isin(ids_s)]
            if r.empty or d.empty:
                return 0.0, 0.0
            # revisions are where redo == 1, count in column 'n'
            rev = float(pd.to_numeric(r[r.get('redo') == 1].get('n', 0), errors='coerce').fillna(0).sum())
            tot = float(pd.to_numeric(d.get('TOT', 0), errors='coerce').fillna(0).groupby(d['finessGeoDP']).max().sum())
            return rev, tot

        def _pct(rev: float, tot: float) -> float:
            return (rev / tot * 100.0) if tot and tot > 0 else 0.0

        # Build id groups
        def _extract_region_from_details(row) -> str | None:
            try:
                for key in ['lib_reg', 'region', 'code_reg', 'region_name']:
                    if key in row and pd.notna(row[key]) and str(row[key]).strip():
                        return str(row[key]).strip()
            except Exception:
                return None
            return None

        region_rev = _extract_region_from_details(selected_hospital_details)
        ids_all_rev = establishments['id'].astype(str).unique().tolist() if 'id' in establishments.columns else []
        ids_reg_rev = (
            establishments[establishments.get('lib_reg', establishments.get('region', '')).astype(str).str.strip() == str(region_rev)]['id'].astype(str).unique().tolist()
            if region_rev is not None and 'id' in establishments.columns else []
        )
        status_rev = str(selected_hospital_details.get('status', '')).strip()
        ids_cat_rev = (
            establishments[establishments.get('statut','').astype(str).str.strip() == status_rev]['id'].astype(str).unique().tolist()
            if 'status' in establishments.columns else []
        )

        if ytd_rev:
            # Use VDA for 2025 YTD
            h_rev, h_tot = _sum_rev_from_vda_2025([selected_hospital_id])
            n_rev, n_tot = _sum_rev_from_vda_2025(ids_all_rev)
            r_rev, r_tot = _sum_rev_from_vda_2025(ids_reg_rev)
            c_rev, c_tot = _sum_rev_from_vda_2025(ids_cat_rev)
        else:
            # Aggregate 2021–2024 from detailed procedures
            years_list = [2021, 2022, 2023, 2024]
            h_rev, h_tot = _sum_rev_from_details([selected_hospital_id], years_list)
            n_rev, n_tot = _sum_rev_from_details(ids_all_rev, years_list)
            r_rev, r_tot = _sum_rev_from_details(ids_reg_rev, years_list)
            c_rev, c_tot = _sum_rev_from_details(ids_cat_rev, years_list)

        cols = st.columns(4)
        vals = [
            (cols[0], 'Hospital', _pct(h_rev, h_tot), 'blue'),
            (cols[1], 'National', _pct(n_rev, n_tot), 'peach'),
            (cols[2], 'Regional', _pct(r_rev, r_tot), 'green'),
            (cols[3], 'Same category', _pct(c_rev, c_tot), 'pink'),
        ]
        for col, label, pctv, color in vals:
            with col:
                st.markdown(f"<div class='nv-bubble {color}' style='width:120px;height:120px;font-size:1.8rem'>{pctv:.0f}%</div>", unsafe_allow_html=True)
                st.markdown(f"<div class='nv-bubble-label'>{label}</div>", unsafe_allow_html=True)
        if ytd_rev:
            st.caption('2025 YTD (until July)')
    except Exception as e:
        st.caption(f"Revisional rate unavailable: {e}")
    st.markdown("</div>", unsafe_allow_html=True)
    
    # --- Lollipop: Revisional rate per hospital (latest year with best coverage) ---
    try:
        st.markdown("""
        <div class='nv-section'>
          <div class='nv-section-title'>Revisional rate — hospitals (latest year)</div>
        """, unsafe_allow_html=True)

        scope_rr = st.radio(
            "Compare against",
            ["National", "Regional", "Same category"],
            horizontal=True,
            index=0,
            key=f"lollipop_rev_scope_{selected_hospital_id}"
        )

        def _extract_region_from_details(row) -> str | None:
            try:
                for key in ['lib_reg', 'region', 'code_reg', 'region_name']:
                    if key in row and pd.notna(row[key]) and str(row[key]).strip():
                        return str(row[key]).strip()
            except Exception:
                return None
            return None

        region_rr = _extract_region_from_details(selected_hospital_details)
        ids_all_rr = establishments['id'].astype(str).unique().tolist() if 'id' in establishments.columns else []
        ids_reg_rr = (
            establishments[establishments.get('lib_reg', establishments.get('region', '')).astype(str).str.strip() == str(region_rr)]['id'].astype(str).unique().tolist()
            if region_rr is not None and 'id' in establishments.columns else []
        )
        status_rr = str(selected_hospital_details.get('status', '')).strip()
        ids_cat_rr = (
            establishments[establishments.get('statut','').astype(str).str.strip() == status_rr]['id'].astype(str).unique().tolist()
            if 'status' in establishments.columns else []
        )

        if scope_rr == "Regional":
            ids_filter = ids_reg_rr
        elif scope_rr == "Same category":
            ids_filter = ids_cat_rr
        else:
            ids_filter = ids_all_rr

        # Helpers to compute revisional rate per hospital for a given year
        def _rev_rate_year_2025(ids: list[str]) -> pd.DataFrame:
            try:
                redo = pd.read_csv('data/export_TAB_REDO_HOP.csv', dtype={'finessGeoDP': str, 'annee': int})
            except Exception:
                redo = pd.DataFrame()
            vda = _load_vda_year_totals_summary()
            if redo.empty or vda.empty:
                return pd.DataFrame(columns=['hid','rate'])
            r = redo[redo['annee'] == 2025].copy()
            d = vda[vda['annee'] == 2025].copy()
            if ids:
                ids_s = [str(i) for i in ids]
                r = r[r['finessGeoDP'].astype(str).isin(ids_s)]
                d = d[d['finessGeoDP'].astype(str).isin(ids_s)]
            if r.empty or d.empty:
                return pd.DataFrame(columns=['hid','rate'])
            rev_by_h = (
                r[r.get('redo') == 1]
                .groupby('finessGeoDP', as_index=False)['n']
                .sum()
                .rename(columns={'finessGeoDP':'hid','n':'rev'})
            )
            tot_by_h = (
                d.groupby('finessGeoDP', as_index=False)['TOT']
                .max()
                .rename(columns={'finessGeoDP':'hid','TOT':'tot'})
            )
            g = rev_by_h.merge(tot_by_h, on='hid', how='inner')
            g['rate'] = (pd.to_numeric(g['rev'], errors='coerce') / pd.to_numeric(g['tot'], errors='coerce')) * 100.0
            g['hid'] = g['hid'].astype(str)
            return g[['hid','rate']]

        def _rev_rate_year(ids: list[str], year: int) -> pd.DataFrame:
            df = procedure_details.copy()
            if df is None or df.empty:
                return pd.DataFrame(columns=['hid','rate'])
            df['hospital_id'] = df['hospital_id'].astype(str)
            df['year'] = pd.to_numeric(df.get('year'), errors='coerce')
            df = df[df['year'] == year]
            if ids:
                df = df[df['hospital_id'].isin([str(i) for i in ids])]
            if df.empty or 'procedure_count' not in df.columns:
                return pd.DataFrame(columns=['hid','rate'])
            grp = df.groupby('hospital_id', as_index=False).agg(
                total=('procedure_count','sum'),
                rev=('is_revision', lambda s: (s == 1).sum() if s.notna().any() else 0)
            ).rename(columns={'hospital_id':'hid'})
            grp['rate'] = (pd.to_numeric(grp['rev'], errors='coerce') / pd.to_numeric(grp['total'], errors='coerce')) * 100.0
            grp['hid'] = grp['hid'].astype(str)
            return grp[['hid','rate']]

        def _get_rev_rate_for_year(year: int, ids: list[str]) -> pd.DataFrame:
            if year == 2025:
                return _rev_rate_year_2025(ids)
            return _rev_rate_year(ids, year)

        # Pick the year with the most hospitals having data
        best_year = None
        best_df = pd.DataFrame()
        for y in [2025, 2024, 2023, 2022, 2021]:
            dfy = _get_rev_rate_for_year(y, ids_filter)
            dfy = dfy.dropna(subset=['rate'])
            if best_year is None or len(dfy) > len(best_df):
                best_year = y
                best_df = dfy
            if len(best_df) >= 200:
                break

        if best_df.empty:
            st.info('No revisional data available for this scope.')
        else:
            # Names and sorting
            name_map = establishments.set_index('id')['name'].to_dict() if 'name' in establishments.columns else {}
            best_df['name'] = best_df['hid'].map(lambda i: name_map.get(i, str(i)))
            best_df = best_df.sort_values('rate').reset_index(drop=True)
            x_pos = list(range(1, len(best_df) + 1))
            colors = ['#FF8C00' if str(h) == str(selected_hospital_id) else '#5DA5DA' for h in best_df['hid']]
            limit = st.slider("Max hospitals to display", 10, max(10, len(best_df)), len(best_df), key=f"lollipop_rev_limit_{scope_rr}")
            plot_df = best_df.tail(limit)
            x_pos = list(range(1, len(plot_df) + 1))
            colors = ['#FF8C00' if str(h) == str(selected_hospital_id) else '#5DA5DA' for h in plot_df['hid']]

            fig_ll_rev = go.Figure()
            # Stems
            for xi, yi, col in zip(x_pos, plot_df['rate'], colors):
                fig_ll_rev.add_trace(go.Scatter(x=[xi, xi], y=[0, yi], mode='lines', line=dict(color=col, width=2), showlegend=False, hoverinfo='skip'))
            # Heads
            fig_ll_rev.add_trace(go.Scatter(x=x_pos, y=plot_df['rate'], mode='markers', marker=dict(color=colors, size=8), showlegend=False, hovertemplate='%{text}<br>Revisional rate: %{y:.0f}%<extra></extra>', text=plot_df['name']))
            # Legend
            fig_ll_rev.add_trace(go.Scatter(x=[None], y=[None], mode='markers', marker=dict(color='#FF8C00', size=8), name='Selected hospital'))
            fig_ll_rev.add_trace(go.Scatter(x=[None], y=[None], mode='markers', marker=dict(color='#5DA5DA', size=8), name='Other hospitals'))
            fig_ll_rev.update_layout(height=360, xaxis_title='Hospitals', yaxis_title='Revisional rate (%)', yaxis=dict(range=[0,100]), plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', xaxis=dict(showticklabels=False))
            st.plotly_chart(fig_ll_rev, use_container_width=True)
            if best_year == 2025:
                st.caption('2025 YTD (until July)')
    except Exception as e:
        st.caption(f"Revisional lollipop unavailable: {e}")
    st.markdown("</div>", unsafe_allow_html=True)
    
    # Procedure share (3 buckets)
    proc_codes = [c for c in BARIATRIC_PROCEDURE_NAMES.keys() if c in selected_hospital_all_data.columns]
    if proc_codes:
        col1, col2 = st.columns([2, 1])  # Hospital graphs larger (2), National graphs smaller (1)
        
    # Approaches share
    appr_codes = [c for c in SURGICAL_APPROACH_NAMES.keys() if c in selected_hospital_all_data.columns]
    if appr_codes:
        # Hospital chart alone (full width)
            st.markdown("""
            <div class='nv-section'>
              <div class='nv-section-title'>Hospital: Surgical Approaches (share %)</div>
            """, unsafe_allow_html=True)
            appr_df = selected_hospital_all_data[['annee']+appr_codes].copy()
            appr_long = []
            for _, r in appr_df.iterrows():
                total = max(1, sum(r[c] for c in appr_codes))
                for code,name in SURGICAL_APPROACH_NAMES.items():
                    if code in r:
                        appr_long.append({'annee':int(r['annee']),'Approach':name,'Share':r[code]/total*100})
            al = pd.DataFrame(appr_long)
            if not al.empty:
                APPROACH_COLORS = {'Coelioscopy': '#2E86AB', 'Robotic': '#F7931E', 'Open Surgery': '#A23B72'}
                fig_bar_h = px.bar(al, x='annee', y='Share', color='Approach', barmode='stack', color_discrete_map=APPROACH_COLORS)
                fig_bar_h.update_layout(height=360, plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)')
                st.plotly_chart(fig_bar_h, use_container_width=True)
                st.caption('Year‑over‑year share of surgical approaches at the hospital (bars sum to 100%).')
            st.markdown("</div>", unsafe_allow_html=True)
        
        # Build National dataset
            st.markdown("")
            nat_appr_data = []
            for year in years_window:
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
            nat_appr_df = pd.DataFrame(nat_appr_data) if nat_appr_data else pd.DataFrame()

            # --- Regional and Same-category approaches (share %) ---
            try:
                # Build id groups
                def _extract_region_from_details(row) -> str | None:
                    try:
                        for key in ['lib_reg', 'region', 'code_reg', 'region_name']:
                            if key in row and pd.notna(row[key]) and str(row[key]).strip():
                                return str(row[key]).strip()
                    except Exception:
                        return None
                    return None

                region_value_a = _extract_region_from_details(selected_hospital_details)
                ids_reg = (
                    establishments[establishments.get('lib_reg', establishments.get('region', '')).astype(str).str.strip() == str(region_value_a)]['id'].astype(str).unique().tolist()
                    if region_value_a is not None and 'id' in establishments.columns else []
                )
                status_val_a = str(selected_hospital_details.get('status', '')).strip()
                ids_cat = (
                    establishments[establishments.get('statut','').astype(str).str.strip() == status_val_a]['id'].astype(str).unique().tolist()
                    if 'status' in establishments.columns else []
                )

                def _approach_share_for_ids(id_list: list[str]) -> pd.DataFrame:
                    if not id_list:
                        return pd.DataFrame()
                    df = annual[annual['id'].astype(str).isin([str(i) for i in id_list])].copy()
                    if df.empty:
                        return pd.DataFrame()
                    shares = []
                    for year in sorted(df['annee'].dropna().unique().tolist()):
                        yd = df[df['annee'] == year]
                        r = float(yd.get('ROB', 0).sum()) if 'ROB' in yd.columns else 0.0
                        c = float(yd.get('COE', 0).sum()) if 'COE' in yd.columns else 0.0
                        o = float(yd.get('LAP', 0).sum()) if 'LAP' in yd.columns else 0.0
                        tot = r + c + o
                        if tot > 0:
                            shares.append({'Year': int(year), 'Approach': 'Robotic', 'Share': r / tot * 100})
                            shares.append({'Year': int(year), 'Approach': 'Coelioscopy', 'Share': c / tot * 100})
                            shares.append({'Year': int(year), 'Approach': 'Open Surgery', 'Share': o / tot * 100})
                    return pd.DataFrame(shares)

                reg_share = _approach_share_for_ids(ids_reg)
                cat_share = _approach_share_for_ids(ids_cat)

                if not nat_appr_df.empty or not reg_share.empty or not cat_share.empty:
                    col_nat, col_reg, col_cat = st.columns(3)
                    # Distinct color palettes per chart (as per your picture)
                    COLORS_NAT = {'Coelioscopy': '#d08b3e', 'Robotic': '#e6a86a', 'Open Surgery': '#a8652b'}
                    COLORS_REG = {'Coelioscopy': '#4F9D69', 'Robotic': '#7DC07A', 'Open Surgery': '#2B6E4F'}
                    COLORS_CAT = {'Coelioscopy': '#B388EB', 'Robotic': '#D0A3FF', 'Open Surgery': '#8E61C6'}

                    with col_nat:
                        st.markdown("#### National: Surgical Approaches (share %)")
                        if not nat_appr_df.empty:
                            fig_nat3 = px.bar(nat_appr_df, x='Year', y='Share', color='Approach', barmode='stack', color_discrete_map=COLORS_NAT)
                            fig_nat3.update_layout(height=300, plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)')
                            st.plotly_chart(fig_nat3, use_container_width=True)
                            st.caption('National share of surgical approaches by year. Helps benchmark technique mix.')
                        else:
                            st.info('No national approach data.')

                    with col_reg:
                        st.markdown("#### Regional: Surgical Approaches (share %)")
                        if not reg_share.empty:
                            fig_r = px.bar(reg_share, x='Year', y='Share', color='Approach', barmode='stack', color_discrete_map=COLORS_REG)
                            fig_r.update_layout(height=300, plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)')
                            st.plotly_chart(fig_r, use_container_width=True)
                            st.caption('Regional share of surgical approaches by year for peer comparison.')
                        else:
                            st.info('No regional approach data.')

                    with col_cat:
                        st.markdown("#### Same category: Surgical Approaches (share %)")
                        if not cat_share.empty:
                            fig_c = px.bar(cat_share, x='Year', y='Share', color='Approach', barmode='stack', color_discrete_map=COLORS_CAT)
                            fig_c.update_layout(height=300, plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)')
                            st.plotly_chart(fig_c, use_container_width=True)
                            st.caption('Same‑category share of surgical approaches by year for like‑for‑like comparison.')
                        else:
                            st.info('No same-category approach data.')
            except Exception as e:
                st.caption(f"Approach breakdown unavailable: {e}")

        # (Removed) Robot share scatter that duplicated the end-of-section chart
        


with tab_complications:
    st.subheader("Complications")
    # Overall complication rate (90 days) — bubble quartet per design
    try:
        st.markdown("### Overall complication rate (90 days)")
        last12 = st.toggle("Last 12 months", value=False, key=f"comp_rate_last12_{selected_hospital_id}")

        # Ensure datetime and numeric types
        comp_src = complications.copy()
        if not comp_src.empty:
            if 'quarter_date' in comp_src.columns:
                comp_src['quarter_date'] = pd.to_datetime(comp_src['quarter_date'], errors='coerce')
            for c in ['complications_count','procedures_count']:
                if c in comp_src.columns:
                    comp_src[c] = pd.to_numeric(comp_src[c], errors='coerce')

        def _extract_region_from_details(row) -> str | None:
            try:
                for key in ['lib_reg', 'region', 'code_reg', 'region_name']:
                    if key in row and pd.notna(row[key]) and str(row[key]).strip():
                        return str(row[key]).strip()
            except Exception:
                return None
            return None

        region_val_c = _extract_region_from_details(selected_hospital_details)
        ids_all_c = establishments['id'].astype(str).unique().tolist() if 'id' in establishments.columns else []
        ids_reg_c = (
            establishments[establishments.get('lib_reg', establishments.get('region', '')).astype(str).str.strip() == str(region_val_c)]['id'].astype(str).unique().tolist()
            if region_val_c is not None and 'id' in establishments.columns else []
        )
        status_val_c = str(selected_hospital_details.get('statut','')).strip()
        ids_cat_c = (
            establishments[establishments.get('statut','').astype(str).str.strip() == status_val_c]['id'].astype(str).unique().tolist()
            if 'status' in establishments.columns else []
        )

        def _rate_for_ids(ids: list[str]) -> float:
            if comp_src is None or comp_src.empty:
                return 0.0
            df = comp_src.copy()
            if 'hospital_id' in df.columns:
                df['hospital_id'] = df['hospital_id'].astype(str)
                if ids:
                    df = df[df['hospital_id'].isin([str(i) for i in ids])]
            if df.empty:
                return 0.0
            if last12 and 'quarter_date' in df.columns:
                mx = df['quarter_date'].dropna().max()
                if pd.notna(mx):
                    start = (mx - pd.DateOffset(months=11))  # approx 12 months; data is quarterly so covers last 4 quarters
                    df = df[(df['quarter_date'] >= start) & (df['quarter_date'] <= mx)]
            # Sum numerator and denominator
            num = float(pd.to_numeric(df.get('complications_count', 0), errors='coerce').fillna(0).sum())
            den = float(pd.to_numeric(df.get('procedures_count', 0), errors='coerce').fillna(0).sum())
            return (num / den * 100.0) if den > 0 else 0.0

        val_h = _rate_for_ids([selected_hospital_id])
        val_n = _rate_for_ids(ids_all_c)
        val_r = _rate_for_ids(ids_reg_c)
        val_s = _rate_for_ids(ids_cat_c)

        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.markdown(f"<div class='nv-bubble blue' style='width:120px;height:120px;font-size:1.8rem'>{val_h:.1f}%</div>", unsafe_allow_html=True)
            st.markdown("<div class='nv-bubble-label'>Hospital</div>", unsafe_allow_html=True)
        with c2:
            st.markdown(f"<div class='nv-bubble peach' style='width:120px;height:120px;font-size:1.8rem'>{val_n:.1f}%</div>", unsafe_allow_html=True)
            st.markdown("<div class='nv-bubble-label'>National</div>", unsafe_allow_html=True)
        with c3:
            st.markdown(f"<div class='nv-bubble green' style='width:120px;height:120px;font-size:1.8rem'>{val_r:.1f}%</div>", unsafe_allow_html=True)
            st.markdown("<div class='nv-bubble-label'>Regional</div>", unsafe_allow_html=True)
        with c4:
            st.markdown(f"<div class='nv-bubble pink' style='width:120px;height:120px;font-size:1.8rem'>{val_s:.1f}%</div>", unsafe_allow_html=True)
            st.markdown("<div class='nv-bubble-label'>Same category</div>", unsafe_allow_html=True)
        if last12:
            st.caption("Last 12 months (approx. last 4 quarters)")
    except Exception as e:
        st.caption(f"Overall complication rate unavailable: {e}")

    # --- Funnel plot: complication rate vs volume with control limits ---
    try:
        st.markdown("#### Overall complication rate — funnel plot (90 days)")
        scope_fp = st.radio(
            "Compare against",
            ["National", "Regional", "Same status"],
            horizontal=True,
            index=0,
            key=f"funnel_scope_{selected_hospital_id}"
        )

        # Build scope ids
        def _extract_region_from_details(row) -> str | None:
            try:
                for key in ['lib_reg', 'region', 'code_reg', 'region_name']:
                    if key in row and pd.notna(row[key]) and str(row[key]).strip():
                        return str(row[key]).strip()
            except Exception:
                return None
            return None

        reg_fp = _extract_region_from_details(selected_hospital_details)
        ids_all_fp = establishments['id'].astype(str).unique().tolist() if 'id' in establishments.columns else []
        ids_reg_fp = (
            establishments[establishments.get('lib_reg', establishments.get('region', '')).astype(str).str.strip() == str(reg_fp)]['id'].astype(str).unique().tolist()
            if reg_fp is not None and 'id' in establishments.columns else []
        )
        status_fp = str(selected_hospital_details.get('status', '')).strip()
        ids_status_fp = (
            establishments[establishments.get('statut','').astype(str).str.strip() == status_fp]['id'].astype(str).unique().tolist()
            if 'status' in establishments.columns else []
        )

        if scope_fp == "Regional":
            ids_scope = ids_reg_fp
        elif scope_fp == "Same status":
            ids_scope = ids_status_fp
        else:
            ids_scope = ids_all_fp

        # Prepare data: sum events and totals over all available quarters
        comp_df = complications.copy()
        if comp_df is None or comp_df.empty:
            st.info('No complications dataset available.')
        else:
            comp_df['hospital_id'] = comp_df.get('hospital_id', '').astype(str)
            for c in ['complications_count','procedures_count']:
                if c in comp_df.columns:
                    comp_df[c] = pd.to_numeric(comp_df[c], errors='coerce').fillna(0)
            if ids_scope:
                comp_df = comp_df[comp_df['hospital_id'].isin([str(i) for i in ids_scope])]
            agg = comp_df.groupby('hospital_id', as_index=False).agg(
                events=('complications_count','sum'),
                total=('procedures_count','sum')
            )
            agg = agg[agg['total'] > 0]
            if agg.empty:
                st.info('No valid complications data for funnel plot.')
            else:
                agg['rate'] = agg['events'] / agg['total']
                # Overall mean (pooled)
                p_bar = float(agg['events'].sum() / agg['total'].sum()) if agg['total'].sum() > 0 else 0.0
                # Control limits vs volume
                vol = np.linspace(max(1, agg['total'].min()), agg['total'].max(), 200)
                se = np.sqrt(p_bar * (1 - p_bar) / vol)
                z95 = 1.96
                z99 = 3.09
                upper95 = p_bar + z95 * se
                lower95 = p_bar - z95 * se
                upper99 = p_bar + z99 * se
                lower99 = p_bar - z99 * se
                # Clip to [0,1]
                upper95 = np.clip(upper95, 0, 1); lower95 = np.clip(lower95, 0, 1)
                upper99 = np.clip(upper99, 0, 1); lower99 = np.clip(lower99, 0, 1)

                name_map = establishments.set_index('id')['name'].to_dict() if 'name' in establishments.columns else {}
                agg['name'] = agg['hospital_id'].map(lambda i: name_map.get(i, str(i)))
                sel = agg[agg['hospital_id'] == str(selected_hospital_id)]
                others = agg[agg['hospital_id'] != str(selected_hospital_id)]

                fig_fp = go.Figure()
                # Others
                fig_fp.add_trace(go.Scatter(
                    x=others['total'], y=others['rate'], mode='markers',
                    marker=dict(color='#60a5fa', size=6, opacity=0.75), name='Other hospitals',
                    hovertemplate='%{text}<br>Volume: %{x:,}<br>Rate: %{y:.1%}<extra></extra>', text=others['name']
                ))
                # Selected
                if not sel.empty:
                    fig_fp.add_trace(go.Scatter(
                        x=sel['total'], y=sel['rate'], mode='markers',
                        marker=dict(color='#FF8C00', size=12, line=dict(color='white', width=1)), name='Selected hospital',
                        hovertemplate='%{text}<br>Volume: %{x:,}<br>Rate: %{y:.1%}<extra></extra>', text=sel['name']
                    ))
                # Mean line
                fig_fp.add_trace(go.Scatter(x=[vol.min(), vol.max()], y=[p_bar, p_bar], mode='lines', line=dict(color='#888', width=1, dash='solid'), name='Mean'))
                # 95% bounds (dashed)
                fig_fp.add_trace(go.Scatter(x=vol, y=upper95, mode='lines', line=dict(color='#aaa', width=1, dash='dash'), name='95% CI'))
                fig_fp.add_trace(go.Scatter(x=vol, y=lower95, mode='lines', line=dict(color='#aaa', width=1, dash='dash'), showlegend=False))
                # 99% bounds (dotted)
                fig_fp.add_trace(go.Scatter(x=vol, y=upper99, mode='lines', line=dict(color='#aaa', width=1, dash='dot'), name='99% CI'))
                fig_fp.add_trace(go.Scatter(x=vol, y=lower99, mode='lines', line=dict(color='#aaa', width=1, dash='dot'), showlegend=False))

                fig_fp.update_layout(
                    height=420,
                    xaxis_title='Hospital volume (all techniques)',
                    yaxis_title='Complication rate', yaxis_tickformat='.0%',
                    plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)'
                )
                st.plotly_chart(fig_fp, use_container_width=True)
                st.caption('Dashed = 95% CI; dotted = 99% CI; solid = overall mean')
    except Exception as e:
        st.caption(f"Funnel plot unavailable: {e}")

    # --- Complication rate by Clavien–Dindo grade (3–5) + Never events ---
    try:
        st.markdown("#### Complication rate by Clavien–Dindo grade (90 days)")

        cl_src = clavien.copy()
        if cl_src is None or cl_src.empty:
            st.info('No Clavien–Dindo dataset available.')
        else:
            cl_src['hospital_id'] = cl_src.get('hospital_id', '').astype(str)
            cl_src['year'] = pd.to_numeric(cl_src.get('year'), errors='coerce')
            # Focus on 2021–2025 inclusive
            cl_src = cl_src[(cl_src['year'] >= 2021) & (cl_src['year'] <= 2025)]

            def _extract_region_from_details(row) -> str | None:
                try:
                    for key in ['lib_reg', 'region', 'code_reg', 'region_name']:
                        if key in row and pd.notna(row[key]) and str(row[key]).strip():
                            return str(row[key]).strip()
                except Exception:
                    return None
                return None

            region_val_g = _extract_region_from_details(selected_hospital_details)
            ids_all_g = establishments['id'].astype(str).unique().tolist() if 'id' in establishments.columns else []
            ids_reg_g = (
                establishments[establishments.get('lib_reg', establishments.get('region', '')).astype(str).str.strip() == str(region_val_g)]['id'].astype(str).unique().tolist()
                if region_val_g is not None and 'id' in establishments.columns else []
            )
            status_val_g = str(selected_hospital_details.get('status', '')).strip()
            ids_cat_g = (
                establishments[establishments.get('statut','').astype(str).str.strip() == status_val_g]['id'].astype(str).unique().tolist()
                if 'status' in establishments.columns else []
            )

            def _sum_unique_totals(df: pd.DataFrame, id_col: str) -> float:
                if 'year' in df.columns and 'total' in df.columns:
                    try:
                        grouped = df.groupby([id_col, 'year'], as_index=False)['total'].max()
                        return float(pd.to_numeric(grouped['total'], errors='coerce').fillna(0).sum())
                    except Exception:
                        return float(pd.to_numeric(df.get('total', 0), errors='coerce').fillna(0).sum())
                return float(pd.to_numeric(df.get('total', 0), errors='coerce').fillna(0).sum())

            def _grade_rates_for_ids(ids: list[str] | None) -> tuple[dict, tuple[int, int]]:
                df = cl_src.copy()
                if ids:
                    df = df[df['hospital_id'].isin([str(i) for i in ids])]
                if df.empty:
                    return ({3: 0.0, 4: 0.0, 5: 0.0}, (0, 0))
                totals = _sum_unique_totals(df, 'hospital_id')
                out = {}
                g5_n = 0
                for g in [3, 4, 5]:
                    gsum = int(pd.to_numeric(df[df.get('clavien_category') == g].get('count', 0), errors='coerce').fillna(0).sum())
                    out[g] = (gsum / totals * 100.0) if totals > 0 else 0.0
                    if g == 5:
                        g5_n = gsum
                return out, (g5_n, int(totals))

            # Compute for four groups
            rates_h, death_h = _grade_rates_for_ids([selected_hospital_id])
            rates_n, death_n = _grade_rates_for_ids(ids_all_g)
            rates_r, death_r = _grade_rates_for_ids(ids_reg_g)
            rates_c, death_c = _grade_rates_for_ids(ids_cat_g)

            # Build grouped bar data
            rows = []
            for grade in [3, 4, 5]:
                rows.append({'Grade': f'grade {grade}', 'Group': 'Hospital', 'Rate': rates_h.get(grade, 0.0)})
                rows.append({'Grade': f'grade {grade}', 'Group': 'National', 'Rate': rates_n.get(grade, 0.0)})
                rows.append({'Grade': f'grade {grade}', 'Group': 'Regional', 'Rate': rates_r.get(grade, 0.0)})
                rows.append({'Grade': f'grade {grade}', 'Group': 'Same status', 'Rate': rates_c.get(grade, 0.0)})
            df_bar = pd.DataFrame(rows)
            COLORS = {
                'Hospital': '#0b4f6c',
                'National': '#f2a777',
                'Regional': '#16a34a',
                'Same status': '#d946ef',
            }
            fig_g = px.bar(df_bar, x='Grade', y='Rate', color='Group', barmode='group', color_discrete_map=COLORS)
            fig_g.update_layout(height=360, yaxis_title='Rate (%)', plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)')
            fig_g.update_yaxes(range=[0, max(8, df_bar['Rate'].max()*1.3)])
            fig_g.update_traces(hovertemplate='%{fullData.name}<br>%{x}: %{y:.1f}%<extra></extra>')

            # Layout: chart on left, never events card on right
            left, right = st.columns([2, 1])
            with left:
                st.plotly_chart(fig_g, use_container_width=True)
            with right:
                def _fmt(n, d):
                    pct = (n / d * 100.0) if d > 0 else 0.0
                    return f"{n:,}/{d:,}", f"{pct:.1f}%"

                rows = [
                    ("Hospital", * _fmt(*death_h), "#0b4f6c"),
                    ("National", * _fmt(*death_n), "#f2a777"),
                    ("Regional", * _fmt(*death_r), "#16a34a"),
                    ("Same status", * _fmt(*death_c), "#d946ef"),
                ]
                # Inline CSS for a clear, carded table
                css = """
                <style>
                  .nv-ne-card { border:1px solid rgba(255,255,255,.2); border-radius:10px; padding:12px 14px; background:rgba(255,255,255,.04); }
                  .nv-ne-title { font-weight:800; font-size:1.05rem; text-align:center; margin:0 0 8px 0; }
                  .nv-ne-row { display:flex; align-items:center; justify-content:space-between; gap:10px; padding:8px 10px; border-radius:8px; margin:6px 0; background:rgba(0,0,0,.15); }
                  .nv-ne-left { display:flex; align-items:center; gap:10px; font-weight:600; }
                  .nv-ne-dot { width:10px; height:10px; border-radius:50%; display:inline-block; }
                  .nv-ne-num { font-weight:800; font-size:1.05rem; }
                  .nv-ne-pct { font-weight:700; opacity:.85; margin-left:8px; }
                </style>
                """
                html = [css, "<div class='nv-ne-card'>",
                        "<div class='nv-ne-title'>Never events (death)</div>"]
                for label, frac, pct, color in rows:
                    html.append(
                        f"<div class='nv-ne-row'><div class='nv-ne-left'><span class='nv-ne-dot' style='background:{color}'></span>{label}</div>"
                        f"<div><span class='nv-ne-num'>{frac}</span><span class='nv-ne-pct'> ({pct})</span></div></div>"
                    )
                html.append("</div>")
                st.markdown("".join(html), unsafe_allow_html=True)
    except Exception as e:
        st.caption(f"Clavien grade chart unavailable: {e}")

    hosp_comp = _get_hospital_complications(complications, str(selected_hospital_id)).sort_values('quarter_date')
    # Global note if 2025 data is present (YTD)
    has_2025_data = False
    try:
        if 'quarter_date' in hosp_comp.columns:
            yrs = hosp_comp['quarter_date'].dropna().dt.year
            has_2025_data = bool((yrs == 2025).any())
        elif 'year' in hosp_comp.columns:
            has_2025_data = bool((pd.to_numeric(hosp_comp['year'], errors='coerce') == 2025).any())
    except Exception:
        has_2025_data = False
    if has_2025_data:
        st.caption("Note: 2025 complication data includes records through July.")
    if not hosp_comp.empty:
        # First: Clavien–Dindo categories (moved to top of section)
        try:
            st.markdown("#### Clavien–Dindo Complication Categories (90 days)")

            # Filter Clavien for selected hospital
            cl_src = clavien.copy()
            if not cl_src.empty and 'hospital_id' in cl_src.columns:
                cl_src['hospital_id'] = cl_src['hospital_id'].astype(str)
                hos_cl = cl_src[cl_src['hospital_id'] == str(selected_hospital_id)].copy()
                if not hos_cl.empty:
                    # Ensure numeric year
                    if 'year' in hos_cl.columns:
                        hos_cl['year'] = pd.to_numeric(hos_cl['year'], errors='coerce')

                    # Toggle: 2025 only vs 2020–2025 aggregate
                    try:
                        show_2025_only = st.toggle("Show 2025 only (data through July)", value=False)
                    except Exception:
                        show_2025_only = st.checkbox("Show 2025 only (data through July)", value=False)

                    if show_2025_only and 'year' in hos_cl.columns:
                        view_df = hos_cl[hos_cl['year'] == 2025].copy()
                        title_suffix = "2025 (YTD)"
                        caption = "Note: 2025 includes data through July."
                    else:
                        # Aggregate across 2020–2025 inclusive
                        if 'year' in hos_cl.columns:
                            view_df = hos_cl[(hos_cl['year'] >= 2020) & (hos_cl['year'] <= 2025)].copy()
                        else:
                            view_df = hos_cl.copy()
                        title_suffix = "2020–2025"
                        caption = None

                    # Map categories: 0 means Clavien 0–2; 3=reoperation; 4=ICU; 5=death
                    label_map = {0: 'Clavien 0–2', 3: 'Reoperation', 4: 'ICU stay', 5: 'Death'}
                    if 'clavien_category' in view_df.columns:
                        view_df['label'] = view_df['clavien_category'].map(label_map).fillna(view_df['clavien_category'].astype(str))
                    else:
                        view_df['label'] = ''

                    # === Summary panel (Hospital vs National, grades 3–5) ===
                    def _sum_unique_totals(df: pd.DataFrame, id_col: str) -> int:
                        if 'year' in df.columns and 'total' in df.columns:
                            try:
                                grouped = df.groupby([id_col, 'year'], as_index=False)['total'].max()
                                return int(pd.to_numeric(grouped['total'], errors='coerce').fillna(0).sum())
                            except Exception:
                                return int(pd.to_numeric(df['total'], errors='coerce').fillna(0).sum())
                        return int(pd.to_numeric(df.get('total', 0), errors='coerce').fillna(0).sum())

                    # Hospital severe (3–5)
                    hosp_period_df = view_df.copy()
                    hosp_total = _sum_unique_totals(hosp_period_df, 'hospital_id')
                    hosp_grade_counts = hosp_period_df[hosp_period_df.get('clavien_category').isin([3,4,5])].groupby('clavien_category', as_index=False)['count'].sum()
                    hosp_overall_events = int(pd.to_numeric(hosp_grade_counts['count'], errors='coerce').fillna(0).sum()) if not hosp_grade_counts.empty else 0
                    hosp_overall_rate = (hosp_overall_events / hosp_total * 100.0) if hosp_total > 0 else 0.0

                    # National severe (3–5) for same period
                    nat_period_df = clavien.copy()
                    if 'year' in nat_period_df.columns and 'year' in hosp_period_df.columns:
                        years_set = sorted(hosp_period_df['year'].dropna().unique().tolist())
                        nat_period_df['year'] = pd.to_numeric(nat_period_df['year'], errors='coerce')
                        nat_period_df = nat_period_df[nat_period_df['year'].isin(years_set)]
                    nat_total = _sum_unique_totals(nat_period_df, 'hospital_id')
                    nat_grade_counts = nat_period_df[nat_period_df.get('clavien_category').isin([3,4,5])].groupby('clavien_category', as_index=False)['count'].sum()
                    nat_overall_events = int(pd.to_numeric(nat_grade_counts['count'], errors='coerce').fillna(0).sum()) if not nat_grade_counts.empty else 0
                    nat_overall_rate = (nat_overall_events / nat_total * 100.0) if nat_total > 0 else 0.0

                    # Relative delta vs national
                    rel_delta = None
                    try:
                        rel_delta = ((hosp_overall_rate - nat_overall_rate) / nat_overall_rate * 100.0) if nat_overall_rate > 0 else None
                    except Exception:
                        rel_delta = None

                    st.markdown("##### Severe complications — Clavien–Dindo grades 3–5")
                    # Card-style top row with spacing and center label
                    m1, m_mid, m3 = st.columns([1.2, 1, 1.2])
                    with m1:
                        st.markdown("<div class='nv-card'>" 
                                    + "<div class='nv-metric-title'>Hospital (overall)</div>"
                                    + f"<div class='nv-metric-value'>{hosp_overall_rate:.1f}%</div>"
                                    + (f"<div style='text-align:center;margin-top:6px;'><span class='nv-pill {('red' if (rel_delta or 0)>0 else 'green')}'>{('↑' if (rel_delta or 0)>0 else '↓')} {abs(rel_delta):.0f}% vs National</span></div>" if rel_delta is not None else "")
                                    + "</div>", unsafe_allow_html=True)
                    with m_mid:
                        st.markdown("<div class='nv-center-label'>Overall complication rate</div>", unsafe_allow_html=True)
                    with m3:
                        st.markdown("<div class='nv-card'>" 
                                    + "<div class='nv-metric-title'>National benchmark</div>"
                                    + f"<div class='nv-metric-value'>{nat_overall_rate:.1f}%</div>"
                                    + "</div>", unsafe_allow_html=True)
                    if caption:
                        st.caption(caption)

                    st.markdown("<div class='nv-row-gap'></div>", unsafe_allow_html=True)

                    # Detail cards grid: three columns (grade, hospital, national)
                    def _grade_rate(g: int, src: pd.DataFrame, total: int) -> float:
                        try:
                            c = int(pd.to_numeric(src[src.get('clavien_category') == g]['count'], errors='coerce').fillna(0).sum())
                            return (c / total * 100.0) if total > 0 else 0.0
                        except Exception:
                            return 0.0

                    h1, h2, h3 = st.columns([1, 1, 1])
                    h1.markdown("**Clavien grade**")
                    h2.markdown("**Hospital**")
                    h3.markdown("**National benchmark**")
                    for g in [3,4,5]:
                        r_h = _grade_rate(g, hosp_period_df, hosp_total)
                        r_n = _grade_rate(g, nat_period_df, nat_total)
                        better = r_h <= r_n
                        arrow = "↑" if not better else "↓"
                        pill_class = 'red' if not better else 'green'
                        c1, c2, c3 = st.columns([1, 1, 1])
                        c1.markdown(f"<div class='nv-card small' style='text-align:center;'><b>{g}</b></div>", unsafe_allow_html=True)
                        c2.markdown(f"<div class='nv-card small' style='text-align:center;'><span style='font-weight:700'>{r_h:.1f}%</span> <span class='nv-pill {pill_class}' style='margin-left:8px'>{arrow}</span></div>", unsafe_allow_html=True)
                        c3.markdown(f"<div class='nv-card small' style='text-align:center;'>{r_n:.1f}%</div>", unsafe_allow_html=True)
                else:
                    st.info("No Clavien data available for this hospital.")
            else:
                st.info("No Clavien dataset available.")
        except Exception as e:
            st.warning(f"Clavien section unavailable: {e}")

        # Prepare national quarterly average series for optional overlays used later
        @st.cache_data(show_spinner=False)
        def _calculate_national_complication_averages_for_overlay(comp_df: pd.DataFrame) -> pd.DataFrame:
            try:
                if comp_df is None or comp_df.empty or 'quarter_date' not in comp_df.columns:
                    return pd.DataFrame()
                nat = (
                    comp_df.groupby('quarter_date')
                    .agg({'complications_count': 'sum', 'procedures_count': 'sum'})
                    .reset_index()
                )
                nat['national_rate'] = (nat['complications_count'] / nat['procedures_count'] * 100)
                return nat
            except Exception:
                return pd.DataFrame()

        national_avg_data = _calculate_national_complication_averages_for_overlay(complications)

        # Length of stay distribution (recreated as 100% stacked bar)
        try:
            st.markdown("#### Length of Stay (days) — distribution by year")
            df_los = los_90.copy()
            required_cols = ['finessGeoDP','annee','duree_90_cat','PCT']
            # Fallback to CSV if parquet bundle is empty OR missing required columns
            needs_fallback = (df_los is None or df_los.empty or any(c not in df_los.columns for c in required_cols))
            if needs_fallback:
                loaded = False
                for sep in [',',';']:
                    try:
                        tmp = pd.read_csv('data/export_TAB_LOS_HOP_90.csv', sep=sep)
                        if not tmp.empty and all(c in tmp.columns for c in required_cols):
                            df_los = tmp
                            loaded = True
                            break
                    except Exception:
                        continue
                if not loaded:
                    df_los = pd.DataFrame()
            if not df_los.empty and all(c in df_los.columns for c in required_cols):
                # Normalize types
                df_los['finessGeoDP'] = df_los['finessGeoDP'].astype(str).str.strip()
                hos_los = df_los[df_los['finessGeoDP'] == str(selected_hospital_id)].copy()
                if not hos_los.empty:
                    # Map categories to friendly labels matching requested buckets
                    cat_map = {
                        '[-1,0]': '0',
                        '(0,3]': '1–3',
                        '(3,6]': '4–6',
                        '(6,480]': '≥7'
                    }
                    hos_los['bucket'] = hos_los['duree_90_cat'].map(cat_map).fillna(hos_los['duree_90_cat'])
                    hos_los['annee'] = pd.to_numeric(hos_los['annee'], errors='coerce')
                    hos_los['PCT'] = pd.to_numeric(hos_los['PCT'], errors='coerce').fillna(0)
                    # Keep desired order and ensure all buckets exist for each year
                    bucket_order = ['0','1–3','4–6','≥7']
                    years = sorted(hos_los['annee'].dropna().unique().astype(int).tolist())
                    if years:
                        idx = pd.MultiIndex.from_product([years, bucket_order], names=['annee','bucket'])
                        hos_los_idx = hos_los.set_index(['annee','bucket'])
                        hos_los_full = hos_los_idx.reindex(idx).reset_index()
                        hos_los_full['PCT'] = pd.to_numeric(hos_los_full['PCT'], errors='coerce').fillna(0)
                        # Build stacked 100% bars
                        COLORS = {
                            '0': '#4b2e83',    # purple
                            '1–3': '#2b6cb0',  # blue
                            '4–6': '#2FBF71',  # green
                            '≥7': '#f2c94c'    # yellow
                        }
                        fig_los = px.bar(
                            hos_los_full,
                            x='annee',
                            y='PCT',
                            color='bucket',
                            category_orders={'bucket': bucket_order},
                            color_discrete_map=COLORS,
                            barmode='stack',
                            title='Length of stay distribution by year (share %)' 
                        )
                        fig_los.update_layout(
                            height=320,
                            yaxis_title='% of stays',
                            xaxis_title='Year',
                            plot_bgcolor='rgba(0,0,0,0)',
                            paper_bgcolor='rgba(0,0,0,0)'
                        )
                        fig_los.update_yaxes(range=[0, 100])
                        # Clean hover template
                        fig_los.update_traces(hovertemplate='Year: %{x}<br>%{fullData.name}: %{y:.0f}%<extra></extra>')
                        st.plotly_chart(fig_los, use_container_width=True)

                        # Mini charts for National, Regional, Same category
                        def _los_share_for_ids(df_all: pd.DataFrame, ids: list[str] | None) -> pd.DataFrame:
                            d = df_all.copy()
                            if ids:
                                d = d[d['finessGeoDP'].astype(str).isin([str(i) for i in ids])]
                            if d.empty:
                                return pd.DataFrame()
                            tmp = d.copy()
                            tmp['bucket'] = tmp['duree_90_cat'].map(cat_map).fillna(tmp['duree_90_cat'])
                            tmp['PCT'] = pd.to_numeric(tmp['PCT'], errors='coerce').fillna(0)
                            g = tmp.groupby(['annee','bucket'], as_index=False)['PCT'].mean()
                            return g

                        # Build id lists
                        def _extract_region_from_details(row) -> str | None:
                            try:
                                for key in ['lib_reg', 'region', 'code_reg', 'region_name']:
                                    if key in row and pd.notna(row[key]) and str(row[key]).strip():
                                        return str(row[key]).strip()
                            except Exception:
                                return None
                            return None

                        reg_val_l = _extract_region_from_details(selected_hospital_details)
                        ids_all_l = establishments['id'].astype(str).unique().tolist() if 'id' in establishments.columns else []
                        ids_reg_l = (
                            establishments[establishments.get('lib_reg', establishments.get('region', '')).astype(str).str.strip() == str(reg_val_l)]['id'].astype(str).unique().tolist()
                            if reg_val_l is not None and 'id' in establishments.columns else []
                        )
                        status_val_l = str(selected_hospital_details.get('status', '')).strip()
                        ids_cat_l = (
                            establishments[establishments.get('statut','').astype(str).str.strip() == status_val_l]['id'].astype(str).unique().tolist()
                            if 'status' in establishments.columns else []
                        )

                        g_nat = _los_share_for_ids(df_los, ids_all_l)
                        g_reg = _los_share_for_ids(df_los, ids_reg_l)
                        g_cat = _los_share_for_ids(df_los, ids_cat_l)

                        c_nat, c_reg, c_cat = st.columns(3)
                        def _mini(fig_df, title, color_map):
                            if fig_df is None or fig_df.empty:
                                st.info(f'No data for {title.lower()}.')
                                return
                            figm = px.bar(fig_df, x='annee', y='PCT', color='bucket', barmode='stack', category_orders={'bucket': bucket_order}, color_discrete_map=color_map)
                            figm.update_layout(height=160, margin=dict(l=10,r=10,t=20,b=10), showlegend=False, plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', title=title, title_x=0.5)
                            figm.update_yaxes(range=[0, 100])
                            st.plotly_chart(figm, use_container_width=True)

                        with c_nat:
                            _mini(g_nat, 'National', {'0':'#f2a777','1–3':'#e59a6a','4–6':'#d98c5d','≥7':'#cc7e50'})
                        with c_reg:
                            _mini(g_reg, 'Regional', {'0':'#2B6E4F','1–3':'#3C8D63','4–6':'#4FAE7A','≥7':'#7DC07A'})
                        with c_cat:
                            _mini(g_cat, 'Same category', {'0':'#8E61C6','1–3':'#A77BD8','4–6':'#C095EA','≥7':'#D0A3FF'})

                        # Bubble panel: average % of patients with LOS ≥7 days (across 2021–2025)
                        try:
                            def _avg_ge7(df_group: pd.DataFrame) -> float:
                                if df_group is None or df_group.empty:
                                    return 0.0
                                d = df_group[df_group['bucket'] == '≥7']
                                if d.empty:
                                    return 0.0
                                return float(pd.to_numeric(d['PCT'], errors='coerce').fillna(0).mean())

                            p_h = _avg_ge7(hos_los_full)
                            p_n = _avg_ge7(g_nat)
                            p_r = _avg_ge7(g_reg)
                            p_c = _avg_ge7(g_cat)

                            st.markdown("#### Patients ≥7 days of 90d‑LOS")
                            b1, b2, b3, b4 = st.columns(4)
                            with b1:
                                st.markdown(f"<div class='nv-bubble blue' style='width:110px;height:110px;font-size:1.6rem'>{p_h:.1f}%</div>", unsafe_allow_html=True)
                                st.markdown("<div class='nv-bubble-label'>Hospital</div>", unsafe_allow_html=True)
                            with b2:
                                st.markdown(f"<div class='nv-bubble peach' style='width:110px;height:110px;font-size:1.6rem'>{p_n:.1f}%</div>", unsafe_allow_html=True)
                                st.markdown("<div class='nv-bubble-label'>National</div>", unsafe_allow_html=True)
                            with b3:
                                st.markdown(f"<div class='nv-bubble green' style='width:110px;height:110px;font-size:1.6rem'>{p_r:.1f}%</div>", unsafe_allow_html=True)
                                st.markdown("<div class='nv-bubble-label'>Regional</div>", unsafe_allow_html=True)
                            with b4:
                                st.markdown(f"<div class='nv-bubble pink' style='width:110px;height:110px;font-size:1.6rem'>{p_c:.1f}%</div>", unsafe_allow_html=True)
                                st.markdown("<div class='nv-bubble-label'>Same category</div>", unsafe_allow_html=True)
                        except Exception:
                            pass

                        # Scatter: share of stays ≥7 days vs average annual volume
                        st.markdown("#### 90d‑LOS — % ≥7 days vs volume")
                        scope_los_sc = st.radio(
                            "Compare against",
                            ["National", "Regional", "Same status"],
                            horizontal=True,
                            index=0,
                            key=f"los_scatter_scope_{selected_hospital_id}"
                        )

                        # Build scope ids
                        def _extract_region_from_details(row) -> str | None:
                            try:
                                for key in ['lib_reg', 'region', 'code_reg', 'region_name']:
                                    if key in row and pd.notna(row[key]) and str(row[key]).strip():
                                        return str(row[key]).strip()
                            except Exception:
                                return None
                            return None

                        reg_sc = _extract_region_from_details(selected_hospital_details)
                        ids_all_sc = establishments['id'].astype(str).unique().tolist() if 'id' in establishments.columns else []
                        ids_reg_sc = (
                            establishments[establishments.get('lib_reg', establishments.get('region', '')).astype(str).str.strip() == str(reg_sc)]['id'].astype(str).unique().tolist()
                            if reg_sc is not None and 'id' in establishments.columns else []
                        )
                        status_sc = str(selected_hospital_details.get('status', '')).strip()
                        ids_cat_sc = (
                            establishments[establishments.get('statut','').astype(str).str.strip() == status_sc]['id'].astype(str).unique().tolist()
                            if 'status' in establishments.columns else []
                        )
                        if scope_los_sc == "Regional":
                            ids_scope_sc = ids_reg_sc
                        elif scope_los_sc == "Same status":
                            ids_scope_sc = ids_cat_sc
                        else:
                            ids_scope_sc = ids_all_sc

                        # Prepare LOS >=7% per hospital averaged across 2021–2025
                        los_all = df_los.copy()
                        los_all['annee'] = pd.to_numeric(los_all.get('annee'), errors='coerce')
                        los_all = los_all[(los_all['annee'] >= 2021) & (los_all['annee'] <= 2025)]
                        los_all['finessGeoDP'] = los_all['finessGeoDP'].astype(str)
                        los_all['bucket'] = los_all['duree_90_cat'].map(cat_map).fillna(los_all['duree_90_cat'])
                        los_all['PCT'] = pd.to_numeric(los_all['PCT'], errors='coerce').fillna(0)
                        los_ge7 = los_all[los_all['bucket'] == '≥7']
                        if ids_scope_sc:
                            los_ge7 = los_ge7[los_ge7['finessGeoDP'].isin([str(i) for i in ids_scope_sc])]
                        ge7_by_h = los_ge7.groupby('finessGeoDP', as_index=False)['PCT'].mean().rename(columns={'finessGeoDP':'hid','PCT':'ge7_pct'})

                        # Average annual volume from annual (2021–2025)
                        ann = annual.copy()
                        ann = ann[(ann.get('annee') >= 2021) & (ann.get('annee') <= 2025)]
                        ann['id'] = ann['id'].astype(str)
                        if ids_scope_sc:
                            ann = ann[ann['id'].isin([str(i) for i in ids_scope_sc])]
                        vol = ann.groupby('id', as_index=False)['total_procedures_year'].mean().rename(columns={'id':'hid','total_procedures_year':'avg_vol'})

                        merged = ge7_by_h.merge(vol, on='hid', how='inner')
                        if not merged.empty:
                            name_map = establishments.set_index('id')['name'].to_dict() if 'name' in establishments.columns else {}
                            merged['name'] = merged['hid'].map(lambda i: name_map.get(i, str(i)))
                            sel = merged[merged['hid'] == str(selected_hospital_id)]
                            oth = merged[merged['hid'] != str(selected_hospital_id)]
                            fig_los_sc = go.Figure()
                            fig_los_sc.add_trace(go.Scatter(
                                x=oth['avg_vol'], y=oth['ge7_pct'], mode='markers',
                                marker=dict(color='#60a5fa', size=6, opacity=0.75), name='Other hospitals',
                                hovertemplate='%{text}<br>Avg volume: %{x:.0f}<br>% ≥7 days: %{y:.0f}%<extra></extra>', text=oth['name']
                            ))
                            if not sel.empty:
                                fig_los_sc.add_trace(go.Scatter(
                                    x=sel['avg_vol'], y=sel['ge7_pct'], mode='markers',
                                    marker=dict(color='#FF8C00', size=12, line=dict(color='white', width=1)), name='Selected hospital',
                                    hovertemplate='%{text}<br>Avg volume: %{x:.0f}<br>% ≥7 days: %{y:.0f}%<extra></extra>', text=sel['name']
                                ))
                            fig_los_sc.update_layout(height=360, xaxis_title='Number of procedures per year (any approach)', yaxis_title='≥7 day of admission (%)', yaxis=dict(range=[0,100]), plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)')
                            st.plotly_chart(fig_los_sc, use_container_width=True)
                        else:
                            st.info('No data to build LOS scatter for this scope.')
                    else:
                        st.info('No LOS years available for this hospital.')
                else:
                    st.info('No length of stay data found for this hospital.')
            else:
                st.info('Length of stay dataset unavailable.')
        except Exception:
            pass

        # 12‑month rolling complication rate for this hospital
        try:
            st.markdown("#### Hospital 12‑month Rolling Complication Rate")
            if has_2025_data:
                st.caption("Note: If present, 2025 data includes records through July.")

            @st.cache_data(show_spinner=False)
            def _load_external_rolling_csv(path: str = "data/22_complication_trimestre.csv") -> pd.DataFrame:
                try:
                    df = pd.read_csv(path, sep=';', dtype=str)
                    # Normalize column names
                    df.columns = [c.strip().strip('"').lower() for c in df.columns]
                    # Parse dates and numerics (commas to dots if present)
                    if 'trimestre_date' in df.columns:
                        df['trimestre_date'] = pd.to_datetime(df['trimestre_date'], errors='coerce')
                    for col in ['taux_glissant','moyenne_nationale','ic_low','ic_high']:
                        if col in df.columns:
                            df[col] = pd.to_numeric(df[col].astype(str).str.replace(',', '.', regex=False), errors='coerce')
                    if 'finessgeodp' in df.columns:
                        df['finessgeodp'] = df['finessgeodp'].astype(str).str.strip()
                    return df
                except Exception:
                    return pd.DataFrame()

            ext = _load_external_rolling_csv()
            used_external = False
            fig_roll = go.Figure()
            if not ext.empty and 'finessgeodp' in ext.columns:
                hosp_ext = ext[ext['finessgeodp'] == str(selected_hospital_id)].copy()
                if not hosp_ext.empty and 'trimestre_date' in hosp_ext.columns and 'taux_glissant' in hosp_ext.columns:
                    hosp_ext = hosp_ext.dropna(subset=['trimestre_date']).sort_values('trimestre_date')
                    fig_roll.add_trace(go.Scatter(
                        x=hosp_ext['trimestre_date'],
                        y=hosp_ext['taux_glissant'],
                        mode='lines+markers',
                        name='Hospital Rolling Rate',
                        line=dict(color='#ff7f0e', width=3),
                        marker=dict(size=6, color='#ff7f0e')
                    ))
                    # National series from same CSV (deduplicate by date)
                    if 'moyenne_nationale' in hosp_ext.columns:
                        nat_series = hosp_ext.dropna(subset=['moyenne_nationale'])[['trimestre_date','moyenne_nationale']].drop_duplicates('trimestre_date')
                        if not nat_series.empty:
                            fig_roll.add_trace(go.Scatter(
                                x=nat_series['trimestre_date'],
                                y=nat_series['moyenne_nationale'],
                                mode='lines',
                                name='National Average',
                                line=dict(color='#1f77b4', width=2, dash='dash')
                            ))
                    used_external = True

            if not used_external:
                # Fallback to computing from internal aggregates
                roll = hosp_comp.dropna(subset=['quarter_date']).sort_values('quarter_date').copy()
                if not roll.empty:
                    if 'rolling_rate' in roll.columns:
                        roll['rolling_pct'] = pd.to_numeric(roll['rolling_rate'], errors='coerce') * 100.0
                    else:
                        roll['complications_count'] = pd.to_numeric(roll.get('complications_count', 0), errors='coerce').fillna(0)
                        roll['procedures_count'] = pd.to_numeric(roll.get('procedures_count', 0), errors='coerce').fillna(0)
                        denom = roll['procedures_count'].rolling(window=4, min_periods=1).sum()
                        num = roll['complications_count'].rolling(window=4, min_periods=1).sum()
                        roll['rolling_pct'] = (num / denom.replace({0: pd.NA})) * 100.0
                    roll['rolling_pct'] = pd.to_numeric(roll['rolling_pct'], errors='coerce')
                    roll_plot = roll.dropna(subset=['rolling_pct'])
                    if not roll_plot.empty:
                        fig_roll.add_trace(go.Scatter(
                            x=roll_plot['quarter_date'],
                            y=roll_plot['rolling_pct'],
                            mode='lines+markers',
                            name='Hospital Rolling Rate',
                            line=dict(color='#ff7f0e', width=3),
                            marker=dict(size=6, color='#ff7f0e')
                        ))
                    else:
                        fig_roll.add_annotation(xref='paper', yref='paper', x=0.5, y=0.5, text='No valid hospital rolling data', showarrow=False)

                    # Optional national overlay from earlier calc
                    try:
                        if 'national_avg_data' in locals() and not national_avg_data.empty and 'national_rate' in national_avg_data.columns:
                            roll_nat_name = 'National Average (YTD)' if has_2025_data else 'National Average'
                            fig_roll.add_trace(go.Scatter(
                                x=national_avg_data['quarter_date'],
                                y=national_avg_data['national_rate'],
                                mode='lines',
                                name=roll_nat_name,
                                line=dict(color='#1f77b4', width=2, dash='dash')
                            ))
                    except Exception:
                        pass

            fig_roll.update_layout(
                title='Hospital 12‑month Rolling Complication Rate',
                xaxis_title='Quarter',
                yaxis_title='Complication Rate (%)',
                height=400,
                hovermode='x unified',
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)'
            )

            st.plotly_chart(fig_roll, use_container_width=True)
        except Exception:
            pass

        # Removed Quarterly Rate vs National chart due to unreliable hospital quarterly data

        
    # Kaplan–Meier style survival curve using robust system
    # try:
    #     st.markdown("#### Kaplan–Meier (approx.) — 6‑month complication rate")
    #     
    #     # Import new KM system
    #     from km import compute_complication_rates_from_aggregates
    #     from charts import create_km_chart, create_multi_km_chart  
    #     from utils.cache import debug_dataframe_signature, show_debug_panel
    #     
    #     # Debug signatures
    #     debug_signatures = {}
    #     
    #     # Get hospital-specific complications data
    #     km_src = _get_hospital_complications(complications, str(selected_hospital_id)).copy()
    #     debug_signatures['hospital_complications'] = debug_dataframe_signature(km_src, f"Hospital {selected_hospital_id} complications")
    #     
    #     if not km_src.empty and 'quarter_date' in km_src.columns:
    #         km_src = km_src.sort_values('quarter_date')
    #         km_src['year'] = km_src['quarter_date'].dt.year
    #         km_src['half'] = ((km_src['quarter_date'].dt.quarter - 1) // 2 + 1)
    #         km_src['semester'] = km_src['year'].astype(str) + ' H' + km_src['half'].astype(int).astype(str)
    #         
    #         # Aggregate by semester
    #         sem = km_src.groupby(['year','half','semester'], as_index=False).agg(
    #             events=('complications_count','sum'),
    #             total=('procedures_count','sum')
    #         ).sort_values(['year','half'])
    #         
    #         debug_signatures['semester_aggregated'] = debug_dataframe_signature(sem, "Aggregated by semester")
    #         
    #         if not sem.empty:
    #             try:
    #                 # Use robust KM computation
    #                 km_curve = compute_complication_rates_from_aggregates(
    #                     df=sem,
    #                     time_col='semester',
    #                     event_col='events',
    #                     at_risk_col='total', 
    #                     group_cols=None,  # Single hospital
    #                     data_hash=debug_signatures['semester_aggregated']['hash'],
    #                     cache_version="v1"
    #                 )
    #                 
    #                 debug_signatures['km_curve'] = debug_dataframe_signature(km_curve, "Final KM curve")
    #                 
    #                 if not km_curve.empty:
    #                     # Compute national comparison curve (same 6‑month buckets)
    #                     fig_km_nat = None
    #                     try:
    #                         nat_src = complications.copy()
    #                         if not nat_src.empty and 'quarter_date' in nat_src.columns:
    #                             nat_src = nat_src.dropna(subset=['quarter_date']).sort_values('quarter_date')
    #                             nat_src['year'] = nat_src['quarter_date'].dt.year
    #                             nat_src['half'] = ((nat_src['quarter_date'].dt.quarter - 1) // 2 + 1)
    #                             nat_src['semester'] = nat_src['year'].astype(str) + ' H' + nat_src['half'].astype(int).astype(str)
    #                             nat_sem = (
    #                                 nat_src.groupby(['year','half','semester'], as_index=False)
    #                                       .agg(events=('complications_count','sum'), total=('procedures_count','sum'))
    #                                       .sort_values(['year','half'])
    #                             )
    #                             if not nat_sem.empty:
    #                                 nat_sig = debug_dataframe_signature(nat_sem, "National semester aggregated")
    #                                 km_curve_nat = compute_complication_rates_from_aggregates(
    #                                     df=nat_sem,
    #                                     time_col='semester',
    #                                     event_col='events',
    #                                     at_risk_col='total',
    #                                     group_cols=None,
    #                                     data_hash=nat_sig['hash'],
    #                                     cache_version="v1"
    #                                 )
    #                                 if not km_curve_nat.empty:
    #                                     fig_km_nat = km_curve_nat
    #                     except Exception as _:
    #                         fig_km_nat = None
    # 
    #                     # Render overlayed comparison chart
    #                     curves_to_plot = {"Hospital": km_curve}
    #                     if fig_km_nat is not None:
    #                         curves_to_plot["National"] = fig_km_nat
    #                     overlay_title = "Hospital vs National Complication Rate Over Time (KM, YTD)" if has_2025_data else "Hospital vs National Complication Rate Over Time (KM)"
    #                     overlay_fig = create_multi_km_chart(
    #                         curves_dict=curves_to_plot,
    #                         title=overlay_title,
    #                                         yaxis_title='Complication Rate (%)',
    #                                         xaxis_title='6‑month interval',
    #                                         height=400,
    #                         colors=['#1f77b4', '#d62728']
    #                     )
    #                     st.plotly_chart(overlay_fig, use_container_width=True, key=f"km_overlay_{selected_hospital_id}_v2")
    # 
    #                     if has_2025_data:
    #                         st.caption("Note: 2025 data includes records through July.")
    # 
    #                     with st.expander('Method (approximation)'):
    #                         st.markdown("This curve approximates a Kaplan–Meier survival function using aggregate 6‑month intervals. For each interval, hazard = events / total procedures, and survival multiplies (1 − hazard) across intervals. It uses hospital‑ and national‑level aggregates (not patient‑level times).")
    #                 else:
    #                     st.info('KM computation returned empty results.')
    #                     
    #             except Exception as e:
    #                 st.error(f"Error in KM computation: {e}")
    #                 debug_signatures['km_error'] = {'error': str(e)}
    #         else:
    #             st.info('Not enough data to compute 6‑month Kaplan–Meier curve.')
    #             debug_signatures['no_semester_data'] = {'message': 'No semester aggregated data'}
    #     else:
    #         st.info('Complication data unavailable for Kaplan–Meier computation.')
    #         debug_signatures['no_raw_data'] = {'message': 'No hospital complications data'}
    #     
    #     # Show debug panel for this hospital (collapsed by default)
    #     if st.checkbox("Show KM debug info", value=False, key=f"km_debug_hospital_{selected_hospital_id}"):
    #         show_debug_panel(debug_signatures, expanded=True)
    #         
    # except Exception as e:
    #     st.error(f"Error computing KM: {e}")

    # Removed approach-specific complication rates (hospital and national) per request

    # Removed Revisions by Procedure Type (2024) deep-dive per request

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
            
            # Show GeoJSON status and add cache controls
            # Removed GeoJSON status and cache controls per request
            
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
            
            # Diagnostics panel removed per request
                
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

# Get competitors for this hospital
hospital_competitors = competitors[competitors['hospital_id'] == str(selected_hospital_id)]

if not hospital_competitors.empty:
    st.markdown("#### Top 5 Competitors (Same Territory)")
    st.caption("These hospitals recruit patients from the same geographic areas")
    
    # Create columns for competitor display
    competitors_with_names = hospital_competitors.merge(
        establishments[['id', 'name', 'city', 'status']], 
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
            competitor_city = competitor.get('city', 'Unknown City')
            st.markdown(f"**{competitor_name}**")
            st.caption(f"📍 {competitor_city}")
        
        with col2:
            competitor_status = competitor.get('status', 'Unknown')
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
# --- NEW CSV-BASED CHARTS SECTION ---
st.header("📈 Enhanced Analytics (CSV Data)")

# Add toggle for CSV-based charts
use_csv_charts = st.checkbox("Use enhanced CSV-based charts", value=True, help="Toggle to use the new CSV data sources for more detailed analytics")

if use_csv_charts:
    st.markdown("### Procedure Mix Analysis")
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**Hospital Level**")
        procedure_mix_fig = create_procedure_mix_chart(
            hospital_id=selected_hospital_id, 
            level='HOP', 
            title="Hospital Procedure Mix"
        )
        st.plotly_chart(procedure_mix_fig, use_container_width=True)
    
    with col2:
        st.markdown("**National Level**")
        procedure_mix_nat_fig = create_procedure_mix_chart(
            hospital_id=None, 
            level='NATL', 
            title="National Procedure Mix"
        )
        st.plotly_chart(procedure_mix_nat_fig, use_container_width=True)
    
    st.markdown("### Surgical Approaches Analysis")
    col3, col4 = st.columns(2)
    
    with col3:
        st.markdown("**Hospital Level**")
        approaches_fig = create_surgical_approaches_chart(
            hospital_id=selected_hospital_id, 
            level='HOP', 
            title="Hospital Surgical Approaches"
        )
        st.plotly_chart(approaches_fig, use_container_width=True)
    
    with col4:
        st.markdown("**National Level**")
        approaches_nat_fig = create_surgical_approaches_chart(
            hospital_id=None, 
            level='NATL', 
            title="National Surgical Approaches"
        )
        st.plotly_chart(approaches_nat_fig, use_container_width=True)
    
    st.markdown("### Volume Trends")
    volume_trend_fig = create_volume_trend_chart(
        hospital_id=selected_hospital_id, 
        level='HOP', 
        title="Hospital Volume Trends"
    )
    st.plotly_chart(volume_trend_fig, use_container_width=True)
    
    st.markdown("### Revision Surgery Analysis")
    col5, col6 = st.columns(2)
    
    with col5:
        st.markdown("**Hospital Revision Rate**")
        revision_fig = create_revision_rate_chart(
            hospital_id=selected_hospital_id, 
            level='HOP', 
            title="Hospital Revision Surgeries"
        )
        st.plotly_chart(revision_fig, use_container_width=True)
    
    with col6:
        st.markdown("**Robotic Surgery Share**")
        robotic_fig = create_robotic_surgery_chart(
            hospital_id=selected_hospital_id, 
            title="Robotic Surgery Share"
        )
        st.plotly_chart(robotic_fig, use_container_width=True)

# --- NEW COMPLICATIONS, LOS, AND NEVER EVENTS SECTION ---
st.header("🏥 Clinical Quality Analytics (New Data)")

# Add toggle for new clinical quality charts
use_clinical_charts = st.checkbox("Use new clinical quality analytics", value=True, help="Toggle to use the new complications, LOS, and Never Events data sources")

if use_clinical_charts:
    st.markdown("### Complications Analysis")
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**Hospital Complications Rate**")
        complications_fig = create_complications_rate_chart(
            hospital_id=selected_hospital_id, 
            level='HOP', 
            timeframe='YEAR',
            title="Hospital Complications Rate"
        )
        st.plotly_chart(complications_fig, use_container_width=True)
    
    with col2:
        st.markdown("**National Complications Rate**")
        complications_nat_fig = create_complications_rate_chart(
            hospital_id=None, 
            level='NATL', 
            timeframe='YEAR',
            title="National Complications Rate"
        )
        st.plotly_chart(complications_nat_fig, use_container_width=True)
    
    st.markdown("### Complications by Grade")
    complications_grade_fig = create_complications_grade_chart(
        hospital_id=selected_hospital_id, 
        level='HOP', 
        title="Hospital Complications by Clavien-Dindo Grade"
    )
    st.plotly_chart(complications_grade_fig, use_container_width=True)
    
    st.markdown("### Length of Stay Analysis")
    col3, col4 = st.columns(2)
    
    with col3:
        st.markdown("**LOS Distribution**")
        los_fig = create_los_distribution_chart(
            hospital_id=selected_hospital_id, 
            level='HOP', 
            title="Hospital Length of Stay Distribution"
        )
        st.plotly_chart(los_fig, use_container_width=True)
    
    with col4:
        st.markdown("**Extended LOS (>7 days)**")
        extended_los_fig = create_extended_los_chart(
            hospital_id=selected_hospital_id, 
            level='HOP', 
            title="Extended Length of Stay"
        )
        st.plotly_chart(extended_los_fig, use_container_width=True)
    
    st.markdown("### Never Events Analysis")
    col5, col6 = st.columns(2)
    
    with col5:
        st.markdown("**Hospital Never Events**")
        never_events_fig = create_never_events_chart(
            hospital_id=selected_hospital_id, 
            level='HOP', 
            title="Hospital Never Events Rate"
        )
        st.plotly_chart(never_events_fig, use_container_width=True)
    
    with col6:
        st.markdown("**National Never Events**")
        never_events_nat_fig = create_never_events_chart(
            hospital_id=None, 
            level='NATL', 
            title="National Never Events Rate"
        )
        st.plotly_chart(never_events_nat_fig, use_container_width=True)

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
                  Annual total surgeries performed at the selected hospital (2020–{latest_year_activity}{ytd_suffix}).
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
                    - {latest_year_activity}{ytd_suffix} value: **{int(last_row['total_procedures_year']):,}**
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
        tabs = st.tabs(["National over time", f"{latest_year_activity}{ytd_suffix} mix"])
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
                year_sel = selected_hospital_all_data[selected_hospital_all_data['annee'] == latest_year_activity]
                hosp_counts = {}
                for code, name in BARIATRIC_PROCEDURE_NAMES.items():
                    if code in year_sel.columns:
                        hosp_counts[name] = int(year_sel[code].sum())
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

                nat_sel = annual[annual['annee'] == latest_year_activity]
                if 'total_procedures_year' in nat_sel.columns:
                    nat_sel = nat_sel[nat_sel['total_procedures_year'] >= 25]
                nat_counts = {}
                for code, name in BARIATRIC_PROCEDURE_NAMES.items():
                    if code in nat_sel.columns:
                        nat_counts[name] = int(nat_sel[code].sum())
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
                    barmode='group', height=360, title=f'{latest_year_activity}{ytd_suffix} Procedure Mix: Hospital vs National',
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
        tabs2 = st.tabs(["National over time", f"{latest_year_activity}{ytd_suffix} mix"])
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
                year_sel = selected_hospital_all_data[selected_hospital_all_data['annee'] == latest_year_activity]
                h_counts = {}
                for code, name in SURGICAL_APPROACH_NAMES.items():
                    if code in year_sel.columns:
                        h_counts[name] = int(year_sel[code].sum())
                h_tot = sum(h_counts.values()) or 1
                h_pct = {k: (v / h_tot * 100) for k, v in h_counts.items()}

                nat_sel2 = annual[annual['annee'] == latest_year_activity]
                if 'total_procedures_year' in nat_sel2.columns:
                    nat_sel2 = nat_sel2[nat_sel2['total_procedures_year'] >= 25]
                n_counts = {}
                for code, name in SURGICAL_APPROACH_NAMES.items():
                    if code in nat_sel2.columns:
                        n_counts[name] = int(nat_sel2[code].sum())
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
                    barmode='group', height=360, title=f'{latest_year_activity}{ytd_suffix} Approach Mix: Hospital vs National',
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
    
    # Show current year (latest, possibly 2025 YTD) robotic rates
    current_year_rates = robotic_rates[robotic_rates['year'] == latest_year_activity]
    if not current_year_rates.empty:
        st.markdown(f"##### {latest_year_activity}{ytd_suffix} Robotic Adoption by Procedure Type")
        
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
