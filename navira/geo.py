"""
GeoJSON loading and INSEE key auto-detection utilities.

This module provides functionality for:
- Loading French communes GeoJSON from configurable paths
- Auto-detecting INSEE code property keys in GeoJSON features
- Caching and validation of geographic data
"""

import json
import os
import gzip
import streamlit as st
from typing import Dict, Any, Optional, List, Tuple
import logging
from pathlib import Path
import pandas as pd


@st.cache_data(show_spinner=False)
def load_communes_geojson(path_override: Optional[str] = None, cache_version: str = "v2") -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    """
    Load French communes GeoJSON with robust path resolution and diagnostics.
    
    Args:
        path_override: Optional explicit path to GeoJSON file
        cache_version: Version string for cache invalidation
            
    Returns:
        Tuple of (geojson_dict | None, diagnostics_dict)
        
    Resolution order:
        1. path_override argument
        2. st.secrets["paths"]["communes_geojson"]
        3. os.environ["COMMUNES_GEOJSON_PATH"]
        4. Default paths: data/communes.geojson, data/communes.geojson.gz
    """
    diagnostics = {
        "resolved_path": None,
        "file_size": 0,
        "feature_count": 0,
        "sample_properties": [],
        "insee_key": None,
        "errors": [],
        "attempted_paths": []
    }
    
    # Determine GeoJSON path with robust resolution
    geojson_path = None
    
    # 1. Explicit path override
    if path_override:
        geojson_path = path_override
        diagnostics["attempted_paths"].append(f"explicit: {path_override}")
    
    # 2. Streamlit secrets
    if not geojson_path:
        try:
            geojson_path = st.secrets.get("paths", {}).get("communes_geojson")
            if geojson_path:
                diagnostics["attempted_paths"].append(f"secrets: {geojson_path}")
        except (AttributeError, FileNotFoundError, KeyError):
            pass
        
    # 3. Environment variable
    if not geojson_path:
        geojson_path = os.environ.get("COMMUNES_GEOJSON_PATH")
        if geojson_path:
            diagnostics["attempted_paths"].append(f"env: {geojson_path}")
        
    # 4. Default paths (including gzipped)
    if not geojson_path:
        default_paths = [
            "data/communes.geojson",
            "data/communes.geojson.gz",
            "data/communes-france.geojson", 
            "data/communes_france.geojson",
            "../data/communes.geojson",
            os.path.join(os.path.dirname(__file__), "..", "data", "communes.geojson")
        ]
        
        for path in default_paths:
            diagnostics["attempted_paths"].append(f"default: {path}")
            if os.path.exists(path):
                geojson_path = path
                break
    
    if not geojson_path:
        diagnostics["errors"].append("No GeoJSON path found in any resolution method")
        return None, diagnostics
    
    diagnostics["resolved_path"] = os.path.abspath(geojson_path)
    
    if not os.path.exists(geojson_path):
        diagnostics["errors"].append(f"File not found: {geojson_path}")
        return None, diagnostics
    
    try:
        # Get file size for diagnostics
        diagnostics["file_size"] = os.path.getsize(geojson_path)
        
        # Load GeoJSON (handle both regular and gzipped files)
        if geojson_path.endswith('.gz'):
            with gzip.open(geojson_path, 'rt', encoding='utf-8') as f:
                geojson_data = json.load(f)
        else:
            with open(geojson_path, 'r', encoding='utf-8') as f:
                geojson_data = json.load(f)
        
        # Validate GeoJSON structure
        if not isinstance(geojson_data, dict):
            diagnostics["errors"].append("Invalid GeoJSON: root is not a dictionary")
            return None, diagnostics
            
        if geojson_data.get('type') != 'FeatureCollection':
            diagnostics["errors"].append("Invalid GeoJSON: not a FeatureCollection")
            return None, diagnostics
            
        features = geojson_data.get('features', [])
        if not isinstance(features, list):
            diagnostics["errors"].append("Invalid GeoJSON: features is not a list")
            return None, diagnostics
        
        diagnostics["feature_count"] = len(features)
        
        # Extract sample properties for diagnostics
        if features:
            sample_props = features[0].get('properties', {})
            diagnostics["sample_properties"] = list(sample_props.keys())[:10]
            
            # Auto-detect INSEE key
            diagnostics["insee_key"] = detect_insee_property(geojson_data)
        
        return geojson_data, diagnostics
        
    except json.JSONDecodeError as e:
        diagnostics["errors"].append(f"Invalid JSON: {str(e)}")
        return None, diagnostics
    except Exception as e:
        diagnostics["errors"].append(f"Loading error: {str(e)}")
        return None, diagnostics


