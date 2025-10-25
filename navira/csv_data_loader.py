"""
New CSV-based data loader for NAVIRA dashboard.
Replaces parquet data sources with 37 CSV files from new_data/ACTIVITY.
"""

import os
import pandas as pd
import streamlit as st
from typing import Dict, Optional, Tuple
import numpy as np

# Get the absolute path to the directory of the current script
script_dir = os.path.dirname(os.path.abspath(__file__))

# Construct the path to the new_data directories
activity_data_dir = os.path.join(script_dir, '..', 'new_data', 'ACTIVITY')
complications_data_dir = os.path.join(script_dir, '..', 'new_data', 'COMPLICATIONS')
geography_data_dir = os.path.join(script_dir, '..', 'new_data', 'GEOGRAPHY')

def _read_csv_with_fallback(path: str, sep: str = ',', decimal: str = '.') -> pd.DataFrame:
    """Read CSV with multiple encoding attempts and French decimal handling."""
    encodings = ["utf-8", "cp1252", "latin1"]
    last_err = None
    for enc in encodings:
        try:
            kwargs = {'sep': sep, 'encoding': enc}
            if decimal is not None:
                kwargs['decimal'] = decimal
            return pd.read_csv(path, **kwargs)
        except Exception as e:
            last_err = e
            continue
    if last_err:
        raise last_err
    raise FileNotFoundError(path)

@st.cache_data(show_spinner=False)
def load_establishments_from_csv() -> pd.DataFrame:
    """Load establishments data from the original hospitals CSV."""
    try:
        # Use the original hospitals CSV from data directory
        script_dir = os.path.dirname(os.path.abspath(__file__))
        data_dir = os.path.join(script_dir, '..', 'data')
        hospitals_path = os.path.join(data_dir, "01_hospitals.csv")
        
        df = _read_csv_with_fallback(hospitals_path, sep=';')
        
        # Normalize column names
        rename_map = {
            'finessGeo': 'id',
            'rs': 'name',
            'ville': 'city',
            'lib_dep': 'department',
            'lib_reg': 'region',
            'statut': 'status'
        }
        
        for old_col, new_col in rename_map.items():
            if old_col in df.columns:
                df = df.rename(columns={old_col: new_col})
        
        # Ensure proper data types
        if 'id' in df.columns:
            df['id'] = df['id'].astype(str)
        
        # Convert coordinates if present
        for coord_col in ['latitude', 'longitude']:
            if coord_col in df.columns:
                df[coord_col] = pd.to_numeric(df[coord_col], errors='coerce')
        
        return df
    except Exception as e:
        st.error(f"Error loading establishments: {e}")
        return pd.DataFrame()

@st.cache_data(show_spinner=False)
def load_app_data() -> Dict[str, pd.DataFrame]:
    """Load surgical approach data (APP files)."""
    app_files = {
        'HOP': 'TAB_APP_HOP_YEAR.csv',
        'NATL': 'TAB_APP_NATL_YEAR.csv', 
        'REG': 'TAB_APP_REG_YEAR.csv',
        'STATUS': 'TAB_APP_STATUS_YEAR.csv'
    }
    
    app_data = {}
    for level, filename in app_files.items():
        try:
            filepath = os.path.join(activity_data_dir, filename)
            df = _read_csv_with_fallback(filepath, sep=',')
            
            # Normalize column names
            rename_map = {
                'finessGeoDP': 'hospital_id',
                'annee': 'year',
                'vda': 'approach',
                'n': 'count',
                'pct': 'percentage'
            }
            
            for old_col, new_col in rename_map.items():
                if old_col in df.columns:
                    df = df.rename(columns={old_col: new_col})
            
            # Ensure proper data types
            if 'hospital_id' in df.columns:
                df['hospital_id'] = df['hospital_id'].astype(str)
            if 'year' in df.columns:
                df['year'] = pd.to_numeric(df['year'], errors='coerce')
            if 'count' in df.columns:
                df['count'] = pd.to_numeric(df['count'], errors='coerce')
            if 'percentage' in df.columns:
                df['percentage'] = pd.to_numeric(df['percentage'], errors='coerce')
            
            app_data[level] = df
        except Exception as e:
            st.warning(f"Could not load {filename}: {e}")
            app_data[level] = pd.DataFrame()
    
    return app_data

