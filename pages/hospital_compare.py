# pages/hospital_compare.py
import streamlit as st
import pandas as pd
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
    page_title="Hospital Comparison",
    page_icon="⚖️",
    layout="wide"
)

# --- Cache Control ---
if st.button("♻️ Clear cache and reload"):
    try:
        st.cache_data.clear()
    except Exception:
        pass
    try:
        st.cache_resource.clear()
    except Exception:
        pass
    # Clear any session state that might cache data
    if 'hospital_compare_data' in st.session_state:
        del st.session_state['hospital_compare_data']
    st.success("Cache cleared! Page will reload...")
    st.rerun()

# Define color palettes for consistency (matching dashboard.py)
PROC_COLORS = {
    'Sleeve': '#ffae91',          # pink
    'Gastric Bypass': '#60a5fa',  # blue
    'Other': '#fbbf24'            # amber
}

APPROACH_COLORS = {
    'Robotic': '#FF7518',
    'Coelioscopy': '#50C878', 
    'Open Surgery': '#8e4585'
}

# Custom CSS for styling
st.markdown("""
<style>
.hospital-card {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    padding: 1.5rem;
    border-radius: 10px;
    color: white;
    margin: 0.5rem 0;
    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
}

.hospital-name {
    font-size: 1.5rem;
    font-weight: bold;
    margin-bottom: 0.5rem;
}

.hospital-details {
    font-size: 0.9rem;
    opacity: 0.9;
}

.comparison-header {
    text-align: center;
    font-size: 2rem;
    font-weight: bold;
    margin: 1rem 0;
    color: #2c3e50;
}

.vs-divider {
    text-align: center;
    font-size: 2rem;
    font-weight: bold;
    color: #e74c3c;
    margin: 1rem 0;
}

.metric-card {
    background: #f8f9fa;
    padding: 1rem;
    border-radius: 8px;
    border-left: 4px solid #3498db;
    margin: 0.5rem 0;
}

.nv-info-wrap {
    display: flex;
    align-items: center;
    gap: 8px;
    margin: 1rem 0 0.5rem 0;
}

.nv-h3 {
    font-size: 1.1rem;
    font-weight: 600;
    margin: 0;
    color: #2c3e50;
}

.nv-tooltip {
    position: relative;
    display: inline-block;
}

.nv-info-badge {
    background: #6c757d;
    color: white;
    border-radius: 50%;
    width: 18px;
    height: 18px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    font-size: 12px;
    font-weight: bold;
    cursor: help;
}

.nv-tooltip .nv-tooltiptext {
    visibility: hidden;
    width: 250px;
    background-color: #2c3e50;
    color: #fff;
    text-align: left;
    border-radius: 6px;
    padding: 8px;
    position: absolute;
    z-index: 1;
    bottom: 125%;
    left: 50%;
    margin-left: -125px;
    opacity: 0;
    transition: opacity 0.3s;
    font-size: 13px;
    line-height: 1.4;
}

.nv-tooltip:hover .nv-tooltiptext {
    visibility: visible;
    opacity: 1;
}
</style>
""", unsafe_allow_html=True)

# --- Load Data ---
@st.cache_data
def load_data():
    establishments, annual = get_dataframes()
    return establishments, annual

try:
    establishments, annual = load_data()
except Exception as e:
    st.error(f"Error loading data: {e}")
    st.stop()

# --- Page Title ---
st.title("⚖️ Hospital Comparison")
st.markdown("Compare two hospitals side-by-side across key metrics and performance indicators.")



# --- Hospital Selection ---
st.subheader("Select Hospitals to Compare")

# Get list of hospitals with procedure data
hospitals_with_data = annual['id'].unique()
hospital_names = []
hospital_mapping = {}

