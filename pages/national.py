import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from streamlit_option_menu import option_menu
import sys
import os

# Add the parent directory to the Python path to import lib
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from lib.national_utils import *

# --- Page Configuration ---
st.set_page_config(
    page_title="National Overview",
    page_icon="🇫🇷",
    layout="wide"
)

# --- HIDE THE DEFAULT SIDEBAR ---
st.markdown("""
    <style>
        [data-testid="stSidebarNav"] {
            display: none;
        }
    </style>
""", unsafe_allow_html=True)

# --- TOP NAVIGATION HEADER ---
selected = option_menu(
    menu_title=None,
    options=["Home", "Hospital Dashboard", "National Overview"],
    icons=["house", "clipboard2-data", "globe2"],
    menu_icon="cast",
    default_index=2,
    orientation="horizontal",
)

if selected == "Home":
    st.switch_page("main.py")
elif selected == "Hospital Dashboard":
    if st.session_state.get('selected_hospital_id'):
        st.switch_page("pages/dashboard.py")
    else:
        st.warning("Please select a hospital from the Home page first.")

# --- Load Data (Parquet via loader) ---
df = load_and_prepare_data()

# --- Page Title and Notice ---
st.title("🇫🇷 National Overview")

# Top notice in info callout
st.info("""
**National means are computed across hospitals (2020–2024 period).**
**Note: Only hospitals with ≥5 interventions per year are considered for this analysis.**
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
        "Avg Surgeries/Year", 
        f"{kpis['avg_surgeries_per_year']:.0f}"
    )

with col3:
    st.metric(
        "Avg Revisions/Year", 
        f"{kpis['avg_revisions_per_year']:.0f}"
    )

with col4:
    delta_color = "normal" if delta_less_50 <= 0 else "inverse"
    st.metric(
        "Hospitals <50/year (2024)",
        f"{volume_2024['<50']:.0f}",
        delta_color=delta_color
    )

with col5:
    delta_color = "normal" if delta_more_200 >= 0 else "inverse"
    st.metric(
        "Hospitals >200/year (2024)",
        f"{volume_2024['>200']:.0f}",
        delta_color=delta_color
    )

# Volume Distribution Chart
st.subheader("Volume Distribution by Hospital (2024)")

# Prepare data for chart
volume_data = []
for bin_name, count in volume_2024.items():
    volume_data.append({
        'Volume Category': bin_name,
        'Number of Hospitals': count,
        'Percentage': (count / kpis['total_hospitals_2024']) * 100 if kpis['total_hospitals_2024'] > 0 else 0
    })

volume_df = pd.DataFrame(volume_data)

# Toggle for baseline comparison
show_baseline = st.toggle("Show 2020-2023 average comparison", value=True)

# Create Plotly chart
fig = go.Figure()

# Main bars for 2024
fig.add_trace(go.Bar(
    x=volume_df['Volume Category'],
    y=volume_df['Number of Hospitals'],
    name='2024',
    marker_color='#2E86AB',
    hovertemplate='<b>%{x}</b><br>Hospitals: %{y}<br>Percentage: %{text:.2f}%<extra></extra>',
    text=volume_df['Percentage'],
    texttemplate='%{text:.2f}%',
    textposition='auto'
))

if show_baseline:
    # Baseline bars (semi-transparent)
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
        marker_color='rgba(255, 193, 7, 0.7)',
        hovertemplate='<b>%{x}</b><br>Average Hospitals: %{y:.2f}<extra></extra>'
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

# First block: Affiliation cards
col1, col2 = st.columns(2)

with col1:
    st.subheader("Public")
    
    # Public university hospitals
    public_univ_count = affiliation_counts.get('Public – Univ.', 0)
   
    st.metric(
        "Public University Hospital",
        f"{public_univ_count}",
    )
    
    # Public non-academic hospitals
    public_non_acad_count = affiliation_counts.get('Public – Non-Acad.', 0)
   
    st.metric(
        "Public, No Academic Affiliation",
        f"{public_non_acad_count}",
    )

with col2:
    st.subheader("Private")
    
    # Private for-profit hospitals
    private_for_profit_count = affiliation_counts.get('Private – For-profit', 0)
    
    st.metric(
        "Private For Profit",
        f"{private_for_profit_count}",
        
    )
    
    # Private not-for-profit hospitals
    private_not_profit_count = affiliation_counts.get('Private – Not-for-profit', 0)
    
    st.metric(
        "Private Not For Profit",
        f"{private_not_profit_count}",
    )

# Second block: Stacked bar chart
st.subheader("Hospital Labels by Affiliation Type")

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
            'SOFFCO Label': '#e9967a',
            'CSO Label': '#00008b',
            'Both': '#00bfff',
            'None': '#9bef01'
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

# --- (3) PROCEDURES ---
st.header("Procedures")

# Compute procedure data
procedure_averages = compute_procedure_averages_2020_2024(df)
procedure_totals_2024 = get_2024_procedure_totals(df)

# Two-column layout
col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("Average Procedures (2020-2024)")
    
    # Prepare data for bar chart
    avg_data = []
    for proc_code, proc_name in BARIATRIC_PROCEDURE_NAMES.items():
        if proc_code in procedure_averages:
            avg_data.append({
                'Procedure': proc_name,
                'Average Count': procedure_averages[proc_code]
            })
    
    avg_df = pd.DataFrame(avg_data)
    avg_df = avg_df.sort_values('Average Count', ascending=False)
    
    if not avg_df.empty:
        fig = px.bar(
            avg_df,
            x='Procedure',
            y='Average Count',
            title="Average Annual Procedures by Type",
            color='Average Count',
            color_continuous_scale='Blues'
        )
        
        fig.update_layout(
            xaxis_title="Procedure Type",
            yaxis_title="Average Annual Count",
            hovermode='x unified',
            height=400,
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            font=dict(size=12),
            margin=dict(l=50, r=50, t=80, b=50)
        )
        
        fig.update_traces(
            hovertemplate='<b>%{x}</b><br>Average: %{y:.0f}<extra></extra>'
        )
        
        st.plotly_chart(fig, use_container_width=True)

with col2:
    st.subheader("2024 Totals")
    
    # Sleeve Gastrectomies in 2024
    sleeve_2024 = procedure_totals_2024.get('SLE', 0)
    st.metric(
        "Sleeve Gastrectomies (2024)",
        f"{sleeve_2024:,}"
    )
    
    # Total procedures in 2024
    total_2024 = procedure_totals_2024.get('total_all', 0)
    st.metric(
        "Total Procedures (2024)",
        f"{total_2024:,}"
    )

st.caption("Averages computed over 2020-2024 across eligible hospital-years.")

# --- (4) APPROACH TRENDS ---
st.header("Approach Trends")

# Compute approach data
approach_trends = compute_approach_trends(df)
approach_mix_2024 = compute_2024_approach_mix(df)




st.subheader("Surgical Approach Trends (2020-2024)")

# Prepare data for line chart
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
    y=trend_df['All Surgeries'],
    mode='lines+markers',
    name='All Surgeries',
    line=dict(color='#2E86AB', width=3),
    marker=dict(size=8, color='#2E86AB')
))

fig.add_trace(go.Scatter(
    x=trend_df['Year'],
    y=trend_df['Robotic Surgeries'],
    mode='lines+markers',
    name='Robotic Surgeries',
    line=dict(color='#F7931E', width=3),
    marker=dict(size=8, color='#F7931E')
))

fig.update_layout(
    title="Surgical Approach Trends",
    xaxis_title="Year",
    yaxis_title="Number of Surgeries",
    hovermode='x unified',
    height=400,
    showlegend=True,
    plot_bgcolor='rgba(0,0,0,0)',
    paper_bgcolor='rgba(0,0,0,0)',
    font=dict(size=12),
    margin=dict(l=50, r=50, t=80, b=50)
)

st.plotly_chart(fig, use_container_width=True)

# Two-column layout for trends and pie chart
col1, col2 = st.columns([2, 1])
with col1:
    st.subheader("Surgical Approach Mix (2024)")

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
                font=dict(size=12)
            )
            
            fig.update_traces(
                hovertemplate='<b>%{label}</b><br>Count: %{value}<br>Percentage: %{percent}<extra></extra>',
                textposition='outside',
                textinfo='percent+label',
                textfont=dict(size=11)
            )
            
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No approach data available for 2024.")
with col2:
    robotic_2024 = approach_trends['robotic'].get(2024, 0)
    st.metric(
        "Total Robotic Surgeries (2024)",
        f"{robotic_2024:,}"
    )





