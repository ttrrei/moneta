# moneta

> Early-stage scaffolding for **Nova**, an ultra-lightweight quantitative strategy discovery and optimization engine for forex, precious metals, crude oil, and equity indices.

## Current Status

**moneta / Nova** is a working research rig, not scaffolding: a deterministic
Bronze→feature pipeline plus a **shared, tested backtest engine** and a
registry-driven strategy loop. The full path
(raw CSV → 1m → 5m/1h → **305/270-column feature tables** → bar-by-bar
backtest → report) is implemented and has been run end-to-end at least once
(strategy **S-01**, see `strategy/docs/strategy_rsi_report.md`).

Implemented and tracked in Git:

- **Pipeline** (`pipeline/`): `extract_oci.py` (OCI PAR download + unzip → CSV),
  `extract_oanda.py` (OANDA gap-fill / history backfill → CSV), `load_data.py`
  (CSV → `all_data.parquet` + DuckDB catalog), `aggregate_ohlcv.py`
  (1m → 5m/1h), `indicators.py` (**feature engine**, source of truth),
  `sanity_check.py`, `profile_check.py`, `table_catalog.py`.
- **Strategy layer** (`strategy/`): `engine.py` (**shared backtest engine** —
  accounting + metric definitions, long & short, tested), `strategy_lib.py`
  (**shared data/eval core** every strategy builds on: parquet loading, the
  timeframe guard, bar-frame build, run wrapper, trade distribution),
  `strategy_rsi_lib.py` (S-01 rule), `strategy_supertrend_lib.py` (S-05),
  `strategy_ema_spread_lib.py` (S-06), `code/strategy_rsi.py` (S-01 CLI),
  `run_matrix.py` (automated 3×2×3 matrix runner → `strategy/results/`),
  `WORKFLOW.md` (steps 0–7 + gates), `STRATEGY_REGISTRY.md`,
  `STRATEGY_BACKGROUND.md`, `generated_strategy.md`, `trial_log.md` (OOS /
  best-of-N discipline), `docs/strategy_rsi_report.md`.
- **Config** (`config/`): `indicators.yml` (feature spec), `strategies.yml`
  (evaluation windows + OOS holdout + trial-log rules), `history_map.yml`,
  `setting.example.yml`.
- **Tests** (`tests/`): **120 passing** unit tests covering the pipeline
  (`extract_oci`, `extract_oanda`, `aggregate_ohlcv`), the feature engine
  (`test_indicators.py` — the six quality gates on synthetic data), and the
  shared engine's metric definitions (`test_metrics.py`). Run with `pytest -q`.
- **Docs** (`docs/`): BRD, SAD, `indicators.md` (spec), `data_profile.md`,
  and `README.md` (the AI-first index — **read that one first**).

Still **not** implemented (see Roadmap / BRD §5.3): automated strategy
*generation*, a vectorized/DuckDB-only engine, a formal dedup engine, and a
full walk-forward harness. **CI is now in place** (`.github/workflows/ci.yml`:
the data-free `check_results.py` gate + the `pytest` suite), and the
out-of-sample discipline (one-shot, fail-closed, finalist-only holdout gate in
`strategy/run_matrix.py` + `strategy/oos_ledger.json`, with the pass bar defined
once in `config/strategies.yml → oos.pass_criteria`) is enforced by that CI. A
full walk-forward harness is still future work.

Note on `legacy/` and `data/`: their *contents* are git-ignored
(`legacy/` holds earlier review notes and reference code; `data/` holds the
Parquet tables and `metadata.duckdb`). Everything above is tracked.
`config/setting.yml` (secrets) is git-ignored.

## What Nova is

A quantitative strategy discovery engine built around a multi-timeframe,
**state-transition** trading paradigm, with causality enforced end to end:

- **Trend / regime determination** on the 1-hour timeframe.
- **Entry execution** on the 5-minute timeframe.
- **Look-ahead elimination**: 1h features are locked to the last *fully closed*
  1h bar via an as-of join (`m.close_time >= h.close_time`), and a strategy
  signal on a closed bar `T` fills only at the **open of bar T+1**.

The strategy loop (read the docs → check the registry → register → code against
the shared engine → run the 3×3×2 matrix → report → record the outcome) is the
core, repeatable workflow. It is a **manual/AI-assisted** loop today, not yet a
fully autonomous generator.

