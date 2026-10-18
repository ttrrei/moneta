# Pipeline

This directory hosts the **data pipeline (Bronze ingestion)** for Nova.

## Implemented now

`extract_oci.py` implements the **Bronze** stage:

1. **Extract from OCI / Unarchive** — `sync_oci_par()` lists and downloads objects from an OCI Object Storage Pre-Authenticated Request (PAR) URL (`config/setting.yml` → `oci.par_url`), with pagination, retries, idempotent size-based skipping, and traversal-safe paths.
2. **Collect CSVs** — `extract_all_zips_to_csv()` recursively extracts every `*.zip` under `data/raw_zips/` and flattens all `*.csv` into `data/raw_csv/` (collision-safe naming).
3. **Entry point** — `main()` orchestrates `sync_oci_and_extract()` end to end; run with `python -m pipeline.extract_oci`.

`load_data.py` implements the **Load + Clean** stage:

1. Reads every `*.csv` under `data/raw_csv/` (recursively, union-by-name).
2. Drops rows where `is_complete` is false.
3. Deduplicates on `(instrument, time)`.
4. Exports the cleaned 1-minute bars to `data/<table_name>/<table_name>.parquet`.
5. Records bookkeeping in `data/metadata.duckdb` (metadata only — no data tables).

Run with `python -m pipeline.load_data` (default table name `all_data`).

## Planned (not yet implemented)

- **Aggregate** — resample 1-minute data into 5-minute and 1-hour OHLCV bars.
- **Feature engineering** — technical indicators and engineered features (Silver/Gold).

Treat the unimplemented steps above as placeholders.