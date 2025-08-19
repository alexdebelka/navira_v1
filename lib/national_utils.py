import pandas as pd
import streamlit as st
from typing import Dict, List, Tuple
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from navira.data_loader import get_dataframes

# --- MAPPING DICTIONARIES ---
BARIATRIC_PROCEDURE_NAMES = {
    'SLE': 'Sleeve Gastrectomy',
    'BPG': 'Gastric Bypass',
    'ANN': 'Gastric Banding',
    'REV': 'Other',
    'ABL': 'Band Removal',
    'DBP': 'Bilio-pancreatic Diversion',
    'GVC': 'Calibrated Vertical Gastroplasty',
    'NDD': 'Not Defined',
}

SURGICAL_APPROACH_NAMES = {
    'LAP': 'Open Surgery', 'COE': 'Coelioscopy', 'ROB': 'Robotic'
}

# --- DATA LOADING AND FILTERING ---
@st.cache_data(show_spinner=False)
def load_and_prepare_data() -> pd.DataFrame:
    """Load Parquet data, merge establishments and annual, and normalize schema for national analysis."""
    try:
        establishments, annual = get_dataframes()
    except Exception:
        st.error("Parquet data not found. Please run: make parquet")
        st.stop()

    # Ensure consistent dtypes and uniqueness on establishments
    est_meta = establishments.copy()
    if 'id' in est_meta.columns:
        est_meta['id'] = est_meta['id'].astype(str)
    # Keep one row per id to avoid duplicate-index issues downstream
    keep_cols = [c for c in ['id', 'name', 'statut', 'ville', 'university', 'cso', 'LAB_SOFFCO', 'latitude', 'longitude', 'lib_reg', 'code_reg'] if c in est_meta.columns]
    est_meta = est_meta[keep_cols].drop_duplicates(subset=['id'], keep='first')

    # Merge metadata into annual records
    merged = annual.merge(
        est_meta,
        on='id', how='left'
    )

    # Derive normalized fields expected by downstream functions
    merged = merged.rename(columns={
        'id': 'hospital_id',
        'annee': 'year',
        'statut': 'sector',
        'ville': 'city',
        'LAB_SOFFCO': 'soffco_label',
        'cso': 'cso_label',
    })

    merged['sector'] = merged['sector'].astype(str).str.strip().str.lower()
    sector_mapping = {
        'private not-for-profit': 'private',
        'public': 'public',
        'private for profit': 'private'
    }
    merged['sector'] = merged['sector'].map(sector_mapping)

    # Profit status from original statut
    merged['profit_status'] = 'not_for_profit'
    merged.loc[merged['sector'] == 'public', 'profit_status'] = 'not_for_profit'
    # Try to infer from raw statut text if available via establishments
    if 'statut' in establishments.columns:
        stat_series = establishments.set_index('id')['statut'].astype(str).str.lower()
        merged['profit_status'] = merged['hospital_id'].map(lambda x: 'for_profit' if stat_series.get(str(x), '').find('for profit') >= 0 else 'not_for_profit')

    # Revision count available at establishment level; map to rows (ensure unique index)
    if 'revision_surgeries_n' in establishments.columns:
        rev_src = establishments.copy()
        if 'id' in rev_src.columns:
            rev_src['id'] = rev_src['id'].astype(str)
        rev_src = rev_src.dropna(subset=['id'])
        rev_src = rev_src.drop_duplicates(subset=['id'], keep='first')
        rev_map = rev_src.set_index('id')['revision_surgeries_n']
        merged['revision_count'] = merged['hospital_id'].astype(str).map(rev_map).fillna(0)

    # Academic affiliation column expected by consumers
    if 'university' in merged.columns:
        merged['academic_affiliation'] = merged['university']

    # Numeric hygiene
    for col in ['year', 'total_procedures_year', 'academic_affiliation', 'cso_label', 'soffco_label', 'latitude', 'longitude']:
        if col in merged.columns:
            merged[col] = pd.to_numeric(merged[col], errors='coerce')

    # Drop duplicates by hospital-year
    merged = merged.drop_duplicates(subset=['hospital_id', 'year'], keep='first')

    return merged

@st.cache_data
def filter_eligible_years(df: pd.DataFrame, min_interventions: int = 25) -> pd.DataFrame:
    """Filter to only include hospital-years with >= min_interventions total procedures."""
    return df[df['total_procedures_year'] >= min_interventions]

