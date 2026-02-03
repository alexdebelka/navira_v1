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
from navira.sections.overall_trends import render_overall_trends
from navira.sections.techniques import render_techniques
from navira.sections.robot import render_robot
from navira.sections.complication_national import render_complication_national
from navira.sections.hospitals import render_hospitals
handle_navigation_request()

# Identify this page early to avoid redirect loops for limited users
st.session_state.current_page = "national"

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
from navira.data_loader import get_all_dataframes, get_dataframes
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

# --- MAP DATA HELPERS ---
@st.cache_data(show_spinner=False)
def load_population_data():
    """Load and process the population data by department."""
    try:
        pop_df = pd.read_csv("data/DS_ESTIMATION_POPULATION (1).csv", sep=';')
        # Clean and process the data
        pop_df = pop_df[pop_df['GEO_OBJECT'] == 'DEP'].copy()  # Only departments
        pop_df = pop_df[pop_df['TIME_PERIOD'] == 2024].copy()  # Use 2024 data (was 2020 in comment but code says 2024?)
        # Double check, user file says 2020 usually, but let's stick to existing logic if it worked
        pop_df['dept_code'] = pop_df['GEO'].str.strip().str.replace('"', '')
        pop_df['population'] = pop_df['OBS_VALUE'].astype(int)
        return pop_df[['dept_code', 'population']]
    except Exception as e:
        st.error(f"Error loading population data: {e}")
        return pd.DataFrame()

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

# --- Page Title and Notice ---
st.title("🇫🇷 National Overview")

# --- CUSTOM CSS ---
st.markdown("""
    <style>
        .summary-card {
            background-color: #2b2b2b;
            border-radius: 15px;
            padding: 20px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
            margin-bottom: 20px;
            height: 100%;
        }
        .card-title {
            font-size: 1.1rem;
            font-weight: 600;
            margin-bottom: 15px;
            color: #e0e0e0;
            text-align: center;
        }
        .metric-value {
            font-size: 2rem;
            font-weight: 700;
            color: #ffffff;
            text-align: center;
        }
        .metric-label {
            font-size: 0.9rem;
            color: #a0a0a0;
            text-align: center;
        }
        .prediction-text {
            color: #ff4b4b;
            font-weight: bold;
        }
        .stat-box {
            background-color: #3b3b3b;
            border-radius: 8px;
            padding: 10px;
            text-align: center;
            margin-bottom: 10px;
            border: 1px solid rgba(255,255,255,0.1);
        }
        .ici-link {
            text-align: center;
            margin-top: 10px;
            font-size: 0.9em;
            color: #888;
        }
        .ici-link a {
            color: #00bfff;
            text-decoration: none;
        }
    </style>
""", unsafe_allow_html=True)

# --- SUMMARY SECTION ---
st.markdown('<div style="width:100%; text-align:right; margin-bottom:20px; font-size:2rem; font-weight:bold; text-decoration: underline; text-decoration-style: wavy; text-decoration-color: red;">Summary</div>', unsafe_allow_html=True)

# Row 1
col1, col2 = st.columns(2)

# Card 1: Monthly Surgeries (Placeholder)
with col1:
    with st.container():
        st.markdown("""
        <div class="summary-card">
            <div class="card-title">Monthly Surgeries with Rolling Statistics</div>
            <div style="height: 300px; display: flex; align-items: center; justify-content: center; background: #333; border-radius: 8px; border: 1px dashed #555;">
                <span style="color: #888;">Graph Placeholder</span>
            </div>
            <div class="ici-link">Bien plus de détails sur <b>les tendances</b> -> <span style="color: #00bfff; cursor: pointer;">ici</span></div>
        </div>
        """, unsafe_allow_html=True)

