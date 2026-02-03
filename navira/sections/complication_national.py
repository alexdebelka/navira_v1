import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import sys
import os

# Add the parent directory to the Python path to import lib
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from navira.data_loader import get_dataframes
from km import compute_complication_rates_from_aggregates
from charts import create_km_chart, create_multi_km_chart
from utils.cache import debug_dataframe_signature, show_debug_panel


def render_complication_national(all_data: dict):
    """Render the Complication section for national page.
    
    This section contains:
    - National complications overview
    - Complication rate trends
    - Kaplan-Meier analysis
    - Hospital performance over time
    """
    
    st.header("Complications Analysis")
    
    complications = all_data.get('complications', pd.DataFrame())
    
    if not complications.empty:
        st.markdown(
            """
            <div class=\"nv-info-wrap\">
              <div class=\"nv-h3\">National Complications Overview</div>
              <div class=\"nv-tooltip\"><span class=\"nv-info-badge\">i</span>
                <div class=\"nv-tooltiptext\">
                  <b>Understanding this analysis:</b><br/>
                  This section analyzes complication rates across all hospitals from 2020-2024. It shows trends in patient safety outcomes and compares hospital performance against national benchmarks.<br/><br/>
                  <b>Key Metrics:</b><br/>
                  • Rolling Rate: 12-month moving average of complication rates<br/>
                  • National Average: Benchmark rate across all eligible hospitals<br/>
                  • Confidence Intervals: Statistical range of expected performance
                </div>
              </div>
            </div>
            """,
            unsafe_allow_html=True
        )
        
        # Calculate overall statistics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            total_procedures = complications['procedures_count'].sum()
            st.metric("Total Procedures Analyzed", f"{int(total_procedures):,}")
        
        with col2:
            total_complications = complications['complications_count'].sum()
            st.metric("Total Complications", f"{int(total_complications):,}")
        
        with col3:
            if total_procedures > 0:
                overall_rate = (total_complications / total_procedures) * 100
                st.metric("Overall Complication Rate", f"{overall_rate:.2f}%")
        
        
        # Temporal trend of national complication rates
        st.markdown("#### National Complication Rate Trends")
        
        # Calculate quarterly national averages
        quarterly_stats = complications.groupby('quarter_date').agg({
            'procedures_count': 'sum',
            'complications_count': 'sum',
            'national_average': 'mean'
        }).reset_index()
        
        quarterly_stats['actual_rate'] = (quarterly_stats['complications_count'] / quarterly_stats['procedures_count'] * 100)
        quarterly_stats['national_avg_pct'] = quarterly_stats['national_average'] * 100
        
        if not quarterly_stats.empty:
            fig = go.Figure()
            
    
            
            # Add actual complication rate
            fig.add_trace(go.Scatter(
                x=quarterly_stats['quarter_date'],
                y=quarterly_stats['actual_rate'],
                mode='lines+markers',
                name='National Rate',
                line=dict(color='#1f77b4', width=3),
                marker=dict(size=6)
            ))
            
            fig.update_layout(
                title="National Complication Rate Over Time",
                xaxis_title="Quarter",
                yaxis_title="Complication Rate (%)",
                height=400,
                hovermode='x unified',
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)'
            )
            
            st.plotly_chart(fig, use_container_width=True)
        
        # Kaplan–Meier representation, moved into the Trends subsection
        st.markdown("##### National Complication Rate Over Time (Kaplan–Meier)")
        col_km1, col_km2 = st.columns([1,2])
        with col_km1:
            km_interval = st.radio("Interval", options=["6 months", "3 months"], index=0, horizontal=True, key="km_interval")
        with col_km2:
            km_label_opts = st.multiselect("Labels", options=["CSO", "SOFFCO", "None"], default=["CSO", "SOFFCO", "None"], help="Filter hospitals by labels", key="km_labels")
            km_top10 = st.checkbox("Top 10 hospitals by procedures (2020–2024)", value=False, key="km_top10")
    
        # Build hospital subset based on labels and top 10
        km_subset_ids = set()
        try:
            est_df = st.session_state.get('establishments', None)
            if est_df is None or (hasattr(est_df, 'empty') and est_df.empty):
                est_df = all_data.get('establishments')
            ann_df = st.session_state.get('annual', None) or all_data.get('annual')
            if est_df is None or ann_df is None:
                est_df, ann_df = get_dataframes()
            estN = est_df.copy()
            estN['id'] = estN['id'].astype(str)
            mask_any = pd.Series([False]*len(estN))
            label_parts = []
            if 'CSO' in km_label_opts and 'cso' in estN.columns:
                label_parts.append(estN['cso'] == 1)
            if 'SOFFCO' in km_label_opts and 'LAB_SOFFCO' in estN.columns:
                label_parts.append(estN['LAB_SOFFCO'] == 1)
            if 'None' in km_label_opts:
                cond_none = ((estN.get('cso', 0) != 1) & (estN.get('LAB_SOFFCO', 0) != 1))
                label_parts.append(cond_none)
            if label_parts:
                mask_any = label_parts[0]
                for p in label_parts[1:]:
                    mask_any = mask_any | p
            est_filtered = estN[mask_any]
            if km_top10 and ann_df is not None and not ann_df.empty:
                annN = ann_df.copy()
                annN['id'] = annN['id'].astype(str)
                vol = annN.groupby('id')['total_procedures_year'].sum().sort_values(ascending=False).head(10)
                est_filtered = est_filtered[est_filtered['id'].isin(vol.index.astype(str))]
            km_subset_ids = set(est_filtered['id'].astype(str)) if not est_filtered.empty else set()
        except Exception:
            km_subset_ids = set()
    
        # Compute KM curve using new robust system
        
        # Debug signatures for tracing
        debug_signatures = {}
        
        km_comp_df = all_data.get('complications', pd.DataFrame())
        debug_signatures['raw_complications'] = debug_dataframe_signature(km_comp_df, "Raw complications data")
        
        if not km_comp_df.empty:
            # Apply filters
            km_data = km_comp_df.copy()
            km_data['hospital_id'] = km_data['hospital_id'].astype(str)
            debug_signatures['after_id_conversion'] = debug_dataframe_signature(km_data, "After ID conversion")
            
            if km_subset_ids:
                km_data = km_data[km_data['hospital_id'].isin(km_subset_ids)]
                debug_signatures['after_hospital_filter'] = debug_dataframe_signature(km_data, f"After hospital filter ({len(km_subset_ids)} hospitals)")
            
            km_data = km_data.dropna(subset=['quarter_date']).sort_values('quarter_date')
            debug_signatures['after_date_filter'] = debug_dataframe_signature(km_data, "After date filter")
            
            # Create time intervals
            km_data['year'] = km_data['quarter_date'].dt.year
            if km_interval.startswith('6'):
                km_data['bucket'] = ((km_data['quarter_date'].dt.quarter - 1) // 2 + 1)
                km_xaxis_label = '6‑month interval'
                time_suffix = 'H'
            else:
                km_data['bucket'] = km_data['quarter_date'].dt.quarter
                km_xaxis_label = '3‑month interval (quarter)'
                time_suffix = 'Q'
            
            km_data['time_label'] = km_data['year'].astype(int).astype(str) + ' ' + time_suffix + km_data['bucket'].astype(int).astype(str)
            
            # First compute overall national curve to get the base hash
            km_agg = km_data.groupby(['year', 'bucket', 'time_label'], as_index=False).agg({
                'complications_count': 'sum',
                'procedures_count': 'sum'
            }).sort_values(['year', 'bucket'])
            
            debug_signatures['aggregated_data'] = debug_dataframe_signature(km_agg, "Aggregated by time intervals")
            
            # Create multiple KM curves based on selected labels
            km_curves = {}
            
            # Get hospital label information for grouping
            est_df = st.session_state.get('establishments', None)
            if est_df is None or (hasattr(est_df, 'empty') and est_df.empty):
                est_df = all_data.get('establishments')
            if est_df is not None and not est_df.empty:
                est_labels = est_df[['id', 'cso', 'LAB_SOFFCO']].copy()
                est_labels['id'] = est_labels['id'].astype(str)
                
                # Merge label info with KM data
                km_data_with_labels = km_data.merge(est_labels, left_on='hospital_id', right_on='id', how='left')
                
                # Create groups based on selected labels
                for label in km_label_opts:
                    if label == 'CSO':
                        mask = km_data_with_labels['cso'] == 1
                        group_name = 'CSO Hospitals'
                    elif label == 'SOFFCO':
                        mask = km_data_with_labels['LAB_SOFFCO'] == 1
                        group_name = 'SOFFCO Hospitals'
                    elif label == 'None':
                        mask = ((km_data_with_labels['cso'] != 1) & (km_data_with_labels['LAB_SOFFCO'] != 1))
                        group_name = 'No Labels'
                    else:
                        continue
                    
                    # Filter data for this label group
                    label_data = km_data_with_labels[mask].copy()
                    if not label_data.empty:
                        # Aggregate by time intervals for this group
                        label_agg = label_data.groupby(['year', 'bucket', 'time_label'], as_index=False).agg({
                            'complications_count': 'sum',
                            'procedures_count': 'sum'
                        }).sort_values(['year', 'bucket'])
                        
                        if not label_agg.empty:
                            try:
                                    # Compute KM curve for this label group
                                    label_curve = compute_complication_rates_from_aggregates(
                                        df=label_agg,
                                        time_col='time_label',
                                        event_col='complications_count', 
                                        at_risk_col='procedures_count',
                                        group_cols=None,
                                        data_hash=f"{debug_signatures['aggregated_data']['hash']}_{label}",
                                        cache_version="v1"
                                    )
                                    
                                    if not label_curve.empty:
                                        km_curves[group_name] = label_curve
                                        
                            except Exception as e:
                                st.error(f"Error computing KM curve for {label}: {e}")
                                debug_signatures[f'km_error_{label}'] = {'error': str(e)}
            
            if not km_agg.empty:
                try:
                    # Overall national curve
                    overall_curve = compute_complication_rates_from_aggregates(
                        df=km_agg,
                        time_col='time_label',
                        event_col='complications_count', 
                        at_risk_col='procedures_count',
                        group_cols=None,
                        data_hash=debug_signatures['aggregated_data']['hash'],
                        cache_version="v1"
                    )
                    
                    if not overall_curve.empty:
                        km_curves['Overall'] = overall_curve
                        
                except Exception as e:
                    st.error(f"Error computing overall KM curve: {e}")
                    debug_signatures['km_error_overall'] = {'error': str(e)}
            
            # Create multi-line chart if we have multiple curves
            if len(km_curves) > 1:
                try:
                    # Create dynamic title based on active filters
                    active_filters = []
                    if km_top10:
                        active_filters.append("Top 10 hospitals")
                    if km_label_opts:
                        active_filters.append(f"Labels: {', '.join(km_label_opts)}")
                    
                    title = "National Complication Rate Over Time (KM)"
                    if active_filters:
                        title += f" - {', '.join(active_filters)}"
                    
                    # Create consistent color mapping for each group type
                    color_mapping = {
                        'CSO Hospitals': '#1f77b4',      # Blue
                        'SOFFCO Hospitals': '#e67e22',   # Orange  
                        'No Labels': '#2ca02c',          # Green
                        'Overall': '#d62728'             # Red
                    }
                    
                    # Sort curves to ensure consistent order: Overall first, then others
                    sorted_curves = {}
                    if 'Overall' in km_curves:
                        sorted_curves['Overall'] = km_curves['Overall']
                    for key in ['CSO Hospitals', 'SOFFCO Hospitals', 'No Labels']:
                        if key in km_curves:
                            sorted_curves[key] = km_curves[key]
                    
                    fig_km_nat = create_multi_km_chart(
                        curves_dict=sorted_curves,
                        title=title,
                        yaxis_title='Complication Rate (%)',
                        xaxis_title=km_xaxis_label,
                        height=400,
                        colors=[color_mapping.get(key, '#9467bd') for key in sorted_curves.keys()]  # Consistent colors
                    )
                    
                    st.plotly_chart(fig_km_nat, use_container_width=True, key="km_national_multi")
                    
                    # Show legend info
                    st.info(f"📊 **Multiple KM curves shown:** {', '.join(km_curves.keys())}")
                    
                except Exception as e:
                    st.error(f"Error creating multi-line KM chart: {e}")
                    debug_signatures['multi_chart_error'] = {'error': str(e)}
                    
            elif len(km_curves) == 1:
                # Single curve - use consistent color mapping
                curve_name, curve_data = list(km_curves.items())[0]
                
                # Use consistent color for single curves too
                color_mapping = {
                    'CSO Hospitals': '#1f77b4',      # Blue
                    'SOFFCO Hospitals': '#e67e22',   # Orange  
                    'No Labels': '#2ca02c',          # Green
                    'Overall': '#d62728'             # Red
                }
                
                curve_color = color_mapping.get(curve_name, '#e67e22')  # Default to orange if unknown
                
                fig_km_nat = create_km_chart(
                    curve_df=curve_data,
                    page_id="national",
                    title=f"National Complication Rate Over Time (KM) - {curve_name}",
                    yaxis_title='Complication Rate (%)',
                    xaxis_title=km_xaxis_label,
                    height=320,
                    color=curve_color,
                    show_complication_rate=True
                )
                
                st.plotly_chart(fig_km_nat, use_container_width=True, key="km_national_single")
                
            else:
                st.info('No data to compute KM curves with current filters.')
                debug_signatures['no_data'] = {'message': 'No KM curves computed'}
        else:
            st.info('Complications dataset unavailable.')
            debug_signatures['no_raw_data'] = {'message': 'No complications data'}
        
        # Show debug panel (collapsed by default)
        if st.checkbox("Show KM debug info", value=False, key="km_debug_national"):
            show_debug_panel(debug_signatures, expanded=True)
    
        # Hospital performance trends ("spaghetti" plot)
        st.markdown("#### Hospital Performance Over Time")
        
        st.info("💡 **About 'top 100 by volume'**: To ensure readability and performance, the spaghetti plot shows only the 100 hospitals with the highest total procedure volume. This represents the largest and most active bariatric surgery centers while maintaining chart clarity.")
        
        hosp_trends = complications.copy()
        if not hosp_trends.empty:
            # Build per-hospital series of rolling rates
            hosp_trends['rolling_pct'] = pd.to_numeric(hosp_trends['rolling_rate'], errors='coerce') * 100
            # Keep reasonable number of lines for performance: top 100 hospitals by total procedures
            totals = hosp_trends.groupby('hospital_id')['procedures_count'].sum().sort_values(ascending=False)
            keep_ids = set(totals.head(100).index.astype(str))
            sub = hosp_trends[hosp_trends['hospital_id'].astype(str).isin(keep_ids)].copy()
            if not sub.empty:
                # Create spaghetti plot using go.Figure for opacity control
                spaghetti = go.Figure()
                
                # Add individual hospital lines with low opacity
                for hosp_id in sub['hospital_id'].unique():
                    hosp_data = sub[sub['hospital_id'] == hosp_id]
                    spaghetti.add_trace(go.Scatter(
                        x=hosp_data['quarter_date'],
                        y=hosp_data['rolling_pct'],
                        mode='lines',
                        name=f'Hospital {hosp_id}',
                        line=dict(width=1),
                        opacity=0.25,
                        showlegend=False,
                        hoverinfo='skip'
                    ))
                
                # Overlay bold national rate
                if not quarterly_stats.empty:
                    spaghetti.add_trace(go.Scatter(
                        x=quarterly_stats['quarter_date'],
                        y=quarterly_stats['actual_rate'],
                        mode='lines',
                        name='National Average',
                        line=dict(color='#ff7f0e', width=3),
                        showlegend=True
                    ))
                
                spaghetti.update_layout(
                    title='Hospital 12‑month Rolling Complication Rates (top 100 by volume)',
                    xaxis_title='Quarter',
                    yaxis_title='Complication Rate (%)',
                    height=420,
                    plot_bgcolor='rgba(0,0,0,0)',
                    paper_bgcolor='rgba(0,0,0,0)',
                    showlegend=False
                )
                st.plotly_chart(spaghetti, use_container_width=True)
    
    else:
        st.info("Complications data not available for national analysis.")