Future goals (not yet implemented): AI-driven strategy generation, self-
describing YAML strategy schemas, a formal dedup engine, vectorized
DuckDB-only backtesting for large sweeps, and a walk-forward harness. The
Medallion layout is already effectively in place (Bronze CSV → `all_data` →
5m/1h → Gold feature tables) over Apache Parquet.

## Current project structure

```text
moneta/
├── docs/                        ← documentation (read docs/README.md first)
│   ├── BRD.md  SAD.md  indicators.md  data_profile.md
├── pipeline/                    ← data pipeline (Bronze → features)
│   ├── extract_oci.py  extract_oanda.py  load_data.py
│   ├── aggregate_ohlcv.py  indicators.py   ← feature engine (orchestrates + TA-Lib)
│   ├── sanity_check.py  profile_check.py  table_catalog.py
├── library/                  ← our own indicator library (TA-Lib gaps)
│   ├── supertrend.py  psar.py  utils.py    ← causal, pure-NumPy, tested in isolation
├── strategy/                    ← the research loop
│   ├── engine.py                ← shared backtest engine (accounting + metrics)
│   ├── strategy_lib.py          ← shared data/eval core every strategy uses
│   ├── strategy_rsi_lib.py      ← S-01 rule (shared by CLI + matrix runner)
│   ├── strategy_supertrend_lib.py  ← S-05 rule
│   ├── strategy_ema_spread_lib.py  ← S-06 rule
│   ├── code/strategy_rsi.py     ← S-01 reference strategy CLI
│   ├── run_matrix.py            ← 3 inst × 2 windows × 3 cost tiers → strategy/results/
│   ├── WORKFLOW.md  STRATEGY_REGISTRY.md  STRATEGY_BACKGROUND.md
│   ├── generated_strategy.md  trial_log.md
│   ├── results/S01|S05|S06/     ← per-cell JSON + matrix.md + summary.csv
│   └── docs/strategy_rsi_report.md
├── config/                      ← indicators.yml, strategies.yml, history_map.yml
├── tests/                       ← 140 pytest tests (pipeline + engine + metrics + strategy rules + OOS gate + custom indicators)
├── scripts/  data/  legacy/     ← helpers / runtime artifacts / notes (git-ignored contents)
└── requirement.txt
```

## Tech stack (from `requirement.txt`)

| Category | Technology |
|----------|------------|
| Language | Python 3.12+ |
| Data engine | DuckDB, Apache Parquet (pyarrow) |
| Object storage | OCI Object Storage |
| Indicators | **TA-Lib** (needs the C library), pandas-ta-classic |
| AI / LLM SDKs | `google-genai` |
| Utilities | NumPy, pandas, PyYAML, python-dotenv |
| Testing | pytest |

## Getting started

The whole project runs on **Python 3.12 in `.venv`**, invoked as
`.venv/bin/python` (POSIX). Install the dependencies first:

```bash
python -m venv .venv
pip install -r requirement.txt
# TA-Lib needs its C library — see docs/indicators.md §9. On most systems:
#   apt-get install libta-lib-dev   (or build from source into ~/.local/ta-lib)
```

Then run things from the repo root:

```bash
# Tests (120, no network needed):
.venv/bin/python -m pytest tests/ -q

# Rebuild the feature tables (only after data or spec changes; ~5 min, streams per instrument):
.venv/bin/python -m pipeline.indicators

# Backtest the reference strategy (5m by default; --timeframe 1h for 1h bars):
.venv/bin/python strategy/code/strategy_rsi.py --instrument EUR_USD --since 2023-01-01
.venv/bin/python strategy/code/strategy_rsi.py --instrument EUR_USD --timeframe 1h

# Run the standard matrix (3 instruments x 2 windows x 3 cost tiers) in one go:
.venv/bin/python strategy/run_matrix.py --strategy s01
# → strategy/results/S01/: per-cell JSON + matrix.md + summary.csv

# Ingest / backfill new data:
.venv/bin/python -m pipeline.extract_oanda --map config/history_map.yml   # download
.venv/bin/python -m pipeline.load_data                                    # → all_data.parquet
.venv/bin/python -m pipeline.aggregate_ohlcv                              # → 5m/1h
.venv/bin/python -m pipeline.sanity_check                                 # integrity checks
```