@st.cache_data
def total_by_hospital_year(df: pd.DataFrame) -> pd.DataFrame:
    """Compute total procedures by hospital-year."""
    return df.groupby(['hospital_id', 'year'])['total_procedures_year'].first().reset_index()

# --- VOLUME ANALYSIS ---
@st.cache_data
def compute_volume_bins_2024(df: pd.DataFrame) -> Dict[str, int]:
    """Compute volume distribution for 2024 with proper binning."""
    df_2024 = df[df['year'] == 2024].copy()
    df_eligible = filter_eligible_years(df_2024)
    
    def categorize_volume(total_procedures):
        if total_procedures < 50:
            return "<50"
        elif total_procedures < 100:
            return "50–100"
        elif total_procedures < 200:
            return "100–200"
        else:
            return ">200"
    
    df_eligible['volume_bin'] = df_eligible['total_procedures_year'].apply(categorize_volume)
    volume_dist = df_eligible['volume_bin'].value_counts()
    
    # Ensure all bins are present
    bins = ["<50", "50–100", "100–200", ">200"]
    result = {bin_name: volume_dist.get(bin_name, 0) for bin_name in bins}
    
    return result

@st.cache_data
def compute_baseline_bins_2020_2023(df: pd.DataFrame) -> Dict[str, float]:
    """Compute average volume distribution for 2020-2023 baseline."""
    df_baseline = df[df['year'].between(2020, 2023)].copy()
    df_eligible = filter_eligible_years(df_baseline)
    
    def categorize_volume(total_procedures):
        if total_procedures < 50:
            return "<50"
        elif total_procedures < 100:
            return "50–100"
        elif total_procedures < 200:
            return "100–200"
        else:
            return ">200"
    
    df_eligible['volume_bin'] = df_eligible['total_procedures_year'].apply(categorize_volume)
    
    # Compute yearly counts then average
    yearly_counts = []
    for year in [2020, 2021, 2022, 2023]:
        year_data = df_eligible[df_eligible['year'] == year]
        year_dist = year_data['volume_bin'].value_counts()
        yearly_counts.append(year_dist)
    
    # Average across years
    bins = ["<50", "50–100", "100–200", ">200"]
    baseline = {}
    for bin_name in bins:
        values = [year_dist.get(bin_name, 0) for year_dist in yearly_counts]
        baseline[bin_name] = sum(values) / len(values)
    
    return baseline

# --- AFFILIATION ANALYSIS ---
@st.cache_data
def compute_affiliation_breakdown_2024(df: pd.DataFrame) -> Dict[str, Dict[str, int]]:
    """Compute hospital affiliation breakdown for 2024."""
    df_2024 = df[df['year'] == 2024].copy()
    df_eligible = filter_eligible_years(df_2024)
    
    # Create affiliation categories
    def get_affiliation_category(row):
        if row['sector'] == 'public':
            if row['academic_affiliation'] == 1:
                return 'Public – Univ.'
            else:
                return 'Public – Non-Acad.'
        else:  # private
            if row['profit_status'] == 'for_profit':
                return 'Private – For-profit'
            else:
                return 'Private – Not-for-profit'
    
    df_eligible['affiliation_category'] = df_eligible.apply(get_affiliation_category, axis=1)
    
    # Count by affiliation
    affiliation_counts = df_eligible['affiliation_category'].value_counts().to_dict()
    
    # Add label breakdown
    label_breakdown = {}
    for category in ['Public – Univ.', 'Public – Non-Acad.', 'Private – For-profit', 'Private – Not-for-profit']:
        category_data = df_eligible[df_eligible['affiliation_category'] == category]
        
        soffco_only = len(category_data[(category_data['soffco_label'] == 1) & (category_data['cso_label'] == 0)])
        cso_only = len(category_data[(category_data['soffco_label'] == 0) & (category_data['cso_label'] == 1)])
        both = len(category_data[(category_data['soffco_label'] == 1) & (category_data['cso_label'] == 1)])
        none = len(category_data[(category_data['soffco_label'] == 0) & (category_data['cso_label'] == 0)])
        
        label_breakdown[category] = {
            'SOFFCO Label': soffco_only,
            'CSO Label': cso_only,
            'Both': both,
            'None': none
        }
    
    return {
        'affiliation_counts': affiliation_counts,
        'label_breakdown': label_breakdown
    }

