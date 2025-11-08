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
        st.info("Loaded establishments data directly (session state was empty)")
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
    st.warning(f"No annual data found for hospital {selected_hospital_id}")
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

# Debug info (can be removed later)
if st.checkbox("Show debug info", value=False):
    st.write(f"**Data Status:**")
    st.write(f"- Establishments loaded: {not establishments.empty} ({len(establishments)} rows)")
    st.write(f"- Annual data loaded: {not annual.empty} ({len(annual)} rows)")
    st.write(f"- Selected hospital ID: {selected_hospital_id}")
    st.write(f"- Hospital details keys: {list(selected_hospital_details.keys()) if not est_row.empty else 'N/A'}")
    st.write(f"- Selected hospital all data: {len(selected_hospital_all_data)} rows")

# Helper to load monthly data for YoY estimate (YTD)
@st.cache_data(show_spinner=False)
def _load_monthly_volumes_summary(path: str = "data/export_TAB_VOL_MOIS_TCN_HOP.csv", cache_buster: str = "") -> pd.DataFrame:
    if ONLY_ACTIVITY_DATA:
        return pd.DataFrame()
    try:
        df = pd.read_csv(path, dtype={'finessGeoDP': str, 'annee': int, 'mois': int})
        df['finessGeoDP'] = df['finessGeoDP'].astype(str).str.strip()
        return df
    except Exception:
        return pd.DataFrame()

# Read VDA file that includes ongoing year (e.g., 2025) totals and approach split
@st.cache_data(show_spinner=False)
def _load_vda_year_totals_summary(path: str = "data/export_TAB_VDA_HOP.csv", cache_buster: str = "") -> pd.DataFrame:
    if ONLY_ACTIVITY_DATA:
        return pd.DataFrame()
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