@st.cache_data(show_spinner=False)
def load_rev_data() -> Dict[str, pd.DataFrame]:
    """Load revision surgery data (REV files)."""
    rev_files = {
        'HOP': 'TAB_REV_HOP.csv',
        'HOP_12M': 'TAB_REV_HOP_12M.csv',
        'NATL': 'TAB_REV_NATL.csv',
        'NATL_12M': 'TAB_REV_NATL_12M.csv',
        'REG': 'TAB_REV_REG.csv',
        'REG_12M': 'TAB_REV_REG_12M.csv',
        'STATUS': 'TAB_REV_STATUS.csv',
        'STATUS_12M': 'TAB_REV_STATUS_12M.csv'
    }
    
    rev_data = {}
    for level, filename in rev_files.items():
        try:
            filepath = os.path.join(activity_data_dir, filename)
            df = _read_csv_with_fallback(filepath, sep=',')
            
            # Normalize column names
            rename_map = {
                'finessGeoDP': 'hospital_id',
                'annee': 'year',
                'redo': 'is_revision',
                'n': 'count'
            }
            
            for old_col, new_col in rename_map.items():
                if old_col in df.columns:
                    df = df.rename(columns={old_col: new_col})
            
            # Ensure proper data types
            if 'hospital_id' in df.columns:
                df['hospital_id'] = df['hospital_id'].astype(str)
            if 'year' in df.columns:
                df['year'] = pd.to_numeric(df['year'], errors='coerce')
            if 'is_revision' in df.columns:
                df['is_revision'] = pd.to_numeric(df['is_revision'], errors='coerce')
            if 'count' in df.columns:
                df['count'] = pd.to_numeric(df['count'], errors='coerce')
            
            rev_data[level] = df
        except Exception as e:
            st.warning(f"Could not load {filename}: {e}")
            rev_data[level] = pd.DataFrame()
    
    return rev_data

@st.cache_data(show_spinner=False)
def load_tcn_data() -> Dict[str, pd.DataFrame]:
    """Load procedure type data (TCN files)."""
    tcn_files = {
        'HOP': 'TAB_TCN_HOP.csv',
        'HOP_YEAR': 'TAB_TCN_HOP_YEAR.csv',
        'HOP_12M': 'TAB_TCN_HOP_12M.csv',
        'HOP_MONTH': 'TAB_TCN_HOP_MONTH.csv',
        'NATL': 'TAB_TCN_NATL.csv',
        'NATL_YEAR': 'TAB_TCN_NATL_YEAR.csv',
        'NATL_12M': 'TAB_TCN_NATL_12M.csv',
        'REG': 'TAB_TCN_REG.csv',
        'REG_YEAR': 'TAB_TCN_REG_YEAR.csv',
        'REG_12M': 'TAB_TCN_REG_12M.csv',
        'STATUS': 'TAB_TCN_STATUS.csv',
        'STATUS_YEAR': 'TAB_TCN_STATUS_YEAR.csv',
        'STATUS_12M': 'TAB_TCN_STATUS_12M.csv'
    }
    
    tcn_data = {}
    for level, filename in tcn_files.items():
        try:
            filepath = os.path.join(activity_data_dir, filename)
            df = _read_csv_with_fallback(filepath, sep=',')
            
            # Normalize column names
            rename_map = {
                'finessGeoDP': 'hospital_id',
                'annee': 'year',
                'baria_t': 'procedure_type',
                'n': 'count',
                'pct': 'percentage'
            }
            
            for old_col, new_col in rename_map.items():
                if old_col in df.columns:
                    df = df.rename(columns={old_col: new_col})
            
            # Ensure proper data types
            if 'hospital_id' in df.columns:
                df['hospital_id'] = df['hospital_id'].astype(str)
            if 'year' in df.columns:
                df['year'] = pd.to_numeric(df['year'], errors='coerce')
            if 'count' in df.columns:
                df['count'] = pd.to_numeric(df['count'], errors='coerce')
            if 'percentage' in df.columns:
                df['percentage'] = pd.to_numeric(df['percentage'], errors='coerce')
            
            tcn_data[level] = df
        except Exception as e:
            st.warning(f"Could not load {filename}: {e}")
            tcn_data[level] = pd.DataFrame()
    
    return tcn_data