# Card 2: Intervention Types
with col2:
    with st.container():
        # Load the CSV data
        try:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            # Load Activity Data
            csv_path = os.path.join(base_dir, "new_data", "ACTIVITY", "TAB_TCN_NATL_YEAR.csv")
            df_activ = pd.read_csv(csv_path)

            # Filter for 2021-2024
            df_activ = df_activ[df_activ['annee'].isin([2021, 2022, 2023, 2024])]
            
            # Calculate totals and ratios from filtered data
            total_procs = df_activ['n'].sum()
            
            # Group by procedure type to get totals
            totals_by_proc = df_activ.groupby('baria_t')['n'].sum()

            sleeve_n = totals_by_proc.get('SLE', 0)
            bypass_n = totals_by_proc.get('BPG', 0)
            
            sleeve_pct = (sleeve_n / total_procs * 100) if total_procs > 0 else 0
            bypass_pct = (bypass_n / total_procs * 100) if total_procs > 0 else 0
            
            # Others: Total - (Sleeve + Bypass)
            others_n = total_procs - sleeve_n - bypass_n
            other_pct = (others_n / total_procs * 100) if total_procs > 0 else 0

            # Load Trend Data for Prediction
            trend_csv_path = os.path.join(base_dir, "new_data", "ACTIVITY", "TAB_TREND_NATL.csv")
            diff_pct_val = 0
            if os.path.exists(trend_csv_path):
                df_trend = pd.read_csv(trend_csv_path)
                diff_pct_val = df_trend['diff_pct'].iloc[0]
                prediction_text = f"{diff_pct_val:+.1f}%"
            else:
                prediction_text = "N/A"

            # Create Combined Figure (Stats + Donut)
            fig_combined = go.Figure()

            # Donut Chart (Right Side)
            labels = ['Gastric Bypass', 'Sleeve Gastrectomy', 'Other Procedures']
            values = [bypass_pct, sleeve_pct, other_pct]
            colors = ['#1f77b4', '#ff7f0e', '#2ca02c'] 
            
            fig_combined.add_trace(go.Pie(
                labels=labels, 
                values=values, 
                hole=.6,
                marker_colors=colors,
                textinfo='percent+label',
                showlegend=False,
                domain={'x': [0.5, 1], 'y': [0, 1]}
            ))

            # Stats Boxes (Left Side Annotations)
            # Box 1: Total Procedures
            fig_combined.add_annotation(
                x=0.06, y=0.88, xref="paper", yref="paper",
                text="Total procedures", showarrow=False,
                font=dict(color="#a0a0a0", size=12), xanchor="left"
            )
            fig_combined.add_annotation(
                x=0.06, y=0.79, xref="paper", yref="paper",
                text=f"{int(total_procs):,}", showarrow=False,
                font=dict(color="white", size=20, weight="bold"), xanchor="left"
            )

            # Box 2: Prediction
            pred_color = "#ff4b4b" if diff_pct_val < 0 else "#2ca02c"
            fig_combined.add_annotation(
                x=0.06, y=0.53, xref="paper", yref="paper",
                text="Prediction", showarrow=False,
                font=dict(color="#a0a0a0", size=12), xanchor="left"
            )
            fig_combined.add_annotation(
                x=0.06, y=0.44, xref="paper", yref="paper",
                text=prediction_text, showarrow=False,
                font=dict(color=pred_color, size=20, weight="bold"), xanchor="left"
            )

            # Box 3: Sleeve/Bypass
            fig_combined.add_annotation(
                x=0.06, y=0.18, xref="paper", yref="paper",
                text="Sleeve/Bypass", showarrow=False,
                font=dict(color="#a0a0a0", size=12), xanchor="left"
            )
            fig_combined.add_annotation(
                x=0.06, y=0.09, xref="paper", yref="paper",
                text=f"{sleeve_pct:.0f}%/{bypass_pct:.0f}%", showarrow=False,
                font=dict(color="white", size=16, weight="bold"), xanchor="left"
            )

            # Add Box Shapes
            box_style = dict(
                type="rect", xref="paper", yref="paper",
                fillcolor="rgba(255, 255, 255, 0.05)",
                line=dict(color="rgba(255, 255, 255, 0.1)", width=1),
                layer="below"
            )
            
            fig_combined.update_layout(
                shapes=[
                    # Box 1
                    dict(x0=0, x1=0.45, y0=0.72, y1=0.98, **box_style),
                    # Box 2
                    dict(x0=0, x1=0.45, y0=0.37, y1=0.63, **box_style),
                    # Box 3
                    dict(x0=0, x1=0.45, y0=0.02, y1=0.28, **box_style),
                ],
                margin=dict(t=10, b=10, l=10, r=10),
                height=250, # Increased height to fit boxes
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)'
            )
            
        except Exception as e:
            st.error(f"Error loading activity/trend data: {e}")
            fig_combined = go.Figure()

        st.markdown(f"""
        <div class="summary-card">
            <div class="card-title">Type d'intervention de chirurgie bariatrique (2021-2024)</div>
        """, unsafe_allow_html=True)
        
        st.plotly_chart(fig_combined, use_container_width=True, config={'displayModeBar': False})
        
        st.markdown("""
            <div class="ici-link">Analyse plus détaillée du type d'intervention bariatrique -> <span style="color: #00bfff; cursor: pointer;">ici</span></div>
        </div>
        """, unsafe_allow_html=True)

