"""
Chart factory functions for consistent, non-reusable plot generation.
Each function creates a fresh Plotly figure to avoid state reuse issues.
"""

import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
from typing import Optional, List
import streamlit as st


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
            # Show complication rate with KM step-like appearance
            # survival field contains the period-specific rate directly
            prev_rate = 0.0  # Start at 0% complication rate
            
            for _, row in curve_df.iterrows():
                time_label = str(row['time'])
                current_rate = float(row['survival']) * 100  # Convert to percentage
                
                # Add horizontal line at previous rate level
                x_vals.append(time_label)
                y_vals.append(prev_rate)
                
                # Add vertical jump to current rate level
                x_vals.append(time_label)  
                y_vals.append(current_rate)
                
                prev_rate = current_rate
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
        # For complication rate, use a reasonable range (0-20% to accommodate hospital variations)
        # This will auto-scale but cap at reasonable upper bound
        fig.update_layout(yaxis=dict(rangemode='tozero', range=[0, 20]))
    else:
        # For survival probability, fix range to 0-100%
        fig.update_layout(yaxis=dict(range=[0, 100]))
    
    return fig


def create_multi_km_chart(
    curves_dict: dict,
    title: str = "Kaplan-Meier Comparison",
    yaxis_title: str = "Complication Rate (%)", 
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
                
            # Create step-like curve for complication rates
            x_vals = []
            y_vals = []
            prev_rate = 0.0  # Start at 0% complication rate
            
            for _, row in curve_df.iterrows():
                time_label = str(row['time'])
                current_rate = float(row['survival']) * 100  # Convert to percentage
                
                # Add horizontal line at previous rate level
                x_vals.append(time_label)
                y_vals.append(prev_rate)
                
                # Add vertical jump to current rate level
                x_vals.append(time_label)  
                y_vals.append(current_rate)
                
                prev_rate = current_rate
            
            # Add trace
            color = colors[color_idx % len(colors)]
            fig.add_trace(go.Scatter(
                x=x_vals,
                y=y_vals,
                mode='lines',
                name=str(group_name),
                line=dict(shape='linear', width=3, color=color),
                hovertemplate=f"{group_name}<br>Time: %{{x}}<br>Complication Rate: %{{y:.1f}}%<extra></extra>"
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
    
    # Set y-axis range for complication rates (0-20% to accommodate variations)
    fig.update_layout(yaxis=dict(rangemode='tozero', range=[0, 20]))
    
    return fig


# New CSV-based chart functions
def create_procedure_mix_chart(hospital_id: str = None, level: str = 'HOP', title: str = "Procedure Mix") -> go.Figure:
    """Create procedure mix chart using CSV data."""
    try:
        from navira.csv_data_loader import get_procedure_mix_data
        
        df = get_procedure_mix_data(hospital_id, level)
        
        if df.empty:
            fig = go.Figure()
            fig.add_annotation(
                text="No procedure mix data available",
                xref="paper", yref="paper",
                x=0.5, y=0.5,
                showarrow=False,
                font=dict(size=16, color="gray")
            )
            return fig
        
        # Aggregate by procedure type
        if 'procedure_type' in df.columns and 'count' in df.columns:
            procedure_summary = df.groupby('procedure_type')['count'].sum().reset_index()
            
            # Map procedure types to readable names
            procedure_names = {
                'SLE': 'Sleeve Gastrectomy',
                'BPG': 'Gastric Bypass', 
                'ANN': 'Gastric Banding',
                'REV': 'Other',
                'ABL': 'Band Removal',
                'DBP': 'Bilio-pancreatic Diversion',
                'GVC': 'Calibrated Vertical Gastroplasty',
                'NDD': 'Not Defined'
            }
            
            procedure_summary['procedure_name'] = procedure_summary['procedure_type'].map(procedure_names)
            procedure_summary['procedure_name'] = procedure_summary['procedure_name'].fillna(procedure_summary['procedure_type'])
            
            fig = px.pie(
                procedure_summary, 
                values='count', 
                names='procedure_name',
                title=title,
                color_discrete_sequence=px.colors.qualitative.Set3
            )
            
            fig.update_layout(
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)',
                font=dict(color='white')
            )
            
            return fig
        else:
            fig = go.Figure()
            fig.add_annotation(
                text="Missing required columns for procedure mix",
                xref="paper", yref="paper",
                x=0.5, y=0.5,
                showarrow=False,
                font=dict(size=16, color="gray")
            )
            return fig
            
    except Exception as e:
        st.error(f"Error creating procedure mix chart: {e}")
        fig = go.Figure()
        fig.add_annotation(
            text=f"Error: {str(e)}",
            xref="paper", yref="paper",
            x=0.5, y=0.5,
            showarrow=False,
            font=dict(size=16, color="red")
        )
        return fig


def create_surgical_approaches_chart(hospital_id: str = None, level: str = 'HOP', title: str = "Surgical Approaches") -> go.Figure:
    """Create surgical approaches chart using CSV data."""
    try:
        from navira.csv_data_loader import get_surgical_approaches_data
        
        df = get_surgical_approaches_data(hospital_id, level)
        
        if df.empty:
            fig = go.Figure()
            fig.add_annotation(
                text="No surgical approaches data available",
                xref="paper", yref="paper",
                x=0.5, y=0.5,
                showarrow=False,
                font=dict(size=16, color="gray")
            )
            return fig
        
        # Aggregate by approach
        if 'approach' in df.columns and 'count' in df.columns:
            approach_summary = df.groupby('approach')['count'].sum().reset_index()
            
            # Map approaches to readable names
            approach_names = {
                'LAP': 'Open Surgery',
                'COE': 'Coelioscopy', 
                'ROB': 'Robotic'
            }
            
            approach_summary['approach_name'] = approach_summary['approach'].map(approach_names)
            approach_summary['approach_name'] = approach_summary['approach_name'].fillna(approach_summary['approach'])
            
            fig = px.pie(
                approach_summary, 
                values='count', 
                names='approach_name',
                title=title,
                color_discrete_sequence=px.colors.qualitative.Set2
            )
            
            fig.update_layout(
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)',
                font=dict(color='white')
            )
            
            return fig
        else:
            fig = go.Figure()
            fig.add_annotation(
                text="Missing required columns for surgical approaches",
                xref="paper", yref="paper",
                x=0.5, y=0.5,
                showarrow=False,
                font=dict(size=16, color="gray")
            )
            return fig
            
    except Exception as e:
        st.error(f"Error creating surgical approaches chart: {e}")
        fig = go.Figure()
        fig.add_annotation(
            text=f"Error: {str(e)}",
            xref="paper", yref="paper",
            x=0.5, y=0.5,
            showarrow=False,
            font=dict(size=16, color="red")
        )
        return fig


def create_volume_trend_chart(hospital_id: str = None, level: str = 'HOP', title: str = "Volume Trends") -> go.Figure:
    """Create volume trend chart using CSV data."""
    try:
        from navira.csv_data_loader import get_volume_data
        
        df = get_volume_data(hospital_id, level)
        
        if df.empty:
            fig = go.Figure()
            fig.add_annotation(
                text="No volume data available",
                xref="paper", yref="paper",
                x=0.5, y=0.5,
                showarrow=False,
                font=dict(size=16, color="gray")
            )
            return fig
        
        # Create time series
        if 'year' in df.columns and 'count' in df.columns:
            # Aggregate by year
            yearly_data = df.groupby('year')['count'].sum().reset_index()
            yearly_data = yearly_data.sort_values('year')
            
            fig = px.line(
                yearly_data,
                x='year',
                y='count',
                title=title,
                markers=True
            )
            
            fig.update_layout(
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)',
                font=dict(color='white'),
                xaxis_title="Year",
                yaxis_title="Number of Procedures"
            )
            
            return fig
        else:
            fig = go.Figure()
            fig.add_annotation(
                text="Missing required columns for volume trends",
                xref="paper", yref="paper",
                x=0.5, y=0.5,
                showarrow=False,
                font=dict(size=16, color="gray")
            )
            return fig
            
    except Exception as e:
        st.error(f"Error creating volume trend chart: {e}")
        fig = go.Figure()
        fig.add_annotation(
            text=f"Error: {str(e)}",
            xref="paper", yref="paper",
            x=0.5, y=0.5,
            showarrow=False,
            font=dict(size=16, color="red")
        )
        return fig