@st.cache_data(show_spinner=False)
def load_vol_data() -> Dict[str, pd.DataFrame]:
    """Load volume data (VOL files)."""
    vol_files = {
        'HOP_YEAR': 'TAB_VOL_HOP_YEAR.csv',
        'HOP_MONTH': 'TAB_VOL_HOP_MONTH.csv',
        'NATL_YEAR': 'TAB_VOL_NATL_YEAR.csv',
        'REG_YEAR': 'TAB_VOL_REG_YEAR.csv',
        'STATUS_YEAR': 'TAB_VOL_STATUS_YEAR.csv'
    }
    
    vol_data = {}
    for level, filename in vol_files.items():
        try:
            filepath = os.path.join(activity_data_dir, filename)
            df = _read_csv_with_fallback(filepath, sep=',')
            
            # Normalize column names
            rename_map = {
                'finessGeoDP': 'hospital_id',
                'annee': 'year',
                'mois': 'month',
                'n': 'count'
            }
            
            for old_col, new_col in rename_map.items():
                if old_col in df.columns:
                    df = df.rename(columns={old_col: new_col})
            
            # Ensure proper data types
            if 'hospital_id' in df.columns:
                df['hospital_id'] = df['hospital_id'].astype(str)
            if 'year' in df.columns:
                df['year'] = pd.to_numeric(df['year'], errors='coerce')
            if 'month' in df.columns:
                df['month'] = pd.to_numeric(df['month'], errors='coerce')
            if 'count' in df.columns:
                df['count'] = pd.to_numeric(df['count'], errors='coerce')
            
            vol_data[level] = df
        except Exception as e:
            st.warning(f"Could not load {filename}: {e}")
            vol_data[level] = pd.DataFrame()
    
    return vol_data

@st.cache_data(show_spinner=False)
def load_rob_data() -> pd.DataFrame:
    """Load robotic surgery data."""
    try:
        filepath = os.path.join(activity_data_dir, 'TAB_ROB_HOP_12M.csv')
        df = _read_csv_with_fallback(filepath, sep=',')
        
        # Normalize column names
        rename_map = {
            'finessGeoDP': 'hospital_id',
            'vda': 'approach',
            'n': 'count',
            'TOT': 'total',
            'PCT_app': 'percentage'
        }
        
        for old_col, new_col in rename_map.items():
            if old_col in df.columns:
                df = df.rename(columns={old_col: new_col})
        
        # Ensure proper data types
        if 'hospital_id' in df.columns:
            df['hospital_id'] = df['hospital_id'].astype(str)
        if 'count' in df.columns:
            df['count'] = pd.to_numeric(df['count'], errors='coerce')
        if 'total' in df.columns:
            df['total'] = pd.to_numeric(df['total'], errors='coerce')
        if 'percentage' in df.columns:
            df['percentage'] = pd.to_numeric(df['percentage'], errors='coerce')
        
        return df
    except Exception as e:
        st.warning(f"Could not load robotic surgery data: {e}")
        return pd.DataFrame()

@st.cache_data(show_spinner=False)
def load_trend_data() -> Dict[str, pd.DataFrame]:
    """Load trend data (TREND files)."""
    trend_files = {
        'HOP': 'TAB_TREND_HOP.csv',
        'NATL': 'TAB_TREND_NATL.csv',
        'REG': 'TAB_TREND_REG.csv',
        'STATUS': 'TAB_TRENDS_STATUS.csv'
    }
    
    trend_data = {}
    for level, filename in trend_files.items():
        try:
            filepath = os.path.join(activity_data_dir, filename)
            df = _read_csv_with_fallback(filepath, sep=',')
            
            # Normalize column names
            rename_map = {
                'finessGeoDP': 'hospital_id',
                'Vol_2024': 'volume_2024',
                'Vol_2025': 'volume_2025',
                'diff_pct': 'change_percentage'
            }
            
            for old_col, new_col in rename_map.items():
                if old_col in df.columns:
                    df = df.rename(columns={old_col: new_col})
            
            # Ensure proper data types
            if 'hospital_id' in df.columns:
                df['hospital_id'] = df['hospital_id'].astype(str)
            for col in ['volume_2024', 'volume_2025', 'change_percentage']:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            
            trend_data[level] = df
        except Exception as e:
            st.warning(f"Could not load {filename}: {e}")
            trend_data[level] = pd.DataFrame()
    
    return trend_data

