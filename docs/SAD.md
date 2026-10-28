# Software Architecture Document (SAD) — moneta / Nova

> **Audience:** developers and AI assistants implementing or modifying the system.
> **Scope:** architecture, data flow, components, and the invariants that must hold.
> For *what/why*, see [BRD.md](BRD.md). For feature semantics, see [indicators.md](indicators.md).
> **Principle:** code is the source of truth. If this doc and code disagree, fix this doc.

## 1. Architectural overview

Nova is a **unidirectional, batch, file-centric** system. There is no server, no service
mesh, no runtime state between runs. The core idea:

> **Parquet is the data. DuckDB is a thin metadata + query layer over Parquet. Python
> scripts are pure, reproducible transforms that read Parquet and write Parquet.**

Data flows strictly forward through a pipeline of stages, each producing an artifact on
disk that the next stage consumes. Strategies are leaf consumers of the final feature
tables.

```
   [OCI PAR]  [OANDA API]                 ┌────────────┐
        \          |                       │  1-minute  │
         \ download/extract                │ all_data   │  (Bronze: cleaned)
          v        v                        └─────┬──────┘
   data/raw_csv/**/*.csv  (Bronze, raw)           │ aggregate
                                                   v
                                   ┌────────────────────────────┐
                                   │ ohlcv_5m · ohlcv_1h (OHLCV)│
                                   └───────────────┬────────────┘
                                                   │ indicators (feature engine)
                                                   v
                              ┌──────────────────────────────────────────────┐
                              │ ohlcv_5m_features (305 cols)               │
                              │ ohlcv_1h_features (270 cols)  ← 1h as-of → 5m
                              └──────────────────────┬───────────────────────┘
                                                     │ read via DuckDB (filter on instrument)
                                                     v
                                    ┌──────────────────────────────────┐
                                    │ strategy/code/strategy_*.py      │
                                    │ self-contained CLI backtests      │
                                    └───────────────┬──────────────────┘
                                                    v
                                    ┌──────────────────────────────────┐
                                    │ strategy/docs/*_report.md +      │
                                    │ STRATEGY_REGISTRY.md (status)    │
                                    └──────────────────────────────────┘
   Cross-cutting: data/metadata.duckdb (catalog + Parquet-backed views, main.*)
```

## 2. Layers & data model

| Layer | Artifact | Grain | Notes |
|---|---|---|---|
| **Bronze (raw)** | `data/raw_csv/**/*.csv` | 1 bar (tick-mid) per row | OANDA mid/bid/ask OHLC, `is_complete`, `time` (UTC). Collision-safe naming; `extract_oci` leaves subdirs untouched. |
| **1-minute (clean)** | `data/all_data/all_data.parquet` | one 1-min bar / instrument | De-dup on `(instrument,time)`, `is_complete=false` dropped. |
| **OHLCV** | `data/ohlcv_5m/...parquet`, `data/ohlcv_1h/...parquet` | one 5m / 1h bar / instrument | `open/close` first/last source bar, `high/low` min/max, `volume` sum, `n_bars` count. |
| **Features** | `data/ohlcv_5m_features/...`, `data/ohlcv_1h_features/...` | one bar / instrument | 5m = 1h **plus** the `h1_*` context block (last 35 cols). `float32` at write, `float64` in compute. |
| **Metadata** | `data/metadata.duckdb` | per-table row | `data_tables` catalog + `main.<name>` Parquet-backed **views**. No row data. |

**Grain rule:** `time` is the bar **OPEN** time (UTC); close time = `time + interval`.

## 3. Components (with responsibilities)

### 3.1 `pipeline/` — the data pipeline

| Component | Responsibility | Key invariants it enforces |
|---|---|---|
| `extract_oci.py` | List + download OCI PAR objects, safe paths, unzip zips → flat CSV | Traversal-safe paths; idempotent size-based skipping; retries. |
| `extract_oanda.py` | OANDA gap-fill / history backfill → raw CSV | Paginate at 5k limit; per-month CSVs + `.empty` markers; layered retries; 401/403 aborts. |
| `load_data.py` | Raw CSV → `all_data.parquet` + DuckDB catalog | De-dup on `(instrument,time)`; drop incomplete; register view. |
| `aggregate_ohlcv.py` | 1m → 5m/1h OHLCV | UTC bucketing; OHLCV semantics; `n_bars` for partial detection. |
| `indicators.py` | Feature engine (305/270 cols) | TA-Lib source of truth; causality; CFD grid; no synthetic fill; float64→float32. |
| `library/` (pkg) | Custom indicators (Supertrend, PSAR dir) | Causal, pure-NumPy modules; tested in isolation (`tests/test_indicators.py`); imported by `pipeline/indicators.py`. |
| `sanity_check.py` | "Is anything broken?" | 0 dup keys / 0 bad OHLC / 0 over-full bars, else exit 1. |
| `profile_check.py` | Judgement profiling + `safe_mtf_view` | Shows naive-vs-safe 1h→5m join leak; gaps/sessions/partial/spread/quality. |
| `table_catalog.py` | Register Parquet tables + views in DuckDB | Identifier/literal quoting; upsert catalog; drop+recreate view. |

