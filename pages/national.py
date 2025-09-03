import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import sys
import os
import requests
import folium
from folium.plugins import HeatMap
from streamlit_folium import st_folium
import branca.colormap as cm
from navira.competitor_layers import build_cp_to_insee
from navira.geojson_loader import load_communes_geojson_filtered, load_communes_geojson, detect_insee_key

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

# Load additional datasets
from navira.data_loader import get_all_dataframes
all_data = get_all_dataframes()
recruitment = all_data.get('recruitment', pd.DataFrame())
french_cities = all_data.get('cities', pd.DataFrame())
# GeoJSON helper for departments
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
complications = all_data.get('complications', pd.DataFrame())
procedure_details = all_data.get('procedure_details', pd.DataFrame())

# Calculate national averages for comparisons
def calculate_national_averages(df: pd.DataFrame):
    """Calculate national averages for hospital comparisons"""
    try:
        # Filter for eligible hospitals (≥25 procedures per year)
        eligible = df[df['total_procedures_year'] >= 25].copy()
        if eligible.empty:
            return {}
        
        # Calculate procedure type averages
        procedure_averages = {}
        for proc_code in BARIATRIC_PROCEDURE_NAMES.keys():
            if proc_code in eligible.columns:
                avg = eligible[proc_code].mean()
                procedure_averages[proc_code] = float(avg) if not pd.isna(avg) else 0.0
        
        # Calculate surgical approach averages
        approach_averages = {}
        for approach_code in SURGICAL_APPROACH_NAMES.keys():
            if approach_code in eligible.columns:
                avg = eligible[approach_code].mean()
                approach_averages[approach_code] = float(avg) if not pd.isna(avg) else 0.0
        
        return {
            'procedure_averages': procedure_averages,
            'approach_averages': approach_averages,
            'total_procedures_avg': float(eligible['total_procedures_year'].mean())
        }
    except Exception as e:
        print(f"Error calculating national averages: {e}")
        return {}

national_averages = calculate_national_averages(df)

# --- Page Title and Notice ---
st.title("🇫🇷 National Overview")
# 

# Surgery-to-Population Ratio Choropleth
st.markdown("### Surgery Density by Department")
st.markdown("*Ratio of total bariatric surgeries to department population (surgeries per 100,000 inhabitants)*")