def create_revision_rate_chart(hospital_id: str = None, level: str = 'HOP', title: str = "Revision Surgery Rate") -> go.Figure:
    """Create revision surgery rate chart using CSV data."""
    try:
        from navira.csv_data_loader import get_revision_data
        
        df = get_revision_data(hospital_id, level)
        
        if df.empty:
            fig = go.Figure()
            fig.add_annotation(
                text="No revision data available",
                xref="paper", yref="paper",
                x=0.5, y=0.5,
                showarrow=False,
                font=dict(size=16, color="gray")
            )
            return fig
        
        # Calculate revision rate
        if 'count' in df.columns:
            total_revisions = df['count'].sum()
            
            fig = go.Figure(go.Indicator(
                mode = "number",
                value = total_revisions,
                title = {"text": "Total Revision Surgeries"},
                number = {'font': {'size': 50}}
            ))
            
            fig.update_layout(
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)',
                font=dict(color='white'),
                title=title
            )
            
            return fig
        else:
            fig = go.Figure()
            fig.add_annotation(
                text="Missing required columns for revision data",
                xref="paper", yref="paper",
                x=0.5, y=0.5,
                showarrow=False,
                font=dict(size=16, color="gray")
            )
            return fig
            
    except Exception as e:
        st.error(f"Error creating revision rate chart: {e}")
        fig = go.Figure()
        fig.add_annotation(
            text=f"Error: {str(e)}",
            xref="paper", yref="paper",
            x=0.5, y=0.5,
            showarrow=False,
            font=dict(size=16, color="red")
        )
        return fig


