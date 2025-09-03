"""
Pure Kaplan-Meier computation module.
Eliminates global state reuse and provides consistent, debuggable KM curves.
"""

import pandas as pd
import numpy as np
import hashlib
from typing import List, Optional, Dict, Any, Literal
import plotly.graph_objects as go
import streamlit as st


def dataframe_md5(df: pd.DataFrame) -> str:
    """Generate MD5 hash of DataFrame content for cache key generation."""
    return hashlib.md5(df.to_csv(index=False).encode()).hexdigest()


def debug_signature(df: pd.DataFrame, *args, **kwargs) -> Dict[str, Any]:
    """Generate debug signature for KM computation tracing."""
    try:
        n_rows = len(df)
        # Try to find event/complication columns
        event_cols = [col for col in df.columns if any(term in col.lower() for term in ['comp', 'event', 'hazard'])]
        n_events = df[event_cols[0]].sum() if event_cols else 0
        
        # Find time-related columns
        time_cols = [col for col in df.columns if any(term in col.lower() for term in ['time', 'date', 'year', 'quarter', 'semester', 'label'])]
        intervals = sorted(df[time_cols[0]].unique()) if time_cols else []
        
        return {
            'n_rows': n_rows,
            'n_events': int(n_events) if pd.notna(n_events) else 0,
            'intervals': intervals[:10],  # First 10 for brevity
            'hash': dataframe_md5(df),
            'args': str(args),
            'kwargs': str(kwargs)
        }
    except Exception as e:
        return {
            'n_rows': len(df) if df is not None else 0,
            'n_events': 0,
            'intervals': [],
            'hash': 'error',
            'error': str(e),
            'args': str(args),
            'kwargs': str(kwargs)
        }


@st.cache_data(show_spinner=False)
def compute_km_from_aggregates(
    df: pd.DataFrame,
    time_col: str,           # e.g., "semester_label" or "quarter"
    event_col: str,          # e.g., "comp" (events in interval)
    at_risk_col: str,        # e.g., "n" (denominator in interval)
    group_cols: Optional[List[str]] = None,   # e.g., ["finessGeoDP"] or None for national
    time_order: Optional[List[str]] = None,   # explicit order of discrete times
    data_hash: Optional[str] = None,  # For cache invalidation
    cache_version: str = "v1"
) -> pd.DataFrame:
    """
    Pure KM computation from aggregate data.
    
    Returns tidy DataFrame with columns:
      group (or 'ALL'), time, at_risk, events, hazard, survival
    Uses product-limit estimator: S_t = Π (1 - d_i / n_i) in time order.
    """
    # Always work on a deep copy to avoid mutation
    df_work = df.copy(deep=True)
    
    # Validate required columns
    required_cols = [time_col, event_col, at_risk_col]
    if group_cols:
        required_cols.extend(group_cols)
    
    missing_cols = [col for col in required_cols if col not in df_work.columns]
    if missing_cols:
        raise ValueError(f"Missing required columns: {missing_cols}")
    
    # Ensure numeric columns
    df_work[event_col] = pd.to_numeric(df_work[event_col], errors='coerce').fillna(0)
    df_work[at_risk_col] = pd.to_numeric(df_work[at_risk_col], errors='coerce').fillna(0)
    
    # Remove rows with zero at-risk (can't compute hazard)
    df_work = df_work[df_work[at_risk_col] > 0].copy()
    
    if df_work.empty:
        return pd.DataFrame(columns=['group', 'time', 'at_risk', 'events', 'hazard', 'survival'])
    
    # Determine time ordering
    if time_order is None:
        # Try to sort intelligently
        if df_work[time_col].dtype in ['object', 'string']:
            # For string times, sort naturally
            time_order = sorted(df_work[time_col].unique())
        else:
            time_order = sorted(df_work[time_col].unique())
    
    # Group processing
    if group_cols:
        # Multi-group KM
        results = []
        for group_vals, group_df in df_work.groupby(group_cols):
            group_name = str(group_vals) if len(group_cols) == 1 else "_".join(map(str, group_vals))
            km_result = _compute_single_group_km(group_df, time_col, event_col, at_risk_col, time_order, group_name)
            results.append(km_result)
        
        if results:
            return pd.concat(results, ignore_index=True)
        else:
            return pd.DataFrame(columns=['group', 'time', 'at_risk', 'events', 'hazard', 'survival'])
    else:
        # Single group (national)
        return _compute_single_group_km(df_work, time_col, event_col, at_risk_col, time_order, 'ALL')