for hospital_id in hospitals_with_data:
    hospital_info = establishments[establishments['id'] == hospital_id]
    if not hospital_info.empty:
        name = hospital_info.iloc[0]['name']
        
        # Try multiple location fields to get the best location info
        location_parts = []
        
        # Debug: Check available columns (can remove later)
        available_cols = list(hospital_info.columns)
        
        # Check for city - try multiple possible column names
        city = None
        for city_col in ['city', 'ville']:
            if city_col in available_cols:
                city = hospital_info.iloc[0].get(city_col, '')
                if city and str(city).strip() and str(city).strip().lower() not in ['nan', 'none', '', 'null']:
                    location_parts.append(str(city).strip())
                    break
        
        # Check for region if city is not available - try multiple possible column names
        if not location_parts:
            for region_col in ['lib_reg', 'region', 'code_reg']:
                if region_col in available_cols:
                    region = hospital_info.iloc[0].get(region_col, '')
                    if region and str(region).strip() and str(region).strip().lower() not in ['nan', 'none', '', 'null']:
                        location_parts.append(str(region).strip())
                        break
        
        # Create display name
        if location_parts:
            display_name = f"{name} ({', '.join(location_parts)})"
        else:
            display_name = name
            
        hospital_names.append(display_name)
        hospital_mapping[display_name] = hospital_id

hospital_names.sort()

col1, col2 = st.columns(2)

with col1:
    st.markdown("**Hospital A**")
    hospital_a_name = st.selectbox(
        "Select first hospital:",
        options=hospital_names,
        key="hospital_a",
        index=0 if hospital_names else None
    )

with col2:
    st.markdown("**Hospital B**")
    hospital_b_name = st.selectbox(
        "Select second hospital:",
        options=hospital_names,
        key="hospital_b", 
        index=1 if len(hospital_names) > 1 else 0
    )

if not hospital_a_name or not hospital_b_name:
    st.warning("Please select two hospitals to compare.")
    st.stop()

hospital_a_id = hospital_mapping[hospital_a_name]
hospital_b_id = hospital_mapping[hospital_b_name]

if hospital_a_id == hospital_b_id:
    st.warning("Please select two different hospitals.")
    st.stop()

# --- Get Hospital Data ---
@st.cache_data
def get_hospital_data(hospital_id):
    # Get establishment info
    est_info = establishments[establishments['id'] == hospital_id].iloc[0]
    
    # Get annual data for this hospital
    hospital_annual = annual[annual['id'] == hospital_id].copy()
    

    
    return est_info, hospital_annual

hospital_a_info, hospital_a_data = get_hospital_data(hospital_a_id)
hospital_b_info, hospital_b_data = get_hospital_data(hospital_b_id)

# --- Display Hospital Cards ---
col1, col2, col3 = st.columns([5, 1, 5])

with col1:
    # Get better location info for hospital A
    location_parts_a = []
    
    # Check for city - try multiple possible column names
    for city_col in ['city', 'ville']:
        city_a = hospital_a_info.get(city_col, '')
        if city_a and str(city_a).strip() and str(city_a).strip().lower() not in ['nan', 'none', '', 'null']:
            location_parts_a.append(str(city_a).strip())
            break
    
    # Check for region if city is not available
    if not location_parts_a:
        for region_col in ['lib_reg', 'region', 'code_reg']:
            region_a = hospital_a_info.get(region_col, '')
            if region_a and str(region_a).strip() and str(region_a).strip().lower() not in ['nan', 'none', '', 'null']:
                location_parts_a.append(str(region_a).strip())
                break
    
    location_display_a = ', '.join(location_parts_a) if location_parts_a else 'Location not specified'
    
    st.markdown(f"""
    <div class="hospital-card">
        <div class="hospital-name">{hospital_a_info['name']}</div>
        <div class="hospital-details">
            📍 {location_display_a}<br>
            🏥 {hospital_a_info.get('statut', 'Unknown').title()}<br>
            🎓 {'Academic' if hospital_a_info.get('academic_affiliation', 0) == 1 else 'Non-Academic'}
        </div>
    </div>
    """, unsafe_allow_html=True)

with col2:
    st.markdown('<div class="vs-divider">VS</div>', unsafe_allow_html=True)

