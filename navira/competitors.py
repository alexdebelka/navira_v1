"""
Competitor analysis and choropleth generation for recruitment zones.

This module provides functionality for:
- Ranking competitors by patient volume
- Generating choropleth data with postal code to INSEE mapping
- Allocation strategies for handling many-to-many mapping
- Diagnostics for data quality assessment
"""

import pandas as pd
import streamlit as st
from typing import Dict, List, Tuple, Literal, NamedTuple
from .data_loaders import load_recruitment_data, load_competitors_data


class ChloroplethDiagnostics(NamedTuple):
    """Diagnostics information for choropleth data generation."""
    total_cps: int
    matched_cps: int  
    unmatched_cps: int
    unmatched_cp_examples: List[str]
    original_total: float
    allocated_total: float
    allocation_difference: float


@st.cache_data
def get_top_competitors(finess: str, n: int = 5) -> List[str]:
    """
    Get top N competitors for a given hospital FINESS code.
    
    Args:
        finess: 9-digit FINESS code of the focal hospital
        n: Number of top competitors to return (default 5)
        
    Returns:
        List of competitor FINESS codes, ranked by TOT_conc desc, TOT_etb desc
        
    Notes:
        - Ranking: primary by TOT_conc (descending), tie-break by TOT_etb (descending)
        - Returns empty list if no competitors found or data unavailable
    """
    try:
        competitors_df = load_competitors_data()
        
        if competitors_df.empty:
            return []
        
        # Ensure FINESS is properly formatted
        finess = str(finess).zfill(9)
        
        # Filter for focal hospital
        hospital_competitors = competitors_df[
            competitors_df['finessGeoDP'] == finess
        ].copy()
        
        if hospital_competitors.empty:
            return []
        
        # Sort by TOT_conc descending, then TOT_etb descending for tie-breaking
        hospital_competitors = hospital_competitors.sort_values(
            ['TOT_conc', 'TOT_etb'], 
            ascending=[False, False]
        )
        
        # Return top N competitor FINESS codes
        top_competitors = hospital_competitors['finessGeoDP_conc'].head(n).tolist()
        
        return top_competitors
        
    except Exception as e:
        st.warning(f"Error getting competitors for FINESS {finess}: {e}")
        return []


@st.cache_data
def competitor_choropleth_df(
    competitor_finess: str, 
    cp_to_insee: Dict[str, List[str]],
    allocation: Literal["even_split", "no_split"] = "even_split"
) -> Tuple[pd.DataFrame, ChloroplethDiagnostics]:
    """
    Generate choropleth dataframe for one competitor with postal code to INSEE mapping.
    
    Args:
        competitor_finess: 9-digit FINESS code of the competitor
        cp_to_insee: Mapping from postal code to list of INSEE codes
        allocation: Strategy for handling multiple INSEE codes per postal code
            - "even_split": divide patient count evenly among mapped INSEE codes
            - "no_split": assign full patient count to all mapped INSEE codes
            
    Returns:
        Tuple of:
        - DataFrame with columns: insee5, value (aggregated patient count per INSEE)
        - ChloroplethDiagnostics with mapping statistics and quality metrics
        
    Notes:
        - Input postal codes are mapped to INSEE codes using cp_to_insee
        - Final values are grouped by INSEE code and summed
        - Diagnostics track data quality and allocation accuracy
    """
    try:
        recruitment_df = load_recruitment_data()
        
        if recruitment_df.empty:
            empty_diag = ChloroplethDiagnostics(0, 0, 0, [], 0.0, 0.0, 0.0)
            return pd.DataFrame(columns=['insee5', 'value']), empty_diag
        
        # Ensure FINESS is properly formatted
        competitor_finess = str(competitor_finess).zfill(9)
        
        # Filter recruitment data for this competitor
        competitor_data = recruitment_df[
            recruitment_df['finessGeoDP'] == competitor_finess
        ].copy()
        
        if competitor_data.empty:
            empty_diag = ChloroplethDiagnostics(0, 0, 0, [], 0.0, 0.0, 0.0)
            return pd.DataFrame(columns=['insee5', 'value']), empty_diag
        
        # Calculate diagnostics
        total_cps = len(competitor_data)
        original_total = competitor_data['nb'].sum()
        
        # Map postal codes to INSEE codes
        mapped_rows = []
        unmatched_cps = []
        paris_debug = []
        
        for _, row in competitor_data.iterrows():
            postal_code = str(row['codeGeo']).zfill(5)
            patient_count = float(row['nb']) if pd.notna(row['nb']) else 0.0
            
            # Debug Paris data
            if postal_code.startswith('750'):
                paris_debug.append(f"{postal_code} -> {cp_to_insee.get(postal_code, 'NOT FOUND')}")
            
            if postal_code in cp_to_insee:
                insee_codes = cp_to_insee[postal_code]
                
                if allocation == "even_split":
                    # Divide patient count evenly among INSEE codes
                    alloc_value = patient_count / len(insee_codes) if insee_codes else 0.0
                    for insee in insee_codes:
                        mapped_rows.append({
                            'insee5': str(insee).zfill(5),
                            'value': alloc_value
                        })
                else:  # no_split
                    # Assign full patient count to all INSEE codes
                    for insee in insee_codes:
                        mapped_rows.append({
                            'insee5': str(insee).zfill(5), 
                            'value': patient_count
                        })
            else:
                unmatched_cps.append(postal_code)
        
        # Create result dataframe
        if mapped_rows:
            result_df = pd.DataFrame(mapped_rows)
            # Group by INSEE and sum values
            result_df = result_df.groupby('insee5')['value'].sum().reset_index()
        else:
            result_df = pd.DataFrame(columns=['insee5', 'value'])
        
        # Calculate final diagnostics
        matched_cps = total_cps - len(unmatched_cps)
        allocated_total = result_df['value'].sum() if not result_df.empty else 0.0
        allocation_diff = allocated_total - original_total
        
        # Limit unmatched examples for display
        unmatched_examples = unmatched_cps[:10]  # Show max 10 examples
        
        # Suppress Paris debug logs in production
        
        diagnostics = ChloroplethDiagnostics(
            total_cps=total_cps,
            matched_cps=matched_cps,
            unmatched_cps=len(unmatched_cps),
            unmatched_cp_examples=unmatched_examples,
            original_total=original_total,
            allocated_total=allocated_total,
            allocation_difference=allocation_diff
        )
        
        return result_df, diagnostics
        
    except Exception as e:
        st.warning(f"Error generating choropleth for competitor {competitor_finess}: {e}")
        empty_diag = ChloroplethDiagnostics(0, 0, 0, [], 0.0, 0.0, 0.0)
        return pd.DataFrame(columns=['insee5', 'value']), empty_diag


