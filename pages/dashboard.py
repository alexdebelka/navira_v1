# pages/Hospital_Dashboard.py
import streamlit as st
import pandas as pd
import altair as alt
from streamlit_option_menu import option_menu

# --- Page Configuration ---
st.set_page_config(
    page_title="Hospital Dashboard",
    page_icon="📊",
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


# --- MAPPING DICTIONARIES ---
BARIATRIC_PROCEDURE_NAMES = {
    'SLE': 'Sleeve Gastrectomy', 'BPG': 'Gastric Bypass', 'ANN': 'Gastric Banding',
    'REV': 'Other', 'ABL': 'Band Removal'
}
SURGICAL_APPROACH_NAMES = {
    'LAP': 'Open Surgery', 'COE': 'Coelioscopy', 'ROB': 'Robotic'
}

# --- Load Data Function (as a fallback) ---
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

# --- TOP NAVIGATION HEADER ---
selected = option_menu(
    menu_title=None,
    options=["Home", "Hospital Dashboard", "National Overview"],
    icons=["house", "clipboard2-data", "globe2"],
    menu_icon="cast",
    default_index=1, # This makes "Hospital Dashboard" the active tab
    orientation="horizontal",
)

if selected == "Home":
    st.switch_page("main.py")
elif selected == "National Overview":
    st.switch_page("pages/national.py")


# --- Safely check for selected hospital and data ---
if "selected_hospital_id" not in st.session_state or st.session_state.selected_hospital_id is None:
    st.warning("Please select a hospital from the Home page first.", icon="👈")
    st.stop()
    
if 'df' not in st.session_state:
    st.session_state.df = load_data()

# --- Load data and averages from session state ---
df = st.session_state.df
filtered_df = st.session_state.get('filtered_df', pd.DataFrame())
selected_hospital_id = st.session_state.selected_hospital_id
national_averages = st.session_state.get('national_averages', {})

# Find all data for the selected hospital
if not filtered_df.empty and selected_hospital_id in filtered_df['ID'].values:
    selected_hospital_all_data = filtered_df[filtered_df['ID'] == selected_hospital_id]
else:
    selected_hospital_all_data = df[df['ID'] == selected_hospital_id]
if selected_hospital_all_data.empty:
    st.error("Could not find data for the selected hospital.")
    st.stop()
selected_hospital_details = selected_hospital_all_data.drop_duplicates(subset=['ID'], keep='first').iloc[0]

# --- (The rest of your dashboard page code follows here) ---
# I'm including the rest of the file for completeness.
st.title("📊 Hospital Details Dashboard")
st.markdown(f"## {selected_hospital_details['Hospital Name']}")
col1, col2, col3 = st.columns(3)
col1.markdown(f"**City:** {selected_hospital_details['City']}")
col2.markdown(f"**Status:** {selected_hospital_details['Status']}")
if 'Distance (km)' in selected_hospital_details:
    col3.markdown(f"**Distance:** {selected_hospital_details['Distance (km)']:.1f} km")
st.markdown("---")
metric_col1, metric_col2 = st.columns(2)
with metric_col1:
    st.markdown("#### Surgery Statistics (2020-2024)")
    total_proc_hospital = selected_hospital_details.get('total_procedures_period', 0)
    total_rev_hospital = selected_hospital_details.get('Revision Surgeries (N)', 0)
    hospital_revision_pct = (total_rev_hospital / total_proc_hospital) * 100 if total_proc_hospital > 0 else 0
    national_total_procedures = df.drop_duplicates(subset=['ID'])['total_procedures_period'].sum()
    national_total_revisions = df.drop_duplicates(subset=['ID'])['Revision Surgeries (N)'].sum()
    national_revision_pct = (national_total_revisions / national_total_procedures) * 100 if national_total_procedures > 0 else 0
    avg_total_proc = national_averages.get('total_procedures_period', 0)
    delta_total = total_proc_hospital - avg_total_proc
    st.metric(
        label="Total Surgeries (All Types)",
        value=f"{total_proc_hospital:.0f}",
        delta=f"{delta_total:+.0f} vs. National Average (={avg_total_proc:.0f})",
        delta_color="normal"
    )
    # Metric 2: Revision Surgeries (UPDATED)
    st.metric(
        label="Revision Surgeries",
        value=f"{total_rev_hospital:.0f}",
        delta=f"{hospital_revision_pct:.1f}% of hospital's total surgeries vs. National Average: {national_revision_pct:.1f}%",
        delta_color="normal"
    )
with metric_col2:
    st.markdown("#### Labels & Affiliations")
    if selected_hospital_details.get('university') == 1: st.success("🎓 University Hospital")
    else: st.warning("➖ No University Affiliation")
    if selected_hospital_details.get('LAB_SOFFCO') == 1: st.success("✅ Centre of Excellence (SOFFCO)")
    else: st.warning("➖ No SOFFCO Centre Label")
    if selected_hospital_details.get('cso') == 1: st.success("✅ Centre of Excellence (Health Ministry)")
    else: st.warning("➖ No Health Ministry Centre Label")
st.markdown("---")
st.header("Annual Statistics")
hospital_annual_data = selected_hospital_all_data.set_index('annee')
st.markdown("#### Bariatric Procedures by Year")
bariatric_df = hospital_annual_data[[key for key in BARIATRIC_PROCEDURE_NAMES.keys() if key in hospital_annual_data.columns]].rename(columns=BARIATRIC_PROCEDURE_NAMES)
bariatric_summary = bariatric_df.sum()
summary_texts = []
for proc_code, proc_name in BARIATRIC_PROCEDURE_NAMES.items():
    count = bariatric_summary.get(proc_name, 0)
    if count > 0:
        avg_count = national_averages.get(proc_code, 0)
        summary_texts.append(f"**{proc_name}**: {int(count)} <span style='color:grey; font-style: italic;'>(National Average: {avg_count:.1f})</span>")
if summary_texts: st.markdown(" | ".join(summary_texts), unsafe_allow_html=True)
bariatric_df_melted = bariatric_df.reset_index().melt('annee', var_name='Procedure', value_name='Count')
if not bariatric_df_melted.empty and bariatric_df_melted['Count'].sum() > 0:
    bariatric_chart = alt.Chart(bariatric_df_melted).mark_bar().encode(
        x=alt.X('annee:O', title='Year', axis=alt.Axis(labelAngle=0)),
        y=alt.Y('Count:Q', title='Number of Procedures', axis= None),
        color='Procedure:N', tooltip=['annee', 'Procedure', 'Count']
    ).properties(
        width=700,
        height=400
    )
    st.altair_chart(bariatric_chart, use_container_width=True)
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
    bar = alt.Chart(approach_df_melted).mark_bar().encode(
        x=alt.X('annee:O', title='Year', axis=alt.Axis(labelAngle=0)),
        y=alt.Y('Count:Q', title='Number of Surgeries', axis= None),
        color='Approach:N', tooltip=['annee', 'Approach', 'Count']
    ).properties(
        width=700,
        height=400
    )
    st.altair_chart(bar, use_container_width=True)
else:
    st.info("No surgical approach data available.")
