# Strategy Background & Context

> **Purpose:** everything an AI (or a human) needs to design, code, and run a
> **new strategy** in this repo — without re-reading the codebase.
>
> **Read order:** this file → [STRATEGY_REGISTRY.md](STRATEGY_REGISTRY.md) →
> start building. If any fact below stops matching reality, fix this file in
> the same change.

---

## 1. What this project is

Quant strategy research on **OANDA CFD** data across 21 instruments
(FX, metals, energy, index CFDs, crypto). A pipeline produces two feature
tables — a **5m signal layer** and a **1h context layer**. Strategies read those
Parquet tables, run a bar-by-bar backtest, and report results vs buy-and-hold.

**Stack:** Python 3.12 in `.venv` · DuckDB (queries + metadata) · Parquet (data) ·
TA-Lib + pandas-ta-classic (indicators) · pandas/NumPy (backtests).
No ML framework is in use yet. No network access is needed to backtest.

**Machine limits:** 2 CPUs, ~8 GB RAM. Keep backtests as a per-instrument loop
loading one instrument at a time. Do **not** load all 21 instruments' 5m feature
frames into memory at once (>10 GB).

---

## 2. The data (exact, verified 2026-10-26)

| Layer | File | Rows | Cols | Grain |
|---|---|---:|---:|---|
| **5m features** | `data/ohlcv_5m_features/ohlcv_5m_features.parquet` | 9,926,663 | **259** | one 5-min bar / instrument |
| **1h features** | `data/ohlcv_1h_features/ohlcv_1h_features.parquet` | 826,353 | **234** | one 1-hour bar / instrument |
| 5m raw OHLCV | `data/ohlcv_5m/ohlcv_5m.parquet` | 9,934,223 | 8 | pre-features |
| 1h raw OHLCV | `data/ohlcv_1h/ohlcv_1h.parquet` | 833,913 | 8 | pre-features |
| 1m raw | `data/all_data/all_data.parquet` | 48,588,451 | — | Bronze source |

- **21 instruments:** AUD_USD, BCO_USD, BTC_USD, CN50_USD, DE30_EUR, ETH_USD,
  EUR_USD, GBP_USD, HK33_HKD, JP225_USD, NAS100_USD, NZD_USD, SPX500_USD,
  UK100_GBP, US30_USD, USD_CAD, USD_CHF, USD_JPY, WTICO_USD, XAG_USD, XAU_USD.
- **Span:** 5m 2020-01-03 → 2026-10-24 · 1h 2020-01-23 → 2026-10-24
  (varies a little per instrument; the warm-up head is already dropped).
- **`time` is the bar OPEN time (UTC).** A bar's close time = `time + interval`
  (5m → +300 s, 1h → +3600 s). This distinction is what makes the as-of join safe.
- **dtypes:** features `float32`; flag columns `int8`; `instrument` string;
  `time` timestamp[us, UTC]; `n_bars` int64; OHLCV prices `float64`.
- **Nulls:** only in `h1_*` columns before the first *closed* 1h bar (~0.8% of
  5m rows — nothing to join yet). Every other column is fully populated.
- **Storage convention (project principle):** DuckDB `data/metadata.duckdb`
  holds *metadata + Parquet-backed views*; **Parquet is the data**. Never store
  row data in DuckDB. (The `data_tables` catalog + `main.*` views expose the
  Parquet by name, e.g. `SELECT ... FROM main.ohlcv_5m_features`.)
- **`metadata.duckdb` is single-user:** close VS Code's DuckDB panel before any
  write to it (file lock).

---

## 3. Feature columns (all 259 / 234, grouped)

The 5m table = the 1h table **plus** the `h1_*` context block (last 25 columns).
Window grid is a **hard whitelist**: `N ∈ {6, 12, 24, 60, 120}`; MACD pairs only
`(6,24)`, `(12,60)`, `(24,120)`. **Do not invent new windows** — extend the grid
in `pipeline/indicators.py` deliberately if you truly need one.