def create_robotic_surgery_chart(hospital_id: str = None, title: str = "Robotic Surgery Share") -> go.Figure:
    """Create robotic surgery share chart using CSV data."""
    try:
        from navira.csv_data_loader import get_robotic_surgery_data
        
        df = get_robotic_surgery_data(hospital_id)
        
        if df.empty:
            fig = go.Figure()
            fig.add_annotation(
                text="No robotic surgery data available",
                xref="paper", yref="paper",
                x=0.5, y=0.5,
                showarrow=False,
                font=dict(size=16, color="gray")
            )
            return fig
        
        # Calculate robotic surgery percentage
        if 'count' in df.columns and 'total' in df.columns:
            total_robotic = df['count'].sum()
            total_procedures = df['total'].sum()
            robotic_percentage = (total_robotic / total_procedures * 100) if total_procedures > 0 else 0
            
            fig = go.Figure(go.Indicator(
                mode = "number+delta",
                value = robotic_percentage,
                title = {"text": "Robotic Surgery Share (%)"},
                number = {'font': {'size': 50}, 'suffix': '%'},
                delta = {'reference': 0}
            ))
            
            fig.update_layout(
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)',
                font=dict(color='white'),
                title=title
            )
            
            return fig
        else:
            fig = go.Figure()
            fig.add_annotation(
                text="Missing required columns for robotic surgery data",
                xref="paper", yref="paper",
                x=0.5, y=0.5,
                showarrow=False,
                font=dict(size=16, color="gray")
            )
            return fig
            
    except Exception as e:
        st.error(f"Error creating robotic surgery chart: {e}")
        fig = go.Figure()
        fig.add_annotation(
            text=f"Error: {str(e)}",
            xref="paper", yref="paper",
            x=0.5, y=0.5,
            showarrow=False,
            font=dict(size=16, color="red")
        )
        return fig


# New chart functions for complications, LOS, and Never Events

