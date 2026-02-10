import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import sys
import os

# Add the parent directory to the Python path to import lib
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from lib.national_utils import (
    compute_procedure_averages_2020_2024,
    get_2024_procedure_totals,
    get_2020_2024_procedure_totals,
    BARIATRIC_PROCEDURE_NAMES
)


def render_techniques(df: pd.DataFrame, national_averages: dict):
    """Render the Techniques section for national page.
    
    This section contains:
    - Procedure type distribution
    - Procedure mix trends
    - National averages summary
    """
    
    st.header("Procedures")
    
    # Compute procedure data
    procedure_averages = compute_procedure_averages_2020_2024(df)
    procedure_totals_2024 = get_2024_procedure_totals(df)
    procedure_totals_2020_2024 = get_2020_2024_procedure_totals(df)
    
    # Toggle between 2020-2024 totals and 2024 only
    toggle_2024_only = st.toggle("Show 2024 data only", value=False, key="techniques_toggle_2024")
    
    # Single column layout
    col1 = st.columns(1)[0]
    
    with col1:
        # Load data from CSV
        try:
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            csv_path = os.path.join(base_dir, "new_data", "ACTIVITY", "TAB_TCN_NATL_YEAR.csv")
            df_activity = pd.read_csv(csv_path)
            
            # Filter to 2024 only as requested
            df_activity = df_activity[df_activity['annee'] <= 2024]
            
            # Map procedure codes to names
            procedure_name_map = {
                'SLE': 'Sleeve Gastrectomy',
                'BPG': 'Gastric Bypass',
                'ANN': 'Gastric Banding',
                'ABL': 'Band Removal',
                'REV': 'Revision Surgery',
                'DBP': 'Bilio-pancreatic Diversion',
                'GVC': 'Gastroplasty',
                'NDD': 'Not Defined'
            }
            
        except Exception as e:
            st.error(f"Error loading activity data: {e}")
            df_activity = pd.DataFrame()
        
        if not toggle_2024_only:
            st.markdown(
                """
                <div class=\"nv-info-wrap\">
                  <div class=\"nv-h3\">Total Procedures (2020–2024)</div>
                  <div class=\"nv-tooltip\"><span class=\"nv-info-badge\">i</span>
                    <div class=\"nv-tooltiptext\">
                      <b>Understanding this chart:</b><br/>
                      This bar chart shows the distribution of different bariatric surgery procedures. The bars represent the total number of procedures performed, and the height indicates the volume of each procedure type.<br/><br/>
                      <b>Time Period:</b><br/>
                      Toggle OFF: Shows data for the entire 2020–2024 period (5 years)<br/>
                      Toggle ON: Shows data for 2024 only
                    </div>
                  </div>
                </div>
                """,
                unsafe_allow_html=True
            )
            with st.expander("What to look for and key findings"):
                st.markdown(
                    """
                    **What to look for:**
                    - Which procedure type has the highest volume
                    - The gap between dominant and secondary procedures
                    - Relative market share of each procedure type
                    - Evolution of less common procedures

                    **Key findings (2020-2024):**
                    - **Sleeve Gastrectomy** is the dominant procedure (~66% of all bariatric surgeries)
                    - **Gastric Bypass** accounts for ~31% (second most common)
                    - **Other procedures** (Banding, Revision, etc.) represent less than 5% combined
                    - Sleeve's dominance reflects current clinical preferences for effective, lower-risk procedures
                    - The concentration in two main procedures suggests strong evidence-based practice standardization
                    """
                )
            
            # Aggregate totals for 2020-2024
            if not df_activity.empty:
                totals_by_type = df_activity.groupby('baria_t')['n'].sum().to_dict()
                total_procedures = sum(totals_by_type.values())
                
                # Group less common procedures under "Other"
                other_procedures = ['NDD', 'GVC', 'DBP']
                other_total = sum(totals_by_type.get(proc_code, 0) for proc_code in other_procedures)
                
                tot_data = []
                for proc_code, proc_name in procedure_name_map.items():
                    if proc_code in other_procedures:
                        continue
                    
                    value = totals_by_type.get(proc_code, 0)
                    if value > 0:
                        raw_percentage = (value / total_procedures) * 100 if total_procedures > 0 else 0
                        percentage = round(raw_percentage, 1) if raw_percentage < 1 else round(raw_percentage)
                        tot_data.append({
                            'Procedure': proc_name,
                            'Value': value,
                            'Percentage': percentage
                        })
                
                # Add "Other" category
                if other_total > 0:
                    other_percentage = (other_total / total_procedures) * 100 if total_procedures > 0 else 0
                    tot_data.append({
                        'Procedure': 'Other',
                        'Value': other_total,
                        'Percentage': other_percentage
                    })
                
                chart_df = pd.DataFrame(tot_data).sort_values('Value', ascending=True)
            else:
                chart_df = pd.DataFrame()
            
            y_title = "Total count (2020-2024)"
            chart_title = "Total Procedures by Type (2020-2024)"
            hover_tmpl = '<b>%{x}</b><br>Total 2020-2024: %{y:,}<br>Percentage: %{customdata[0]}%<extra></extra>'
        else:
            st.markdown(
                """
                <div class=\"nv-info-wrap\">
                  <div class=\"nv-h3\">Total Procedures (2024)</div>
                  <div class=\"nv-tooltip\"><span class=\"nv-info-badge\">i</span>
                    <div class=\"nv-tooltiptext\">
                      <b>Understanding this chart:</b><br/>
                      This bar chart shows the distribution of different bariatric surgery procedures. The bars represent the total number of procedures performed, and the height indicates the volume of each procedure type.<br/><br/>
                      <b>Time Period:</b><br/>
                      Toggle OFF: Shows data for the entire 2020–2024 period (5 years)<br/>
                      Toggle ON: Shows data for 2024 only
                    </div>
                  </div>
                </div>
                """,
                unsafe_allow_html=True
            )
            with st.expander("What to look for and key findings"):
                st.markdown(
                    """
                    **What to look for:**
                    - Current procedure distribution patterns
                    - Which techniques are most commonly performed
                    - Comparison of major procedure volumes
                    - Shifts from historical patterns

                    **Key findings (2024):**
                    - **Sleeve Gastrectomy** remains dominant at ~63.5% of all procedures
                    - **Gastric Bypass** increased to ~34.3% (up from ~30% in 2021)
                    - **Gastric Banding** continues to decline (~2%, down from ~2.7% in 2021)
                    - The trend shows increasing preference for Bypass while Sleeve remains the standard
                    - Revision surgeries represent a small but important portion of the workload
                    """
                )
            
            # Filter to 2024 only
            if not df_activity.empty:
                df_2024 = df_activity[df_activity['annee'] == 2024]
                totals_by_type = df_2024.groupby('baria_t')['n'].sum().to_dict()
                total_procedures = sum(totals_by_type.values())
                
                # Group less common procedures under "Other"
                other_procedures = ['NDD', 'GVC', 'DBP']
                other_total = sum(totals_by_type.get(proc_code, 0) for proc_code in other_procedures)
                
                tot_data = []
                for proc_code, proc_name in procedure_name_map.items():
                    if proc_code in other_procedures:
                        continue
                    
                    value = totals_by_type.get(proc_code, 0)
                    if value > 0:
                        raw_percentage = (value / total_procedures) * 100 if total_procedures > 0 else 0
                        percentage = round(raw_percentage, 1) if raw_percentage < 1 else round(raw_percentage)
                        tot_data.append({
                            'Procedure': proc_name,
                            'Value': value,
                            'Percentage': percentage
                        })
                
                # Add "Other" category
                if other_total > 0:
                    other_percentage = (other_total / total_procedures) * 100 if total_procedures > 0 else 0
                    tot_data.append({
                        'Procedure': 'Other',
                        'Value': other_total,
                        'Percentage': other_percentage
                    })
                
                chart_df = pd.DataFrame(tot_data).sort_values('Value', ascending=True)
            else:
                chart_df = pd.DataFrame()
            
            y_title = "Total count (2024)"
            chart_title = "Total Procedures by Type (2024)"
            hover_tmpl = '<b>%{x}</b><br>Total 2024: %{y:,}<br>Percentage: %{customdata[0]}%<extra></extra>'

        if not chart_df.empty:

            # Use a single blue color for all bars to emphasize totals
            # Build label: show one decimal for percentages <1%, otherwise whole number
            # Use a fresh calculation to ensure consistency
            def format_percentage(p):
                if p < 1:
                    return f"{p:.1f}%"
                else:
                    return f"{p:.0f}%"
            chart_df = chart_df.assign(Label=chart_df['Percentage'].apply(format_percentage))

            fig = px.bar(
                chart_df,
                x='Value',
                y='Procedure',
                orientation='h',
                title=chart_title,
                color_discrete_sequence=['#4C84C8'],
                custom_data=['Percentage'],
                text='Label'
            )
            fig.update_layout(
                xaxis_title=y_title,
                yaxis_title="Procedure Type",
                hovermode='y unified',
                height=440,
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)',
                font=dict(size=12),
                margin=dict(l=160, r=50, t=80, b=40),
                yaxis=dict(automargin=True)
            )
            # Horizontal hover shows category on Y; text already includes % with proper decimals
            hover_tmpl_h = hover_tmpl.replace('%{x}', '%{y}').replace('%{y:,}', '%{x:,}')
            fig.update_traces(hovertemplate=hover_tmpl_h, textposition='outside', cliponaxis=False)
            st.plotly_chart(fig, use_container_width=True)

            # Procedure mix trends (shares) — below the bar plot
            # Update title and tooltip based on toggle state
            if toggle_2024_only:
                time_period = "2024"
                tooltip_text = "Stacked bar shows the procedure mix for 2024. Each segment represents the percentage share of Sleeve, Gastric Bypass, and Other procedures, totaling 100%."
            else:
                time_period = "2021–2024"
                tooltip_text = "Stacked bars show annual shares of Sleeve, Gastric Bypass, and Other procedures (2021-2024). Each bar totals 100%."
            
            st.markdown(
                f"""
                <div class=\"nv-info-wrap\">
                  <div class=\"nv-h3\">Procedure Mix Trends ({time_period})</div>
                  <div class=\"nv-tooltip\"><span class=\"nv-info-badge\">i</span>
                    <div class=\"nv-tooltiptext\">
                      <b>Understanding this chart:</b><br/>
                      {tooltip_text}
                    </div>
                  </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            
            # Build stacked bar data from CSV
            if not df_activity.empty:
                # Filter years based on toggle
                if toggle_2024_only:
                    years_df = df_activity[df_activity['annee'] == 2024]
                else:
                    years_df = df_activity[df_activity['annee'].isin([2021, 2022, 2023, 2024])]
                
                # Calculate percentages for each year
                proc_trend_rows = []
                for year in years_df['annee'].unique():
                    year_data = years_df[years_df['annee'] == year]
                    
                    # Get totals
                    sleeve = year_data[year_data['baria_t'] == 'SLE']['n'].sum()
                    bypass = year_data[year_data['baria_t'] == 'BPG']['n'].sum()
                    
                    # Others: everything except Sleeve and Bypass
                    others_codes = ['ANN', 'DBP', 'GVC', 'NDD', 'ABL', 'REV']
                    others = year_data[year_data['baria_t'].isin(others_codes)]['n'].sum()
                    
                    total = sleeve + bypass + others
                    
                    if total > 0:
                        proc_trend_rows.append({
                            'Year': int(year),
                            'Procedure': 'Sleeve',
                            'Count': sleeve,
                            'Percentage': (sleeve / total) * 100
                        })
                        proc_trend_rows.append({
                            'Year': int(year),
                            'Procedure': 'Gastric Bypass',
                            'Count': bypass,
                            'Percentage': (bypass / total) * 100
                        })
                        proc_trend_rows.append({
                            'Year': int(year),
                            'Procedure': 'Other',
                            'Count': others,
                            'Percentage': (others / total) * 100
                        })
                
                proc_trend_df = pd.DataFrame(proc_trend_rows)
            else:
                proc_trend_df = pd.DataFrame()
            
            if not proc_trend_df.empty:
                proc_colors = {
                    'Sleeve': '#4C84C8',
                    'Gastric Bypass': '#7aa7f7',
                    'Other': '#f59e0b'
                }
                
                st.markdown("#### National: Procedure Mix Trends")
                
                # Add a column to determine which segments should show text
                # Only show text for segments > 5% to avoid unreadable small text
                proc_trend_df['show_text'] = proc_trend_df['Percentage'].apply(
                    lambda x: f'{x:.1f}%' if x > 5 else ''
                )
                
                # Create stacked bar chart
                fig = px.bar(
                    proc_trend_df,
                    x='Year',
                    y='Percentage',
                    color='Procedure',
                    title=f'National Procedure Mix ({time_period})',
                    color_discrete_map=proc_colors,
                    category_orders={'Procedure': ['Sleeve', 'Gastric Bypass', 'Other']},
                    text='show_text'
                )
                
                fig.update_traces(
                    textposition='inside',
                    hovertemplate='<b>%{fullData.name}</b><br>Year: %{x}<br>Share: %{y:.1f}%<br>Count: %{customdata[0]:,.0f}<extra></extra>',
                    customdata=proc_trend_df[['Count']].values
                )
                
                fig.update_layout(
                    height=400,
                    xaxis_title='Year',
                    yaxis_title='% of procedures',
                    plot_bgcolor='rgba(0,0,0,0)',
                    paper_bgcolor='rgba(0,0,0,0)',
                    barmode='stack',
                    yaxis=dict(range=[0, 100]),
                    xaxis=dict(type='category'),
                    showlegend=True,
                    legend=dict(
                        orientation="v",
                        yanchor="top",
                        y=1,
                        xanchor="left",
                        x=1.02
                    )
                )
                
                st.plotly_chart(fig, use_container_width=True)
                
                # Expander for Procedure Mix Trends chart
                with st.expander("What to look for and key findings"):
                    try:
                        if toggle_2024_only:
                            # For 2024 only data, show breakdown analysis
                            df_2024 = proc_trend_df[proc_trend_df['Year'] == 2024]
                            dominant = df_2024.sort_values('Percentage', ascending=False).iloc[0]
                            st.markdown(f"""
                            **What to look for:**
                            - Relative size of each procedure type segment in 2024
                            - Dominant procedure type
                            - Share distribution between major procedures

                            **Key findings (2024):**
                            - Dominant procedure: **{dominant['Procedure']}** (~{dominant['Percentage']:.0f}%)
                            - Procedure breakdown: {', '.join([f"**{row['Procedure']}**: {row['Percentage']:.1f}%" for _, row in df_2024.sort_values('Percentage', ascending=False).iterrows()])}
                            - The procedure mix reflects current evidence-based practice standards
                            """)
                        else:
                            # For multi-year data, show trend analysis
                            # Get sleeve and bypass trends
                            sleeve_trend = proc_trend_df[proc_trend_df['Procedure'] == 'Sleeve'].sort_values('Year')
                            bypass_trend = proc_trend_df[proc_trend_df['Procedure'] == 'Gastric Bypass'].sort_values('Year')
                            
                            sleeve_change = sleeve_trend.iloc[-1]['Percentage'] - sleeve_trend.iloc[0]['Percentage']
                            bypass_change = bypass_trend.iloc[-1]['Percentage'] - bypass_trend.iloc[0]['Percentage']
                            
                            st.markdown(f"""
                            **What to look for:**
                            - Stability vs shifts in procedure mix over time
                            - Which procedures gain or lose market share
                            - Year-over-year trends in procedure adoption
                            - Consistency in clinical practice

                            **Key findings (2021-2024):**
                            - **Sleeve Gastrectomy** maintains dominance (63-67% consistently)
                            - **Gastric Bypass** share is gradually increasing: {bypass_change:+.1f}% points since 2021
                            - **Sleeve** share slightly declining: {sleeve_change:+.1f}% points (still dominant)
                            - **Other procedures** declining, suggesting practice standardization
                            - Procedure mix is relatively stable, indicating established best practices
                            - The shift toward Bypass suggests growing comfort with more complex procedures
                            """)
                    except Exception as e:
                        if toggle_2024_only:
                            st.markdown("Review the stacked bar for procedure distribution in 2024.")
                        else:
                            st.markdown("Review the stacked bars for dominant procedures each year.")
                

                # National Averages Summary with toggle
                toggle_avg_2024_only = st.toggle("Show 2024 data only", value=False, key="avg_summary_toggle_2024")
                
                if toggle_avg_2024_only:
                    st.markdown("#### National Averages Summary (2024)")
                else:
                    st.markdown("#### National Averages Summary (2021-2024)")
                
                # Load and calculate metrics from CSV files
                try:
                    # Determine year filter based on toggle
                    if toggle_avg_2024_only:
                        year_filter = lambda df: df[df['annee'] == 2024]
                    else:
                        year_filter = lambda df: df[(df['annee'] >= 2021) & (df['annee'] <= 2024)]
                    
                    # 1. Avg Procedures per Hospital from TAB_VOL_HOP_YEAR.csv
                    vol_path = os.path.join(base_dir, "new_data", "ACTIVITY", "TAB_VOL_HOP_YEAR.csv")
                    df_vol = pd.read_csv(vol_path)
                    df_vol_filtered = year_filter(df_vol)
                    
                    # Calculate average: sum procedures per hospital, then average across hospitals
                    hospital_totals = df_vol_filtered.groupby('finessGeoDP')['n'].sum()
                    avg_procedures_per_hospital = int(hospital_totals.mean()) if not hospital_totals.empty else 0
                    
                    # 2. Avg Sleeve Gastrectomy % from TAB_TCN_NATL_YEAR.csv
                    tcn_path = os.path.join(base_dir, "new_data", "ACTIVITY", "TAB_TCN_NATL_YEAR.csv")
                    df_tcn = pd.read_csv(tcn_path)
                    df_tcn_filtered = year_filter(df_tcn)
                    
                    total_procedures_tcn = df_tcn_filtered['n'].sum()
                    sleeve_procedures = df_tcn_filtered[df_tcn_filtered['baria_t'] == 'SLE']['n'].sum()
                    sleeve_pct = (sleeve_procedures / total_procedures_tcn * 100) if total_procedures_tcn > 0 else 0.0
                    
                    # 3. Avg Robotic Approach % from TAB_APP_NATL_YEAR.csv
                    app_path = os.path.join(base_dir, "new_data", "ACTIVITY", "TAB_APP_NATL_YEAR.csv")
                    df_app = pd.read_csv(app_path)
                    df_app_filtered = year_filter(df_app)
                    
                    total_procedures_app = df_app_filtered['n'].sum()
                    robotic_procedures = df_app_filtered[df_app_filtered['vda'] == 'ROB']['n'].sum()
                    robotic_pct = (robotic_procedures / total_procedures_app * 100) if total_procedures_app > 0 else 0.0
                    
                    # Display metrics
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        st.metric("Avg Procedures per Hospital", f"{avg_procedures_per_hospital:,}")
                    
                    with col2:
                        st.metric("Avg Sleeve Gastrectomy", f"{sleeve_pct:.1f}%")
                    
                    with col3:
                        st.metric("Avg Robotic Approach", f"{robotic_pct:.1f}%")
                    
                    # Add interpretation expander
                    with st.expander("What to look for and key findings"):
                        if toggle_avg_2024_only:
                            st.markdown(f"""
                            **What to look for:**
                            - Volume benchmarks for 2024
                            - Current adoption rates of newer techniques
                            - Procedure preferences in the national landscape

                            **Key findings (2024):**
                            - Average hospital performs **{avg_procedures_per_hospital:,} procedures** in 2024
                            - **Sleeve Gastrectomy** represents {sleeve_pct:.1f}% of procedures (dominant choice)
                            - **Robotic approach** adoption at {robotic_pct:.1f}% in 2024
                            - Robotic surgery adoption is growing but still represents a small fraction
                            - Most procedures are still performed via conventional or laparoscopic approaches
                            """)
                        else:
                            st.markdown(f"""
                            **What to look for:**
                            - National volume patterns over 4 years (2021-2024)
                            - Trends in surgical approach adoption
                            - Procedure type preferences across the system

                            **Key findings (2021-2024):**
                            - Average hospital volume: **{avg_procedures_per_hospital:,} procedures** over 4 years
                            - **Sleeve Gastrectomy**: {sleeve_pct:.1f}% (dominant procedure nationally)
                            - **Robotic approach** growing from 4.0% (2021) to 6.2% (2024)
                            - Laparoscopic approaches declining as conventional and robotic gain share
                            - The shift toward robotics suggests technological adoption in bariatric surgery
                            - Most centers performing 50-150 total procedures over the 4-year period
                            """)
                        
                except Exception as e:
                    st.error(f"Error loading national averages data: {e}")
                    # Fallback display with zeros
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Avg Procedures per Hospital", "0")
                    with col2:
                        st.metric("Avg Sleeve Gastrectomy", "0.0%")
                    with col3:
                        st.metric("Avg Robotic Approach", "0.0%")
                

            else:
                st.info("Procedure trends chart unavailable - insufficient data or missing columns.")