with col3:
    # Get better location info for hospital B
    location_parts_b = []
    
    # Check for city - try multiple possible column names
    for city_col in ['city', 'ville']:
        city_b = hospital_b_info.get(city_col, '')
        if city_b and str(city_b).strip() and str(city_b).strip().lower() not in ['nan', 'none', '', 'null']:
            location_parts_b.append(str(city_b).strip())
            break
    
    # Check for region if city is not available
    if not location_parts_b:
        for region_col in ['lib_reg', 'region', 'code_reg']:
            region_b = hospital_b_info.get(region_col, '')
            if region_b and str(region_b).strip() and str(region_b).strip().lower() not in ['nan', 'none', '', 'null']:
                location_parts_b.append(str(region_b).strip())
                break
    
    location_display_b = ', '.join(location_parts_b) if location_parts_b else 'Location not specified'
    
    st.markdown(f"""
    <div class="hospital-card">
        <div class="hospital-name">{hospital_b_info['name']}</div>
        <div class="hospital-details">
            📍 {location_display_b}<br>
            🏥 {hospital_b_info.get('statut', 'Unknown').title()}<br>
            🎓 {'Academic' if hospital_b_info.get('academic_affiliation', 0) == 1 else 'Non-Academic'}
        </div>
    </div>
    """, unsafe_allow_html=True)

# --- Comparison Metrics ---
st.header("📊 Key Metrics Comparison")

# Calculate metrics for both hospitals
def calculate_metrics(hospital_data):
    if hospital_data.empty:
        return {
            'total_procedures_2024': 0,
            'avg_procedures_per_year': 0,
            'years_active': 0,
            'robotic_percentage_2024': 0,
            'sleeve_percentage_2024': 0
        }
    
    # Check required columns exist
    if 'annee' not in hospital_data.columns or 'total_procedures_year' not in hospital_data.columns:
        return {
            'total_procedures_2024': 0,
            'avg_procedures_per_year': 0,
            'years_active': 0,
            'robotic_percentage_2024': 0,
            'sleeve_percentage_2024': 0
        }
    
    # 2024 data
    data_2024 = hospital_data[hospital_data['annee'] == 2024]
    total_2024 = data_2024['total_procedures_year'].sum() if not data_2024.empty else 0
    
    # Average across all years
    avg_procedures = hospital_data['total_procedures_year'].mean()
    years_active = len(hospital_data['annee'].unique())
    
    # Robotic percentage in 2024
    if not data_2024.empty and 'ROB' in data_2024.columns and total_2024 > 0:
        robotic_2024 = data_2024['ROB'].sum()
        robotic_pct = (robotic_2024 / total_2024 * 100) if not pd.isna(robotic_2024) else 0
    else:
        robotic_pct = 0
    
    # Sleeve percentage in 2024
    if not data_2024.empty and 'SLE' in data_2024.columns and total_2024 > 0:
        sleeve_2024 = data_2024['SLE'].sum()
        sleeve_pct = (sleeve_2024 / total_2024 * 100) if not pd.isna(sleeve_2024) else 0
    else:
        sleeve_pct = 0
    
    return {
        'total_procedures_2024': int(total_2024) if not pd.isna(total_2024) else 0,
        'avg_procedures_per_year': int(avg_procedures) if not pd.isna(avg_procedures) else 0,
        'years_active': years_active,
        'robotic_percentage_2024': round(robotic_pct, 1),
        'sleeve_percentage_2024': round(sleeve_pct, 1)
    }

metrics_a = calculate_metrics(hospital_a_data)
metrics_b = calculate_metrics(hospital_b_data)

# Display metrics in columns
col1, col2 = st.columns(2)

with col1:
    st.subheader(f"🏥 {hospital_a_info['name']}")
    st.metric("Total Procedures (2024)", f"{metrics_a['total_procedures_2024']:,}")
    st.metric("Avg Procedures/Year", f"{metrics_a['avg_procedures_per_year']:,}")
    st.metric("Years Active", metrics_a['years_active'])
    st.metric("Robotic Surgery % (2024)", f"{metrics_a['robotic_percentage_2024']}%")
    st.metric("Sleeve Gastrectomy % (2024)", f"{metrics_a['sleeve_percentage_2024']}%")

