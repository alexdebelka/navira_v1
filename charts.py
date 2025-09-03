"""
Chart factory functions for consistent, non-reusable plot generation.
Each function creates a fresh Plotly figure to avoid state reuse issues.
"""

import plotly.graph_objects as go
import pandas as pd
from typing import Optional, List


def create_km_chart(
    curve_df: pd.DataFrame,
    page_id: str,
    title: str = "Kaplan-Meier Survival Curve",
    yaxis_title: str = "Complication rate (%)",
    xaxis_title: str = "Time interval",
    height: int = 320,
    color: str = '#1f77b4',
    show_complication_rate: bool = True
) -> go.Figure:
    """
    Create a fresh KM chart for a specific page.
    
    Args:
        curve_df: DataFrame with columns ['time', 'survival'] at minimum
        page_id: Unique identifier for the page (for debugging)
        title: Chart title
        yaxis_title: Y-axis label
        xaxis_title: X-axis label  
        height: Chart height in pixels
        color: Line color
    
    Returns:
        Fresh Plotly Figure object
    """
    # Always create a new figure
    fig = go.Figure()
    
    if curve_df.empty:
        # Show empty state
        fig.add_annotation(
            text="No data available for KM curve",
            xref="paper", yref="paper",
            x=0.5, y=0.5,
            showarrow=False,
            font=dict(size=16, color="gray")
        )
    else:
        # Create step-like curve
        x_vals = []
        y_vals = []
        
        if show_complication_rate:
            # Show period-specific complication rates directly
            # survival field now contains the period-specific rate directly
            for _, row in curve_df.iterrows():
                time_label = str(row['time'])
                current_rate = float(row['survival']) * 100  # Convert to percentage
                
                # Add data point
                x_vals.append(time_label)
                y_vals.append(current_rate)
        else:
            # Show survival probability (original behavior)
            prev_survival = 1.0
            
            for _, row in curve_df.iterrows():
                time_label = str(row['time'])
                current_survival = float(row['survival'])
                
                # Add horizontal line at previous survival level
                x_vals.append(time_label)
                y_vals.append(prev_survival * 100)
                
                # Add vertical drop to current survival level
                x_vals.append(time_label)  
                y_vals.append(current_survival * 100)
                
                prev_survival = current_survival
        
        # Add the trace
        fig.add_trace(go.Scatter(
            x=x_vals,
            y=y_vals,
            mode='lines',
            name=f'KM Curve ({page_id})',
            line=dict(shape='linear', width=3, color=color),
            hovertemplate=f"Time: %{{x}}<br>{'Complication Rate' if show_complication_rate else 'Survival'}: %{{y:.1f}}%<extra></extra>"
        ))
    
    # Configure layout
    fig.update_layout(
        title=title,
        height=height,
        yaxis_title=yaxis_title,
        xaxis_title=xaxis_title,
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        hovermode='x unified',
        showlegend=False  # Single curve doesn't need legend
    )
    
    # Set y-axis range based on what we're showing
    if show_complication_rate:
        # For complication rate, start at 0 and let it scale naturally
        fig.update_layout(yaxis=dict(rangemode='tozero'))
    else:
        # For survival probability, fix range to 0-100%
        fig.update_layout(yaxis=dict(range=[0, 100]))
    
    return fig


def create_multi_km_chart(
    curves_dict: dict,
    title: str = "Kaplan-Meier Comparison",
    yaxis_title: str = "Complication-free probability (%)", 
    xaxis_title: str = "Time interval",
    height: int = 400,
    colors: Optional[List[str]] = None
) -> go.Figure:
    """
    Create a chart with multiple KM curves for comparison.
    
    Args:
        curves_dict: Dict of {group_name: curve_df} 
        title: Chart title
        yaxis_title: Y-axis label
        xaxis_title: X-axis label
        height: Chart height in pixels
        colors: List of colors for different curves
    
    Returns:
        Fresh Plotly Figure object with multiple curves
    """
    # Default colors
    if colors is None:
        colors = ['#e67e22', '#1f77b4', '#2ca02c', '#d62728', '#9467bd', '#8c564b']
    
    # Always create a new figure
    fig = go.Figure()
    
    if not curves_dict or all(df.empty for df in curves_dict.values()):
        # Show empty state
        fig.add_annotation(
            text="No data available for comparison",
            xref="paper", yref="paper", 
            x=0.5, y=0.5,
            showarrow=False,
            font=dict(size=16, color="gray")
        )
    else:
        # Add each curve
        color_idx = 0
        for group_name, curve_df in curves_dict.items():
            if curve_df.empty:
                continue
                
            # Create step-like curve
            x_vals = []
            y_vals = []
            prev_survival = 1.0
            
            for _, row in curve_df.iterrows():
                time_label = str(row['time'])
                current_survival = float(row['survival'])
                
                x_vals.extend([time_label, time_label])
                y_vals.extend([prev_survival * 100, current_survival * 100])
                
                prev_survival = current_survival
            
            # Add trace
            color = colors[color_idx % len(colors)]
            fig.add_trace(go.Scatter(
                x=x_vals,
                y=y_vals,
                mode='lines',
                name=str(group_name),
                line=dict(shape='linear', width=3, color=color),
                hovertemplate=f"{group_name}<br>Time: %{{x}}<br>Survival: %{{y:.1f}}%<extra></extra>"
            ))
            
            color_idx += 1
    
    # Configure layout
    fig.update_layout(
        title=title,
        height=height,
        yaxis_title=yaxis_title,
        xaxis_title=xaxis_title,
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        hovermode='x unified',
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right", 
            x=1
        )
    )
    
    # Set y-axis range
    fig.update_layout(yaxis=dict(range=[0, 100]))
    
    return fig