@st.cache_data
def compute_affiliation_trends_2020_2024(df: pd.DataFrame) -> Dict[str, Dict[int, int]]:
    """Compute affiliation trends over 2020-2024 period."""
    trends = {
        'Public – Univ.': {},
        'Public – Non-Acad.': {},
        'Private – For-profit': {},
        'Private – Not-for-profit': {}
    }
    
    for year in range(2020, 2025):
        df_year = df[df['year'] == year].copy()
        df_eligible = filter_eligible_years(df_year)
        
        # Create affiliation categories for this year
        def get_affiliation_category(row):
            if row['sector'] == 'public':
                if row['academic_affiliation'] == 1:
                    return 'Public – Univ.'
                else:
                    return 'Public – Non-Acad.'
            else:  # private
                if row['profit_status'] == 'for_profit':
                    return 'Private – For-profit'
                else:
                    return 'Private – Not-for-profit'
        
        df_eligible['affiliation_category'] = df_eligible.apply(get_affiliation_category, axis=1)
        
        # Count by affiliation for this year
        year_counts = df_eligible['affiliation_category'].value_counts()
        
        for category in trends.keys():
            trends[category][year] = year_counts.get(category, 0)
    
    return trends

# --- ROBOTIC SURGERY COMPARISON ANALYSIS ---
@st.cache_data
def compute_robotic_geographic_analysis(df: pd.DataFrame) -> Dict[str, Dict[str, int]]:
    """Compute robotic surgery adoption by geographic region."""
    df_2024 = df[df['year'] == 2024].copy()
    df_eligible = filter_eligible_years(df_2024)
    
    # Group by region and compute robotic adoption
    if 'lib_reg' in df_eligible.columns:
        regional_data = df_eligible.groupby('lib_reg', observed=False).agg({
            'ROB': 'sum',
            'total_procedures_year': 'sum'
        }).reset_index()
        
        regional_data['robotic_percentage'] = (regional_data['ROB'] / regional_data['total_procedures_year'] * 100).round(1)
        # Remove regions with no data or NaN values
        regional_data = regional_data.dropna(subset=['robotic_percentage'])
        regional_data = regional_data[regional_data['robotic_percentage'] > 0]
        regional_data = regional_data.sort_values('robotic_percentage', ascending=False)
        
        return {
            'regions': regional_data['lib_reg'].tolist(),
            'robotic_counts': regional_data['ROB'].tolist(),
            'total_counts': regional_data['total_procedures_year'].tolist(),
            'percentages': regional_data['robotic_percentage'].tolist()
        }
    else:
        return {'regions': [], 'robotic_counts': [], 'total_counts': [], 'percentages': []}

@st.cache_data
def compute_robotic_affiliation_analysis(df: pd.DataFrame) -> Dict[str, Dict[str, int]]:
    """Compute robotic surgery adoption by hospital affiliation type."""
    df_2024 = df[df['year'] == 2024].copy()
    df_eligible = filter_eligible_years(df_2024)
    
    # Create affiliation categories
    def get_affiliation_category(row):
        if row['sector'] == 'public':
            if row['academic_affiliation'] == 1:
                return 'Public – Univ.'
            else:
                return 'Public – Non-Acad.'
        else:  # private
            if row['profit_status'] == 'for_profit':
                return 'Private – For-profit'
            else:
                return 'Private – Not-for-profit'
    
    df_eligible['affiliation_category'] = df_eligible.apply(get_affiliation_category, axis=1)
    
    # Group by affiliation and compute robotic adoption
    affiliation_data = df_eligible.groupby('affiliation_category').agg({
        'ROB': 'sum',
        'total_procedures_year': 'sum'
    }).reset_index()
    
    affiliation_data['robotic_percentage'] = (affiliation_data['ROB'] / affiliation_data['total_procedures_year'] * 100).round(1)
    affiliation_data = affiliation_data.sort_values('robotic_percentage', ascending=False)
    
    return {
        'affiliations': affiliation_data['affiliation_category'].tolist(),
        'robotic_counts': affiliation_data['ROB'].tolist(),
        'total_counts': affiliation_data['total_procedures_year'].tolist(),
        'percentages': affiliation_data['robotic_percentage'].tolist()
    }