with col2:
    st.subheader(f"🏥 {hospital_b_info['name']}")
    st.metric("Total Procedures (2024)", f"{metrics_b['total_procedures_2024']:,}")
    st.metric("Avg Procedures/Year", f"{metrics_b['avg_procedures_per_year']:,}")
    st.metric("Years Active", metrics_b['years_active'])
    st.metric("Robotic Surgery % (2024)", f"{metrics_b['robotic_percentage_2024']}%")
    st.metric("Sleeve Gastrectomy % (2024)", f"{metrics_b['sleeve_percentage_2024']}%")

# --- Volume Trends Comparison ---
st.header("📈 Volume Trends Over Time")

st.markdown(
    """
    <div class="nv-info-wrap">
      <div class="nv-h3">Total Surgeries Comparison (2020-2024)</div>
      <div class="nv-tooltip"><span class="nv-info-badge">i</span>
        <div class="nv-tooltiptext">
          <b>Understanding this chart:</b><br/>
          Shows annual procedure volumes for both hospitals, allowing you to compare growth patterns and overall volume.
        </div>
      </div>
    </div>
    """,
    unsafe_allow_html=True
)

# Create volume comparison chart
volume_data = []
# Check if required columns exist for both hospitals
if ('annee' in hospital_a_data.columns and 'total_procedures_year' in hospital_a_data.columns and
    'annee' in hospital_b_data.columns and 'total_procedures_year' in hospital_b_data.columns):
    
    for year in range(2020, 2025):
        # Hospital A
        data_a_year = hospital_a_data[hospital_a_data['annee'] == year]
        volume_a = data_a_year['total_procedures_year'].sum() if not data_a_year.empty else 0
        volume_a = int(volume_a) if not pd.isna(volume_a) else 0
        volume_data.append({'Year': year, 'Hospital': hospital_a_info['name'], 'Volume': volume_a})
        
        # Hospital B  
        data_b_year = hospital_b_data[hospital_b_data['annee'] == year]
        volume_b = data_b_year['total_procedures_year'].sum() if not data_b_year.empty else 0
        volume_b = int(volume_b) if not pd.isna(volume_b) else 0
        volume_data.append({'Year': year, 'Hospital': hospital_b_info['name'], 'Volume': volume_b})

volume_df = pd.DataFrame(volume_data)

if not volume_df.empty and volume_df['Volume'].sum() > 0:
    fig_volume = px.line(
        volume_df,
        x='Year',
        y='Volume', 
        color='Hospital',
        title='Annual Procedure Volume Comparison',
        markers=True,
        color_discrete_sequence=['#3498db', '#e74c3c']  # Bright blue and red
    )
    fig_volume.update_layout(
        height=400,
        xaxis_title='Year',
        yaxis_title='Total Procedures',
        hovermode='x unified',
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        title_font_color='white',
        font=dict(color='white'),
        xaxis=dict(gridcolor='rgba(255,255,255,0.1)'),
        yaxis=dict(gridcolor='rgba(255,255,255,0.1)')
    )
    fig_volume.update_traces(
        hovertemplate='<b>%{fullData.name}</b><br>Year: %{x}<br>Volume: %{y:,}<extra></extra>'
    )
    st.plotly_chart(fig_volume, use_container_width=True)
else:
    st.warning("📊 No volume data available for comparison. This may be due to:")
    st.markdown("""
    - Missing data for the selected time period
    - Hospitals not meeting minimum procedure thresholds  
    - Data availability issues
    
    *Try selecting different hospitals or check back later.*
    """)

# --- Procedure Mix Comparison ---
st.header("🔬 Procedure Mix Comparison (2024)")

st.markdown(
    """
    <div class="nv-info-wrap">
      <div class="nv-h3">Bariatric Procedure Distribution</div>
      <div class="nv-tooltip"><span class="nv-info-badge">i</span>
        <div class="nv-tooltiptext">
          <b>Understanding this chart:</b><br/>
          Compare the types of bariatric procedures performed at each hospital in 2024.
        </div>
      </div>
    </div>
    """,
    unsafe_allow_html=True
)