(On Windows use `.venv\Scripts\python.exe` instead of `.venv/bin/python`.)

## Configuration

Raw market data is fetched from OCI Object Storage using the PAR URL in `config/setting.yml`:

```yaml
oci:
  par_url: "https://objectstorage.ap-sydney-1.oraclecloud.com/p/.../n/.../b/.../o/"
```

Historical OANDA candles can be downloaded with `pipeline.extract_oanda`. Put
the OANDA API token in the ignored local `config/setting.yml` (start from
`config/setting.example.yml`):

```yaml
oanda:
  api_token: "YOUR_ROTATED_TOKEN"
  environment: "practice" # or live
  price: "MBA"
  smooth: false
```

Extract either a gap or a historical interval by specifying inclusive UTC
timestamps:

```bash
.venv/bin/python -m pipeline.extract_oanda --instrument GBP_USD \
  --from 2026-07-08T02:25:00Z --to 2026-07-08T20:47:00Z
```

The extractor paginates requests at OANDA's 5,000-candle limit and writes the
raw CSV schema under `data/raw_csv/<instrument>/`, ready for
`.venv/bin/python -m pipeline.load_data`. Re-running the same interval replaces
that interval's output file; loading deduplicates overlapping intervals by
`(instrument, time)`. Use `--output` to select a specific CSV destination or
`--json-out` to preserve the raw API response. `OANDA_API_TOKEN` and `--token`
can override the configured token.

### Backfilling earlier history

List the instruments (and how far back) in `config/history_map.yml`, then:

```bash
.venv/bin/python -m pipeline.extract_oanda --map config/history_map.yml --dry-run
.venv/bin/python -m pipeline.extract_oanda --map config/history_map.yml
.venv/bin/python -m pipeline.load_data
```

`from` sets how far back to go; `to: auto` (the default) stops just before the
earliest candle already ingested, so the new files never overlap existing data.
If nothing is ingested yet (empty DuckDB / no parquet), `to: auto` fills from
`from` up to now, so a fresh start works with any past start time.
Output is one CSV per instrument per UTC month; finished months are skipped, so
re-running resumes an interrupted backfill. After loading, re-run
`.venv/bin/python pipeline/profile_check.py --raw` to confirm the merged data has no gaps
at the seam and no conflicting duplicates.

Tokens should not be committed. Any token pasted into a chat, command history,
or other shared location should be revoked and replaced before use.

## Roadmap

Done (tracked in Git):

- [x] Bronze data ingestion (OCI + OANDA backfill) and dedup on `(instrument, time)`
- [x] DuckDB loading of raw CSVs (`load_data.py`) — Parquet is the data, DuckDB is metadata + views
- [x] Silver transformation — 1m resampled to 5m / 1h (`aggregate_ohlcv.py`)
- [x] Gold feature wide tables — **305 / 270 columns** (`pipeline/indicators.py` + `library/`, spec in `docs/indicators.md`)
- [x] **Shared, tested backtest engine** with standard metrics, cost handling, and buy-and-hold (`strategy/engine.py`)
- [x] Strategy registry + background/checklist + trial log + OOS holdout discipline
- [x] Automated tests — **140 passing** (pipeline, feature-engine quality gates, engine metrics, B6 entry guard, strategy rules, DST regression, OOS gate: finalist-only + one-shot + fail-closed + machine pass/fail)

Not yet done (future, see BRD §5.3 / §11):

- [ ] Full out-of-sample / walk-forward *harness* (a one-shot, finalist-only, machine-checked holdout gate now exists — `strategy/run_matrix.py`, `strategy/oos_ledger.json`, `config/strategies.yml → oos`; running a real holdout still needs the owner's go-ahead)
- [ ] Automated strategy *generation* (LLM-driven) — the loop is currently AI-assisted/manual
- [ ] Vectorized / DuckDB-only backtest engine for large-scale sweeps
- [ ] Formal deduplication engine (fingerprinting, signal correlation)
- [ ] Self-describing YAML strategy schema
- [x] CI (`pytest` + the data-free doc-vs-code drift check, `scripts/check_results.py`) — live in `.github/workflows/ci.yml`; a linter is the remaining piece

## License

[MIT License](LICENSE)