@st.cache_data(show_spinner=False)
def load_dictionary() -> pd.DataFrame:
    """Load the NAVIRA dictionary for variable definitions."""
    try:
        filepath = os.path.join(activity_data_dir, '..', 'NAVIRA_dictionnary.csv')
        df = _read_csv_with_fallback(filepath, sep=',')
        return df
    except Exception as e:
        st.warning(f"Could not load dictionary: {e}")
        return pd.DataFrame()

def get_csv_dataframes():
    """Get all CSV dataframes - main entry point."""
    establishments = load_establishments_from_csv()
    app_data = load_app_data()
    rev_data = load_rev_data()
    tcn_data = load_tcn_data()
    vol_data = load_vol_data()
    rob_data = load_rob_data()
    trend_data = load_trend_data()
    dictionary = load_dictionary()
    
    # Load new data sources
    complications_data = load_complications_data()
    los_data = load_los_data()
    never_events_data = load_never_events_data()
    
    return {
        'establishments': establishments,
        'app_data': app_data,
        'rev_data': rev_data,
        'tcn_data': tcn_data,
        'vol_data': vol_data,
        'rob_data': rob_data,
        'trend_data': trend_data,
        'dictionary': dictionary,
        'complications_data': complications_data,
        'los_data': los_data,
        'never_events_data': never_events_data
    }

def get_annual_procedures_from_csv():
    """Create annual procedures dataframe from CSV data for compatibility."""
    try:
        # Use HOP_YEAR volume data as the base
        vol_data = load_vol_data()
        vol_hop_year = vol_data.get('HOP_YEAR', pd.DataFrame())
        
        if vol_hop_year.empty:
            return pd.DataFrame()
        
        # Create a simplified annual procedures dataframe
        annual_df = vol_hop_year.copy()
        annual_df = annual_df.rename(columns={
            'hospital_id': 'id',
            'count': 'total_procedures_year'
        })
        
        # Add year column if not present
        if 'year' not in annual_df.columns:
            annual_df['year'] = annual_df.get('annee', 2024)
        
        return annual_df
    except Exception as e:
        st.error(f"Error creating annual procedures dataframe: {e}")
        return pd.DataFrame()

def get_all_csv_dataframes():
    """Get all CSV dataframes including compatibility layer."""
    csv_data = get_csv_dataframes()
    
    # Add compatibility layer for existing dashboard code
    csv_data['annual'] = get_annual_procedures_from_csv()
    
    return csv_data

# Helper functions for dashboard compatibility
def get_procedure_mix_data(hospital_id: str = None, level: str = 'HOP') -> pd.DataFrame:
    """Get procedure mix data for charts."""
    try:
        csv_data = get_csv_dataframes()
        tcn_data = csv_data['tcn_data']
        
        # Use appropriate level data
        if level == 'HOP':
            df = tcn_data.get('HOP_YEAR', pd.DataFrame())
        elif level == 'NATL':
            df = tcn_data.get('NATL_YEAR', pd.DataFrame())
        elif level == 'REG':
            df = tcn_data.get('REG_YEAR', pd.DataFrame())
        elif level == 'STATUS':
            df = tcn_data.get('STATUS_YEAR', pd.DataFrame())
        else:
            df = tcn_data.get('HOP_YEAR', pd.DataFrame())
        
        if hospital_id and 'hospital_id' in df.columns:
            df = df[df['hospital_id'] == hospital_id]
        
        return df
    except Exception as e:
        st.error(f"Error getting procedure mix data: {e}")
        return pd.DataFrame()

def get_surgical_approaches_data(hospital_id: str = None, level: str = 'HOP') -> pd.DataFrame:
    """Get surgical approaches data for charts."""
    try:
        csv_data = get_csv_dataframes()
        app_data = csv_data['app_data']
        
        # Use appropriate level data
        if level == 'HOP':
            df = app_data.get('HOP', pd.DataFrame())
        elif level == 'NATL':
            df = app_data.get('NATL', pd.DataFrame())
        elif level == 'REG':
            df = app_data.get('REG', pd.DataFrame())
        elif level == 'STATUS':
            df = app_data.get('STATUS', pd.DataFrame())
        else:
            df = app_data.get('HOP', pd.DataFrame())
        
        if hospital_id and 'hospital_id' in df.columns:
            df = df[df['hospital_id'] == hospital_id]
        
        return df
    except Exception as e:
        st.error(f"Error getting surgical approaches data: {e}")
        return pd.DataFrame()