def _compute_single_group_km(
    df: pd.DataFrame, 
    time_col: str, 
    event_col: str, 
    at_risk_col: str, 
    time_order: List[str], 
    group_name: str
) -> pd.DataFrame:
    """Compute KM for a single group."""
    # Aggregate by time (in case of duplicates)
    agg_df = df.groupby(time_col, as_index=False).agg({
        event_col: 'sum',
        at_risk_col: 'sum'
    })
    
    # Ensure all time points are present (fill missing with 0 events)
    time_df = pd.DataFrame({time_col: time_order})
    agg_df = time_df.merge(agg_df, on=time_col, how='left')
    agg_df[event_col] = agg_df[event_col].fillna(0)
    agg_df[at_risk_col] = agg_df[at_risk_col].fillna(0)
    
    # Remove time points with no at-risk population
    agg_df = agg_df[agg_df[at_risk_col] > 0].copy()
    
    if agg_df.empty:
        return pd.DataFrame(columns=['group', 'time', 'at_risk', 'events', 'hazard', 'survival'])
    
    # Sort by time order
    time_to_order = {time: i for i, time in enumerate(time_order)}
    agg_df['_order'] = agg_df[time_col].map(time_to_order)
    agg_df = agg_df.sort_values('_order').drop('_order', axis=1)
    
    # Compute hazard and survival
    agg_df['hazard'] = agg_df[event_col] / agg_df[at_risk_col]
    agg_df['survival'] = (1 - agg_df['hazard']).cumprod()
    
    # Add group identifier
    agg_df['group'] = group_name
    
    # Rename columns for consistency
    result_df = agg_df.rename(columns={
        time_col: 'time',
        event_col: 'events',
        at_risk_col: 'at_risk'
    })
    
    return result_df[['group', 'time', 'at_risk', 'events', 'hazard', 'survival']]


def km_plot(
    curve_df: pd.DataFrame, 
    group_col: str = "group", 
    time_col: str = "time",
    title: str = "Kaplan-Meier Survival Curve",
    yaxis_title: str = "Complication-free probability (%)",
    xaxis_title: str = "Time interval",
    height: int = 320,
    colors: Optional[List[str]] = None
) -> go.Figure:
    """
    Create a new Plotly KM plot from curve data.
    Always returns a fresh Figure object to avoid reuse issues.
    """
    fig = go.Figure()
    
    if curve_df.empty:
        fig.add_annotation(
            text="No data available",
            xref="paper", yref="paper",
            x=0.5, y=0.5,
            showarrow=False,
            font=dict(size=16, color="gray")
        )
    else:
        # Default colors if not provided
        if colors is None:
            colors = ['#e67e22', '#1f77b4', '#2ca02c', '#d62728', '#9467bd', '#8c564b', '#e377c2', '#7f7f7f']
        
        color_idx = 0
        for group_name, group_data in curve_df.groupby(group_col):
            # Create step-like KM curve
            x_vals = []
            y_vals = []
            
            prev_survival = 1.0
            for _, row in group_data.iterrows():
                time_label = str(row[time_col])
                current_survival = float(row['survival'])
                
                # Add step: horizontal line at previous survival, then vertical drop
                x_vals.extend([time_label, time_label])
                y_vals.extend([prev_survival * 100, current_survival * 100])
                
                prev_survival = current_survival
            
            # Add trace
            color = colors[color_idx % len(colors)]
            trace_name = f"{group_name} KM" if group_name != 'ALL' else 'National KM'
            
            fig.add_trace(go.Scatter(
                x=x_vals,
                y=y_vals,
                mode='lines',
                name=trace_name,
                line=dict(shape='linear', width=3, color=color),
                hovertemplate=f"{trace_name}<br>Time: %{{x}}<br>Survival: %{{y:.1f}}%<extra></extra>"
            ))
            
            color_idx += 1
    
    # Update layout
    fig.update_layout(
        title=title,
        height=height,
        yaxis_title=yaxis_title,
        xaxis_title=xaxis_title,
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        hovermode='x unified'
    )
    
    return fig


def clear_km_cache():
    """Clear all KM-related cached data."""
    try:
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"Error clearing cache: {e}")
        return False
