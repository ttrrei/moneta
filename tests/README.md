# Tests

This directory is the **pytest suite** for the whole repo (pipeline + strategy).
All tests run **without network access and without the real `data/` Parquet
files** — they use synthetic OHLCV or hand-built price paths — so they run in
any environment and are the intended basis for a future CI.

Run with:

```bash
.venv/bin/python -m pytest tests/ -q        # 86 tests
```

## What is covered

- `test_extract_oci.py` — OCI listing/download, idempotent skipping, safe path
  resolution, zip extraction to a flat CSV directory, YAML config loading, and
  edge cases (missing files / empty inputs).
- `test_extract_oanda.py` — OANDA gap-fill / history backfill logic (pagination,
  resume, failure handling) with mocked HTTP.
- `test_aggregate_ohlcv.py` — 1m → 5m/1h aggregation (buckets, OHLC, partial
  bars, dedup).
- `test_indicators.py` — the **six quality gates** for the feature engine
  (`pipeline/indicators.py`) **plus the custom `indicators/` library** (PSAR,
  Supertrend) on synthetic data:
  - Gate 1 — causality / prefix invariance + no-future-leakage;
  - Gate 3 — bounds & invariants (RSI/Stoch ∈ [0,100], ATR ≥ 0,
    bb_lower ≤ bb_upper, binary flags);
  - Gate 4 — degenerate (zero-amplitude) input produces no Inf and no crash;
  - Gate 6 — the 1h→5m as-of join never exposes an unclosed 1h bar;
  - Gate 5 (smoke) — RSI/SMA parity against a direct TA-Lib call, and
    Supertrend direction parity against `pandas_ta_classic.supertrend`
    (agreement > 99.8%);
  - **PSAR / Supertrend** — column presence, free-param handling (not
    whitelisted, but windows still are), direction = side of price, Supertrend
    line on the trend side, wider multiplier flips less, flip-on-close, and
    prefix-invariance under custom parameters.
- `test_metrics.py` — **golden-value tests for the shared engine**
  (`strategy/engine.py`): exact accounting on known price paths, long/short
  symmetry, force-close, next-open fill, the **corrected annualised Sharpe**
  (invariant to sample length, unlike the old `* sqrt(n_trades * 12)` form),
  and the **B6 entry guard** (`no_entry_mask` blocks new entries from flat but
  never blocks exits or the end-of-data force-close).

## Conventions

- Test files are named `test_*.py` and auto-discovered by pytest (no extra
  config; `strategy/` is imported as a namespace package from the repo root).
- Prefer unit tests that need no network; mock OCI/OANDA and the filesystem.
- Strategy/Alpha validation (i.e. running real backtests to *find* alpha) is
  **out of scope** here — these tests lock *definitions* and *invariants*, not
  trading performance.