def create_complications_rate_chart(hospital_id: str = None, level: str = 'HOP', timeframe: str = 'YEAR', title: str = "Complications Rate") -> go.Figure:
    """Create complications rate chart using new CSV data."""
    try:
        from navira.csv_data_loader import get_complications_data
        
        df = get_complications_data(hospital_id, level, timeframe)
        
        if df.empty:
            fig = go.Figure()
            fig.add_annotation(
                text="No complications data available",
                xref="paper", yref="paper",
                x=0.5, y=0.5,
                showarrow=False,
                font=dict(size=16, color="gray")
            )
            return fig
        
        # Create time series if year data is available
        if 'year' in df.columns and 'complications_percentage' in df.columns:
            yearly_data = df.groupby('year')['complications_percentage'].mean().reset_index()
            yearly_data = yearly_data.sort_values('year')
            
            fig = px.line(
                yearly_data,
                x='year',
                y='complications_percentage',
                title=title,
                markers=True
            )
            
            fig.update_layout(
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)',
                font=dict(color='white'),
                xaxis_title="Year",
                yaxis_title="Complications Rate (%)"
            )
            
            return fig
        else:
            # Show overall complications rate
            if 'complications_percentage' in df.columns:
                avg_rate = df['complications_percentage'].mean()
                
                fig = go.Figure(go.Indicator(
                    mode = "number",
                    value = avg_rate,
                    title = {"text": "Average Complications Rate (%)"},
                    number = {'font': {'size': 50}, 'suffix': '%'}
                ))
                
                fig.update_layout(
                    plot_bgcolor='rgba(0,0,0,0)',
                    paper_bgcolor='rgba(0,0,0,0)',
                    font=dict(color='white'),
                    title=title
                )
                
                return fig
            else:
                fig = go.Figure()
                fig.add_annotation(
                    text="Missing required columns for complications data",
                    xref="paper", yref="paper",
                    x=0.5, y=0.5,
                    showarrow=False,
                    font=dict(size=16, color="gray")
                )
                return fig
            
    except Exception as e:
        st.error(f"Error creating complications rate chart: {e}")
        fig = go.Figure()
        fig.add_annotation(
            text=f"Error: {str(e)}",
            xref="paper", yref="paper",
            x=0.5, y=0.5,
            showarrow=False,
            font=dict(size=16, color="red")
        )
        return fig


def create_complications_grade_chart(hospital_id: str = None, level: str = 'HOP', title: str = "Complications by Grade") -> go.Figure:
    """Create complications grade distribution chart."""
    try:
        from navira.csv_data_loader import get_complications_grade_data
        
        df = get_complications_grade_data(hospital_id, level)
        
        if df.empty:
            fig = go.Figure()
            fig.add_annotation(
                text="No complications grade data available",
                xref="paper", yref="paper",
                x=0.5, y=0.5,
                showarrow=False,
                font=dict(size=16, color="gray")
            )
            return fig
        
        # Aggregate by Clavien grade
        if 'clavien_grade' in df.columns and 'complications_count' in df.columns:
            grade_summary = df.groupby('clavien_grade')['complications_count'].sum().reset_index()
            
            # Map grades to readable names
            grade_names = {
                1: 'Grade I (Minor)',
                2: 'Grade II (Moderate)', 
                3: 'Grade III (Severe)',
                4: 'Grade IV (Life-threatening)',
                5: 'Grade V (Death)'
            }
            
            grade_summary['grade_name'] = grade_summary['clavien_grade'].map(grade_names)
            grade_summary['grade_name'] = grade_summary['grade_name'].fillna(f"Grade {grade_summary['clavien_grade']}")
            
            fig = px.bar(
                grade_summary,
                x='grade_name',
                y='complications_count',
                title=title,
                color='complications_count',
                color_continuous_scale='Reds'
            )
            
            fig.update_layout(
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)',
                font=dict(color='white'),
                xaxis_title="Clavien-Dindo Grade",
                yaxis_title="Number of Complications"
            )
            
            return fig
        else:
            fig = go.Figure()
            fig.add_annotation(
                text="Missing required columns for complications grade data",
                xref="paper", yref="paper",
                x=0.5, y=0.5,
                showarrow=False,
                font=dict(size=16, color="gray")
            )
            return fig
            
    except Exception as e:
        st.error(f"Error creating complications grade chart: {e}")
        fig = go.Figure()
        fig.add_annotation(
            text=f"Error: {str(e)}",
            xref="paper", yref="paper",
            x=0.5, y=0.5,
            showarrow=False,
            font=dict(size=16, color="red")
        )
        return fig


