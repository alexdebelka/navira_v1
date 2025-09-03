from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional, Iterable, Set

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
    if gj_path and os.path.exists(gj_path):
        try:
            with open(gj_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    # Fallback: try remote download (simplifies setup)
    try:
        import requests  # local import to avoid hard dep if not used

        url = (
            os.environ.get("COMMUNES_GEOJSON_URL")
            or (st.secrets.get("geojson", {}).get("communes_url") if hasattr(st, "secrets") else None)
            or "https://france-geojson.gregoiredavid.fr/repo/communes.geojson"
        )
        r = requests.get(url, timeout=30)
        if r.ok:
            return r.json()
    except Exception:
        return None
    return None


@st.cache_data(show_spinner=False)
def load_communes_geojson_filtered(insee_codes: Iterable[str], path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    base = load_communes_geojson(path)
    if not base:
        return None
    codes: Set[str] = {str(c).strip().zfill(5) for c in insee_codes}
    key = detect_insee_key(base) or "code"
    feats = base.get("features", [])
    filtered = [f for f in feats if str(f.get("properties", {}).get(key, "")).zfill(5) in codes]
    if not filtered:
        return base  # nothing matched; return full to allow other joins
    return {"type": "FeatureCollection", "features": filtered}


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


