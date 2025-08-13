import streamlit as st
import pandas as pd
import altair as alt
from streamlit_option_menu import option_menu

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

# --- MAPPING DICTIONARIES (keep consistent with main.py) ---
BARIATRIC_PROCEDURE_NAMES = {
    'SLE': 'Sleeve Gastrectomy', 'BPG': 'Gastric Bypass', 'ANN': 'Gastric Banding',
    'REV': 'Other', 'ABL': 'Band Removal'
}
SURGICAL_APPROACH_NAMES = {
    'LAP': 'Open Surgery', 'COE': 'Coelioscopy', 'ROB': 'Robotic'
}

# --- Load Data Fallback ---
@st.cache_data
def load_data(path="data/flattened_v3.csv"):
    try:
        df = pd.read_csv(path)
        df.rename(columns={
            'id': 'ID', 'rs': 'Hospital Name', 'statut': 'Status', 'ville': 'City',
            'revision_surgeries_n': 'Revision Surgeries (N)', 'revision_surgeries_pct': 'Revision Surgeries (%)'
        }, inplace=True)
        df['Status'] = df['Status'].astype(str).str.strip().str.lower()
        status_mapping = {'private not-for-profit': 'private-non-profit', 'public': 'public', 'private for profit': 'private-for-profit'}
        df['Status'] = df['Status'].map(status_mapping)
        numeric_cols = [
            'Revision Surgeries (N)', 'total_procedures_period', 'annee', 'total_procedures_year',
            'university', 'cso', 'LAB_SOFFCO', 'latitude', 'longitude', 'Revision Surgeries (%)'
        ] + list(BARIATRIC_PROCEDURE_NAMES.keys()) + list(SURGICAL_APPROACH_NAMES.keys())
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        df.dropna(subset=['latitude', 'longitude'], inplace=True)
        df = df[df['latitude'].between(-90, 90) & df['longitude'].between(-180, 180)]
        return df
    except FileNotFoundError:
        st.error(f"Fatal Error: Data file '{path}' not found.")
        st.stop()

# --- National averages computation (reuse from session if available) ---
@st.cache_data
def calculate_national_averages(dataf):
    hospital_sums = dataf.groupby('ID').agg({
         'total_procedures_period': 'first', 'Revision Surgeries (N)': 'first',
         **{proc: 'sum' for proc in BARIATRIC_PROCEDURE_NAMES.keys()},
         **{app: 'sum' for app in SURGICAL_APPROACH_NAMES.keys()}
    })
    averages = hospital_sums.mean().to_dict()
    total_approaches = sum(averages.get(app, 0) for app in SURGICAL_APPROACH_NAMES.keys())
    averages['approaches_pct'] = {}
    if total_approaches > 0:
        for app_code, app_name in SURGICAL_APPROACH_NAMES.items():
            avg_count = averages.get(app_code, 0)
            averages['approaches_pct'][app_name] = (avg_count / total_approaches) * 100 if total_approaches else 0
    return averages

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

# --- Load data and compute/reuse averages ---
if 'df' not in st.session_state:
    st.session_state.df = load_data()
df = st.session_state.df

if 'national_averages' not in st.session_state:
    st.session_state.national_averages = calculate_national_averages(df)
national_averages = st.session_state.national_averages

# --- Page Title ---
st.title("🇫🇷 National Overview (Averages per Hospital)")
st.markdown("National means are computed across hospitals (2020–2024 period).")
st.markdown("---")

# --- High-level metrics ---
unique_hospitals = df.drop_duplicates(subset=['ID'])
num_hospitals = len(unique_hospitals)
avg_total_surgeries = national_averages.get('total_procedures_period', 0)
avg_revision_n = national_averages.get('Revision Surgeries (N)', 0)

national_total_procedures = unique_hospitals['total_procedures_period'].sum()
national_total_revisions = unique_hospitals['Revision Surgeries (N)'].sum()
national_revision_pct = (national_total_revisions / national_total_procedures) * 100 if national_total_procedures > 0 else 0

colA, colB, colC, colD = st.columns(4)
colA.metric("Hospitals in Dataset", f"{num_hospitals}")
colB.metric("Avg. Total Surgeries per Hospital", f"{avg_total_surgeries:.0f}")
colC.metric("Avg. Revision Surgeries per Hospital", f"{avg_revision_n:.0f}")
colD.metric("National Revision Rate (overall)", f"{national_revision_pct:.1f}%")

st.markdown("---")

# --- Hospital volume distribution ---
st.subheader("Hospital Volume Distribution (Most Recent Year: 2024)")
st.markdown("*Note: Only hospitals with ≥5 interventions per year are considered for this analysis*")

