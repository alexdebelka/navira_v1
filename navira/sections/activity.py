import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import numpy as np

import os
from pathlib import Path


APPROACH_LABELS = {"LAP": "Open Surgery", "COE": "Coelioscopy", "ROB": "Robotic"}
APPROACH_COLORS = {"Open Surgery": "#A23B72", "Coelioscopy": "#2E86AB", "Robotic": "#F7931E"}


def _latest_year(df: pd.DataFrame) -> int | None:
    if df is None or df.empty:
        return None
    if "annee" in df.columns:
        years = pd.to_numeric(df["annee"], errors="coerce").dropna().astype(int)
    elif "year" in df.columns:
        years = pd.to_numeric(df["year"], errors="coerce").dropna().astype(int)
    else:
        return None
    return int(years.max()) if not years.empty else None


def _pie_from(df: pd.DataFrame, title: str):
    if df is None or df.empty:
        st.info(f"No data for {title}.")
        return
    totals: dict[str, float] = {}
    for _, r in df.iterrows():
        code = str(r.get("vda") or r.get("VDA") or "").upper()
        raw_val = r.get("n", pd.NA)
        if pd.isna(raw_val):
            raw_val = r.get("TOT", 0)
        val = pd.to_numeric(raw_val, errors="coerce")
        if code:
            totals[code] = totals.get(code, 0.0) + float(val)
    labels, values, colors = [], [], []
    for code in ["LAP", "COE", "ROB"]:
        if code in totals and totals[code] > 0:
            labels.append(APPROACH_LABELS.get(code, code))
            values.append(totals[code])
            colors.append(APPROACH_COLORS.get(APPROACH_LABELS.get(code, code), None))
    if not values:
        st.info(f"No data for {title}.")
        return
    fig = go.Figure(go.Pie(labels=labels, values=values, hole=0.4, marker_colors=colors))
    fig.update_layout(title=title, height=320, plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)')
    st.plotly_chart(fig, use_container_width=True)


