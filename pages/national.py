import streamlit as st

# Must be the first Streamlit command
st.set_page_config(
    page_title="National Overview - Navira",
    page_icon="🇫🇷",
    layout="wide"
)

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

# Add the parent directory to the Python path FIRST
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Now import from navira and local modules
from navira.competitor_layers import build_cp_to_insee
from navira.geojson_loader import load_communes_geojson_filtered, load_communes_geojson, detect_insee_key
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
    render_hospitals(df, procedure_details)






