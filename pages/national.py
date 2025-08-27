import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import sys
import os

# Add the parent directory to the Python path to import lib
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from lib.national_utils import *
from auth_wrapper import add_auth_to_page
from navigation_utils import handle_navigation_request
handle_navigation_request()

# Add authentication check
add_auth_to_page()

# --- HIDE THE DEFAULT STREAMLIT NAVIGATION ---
st.markdown("""
    <style>
        [data-testid="stSidebarNav"] {
            display: none;
        }
        [data-testid="stPageNav"] {
            display: none;
        }
        /* Tooltip styles for info badge */
        .nv-info-wrap { display:inline-flex; align-items:center; gap:8px; }
        .nv-info-badge { width:18px; height:18px; border-radius:50%; background:#444; color:#fff; font-weight:600; font-size:12px; display:inline-flex; align-items:center; justify-content:center; cursor:help; }
        .nv-tooltip { position:relative; display:inline-block; }
        .nv-tooltip .nv-tooltiptext { visibility:hidden; opacity:0; transition:opacity .15s ease; position:absolute; z-index:9999; top:22px; left:50%; transform:translateX(-50%); width:min(420px, 80vw); background:#2b2b2b; color:#fff; border:1px solid rgba(255,255,255,.1); border-radius:6px; padding:10px 12px; box-shadow:0 4px 14px rgba(0,0,0,.35); text-align:left; font-size:0.9rem; line-height:1.25rem; }
        .nv-tooltip:hover .nv-tooltiptext { visibility:visible; opacity:1; }
        .nv-h3 { font-weight:600; font-size:1.25rem; margin:0; }
    </style>
""", unsafe_allow_html=True)

# Navigation is now handled by the sidebar

# --- Load Data (Parquet via loader) ---
df = load_and_prepare_data()

# --- Page Title and Notice ---
st.title("🇫🇷 National Overview")

# Track page view
try:
    from analytics_integration import track_page_view
    track_page_view("national_overview")
except Exception as e:
    print(f"Analytics tracking error: {e}")

# Top notice (plain text instead of blue info box)
st.markdown("""
> **Note:** National means are computed across hospitals (2020–2024). Only hospitals with ≥25 interventions per year are considered.
""")

# --- (1) HOSPITAL VOLUME DISTRIBUTION ---
st.header("Hospital Volume Distribution")

# Compute KPIs
kpis = compute_national_kpis(df)
volume_2024 = compute_volume_bins_2024(df)
baseline_2020_2023 = compute_baseline_bins_2020_2023(df)

# Calculate deltas
delta_less_50 = volume_2024["<50"] - baseline_2020_2023["<50"]
delta_more_200 = volume_2024[">200"] - baseline_2020_2023[">200"]

# KPI Row
col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    st.metric(
        "Total Hospitals (2024)", 
        f"{kpis['total_hospitals_2024']:.0f}"
    )

with col2:
    st.metric(
        "Total Surgeries (2024)", 
        f"{int(round(kpis['avg_surgeries_per_year'])):,}" # it is total_surgeries_2024
    )

with col3:
    # Calculate revision percentage
    revision_percentage = (kpis['avg_revisions_per_year'] / kpis['avg_surgeries_per_year']) * 100 if kpis['avg_surgeries_per_year'] > 0 else 0
    
    st.metric(
        "Total Revisions (2024)", 
        f"{int(round(kpis['avg_revisions_per_year'])):,}" # it is total_revisions_2024
    )
    st.markdown(f"<span style='color: grey; font-size: 0.9em; display:block; margin-top:-8px;'>{revision_percentage:.0f}% of total surgeries</span>", unsafe_allow_html=True)

with col4:
    delta_color = "normal" if delta_less_50 <= 0 else "inverse"
    st.metric(
        "Hospitals <50/year (2024)",
        f"{int(round(volume_2024['<50'])):,}",
        delta_color=delta_color
    )

with col5:
    delta_color = "normal" if delta_more_200 >= 0 else "inverse"
    st.metric(
        "Hospitals >200/year (2024)",
        f"{int(round(volume_2024['>200'])):,}",
        delta_color=delta_color
    )

# Volume Distribution Chart (with hover info)
st.markdown(
    """
    <div class="nv-info-wrap">
      <div class="nv-h3">Volume Distribution by Hospital</div>
      <div class="nv-tooltip"><span class="nv-info-badge">i</span>
        <div class="nv-tooltiptext">
          <b>Understanding this chart:</b><br/>
          This chart shows how hospitals are distributed across different volume categories based on their annual bariatric surgery procedures. The main bars (blue) represent the average number of hospitals in each volume category during the 2020–2023 period, serving as a baseline for comparison.<br/><br/>
          <b>Volume Categories:</b><br/>
          &lt;50 procedures/year: Small‑volume hospitals (typically smaller facilities or those just starting bariatric programs)<br/>
          50–100 procedures/year: Medium‑low volume hospitals<br/>
          100–200 procedures/year: Medium‑high volume hospitals<br/>
          &gt;200 procedures/year: High‑volume hospitals (typically specialized centers of excellence)<br/><br/>
          When you toggle "Show 2024 comparison", the overlay bars (yellow) show the actual 2024 distribution, allowing you to see how hospital volumes have changed compared to the previous 4‑year average.
        </div>
      </div>
    </div>
    """,
    unsafe_allow_html=True
)

# Pre-compute values used in dropdown key findings
small_vol_2024 = int(volume_2024['<50'])
small_vol_baseline = round(baseline_2020_2023['<50'])
med_low_2024 = int(volume_2024['50–100'])
med_low_baseline = round(baseline_2020_2023['50–100'])
med_high_2024 = int(volume_2024['100–200'])
med_high_baseline = round(baseline_2020_2023['100–200'])
high_vol_2024 = int(volume_2024['>200'])
high_vol_baseline = round(baseline_2020_2023['>200'])

# Calculate percentages
high_vol_pct = round((high_vol_2024 / kpis['total_hospitals_2024']) * 100)
small_vol_pct = round((small_vol_2024 / kpis['total_hospitals_2024']) * 100)
med_low_pct = round((med_low_2024 / kpis['total_hospitals_2024']) * 100)
med_high_pct = round((med_high_2024 / kpis['total_hospitals_2024']) * 100)

# Calculate trends
concentration_trend = "increased" if high_vol_2024 > high_vol_baseline else "decreased"
small_vol_trend = "More" if small_vol_2024 > small_vol_baseline else "Fewer"
med_low_trend = "increased" if med_low_2024 > med_low_baseline else "decreased"
med_high_trend = "increased" if med_high_2024 > med_high_baseline else "decreased"

# Dropdown with only What to look for + Key findings (understanding lives in the info tooltip above)
with st.expander("What to look for and key findings"):
    st.markdown(
        f"""
        **What to look for:**
        - Distribution shifts across the four volume bins
        - Growth or decline in the medium categories (50–100, 100–200)
        - Concentration of high‑volume centers (>200)

        **Key findings:**
        - Small‑volume hospitals (<50/year): **{small_vol_2024}** in 2024 vs **{small_vol_baseline}** avg (2020–2023)
        - High‑volume hospitals (>200/year): **{high_vol_2024}** in 2024 vs **{high_vol_baseline}** avg (2020–2023)
        - Medium‑low volume (50–100/year): **{med_low_2024}** in 2024 vs **{med_low_baseline}** avg — **{med_low_trend}** by **{abs(med_low_2024 - med_low_baseline)}** hospitals
        - Medium‑high volume (100–200/year): **{med_high_2024}** in 2024 vs **{med_high_baseline}** avg — **{med_high_trend}** by **{abs(med_high_2024 - med_high_baseline)}** hospitals

        **Current Distribution (2024):**
        - <50: **{small_vol_pct}%** of hospitals | 50–100: **{med_low_pct}%** | 100–200: **{med_high_pct}%** | >200: **{high_vol_pct}%**
        """
    )

