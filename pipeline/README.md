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
5. Records the Parquet path, row count, and schema in `data/metadata.duckdb`.
   DuckDB exposes `main.all_data` as a view over the Parquet file; it does not
   duplicate the table data in the database.

Run with `python -m pipeline.load_data` (default table name `all_data`).

## Implemented now (continued)

`aggregate_ohlcv.py` implements the **Aggregate** stage:

1. Reads the cleaned 1-minute bars (from Parquet or a DuckDB `main.all_data` table).
2. Filters out incomplete rows when an `is_complete` column is present.
3. Buckets bars on UTC boundaries into 5-minute and 1-hour OHLCV bars.
4. Computes `open`/`close` via `arg_min`/`arg_max` by source time (first/last bar), `high`/`low` via MAX/MIN, `volume` via SUM, and `n_bars` via COUNT for partial-bar detection.
5. Writes results to `data/ohlcv_5m/ohlcv_5m.parquet` and `data/ohlcv_1h/ohlcv_1h.parquet` (one directory per table, consistent with `data/all_data/all_data.parquet`).
6. Registers each Parquet path, row count, and schema in DuckDB's `data_tables`
   catalog and exposes `main.ohlcv_5m` / `main.ohlcv_1h` as Parquet-backed views.

Run with `python -m pipeline.aggregate_ohlcv` (default paths).

`extract_oanda.py` is the single OANDA downloader. It reads the token and
practice/live setting from the `oanda` section of `config/setting.yml` and
writes loader-compatible CSVs to `data/raw_csv/<instrument>/`.

Gap fill or one instrument (inclusive UTC window):

```bash
python -m pipeline.extract_oanda --instrument GBP_USD \
  --from 2026-07-08T02:25:00Z --to 2026-07-08T20:47:00Z
```

Backfill earlier history for many instruments from `config/history_map.yml`
(one entry per instrument; `to: auto` stops one candle before the earliest
candle already in `data/all_data/all_data.parquet`, so nothing overlaps. With no
ingested data yet it fills from `from` up to now):

```bash
python -m pipeline.extract_oanda --map config/history_map.yml --dry-run  # plan only
python -m pipeline.extract_oanda --map config/history_map.yml            # download
python -m pipeline.extract_oanda --map config/history_map.yml --only GBP_USD
python -m pipeline.load_data                                             # then ingest
```

Backfill writes one CSV per instrument per UTC month and skips finished months
on re-run, so an interrupted run resumes.
Failures are handled in layers: each HTTP request is retried (5 attempts with
backoff); an instrument that still fails is retried after `--retry-wait` seconds
(default 60) for up to `--retries` extra passes (default 2), resuming at the month
that failed; whatever is still failing is reported at the end with a non-zero
exit code. A month OANDA has no candles for gets
an `.empty` marker file instead of a header-only CSV. A 401/403 aborts the run;
any other error stops only that instrument and the exit code is non-zero.
To backfill, ingest and check in one go (stops at the first failing step):

```bash
scripts/backfill_and_check.sh                  # or: --only GBP_USD / --dry-run
```

It runs `extract_oanda --map`, `load_data`, `aggregate_ohlcv`, `sanity_check` and
`profile_check --raw --out docs/profile_output.txt`.

`extract_oci` leaves sub-directories of `data/raw_csv/` alone, so backfilled
files survive an OCI re-sync.

## Implemented now (feature engine)

`indicators.py` implements the **feature engine** (the "Gold" wide tables) —
the single source of truth for the 5m/1h feature matrix. It reads the 5m/1h
OHLCV tables and, per instrument, computes **305 (5m) / 270 (1h) feature
columns** across trend, momentum, volatility, regime, candle-structure,
volume-proxy, and derived families, then drops the 360-bar warm-up head and
streams the result to Parquet (registering metadata + views in DuckDB).

```bash
.venv/bin/python -m pipeline.indicators    # rebuild both feature tables (~5 min)
# free (non-window) parameters, e.g. different PSAR sets / Supertrend multipliers:
.venv/bin/python -m pipeline.indicators --psar 0.02:0.2 --st-mult 3
```

The spec is `docs/indicators.md`; the readable (non-code) mirror is
`config/indicators.yml`. If the two ever disagree, **`pipeline/indicators.py`
wins** — update the spec in the same change.

**Custom indicators live in the `library/` package** (our own code, not
TA-Lib): `supertrend.py` (causal Supertrend line + direction — TA-Lib has no
Supertrend), `psar.py` (PSAR line via `talib.SAR` + our direction convention),
`utils.py` (shared helpers). They are pure NumPy, causal, and **tested in
isolation** in `tests/test_indicators.py`; the pipeline imports them rather
than re-implementing.

The feature engine is covered by the six quality gates in
`tests/test_indicators.py` (causality/prefix-invariance, bounds & invariants,
degenerate-input safety, the 1h→5m as-of alignment, and the custom-indicator
tests above), runnable with no real data and no network.

## Not yet implemented

- A standalone `scripts/verify_indicator_parity.py` dual-library parity harness
  (Gate 5 is currently covered at the smoke level by `tests/test_indicators.py`;
  the full TA-Lib vs pandas-ta parity fixture on a fixed 20k-row sample is still
  future work).