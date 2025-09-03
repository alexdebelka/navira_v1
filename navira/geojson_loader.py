from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional

import streamlit as st


@st.cache_data(show_spinner=False)
def load_communes_geojson(path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Load communes geojson from a local path.

    Resolution order:
    1) explicit path arg
    2) env var COMMUNES_GEOJSON_PATH
    3) st.secrets["geojson"]["communes_path"] if present
    4) data/communes.geojson (relative)
    """
    gj_path = (
        path
        or os.environ.get("COMMUNES_GEOJSON_PATH")
        or (st.secrets.get("geojson", {}).get("communes_path") if hasattr(st, "secrets") else None)
        or os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "communes.geojson")
    )
    if not gj_path or not os.path.exists(gj_path):
        return None
    try:
        with open(gj_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def detect_insee_key(geojson: Dict[str, Any]) -> Optional[str]:
    """Detect the property name that contains the INSEE commune code.

    Common keys: INSEE_COM, code, insee, CODE_INSEE
    """
    try:
        feats = geojson.get("features", [])
        if not feats:
            return None
        candidate_keys = [
            "INSEE_COM",
            "code",
            "insee",
            "CODE_INSEE",
            "insee_com",
            "INSEE",
        ]
        props = feats[0].get("properties", {})
        for k in candidate_keys:
            if k in props:
                return k
        # last-resort: heuristic - first property with length 5 and digits
        for k, v in props.items():
            try:
                s = str(v).strip()
                if len(s) == 5 and s.isdigit():
                    return k
            except Exception:
                continue
        return None
    except Exception:
        return None