# (Removed previous info block in favor of hover tooltip)

# Prepare data for chart
volume_data = []
for bin_name, count in volume_2024.items():
    volume_data.append({
        'Volume Category': bin_name,
        'Number of Hospitals': count,
        'Percentage': (count / kpis['total_hospitals_2024']) * 100 if kpis['total_hospitals_2024'] > 0 else 0
    })

volume_df = pd.DataFrame(volume_data)

# Toggle for 2024 comparison
show_baseline = st.toggle("Show 2024 comparison", value=True)

# Create Plotly chart
fig = go.Figure()

# Main bars for 2020-2023 average
baseline_data = []
for bin_name, avg_count in baseline_2020_2023.items():
    baseline_data.append({
        'Volume Category': bin_name,
        'Average Hospitals': avg_count
    })
baseline_df = pd.DataFrame(baseline_data)

fig.add_trace(go.Bar(
    x=baseline_df['Volume Category'],
    y=baseline_df['Average Hospitals'],
    name='2020-2023 Average',
    marker_color='#2E86AB',
    hovertemplate='<b>%{x}</b><br>Average Hospitals: %{y:.2f}<extra></extra>'
))

if show_baseline:
    # 2024 bars as overlay (semi-transparent)
    fig.add_trace(go.Bar(
        x=volume_df['Volume Category'],
        y=volume_df['Number of Hospitals'],
        name='2024',
        marker_color='rgba(255, 193, 7, 0.7)',
        hovertemplate='<b>%{x}</b><br>Hospitals: %{y}<br>Percentage: %{text:.2f}%<extra></extra>',
        text=volume_df['Percentage'],
        texttemplate='%{text:.2f}%',
        textposition='auto'
    ))

fig.update_layout(
    title="Hospital Volume Distribution",
    xaxis_title="Annual Interventions per Hospital",
    yaxis_title="Number of Hospitals",
    barmode='overlay',
    hovermode='x unified',
    showlegend=True,
    height=400,
    plot_bgcolor='rgba(0,0,0,0)',
    paper_bgcolor='rgba(0,0,0,0)',
    font=dict(size=12),
    margin=dict(l=50, r=50, t=80, b=50)
)

st.plotly_chart(fig, use_container_width=True)

# --- (2) HOSPITAL AFFILIATION ---
st.header("Hospital Affiliation (2024)")

affiliation_data = compute_affiliation_breakdown_2024(df)
affiliation_counts = affiliation_data['affiliation_counts']
label_breakdown = affiliation_data['label_breakdown']

# Compute affiliation trends for line plot
affiliation_trends = compute_affiliation_trends_2020_2024(df)

# First block: Affiliation cards
col1, col2 = st.columns(2)

with col1:
    st.subheader("Public")
    
    # Calculate total hospitals for percentage
    total_hospitals = sum(affiliation_counts.values())
    
    # Public university hospitals
    public_univ_count = affiliation_counts.get('Public – Univ.', 0)
    public_univ_pct = round((public_univ_count / total_hospitals) * 100) if total_hospitals > 0 else 0
   
    st.metric(
        "Public University Hospital",
        f"{int(round(public_univ_count)):,}"
    )
    st.markdown(f"<span style='color: grey; font-size: 0.9em; display:block; margin-top:-8px;'>{public_univ_pct}% of total</span>", unsafe_allow_html=True)
    
    # Public non-academic hospitals
    public_non_acad_count = affiliation_counts.get('Public – Non-Acad.', 0)
    public_non_acad_pct = round((public_non_acad_count / total_hospitals) * 100) if total_hospitals > 0 else 0
   
    st.metric(
        "Public, No Academic Affiliation",
        f"{int(round(public_non_acad_count)):,}"
    )
    st.markdown(f"<span style='color: grey; font-size: 0.9em; display:block; margin-top:-8px;'>{public_non_acad_pct}% of total</span>", unsafe_allow_html=True)

with col2:
    st.subheader("Private")
    
    # Private for-profit hospitals
    private_for_profit_count = affiliation_counts.get('Private – For-profit', 0)
    private_for_profit_pct = round((private_for_profit_count / total_hospitals) * 100) if total_hospitals > 0 else 0
    
    st.metric(
        "Private For Profit",
        f"{int(round(private_for_profit_count)):,}"
    )
    st.markdown(f"<span style='color: grey; font-size: 0.9em; display:block; margin-top:-8px;'>{private_for_profit_pct}% of total</span>", unsafe_allow_html=True)
    
    # Private not-for-profit hospitals
    private_not_profit_count = affiliation_counts.get('Private – Not-for-profit', 0)
    private_not_profit_pct = round((private_not_profit_count / total_hospitals) * 100) if total_hospitals > 0 else 0
    
    st.metric(
        "Private Not For Profit",
        f"{int(round(private_not_profit_count)):,}"
    )
    st.markdown(f"<span style='color: grey; font-size: 0.9em; display:block; margin-top:-8px;'>{private_not_profit_pct}% of total</span>", unsafe_allow_html=True)

# Second block: Stacked bar chart
st.markdown(
    """
    <div class=\"nv-info-wrap\">
      <div class=\"nv-h3\">Hospital Labels by Affiliation Type</div>
      <div class=\"nv-tooltip\"><span class=\"nv-info-badge\">i</span>
        <div class=\"nv-tooltiptext\">
          <b>Understanding this chart:</b><br/>
          This stacked bar chart shows the distribution of hospital labels (SOFFCO and CSO) across different affiliation types. Each bar represents an affiliation category, and the colored segments within each bar show how many hospitals have specific label combinations.
        </div>
      </div>
    </div>
    """,
    unsafe_allow_html=True
)

with st.expander("What to look for and key findings"):
    # Computed key findings from label_breakdown
    try:
        totals = {k: 0 for k in ['SOFFCO Label', 'CSO Label', 'Both', 'None']}
        labeled_by_category = {}
        for cat in ['Public – Univ.', 'Public – Non-Acad.', 'Private – For-profit', 'Private – Not-for-profit']:
            if cat in label_breakdown:
                labeled_by_category[cat] = (
                    label_breakdown[cat].get('SOFFCO Label', 0)
                    + label_breakdown[cat].get('CSO Label', 0)
                    + label_breakdown[cat].get('Both', 0)
                )
                for lab in totals.keys():
                    totals[lab] += label_breakdown[cat].get(lab, 0)

        top_cat = max(labeled_by_category.items(), key=lambda x: x[1])[0] if labeled_by_category else None
        most_common_label = max(totals.items(), key=lambda x: x[1])[0] if totals else None

        st.markdown(
            f"""
            **What to look for:**
            - Label concentration by affiliation type
            - Balance of SOFFCO vs CSO vs Dual labels
            - Affiliation types with few or no labels

            **Key findings:**
            - Most labeled affiliation type: **{top_cat if top_cat else 'n/a'}**
            - Most common label overall: **{most_common_label if most_common_label else 'n/a'}**
            - Totals — SOFFCO: **{totals.get('SOFFCO Label', 0):,}**, CSO: **{totals.get('CSO Label', 0):,}**, Both: **{totals.get('Both', 0):,}**, None: **{totals.get('None', 0):,}**
            """
        )
    except Exception:
        pass