def format_diagnostics_summary(diag: ChloroplethDiagnostics) -> str:
    """
    Format diagnostics information for display.
    
    Args:
        diag: ChloroplethDiagnostics object
        
    Returns:
        Formatted string summary of diagnostics
    """
    if diag.total_cps == 0:
        return "No data available"
    
    match_rate = (diag.matched_cps / diag.total_cps) * 100 if diag.total_cps > 0 else 0
    
    summary = f"📊 {diag.matched_cps}/{diag.total_cps} postal codes mapped ({match_rate:.1f}%)"
    
    if diag.unmatched_cps > 0:
        summary += f" | ⚠️ {diag.unmatched_cps} unmatched"
        if diag.unmatched_cp_examples:
            examples = ", ".join(diag.unmatched_cp_examples[:3])
            if len(diag.unmatched_cp_examples) > 3:
                examples += "..."
            summary += f" (e.g., {examples})"
    
    # Check allocation accuracy (for even_split)
    if abs(diag.allocation_difference) > 0.01:  # Allow small floating point errors
        summary += f" | 📈 Total: {diag.original_total:.0f} → {diag.allocated_total:.0f}"
    
    return summary


def get_competitor_names(competitor_finess_list: List[str], establishments_df: pd.DataFrame) -> Dict[str, str]:
    """
    Get human-readable names for competitor FINESS codes.
    
    Args:
        competitor_finess_list: List of FINESS codes
        establishments_df: DataFrame with establishment information (must have 'id' and 'name' columns)
        
    Returns:
        Dictionary mapping FINESS -> hospital name
    """
    name_mapping = {}
    
    if establishments_df.empty or 'id' not in establishments_df.columns or 'name' not in establishments_df.columns:
        # Fallback to FINESS codes
        for finess in competitor_finess_list:
            name_mapping[finess] = f"Hospital {finess}"
        return name_mapping
    
    # Ensure FINESS codes are properly formatted for matching
    establishments_copy = establishments_df.copy()
    establishments_copy['id'] = establishments_copy['id'].astype(str).str.zfill(9)
    
    for finess in competitor_finess_list:
        finess_formatted = str(finess).zfill(9)
        matching_rows = establishments_copy[establishments_copy['id'] == finess_formatted]
        
        if not matching_rows.empty:
            name = matching_rows.iloc[0]['name']
            # Truncate long names for display
            if len(str(name)) > 40:
                name = str(name)[:37] + "..."
            name_mapping[finess] = str(name)
        else:
            name_mapping[finess] = f"Hospital {finess}"
    
    return name_mapping
