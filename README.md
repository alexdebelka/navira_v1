# navira
Created in collaboration with Avicenne Hospital, Bobigny

## Data workflow

- Build Parquet datasets from raw CSVs:

```bash
make parquet
# or
python scripts/build_parquet.py
```

Inputs (semicolon-delimited): `data/01_hospitals.csv`, `data/02_tab_tcn.csv`, `data/03_tab_vda.csv`, `data/04_tab_redo.csv`

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

## Tests

Run minimal tests:

```bash
pytest -q
```
