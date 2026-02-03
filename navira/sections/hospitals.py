import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import sys
import os

# Add the parent directory to the Python path to import lib
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


def render_hospitals(procedure_details: pd.DataFrame):
    """Render the Hospitals section for national page.
    
    This section contains:
    - Advanced Procedure Metrics
    - Procedure-specific robotic rates
    - Primary vs revisional surgery analysis
    - Robotic adoption trends by procedure
    """
    
    st.header("Advanced Procedure Metrics")
    
    if not procedure_details.empty:
        st.markdown(
            """
            <div class=\"nv-info-wrap\">
              <div class=\"nv-h3\">Detailed Procedure Analysis</div>
              <div class=\"nv-tooltip\"><span class=\"nv-info-badge\">i</span>
                <div class=\"nv-tooltiptext\">
                  <b>Understanding this analysis:</b><br/>
                  This section provides detailed insights into surgical procedures, including procedure-specific robotic rates, primary vs revisional surgery patterns, and robotic approach by procedure type. Data covers 2020-2024 across all eligible hospitals.<br/><br/>
                  <b>Key Metrics:</b><br/>
                  • Procedure-specific robotic rates<br/>
                  • Primary vs revisional surgery breakdown<br/>
                  • Robotic approach adoption by procedure type
                </div>
              </div>
            </div>
            """,
            unsafe_allow_html=True
        )
        
        # Procedure-specific robotic rates
        st.markdown("#### Procedure-Specific Robotic Rates (2024)")
        
        # Calculate robotic rates by procedure type for 2024
        procedure_2024 = procedure_details[procedure_details['year'] == 2024]
        
        if not procedure_2024.empty:
            robotic_by_procedure = procedure_2024[
                procedure_2024['surgical_approach'] == 'ROB'
            ].groupby('procedure_type')['procedure_count'].sum().reset_index()
            robotic_by_procedure = robotic_by_procedure.rename(columns={'procedure_count': 'robotic_count'})
            
            total_by_procedure = procedure_2024.groupby('procedure_type')['procedure_count'].sum().reset_index()
            total_by_procedure = total_by_procedure.rename(columns={'procedure_count': 'total_count'})
            
            # Merge to calculate percentages
            procedure_robotic_rates = total_by_procedure.merge(
                robotic_by_procedure, 
                on='procedure_type', 
                how='left'
            ).fillna(0)
            procedure_robotic_rates['robotic_rate'] = (
                procedure_robotic_rates['robotic_count'] / procedure_robotic_rates['total_count'] * 100
            )
            
            # Map procedure codes to names
            procedure_names = {
                'SLE': 'Sleeve Gastrectomy',
                'BPG': 'Gastric Bypass', 
                'ANN': 'Gastric Banding',
                'REV': 'Revision Surgery',
                'ABL': 'Band Removal',
                'DBP': 'Bilio-pancreatic Diversion',
                'GVC': 'Gastroplasty',
                'NDD': 'Not Defined'
            }
            
            procedure_robotic_rates['procedure_name'] = procedure_robotic_rates['procedure_type'].map(procedure_names)
            procedure_robotic_rates = procedure_robotic_rates.sort_values('robotic_rate', ascending=False)
            
            # Filter to show only Sleeve Gastrectomy and Gastric Bypass
            procedure_robotic_rates = procedure_robotic_rates[
                procedure_robotic_rates['procedure_type'].isin(['SLE', 'BPG'])
            ]
            
            # Create visualization
            fig = px.bar(
                procedure_robotic_rates,
                x='robotic_rate',
                y='procedure_name',
                orientation='h',
                title="Robotic Adoption by Procedure Type (2024)",
                labels={'robotic_rate': 'Robotic Rate (%)', 'procedure_name': 'Procedure Type'},
                text='robotic_rate'
            )
            
            fig.update_traces(
                texttemplate='%{text:.1f}%',
                textposition='outside',
                cliponaxis=False
            )
            
            fig.update_layout(
                height=400,
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)',
                yaxis={'categoryorder': 'total ascending'}
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
            # Show summary table
            display_table = procedure_robotic_rates[['procedure_name', 'total_count', 'robotic_count', 'robotic_rate']].copy()
            display_table['robotic_rate'] = display_table['robotic_rate'].round(1)
            display_table = display_table.rename(columns={
                'procedure_name': 'Procedure',
                'total_count': 'Total Procedures',
                'robotic_count': 'Robotic Procedures',
                'robotic_rate': 'Robotic Rate (%)'
            })
            
            st.dataframe(display_table, use_container_width=True, hide_index=True)
        
        # Primary vs Revisional Surgery Analysis
        st.markdown("#### Primary vs Revisional Surgery (2024)")
        
        if not procedure_2024.empty:
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("##### Primary Procedures")
                primary_2024 = procedure_2024[procedure_2024['is_revision'] == 0]
                if not primary_2024.empty:
                    total_primary = primary_2024['procedure_count'].sum()
                    robotic_primary = primary_2024[primary_2024['surgical_approach'] == 'ROB']['procedure_count'].sum()
                    robotic_rate_primary = (robotic_primary / total_primary * 100) if total_primary > 0 else 0
                    
                    st.metric("Total Primary Procedures", f"{int(total_primary):,}")
                    st.metric("Robotic Primary Procedures", f"{int(robotic_primary):,}")
                    st.metric("Robotic Rate (Primary)", f"{robotic_rate_primary:.1f}%")
            
            with col2:
                st.markdown("##### Revision Procedures")
                revision_2024 = procedure_2024[procedure_2024['is_revision'] == 1]
                if not revision_2024.empty:
                    total_revision = revision_2024['procedure_count'].sum()
                    robotic_revision = revision_2024[revision_2024['surgical_approach'] == 'ROB']['procedure_count'].sum()
                    robotic_rate_revision = (robotic_revision / total_revision * 100) if total_revision > 0 else 0
                    
                    st.metric("Total Revision Procedures", f"{int(total_revision):,}")
                    st.metric("Robotic Revision Procedures", f"{int(robotic_revision):,}")
                    st.metric("Robotic Rate (Revision)", f"{robotic_rate_revision:.1f}%")
        
        # Robotic Approach by Procedure Type Over Time
        st.markdown("#### Robotic Adoption Trends by Procedure (2020-2024)")
        
        # Calculate yearly robotic rates by procedure
        yearly_procedure_trends = []
        
        for year in range(2020, 2025):
            year_data = procedure_details[procedure_details['year'] == year]
            if year_data.empty:
                continue
                
            for proc_type in year_data['procedure_type'].unique():
                proc_data = year_data[year_data['procedure_type'] == proc_type]
                total_procedures = proc_data['procedure_count'].sum()
                robotic_procedures = proc_data[proc_data['surgical_approach'] == 'ROB']['procedure_count'].sum()
                
                if total_procedures > 0:
                    robotic_rate = (robotic_procedures / total_procedures) * 100
                    yearly_procedure_trends.append({
                        'year': year,
                        'procedure_type': proc_type,
                        'procedure_name': procedure_names.get(proc_type, proc_type),
                        'robotic_rate': robotic_rate,
                        'total_procedures': total_procedures
                    })
        
        if yearly_procedure_trends:
            trends_df = pd.DataFrame(yearly_procedure_trends)
            
            # Filter to show only Sleeve Gastrectomy and Gastric Bypass
            trends_df = trends_df[trends_df['procedure_type'].isin(['SLE', 'BPG'])]
            
            if not trends_df.empty:
                fig = px.line(
                    trends_df,
                    x='year',
                    y='robotic_rate',
                    color='procedure_name',
                    title="Robotic Adoption Trends by Major Procedure Types",
                    labels={'robotic_rate': 'Robotic Rate (%)', 'year': 'Year', 'procedure_name': 'Procedure'}
                )
                
                fig.update_layout(
                    height=400,
                    plot_bgcolor='rgba(0,0,0,0)',
                    paper_bgcolor='rgba(0,0,0,0)'
                )
                
                st.plotly_chart(fig, use_container_width=True)
        
        # Summary insights
        with st.expander("Key Insights and Analysis"):
            st.markdown("""
            **Key Findings from Advanced Procedure Analysis:**
            
            **Procedure-Specific Robotic Adoption:**
            - Shows which procedures are most/least likely to be performed robotically
            - Identifies opportunities for robotic surgery expansion
            - Reveals procedure complexity and technology suitability patterns
            
            **Primary vs Revisional Surgery:**
            - Compares robotic adoption between initial and revision procedures
            - May indicate surgeon comfort and patient selection criteria
            - Shows technology adoption in complex vs routine cases
            
            **Temporal Trends:**
            - Tracks how robotic adoption varies by procedure type over time
            - Identifies which procedures are driving overall robotic growth
            - Shows procedure-specific learning curves and adoption patterns
            
            **Clinical Implications:**
            - Higher robotic rates in certain procedures may indicate clinical benefits
            - Variation between hospitals suggests opportunities for best practice sharing
            - Trends can inform training and equipment investment decisions
            """)

    else:
        st.info("Advanced procedure data not available for national analysis.")
        
        st.markdown("""
        **Available from current data:**
        - Overall robotic surgery trends (shown in Approach Trends section above)
        - Basic procedure type distributions
        - General surgical approach patterns
        
        **Requires detailed procedure data:**
        - Procedure-specific robotic rates (e.g., % of gastric sleeves done robotically)
        - Primary vs revisional robotic procedures
        - Robotic approach by procedure type analysis
        """)
