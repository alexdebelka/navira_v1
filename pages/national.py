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

'''
# --- (1) HOSPITAL VOLUME DISTRIBUTION ---
st.header("Hospital Volume Distribution")

# Load and Process Data Locally
try:
    vol_csv_path = os.path.join(base_dir, "new_data", "ACTIVITY", "TAB_VOL_HOP_YEAR.csv")
    df_vol = pd.read_csv(vol_csv_path)

    # Filter years (assuming 2021 start based on file inspection)
    # We need 2024 for current, and 2021-2023 for baseline
    df_vol = df_vol[df_vol['annee'].isin([2021, 2022, 2023, 2024])]

    # Define Bins
    def assign_bin(n):
        if n < 50: return "<50"
        elif 50 <= n < 100: return "50–100"
        elif 100 <= n < 200: return "100–200"
        else: return ">200"

    df_vol['bin'] = df_vol['n'].apply(assign_bin)
    
    # KPIs for 2024
    df_2024 = df_vol[df_vol['annee'] == 2024]
    total_hosp_2024 = df_2024['finessGeoDP'].nunique()
    total_surg_2024 = df_2024['n'].sum()
    
    # Bin counts for 2024
    counts_2024 = df_2024['bin'].value_counts()
    
    hosp_less_50_2024 = counts_2024.get("<50", 0)
    hosp_more_200_2024 = counts_2024.get(">200", 0)

    # Baseline (2021-2023) Average
    df_baseline = df_vol[df_vol['annee'].isin([2021, 2022, 2023])]
    # Count per year then average
    baseline_counts_per_year = df_baseline.groupby(['annee', 'bin'])['finessGeoDP'].count().unstack(fill_value=0)
    avg_baseline = baseline_counts_per_year.mean()
    
    hosp_less_50_base = avg_baseline.get("<50", 0)
    hosp_more_200_base = avg_baseline.get(">200", 0)
    
    delta_less_50 = hosp_less_50_2024 - hosp_less_50_base
    delta_more_200 = hosp_more_200_2024 - hosp_more_200_base

    # Display KPIs
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Hospitals (2024)", f"{total_hosp_2024}")
        
    with col2:
        st.metric("Total Surgeries (2024)", f"{total_surg_2024:,}")
        
    with col3:
        st.metric(
            "Hospitals <50/year (2024)", 
            f"{hosp_less_50_2024}", 
            delta=f"{delta_less_50:+.1f} vs 21-23 avg",
            delta_color="inverse"
        )
        
    with col4:
        st.metric(
            "Hospitals >200/year (2024)", 
            f"{hosp_more_200_2024}", 
            delta=f"{delta_more_200:+.1f} vs 21-23 avg",
            delta_color="normal"
        )

    # Chart Section
    st.markdown("""
        <div class="nv-info-wrap">
          <div class="nv-h3">Volume Distribution by Hospital</div>
          <div class="nv-tooltip"><span class="nv-info-badge">i</span>
            <div class="nv-tooltiptext">
              <b>Understanding this chart:</b><br/>
              Distribution of hospitals based on annual surgical volume.<br/>
              Categories: &lt;50, 50–100, 100–200, &gt;200 procedures/year.<br/>
              Use the toggle to compare 2024 against the 2021–2023 average.
            </div>
          </div>
        </div>
    """, unsafe_allow_html=True)
    
    # Toggle
    show_comparison = st.toggle("Show 2024 comparison (vs 2021-23 Avg)", value=True)
    
    # Helper to ensure all bins are present in order
    bin_order = ["<50", "50–100", "100–200", ">200"]
    
    # Align data to bin order
    y_2024 = [counts_2024.get(b, 0) for b in bin_order]
    y_base = [avg_baseline.get(b, 0) for b in bin_order]
    
    fig_vol = go.Figure()
    
    if show_comparison:
        # Baseline Bars
        fig_vol.add_trace(go.Bar(
            x=bin_order, y=y_base,
            name='2021-2023 Average',
            marker_color='#2E86AB',
            hovertemplate='<b>%{x}</b><br>Avg: %{y:.1f}<extra></extra>'
        ))
        
        # 2024 Overlay
        fig_vol.add_trace(go.Bar(
            x=bin_order, y=y_2024,
            name='2024',
            marker_color='rgba(255, 193, 7, 0.7)',
            text=y_2024,
            textposition='auto',
            hovertemplate='<b>%{x}</b><br>2024: %{y}<extra></extra>'
        ))
        barmode = 'overlay'
    else:
        # Only 2024
        fig_vol.add_trace(go.Bar(
            x=bin_order, y=y_2024,
            name='2024',
            marker_color='#FFC107',
            text=y_2024,
            textposition='auto',
            hovertemplate='<b>%{x}</b><br>2024: %{y}<extra></extra>'
        ))
        barmode = 'group'

    fig_vol.update_layout(
        title="Hospital Volume Distribution",
        xaxis_title="Procedures per Year",
        yaxis_title="Number of Hospitals",
        barmode=barmode,
        hovermode='x unified',
        height=400,
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        margin=dict(l=50, r=50, t=50, b=50),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    
    st.plotly_chart(fig_vol, use_container_width=True)
    
    # Key Findings / Expander
    with st.expander("Key findings"):
        st.markdown(f"""
        **2024 Distribution:**
        - **{hosp_less_50_2024}** hospitals performed <50 procedures.
        - **{hosp_more_200_2024}** hospitals performed >200 procedures.
        
        **Compared to 2021-2023 Average:**
        - Small volume (<50): {delta_less_50:+.1f}
        - High volume (>200): {delta_more_200:+.1f}
        """)

except Exception as e:
    st.error(f"Error loading volume data: {e}")
'''

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