# Calculate procedure mix for 2024
def get_procedure_mix_2024(hospital_data):
    data_2024 = hospital_data[hospital_data['annee'] == 2024]
    if data_2024.empty:
        return {}
    
    procedure_codes = {'SLE': 'Sleeve', 'BPG': 'Gastric Bypass'}
    mix = {}
    
    # Check if total_procedures_year exists
    if 'total_procedures_year' not in data_2024.columns:
        return {}
        
    total = data_2024['total_procedures_year'].sum()
    if total <= 0:
        return {}
    
    for code, name in procedure_codes.items():
        if code in data_2024.columns:
            count = data_2024[code].sum()
            mix[name] = int(count) if not pd.isna(count) else 0
        else:
            mix[name] = 0
    
    # Calculate "Other" as the remaining procedures
    accounted = sum(mix.values())
    other_count = max(0, int(total) - accounted)
    mix['Other'] = other_count
    
    return mix

mix_a = get_procedure_mix_2024(hospital_a_data)
mix_b = get_procedure_mix_2024(hospital_b_data)

col1, col2 = st.columns(2)

# Hospital A procedure mix
with col1:
    if mix_a and sum(mix_a.values()) > 0:
        mix_a_df = pd.DataFrame(list(mix_a.items()), columns=['Procedure', 'Count'])
        mix_a_df = mix_a_df[mix_a_df['Count'] > 0]
        
        fig_a = px.pie(
            mix_a_df,
            values='Count',
            names='Procedure',
            title=f"{hospital_a_info['name']} (2024)",
            color='Procedure',
            color_discrete_map=PROC_COLORS
        )
        fig_a.update_traces(textposition='inside', textinfo='percent+label')
        fig_a.update_layout(
            height=400, 
            plot_bgcolor='rgba(0,0,0,0)', 
            paper_bgcolor='rgba(0,0,0,0)',
            title_font_color='white'
        )
        st.plotly_chart(fig_a, use_container_width=True)
    else:
        st.info("🔬 No procedure breakdown available for 2024")
        if not hospital_a_data.empty:
            st.caption("Hospital has data but no detailed procedure breakdown for this year.")

# Hospital B procedure mix  
with col2:
    if mix_b and sum(mix_b.values()) > 0:
        mix_b_df = pd.DataFrame(list(mix_b.items()), columns=['Procedure', 'Count'])
        mix_b_df = mix_b_df[mix_b_df['Count'] > 0]
        
        fig_b = px.pie(
            mix_b_df,
            values='Count',
            names='Procedure', 
            title=f"{hospital_b_info['name']} (2024)",
            color='Procedure',
            color_discrete_map=PROC_COLORS
        )
        fig_b.update_traces(textposition='inside', textinfo='percent+label')
        fig_b.update_layout(
            height=400, 
            plot_bgcolor='rgba(0,0,0,0)', 
            paper_bgcolor='rgba(0,0,0,0)',
            title_font_color='white'
        )
        st.plotly_chart(fig_b, use_container_width=True)
    else:
        st.info("🔬 No procedure breakdown available for 2024")
        if not hospital_b_data.empty:
            st.caption("Hospital has data but no detailed procedure breakdown for this year.")

# --- Surgical Approach Comparison ---
st.header("🔧 Surgical Approach Comparison (2024)")

st.markdown(
    """
    <div class="nv-info-wrap">
      <div class="nv-h3">Surgical Approach Distribution</div>
      <div class="nv-tooltip"><span class="nv-info-badge">i</span>
        <div class="nv-tooltiptext">
          <b>Understanding this chart:</b><br/>
          Compare surgical approaches (Robotic, Coelioscopy, Open Surgery) used at each hospital in 2024.
        </div>
      </div>
    </div>
    """,
    unsafe_allow_html=True
)