# Row 2
col3, col4 = st.columns(2)

# Card 3: MBS Robotic Rate
with col3:
    with st.container():
        # Load the CSV data for robotic rate
        try:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            rob_csv_path = os.path.join(base_dir, "new_data", "ACTIVITY", "TAB_APP_NATL_YEAR.csv")
            df_rob = pd.read_csv(rob_csv_path)

            # Filter for Robotic approach (ROB) and years 2021-2024
            df_rob = df_rob[(df_rob['vda'] == 'ROB') & (df_rob['annee'].isin([2021, 2022, 2023, 2024]))]
            
            # Sort by year just in case
            df_rob = df_rob.sort_values('annee')
            
            years = df_rob['annee'].tolist()
            rates = df_rob['pct'].tolist()
            
        except Exception as e:
            st.error(f"Error loading robotic data: {e}")
            years = []
            rates = []

        fig_rob = go.Figure()
        
        if years:
            fig_rob.add_trace(go.Bar(
                x=years,
                y=rates,
                text=[f"{r}%" for r in rates],
                textposition='outside', # Show text above data
                marker_color='#003366',
                name='Robotic Rate'
            ))
        
        fig_rob.update_layout(
            margin=dict(t=20, b=0, l=0, r=0),
            height=200,
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            xaxis=dict(
                showgrid=False, 
                type='category', # Treat years as categories so they are evenly spaced
                tickfont=dict(color='#888')
            ), 
            yaxis=dict(
                showgrid=False, # Clean look per reference
                visible=False,   # Hide y-axis if we have labels
                range=[0, max(rates)*1.2 if rates else 10] # Add headroom for labels
            ),
            showlegend=False
        )

        st.markdown("""
        <div class="summary-card">
            <div class="card-title" style="text-align:left; font-size:1rem;">MBS Robotic rate</div>
        """, unsafe_allow_html=True)
        st.plotly_chart(fig_rob, use_container_width=True, config={'displayModeBar': False})
        st.markdown("""
            <div class="ici-link">Bien plus de détails sur <b>l'activité robotique</b> -> <span style="color: #00bfff; cursor: pointer;">ici</span></div>
        </div>
        """, unsafe_allow_html=True)

