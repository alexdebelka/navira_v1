import os
import pandas as pd
import streamlit as st

# Get the absolute path to the directory of the current script
script_dir = os.path.dirname(os.path.abspath(__file__))

# Construct the path to the data directory (go up one level from 'navira' to the project root, then into 'data')
data_dir = os.path.join(script_dir, '..', 'data')
processed_data_dir = os.path.join(data_dir, 'processed')

# Use environment variable if set, otherwise use the constructed path
DATA_DIR_DEFAULT = os.environ.get("NAVIRA_OUT_DIR", processed_data_dir)
RAW_FALLBACK_DIR = data_dir

# Import the new CSV data loader
from .csv_data_loader import get_csv_dataframes, get_all_csv_dataframes

def _resolve_parquet_path(filename: str) -> str:
    """Return the existing Parquet path, preferring NAVIRA_OUT_DIR then falling back to data/."""
    preferred = os.path.join(DATA_DIR_DEFAULT, filename)
    if os.path.exists(preferred):
        return preferred
    fallback = os.path.join(RAW_FALLBACK_DIR, filename)
    return fallback


def _mtime(path: str) -> float:
    try:
        return os.path.getmtime(path)
    except FileNotFoundError:
        return -1.0


def _read_csv_with_fallback(path: str, sep: str = ';', decimal: str | None = None) -> pd.DataFrame:
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


def _backfill_id_from_raw_csv(est_df: pd.DataFrame) -> pd.DataFrame:
    """If `id` is missing, try to backfill from raw hospitals CSV by matching on name and city."""
    hospitals_csv = os.path.join(RAW_FALLBACK_DIR, "01_hospitals.csv")
    if not os.path.exists(hospitals_csv):
        return est_df
    try:
        raw = _read_csv_with_fallback(hospitals_csv, sep=';')
    except Exception:
        return est_df
    # Normalize columns
    raw = raw.rename(columns={'finessGeo': 'id', 'rs': 'name'})
    for col in ['name', 'ville']:
        if col in raw.columns:
            raw[col] = raw[col].astype(str).str.strip().str.upper()
    est_norm = est_df.copy()
    for col in ['name', 'ville']:
        if col in est_norm.columns:
            est_norm[col] = est_norm[col].astype(str).str.strip().str.upper()
    # Join on (name, ville)
    if {'name', 'ville'}.issubset(est_norm.columns) and {'name', 'ville', 'id'}.issubset(raw.columns):
        est_norm = est_norm.merge(raw[['name', 'ville', 'id']].drop_duplicates(), on=['name', 'ville'], how='left')
        # If id existed previously, prefer it
        if 'id_x' in est_norm.columns and 'id_y' in est_norm.columns:
            est_norm['id'] = est_norm['id_x'].fillna(est_norm['id_y'])
            est_norm = est_norm.drop(columns=['id_x', 'id_y'])
        return est_norm
    return est_df


@st.cache_data(show_spinner=False)
def load_establishments(path: str, _ver: float) -> pd.DataFrame:
    """Load establishments once; cache invalidates if file mtime changes."""
    df = pd.read_parquet(path, engine="pyarrow")
    # Normalize schema for downstream usage
    if 'id' not in df.columns:
        if 'finessGeo' in df.columns:
            df['id'] = df['finessGeo']
        elif 'ID' in df.columns:
            df = df.rename(columns={'ID': 'id'})
    if 'name' not in df.columns:
        if 'rs' in df.columns:
            df = df.rename(columns={'rs': 'name'})
        elif 'Hospital Name' in df.columns:
            df = df.rename(columns={'Hospital Name': 'name'})
    if 'ville' not in df.columns and 'City' in df.columns:
        df = df.rename(columns={'City': 'ville'})
    # lat/lon variations
    if 'latitude' not in df.columns and 'lat' in df.columns:
        df = df.rename(columns={'lat': 'latitude'})
    if 'longitude' not in df.columns and 'lon' in df.columns:
        df = df.rename(columns={'lon': 'longitude'})
    # status variations
    if 'statut' not in df.columns and 'Status' in df.columns:
        df = df.rename(columns={'Status': 'statut'})
    # label variations
    if 'LAB_SOFFCO' not in df.columns and 'soffco_label' in df.columns:
        df = df.rename(columns={'soffco_label': 'LAB_SOFFCO'})
    if 'cso' not in df.columns and 'cso_label' in df.columns:
        df = df.rename(columns={'cso_label': 'cso'})
    if 'university' not in df.columns and 'academic_affiliation' in df.columns:
        df = df.rename(columns={'academic_affiliation': 'university'})
    # If still no id, try to backfill from raw CSV by name+city
    if 'id' not in df.columns:
        df = _backfill_id_from_raw_csv(df)

    # Prefer lightweight dtypes for speed
    if 'id' in df:
        df['id'] = df['id'].astype(str)
    # Optional: reduce memory footprint for categorical strings
    for col in ['statut', 'ville', 'lib_dep', 'lib_reg']:
        if col in df.columns:
            df[col] = df[col].astype('category')
    # Validate coordinates if present
    if 'latitude' in df.columns and 'longitude' in df.columns:
        df['latitude'] = pd.to_numeric(df['latitude'], errors='coerce')
        df['longitude'] = pd.to_numeric(df['longitude'], errors='coerce')
        df = df.dropna(subset=['latitude', 'longitude'])
        df = df[df['latitude'].between(-90, 90) & df['longitude'].between(-180, 180)]
    return df


