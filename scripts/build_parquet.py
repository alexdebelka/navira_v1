import os
import sys
import pandas as pd

RAW_DIR = os.environ.get("NAVIRA_RAW_DIR", "data")
OUT_DIR = os.environ.get("NAVIRA_OUT_DIR", "data/processed")
os.makedirs(OUT_DIR, exist_ok=True)

HOSPITALS_CSV = os.path.join(RAW_DIR, "01_hospitals.csv")
TCN_CSV = os.path.join(RAW_DIR, "02_tab_tcn.csv")   # procedure types / year
VDA_CSV = os.path.join(RAW_DIR, "03_tab_vda.csv")   # surgical approach / year
REDO_CSV = os.path.join(RAW_DIR, "04_tab_redo.csv")  # revision summary over 2020–2024

ESTABLISHMENTS_PARQUET = os.path.join(OUT_DIR, "establishments.parquet")
ANNUAL_PROCEDURES_PARQUET = os.path.join(OUT_DIR, "annual_procedures.parquet")


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


def load_sources():
    hospitals_df = _read_csv_with_fallback(HOSPITALS_CSV, sep=';')
    tcn_df = _read_csv_with_fallback(TCN_CSV, sep=';', decimal=',')
    vda_df = _read_csv_with_fallback(VDA_CSV, sep=';', decimal=',')
    redo_df = _read_csv_with_fallback(REDO_CSV, sep=';', decimal=',')
    return hospitals_df, tcn_df, vda_df, redo_df


def clean_hospitals(hospitals_df: pd.DataFrame) -> pd.DataFrame:
    # Canonical columns
    hospitals_df = hospitals_df.rename(columns={
        'finessGeo': 'id',
        'rs': 'name'
    }).copy()

    # Keep 1 row / id
    hospitals_df = hospitals_df.drop_duplicates(subset='id', keep='first')
    hospitals_df = hospitals_df.set_index('id', drop=False)

    # Optional niceties: strip strings
    for col in hospitals_df.select_dtypes(include=['object']).columns:
        hospitals_df[col] = hospitals_df[col].astype(str).str.strip()

    # Coerce numeric columns used by the app
    for col in ['latitude', 'longitude', 'university', 'cso', 'LAB_SOFFCO']:
        if col in hospitals_df.columns:
            hospitals_df[col] = pd.to_numeric(hospitals_df[col], errors='coerce')

    # Drop rows with invalid coordinates
    if {'latitude', 'longitude'}.issubset(hospitals_df.columns):
        hospitals_df = hospitals_df.dropna(subset=['latitude', 'longitude'])
        hospitals_df = hospitals_df[
            hospitals_df['latitude'].between(-90, 90) & hospitals_df['longitude'].between(-180, 180)
        ]

    return hospitals_df


def prepare_establishments(hospitals_df: pd.DataFrame, redo_df: pd.DataFrame) -> pd.DataFrame:
    redo_df = redo_df.rename(columns={
        'finessGeoDP': 'id',
        'n': 'revision_surgeries_n',
        'PCT': 'revision_surgeries_pct',
        'TOT': 'total_procedures_period'
    }).copy()

    redo_df = redo_df.drop_duplicates(subset='id', keep='first').set_index('id', drop=False)
    establishments_df = hospitals_df.join(redo_df.set_index('id'), on='id', how='left', rsuffix='_redo')

    # Dtypes & ordering
    if 'revision_surgeries_n' in establishments_df:
        establishments_df['revision_surgeries_n'] = establishments_df['revision_surgeries_n'].fillna(0).astype('Int64')
    if 'revision_surgeries_pct' in establishments_df:
        establishments_df['revision_surgeries_pct'] = establishments_df['revision_surgeries_pct'].astype(float)
    if 'total_procedures_period' in establishments_df:
        establishments_df['total_procedures_period'] = establishments_df['total_procedures_period'].fillna(0).astype('Int64')

    return establishments_df.reset_index(drop=True)


