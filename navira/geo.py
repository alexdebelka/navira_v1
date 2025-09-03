"""
GeoJSON loading and INSEE key auto-detection utilities.

This module provides functionality for:
- Loading French communes GeoJSON from configurable paths
- Auto-detecting INSEE code property keys in GeoJSON features
- Caching and validation of geographic data
"""

import json
import os
import streamlit as st
from typing import Dict, Any, Optional, List
import logging


@st.cache_data
def load_communes_geojson(geojson_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Load French communes GeoJSON with configurable path.
    
    Args:
        geojson_path: Path to GeoJSON file. If None, tries multiple sources:
            1. st.secrets["COMMUNES_GEOJSON_PATH"] 
            2. Environment variable COMMUNES_GEOJSON_PATH
            3. Default paths: data/communes.geojson, data/communes-france.geojson
            
    Returns:
        Parsed GeoJSON dictionary or None if not found/invalid
        
    Notes:
        - Validates GeoJSON structure (type, features array)
        - Logs informative messages about data source and feature count
        - Returns None gracefully if file not found or invalid
    """
    # Determine GeoJSON path from multiple sources
    if geojson_path is None:
        # Try Streamlit secrets first
        try:
            geojson_path = st.secrets.get("COMMUNES_GEOJSON_PATH")
        except (AttributeError, FileNotFoundError):
            pass
        
        # Try environment variable
        if not geojson_path:
            geojson_path = os.environ.get("COMMUNES_GEOJSON_PATH")
        
        # Try default paths
        if not geojson_path:
            default_paths = [
                "data/communes.geojson",
                "data/communes-france.geojson", 
                "data/communes_france.geojson",
                "../data/communes.geojson",
                os.path.join(os.path.dirname(__file__), "..", "data", "communes.geojson")
            ]
            
            for path in default_paths:
                if os.path.exists(path):
                    geojson_path = path
                    break
    
    if not geojson_path:
        logging.warning("No GeoJSON path configured. Set COMMUNES_GEOJSON_PATH in secrets or environment.")
        return None
    
    if not os.path.exists(geojson_path):
        logging.warning(f"GeoJSON file not found: {geojson_path}")
        return None
    
    try:
        with open(geojson_path, 'r', encoding='utf-8') as f:
            geojson_data = json.load(f)
        
        # Validate GeoJSON structure
        if not isinstance(geojson_data, dict):
            logging.error("Invalid GeoJSON: root is not a dictionary")
            return None
            
        if geojson_data.get('type') != 'FeatureCollection':
            logging.error("Invalid GeoJSON: not a FeatureCollection")
            return None
            
        features = geojson_data.get('features', [])
        if not isinstance(features, list):
            logging.error("Invalid GeoJSON: features is not a list")
            return None
        
        logging.info(f"Loaded GeoJSON from {geojson_path} with {len(features)} features")
        return geojson_data
        
    except json.JSONDecodeError as e:
        logging.error(f"Invalid JSON in GeoJSON file {geojson_path}: {e}")
        return None
    except Exception as e:
        logging.error(f"Error loading GeoJSON from {geojson_path}: {e}")
        return None


@st.cache_data
def load_communes_geojson_filtered(needed_insee_codes: List[str]) -> Optional[Dict[str, Any]]:
    """
    Load GeoJSON filtered to only include specific INSEE codes for performance.
    
    Args:
        needed_insee_codes: List of INSEE codes to include in filtered GeoJSON
        
    Returns:
        Filtered GeoJSON dictionary or None if source not available
        
    Notes:
        - Reduces payload size by including only needed communes
        - Auto-detects INSEE property key before filtering
        - Returns full GeoJSON if no INSEE codes specified or detection fails
    """
    full_geojson = load_communes_geojson()
    
    if not full_geojson or not needed_insee_codes:
        return full_geojson
    
    insee_key = detect_insee_key(full_geojson)
    if not insee_key:
        logging.warning("Could not detect INSEE key for filtering, returning full GeoJSON")
        return full_geojson
    
    try:
        # Convert needed codes to set for faster lookup
        needed_set = set(str(code).zfill(5) for code in needed_insee_codes)
        
        filtered_features = []
        original_count = len(full_geojson['features'])
        
        for feature in full_geojson['features']:
            feature_insee = str(feature.get('properties', {}).get(insee_key, '')).zfill(5)
            if feature_insee in needed_set:
                filtered_features.append(feature)
        
        # Create filtered GeoJSON
        filtered_geojson = full_geojson.copy()
        filtered_geojson['features'] = filtered_features
        
        logging.info(f"Filtered GeoJSON from {original_count} to {len(filtered_features)} features")
        return filtered_geojson
        
    except Exception as e:
        logging.warning(f"Error filtering GeoJSON: {e}, returning full GeoJSON")
        return full_geojson


def detect_insee_key(geojson_data: Dict[str, Any]) -> Optional[str]:
    """
    Auto-detect INSEE code property key in GeoJSON features.
    
    Args:
        geojson_data: Parsed GeoJSON dictionary
        
    Returns:
        Property key name for INSEE codes, or None if not detected
        
    Algorithm:
        1. Checks common known keys: INSEE_COM, insee, code_insee, INSEE_CODE
        2. Scans first 10 features for properties with 5-digit numeric values
        3. Validates detected key by checking multiple features
        
    Notes:
        - Logs the detection process and chosen key
        - Prioritizes exact matches over pattern-based detection
        - Returns None if no plausible INSEE key found
    """
    if not geojson_data or 'features' not in geojson_data:
        return None
    
    features = geojson_data['features']
    if not features:
        return None
    
    # Known common INSEE property keys (in priority order)
    known_keys = ['INSEE_COM', 'insee', 'code_insee', 'INSEE_CODE', 'com_insee', 'codgeo']
    
    # Check for exact matches first
    sample_properties = features[0].get('properties', {})
    for key in known_keys:
        if key in sample_properties:
            # Validate that this key contains INSEE-like values
            if _validate_insee_key(features[:10], key):
                logging.info(f"Detected INSEE key by exact match: {key}")
                return key
    
    # Pattern-based detection: look for properties with 5-digit numeric values
    candidate_keys = []
    
    for feature in features[:10]:  # Sample first 10 features
        properties = feature.get('properties', {})
        for key, value in properties.items():
            if _looks_like_insee_code(value):
                candidate_keys.append(key)
    
    # Find most common candidate key
    if candidate_keys:
        from collections import Counter
        key_counts = Counter(candidate_keys)
        most_common_key = key_counts.most_common(1)[0][0]
        
        # Validate the candidate
        if _validate_insee_key(features[:20], most_common_key):
            logging.info(f"Detected INSEE key by pattern matching: {most_common_key}")
            return most_common_key
    
    logging.warning("Could not detect INSEE property key in GeoJSON")
    logging.debug(f"Sample properties: {list(sample_properties.keys())}")
    return None


def _looks_like_insee_code(value: Any) -> bool:
    """
    Check if a value looks like an INSEE code (5-digit string/number).
    
    Args:
        value: Property value to check
        
    Returns:
        True if value resembles an INSEE code
    """
    if value is None:
        return False
    
    # Convert to string and clean
    str_value = str(value).strip()
    
    # Check if it's 4-5 digits (INSEE codes are typically 5 digits, sometimes 4)
    if str_value.isdigit() and 4 <= len(str_value) <= 5:
        return True
    
    # Check if it's 5 digits when zero-padded
    if str_value.isdigit() and len(str_value.zfill(5)) == 5:
        return True
    
    return False


def _validate_insee_key(features: List[Dict[str, Any]], key: str) -> bool:
    """
    Validate that a property key consistently contains INSEE-like codes.
    
    Args:
        features: List of GeoJSON features to validate
        key: Property key to validate
        
    Returns:
        True if key appears to contain INSEE codes consistently
    """
    valid_count = 0
    total_count = 0
    
    for feature in features:
        properties = feature.get('properties', {})
        if key in properties:
            total_count += 1
            if _looks_like_insee_code(properties[key]):
                valid_count += 1
    
    # Require at least 70% of features to have INSEE-like values
    if total_count == 0:
        return False
    
    validation_rate = valid_count / total_count
    return validation_rate >= 0.7


def get_geojson_summary(geojson_data: Optional[Dict[str, Any]]) -> str:
    """
    Generate a summary description of loaded GeoJSON data.
    
    Args:
        geojson_data: Parsed GeoJSON dictionary or None
        
    Returns:
        Human-readable summary string
    """
    if not geojson_data:
        return "❌ No GeoJSON data available"
    
    features = geojson_data.get('features', [])
    feature_count = len(features)
    
    insee_key = detect_insee_key(geojson_data)
    insee_status = f"INSEE key: {insee_key}" if insee_key else "INSEE key: not detected"
    
    return f"✅ {feature_count:,} communes loaded | {insee_status}"
