# Business Requirements Document (BRD) — moneta / Nova

> **Audience:** developers, AI assistants, and stakeholders who need to understand
> *what* this project is for, *why*, and *how success is measured*.
> **Scope:** requirements only — no implementation detail. For architecture and
> design, see [SAD.md](SAD.md).
> **Companion docs:** [indicators.md](indicators.md) (feature spec),
> [data_profile.md](data_profile.md) (data facts),
> `strategy/STRATEGY_BACKGROUND.md` + `strategy/STRATEGY_REGISTRY.md` (strategy work).

## 1. Overview

**moneta / Nova** is an early-stage, ultra-lightweight engine for **discovering and
backtesting quantitative trading strategies** on OANDA CFD data. It exists to answer
one question honestly: *given clean, causal, well-instrumented market data, do any
simple, rules-based strategies produce an edge after real transaction costs — and if
so, which, on which instruments, at which timeframe?*

The system is deliberately **not** a black box. Every strategy is a small, readable,
self-contained backtest; every feature is defined by a written spec; and a shared
**registry** prevents the team (or an AI) from re-testing the same idea under new
clothes.

## 2. Problem statement

- **Costs kill most naive signals.** The reference strategy (S-01, 5m RSI-24
  mean-reversion) lost money on every instrument tested — not because the signal is
  meaningless, but because ~1,000 trades × ~4 bps round-trip ≈ **40% of equity paid in
  spread**, while the average trade edge was only ±0.03%. There is no systematic way
  to test whether a signal's *per-trade edge* exceeds its *per-trade cost* before
  spending time tuning it.
- **Lookahead / data-quality bugs are the #1 way to produce fake alpha.** Without
  enforced causality rules and explicit gap handling, backtests silently overstate
  performance.
- **Duplicate research.** Without a registry, the same indicator + timeframe + rule
  combination gets re-derived and re-tested repeatedly (by humans and AI).

Nova addresses all three: a **clean causal data layer**, **honest cost/benchmark
reporting**, and a **strategy registry** that makes "we already tried this" a first-class
fact.

## 3. Objectives

1. Provide a **reproducible, causal, gap-aware** feature dataset (5m signal + 1h context
   layers) for 21 CFD instruments, long enough (2020 → present) to span multiple regimes.
2. Enable **fast, low-friction** backtesting: one strategy = one self-contained CLI
   script that reads Parquet via DuckDB, runs in ~1 second per instrument, and reports a
   standard metrics block vs buy-and-hold.
3. Enforce **honest evaluation** by convention: no-lookahead execution, explicit
   transaction costs, buy-and-hold benchmark, and cost sensitivity near break-even.
4. **Prevent duplicate research** with a mandatory strategy registry and a
   new-strategy checklist.
5. Keep the system **ultra-lightweight and auditable**: no ML framework required, no
   network for backtests, human-readable code and specs.

## 4. Non-goals (explicitly out of scope, for now)

- No live/real-money trading, order routing, or execution infrastructure.
- No ML/dl model training or feature selection automation (feature matrix exists; models
  are a possible future consumer, not a current deliverable).
- No cross-sectional (multi-instrument simultaneous) portfolio optimization.
- No proprietary data acquisition beyond the existing OCI/OANDA sources.
- No web UI, API service, or deployment.

## 5. Scope (what "done" looks like per area)

### 5.1 Data pipeline — IN SCOPE (implemented)
- Bronze ingest from OCI (PAR) and OANDA (gap-fill + history backfill) to raw CSV.
- Load + clean to a de-duplicated 1-minute Parquet table.
- Aggregate to 5m and 1h OHLCV on UTC boundaries.
- Feature engineering to the two feature tables (259 / 234 columns).
- Integrity checks and profiling (sanity + profile checks).

### 5.2 Strategy research — IN SCOPE (implemented workflow)
- Self-contained backtest CLIs reading the feature Parquet.
- Standard metrics + buy-and-hold benchmark + cost handling.
- Strategy registry + background/checklist docs.

### 5.3 Out of scope (roadmap, not yet delivered)
- Automated strategy *generation* (LLM-driven idea generation).
- Vectorized/DuckDB-only backtest engine replacing per-instrument event loops.
- Formal deduplication engine (syntax fingerprint, signal-correlation).
- Out-of-sample / walk-forward validation harness.
- CI beyond local `pytest`.

## 6. Stakeholders