# Removed previous blue info box in favor of hover tooltip + dropdown

# Prepare data for stacked bar chart
stacked_data = []
categories = ['Public – Univ.', 'Public – Non-Acad.', 'Private – For-profit', 'Private – Not-for-profit']
labels = ['SOFFCO Label', 'CSO Label', 'Both', 'None']

for category in categories:
    if category in label_breakdown:
        for label in labels:
            count = label_breakdown[category].get(label, 0)
            if count > 0:  # Only add non-zero values
                stacked_data.append({
                    'Affiliation': category,
                    'Label': label,
                    'Count': count
                })

stacked_df = pd.DataFrame(stacked_data)

if not stacked_df.empty:
    fig = px.bar(
        stacked_df,
        x='Affiliation',
        y='Count',
        color='Label',
        title="Hospital Labels by Affiliation Type",
        color_discrete_map={
            'SOFFCO Label': '#7fd8be',
            'CSO Label': '#ffd97d',
            'Both': '#00bfff',
            'None': '#f08080'
        }
    )
    
    fig.update_layout(
        xaxis_title="Affiliation Type",
        yaxis_title="Number of Hospitals",
        hovermode='x unified',
        height=400,
        showlegend=True,
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        font=dict(size=12),
        margin=dict(l=50, r=50, t=80, b=50)
    )
    
    fig.update_traces(
        hovertemplate='<b>%{fullData.name}</b><br>%{x}<br>Count: %{y}<extra></extra>'
    )
    
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("No label data available for the selected criteria.")

# Affiliation trends line plot
st.markdown(
    """
    <div class=\"nv-info-wrap\">
      <div class=\"nv-h3\">Hospital Affiliation Trends (2020–2024)</div>
      <div class=\"nv-tooltip\"><span class=\"nv-info-badge\">i</span>
        <div class=\"nv-tooltiptext\">
          <b>Understanding this chart:</b><br/>
          This stacked area chart shows how hospital affiliations have evolved from 2020 to 2024. The total height of the chart at any point represents the total number of hospitals, while the colored segments show the proportion of each affiliation type.<br/><br/>
          <b>Affiliation Types:</b><br/>
          Public – Univ.: Public hospitals with university/academic affiliation<br/>
          Public – Non‑Acad.: Public hospitals without academic affiliation<br/>
          Private – For‑profit: Private for‑profit hospitals<br/>
          Private – Not‑for‑profit: Private not‑for‑profit hospitals
        </div>
      </div>
    </div>
    """,
    unsafe_allow_html=True
)

with st.expander("What to look for and key findings"):
    try:
        # Compute key changes 2020 -> 2024
        base_year = 2020
        last_year = 2024
        diffs = {cat: affiliation_trends[cat].get(last_year, 0) - affiliation_trends[cat].get(base_year, 0) for cat in ['Public – Univ.', 'Public – Non-Acad.', 'Private – For-profit', 'Private – Not-for-profit']}
        top_inc_cat = max(diffs.items(), key=lambda x: x[1])[0] if diffs else None
        top_dec_cat = min(diffs.items(), key=lambda x: x[1])[0] if diffs else None
        st.markdown(
            f"""
            **What to look for:**
            - Shifts in affiliation mix between 2020 and 2024
            - Whether public or private segments gained share
            - Academic vs non‑academic trajectories

            **Key findings:**
            - Largest increase: **{top_inc_cat if top_inc_cat else 'n/a'}** ({diffs.get(top_inc_cat, 0):+d})
            - Largest decrease: **{top_dec_cat if top_dec_cat else 'n/a'}** ({diffs.get(top_dec_cat, 0):+d})
            """
        )
    except Exception:
        st.markdown("**What to look for:** Compare the stacked areas across years to spot increases or decreases by affiliation.\n\n**Key findings:** Data sufficient to compute detailed deltas was not available.")

# Removed previous blue info box in favor of hover tooltip + dropdown

# Prepare data for line chart
trend_data = []
for year in range(2020, 2025):
    for category in ['Public – Univ.', 'Public – Non-Acad.', 'Private – For-profit', 'Private – Not-for-profit']:
        count = affiliation_trends[category].get(year, 0)
        trend_data.append({
            'Year': year,
            'Affiliation': category,
            'Count': count
        })

trend_df = pd.DataFrame(trend_data)

if not trend_df.empty:
    fig = px.area(
        trend_df,
        x='Year',
        y='Count',
        color='Affiliation',
        title="Hospital Affiliation Trends Over Time",
        color_discrete_map={
            'Public – Univ.': '#ee6055',
            'Public – Non-Acad.': '#60d394',
            'Private – For-profit': '#ffd97d',
            'Private – Not-for-profit': '#7161ef'
        }
    )
    
    fig.update_layout(
        xaxis_title="Year",
        yaxis_title="Number of Hospitals",
        hovermode='x unified',
        height=400,
        showlegend=True,
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        font=dict(size=12),
        margin=dict(l=50, r=50, t=80, b=50),
        xaxis=dict(
            tickmode='array',
            tickvals=[2020, 2021, 2022, 2023, 2024],
            ticktext=['2020', '2021', '2022', '2023', '2024'],
            tickformat='d'
        )
    )
    
    fig.update_traces(
        line=dict(width=0),
        opacity=0.8
    )
    
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("No affiliation trend data available.")

# --- (3) PROCEDURES ---
st.header("Procedures")

# Compute procedure data
procedure_averages = compute_procedure_averages_2020_2024(df)
procedure_totals_2024 = get_2024_procedure_totals(df)
procedure_totals_2020_2024 = get_2020_2024_procedure_totals(df)

# Toggle between 2020-2024 totals and 2024 only
toggle_2024_only = st.toggle("Show 2024 data only", value=False)

# Two-column layout
col1, col2 = st.columns([2, 1])