### 3.2 `strategy/` — the research layer

| Component | Responsibility |
|---|---|
| `STRATEGY_BACKGROUND.md` | Data contract + hard rules + new-strategy checklist (authoritative). |
| `STRATEGY_REGISTRY.md` | Single source of truth for all strategies; dedup + status. |
| `code/strategy_*.py` | One self-contained CLI per strategy (`--instrument --since --parquet --json`). |
| `docs/strategy_*_report.md` | Results vs buy-hold, diagnosis, cost sensitivity. |

### 3.3 Config

| File | Role |
|---|---|
| `config/setting.example.yml` | Template: `oci.par_url`, `oanda.*`. |
| `config/setting.yml` | **Git-ignored** real secrets; the only place tokens live. |
| `config/history_map.yml` | Per-instrument backfill ranges (`from`, `to: auto`). |
| `config/indicators.yml` | Readable indicator/feature spec (not loaded at runtime). Superseded by, and must match, `indicators.py`. |

## 4. Key design decisions (ADRs, summarized)

- **AD-1 File-centric over in-DB.** Parquet is the store; DuckDB is metadata + views.
  *Why:* columnar, portable, zero-copy querying, single-file artifacts, no DB engine
  dependency for data. *Trade-off:* no transactional updates — transforms are rewrite.
- **AD-2 TA-Lib (C) as indicator source of truth.** *Why:* correctness + speed;
  `pandas_ta_classic` only for ER/Chop and as the parity oracle.
- **AD-3 Causality by construction.** *Why:* eliminates the #1 source of fake alpha.
  Signals on closed bar `T`; fills at open of `T+1`; 1h→5m as-of on `close_time`.
- **AD-4 No synthetic gap filling.** *Why:* ffill on 48h weekends fabricates flat bars
  and corrupts MA/ATR. Gaps are exposed as `is_gap_bar`/`is_partial` inputs instead.
- **AD-5 CFD parameter grid (whitelist).** *Why:* removes US-equity habit parameters and
  keeps the feature space small, uniform, and auditable.
- **AD-6 float64 compute / float32 store.** *Why:* numerical stability + ~2× storage/IO
  savings for tree/NN consumers.
- **AD-7 Per-instrument strategy loops.** *Why:* 8 GB RAM cap; one instrument at a time.
- **AD-8 Registry-gated research.** *Why:* cheap to enforce, prevents duplicate work.

## 5. Critical invariants (must hold in any change)

1. **Causality.** No feature at bar `T` may depend on data after `T`. No `shift(-k)`,
   no repaint, no same-bar fill. 1h context uses only the last *closed* 1h bar
   (`m.close_time >= h.close_time`).
2. **Parquet-owns-data.** `metadata.duckdb` holds only the `data_tables` catalog +
   `main.*` Parquet-backed views.
3. **Grid closure.** All windows/pairs in `N_GRID = {6,12,24,60,120}` /
   `PAIRS = {(6,24),(12,60),(24,120)}`. `validate_grid()` rejects anything else.
4. **UTC + open-time grain.** Bars bucket on UTC boundaries; `time` = open time.
5. **Reproducibility.** Same inputs + config → same Parquet + same metrics.
6. **Secrets isolation.** Tokens only in git-ignored `config/setting.yml`.

## 6. Execution & dataflow sequence (end-to-end)

```
1. python -m pipeline.extract_oci            # or extract_oanda --map ...
      └─ writes data/raw_csv/<instrument>/**/*.csv
2. python -m pipeline.load_data              # 1m clean
      └─ writes data/all_data/all_data.parquet; registers main.all_data
3. python -m pipeline.aggregate_ohlcv        # 1m → 5m/1h
      └─ writes data/ohlcv_5m/*, data/ohlcv_1h/*; registers main.ohlcv_5m / main.ohlcv_1h
4. python -m pipeline.indicators             # features
      └─ writes data/ohlcv_5m_features/*, data/ohlcv_1h_features/*
5. python -m pipeline.sanity_check           # hard-integrity gate
6. python pipeline/profile_check.py          # judgement profiling (+ --raw reconciliation)
7. strategy/code/strategy_<x>.py --instrument ...
      └─ reads features via DuckDB; prints JSON metrics vs buy-hold
8. update strategy/STRATEGY_REGISTRY.md (status, result, last run)
```

One-shot: `scripts/backfill_and_check.sh` (extract_oanda --map → load_data →
aggregate_ohlcv → sanity_check → profile_check --raw).

## 7. Interface contracts

