import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

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
        # Simple YoY bubble 2025 vs 2024 using vol_hop_year if available
        yoy_text = "—"
        try:
            h = vol_hop_year[vol_hop_year["finessGeoDP"] == str(hospital_id)]
            if not h.empty:
                by_year = h.groupby("annee" if "annee" in h.columns else "year", as_index=False)["n" if "n" in h.columns else "TOT"].sum()
                y24 = float(by_year[by_year.iloc[:, 0] == 2024].iloc[0, 1]) if (by_year.iloc[:, 0] == 2024).any() else None
                y25 = float(by_year[by_year.iloc[:, 0] == 2025].iloc[0, 1]) if (by_year.iloc[:, 0] == 2025).any() else None
                if y24 and y25 is not None and y24 > 0:
                    yoy_text = f"{((y25 / y24 - 1.0) * 100.0):+.0f}%"
        except Exception:
            pass
        st.markdown(f"<div class='nv-bubble teal' style='width:110px;height:110px;font-size:1.6rem'>{yoy_text}</div>", unsafe_allow_html=True)
        st.caption('2025 YTD vs 2024 (based on CSV totals)')

    # National / Regional / Same-category — Procedures per year directly from VOL CSVs
    def _diff_vs_hospital_label(group_df: pd.DataFrame, hosp_df: pd.DataFrame, preferred_year: int = 2024) -> str | None:
        try:
            if group_df is None or group_df.empty or hosp_df is None or hosp_df.empty:
                return None
            # Determine available years
            gy = pd.to_numeric((group_df.get("annee") if "annee" in group_df.columns else group_df.get("year")), errors="coerce").dropna().astype(int)
            hy = pd.to_numeric((hosp_df.get("annee") if "annee" in hosp_df.columns else hosp_df.get("year")), errors="coerce").dropna().astype(int)
            common = sorted(set(gy.tolist()).intersection(set(hy.tolist())))
            if not common:
                return None
            year_candidates = [y for y in common if y <= preferred_year]
            if not year_candidates:
                return None
            year = year_candidates[-1]
            gv = float(group_df[(group_df.get("annee", group_df.get("year")) == year)]["n"].sum())
            hv = float(hosp_df[(hosp_df.get("annee", hosp_df.get("year")) == year)]["n"].sum())
            if gv <= 0:
                return None
            diff = (hv / gv - 1.0) * 100.0
            return f"{diff:+.0f}%"
        except Exception:
            return None

    # Median-based comparison helpers (preferred): Hospital vs group median (per-hospital), 2024
    def _hospital_vs_median_labels(vol_hop_df: pd.DataFrame, rev_df: pd.DataFrame, hid: str, region_val: str | None, status_val: str | None, year: int = 2024) -> dict[str, str | None]:
        out = {"national": None, "regional": None, "status": None}
        try:
            if vol_hop_df is None or vol_hop_df.empty:
                return out
            v = vol_hop_df.copy()
            year_col = "annee" if "annee" in v.columns else ("year" if "year" in v.columns else None)
            if year_col is None:
                return out
            v = v[pd.to_numeric(v[year_col], errors="coerce") == year]
            if v.empty or "finessGeoDP" not in v.columns or "n" not in v.columns:
                return out
            # Sum per hospital for the year
            v = v.groupby("finessGeoDP", as_index=False)["n"].sum()
            # Attach region/status mapping
            if rev_df is not None and not rev_df.empty:
                m = rev_df[[c for c in ["finessGeoDP","lib_reg","statut","region","status"] if c in rev_df.columns]].copy()
                m["finessGeoDP"] = m["finessGeoDP"].astype(str)
                # Prefer lib_reg/statut; fallback to region/status if needed
                if "lib_reg" not in m.columns and "region" in m.columns:
                    m["lib_reg"] = m["region"].astype(str)
                if "statut" not in m.columns and "status" in m.columns:
                    m["statut"] = m["status"].astype(str)
                m = m.drop_duplicates(subset=["finessGeoDP"])  # one row per hospital
                v = v.merge(m[["finessGeoDP","lib_reg","statut"]], on="finessGeoDP", how="left")
            # Hospital value
            try:
                hv = float(v[v["finessGeoDP"].astype(str) == str(hid)]["n"].iloc[0])
            except Exception:
                hv = None
            if hv is None or hv <= 0:
                return out
            # National median
            try:
                nat_med = float(v["n"].median())
                out["national"] = f"{((hv / nat_med - 1.0) * 100.0):+.0f}%" if nat_med and nat_med > 0 else None
            except Exception:
                out["national"] = None
            # Regional median (same lib_reg as selected hospital)
            try:
                if region_val:
                    reg_med_series = v[v.get("lib_reg").astype(str) == str(region_val)]["n"]
                    if not reg_med_series.empty:
                        reg_med = float(reg_med_series.median())
                        out["regional"] = f"{((hv / reg_med - 1.0) * 100.0):+.0f}%" if reg_med and reg_med > 0 else None
            except Exception:
                out["regional"] = None
            # Status median (same statut)
            try:
                if status_val:
                    cat_med_series = v[v.get("statut").astype(str) == str(status_val)]["n"]
                    if not cat_med_series.empty:
                        cat_med = float(cat_med_series.median())
                        out["status"] = f"{((hv / cat_med - 1.0) * 100.0):+.0f}%" if cat_med and cat_med > 0 else None
            except Exception:
                out["status"] = None
        except Exception:
            pass
        return out

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
    # Compute median-based labels once
    median_labels = _hospital_vs_median_labels(vol_hop_year, rev_hop_12m, str(hospital_id), region_name, status_val, year=2024)

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
                lbl = median_labels.get("national")
                if lbl:
                    st.markdown(f"<div class='nv-bubble' style='background:#E9A23B;width:90px;height:90px;font-size:1.2rem'>{lbl}</div>", unsafe_allow_html=True)
                    st.caption('Hospital vs National median (2024)')
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
                    lbl = median_labels.get("regional")
                    if lbl:
                        st.markdown(f"<div class='nv-bubble' style='background:#4ECDC4;width:90px;height:90px;font-size:1.2rem'>{lbl}</div>", unsafe_allow_html=True)
                        st.caption('Hospital vs Regional median (2024)')
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
                    lbl = median_labels.get("status")
                    if lbl:
                        st.markdown(f"<div class='nv-bubble' style='background:#A78BFA;width:90px;height:90px;font-size:1.2rem'>{lbl}</div>", unsafe_allow_html=True)
                        st.caption('Hospital vs Same category median (2024)')
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

    # Row 2: Approaches pies
    st.markdown("#### Surgical Approaches (Hospital / National / Regional / Same category)")
    # Hospital (center, latest year)
    latest_h = _latest_year(app_hop_year[app_hop_year["finessGeoDP"] == str(hospital_id)]) if not app_hop_year.empty else None
    if latest_h is not None:
        _sp_l, _center, _sp_r = st.columns([1, 1.6, 1])
        with _center:
            _pie_from(app_hop_year[(app_hop_year["finessGeoDP"] == str(hospital_id)) & ((app_hop_year.get("annee", app_hop_year.get("year"))) == latest_h)], f"Hospital ({latest_h})")
    else:
        st.info("No hospital approach data available.")

    c_nat, c_reg, c_cat = st.columns(3)
    with c_nat:
        ly = _latest_year(app_nat_year)
        if ly is not None:
            _pie_from(app_nat_year[(app_nat_year.get("annee", app_nat_year.get("year"))) == ly], f"National ({ly})")
        else:
            st.info("National approach CSV not loaded.")

    # Region and status derived from REV 12M (already loaded above)
    with c_reg:
        if region_name and not app_reg_year.empty:
            reg = app_reg_year[app_reg_year.get("lib_reg").astype(str).str.strip() == str(region_name)]
            ly = _latest_year(reg)
            if ly is not None:
                _pie_from(reg[(reg.get("annee", reg.get("year"))) == ly], f"Regional — {region_name} ({ly})")
            else:
                st.info("No regional rows for hospital's region.")
        else:
            st.info("Regional approach CSV not loaded or region not found.")

    with c_cat:
        if status_val and not app_status_year.empty:
            cat = app_status_year[app_status_year.get("statut").astype(str).str.strip() == str(status_val)]
            ly = _latest_year(cat)
            if ly is not None:
                _pie_from(cat[(cat.get("annee", cat.get("year"))) == ly], f"Same category ({ly})")
            else:
                st.info("No rows for this category.")
        else:
            st.info("Same-category approach CSV not loaded or status not found.")

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
    PROC_COLORS = {
        'Sleeve': '#1f77b4',
        'Gastric Bypass': '#ff7f0e',
        'Other': '#2ca02c'
    }

    def _tcn_pie(df: pd.DataFrame, title: str, filters: dict | None = None):
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
        figp = px.pie(dfp, values='Count', names='Procedure', hole=0.55, color='Procedure', color_discrete_map=PROC_COLORS)
        figp.update_traces(textposition='inside', textinfo='percent+label')
        figp.update_layout(title=title, height=260, showlegend=False, plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)')
        st.plotly_chart(figp, use_container_width=True)

    # Layout: hospital centered (large), then three small pies below
    _sp_l, _center, _sp_r = st.columns([1, 1.2, 1])
    with _center:
        _tcn_pie(tcn_hop, "Hospital", { 'finessGeoDP': str(hospital_id) })

    c_nat2, c_reg2, c_cat2 = st.columns(3)
    with c_nat2:
        _tcn_pie(tcn_nat, "National", None)
    with c_reg2:
        _tcn_pie(tcn_reg, f"Regional", { 'lib_reg': region_name })
    with c_cat2:
        _tcn_pie(tcn_status, "Same category", { 'statut': status_val })


