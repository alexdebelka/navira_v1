import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import sys
import os

# Add the parent directory to the Python path to import lib
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from lib.national_utils import (
    compute_approach_trends,
    compute_2024_approach_mix,
    compute_robotic_geographic_analysis,
    compute_robotic_affiliation_analysis,
    compute_robotic_volume_analysis,
    compute_robotic_temporal_analysis,
    compute_robotic_institutional_analysis,
    compute_robotic_volume_distribution
)
from navira.data_loader import get_dataframes


def render_robot(df: pd.DataFrame):
    """Render the Robot section for national page.
    
    This section contains:
    - Approach Trends (surgical approach mix and trends)
    - Robotic Surgery Comparative Analysis
    """
    
    st.header("Approach Trends")
    
    # Get base directory for CSV loading
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    # Add toggle for year filtering
    toggle_robot_2024_only = st.toggle("Show 2024 data only", value=False, key="robot_approach_toggle_2024")
    
    # Load data from CSV
    try:
        app_path = os.path.join(base_dir, "new_data", "ACTIVITY", "TAB_APP_NATL_YEAR.csv")
        df_app = pd.read_csv(app_path)
        
        # Filter by year based on toggle
        if toggle_robot_2024_only:
            df_app_filtered = df_app[df_app['annee'] == 2024]
            year_label = "2024"
        else:
            df_app_filtered = df_app[(df_app['annee'] >= 2021) & (df_app['annee'] <= 2024)]
            year_label = "2021-2024"
        
        # Map approach codes to names
        approach_map = {
            'COE': 'Laparoscopy',
            'LAP': 'Open Surgery',
            'ROB': 'Robotic'
        }
        
        # Aggregate data
        approach_totals = df_app_filtered.groupby('vda')['n'].sum().reset_index()
        approach_totals['Approach'] = approach_totals['vda'].map(approach_map)
        approach_totals = approach_totals.rename(columns={'n': 'Count'})
        
        st.markdown(
            f"""
            <div class=\"nv-info-wrap\">
              <div class=\"nv-h3\">Surgical Approach Mix ({year_label})</div>
              <div class=\"nv-tooltip\"><span class=\"nv-info-badge\">i</span>
                <div class=\"nv-tooltiptext\">
                  <b>Understanding this chart:</b><br/>
                  This pie chart shows the proportion of surgical approaches used across all bariatric procedures.
                </div>
              </div>
            </div>
            """,
            unsafe_allow_html=True
        )
        
        if not approach_totals.empty:
            # Precompute integer percentage labels
            total_cnt = max(1, int(approach_totals['Count'].sum()))
            approach_totals['PctLabel'] = (approach_totals['Count'] / total_cnt * 100).round(0).astype(int).astype(str) + '%'

            # Create side-by-side comparison
            col1, col2 = st.columns([2, 1])
            
            with col1:
                st.markdown(f"#### National: Surgical Approach Distribution ({year_label})")
                # Define consistent color mapping
                APPROACH_COLORS = {
                    'Laparoscopy': '#2E86AB',
                    'Open Surgery': '#A6CEE3',
                    'Robotic': '#F7931E'
                }

                fig = px.pie(
                    approach_totals,
                    values='Count',
                    names='Approach',
                    title=f"National Approach Distribution ({year_label})",
                    color='Approach',
                    color_discrete_map=APPROACH_COLORS
                )
                
                fig.update_layout(
                    height=400,
                    showlegend=False,
                    font=dict(size=12)
                )
                
                fig.update_traces(
                    hovertemplate='<b>%{label}</b><br>Count: %{value:,}<br>Percentage: %{percent:.1f}%<extra></extra>',
                    textposition='outside',
                    text=approach_totals['PctLabel'],
                    textinfo='text+label',
                    textfont=dict(size=16)
                )
                
                st.plotly_chart(fig, use_container_width=True)
            
            # Enhanced "What to look for" expander
            with st.expander("What to look for and key findings"):
                try:
                    total_approaches = approach_totals['Count'].sum()
                    robotic_cnt = int(approach_totals[approach_totals['Approach'] == 'Robotic']['Count'].sum()) if 'Robotic' in approach_totals['Approach'].values else 0
                    robotic_share = (robotic_cnt / total_approaches * 100) if total_approaches > 0 else 0
                    
                    laparoscopy_cnt = int(approach_totals[approach_totals['Approach'] == 'Laparoscopy']['Count'].sum()) if 'Laparoscopy' in approach_totals['Approach'].values else 0
                    laparoscopy_pct = (laparoscopy_cnt / total_approaches * 100) if total_approaches > 0 else 0
                    
                    top_row = approach_totals.sort_values('Count', ascending=False).iloc[0]
                    top_pct = (top_row['Count'] / total_approaches * 100) if total_approaches > 0 else 0
                    
                    if toggle_robot_2024_only:
                        st.markdown(f"""
                        **What to look for:**
                        - Relative proportion of each surgical approach in 2024
                        - Dominant approach vs emerging techniques
                        - Share of robotic surgery in the current year
                        - Balance between traditional and innovative approaches

                        **Key findings (2024):**
                        - **Robotic surgery** accounts for **{robotic_share:.1f}%** of procedures ({robotic_cnt:,} cases)
                        - Most common approach: **{top_row['Approach']}** ({int(top_row['Count']):,} procedures, {top_pct:.1f}%)
                        - **Laparoscopy** represents **{laparoscopy_pct:.1f}%** of surgeries
                        - Robotic adoption shows continued growth trajectory
                        """)
                    else:
                        st.markdown(f"""
                        **What to look for:**
                        - Overall distribution across 4 years (2021-2024)
                        - Which approach dominates the national landscape
                        - Cumulative robotic surgery volume and market share
                        - Evolution of surgical technique preferences

                        **Key findings (2021-2024):**
                        - **Robotic surgery**: **{robotic_share:.1f}%** of all {int(total_approaches):,} procedures
                        - Total robotic procedures: **{robotic_cnt:,}** over 4 years
                        - Most common approach: **{top_row['Approach']}** ({int(top_row['Count']):,} procedures, {top_pct:.1f}%)
                        - **Laparoscopy** is the dominant technique at **{laparoscopy_pct:.1f}%**
                        - Robotic share growing year-over-year from 4.0% (2021) to 6.2% (2024)
                        """)
                except Exception as e:
                    st.markdown("Unable to compute detailed insights.")
        else:
            st.info(f"No approach data available for {year_label}.")
    
    except Exception as e:
        st.error(f"Error loading approach data: {e}")
        st.info("Unable to load surgical approach data from CSV.")
    
    # Compute approach trends for the line chart (keep using df for now)
    approach_trends = compute_approach_trends(df)

    
    # Single column layout for trends
    with st.container():
        st.markdown(
            """
            <div class=\"nv-info-wrap\">
              <div class=\"nv-h3\">Surgical Approach Trends (2020–2024)</div>
              <div class=\"nv-tooltip\"><span class=\"nv-info-badge\">i</span>
                <div class=\"nv-tooltiptext\">
                  <b>Understanding this chart:</b><br/>
                  This line chart tracks the number of robotic surgeries by year from 2020 to 2024.
                </div>
              </div>
            </div>
            """,
            unsafe_allow_html=True
        )
        
        # Load hospital-level robotic data for additional metrics
        try:
            rob_hosp_path = os.path.join(base_dir, "new_data", "ACTIVITY", "TAB_ROB_HOP_12M.csv")
            df_rob_hosp = pd.read_csv(rob_hosp_path)
            
            # Calculate metrics
            num_hospitals = len(df_rob_hosp)
            avg_rob_per_hospital = int(df_rob_hosp['n'].mean())
            total_rob_12m = int(df_rob_hosp['n'].sum())
            
            # Display metrics in columns
            met_col1, met_col2, met_col3 = st.columns(3)
            
            with met_col1:
                st.metric(
                    "Hospitals Performing Robotic Surgery", 
                    f"{num_hospitals}",
                    help="Number of hospitals that performed at least 1 robotic bariatric surgery (recent 12 months)"
                )
            
            with met_col2:
                st.metric(
                    "Avg Robotic Procedures per Hospital", 
                    f"{avg_rob_per_hospital}",
                    help="Average number of robotic procedures per hospital (recent 12 months)"
                )
            
            with met_col3:
                st.metric(
                    "Total Robotic (12-month snapshot)", 
                    f"{total_rob_12m:,}",
                    help="Total robotic procedures across all hospitals (recent 12 months)"
                )
        except Exception as e:
            # If we can't load the data, just skip the metrics
            pass
        
        trend_data = []
        for year in range(2020, 2025):
            trend_data.append({
                'Year': year,
                'All Surgeries': approach_trends['all'].get(year, 0),
                'Robotic Surgeries': approach_trends['robotic'].get(year, 0)
            })

        trend_df = pd.DataFrame(trend_data)

        fig = go.Figure()

        fig.add_trace(go.Scatter(
            x=trend_df['Year'],
            y=trend_df['Robotic Surgeries'],
            mode='lines+markers',
            name='Robotic Surgeries',
            line=dict(color='#F7931E', width=3),
            marker=dict(size=8, color='#F7931E')
        ))

        fig.update_layout(
            title="Robotic Surgery Trends (2020-2024)",
            xaxis_title="Year",
            yaxis_title="Number of Robotic Surgeries",
            hovermode='x unified',
            height=400,
            showlegend=False,
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            font=dict(size=12),
            margin=dict(l=50, r=50, t=80, b=50)
        )

        st.plotly_chart(fig, use_container_width=True)
        
        with st.expander("What to look for and key findings"):
            try:
                first_year = 2020
                last_year = 2024
                rob_start = int(approach_trends['robotic'].get(first_year, 0))
                rob_end = int(approach_trends['robotic'].get(last_year, 0))
                pct_rob_2024 = (approach_trends['robotic'].get(2024, 0) / max(approach_trends['all'].get(2024, 1), 1)) * 100 if approach_trends['all'].get(2024, 0) else 0
                
                # Calculate growth rate
                growth_pct = ((rob_end - rob_start) / rob_start * 100) if rob_start > 0 else 0
                
                st.markdown(f"""
                **What to look for:**
                - Year-over-year growth trajectory in total robotic surgeries
                - Acceleration or deceleration in adoption rate
                - Current number of hospitals offering robotic surgery
                - Average volume per hospital (indicates both adoption and experience level)

                **Key findings (2020-2024):**
                - Total robotic surgeries grew from **{rob_start:,}** (2020) to **{rob_end:,}** (2024)
                - Overall growth rate: **{growth_pct:+.1f}%** over 5 years
                - Robotic share in 2024: **{pct_rob_2024:.1f}%** of all bariatric surgeries
                - **{num_hospitals} hospitals** currently performing robotic bariatric surgery
                - Average robotic volume per hospital: **~{avg_rob_per_hospital} procedures** per year
                
                **Insights on adoption:**
                - Robotic surgery is spreading to more centers but remains in **early adoption phase**
                - Most centers perform relatively low volumes (avg ~{avg_rob_per_hospital}/year)
                - This suggests technology is accessible but not yet mainstream
                - Both volume growth AND number of centers are increasing
                
                **Calculation methodology:**
                - Hospital count and averages based on TAB_ROB_HOP_12M.csv (most recent 12-month period)
                - Only hospitals with at least 1 robotic procedure counted
                - Average = Total robotic procedures ÷ Number of hospitals performing robotic surgery
                """)
            except Exception:
                st.markdown("""
                Review the chart for year-over-year growth patterns in robotic surgery adoption.
                """)
    
    # --- Robot share scatter plot (National level) ---
    st.markdown("---")
    st.markdown("#### Robot share vs Hospital Volume")
    
    # Load robotic data from TAB_ROB_HOP_12M.csv
    try:
        rob_path = os.path.join(base_dir, "new_data", "ACTIVITY", "TAB_ROB_HOP_12M.csv")
        rob_data = pd.read_csv(rob_path)
        
        if not rob_data.empty and "TOT" in rob_data.columns and "PCT_app" in rob_data.columns:
            d = rob_data.copy()
            d["finessGeoDP"] = d.get("finessGeoDP", "").astype(str)
            d["TOT"] = pd.to_numeric(d.get("TOT", 0), errors="coerce").fillna(0)
            d["PCT_app"] = pd.to_numeric(d.get("PCT_app", 0), errors="coerce").fillna(0)
            
            # National level - show all hospitals
            d_national = d.copy()
            
            if not d_national.empty:
                fig_rob = go.Figure()
                # All hospitals
                fig_rob.add_trace(go.Scatter(
                    x=d_national["TOT"], y=d_national["PCT_app"], mode="markers",
                    marker=dict(color="#60a5fa", size=6, opacity=0.75), name="All hospitals",
                    hovertemplate='Procedures: %{x:.0f}<br>Robot share: %{y:.1f}%<extra></extra>'
                ))
                
                fig_rob.update_layout(
                    height=420,
                    xaxis_title="Number of procedures per year (any approach)", 
                    yaxis_title="Robot share (%)",
                    xaxis=dict(range=[0, None]), 
                    yaxis=dict(range=[0, 100]),
                    plot_bgcolor='rgba(0,0,0,0)', 
                    paper_bgcolor='rgba(0,0,0,0)'
                )
                st.plotly_chart(fig_rob, use_container_width=True)
                st.caption("Based on robotic procedures last 12 months (TAB_ROB_HOP_12M)")
            else:
                st.info("No data to build robot share scatter for national scope.")
        else:
            st.info("No robotic dataset available for scatter plot.")
    except Exception as e:
        st.warning(f"Could not load robot share data: {e}")
    
    # --- Robotic Adoption Trends Over Time ---
    st.markdown("---")
    st.markdown("#### Robotic Surgery Adoption Trends (2021-2024)")
    
    # What to look for guidance
    with st.expander("ℹ️ What to look for"):
        st.markdown("""
        **Understanding robotic adoption:**
        - Shows the percentage of all bariatric procedures performed using robotic assistance over time
        - Includes all procedure types (Sleeve, Bypass, etc.)
        
        **Key findings:**
        - Steady increase from **4.0% in 2021** to **6.2% in 2024**
        - Growth indicates expanding robotic surgery capabilities across hospitals
        
        **What to watch for:**
        - 📈 **Continuous growth**: Positive sign of technology adoption
        - **Plateaus**: May indicate capacity constraints or training limitations
        - **Regional variation**: Some areas may adopt faster than others
        
        **Note:** Robotic surgery typically shows higher adoption rates for bypass procedures compared to sleeve gastrectomy
        """)
    
    try:
        app_path = os.path.join(base_dir, "new_data", "ACTIVITY", "TAB_APP_NATL_YEAR.csv")
        df_app_trends = pd.read_csv(app_path)
        
        # Filter to 2021-2024 and get robotic percentage
        df_trends = df_app_trends[(df_app_trends['annee'] >= 2021) & (df_app_trends['annee'] <= 2024)].copy()
        
        if not df_trends.empty:
            # Get robotic rates by year
            robotic_trends = df_trends[df_trends['vda'] == 'ROB'][['annee', 'pct']].copy()
            robotic_trends = robotic_trends.sort_values('annee')
            
            if not robotic_trends.empty:
                fig_trends = go.Figure()
                fig_trends.add_trace(go.Scatter(
                    x=robotic_trends['annee'],
                    y=robotic_trends['pct'],
                    mode='lines+markers+text',
                    text=[f"{r:.1f}%" for r in robotic_trends['pct']],
                    textposition="top center",
                    line=dict(color='#F7931E', width=3),
                    marker=dict(size=10, color='#F7931E'),
                    name='Robotic Rate',
                    showlegend=False
                ))
                
                fig_trends.update_layout(
                    height=350,
                    xaxis_title="Year",
                    yaxis_title="Robotic Surgery Rate (%)",
                    plot_bgcolor='rgba(0,0,0,0)',
                    paper_bgcolor='rgba(0,0,0,0)',
                    xaxis=dict(
                        showgrid=False,
                        type='category',
                        tickfont=dict(color='#888')
                    ),
                    yaxis=dict(
                        showgrid=True,
                        gridcolor='rgba(255,255,255,0.1)',
                        range=[0, max(robotic_trends['pct']) * 1.3],
                        tickfont=dict(color='#888')
                    )
                )
                
                st.plotly_chart(fig_trends, use_container_width=True, key="robot_adoption_trends")
                st.caption("Source: TAB_APP_NATL_YEAR.csv - National robotic adoption rate across all bariatric procedures")
            else:
                st.info("No robotic trend data available")
        else:
            st.info("No trend data available for the selected period")
            
    except Exception as e:
        st.warning(f"Could not load robotic adoption trends: {e}")