### 7.1 Strategy CLI (mandatory shape)
```
python strategy/code/strategy_<name>.py
  --instrument <SYM>      # default EUR_USD
  --timeframe <5m|1h>     # default 5m; selects the matching feature table
  --since <ISO date>      # optional lower bound on time
  --parquet <path>        # optional override; default depends on --timeframe
  --cost-bps <f>          # one-way cost, default 2
  --json <path>           # optional: also write the metrics block to file
```
The loader **must** verify the loaded table's bar length matches `--timeframe`
and fail loudly on a mismatch (a 1h rule run on 5m data must be impossible, not
silent). Outputs a JSON block containing at least:
`n_trades, win_rate_pct, total_return_pct, buyhold_return_pct, max_drawdown_pct,
avg_trade_return_pct, sharpe, exposure_pct`.

Accounting and these metrics are owned by the **shared engine**
(`strategy/engine.py`); a strategy file declares only its signal rule and must
not re-implement the event loop or the metric formulas.

### 7.2 Metrics definitions (consistent across strategies)

All accounting: signal on closed bar `T` → fill at `open[T+1]`; one-way
transaction cost at **both** entry and exit (default 2 bps); one position at a
time; an open position is force-closed at the last bar's close.

- `buyhold_return_pct` = `close[-1] / open[0] - 1` (cost-free reference for the
  identical window).
- `total_return_pct` = compounded account equity over the window, in %.
- `max_drawdown_pct` = `max((peak_equity - equity) / peak_equity)`, in %.
- `win_rate_pct` = fraction of closed trades with net return > 0, in %.
- `avg_trade_return_pct` = mean per-trade net return, in %.
- `exposure_pct` = fraction of bars with a non-zero position, in %.
- `sharpe` = **annualised, trade-rate-based Sharpe**:
  `mean(tr) / std(tr, ddof=1) * sqrt(n_trades / span_years)`, where `tr` is the
  per-trade net return and `span_years` is the observed window length in
  fractional years. It depends on the *rate* of trading, not the total count —
  so the same edge over a longer sample gives the same Sharpe (it is
  comparable across strategies and windows). This supersedes the earlier
  `* sqrt(n_trades * 12)` form, which inflated with sample length.

### 7.3 DuckDB view contract
- `main.all_data`, `main.ohlcv_5m`, `main.ohlcv_1h`, `main.ohlcv_5m_features`,
  `main.ohlcv_1h_features` — all `SELECT * FROM read_parquet(<path>)`.
- Filter by `instrument` for fast per-instrument reads.

## 8. Technology stack

| Category | Choice |
|---|---|
| Language | Python 3.12 (`.venv`) |
| Compute / indicators | NumPy, pandas, **TA-Lib** (C lib), `pandas-ta-classic` |
| Storage / query | **Parquet** (pyarrow) + **DuckDB** (metadata + views) |
| Data sources | OCI Object Storage (PAR), OANDA API |
| Config | PyYAML, `python-dotenv` |
| Testing | pytest (unit, no network) |
| (future) AI | `google-genai` (not in the critical path) |

## 9. Error & edge handling

- **Ingestion:** per-request retries with backoff; per-instrument resume at failed month;
  `.empty` markers for candleless months; 401/403 aborts; non-zero exit on residual failure.
- **Data integrity:** `sanity_check` hard-fails (exit 1) on duplicate keys, self-contradicting
  OHLC, or over-full bars; gaps/partial bars are reported (expected) not fatal.
- **Lookahead:** `profile_check` demonstrates naive-vs-safe join; `indicators.py` enforces
  causality so safe joins are the default.
- **Locking:** `metadata.duckdb` is single-user; close VS Code DuckDB panels before writes.

## 10. Extensibility (how to add things without breaking invariants)

- **New indicator:** add to `pipeline/indicators.py` only if the window is in the grid;
  re-run `pipeline.indicators`; update `indicators.md` + `STRATEGY_BACKGROUND.md` §3 in
  the same change. Do **not** hand-write base formulas — extend TA-Lib usage.
- **New strategy:** follow `STRATEGY_BACKGROUND.md` §8 checklist (register → code → run on
  EUR_USD + a trending + a metal, full + 12m slice → report → update registry).
- **New timeframe:** extend the grid deliberately + regenerate both feature tables.

## 11. Security & data-handling
- Secrets only in git-ignored `config/setting.yml`. Rotate any token ever shared.
- No row data in DuckDB; Parquet files are the artifacts (large — git-ignored contents).

## 12. Test strategy
- **Unit (`tests/`):** pipeline public functions, mocked I/O, no network. `pytest -q`.
- **Integration gates:** `sanity_check` (hard) + `profile_check` (judgement) after each
  data rebuild.
- **Strategy:** each strategy is itself a runnable, assertion-free repro; report records
  results. (A formal OOS/harness is a roadmap item, see BRD §5.3.)