with col1:
    if not toggle_2024_only:
        st.markdown(
            """
            <div class=\"nv-info-wrap\">
              <div class=\"nv-h3\">Total Procedures (2020–2024)</div>
              <div class=\"nv-tooltip\"><span class=\"nv-info-badge\">i</span>
                <div class=\"nv-tooltiptext\">
                  <b>Understanding this chart:</b><br/>
                  This bar chart shows the distribution of different bariatric surgery procedures. The bars represent the total number of procedures performed, and the height indicates the volume of each procedure type.<br/><br/>
                  <b>Time Period:</b><br/>
                  Toggle OFF: Shows data for the entire 2020–2024 period (5 years)<br/>
                  Toggle ON: Shows data for 2024 only
                </div>
              </div>
            </div>
            """,
            unsafe_allow_html=True
        )
        with st.expander("What to look for and key findings"):
            st.markdown(
                """
                This bar chart shows the distribution of different bariatric surgery procedures. The bars represent the total number of procedures performed, and the height indicates the volume of each procedure type.

                **Time Period:**
                - Toggle OFF: Shows data for the entire 2020–2024 period (5 years)
                - Toggle ON: Shows data for 2024 only
                """
            )
        # Prepare data for bar chart (2020-2024 totals)
        tot_data = []
        total_procedures = sum(procedure_totals_2020_2024.get(proc_code, 0) for proc_code in BARIATRIC_PROCEDURE_NAMES.keys())
        for proc_code, proc_name in BARIATRIC_PROCEDURE_NAMES.items():
            if proc_code in procedure_totals_2020_2024:
                value = procedure_totals_2020_2024[proc_code]
                raw_percentage = (value / total_procedures) * 100 if total_procedures > 0 else 0
                # Show decimals for percentages less than 1%, otherwise round to whole number
                percentage = round(raw_percentage, 1) if raw_percentage < 1 else round(raw_percentage)
                tot_data.append({
                    'Procedure': proc_name,
                    'Value': value,
                    'Percentage': percentage
                })
        chart_df = pd.DataFrame(tot_data).sort_values('Value', ascending=False)
        y_title = "Total count (2020-2024)"
        chart_title = "Total Procedures by Type (2020-2024)"
        hover_tmpl = '<b>%{x}</b><br>Total 2020-2024: %{y:,}<br>Percentage: %{customdata[0]}%<extra></extra>'
    else:
        st.markdown(
            """
            <div class=\"nv-info-wrap\">
              <div class=\"nv-h3\">Total Procedures (2024)</div>
              <div class=\"nv-tooltip\"><span class=\"nv-info-badge\">i</span>
                <div class=\"nv-tooltiptext\">
                  <b>Understanding this chart:</b><br/>
                  This bar chart shows the distribution of different bariatric surgery procedures. The bars represent the total number of procedures performed, and the height indicates the volume of each procedure type.<br/><br/>
                  <b>Time Period:</b><br/>
                  Toggle OFF: Shows data for the entire 2020–2024 period (5 years)<br/>
                  Toggle ON: Shows data for 2024 only
                </div>
              </div>
            </div>
            """,
            unsafe_allow_html=True
        )
        with st.expander("What to look for and key findings"):
            st.markdown(
                """
                This bar chart shows the distribution of different bariatric surgery procedures. The bars represent the total number of procedures performed, and the height indicates the volume of each procedure type.

                **Time Period:**
                - Toggle OFF: Shows data for the entire 2020–2024 period (5 years)
                - Toggle ON: Shows data for 2024 only
                """
            )
        # Prepare data for bar chart (2024 totals only)
        tot_data = []
        total_procedures = sum(procedure_totals_2024.get(proc_code, 0) for proc_code in BARIATRIC_PROCEDURE_NAMES.keys())
        for proc_code, proc_name in BARIATRIC_PROCEDURE_NAMES.items():
            if proc_code in procedure_totals_2024:
                value = procedure_totals_2024[proc_code]
                raw_percentage = (value / total_procedures) * 100 if total_procedures > 0 else 0
                # Show decimals for percentages less than 1%, otherwise round to whole number
                percentage = round(raw_percentage, 1) if raw_percentage < 1 else round(raw_percentage)
                tot_data.append({
                    'Procedure': proc_name,
                    'Value': value,
                    'Percentage': percentage
                })
        chart_df = pd.DataFrame(tot_data).sort_values('Value', ascending=False)
        y_title = "Total count (2024)"
        chart_title = "Total Procedures by Type (2024)"
        hover_tmpl = '<b>%{x}</b><br>Total 2024: %{y:,}<br>Percentage: %{customdata[0]}%<extra></extra>'

    if not chart_df.empty:

        # Use a single blue color for all bars to emphasize totals
        # Build label: show one decimal for percentages <1%, otherwise whole number
        chart_df = chart_df.assign(Label=chart_df['Percentage'].apply(lambda p: f"{p:.1f}%" if p < 1 else f"{p:.0f}%"))

        fig = px.bar(
            chart_df,
            x='Value',
            y='Procedure',
            orientation='h',
            title=chart_title,
            color_discrete_sequence=['#4C84C8'],
            custom_data=['Percentage'],
            text='Label'
        )
        fig.update_layout(
            xaxis_title=y_title,
            yaxis_title="Procedure Type",
            hovermode='y unified',
            height=440,
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            font=dict(size=12),
            margin=dict(l=160, r=50, t=80, b=40),
            yaxis=dict(automargin=True)
        )
        # Horizontal hover shows category on Y; text already includes % with proper decimals
        hover_tmpl_h = hover_tmpl.replace('%{x}', '%{y}').replace('%{y:,}', '%{x:,}')
        fig.update_traces(hovertemplate=hover_tmpl_h, textposition='outside', cliponaxis=False)
        st.plotly_chart(fig, use_container_width=True)

        # Procedure mix trends (shares) — below the bar plot
        # Update title and tooltip based on toggle state
        if toggle_2024_only:
            time_period = "2024"
            tooltip_text = "Stacked area shows the procedure mix for 2024 (single‑year view). The segments represent the percentage share of Sleeve, Gastric Bypass, and Other procedures, totaling 100%."
        else:
            time_period = "2020–2024"
            tooltip_text = "Stacked area shows annual shares of Sleeve, Gastric Bypass, and Other across eligible hospitals. Each year sums to 100%."
        
        st.markdown(
            f"""
            <div class=\"nv-info-wrap\">
              <div class=\"nv-h3\">Procedure Mix Trends ({time_period})</div>
              <div class=\"nv-tooltip\"><span class=\"nv-info-badge\">i</span>
                <div class=\"nv-tooltiptext\">
                  <b>Understanding this chart:</b><br/>
                  {tooltip_text}
                </div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        # Collapse to Sleeve, Gastric Bypass, Other
        known_codes = ['SLE','BPG','ANN','REV','ABL','DBP','GVC','NDD']
        available = [c for c in known_codes if c in df.columns]
        proc_trend_rows = []
        
        # Check if required columns exist (note: 'annee' is renamed to 'year' in data loading)
        year_col = 'year' if 'year' in df.columns else 'annee'
        if year_col in df.columns and available:
            # Filter years based on toggle state
            if toggle_2024_only:
                years_to_process = [2024]
            else:
                years_to_process = sorted(df[year_col].unique())
            
            for year in years_to_process:
                yearly = df[df[year_col] == year]
                if yearly.empty:
                    continue
                totals = yearly[available].sum(numeric_only=True)
                sleeve = float(totals.get('SLE', 0))
                bypass = float(totals.get('BPG', 0))
                other = float(totals.sum() - sleeve - bypass)
                total_sum = sleeve + bypass + other
                if total_sum <= 0:
                    continue
                for name, val in [('Sleeve', sleeve), ('Gastric Bypass', bypass), ('Other', other)]:
                    proc_trend_rows.append({'Year': int(year), 'Procedure': name, 'Share': val / total_sum * 100})
        
        proc_trend_df = pd.DataFrame(proc_trend_rows)
        if not proc_trend_df.empty:
            proc_colors = {'Sleeve': '#4C84C8', 'Gastric Bypass': '#7aa7f7', 'Other': '#f59e0b'}
            
            # Always use area chart. For single year (2024) repeat the same shares
            # across a full year range so the stacked areas span the full width.
            plot_df = proc_trend_df.copy()
            if toggle_2024_only and not plot_df.empty:
                try:
                    years_full = [2020, 2021, 2022, 2023, 2024]
                    base_rows = plot_df.copy()
                    frames = []
                    for y in years_full:
                        tmp = base_rows.copy()
                        tmp['Year'] = y
                        frames.append(tmp)
                    plot_df = pd.concat(frames, ignore_index=True)
                except Exception:
                    pass

            fig = px.area(
                plot_df, x='Year', y='Share', color='Procedure',
                title=f'Procedure Mix Trends Over Time ({time_period})',
                color_discrete_map=proc_colors,
                category_orders={'Procedure': ['Sleeve', 'Gastric Bypass', 'Other']}
            )
            fig.update_layout(
                height=380, 
                xaxis_title='Year', 
                yaxis_title='% of procedures', 
                plot_bgcolor='rgba(0,0,0,0)', 
                paper_bgcolor='rgba(0,0,0,0)'
            )
            # For single-year view, keep standard 2020–2024 ticks but the data is flat
            if toggle_2024_only:
                fig.update_layout(xaxis=dict(tickmode='array', tickvals=[2020, 2021, 2022, 2023, 2024], ticktext=['2020','2021','2022','2023','2024']))
            fig.update_traces(line=dict(width=0), opacity=0.9)
            
            st.plotly_chart(fig, use_container_width=True)
            
            with st.expander("What to look for and key findings"):
                try:
                    if toggle_2024_only:
                        # For 2024 only data, show breakdown analysis
                        dominant = proc_trend_df.sort_values('Share', ascending=False).iloc[0]
                        st.markdown(f"""
                        **What to look for:**
                        - Relative size of each procedure type segment in 2024
                        - Dominant procedure type
                        - Share distribution between major procedures

                        **Key findings:**
                        - Dominant procedure in 2024: **{dominant['Procedure']}** (~{dominant['Share']:.0f}%)
                        - Procedure breakdown: {', '.join([f"**{row['Procedure']}**: {row['Share']:.1f}%" for _, row in proc_trend_df.sort_values('Share', ascending=False).iterrows()])}
                        """)
                    else:
                        # For multi-year data, show trend analysis
                        last = proc_trend_df[proc_trend_df['Year']==proc_trend_df['Year'].max()].sort_values('Share', ascending=False).iloc[0]
                        st.markdown(f"""
                        **What to look for:**
                        - Stability vs shifts in procedure mix
                        - Which procedures gain or lose share across years
                        - Year-over-year trends in procedure dominance

                        **Key findings:**
                        - Dominant procedure in {int(proc_trend_df['Year'].max())}: **{last['Procedure']}** (~{last['Share']:.0f}%)
                        """)
                except Exception:
                    if toggle_2024_only:
                        st.markdown("Review the stacked area for procedure distribution in 2024.")
                    else:
                        st.markdown("Review the stacked areas for dominant procedures each year.")
        else:
            st.info("Procedure trends chart unavailable - insufficient data or missing columns.")


with col2:
    if not toggle_2024_only:
        st.subheader("2020-2024 Totals")
        # Sleeve Gastrectomies 2020-2024
        sleeve_total = procedure_totals_2020_2024.get('SLE', 0)
        st.metric(
            "Sleeve Gastrectomies (2020-2024)",
            f"{int(round(sleeve_total)):,}"
        )
        # Total procedures 2020-2024
        total_all = procedure_totals_2020_2024.get('total_all', 0)
        st.metric(
            "Total Procedures (2020-2024)",
            f"{int(round(total_all)):,}"
        )
    else:
        st.subheader("2024 Totals")
        # Sleeve Gastrectomies in 2024
        sleeve_2024 = procedure_totals_2024.get('SLE', 0)
        st.metric(
            "Sleeve Gastrectomies (2024)",
            f"{int(round(sleeve_2024)):,}"
        )
        # Total procedures in 2024
        total_2024 = procedure_totals_2024.get('total_all', 0)
        st.metric(
            "Total Procedures (2024)",
            f"{int(round(total_2024)):,}"
        )

st.caption("Data computed across eligible hospital-years (≥25 procedures per year).")

# --- (4) APPROACH TRENDS ---
st.header("Approach Trends")

# Compute approach data
approach_trends = compute_approach_trends(df)
approach_mix_2024 = compute_2024_approach_mix(df)






st.markdown(
    """
    <div class=\"nv-info-wrap\">
      <div class=\"nv-h3\">Surgical Approach Mix (2024)</div>
      <div class=\"nv-tooltip\"><span class=\"nv-info-badge\">i</span>
        <div class=\"nv-tooltiptext\">
          <b>Understanding this chart:</b><br/>
          This pie chart shows the proportion of surgical approaches used in 2024 across all eligible hospitals.
        </div>
      </div>
    </div>
    """,
    unsafe_allow_html=True
)

if approach_mix_2024:
    # Prepare data for pie chart
    pie_data = []
    for approach_name, count in approach_mix_2024.items():
        if count > 0:
            pie_data.append({
                'Approach': approach_name,
                'Count': count
            })
    
    pie_df = pd.DataFrame(pie_data)
    
    if not pie_df.empty:
        # Precompute integer percentage labels (no decimals)
        total_cnt = max(1, int(pie_df['Count'].sum()))
        pie_df['PctLabel'] = (pie_df['Count'] / total_cnt * 100).round(0).astype(int).astype(str) + '%'

        fig = px.pie(
            pie_df,
            values='Count',
            names='Approach',
            title="Surgical Approach Distribution (2024)",
            color_discrete_sequence=['#2E86AB', '#F7931E', '#A23B72', '#F18F01']
        )
        
        fig.update_layout(
            height=400,
            showlegend=True,
            font=dict(size=12),
            legend=dict(
                itemclick=False,
                itemdoubleclick=False
            )
        )
        
        fig.update_traces(
            hovertemplate='<b>%{label}</b><br>Count: %{value:,}<br>Percentage: %{percent:.0f}%<extra></extra>',
            textposition='outside',
            text=pie_df['PctLabel'],
            textinfo='text+label',
            textfont=dict(size=16)
        )
        
        st.plotly_chart(fig, use_container_width=True)
        # Dropdown with What to look for + Key findings
        try:
            total_approaches = pie_df['Count'].sum()
            robotic_cnt = int(pie_df[pie_df['Approach'] == 'Robotic']['Count'].sum()) if 'Robotic' in pie_df['Approach'].values else 0
            robotic_share = (robotic_cnt / total_approaches * 100) if total_approaches > 0 else 0
            top_row = pie_df.sort_values('Count', ascending=False).iloc[0]
            with st.expander("What to look for and key findings"):
                st.markdown(f"""
                **What to look for:**
                - Dominant approach segment size
                - Relative share of Robotic vs others
                - Presence of small slivers indicating rare approaches

                **Key findings:**
                - Robotic share in 2024: **{robotic_share:.1f}%** ({robotic_cnt:,} procedures)
                - Most common approach: **{top_row['Approach']}** ({int(top_row['Count']):,})
                """)
        except Exception:
            pass
else:
    st.info("No approach data available for 2024.")
# Two-column layout for trends and pie chart
col1, col2 = st.columns([2, 1])
with col1:
    st.markdown(
        """
        <div class=\"nv-info-wrap\">
          <div class=\"nv-h3\">Surgical Approach Trends (2020–2024)</div>
          <div class=\"nv-tooltip\"><span class=\"nv-info-badge\">i</span>
            <div class=\"nv-tooltiptext\">
              <b>Understanding this chart:</b><br/>
              This line chart tracks the number of robotic surgeries by year from 2020 to 2024.
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True
    )
    trend_data = []
    for year in range(2020, 2025):
        trend_data.append({
            'Year': year,
            'All Surgeries': approach_trends['all'].get(year, 0),
            'Robotic Surgeries': approach_trends['robotic'].get(year, 0)
        })

    trend_df = pd.DataFrame(trend_data)

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=trend_df['Year'],
        y=trend_df['Robotic Surgeries'],
        mode='lines+markers',
        name='Robotic Surgeries',
        line=dict(color='#F7931E', width=3),
        marker=dict(size=8, color='#F7931E')
    ))

    fig.update_layout(
        title="Robotic Surgery Trends (2020-2024)",
        xaxis_title="Year",
        yaxis_title="Number of Robotic Surgeries",
        hovermode='x unified',
        height=400,
        showlegend=True,
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        font=dict(size=12),
        margin=dict(l=50, r=50, t=80, b=50)
    )

    st.plotly_chart(fig, use_container_width=True)
    try:
        first_year = 2020
        last_year = 2024
        rob_start = int(approach_trends['robotic'].get(first_year, 0))
        rob_end = int(approach_trends['robotic'].get(last_year, 0))
        pct_rob_2024 = (approach_trends['robotic'].get(2024, 0) / max(approach_trends['all'].get(2024, 1), 1)) * 100 if approach_trends['all'].get(2024, 0) else 0
        with st.expander("What to look for and key findings"):
            st.markdown(f"""
            **What to look for:**
            - Year‑over‑year growth or dips
            - Peak adoption year
            - Gap between robotic and total surgeries

            **Key findings:**
            - Robotic surgeries grew from **{rob_start:,}** (2020) to **{rob_end:,}** (2024)
            - Robotic share in 2024: **{pct_rob_2024:.1f}%** of all surgeries
            """)
    except Exception:
        pass
        