@st.cache_data(show_spinner=False)
def load_annual(path: str, _ver: float) -> pd.DataFrame:
    """Load annual procedures; cache invalidates if file mtime changes."""
    df = pd.read_parquet(path, engine="pyarrow")
    # Normalize schema
    if 'id' not in df.columns:
        if 'finessGeoDP' in df.columns:
            df = df.rename(columns={'finessGeoDP': 'id'})
        elif 'ID' in df.columns:
            df = df.rename(columns={'ID': 'id'})
    if 'annee' not in df.columns and 'year' in df.columns:
        df = df.rename(columns={'year': 'annee'})
    if 'total_procedures_year' not in df.columns:
        if 'TOT' in df.columns:
            df = df.rename(columns={'TOT': 'total_procedures_year'})
    if 'id' in df:
        df['id'] = df['id'].astype(str)
    if 'annee' in df:
        # astype with errors='ignore' is not supported here; ensure downcast
        df['annee'] = pd.to_numeric(df['annee'], errors='coerce').fillna(0).astype('int16')
    return df


def get_dataframes():
    """Get dataframes - now uses CSV data by default."""
    try:
        # Try CSV data first
        csv_data = get_all_csv_dataframes()
        return csv_data['establishments'], csv_data['annual']
    except Exception as e:
        st.warning(f"CSV data not available, falling back to parquet: {e}")
        # Fallback to parquet
        est_path = _resolve_parquet_path("establishments.parquet")
        ann_path = _resolve_parquet_path("annual_procedures.parquet")
        est_ver = _mtime(est_path)
        ann_ver = _mtime(ann_path)
        est = load_establishments(est_path, est_ver)
        ann = load_annual(ann_path, ann_ver)
        return est, ann


@st.cache_data(show_spinner=False)
def load_recruitment_zones():
    """Load patient recruitment zones data"""
    try:
        recruitment_path = os.path.join(RAW_FALLBACK_DIR, "11_recruitement_zone.csv")
        df = _read_csv_with_fallback(recruitment_path, sep=';')
        
        # Normalize column names
        if 'finessGeoDP' in df.columns:
            df = df.rename(columns={'finessGeoDP': 'hospital_id'})
        if 'codeGeo' in df.columns:
            df = df.rename(columns={'codeGeo': 'city_code'})
        if 'nb' in df.columns:
            df = df.rename(columns={'nb': 'patient_count'})
        if 'TOT' in df.columns:
            df = df.rename(columns={'TOT': 'hospital_total'})
        if 'PCT' in df.columns:
            df = df.rename(columns={'PCT': 'percentage'})
        if 'PCT_CUM' in df.columns:
            df = df.rename(columns={'PCT_CUM': 'cumulative_percentage'})
            
        # Ensure proper data types
        if 'hospital_id' in df.columns:
            df['hospital_id'] = df['hospital_id'].astype(str)
        if 'patient_count' in df.columns:
            df['patient_count'] = pd.to_numeric(df['patient_count'], errors='coerce')
        if 'percentage' in df.columns:
            df['percentage'] = pd.to_numeric(df['percentage'], errors='coerce')
            
        return df
    except Exception as e:
        print(f"Error loading recruitment zones: {e}")
        return pd.DataFrame()