@st.cache_data
def compute_robotic_volume_analysis(df: pd.DataFrame) -> Dict[str, Dict[str, int]]:
    """Compute robotic surgery adoption by hospital volume category."""
    df_2024 = df[df['year'] == 2024].copy()
    df_eligible = filter_eligible_years(df_2024)
    
    # Categorize hospitals by volume
    def categorize_volume(total_procedures):
        if total_procedures < 50:
            return "<50"
        elif total_procedures < 100:
            return "50–100"
        elif total_procedures < 200:
            return "100–200"
        else:
            return ">200"
    
    df_eligible['volume_category'] = df_eligible['total_procedures_year'].apply(categorize_volume)
    
    # Group by volume category and compute robotic adoption
    volume_data = df_eligible.groupby('volume_category').agg({
        'ROB': 'sum',
        'total_procedures_year': 'sum'
    }).reset_index()
    
    volume_data['robotic_percentage'] = (volume_data['ROB'] / volume_data['total_procedures_year'] * 100).round(1)
    
    # Sort by volume category order
    volume_order = ["<50", "50–100", "100–200", ">200"]
    volume_data['volume_order'] = volume_data['volume_category'].map({cat: i for i, cat in enumerate(volume_order)})
    volume_data = volume_data.sort_values('volume_order')
    
    return {
        'volume_categories': volume_data['volume_category'].tolist(),
        'robotic_counts': volume_data['ROB'].tolist(),
        'total_counts': volume_data['total_procedures_year'].tolist(),
        'percentages': volume_data['robotic_percentage'].tolist()
    }

@st.cache_data
def compute_robotic_temporal_analysis(df: pd.DataFrame) -> Dict[str, Dict[str, int]]:
    """Compute robotic surgery adoption trends over time."""
    temporal_data = []
    
    for year in range(2020, 2025):
        df_year = df[df['year'] == year].copy()
        df_eligible = filter_eligible_years(df_year)
        
        total_robotic = df_eligible['ROB'].sum()
        total_procedures = df_eligible['total_procedures_year'].sum()
        robotic_percentage = round((total_robotic / total_procedures) * 100, 1) if total_procedures > 0 else 0
        
        temporal_data.append({
            'year': year,
            'robotic_count': total_robotic,
            'total_count': total_procedures,
            'percentage': robotic_percentage
        })
    
    return {
        'years': [d['year'] for d in temporal_data],
        'robotic_counts': [d['robotic_count'] for d in temporal_data],
        'total_counts': [d['total_count'] for d in temporal_data],
        'percentages': [d['percentage'] for d in temporal_data]
    }

@st.cache_data
def compute_robotic_institutional_analysis(df: pd.DataFrame) -> Dict[str, Dict[str, int]]:
    """Compute robotic surgery adoption by institutional characteristics."""
    df_2024 = df[df['year'] == 2024].copy()
    df_eligible = filter_eligible_years(df_2024)
    
    # Analyze by academic affiliation
    academic_data = df_eligible.groupby('academic_affiliation').agg({
        'ROB': 'sum',
        'total_procedures_year': 'sum'
    }).reset_index()
    
    academic_data['robotic_percentage'] = (academic_data['ROB'] / academic_data['total_procedures_year'] * 100).round(1)
    academic_data['institution_type'] = academic_data['academic_affiliation'].map({1: 'Academic', 0: 'Non-Academic'})
    
    # Analyze by sector
    sector_data = df_eligible.groupby('sector').agg({
        'ROB': 'sum',
        'total_procedures_year': 'sum'
    }).reset_index()
    
    sector_data['robotic_percentage'] = (sector_data['ROB'] / sector_data['total_procedures_year'] * 100).round(1)
    sector_data['institution_type'] = sector_data['sector'].map({'public': 'Public', 'private': 'Private'})
    
    return {
        'academic': {
            'types': academic_data['institution_type'].tolist(),
            'robotic_counts': academic_data['ROB'].tolist(),
            'total_counts': academic_data['total_procedures_year'].tolist(),
            'percentages': academic_data['robotic_percentage'].tolist()
        },
        'sector': {
            'types': sector_data['institution_type'].tolist(),
            'robotic_counts': sector_data['ROB'].tolist(),
            'total_counts': sector_data['total_procedures_year'].tolist(),
            'percentages': sector_data['robotic_percentage'].tolist()
        }
    }

# --- PROCEDURE ANALYSIS ---
@st.cache_data
def compute_procedure_averages_2020_2024(df: pd.DataFrame) -> Dict[str, float]:
    """Compute average procedure counts per hospital across 2020-2024 (FIXED)."""
    df_period = df[df['year'].between(2020, 2024)].copy()
    df_eligible = filter_eligible_years(df_period)
    
    # Group by hospital and compute averages per hospital
    hospital_averages = df_eligible.groupby('hospital_id').agg({
        proc_code: 'mean' for proc_code in BARIATRIC_PROCEDURE_NAMES.keys()
    })
    
    # Then average across all hospitals
    procedure_averages = {}
    for proc_code in BARIATRIC_PROCEDURE_NAMES.keys():
        if proc_code in hospital_averages.columns:
            procedure_averages[proc_code] = hospital_averages[proc_code].mean()
    
    return procedure_averages

