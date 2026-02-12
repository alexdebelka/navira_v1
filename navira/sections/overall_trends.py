import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import os
import sys
import requests
import folium
from streamlit_folium import st_folium
import branca.colormap as cm

# Add the parent directory to the Python path to import lib
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from lib.national_utils import compute_affiliation_breakdown_2024


def render_overall_trends(df: pd.DataFrame):
    """Render the Overall Trends section (formerly Summary section) for national page.
    
    This section contains summary cards showing:
    - Monthly Surgeries with Rolling Statistics (placeholder)
    - Type d'intervention (procedure types donut chart)
    - MBS Robotic rate
    - Severe Complications trend
    - Surgery Density Map
    - Hospital Labels by Affiliation
    """
    
    # Helper functions for map
    @st.cache_data(show_spinner=False)
    def _get_fr_departments_geojson():
        try:
            url = "https://france-geojson.gregoiredavid.fr/repo/departements.geojson"
            r = requests.get(url, timeout=10)
            r.raise_for_status()
            return r.json()
        except Exception:
            return None
    
    @st.cache_data(show_spinner=False)
    def load_population_data():
        """Load and process the population data by department."""
        try:
            pop_df = pd.read_csv("data/DS_ESTIMATION_POPULATION (1).csv", sep=';')
            pop_df = pop_df[pop_df['GEO_OBJECT'] == 'DEP'].copy()
            pop_df = pop_df[pop_df['TIME_PERIOD'] == 2024].copy()
            pop_df['dept_code'] = pop_df['GEO'].str.strip().str.replace('"', '')
            pop_df['population'] = pop_df['OBS_VALUE'].astype(int)
            return pop_df[['dept_code', 'population']]
        except Exception as e:
            st.error(f"Error loading population data: {e}")
            return pd.DataFrame()
    
    @st.cache_data(show_spinner=False)
    def calculate_surgery_by_department(_df):
        """Calculate total surgeries by department from hospital data."""
        try:
            df_copy = _df.copy()
            
            def standardize_dept_code(postal_code):
                postal_str = str(postal_code)
                if postal_str.startswith('97') or postal_str.startswith('98'):
                    return postal_str[:3]
                elif postal_str.startswith('201'):
                    return '2A'
                elif postal_str.startswith('202'):
                    return '2B'
                else:
                    return postal_str[:2]
            
            df_copy['dept_code'] = df_copy['code_postal'].astype(str).apply(standardize_dept_code)
            dept_surgeries = df_copy.groupby('dept_code')['total_procedures_year'].sum().reset_index()
            dept_surgeries.columns = ['dept_code', 'total_surgeries']
            
            return dept_surgeries
        except Exception as e:
            st.error(f"Error calculating surgery totals: {e}")
            return pd.DataFrame()
    
    # Row 1
    col1, col2 = st.columns(2)
    
    # Card 1: Monthly Surgeries (Placeholder)
    with col1:
        with st.container():
            st.markdown("""
            <div class="summary-card">
                <div class="card-title">Monthly Surgeries with Rolling Statistics</div>
                <div style="height: 300px; display: flex; align-items: center; justify-content: center; background: #333; border-radius: 8px; border: 1px dashed #555;">
                    <span style="color: #888;">Graph Placeholder</span>
                </div>
                <div class="ici-link">Bien plus de détails sur <b>les tendances</b> -> <span style="color: #00bfff; cursor: pointer;">ici</span></div>
            </div>
            """, unsafe_allow_html=True)
    
    # Card 2: Intervention Types
    with col2:
        with st.container():
            # Load the CSV data
            try:
                base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                csv_path = os.path.join(base_dir, "new_data", "ACTIVITY", "TAB_TCN_NATL_YEAR.csv")
                df_activ = pd.read_csv(csv_path)
    
                df_activ = df_activ[df_activ['annee'].isin([2021, 2022, 2023, 2024])]
                total_procs = df_activ['n'].sum()
                totals_by_proc = df_activ.groupby('baria_t')['n'].sum()
    
                sleeve_n = totals_by_proc.get('SLE', 0)
                bypass_n = totals_by_proc.get('BPG', 0)
                sleeve_pct = (sleeve_n / total_procs * 100) if total_procs > 0 else 0
                bypass_pct = (bypass_n / total_procs * 100) if total_procs > 0 else 0
                others_n = total_procs - sleeve_n - bypass_n
                other_pct = (others_n / total_procs * 100) if total_procs > 0 else 0
    
                # Load Trend Data for Prediction
                trend_csv_path = os.path.join(base_dir, "new_data", "ACTIVITY", "TAB_TREND_NATL.csv")
                diff_pct_val = 0
                if os.path.exists(trend_csv_path):
                    df_trend = pd.read_csv(trend_csv_path)
                    diff_pct_val = df_trend['diff_pct'].iloc[0]
                    prediction_text = f"{diff_pct_val:+.1f}%"
                else:
                    prediction_text = "N/A"
    
                # Create Combined Figure
                fig_combined = go.Figure()
                labels = ['Gastric Bypass', 'Sleeve Gastrectomy', 'Other Procedures']
                values = [bypass_pct, sleeve_pct, other_pct]
                colors = ['#1f77b4', '#ff7f0e', '#2ca02c'] 
                
                fig_combined.add_trace(go.Pie(
                    labels=labels, 
                    values=values, 
                    hole=.6,
                    marker_colors=colors,
                    textinfo='percent+label',
                    showlegend=False,
                    domain={'x': [0.5, 1], 'y': [0, 1]}
                ))
    
                # Stats Boxes
                pred_color = "#ff4b4b" if diff_pct_val < 0 else "#2ca02c"
                fig_combined.add_annotation(x=0.06, y=0.88, xref="paper", yref="paper", text="Total procedures", showarrow=False, font=dict(color="#a0a0a0", size=12), xanchor="left")
                fig_combined.add_annotation(x=0.06, y=0.79, xref="paper", yref="paper", text=f"{int(total_procs):,}", showarrow=False, font=dict(size=20), xanchor="left")
                fig_combined.add_annotation(x=0.06, y=0.53, xref="paper", yref="paper", text="Prediction", showarrow=False, font=dict(color="#a0a0a0", size=12), xanchor="left")
                fig_combined.add_annotation(x=0.06, y=0.44, xref="paper", yref="paper", text=prediction_text, showarrow=False, font=dict(color=pred_color, size=20), xanchor="left")
                fig_combined.add_annotation(x=0.06, y=0.18, xref="paper", yref="paper", text="Sleeve/Bypass", showarrow=False, font=dict(color="#a0a0a0", size=12), xanchor="left")
                fig_combined.add_annotation(x=0.06, y=0.09, xref="paper", yref="paper", text=f"{sleeve_pct:.0f}%/{bypass_pct:.0f}%", showarrow=False, font=dict(size=16), xanchor="left")
    
                box_style = dict(type="rect", xref="paper", yref="paper", fillcolor="rgba(255, 255, 255, 0.05)", line=dict(color="rgba(255, 255, 255, 0.1)", width=1), layer="below")
                fig_combined.update_layout(
                    shapes=[
                        dict(x0=0, x1=0.45, y0=0.72, y1=0.98, **box_style),
                        dict(x0=0, x1=0.45, y0=0.37, y1=0.63, **box_style),
                        dict(x0=0, x1=0.45, y0=0.02, y1=0.28, **box_style),
                    ],
                    margin=dict(t=10, b=10, l=10, r=10),
                    height=250,
                    paper_bgcolor='rgba(0,0,0,0)',
                    plot_bgcolor='rgba(0,0,0,0)'
                )
                
            except Exception as e:
                st.error(f"Error loading activity/trend data: {e}")
                fig_combined = go.Figure()
    
            st.markdown("""
            <div class="summary-card">
                <div class="card-title" style="margin-bottom: 10px; line-height: 1.3;">Type d'intervention de chirurgie bariatrique (2021-2024)</div>
            </div>
            """, unsafe_allow_html=True)
            st.plotly_chart(fig_combined, use_container_width=True, config={'displayModeBar': False})
            st.markdown("""
            <div class="summary-card" style="margin-top: -20px;">
                <div class="ici-link">Analyse plus détaillée du type d'intervention bariatrique -> <span style="color: #00bfff; cursor: pointer;">ici</span></div>
            </div>
            """, unsafe_allow_html=True)
    
    # Row 2
    col3, col4 = st.columns(2)
    
    # Card 3: MBS Robotic Rate
    with col3:
        with st.container():
            try:
                base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                rob_csv_path = os.path.join(base_dir, "new_data", "ACTIVITY", "TAB_APP_NATL_YEAR.csv")
                df_rob = pd.read_csv(rob_csv_path)
                df_rob = df_rob[(df_rob['vda'] == 'ROB') & (df_rob['annee'].isin([2021, 2022, 2023, 2024]))]
                df_rob = df_rob.sort_values('annee')
                years = df_rob['annee'].tolist()
                rates = df_rob['pct'].tolist()
            except Exception as e:
                st.error(f"Error loading robotic data: {e}")
                years = []
                rates = []
    
            fig_rob = go.Figure()
            if years:
                fig_rob.add_trace(go.Bar(x=years, y=rates, text=[f"{r}%" for r in rates], textposition='outside', marker_color='#003366', name='Robotic Rate'))
            
            fig_rob.update_layout(
                margin=dict(t=20, b=0, l=0, r=0), height=200, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                xaxis=dict(showgrid=False, type='category', tickfont=dict(color='#888')), 
                yaxis=dict(showgrid=False, visible=False, range=[0, max(rates)*1.2 if rates else 10]),
                showlegend=False
            )
    
            st.markdown("""
            <div class="summary-card">
                <div class="card-title" style="text-align:left; font-size:1rem;">MBS Robotic rate</div>
            """, unsafe_allow_html=True)
            st.plotly_chart(fig_rob, use_container_width=True, config={'displayModeBar': False})
            st.markdown("""
                <div class="ici-link">Bien plus de détails sur <b>l'activité robotique</b> -> <span style="color: #00bfff; cursor: pointer;">ici</span></div>
            </div>
            """, unsafe_allow_html=True)
    
    # Card 4: Severe Complications
    with col4:
        with st.container():
            try:
                base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                comp_csv_path = os.path.join(base_dir, "new_data", "COMPLICATIONS", "TAB_COMPL_GRADE_NATL_YEAR.csv")
                df_comp = pd.read_csv(comp_csv_path)
                df_comp = df_comp[(df_comp['annee'].isin([2021, 2022, 2023, 2024])) & (df_comp['clav_cat_90'].isin([3, 4, 5]))]
                yearly_severe = df_comp.groupby('annee')['COMPL_pct'].sum().reset_index().sort_values('annee')
                comp_years = yearly_severe['annee'].tolist()
                comp_rates = yearly_severe['COMPL_pct'].tolist()
            except Exception as e:
                st.error(f"Error loading complications data: {e}")
                comp_years = []
                comp_rates = []
            
            fig_comp = go.Figure()
            if comp_years:
                 fig_comp.add_trace(go.Scatter(x=comp_years, y=comp_rates, mode='lines+markers+text', text=[f"{r:.1f}%" for r in comp_rates], textposition="top center", line=dict(color='#FF8C00', width=3), marker=dict(size=8), showlegend=False))
            
            fig_comp.update_layout(
                margin=dict(t=20, b=0, l=0, r=0), height=200, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                xaxis=dict(showgrid=False, type='category', tickfont=dict(color='#888')), 
                yaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.1)', range=[0, max(comp_rates)*1.3 if comp_rates else 5], tickfont=dict(color='#888'))
            )
    
            st.markdown("""
            <div class="summary-card">
                <div class="card-title">Taux de complications sévères à 90 jours après chirurgie bariatrique (estimation)</div>
            """, unsafe_allow_html=True)
            st.plotly_chart(fig_comp, use_container_width=True, config={'displayModeBar': False})
            st.markdown("""
                <div class="ici-link">Bien plus de détails sur <b>les complications</b> -> <span style="color: #00bfff; cursor: pointer;">ici</span></div>
            </div>
            """, unsafe_allow_html=True)
    
    # Row 3
    col5, col6 = st.columns(2)
    
    # Card 5: Surgery Density Map
    with col5:
        with st.container():
            st.header("Surgery Density by Department")
            st.markdown("*Ratio of total bariatric surgeries to department population (surgeries per 100,000 inhabitants)*")
            
            try:
                population_data = load_population_data()
                surgery_data = calculate_surgery_by_department(df)
                
                if not population_data.empty and not surgery_data.empty:
                    ratio_data = pd.merge(surgery_data, population_data, on='dept_code', how='inner')
                    ratio_data['surgery_ratio'] = (ratio_data['total_surgeries'] / ratio_data['population']) * 100000
                    ratio_data['surgery_ratio'] = ratio_data['surgery_ratio'].round(1)
                    
                    gj = _get_fr_departments_geojson()
                    if gj and not ratio_data.empty:
                        m = folium.Map(location=[46.5, 2.5], zoom_start=5, tiles="CartoDB positron")
                        vmin = float(ratio_data['surgery_ratio'].min())
                        vmax = float(ratio_data['surgery_ratio'].max())
                        colormap = cm.linear.YlOrRd_09.scale(vmin, vmax)
                        colormap.caption = 'Surgeries per 100K inhabitants'
                        colormap.add_to(m)
                        
                        val_map = dict(zip(ratio_data['dept_code'].astype(str), ratio_data['surgery_ratio'].astype(float)))
                        
                        def _style_fn(feat):
                            code = str(feat.get('properties', {}).get('code', ''))
                            v = val_map.get(code, 0.0)
                            opacity = 0.25 if v == 0 else 0.7
                            return {"fillColor": colormap(v), "color": "#555555", "weight": 0.8, "fillOpacity": opacity}
                        
                        folium.GeoJson(gj, style_function=_style_fn, tooltip=folium.Tooltip("Click for details"), popup=None).add_to(m)
                        st_folium(m, width="100%", height=400, key="surgery_population_ratio_choropleth_summary")
                    else:
                        st.error("Could not load department GeoJSON for surgery ratio map.")
                else:
                     st.info("Data for map not available.")
                    
            except Exception as e:
                st.error(f"Error creating surgery-to-population ratio map: {e}")
    
            st.markdown("""
                <div class="ici-link" style="text-align:left;">Distribution de <b>l'offre de soins</b> sur le territoire -> <span style="color: #00bfff; cursor: pointer;">ici</span></div>
            """, unsafe_allow_html=True)
    
    # Card 6: Hospital Labels by Affiliation Type
    with col6:
        with st.container():
            try:
                # Load hospital data from the new CSV file
                base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                hosp_csv_path = os.path.join(base_dir, "new_data", "01_hospitals_redux.csv")
                df_hosp = pd.read_csv(hosp_csv_path)
                
                # Filter for 2025 data
                df_hosp_2025 = df_hosp[df_hosp['annee'] == 2025].copy()
                
                # Map status to affiliation names
                status_mapping = {
                    'public academic': 'Public – Univ.',
                    'public': 'Public – Non-Acad.',
                    'private for profit': 'Private – For-profit',
                    'private not-for-profit': 'Private – Not-for-profit'
                }
                
                df_hosp_2025['Affiliation'] = df_hosp_2025['statut'].map(status_mapping)
                df_hosp_2025 = df_hosp_2025.dropna(subset=['Affiliation'])
                
                # Calculate label categories based on cso and LAB_SOFFCO columns
                def get_label_category(row):
                    has_cso = row['cso'] == 1
                    has_soffco = row['LAB_SOFFCO'] == 1
                    
                    if has_cso and has_soffco:
                        return 'Both'
                    elif has_soffco:
                        return 'SOFFCO Label'
                    elif has_cso:
                        return 'CSO Label'
                    else:
                        return 'None'
                
                df_hosp_2025['Label_Category'] = df_hosp_2025.apply(get_label_category, axis=1)
                
                # Group by affiliation and label category
                label_counts = df_hosp_2025.groupby(['Affiliation', 'Label_Category']).size().unstack(fill_value=0)
                
                # Define categories in order
                categories = ['Public – Univ.', 'Public – Non-Acad.', 'Private – Not-for-profit', 'Private – For-profit']
                
                # Prepare data for each label type
                soffco = [label_counts.loc[cat, 'SOFFCO Label'] if cat in label_counts.index and 'SOFFCO Label' in label_counts.columns else 0 for cat in categories]
                cso = [label_counts.loc[cat, 'CSO Label'] if cat in label_counts.index and 'CSO Label' in label_counts.columns else 0 for cat in categories]
                both = [label_counts.loc[cat, 'Both'] if cat in label_counts.index and 'Both' in label_counts.columns else 0 for cat in categories]
                none = [label_counts.loc[cat, 'None'] if cat in label_counts.index and 'None' in label_counts.columns else 0 for cat in categories]
                
                fig_aff = go.Figure()
                fig_aff.add_trace(go.Bar(name='SOFFCO Label', x=categories, y=soffco, marker_color='#76D7C4'))
                fig_aff.add_trace(go.Bar(name='CSO Label', x=categories, y=cso, marker_color='#F7DC6F'))
                fig_aff.add_trace(go.Bar(name='Both', x=categories, y=both, marker_color='#00BFFF'))
                fig_aff.add_trace(go.Bar(name='None', x=categories, y=none, marker_color='#F1948A'))
    
                fig_aff.update_layout(
                    barmode='stack', margin=dict(t=20, b=0, l=0, r=0), height=300,
                    paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                    legend=dict(orientation="v", yanchor="top", y=1, xanchor="right", x=1.2, font=dict(size=9)),
                    xaxis=dict(showgrid=False, tickfont=dict(size=10)),
                    yaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.1)', title="Number of Hospitals")
                )
    
            except Exception as e:
                st.error(f"Error loading hospital labels data: {e}")
                fig_aff = go.Figure()
    
            st.markdown("""
            <div class="summary-card">
                <div class="card-title">Hospital Labels by Affiliation Type (2025)</div>
            """, unsafe_allow_html=True)
            st.plotly_chart(fig_aff, use_container_width=True, config={'displayModeBar': False})
            st.markdown("""
                <div class="ici-link">Bien plus de détails sur <b>l'activité des hôpitaux</b> -> <span style="color: #00bfff; cursor: pointer;">ici</span></div>
            </div>
            """, unsafe_allow_html=True)