@st.cache_data(show_spinner=False)
def load_communes_geojson_filtered(needed_insee_codes: List[str], cache_version: str = "v2") -> Optional[Dict[str, Any]]:
    """
    Load GeoJSON filtered to only include specific INSEE codes for performance.
    
    Args:
        needed_insee_codes: List of INSEE codes to include in filtered GeoJSON
        cache_version: Version string for cache invalidation
        
    Returns:
        Filtered GeoJSON dictionary or None if source not available
        
    Notes:
        - Reduces payload size by including only needed communes
        - Auto-detects INSEE property key before filtering
        - Returns full GeoJSON if no INSEE codes specified or detection fails
    """
    full_geojson, _ = load_communes_geojson()
    
    if not full_geojson or not needed_insee_codes:
        return full_geojson
    
    insee_key = detect_insee_property(full_geojson)
    if not insee_key:
        return full_geojson
    
    try:
        # Convert needed codes to set for faster lookup (handle Corsica codes)
        needed_set = set()
        for code in needed_insee_codes:
            code_str = str(code).strip().upper()
            if code_str.startswith('2A') or code_str.startswith('2B'):
                needed_set.add(code_str)
            else:
                needed_set.add(code_str.zfill(5))
        
        filtered_features = []
        original_count = len(full_geojson['features'])
        
        for feature in full_geojson['features']:
            props = feature.get('properties', {})
            if insee_key in props:
                feature_insee = str(props[insee_key]).strip().upper()
                if feature_insee.startswith('2A') or feature_insee.startswith('2B'):
                    if feature_insee in needed_set:
                        filtered_features.append(feature)
                else:
                    if feature_insee.zfill(5) in needed_set:
                        filtered_features.append(feature)
        
        # Create filtered GeoJSON
        filtered_geojson = full_geojson.copy()
        filtered_geojson['features'] = filtered_features
        
        return filtered_geojson
        
    except Exception as e:
        return full_geojson


def detect_insee_property(geojson_dict: Dict[str, Any]) -> Optional[str]:
    """
    Auto-detect INSEE code property key in GeoJSON features with comprehensive validation.
    
    Args:
        geojson_dict: Parsed GeoJSON dictionary
        
    Returns:
        Property key name for INSEE codes, or None if not detected
        
    Algorithm:
        1. Prioritizes exact matches of common keys
        2. Uses regex pattern matching for broader detection
        3. Validates coverage (≥90% of features have valid INSEE codes)
        4. Handles Corsica codes (2A/2B) gracefully
    """
    if not geojson_dict or 'features' not in geojson_dict:
        return None
    
    features = geojson_dict['features']
    if not features:
        return None
    
    import re
    from collections import Counter
    
    # Known common INSEE property keys (in priority order)
    known_keys = ['code', 'INSEE_COM', 'insee', 'code_insee', 'INSEE_CODE', 'com_insee', 'codgeo']
    
    # Check for exact matches first
    sample_properties = features[0].get('properties', {})
    for key in known_keys:
        if key in sample_properties:
            # Validate that this key contains INSEE-like values
            if _validate_insee_property_coverage(features, key):
                return key
    
    # Pattern-based detection using regex
    insee_pattern = re.compile(r'^(INSEE.*|code(_)?insee|codgeo)$', re.IGNORECASE)
    candidate_keys = []
    
    # Scan property keys across multiple features
    for feature in features[:20]:  # Sample more features for better detection
        properties = feature.get('properties', {})
        for key in properties.keys():
            if insee_pattern.match(key):
                candidate_keys.append(key)
    
    # Find most common candidate key
    if candidate_keys:
        key_counts = Counter(candidate_keys)
        for key, count in key_counts.most_common():
            # Validate the candidate has good coverage
            if _validate_insee_property_coverage(features, key):
                return key
    
    # Fallback: look for any property with INSEE-like values
    for key in sample_properties.keys():
        if _validate_insee_property_coverage(features, key):
            return key
    
    return None


