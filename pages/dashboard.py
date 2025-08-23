# pages/Hospital_Dashboard.py
import streamlit as st
import pandas as pd
import altair as alt
import plotly.express as px
from navira.data_loader import get_dataframes
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
        st.metric(
            label="National Avg Revision %",
            value=f"{national_revision_pct:.1f}%"
        )
with metric_col2:
    st.markdown("#### Labels & Affiliations")
    if selected_hospital_details.get('university') == 1: st.success("🎓 University Hospital")
    else: st.warning("➖ No University Affiliation")
    if selected_hospital_details.get('LAB_SOFFCO') == 1: st.success("✅ Centre of Excellence (SOFFCO)")
    else: st.warning("➖ No SOFFCO Centre Label")
    if selected_hospital_details.get('cso') == 1: st.success("✅ Centre of Excellence (Health Ministry)")
    else: st.warning("➖ No Health Ministry Centre Label")
st.markdown("---")
st.header("Annual Statistics")
hospital_annual_data = selected_hospital_all_data.set_index('annee')

# Small sparkline trends for key metrics
spark_col1, spark_col2 = st.columns(2)
try:
    # Total surgeries per year sparkline
    total_series = selected_hospital_all_data[['annee', 'total_procedures_year']].dropna()
    if not total_series.empty:
        spark1 = px.line(total_series, x='annee', y='total_procedures_year', markers=True)
        spark1.update_layout(height=120, margin=dict(l=20, r=20, t=10, b=10),
                             xaxis_title=None, yaxis_title=None, plot_bgcolor='rgba(0,0,0,0)',
                             paper_bgcolor='rgba(0,0,0,0)')
        spark1.update_xaxes(showgrid=False)
        spark1.update_yaxes(showgrid=False)
        spark_col1.markdown("##### Total Surgeries Trend")
        spark_col1.plotly_chart(spark1, use_container_width=True)

    # Robotic share per year sparkline (if ROB exists)
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
            spark_col2.markdown("##### Robotic Share Trend (%)")
            spark_col2.plotly_chart(spark2, use_container_width=True)
except Exception:
    pass
st.markdown("#### Bariatric Procedures by Year")
st.caption("📊 Chart shows annual procedures. Averages compare hospital's yearly average vs. national yearly average per hospital.")
bariatric_df = hospital_annual_data[[key for key in BARIATRIC_PROCEDURE_NAMES.keys() if key in hospital_annual_data.columns]].rename(columns=BARIATRIC_PROCEDURE_NAMES)
bariatric_summary = bariatric_df.sum()
summary_texts = []
for proc_code, proc_name in BARIATRIC_PROCEDURE_NAMES.items():
    # Skip Bilio-pancreatic Diversion in the textual summary, but keep it in charts
    if proc_code == 'DBP':
        continue
    count = bariatric_summary.get(proc_name, 0)
    if count > 0:
        avg_count = national_averages.get(proc_code, 0)
        # Calculate hospital's average per year for fair comparison
        hospital_avg_per_year = count / 5  # 5 years (2020-2024)
        summary_texts.append(f"**{proc_name}**: {int(count)} total ({hospital_avg_per_year:.1f}/year) <span style='color:grey; font-style: italic;'>(National Avg: {avg_count:.1f}/year)</span>")
if summary_texts: st.markdown(" | ".join(summary_texts), unsafe_allow_html=True)
bariatric_df_melted = bariatric_df.reset_index().melt('annee', var_name='Procedure', value_name='Count')
if not bariatric_df_melted.empty and bariatric_df_melted['Count'].sum() > 0:
    left, right = st.columns([2, 1])
    with left:
        fig = px.bar(
        bariatric_df_melted,
        x='annee',
        y='Count',
        color='Procedure',
        title='Bariatric Procedures by Year (share %)',
        barmode='stack',
        barnorm='percent'
        )
        fig.update_layout(
        xaxis_title='Year',
        yaxis_title='Share of procedures (%)',
        hovermode='x unified',
        height=400,
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)'
        )
        st.plotly_chart(fig, use_container_width=True)

    # Right column: 2024 mix comparison (Hospital vs National)
    with right:
        try:
            year_2024 = selected_hospital_all_data[selected_hospital_all_data['annee'] == 2024]
            hosp_counts = {}
            for code, name in BARIATRIC_PROCEDURE_NAMES.items():
                if code in year_2024.columns:
                    hosp_counts[name] = int(year_2024[code].sum())
            hosp_total = sum(hosp_counts.values()) or 1
            hosp_pct = {k: (v / hosp_total * 100) for k, v in hosp_counts.items()}

            nat_2024 = annual[annual['annee'] == 2024]
            if 'total_procedures_year' in nat_2024.columns:
                nat_2024 = nat_2024[nat_2024['total_procedures_year'] >= 25]
            nat_counts = {}
            for code, name in BARIATRIC_PROCEDURE_NAMES.items():
                if code in nat_2024.columns:
                    nat_counts[name] = int(nat_2024[code].sum())
            nat_total = sum(nat_counts.values()) or 1
            nat_pct = {k: (v / nat_total * 100) for k, v in nat_counts.items()}

            comp_rows = []
            for name in BARIATRIC_PROCEDURE_NAMES.values():
                if name in hosp_pct or name in nat_pct:
                    comp_rows.append({
                        'Procedure': name,
                        'Hospital %': hosp_pct.get(name, 0),
                        'National %': nat_pct.get(name, 0)
                    })
            comp_df = pd.DataFrame(comp_rows)
            if not comp_df.empty:
                comp_long = comp_df.melt('Procedure', var_name='Source', value_name='Percent')
                comp_fig = px.bar(
                    comp_long,
                    x='Percent', y='Procedure', color='Source', orientation='h',
                    title='2024 Procedure Mix: Hospital vs National'
                )
                comp_fig.update_layout(height=400, xaxis_title='% of procedures', yaxis_title=None,
                                       plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)')
                st.plotly_chart(comp_fig, use_container_width=True)
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
        fig2 = px.bar(
            approach_df_melted,
            x='annee',
            y='Count',
            color='Approach',
            title='Surgical Approaches by Year (share %)',
            barmode='stack',
            barnorm='percent'
        )
        fig2.update_layout(
            xaxis_title='Year',
            yaxis_title='Share of surgeries (%)',
            hovermode='x unified',
            height=400,
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)'
        )
        st.plotly_chart(fig2, use_container_width=True)

    with right2:
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

            rows = []
            for name in SURGICAL_APPROACH_NAMES.values():
                if name in h_pct or name in n_pct:
                    rows.append({'Approach': name, 'Hospital %': h_pct.get(name, 0), 'National %': n_pct.get(name, 0)})
            dfc = pd.DataFrame(rows)
            if not dfc.empty:
                long = dfc.melt('Approach', var_name='Source', value_name='Percent')
                cmp = px.bar(long, x='Percent', y='Approach', color='Source', orientation='h', title='2024 Approach Mix: Hospital vs National')
                cmp.update_layout(height=400, xaxis_title='% of surgeries', yaxis_title=None, plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)')
                st.plotly_chart(cmp, use_container_width=True)
        except Exception:
            pass
else:
    st.info("No surgical approach data available.")