with col2:
    robotic_2024 = approach_trends['robotic'].get(2024, 0)
    total_2024 = approach_trends['all'].get(2024, 0)
    robotic_pct_2024 = round((robotic_2024 / total_2024) * 100, 1) if total_2024 > 0 else 0
    
    st.metric(
        "Total Robotic Surgeries (2024)",
        f"{int(round(robotic_2024)):,}",
        delta=f"{robotic_pct_2024}% of total surgeries"
    )
    
    # Add comprehensive robotic surgery analysis
    with st.expander("🔍 Robotic Surgery Analysis"):
        st.markdown("""
        **Robotic Surgery Data Availability:**
        
        **What we CAN analyze:**
        - **Total robotic surgeries** by year (2020-2024)
        - **Robotic vs non-robotic** overall trends
        - **Robotic adoption rate** over time
        - **Geographic distribution** of robotic centers
        - **Hospital volume** correlation with robotic use
        - **Affiliation type** correlation (public vs private)
        
        **What we CANNOT analyze (data limitation):**
        - **Procedure-specific robotic rates** (e.g., % of gastric sleeves done robotically)
        - **Primary vs revisional** robotic procedures
        - **Robotic approach by procedure type** (which procedures are more likely to be robotic)
        
        **Key Insights from Available Data:**
        - **Growth trend**: Robotic surgery adoption has increased significantly
        - **Current usage**: ~5.6% of all bariatric surgeries are robotic (2024)
        - **Peak year**: 2023 had the highest robotic volume (2,209 procedures)
        - **Market penetration**: Still relatively low but growing rapidly
        
        **Possible Comparisons:**
        1. **Temporal**: Year-over-year growth in robotic adoption
        2. **Geographic**: Regional differences in robotic availability
        3. **Institutional**: Hospital type vs robotic adoption
        4. **Volume-based**: High-volume vs low-volume center robotic use
        5. **Affiliation**: Public vs private hospital robotic adoption
        """)

