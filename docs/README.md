# docs/ — Documentation Entry Point (read me first)

> **Purpose:** This is the single entry point for any AI assistant (or human)
> working in this repo. **Read this file first**, then open only the specific
> document relevant to your task. The goal is that you can complete a task by
> reading documentation, without scanning the whole codebase.

Latest follow-up: [verification of repo_review_20261031_initial.md](repo_review_20261031_verification.md),
including full-day boundaries, implementation/data freezes and versioned replays.
The earlier [verification of all three legacy reviews](review_verification_20261031.md)
records the first hardening pass. Its [audit](research_audit_20261031.json), now
extended with gross/net diagnostics, is reproducible without market data.

The first [P1 indicator research report](indicator_research_20261031_report.md)
covers nine feature families, empirical development results and three review
passes. Its [definition/protocol spec](indicator_research_P1_spec.md) describes
the additive research layer; the original Gold column counts remain unchanged.

All fifty first versions in the [idea catalogue](indicator_idea_catalogue_20261031.md)
are now implemented and evaluated. The [results/progress report](indicator_catalogue_results_20261031.md)
records 2,250 comparisons, 734 passing tests, five deterministic replays and
final decisions: 43 reject, 7 revise. No idea met the full replication rule.

The follow-up [two-round strategy/feature study](../strategy/docs/strategy_research_200_20261031_results.md)
completed 100 + 100 executable strategies and research of their 200 composite
entry features. All 9,000 backtest cells completed; zero rules qualify for
promotion. Event research records 199 revise / 1 reject / 0 keep, mainly due
to inadequate matching/sample support. The [200-rule index](../strategy/docs/strategy_research_200_20261031_index.md)
links every hypothesis, cost result and decision. This adds related rules
from the existing fifty feature families, not 200 independent new indicators.

## What is this project?

**moneta / Nova** is an early-stage, ultra-lightweight **quantitative strategy
discovery and backtesting engine** on OANDA CFD data across 21 instruments
(FX, precious metals, crude oil, equity-index CFDs, crypto). A deterministic
pipeline produces two feature tables — a **5-minute signal layer** and a
**1-hour context layer** — and strategies are researched by reading those Parquet
tables and running bar-by-bar, **no-lookahead** backtests against buy-and-hold.

It is **not** a production trading system and **not** an ML platform yet. It is a
research rig: clean causal data + a self-describing feature matrix + a strategy
registry that prevents duplicate work.

## Read-order map (task → file)

| If your task is… | Read this first | Then, if needed |
|---|---|---|
| Understand the business case, goals, scope, success criteria | [BRD.md](BRD.md) | [SAD.md](SAD.md) |
| Understand system architecture, data flow, components, invariants | [SAD.md](SAD.md) | [indicators.md](indicators.md) |
| **Generate a new strategy** (AI task: "follow the action list and do the downstream jobs") | `strategy/generated_strategy.md` (the *what*) → `strategy/WORKFLOW.md` (the *how*: steps 0–7 with gates) | `strategy/STRATEGY_REGISTRY.md`, [data_profile.md](data_profile.md) |
| **Declare a new strategy** (preferred path — a strategy is *data*, not a file) | [`config/strategy_specs.yml`](../config/strategy_specs.yml) → `strategy/rule_spec.py` | [REFACTOR_PLAN.md](REFACTOR_PLAN.md) (why the spec language is the target architecture) |
| Understand the **refactor direction** and why the strategy catalogue is being restructured | [REFACTOR_PLAN.md](REFACTOR_PLAN.md) | `strategy/rule_spec.py`, `strategy/rule_engine.py` |
| Design / code / test a **new strategy** by hand | `strategy/STRATEGY_BACKGROUND.md` → `strategy/STRATEGY_REGISTRY.md` | [data_profile.md](data_profile.md) |
| Understand the **feature/indicator engine** (305/270 columns) | [indicators.md](indicators.md) | `pipeline/indicators.py` + `library/` (custom: Supertrend, PSAR) |
| Research **P1 indicators and conditional returns** | [indicator_research_20261031_report.md](indicator_research_20261031_report.md) | [indicator_research_P1_spec.md](indicator_research_P1_spec.md), `config/indicator_research.yml` |
| Choose **new indicator ideas across five styles** | [indicator_idea_catalogue_20261031.md](indicator_idea_catalogue_20261031.md) | Existing P1 results and `pipeline/indicators.py` |
| Check **all-50 implementation/testing/validation progress** | [indicator_catalogue_results_20261031.md](indicator_catalogue_results_20261031.md) | [validation contract](indicator_catalogue_validation_spec_20261031.md), `research/indicators/CATALOGUE-50-20261031/idea_progress.csv` |
| Inspect **100 + 100 executable strategies and entry-feature research** | [Combined results](../strategy/docs/strategy_research_200_20261031_results.md) | [Every rule/report](../strategy/docs/strategy_research_200_20261031_index.md), `research/strategies/SR-20261031-200/strategy_progress.csv` |
| Understand the **data** (rows, grain, dtypes, gotchas) | [data_profile.md](data_profile.md) | `pipeline/sanity_check.py`, `pipeline/profile_check.py` |
| Review the **roadmap** and verify external recommendations | [review_verification_20261031.md](review_verification_20261031.md) | Older `repo_review_*.md` files are historical; raw reviews live in `legacy/` (git-ignored) |
| Ingest / backfill data | `pipeline/README.md` | `pipeline/extract_oanda.py`, `load_data.py`, `aggregate_ohlcv.py` |

