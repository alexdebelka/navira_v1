import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import numpy as np

import os
from pathlib import Path


def render_complications(hospital_id: str):
    """Render the Complications section using CSV data from new_data/COMPLICATIONS.
    
    Layout includes:
      - Overall complication rate bubbles (Hospital, National, Regional, Same category)
      - Funnel plot for complication rate vs volume
      - Complication rate by Clavien-Dindo grade (3-5) + Never events table
      - Length of stay distribution and scatter plots
    """
    st.subheader("Complications Overview")

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

    # Load complications data
    compl_hop = _read_csv_complications("TAB_COMPL_HOP_ROLL12.csv")
    compl_natl = _read_csv_complications("TAB_COMPL_NATL_ROLL12.csv")
    compl_reg = _read_csv_complications("TAB_COMPL_REG_ROLL12.csv")
    compl_status = _read_csv_complications("TAB_COMPL_STATUS_ROLL12.csv")

    # Load region/status mapping (from ACTIVITY folder for consistency)
    @st.cache_data(show_spinner=False)
    def _read_csv_activity(filename: str) -> pd.DataFrame:
        """Read CSV from ACTIVITY folder for region/status mapping."""
        candidates: list[str] = []
        try:
            candidates.append(str(Path.cwd() / "new_data" / "ACTIVITY"))
        except Exception:
            pass
        try:
            here = Path(__file__).resolve()
            candidates.append(str((here.parent / ".." / "new_data" / "ACTIVITY").resolve()))
            candidates.append(str((here.parent.parent / "new_data" / "ACTIVITY").resolve()))
        except Exception:
            pass
        candidates.append("/Users/alexdebelka/Downloads/navira/new_data/ACTIVITY")
        for c in candidates:
            try:
                if Path(c).is_dir():
                    p = Path(c) / filename
                    if p.exists():
                        df = pd.read_csv(p)
                        if "finessGeoDP" in df.columns:
                            df["finessGeoDP"] = df["finessGeoDP"].astype(str).str.strip()
                        if "lib_reg" in df.columns:
                            df["lib_reg"] = df["lib_reg"].astype(str).str.strip()
                        if "statut" in df.columns:
                            df["statut"] = df["statut"].astype(str).str.strip()
                        return df
            except Exception:
                continue
        return pd.DataFrame()

    rev_hop_12m = _read_csv_activity("TAB_REV_HOP_12M.csv")

    # Resolve region/status for this hospital
    region_name = None
    status_val = None
    try:
        _row = rev_hop_12m[rev_hop_12m.get("finessGeoDP").astype(str) == str(hospital_id)].head(1)
        region_name = str(_row.iloc[0].get("lib_reg") or _row.iloc[0].get("region") or "").strip() if not _row.empty else None
        status_val = str(_row.iloc[0].get("statut") or _row.iloc[0].get("status") or "").strip() if not _row.empty else None
    except Exception:
        pass

    # --- Overall complication rate (90 days) — bubble quartet ---
    st.markdown("### Overall complication rate (90 days)")
    use_12m_compl = st.toggle("Show last 12 months", value=False, key=f"compl_tab_12m_{hospital_id}")

    # Reload data based on toggle
    if use_12m_compl:
        compl_hop = _read_csv_complications("TAB_COMPL_HOP_ROLL12.csv")
        compl_natl = _read_csv_complications("TAB_COMPL_NATL_ROLL12.csv")
        compl_reg = _read_csv_complications("TAB_COMPL_REG_ROLL12.csv")
        compl_status = _read_csv_complications("TAB_COMPL_STATUS_ROLL12.csv")
    else:
        compl_hop = _read_csv_complications("TAB_COMPL_HOP_YEAR.csv")
        compl_natl = _read_csv_complications("TAB_COMPL_NATL_YEAR.csv")
        compl_reg = _read_csv_complications("TAB_COMPL_REG_YEAR.csv")
        compl_status = _read_csv_complications("TAB_COMPL_STATUS_YEAR.csv")

    # Color scheme matching procedures per year
    COMPL_COLORS = {
        "hospital": "#1f4e79",  # Dark teal/blue for hospital
        "national": "#E9A23B",  # Orange
        "regional": "#4ECDC4",  # Turquoise/teal
        "status": "#A78BFA"     # Purple
    }

    # Bubble display: Hospital, National, Regional, Same category
    col_hosp, col_nat, col_reg, col_cat = st.columns(4)
    
    # Hospital bubble
    with col_hosp:
        hosp_compl = "—"
        try:
            if not compl_hop.empty and "finessGeoDP" in compl_hop.columns and "COMPL_pct" in compl_hop.columns:
                hosp_rows = compl_hop[compl_hop["finessGeoDP"].astype(str) == str(hospital_id)]
                if not hosp_rows.empty:
                    # If YEAR file, get latest year; if ROLL12, should be a single row
                    if not use_12m_compl and "annee" in hosp_rows.columns:
                        hosp_rows["annee"] = pd.to_numeric(hosp_rows["annee"], errors="coerce")
                        latest_year = hosp_rows["annee"].max()
                        hosp_rows = hosp_rows[hosp_rows["annee"] == latest_year]
                    if not hosp_rows.empty:
                        compl_val = hosp_rows.iloc[0]["COMPL_pct"]
                        if pd.notna(compl_val):
                            hosp_compl = f"{float(compl_val):.1f}%"
        except Exception:
            pass
        st.markdown(f"<div class='nv-bubble' style='background:{COMPL_COLORS['hospital']};width:120px;height:120px;font-size:1.8rem'>{hosp_compl}</div>", unsafe_allow_html=True)
        st.caption("Hospital")

    # National bubble
    with col_nat:
        nat_compl = "—"
        try:
            if not compl_natl.empty and "COMPL_pct" in compl_natl.columns:
                natl_rows = compl_natl.copy()
                # If YEAR file, get latest year
                if not use_12m_compl and "annee" in natl_rows.columns:
                    natl_rows["annee"] = pd.to_numeric(natl_rows["annee"], errors="coerce")
                    latest_year = natl_rows["annee"].max()
                    natl_rows = natl_rows[natl_rows["annee"] == latest_year]
                if not natl_rows.empty:
                    compl_val = natl_rows.iloc[0]["COMPL_pct"]
                    if pd.notna(compl_val):
                        nat_compl = f"{float(compl_val):.1f}%"
        except Exception:
            pass
        st.markdown(f"<div class='nv-bubble' style='background:{COMPL_COLORS['national']};width:120px;height:120px;font-size:1.8rem'>{nat_compl}</div>", unsafe_allow_html=True)
        st.caption("National")

    # Regional bubble
    with col_reg:
        reg_compl = "—"
        try:
            if region_name and not compl_reg.empty and "lib_reg" in compl_reg.columns and "COMPL_pct" in compl_reg.columns:
                reg_rows = compl_reg[compl_reg["lib_reg"].astype(str).str.strip() == str(region_name)]
                # If YEAR file, get latest year
                if not use_12m_compl and not reg_rows.empty and "annee" in reg_rows.columns:
                    reg_rows["annee"] = pd.to_numeric(reg_rows["annee"], errors="coerce")
                    latest_year = reg_rows["annee"].max()
                    reg_rows = reg_rows[reg_rows["annee"] == latest_year]
                if not reg_rows.empty:
                    compl_val = reg_rows.iloc[0]["COMPL_pct"]
                    if pd.notna(compl_val):
                        reg_compl = f"{float(compl_val):.1f}%"
        except Exception:
            pass
        st.markdown(f"<div class='nv-bubble' style='background:{COMPL_COLORS['regional']};width:120px;height:120px;font-size:1.8rem'>{reg_compl}</div>", unsafe_allow_html=True)
        st.caption("Regional")

    # Same category bubble
    with col_cat:
        status_compl = "—"
        try:
            if status_val and not compl_status.empty and "statut" in compl_status.columns and "COMPL_pct" in compl_status.columns:
                status_rows = compl_status[compl_status["statut"].astype(str).str.strip() == str(status_val)]
                # If YEAR file, get latest year
                if not use_12m_compl and not status_rows.empty and "annee" in status_rows.columns:
                    status_rows["annee"] = pd.to_numeric(status_rows["annee"], errors="coerce")
                    latest_year = status_rows["annee"].max()
                    status_rows = status_rows[status_rows["annee"] == latest_year]
                if not status_rows.empty:
                    compl_val = status_rows.iloc[0]["COMPL_pct"]
                    if pd.notna(compl_val):
                        status_compl = f"{float(compl_val):.1f}%"
        except Exception:
            pass
        st.markdown(f"<div class='nv-bubble' style='background:{COMPL_COLORS['status']};width:120px;height:120px;font-size:1.8rem'>{status_compl}</div>", unsafe_allow_html=True)
        st.caption("Same category Hospitals")

    # --- Funnel plot: Overall complication rate (90 days) ---
    st.markdown("---")
    st.markdown("#### Overall complication rate")
    st.markdown("##### Funnel plot: 90-day complications by hospital volume")
    
    scope_funnel = st.radio(
        "Compare against",
        ["National", "Regional", "Same status"],
        horizontal=True,
        index=0,
        key=f"compl_tab_funnel_scope_{hospital_id}"
    )

    # Load monthly hospital data to get last 3 months (90 days)
    compl_hop_monthly = _read_csv_complications("TAB_COMPL_HOP_ROLL12.csv")
    
    if compl_hop_monthly is None or compl_hop_monthly.empty or "COMPL_nb" not in compl_hop_monthly.columns:
        st.info("No monthly complications data available for funnel plot.")
    else:
        try:
            d = compl_hop_monthly.copy()
            # Normalize columns
            d["finessGeoDP"] = d.get("finessGeoDP").astype(str)
            d["annee"] = pd.to_numeric(d.get("annee"), errors="coerce")
            d["mois"] = pd.to_numeric(d.get("mois"), errors="coerce")
            d["TOT"] = pd.to_numeric(d.get("TOT"), errors="coerce").fillna(0)
            d["COMPL_nb"] = pd.to_numeric(d.get("COMPL_nb"), errors="coerce").fillna(0)
            
            # Get last 3 months (90 days)
            d = d.dropna(subset=["annee", "mois"])
            if not d.empty:
                # Create a sortable year-month column
                d["year_month"] = d["annee"] * 100 + d["mois"]
                max_ym = d["year_month"].max()
                
                # Get last 3 month-year combinations
                unique_ym = sorted(d["year_month"].unique(), reverse=True)[:3]
                d_last3 = d[d["year_month"].isin(unique_ym)]
                
                # Aggregate by hospital: sum TOT and COMPL_nb over last 3 months
                agg = d_last3.groupby("finessGeoDP", as_index=False).agg(
                    total=("TOT", "sum"),
                    events=("COMPL_nb", "sum")
                )
                agg = agg[agg["total"] > 0]
                
                if agg.empty:
                    st.info("No valid data for funnel plot.")
                else:
                    agg["rate"] = agg["events"] / agg["total"]
                    
                    # Scope filtering using region/status from rev_hop_12m
                    if scope_funnel == "Regional":
                        if region_name and not rev_hop_12m.empty and "lib_reg" in rev_hop_12m.columns:
                            reg_ids = rev_hop_12m[rev_hop_12m.get("lib_reg").astype(str).str.strip() == str(region_name)]["finessGeoDP"].astype(str).unique().tolist()
                            agg = agg[agg["finessGeoDP"].isin(reg_ids)]
                    elif scope_funnel == "Same status":
                        if status_val and not rev_hop_12m.empty and "statut" in rev_hop_12m.columns:
                            status_ids = rev_hop_12m[rev_hop_12m.get("statut").astype(str).str.strip() == str(status_val)]["finessGeoDP"].astype(str).unique().tolist()
                            agg = agg[agg["finessGeoDP"].isin(status_ids)]
                    
                    if agg.empty:
                        st.info(f"No data for {scope_funnel} scope.")
                    else:
                        # Overall mean (pooled)
                        p_bar = float(agg["events"].sum() / agg["total"].sum()) if agg["total"].sum() > 0 else 0.0
                        
                        # Control limits vs volume
                        vol = np.linspace(max(1, agg["total"].min()), agg["total"].max(), 200)
                        se = np.sqrt(p_bar * (1 - p_bar) / vol)
                        z95 = 1.96
                        z99 = 3.09
                        upper95 = p_bar + z95 * se
                        lower95 = p_bar - z95 * se
                        upper99 = p_bar + z99 * se
                        lower99 = p_bar - z99 * se
                        
                        # Clip to [0,1]
                        upper95 = np.clip(upper95, 0, 1)
                        lower95 = np.clip(lower95, 0, 1)
                        upper99 = np.clip(upper99, 0, 1)
                        lower99 = np.clip(lower99, 0, 1)
                        
                        # Separate selected and other hospitals
                        sel = agg[agg["finessGeoDP"] == str(hospital_id)]
                        others = agg[agg["finessGeoDP"] != str(hospital_id)]
                        
                        fig_funnel = go.Figure()
                        
                        # Other hospitals
                        if not others.empty:
                            fig_funnel.add_trace(go.Scatter(
                                x=others["total"], y=others["rate"], mode="markers",
                                marker=dict(color="#60a5fa", size=6, opacity=0.75), name="Other hospitals",
                                hovertemplate='Volume: %{x:,}<br>Rate: %{y:.1%}<extra></extra>'
                            ))
                        
                        # Selected hospital
                        if not sel.empty:
                            fig_funnel.add_trace(go.Scatter(
                                x=sel["total"], y=sel["rate"], mode="markers",
                                marker=dict(color="#FF8C00", size=12, line=dict(color="white", width=1)), name="Selected hospital",
                                hovertemplate='Volume: %{x:,}<br>Rate: %{y:.1%}<extra></extra>'
                            ))
                        
                        # Mean line
                        fig_funnel.add_trace(go.Scatter(
                            x=[vol.min(), vol.max()], y=[p_bar, p_bar], mode="lines",
                            line=dict(color="#4A90E2", width=2, dash="solid"), name="Overall mean"
                        ))
                        
                        # 95% CI (dashed)
                        fig_funnel.add_trace(go.Scatter(
                            x=vol, y=upper95, mode="lines",
                            line=dict(color="#7FB3D5", width=1, dash="dash"), name="95% CI"
                        ))
                        fig_funnel.add_trace(go.Scatter(
                            x=vol, y=lower95, mode="lines",
                            line=dict(color="#7FB3D5", width=1, dash="dash"), showlegend=False
                        ))
                        
                        # 99% CI (dotted)
                        fig_funnel.add_trace(go.Scatter(
                            x=vol, y=upper99, mode="lines",
                            line=dict(color="#9DC6E0", width=1, dash="dot"), name="99% CI"
                        ))
                        fig_funnel.add_trace(go.Scatter(
                            x=vol, y=lower99, mode="lines",
                            line=dict(color="#9DC6E0", width=1, dash="dot"), showlegend=False
                        ))
                        
                        fig_funnel.update_layout(
                            height=450,
                            xaxis_title="Hospital volume (all techniques)",
                            yaxis_title="Complication rate",
                            yaxis_tickformat=".1%",
                            plot_bgcolor='rgba(0,0,0,0)',
                            paper_bgcolor='rgba(0,0,0,0)'
                        )
                        st.plotly_chart(fig_funnel, use_container_width=True, key=f"compl_funnel_chart_{hospital_id}")
                        st.caption("Dashed = 95% CI; dotted = 99% CI; solid = overall mean")
        except Exception as e:
            st.info(f"Could not render funnel plot: {e}")

    # --- Complication rate by Clavien-Dindo grade + Never events ---
    st.markdown("---")
    st.markdown("#### Complication rate by Clavien-Dindo grade (90 days)")

    # Load Clavien-Dindo grade data
    grade_hop = _read_csv_complications("TAB_COMPL_GRADE_HOP_YEAR.csv")
    grade_natl = _read_csv_complications("TAB_COMPL_GRADE_NATL_YEAR.csv")
    grade_reg = _read_csv_complications("TAB_COMPL_GRADE_REG_YEAR.csv")
    grade_status = _read_csv_complications("TAB_COMPL_GRADE_STATUS_YEAR.csv")

    # Load Never events data
    never_hop = _read_csv_complications("TAB_NEVER_HOP.csv")
    never_natl = _read_csv_complications("TAB_NEVER_NATL.csv")
    never_reg = _read_csv_complications("TAB_NEVER_REG.csv")
    never_status = _read_csv_complications("TAB_NEVER_STATUS.csv")

    # Color scheme for bar plot
    GRADE_COLORS = {
        'Hospital': '#1f4e79',     # Dark blue
        'National': '#E9A23B',     # Orange
        'Regional': '#4ECDC4',     # Green/teal
        'Same status': '#A78BFA'   # Light blue/purple
    }

    # Helper function to get grade rates for a given dataset
    def _get_grade_rates(df: pd.DataFrame, filters: dict | None = None) -> dict[int, float]:
        """Get complication rates for grades 3, 4, 5 from latest year."""
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
        
        # Get latest year
        if "annee" in d.columns:
            d["annee"] = pd.to_numeric(d["annee"], errors="coerce")
            latest_year = d["annee"].max()
            d = d[d["annee"] == latest_year]
        
        if d.empty:
            return {3: 0.0, 4: 0.0, 5: 0.0}
        
        # Normalize columns
        d["clav_cat_90"] = pd.to_numeric(d["clav_cat_90"], errors="coerce")
        d["TOT"] = pd.to_numeric(d["TOT"], errors="coerce").fillna(0)
        d["COMPL_nb"] = pd.to_numeric(d["COMPL_nb"], errors="coerce").fillna(0)
        
        # Aggregate by grade
        rates = {}
        for grade in [3, 4, 5]:
            grade_rows = d[d["clav_cat_90"] == grade]
            if not grade_rows.empty:
                # Sum complications and total for this grade
                total_compl = grade_rows["COMPL_nb"].sum()
                total_proc = grade_rows["TOT"].iloc[0] if len(grade_rows) > 0 else 0  # TOT should be same per year
                rates[grade] = (total_compl / total_proc * 100.0) if total_proc > 0 else 0.0
            else:
                rates[grade] = 0.0
        
        return rates

    # Get never events data
    def _get_never_events(df: pd.DataFrame, filters: dict | None = None) -> tuple[int, int]:
        """Returns (NEVER_nb, TOT) for never events calculation."""
        if df is None or df.empty or "NEVER_nb" not in df.columns or "TOT" not in df.columns:
            return (0, 0)
        
        d = df.copy()
        
        # Apply filters
        if filters:
            for k, v in filters.items():
                if k in d.columns and v is not None and str(v):
                    d = d[d[k].astype(str).str.strip() == str(v)]
        
        if d.empty:
            return (0, 0)
        
        # Normalize and sum
        never_nb = int(pd.to_numeric(d["NEVER_nb"], errors="coerce").fillna(0).sum())
        tot = int(pd.to_numeric(d["TOT"], errors="coerce").fillna(0).sum())
        
        return (never_nb, tot)

    # Compute rates for all groups
    rates_h = _get_grade_rates(grade_hop, {'finessGeoDP': str(hospital_id)})
    rates_n = _get_grade_rates(grade_natl, None)
    rates_r = _get_grade_rates(grade_reg, {'lib_reg': region_name} if region_name else None)
    rates_s = _get_grade_rates(grade_status, {'statut': status_val} if status_val else None)

    # Compute never events
    never_h = _get_never_events(never_hop, {'finessGeoDP': str(hospital_id)})
    never_n = _get_never_events(never_natl, None)
    never_r = _get_never_events(never_reg, {'lib_reg': region_name} if region_name else None)
    never_s = _get_never_events(never_status, {'statut': status_val} if status_val else None)

    # Build bar chart data
    rows = []
    for grade in [3, 4, 5]:
        rows.append({'Grade': f'grade {grade}', 'Group': 'Hospital', 'Rate': rates_h.get(grade, 0.0)})
        rows.append({'Grade': f'grade {grade}', 'Group': 'National', 'Rate': rates_n.get(grade, 0.0)})
        rows.append({'Grade': f'grade {grade}', 'Group': 'Regional', 'Rate': rates_r.get(grade, 0.0)})
        rows.append({'Grade': f'grade {grade}', 'Group': 'Same status', 'Rate': rates_s.get(grade, 0.0)})
    
    df_bar = pd.DataFrame(rows)
    
    # Layout: bar chart on left, never events table on right
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
            paper_bgcolor='rgba(0,0,0,0)'
        )
        fig_grade.update_yaxes(range=[0, max(8, df_bar['Rate'].max() * 1.3)])
        fig_grade.update_traces(hovertemplate='%{fullData.name}<br>%{x}: %{y:.1f}%<extra></extra>')
        st.plotly_chart(fig_grade, use_container_width=True, key=f"compl_grade_chart_{hospital_id}")
    
    with right:
        # Never events table
        def _fmt_never(n, d):
            pct = (n / d * 100.0) if d > 0 else 0.0
            return f"{n:,}/{d:,}", f"{pct:.1f}%"
        
        never_rows = [
            ("Hospital", *_fmt_never(*never_h), GRADE_COLORS['Hospital']),
            ("National", *_fmt_never(*never_n), GRADE_COLORS['National']),
            ("Regional", *_fmt_never(*never_r), GRADE_COLORS['Regional']),
            ("Same status", *_fmt_never(*never_s), GRADE_COLORS['Same status']),
        ]
        
        # Inline CSS for styled table
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
        for label, frac, pct, color in never_rows:
            html.append(
                f"<div class='nv-ne-row'><div class='nv-ne-left'><span class='nv-ne-dot' style='background:{color}'></span>{label}</div>"
                f"<div><span class='nv-ne-num'>{frac}</span><span class='nv-ne-pct'> ({pct})</span></div></div>"
            )
        html.append("</div>")
        st.markdown("".join(html), unsafe_allow_html=True)

    # --- Length of stay — index admission ---
    st.markdown("---")
    st.markdown("#### Length of stay – index admission")
    
    # Load LOS data
    los_hop = _read_csv_complications("TAB_LOS_HOP.csv")
    los_natl = _read_csv_complications("TAB_LOS_NATL.csv")
    los_reg = _read_csv_complications("TAB_LOS_REG.csv")
    los_status = _read_csv_complications("TAB_LOS_STATUS.csv")
    
    # Color schemes matching the procedures per year section
    # Hospital: variations of dark blue (#1f4e79)
    LOS_COLORS_HOSPITAL = {
        '[-1,0]': '#0f273d',      # Darker blue
        '(0,3]': '#1f4e79',       # Dark blue (base)
        '(3,6]': '#3a6ba3',       # Medium blue
        '(6,225]': '#5a8bc9'      # Lighter blue
    }
    # National: variations of orange (#E9A23B)
    LOS_COLORS_NATIONAL = {
        '[-1,0]': '#CC7A00',      # Darker orange
        '(0,3]': '#E9A23B',       # Orange (base)
        '(3,6]': '#FFB84D',       # Lighter orange
        '(6,225]': '#FFD699'      # Lightest orange
    }
    # Regional: variations of turquoise (#4ECDC4)
    LOS_COLORS_REGIONAL = {
        '[-1,0]': '#2E9D95',      # Darker turquoise
        '(0,3]': '#4ECDC4',       # Turquoise (base)
        '(3,6]': '#6EDDD4',       # Lighter turquoise
        '(6,225]': '#8EF3EA'      # Lightest turquoise
    }
    # Same category: variations of purple (#A78BFA)
    LOS_COLORS_CATEGORY = {
        '[-1,0]': '#8B6FD4',      # Darker purple
        '(0,3]': '#A78BFA',       # Purple (base)
        '(3,6]': '#C4A8FF',       # Lighter purple
        '(6,225]': '#E0D0FF'      # Lightest purple
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
        
        colors = color_map if color_map else LOS_COLORS_HOSPITAL
        
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
            legend_title_text='bucket'
        )
        fig.update_yaxes(range=[0, 100])
        fig.update_traces(hovertemplate='%{x}<br>%{y:.0f}%<extra></extra>')
        
        # Update legend labels to use bucket names
        for trace in fig.data:
            if trace.name in LOS_BUCKET_LABELS:
                trace.name = LOS_BUCKET_LABELS[trace.name]
        
        st.plotly_chart(fig, use_container_width=True, key=chart_key if chart_key else None)
    
    # Load >7 days LOS data for bubble panel (before column split)
    los7_hop_bubble = _read_csv_complications("TAB_LOS7_HOP.csv")
    los7_natl_bubble = _read_csv_complications("TAB_LOS7_NATL.csv")
    los7_reg_bubble = _read_csv_complications("TAB_LOS7_REG.csv")
    los7_status_bubble = _read_csv_complications("TAB_LOS7_STATUS.csv")
    
    # Layout: LOS distribution charts on left, bubble panel on right
    left_charts, right_bubbles = st.columns([2.5, 1])
    
    with left_charts:
        st.markdown("##### Length of stay distribution by year (share %)")
        
        # Hospital chart (larger)
        _los_bars(los_hop, 'Hospital', {'finessGeoDP': str(hospital_id)}, height=240, color_map=LOS_COLORS_HOSPITAL, chart_key=f"compl_los_hosp_{hospital_id}")
        
        # Three small charts: national, regional, same category (with theme colors)
        c_nat2, c_reg2, c_cat2 = st.columns(3)
        with c_nat2:
            _los_bars(los_natl, 'National', None, color_map=LOS_COLORS_NATIONAL, chart_key=f"compl_los_natl_{hospital_id}")
        with c_reg2:
            _los_bars(los_reg, 'Regional', {'lib_reg': region_name} if region_name else None, color_map=LOS_COLORS_REGIONAL, chart_key=f"compl_los_reg_{hospital_id}")
        with c_cat2:
            _los_bars(los_status, 'Same category Hospitals', {'statut': status_val} if status_val else None, color_map=LOS_COLORS_CATEGORY, chart_key=f"compl_los_cat_{hospital_id}")
    
    with right_bubbles:
        
        st.markdown("##### Patients >7 days of 90d-LOS")
        
        # Hospital >7 days percentage
        hosp_los7_pct = "—"
        try:
            if not los7_hop_bubble.empty and "finessGeoDP" in los7_hop_bubble.columns and "LOS_7_pct" in los7_hop_bubble.columns:
                hosp_row = los7_hop_bubble[los7_hop_bubble["finessGeoDP"].astype(str) == str(hospital_id)]
                if not hosp_row.empty:
                    pct_val = hosp_row.iloc[0]["LOS_7_pct"]
                    if pd.notna(pct_val):
                        hosp_los7_pct = f"{float(pct_val):.1f}%"
        except Exception:
            pass
        st.markdown(f"<div class='nv-bubble' style='background:#1f4e79;width:110px;height:110px;font-size:1.6rem'>{hosp_los7_pct}</div>", unsafe_allow_html=True)
        st.caption("Hospital")
        
        # National >7 days percentage
        natl_los7_pct = "—"
        try:
            if not los7_natl_bubble.empty and "LOS_7_pct" in los7_natl_bubble.columns:
                pct_val = los7_natl_bubble.iloc[0]["LOS_7_pct"]
                if pd.notna(pct_val):
                    natl_los7_pct = f"{float(pct_val):.1f}%"
        except Exception:
            pass
        st.markdown(f"<div class='nv-bubble' style='background:#E9A23B;width:110px;height:110px;font-size:1.6rem'>{natl_los7_pct}</div>", unsafe_allow_html=True)
        st.caption("National")
        
        # Regional >7 days percentage
        reg_los7_pct = "—"
        try:
            if region_name and not los7_reg_bubble.empty and "lib_reg" in los7_reg_bubble.columns and "LOS_7_pct" in los7_reg_bubble.columns:
                reg_row = los7_reg_bubble[los7_reg_bubble["lib_reg"].astype(str).str.strip() == str(region_name)]
                if not reg_row.empty:
                    pct_val = reg_row.iloc[0]["LOS_7_pct"]
                    if pd.notna(pct_val):
                        reg_los7_pct = f"{float(pct_val):.1f}%"
        except Exception:
            pass
        st.markdown(f"<div class='nv-bubble' style='background:#4ECDC4;width:110px;height:110px;font-size:1.6rem'>{reg_los7_pct}</div>", unsafe_allow_html=True)
        st.caption("Regional")
        
        # Same category >7 days percentage
        status_los7_pct = "—"
        try:
            if status_val and not los7_status_bubble.empty and "statut" in los7_status_bubble.columns and "LOS_7_pct" in los7_status_bubble.columns:
                status_row = los7_status_bubble[los7_status_bubble["statut"].astype(str).str.strip() == str(status_val)]
                if not status_row.empty:
                    pct_val = status_row.iloc[0]["LOS_7_pct"]
                    if pd.notna(pct_val):
                        status_los7_pct = f"{float(pct_val):.1f}%"
        except Exception:
            pass
        st.markdown(f"<div class='nv-bubble' style='background:#A78BFA;width:110px;height:110px;font-size:1.6rem'>{status_los7_pct}</div>", unsafe_allow_html=True)
        st.caption("Same category")

    # --- Scatter plot for >7 days length of stay ---
    st.markdown("---")
    st.markdown("#### Scatter plot: >7 days LOS vs procedure volume")
    
    scope_los7 = st.radio(
        "Compare against",
        ["National", "Regional", "Same status"],
        horizontal=True,
        index=0,
        key=f"compl_tab_los7_scatter_scope_{hospital_id}"
    )

    # Use already loaded >7 days LOS data from bubble panel
    los7_hop = los7_hop_bubble
    
    if los7_hop is None or los7_hop.empty or "TOT" not in los7_hop.columns or "LOS_7_pct" not in los7_hop.columns:
        st.info("No >7 days LOS dataset available for scatter.")
    else:
        d = los7_hop.copy()
        d["finessGeoDP"] = d.get("finessGeoDP").astype(str)
        d["TOT"] = pd.to_numeric(d.get("TOT", 0), errors="coerce").fillna(0)
        d["LOS_7_pct"] = pd.to_numeric(d.get("LOS_7_pct", 0), errors="coerce").fillna(0)

        # Scope filtering - need to use region/status info from other datasets
        # We can use rev_hop_12m which has lib_reg and statut columns
        if scope_los7 == "Regional":
            if region_name and not rev_hop_12m.empty and "lib_reg" in rev_hop_12m.columns:
                reg_ids = rev_hop_12m[rev_hop_12m.get("lib_reg").astype(str).str.strip() == str(region_name)]["finessGeoDP"].astype(str).unique().tolist()
                d_sc = d[d["finessGeoDP"].isin(reg_ids)]
            else:
                d_sc = pd.DataFrame()
        elif scope_los7 == "Same status":
            if status_val and not rev_hop_12m.empty and "statut" in rev_hop_12m.columns:
                status_ids = rev_hop_12m[rev_hop_12m.get("statut").astype(str).str.strip() == str(status_val)]["finessGeoDP"].astype(str).unique().tolist()
                d_sc = d[d["finessGeoDP"].isin(status_ids)]
            else:
                d_sc = pd.DataFrame()
        else:
            d_sc = d.copy()

        if d_sc.empty:
            st.info("No data to build >7 days LOS scatter for this scope.")
        else:
            sel = d_sc[d_sc["finessGeoDP"].astype(str) == str(hospital_id)]
            oth = d_sc[d_sc["finessGeoDP"].astype(str) != str(hospital_id)]
            fig_los7 = go.Figure()
            
            # Others
            if not oth.empty:
                fig_los7.add_trace(go.Scatter(
                    x=oth["TOT"], y=oth["LOS_7_pct"], mode="markers",
                    marker=dict(color="#60a5fa", size=6, opacity=0.75), name="Other hospitals",
                    hovertemplate='Procedures: %{x:.0f}<br>>7 day admission: %{y:.1f}%<extra></extra>'
                ))
            
            # Selected
            if not sel.empty:
                fig_los7.add_trace(go.Scatter(
                    x=sel["TOT"], y=sel["LOS_7_pct"], mode="markers",
                    marker=dict(color="#FF8C00", size=12, line=dict(color="white", width=1)), name="Selected hospital",
                    hovertemplate='Procedures: %{x:.0f}<br>>7 day admission: %{y:.1f}%<extra></extra>'
                ))
            
            fig_los7.update_layout(
                height=420,
                xaxis_title="Number of procedure per year (any approach)",
                yaxis_title=">7 day of admission (%)",
                xaxis=dict(range=[0, None]),
                yaxis=dict(range=[0, None]),
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)'
            )
            st.plotly_chart(fig_los7, use_container_width=True, key=f"compl_los7_scatter_{hospital_id}")
            st.caption(f"Scope: {scope_los7}; Each point represents a hospital's procedure volume vs. percentage of patients with >7 days LOS in 90-day period")