try:
    # Load population data
    @st.cache_data(show_spinner=False)
    def load_population_data():
        """Load and process the population data by department."""
        try:
            pop_df = pd.read_csv("data/DS_ESTIMATION_POPULATION (1).csv", sep=';')
            # Clean and process the data
            pop_df = pop_df[pop_df['GEO_OBJECT'] == 'DEP'].copy()  # Only departments
            pop_df = pop_df[pop_df['TIME_PERIOD'] == 2024].copy()  # Use 2020 data
            pop_df['dept_code'] = pop_df['GEO'].str.strip().str.replace('"', '')
            pop_df['population'] = pop_df['OBS_VALUE'].astype(int)
            return pop_df[['dept_code', 'population']]
        except Exception as e:
            st.error(f"Error loading population data: {e}")
            return pd.DataFrame()

    # Calculate surgery totals by department
    @st.cache_data(show_spinner=False)
    def calculate_surgery_by_department(_df):
        """Calculate total surgeries by department from hospital data."""
        try:
            # Get department from hospital data
            df_copy = _df.copy()
            df_copy['dept_code'] = df_copy['code_postal'].astype(str).str[:2]
            
            # Handle special cases (Corsica, overseas)
            def standardize_dept_code(postal_code):
                postal_str = str(postal_code)
                if postal_str.startswith('97') or postal_str.startswith('98'):
                    return postal_str[:3]
                elif postal_str.startswith('201'):
                    return '2A'
                elif postal_str.startswith('202'):
                    return '2B'
                else:
                    return postal_str[:2]
            
            df_copy['dept_code'] = df_copy['code_postal'].astype(str).apply(standardize_dept_code)
            
            # Sum total procedures by department
            dept_surgeries = df_copy.groupby('dept_code')['total_procedures_year'].sum().reset_index()
            dept_surgeries.columns = ['dept_code', 'total_surgeries']
            
            return dept_surgeries
        except Exception as e:
            st.error(f"Error calculating surgery totals: {e}")
            return pd.DataFrame()

    # Load the data
    population_data = load_population_data()
    surgery_data = calculate_surgery_by_department(df)
    
    if not population_data.empty and not surgery_data.empty:
        # Merge population and surgery data
        ratio_data = pd.merge(surgery_data, population_data, on='dept_code', how='inner')
        
        # Calculate ratio (surgeries per 100,000 inhabitants)
        ratio_data['surgery_ratio'] = (ratio_data['total_surgeries'] / ratio_data['population']) * 100000
        ratio_data['surgery_ratio'] = ratio_data['surgery_ratio'].round(1)
        
        # Display summary stats
        col1, col2, col3, col4 = st.columns([1, 1, 1.5, 1])
        with col1:
            st.metric("Departments with Data", len(ratio_data))
        with col2:
            avg_ratio = ratio_data['surgery_ratio'].mean()
            st.metric("Average Ratio", f"{avg_ratio:.1f}")
        with col3:
            max_dept = ratio_data.loc[ratio_data['surgery_ratio'].idxmax()]
            st.metric("Highest Ratio", f"Dep. {max_dept['dept_code']}: {max_dept['surgery_ratio']:.1f}")
        with col4:
            total_surgeries = ratio_data['total_surgeries'].sum()
            st.metric("Total Surgeries", f"{total_surgeries:,}")
        
        # Create the choropleth map
        gj = _get_fr_departments_geojson()
        if gj and not ratio_data.empty:
            m = folium.Map(location=[46.5, 2.5], zoom_start=6, tiles="CartoDB positron")
            
            # Create value mapping and colormap
            vmin = float(ratio_data['surgery_ratio'].min())
            vmax = float(ratio_data['surgery_ratio'].max())
            colormap = cm.linear.YlOrRd_09.scale(vmin, vmax)
            colormap.caption = 'Surgeries per 100K inhabitants'
            colormap.add_to(m)
            
            val_map = dict(zip(ratio_data['dept_code'].astype(str), ratio_data['surgery_ratio'].astype(float)))
            
            def _style_fn(feat):
                code = str(feat.get('properties', {}).get('code', ''))
                v = val_map.get(code, 0.0)
                opacity = 0.25 if v == 0 else 0.7
                return {"fillColor": colormap(v), "color": "#555555", "weight": 0.8, "fillOpacity": opacity}
            
            # Add GeoJSON with proper tooltips and popups
            def create_feature_popup(feature):
                """Create popup content for each department."""
                props = feature.get('properties', {})
                code = str(props.get('code', ''))
                name = str(props.get('nom', code))
                ratio_val = val_map.get(code, 0.0)
                
                # Get additional data for popup
                dept_row = ratio_data[ratio_data['dept_code'] == code]
                if not dept_row.empty:
                    surgeries = int(dept_row.iloc[0]['total_surgeries'])
                    population = int(dept_row.iloc[0]['population'])
                    
                    popup_html = f"""
                    <div style="font-family: Arial, sans-serif; min-width: 200px;">
                        <h4 style="margin: 0 0 8px 0; color: #d62728; font-size: 16px;">{name}</h4>
                        <div style="font-size: 12px; color: #666;">Department {code}</div>
                        <hr style="margin: 8px 0; border: none; border-top: 1px solid #ddd;">
                        <div style="display: flex; flex-direction: column; gap: 4px;">
                            <div><strong>Surgery Density:</strong> {ratio_val:.1f} per 100K inhabitants</div>
                            <div><strong>Total Surgeries:</strong> {surgeries:,}</div>
                            <div><strong>Population (2020):</strong> {population:,}</div>
                        </div>
                    </div>
                    """
                    return popup_html
                else:
                    return f"""
                    <div style="font-family: Arial, sans-serif; min-width: 200px;">
                        <h4 style="margin: 0 0 8px 0; color: #666; font-size: 16px;">{name}</h4>
                        <div style="font-size: 12px; color: #666;">Department {code}</div>
                        <hr style="margin: 8px 0; border: none; border-top: 1px solid #ddd;">
                        <div style="color: #888;">No surgery data available</div>
                    </div>
                    """
            
            # Create GeoJSON layer with proper popups
            geojson_layer = folium.GeoJson(
                gj,
                style_function=_style_fn,
                tooltip=folium.Tooltip("Click for details"),
                popup=None  # We'll add custom popups below
            )
            
            # Add custom popups to each feature
            for feature in gj['features']:
                code = str(feature.get('properties', {}).get('code', ''))
                name = str(feature.get('properties', {}).get('nom', code))
                ratio_val = val_map.get(code, 0.0)
                
                # Create tooltip text
                tooltip_text = f"{name}: {ratio_val:.1f} per 100K"
                
                # Create popup content
                popup_content = create_feature_popup(feature)
                
                # Add to the layer
                folium.GeoJson(
                    feature,
                    style_function=_style_fn,
                    tooltip=tooltip_text,
                    popup=folium.Popup(popup_content, max_width=300)
                ).add_to(m)
            
            # Fit bounds to France
            try:
                m.fit_bounds([[41.0, -5.3], [51.5, 9.6]])
            except Exception:
                pass
            
            # Display the map
            st_folium(m, width="100%", height=540, key="surgery_population_ratio_choropleth")
            
            # Show top/bottom departments
            st.markdown("#### 📊 Department Rankings")
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("**Highest Surgery Density (per 100K inhabitants)**")
                top_5 = ratio_data.nlargest(5, 'surgery_ratio')[['dept_code', 'surgery_ratio', 'total_surgeries']]
                for _, row in top_5.iterrows():
                    st.write(f"**Dep. {row['dept_code']}**: {row['surgery_ratio']:.1f} ({row['total_surgeries']} surgeries)")
            
            with col2:
                st.markdown("**📉 Lowest Surgery Density**")
                bottom_5 = ratio_data.nsmallest(5, 'surgery_ratio')[['dept_code', 'surgery_ratio', 'total_surgeries']]
                for _, row in bottom_5.iterrows():
                    st.write(f"**Dep. {row['dept_code']}**: {row['surgery_ratio']:.1f} ({row['total_surgeries']} surgeries)")
        else:
            st.error("Could not load department GeoJSON for surgery ratio map.")
    else:
        st.error("Could not load population or surgery data for ratio calculation.")
        