def get_revision_data(hospital_id: str = None, level: str = 'HOP') -> pd.DataFrame:
    """Get revision surgery data for charts."""
    try:
        csv_data = get_csv_dataframes()
        rev_data = csv_data['rev_data']
        
        # Use appropriate level data
        if level == 'HOP':
            df = rev_data.get('HOP', pd.DataFrame())
        elif level == 'NATL':
            df = rev_data.get('NATL', pd.DataFrame())
        elif level == 'REG':
            df = rev_data.get('REG', pd.DataFrame())
        elif level == 'STATUS':
            df = rev_data.get('STATUS', pd.DataFrame())
        else:
            df = rev_data.get('HOP', pd.DataFrame())
        
        if hospital_id and 'hospital_id' in df.columns:
            df = df[df['hospital_id'] == hospital_id]
        
        # Filter for revision surgeries only
        if 'is_revision' in df.columns:
            df = df[df['is_revision'] == 1]
        
        return df
    except Exception as e:
        st.error(f"Error getting revision data: {e}")
        return pd.DataFrame()

def get_volume_data(hospital_id: str = None, level: str = 'HOP') -> pd.DataFrame:
    """Get volume data for time series charts."""
    try:
        csv_data = get_csv_dataframes()
        vol_data = csv_data['vol_data']
        
        # Use appropriate level data
        if level == 'HOP':
            df = vol_data.get('HOP_YEAR', pd.DataFrame())
        elif level == 'NATL':
            df = vol_data.get('NATL_YEAR', pd.DataFrame())
        elif level == 'REG':
            df = vol_data.get('REG_YEAR', pd.DataFrame())
        elif level == 'STATUS':
            df = vol_data.get('STATUS_YEAR', pd.DataFrame())
        else:
            df = vol_data.get('HOP_YEAR', pd.DataFrame())
        
        if hospital_id and 'hospital_id' in df.columns:
            df = df[df['hospital_id'] == hospital_id]
        
        return df
    except Exception as e:
        st.error(f"Error getting volume data: {e}")
        return pd.DataFrame()

def get_robotic_surgery_data(hospital_id: str = None) -> pd.DataFrame:
    """Get robotic surgery data for charts."""
    try:
        csv_data = get_csv_dataframes()
        rob_data = csv_data['rob_data']
        
        if hospital_id and 'hospital_id' in rob_data.columns:
            rob_data = rob_data[rob_data['hospital_id'] == hospital_id]
        
        return rob_data
    except Exception as e:
        st.error(f"Error getting robotic surgery data: {e}")
        return pd.DataFrame()

def get_trend_data(hospital_id: str = None, level: str = 'HOP') -> pd.DataFrame:
    """Get trend data for charts."""
    try:
        csv_data = get_csv_dataframes()
        trend_data = csv_data['trend_data']
        
        # Use appropriate level data
        if level == 'HOP':
            df = trend_data.get('HOP', pd.DataFrame())
        elif level == 'NATL':
            df = trend_data.get('NATL', pd.DataFrame())
        elif level == 'REG':
            df = trend_data.get('REG', pd.DataFrame())
        elif level == 'STATUS':
            df = trend_data.get('STATUS', pd.DataFrame())
        else:
            df = trend_data.get('HOP', pd.DataFrame())
        
        if hospital_id and 'hospital_id' in df.columns:
            df = df[df['hospital_id'] == hospital_id]
        
        return df
    except Exception as e:
        st.error(f"Error getting trend data: {e}")
        return pd.DataFrame()

# Helper functions for new data sources

def get_complications_data(hospital_id: str = None, level: str = 'HOP', timeframe: str = 'YEAR') -> pd.DataFrame:
    """Get complications data for charts."""
    try:
        csv_data = get_csv_dataframes()
        complications_data = csv_data['complications_data']
        
        # Use appropriate level and timeframe data
        key = f"{level}_{timeframe}" if timeframe in ['YEAR', 'ROLL12'] else level
        if key == 'HOP' and timeframe == 'YEAR':
            key = 'HOP_YEAR'
        elif key == 'HOP' and timeframe == 'ROLL12':
            key = 'HOP_ROLL12'
        
        df = complications_data.get(key, pd.DataFrame())
        
        if hospital_id and 'hospital_id' in df.columns:
            df = df[df['hospital_id'] == hospital_id]
        
        return df
    except Exception as e:
        st.error(f"Error getting complications data: {e}")
        return pd.DataFrame()