def create_los_distribution_chart(hospital_id: str = None, level: str = 'HOP', title: str = "Length of Stay Distribution") -> go.Figure:
    """Create length of stay distribution chart."""
    try:
        from navira.csv_data_loader import get_los_data
        
        df = get_los_data(hospital_id, level, extended=False)
        
        if df.empty:
            fig = go.Figure()
            fig.add_annotation(
                text="No LOS data available",
                xref="paper", yref="paper",
                x=0.5, y=0.5,
                showarrow=False,
                font=dict(size=16, color="gray")
            )
            return fig
        
        # Create distribution chart
        if 'duration_category' in df.columns and 'los_percentage' in df.columns:
            # Aggregate by duration category
            los_summary = df.groupby('duration_category')['los_percentage'].mean().reset_index()
            los_summary = los_summary.sort_values('duration_category')
            
            fig = px.bar(
                los_summary,
                x='duration_category',
                y='los_percentage',
                title=title,
                color='los_percentage',
                color_continuous_scale='Blues'
            )
            
            fig.update_layout(
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)',
                font=dict(color='white'),
                xaxis_title="Length of Stay Category",
                yaxis_title="Percentage of Patients (%)"
            )
            
            return fig
        else:
            fig = go.Figure()
            fig.add_annotation(
                text="Missing required columns for LOS data",
                xref="paper", yref="paper",
                x=0.5, y=0.5,
                showarrow=False,
                font=dict(size=16, color="gray")
            )
            return fig
            
    except Exception as e:
        st.error(f"Error creating LOS distribution chart: {e}")
        fig = go.Figure()
        fig.add_annotation(
            text=f"Error: {str(e)}",
            xref="paper", yref="paper",
            x=0.5, y=0.5,
            showarrow=False,
            font=dict(size=16, color="red")
        )
        return fig


def create_extended_los_chart(hospital_id: str = None, level: str = 'HOP', title: str = "Extended Length of Stay (>7 days)") -> go.Figure:
    """Create extended length of stay chart."""
    try:
        from navira.csv_data_loader import get_los_data
        
        df = get_los_data(hospital_id, level, extended=True)
        
        if df.empty:
            fig = go.Figure()
            fig.add_annotation(
                text="No extended LOS data available",
                xref="paper", yref="paper",
                x=0.5, y=0.5,
                showarrow=False,
                font=dict(size=16, color="gray")
            )
            return fig
        
        # Calculate extended LOS rate
        if 'los_7_percentage' in df.columns:
            avg_rate = df['los_7_percentage'].mean()
            
            fig = go.Figure(go.Indicator(
                mode = "number",
                value = avg_rate,
                title = {"text": "Extended LOS Rate (%)"},
                number = {'font': {'size': 50}, 'suffix': '%'}
            ))
            
            fig.update_layout(
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)',
                font=dict(color='white'),
                title=title
            )
            
            return fig
        else:
            fig = go.Figure()
            fig.add_annotation(
                text="Missing required columns for extended LOS data",
                xref="paper", yref="paper",
                x=0.5, y=0.5,
                showarrow=False,
                font=dict(size=16, color="gray")
            )
            return fig
            
    except Exception as e:
        st.error(f"Error creating extended LOS chart: {e}")
        fig = go.Figure()
        fig.add_annotation(
            text=f"Error: {str(e)}",
            xref="paper", yref="paper",
            x=0.5, y=0.5,
            showarrow=False,
            font=dict(size=16, color="red")
        )
        return fig


def create_never_events_chart(hospital_id: str = None, level: str = 'HOP', title: str = "Never Events") -> go.Figure:
    """Create Never Events chart."""
    try:
        from navira.csv_data_loader import get_never_events_data
        
        df = get_never_events_data(hospital_id, level)
        
        if df.empty:
            fig = go.Figure()
            fig.add_annotation(
                text="No Never Events data available",
                xref="paper", yref="paper",
                x=0.5, y=0.5,
                showarrow=False,
                font=dict(size=16, color="gray")
            )
            return fig
        
        # Calculate Never Events rate
        if 'never_events_percentage' in df.columns:
            avg_rate = df['never_events_percentage'].mean()
            
            fig = go.Figure(go.Indicator(
                mode = "number",
                value = avg_rate,
                title = {"text": "Never Events Rate (%)"},
                number = {'font': {'size': 50}, 'suffix': '%'}
            ))
            
            fig.update_layout(
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)',
                font=dict(color='white'),
                title=title
            )
            
            return fig
        else:
            fig = go.Figure()
            fig.add_annotation(
                text="Missing required columns for Never Events data",
                xref="paper", yref="paper",
                x=0.5, y=0.5,
                showarrow=False,
                font=dict(size=16, color="gray")
            )
            return fig
            
    except Exception as e:
        st.error(f"Error creating Never Events chart: {e}")
        fig = go.Figure()
        fig.add_annotation(
            text=f"Error: {str(e)}",
            xref="paper", yref="paper",
            x=0.5, y=0.5,
            showarrow=False,
            font=dict(size=16, color="red")
        )
        return fig