| Family | Columns (repeat per N = 6,12,24,60,120) |
|---|---|
| Base | `instrument, time, open, high, low, close, volume, n_bars` |
| **Trend** | `sma_N`, `ema_N`, `adx_N`, `plus_di_N`, `minus_di_N`, `aroon_up_N`, `aroon_down_N`, `dc_upper_N`, `dc_lower_N`, `dc_mid_N` · plus MACD triples `macd_f_s`, `macd_signal_f_s`, `macd_hist_f_s` (signal period = fast) |
| **Momentum** | `rsi_N`, `roc_N`, `mom_N`, `stoch_k_N`, `stoch_d_N`, `cci_N`, `willr_N` |
| **Volatility** | `tr` (no window), `atr_N`, `bb_mid_N`, `bb_upper_N`, `bb_lower_N`, `bb_width_N`, `bb_pctb_N`, `kc_mid_N`, `kc_upper_N`, `kc_lower_N`, `sqz_on_N` (0/1: BB inside Keltner), `hv_N` (log-return std) |
| **Regime** | `er_N` (efficiency ratio 0–1; 1=trend, 0=chop), `chop_N` (choppiness 0–100; >61.8 range, <38.2 trend) |
| **Candle** (no window) | `bar_body_ratio`, `bar_upper_wick_ratio`, `bar_lower_wick_ratio`, `bar_clv` (−1…+1) |
| **Volume** (tick volume = activity proxy) | `vol_sma_N`, `vol_rel_N` (=vol/its SMA), `mfi_N`, `cmf_N` · `vwap` (no window, session-anchored) |
| **Derived / scale-free** | `atr_pct_N` (=atr/close), `ema_dist_N` ((close−ema)/atr24), `ema_spread_f_s`, `macd_hist_atr_f_s`, `vol_ratio_f_s`, `dc_pos_N` (0–1 in channel), `dist_high_N`, `dist_low_N` (ATR distance to prior N-bar extreme, pre-shifted → lookahead-safe) |
| **Time cyclic** | `hour_sin`, `hour_cos`, `dow_sin`, `dow_cos` |
| **Flags** (int8 0/1) | `is_gap_bar` (gap since prev close), `is_partial` (bar built from < full 1m count), `is_near_market_close` (Fri, 2h before session anchor) |
| **1h context (5m table only)** | `h1_ema_dist_N`, `h1_adx_N`, `h1_rsi_N`, `h1_er_N`, `h1_atr_pct_N` — as-of joined, **already lookahead-safe** |

**Semantics you must respect:**
- `stoch_d_N` = SMA-6 of raw `%K` (built with `STOCHF`, not the smoothed `STOCH`).
- `bb_*` use population std (ddof=0) to match TA-Lib; `kc_*` = `ema_N ± 2.0·atr_N`.
- `dist_high_N` / `dist_low_N` compare against the **previous** N-bar extreme
  (already `shift(1)`) — safe to compare directly with the current `close`.
- `vwap` resets at each instrument's **session anchor** (below), not UTC midnight.
- `n_bars` (raw tables) = how many 1-min bars fed the bar; `is_partial` mirrors it.

**Session anchors for `vwap` reset & `is_near_market_close`** (local market time):

| Group | Instruments | Anchor |
|---|---|---|
| FX & metals | AUD, EUR, GBP, NZD, USD_CAD, USD_CHF, USD_JPY, XAU, XAG | 17:00 New York |
| US index CFDs | US30, SPX500, NAS100 | 09:30 New York |
| EU index CFDs | DE30, UK100 | 08:00 CET/BST |
| Asia index CFDs | JP225 (09:00 JST), HK33 (09:30 HKT), CN50 (09:30 HKT) | local open |
| Energy & crypto | BCO, WTICO, BTC, ETH | 00:00 UTC |

---

## 4. Hard rules for ANY strategy (from `docs/indicators.md` §3)

1. **No lookahead.** A signal computed on a **closed** bar T may only be filled at
   the **open of bar T+1**. Never fill at bar T's own close, never `shift(-k)`.
2. **No synthetic data.** Missing bars stay missing. Use `is_gap_bar` /
   `is_partial` as *inputs*; do not impute or forward-fill prices.
3. **1h context:** use the `h1_*` columns as-is (already correct). If you must
   join 1h yourself the only valid rule is `m.close_time >= h.close_time`.
4. **Costs:** assume **2 bps one-way** (OANDA CFD spread) on every fill unless a
   report states otherwise. When a result is near zero, always show a
   0 / 2 / 5 bps sensitivity so the required edge is explicit.
5. **Benchmark:** report **buy-and-hold** for the identical window in every result table.
6. **Register first.** Add a `candidate` row to [STRATEGY_REGISTRY.md](STRATEGY_REGISTRY.md)
   before coding; update status + result after the first run.