# Backward compatibility functions
def detect_insee_key(geojson_data: Dict[str, Any]) -> Optional[str]:
    """Backward compatibility wrapper for detect_insee_property."""
    return detect_insee_property(geojson_data)


def _validate_insee_property_coverage(features: List[Dict[str, Any]], key: str, min_coverage: float = 0.9) -> bool:
    """
    Validate that a property key consistently contains INSEE-like codes across features.
    
    Args:
        features: List of GeoJSON features to validate
        key: Property key to validate
        min_coverage: Minimum fraction of features that must have valid INSEE codes
        
    Returns:
        True if key has sufficient coverage of valid INSEE codes
    """
    if not features:
        return False
        
    valid_count = 0
    total_count = len(features)
    
    for feature in features:
        properties = feature.get('properties', {})
        if key in properties:
            if _is_valid_insee_code(properties[key]):
                valid_count += 1
    
    coverage = valid_count / total_count if total_count > 0 else 0
    return coverage >= min_coverage


def _is_valid_insee_code(value: Any) -> bool:
    """
    Check if a value is a valid INSEE commune code.
    
    Args:
        value: Property value to check
        
    Returns:
        True if value is a valid INSEE code
        
    Notes:
        - Handles regular 5-digit codes (01001-99999)
        - Handles Corsica codes (2A001-2A999, 2B001-2B999)
        - Allows both string and numeric input
    """
    if value is None:
        return False
    
    # Convert to string and clean
    str_value = str(value).strip().upper()
    
    # Handle Corsica codes (2A/2B prefix)
    if str_value.startswith('2A') or str_value.startswith('2B'):
        if len(str_value) == 5 and str_value[2:].isdigit():
            return True
    
    # Handle regular numeric codes
    if str_value.isdigit():
        # Must be 4-5 digits (zero-pad to 5 for validation)
        if 1 <= len(str_value) <= 5:
            padded = str_value.zfill(5)
            # Basic range check (01001-99999, excluding some invalid ranges)
            code_num = int(padded)
            return 1001 <= code_num <= 99999
    
    return False


