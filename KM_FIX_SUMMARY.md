# Kaplan-Meier Chart Fix Summary

## Problem Diagnosed

Multiple pages were showing **identical KM curves** despite different filters and datasets due to:

1. **Global State Reuse**: Plotly figures were being reused across pages
2. **Improper Caching**: `@st.cache_data` without proper cache keys led to same cached results
3. **Missing Unique Keys**: `st.plotly_chart` used default keys, causing figure collision
4. **No Data Validation**: No verification that filters actually changed the underlying data

## Root Causes Identified

- **Figure Object Reuse**: Same `go.Figure()` objects modified and reused
- **Cache Key Issues**: Cache keys didn't include data content, only function signature
- **Session State Collisions**: No page-specific namespacing for widgets
- **Filter Validation Missing**: No checks if filters actually modified datasets

## Solution Implemented

### 1. Pure KM Computation (`km.py`)
- **`compute_km_from_aggregates()`**: Pure function with proper cache keys including data hashes
- **`debug_signature()`**: Generates data fingerprints for tracing
- **Proper time ordering**: Handles both 6-month and 3-month intervals
- **Group support**: Can compute multiple curves (national vs hospital-specific)

### 2. Chart Factory (`charts.py`)  
- **`create_km_chart()`**: Always creates fresh `go.Figure()` objects
- **Page-specific styling**: Different colors and titles per page
- **No object reuse**: Each call returns a completely new figure
- **Unique hover templates**: Page-specific hover information

### 3. Cache Management (`utils/cache.py`)
- **`dataframe_md5()`**: Content-based hashing for cache keys
- **`debug_dataframe_signature()`**: Data fingerprinting for debugging
- **`show_debug_panel()`**: UI component for tracing data flow
- **`clear_all_caches()`**: One-click cache clearing

### 4. Page Refactoring

#### National Page (`pages/national.py`)
- Uses `compute_km_from_aggregates()` with national-level aggregation
- Unique chart key: `"km_national_v2"`
- Debug panel with data signatures at each step
- Proper filter application with hospital subset filtering

#### Dashboard Page (`pages/dashboard.py`) 
- Uses hospital-specific complications via `_get_hospital_complications()`
- Unique chart key: `f"km_hospital_{selected_hospital_id}_v2"`
- Hospital-specific debug panel
- Semester-level aggregation for individual hospitals

### 5. Debug System
- **Data Signatures**: MD5 hashes and row counts at each processing step
- **Debug Panels**: Collapsible UI showing data flow and transformations
- **Cache Clearing**: Button to reset all cached data
- **Error Tracking**: Captures and displays computation errors

### 6. Unit Tests (`tests/test_km.py`)
- **Different Curves Test**: Verifies different hazards → different curves
- **Caching Tests**: Ensures different data → different cache keys
- **Edge Cases**: Zero events, missing data, invalid inputs
- **Group Processing**: Multi-group KM computation
- **Time Ordering**: Proper chronological sequence handling

## Key Improvements

### ✅ **Eliminated State Reuse**
- Every `st.plotly_chart()` call uses unique keys
- Fresh `go.Figure()` objects created for each chart
- No global variables or mutable objects shared between pages

### ✅ **Robust Caching**
- Cache keys include data content hashes (`data_hash` parameter)
- Different filters → different data → different cache keys → different results
- Cache versioning (`cache_version="v1"`) for future invalidation

### ✅ **Data Flow Validation**
- Debug signatures trace data through each transformation step
- Verification that filters actually change the underlying datasets
- Hash comparison to detect when data is identical vs different

### ✅ **Error Handling**
- Graceful handling of missing data, invalid columns, zero at-risk populations
- Clear error messages with specific failure points
- Fallback to empty charts with informative messages

### ✅ **Testing Coverage**
- Unit tests for different hazard patterns producing different curves
- Cache behavior validation (same data → same hash, different data → different hash)
- Edge case handling (zero events, missing data, invalid inputs)

## Usage

### For Users
1. **Enable Debug Mode**: Check "Show KM debug info" to see data signatures
2. **Clear Caches**: Use "Clear All Caches" button if curves seem stuck
3. **Verify Filters**: Debug panel shows if filters actually changed the data

### For Developers
1. **Adding New KM Charts**: Use `create_km_chart()` with unique `page_id`
2. **Cache Keys**: Always include `data_hash` parameter for proper caching
3. **Debug Integration**: Add debug signatures to trace data flow
4. **Testing**: Run `pytest tests/test_km.py` to verify KM computation

## Files Modified/Created

### New Files
- `km.py` - Pure KM computation functions
- `charts.py` - Chart factory functions  
- `utils/cache.py` - Cache management utilities
- `utils/__init__.py` - Utils package init
- `tests/test_km.py` - Comprehensive unit tests
- `KM_FIX_SUMMARY.md` - This documentation

### Modified Files
- `pages/national.py` - Refactored to use new KM system
- `pages/dashboard.py` - Refactored to use new KM system  
- `README.md` - Added KM documentation section

## Verification Steps

1. **Navigate to National page** → Enable KM debug → Note data hash
2. **Change filters** (interval, labels, top-10) → Verify hash changes
3. **Navigate to Hospital page** → Different hospital → Different hash  
4. **Compare curves** → Should be visibly different when data differs
5. **Clear caches** → Verify curves regenerate correctly

## Success Criteria Met ✅

- [x] **Different pages show different KM curves** when data differs
- [x] **Same filters produce identical curves** (consistency)
- [x] **Cache invalidation works** when data/filters change
- [x] **Debug information available** for troubleshooting
- [x] **No global state reuse** between pages
- [x] **Comprehensive test coverage** for edge cases
- [x] **Clear documentation** for usage and troubleshooting

The KM chart system is now robust, debuggable, and produces correctly differentiated curves across different pages and filters.
