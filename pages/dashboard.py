# pages/dashboard.py
import streamlit as st
import pandas as pd
import altair as alt
import os

# --- Page Configuration ---
st.set_page_config(
    page_title="Hospital Dashboard",
    page_icon="📊",
    layout="wide"
)

# --- MAPPING DICTIONARIES (must be consistent with main page) ---
BARIATRIC_PROCEDURE_NAMES = {
    'SLE': 'Sleeve Gastrectomy', 'BPG': 'Gastric Bypass', 'ANN': 'Band Removal',
    'REV': 'Other', 'ABL': 'Gastric Banding'
}
SURGICAL_APPROACH_NAMES = {
    'LAP': 'Open Surgery', 'COE': 'Coelioscopy', 'ROB': 'Robotic'
}

# <<< FIX: The load_data function is updated to use a comma separator >>>
@st.cache_data
def load_data(path): # Removed default path here
    try:
        # Use sep=',' because your CSV file is comma-separated
        df = pd.read_csv(path, sep=',')
        df.rename(columns={
            'id': 'ID', 'rs': 'Hospital Name', 'statut': 'Status', 'ville': 'City',
            'revision_surgeries_n': 'Revision Surgeries (N)', 'revision_surgeries_pct': 'Revision Surgeries (%)'
        }, inplace=True)
        df['Status'] = df['Status'].astype(str).str.strip().str.lower()
        status_mapping = {
            'private not-for-profit': 'private-non-profit', 'public': 'public', 'private for profit': 'private-for-profit'
        }
        df['Status'] = df['Status'].map(status_mapping)
        numeric_cols = [
            'Revision Surgeries (N)', 'total_procedures_period', 'annee', 'total_procedures_year',
            'university', 'cso', 'LAB_SOFFCO', 'latitude', 'longitude', 'Revision Surgeries (%)'
        ] + list(BARIATRIC_PROCEDURE_NAMES.keys()) + list(SURGICAL_APPROACH_NAMES.keys())
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        for col in ['lib_dep', 'lib_reg']:
            if col in df.columns:
                df[col] = df[col].astype(str).fillna('N/A')
        df.drop_duplicates(subset=['ID', 'annee'], keep='first', inplace=True)
        df.dropna(subset=['latitude', 'longitude'], inplace=True)
        df = df[df['latitude'].between(-90, 90) & df['longitude'].between(-180, 180)]
        return df
    except FileNotFoundError:
        st.error(f"Fatal Error: Data file not found at the constructed path: '{path}'")
        st.stop()
    except Exception as e:
        st.error(f"An error occurred loading data: {e}")
        st.stop()

# <<< FIX: Construct the correct, absolute path to your data file >>>
# This gets the directory of the current script (pages/)
script_dir = os.path.dirname(os.path.abspath(__file__))
# This goes up one level ('..') to the main project folder, then into the 'data' folder
file_path = os.path.join(script_dir, '..', 'data', 'flattened_v3.csv')


st.title("📊 Hospital Details Dashboard")

# --- Safely check for selected hospital ---
if "selected_hospital_id" not in st.session_state or st.session_state.selected_hospital_id is None:
    st.warning("Please select a hospital from the main '🏥 Navira - French Hospital Explorer' page first.", icon="👈")
    st.stop()

# <<< FIX: Load the main dataframe using the correct path if it's not in the session state >>>
if 'df' not in st.session_state:
    st.session_state.df = load_data(file_path) # Pass the correct path to the function


# --- Load data from session state ---
df = st.session_state.df
# Use .get() for filtered_df for extra safety
filtered_df = st.session_state.get('filtered_df', pd.DataFrame())
selected_hospital_id = st.session_state.selected_hospital_id

# Find all data for the selected hospital
if not filtered_df.empty and selected_hospital_id in filtered_df['ID'].values:
    selected_hospital_all_data = filtered_df[filtered_df['ID'] == selected_hospital_id]
    selected_hospital_details = selected_hospital_all_data.iloc[0]
else:
    # Fallback for page refresh
    selected_hospital_all_data = df[df['ID'] == selected_hospital_id]
    if selected_hospital_all_data.empty:
        st.error("Could not find data for the selected hospital. Please select another.")
        st.stop()
    selected_hospital_details = selected_hospital_all_data.iloc[0]