def validate_choropleth_inputs(df: pd.DataFrame, insee_col: str, geojson: Dict[str, Any], insee_key: str) -> Dict[str, Any]:
    """
    Validate that DataFrame and GeoJSON can be properly joined for choropleth mapping.
    
    Args:
        df: DataFrame with INSEE codes and values
        insee_col: Column name in df containing INSEE codes
        geojson: GeoJSON dictionary
        insee_key: Property key in GeoJSON containing INSEE codes
        
    Returns:
        Dictionary with validation results and diagnostics
    """
    diagnostics = {
        "df_rows": len(df),
        "df_unique_insee": 0,
        "geo_features": 0,
        "geo_unique_insee": 0,
        "intersection_count": 0,
        "coverage_pct": 0.0,
        "missing_from_geo": [],
        "missing_from_df": [],
        "errors": [],
        "warnings": []
    }
    
    try:
        # Validate inputs
        if df.empty:
            diagnostics["errors"].append("DataFrame is empty")
            return diagnostics
            
        if insee_col not in df.columns:
            diagnostics["errors"].append(f"Column '{insee_col}' not found in DataFrame")
            return diagnostics
        
        if not geojson or 'features' not in geojson:
            diagnostics["errors"].append("Invalid or empty GeoJSON")
            return diagnostics
            
        features = geojson.get('features', [])
        diagnostics["geo_features"] = len(features)
        
        if not features:
            diagnostics["errors"].append("GeoJSON has no features")
            return diagnostics
        
        # Normalize INSEE codes to strings with zero-padding
        df_insee_codes = set()
        for code in df[insee_col].dropna():
            normalized = str(code).strip().zfill(5)
            # Handle Corsica codes
            if normalized.startswith('2A') or normalized.startswith('2B'):
                df_insee_codes.add(normalized.upper())
            else:
                df_insee_codes.add(normalized)
        
        diagnostics["df_unique_insee"] = len(df_insee_codes)
        
        # Extract INSEE codes from GeoJSON
        geo_insee_codes = set()
        for feature in features:
            props = feature.get('properties', {})
            if insee_key in props:
                code = str(props[insee_key]).strip().upper()
                if code.startswith('2A') or code.startswith('2B'):
                    geo_insee_codes.add(code)
                else:
                    geo_insee_codes.add(code.zfill(5))
        
        diagnostics["geo_unique_insee"] = len(geo_insee_codes)
        
        # Calculate intersection and coverage
        intersection = df_insee_codes & geo_insee_codes
        diagnostics["intersection_count"] = len(intersection)
        
        if len(df_insee_codes) > 0:
            diagnostics["coverage_pct"] = (len(intersection) / len(df_insee_codes)) * 100
        
        # Find missing codes (limit to top 10 for readability)
        missing_from_geo = list(df_insee_codes - geo_insee_codes)[:10]
        missing_from_df = list(geo_insee_codes - df_insee_codes)[:10]
        
        diagnostics["missing_from_geo"] = missing_from_geo
        diagnostics["missing_from_df"] = missing_from_df
        
        # Generate warnings/errors based on coverage
        if diagnostics["coverage_pct"] < 5:
            diagnostics["errors"].append(
                f"Very low join coverage ({diagnostics['coverage_pct']:.1f}%). "
                f"Only {len(intersection)} out of {len(df_insee_codes)} codes match. "
                f"Check INSEE code format and GeoJSON property key."
            )
        elif diagnostics["coverage_pct"] < 50:
            diagnostics["warnings"].append(
                f"Low join coverage ({diagnostics['coverage_pct']:.1f}%). "
                f"Consider checking INSEE code formats."
            )
        
        if missing_from_geo:
            diagnostics["warnings"].append(
                f"Example codes in DataFrame not found in GeoJSON: {missing_from_geo[:5]}"
            )
            
    except Exception as e:
        diagnostics["errors"].append(f"Validation error: {str(e)}")
    
    return diagnostics


def get_geojson_summary(geojson_data: Optional[Dict[str, Any]], diagnostics: Optional[Dict[str, Any]] = None) -> str:
    """
    Generate a summary description of loaded GeoJSON data.
    
    Args:
        geojson_data: Parsed GeoJSON dictionary or None
        diagnostics: Optional diagnostics dictionary from load_communes_geojson
        
    Returns:
        Human-readable summary string
    """
    if not geojson_data:
        if diagnostics and diagnostics.get("errors"):
            return f"❌ {diagnostics['errors'][0]}"
        return "❌ No GeoJSON data available"
    
    if diagnostics:
        feature_count = diagnostics.get("feature_count", 0)
        insee_key = diagnostics.get("insee_key", "not detected")
        file_size_mb = diagnostics.get("file_size", 0) / (1024 * 1024)
        
        return f"✅ {feature_count:,} communes loaded ({file_size_mb:.1f}MB) | INSEE key: {insee_key}"
    else:
        # Fallback for backward compatibility
        features = geojson_data.get('features', [])
        feature_count = len(features)
        
        insee_key = detect_insee_key(geojson_data)
        insee_status = insee_key if insee_key else "not detected"
        
        return f"✅ {feature_count:,} communes loaded | INSEE key: {insee_status}"