# Card 4: Severe Complications
with col4:
    with st.container():
        # Load the CSV data for complications
        try:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            comp_csv_path = os.path.join(base_dir, "new_data", "COMPLICATIONS", "TAB_COMPL_GRADE_NATL_YEAR.csv")
            df_comp = pd.read_csv(comp_csv_path)

            # Filter for years 2021-2024 and Severe Complications (Grade >= 3)
            # The CSV has 'clav_cat_90' which seems to be the grade (3, 4, 5)
            df_comp = df_comp[
                (df_comp['annee'].isin([2021, 2022, 2023, 2024])) & 
                (df_comp['clav_cat_90'].isin([3, 4, 5]))
            ]
            
            # Group by year and sum the percentages (since they are parts of the total)
            yearly_severe = df_comp.groupby('annee')['COMPL_pct'].sum().reset_index()
            yearly_severe = yearly_severe.sort_values('annee')
            
            comp_years = yearly_severe['annee'].tolist()
            comp_rates = yearly_severe['COMPL_pct'].tolist()
            
        except Exception as e:
            st.error(f"Error loading complications data: {e}")
            comp_years = []
            comp_rates = []
        
        fig_comp = go.Figure()
        if comp_years:
             fig_comp.add_trace(go.Scatter(
                x=comp_years,
                y=comp_rates,
                mode='lines+markers+text',
                text=[f"{r:.1f}%" for r in comp_rates],
                textposition="top center",
                line=dict(color='#FF8C00', width=3),
                marker=dict(size=8),
                showlegend=False
            ))
        
        fig_comp.update_layout(
            margin=dict(t=20, b=0, l=0, r=0),
            height=200,
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            xaxis=dict(
                showgrid=False,
                type='category',
                tickfont=dict(color='#888')
            ), 
            yaxis=dict(
                showgrid=True, 
                gridcolor='rgba(255,255,255,0.1)', 
                range=[0, max(comp_rates)*1.3 if comp_rates else 5],
                tickfont=dict(color='#888')
            )
        )

        st.markdown("""
        <div class="summary-card">
            <div class="card-title">Taux de complications sévères à 90 jours après chirurgie bariatrique (estimation)</div>
        """, unsafe_allow_html=True)
        st.plotly_chart(fig_comp, use_container_width=True, config={'displayModeBar': False})
        st.markdown("""
            <div class="ici-link">Bien plus de détails sur <b>les complications</b> -> <span style="color: #00bfff; cursor: pointer;">ici</span></div>
        </div>
        """, unsafe_allow_html=True)

# Row 3
col5, col6 = st.columns(2)

# Card 5: Surgery Density Map
with col5:
    with st.container():
        st.header("Surgery Density by Department")
        st.markdown("*Ratio of total bariatric surgeries to department population (surgeries per 100,000 inhabitants)*")
        
        try:
            # Load the data using helpers defined at top
            population_data = load_population_data()
            surgery_data = calculate_surgery_by_department(df)
            
            if not population_data.empty and not surgery_data.empty:
                # Merge population and surgery data
                ratio_data = pd.merge(surgery_data, population_data, on='dept_code', how='inner')
                
                # Calculate ratio (surgeries per 100,000 inhabitants)
                ratio_data['surgery_ratio'] = (ratio_data['total_surgeries'] / ratio_data['population']) * 100000
                ratio_data['surgery_ratio'] = ratio_data['surgery_ratio'].round(1)
                
                # Create the choropleth map
                gj = _get_fr_departments_geojson()
                if gj and not ratio_data.empty:
                    m = folium.Map(location=[46.5, 2.5], zoom_start=5, tiles="CartoDB positron")
                    
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
                    
                    # Add GeoJSON layer
                    folium.GeoJson(
                        gj,
                        style_function=_style_fn,
                        tooltip=folium.Tooltip("Click for details"),
                        popup=None
                    ).add_to(m)
                    
                    # Display the map
                    st_folium(m, width="100%", height=400, key="surgery_population_ratio_choropleth_summary")
                else:
                    st.error("Could not load department GeoJSON for surgery ratio map.")
            else:
                 st.info("Data for map not available.")
                
        except Exception as e:
            st.error(f"Error creating surgery-to-population ratio map: {e}")

        st.markdown("""
            <div class="ici-link" style="text-align:left;">Distribution de <b>l'offre de soins</b> sur le territoire -> <span style="color: #00bfff; cursor: pointer;">ici</span></div>
        """, unsafe_allow_html=True)