@st.cache_data(show_spinner=False)
def load_competitors():
    """Load hospital competitors data"""
    try:
        competitors_path = os.path.join(RAW_FALLBACK_DIR, "13_main_competitors.csv")
        df = _read_csv_with_fallback(competitors_path, sep=';')
        
        # Normalize column names
        if 'finessGeoDP' in df.columns:
            df = df.rename(columns={'finessGeoDP': 'hospital_id'})
        if 'finessGeoDP_conc' in df.columns:
            df = df.rename(columns={'finessGeoDP_conc': 'competitor_id'})
        if 'TOT_etb' in df.columns:
            df = df.rename(columns={'TOT_etb': 'hospital_patients'})
        if 'TOT_conc' in df.columns:
            df = df.rename(columns={'TOT_conc': 'competitor_patients'})
            
        # Ensure proper data types
        if 'hospital_id' in df.columns:
            df['hospital_id'] = df['hospital_id'].astype(str)
        if 'competitor_id' in df.columns:
            df['competitor_id'] = df['competitor_id'].astype(str)
        if 'hospital_patients' in df.columns:
            df['hospital_patients'] = pd.to_numeric(df['hospital_patients'], errors='coerce')
        if 'competitor_patients' in df.columns:
            df['competitor_patients'] = pd.to_numeric(df['competitor_patients'], errors='coerce')
            
        return df
    except Exception as e:
        print(f"Error loading competitors: {e}")
        return pd.DataFrame()


@st.cache_data(show_spinner=False)
def load_complications():
    """Load complications statistics data"""
    try:
        complications_path = os.path.join(RAW_FALLBACK_DIR, "22_complication_trimestre.csv")
        df = _read_csv_with_fallback(complications_path, sep=';')
        
        # Normalize column names
        if 'finessGeoDP' in df.columns:
            df = df.rename(columns={'finessGeoDP': 'hospital_id'})
        if 'trimestre' in df.columns:
            df = df.rename(columns={'trimestre': 'quarter'})
        if 'n' in df.columns:
            df = df.rename(columns={'n': 'procedures_count'})
        if 'comp' in df.columns:
            df = df.rename(columns={'comp': 'complications_count'})
        if 'taux' in df.columns:
            df = df.rename(columns={'taux': 'complication_rate'})
        if 'taux_glissant' in df.columns:
            df = df.rename(columns={'taux_glissant': 'rolling_rate'})
        if 'moyenne_nationale' in df.columns:
            df = df.rename(columns={'moyenne_nationale': 'national_average'})
        if 'trimestre_date' in df.columns:
            df = df.rename(columns={'trimestre_date': 'quarter_date'})
        if 'se' in df.columns:
            df = df.rename(columns={'se': 'standard_error'})
        if 'ic_low' in df.columns:
            df = df.rename(columns={'ic_low': 'confidence_low'})
        if 'ic_high' in df.columns:
            df = df.rename(columns={'ic_high': 'confidence_high'})
            
        # Ensure proper data types
        if 'hospital_id' in df.columns:
            df['hospital_id'] = df['hospital_id'].astype(str)
        if 'quarter_date' in df.columns:
            df['quarter_date'] = pd.to_datetime(df['quarter_date'], errors='coerce')
        
        # Convert numeric columns
        numeric_cols = ['procedures_count', 'complications_count', 'complication_rate', 
                       'rolling_rate', 'national_average', 'standard_error', 
                       'confidence_low', 'confidence_high']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
                
        return df
    except Exception as e:
        print(f"Error loading complications: {e}")
        return pd.DataFrame()