7. **No duplicates.** If the idea already matches an existing
   key-indicators + timeframe + entry-logic row, stop — don't re-test a tweak.

---

## 5. Repo layout (strategy-relevant)

```
strategy/
├── STRATEGY_BACKGROUND.md   ← this file (read me first)
├── STRATEGY_REGISTRY.md     ← check before creating, update after running
├── code/                    ← one self-contained CLI .py per strategy
│   └── strategy_rsi.py
└── docs/                    ← one report .md per strategy
    └── strategy_rsi_report.md

pipeline/
├── indicators.py            ← feature builder: source of truth for names & semantics
├── load_data.py             ← CSV → all_data.parquet + DuckDB catalog registration
├── aggregate_ohlcv.py       ← 1m → 5m/1h
├── sanity_check.py          ← data-integrity checks (dups, bad OHLC, gaps)
├── profile_check.py         ← gap/session/quality profiling, safe 1h→5m join helper
└── table_catalog.py         ← DuckDB metadata + Parquet views

data/                        ← Parquet tables (see §2)
docs/indicators.md           ← v2.0 spec (source of truth for indicator definitions)
tests/                       ← pipeline unit tests (pytest)
```

---

## 6. How to run things (repo root, `.venv`)

```bash
# Backtest an existing strategy (pattern: self-contained CLI):
.venv/bin/python strategy/code/strategy_rsi.py --instrument EUR_USD --since 2023-01-01

# Rebuild features (only after data or spec changes): ~5 min, streams per instrument
.venv/bin/python -m pipeline.indicators

# Ad-hoc query (open the metadata DB for the registered views, ~instant):
.venv/bin/python -c "import duckdb;print(duckdb.connect('data/metadata.duckdb', read_only=True).execute(\"SELECT * FROM main.ohlcv_5m_features LIMIT 3\").fetchdf())"

# Pipeline tests:
.venv/bin/python -m pytest tests/ -q
```

A **fast ad-hoc pattern** for a new idea (no file needed) — query one instrument's
feature slice and loop in Python/NumPy, enforcing signal-at-T / fill-at-T+1-open.

---

## 7. Baseline evidence — do NOT re-discover

- **S-01 (5m RSI-24, 30/55, long-only) is REJECTED** on all 4 tested instruments.
  Why: ~1,000 trades × ~4 bps round-trip ≈ **40% of equity paid in spread**, while
  the average trade is only ±0.03% — the per-trade edge is *smaller than the
  per-trade cost*. High win rate (54–63%) with negative expectancy.
  **Consequence:** any new 5m strategy must produce **far fewer trades** or a
  demonstrably larger per-trade edge. Moving the same rule to **1h** divides both
  trade count and cost by ~12 (S-02).
- Full write-up: [docs/strategy_rsi_report.md](docs/strategy_rsi_report.md).

---

## 8. New-strategy checklist

1. Read this file + the registry. Already listed as S-01…S-NN? → stop.
2. Add a `candidate` row (next `S-NN`) to [STRATEGY_REGISTRY.md](STRATEGY_REGISTRY.md).
3. Create `strategy/code/strategy_<name>.py`, self-contained CLI with
   `--instrument`, `--since`, `--parquet`, `--json`; load via DuckDB filtered on
   `instrument` (fast); enforce the §4 rules; print a JSON metrics block
   (`n_trades, win_rate, total_return, buyhold_return, max_dd, avg_trade, sharpe, exposure`).
4. Run on **EUR_USD + a trending instrument (BTC_USD) + a metal (XAU_USD)**,
   full history **and** a recent 12-month slice.
5. Write `strategy/docs/strategy_<name>_report.md`: results vs buy-hold,
   why it wins/loses, cost sensitivity (0/2/5 bps).
6. Update the registry: status, last run, result. If it fails → **rejected** + reason.

---

## 9. Environment quick facts

- Python `.venv` (3.12). Key packages: `duckdb`, `pyarrow`, `pandas`, `numpy`,
  `ta-lib` 0.8.2 (+ local C lib in `~/.local/ta-lib`), `pandas-ta-classic`
  (import as `pandas_ta_classic`).
- Indicator constants (from `pipeline/indicators.py`): `NORM_ATR=24`,
  `BB_SIGMA=2.0`, `KC_MULT=2.0`, Stochastic `%D` = SMA-6, `EPS=1e-12`,
  warm-up drop = `3×max(N)` = 360 bars.
- No secrets and no network needed for backtests.