except Exception as e:
    st.error(f"Error creating surgery-to-population ratio map: {e}")
    st.exception(e)

## Moved: Kaplan–Meier national complication rate section now lives under the "National Complication Rate Trends" subsection below.

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

# Calculate label statistics for university vs private hospitals
try:
    # Calculate university hospitals with labels
    univ_total = affiliation_counts.get('Public – Univ.', 0)
    univ_labeled = (
        label_breakdown.get('Public – Univ.', {}).get('SOFFCO Label', 0) +
        label_breakdown.get('Public – Univ.', {}).get('CSO Label', 0) +
        label_breakdown.get('Public – Univ.', {}).get('Both', 0)
    )
    univ_pct = round((univ_labeled / univ_total * 100)) if univ_total > 0 else 0
    
    # Calculate private hospitals with labels
    private_total = (
        affiliation_counts.get('Private – For-profit', 0) +
        affiliation_counts.get('Private – Not-for-profit', 0)
    )
    private_labeled = (
        label_breakdown.get('Private – For-profit', {}).get('SOFFCO Label', 0) +
        label_breakdown.get('Private – For-profit', {}).get('CSO Label', 0) +
        label_breakdown.get('Private – For-profit', {}).get('Both', 0) +
        label_breakdown.get('Private – Not-for-profit', {}).get('SOFFCO Label', 0) +
        label_breakdown.get('Private – Not-for-profit', {}).get('CSO Label', 0) +
        label_breakdown.get('Private – Not-for-profit', {}).get('Both', 0)
    )
    private_pct = round((private_labeled / private_total * 100)) if private_total > 0 else 0
    
    st.markdown(f"#### **{univ_pct}%** of the university hospitals have SOFFCO, CSO or both labels and **{private_pct}%** of private hospitals have SOFFCO, CSO or both labels")
except Exception:
    st.markdown("Label statistics unavailable")

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