@st.cache_data(show_spinner=False)
def load_los_90():
    """Load 90-day post-surgery length of stay distribution per hospital/year.

    Source: data/export_TAB_LOS_HOP_90.csv
    Columns in source: finessGeoDP, annee, duree_90_cat, VOL, TOT, PCT
    """
    try:
        los90_path = os.path.join(RAW_FALLBACK_DIR, "export_TAB_LOS_HOP_90.csv")
        df = _read_csv_with_fallback(los90_path, sep=',')

        # Normalize column names
        rename_map = {
            'finessGeoDP': 'hospital_id',
            'annee': 'year',
            'duree_90_cat': 'category',
            'VOL': 'count',
            'TOT': 'total',
            'PCT': 'percentage',
        }
        for k, v in rename_map.items():
            if k in df.columns and v not in df.columns:
                df = df.rename(columns={k: v})

        # Types
        if 'hospital_id' in df.columns:
            df['hospital_id'] = df['hospital_id'].astype(str)
        for num_col in ['year', 'count', 'total', 'percentage']:
            if num_col in df.columns:
                df[num_col] = pd.to_numeric(df[num_col], errors='coerce')

        # Trim whitespace in category labels
        if 'category' in df.columns:
            df['category'] = df['category'].astype(str).str.strip()

        return df
    except Exception as e:
        print(f"Error loading LOS-90 data: {e}")
        return pd.DataFrame()


@st.cache_data(show_spinner=False)
def load_clavien():
    """Load Clavien-Dindo complication categories per hospital/year (90-day).

    Source: data/TAB_CLAV_CAT_HOP_AN.csv
    Columns in source: finessGeoDP, annee, clav_cat_90, NB, PCT, TOT_y
    Notes: NB is the number of events in the category; TOT_y appears to be total
           procedures; PCT is percentage relative to total.
    """
    try:
        clavien_path = os.path.join(RAW_FALLBACK_DIR, "TAB_CLAV_CAT_HOP_AN.csv")
        df = _read_csv_with_fallback(clavien_path, sep=',')

        # Normalize column names
        rename_map = {
            'finessGeoDP': 'hospital_id',
            'annee': 'year',
            'clav_cat_90': 'clavien_category',
            'NB': 'count',
            'PCT': 'percentage',
            'TOT_y': 'total',
        }
        for k, v in rename_map.items():
            if k in df.columns and v not in df.columns:
                df = df.rename(columns={k: v})

        # Types
        if 'hospital_id' in df.columns:
            df['hospital_id'] = df['hospital_id'].astype(str)
        for num_col in ['year', 'clavien_category', 'count', 'percentage', 'total']:
            if num_col in df.columns:
                df[num_col] = pd.to_numeric(df[num_col], errors='coerce')

        return df
    except Exception as e:
        print(f"Error loading Clavien data: {e}")
        return pd.DataFrame()


@st.cache_data(show_spinner=False)
def load_procedure_details():
    """Load detailed procedure data with surgical approach and technique"""
    try:
        procedure_path = os.path.join(RAW_FALLBACK_DIR, "07_tab_vda_tcn_redo.csv")
        df = _read_csv_with_fallback(procedure_path, sep=';')
        
        # Normalize column names
        if 'finessGeoDP' in df.columns:
            df = df.rename(columns={'finessGeoDP': 'hospital_id'})
        if 'annee' in df.columns:
            df = df.rename(columns={'annee': 'year'})
        if 'vda' in df.columns:
            df = df.rename(columns={'vda': 'surgical_approach'})
        if 'baria_t' in df.columns:
            df = df.rename(columns={'baria_t': 'procedure_type'})
        if 'redo' in df.columns:
            df = df.rename(columns={'redo': 'is_revision'})
        if 'n' in df.columns:
            df = df.rename(columns={'n': 'procedure_count'})
        if 'TOT' in df.columns:
            df = df.rename(columns={'TOT': 'total_procedures'})
        if 'PCT' in df.columns:
            df = df.rename(columns={'PCT': 'percentage'})
            
        # Ensure proper data types
        if 'hospital_id' in df.columns:
            df['hospital_id'] = df['hospital_id'].astype(str)
        if 'year' in df.columns:
            df['year'] = pd.to_numeric(df['year'], errors='coerce')
        if 'is_revision' in df.columns:
            df['is_revision'] = pd.to_numeric(df['is_revision'], errors='coerce')
        
        # Convert numeric columns
        numeric_cols = ['procedure_count', 'total_procedures', 'percentage']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
                
        return df
    except Exception as e:
        print(f"Error loading procedure details: {e}")
        return pd.DataFrame()


