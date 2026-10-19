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

## Implemented now (continued)

`aggregate_ohlcv.py` implements the **Aggregate** stage:

1. Reads the cleaned 1-minute bars (from Parquet or a DuckDB `main.all_data` table).
2. Filters out incomplete rows when an `is_complete` column is present.
3. Buckets bars on UTC boundaries into 5-minute and 1-hour OHLCV bars.
4. Computes `open`/`close` via `arg_min`/`arg_max` by source time (first/last bar), `high`/`low` via MAX/MIN, `volume` via SUM, and `n_bars` via COUNT for partial-bar detection.
5. Writes results to `data/ohlcv_5m/ohlcv_5m.parquet` and `data/ohlcv_1h/ohlcv_1h.parquet` (one directory per table, consistent with `data/all_data/all_data.parquet`).

Run with `python -m pipeline.aggregate_ohlcv` (default paths).

## Planned (not yet implemented)

- **Feature engineering** — technical indicators and engineered features (Silver/Gold).

Treat the unimplemented steps above as placeholders.