# Get the most recent year's data (2024)
latest_year = 2024
latest_year_data = df[df['annee'] == latest_year].drop_duplicates(subset=['ID'])

# Apply minimum cutoff of 5 interventions per year
valid_hospitals = latest_year_data[latest_year_data['total_procedures_year'] >= 5]
total_valid_hospitals = len(valid_hospitals)

# Define volume categories
def categorize_volume(annual_interventions):
    if annual_interventions < 50:
        return "< 50"
    elif annual_interventions < 100:
        return "50-100"
    elif annual_interventions < 200:
        return "100-200"
    else:
        return "≥ 200"

valid_hospitals['volume_category'] = valid_hospitals['total_procedures_year'].apply(categorize_volume)
volume_distribution = valid_hospitals['volume_category'].value_counts().reindex(['< 50', '50-100', '100-200', '≥ 200'])

# Create distribution data
volume_data = []
for category in ['< 50', '50-100', '100-200', '≥ 200']:
    count = volume_distribution.get(category, 0)
    percentage = (count / total_valid_hospitals) * 100 if total_valid_hospitals > 0 else 0
    volume_data.append({
        'Volume Category': category,
        'Number of Hospitals': count,
        'Percentage': round(percentage, 1)
    })

volume_df = pd.DataFrame(volume_data)

# Display metrics
col1, col2, col3 = st.columns(3)
col1.metric("Total Valid Hospitals (2024)", f"{total_valid_hospitals}")
col2.metric("Hospitals < 50/year", f"{volume_data[0]['Number of Hospitals']} ({volume_data[0]['Percentage']}%)")
col3.metric("Hospitals ≥ 200/year", f"{volume_data[3]['Number of Hospitals']} ({volume_data[3]['Percentage']}%)")

# Display table and chart
left, right = st.columns([1, 1])
with left:
    st.markdown("**Volume Distribution Table**")
    st.dataframe(volume_df, hide_index=True, use_container_width=True)

with right:
    st.markdown("**Volume Distribution Chart**")
    chart = alt.Chart(volume_df).mark_bar().encode(
        x=alt.X('Volume Category:N', title='Annual Interventions'),
        y=alt.Y('Number of Hospitals:Q', title='Number of Hospitals'),
        color=alt.Color('Volume Category:N'),
        tooltip=['Volume Category', 'Number of Hospitals', alt.Tooltip('Percentage:Q', format='.1f')]
    ).properties(height=300).configure_axisX(labelAngle=0)
    st.altair_chart(chart, use_container_width=True)

st.markdown("---")

# --- Hospital characteristics distribution ---
st.subheader("Hospital Characteristics Distribution (Most Recent Year: 2024)")

# Get all hospitals from 2024 (not just valid ones for this analysis)
all_2024_hospitals = df[df['annee'] == latest_year].drop_duplicates(subset=['ID'])
total_hospitals_2024 = len(all_2024_hospitals)

# Establishment type distribution
status_distribution = all_2024_hospitals['Status'].value_counts()
status_data = []
for status, count in status_distribution.items():
    percentage = (count / total_hospitals_2024) * 100
    status_data.append({
        'Category': 'Establishment Type',
        'Type': status.replace('-', ' ').title(),
        'Number of Hospitals': count,
        'Percentage': round(percentage, 1)
    })

# Certification and affiliation distribution
certification_data = []

# University affiliation
university_hospitals = all_2024_hospitals[all_2024_hospitals['university'] == 1]
university_count = len(university_hospitals)
university_pct = (university_count / total_hospitals_2024) * 100
certification_data.append({
    'Category': 'Certifications & Affiliations',
    'Type': 'University Hospital',
    'Number of Hospitals': university_count,
    'Percentage': round(university_pct, 1)
})

# SOFFCO certification
soffco_hospitals = all_2024_hospitals[all_2024_hospitals['LAB_SOFFCO'] == 1]
soffco_count = len(soffco_hospitals)
soffco_pct = (soffco_count / total_hospitals_2024) * 100
certification_data.append({
    'Category': 'Certifications & Affiliations',
    'Type': 'Centre of Excellence (SOFFCO)',
    'Number of Hospitals': soffco_count,
    'Percentage': round(soffco_pct, 1)
})

# Health Ministry certification
health_ministry_hospitals = all_2024_hospitals[all_2024_hospitals['cso'] == 1]
health_ministry_count = len(health_ministry_hospitals)
health_ministry_pct = (health_ministry_count / total_hospitals_2024) * 100
certification_data.append({
    'Category': 'Certifications & Affiliations',
    'Type': 'Centre of Excellence (Health Ministry)',
    'Number of Hospitals': health_ministry_count,
    'Percentage': round(health_ministry_pct, 1)
})

