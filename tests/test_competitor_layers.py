import os
import pandas as pd

from navira.competitor_layers import (
    _to_str_zfill,
    competitor_choropleth_df,
)


def test_to_str_zfill():
    s = pd.Series([1, "23", "004", " 5 "])
    out = _to_str_zfill(s, 3)
    assert out.tolist() == ["001", "023", "004", "005"]


def test_even_split_aggregation(tmp_path):
    # Build tiny recruitment CSV
    rec_path = tmp_path / "rec.csv"
    rec = pd.DataFrame(
        {
            "finessGeoDP": ["000000001", "000000001"],
            "codeGeo": ["75001", "75001"],
            "nb": [10, 20],
        }
    )
    rec.to_csv(rec_path, sep=";", index=False)

    # cp->insee mapping (75001 maps to two communes)
    cp_map = {"75001": ["75056", "75101"]}

    df, diag = competitor_choropleth_df(str(rec_path), "000000001", cp_map, allocation="even_split")
    # Total nb = 30, split across 2 => alloc sum still 30
    assert abs(df["value"].sum() - 30.0) < 1e-6