def prepare_annual(tcn_df: pd.DataFrame, vda_df: pd.DataFrame) -> pd.DataFrame:
    # Procedure types per (id, year)
    tcn = tcn_df.rename(columns={'finessGeoDP': 'id'}).copy()
    # Pivot counts by 'baria_t' category
    proc_pivot = tcn.pivot_table(
        index=['id', 'annee'],
        columns='baria_t',
        values='n',
        aggfunc='sum',
        fill_value=0
    ).reset_index()

    # Bring yearly totals from source (assumes 'TOT' col exists per id/year)
    # If there are multiple rows per (id, annee), select distinct pairs.
    yearly_totals = tcn[['id', 'annee', 'TOT']].drop_duplicates()
    yearly_totals = yearly_totals.rename(columns={'TOT': 'total_procedures_year'})

    procedures_df = pd.merge(proc_pivot, yearly_totals, on=['id', 'annee'], how='left')

    # Surgical approaches per (id, year)
    vda = vda_df.rename(columns={'finessGeoDP': 'id'}).copy()
    appr_pivot = vda.pivot_table(
        index=['id', 'annee'],
        columns='vda',
        values='n',
        aggfunc='sum',
        fill_value=0
    ).reset_index()

    # Merge both pivots
    annual = pd.merge(procedures_df, appr_pivot, on=['id', 'annee'], how='outer').fillna(0)

    # Types & hygiene
    annual['id'] = annual['id'].astype(str)
    if 'annee' in annual:
        annual['annee'] = pd.to_numeric(annual['annee'], errors='coerce').fillna(0).astype('int16')

    # Validation: check that the sum of primary procedure columns ≈ yearly total.
    # Heuristic: treat all pivoted 'baria_t' columns as primary procedures except obvious non-count columns.
    non_proc = {'id', 'annee', 'total_procedures_year'} | set(appr_pivot.columns) - {'id', 'annee'}
    candidate_proc_cols = [c for c in procedures_df.columns if c not in non_proc and c not in {'id', 'annee'}]
    if candidate_proc_cols:
        annual['calculated_total_primary'] = annual[candidate_proc_cols].sum(axis=1).astype('Int64')
        # If 'total_procedures_year' missing, backfill from calculated sum.
        if 'total_procedures_year' in annual:
            annual['total_procedures_year'] = annual['total_procedures_year'].fillna(annual['calculated_total_primary'])
        else:
            annual['total_procedures_year'] = annual['calculated_total_primary']

    return annual


def main():
    try:
        hospitals_df, tcn_df, vda_df, redo_df = load_sources()
    except FileNotFoundError as e:
        print(f"[ETL] Missing file: {e}", file=sys.stderr)
        sys.exit(1)

    hospitals_df = clean_hospitals(hospitals_df)
    establishments_df = prepare_establishments(hospitals_df, redo_df)
    annual_df = prepare_annual(tcn_df, vda_df)

    # Save Parquets
    establishments_df.to_parquet(ESTABLISHMENTS_PARQUET, engine="pyarrow", index=False)
    annual_df.to_parquet(ANNUAL_PROCEDURES_PARQUET, engine="pyarrow", index=False)

    # Minimal sanity checks
    if establishments_df['id'].nunique() == 0:
        print("[ETL] ERROR: establishments has zero IDs", file=sys.stderr); sys.exit(2)
    if annual_df[['id','annee']].dropna().empty:
        print("[ETL] ERROR: annual_procedures appears empty", file=sys.stderr); sys.exit(3)

    print(f"[ETL] Wrote {ESTABLISHMENTS_PARQUET} ({len(establishments_df):,} rows)")
    print(f"[ETL] Wrote {ANNUAL_PROCEDURES_PARQUET} ({len(annual_df):,} rows)")


if __name__ == "__main__":
    main()


