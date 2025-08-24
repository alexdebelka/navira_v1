import os
import pandas as pd

# Create output directory
os.makedirs("data/processed", exist_ok=True)

print("Loading CSV files...")

# Load hospitals data
print("Loading hospitals...")
hospitals_df = pd.read_csv("data/01_hospitals.csv", sep=';', encoding='latin1')
if hospitals_df.columns[0].startswith('Unnamed'):
    hospitals_df = hospitals_df.iloc[:, 1:]
print(f"Hospitals shape: {hospitals_df.shape}")

# Load TCN data (procedure types)
print("Loading TCN data...")
tcn_df = pd.read_csv("data/06_tab_tcn_redo_new.csv", sep=';', encoding='latin1', decimal=',')
if tcn_df.columns[0].startswith('Unnamed'):
    tcn_df = tcn_df.iloc[:, 1:]
print(f"TCN shape: {tcn_df.shape}")

# Load VDA data (surgical approaches)
print("Loading VDA data...")
vda_df = pd.read_csv("data/03_tab_vda_new.csv", sep=';', encoding='latin1', decimal=',')
if vda_df.columns[0].startswith('Unnamed'):
    vda_df = vda_df.iloc[:, 1:]
print(f"VDA shape: {vda_df.shape}")

# Load redo data
print("Loading redo data...")
redo_df = pd.read_csv("data/04_tab_redo.csv", sep=';', encoding='latin1', decimal=',')
if redo_df.columns[0].startswith('Unnamed'):
    redo_df = redo_df.iloc[:, 1:]
print(f"Redo shape: {redo_df.shape}")

print("\nProcessing data...")

# Clean hospitals data
hospitals_df = hospitals_df.rename(columns={
    'finessGeo': 'id',
    'rs': 'name'
}).copy()

# Keep 1 row / id
hospitals_df = hospitals_df.drop_duplicates(subset='id', keep='first')

# Strip strings
for col in hospitals_df.select_dtypes(include=['object']).columns:
    hospitals_df[col] = hospitals_df[col].astype(str).str.strip()

# Coerce numeric columns
for col in ['latitude', 'longitude', 'university', 'cso', 'LAB_SOFFCO']:
    if col in hospitals_df.columns:
        hospitals_df[col] = pd.to_numeric(hospitals_df[col], errors='coerce')

# Drop rows with invalid coordinates
if {'latitude', 'longitude'}.issubset(hospitals_df.columns):
    hospitals_df = hospitals_df.dropna(subset=['latitude', 'longitude'])
    hospitals_df = hospitals_df[
        hospitals_df['latitude'].between(-90, 90) & hospitals_df['longitude'].between(-180, 180)
    ]

# Prepare establishments
redo_df = redo_df.rename(columns={
    'finessGeoDP': 'id',
    'n': 'revision_surgeries_n',
    'PCT': 'revision_surgeries_pct',
    'TOT': 'total_procedures_period'
}).copy()

redo_df = redo_df.drop_duplicates(subset='id', keep='first')
establishments_df = hospitals_df.merge(redo_df, on='id', how='left', suffixes=('', '_redo'))

# Set dtypes
if 'revision_surgeries_n' in establishments_df:
    establishments_df['revision_surgeries_n'] = establishments_df['revision_surgeries_n'].fillna(0).astype('Int64')
if 'revision_surgeries_pct' in establishments_df:
    establishments_df['revision_surgeries_pct'] = establishments_df['revision_surgeries_pct'].astype(float)
if 'total_procedures_period' in establishments_df:
    establishments_df['total_procedures_period'] = establishments_df['total_procedures_period'].fillna(0).astype('Int64')

establishments_df = establishments_df.reset_index(drop=True)

# Prepare annual procedures
tcn = tcn_df.rename(columns={'finessGeoDP': 'id'}).copy()

# Pivot counts by 'baria_t' category
proc_pivot = tcn.pivot_table(
    index=['id', 'annee'],
    columns='baria_t',
    values='n',
    aggfunc='sum',
    fill_value=0
).reset_index()

# Bring yearly totals
yearly_totals = tcn[['id', 'annee', 'TOT']].drop_duplicates()
yearly_totals = yearly_totals.rename(columns={'TOT': 'total_procedures_year'})

procedures_df = pd.merge(proc_pivot, yearly_totals, on=['id', 'annee'], how='left')

# Surgical approaches
vda = vda_df.rename(columns={'finessGeoDP': 'id'}).copy()
appr_pivot = vda.pivot_table(
    index=['id', 'annee'],
    columns='vda',
    values='n',
    aggfunc='sum',
    fill_value=0
).reset_index()

# Merge both pivots
annual_df = pd.merge(procedures_df, appr_pivot, on=['id', 'annee'], how='outer').fillna(0)

# Types & hygiene
annual_df['id'] = annual_df['id'].astype(str)
if 'annee' in annual_df:
    annual_df['annee'] = pd.to_numeric(annual_df['annee'], errors='coerce').fillna(0).astype('int16')

# Validation
non_proc = {'id', 'annee', 'total_procedures_year'} | set(appr_pivot.columns) - {'id', 'annee'}
candidate_proc_cols = [c for c in procedures_df.columns if c not in non_proc and c not in {'id', 'annee'}]
if candidate_proc_cols:
    annual_df['calculated_total_primary'] = annual_df[candidate_proc_cols].sum(axis=1).astype('Int64')
    if 'total_procedures_year' in annual_df:
        annual_df['total_procedures_year'] = annual_df['total_procedures_year'].fillna(annual_df['calculated_total_primary'])
    else:
        annual_df['total_procedures_year'] = annual_df['calculated_total_primary']

print("\nSaving parquet files...")

# Save parquet files
establishments_df.to_parquet("data/processed/establishments.parquet", engine="pyarrow", index=False)
annual_df.to_parquet("data/processed/annual_procedures.parquet", engine="pyarrow", index=False)

print(f"✅ Wrote establishments.parquet ({len(establishments_df):,} rows)")
print(f"✅ Wrote annual_procedures.parquet ({len(annual_df):,} rows)")

# Verify the files were created
if os.path.exists("data/processed/establishments.parquet"):
    print("✅ establishments.parquet created successfully")
else:
    print("❌ establishments.parquet creation failed")

if os.path.exists("data/processed/annual_procedures.parquet"):
    print("✅ annual_procedures.parquet created successfully")
else:
    print("❌ annual_procedures.parquet creation failed")
