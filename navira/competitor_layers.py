from __future__ import annotations

import os
from typing import Dict, Iterable, List, Literal, Optional, Tuple

import pandas as pd
import streamlit as st


AllocationMode = Literal["even_split", "no_split"]


def _to_str_zfill(series: pd.Series, width: int) -> pd.Series:
    s = series.astype(str).str.strip()
    return s.str.replace(".0$", "", regex=True).str.zfill(width)


@st.cache_data(show_spinner=False)
def load_recruitment_csv(path: str) -> pd.DataFrame:
    encodings = ["utf-8", "cp1252", "latin1"]
    last_err: Optional[Exception] = None
    for enc in encodings:
        try:
            df = pd.read_csv(path, sep=";", encoding=enc)
            # Normalize columns
            if "finessGeoDP" in df.columns:
                df = df.rename(columns={"finessGeoDP": "finess"})
            if "codeGeo" in df.columns:
                df = df.rename(columns={"codeGeo": "postal"})
            if "nb" in df.columns:
                df = df.rename(columns={"nb": "nb_patients"})
            # Types
            if "finess" in df.columns:
                df["finess"] = _to_str_zfill(df["finess"], 9)
            if "postal" in df.columns:
                df["postal"] = _to_str_zfill(df["postal"], 5)
            # Handle comma decimals on PCT cols if present
            for col in ["PCT", "PCT_CUM"]:
                if col in df.columns and df[col].dtype == object:
                    df[col] = (
                        df[col]
                        .astype(str)
                        .str.replace(",", ".", regex=False)
                        .str.replace("%", "", regex=False)
                    )
                    df[col] = pd.to_numeric(df[col], errors="coerce")
            if "nb_patients" in df.columns:
                df["nb_patients"] = pd.to_numeric(df["nb_patients"], errors="coerce").fillna(0.0)
            return df
        except Exception as e:  # pragma: no cover - exercised in production
            last_err = e
            continue
    if last_err:
        raise last_err
    return pd.DataFrame()


@st.cache_data(show_spinner=False)
def load_competitors_csv(path: str) -> pd.DataFrame:
    encodings = ["utf-8", "cp1252", "latin1"]
    last_err: Optional[Exception] = None
    for enc in encodings:
        try:
            df = pd.read_csv(path, sep=";", encoding=enc)
            # Normalize
            df = df.rename(
                columns={
                    "finessGeoDP": "hospital_id",
                    "finessGeoDP_conc": "competitor_id",
                    "TOT_conc": "competitor_patients",
                    "TOT_etb": "hospital_patients",
                }
            )
            for col in ["hospital_id", "competitor_id"]:
                if col in df.columns:
                    df[col] = _to_str_zfill(df[col], 9)
            for col in ["competitor_patients", "hospital_patients"]:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
            return df
        except Exception as e:  # pragma: no cover
            last_err = e
            continue
    if last_err:
        raise last_err
    return pd.DataFrame()


@st.cache_data(show_spinner=False)
def load_communes_csv(path: str) -> pd.DataFrame:
    df = pd.read_csv(path, sep=";", encoding="utf-8", decimal=",")
    df = df.rename(
        columns={
            "codeInsee": "insee",
            "codePostal": "postal",
            "nomCommune": "name",
        }
    )
    df["insee"] = _to_str_zfill(df["insee"], 5)
    df["postal"] = _to_str_zfill(df["postal"], 5)
    return df[["insee", "postal", "name", "latitude", "longitude"]]


@st.cache_data(show_spinner=False)
def build_cp_to_insee(communes_csv_path: str) -> Dict[str, List[str]]:
    cities = load_communes_csv(communes_csv_path)
    mapping: Dict[str, List[str]] = {}
    for postal, group in cities.groupby("postal"):
        mapping[postal] = group["insee"].dropna().astype(str).tolist()
    return mapping


@st.cache_data(show_spinner=False)
def get_top_competitors(
    competitors_csv_path: str, finess: str, n: int = 5
) -> List[str]:
    finess9 = str(finess).strip().zfill(9)
    comp = load_competitors_csv(competitors_csv_path)
    if comp.empty:
        return []
    filt = comp[comp["hospital_id"] == finess9].copy()
    if filt.empty:
        return []
    filt = filt.sort_values(
        by=["competitor_patients", "hospital_patients"], ascending=[False, False]
    )
    return filt["competitor_id"].dropna().astype(str).head(n).tolist()


@st.cache_data(show_spinner=False)
def competitor_choropleth_df(
    recruitment_csv_path: str,
    competitor_finess: str,
    cp_to_insee: Dict[str, List[str]],
    allocation: AllocationMode = "even_split",
) -> Tuple[pd.DataFrame, Dict[str, object]]:
    comp9 = str(competitor_finess).strip().zfill(9)
    rec = load_recruitment_csv(recruitment_csv_path)
    rec = rec[rec["finess"] == comp9].copy()
    if rec.empty:
        return pd.DataFrame(columns=["insee5", "value"]), {
            "rows": 0,
            "cp_missing": 0,
            "cp_unmapped": [],
            "total_nb": 0.0,
            "total_alloc": 0.0,
        }

    total_nb = float(rec["nb_patients"].sum())
    rec["cp"] = rec["postal"].astype(str)

    # Map postal to insee list
    rec["insee_list"] = rec["cp"].map(lambda cp: cp_to_insee.get(cp, []))
    unmapped = rec[rec["insee_list"].map(len) == 0]["cp"].unique().tolist()

    # Explode mapping
    exploded = rec.explode("insee_list")
    exploded = exploded.dropna(subset=["insee_list"]).copy()
    exploded["insee5"] = exploded["insee_list"].astype(str).str.zfill(5)

    if allocation == "no_split":
        exploded["alloc"] = exploded["nb_patients"].astype(float)
    else:
        # even_split
        counts = (
            rec.assign(num_insee=rec["insee_list"].map(len))[["cp", "num_insee"]]
            .drop_duplicates()
            .set_index("cp")
        )
        exploded = exploded.join(counts, on="cp")
        exploded["num_insee"] = exploded["num_insee"].replace(0, 1)
        exploded["alloc"] = exploded["nb_patients"].astype(float) / exploded[
            "num_insee"
        ]

    agg = (
        exploded.groupby("insee5", as_index=False)["alloc"].sum().rename(columns={"alloc": "value"})
    )
    diagnostics = {
        "rows": int(len(rec)),
        "cp_missing": int(len(unmapped)),
        "cp_unmapped": unmapped[:10],
        "total_nb": float(total_nb),
        "total_alloc": float(agg["value"].sum()),
    }
    return agg, diagnostics


