import os
from pathlib import Path
from typing import Optional, Tuple

import pandas as pd
import streamlit as st


def _resolve_activity_dir() -> Optional[str]:
    """Resolve the base directory for ACTIVITY CSVs.

    Order:
    - NAVIRA_ACTIVITY_DIR env
    - CWD/new_data/ACTIVITY
    - Relative to this file's parent
    - Hardcoded repo path for local dev
    """
    candidates: list[str] = []
    env_dir = os.environ.get("NAVIRA_ACTIVITY_DIR")
    if env_dir:
        candidates.append(env_dir)
    try:
        candidates.append(str(Path.cwd() / "new_data" / "ACTIVITY"))
    except Exception:
        pass
    try:
        here = Path(__file__).resolve()
        candidates.append(str((here.parent / ".." / "new_data" / "ACTIVITY").resolve()))
        candidates.append(str((here.parent.parent / "new_data" / "ACTIVITY").resolve()))
    except Exception:
        pass
    # Local workspace fallback
    candidates.append("/Users/alexdebelka/Downloads/navira/new_data/ACTIVITY")

    for c in candidates:
        try:
            if Path(c).is_dir():
                return c
        except Exception:
            continue
    return None


@st.cache_data(show_spinner=False)
def _read_csv_cached(base_dir: str, filename: str) -> pd.DataFrame:
    try:
        p = Path(base_dir) / filename
        if not p.exists():
            raise FileNotFoundError(str(p))
        df = pd.read_csv(p)
        return df
    except Exception:
        return pd.DataFrame()


def _normalize_common(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    d = df.copy()
    # ids
    if "finessGeoDP" in d.columns:
        d["finessGeoDP"] = d["finessGeoDP"].astype(str).str.strip()
    # year
    if "annee" in d.columns:
        d["annee"] = pd.to_numeric(d["annee"], errors="coerce").astype("Int64")
        if "year" not in d.columns:
            d["year"] = d["annee"]
    elif "year" in d.columns:
        d["year"] = pd.to_numeric(d["year"], errors="coerce").astype("Int64")
    # vda codes
    for c in ["vda", "VDA"]:
        if c in d.columns:
            d[c] = d[c].astype(str).str.upper().str.strip()
    # numeric columns
    for c in ["n", "TOT", "PCT", "TOT_month", "TOT_month_tcn"]:
        if c in d.columns:
            d[c] = pd.to_numeric(d[c], errors="coerce")
    return d


class DataRepo:
    """CSV-first repository for Activity/Approach/Revision datasets.

    All getters return normalized DataFrames with consistent dtypes and column aliases.
    """

    def __init__(self, base_dir: Optional[str] = None):
        self.base_dir = base_dir or _resolve_activity_dir()

    def _read(self, filename: str) -> pd.DataFrame:
        if not self.base_dir:
            return pd.DataFrame()
        raw = _read_csv_cached(self.base_dir, filename)
        return _normalize_common(raw)

    # Volume
    def get_vol_hop_year(self) -> pd.DataFrame:
        return self._read("TAB_VOL_HOP_YEAR.csv")

    # Procedures by type per hospital-year (TCN)
    def get_tcn_hop_year(self) -> pd.DataFrame:
        return self._read("TAB_TCN_HOP_YEAR.csv")

    # Approaches
    def get_app_hop_year(self) -> pd.DataFrame:
        return self._read("TAB_APP_HOP_YEAR.csv")

    def get_app_nat_year(self) -> pd.DataFrame:
        return self._read("TAB_APP_NATL_YEAR.csv")

    def get_app_reg_year(self) -> pd.DataFrame:
        return self._read("TAB_APP_REG_YEAR.csv")

    def get_app_status_year(self) -> pd.DataFrame:
        return self._read("TAB_APP_STATUS_YEAR.csv")

    # Revisions 12m — used as mapping source for region/status
    def get_rev_hop_12m(self) -> pd.DataFrame:
        return self._read("TAB_REV_HOP_12M.csv")

    def get_region_and_status(self, hospital_id: str) -> Tuple[Optional[str], Optional[str]]:
        df = self.get_rev_hop_12m()
        if df.empty:
            return None, None
        try:
            df = df[df.get("finessGeoDP").astype(str) == str(hospital_id)]
        except Exception:
            return None, None
        if df.empty:
            return None, None
        row = df.iloc[0]
        region = None
        status = None
        for k in ["lib_reg", "region", "code_reg", "region_name"]:
            if k in row and pd.notna(row[k]) and str(row[k]).strip():
                region = str(row[k]).strip()
                break
        for k in ["statut", "status"]:
            if k in row and pd.notna(row[k]) and str(row[k]).strip():
                status = str(row[k]).strip()
                break
        return region, status

    @staticmethod
    def ensure_year_column(df: pd.DataFrame) -> pd.DataFrame:
        if df is None or df.empty:
            return pd.DataFrame()
        d = df.copy()
        if "year" not in d.columns and "annee" in d.columns:
            d["year"] = d["annee"]
        return d