# Hospitals with both certifications
both_certifications = all_2024_hospitals[
    (all_2024_hospitals['LAB_SOFFCO'] == 1) & 
    (all_2024_hospitals['cso'] == 1)
]
both_count = len(both_certifications)
both_pct = (both_count / total_hospitals_2024) * 100
certification_data.append({
    'Category': 'Certifications & Affiliations',
    'Type': 'Both Certifications (SOFFCO + Health Ministry)',
    'Number of Hospitals': both_count,
    'Percentage': round(both_pct, 1)
})

# Display metrics
col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Hospitals (2024)", f"{total_hospitals_2024}")
col2.metric("Public Hospitals", f"{status_distribution.get('public', 0)} ({round((status_distribution.get('public', 0) / total_hospitals_2024) * 100, 1)}%)")
col3.metric("University Hospitals", f"{university_count} ({university_pct:.1f}%)")
col4.metric("SOFFCO Centers", f"{soffco_count} ({soffco_pct:.1f}%)")

# Display tables
st.markdown("**Establishment Type Distribution**")
status_df = pd.DataFrame(status_data)
st.dataframe(status_df[['Type', 'Number of Hospitals', 'Percentage']], hide_index=True, use_container_width=True)

st.markdown("**Certifications & Affiliations Distribution**")
cert_df = pd.DataFrame(certification_data)
st.dataframe(cert_df[['Type', 'Number of Hospitals', 'Percentage']], hide_index=True, use_container_width=True)

# Create charts
col1, col2 = st.columns(2)

with col1:
    st.markdown("**Establishment Type Chart**")
    status_chart = alt.Chart(status_df).mark_bar().encode(
        x=alt.X('Type:N', title='Establishment Type'),
        y=alt.Y('Number of Hospitals:Q', title='Number of Hospitals'),
        color=alt.Color('Type:N'),
        tooltip=['Type', 'Number of Hospitals', alt.Tooltip('Percentage:Q', format='.1f')]
    ).properties(height=300).configure_axisX(labelAngle=0)
    st.altair_chart(status_chart, use_container_width=True)

with col2:
    st.markdown("**Certifications & Affiliations Chart**")
    cert_chart = alt.Chart(cert_df).mark_bar().encode(
        x=alt.X('Type:N', title='Certification Type'),
        y=alt.Y('Number of Hospitals:Q', title='Number of Hospitals'),
        color=alt.Color('Type:N'),
        tooltip=['Type', 'Number of Hospitals', alt.Tooltip('Percentage:Q', format='.1f')]
    ).properties(height=300).configure_axisX(labelAngle=0)
    st.altair_chart(cert_chart, use_container_width=True)

st.markdown("---")

# --- Average bariatric procedures per hospital ---
st.subheader("Average Bariatric Procedures per Hospital")
avg_proc_rows = []
for code, name in BARIATRIC_PROCEDURE_NAMES.items():
    if code in national_averages:
        avg_proc_rows.append({"Procedure": name, "Average per Hospital": round(national_averages.get(code, 0), 2)})
avg_proc_df = pd.DataFrame(avg_proc_rows)
if not avg_proc_df.empty:
    left, right = st.columns([2, 3])
    with left:
        st.dataframe(avg_proc_df, hide_index=True, use_container_width=True)
    with right:
        chart = alt.Chart(avg_proc_df).mark_bar().encode(
            x=alt.X('Average per Hospital:Q', title='Average Count'),
            y=alt.Y('Procedure:N', sort='-x', title='Procedure'),
            tooltip=['Procedure', alt.Tooltip('Average per Hospital:Q', format='.2f')]
        ).properties(height=300).configure_axisY(labelAngle=0)
        st.altair_chart(chart, use_container_width=True)
else:
    st.info("No bariatric procedure data available.")

st.markdown("---")

# --- Average surgical approaches share ---
st.subheader("Average Surgical Approaches Share (per Hospital)")
approach_pct = national_averages.get('approaches_pct', {})
approach_rows = [{"Approach": name, "Share (%)": round(pct, 2)} for name, pct in approach_pct.items()]
approach_df = pd.DataFrame(approach_rows)
if not approach_df.empty:
    c = alt.Chart(approach_df).mark_arc(innerRadius=60).encode(
        theta=alt.Theta(field='Share (%)', type='quantitative'),
        color=alt.Color(field='Approach', type='nominal'),
        tooltip=['Approach', alt.Tooltip('Share (%):Q', format='.2f')]
    ).properties(height=300)
    st.altair_chart(c, use_container_width=False)
    st.dataframe(approach_df, hide_index=True, use_container_width=True)
else:
    st.info("No surgical approach data available.")