# Single column layout
col1 = st.columns(1)[0]

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
        
        # Group less common procedures under "Other"
        other_procedures = ['NDD', 'GVC', 'DBP']  # Not Defined, Calibrated Vertical Gastroplasty, Bilio-pancreatic Diversion
        other_total = sum(procedure_totals_2020_2024.get(proc_code, 0) for proc_code in other_procedures)
        
        for proc_code, proc_name in BARIATRIC_PROCEDURE_NAMES.items():
            if proc_code in procedure_totals_2020_2024:
                value = procedure_totals_2020_2024[proc_code]
                
                # Skip individual entries for procedures that will be grouped under "Other"
                if proc_code in other_procedures:
                    continue
                    
                raw_percentage = (value / total_procedures) * 100 if total_procedures > 0 else 0
                # Show decimals for percentages less than 1%, otherwise round to whole number
                percentage = round(raw_percentage, 1) if raw_percentage < 1 else round(raw_percentage)
                tot_data.append({
                    'Procedure': proc_name,
                    'Value': value,
                    'Percentage': percentage
                })
        
        # Add "Other" category for grouped procedures
        if other_total > 0:
            other_percentage = (other_total / total_procedures) * 100 if total_procedures > 0 else 0
            tot_data.append({
                'Procedure': 'Other',
                'Value': other_total,
                'Percentage': other_percentage  # Store raw percentage, format later
            })
        chart_df = pd.DataFrame(tot_data).sort_values('Value', ascending=True)
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
        
        # Group less common procedures under "Other"
        other_procedures = ['NDD', 'GVC', 'DBP']  # Not Defined, Calibrated Vertical Gastroplasty, Bilio-pancreatic Diversion
        other_total = sum(procedure_totals_2024.get(proc_code, 0) for proc_code in other_procedures)
        
        for proc_code, proc_name in BARIATRIC_PROCEDURE_NAMES.items():
            if proc_code in procedure_totals_2024:
                value = procedure_totals_2024[proc_code]
                
                # Skip individual entries for procedures that will be grouped under "Other"
                if proc_code in other_procedures:
                    continue
                    
                raw_percentage = (value / total_procedures) * 100 if total_procedures > 0 else 0
                # Show decimals for percentages less than 1%, otherwise round to whole number
                percentage = round(raw_percentage, 1) if raw_percentage < 1 else round(raw_percentage)
                tot_data.append({
                    'Procedure': proc_name,
                    'Value': value,
                    'Percentage': percentage
                })
        
        # Add "Other" category for grouped procedures
        if other_total > 0:
            other_percentage = (other_total / total_procedures) * 100 if total_procedures > 0 else 0
            tot_data.append({
                'Procedure': 'Other',
                'Value': other_total,
                'Percentage': other_percentage  # Store raw percentage, format later
            })
        chart_df = pd.DataFrame(tot_data).sort_values('Value', ascending=True)
        y_title = "Total count (2024)"
        chart_title = "Total Procedures by Type (2024)"
        hover_tmpl = '<b>%{x}</b><br>Total 2024: %{y:,}<br>Percentage: %{customdata[0]}%<extra></extra>'

    if not chart_df.empty:

        # Use a single blue color for all bars to emphasize totals
        # Build label: show one decimal for percentages <1%, otherwise whole number
        # Use a fresh calculation to ensure consistency
        def format_percentage(p):
            if p < 1:
                return f"{p:.1f}%"
            else:
                return f"{p:.0f}%"
        chart_df = chart_df.assign(Label=chart_df['Percentage'].apply(format_percentage))

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
            
            # Always use area chart. For single‑year (2024) repeat the same shares
            # at two x positions around 2024 so the stacked areas span the full width.
            plot_df = proc_trend_df.copy()
            if toggle_2024_only and not plot_df.empty:
                try:
                    left_x = 2023.5
                    right_x = 2024.5
                    base_rows = plot_df.copy()
                    left = base_rows.copy(); left['Year'] = left_x
                    right = base_rows.copy(); right['Year'] = right_x
                    plot_df = pd.concat([left, right], ignore_index=True)
                except Exception:
                    pass

            # Create side-by-side comparison
            col1, col2 = st.columns([2, 1])  # National graphs larger (2), Hospital comparison smaller (1)
            
            with col1:
                st.markdown("#### National: Procedure Mix Trends")
                fig = px.area(
                    plot_df, x='Year', y='Share', color='Procedure',
                    title=f'National Procedure Mix ({time_period})',
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
                # For single-year view, center 2024 and show only that tick
                if toggle_2024_only:
                    fig.update_layout(xaxis=dict(tickmode='array', tickvals=[2024], ticktext=['2024'], range=[2023.25, 2024.75]))
                    fig.update_traces(hovertemplate='<b>%{fullData.name}</b><br>Year: 2024<br>Share: %{y:.1f}%<extra></extra>')
                fig.update_traces(line=dict(width=0), opacity=0.9)
                
                st.plotly_chart(fig, use_container_width=True)
            
            # National Averages Summary
            st.markdown("#### National Averages Summary (2024)")
            
            if national_averages:
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    avg_total = national_averages.get('total_procedures_avg', 0)
                    st.metric("Avg Procedures per Hospital", f"{int(avg_total):,}")
                
                with col2:
                    proc_avgs = national_averages.get('procedure_averages', {})
                    sleeve_avg = proc_avgs.get('SLE', 0)
                    sleeve_pct = (sleeve_avg / avg_total * 100) if avg_total > 0 else 0
                    st.metric("Avg Sleeve Gastrectomy", f"{sleeve_pct:.1f}%")
                
                with col3:
                    approach_avgs = national_averages.get('approach_averages', {})
                    robotic_avg = approach_avgs.get('ROB', 0)
                    robotic_pct = (robotic_avg / avg_total * 100) if avg_total > 0 else 0
                    st.metric("Avg Robotic Approach", f"{robotic_pct:.1f}%")
            
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

        # Create side-by-side comparison
        col1, col2 = st.columns([2, 1])  # National graphs larger (2), Hospital comparison smaller (1)
        
        with col1:
            st.markdown("#### National: Surgical Approach Distribution")
            fig = px.pie(
                pie_df,
                values='Count',
                names='Approach',
                title="National Approach Distribution (2024)",
                color_discrete_sequence=['#2E86AB', '#F7931E', '#A23B72', '#F18F01']
            )
            
            fig.update_layout(
                height=400,
                showlegend=False,
                font=dict(size=12)
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
# Single column layout for trends
with st.container():
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
        showlegend=False,
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
            yaxis_title="",
            height=440,
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            font=dict(size=12),
            margin=dict(l=160, r=50, t=80, b=40),
            yaxis=dict(automargin=True, categoryorder='total ascending')
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
        fig_merge.update_layout(height=380, plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', xaxis_title=None, yaxis_title='Robotic Surgery Percentage (%)', showlegend=False)
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
            
            # Add hospital names to the dataframe for hover information
            try:
                establishments, _ = get_dataframes()
                if 'id' in establishments.columns and 'name' in establishments.columns:
                    # Ensure consistent data types
                    establishments['id'] = establishments['id'].astype(str)
                    dist_df['hospital_id'] = dist_df['hospital_id'].astype(str)
                    
                    # Merge hospital names
                    dist_df = dist_df.merge(
                        establishments[['id', 'name']].drop_duplicates(subset=['id']),
                        left_on='hospital_id',
                        right_on='id',
                        how='left'
                    )
                    dist_df['hospital_name'] = dist_df['name'].fillna('Unknown Hospital')
                else:
                    dist_df['hospital_name'] = 'Hospital ' + dist_df['hospital_id'].astype(str)
            except Exception:
                dist_df['hospital_name'] = 'Hospital ' + dist_df['hospital_id'].astype(str)
            
            cont = px.scatter(
                dist_df,
                x='total_surgeries',
                y='hospital_pct',
                color='volume_category',
                hover_data=['hospital_name'],
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

# --- COMPLICATIONS ANALYSIS ---
st.header("Complications Analysis")

if not complications.empty:
    st.markdown(
        """
        <div class=\"nv-info-wrap\">
          <div class=\"nv-h3\">National Complications Overview</div>
          <div class=\"nv-tooltip\"><span class=\"nv-info-badge\">i</span>
            <div class=\"nv-tooltiptext\">
              <b>Understanding this analysis:</b><br/>
              This section analyzes complication rates across all hospitals from 2020-2024. It shows trends in patient safety outcomes and compares hospital performance against national benchmarks.<br/><br/>
              <b>Key Metrics:</b><br/>
              • Rolling Rate: 12-month moving average of complication rates<br/>
              • National Average: Benchmark rate across all eligible hospitals<br/>
              • Confidence Intervals: Statistical range of expected performance
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True
    )
    
    # Calculate overall statistics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total_procedures = complications['procedures_count'].sum()
        st.metric("Total Procedures Analyzed", f"{int(total_procedures):,}")
    
    with col2:
        total_complications = complications['complications_count'].sum()
        st.metric("Total Complications", f"{int(total_complications):,}")
    
    with col3:
        if total_procedures > 0:
            overall_rate = (total_complications / total_procedures) * 100
            st.metric("Overall Complication Rate", f"{overall_rate:.2f}%")
    
    
    # Temporal trend of national complication rates
    st.markdown("#### National Complication Rate Trends")
    
    # Calculate quarterly national averages
    quarterly_stats = complications.groupby('quarter_date').agg({
        'procedures_count': 'sum',
        'complications_count': 'sum',
        'national_average': 'mean'
    }).reset_index()
    
    quarterly_stats['actual_rate'] = (quarterly_stats['complications_count'] / quarterly_stats['procedures_count'] * 100)
    quarterly_stats['national_avg_pct'] = quarterly_stats['national_average'] * 100
    
    if not quarterly_stats.empty:
        fig = go.Figure()
        

        
        # Add actual complication rate
        fig.add_trace(go.Scatter(
            x=quarterly_stats['quarter_date'],
            y=quarterly_stats['actual_rate'],
            mode='lines+markers',
            name='National Rate',
            line=dict(color='#1f77b4', width=3),
            marker=dict(size=6)
        ))
        
        fig.update_layout(
            title="National Complication Rate Over Time",
            xaxis_title="Quarter",
            yaxis_title="Complication Rate (%)",
            height=400,
            hovermode='x unified',
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)'
        )
        
        st.plotly_chart(fig, use_container_width=True)
    
    # Kaplan–Meier representation, moved into the Trends subsection
    st.markdown("##### National Complication Rate Over Time (Kaplan–Meier)")
    col_km1, col_km2 = st.columns([1,2])
    with col_km1:
        km_interval = st.radio("Interval", options=["6 months", "3 months"], index=0, horizontal=True, key="km_interval")
    with col_km2:
        km_label_opts = st.multiselect("Labels", options=["CSO", "SOFFCO", "None"], default=["CSO", "SOFFCO", "None"], help="Filter hospitals by labels", key="km_labels")
        km_top10 = st.checkbox("Top 10 hospitals by procedures (2020–2024)", value=False, key="km_top10")

    # Build hospital subset based on labels and top 10
    km_subset_ids = set()
    try:
        est_df = st.session_state.get('establishments', None) or all_data.get('establishments')
        ann_df = st.session_state.get('annual', None) or all_data.get('annual')
        if est_df is None or ann_df is None:
            est_df, ann_df = get_dataframes()
        estN = est_df.copy()
        estN['id'] = estN['id'].astype(str)
        mask_any = pd.Series([False]*len(estN))
        label_parts = []
        if 'CSO' in km_label_opts and 'cso' in estN.columns:
            label_parts.append(estN['cso'] == 1)
        if 'SOFFCO' in km_label_opts and 'LAB_SOFFCO' in estN.columns:
            label_parts.append(estN['LAB_SOFFCO'] == 1)
        if 'None' in km_label_opts:
            cond_none = ((estN.get('cso', 0) != 1) & (estN.get('LAB_SOFFCO', 0) != 1))
            label_parts.append(cond_none)
        if label_parts:
            mask_any = label_parts[0]
            for p in label_parts[1:]:
                mask_any = mask_any | p
        est_filtered = estN[mask_any]
        if km_top10 and ann_df is not None and not ann_df.empty:
            annN = ann_df.copy()
            annN['id'] = annN['id'].astype(str)
            vol = annN.groupby('id')['total_procedures_year'].sum().sort_values(ascending=False).head(10)
            est_filtered = est_filtered[est_filtered['id'].isin(vol.index.astype(str))]
        km_subset_ids = set(est_filtered['id'].astype(str)) if not est_filtered.empty else set()
    except Exception:
        km_subset_ids = set()

    # Compute KM curve using new robust system
    from km import compute_km_from_aggregates, debug_signature
    from charts import create_km_chart
    from utils.cache import debug_dataframe_signature, show_debug_panel
    
    # Debug signatures for tracing
    debug_signatures = {}
    
    km_comp_df = all_data.get('complications', pd.DataFrame())
    debug_signatures['raw_complications'] = debug_dataframe_signature(km_comp_df, "Raw complications data")
    
    if not km_comp_df.empty:
        # Apply filters
        km_data = km_comp_df.copy()
        km_data['hospital_id'] = km_data['hospital_id'].astype(str)
        debug_signatures['after_id_conversion'] = debug_dataframe_signature(km_data, "After ID conversion")
        
        if km_subset_ids:
            km_data = km_data[km_data['hospital_id'].isin(km_subset_ids)]
            debug_signatures['after_hospital_filter'] = debug_dataframe_signature(km_data, f"After hospital filter ({len(km_subset_ids)} hospitals)")
        
        km_data = km_data.dropna(subset=['quarter_date']).sort_values('quarter_date')
        debug_signatures['after_date_filter'] = debug_dataframe_signature(km_data, "After date filter")
        
        # Create time intervals
        km_data['year'] = km_data['quarter_date'].dt.year
        if km_interval.startswith('6'):
            km_data['bucket'] = ((km_data['quarter_date'].dt.quarter - 1) // 2 + 1)
            km_xaxis_label = '6‑month interval'
            time_suffix = 'H'
        else:
            km_data['bucket'] = km_data['quarter_date'].dt.quarter
            km_xaxis_label = '3‑month interval (quarter)'
            time_suffix = 'Q'
        
        km_data['time_label'] = km_data['year'].astype(int).astype(str) + ' ' + time_suffix + km_data['bucket'].astype(int).astype(str)
        
        # Aggregate by time intervals
        km_agg = km_data.groupby(['year', 'bucket', 'time_label'], as_index=False).agg({
            'complications_count': 'sum',
            'procedures_count': 'sum'
        }).sort_values(['year', 'bucket'])
        
        debug_signatures['aggregated_data'] = debug_dataframe_signature(km_agg, "Aggregated by time intervals")
        
        if not km_agg.empty:
            try:
                # Use the robust KM computation
                km_curve = compute_km_from_aggregates(
                    df=km_agg,
                    time_col='time_label',
                    event_col='complications_count', 
                    at_risk_col='procedures_count',
                    group_cols=None,  # National level
                    data_hash=debug_signatures['aggregated_data']['hash'],
                    cache_version="v1"
                )
                
                debug_signatures['km_curve'] = debug_dataframe_signature(km_curve, "Final KM curve")
                
                if not km_curve.empty:
                    # Create chart using new system - showing complication rate
                    fig_km_nat = create_km_chart(
                        curve_df=km_curve,
                        page_id="national",
                        title="National Complication Rate Over Time (KM)",
                        yaxis_title='Complication Rate (%)',
                        xaxis_title=km_xaxis_label,
                        height=320,
                        color='#e67e22',
                        show_complication_rate=True
                    )
                    
                    st.plotly_chart(fig_km_nat, use_container_width=True, key="km_national_v2")
                else:
                    st.info('KM computation returned empty results.')
                    
            except Exception as e:
                st.error(f"Error computing KM curve: {e}")
                debug_signatures['km_error'] = {'error': str(e)}
        else:
            st.info('No data to compute national KM curve with current filters.')
            debug_signatures['no_data'] = {'message': 'Empty aggregated data'}
    else:
        st.info('Complications dataset unavailable.')
        debug_signatures['no_raw_data'] = {'message': 'No complications data'}
    
    # Show debug panel (collapsed by default)
    if st.checkbox("Show KM debug info", value=False, key="km_debug_national"):
        show_debug_panel(debug_signatures, expanded=True)

    # Hospital performance trends ("spaghetti" plot)
    st.markdown("#### Hospital Performance Over Time")
    
    st.info("💡 **About 'top 100 by volume'**: To ensure readability and performance, the spaghetti plot shows only the 100 hospitals with the highest total procedure volume. This represents the largest and most active bariatric surgery centers while maintaining chart clarity.")
    
    hosp_trends = complications.copy()
    if not hosp_trends.empty:
        # Build per-hospital series of rolling rates
        hosp_trends['rolling_pct'] = pd.to_numeric(hosp_trends['rolling_rate'], errors='coerce') * 100
        # Keep reasonable number of lines for performance: top 100 hospitals by total procedures
        totals = hosp_trends.groupby('hospital_id')['procedures_count'].sum().sort_values(ascending=False)
        keep_ids = set(totals.head(100).index.astype(str))
        sub = hosp_trends[hosp_trends['hospital_id'].astype(str).isin(keep_ids)].copy()
        if not sub.empty:
            # Create spaghetti plot using go.Figure for opacity control
            spaghetti = go.Figure()
            
            # Add individual hospital lines with low opacity
            for hosp_id in sub['hospital_id'].unique():
                hosp_data = sub[sub['hospital_id'] == hosp_id]
                spaghetti.add_trace(go.Scatter(
                    x=hosp_data['quarter_date'],
                    y=hosp_data['rolling_pct'],
                    mode='lines',
                    name=f'Hospital {hosp_id}',
                    line=dict(width=1),
                    opacity=0.25,
                    showlegend=False,
                    hoverinfo='skip'
                ))
            
            # Overlay bold national rate
            if not quarterly_stats.empty:
                spaghetti.add_trace(go.Scatter(
                    x=quarterly_stats['quarter_date'],
                    y=quarterly_stats['actual_rate'],
                    mode='lines',
                    name='National Average',
                    line=dict(color='#ff7f0e', width=3),
                    showlegend=True
                ))
            
            spaghetti.update_layout(
                title='Hospital 12‑month Rolling Complication Rates (top 100 by volume)',
                xaxis_title='Quarter',
                yaxis_title='Complication Rate (%)',
                height=420,
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)',
                showlegend=False
            )
            st.plotly_chart(spaghetti, use_container_width=True)

else:
    st.info("Complications data not available for national analysis.")



# --- ADVANCED PROCEDURE METRICS ---
st.header("Advanced Procedure Metrics")

if not procedure_details.empty:
    st.markdown(
        """
        <div class=\"nv-info-wrap\">
          <div class=\"nv-h3\">Detailed Procedure Analysis</div>
          <div class=\"nv-tooltip\"><span class=\"nv-info-badge\">i</span>
            <div class=\"nv-tooltiptext\">
              <b>Understanding this analysis:</b><br/>
              This section provides detailed insights into surgical procedures, including procedure-specific robotic rates, primary vs revisional surgery patterns, and robotic approach by procedure type. Data covers 2020-2024 across all eligible hospitals.<br/><br/>
              <b>Key Metrics:</b><br/>
              • Procedure-specific robotic rates<br/>
              • Primary vs revisional surgery breakdown<br/>
              • Robotic approach adoption by procedure type
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True
    )
    
    # Procedure-specific robotic rates
    st.markdown("#### Procedure-Specific Robotic Rates (2024)")
    
    # Calculate robotic rates by procedure type for 2024
    procedure_2024 = procedure_details[procedure_details['year'] == 2024]
    
    if not procedure_2024.empty:
        robotic_by_procedure = procedure_2024[
            procedure_2024['surgical_approach'] == 'ROB'
        ].groupby('procedure_type')['procedure_count'].sum().reset_index()
        robotic_by_procedure = robotic_by_procedure.rename(columns={'procedure_count': 'robotic_count'})
        
        total_by_procedure = procedure_2024.groupby('procedure_type')['procedure_count'].sum().reset_index()
        total_by_procedure = total_by_procedure.rename(columns={'procedure_count': 'total_count'})
        
        # Merge to calculate percentages
        procedure_robotic_rates = total_by_procedure.merge(
            robotic_by_procedure, 
            on='procedure_type', 
            how='left'
        ).fillna(0)
        procedure_robotic_rates['robotic_rate'] = (
            procedure_robotic_rates['robotic_count'] / procedure_robotic_rates['total_count'] * 100
        )
        
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
        
        procedure_robotic_rates['procedure_name'] = procedure_robotic_rates['procedure_type'].map(procedure_names)
        procedure_robotic_rates = procedure_robotic_rates.sort_values('robotic_rate', ascending=False)
        
        # Filter to show only Sleeve Gastrectomy and Gastric Bypass
        procedure_robotic_rates = procedure_robotic_rates[
            procedure_robotic_rates['procedure_type'].isin(['SLE', 'BPG'])
        ]
        
        # Create visualization
        fig = px.bar(
            procedure_robotic_rates,
            x='robotic_rate',
            y='procedure_name',
            orientation='h',
            title="Robotic Adoption by Procedure Type (2024)",
            labels={'robotic_rate': 'Robotic Rate (%)', 'procedure_name': 'Procedure Type'},
            text='robotic_rate'
        )
        
        fig.update_traces(
            texttemplate='%{text:.1f}%',
            textposition='outside',
            cliponaxis=False
        )
        
        fig.update_layout(
            height=400,
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            yaxis={'categoryorder': 'total ascending'}
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Show summary table
        display_table = procedure_robotic_rates[['procedure_name', 'total_count', 'robotic_count', 'robotic_rate']].copy()
        display_table['robotic_rate'] = display_table['robotic_rate'].round(1)
        display_table = display_table.rename(columns={
            'procedure_name': 'Procedure',
            'total_count': 'Total Procedures',
            'robotic_count': 'Robotic Procedures',
            'robotic_rate': 'Robotic Rate (%)'
        })
        
        st.dataframe(display_table, use_container_width=True, hide_index=True)
    
    # Primary vs Revisional Surgery Analysis
    st.markdown("#### Primary vs Revisional Surgery (2024)")
    
    if not procedure_2024.empty:
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("##### Primary Procedures")
            primary_2024 = procedure_2024[procedure_2024['is_revision'] == 0]
            if not primary_2024.empty:
                total_primary = primary_2024['procedure_count'].sum()
                robotic_primary = primary_2024[primary_2024['surgical_approach'] == 'ROB']['procedure_count'].sum()
                robotic_rate_primary = (robotic_primary / total_primary * 100) if total_primary > 0 else 0
                
                st.metric("Total Primary Procedures", f"{int(total_primary):,}")
                st.metric("Robotic Primary Procedures", f"{int(robotic_primary):,}")
                st.metric("Robotic Rate (Primary)", f"{robotic_rate_primary:.1f}%")
        
        with col2:
            st.markdown("##### Revision Procedures")
            revision_2024 = procedure_2024[procedure_2024['is_revision'] == 1]
            if not revision_2024.empty:
                total_revision = revision_2024['procedure_count'].sum()
                robotic_revision = revision_2024[revision_2024['surgical_approach'] == 'ROB']['procedure_count'].sum()
                robotic_rate_revision = (robotic_revision / total_revision * 100) if total_revision > 0 else 0
                
                st.metric("Total Revision Procedures", f"{int(total_revision):,}")
                st.metric("Robotic Revision Procedures", f"{int(robotic_revision):,}")
                st.metric("Robotic Rate (Revision)", f"{robotic_rate_revision:.1f}%")
    
    # Robotic Approach by Procedure Type Over Time
    st.markdown("#### Robotic Adoption Trends by Procedure (2020-2024)")
    
    # Calculate yearly robotic rates by procedure
    yearly_procedure_trends = []
    
    for year in range(2020, 2025):
        year_data = procedure_details[procedure_details['year'] == year]
        if year_data.empty:
            continue
            
        for proc_type in year_data['procedure_type'].unique():
            proc_data = year_data[year_data['procedure_type'] == proc_type]
            total_procedures = proc_data['procedure_count'].sum()
            robotic_procedures = proc_data[proc_data['surgical_approach'] == 'ROB']['procedure_count'].sum()
            
            if total_procedures > 0:
                robotic_rate = (robotic_procedures / total_procedures) * 100
                yearly_procedure_trends.append({
                    'year': year,
                    'procedure_type': proc_type,
                    'procedure_name': procedure_names.get(proc_type, proc_type),
                    'robotic_rate': robotic_rate,
                    'total_procedures': total_procedures
                })
    
    if yearly_procedure_trends:
        trends_df = pd.DataFrame(yearly_procedure_trends)
        
        # Filter to show only Sleeve Gastrectomy and Gastric Bypass
        trends_df = trends_df[trends_df['procedure_type'].isin(['SLE', 'BPG'])]
        
        if not trends_df.empty:
            fig = px.line(
                trends_df,
                x='year',
                y='robotic_rate',
                color='procedure_name',
                title="Robotic Adoption Trends by Major Procedure Types",
                labels={'robotic_rate': 'Robotic Rate (%)', 'year': 'Year', 'procedure_name': 'Procedure'}
            )
            
            fig.update_layout(
                height=400,
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)'
            )
            
            st.plotly_chart(fig, use_container_width=True)
    
    # Summary insights
    with st.expander("Key Insights and Analysis"):
        st.markdown("""
        **Key Findings from Advanced Procedure Analysis:**
        
        **Procedure-Specific Robotic Adoption:**
        - Shows which procedures are most/least likely to be performed robotically
        - Identifies opportunities for robotic surgery expansion
        - Reveals procedure complexity and technology suitability patterns
        
        **Primary vs Revisional Surgery:**
        - Compares robotic adoption between initial and revision procedures
        - May indicate surgeon comfort and patient selection criteria
        - Shows technology adoption in complex vs routine cases
        
        **Temporal Trends:**
        - Tracks how robotic adoption varies by procedure type over time
        - Identifies which procedures are driving overall robotic growth
        - Shows procedure-specific learning curves and adoption patterns
        
        **Clinical Implications:**
        - Higher robotic rates in certain procedures may indicate clinical benefits
        - Variation between hospitals suggests opportunities for best practice sharing
        - Trends can inform training and equipment investment decisions
        """)

else:
    st.info("Advanced procedure data not available for national analysis.")
    
    st.markdown("""
    **Available from current data:**
    - Overall robotic surgery trends (shown in Approach Trends section above)
    - Basic procedure type distributions
    - General surgical approach patterns
    
    **Requires detailed procedure data:**
    - Procedure-specific robotic rates (e.g., % of gastric sleeves done robotically)
    - Primary vs revisional robotic procedures
    - Robotic approach by procedure type analysis
    """)

# 4. Volume-based Analysis


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