@st.cache_data
def get_2024_procedure_totals(df: pd.DataFrame) -> Dict[str, int]:
    """Get total procedure counts for 2024."""
    df_2024 = df[df['year'] == 2024].copy()
    df_eligible = filter_eligible_years(df_2024)
    
    totals = {}
    for proc_code in BARIATRIC_PROCEDURE_NAMES.keys():
        if proc_code in df_eligible.columns:
            totals[proc_code] = df_eligible[proc_code].sum()
    
    totals['total_all'] = df_eligible['total_procedures_year'].sum()
    
    return totals

@st.cache_data
def get_2020_2024_procedure_totals(df: pd.DataFrame) -> Dict[str, int]:
    """Get total procedure counts for 2020-2024 period."""
    df_period = df[df['year'].between(2020, 2024)].copy()
    df_eligible = filter_eligible_years(df_period)
    
    totals = {}
    for proc_code in BARIATRIC_PROCEDURE_NAMES.keys():
        if proc_code in df_eligible.columns:
            totals[proc_code] = df_eligible[proc_code].sum()
    
    totals['total_all'] = df_eligible['total_procedures_year'].sum()
    
    return totals

# --- APPROACH ANALYSIS ---
@st.cache_data
def compute_approach_trends(df: pd.DataFrame) -> Dict[str, Dict[int, int]]:
    """Compute approach trends over 2020-2024."""
    df_period = df[df['year'].between(2020, 2024)].copy()
    df_eligible = filter_eligible_years(df_period)
    
    trends = {'all': {}, 'robotic': {}}
    
    for year in range(2020, 2025):
        year_data = df_eligible[df_eligible['year'] == year]
        trends['all'][year] = year_data['total_procedures_year'].sum()
        trends['robotic'][year] = year_data['ROB'].sum() if 'ROB' in year_data.columns else 0
    
    return trends

@st.cache_data
def compute_2024_approach_mix(df: pd.DataFrame) -> Dict[str, int]:
    """Compute approach mix for 2024."""
    df_2024 = df[df['year'] == 2024].copy()
    df_eligible = filter_eligible_years(df_2024)
    
    approach_mix = {}
    for approach_code, approach_name in SURGICAL_APPROACH_NAMES.items():
        if approach_code in df_eligible.columns:
            approach_mix[approach_name] = df_eligible[approach_code].sum()
    
    return approach_mix

# --- KPI COMPUTATIONS ---
@st.cache_data
def compute_national_kpis(df: pd.DataFrame) -> Dict[str, float]:
    """Compute key national KPIs."""
    df_2024 = df[df['year'] == 2024].copy()
    df_eligible = filter_eligible_years(df_2024)
    
    # Total hospitals meeting criteria
    total_hospitals = len(df_eligible['hospital_id'].unique())
    
    # Total surgeries in 2024
    total_surgeries_2024 = df_eligible['total_procedures_year'].sum()
    
    # Total revisions in 2024 - calculate using revision percentage
    # Since revision_count is cumulative data, we need to estimate 2024 revisions
    # We'll use the revision percentage to estimate 2024 revisions
    total_revisions_2024 = 0
    
    # Get establishments data to access revision percentages
    try:
        establishments, _ = get_dataframes()
        establishments['id'] = establishments['id'].astype(str)
        
        # For each hospital in 2024, calculate estimated 2024 revisions
        for _, row in df_eligible.iterrows():
            hospital_id = row['hospital_id']
            hospital_procedures_2024 = row['total_procedures_year']
            
            # Find corresponding establishment data
            est_data = establishments[establishments['id'] == hospital_id]
            if not est_data.empty:
                revision_pct = est_data.iloc[0].get('revision_surgeries_pct', 0)
                if pd.notna(revision_pct) and revision_pct > 0:
                    estimated_2024_revisions = (hospital_procedures_2024 * revision_pct) / 100
                    total_revisions_2024 += estimated_2024_revisions
    except Exception:
        # Fallback: use simple average if percentage calculation fails
        total_revisions_2024 = df_eligible['revision_count'].sum() / 5  # Divide by 5 years (2020-2024)
    
    return {
        'total_hospitals_2024': total_hospitals,
        'avg_surgeries_per_year': total_surgeries_2024,
        'avg_revisions_per_year': total_revisions_2024
    }