# --- ROBOTIC SURGERY COMPARATIVE ANALYSIS ---
st.header("Robotic Surgery Comparative Analysis")

# Compute all robotic surgery comparisons
robotic_geographic = compute_robotic_geographic_analysis(df)
robotic_affiliation = compute_robotic_affiliation_analysis(df)
robotic_volume = compute_robotic_volume_analysis(df)
robotic_temporal = compute_robotic_temporal_analysis(df)
robotic_institutional = compute_robotic_institutional_analysis(df)

# #  1. Temporal Analysis
# with st.expander("📈 1. Temporal Analysis - Robotic Adoption Over Time"):
#     st.markdown("""
#     **Understanding this analysis:**
    
#     This chart shows how robotic surgery adoption has evolved from 2020 to 2024. It tracks both the absolute number of robotic procedures and the percentage of all surgeries that are performed robotically.
    
#     **How we calculated this:**
#     - **Data source**: Annual procedures data (2020-2024) for all eligible hospitals
#     - **Filtering**: Only hospitals with ≥25 procedures/year in each year
#     - **Robotic count**: Sum of all robotic procedures (ROB column) per year
#     - **Total procedures**: Sum of all bariatric procedures per year
#     - **Percentage**: (Robotic procedures / Total procedures) × 100 for each year
    
#     **Key metrics:**
#     - **Absolute growth**: Total number of robotic surgeries each year
#     - **Relative growth**: Percentage of all surgeries that are robotic
#     - **Adoption rate**: How quickly hospitals are adopting robotic technology
    
#     **What to look for:**
#     - **Acceleration**: Is robotic adoption speeding up or slowing down?
#     - **Market penetration**: How much room is there for further growth?
#     - **Year-over-year changes**: Which years saw the biggest increases?
#     """)
    
#     if robotic_temporal['years']:
#         fig = go.Figure()
        
#         fig.add_trace(go.Bar(
#             x=robotic_temporal['years'],
#             y=robotic_temporal['robotic_counts'],
#             name='Robotic Surgeries',
#             marker_color='#F7931E',
#             hovertemplate='<b>%{x}</b><br>Robotic: %{y:,}<br>Percentage: %{customdata[0]}%<extra></extra>',
#             customdata=robotic_temporal['percentages']
#         ))
        
#         fig.update_layout(
#             title="Robotic Surgery Adoption (2020-2024)",
#             xaxis_title="Year",
#             yaxis_title="Number of Robotic Surgeries",
#             height=400,
#             showlegend=True,
#             plot_bgcolor='rgba(0,0,0,0)',
#             paper_bgcolor='rgba(0,0,0,0)',
#             font=dict(size=12),
#             margin=dict(l=50, r=50, t=80, b=50)
#         )
        
#         st.plotly_chart(fig, use_container_width=True)
        
#         # Show percentage trend
#         col1, col2, col3 = st.columns(3)
#         with col1:
#             st.metric("2020", f"{robotic_temporal['percentages'][0]}%")
#         with col2:
#             st.metric("2022", f"{robotic_temporal['percentages'][2]}%")
#         with col3:
#             st.metric("2024", f"{robotic_temporal['percentages'][4]}%")

# 2. Geographic Analysis
with st.expander("🗺️ 1. Geographic Analysis - Regional Robotic Adoption"):
    st.markdown("""
    **Understanding this analysis:**
    
    This chart shows robotic surgery adoption rates across different geographic regions of France. It reveals which regions are leading in robotic technology adoption and which may need more support.
    
    **How we calculated this:**
    - **Data source**: 2024 data for all eligible hospitals (≥25 procedures/year)
    - **Grouping**: Hospitals grouped by their geographic region (lib_reg column)
    - **Robotic count**: Sum of robotic procedures (ROB column) per region
    - **Total procedures**: Sum of all bariatric procedures per region
    - **Percentage**: (Robotic procedures / Total procedures) × 100 per region
    - **Filtering**: Only regions with >0 robotic procedures and valid percentages
    
    **What the percentages mean:**
    - **Percentage**: Shows what % of ALL bariatric surgeries in that region are performed robotically
    - **Example**: If ILE-DE-FRANCE shows 5.4%, it means 5.4% of all bariatric surgeries in Île‑de‑France are robotic
    - **Robotic count**: The actual number of robotic procedures performed in that region
    
    """)
    
    if robotic_geographic['regions'] and len(robotic_geographic['regions']) > 0:
        fig = px.bar(
            x=robotic_geographic['percentages'],
            y=robotic_geographic['regions'],
            orientation='h',
            title="Robotic Surgery Adoption by Region (2024)",
            color=robotic_geographic['percentages'],
            color_continuous_scale='Oranges',
            text=[f"{p:.1f}%" for p in robotic_geographic['percentages']]
        )
        
        fig.update_layout(
            xaxis_title="Robotic Surgery Percentage (%)",
            yaxis_title="Region",
            height=440,
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            font=dict(size=12),
            margin=dict(l=160, r=50, t=80, b=40),
            yaxis=dict(automargin=True)
        )
        
        fig.update_traces(
            hovertemplate='<b>%{y}</b><br>Percentage: %{x:.1f}%<br>Robotic: %{customdata}<extra></extra>',
            customdata=robotic_geographic['robotic_counts']
        )
        fig.update_traces(textposition='outside', cliponaxis=False)
        
        st.plotly_chart(fig, use_container_width=True)
        try:
            top_idx = int(pd.Series(robotic_geographic['percentages']).idxmax())
            top_region = robotic_geographic['regions'][top_idx]
            top_pct = robotic_geographic['percentages'][top_idx]
            with st.expander("What to look for and key findings"):
                st.markdown(f"""
                **What to look for:**
                - Regions with notably higher robotic percentages
                - Regional disparities in access to robotic surgery
                
                **Key findings:**
                - Highest regional adoption: **{top_region}** at **{top_pct:.1f}%**
                """)
        except Exception:
            pass
    else:
        st.info("No geographic data available. Region information may not be included in the dataset.")

