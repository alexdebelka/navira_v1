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
    
    # Compute approach data
    approach_trends = compute_approach_trends(df)
    approach_mix_2024 = compute_2024_approach_mix(df)
    
    st.markdown(
        """
        <div class=\"nv-info-wrap\">
          <div class=\"nv-h3\">Surgical Approach Mix (2024)</div>
          <div class=\"nv-tooltip\"><span class=\"nv-info-badge\">i</span>
            <div class=\"nv-tooltiptext\">
              <b>Understanding this chart:</b><br/>
              This pie chart shows the proportion of surgical approaches used in 2024 across all eligible hospitals.
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True
    )
    
    if approach_mix_2024:
        # Prepare data for pie chart
        pie_data = []
        for approach_name, count in approach_mix_2024.items():
            if count > 0:
                pie_data.append({
                    'Approach': approach_name,
                    'Count': count
                })
        
        pie_df = pd.DataFrame(pie_data)
        
        if not pie_df.empty:
            # Precompute integer percentage labels (no decimals)
            total_cnt = max(1, int(pie_df['Count'].sum()))
            pie_df['PctLabel'] = (pie_df['Count'] / total_cnt * 100).round(0).astype(int).astype(str) + '%'

            # Create side-by-side comparison
            col1, col2 = st.columns([2, 1])  # National graphs larger (2), Hospital comparison smaller (1)
            
            with col1:
                st.markdown("#### National: Surgical Approach Distribution")
                # Define a consistent color mapping used across pie and bars
                APPROACH_COLORS = {
                    'Coelioscopy': '#2E86AB',
                    'Robotic': '#F7931E',
                    'Open Surgery': '#A23B72'
                }

                fig = px.pie(
                    pie_df,
                    values='Count',
                    names='Approach',
                    title="National Approach Distribution (2024)",
                    color='Approach',
                    color_discrete_map=APPROACH_COLORS
                )
                
                fig.update_layout(
                    height=400,
                    showlegend=False,
                    font=dict(size=12)
                )
                
                fig.update_traces(
                    hovertemplate='<b>%{label}</b><br>Count: %{value:,}<br>Percentage: %{percent:.0f}%<extra></extra>',
                    textposition='outside',
                    text=pie_df['PctLabel'],
                    textinfo='text+label',
                    textfont=dict(size=16)
                )
                
                st.plotly_chart(fig, use_container_width=True)
            
            
            # Dropdown with What to look for + Key findings
            try:
                total_approaches = pie_df['Count'].sum()
                robotic_cnt = int(pie_df[pie_df['Approach'] == 'Robotic']['Count'].sum()) if 'Robotic' in pie_df['Approach'].values else 0
                robotic_share = (robotic_cnt / total_approaches * 100) if total_approaches > 0 else 0
                top_row = pie_df.sort_values('Count', ascending=False).iloc[0]
                with st.expander("What to look for and key findings"):
                    st.markdown(f"""
                    **What to look for:**
                    - Dominant approach segment size
                    - Relative share of Robotic vs others
                    - Presence of small slivers indicating rare approaches

                    **Key findings:**
                    - Robotic share in 2024: **{robotic_share:.1f}%** ({robotic_cnt:,} procedures)
                    - Most common approach: **{top_row['Approach']}** ({int(top_row['Count']):,})
                    """)
            except Exception:
                pass
    else:
        st.info("No approach data available for 2024.")
    
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
        try:
            first_year = 2020
            last_year = 2024
            rob_start = int(approach_trends['robotic'].get(first_year, 0))
            rob_end = int(approach_trends['robotic'].get(last_year, 0))
            pct_rob_2024 = (approach_trends['robotic'].get(2024, 0) / max(approach_trends['all'].get(2024, 1), 1)) * 100 if approach_trends['all'].get(2024, 0) else 0
            with st.expander("What to look for and key findings"):
                st.markdown(f"""
                **What to look for:**
                - Year‑over‑year growth or dips
                - Peak adoption year
                - Gap between robotic and total surgeries

                **Key findings:**
                - Robotic surgeries grew from **{rob_start:,}** (2020) to **{rob_end:,}** (2024)
                - Robotic share in 2024: **{pct_rob_2024:.1f}%** of all surgeries
                """)
        except Exception:
            pass


    # --- ROBOTIC SURGERY COMPARATIVE ANALYSIS ---
    st.header("Robotic Surgery Comparative Analysis")
    
    # Compute all robotic surgery comparisons
    robotic_geographic = compute_robotic_geographic_analysis(df)
    robotic_affiliation = compute_robotic_affiliation_analysis(df)
    robotic_volume = compute_robotic_volume_analysis(df)
    robotic_temporal = compute_robotic_temporal_analysis(df)
    robotic_institutional = compute_robotic_institutional_analysis(df)

    # 2. Geographic Analysis
    with st.expander("🗺️ 1. Geographic Analysis - Regional Robotic Adoption"):
        st.markdown("""
        **Understanding this analysis:**
        
        This chart shows robotic surgery adoption rates across different geographic regions of France. It reveals which regions are leading in robotic technology adoption and which may need more support.
        
        **How we calculated this:**
        - **Data source**: 2024 data for all eligible hospitals (≥25 procedures/year)
        - **Grouping**: Hospitals grouped by their geographic region (lib_reg column)
        - **Robotic count**: Sum of robotic procedures (ROB column) per region
        - **Total procedures**: Sum of all bariatric procedures per region
        - **Percentage**: (Robotic procedures / Total procedures) × 100 per region
        - **Filtering**: Only regions with >0 robotic procedures and valid percentages
        
        **What the percentages mean:**
        - **Percentage**: Shows what % of ALL bariatric surgeries in that region are performed robotically
        - **Example**: If ILE-DE-FRANCE shows 5.4%, it means 5.4% of all bariatric surgeries in Île‑de‑France are robotic
        - **Robotic count**: The actual number of robotic procedures performed in that region
        
        """)
        
        if robotic_geographic['regions'] and len(robotic_geographic['regions']) > 0:
            fig = px.bar(
                x=robotic_geographic['percentages'],
                y=robotic_geographic['regions'],
                orientation='h',
                title="Robotic Surgery Adoption by Region (2024)",
                color=robotic_geographic['percentages'],
                color_continuous_scale='Oranges',
                text=[f"{p:.1f}%" for p in robotic_geographic['percentages']]
            )
            
            fig.update_layout(
                xaxis_title="Robotic Surgery Percentage (%)",
                yaxis_title="",
                height=440,
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)',
                font=dict(size=12),
                margin=dict(l=160, r=50, t=80, b=40),
                yaxis=dict(automargin=True, categoryorder='total ascending')
            )
            
            fig.update_traces(
                hovertemplate='<b>%{y}</b><br>Percentage: %{x:.1f}%<br>Robotic: %{customdata}<extra></extra>',
                customdata=robotic_geographic['robotic_counts']
            )
            fig.update_traces(textposition='outside', cliponaxis=False)
            
            st.plotly_chart(fig, use_container_width=True)
            try:
                top_idx = int(pd.Series(robotic_geographic['percentages']).idxmax())
                top_region = robotic_geographic['regions'][top_idx]
                top_pct = robotic_geographic['percentages'][top_idx]
                with st.expander("What to look for and key findings"):
                    st.markdown(f"""
                    **What to look for:**
                    - Regions with notably higher robotic percentages
                    - Regional disparities in access to robotic surgery
                    
                    **Key findings:**
                    - Highest regional adoption: **{top_region}** at **{top_pct:.1f}%**
                    """)
            except Exception:
                pass
        else:
            st.info("No geographic data available. Region information may not be included in the dataset.")
    
    # 3. Institutional Analysis
    with st.expander("🏥 2. Affiliation Analysis"):
        st.markdown("""
        **Understanding this analysis:**
        
        This chart compares robotic surgery adoption between hospital sectors: public vs private institutions.
        
        **How we calculated this:**
        - **Data source**: 2024 data for all eligible hospitals (≥25 procedures/year)
        - **Sector grouping**: Hospitals grouped by sector (public vs private)
        - **Robotic count**: Sum of robotic procedures (ROB column) per hospital type
        - **Total procedures**: Sum of all bariatric procedures per hospital type
        - **Percentage**: (Robotic procedures / Total procedures) × 100 per hospital type
        
        **What the percentages mean:**
        - **Percentage**: Share of all bariatric surgeries in that sector that are robotic
        - **Robotic count**: The actual number of robotic procedures performed in that sector
        """)
        
        # Merged bar chart: sector and affiliation side-by-side
        merged_x = []
        merged_y = []
        merged_color = []
        # Sector bars removed per request (keep only affiliation bars)
        try:
            if robotic_affiliation['affiliations'] and robotic_affiliation['percentages']:
                for t, v in zip(robotic_affiliation['affiliations'], robotic_affiliation['percentages']):
                    merged_x.append(f"Affil – {t}")
                    merged_y.append(v)
                    merged_color.append('Affiliation')
        except Exception:
            pass
        if merged_x:
            fig_merge = px.bar(x=merged_x, y=merged_y, color=merged_color, title="Robotic Adoption by Sector and Affiliation (2024)",
                               color_discrete_map={'Sector':'#34a853','Affiliation':'#db4437'})
            fig_merge.update_layout(height=380, plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', xaxis_title=None, yaxis_title='Robotic Surgery Percentage (%)', showlegend=False)
            fig_merge.update_traces(hovertemplate='<b>%{x}</b><br>Percentage: %{y:.1f}%<extra></extra>', marker_line_width=0)
            st.plotly_chart(fig_merge, use_container_width=True)
            with st.expander("What to look for and key findings"):
                try:
                    import numpy as np
                    sector_vals = np.array(robotic_institutional.get('sector',{}).get('percentages',[]) or [])
                    aff_vals = np.array(robotic_affiliation.get('percentages',[]) or [])
                    s_max = sector_vals.max() if sector_vals.size else None
                    a_max = aff_vals.max() if aff_vals.size else None
                    st.markdown(f"""
                    **What to look for:**
                    - Sector vs affiliation differences in adoption
                    - Which subgroups stand out at the high end

                    **Key findings:**
                    - Highest sector value: **{s_max:.1f}%** if available
                    - Highest affiliation value: **{a_max:.1f}%** if available
                    """)
                except Exception:
                    st.markdown("Insights unavailable due to missing values.")
        else:
            st.info("No sector/affiliation data available for the merged comparison.")
    
    with st.expander("📊 3. Volume-based Analysis - Hospital Volume vs Robotic Adoption"):
        st.markdown("""
        **Understanding this analysis:**
        
        This chart shows how robotic surgery adoption varies with hospital volume. It examines whether high‑volume centers are more likely to use robotic technology.
        
        **How we calculated this (default chart):**
        - **Data source**: 2024 data for all eligible hospitals (≥25 procedures/year)
        - **Volume categorization**: Hospitals grouped by annual procedure volume:
          * less than 50 procedures/year
          * 50–100 procedures/year  
          * 100–200 procedures/year
          * more than 200 procedures/year
        - **Weighted percentage**: For each volume group, we compute (sum of robotic surgeries ÷ sum of all surgeries) × 100. This weights each hospital by its number of surgeries so large centers are represented proportionally.
        - Hover shows: **weighted % robotic** and the **robotic count** in that group.
        
        **Alternative view (optional expander below the chart):**
        - **Unweighted mean**: Average of per‑hospital robotic shares within each group (each hospital contributes equally, regardless of size).
        
        **Why both matter:**
        - Weighted view answers: "What share of all surgeries in this group are robotic?" (system‑wide perspective).
        - Unweighted view answers: "What is the typical hospital's robotic share in this group?" (center‑level perspective).
        
        **Questions this helps answer:**
        - Do higher‑volume centers have higher robotic adoption?
        - Is the difference driven by a few very large programs or broadly across centers?
        """)
        
        if robotic_volume['volume_categories'] and len(robotic_volume['volume_categories']) > 0:
            # Keep only the continuous scatter with trendline (as per screenshot)
            try:
                dist_df = compute_robotic_volume_distribution(df)
            except Exception:
                dist_df = pd.DataFrame()
            if not dist_df.empty:
                st.subheader("Continuous relationship: volume vs robotic %")
                
                # Add hospital names to the dataframe for hover information
                try:
                    establishments, _ = get_dataframes()
                    if 'id' in establishments.columns and 'name' in establishments.columns:
                        # Ensure consistent data types
                        establishments['id'] = establishments['id'].astype(str)
                        dist_df['hospital_id'] = dist_df['hospital_id'].astype(str)
                        
                        # Merge hospital names
                        dist_df = dist_df.merge(
                            establishments[['id', 'name']].drop_duplicates(subset=['id']),
                            left_on='hospital_id',
                            right_on='id',
                            how='left'
                        )
                        dist_df['hospital_name'] = dist_df['name'].fillna('Unknown Hospital')
                    else:
                        dist_df['hospital_name'] = 'Hospital ' + dist_df['hospital_id'].astype(str)
                except Exception:
                    dist_df['hospital_name'] = 'Hospital ' + dist_df['hospital_id'].astype(str)
                
                cont = px.scatter(
                    dist_df,
                    x='total_surgeries',
                    y='hospital_pct',
                    color='volume_category',
                    hover_data=['hospital_name'],
                    opacity=0.65,
                    title='Hospital volume (continuous) vs robotic %'
                )
                # Linear trendline removed per request
                cont.update_layout(
                    xaxis_title='Total surgeries (2024)',
                    yaxis_title='Robotic % (per hospital)',
                    height=420,
                    plot_bgcolor='rgba(0,0,0,0)',
                    paper_bgcolor='rgba(0,0,0,0)'
                )
                st.plotly_chart(cont, use_container_width=True)

            # Annotations: hospitals and average surgeries per bin
            try:
                num_hosp = robotic_volume.get('hospitals')
                total_counts = robotic_volume.get('total_counts')
                ann_text = []
                if num_hosp and total_counts:
                    avg_surg = [round(tc / h, 1) if h else 0 for tc, h in zip(total_counts, num_hosp)]
                    for xc, h, a in zip(robotic_volume['volume_categories'], num_hosp, avg_surg):
                        ann_text.append(f"{h} hospitals\\n~{a} surgeries/hosp")
                    fig_ann = px.bar(x=robotic_volume['volume_categories'], y=[0]*len(num_hosp))
                    fig_ann.update_layout(height=1)  # placeholder
                st.caption("Hospitals and avg surgeries per bin: " + ", ".join(ann_text))
            except Exception:
                pass
