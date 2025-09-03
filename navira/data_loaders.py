"""
Data loading and cleaning utilities for recruitment zone analysis.

This module provides cached, typed data loading functions for:
- Recruitment zone data with proper FINESS and postal code formatting
- Competitor data with cleaned numeric fields
- French communes data with INSEE code mapping
"""

import pandas as pd
import streamlit as st
from typing import Dict, List, Tuple
import os


@st.cache_data
def load_recruitment_data(file_path: str = "data/11_recruitement_zone.csv") -> pd.DataFrame:
    """
    Load and clean recruitment zone data.
    
    Args:
        file_path: Path to recruitment zone CSV file
        
    Returns:
        DataFrame with cleaned FINESS, postal codes, and numeric fields
        
    Columns:
        - finessGeoDP: 9-digit FINESS code (string)
        - codeGeo: 5-digit postal code (string) 
        - nb: Number of patients (float)
        - TOT: Total patients (float)
        - PCT: Percentage (float)
        - PCT_CUM: Cumulative percentage (float)
    """
    try:
        df = pd.read_csv(file_path, sep=';', quotechar='"', index_col=0)  # Handle quoted semicolon format
        
        # Clean column names by removing quotes
        df.columns = df.columns.str.strip('"')
        
        # Clean FINESS codes - pad to 9 digits and remove quotes
        if 'finessGeoDP' in df.columns:
            df['finessGeoDP'] = df['finessGeoDP'].astype(str).str.strip('"').str.zfill(9)
        
        # Clean postal codes - pad to 5 digits and remove quotes
        if 'codeGeo' in df.columns:
            df['codeGeo'] = df['codeGeo'].astype(str).str.strip('"').str.zfill(5)
        
        # Convert comma decimal strings to float
        numeric_cols = ['nb', 'TOT', 'PCT', 'PCT_CUM']
        for col in numeric_cols:
            if col in df.columns:
                if df[col].dtype == 'object':
                    df[col] = df[col].astype(str).str.replace(',', '.', regex=False)
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        return df
        
    except Exception as e:
        st.error(f"Error loading recruitment data: {e}")
        return pd.DataFrame()


@st.cache_data
def load_competitors_data(file_path: str = "data/13_main_competitors.csv") -> pd.DataFrame:
    """
    Load and clean competitor data.
    
    Args:
        file_path: Path to competitors CSV file
        
    Returns:
        DataFrame with cleaned FINESS codes and numeric fields
        
    Columns:
        - finessGeoDP: 9-digit focal hospital FINESS (string)
        - finessGeoDP_conc: 9-digit competitor FINESS (string)
        - TOT_etb: Total for establishment (float)
        - TOT_conc: Total for competitor (float)
    """
    try:
        df = pd.read_csv(file_path, sep=';', quotechar='"', index_col=0)  # Handle quoted semicolon format
        
        # Clean column names by removing quotes
        df.columns = df.columns.str.strip('"')
        
        # Clean FINESS codes - pad to 9 digits and remove quotes
        finess_cols = ['finessGeoDP', 'finessGeoDP_conc']
        for col in finess_cols:
            if col in df.columns:
                df[col] = df[col].astype(str).str.strip('"').str.zfill(9)
        
        # Convert numeric columns
        numeric_cols = ['TOT_etb', 'TOT_conc']
        for col in numeric_cols:
            if col in df.columns:
                if df[col].dtype == 'object':
                    df[col] = df[col].astype(str).str.replace(',', '.', regex=False)
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        return df
        
    except Exception as e:
        st.error(f"Error loading competitors data: {e}")
        return pd.DataFrame()


@st.cache_data
def load_communes_data(file_path: str = "data/COMMUNES_FRANCE_INSEE.csv") -> pd.DataFrame:
    """
    Load and clean French communes data with INSEE codes.
    
    Args:
        file_path: Path to communes CSV file
        
    Returns:
        DataFrame with cleaned INSEE and postal codes
        
    Columns:
        - codeInsee: 5-digit INSEE code (string)
        - codePostal: 5-digit postal code (string)
        - longitude: Longitude (float)
        - latitude: Latitude (float)  
        - nomCommune: Commune name (string)
    """
    try:
        df = pd.read_csv(file_path, sep=';')  # French CSV files often use semicolon separators
        
        # Clean INSEE codes - pad to 5 digits
        if 'codeInsee' in df.columns:
            df['codeInsee'] = df['codeInsee'].astype(str).str.zfill(5)
        
        # Clean postal codes - pad to 5 digits
        if 'codePostal' in df.columns:
            df['codePostal'] = df['codePostal'].astype(str).str.zfill(5)
        
        # Convert coordinates to numeric (French files often use comma as decimal separator)
        coord_cols = ['longitude', 'latitude']
        for col in coord_cols:
            if col in df.columns:
                if df[col].dtype == 'object':
                    df[col] = df[col].astype(str).str.replace(',', '.', regex=False)
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        return df
        
    except Exception as e:
        st.error(f"Error loading communes data: {e}")
        return pd.DataFrame()


@st.cache_data
def build_postal_to_insee_mapping(communes_df: pd.DataFrame) -> Dict[str, List[str]]:
    """
    Build mapping from postal codes to INSEE commune codes.
    
    Args:
        communes_df: DataFrame from load_communes_data()
        
    Returns:
        Dictionary mapping postal code -> list of INSEE codes
        Note: Multiple INSEE codes per postal code is common in France
    """
    mapping = {}
    
    if communes_df.empty or 'codePostal' not in communes_df.columns or 'codeInsee' not in communes_df.columns:
        return mapping
    
    # Group by postal code and collect all INSEE codes
    grouped = communes_df.groupby('codePostal')['codeInsee'].apply(list).to_dict()
    
    # Ensure all values are lists and remove duplicates
    for postal, insee_list in grouped.items():
        mapping[postal] = list(set(insee_list))
    
    return mapping


def get_data_file_path(filename: str) -> str:
    """
    Get absolute path for data file, checking multiple possible locations.
    
    Args:
        filename: Name of the data file
        
    Returns:
        Absolute path to the file
        
    Raises:
        FileNotFoundError: If file is not found in any expected location
    """
    # Try relative to current working directory
    paths_to_try = [
        os.path.join("data", filename),
        os.path.join("..", "data", filename),
        os.path.join(os.path.dirname(__file__), "..", "data", filename),
        filename  # Direct path
    ]
    
    for path in paths_to_try:
        if os.path.exists(path):
            return os.path.abspath(path)
    
    raise FileNotFoundError(f"Could not find data file {filename} in any of: {paths_to_try}")


def validate_data_availability() -> Tuple[bool, List[str]]:
    """
    Validate that all required data files are available.
    
    Returns:
        Tuple of (all_available: bool, missing_files: List[str])
    """
    required_files = [
        "11_recruitement_zone.csv",
        "13_main_competitors.csv", 
        "COMMUNES_FRANCE_INSEE.csv"
    ]
    
    missing = []
    for filename in required_files:
        try:
            get_data_file_path(filename)
        except FileNotFoundError:
            missing.append(filename)
    
    return len(missing) == 0, missing