# --- Display Hospital Details ---
st.markdown(f"## {selected_hospital_details['Hospital Name']}")
col1, col2, col3 = st.columns(3)
col1.markdown(f"**City:** {selected_hospital_details['City']}")
col2.markdown(f"**Status:** {selected_hospital_details['Status']}")
if 'Distance (km)' in selected_hospital_details:
    col3.markdown(f"**Distance:** {selected_hospital_details['Distance (km)']:.1f} km")
st.markdown("---")

metric_col1, metric_col2 = st.columns(2)
with metric_col1:
    st.markdown("##### Surgery Statistics (2020-2024)")
    total_proc = selected_hospital_details.get('total_procedures_period', 0)
    st.metric("Total Surgeries (All Types)", f"{total_proc:.0f}")
    st.metric("Total Revision Surgeries", f"{selected_hospital_details['Revision Surgeries (N)']:.0f}")

with metric_col2:
    st.markdown("##### Labels & Affiliations")
    if selected_hospital_details.get('university') == 1:
        st.success("🎓 University Hospital (Academic Affiliation)")
    else:
        st.warning("➖ No University Affiliation")
    if selected_hospital_details.get('LAB_SOFFCO') == 1:
        st.success("✅ Centre of Excellence (SOFFCO)")
    else:
        st.warning("➖ No SOFFCO Centre Label")
    if selected_hospital_details.get('cso') == 1:
        st.success("✅ Centre of Excellence (Health Ministry)")
    else:
        st.warning("➖ No Health Ministry Centre Label")

st.markdown("---")
st.header("Annual Statistics")

hospital_annual_data = selected_hospital_all_data.set_index('annee').sort_index()

# --- Bariatric Procedures Chart ---
st.markdown("##### Bariatric Procedures by Year")
bariatric_df = hospital_annual_data[list(BARIATRIC_PROCEDURE_NAMES.keys())].rename(columns=BARIATRIC_PROCEDURE_NAMES)
bariatric_summary = bariatric_df.sum()
summary_texts = [f"**{name}**: {int(count)}" for name, count in bariatric_summary.items() if count > 0]
if summary_texts: st.markdown(" | ".join(summary_texts))

bariatric_df_melted = bariatric_df.reset_index().melt('annee', var_name='Procedure', value_name='Count')
if not bariatric_df_melted.empty and bariatric_df_melted['Count'].sum() > 0:
    bariatric_chart = alt.Chart(bariatric_df_melted).mark_bar().encode(
        x=alt.X('annee:O', title='Year', axis=alt.Axis(labelAngle=0)),
        y=alt.Y('Count:Q', title='Number of Procedures'),
        color='Procedure:N', tooltip=['annee', 'Procedure', 'Count']
    ).interactive()
    st.altair_chart(bariatric_chart, use_container_width=True)
else:
    st.info("No bariatric procedure data available.")

st.markdown("---")

# --- Surgical Approaches Chart ---
st.markdown("##### Surgical Approaches by Year")
approach_df = hospital_annual_data[list(SURGICAL_APPROACH_NAMES.keys())].rename(columns=SURGICAL_APPROACH_NAMES)
approach_summary = approach_df.sum()
total_approaches = approach_summary.sum()
summary_texts_approach = []
if total_approaches > 0:
    for name, count in approach_summary.items():
        if count > 0:
            percentage = (count / total_approaches) * 100
            summary_texts_approach.append(f"**{name}**: {int(count)} ({percentage:.1f}%)")
if summary_texts_approach: st.markdown(" | ".join(summary_texts_approach))

approach_df_melted = approach_df.reset_index().melt('annee', var_name='Approach', value_name='Count')
if not approach_df_melted.empty and approach_df_melted['Count'].sum() > 0:
    bar = alt.Chart(approach_df_melted).mark_bar().encode(
        x=alt.X('annee:O', title='Year', axis=alt.Axis(labelAngle=0)),
        y=alt.Y('Count:Q', title='Number of Surgeries'),
        color='Approach:N', tooltip=['annee', 'Approach', 'Count']
    )
    st.altair_chart(bar.interactive(), use_container_width=True)
else:
    st.info("No surgical approach data available.")
