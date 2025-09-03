# navira
Created in collaboration with Avicenne Hospital, Bobigny

## Overview

Navira is a comprehensive analytics platform for bariatric surgery centers in France, providing insights into hospital performance, competitor analysis, and recruitment zone visualization through interactive choropleth maps.

### Key Features

- **Hospital Performance Analytics**: Volume trends, robotic surgery rates, complication analysis
- **Recruitment Zone Mapping**: Interactive choropleth visualization of patient recruitment by postal code/commune
- **Competitor Analysis**: Top 5 competitor identification and comparison
- **National Benchmarking**: Performance comparison against national averages
- **Geographic Insights**: Interactive maps with toggleable layers for recruitment analysis

## Data workflow

- Build Parquet datasets from raw CSVs:

```bash
make parquet
# or
python scripts/build_parquet.py
```

Inputs (semicolon-delimited): `data/01_hospitals.csv`, `data/06_tab_tcn_redo_new.csv`, `data/03_tab_vda_new.csv`, `data/04_tab_redo.csv`

Outputs: `data/processed/establishments.parquet`, `data/processed/annual_procedures.parquet`

Environment variables:
- `NAVIRA_RAW_DIR` (default `data`)
- `NAVIRA_OUT_DIR` (default `data/processed`)

## Running the app

Install deps and run Streamlit as usual:

```bash
pip install -r requirements.txt
streamlit run main.py
```

The app loads only Parquet files for visualization. If they are missing, the UI will show an error instructing you to build them.

## National overview note

National means are computed across hospitals (2020–2024). Only hospitals with ≥25 interventions/year are considered for that analysis.

## Troubleshooting

- Parquet not found: run `make parquet`.
- Cache doesn’t refresh after rebuilding: run in a Python REPL or at app start:

```python
import streamlit as st
st.cache_data.clear()
```

- Schema mismatch: ensure `establishments.parquet` contains at least `['id','name']` and `annual_procedures.parquet` contains `['id','annee','total_procedures_year']`.

## Recruitment Zone Choropleth Feature

### Overview
The recruitment zone feature provides interactive choropleth maps showing patient recruitment patterns for hospitals and their competitors across French communes.

### Data Requirements

**Required CSV Files:**
- `data/11_recruitement_zone.csv`: Patient recruitment data by postal code
  - Columns: `finessGeoDP` (hospital FINESS), `codeGeo` (postal code), `nb` (patient count), etc.
- `data/13_main_competitors.csv`: Hospital competitor relationships  
  - Columns: `finessGeoDP` (focal hospital), `finessGeoDP_conc` (competitor), `TOT_conc` (competitor volume)
- `data/COMMUNES_FRANCE_INSEE.csv`: French communes with INSEE codes
  - Columns: `codeInsee`, `codePostal`, `longitude`, `latitude`, `nomCommune`

**GeoJSON Configuration:**
- Set `COMMUNES_GEOJSON_PATH` in Streamlit secrets or environment variable
- Or place GeoJSON file at: `data/communes.geojson`, `data/communes-france.geojson`, etc.
- Required property: INSEE commune code (auto-detected as `INSEE_COM`, `insee`, `code_insee`, etc.)

### Data Processing

**Postal Code → INSEE Mapping:**
- French postal codes often map to multiple INSEE commune codes (many-to-many relationship)
- Two allocation strategies available:
  - `even_split` (default): Divide patient count evenly among mapped INSEE codes
  - `no_split`: Assign full patient count to all mapped INSEE codes (for validation)

**Competitor Ranking:**
- Competitors ranked by `TOT_conc` (descending), tie-broken by `TOT_etb` (descending)
- Up to 5 top competitors shown as toggleable choropleth layers

**Data Cleaning:**
- FINESS codes padded to 9 digits with leading zeros
- Postal/INSEE codes padded to 5 digits
- Comma decimal strings ("29,6") converted to float (29.6)

### Map Features

**Interactive Elements:**
- Hospital marker (red) at selected hospital location
- Competitor markers (blue) if coordinates available
- Choropleth layers (one per top competitor) with shared color scale
- Layer control panel for toggling choropleth visibility
- Commune tooltips showing name and patient count
- Legend showing patient recruitment scale

**Performance Optimizations:**
- Filtered GeoJSON loading (only needed INSEE codes)
- Cached data loading and processing
- Memoized choropleth calculations

### Configuration

**Streamlit Secrets (recommended):**
```toml
# .streamlit/secrets.toml
COMMUNES_GEOJSON_PATH = "/path/to/communes.geojson"
```

**Environment Variable:**
```bash
export COMMUNES_GEOJSON_PATH="/path/to/communes.geojson"
```

**Default Paths Searched:**
- `data/communes.geojson`
- `data/communes-france.geojson`
- `data/communes_france.geojson`
- `../data/communes.geojson`

### Known Limitations

**Postal Code ↔ INSEE Mapping:**
- Some postal codes may not have corresponding INSEE codes in the reference file
- Historical INSEE code changes not automatically handled
- Overseas territories may have different coding schemes

**Performance Considerations:**
- Large GeoJSON files (>100MB) may cause browser performance issues
- Streamlit tabs can have rendering issues with complex Folium maps
- Layer control with 5+ layers may be visually crowded

### Troubleshooting

**Map Not Displaying:**
- Check browser console for JavaScript errors
- Verify GeoJSON file format and INSEE property names
- Try reducing number of competitor layers
- Clear Streamlit cache: `st.cache_data.clear()`

**Missing Choropleths:**
- Verify `COMMUNES_GEOJSON_PATH` configuration
- Check INSEE key auto-detection in diagnostics panel
- Ensure recruitment data contains matching FINESS codes

**Performance Issues:**
- Use filtered GeoJSON loading for large datasets
- Reduce number of competitor layers
- Check memory usage in browser developer tools

## Tests

Comprehensive test suite covering:

```bash
# Run all tests
pytest

# Run specific test modules
pytest tests/test_recruitment_zones.py -v

# Run with coverage
pytest --cov=navira tests/
```

**Test Coverage:**
- Data loading and cleaning with comma decimal conversion
- Competitor ranking determinism
- Postal → INSEE mapping with one-to-many relationships  
- Choropleth generation with both allocation strategies
- Total patient conservation under even_split allocation
- GeoJSON INSEE key auto-detection
- Error handling and edge cases
- Memory efficiency with large datasets

**Test Data:**
- Sample CSV files in `tests/data/` for validation
- Synthetic fixtures for unit testing
- Integration tests with full pipeline
# deploy test
