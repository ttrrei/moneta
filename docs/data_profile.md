# Data Profile — moneta 1-minute market data

Bronze raw → cleaned **1-minute** Parquet (output of `pipeline/load_data.py`).

## Source (Bronze)
- Directory: `data/raw_csv/**/*.csv` (292 files)
- Columns: `instrument, is_complete, time, volume, mid_o/mid_h/mid_l/mid_c, bid_o/bid_h/bid_l/bid_c, ask_o/ask_h/ask_l/ask_c`

## Raw profile
- Raw rows (all files, union-by-name): **24,152,974**
- Distinct `(instrument, time)`: **6,643,328**
- `is_complete` distribution: False = 4,990; True = 24,147,984 (only **21** keys occur solely as incomplete)
- Vendors/instruments: **21** (FX, metals, indices, crypto, crude) — e.g. EUR_USD, XAU_USD, BTC_USD, SPX500_USD, NAS100_USD, JP225_USD
- Time column is timezone-aware **UTC** (instants stored/interpreted as UTC; **no DST**, no local-time conversion)
- Time span: `2025-11-14 10:57 (UTC)` → `2026-10-19 01:29 (UTC)`
- ~6,639,117 raw keys had duplicates (i.e. all keys are duplicated across slices)

## Cleaned (1-minute) Parquet
- Output: `data/all_data/all_data.parquet` (~271 MB)
- Rows: **6,643,307**
- `(instrument, time)` unique: yes (0 duplicates)
- Incomplete rows: 0
- All timestamps on exact minute boundary (0 rows off-minute)
- Per-instrument rows: ~215k – 340k each
- Metadata (table name, CSV dir, parquet path, row count, loaded_at) stored in `data/metadata.duckdb` → `loaded_tables` only; **no full data tables in DuckDB**.

## Notes / gotchas
- Most row reduction (~17.4M) comes from cross-file duplication: multiple slices (e.g. `prices_*.csv` + `OUTPUT_BASE*.csv`) contain the same instrument/time.
- Downstream resampling (5m/1h OHLCV) is carried out in **UTC** (bars aligned to UTC minute/hour boundaries; no DST shifts).
- The `clean_all_data` / `load_csvs_to_duckdb` legacy entry points remain for compatibility but now delegate to `load_data`.