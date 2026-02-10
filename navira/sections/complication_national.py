import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import numpy as np

import os
from pathlib import Path


def render_complication_national(data=None):
    """Render the Complications section for national page using CSV data from new_data/COMPLICATIONS.
    
    This is a national-only version showing aggregated data without hospital-specific filtering.
    
    Args:
        data: Optional data parameter (not used, loads data directly from CSV files)
    """
    st.subheader("Complications Overview (National)")
    
    def _resolve_complications_dir() -> str | None:
        """Resolve path to new_data/COMPLICATIONS directory."""
        candidates: list[str] = []
        try:
            candidates.append(str(Path.cwd() / "new_data" / "COMPLICATIONS"))
        except Exception:
            pass
        try:
            here = Path(__file__).resolve()
            candidates.append(str((here.parent / ".." / "new_data" / "COMPLICATIONS").resolve()))
            candidates.append(str((here.parent.parent / "new_data" / "COMPLICATIONS").resolve()))
        except Exception:
            pass
        candidates.append("/Users/alexdebelka/Downloads/navira/new_data/COMPLICATIONS")
        for c in candidates:
            if Path(c).is_dir():
                return c
        return None

    @st.cache_data(show_spinner=False)
    def _read_csv_complications(filename: str) -> pd.DataFrame:
        """Read CSV from COMPLICATIONS folder."""
        base = _resolve_complications_dir()
        if not base:
            return pd.DataFrame()
        p = Path(base) / filename
        try:
            df = pd.read_csv(p)
            # Normalization
            if "annee" in df.columns:
                df["annee"] = pd.to_numeric(df["annee"], errors="coerce").astype("Int64")
            if "year" in df.columns:
                df["year"] = pd.to_numeric(df["year"], errors="coerce").astype("Int64")
            if "n" in df.columns:
                df["n"] = pd.to_numeric(df["n"], errors="coerce")
            if "finessGeoDP" in df.columns:
                df["finessGeoDP"] = df["finessGeoDP"].astype(str).str.strip()
            if "lib_reg" in df.columns:
                df["lib_reg"] = df["lib_reg"].astype(str).str.strip()
            if "statut" in df.columns:
                df["statut"] = df["statut"].astype(str).str.strip()
            # Handle complications columns
            if "COMPL_pct" in df.columns:
                df["COMPL_pct"] = pd.to_numeric(df["COMPL_pct"], errors="coerce")
            if "COMPL_nb" in df.columns:
                df["COMPL_nb"] = pd.to_numeric(df["COMPL_nb"], errors="coerce")
            if "clav_cat_90" in df.columns:
                df["clav_cat_90"] = pd.to_numeric(df["clav_cat_90"], errors="coerce")
            # Handle never events columns
            if "NEVER_nb" in df.columns:
                df["NEVER_nb"] = pd.to_numeric(df["NEVER_nb"], errors="coerce")
            if "NEVER_pct" in df.columns:
                df["NEVER_pct"] = pd.to_numeric(df["NEVER_pct"], errors="coerce")
            # Handle length of stay columns
            if "LOS_nb" in df.columns:
                df["LOS_nb"] = pd.to_numeric(df["LOS_nb"], errors="coerce")
            if "LOS_pct" in df.columns:
                df["LOS_pct"] = pd.to_numeric(df["LOS_pct"], errors="coerce")
            if "LOS_7_nb" in df.columns:
                df["LOS_7_nb"] = pd.to_numeric(df["LOS_7_nb"], errors="coerce")
            if "LOS_7_pct" in df.columns:
                df["LOS_7_pct"] = pd.to_numeric(df["LOS_7_pct"], errors="coerce")
            if "TOT" in df.columns:
                df["TOT"] = pd.to_numeric(df["TOT"], errors="coerce")
            return df
        except Exception:
            return pd.DataFrame()
    
    # Check complications directory
    complications_data_dir = _resolve_complications_dir()
    if complications_data_dir is None:
        st.error("❌ Complications data directory not found. Please ensure new_data/COMPLICATIONS exists.")
        st.info(f"Looking for directory at: new_data/COMPLICATIONS")
        st.stop()

    # Color scheme for national data (matching overall_trends.py)
    COMPL_COLORS = {
        "national": "#FF8C00",  # Orange (matches overall_trends.py complication color)
    }

    # Helper function to get latest complete year (exclude current partial year)
    def _get_latest_complete_year(df: pd.DataFrame) -> int | None:
        """Get the latest complete year, excluding current partial year."""
        if df.empty or "annee" not in df.columns:
            return None
        df_copy = df.copy()
        df_copy["annee"] = pd.to_numeric(df_copy["annee"], errors="coerce")
        years = df_copy["annee"].dropna().unique()
        if len(years) == 0:
            return None
        # Sort years descending
        years_sorted = sorted(years, reverse=True)
        # If we have multiple years, use second-to-last (skip partial current year)
        if len(years_sorted) >= 2:
            return int(years_sorted[1])
        # If only one year, use it
        return int(years_sorted[0])
    
    # --- Overall complication rate (90 days) — National line chart ---
    st.markdown("### Overall complication rate (90 days)")
    
    # What to look for guidance
    with st.expander("ℹ️ What to look for"):
        st.markdown("""
        **Understanding this metric:**
        - This shows the percentage of patients who experienced any complication within 90 days after bariatric surgery
        - Captures all complications from minor (Grade 1-2) to severe (Grade 3-5)
        
        **Key findings:**
        - National trend shows complications are **stable around 2.4-2.5%** across recent years
        - This indicates consistent surgical quality and patient safety at the national level
        
        **What to watch for:**
        - 📉 **Decreasing trend**: Indicates improving surgical techniques and patient outcomes
        - 📈 **Increasing trend**: May signal need for quality improvement initiatives
        - **Stability**: Current stability suggests well-established protocols
        """)
    
    # Load annual data for trend visualization
    compl_natl = _read_csv_complications("TAB_COMPL_NATL_YEAR.csv")

    # Prepare data for line chart
    if not compl_natl.empty and "annee" in compl_natl.columns and "COMPL_pct" in compl_natl.columns:
        # Filter to complete years (2021-2024)
        df_trend = compl_natl.copy()
        df_trend["annee"] = pd.to_numeric(df_trend["annee"], errors="coerce")
        df_trend["COMPL_pct"] = pd.to_numeric(df_trend["COMPL_pct"], errors="coerce")
        df_trend = df_trend.dropna(subset=["annee", "COMPL_pct"])
        df_trend = df_trend[df_trend["annee"].isin([2021, 2022, 2023, 2024])]
        df_trend = df_trend.sort_values("annee")
        
        if not df_trend.empty:
            years = df_trend["annee"].tolist()
            comp_rates = df_trend["COMPL_pct"].tolist()
            
            fig_comp = go.Figure()
            fig_comp.add_trace(go.Scatter(
                x=years, 
                y=comp_rates, 
                mode='lines+markers+text',
                text=[f"{r:.1f}%" for r in comp_rates],
                textposition="top center",
                line=dict(color='#FF8C00', width=3),
                marker=dict(size=10, color='#FF8C00'),
                showlegend=False
            ))
            
            fig_comp.update_layout(
                margin=dict(t=30, b=20, l=20, r=20),
                height=280,
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                xaxis=dict(
                    showgrid=False,
                    type='category',
                    tickfont=dict(color='#888'),
                    title="Year"
                ),
                yaxis=dict(
                    showgrid=True,
                    gridcolor='rgba(255,255,255,0.1)',
                    range=[0, max(comp_rates) * 1.3 if comp_rates else 5],
                    tickfont=dict(color='#888'),
                    title="Complication Rate (%)"
                )
            )
            
            st.plotly_chart(fig_comp, use_container_width=True, key="compl_nat_trend")
        else:
            st.info("No data available for complication rate trend.")
    else:
        st.info("No data available for complication rate trend.")


    # --- Complication rate by Clavien-Dindo grade + Never events ---
    st.markdown("---")
    st.markdown("#### Complication rate by Clavien-Dindo grade (90 days)")
    
    # What to look for guidance
    with st.expander("ℹ️ What to look for"):
        st.markdown("""
        **Understanding the Clavien-Dindo Classification:**
        - **Grade 3**: Requiring surgical, endoscopic or radiological intervention
        - **Grade 4**: Life-threatening complications requiring ICU management
        - **Grade 5**: Death of patient (also shown separately as "Never Events")
        
        **Key findings:**
        - Most severe complications are **Grade 3** (requiring intervention but not life-threatening)
        - Grade 4 and 5 events are rare, indicating good patient safety
        - **Never Events (deaths)** are tracked separately and should remain at very low levels
        
        **What to watch for:**
        - Grade 3 complications around **1-2%** is typical for bariatric surgery
        - Grade 4 should be **<0.5%** - higher rates may indicate patient selection or care issues
        - Grade 5 (death) should be **<0.1%** - any increase requires immediate attention
        """)

    # Load Clavien-Dindo grade data
    grade_natl = _read_csv_complications("TAB_COMPL_GRADE_NATL_YEAR.csv")

    # Load Never events data
    never_natl = _read_csv_complications("TAB_NEVER_NATL.csv")

    # Color scheme for bar plot (matching overall_trends.py)
    GRADE_COLORS = {
        'National': '#FF8C00',     # Orange (matches overall_trends.py)
    }

    # Helper function to get grade rates for a given dataset
    def _get_grade_rates(df: pd.DataFrame, filters: dict | None = None) -> dict[int, float]:
        """Get complication rates for grades 3, 4, 5 from latest complete year."""
        if df is None or df.empty or "clav_cat_90" not in df.columns or "COMPL_pct" not in df.columns:
            return {3: 0.0, 4: 0.0, 5: 0.0}
        
        d = df.copy()
        
        # Apply filters
        if filters:
            for k, v in filters.items():
                if k in d.columns and v is not None and str(v):
                    d = d[d[k].astype(str).str.strip() == str(v)]
        
        if d.empty:
            return {3: 0.0, 4: 0.0, 5: 0.0}
        
        # Get latest complete year (use helper function from above)
        if "annee" in d.columns:
            latest_year = _get_latest_complete_year(d)
            if latest_year:
                d = d[pd.to_numeric(d["annee"], errors="coerce") == latest_year]
        
        if d.empty:
            return {3: 0.0, 4: 0.0, 5: 0.0}
        
        # Normalize columns
        d["clav_cat_90"] = pd.to_numeric(d["clav_cat_90"], errors="coerce")
        d["COMPL_pct"] = pd.to_numeric(d["COMPL_pct"], errors="coerce").fillna(0)
        
        # Use pre-calculated percentages directly from CSV
        rates = {}
        for grade in [3, 4, 5]:
            grade_rows = d[d["clav_cat_90"] == grade]
            if not grade_rows.empty:
                # Use pre-calculated COMPL_pct from the CSV file
                rates[grade] = float(grade_rows.iloc[0]["COMPL_pct"])
            else:
                rates[grade] = 0.0
        
        return rates

    # Get never events data
    def _get_never_events(df: pd.DataFrame, filters: dict | None = None) -> tuple[int, int, float]:
        """Returns (NEVER_nb, TOT, NEVER_pct) using pre-calculated percentage."""
        if df is None or df.empty or "NEVER_nb" not in df.columns or "TOT" not in df.columns:
            return (0, 0, 0.0)
        
        d = df.copy()
        
        # Apply filters
        if filters:
            for k, v in filters.items():
                if k in d.columns and v is not None and str(v):
                    d = d[d[k].astype(str).str.strip() == str(v)]
        
        if d.empty:
            return (0, 0, 0.0)
        
        # Normalize and sum
        never_nb = int(pd.to_numeric(d["NEVER_nb"], errors="coerce").fillna(0).sum())
        tot = int(pd.to_numeric(d["TOT"], errors="coerce").fillna(0).sum())
        
        # Use pre-calculated NEVER_pct if available, otherwise calculate
        if "NEVER_pct" in d.columns:
            never_pct = float(pd.to_numeric(d["NEVER_pct"], errors="coerce").fillna(0).iloc[0])
        else:
            never_pct = (never_nb / tot * 100.0) if tot > 0 else 0.0
        
        return (never_nb, tot, never_pct)

    # Compute rates for national
    rates_n = _get_grade_rates(grade_natl, None)

    # Compute never events
    never_n = _get_never_events(never_natl, None)

    # Build bar chart data (national only)
    rows = []
    for grade in [3, 4, 5]:
        rows.append({'Grade': f'Grade {grade}', 'Group': 'National', 'Rate': rates_n.get(grade, 0.0)})
    
    df_bar = pd.DataFrame(rows)
    
    # Layout: bar chart on left, never events card on right
    left, right = st.columns([2, 1])
    
    with left:
        fig_grade = px.bar(
            df_bar, x='Grade', y='Rate', color='Group', barmode='group',
            color_discrete_map=GRADE_COLORS
        )
        fig_grade.update_layout(
            height=360,
            yaxis_title='Rate (%)',
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            showlegend=False
        )
        fig_grade.update_yaxes(range=[0, max(8, df_bar['Rate'].max() * 1.3)])
        fig_grade.update_traces(hovertemplate='%{x}: %{y:.1f}%<extra></extra>')
        st.plotly_chart(fig_grade, use_container_width=True, key="compl_nat_grade_chart")
    
    with right:
        # Never events card - use pre-calculated percentages
        def _fmt_never(n, d, pct):
            """Format never events using pre-calculated percentage."""
            return f"{n:,}/{d:,}", f"{pct:.1f}%"
        
        never_label, never_frac, never_pct_str = "National", *_fmt_never(*never_n)
        
        # Inline CSS for styled card
        css = """
        <style>
          .nv-ne-card { border:1px solid rgba(255,255,255,.2); border-radius:10px; padding:12px 14px; background:rgba(255,255,255,.04); }
          .nv-ne-title { font-weight:800; font-size:1.05rem; text-align:center; margin:0 0 8px 0; }
          .nv-ne-row { display:flex; align-items:center; justify-content:space-between; gap:10px; padding:8px 10px; border-radius:8px; margin:6px 0; background:rgba(0,0,0,.15); }
          .nv-ne-left { display:flex; align-items:center; gap:10px; font-weight:600; }
          .nv-ne-dot { width:10px; height:10px; border-radius:50%; display:inline-block; }
          .nv-ne-num { font-weight:800; font-size:1.05rem; }
          .nv-ne-pct { font-weight:700; opacity:.85; margin-left:8px; }
        </style>
        """
        html = [css, "<div class='nv-ne-card'>",
                "<div class='nv-ne-title'>Never events (death)</div>"]
        html.append(
            f"<div class='nv-ne-row'><div class='nv-ne-left'><span class='nv-ne-dot' style='background:{GRADE_COLORS['National']}'></span>{never_label}</div>"
            f"<div><span class='nv-ne-num'>{never_frac}</span><span class='nv-ne-pct'> ({never_pct_str})</span></div></div>"
        )
        html.append("</div>")
        st.markdown("".join(html), unsafe_allow_html=True)

    # --- Length of stay — index admission ---
    st.markdown("---")
    st.markdown("#### Length of stay – index admission")
    
    # What to look for guidance
    with st.expander("ℹ️ What to look for"):
        st.markdown("""
        **Understanding length of stay (LOS):**
        - Tracks how long patients remain hospitalized after their initial bariatric surgery
        - Measured within 90-day period following surgery
        - Categorized as: **0 days**, **1-3 days**, **4-6 days**, and **≥7 days**
        
        **Key findings:**
        - Most patients (75-80%) have short stays of **1-3 days**
        - Trend shows increasing short stays, indicating faster recovery protocols
        - Patients with **>7 days** stay around **2.7-3.0%** - these often had complications
        
        **What to watch for:**
        - 📈 **Increasing 1-3 day stays**: Positive trend indicating enhanced recovery protocols
        - 📉 **Decreasing ≥7 day stays**: Good sign of fewer complications and better outcomes
        - **Sudden increases in long stays**: May indicate emerging complications or patient selection changes
        
        **Benchmark:** Most modern bariatric programs aim for >75% of patients discharged within 1-3 days
        """)
    
    # Load LOS data (national only)
    los_natl = _read_csv_complications("TAB_LOS_NATL.csv")
    
    # Color schemes matching national theme (using blue palette like techniques.py)
    # Using blue shades for better visual hierarchy
    LOS_COLORS_NATIONAL = {
        '[-1,0]': '#1f77b4',      # Blue (base - matches overall_trends color palette)
        '(0,3]': '#4C84C8',       # Medium blue (matches techniques.py)
        '(3,6]': '#76A5D8',       # Light blue
        '(6,225]': '#A0C4E8'      # Lightest blue
    }
    
    # Bucket labels for legend
    LOS_BUCKET_LABELS = {
        '[-1,0]': '0',
        '(0,3]': '1-3',
        '(3,6]': '4-6',
        '(6,225]': '≥7'
    }
    
    def _los_bars(df: pd.DataFrame, title: str, filters: dict | None = None, height: int = 260, color_map: dict | None = None, chart_key: str = ""):
        """Create stacked bar chart for length of stay distribution by year."""
        if df is None or df.empty:
            st.info(f"No data for {title}.")
            return
        
        d = df.copy()
        
        # Apply filters
        if filters:
            for k, v in filters.items():
                if k in d.columns and v is not None and str(v):
                    d = d[d[k].astype(str).str.strip() == str(v)]
        
        if d.empty:
            st.info(f"No data for {title}.")
            return
        
        if 'annee' not in d.columns or 'duree_cat' not in d.columns or 'LOS_pct' not in d.columns:
            st.info(f"Missing columns for {title}.")
            return
        
        # Normalize columns
        d['annee'] = pd.to_numeric(d['annee'], errors='coerce')
        d['LOS_pct'] = pd.to_numeric(d['LOS_pct'], errors='coerce').fillna(0)
        d = d.dropna(subset=['annee'])
        
        if d.empty:
            st.info(f"No data for {title}.")
            return
        
        # Map bucket labels
        d['bucket'] = d['duree_cat'].astype(str).map(LOS_BUCKET_LABELS).fillna(d['duree_cat'])
        d['annee'] = d['annee'].astype(int).astype(str)
        
        colors = color_map if color_map else LOS_COLORS_NATIONAL
        
        fig = px.bar(
            d.sort_values('annee'),
            x='annee', y='LOS_pct', color='duree_cat', barmode='stack',
            color_discrete_map=colors,
            category_orders={'duree_cat': ['[-1,0]', '(0,3]', '(3,6]', '(6,225]']}
        )
        fig.update_layout(
            height=height,
            xaxis_title='Year',
            yaxis_title='% of stays',
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            title=title,
            legend_title_text='LOS bucket'
        )
        fig.update_yaxes(range=[0, 100])
        fig.update_traces(hovertemplate='%{x}<br>%{y:.0f}%<extra></extra>')
        
        # Update legend labels to use bucket names
        for trace in fig.data:
            if trace.name in LOS_BUCKET_LABELS:
                trace.name = LOS_BUCKET_LABELS[trace.name]
        
        st.plotly_chart(fig, use_container_width=True, key=chart_key if chart_key else None)
    
    # Load >7 days LOS data for bubble (national only)
    los7_natl_bubble = _read_csv_complications("TAB_LOS7_NATL.csv")
    
    # Layout: LOS distribution chart on left, bubble on right
    left_charts, right_bubbles = st.columns([2.5, 1])
    
    with left_charts:
        st.markdown("##### Length of stay distribution by year (share %)")
        
        # National chart
        _los_bars(los_natl, 'National', None, height=320, color_map=LOS_COLORS_NATIONAL, chart_key="compl_nat_los_natl")
    
    with right_bubbles:
        st.markdown("##### Patients >7 days of 90d-LOS")
        
        # Extract >7 days trend from the main LOS data by filtering for (6,225] category
        if not los_natl.empty and "annee" in los_natl.columns and "duree_cat" in los_natl.columns and "LOS_pct" in los_natl.columns:
            # Filter for >7 days category: (6,225]
            df_los7_trend = los_natl[los_natl["duree_cat"] == "(6,225]"].copy()
            df_los7_trend["annee"] = pd.to_numeric(df_los7_trend["annee"], errors="coerce")
            df_los7_trend["LOS_pct"] = pd.to_numeric(df_los7_trend["LOS_pct"], errors="coerce")
            df_los7_trend = df_los7_trend.dropna(subset=["annee", "LOS_pct"])
            df_los7_trend = df_los7_trend[df_los7_trend["annee"].isin([2021, 2022, 2023, 2024])]
            df_los7_trend = df_los7_trend.sort_values("annee")
            
            if not df_los7_trend.empty:
                years = df_los7_trend["annee"].tolist()
                los7_rates = df_los7_trend["LOS_pct"].tolist()
                
                fig_los7 = go.Figure()
                fig_los7.add_trace(go.Scatter(
                    x=years,
                    y=los7_rates,
                    mode='lines+markers+text',
                    text=[f"{r:.1f}%" for r in los7_rates],
                    textposition="top center",
                    line=dict(color='#FF8C00', width=3),
                    marker=dict(size=10, color='#FF8C00'),
                    showlegend=False
                ))
                
                fig_los7.update_layout(
                    margin=dict(t=30, b=20, l=30, r=10),
                    height=280,
                    paper_bgcolor='rgba(0,0,0,0)',
                    plot_bgcolor='rgba(0,0,0,0)',
                    xaxis=dict(
                        showgrid=False,
                        type='category',
                        tickfont=dict(color='#888', size=10),
                        title="Year"
                    ),
                    yaxis=dict(
                        showgrid=True,
                        gridcolor='rgba(255,255,255,0.1)',
                        range=[0, max(los7_rates) * 1.3 if los7_rates else 5],
                        tickfont=dict(color='#888', size=10),
                        title=">7d LOS (%)"
                    )
                )
                
                st.plotly_chart(fig_los7, use_container_width=True, key="compl_nat_los7_trend")
            else:
                # Fallback to static bubble if no trend data
                natl_los7_pct = "—"
                try:
                    los7_natl_bubble = _read_csv_complications("TAB_LOS7_NATL.csv")
                    if not los7_natl_bubble.empty and "LOS_7_pct" in los7_natl_bubble.columns:
                        pct_val = los7_natl_bubble.iloc[0]["LOS_7_pct"]
                        if pd.notna(pct_val):
                            natl_los7_pct = f"{float(pct_val):.1f}%"
                except Exception:
                    pass
                st.markdown(f"<div class='nv-bubble' style='background:#FF8C00;width:120px;height:120px;font-size:1.7rem'>{natl_los7_pct}</div>", unsafe_allow_html=True)
                st.caption("National")
        else:
            # Fallback to static bubble
            natl_los7_pct = "—"
            try:
                los7_natl_bubble = _read_csv_complications("TAB_LOS7_NATL.csv")
                if not los7_natl_bubble.empty and "LOS_7_pct" in los7_natl_bubble.columns:
                    pct_val = los7_natl_bubble.iloc[0]["LOS_7_pct"]
                    if pd.notna(pct_val):
                        natl_los7_pct = f"{float(pct_val):.1f}%"
            except Exception:
                pass
            st.markdown(f"<div class='nv-bubble' style='background:#FF8C00;width:120px;height:120px;font-size:1.7rem'>{natl_los7_pct}</div>", unsafe_allow_html=True)
            st.caption("National")



