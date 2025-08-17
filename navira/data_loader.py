import os
import pandas as pd
import streamlit as st

DATA_DIR_DEFAULT = os.environ.get("NAVIRA_OUT_DIR", "data/processed")
RAW_FALLBACK_DIR = "data"

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
            return pd.read_csv(path, sep=sep, encoding=enc, decimal=decimal)
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
    est_path = _resolve_parquet_path("establishments.parquet")
    ann_path = _resolve_parquet_path("annual_procedures.parquet")
    est_ver = _mtime(est_path)
    ann_ver = _mtime(ann_path)
    est = load_establishments(est_path, est_ver)
    ann = load_annual(ann_path, ann_ver)
    return est, ann