def render_activity(hospital_id: str):
    """Render the Activity section (Version 2 layout) using CSV repo data only.

    Layout:
      - Row 1: big hospital volume bar (per year) + YoY bubble (2025 vs 2024 if present)
      - Row 2: hospital approaches (large, latest year) and three small pies (national, regional, same category)
    """
    st.subheader("Activity Overview")

    # Even though a repo is accepted for backward compatibility, for this section
    # we now read totals directly from dedicated VOL CSVs (CSV-first, no recompute)
    @st.cache_data(show_spinner=False)
    def _resolve_activity_dir() -> str | None:
        candidates: list[str] = []
        env_dir = os.environ.get("NAVIRA_ACTIVITY_DIR")
        if env_dir:
            candidates.append(env_dir)
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
                    return c
            except Exception:
                continue
        return None

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
            # Same normalization as _read_csv
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

    @st.cache_data(show_spinner=False)
    def _read_csv(filename: str) -> pd.DataFrame:
        base = _resolve_activity_dir()
        if not base:
            return pd.DataFrame()
        p = Path(base) / filename
        try:
            df = pd.read_csv(p)
            # Normalization: types used below
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
            # Handle diff_pct column in trend files (may contain "NA" strings)
            if "diff_pct" in df.columns:
                df["diff_pct"] = pd.to_numeric(df["diff_pct"], errors="coerce")
            # Handle PCT_rev and TOT_rev columns in revisional files
            if "PCT_rev" in df.columns:
                df["PCT_rev"] = pd.to_numeric(df["PCT_rev"], errors="coerce")
            if "TOT_rev" in df.columns:
                df["TOT_rev"] = pd.to_numeric(df["TOT_rev"], errors="coerce")
            if "TOT" in df.columns:
                df["TOT"] = pd.to_numeric(df["TOT"], errors="coerce")
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
            return df
        except Exception:
            return pd.DataFrame()

    # Load totals CSVs directly
    vol_hop_year = _read_csv("TAB_VOL_HOP_YEAR.csv")
    vol_reg_year = _read_csv("TAB_VOL_REG_YEAR.csv")
    vol_nat_year = _read_csv("TAB_VOL_NATL_YEAR.csv")
    vol_status_year = _read_csv("TAB_VOL_STATUS_YEAR.csv")
    # Approach pies — also use APP CSVs directly
    app_hop_year = _read_csv("TAB_APP_HOP_YEAR.csv")
    app_nat_year = _read_csv("TAB_APP_NATL_YEAR.csv")
    app_reg_year = _read_csv("TAB_APP_REG_YEAR.csv")
    app_status_year = _read_csv("TAB_APP_STATUS_YEAR.csv")
    # Region/Status mapping for this hospital
    rev_hop_12m = _read_csv("TAB_REV_HOP_12M.csv")
    # Trend data for YoY bubbles
    trend_hop = _read_csv("TAB_TREND_HOP.csv")
    trend_natl = _read_csv("TAB_TREND_NATL.csv")
    trend_reg = _read_csv("TAB_TREND_REG.csv")
    trend_status = _read_csv("TAB_TRENDS_STATUS.csv")

    # Row 1: Hospital volume per year (bar)
    col1, col2 = st.columns([2, 1])
    with col1:
        d = vol_hop_year
        if not d.empty:
            hosp = d[d["finessGeoDP"] == str(hospital_id)].copy()
            if not hosp.empty:
                hosp = hosp.sort_values("annee" if "annee" in hosp.columns else "year")
                x = hosp["annee" if "annee" in hosp.columns else "year"].astype(int).astype(str)
                value_col = "n" if "n" in hosp.columns else ("TOT" if "TOT" in hosp.columns else None)
                y = pd.to_numeric(hosp[value_col], errors="coerce").fillna(0) if value_col else pd.Series([], dtype=float)
                colors = ["#1f4e79" if v == "2025" else "#4e79a7" for v in x]
                fig = go.Figure(go.Bar(x=x, y=y, marker_color=colors, hovertemplate='Year: %{x}<br>Procedures: %{y:,}<extra></extra>'))
                fig.update_layout(title="Hospital Procedures per Year", height=380, plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)')
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info(f"No volume data found for hospital {hospital_id}")
        else:
            st.warning("Volume data not available")

    with col2:
        # YoY bubble 2025 vs 2024 from trend data
        yoy_text = "—"
        try:
            if not trend_hop.empty and "finessGeoDP" in trend_hop.columns and "diff_pct" in trend_hop.columns:
                hosp_trend = trend_hop[trend_hop["finessGeoDP"].astype(str) == str(hospital_id)]
                if not hosp_trend.empty:
                    diff_val = hosp_trend.iloc[0]["diff_pct"]
                    if pd.notna(diff_val):
                        yoy_text = f"{float(diff_val):+.1f}%"
        except Exception:
            pass
        st.markdown(f"<div class='nv-bubble teal' style='width:110px;height:110px;font-size:1.6rem'>{yoy_text}</div>", unsafe_allow_html=True)
        st.caption('2025 YTD vs 2024 (% change)')


    st.markdown("---")
    st.markdown("#### National / Regional / Same category — Procedures per year")
    c_nat, c_reg, c_cat = st.columns(3)

    # Slice hospital totals once
    hosp_totals_df = vol_hop_year[vol_hop_year.get("finessGeoDP").astype(str) == str(hospital_id)].copy()

    # Resolve region/status from REV 12M file (before computing labels)
    try:
        _row = rev_hop_12m[rev_hop_12m.get("finessGeoDP").astype(str) == str(hospital_id)].head(1)
        region_name = str(_row.iloc[0].get("lib_reg") or _row.iloc[0].get("region") or "").strip() if not _row.empty else None
        status_val = str(_row.iloc[0].get("statut") or _row.iloc[0].get("status") or "").strip() if not _row.empty else None
    except Exception:
        region_name = None
        status_val = None

    # National
    with c_nat:
        nat_tot = vol_nat_year.copy()
        if not nat_tot.empty:
            s1, s2 = st.columns([4, 1])
            with s1:
                dfp = nat_tot.copy()
                dfp = dfp.sort_values("annee")
                fig_n = px.bar(
                    dfp.assign(annee=lambda d: d["annee"].astype(int).astype(str)),
                    x="annee", y="n", title="National",
                    color_discrete_sequence=["#E9A23B"],
                )
                fig_n.update_layout(height=260, plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)')
                fig_n.update_traces(hovertemplate='Year: %{x}<br>Procedures: %{y:,}<extra></extra>')
                st.plotly_chart(fig_n, use_container_width=True)
            with s2:
                # Get YoY change from trend data
                nat_yoy = "—"
                try:
                    if not trend_natl.empty and "diff_pct" in trend_natl.columns:
                        diff_val = trend_natl.iloc[0]["diff_pct"]
                        if pd.notna(diff_val):
                            nat_yoy = f"{float(diff_val):+.1f}%"
                except Exception:
                    pass
                if nat_yoy != "—":
                    st.markdown(f"<div class='nv-bubble' style='background:#E9A23B;width:90px;height:90px;font-size:1.2rem'>{nat_yoy}</div>", unsafe_allow_html=True)
                    st.caption('2025 YTD vs 2024 (% change)')
        else:
            st.info("No national APP CSV data.")

    # Regional
    with c_reg:
        if region_name and not app_reg_year.empty:
            reg = vol_reg_year[vol_reg_year.get("lib_reg").astype(str).str.strip() == str(region_name)]
            if not reg.empty:
                s1, s2 = st.columns([4, 1])
                with s1:
                    dfp = reg.sort_values("annee")
                    fig_r = px.bar(
                        dfp.assign(annee=lambda d: d["annee"].astype(int).astype(str)),
                        x="annee", y="n", title=f"Regional — {region_name}",
                        color_discrete_sequence=["#4ECDC4"],
                    )
                    fig_r.update_layout(height=260, plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)')
                    fig_r.update_traces(hovertemplate='Year: %{x}<br>Procedures: %{y:,}<extra></extra>')
                    st.plotly_chart(fig_r, use_container_width=True)
                with s2:
                    # Get YoY change from trend data
                    reg_yoy = "—"
                    try:
                        if not trend_reg.empty and "lib_reg" in trend_reg.columns and "diff_pct" in trend_reg.columns:
                            reg_trend = trend_reg[trend_reg["lib_reg"].astype(str).str.strip() == str(region_name)]
                            if not reg_trend.empty:
                                diff_val = reg_trend.iloc[0]["diff_pct"]
                                if pd.notna(diff_val):
                                    reg_yoy = f"{float(diff_val):+.1f}%"
                    except Exception:
                        pass
                    if reg_yoy != "—":
                        st.markdown(f"<div class='nv-bubble' style='background:#4ECDC4;width:90px;height:90px;font-size:1.2rem'>{reg_yoy}</div>", unsafe_allow_html=True)
                        st.caption('2025 YTD vs 2024 (% change)')
            else:
                st.info("No regional APP rows for this region.")
        else:
            st.info("Regional APP CSV not loaded or region not found.")

    # Same category
    with c_cat:
        if status_val and not vol_status_year.empty:
            cat = vol_status_year[vol_status_year.get("statut").astype(str).str.strip() == str(status_val)]
            if not cat.empty:
                s1, s2 = st.columns([4, 1])
                with s1:
                    dfp = cat.sort_values("annee")
                    fig_c = px.bar(
                        dfp.assign(annee=lambda d: d["annee"].astype(int).astype(str)),
                        x="annee", y="n", title="Same category",
                        color_discrete_sequence=["#A78BFA"],
                    )
                    fig_c.update_layout(height=260, plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)')
                    fig_c.update_traces(hovertemplate='Year: %{x}<br>Procedures: %{y:,}<extra></extra>')
                    st.plotly_chart(fig_c, use_container_width=True)
                with s2:
                    # Get YoY change from trend data
                    status_yoy = "—"
                    try:
                        if not trend_status.empty and "statut" in trend_status.columns and "diff_pct" in trend_status.columns:
                            status_trend = trend_status[trend_status["statut"].astype(str).str.strip() == str(status_val)]
                            if not status_trend.empty:
                                diff_val = status_trend.iloc[0]["diff_pct"]
                                if pd.notna(diff_val):
                                    status_yoy = f"{float(diff_val):+.1f}%"
                    except Exception:
                        pass
                    if status_yoy != "—":
                        st.markdown(f"<div class='nv-bubble' style='background:#A78BFA;width:90px;height:90px;font-size:1.2rem'>{status_yoy}</div>", unsafe_allow_html=True)
                        st.caption('2025 YTD vs 2024 (% change)')
            else:
                st.info("No same-category APP rows for this status.")
        else:
            st.info("Same-category APP CSV not loaded or status not found.")

    st.markdown("---")

    # Lollipop — Number of procedures per hospital (2024), with scope toggle
    st.markdown("#### Number of procedures per hospital — lollipop (2024)")
    scope = st.radio(
        "Compare against",
        ["National", "Regional", "Same status"],
        horizontal=True,
        index=0,
        key=f"lollipop_scope_{hospital_id}"
    )

    # Choose target year: 2024 if present else latest ≤ 2024
    year_col = "annee" if "annee" in vol_hop_year.columns else ("year" if "year" in vol_hop_year.columns else None)
    if year_col is None:
        st.info("Hospital totals file missing year column.")
    else:
        years_available = pd.to_numeric(vol_hop_year[year_col], errors="coerce").dropna().astype(int)
        target_year = 2024 if (years_available == 2024).any() else (years_available[years_available <= 2024].max() if not years_available[years_available <= 2024].empty else years_available.max())

        # Build id filters for scopes from REV mapping
        all_ids = vol_hop_year.get("finessGeoDP").astype(str).unique().tolist() if "finessGeoDP" in vol_hop_year.columns else []
        reg_ids = []
        status_ids = []
        try:
            if not rev_hop_12m.empty and "finessGeoDP" in rev_hop_12m.columns:
                if region_name:
                    reg_ids = rev_hop_12m[rev_hop_12m.get("lib_reg").astype(str) == str(region_name)]["finessGeoDP"].astype(str).unique().tolist()
                if status_val:
                    status_ids = rev_hop_12m[rev_hop_12m.get("statut").astype(str) == str(status_val)]["finessGeoDP"].astype(str).unique().tolist()
        except Exception:
            reg_ids = []
            status_ids = []

        if scope == "Regional":
            ids_scope = reg_ids
        elif scope == "Same status":
            ids_scope = status_ids
        else:
            ids_scope = all_ids

        # Build per-hospital totals for target year
        df_year = vol_hop_year[pd.to_numeric(vol_hop_year[year_col], errors="coerce") == target_year].copy()
        if ids_scope:
            df_year = df_year[df_year.get("finessGeoDP").astype(str).isin([str(i) for i in ids_scope])]
        if df_year.empty or "n" not in df_year.columns:
            st.info("No data to build lollipop for this scope/year.")
        else:
            totals = (df_year.groupby("finessGeoDP", as_index=False)["n"].sum().rename(columns={"n":"total"}))
            # Sort ascending and produce x positions
            totals = totals.sort_values("total").reset_index(drop=True)
            x_pos = list(range(1, len(totals) + 1))
            # Colors: highlight selected hospital
            colors = ["#FF8C00" if str(h) == str(hospital_id) else "#5DA5DA" for h in totals["finessGeoDP"].astype(str)]

            fig_ll = go.Figure()
            # Stems
            for xi, yi, col in zip(x_pos, totals["total"], colors):
                fig_ll.add_trace(go.Scatter(x=[xi, xi], y=[0, yi], mode="lines", line=dict(color=col, width=2), showlegend=False, hoverinfo='skip'))
            # Heads (markers)
            fig_ll.add_trace(go.Scatter(
                x=x_pos,
                y=totals["total"],
                mode="markers",
                marker=dict(color=colors, size=8),
                showlegend=False,
                hovertemplate='Hospital: %{x}<br>Procedures: %{y:,}<extra></extra>'
            ))
            # Legend via dummy markers
            fig_ll.add_trace(go.Scatter(x=[None], y=[None], mode='markers', marker=dict(color='#FF8C00', size=8), name='Selected hospital'))
            fig_ll.add_trace(go.Scatter(x=[None], y=[None], mode='markers', marker=dict(color='#5DA5DA', size=8), name='Other hospitals'))

            fig_ll.update_layout(
                height=360,
                xaxis_title='Hospitals',
                yaxis_title='Number of procedures',
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)',
                xaxis=dict(showticklabels=False)
            )
            st.plotly_chart(fig_ll, use_container_width=True)
            st.caption(f"Scope: {scope}; Year: {int(target_year)}")

    # Monthly procedure volume trends — hospital line + 12‑month average
    st.markdown("---")
    st.markdown("#### Monthly Procedure Volume Trends")
    vol_hop_month = _read_csv("TAB_VOL_HOP_MONTH.csv")
    if vol_hop_month is None or vol_hop_month.empty:
        st.info("Monthly CSV (TAB_VOL_HOP_MONTH.csv) not found or empty.")
    else:
        try:
            dfm = vol_hop_month.copy()
            # Normalize columns
            if "finessGeoDP" in dfm.columns:
                dfm["finessGeoDP"] = dfm["finessGeoDP"].astype(str).str.strip()
            # Determine year/month columns
            ycol = "annee" if "annee" in dfm.columns else ("year" if "year" in dfm.columns else None)
            mcol = "mois" if "mois" in dfm.columns else ("month" if "month" in dfm.columns else None)
            # Value column detection
            vcol = None
            for c in ["n", "TOT_month", "TOT_month_tcn", "TOT", "value"]:
                if c in dfm.columns:
                    vcol = c
                    break
            if ycol is None or mcol is None or vcol is None:
                st.info("Monthly CSV is missing required columns (year/month/value).")
            else:
                # Filter to hospital
                dfm = dfm[dfm["finessGeoDP"].astype(str) == str(hospital_id)].copy()
                if dfm.empty:
                    st.info("No monthly rows for this hospital.")
                else:
                    dfm[ycol] = pd.to_numeric(dfm[ycol], errors="coerce")
                    dfm[mcol] = pd.to_numeric(dfm[mcol], errors="coerce")
                    dfm[vcol] = pd.to_numeric(dfm[vcol], errors="coerce").fillna(0)
                    dfm = dfm.dropna(subset=[ycol, mcol])
                    # Build date column and sort
                    dfm["date"] = pd.to_datetime(dfm[ycol].astype(int).astype(str) + "-" + dfm[mcol].astype(int).astype(str).str.zfill(2) + "-01", errors="coerce")
                    dfm = dfm.dropna(subset=["date"]).sort_values("date")
                    if dfm.empty:
                        st.info("No valid monthly dates after cleaning.")
                    else:
                        # 12‑month rolling average
                        dfm["rolling12"] = dfm[vcol].rolling(window=12, min_periods=1).mean()
                        fig_month = go.Figure()
                        fig_month.add_trace(go.Scatter(
                            x=dfm["date"], y=dfm[vcol], mode="lines+markers",
                            name="Monthly Total", line=dict(color="#1f77b4", width=2), marker=dict(size=4),
                            hovertemplate='%{x|%b %Y}<br>Procedures: %{y:.0f}<extra></extra>'
                        ))
                        fig_month.add_trace(go.Scatter(
                            x=dfm["date"], y=dfm["rolling12"], mode="lines",
                            name="12‑month Average", line=dict(color="#ff7f0e", width=3, dash="dash"),
                            hovertemplate='%{x|%b %Y}<br>12‑mo Avg: %{y:.1f}<extra></extra>'
                        ))
                        fig_month.update_layout(
                            height=380, xaxis_title="Month", yaxis_title="Number of procedures",
                            hovermode='x unified', plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)'
                        )
                        st.plotly_chart(fig_month, use_container_width=True)
        except Exception as _e:
            st.info(f"Could not render monthly trend: {_e}")

    # --- Surgical approach (stacked bars % over years) ---
    st.markdown("#### Surgical approach")

    APPROACH_LABELS_BARS = { 'COE': 'Coelioscopy', 'ROB': 'Robotic', 'LAP': 'Open Surgery' }
    # Default approach colors for hospital chart
    APPROACH_COLORS_DEFAULT = { 'Coelioscopy': '#2E86AB', 'Robotic': '#F7931E', 'Open Surgery': '#A23B72' }
    # Theme-based colors matching procedures per year: National (#E9A23B), Regional (#4ECDC4), Same category (#A78BFA)
    # Create variations of theme colors for the three approaches
    APPROACH_COLORS_NATIONAL = { 'Coelioscopy': '#FFB84D', 'Robotic': '#E9A23B', 'Open Surgery': '#CC7A00' }
    APPROACH_COLORS_REGIONAL = { 'Coelioscopy': '#6EDDD4', 'Robotic': '#4ECDC4', 'Open Surgery': '#2E9D95' }
    APPROACH_COLORS_CATEGORY = { 'Coelioscopy': '#C4A8FF', 'Robotic': '#A78BFA', 'Open Surgery': '#8B6FD4' }

    def _approach_bars(df: pd.DataFrame, title: str, filters: dict | None = None, height: int = 260, color_map: dict | None = None):
        if df is None or df.empty:
            st.info(f"No data for {title}.")
            return
        d = df.copy()
        if filters:
            for k, v in filters.items():
                if k in d.columns and v is not None and str(v):
                    d = d[d[k].astype(str).str.strip() == str(v)]
        if d.empty:
            st.info(f"No data for {title}.")
            return
        if 'annee' not in d.columns or 'vda' not in d.columns:
            st.info(f"Missing columns for {title}.")
            return
        d['n'] = pd.to_numeric(d.get('n', 0), errors='coerce').fillna(0)
        agg = d.groupby(['annee','vda'], as_index=False)['n'].sum()
        # Map labels and compute shares per year
        agg['Approach'] = agg['vda'].astype(str).str.upper().map(APPROACH_LABELS_BARS).fillna(agg['vda'])
        totals = agg.groupby('annee', as_index=False)['n'].sum().rename(columns={'n':'tot'})
        merged = agg.merge(totals, on='annee', how='left')
        merged = merged[merged['tot'] > 0]
        merged['Share'] = merged['n'] / merged['tot'] * 100.0
        merged['annee'] = pd.to_numeric(merged['annee'], errors='coerce').astype('Int64')
        merged = merged.dropna(subset=['annee'])
        if merged.empty:
            st.info(f"No data for {title}.")
            return
        colors = color_map if color_map else APPROACH_COLORS_DEFAULT
        fig = px.bar(
            merged.sort_values('annee').assign(annee=lambda x: x['annee'].astype(int).astype(str)),
            x='annee', y='Share', color='Approach', barmode='stack',
            color_discrete_map=colors
        )
        fig.update_layout(height=height, plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', title=title)
        fig.update_traces(hovertemplate='%{x}<br>%{fullData.name}: %{y:.0f}%<extra></extra>')
        fig.update_yaxes(range=[0,100])
        st.plotly_chart(fig, use_container_width=True)

    # Hospital big chart
    _sp_l, _center, _sp_r = st.columns([1, 1.6, 1])
    with _center:
        _approach_bars(app_hop_year, 'Hospital', { 'finessGeoDP': str(hospital_id) }, height=300, color_map=APPROACH_COLORS_DEFAULT)
    # Three small charts: national, regional, same category (with theme colors matching procedures per year)
    c_nat, c_reg, c_cat = st.columns(3)
    with c_nat:
        _approach_bars(app_nat_year, 'National', None, color_map=APPROACH_COLORS_NATIONAL)
    with c_reg:
        _approach_bars(app_reg_year, 'Regional', { 'lib_reg': region_name } if region_name else None, color_map=APPROACH_COLORS_REGIONAL)
    with c_cat:
        _approach_bars(app_status_year, 'Same category', { 'statut': status_val } if status_val else None, color_map=APPROACH_COLORS_CATEGORY)

    # --- Robot share (%) — last 12 months scatter ---
    st.markdown("---")
    st.markdown("#### Robot share")
    scope_rob = st.radio(
        "Compare against",
        ["National", "Regional", "Same status"],
        horizontal=True,
        index=0,
        key=f"rob_scatter_scope_{hospital_id}"
    )

    # Load robotic data from TAB_ROB_HOP_12M.csv
    rob_data = _read_csv("TAB_ROB_HOP_12M.csv")
    if rob_data is None or rob_data.empty or "TOT" not in rob_data.columns or "PCT_app" not in rob_data.columns:
        st.info("No robotic dataset available for scatter.")
    else:
        d = rob_data.copy()
        d["finessGeoDP"] = d.get("finessGeoDP").astype(str)
        d["TOT"] = pd.to_numeric(d.get("TOT", 0), errors="coerce").fillna(0)
        d["PCT_app"] = pd.to_numeric(d.get("PCT_app", 0), errors="coerce").fillna(0)

        # Scope filtering - rob_data already contains lib_reg and statut columns
        if scope_rob == "Regional":
            if region_name and "lib_reg" in d.columns:
                d_sc = d[d.get("lib_reg").astype(str).str.strip() == str(region_name)].copy()
            else:
                d_sc = pd.DataFrame()
        elif scope_rob == "Same status":
            if status_val and "statut" in d.columns:
                d_sc = d[d.get("statut").astype(str).str.strip() == str(status_val)].copy()
                d_sc = d[d.get("statut").astype(str).str.strip() == str(status_val)].copy()
            else:
                d_sc = pd.DataFrame()
        else:
            d_sc = d.copy()
        if d_sc.empty:
            st.info("No data to build robot share scatter for this scope.")
        else:
            sel = d_sc[d_sc["finessGeoDP"].astype(str) == str(hospital_id)]
            oth = d_sc[d_sc["finessGeoDP"].astype(str) != str(hospital_id)]
            fig_rob = go.Figure()
            # Others
            if not oth.empty:
                fig_rob.add_trace(go.Scatter(
                    x=oth["TOT"], y=oth["PCT_app"], mode="markers",
                    marker=dict(color="#60a5fa", size=6, opacity=0.75), name="Other hospitals",
                    hovertemplate='Procedures: %{x:.0f}<br>Robot share: %{y:.1f}%<extra></extra>'
                ))
            # Selected
            if not sel.empty:
                fig_rob.add_trace(go.Scatter(
                    x=sel["TOT"], y=sel["PCT_app"], mode="markers",
                    marker=dict(color="#FF8C00", size=12, line=dict(color="white", width=1)), name="Selected hospital",
                    hovertemplate='Procedures: %{x:.0f}<br>Robot share: %{y:.1f}%<extra></extra>'
                ))
            fig_rob.update_layout(
                height=420,
                xaxis_title="Number of procedure per year (any approach)", yaxis_title="Robot share (%)",
                xaxis=dict(range=[0, None]), yaxis=dict(range=[0, 100]),
                plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)'
            )
            st.plotly_chart(fig_rob, use_container_width=True)
            st.caption("Based on robotic procedures last 12 months (TAB_ROB_HOP_12M)")

    # --- Procedure casemix (TCN) — hospital centered, peers below; toggle 12M ---
    st.markdown("---")
    st.markdown("#### Procedure casemix")
    use_12m = st.toggle("Show last 12 months", value=False, key=f"tcn_12m_{hospital_id}")

    # Load TCN datasets depending on toggle
    tcn_hop = _read_csv("TAB_TCN_HOP_12M.csv" if use_12m else "TAB_TCN_HOP_YEAR.csv")
    tcn_nat = _read_csv("TAB_TCN_NATL_12M.csv" if use_12m else "TAB_TCN_NATL_YEAR.csv")
    tcn_reg = _read_csv("TAB_TCN_REG_12M.csv" if use_12m else "TAB_TCN_REG_YEAR.csv")
    tcn_status = _read_csv("TAB_TCN_STATUS_12M.csv" if use_12m else "TAB_TCN_STATUS_YEAR.csv")

    PROC_LABELS = {
        'SLE': 'Sleeve',
        'BPG': 'Gastric Bypass',
        'ANN': 'Other',
        'DBP': 'Other',
        'GVC': 'Other',
        'NDD': 'Other'
    }
    # Default procedure colors for hospital chart
    PROC_COLORS_DEFAULT = {
        'Sleeve': '#1f77b4',
        'Gastric Bypass': '#ff7f0e',
        'Other': '#2ca02c'
    }
    # Theme-based colors matching procedures per year: National (#E9A23B), Regional (#4ECDC4), Same category (#A78BFA)
    # Create variations of theme colors for the three procedure types
    PROC_COLORS_NATIONAL = {
        'Sleeve': '#FFB84D',
        'Gastric Bypass': '#E9A23B',
        'Other': '#CC7A00'
    }
    PROC_COLORS_REGIONAL = {
        'Sleeve': '#6EDDD4',
        'Gastric Bypass': '#4ECDC4',
        'Other': '#2E9D95'
    }
    PROC_COLORS_CATEGORY = {
        'Sleeve': '#C4A8FF',
        'Gastric Bypass': '#A78BFA',
        'Other': '#8B6FD4'
    }

    def _tcn_pie(df: pd.DataFrame, title: str, filters: dict | None = None, color_map: dict | None = None):
        if df is None or df.empty:
            st.info(f"No data for {title}.")
            return
        d = df.copy()
        if filters:
            for k, v in filters.items():
                if k in d.columns and v is not None and str(v):
                    d = d[d[k].astype(str).str.strip() == str(v)]
        if d.empty:
            st.info(f"No data for {title}.")
            return
        # Choose latest year if YEAR file
        if not use_12m and ('annee' in d.columns or 'year' in d.columns):
            ycol = 'annee' if 'annee' in d.columns else 'year'
            d[ycol] = pd.to_numeric(d[ycol], errors='coerce')
            maxy = int(d[ycol].dropna().max()) if not d[ycol].dropna().empty else None
            if maxy is not None:
                d = d[d[ycol] == maxy]
        # Aggregate counts by procedure
        if 'n' not in d.columns and 'TOT' in d.columns:
            d['n'] = pd.to_numeric(d['TOT'], errors='coerce')
        d['n'] = pd.to_numeric(d.get('n', 0), errors='coerce').fillna(0)
        if 'baria_t' not in d.columns:
            st.info(f"No procedure type column for {title}.")
            return
        grp = d.groupby('baria_t', as_index=False)['n'].sum()
        # Map to three buckets
        totals = {'Sleeve': 0.0, 'Gastric Bypass': 0.0, 'Other': 0.0}
        for _, r in grp.iterrows():
            code = str(r['baria_t']).upper().strip()
            label = PROC_LABELS.get(code, 'Other')
            totals[label] += float(r['n'])
        vals = {k: v for k, v in totals.items() if v > 0}
        if not vals:
            st.info(f"No data for {title}.")
            return
        dfp = pd.DataFrame({'Procedure': list(vals.keys()), 'Count': list(vals.values())})
        # Determine smallest slice to place label outside for better legibility
        try:
            min_idx = int(dfp['Count'].astype(float).idxmin())
        except Exception:
            min_idx = 0
        positions = ['inside'] * len(dfp)
        if 0 <= min_idx < len(positions):
            positions[min_idx] = 'outside'
        colors = color_map if color_map else PROC_COLORS_DEFAULT
        figp = px.pie(dfp, values='Count', names='Procedure', hole=0.55, color='Procedure', color_discrete_map=colors)
        figp.update_traces(textposition=positions, textinfo='percent+label', insidetextfont=dict(size=12), outsidetextfont=dict(size=16))
        figp.update_layout(title=title, height=390, showlegend=False, plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)')
        st.plotly_chart(figp, use_container_width=True)

    # Layout: hospital centered (large), then three small pies below
    _sp_l, _center, _sp_r = st.columns([1, 1.2, 1])
    with _center:
        _tcn_pie(tcn_hop, "Hospital", { 'finessGeoDP': str(hospital_id) }, color_map=PROC_COLORS_DEFAULT)

    c_nat2, c_reg2, c_cat2 = st.columns(3)
    with c_nat2:
        _tcn_pie(tcn_nat, "National", None, color_map=PROC_COLORS_NATIONAL)
    with c_reg2:
        _tcn_pie(tcn_reg, f"Regional", { 'lib_reg': region_name }, color_map=PROC_COLORS_REGIONAL)
    with c_cat2:
        _tcn_pie(tcn_status, "Same category", { 'statut': status_val }, color_map=PROC_COLORS_CATEGORY)

    # --- Sleeve & Bypass share (%) — last 12 months scatter ---
    st.markdown("---")
    st.markdown("#### Sleeve & Bypass share (%) — last 12 months")
    scope_sc = st.radio(
        "Compare against",
        ["National", "Regional", "Same status"],
        horizontal=True,
        index=0,
        key=f"tcn_scatter_scope_{hospital_id}"
    )

    # Build per-hospital SLE/BPG shares from last 12 months
    tcn12 = _read_csv("TAB_TCN_HOP_12M.csv")
    if tcn12 is None or tcn12.empty or "baria_t" not in tcn12.columns:
        st.info("No TCN 12-month dataset available for scatter.")
    else:
        d = tcn12.copy()
        d["finessGeoDP"] = d.get("finessGeoDP").astype(str)
        d["n"] = pd.to_numeric(d.get("n", 0), errors="coerce").fillna(0)
        # Pivot to SLE/BPG columns per hospital
        piv = d[d["baria_t"].isin(["SLE","BPG"])].pivot_table(index="finessGeoDP", columns="baria_t", values="n", aggfunc="sum").fillna(0)
        piv = piv.reset_index().rename_axis(None, axis=1)
        if "SLE" not in piv.columns:
            piv["SLE"] = 0
        if "BPG" not in piv.columns:
            piv["BPG"] = 0
        piv["den"] = piv["SLE"] + piv["BPG"]
        piv = piv[piv["den"] > 0]
        piv["sleeve_pct"] = piv["SLE"] / piv["den"] * 100.0
        piv["bypass_pct"] = piv["BPG"] / piv["den"] * 100.0

        # Scope filtering via REV mapping
        ids_natl = piv["finessGeoDP"].astype(str).unique().tolist()
        ids_reg = []
        ids_status = []
        try:
            if not rev_hop_12m.empty and "finessGeoDP" in rev_hop_12m.columns:
                if region_name:
                    ids_reg = rev_hop_12m[rev_hop_12m.get("lib_reg").astype(str) == str(region_name)]["finessGeoDP"].astype(str).unique().tolist()
                if status_val:
                    ids_status = rev_hop_12m[rev_hop_12m.get("statut").astype(str) == str(status_val)]["finessGeoDP"].astype(str).unique().tolist()
        except Exception:
            ids_reg = []
            ids_status = []

        if scope_sc == "Regional":
            ids_scope = ids_reg
        elif scope_sc == "Same status":
            ids_scope = ids_status
        else:
            ids_scope = ids_natl

        if ids_scope:
            piv_sc = piv[piv["finessGeoDP"].astype(str).isin([str(i) for i in ids_scope])].copy()
        else:
            piv_sc = piv.copy()

        if piv_sc.empty:
            st.info("No data to build sleeve/bypass scatter for this scope.")
        else:
            sel = piv_sc[piv_sc["finessGeoDP"].astype(str) == str(hospital_id)]
            oth = piv_sc[piv_sc["finessGeoDP"].astype(str) != str(hospital_id)]
            fig_sc = go.Figure()
            # Others
            fig_sc.add_trace(go.Scatter(
                x=oth["sleeve_pct"], y=oth["bypass_pct"], mode="markers",
                marker=dict(color="#1f77b4", size=6, opacity=0.75), name="Other hospitals",
                hovertemplate='Sleeve: %{x:.0f}%<br>Bypass: %{y:.0f}%<extra></extra>'
            ))
            # Selected
            if not sel.empty:
                fig_sc.add_trace(go.Scatter(
                    x=sel["sleeve_pct"], y=sel["bypass_pct"], mode="markers",
                    marker=dict(color="#FF8C00", size=12, line=dict(color="white", width=1)), name="Selected hospital",
                    hovertemplate='Sleeve: %{x:.0f}%<br>Bypass: %{y:.0f}%<extra></extra>'
                ))
            fig_sc.update_layout(
                height=420,
                xaxis_title="Sleeve rate (%)", yaxis_title="Bypass rate (%)",
                xaxis=dict(range=[0,100]), yaxis=dict(range=[0,100]),
                plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)'
            )
            st.plotly_chart(fig_sc, use_container_width=True)
            st.caption("Based on TCN last 12 months (HOP_12M)")

    # --- Revisional rate ---
    st.markdown("---")
    st.markdown("#### Revisional rate")
    use_12m_rev = st.toggle("Show last 12 months", value=False, key=f"rev_12m_{hospital_id}")

    # Load revisional data based on toggle
    rev_hop = _read_csv("TAB_REV_HOP_12M.csv" if use_12m_rev else "TAB_REV_HOP.csv")
    rev_natl = _read_csv("TAB_REV_NATL_12M.csv" if use_12m_rev else "TAB_REV_NATL.csv")
    rev_reg = _read_csv("TAB_REV_REG_12M.csv" if use_12m_rev else "TAB_REV_REG.csv")
    rev_status = _read_csv("TAB_REV_STATUS_12M.csv" if use_12m_rev else "TAB_REV_STATUS.csv")

    # Color scheme matching procedures per year
    REV_COLORS = {
        "hospital": "#1f4e79",  # Dark teal/blue for hospital
        "national": "#E9A23B",  # Orange
        "regional": "#4ECDC4",  # Turquoise/teal
        "status": "#A78BFA"     # Purple
    }

    # Bubble display: Hospital, National, Regional, Same category
    col_hosp, col_nat, col_reg, col_cat = st.columns(4)
    
    # Hospital bubble
    with col_hosp:
        hosp_rev = "—"
        try:
            if not rev_hop.empty and "finessGeoDP" in rev_hop.columns and "PCT_rev" in rev_hop.columns:
                hosp_row = rev_hop[rev_hop["finessGeoDP"].astype(str) == str(hospital_id)]
                if not hosp_row.empty:
                    rev_val = hosp_row.iloc[0]["PCT_rev"]
                    if pd.notna(rev_val):
                        hosp_rev = f"{float(rev_val):.0f}%"
        except Exception:
            pass
        st.markdown(f"<div class='nv-bubble' style='background:{REV_COLORS['hospital']};width:120px;height:120px;font-size:1.8rem'>{hosp_rev}</div>", unsafe_allow_html=True)
        st.caption("Hospital")

    # National bubble
    with col_nat:
        nat_rev = "—"
        try:
            if not rev_natl.empty and "PCT_rev" in rev_natl.columns:
                rev_val = rev_natl.iloc[0]["PCT_rev"]
                if pd.notna(rev_val):
                    nat_rev = f"{float(rev_val):.0f}%"
        except Exception:
            pass
        st.markdown(f"<div class='nv-bubble' style='background:{REV_COLORS['national']};width:120px;height:120px;font-size:1.8rem'>{nat_rev}</div>", unsafe_allow_html=True)
        st.caption("National")

    # Regional bubble
    with col_reg:
        reg_rev = "—"
        try:
            if region_name and not rev_reg.empty and "lib_reg" in rev_reg.columns and "PCT_rev" in rev_reg.columns:
                reg_row = rev_reg[rev_reg["lib_reg"].astype(str).str.strip() == str(region_name)]
                if not reg_row.empty:
                    rev_val = reg_row.iloc[0]["PCT_rev"]
                    if pd.notna(rev_val):
                        reg_rev = f"{float(rev_val):.0f}%"
        except Exception:
            pass
        st.markdown(f"<div class='nv-bubble' style='background:{REV_COLORS['regional']};width:120px;height:120px;font-size:1.8rem'>{reg_rev}</div>", unsafe_allow_html=True)
        st.caption("Regional")

    # Same category bubble
    with col_cat:
        status_rev = "—"
        try:
            if status_val and not rev_status.empty and "statut" in rev_status.columns and "PCT_rev" in rev_status.columns:
                status_row = rev_status[rev_status["statut"].astype(str).str.strip() == str(status_val)]
                if not status_row.empty:
                    rev_val = status_row.iloc[0]["PCT_rev"]
                    if pd.notna(rev_val):
                        status_rev = f"{float(rev_val):.0f}%"
        except Exception:
            pass
        st.markdown(f"<div class='nv-bubble' style='background:{REV_COLORS['status']};width:120px;height:120px;font-size:1.8rem'>{status_rev}</div>", unsafe_allow_html=True)
        st.caption("Same category Hospitals")

    # Bar chart: Revisional rate per hospital
    st.markdown("---")
    st.markdown("#### Revisional rate")
    scope_rev = st.radio(
        "Compare against",
        ["National", "Regional", "Same status"],
        horizontal=True,
        index=0,
        key=f"rev_bar_scope_{hospital_id}"
    )

    if rev_hop is None or rev_hop.empty or "PCT_rev" not in rev_hop.columns:
        st.info("No revisional dataset available.")
    else:
        d = rev_hop.copy()
        d["finessGeoDP"] = d.get("finessGeoDP").astype(str)
        d["PCT_rev"] = pd.to_numeric(d.get("PCT_rev", 0), errors="coerce").fillna(0)

        # Scope filtering
        if scope_rev == "Regional":
            if region_name and "lib_reg" in d.columns:
                d_sc = d[d.get("lib_reg").astype(str).str.strip() == str(region_name)].copy()
            else:
                d_sc = pd.DataFrame()
        elif scope_rev == "Same status":
            if status_val and "statut" in d.columns:
                d_sc = d[d.get("statut").astype(str).str.strip() == str(status_val)].copy()
            else:
                d_sc = pd.DataFrame()
        else:
            d_sc = d.copy()

        if d_sc.empty:
            st.info("No data to build revisional rate bar chart for this scope.")
        else:
            # Sort by revisional rate (ascending)
            d_sc = d_sc.sort_values("PCT_rev").reset_index(drop=True)
            x_pos = list(range(1, len(d_sc) + 1))

            fig_rev = go.Figure()
            
            # Create separate lists for selected and other hospitals
            sel_x, sel_y = [], []
            oth_x, oth_y = [], []
            
            for i, (idx, row) in enumerate(d_sc.iterrows()):
                x_val = x_pos[i]
                y_val = row["PCT_rev"]
                if str(row["finessGeoDP"]) == str(hospital_id):
                    sel_x.append(x_val)
                    sel_y.append(y_val)
                else:
                    oth_x.append(x_val)
                    oth_y.append(y_val)
            
            # Other hospitals bars
            if oth_x:
                fig_rev.add_trace(go.Bar(
                    x=oth_x,
                    y=oth_y,
                    marker=dict(color='#A78BFA'),
                    name='Other hospitals',
                    hovertemplate='Hospital: %{x}<br>Revisional rate: %{y:.1f}%<extra></extra>'
                ))
                # Markers on top for other hospitals
                fig_rev.add_trace(go.Scatter(
                    x=oth_x,
                    y=oth_y,
                    mode="markers",
                    marker=dict(color='#A78BFA', size=6),
                    showlegend=False,
                    hoverinfo='skip'
                ))
            
            # Selected hospital bar
            if sel_x:
                fig_rev.add_trace(go.Bar(
                    x=sel_x,
                    y=sel_y,
                    marker=dict(color='#00FF00'),
                    name='Selected hospital',
                    hovertemplate='Hospital: %{x}<br>Revisional rate: %{y:.1f}%<extra></extra>'
                ))
                # Marker on top for selected hospital
                fig_rev.add_trace(go.Scatter(
                    x=sel_x,
                    y=sel_y,
                    mode="markers",
                    marker=dict(color='#00FF00', size=6),
                    showlegend=False,
                    hoverinfo='skip'
                ))

            fig_rev.update_layout(
                height=420,
                xaxis_title="Hospitals",
                yaxis_title="Revisional rate (%)",
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)',
                xaxis=dict(showticklabels=False),
                yaxis=dict(range=[0, 100])
            )
            st.plotly_chart(fig_rev, use_container_width=True)
            st.caption(f"Scope: {scope_rev}; {'Last 12 months' if use_12m_rev else 'Full period (2021-2025)'}")