def get_approach_mix_2024(hospital_data):
    data_2024 = hospital_data[hospital_data['annee'] == 2024]
    if data_2024.empty:
        return {}
    
    approach_codes = {'ROB': 'Robotic', 'COE': 'Coelioscopy', 'OUV': 'Open Surgery'}
    mix = {}
    
    for code, name in approach_codes.items():
        if code in data_2024.columns:
            count = data_2024[code].sum()
            mix[name] = int(count) if not pd.isna(count) else 0
        else:
            mix[name] = 0
    
    # If all approaches are 0, try to get total and distribute it
    total_approaches = sum(mix.values())
    if total_approaches == 0 and 'total_procedures_year' in data_2024.columns:
        total_proc = data_2024['total_procedures_year'].sum()
        if total_proc > 0:
            # If we have total procedures but no approach breakdown, show as "Other"
            mix['Open Surgery'] = int(total_proc)  # Default to open surgery
    
    return mix

approach_a = get_approach_mix_2024(hospital_a_data)
approach_b = get_approach_mix_2024(hospital_b_data)

col1, col2 = st.columns(2)

# Hospital A approach mix
with col1:
    if approach_a and sum(approach_a.values()) > 0:
        approach_a_df = pd.DataFrame(list(approach_a.items()), columns=['Approach', 'Count'])
        approach_a_df = approach_a_df[approach_a_df['Count'] > 0]
        
        fig_a_app = px.pie(
            approach_a_df,
            values='Count',
            names='Approach',
            title=f"{hospital_a_info['name']} (2024)",
            color='Approach',
            color_discrete_map=APPROACH_COLORS
        )
        fig_a_app.update_traces(textposition='inside', textinfo='percent+label')
        fig_a_app.update_layout(
            height=400, 
            plot_bgcolor='rgba(0,0,0,0)', 
            paper_bgcolor='rgba(0,0,0,0)',
            title_font_color='white'
        )
        st.plotly_chart(fig_a_app, use_container_width=True)
    else:
        st.info("🔧 No surgical approach breakdown available for 2024")
        if not hospital_a_data.empty:
            st.caption("Hospital has data but no detailed approach breakdown for this year.")

# Hospital B approach mix
with col2:
    if approach_b and sum(approach_b.values()) > 0:
        approach_b_df = pd.DataFrame(list(approach_b.items()), columns=['Approach', 'Count'])
        approach_b_df = approach_b_df[approach_b_df['Count'] > 0]
        
        fig_b_app = px.pie(
            approach_b_df,
            values='Count',
            names='Approach',
            title=f"{hospital_b_info['name']} (2024)",
            color='Approach',
            color_discrete_map=APPROACH_COLORS
        )
        fig_b_app.update_traces(textposition='inside', textinfo='percent+label')
        fig_b_app.update_layout(
            height=400, 
            plot_bgcolor='rgba(0,0,0,0)', 
            paper_bgcolor='rgba(0,0,0,0)',
            title_font_color='white'
        )
        st.plotly_chart(fig_b_app, use_container_width=True)
    else:
        st.info("🔧 No surgical approach breakdown available for 2024")
        if not hospital_b_data.empty:
            st.caption("Hospital has data but no detailed approach breakdown for this year.")

# --- Summary Insights ---
st.header("💡 Key Insights")

with st.expander("Comparison Summary"):
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown(f"**{hospital_a_info['name']}**")
        st.markdown(f"- **Volume**: {metrics_a['total_procedures_2024']:,} procedures in 2024")
        st.markdown(f"- **Robotic adoption**: {metrics_a['robotic_percentage_2024']}%")
        st.markdown(f"- **Primary procedure**: {max(mix_a.items(), key=lambda x: x[1])[0] if mix_a else 'Unknown'}")
        st.markdown(f"- **Experience**: {metrics_a['years_active']} years in dataset")
    
    with col2:
        st.markdown(f"**{hospital_b_info['name']}**")
        st.markdown(f"- **Volume**: {metrics_b['total_procedures_2024']:,} procedures in 2024")
        st.markdown(f"- **Robotic adoption**: {metrics_b['robotic_percentage_2024']}%")
        st.markdown(f"- **Primary procedure**: {max(mix_b.items(), key=lambda x: x[1])[0] if mix_b else 'Unknown'}")
        st.markdown(f"- **Experience**: {metrics_b['years_active']} years in dataset")

st.caption("Data reflects eligible hospital-years with ≥25 procedures per year.")
