import os
import pandas as pd


def _find_path(name: str) -> str:
    candidates = [
        os.path.join("data", "processed", name),
        os.path.join("data", name),
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    return candidates[0]


def test_parquet_files_exist():
    assert os.path.exists(_find_path("establishments.parquet"))
    assert os.path.exists(_find_path("annual_procedures.parquet"))


def test_establishments_has_id_and_name():
    df = pd.read_parquet(_find_path("establishments.parquet"))
    for col in ["id", "name"]:
        assert col in df.columns
    assert df["id"].nunique() == len(df["id"])  # unique ids


def test_annual_has_core_cols():
    df = pd.read_parquet(_find_path("annual_procedures.parquet"))
    for col in ["id", "annee", "total_procedures_year"]:
        assert col in df.columns