@st.cache_data(show_spinner=False)
def load_french_cities():
    """Load French cities data for geocoding"""
    try:
        cities_path = os.path.join(RAW_FALLBACK_DIR, "COMMUNES_FRANCE_INSEE.csv")
        df = _read_csv_with_fallback(cities_path, sep=';', decimal=',')
        
        # Normalize column names
        if 'codeInsee' in df.columns:
            df = df.rename(columns={'codeInsee': 'city_code'})
        if 'codePostal' in df.columns:
            df = df.rename(columns={'codePostal': 'postal_code'})
        if 'nomCommune' in df.columns:
            df = df.rename(columns={'nomCommune': 'city_name'})
            
        # Fix coordinate columns - they are swapped in the CSV
        if 'latitude' in df.columns and 'longitude' in df.columns:
            # Swap the columns to fix the coordinate order
            df = df.rename(columns={'latitude': 'temp_lat', 'longitude': 'latitude'})
            df = df.rename(columns={'temp_lat': 'longitude'})
            
        # Ensure proper data types
        if 'city_code' in df.columns:
            df['city_code'] = df['city_code'].astype(str)
        if 'postal_code' in df.columns:
            df['postal_code'] = df['postal_code'].astype(str)
        if 'latitude' in df.columns:
            df['latitude'] = pd.to_numeric(df['latitude'], errors='coerce')
        if 'longitude' in df.columns:
            df['longitude'] = pd.to_numeric(df['longitude'], errors='coerce')
            
        return df
    except Exception as e:
        print(f"Error loading French cities: {e}")
        return pd.DataFrame()


def get_all_dataframes():
    """Get all dataframes including the new ones - now uses CSV data by default."""
    try:
        # Try CSV data first
        csv_data = get_all_csv_dataframes()
        
        # Add legacy data that's not in CSV format
        recruitment = load_recruitment_zones()
        competitors = load_competitors()
        complications = load_complications()
        procedure_details = load_procedure_details()
        cities = load_french_cities()
        los_90 = load_los_90()
        clavien = load_clavien()
        
        # Merge CSV data with legacy data
        result = csv_data.copy()
        result.update({
            'recruitment': recruitment,
            'competitors': competitors,
            'complications': complications,
            'procedure_details': procedure_details,
            'cities': cities,
            'los_90': los_90,
            'clavien': clavien,
        })
        
        return result
    except Exception as e:
        st.warning(f"CSV data not available, falling back to parquet: {e}")
        # Fallback to original parquet-based system
        establishments, annual = get_dataframes()
        recruitment = load_recruitment_zones()
        competitors = load_competitors()
        complications = load_complications()
        procedure_details = load_procedure_details()
        cities = load_french_cities()
        los_90 = load_los_90()
        clavien = load_clavien()
        
        return {
            'establishments': establishments,
            'annual': annual,
            'recruitment': recruitment,
            'competitors': competitors,
            'complications': complications,
            'procedure_details': procedure_details,
            'cities': cities,
            'los_90': los_90,
            'clavien': clavien,
        }


@st.cache_data
def load_data():
    """
    Loads all the necessary data for the app using dynamic paths.
    This function is optimized for deployment environments.
    """
    # Get the absolute path to the directory of the current script
    script_dir = os.path.dirname(os.path.abspath(__file__))

    # Construct the path to the data directory (go up one level from 'navira' to the project root, then into 'data')
    data_dir = os.path.join(script_dir, '..', 'data')

    # Construct the full paths to the data files
    establishments_path = os.path.join(data_dir, 'establishments.parquet')
    annual_procedures_path = os.path.join(data_dir, 'annual_procedures.parquet')

    # Load the datasets
    establishments = pd.read_parquet(establishments_path)
    annual_procedures = pd.read_parquet(annual_procedures_path)

    # Rename columns for establishments (only if they exist)
    rename_mapping = {}
    if 'rs' in establishments.columns:
        rename_mapping['rs'] = 'name'
    if 'finess_geo' in establishments.columns:
        rename_mapping['finess_geo'] = 'finess'
    
    if rename_mapping:
        establishments = establishments.rename(columns=rename_mapping)

    return establishments, annual_procedures