# Card 6: Hospital Labels by Affiliation Type (Moved here)
with col6:
    with st.container():
        # Compute affiliation breakdown
        try:
             # Need to calculate it here
            affiliation_data = compute_affiliation_breakdown_2024(df)
            label_breakdown = affiliation_data['label_breakdown']
            
            # Prepare data for plotting
            categories = ['Public – Univ.', 'Public – Non-Acad.', 'Private – Not-for-profit', 'Private – For-profit']
            
            # Stack components
            soffco = [label_breakdown.get(cat, {}).get('SOFFCO Label', 0) for cat in categories]
            cso = [label_breakdown.get(cat, {}).get('CSO Label', 0) for cat in categories]
            both = [label_breakdown.get(cat, {}).get('Both', 0) for cat in categories]
            none = [label_breakdown.get(cat, {}).get('None', 0) for cat in categories]
            
            fig_aff = go.Figure()
            
            # Trace 1: SOFFCO Label (Green)
            fig_aff.add_trace(go.Bar(
                name='SOFFCO Label', x=categories, y=soffco, marker_color='#76D7C4'
            ))
            # Trace 2: CSO Label (Yellow)
            fig_aff.add_trace(go.Bar(
                name='CSO Label', x=categories, y=cso, marker_color='#F7DC6F'
            ))
            # Trace 3: Both (Blue)
            fig_aff.add_trace(go.Bar(
                name='Both', x=categories, y=both, marker_color='#00BFFF'
            ))
            # Trace 4: None (Red/Pink)
            fig_aff.add_trace(go.Bar(
                name='None', x=categories, y=none, marker_color='#F1948A'
            ))

            fig_aff.update_layout(
                barmode='stack',
                margin=dict(t=20, b=0, l=0, r=0),
                height=300,  # Slightly taller for this position
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                legend=dict(orientation="v", yanchor="top", y=1, xanchor="right", x=1.2, font=dict(size=9)),
                xaxis=dict(showgrid=False, tickfont=dict(size=10)),
                yaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.1)', title="Number of Hospitals")
            )

        except Exception as e:
            st.error(f"Error computing affiliation data: {e}")
            fig_aff = go.Figure()

        st.markdown("""
        <div class="summary-card">
            <div class="card-title">Hospital Labels by Affiliation Type</div>
        """, unsafe_allow_html=True)
        st.plotly_chart(fig_aff, use_container_width=True, config={'displayModeBar': False})
        st.markdown("""
            <div class="ici-link">Bien plus de détails sur <b>l'activité des hôpitaux</b> -> <span style="color: #00bfff; cursor: pointer;">ici</span></div>
        </div>
        """, unsafe_allow_html=True)



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

# Add tab styling CSS
st.markdown("""
    <style>
        /* Tab container */
        .stTabs [data-baseweb="tab-list"] {
            gap: 8px;
            background-color: rgba(50, 50, 50, 0.3);
            padding: 8px;
            border-radius: 10px;
        }
        
        /* Individual tabs  */
        .stTabs [data-baseweb="tab"] {
            height: 50px;
            background-color: rgba(80, 80, 80, 0.2);
            border-radius: 8px;
            padding-left: 20px;
            padding-right: 20px;
            color: #ffffff;
            font-size: 16px;
            font-weight: 500;
        }
        
        /* Active/selected tab */
        .stTabs [aria-selected="true"] {
            background-color: #1f77b4;
            font-weight: 600;
        }
        
        /* Hover effect */
        .stTabs [data-baseweb="tab"]:hover {
            background-color: rgba(31, 119, 180, 0.5);
        }
    </style>
""", unsafe_allow_html=True)

# Create tabs
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "Overall Trends", 
    "Techniques", 
    "Robot", 
    "Complication", 
    "Hospitals"
])

with tab1:
    render_overall_trends(df)

with tab2:
    render_techniques(df, national_averages)

with tab3:
    render_robot(df)

with tab4:
    render_complication_national(all_data)

with tab5:
    render_hospitals(procedure_details)






    """)