import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from navira.data_repo import DataRepo


APPROACH_LABELS = {"LAP": "Open Surgery", "COE": "Coelioscopy", "ROB": "Robotic"}
APPROACH_COLORS = {"Open Surgery": "#A23B72", "Coelioscopy": "#2E86AB", "Robotic": "#F7931E"}


def _latest_year(df: pd.DataFrame) -> int | None:
    if df is None or df.empty:
        return None
    d = DataRepo.ensure_year_column(df)
    if d.empty or "year" not in d.columns:
        return None
    years = pd.to_numeric(d["year"], errors="coerce").dropna().astype(int)
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


def render_activity(hospital_id: str, repo: DataRepo):
    """Render the Activity section (Version 2 layout) using CSV repo data only.

    Layout:
      - Row 1: big hospital volume bar (per year) + YoY bubble (2025 vs 2024 if present)
      - Row 2: hospital approaches (large, latest year) and three small pies (national, regional, same category)
    """
    st.subheader("Activity Overview")

    vol_hop_year = repo.get_vol_hop_year()
    app_hop_year = repo.get_app_hop_year()
    app_nat_year = repo.get_app_nat_year()
    app_reg_year = repo.get_app_reg_year()
    app_status_year = repo.get_app_status_year()

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

    st.markdown("---")

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

    # Region and status from repo helper
    region_name, status_val = repo.get_region_and_status(hospital_id)
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