def get_los_data(hospital_id: str = None, level: str = 'HOP', extended: bool = False) -> pd.DataFrame:
    """Get length of stay data for charts."""
    try:
        csv_data = get_csv_dataframes()
        los_data = csv_data['los_data']
        
        # Use appropriate level data
        key = f"{level}_7" if extended else level
        df = los_data.get(key, pd.DataFrame())
        
        if hospital_id and 'hospital_id' in df.columns:
            df = df[df['hospital_id'] == hospital_id]
        
        return df
    except Exception as e:
        st.error(f"Error getting LOS data: {e}")
        return pd.DataFrame()

def get_never_events_data(hospital_id: str = None, level: str = 'HOP') -> pd.DataFrame:
    """Get Never Events data for charts."""
    try:
        csv_data = get_csv_dataframes()
        never_events_data = csv_data['never_events_data']
        
        # Use appropriate level data
        df = never_events_data.get(level, pd.DataFrame())
        
        if hospital_id and 'hospital_id' in df.columns:
            df = df[df['hospital_id'] == hospital_id]
        
        return df
    except Exception as e:
        st.error(f"Error getting Never Events data: {e}")
        return pd.DataFrame()

def get_complications_grade_data(hospital_id: str = None, level: str = 'HOP') -> pd.DataFrame:
    """Get complications grade data for charts."""
    try:
        csv_data = get_csv_dataframes()
        complications_data = csv_data['complications_data']
        
        # Use appropriate grade data
        key = f"GRADE_{level}_YEAR"
        df = complications_data.get(key, pd.DataFrame())
        
        if hospital_id and 'hospital_id' in df.columns:
            df = df[df['hospital_id'] == hospital_id]
        
        return df
    except Exception as e:
        st.error(f"Error getting complications grade data: {e}")
        return pd.DataFrame()

# New data loading functions for complications, LOS, and Never Events

@st.cache_data(show_spinner=False)
def load_complications_data() -> Dict[str, pd.DataFrame]:
    """Load complications data from all levels and timeframes."""
    complications_files = {
        'HOP_YEAR': 'TAB_COMPL_HOP_YEAR.csv',
        'HOP_ROLL12': 'TAB_COMPL_HOP_ROLL12.csv',
        'NATL_YEAR': 'TAB_COMPL_NATL_YEAR.csv',
        'NATL_ROLL12': 'TAB_COMPL_NATL_ROLL12.csv',
        'REG_YEAR': 'TAB_COMPL_REG_YEAR.csv',
        'REG_ROLL12': 'TAB_COMPL_REG_ROLL12.csv',
        'STATUS_YEAR': 'TAB_COMPL_STATUS_YEAR.csv',
        'STATUS_ROLL12': 'TAB_COMPL_STATUS_ROLL12.csv',
        'GRADE_HOP_YEAR': 'TAB_COMPL_GRADE_HOP_YEAR.csv',
        'GRADE_NATL_YEAR': 'TAB_COMPL_GRADE_NATL_YEAR.csv',
        'GRADE_REG_YEAR': 'TAB_COMPL_GRADE_REG_YEAR.csv',
        'GRADE_STATUS_YEAR': 'TAB_COMPL_GRADE_STATUS_YEAR.csv'
    }
    
    complications_data = {}
    for level, filename in complications_files.items():
        try:
            filepath = os.path.join(complications_data_dir, filename)
            df = _read_csv_with_fallback(filepath, sep=',')
            
            # Normalize column names
            rename_map = {
                'finessGeoDP': 'hospital_id',
                'annee': 'year',
                'date': 'date',
                'mois': 'month',
                'TOT': 'total_procedures',
                'COMPL_nb': 'complications_count',
                'COMPL_pct': 'complications_percentage',
                'COMPL_pct_roll12': 'complications_percentage_rolling',
                'clav_cat_90': 'clavien_grade'
            }
            
            for old_col, new_col in rename_map.items():
                if old_col in df.columns:
                    df = df.rename(columns={old_col: new_col})
            
            # Ensure proper data types
            if 'hospital_id' in df.columns:
                df['hospital_id'] = df['hospital_id'].astype(str)
            if 'year' in df.columns:
                df['year'] = pd.to_numeric(df['year'], errors='coerce')
            if 'month' in df.columns:
                df['month'] = pd.to_numeric(df['month'], errors='coerce')
            if 'date' in df.columns:
                df['date'] = pd.to_datetime(df['date'], errors='coerce')
            
            # Convert numeric columns
            numeric_cols = ['total_procedures', 'complications_count', 'complications_percentage', 
                           'complications_percentage_rolling', 'clavien_grade']
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            
            complications_data[level] = df
        except Exception as e:
            st.warning(f"Could not load {filename}: {e}")
            complications_data[level] = pd.DataFrame()
    
    return complications_data

