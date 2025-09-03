"""
Cache utility functions for debugging and management.
"""

import hashlib
import pandas as pd
import streamlit as st
from typing import Dict, Any


def dataframe_md5(df: pd.DataFrame) -> str:
    """Generate MD5 hash of DataFrame content for cache key generation."""
    try:
        return hashlib.md5(df.to_csv(index=False).encode()).hexdigest()
    except Exception:
        return "error_hash"


def debug_dataframe_signature(df: pd.DataFrame, label: str = "") -> Dict[str, Any]:
    """Generate debug signature for DataFrame content tracing."""
    try:
        if df is None or df.empty:
            return {
                'label': label,
                'n_rows': 0,
                'n_cols': 0,
                'hash': 'empty',
                'columns': []
            }
        
        return {
            'label': label,
            'n_rows': len(df),
            'n_cols': len(df.columns),
            'hash': dataframe_md5(df)[:8],  # First 8 chars for brevity
            'columns': list(df.columns)[:10],  # First 10 columns
            'sample_values': {
                col: df[col].iloc[0] if len(df) > 0 else None 
                for col in df.columns[:3]  # First 3 columns
            }
        }
    except Exception as e:
        return {
            'label': label,
            'error': str(e),
            'hash': 'error'
        }


def clear_all_caches():
    """Clear all Streamlit caches."""
    try:
        st.cache_data.clear()
        if hasattr(st, 'cache_resource'):
            st.cache_resource.clear()
        return True
    except Exception as e:
        st.error(f"Error clearing caches: {e}")
        return False


def show_debug_panel(signatures: Dict[str, Dict[str, Any]], expanded: bool = False):
    """Display debug information in an expandable panel."""
    with st.expander("🔧 KM Debug Information", expanded=expanded):
        st.markdown("**Data Signatures:**")
        
        for step_name, sig in signatures.items():
            st.markdown(f"**{step_name}:**")
            
            if 'error' in sig:
                st.error(f"Error: {sig['error']}")
            else:
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Rows", sig.get('n_rows', 0))
                with col2:
                    st.metric("Hash", sig.get('hash', 'N/A'))
                with col3:
                    if 'sample_values' in sig:
                        st.json(sig['sample_values'])
            
            st.markdown("---")
        
        if st.button("🗑️ Clear All Caches"):
            if clear_all_caches():
                st.success("Caches cleared! Please refresh the page.")
                st.rerun()
            else:
                st.error("Failed to clear caches.")


def create_cache_key(*args, **kwargs) -> str:
    """Create a deterministic cache key from arguments."""
    key_parts = []
    
    # Add positional args
    for arg in args:
        if isinstance(arg, pd.DataFrame):
            key_parts.append(dataframe_md5(arg))
        else:
            key_parts.append(str(arg))
    
    # Add keyword args
    for k, v in sorted(kwargs.items()):
        if isinstance(v, pd.DataFrame):
            key_parts.append(f"{k}={dataframe_md5(v)}")
        else:
            key_parts.append(f"{k}={v}")
    
    # Create hash of combined key
    combined = "|".join(key_parts)
    return hashlib.md5(combined.encode()).hexdigest()[:16]
