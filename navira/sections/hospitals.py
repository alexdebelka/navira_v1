import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import sys
import os

# Add the parent directory to the Python path to import lib
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from lib.national_utils import (
    compute_affiliation_breakdown_2024,
    compute_affiliation_trends_2020_2024,
    BARIATRIC_PROCEDURE_NAMES
)


def render_hospitals(procedure_details: pd.DataFrame):
    """Render the Hospitals section for national page.
    
    This section contains:
    - Hospital Volume Distribution (from old Overall Trends)
    - Hospital Affiliation breakdown and trends  (from old Overall Trends)
    - Advanced Procedure Metrics (from old Hospitals)
    - Procedure-specific robotic rates
    - Primary vs revisional surgery analysis
    - Robotic adoption trends by procedure
    """
    
    # Get dataframe from session state or data loader
    try:
        df = st.session_state.get('df')
        if df is None:
            from navira.data_loader import get_all_dataframes
            all_data = get_all_dataframes()
            df = all_data.get('annual', pd.DataFrame())
    except Exception:
        df = pd.DataFrame()
    
    # ---(1) HOSPITAL VOLUME DISTRIBUTION ---
    st.header("Hospital Volume Distribution")
    
    # Load and Process Data Locally
    try:
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        vol_csv_path = os.path.join(base_dir, "new_data", "ACTIVITY", "TAB_VOL_HOP_YEAR.csv")
        df_vol = pd.read_csv(vol_csv_path)
    
        df_vol = df_vol[df_vol['annee'].isin([2021, 2022, 2023, 2024])]
    
        # Define Bins
        def assign_bin(n):
            if n < 50: return "<50"
            elif 50 <= n < 100: return "50–100"
            elif 100 <= n < 200: return "100–200"
            else: return ">200"
    
        df_vol['bin'] = df_vol['n'].apply(assign_bin)
        
        # KPIs for 2024
        df_2024 = df_vol[df_vol['annee'] == 2024]
        total_hosp_2024 = df_2024['finessGeoDP'].nunique()
        total_surg_2024 = df_2024['n'].sum()
        
        counts_2024 = df_2024['bin'].value_counts()
        hosp_less_50_2024 = counts_2024.get("<50", 0)
        hosp_more_200_2024 = counts_2024.get(">200", 0)
    
        # Baseline (2021-2023) Average
        df_baseline = df_vol[df_vol['annee'].isin([2021, 2022, 2023])]
        baseline_counts_per_year = df_baseline.groupby(['annee', 'bin'])['finessGeoDP'].count().unstack(fill_value=0)
        avg_baseline = baseline_counts_per_year.mean()
        
        hosp_less_50_base = avg_baseline.get("<50", 0)
        hosp_more_200_base = avg_baseline.get(">200", 0)
        
        delta_less_50 = hosp_less_50_2024 - hosp_less_50_base
        delta_more_200 = hosp_more_200_2024 - hosp_more_200_base
    
        # Display KPIs
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total Hospitals (2024)", f"{total_hosp_2024}")
        with col2:
            st.metric("Total Surgeries (2024)", f"{total_surg_2024:,}")
        with col3:
            st.metric("Hospitals <50/year (2024)", f"{hosp_less_50_2024}", delta=f"{delta_less_50:+.1f} vs 21-23 avg", delta_color="inverse")
        with col4:
            st.metric("Hospitals >200/year (2024)", f"{hosp_more_200_2024}", delta=f"{delta_more_200:+.1f} vs 21-23 avg", delta_color="normal")
    
        # Chart Section
        st.markdown("""
            <div class="nv-info-wrap">
              <div class="nv-h3">Volume Distribution by Hospital</div>
              <div class="nv-tooltip"><span class="nv-info-badge">i</span>
                <div class="nv-tooltiptext">
                  <b>Understanding this chart:</b><br/>
                  Distribution of hospitals based on annual surgical volume.<br/>
                  Categories: &lt;50, 50–100, 100–200, &gt;200 procedures/year.<br/>
                  Use the toggle to compare 2024 against the 2021–2023 average.
                </div>
              </div>
            </div>
        """, unsafe_allow_html=True)
        
        show_comparison = st.toggle("Show 2024 comparison (vs 2021-23 Avg)", value=True, key="vol_dist_toggle")
        bin_order = ["<50", "50–100", "100–200", ">200"]
        y_2024 = [counts_2024.get(b, 0) for b in bin_order]
        y_base = [avg_baseline.get(b, 0) for b in bin_order]
        
        fig_vol = go.Figure()
        if show_comparison:
            fig_vol.add_trace(go.Bar(x=bin_order, y=y_base, name='2021-2023 Average', marker_color='#2E86AB', hovertemplate='<b>%{x}</b><br>Avg: %{y:.1f}<extra></extra>'))
            fig_vol.add_trace(go.Bar(x=bin_order, y=y_2024, name='2024', marker_color='rgba(255, 193, 7, 0.7)', text=y_2024, textposition='auto', hovertemplate='<b>%{x}</b><br>2024: %{y}<extra></extra>'))
            barmode = 'overlay'
        else:
            fig_vol.add_trace(go.Bar(x=bin_order, y=y_2024, name='2024', marker_color='#FFC107', text=y_2024, textposition='auto', hovertemplate='<b>%{x}</b><br>2024: %{y}<extra></extra>'))
            barmode = 'group'
    
        fig_vol.update_layout(
            title="Hospital Volume Distribution",
            xaxis_title="Procedures per Year",
            yaxis_title="Number of Hospitals",
            barmode=barmode,
            hovermode='x unified',
            height=400,
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            margin=dict(l=50, r=50, t=50, b=50),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        
        st.plotly_chart(fig_vol, use_container_width=True)
        
        with st.expander("Key findings"):
            st.markdown(f"""
            **2024 Distribution:**
            - **{hosp_less_50_2024}** hospitals performed <50 procedures.
            - **{hosp_more_200_2024}** hospitals performed >200 procedures.
            
            **Compared to 2021-2023 Average:**
            - Small volume (<50): {delta_less_50:+.1f}
            - High volume (>200): {delta_more_200:+.1f}
            """)
    
    except Exception as e:
        st.error(f"Error loading volume data: {e}")
    
    
    # --- (2) HOSPITAL AFFILIATION ---
    st.header("Hospital Affiliation (2024)")
    
    if not df.empty:
        affiliation_data = compute_affiliation_breakdown_2024(df)
        affiliation_counts = affiliation_data['affiliation_counts']
        label_breakdown = affiliation_data['label_breakdown']
        
        affiliation_trends = compute_affiliation_trends_2020_2024(df)
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Public")
            total_hospitals = sum(affiliation_counts.values())
            
            public_univ_count = affiliation_counts.get('Public – Univ.', 0)
            public_univ_pct = round((public_univ_count / total_hospitals) * 100) if total_hospitals > 0 else 0
            st.metric("Public University Hospital", f"{int(round(public_univ_count)):,}")
            st.markdown(f"<span style='color: grey; font-size: 0.9em; display:block; margin-top:-8px;'>{public_univ_pct}% of total</span>", unsafe_allow_html=True)
            
            public_non_acad_count = affiliation_counts.get('Public – Non-Acad.', 0)
            public_non_acad_pct = round((public_non_acad_count / total_hospitals) * 100) if total_hospitals > 0 else 0
            st.metric("Public, No Academic Affiliation", f"{int(round(public_non_acad_count)):,}")
            st.markdown(f"<span style='color: grey; font-size: 0.9em; display:block; margin-top:-8px;'>{public_non_acad_pct}% of total</span>", unsafe_allow_html=True)
        
        with col2:
            st.subheader("Private")
            
            private_for_profit_count = affiliation_counts.get('Private – For-profit', 0)
            private_for_profit_pct = round((private_for_profit_count / total_hospitals) * 100) if total_hospitals > 0 else 0
            st.metric("Private For Profit", f"{int(round(private_for_profit_count)):,}")
            st.markdown(f"<span style='color: grey; font-size: 0.9em; display:block; margin-top:-8px;'>{private_for_profit_pct}% of total</span>", unsafe_allow_html=True)
            
            private_not_profit_count = affiliation_counts.get('Private – Not-for-profit', 0)
            private_not_profit_pct = round((private_not_profit_count / total_hospitals) * 100) if total_hospitals > 0 else 0
            st.metric("Private Not For Profit", f"{int(round(private_not_profit_count)):,}")
            st.markdown(f"<span style='color: grey; font-size: 0.9em; display:block; margin-top:-8px;'>{private_not_profit_pct}% of total</span>", unsafe_allow_html=True)
        
        # Label statistics
        try:
            univ_total = affiliation_counts.get('Public – Univ.', 0)
            univ_labeled = (
                label_breakdown.get('Public – Univ.', {}).get('SOFFCO Label', 0) +
                label_breakdown.get('Public – Univ.', {}).get('CSO Label', 0) +
                label_breakdown.get('Public – Univ.', {}).get('Both', 0)
            )
            univ_pct = round((univ_labeled / univ_total * 100)) if univ_total > 0 else 0
            
            private_total = (
                affiliation_counts.get('Private – For-profit', 0) +
                affiliation_counts.get('Private – Not-for-profit', 0)
            )
            private_labeled = (
                label_breakdown.get('Private – For-profit', {}).get('SOFFCO Label', 0) +
                label_breakdown.get('Private – For-profit', {}).get('CSO Label', 0) +
                label_breakdown.get('Private – For-profit', {}).get('Both', 0) +
                label_breakdown.get('Private – Not-for-profit', {}).get('SOFFCO Label', 0) +
                label_breakdown.get('Private – Not-for-profit', {}).get('CSO Label', 0) +
                label_breakdown.get('Private – Not-for-profit', {}).get('Both', 0)
            )
            private_pct = round((private_labeled / private_total * 100)) if private_total > 0 else 0
            
            st.markdown(f"#### **{univ_pct}%** of the university hospitals have SOFFCO, CSO or both labels and **{private_pct}%** of private hospitals have SOFFCO, CSO or both labels")
        except Exception:
            st.markdown("Label statistics unavailable")
        
        # Stacked bar chart
        st.markdown("""
            <div class="nv-info-wrap">
              <div class="nv-h3">Hospital Labels by Affiliation Type</div>
              <div class="nv-tooltip"><span class="nv-info-badge">i</span>
                <div class="nv-tooltiptext">
                  <b>Understanding this chart:</b><br/>
                  This stacked bar chart shows the distribution of hospital labels (SOFFCO and CSO) across different affiliation types.
                </div>
              </div>
            </div>
        """, unsafe_allow_html=True)
        
        with st.expander("What to look for and key findings"):
            try:
                totals = {k: 0 for k in ['SOFFCO Label', 'CSO Label', 'Both', 'None']}
                labeled_by_category = {}
                for cat in ['Public – Univ.', 'Public – Non-Acad.', 'Private – For-profit', 'Private – Not-for-profit']:
                    if cat in label_breakdown:
                        labeled_by_category[cat] = (
                            label_breakdown[cat].get('SOFFCO Label', 0) +
                            label_breakdown[cat].get('CSO Label', 0) +
                            label_breakdown[cat].get('Both', 0)
                        )
                        for lab in totals.keys():
                            totals[lab] += label_breakdown[cat].get(lab, 0)
        
                top_cat = max(labeled_by_category.items(), key=lambda x: x[1])[0] if labeled_by_category else None
                most_common_label = max(totals.items(), key=lambda x: x[1])[0] if totals else None
        
                st.markdown(f"""
                    **What to look for:**
                    - Label concentration by affiliation type
                    - Balance of SOFFCO vs CSO vs Dual labels
                    
                    **Key findings:**
                    - Most labeled affiliation type: **{top_cat if top_cat else 'n/a'}**
                    - Most common label overall: **{most_common_label if most_common_label else 'n/a'}**
                    - Totals — SOFFCO: **{totals.get('SOFFCO Label', 0):,}**, CSO: **{totals.get('CSO Label', 0):,}**, Both: **{totals.get('Both', 0):,}**, None: **{totals.get('None', 0):,}**
                """)
            except Exception:
                pass
        
        # Prepare data for stacked bar chart
        stacked_data = []
        categories = ['Public – Univ.', 'Public – Non-Acad.', 'Private – For-profit', 'Private – Not-for-profit']
        labels = ['SOFFCO Label', 'CSO Label', 'Both', 'None']
        
        for category in categories:
            if category in label_breakdown:
                for label in labels:
                    count = label_breakdown[category].get(label, 0)
                    if count > 0:
                        stacked_data.append({'Affiliation': category, 'Label': label, 'Count': count})
        
        stacked_df = pd.DataFrame(stacked_data)
        
        if not stacked_df.empty:
            fig = px.bar(
                stacked_df, x='Affiliation', y='Count', color='Label',
                title="Hospital Labels by Affiliation Type",
                color_discrete_map={'SOFFCO Label': '#7fd8be', 'CSO Label': '#ffd97d', 'Both': '#00bfff', 'None': '#f08080'}
            )
            fig.update_layout(
                xaxis_title="Affiliation Type", yaxis_title="Number of Hospitals",
                hovermode='x unified', height=400, showlegend=True,
                plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
                font=dict(size=12), margin=dict(l=50, r=50, t=80, b=50)
            )
            fig.update_traces(hovertemplate='<b>%{fullData.name}</b><br>%{x}<br>Count: %{y}<extra></extra>')
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No label data available for the selected criteria.")
        
        # Affiliation trends line plot
        st.markdown("""
            <div class="nv-info-wrap">
              <div class="nv-h3">Activity by Affiliation Trends (2021–2024)</div>
              <div class="nv-tooltip"><span class="nv-info-badge">i</span>
                <div class="nv-tooltiptext">
                  <b>Understanding this chart:</b><br/>
                  Stacked area chart showing the evolution of surgical volume by hospital affiliation type (2021-2024).
                </div>
              </div>
            </div>
        """, unsafe_allow_html=True)
        
        # Load data locally from CSV
        try:
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            status_csv_path = os.path.join(base_dir, "new_data", "ACTIVITY", "TAB_VOL_STATUS_YEAR.csv")
            df_status = pd.read_csv(status_csv_path)
        
            df_status = df_status[df_status['annee'].isin([2021, 2022, 2023, 2024])]
            status_mapping = {
                'public academic': 'Public – Univ.',
                'public': 'Public – Non-Acad.',
                'private for profit': 'Private – For-profit',
                'private not-for-profit': 'Private – Not-for-profit'
            }
            df_status['Affiliation'] = df_status['statut'].map(status_mapping)
            df_status = df_status.dropna(subset=['Affiliation'])
            trend_df = df_status.rename(columns={'annee': 'Year', 'n': 'Count'})
            key_categories = ['Public – Univ.', 'Public – Non-Acad.', 'Private – For-profit', 'Private – Not-for-profit']
            
            df_2024 = trend_df[trend_df['Year'] == 2024].set_index('Affiliation')['Count']
            df_2021 = trend_df[trend_df['Year'] == 2021].set_index('Affiliation')['Count']
            
            diffs = {}
            for cat in key_categories:
                val_24 = df_2024.get(cat, 0)
                val_21 = df_2021.get(cat, 0)
                diffs[cat] = val_24 - val_21
        
            top_inc_cat = max(diffs.items(), key=lambda x: x[1])[0] if diffs else None
            top_dec_cat = min(diffs.items(), key=lambda x: x[1])[0] if diffs else None
        
            with st.expander("What to look for and key findings"):
                st.markdown(f"""
                    **What to look for:**
                    - Volume shifts between public and private sectors
                    - Which affiliation type is driving growth or decline
                    
                    **Key findings (2024 vs 2021):**
                    - Largest increase: **{top_inc_cat if top_inc_cat and diffs[top_inc_cat] > 0 else 'None'}** ({diffs.get(top_inc_cat, 0):+d})
                    - Largest decrease: **{top_dec_cat if top_dec_cat and diffs[top_dec_cat] < 0 else 'None'}** ({diffs.get(top_dec_cat, 0):+d})
                """)
        
            if not trend_df.empty:
                fig = px.area(
                    trend_df, x='Year', y='Count', color='Affiliation',
                    title="Surgical Volume by Affiliation Over Time",
                    color_discrete_map={
                        'Public – Univ.': '#ee6055',
                        'Public – Non-Acad.': '#60d394',
                        'Private – For-profit': '#ffd97d',
                        'Private – Not-for-profit': '#7161ef'
                    },
                    category_orders={'Affiliation': key_categories}
                )
                fig.update_layout(
                    xaxis_title="Year", yaxis_title="Total Procedures",
                    hovermode='x unified', height=400, showlegend=True,
                    plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
                    font=dict(size=12), margin=dict(l=50, r=50, t=80, b=50),
                    xaxis=dict(tickmode='array', tickvals=[2021, 2022, 2023, 2024], ticktext=['2021', '2022', '2023', '2024'], tickformat='d')
                )
                fig.update_traces(line=dict(width=0), opacity=0.8)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No data available after filtering.")
        
        except Exception as e:
            st.error(f"Error loading affiliation trends: {e}")
    
    else:
        st.info("Hospital affiliation data not available.")
    
    # --- ADVANCED PROCEDURE METRICS (from old hospitals.py) ---
    st.header("Advanced Procedure Metrics")
    
    if not procedure_details.empty:
        st.markdown("""
            <div class="nv-info-wrap">
              <div class="nv-h3">Detailed Procedure Analysis</div>
              <div class="nv-tooltip"><span class="nv-info-badge">i</span>
                <div class="nv-tooltiptext">
                  <b>Understanding this analysis:</b><br/>
                  Detailed insights into surgical procedures: procedure-specific robotic rates, primary vs revisional surgery patterns, and robotic approach by procedure type (2020-2024).
                </div>
              </div>
            </div>
        """, unsafe_allow_html=True)
        
        # Procedure-specific robotic rates
        st.markdown("#### Procedure-Specific Robotic Rates (2024)")
        
        procedure_2024 = procedure_details[procedure_details['year'] == 2024]
        
        if not procedure_2024.empty:
            robotic_by_procedure = procedure_2024[procedure_2024['surgical_approach'] == 'ROB'].groupby('procedure_type')['procedure_count'].sum().reset_index()
            robotic_by_procedure = robotic_by_procedure.rename(columns={'procedure_count': 'robotic_count'})
            
            total_by_procedure = procedure_2024.groupby('procedure_type')['procedure_count'].sum().reset_index()
            total_by_procedure = total_by_procedure.rename(columns={'procedure_count': 'total_count'})
            
            procedure_robotic_rates = total_by_procedure.merge(robotic_by_procedure, on='procedure_type', how='left').fillna(0)
            procedure_robotic_rates['robotic_rate'] = (procedure_robotic_rates['robotic_count'] / procedure_robotic_rates['total_count'] * 100)
            
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
            procedure_robotic_rates = procedure_robotic_rates[procedure_robotic_rates['procedure_type'].isin(['SLE', 'BPG'])]
            
            fig = px.bar(
                procedure_robotic_rates, x='robotic_rate', y='procedure_name', orientation='h',
                title="Robotic Adoption by Procedure Type (2024)",
                labels={'robotic_rate': 'Robotic Rate (%)', 'procedure_name': 'Procedure Type'},
                text='robotic_rate'
            )
            fig.update_traces(texttemplate='%{text:.1f}%', textposition='outside', cliponaxis=False)
            fig.update_layout(height=400, plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', yaxis={'categoryorder': 'total ascending'})
            st.plotly_chart(fig, use_container_width=True)
            
            display_table = procedure_robotic_rates[['procedure_name', 'total_count', 'robotic_count', 'robotic_rate']].copy()
            display_table['robotic_rate'] = display_table['robotic_rate'].round(1)
            display_table = display_table.rename(columns={'procedure_name': 'Procedure', 'total_count': 'Total Procedures', 'robotic_count': 'Robotic Procedures', 'robotic_rate': 'Robotic Rate (%)'})
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
            trends_df = trends_df[trends_df['procedure_type'].isin(['SLE', 'BPG'])]
            
            if not trends_df.empty:
                fig = px.line(
                    trends_df, x='year', y='robotic_rate', color='procedure_name',
                    title="Robotic Adoption Trends by Major Procedure Types",
                    labels={'robotic_rate': 'Robotic Rate (%)', 'year': 'Year', 'procedure_name': 'Procedure'}
                )
                fig.update_layout(height=400, plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)')
                st.plotly_chart(fig, use_container_width=True)
        
        # Summary insights
        with st.expander("Key Insights and Analysis"):
            st.markdown("""
            **Key Findings from Advanced Procedure Analysis:**
            
            **Procedure-Specific Robotic Adoption:**
            - Shows which procedures are most/least likely to be performed robotically
            - Identifies opportunities for robotic surgery expansion
            
            **Primary vs Revisional Surgery:**
            - Compares robotic adoption between initial and revision procedures
            - May indicate surgeon comfort and patient selection criteria
            
            **Temporal Trends:**
            - Tracks robotic adoption variation by procedure type over time
            - Identifies which procedures are driving overall robotic growth
            
            **Clinical Implications:**
            - Higher robotic rates in certain procedures may indicate clinical benefits
            - Variation between hospitals suggests opportunities for best practice sharing
            """)

    else:
        st.info("Advanced procedure data not available for national analysis.")