@st.cache_data(show_spinner=False)
def load_los_data() -> Dict[str, pd.DataFrame]:
    """Load length of stay data from all levels."""
    los_files = {
        'HOP': 'TAB_LOS_HOP.csv',
        'NATL': 'TAB_LOS_NATL.csv',
        'REG': 'TAB_LOS_REG.csv',
        'STATUS': 'TAB_LOS_STATUS.csv',
        'HOP_7': 'TAB_LOS7_HOP.csv',
        'NATL_7': 'TAB_LOS7_NATL.csv',
        'REG_7': 'TAB_LOS7_REG.csv',
        'STATUS_7': 'TAB_LOS7_STATUS.csv'
    }
    
    los_data = {}
    for level, filename in los_files.items():
        try:
            filepath = os.path.join(complications_data_dir, filename)
            df = _read_csv_with_fallback(filepath, sep=',')
            
            # Normalize column names
            rename_map = {
                'finessGeoDP': 'hospital_id',
                'annee': 'year',
                'duree_cat': 'duration_category',
                'LOS_nb': 'los_count',
                'LOS_pct': 'los_percentage',
                'TOT': 'total_procedures',
                'LOS_7_nb': 'los_7_count',
                'LOS_7_pct': 'los_7_percentage'
            }
            
            for old_col, new_col in rename_map.items():
                if old_col in df.columns:
                    df = df.rename(columns={old_col: new_col})
            
            # Ensure proper data types
            if 'hospital_id' in df.columns:
                df['hospital_id'] = df['hospital_id'].astype(str)
            if 'year' in df.columns:
                df['year'] = pd.to_numeric(df['year'], errors='coerce')
            
            # Convert numeric columns
            numeric_cols = ['total_procedures', 'los_count', 'los_percentage', 
                           'los_7_count', 'los_7_percentage']
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            
            los_data[level] = df
        except Exception as e:
            st.warning(f"Could not load {filename}: {e}")
            los_data[level] = pd.DataFrame()
    
    return los_data

@st.cache_data(show_spinner=False)
def load_never_events_data() -> Dict[str, pd.DataFrame]:
    """Load Never Events data from all levels."""
    never_files = {
        'HOP': 'TAB_NEVER_HOP.csv',
        'NATL': 'TAB_NEVER_NATL.csv',
        'REG': 'TAB_NEVER_REG.csv',
        'STATUS': 'TAB_NEVER_STATUS.csv'
    }
    
    never_data = {}
    for level, filename in never_files.items():
        try:
            filepath = os.path.join(complications_data_dir, filename)
            df = _read_csv_with_fallback(filepath, sep=',')
            
            # Normalize column names
            rename_map = {
                'finessGeoDP': 'hospital_id',
                'TOT': 'total_procedures',
                'NEVER_nb': 'never_events_count',
                'NEVER_pct': 'never_events_percentage'
            }
            
            for old_col, new_col in rename_map.items():
                if old_col in df.columns:
                    df = df.rename(columns={old_col: new_col})
            
            # Ensure proper data types
            if 'hospital_id' in df.columns:
                df['hospital_id'] = df['hospital_id'].astype(str)
            
            # Convert numeric columns
            numeric_cols = ['total_procedures', 'never_events_count', 'never_events_percentage']
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            
            never_data[level] = df
        except Exception as e:
            st.warning(f"Could not load {filename}: {e}")
            never_data[level] = pd.DataFrame()
    
    return never_data
