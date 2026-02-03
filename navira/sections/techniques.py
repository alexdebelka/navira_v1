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
                    This bar chart shows the distribution of different bariatric surgery procedures. The bars represent the total number of procedures performed, and the height indicates the volume of each procedure type.

                    **Time Period:**
                    - Toggle OFF: Shows data for the entire 2020–2024 period (5 years)
                    - Toggle ON: Shows data for 2024 only
                    """
                )
            # Prepare data for bar chart (2020-2024 totals)
            tot_data = []
            total_procedures = sum(procedure_totals_2020_2024.get(proc_code, 0) for proc_code in BARIATRIC_PROCEDURE_NAMES.keys())
            
            # Group less common procedures under "Other"
            other_procedures = ['NDD', 'GVC', 'DBP']  # Not Defined, Calibrated Vertical Gastroplasty, Bilio-pancreatic Diversion
            other_total = sum(procedure_totals_2020_2024.get(proc_code, 0) for proc_code in other_procedures)
            
            for proc_code, proc_name in BARIATRIC_PROCEDURE_NAMES.items():
                if proc_code in procedure_totals_2020_2024:
                    value = procedure_totals_2020_2024[proc_code]
                    
                    # Skip individual entries for procedures that will be grouped under "Other"
                    if proc_code in other_procedures:
                        continue
                        
                    raw_percentage = (value / total_procedures) * 100 if total_procedures > 0 else 0
                    # Show decimals for percentages less than 1%, otherwise round to whole number
                    percentage = round(raw_percentage, 1) if raw_percentage < 1 else round(raw_percentage)
                    tot_data.append({
                        'Procedure': proc_name,
                        'Value': value,
                        'Percentage': percentage
                    })
            
            # Add "Other" category for grouped procedures
            if other_total > 0:
                other_percentage = (other_total / total_procedures) * 100 if total_procedures > 0 else 0
                tot_data.append({
                    'Procedure': 'Other',
                    'Value': other_total,
                    'Percentage': other_percentage  # Store raw percentage, format later
                })
            chart_df = pd.DataFrame(tot_data).sort_values('Value', ascending=True)
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
                    This bar chart shows the distribution of different bariatric surgery procedures. The bars represent the total number of procedures performed, and the height indicates the volume of each procedure type.

                    **Time Period:**
                    - Toggle OFF: Shows data for the entire 2020–2024 period (5 years)
                    - Toggle ON: Shows data for 2024 only
                    """
                )
            # Prepare data for bar chart (2024 totals only)
            tot_data = []
            total_procedures = sum(procedure_totals_2024.get(proc_code, 0) for proc_code in BARIATRIC_PROCEDURE_NAMES.keys())
            
            # Group less common procedures under "Other"
            other_procedures = ['NDD', 'GVC', 'DBP']  # Not Defined, Calibrated Vertical Gastroplasty, Bilio-pancreatic Diversion
            other_total = sum(procedure_totals_2024.get(proc_code, 0) for proc_code in other_procedures)
            
            for proc_code, proc_name in BARIATRIC_PROCEDURE_NAMES.items():
                if proc_code in procedure_totals_2024:
                    value = procedure_totals_2024[proc_code]
                    
                    # Skip individual entries for procedures that will be grouped under "Other"
                    if proc_code in other_procedures:
                        continue
                        
                    raw_percentage = (value / total_procedures) * 100 if total_procedures > 0 else 0
                    # Show decimals for percentages less than 1%, otherwise round to whole number
                    percentage = round(raw_percentage, 1) if raw_percentage < 1 else round(raw_percentage)
                    tot_data.append({
                        'Procedure': proc_name,
                        'Value': value,
                        'Percentage': percentage
                    })
            
            # Add "Other" category for grouped procedures
            if other_total > 0:
                other_percentage = (other_total / total_procedures) * 100 if total_procedures > 0 else 0
                tot_data.append({
                    'Procedure': 'Other',
                    'Value': other_total,
                    'Percentage': other_percentage  # Store raw percentage, format later
                })
            chart_df = pd.DataFrame(tot_data).sort_values('Value', ascending=True)
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
                tooltip_text = "Stacked area shows the procedure mix for 2024 (single‑year view). The segments represent the percentage share of Sleeve, Gastric Bypass, and Other procedures, totaling 100%."
            else:
                time_period = "2021–2024"
                tooltip_text = "Stacked area shows annual shares of Sleeve, Gastric Bypass, and Other across eligible hospitals (2021-2024, excluding 2020). Each year sums to 100%."
            
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
            # Collapse to Sleeve, Gastric Bypass, Other
            known_codes = ['SLE','BPG','ANN','REV','ABL','DBP','GVC','NDD']
            available = [c for c in known_codes if c in df.columns]
            proc_trend_rows = []
            
            # Check if required columns exist (note: 'annee' is renamed to 'year' in data loading)
            year_col = 'year' if 'year' in df.columns else 'annee'
            if year_col in df.columns and available:
                # Filter years based on toggle state
                if toggle_2024_only:
                    years_to_process = [2024]
                else:
                    # Exclude 2020 from years
                    years_to_process = sorted([y for y in df[year_col].unique() if y > 2020])
                
                for year in years_to_process:
                    yearly = df[df[year_col] == year]
                    if yearly.empty:
                        continue
                    totals = yearly[available].sum(numeric_only=True)
                    sleeve = float(totals.get('SLE', 0))
                    bypass = float(totals.get('BPG', 0))
                    other = float(totals.sum() - sleeve - bypass)
                    total_sum = sleeve + bypass + other
                    if total_sum <= 0:
                        continue
                    for name, val in [('Sleeve', sleeve), ('Gastric Bypass', bypass), ('Other', other)]:
                        proc_trend_rows.append({'Year': int(year), 'Procedure': name, 'Share': val / total_sum * 100})
            elif not available:
                # If no procedure columns available, create dummy trend data
                if toggle_2024_only:
                    years_to_process = [2024]
                else:
                    years_to_process = [2021, 2022, 2023, 2024]
                
                for year in years_to_process:
                    # Dummy data: Sleeve 60%, Gastric Bypass 30%, Other 10%
                    proc_trend_rows.append({'Year': int(year), 'Procedure': 'Sleeve', 'Share': 60.0})
                    proc_trend_rows.append({'Year': int(year), 'Procedure': 'Gastric Bypass', 'Share': 30.0})
                    proc_trend_rows.append({'Year': int(year), 'Procedure': 'Other', 'Share': 10.0})
            
            proc_trend_df = pd.DataFrame(proc_trend_rows)
            if not proc_trend_df.empty:
                proc_colors = {'Sleeve': '#4C84C8', 'Gastric Bypass': '#7aa7f7', 'Other': '#f59e0b'}
                
                # Always use area chart. For single‑year (2024) repeat the same shares
                # at two x positions around 2024 so the stacked areas span the full width.
                plot_df = proc_trend_df.copy()
                if toggle_2024_only and not plot_df.empty:
                    try:
                        left_x = 2023.5
                        right_x = 2024.5
                        base_rows = plot_df.copy()
                        left = base_rows.copy(); left['Year'] = left_x
                        right = base_rows.copy(); right['Year'] = right_x
                        plot_df = pd.concat([left, right], ignore_index=True)
                    except Exception:
                        pass

                # Create side-by-side comparison
                col1, col2 = st.columns([2, 1])  # National graphs larger (2), Hospital comparison smaller (1)
                
                with col1:
                    st.markdown("#### National: Procedure Mix Trends")
                    fig = px.area(
                        plot_df, x='Year', y='Share', color='Procedure',
                        title=f'National Procedure Mix ({time_period})',
                        color_discrete_map=proc_colors,
                        category_orders={'Procedure': ['Sleeve', 'Gastric Bypass', 'Other']}
                    )
                    fig.update_layout(
                        height=380, 
                        xaxis_title='Year', 
                        yaxis_title='% of procedures', 
                        plot_bgcolor='rgba(0,0,0,0)', 
                        paper_bgcolor='rgba(0,0,0,0)'
                    )
                    # For single-year view, center 2024 and show only that tick
                    if toggle_2024_only:
                        fig.update_layout(xaxis=dict(tickmode='array', tickvals=[2024], ticktext=['2024'], range=[2023.25, 2024.75]))
                        fig.update_traces(hovertemplate='<b>%{fullData.name}</b><br>Year: 2024<br>Share: %{y:.1f}%<extra></extra>')
                    fig.update_traces(line=dict(width=0), opacity=0.9)
                    
                    st.plotly_chart(fig, use_container_width=True)
                
                # National Averages Summary
                st.markdown("#### National Averages Summary (2024)")
                
                if national_averages:
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        avg_total = national_averages.get('total_procedures_avg', 0)
                        st.metric("Avg Procedures per Hospital", f"{int(avg_total):,}")
                    
                    with col2:
                        proc_avgs = national_averages.get('procedure_averages', {})
                        sleeve_avg = proc_avgs.get('SLE', 0)
                        sleeve_pct = (sleeve_avg / avg_total * 100) if avg_total > 0 else 0
                        st.metric("Avg Sleeve Gastrectomy", f"{sleeve_pct:.1f}%")
                    
                    with col3:
                        approach_avgs = national_averages.get('approach_averages', {})
                        robotic_avg = approach_avgs.get('ROB', 0)
                        robotic_pct = (robotic_avg / avg_total * 100) if avg_total > 0 else 0
                        st.metric("Avg Robotic Approach", f"{robotic_pct:.1f}%")
                
                with st.expander("What to look for and key findings"):
                    try:
                        if toggle_2024_only:
                            # For 2024 only data, show breakdown analysis
                            dominant = proc_trend_df.sort_values('Share', ascending=False).iloc[0]
                            st.markdown(f"""
                            **What to look for:**
                            - Relative size of each procedure type segment in 2024
                            - Dominant procedure type
                            - Share distribution between major procedures

                            **Key findings:**
                            - Dominant procedure in 2024: **{dominant['Procedure']}** (~{dominant['Share']:.0f}%)
                            - Procedure breakdown: {', '.join([f"**{row['Procedure']}**: {row['Share']:.1f}%" for _, row in proc_trend_df.sort_values('Share', ascending=False).iterrows()])}
                            """)
                        else:
                            # For multi-year data, show trend analysis
                            last = proc_trend_df[proc_trend_df['Year']==proc_trend_df['Year'].max()].sort_values('Share', ascending=False).iloc[0]
                            st.markdown(f"""
                            **What to look for:**
                            - Stability vs shifts in procedure mix
                            - Which procedures gain or lose share across years
                            - Year-over-year trends in procedure dominance

                            **Key findings:**
                            - Dominant procedure in {int(proc_trend_df['Year'].max())}: **{last['Procedure']}** (~{last['Share']:.0f}%)
                            """)
                    except Exception:
                        if toggle_2024_only:
                            st.markdown("Review the stacked area for procedure distribution in 2024.")
                        else:
                            st.markdown("Review the stacked areas for dominant procedures each year.")
            else:
                st.info("Procedure trends chart unavailable - insufficient data or missing columns.")

    st.caption("Data computed across eligible hospital-years (≥25 procedures per year).")
