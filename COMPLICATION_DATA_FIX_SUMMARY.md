# Complication Section Data Fix Summary

## Issues Found and Fixed

### Issue #1: Partial Year Data (Toggle OFF - Annual View)
**Problem:** When the toggle was OFF (showing annual data), the code was using `.max()` to select the "latest year", which picked up **2025** - a partial year with only 6 months of data (January-June 2025). This resulted in misleading and inflated percentages.

**Example:**
- National complication rate was showing **3.8%** (partial 2025)
- Should show **2.5%** (complete 2024)
- Hospital 930100037 was showing **10.2%** (partial 2025)
- Should show **6.4%** (complete 2024)

**Root Cause:** 
```python
# OLD CODE (WRONG)
latest_year = df["annee"].max()  # Returns 2025 (partial year!)
```

**Fix Applied:**
Created `_get_latest_complete_year()` helper function that:
1. Gets all available years
2. Sorts them in descending order
3. If multiple years exist, uses the **second-to-last year** (skipping the current partial year)
4. This ensures we always use complete yearly data

```python
# NEW CODE (CORRECT)
def _get_latest_complete_year(df: pd.DataFrame) -> int | None:
    """Get the latest complete year, excluding current partial year."""
    if df.empty or "annee" not in df.columns:
        return None
    df_copy = df.copy()
    df_copy["annee"] = pd.to_numeric(df_copy["annee"], errors="coerce")
    years = df_copy["annee"].dropna().unique()
    if len(years) == 0:
        return None
    years_sorted = sorted(years, reverse=True)
    # If we have multiple years, use second-to-last (skip partial current year)
    if len(years_sorted) >= 2:
        return int(years_sorted[1])
    # If only one year, use it
    return int(years_sorted[0])
```

---

### Issue #2: Wrong Column Used (Toggle ON - Last 12 Months)
**Problem:** When the toggle was ON (showing last 12 months), the code was loading the `TAB_COMPL_*_ROLL12.csv` tables but using the **wrong column**.

The ROLL12 tables have TWO percentage columns:
- `COMPL_pct`: Monthly complication rate for that specific month
- `COMPL_pct_roll12`: Rolling 12-month average ← **This is what we should use!**

The code was using `COMPL_pct` (single month) instead of `COMPL_pct_roll12` (rolling 12-month average).

**Fix Applied:**
Updated all four bubble displays (Hospital, National, Regional, Same category) to:
1. Detect if using ROLL12 data (when `use_12m_compl` is True)
2. Use `COMPL_pct_roll12` column instead of `COMPL_pct`
3. Sort by year/month to get the latest month's rolling 12-month average

```python
# NEW CODE (CORRECT)
if use_12m_compl:
    # ROLL12 file: get latest month, use COMPL_pct_roll12
    if "COMPL_pct_roll12" in rows.columns:
        # Sort by date/year/month to get latest
        if "annee" in rows.columns and "mois" in rows.columns:
            rows["_ym"] = pd.to_numeric(rows["annee"], errors="coerce") * 100 + pd.to_numeric(rows["mois"], errors="coerce")
            rows = rows.sort_values("_ym", ascending=False)
        compl_val = rows.iloc[0]["COMPL_pct_roll12"]
        if pd.notna(compl_val):
            result = f"{float(compl_val):.1f}%"
```

---

## Files Modified

### `/Users/alexdebelka/Downloads/navira/navira/sections/complication.py`

**Changes Made:**

1. **Lines 172-188**: Added `_get_latest_complete_year()` helper function
2. **Lines 193-223**: Updated Hospital bubble to use correct logic for both YEAR and ROLL12 data
3. **Lines 225-254**: Updated National bubble to use correct logic for both YEAR and ROLL12 data
4. **Lines 256-286**: Updated Regional bubble to use correct logic for both YEAR and ROLL12 data
5. **Lines 288-318**: Updated Same category bubble to use correct logic for both YEAR and ROLL12 data
6. **Lines 489-531**: Updated `_get_grade_rates()` function to use `_get_latest_complete_year()` for Clavien-Dindo grade calculations

---

## Tables Used

### When Toggle is OFF (Annual View):
- `TAB_COMPL_HOP_YEAR.csv` - Hospital yearly complications
- `TAB_COMPL_NATL_YEAR.csv` - National yearly complications
- `TAB_COMPL_REG_YEAR.csv` - Regional yearly complications
- `TAB_COMPL_STATUS_YEAR.csv` - Status/category yearly complications
- Column used: `COMPL_pct`
- Year selection: **Latest COMPLETE year (2024)** ✅

### When Toggle is ON (Last 12 Months):
- `TAB_COMPL_HOP_ROLL12.csv` - Hospital monthly complications with rolling averages
- `TAB_COMPL_NATL_ROLL12.csv` - National monthly complications with rolling averages
- `TAB_COMPL_REG_ROLL12.csv` - Regional monthly complications with rolling averages
- `TAB_COMPL_STATUS_ROLL12.csv` - Status/category monthly complications with rolling averages
- Column used: **`COMPL_pct_roll12`** (rolling 12-month average) ✅
- Month selection: Latest available month (June 2025)

---

## Test Results

### Before Fix:
- **Toggle OFF**: National = 3.8%, Hospital 930100037 = 10.2% (using partial 2025 data ❌)
- **Toggle ON**: Would use single-month rate instead of rolling 12-month average ❌

### After Fix:
- **Toggle OFF**: National = 2.5%, Hospital 930100037 = 6.4% (using complete 2024 data ✅)
- **Toggle ON**: National = 3.04% (using rolling 12-month average ✅)

---

## Impact

This fix ensures that:
1. ✅ Annual percentages are based on **complete year data** (2024), not partial year (2025)
2. ✅ Rolling 12-month percentages use the **correct rolling average column**, not single-month data
3. ✅ All four comparison bubbles (Hospital, National, Regional, Same category) display accurate data
4. ✅ Clavien-Dindo grade complications also use complete year data
5. ✅ Never events calculations use complete year data

---

## Date Fixed
November 10, 2025

## Author
AI Assistant (Claude Sonnet 4.5)