| Stakeholder | Interest |
|---|---|
| Research developer (primary user) | Fast, honest, non-duplicative strategy backtesting on clean data. |
| AI assistant (primary user) | Deterministic context from docs; unambiguous data contract and rules. |
| Data owner | Provenance, reproducibility, data-quality visibility. |

## 7. Requirements

### Functional

- **FR-1 Ingest.** Fetch market data from OCI (PAR URL) and OANDA (token, practice/live)
  into raw CSVs under `data/raw_csv/<instrument>/`, with pagination, retries, and
  idempotent (size-based / month-marker) skipping.
- **FR-2 Clean.** Produce a de-duplicated 1-minute table keyed on `(instrument, time)`,
  dropping `is_complete = false` rows.
- **FR-3 Aggregate.** Resample to 5m and 1h OHLCV bars on UTC boundaries, preserving
  `open`/`close` by first/last source bar, `high`/`low` by min/max, `volume` by sum, and
  `n_bars` for partial-bar detection.
- **FR-4 Feature.** Produce the 5m and 1h feature tables per the CFD parameter grid, with
  a causality-safe 1h→5m as-of join (`close_time`) and explicit gap/partial/session flags.
- **FR-5 Backtest.** Support self-contained CLI strategies that load one instrument's
  features, run a no-lookahead event loop (signal at closed bar `T`, fill at open of
  `T+1`), and emit a standard JSON metrics block vs buy-and-hold.
- **FR-6 Register.** Require every strategy to be registered (candidate → tested →
  rejected/parked) in the registry with key indicators, timeframe, and entry/exit logic.
- **FR-7 Check.** Provide integrity checks (duplicate keys, self-contradicting OHLC,
  over-full bars) and profiling (gaps, sessions, partial bars, lookahead safety, spread,
  data quality).

### Non-functional

- **NFR-1 Causality (hard).** No lookahead anywhere in the pipeline or any strategy.
- **NFR-2 Reproducibility.** Given the same raw data and config, outputs are identical.
- **NFR-3 Portability / lightness.** Runs on a small machine (2 CPU / ~8 GB); no network
  or ML dependency to backtest.
- **NFR-4 Auditability.** Every feature has a written spec and a named source; every
  strategy has a code file, a report, and a registry row.
- **NFR-5 Security.** Secrets (OANDA token, OCI PAR URL) live only in the git-ignored
  `config/setting.yml`; never committed. Tokens pasted anywhere shared must be revoked.
- **NFR-6 Data discipline.** Parquet is the data store; DuckDB holds metadata + views only.

## 8. Success criteria

| Criterion | Measure |
|---|---|
| Honest baseline established | Any near-zero result reports a 0/2/5 bps cost-sensitivity so the required edge is explicit. |
| No duplicate research | Every new idea is checked against the registry before coding; no `S-NN` ID is reused. |
| Causality preserved | A profile check shows the safe 1h→5m join has **no lookahead leak**. |
| Usable workflow | A new strategy goes idea → registered → running backtest with ~1 s/instrument. |
| Data integrity | Sanity check reports **0** duplicate keys, **0** bad OHLC bars, **0** over-full bars. |

## 9. Assumptions & constraints

- **Assumption:** 2 bps one-way is a reasonable OANDA CFD spread for most instruments
  (per-instrument spread can refine this).
- **Constraint:** machine has 2 CPUs / ~8 GB RAM → backtests must be per-instrument loops.
- **Constraint:** OANDA data is sparse on weekends / low liquidity → no synthetic filling;
  gaps are exposed as features instead.
- **Assumption:** `time` is the bar **open** time (UTC); close time = `time + interval`.

## 10. Risks

| Risk | Impact | Mitigation |
|---|---|---|
| Overfitting to in-sample (all 2020→26 is in-sample) | Fake alpha | Hold out last 12 months before any tuning; register and record status. |
| Cost assumption off per instrument | Misleading P&L | Report cost sensitivity; pull per-instrument spread via `profile_check`. |
| Stale docs vs code | Wrong AI decisions | "Code wins" rule + maintenance rule in [README.md](README.md). |
| Single-user DuckDB lock | Write failures | Close DuckDB panels before writes (documented). |

## 11. Roadmap (post-MVP, not committed)

1. Slow the signal (1h) / add regime / squeeze filters — see `strategy_rsi_report.md` §5.
2. Out-of-sample / walk-forward validation harness.
3. Optional LLM-assisted strategy idea generation (still gated by the registry).
4. Optional DuckDB-vectorized backtest engine for large-scale sweeps.
5. CI (lint + `pytest`) and automated doc-vs-code drift check.