## Authoritative sources (do NOT trust this index over them)

When a fact here and in code disagree, **code wins**. The two files below are the
maintained single sources of truth for their domains:

- **Feature names, semantics, parameter grid, causality rules:**
  [indicators.md](indicators.md) and its implementation `pipeline/indicators.py`.
- **Data contract, hard strategy rules, new-strategy checklist:**
  `strategy/STRATEGY_BACKGROUND.md`.
- **Every strategy already tried (don't duplicate these):**
  `strategy/STRATEGY_REGISTRY.md`.
- **Backtest accounting & metric definitions (Sharpe, drawdown, …):**
  `strategy/engine.py` (the shared engine) — the single source of truth; a
  strategy file must not re-implement them.
- **Evaluation windows, OOS holdout, and the trial log:**
  `config/strategies.yml` + `strategy/trial_log.md`.

## Non-negotiable rules (must hold in any change you make)

1. **No lookahead.** A signal computed on a *closed* bar `T` may only be filled at
   the **open of bar `T+1`**. Never fill at bar `T`'s own close; never `shift(-k)`;
   never repaint. (Full rule: `indicators.md` §3.3, `STRATEGY_BACKGROUND.md` §4.)
2. **No synthetic data.** Missing bars stay missing. Use `is_gap_bar` /
   `is_partial` as *inputs*; never impute or forward-fill prices.
3. **1h→5m joins** only via `m.close_time >= h.close_time` (as-of on close time).
4. **Parquet is the data; DuckDB is metadata + views.** Never store row data in
   `data/metadata.duckdb`.
5. **CFD parameter grid is a hard whitelist:** `N ∈ {6, 12, 24, 60, 120}`;
   MACD pairs only `(6,24)`, `(12,60)`, `(24,120)`. Do not invent new windows.
6. **Costs:** assume **2 bps one-way** per fill unless a report states otherwise.
   Always report buy-and-hold for the identical window.

## Repo map (strategy-relevant)

```
moneta/
├── docs/                        ← you are here
│   ├── README.md                ← this index (read first)
│   ├── BRD.md                   ← business requirements
│   ├── SAD.md                   ← software architecture (incl. §7 metric contract)
│   ├── indicators.md            ← feature-engine spec (authoritative)
│   └── data_profile.md          ← data profile (rows/grain/dtypes)
├── strategy/
│   ├── generated_strategy.md    ← generation brief: the "what" (read first for AI strategy tasks)
│   ├── WORKFLOW.md              ← execution playbook: the "how" (steps 0–7, gates, failure paths)
│   ├── STRATEGY_BACKGROUND.md   ← read before coding a strategy (authoritative)
│   ├── STRATEGY_REGISTRY.md     ← register/check strategies (authoritative)
│   ├── engine.py                ← SHARED BACKTEST ENGINE (accounting + metrics; tested)
│   ├── rule_spec.py             ← CANONICAL STRATEGY SPEC (a strategy is data, not code)
│   ├── rule_engine.py           ← vectorised spec evaluation (bit-exact vs the per-bar oracle)
│   ├── strategy_spec_runner.py  ← run a spec end-to-end (load once / compute once / reuse cost tiers)
│   ├── trial_log.md             ← every attempt + "best-of-N" count (OOS discipline)
│   ├── code/strategy_rsi.py     ← reference strategy (S-01), built on engine.py
│   └── docs/strategy_rsi_report.md
├── pipeline/                    ← data pipeline (Bronze → features)
│   ├── extract_oci.py           ← OCI PAR download + unzip → raw CSV
│   ├── extract_oanda.py         ← OANDA gap-fill / history backfill → raw CSV
│   ├── load_data.py             ← raw CSV → all_data.parquet (1m) + DuckDB catalog
│   ├── aggregate_ohlcv.py       ← 1m → ohlcv_5m / ohlcv_1h
│   ├── indicators.py            ← 5m/1h feature engine (source of truth)
│   ├── sanity_check.py          ← integrity checks (dups, bad OHLC, gaps)
│   ├── profile_check.py         ← judgement profiling + safe 1h→5m join helper
│   └── table_catalog.py         ← DuckDB metadata + Parquet-backed views
├── config/
│   ├── setting.example.yml      ← template (oci.par_url, oanda.*); setting.yml is git-ignored
│   ├── history_map.yml          ← per-instrument backfill ranges
│   ├── indicators.yml           ← indicator/feature spec (matches pipeline/indicators.py)
│   ├── strategy_specs.yml       ← THE STRATEGY CATALOGUE (declarative specs; S-113..S-132)
│   └── strategies.yml           ← evaluation windows + OOS holdout + trial-log rules
├── tests/                       ← pytest suite: pipeline + engine + metrics + strategy rules + OOS gate + custom indicators (no network)
└── data/                        ← Parquet tables + metadata.duckdb (git-ignored contents)
```

## How to run things (repo root, `.venv`, Python 3.12)

```bash
.venv/bin/python strategy/code/strategy_rsi.py --instrument EUR_USD --since 2023-01-01 --until 2025-07-31
.venv/bin/python strategy/code/strategy_rsi.py --instrument EUR_USD --timeframe 1h --until 2025-07-31
.venv/bin/python -m pipeline.indicators                    # rebuild features (~5 min)
.venv/bin/python -m pytest tests/ -q                       # tests (pipeline + engine + metrics + strategy rules + OOS gate)
# ad-hoc query via the registered Parquet-backed views:
.venv/bin/python -c "import duckdb;print(duckdb.connect('data/metadata.duckdb', read_only=True).execute('SELECT * FROM main.ohlcv_5m_features LIMIT 3').fetchdf())"
```

Machine limits: **2 CPUs, ~8 GB RAM** — keep backtests a per-instrument loop; never
load all 21 instruments' 5m frames at once (>10 GB). No network is needed to backtest.

## Known gotchas

- **`config/indicators.yml`** is a readable spec, **not** code — it is not loaded at
  runtime. If it and `pipeline/indicators.py` ever disagree, the code wins; fix the YAML
  in the same change. (A legacy version of this file listed stale US-equity windows; it was
  rewritten to match the implemented CFD grid. Original preserved in the session artifacts
  folder as `indicators.yml.legacy.bak`.)
- **`metadata.duckdb` is single-user.** Close any VS Code DuckDB panel (file lock)
  before writing to it.
- **Session DST correction (2026-10-31):** the session helper now resolves the
  anchor's own local date. Stored Gold VWAP has not been rebuilt; new catalogue
  session research uses its corrected reference. See the all-50 results report
  before assuming historical stored VWAP has the corrected grouping.

## Maintenance rule for this documentation

When a change in code or data makes a statement in any doc stale, **update the
matching doc in the same change.** Prefer editing the authoritative file
(`indicators.md`, `STRATEGY_BACKGROUND.md`, `STRATEGY_REGISTRY.md`) over the index.
