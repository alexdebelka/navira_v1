# pages/Hospital_Dashboard.py
import streamlit as st
import pandas as pd
import altair as alt
import plotly.express as px
import plotly.graph_objects as go
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
st.markdown("---")
st.header("Annual Statistics")
hospital_annual_data = selected_hospital_all_data.set_index('annee')

# Small sparkline trends for key metrics
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
        st.markdown("##### Total Surgeries Trend")
        st.plotly_chart(spark1, use_container_width=True)
except Exception:
    pass
st.markdown("#### Bariatric Procedures by Year")
st.caption("📊 Chart shows annual procedures. Averages compare hospital's yearly average vs. national yearly average per hospital.")
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
    bariatric_df_melted['Procedure3'] = bariatric_df_melted['Procedure'].map(_proc_cat)
    bariatric_df_melted = (bariatric_df_melted
                           .groupby(['annee', 'Procedure3'], as_index=False)['Count']
                           .sum())

if not bariatric_df_melted.empty and bariatric_df_melted['Count'].sum() > 0:
    left, right = st.columns([2, 1])
    with left:
        # Compute share per year explicitly to avoid barnorm dependency
        _totals = bariatric_df_melted.groupby('annee')['Count'].sum().replace(0, 1)
        bariatric_share = bariatric_df_melted.copy()
        bariatric_share['Share'] = bariatric_share['Count'] / bariatric_share['annee'].map(_totals) * 100
        fig = px.bar(
        bariatric_share,
        x='annee',
        y='Share',
        color='Procedure3',
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
        # Overlay national averages as dashed lines (share % per year)
        try:
            nat_df = annual.copy()
            if 'total_procedures_year' in nat_df.columns:
                nat_df = nat_df[nat_df['total_procedures_year'] >= 25]
            proc_codes = [c for c in BARIATRIC_PROCEDURE_NAMES.keys() if c in nat_df.columns]
            nat_year = nat_df.groupby('annee')[proc_codes].sum().reset_index()
            # Build three-category national shares per year
            def _row_pct(row, cols):
                total = row[cols].sum()
                return 0 if total == 0 else (row / total * 100)
            nat_year['Sleeve'] = nat_year.get('SLE', 0)
            nat_year['Gastric Bypass'] = nat_year.get('BPG', 0)
            other_cols = [c for c in proc_codes if c not in ['SLE', 'BPG']]
            nat_year['Other'] = nat_year[other_cols].sum(axis=1) if other_cols else 0
            nat_year['__total__'] = nat_year[['Sleeve', 'Gastric Bypass', 'Other']].sum(axis=1).replace(0, 1)
            for cat in ['Sleeve', 'Gastric Bypass', 'Other']:
                pct = nat_year[cat] / nat_year['__total__'] * 100
                fig.add_trace(
                    go.Scatter(
                        x=nat_year['annee'], y=pct,
                        mode='lines+markers', name=f"{cat} (Nat)",
                        line=dict(dash='dash', width=2), marker=dict(size=5)
                    )
                )
        except Exception:
            pass

        st.plotly_chart(fig, use_container_width=True)

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
                        nat_long.append({'annee': int(r['annee']), 'Procedure3': label, 'Share': val/total*100})
                nat_share_df = pd.DataFrame(nat_long)
                if not nat_share_df.empty:
                    nat_fig = px.bar(nat_share_df, x='annee', y='Share', color='Procedure3', title='National procedures (share %)', barmode='stack')
                    nat_fig.update_layout(height=360, xaxis_title='Year', yaxis_title='% of procedures', plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)')
                    nat_fig.update_traces(opacity=0.85)
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

                comp_rows = []
                for name in ['Sleeve', 'Gastric Bypass', 'Other']:
                    comp_rows.append({'Procedure': name, 'Hospital %': hosp_pct3.get(name, 0), 'National %': nat_pct3.get(name, 0)})
                comp_df = pd.DataFrame(comp_rows)
                if not comp_df.empty:
                    comp_long = comp_df.melt('Procedure', var_name='Source', value_name='Percent')
                    comp_fig = px.bar(comp_long, x='Percent', y='Procedure', color='Source', orientation='h', title='2024 Procedure Mix: Hospital vs National')
                    comp_fig.update_layout(height=360, xaxis_title='% of procedures', yaxis_title=None, plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)')
                    st.plotly_chart(comp_fig, use_container_width=True)
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
        fig2 = px.bar(
            approach_share,
            x='annee',
            y='Share',
            color='Approach',
            title='Surgical Approaches by Year (share %)',
            barmode='stack'
        )
        fig2.update_layout(
            xaxis_title='Year',
            yaxis_title='Share of surgeries (%)',
            hovermode='x unified',
            height=400,
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)'
        )
        # Overlay national approach shares as dashed lines
        try:
            nat_df2 = annual.copy()
            if 'total_procedures_year' in nat_df2.columns:
                nat_df2 = nat_df2[nat_df2['total_procedures_year'] >= 25]
            appr_codes = [c for c in SURGICAL_APPROACH_NAMES.keys() if c in nat_df2.columns]
            nat_year2 = nat_df2.groupby('annee')[appr_codes].sum().reset_index()
            nat_year2['__total__'] = nat_year2[appr_codes].sum(axis=1).replace(0, 1)
            for code, name in SURGICAL_APPROACH_NAMES.items():
                if code in nat_year2.columns:
                    pct = nat_year2[code] / nat_year2['__total__'] * 100
                    fig2.add_trace(
                        go.Scatter(
                            x=nat_year2['annee'], y=pct,
                            mode='lines+markers', name=f"{name} (Nat)",
                            line=dict(dash='dash', width=2), marker=dict(size=5)
                        )
                    )
        except Exception:
            pass

        st.plotly_chart(fig2, use_container_width=True)

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
                    nat_fig2 = px.bar(nat_share2, x='annee', y='Share', color='Approach', title='National approaches (share %)', barmode='stack')
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

                rows = []
                for name in SURGICAL_APPROACH_NAMES.values():
                    if name in h_pct or name in n_pct:
                        rows.append({'Approach': name, 'Hospital %': h_pct.get(name, 0), 'National %': n_pct.get(name, 0)})
                dfc = pd.DataFrame(rows)
                if not dfc.empty:
                    long = dfc.melt('Approach', var_name='Source', value_name='Percent')
                    cmp = px.bar(long, x='Percent', y='Approach', color='Source', orientation='h', title='2024 Approach Mix: Hospital vs National')
                    cmp.update_layout(height=360, xaxis_title='% of surgeries', yaxis_title=None, plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)')
                    st.plotly_chart(cmp, use_container_width=True)
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
