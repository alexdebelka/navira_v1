from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
from pathlib import Path
import math

app = FastAPI()

# Allow CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Path to data (relative to the root of the repo, assuming backend is run from next_migration/backend)
# We need to go up two levels: next_migration/backend -> next_migration -> root
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "new_data"

def read_csv(folder: str, filename: str) -> pd.DataFrame:
    p = DATA_DIR / folder / filename
    if not p.exists():
        return pd.DataFrame()
    try:
        df = pd.read_csv(p, dtype={'finessGeoDP': str})
        # Normalize common columns
        if 'finessGeoDP' in df.columns:
            df['finessGeoDP'] = df['finessGeoDP'].astype(str).str.strip()
        if 'annee' in df.columns:
            df['annee'] = pd.to_numeric(df['annee'], errors='coerce')
        return df
    except Exception as e:
        print(f"Error reading {filename}: {e}")
        return pd.DataFrame()

@app.get("/api/summary/{hospital_id}")
def get_summary(hospital_id: str):
    # 1. Load Data
    vol_hop = read_csv("ACTIVITY", "TAB_VOL_HOP_YEAR.csv")
    trend_hop = read_csv("ACTIVITY", "TAB_TREND_HOP.csv")
    rev_hop = read_csv("ACTIVITY", "TAB_REV_HOP_12M.csv")
    compl_hop = read_csv("COMPLICATIONS", "TAB_COMPL_HOP_YEAR.csv")
    
    # Initialize metrics
    metrics = {
        "procedures_2021_2024": 0,
        "procedures_2025": 0,
        "trend_2025": "—",
        "revisional_rate": 0.0,
        "complication_rate": None,
        "volume_history": [],
        "approach_mix": []
    }

    # 2. Calculate Metrics
    
    # Volume 2021-2024
    if not vol_hop.empty:
        hosp_vol = vol_hop[vol_hop['finessGeoDP'] == hospital_id]
        period_data = hosp_vol[(hosp_vol['annee'] >= 2021) & (hosp_vol['annee'] <= 2024)]
        metrics["procedures_2021_2024"] = int(period_data['n'].fillna(0).sum())
        
        # Volume 2025
        ongoing_data = hosp_vol[hosp_vol['annee'] == 2025]
        metrics["procedures_2025"] = int(ongoing_data['n'].fillna(0).sum())

    # Trend
    if not trend_hop.empty:
        hosp_trend = trend_hop[trend_hop['finessGeoDP'] == hospital_id]
        if not hosp_trend.empty and 'diff_pct' in hosp_trend.columns:
            val = hosp_trend.iloc[0]['diff_pct']
            if pd.notna(val):
                metrics["trend_2025"] = f"{float(val):+.1f}%"

    # Revisional Rate
    if not rev_hop.empty:
        hosp_rev = rev_hop[rev_hop['finessGeoDP'] == hospital_id]
        if not hosp_rev.empty and 'PCT_rev' in hosp_rev.columns:
            val = hosp_rev.iloc[0]['PCT_rev']
            if pd.notna(val):
                metrics["revisional_rate"] = float(val)

    # Complication Rate (Latest complete year)
    if not compl_hop.empty:
        hosp_compl = compl_hop[compl_hop['finessGeoDP'] == hospital_id]
        if not hosp_compl.empty and 'COMPL_pct' in hosp_compl.columns and 'annee' in hosp_compl.columns:
            years = sorted(hosp_compl['annee'].dropna().unique(), reverse=True)
            target_year = None
            if len(years) >= 2:
                target_year = years[1] # Skip partial current year
            elif len(years) == 1:
                target_year = years[0]
            
            if target_year:
                row = hosp_compl[hosp_compl['annee'] == target_year]
                if not row.empty:
                    val = row.iloc[0]['COMPL_pct']
                    if pd.notna(val):
                        metrics["complication_rate"] = float(val)

    # 3. Additional Data for Charts
    metrics["volume_history"] = []
    if not vol_hop.empty:
        hosp_vol = vol_hop[vol_hop['finessGeoDP'] == hospital_id]
        if not hosp_vol.empty:
            # Get last 5 years
            hosp_vol = hosp_vol.sort_values('annee')
            for _, row in hosp_vol.tail(5).iterrows():
                metrics["volume_history"].append({
                    "year": int(row['annee']),
                    "count": int(row['n'])
                })

    metrics["approach_mix"] = []
    # Load APP data for approach shares (latest year)
    app_hop = read_csv("ACTIVITY", "TAB_APP_HOP_YEAR.csv")
    if not app_hop.empty:
        hosp_app = app_hop[app_hop['finessGeoDP'] == hospital_id]
        if not hosp_app.empty:
            latest_yr = 2024 # Default to 2024 as per dashboard logic
            if (hosp_app['annee'] == 2024).any():
                latest_yr = 2024
            else:
                latest_yr = hosp_app['annee'].max()
            
            hosp_app_yr = hosp_app[hosp_app['annee'] == latest_yr]
            
            totals = {}
            for _, r in hosp_app_yr.iterrows():
                approach = str(r.get('vda', '')).upper().strip()
                count = float(r.get('n', 0))
                totals[approach] = totals.get(approach, 0.0) + count
            
            approach_map = {'ROB': 'Robotic', 'COE': 'Coelioscopy', 'LAP': 'Open Surgery'}
            for k, v in totals.items():
                if v > 0:
                    metrics["approach_mix"].append({
                        "name": approach_map.get(k, k),
                        "value": v
                    })

    return metrics

@app.get("/")
def root():
    return {"message": "Navira API is running"}