# 3. Institutional Analysis
with st.expander("🏥 2. Affiliation Analysis"):
    st.markdown("""
    **Understanding this analysis:**
    
    This chart compares robotic surgery adoption between hospital sectors: public vs private institutions.
    
    **How we calculated this:**
    - **Data source**: 2024 data for all eligible hospitals (≥25 procedures/year)
    - **Sector grouping**: Hospitals grouped by sector (public vs private)
    - **Robotic count**: Sum of robotic procedures (ROB column) per hospital type
    - **Total procedures**: Sum of all bariatric procedures per hospital type
    - **Percentage**: (Robotic procedures / Total procedures) × 100 per hospital type
    
    **What the percentages mean:**
    - **Percentage**: Share of all bariatric surgeries in that sector that are robotic
    - **Robotic count**: The actual number of robotic procedures performed in that sector
    """)
    
    # Merged bar chart: sector and affiliation side-by-side
    merged_x = []
    merged_y = []
    merged_color = []
    # Sector bars removed per request (keep only affiliation bars)
    try:
        if robotic_affiliation['affiliations'] and robotic_affiliation['percentages']:
            for t, v in zip(robotic_affiliation['affiliations'], robotic_affiliation['percentages']):
                merged_x.append(f"Affil – {t}")
                merged_y.append(v)
                merged_color.append('Affiliation')
    except Exception:
        pass
    if merged_x:
        fig_merge = px.bar(x=merged_x, y=merged_y, color=merged_color, title="Robotic Adoption by Sector and Affiliation (2024)",
                           color_discrete_map={'Sector':'#34a853','Affiliation':'#db4437'})
        fig_merge.update_layout(height=380, plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', xaxis_title=None, yaxis_title='Robotic Surgery Percentage (%)')
        fig_merge.update_traces(hovertemplate='<b>%{x}</b><br>Percentage: %{y:.1f}%<extra></extra>', marker_line_width=0)
        st.plotly_chart(fig_merge, use_container_width=True)
        with st.expander("What to look for and key findings"):
            try:
                import numpy as np
                sector_vals = np.array(robotic_institutional.get('sector',{}).get('percentages',[]) or [])
                aff_vals = np.array(robotic_affiliation.get('percentages',[]) or [])
                s_max = sector_vals.max() if sector_vals.size else None
                a_max = aff_vals.max() if aff_vals.size else None
                st.markdown(f"""
                **What to look for:**
                - Sector vs affiliation differences in adoption
                - Which subgroups stand out at the high end

                **Key findings:**
                - Highest sector value: **{s_max:.1f}%** if available
                - Highest affiliation value: **{a_max:.1f}%** if available
                """)
            except Exception:
                st.markdown("Insights unavailable due to missing values.")
    else:
        st.info("No sector/affiliation data available for the merged comparison.")

# 4. Volume-based Analysis
with st.expander("📊 3. Volume-based Analysis - Hospital Volume vs Robotic Adoption"):
    st.markdown("""
    **Understanding this analysis:**
    
    This chart shows how robotic surgery adoption varies with hospital volume. It examines whether high‑volume centers are more likely to use robotic technology.
    
    **How we calculated this (default chart):**
    - **Data source**: 2024 data for all eligible hospitals (≥25 procedures/year)
    - **Volume categorization**: Hospitals grouped by annual procedure volume:
      * less than 50 procedures/year
      * 50–100 procedures/year  
      * 100–200 procedures/year
      * more than 200 procedures/year
    - **Weighted percentage**: For each volume group, we compute (sum of robotic surgeries ÷ sum of all surgeries) × 100. This weights each hospital by its number of surgeries so large centers are represented proportionally.
    - Hover shows: **weighted % robotic** and the **robotic count** in that group.
    
    **Alternative view (optional expander below the chart):**
    - **Unweighted mean**: Average of per‑hospital robotic shares within each group (each hospital contributes equally, regardless of size).
    
    **Why both matter:**
    - Weighted view answers: “What share of all surgeries in this group are robotic?” (system‑wide perspective).
    - Unweighted view answers: “What is the typical hospital’s robotic share in this group?” (center‑level perspective).
    
    **Questions this helps answer:**
    - Do higher‑volume centers have higher robotic adoption?
    - Is the difference driven by a few very large programs or broadly across centers?
    """)
    
    if robotic_volume['volume_categories'] and len(robotic_volume['volume_categories']) > 0:
        # Keep only the continuous scatter with trendline (as per screenshot)
        try:
            from lib.national_utils import compute_robotic_volume_distribution
            dist_df = compute_robotic_volume_distribution(df)
        except Exception:
            dist_df = pd.DataFrame()
        if not dist_df.empty:
            st.subheader("Continuous relationship: volume vs robotic %")
            cont = px.scatter(
                dist_df,
                x='total_surgeries',
                y='hospital_pct',
                color='volume_category',
                opacity=0.65,
                title='Hospital volume (continuous) vs robotic %'
            )
            # Linear trendline removed per request
            cont.update_layout(
                xaxis_title='Total surgeries (2024)',
                yaxis_title='Robotic % (per hospital)',
                height=420,
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)'
            )
            st.plotly_chart(cont, use_container_width=True)

        # Annotations: hospitals and average surgeries per bin
        try:
            num_hosp = robotic_volume.get('hospitals')
            total_counts = robotic_volume.get('total_counts')
            ann_text = []
            if num_hosp and total_counts:
                avg_surg = [round(tc / h, 1) if h else 0 for tc, h in zip(total_counts, num_hosp)]
                for xc, h, a in zip(robotic_volume['volume_categories'], num_hosp, avg_surg):
                    ann_text.append(f"{h} hospitals\n~{a} surgeries/hosp")
                fig_ann = px.bar(x=robotic_volume['volume_categories'], y=[0]*len(num_hosp))
                fig_ann.update_layout(height=1)  # placeholder
            st.caption("Hospitals and avg surgeries per bin: " + ", ".join(ann_text))
        except Exception:
            pass

        # # ECDF by volume bin
        # try:
        #     from lib.national_utils import compute_robotic_volume_distribution
        #     dist_df = compute_robotic_volume_distribution(df)
        #     if not dist_df.empty:
        #         st.subheader("ECDF of hospital robotic% by volume bin")
        #         show_ge = st.toggle("Show ≥ threshold (instead of ≤)", value=False)
        #         ordered_cats = ["<50", "50–100", "100–200", ">200"]
        #         ecdf_records = []
        #         for cat in ordered_cats:
        #             sub = dist_df[dist_df['volume_category'] == cat]['hospital_pct'].dropna().astype(float)
        #             if len(sub) == 0:
        #                 continue
        #             vals = np.sort(sub.values)
        #             frac = np.arange(1, len(vals) + 1) / len(vals)
        #             for v, f in zip(vals, frac):
        #                 ecdf_records.append({
        #                     'volume_category': cat,
        #                     'hospital_pct': v,
        #                     'ecdf': f
        #                 })

        #         ecdf_df = pd.DataFrame(ecdf_records)
        #         if not ecdf_df.empty:
        #             # Invert if showing ≥ threshold
        #             ecdf_df['ecdf_plot'] = 1 - ecdf_df['ecdf'] if show_ge else ecdf_df['ecdf']
        #             operator = '≥' if show_ge else '≤'
        #             ecdf_fig = px.line(
        #                 ecdf_df,
        #                 x='hospital_pct',
        #                 y='ecdf_plot',
        #                 color='volume_category',
        #                 title=f'ECDF: Share of hospitals with robotic% {operator} threshold',
        #                 line_shape='hv'
        #             )
        #             ecdf_fig.update_layout(
        #                 xaxis_title='Robotic % (threshold)',
        #                 yaxis_title='Cumulative share of hospitals',
        #                 height=420,
        #                 plot_bgcolor='rgba(0,0,0,0)',
        #                 paper_bgcolor='rgba(0,0,0,0)'
        #             )
        #             ecdf_fig.update_yaxes(tickformat='.0%')
        #             ecdf_fig.update_traces(
        #                 hovertemplate=f'%{{fullData.name}}<br>{operator} %{{x:.1f}}% -> %{{y:.0%}}<extra></extra>'
        #             )
        #             # Add vertical guide lines at key thresholds
        #             for thr in [5, 10, 20]:
        #                 ecdf_fig.add_vline(x=thr, line_dash='dot', line_color='gray', opacity=0.5)
        #                 ecdf_fig.add_annotation(x=thr, y=1.02, xref='x', yref='paper',
        #                                         text=f'{thr}%', showarrow=False, font=dict(size=10, color='gray'))
        #             st.plotly_chart(ecdf_fig, use_container_width=True)
        # except Exception:
        #     pass

        # # Δ between weighted and mean
        # try:
        #     weighted = robotic_volume.get('percentages_weighted') or [None]*len(robotic_volume['volume_categories'])
        #     mean_vals = robotic_volume.get('percentages_mean') or [None]*len(robotic_volume['volume_categories'])
        #     deltas = []
        #     for w, m in zip(weighted, mean_vals):
        #         if w is not None and m is not None:
        #             deltas.append(round(w - m, 1))
        #         else:
        #             deltas.append(None)
        #     st.markdown("**Δ (weighted − mean) by volume bin:** " + ", ".join(
        #         [f"{cat}: {d:+.1f}%" if d is not None else f"{cat}: n/a" for cat, d in zip(robotic_volume['volume_categories'], deltas)]
        #     ))
        # except Exception:
        #     pass

        # # Distribution plot (per-hospital robotic share) by volume bin
        # try:
        #     from lib.national_utils import compute_robotic_volume_distribution
        #     dist_df = compute_robotic_volume_distribution(df)
        #     st.subheader("Per-hospital distribution by volume")

        #     # Choose representation
        #     style = st.radio(
        #         "Distribution style",
        #         options=["Violin + beeswarm", "Box + beeswarm"],
        #         horizontal=True,
        #         index=0
        #     )

        #     ordered_cats = ["<50", "50–100", "100–200", ">200"]
        #     fig = go.Figure()

        #     for cat in ordered_cats:
        #         sub = dist_df[dist_df['volume_category'] == cat]
        #         if sub.empty:
        #             continue
        #         if style == "Violin + beeswarm":
        #             fig.add_trace(go.Violin(
        #                 x=[cat] * len(sub),
        #                 y=sub['hospital_pct'],
        #                 name=cat,
        #                 points='all',
        #                 jitter=0.3,
        #                 pointpos=0.0,
        #                 box_visible=True,
        #                 meanline_visible=True,
        #                 marker=dict(size=6, opacity=0.55)
        #             ))
        #         else:
        #             fig.add_trace(go.Box(
        #                 x=[cat] * len(sub),
        #                 y=sub['hospital_pct'],
        #                 name=cat,
        #                 boxpoints='all',
        #                 jitter=0.3,
        #                 pointpos=0.0,
        #                 marker=dict(size=6, opacity=0.55)
        #             ))

        #     fig.update_layout(
        #         showlegend=False,
        #         xaxis_title=None,
        #         yaxis_title='Robotic % (per hospital)',
        #         height=420,
        #         plot_bgcolor='rgba(0,0,0,0)',
        #         paper_bgcolor='rgba(0,0,0,0)'
        #     )
        #     st.plotly_chart(fig, use_container_width=True)
        # except Exception as e:
        #     st.info(f"Distribution view unavailable: {e}")

        # # Continuous scatter with linear trendline
        # try:
        #     from lib.national_utils import compute_robotic_volume_distribution
        #     dist_df = compute_robotic_volume_distribution(df)
        #     if not dist_df.empty:
        #         st.subheader("Continuous relationship: volume vs robotic %")
        #         cont = px.scatter(
        #             dist_df,
        #             x='total_surgeries',
        #             y='hospital_pct',
        #             color='volume_category',
        #             opacity=0.65,
        #             title='Hospital volume (continuous) vs robotic %'
        #         )
        #         # Linear trendline via numpy
        #         try:
        #             xvals = dist_df['total_surgeries'].astype(float).values
        #             yvals = dist_df['hospital_pct'].astype(float).values
        #             if len(xvals) >= 2:
        #                 slope, intercept = np.polyfit(xvals, yvals, 1)
        #                 xs = np.linspace(xvals.min(), xvals.max(), 100)
        #                 ys = slope * xs + intercept
        #                 cont.add_trace(go.Scatter(x=xs, y=ys, mode='lines', name='Linear trend', line=dict(color='#4c78a8', width=2)))
        #         except Exception:
        #             pass

        #         cont.update_layout(
        #             xaxis_title='Total surgeries (2024)',
        #             yaxis_title='Robotic % (per hospital)',
        #             height=420,
        #             plot_bgcolor='rgba(0,0,0,0)',
        #             paper_bgcolor='rgba(0,0,0,0)'
        #         )
        #         st.plotly_chart(cont, use_container_width=True)
        #         # WTLF + key findings for continuous scatter
        #         try:
        #             r = float(np.corrcoef(xvals, yvals)[0,1]) if len(xvals) > 1 else 0.0
        #             with st.expander("What to look for and key findings"):
        #                 st.markdown(
        #                     f"""
        #                     **What to look for:**
        #                     - Overall relationship slope between volume and robotic%
        #                     - Clusters and outliers at high/low volumes

        #                     **Key findings:**
        #                     - Linear trend slope: **{slope:.3f}** percentage points per surgery (approx)
        #                     - Correlation (r): **{r:.2f}**
        #                     """
        #                 )
        #         except Exception:
        #             pass
        # except Exception:
        #     pass