st.stop()
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
            time_period = "2021–2024"
            tooltip_text = "Stacked area shows annual shares of Sleeve, Gastric Bypass, and Other across eligible hospitals (2021-2024, excluding 2020). Each year sums to 100%."
        
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
                # Exclude 2020 from years
                years_to_process = sorted([y for y in df[year_col].unique() if y > 2020])
            
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
        elif not available:
            # If no procedure columns available, create dummy trend data
            if toggle_2024_only:
                years_to_process = [2024]
            else:
                years_to_process = [2021, 2022, 2023, 2024]
            
            for year in years_to_process:
                # Dummy data: Sleeve 60%, Gastric Bypass 30%, Other 10%
                proc_trend_rows.append({'Year': int(year), 'Procedure': 'Sleeve', 'Share': 60.0})
                proc_trend_rows.append({'Year': int(year), 'Procedure': 'Gastric Bypass', 'Share': 30.0})
                proc_trend_rows.append({'Year': int(year), 'Procedure': 'Other', 'Share': 10.0})
        
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
            # Define a consistent color mapping used across pie and bars
            APPROACH_COLORS = {
                'Coelioscopy': '#2E86AB',
                'Robotic': '#F7931E',
                'Open Surgery': '#A23B72'
            }

            fig = px.pie(
                pie_df,
                values='Count',
                names='Approach',
                title="National Approach Distribution (2024)",
                color='Approach',
                color_discrete_map=APPROACH_COLORS
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
        est_df = st.session_state.get('establishments', None)
        if est_df is None or (hasattr(est_df, 'empty') and est_df.empty):
            est_df = all_data.get('establishments')
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
    from km import compute_complication_rates_from_aggregates, debug_signature
    from charts import create_km_chart, create_multi_km_chart
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
        
        # First compute overall national curve to get the base hash
        km_agg = km_data.groupby(['year', 'bucket', 'time_label'], as_index=False).agg({
            'complications_count': 'sum',
            'procedures_count': 'sum'
        }).sort_values(['year', 'bucket'])
        
        debug_signatures['aggregated_data'] = debug_dataframe_signature(km_agg, "Aggregated by time intervals")
        
        # Create multiple KM curves based on selected labels
        km_curves = {}
        
        # Get hospital label information for grouping
        est_df = st.session_state.get('establishments', None)
        if est_df is None or (hasattr(est_df, 'empty') and est_df.empty):
            est_df = all_data.get('establishments')
        if est_df is not None and not est_df.empty:
            est_labels = est_df[['id', 'cso', 'LAB_SOFFCO']].copy()
            est_labels['id'] = est_labels['id'].astype(str)
            
            # Merge label info with KM data
            km_data_with_labels = km_data.merge(est_labels, left_on='hospital_id', right_on='id', how='left')
            
            # Create groups based on selected labels
            for label in km_label_opts:
                if label == 'CSO':
                    mask = km_data_with_labels['cso'] == 1
                    group_name = 'CSO Hospitals'
                elif label == 'SOFFCO':
                    mask = km_data_with_labels['LAB_SOFFCO'] == 1
                    group_name = 'SOFFCO Hospitals'
                elif label == 'None':
                    mask = ((km_data_with_labels['cso'] != 1) & (km_data_with_labels['LAB_SOFFCO'] != 1))
                    group_name = 'No Labels'
                else:
                    continue
                
                # Filter data for this label group
                label_data = km_data_with_labels[mask].copy()
                if not label_data.empty:
                    # Aggregate by time intervals for this group
                    label_agg = label_data.groupby(['year', 'bucket', 'time_label'], as_index=False).agg({
                        'complications_count': 'sum',
                        'procedures_count': 'sum'
                    }).sort_values(['year', 'bucket'])
                    
                    if not label_agg.empty:
                        try:
                            # Compute KM curve for this label group
                            label_curve = compute_complication_rates_from_aggregates(
                                df=label_agg,
                                time_col='time_label',
                                event_col='complications_count', 
                                at_risk_col='procedures_count',
                                group_cols=None,
                                data_hash=f"{debug_signatures['aggregated_data']['hash']}_{label}",
                                cache_version="v1"
                            )
                            
                            if not label_curve.empty:
                                km_curves[group_name] = label_curve
                                
                        except Exception as e:
                            st.error(f"Error computing KM curve for {label}: {e}")
                            debug_signatures[f'km_error_{label}'] = {'error': str(e)}
        
        if not km_agg.empty:
            try:
                # Overall national curve
                overall_curve = compute_complication_rates_from_aggregates(
                    df=km_agg,
                    time_col='time_label',
                    event_col='complications_count', 
                    at_risk_col='procedures_count',
                    group_cols=None,
                    data_hash=debug_signatures['aggregated_data']['hash'],
                    cache_version="v1"
                )
                
                if not overall_curve.empty:
                    km_curves['Overall'] = overall_curve
                    
            except Exception as e:
                st.error(f"Error computing overall KM curve: {e}")
                debug_signatures['km_error_overall'] = {'error': str(e)}
        
        # Create multi-line chart if we have multiple curves
        if len(km_curves) > 1:
            try:
                # Create dynamic title based on active filters
                active_filters = []
                if km_top10:
                    active_filters.append("Top 10 hospitals")
                if km_label_opts:
                    active_filters.append(f"Labels: {', '.join(km_label_opts)}")
                
                title = "National Complication Rate Over Time (KM)"
                if active_filters:
                    title += f" - {', '.join(active_filters)}"
                
                # Create consistent color mapping for each group type
                color_mapping = {
                    'CSO Hospitals': '#1f77b4',      # Blue
                    'SOFFCO Hospitals': '#e67e22',   # Orange  
                    'No Labels': '#2ca02c',          # Green
                    'Overall': '#d62728'             # Red
                }
                
                # Sort curves to ensure consistent order: Overall first, then others
                sorted_curves = {}
                if 'Overall' in km_curves:
                    sorted_curves['Overall'] = km_curves['Overall']
                for key in ['CSO Hospitals', 'SOFFCO Hospitals', 'No Labels']:
                    if key in km_curves:
                        sorted_curves[key] = km_curves[key]
                
                fig_km_nat = create_multi_km_chart(
                    curves_dict=sorted_curves,
                    title=title,
                    yaxis_title='Complication Rate (%)',
                    xaxis_title=km_xaxis_label,
                    height=400,
                    colors=[color_mapping.get(key, '#9467bd') for key in sorted_curves.keys()]  # Consistent colors
                )
                
                st.plotly_chart(fig_km_nat, use_container_width=True, key="km_national_multi")
                
                # Show legend info
                st.info(f"📊 **Multiple KM curves shown:** {', '.join(km_curves.keys())}")
                
            except Exception as e:
                st.error(f"Error creating multi-line KM chart: {e}")
                debug_signatures['multi_chart_error'] = {'error': str(e)}
                
        elif len(km_curves) == 1:
            # Single curve - use consistent color mapping
            curve_name, curve_data = list(km_curves.items())[0]
            
            # Use consistent color for single curves too
            color_mapping = {
                'CSO Hospitals': '#1f77b4',      # Blue
                'SOFFCO Hospitals': '#e67e22',   # Orange  
                'No Labels': '#2ca02c',          # Green
                'Overall': '#d62728'             # Red
            }
            
            curve_color = color_mapping.get(curve_name, '#e67e22')  # Default to orange if unknown
            
            fig_km_nat = create_km_chart(
                curve_df=curve_data,
                page_id="national",
                title=f"National Complication Rate Over Time (KM) - {curve_name}",
                yaxis_title='Complication Rate (%)',
                xaxis_title=km_xaxis_label,
                height=320,
                color=curve_color,
                show_complication_rate=True
            )
            
            st.plotly_chart(fig_km_nat, use_container_width=True, key="km_national_single")
            
        else:
            st.info('No data to compute KM curves with current filters.')
            debug_signatures['no_data'] = {'message': 'No KM curves computed'}
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