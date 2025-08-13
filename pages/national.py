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
        ).properties(height=300)
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


