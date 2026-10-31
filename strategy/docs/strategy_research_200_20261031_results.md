# Fifty source ideas → 100 strategies → 100 follow-ups: final research record

Date: 2026-10-31. Study: `SR-20261031-200`.

**Completed both requested rounds: 200 executable portfolio strategies and
research of their 200 composite entry features. No strategy qualifies for
promotion, and no new entry-feature contrast survives joint correction.**
The second round trades less and loses less on typical paths; its much lower
exposure and sparse samples prevent interpreting that improvement as alpha.
No protected holdout was accessed and no live orders were placed.

Start with the [200-rule index](strategy_research_200_20261031_index.md) or
[progress CSV](../../research/strategies/SR-20261031-200/strategy_progress.csv)
for individual results. Each rule has a report with its hypothesis, parent,
operational rules, fitted cuts, costs, all twelve primary contrasts and both
decisions. The [registry](../STRATEGY_REGISTRY.md) and
[trial log](../trial_log.md) contain all 200 experimental rows.

## What was analyzed and built

The previous [fifty-idea study](../../docs/indicator_catalogue_results_20261031.md)
was feature research: 43 reject, 7 revise, no complete replication pass.
Its 22 isolated adjusted findings included 21 movement-magnitude/risk findings
and one directional finding. PS-08's EUR_USD activity surprise was a
movement-context lead. It did not specify a tradable direction.

This experiment consequently uses magnitude/risk features as context for
independently declared direction models. It does not relabel them as buy/sell
predictors or treat the old fifty as fifty previously profitable strategies.

| Stage | Implementation | Analysis / evidence |
|---|---|---|
| Source analysis | Inspect the 50 definitions, results, sparse populations and 827 legacy trials | [Initial analysis](strategy_research_200_20261031_initial_analysis.md) |
| First 100 | Two entry/context mechanisms for each source idea; 20 rules per style | [Round 1 findings](strategy_research_200_20261031_round1.md) |
| Second 100 | One causal follow-up per parent, selected by a fixed training-only policy | [Round 2 findings](strategy_research_200_20261031_round2.md) |
| Both research layers | Execute each portfolio and independently study its entry feature | [Registered contracts](strategy_research_200_20261031_design.md) |
| Final review | Deterministic replays, independent accounting and matched-sample reconstruction | Audit records linked below |

The five source styles are compression, trend, mean reversion, candle
structure and persistence. Each has 20 rules per round, 40 across both rounds.
These are **200 related configurations built from 50 primitive feature
families**, not 200 independent economic mechanisms or 200 newly invented
primitive indicators. Semantic hashes are unique; equal realized paths and
empty strategies remain explicitly recorded as behavioral duplicates.

The linked experimental namespace preserves mature S-series nomination and
saturation controls. User authorization for this bulk/new-feature experiment
does not grant any rule automatic finalist or OOS eligibility.

## Execution and validation contract

Use EUR_USD, BTC_USD and XAU_USD. Read complete 5m features at their exact
native 1h close; fill on the following native hourly open. Original 5m/1h
feature windows keep their units. Source data is the archived, hashed
development-only catalogue input. All data ends before 2025-08-01.

An important pre-execution correction was to recompute calibrated features
and tail/context cuts from **2020-01-01 through 2020-07-01 exclusive**. The
older feature-study cuts used data through 2022 and could not causally trade
in 2020. No new portfolio opens before July 2020. The full-history benchmark
still includes the initial cash/calibration period, as disclosed in every
report; it is not an equal-exposure benchmark.

Each rule holds at most one unit long or short. Stops are one frozen native
ATR24, profits two ATR, maximum holding 24 observed hourly bars. Decisions
use completed closes and fill at the next open. This does not simulate
intrabar stop execution or intrahour maximum drawdown. Cooldowns are six
observations in round 1 and twelve in round 2. Gaps/known near-close clocks
block entries; eventual completeness of the future fill candle is not read.

Five development windows are retained:

| Window | Inclusive start | Exclusive end | Use |
|---|---|---|---|
| Full | 2020-01-01 | 2025-08-01 | Legacy return/frequency diagnostics; initial calibration cash |
| Last 12 months | 2024-08-01 | 2025-08-01 | Legacy recent diagnostics |
| Development training | 2020-07-01 | 2023-01-01 | Fixed round-2 adaptation policy |
| Validation 1 | 2023-01-01 | 2025-01-01 | Primary development contrast |
| Validation 2 | 2025-01-01 | 2025-08-01 | Primary development contrast |

Native warm-up means actual first bars occur after configured starts. Each
window resets portfolio state but keeps the early fitted covariates. Full
and recent overlap; the development validation periods have also been used
in earlier research. Round 2 is adaptive development on reused history,
not fresh out-of-sample confirmation.

All strategies run at **0, 2 and 5 bps per leg** through the existing engine:
200 × 3 assets × 5 windows × 3 costs = **9,000 matrix cells**. Both legs pay
fees; buy-and-hold is cost-free. No financing, live spreads or slippage are
modeled. Existing reciprocal short equity accounting is retained and differs
from entry-notional cash P&L in the feature study.

## Portfolio findings

| Measure | First 100 | Second 100 |
|---|---:|---:|
| Completed matrix cells | 4,500 | 4,500 |
| Supported primary portfolio contrasts / 600 | 531 | 356 |
| Rules meeting legacy full/recent bar | 0 | 0 |
| Rules meeting complete research criteria | 0 | 0 |
| Full-history benchmark wins / 300 asset/rule pairs at c2 | 0 | 0 |
| Rules exceeding 300 full trades on any asset | 69 | 29 |
| Empty full asset/rule pairs | 7 | 32 |
| Completely empty rules | 0 | 5 |
| Median full trades across 300 asset/rule pairs | 549.5 | 106.0 |
| Median full exposure across those pairs | 15.265% | 2.655% |
| Median full maximum drawdown across those pairs | 29.105% | 9.385% |
| Median across rules of mean full asset return c2 | -14.607% | -1.268% |
| Minimum positive-outperformance p-value | 0.210497 | 0.266439 |
| Minimum portfolio q, final joint family | 1.0 | 1.0 |

Arithmetic asset averages are diagnostics, not combined-portfolio returns.
Lower activity reduces cost and risk, but also causes more empty/sparse
paths. Full c2 buy/hold is +2.96% EUR_USD, +1257.33% BTC_USD and +110.43%
XAU_USD. Even positive BTC strategy returns fail that declared benchmark.
Neither conditional event statistics nor smaller drawdown override the
original return/replication gate. A different risk-matched objective would
require a separately recorded study.

Round 1's candle-confirmation model lost less than trend alignment on the
median arithmetic asset-return diagnostic (-8.465% versus -22.908%), while
neither established benchmark-relative performance. The fixed training-only
response produced 50 failure reversals, 32 persistent contexts and 18 pullback
confirmations in round 2. The pullback median is positive (+0.420%), but its
median maximum full-history trade count is only eight. That is insufficient
for the required repeated validation. No highest-return sparse example is
being promoted.

## Entry-feature research findings

The user's “both, execute and research” clarification added a separate study
of the 200 causal entry-intent outputs. This protocol was frozen before its
forward-label analysis, after portfolio results were known. This timing is
recorded in `events.jsonl` and the feature manifest. It is not an external
preregistration before all prior outcomes.

Feature episodes ignore portfolio holdings, cooldowns and entry-clock
blocking. Labels require an adjacent next open and exit after 24 **observed**
native hours; weekends/session gaps may extend elapsed time. Events are
greedily thinned to non-overlap. Training-only volatility-tertile × direction
strata and event-count weights define the matched population. Controls use
a fixed non-overlap grid in both directions; same-clock controls share
bootstrap blocks. Feature cash returns are not portfolio P&L, and no stop or
profit exit is embedded in their target.

| Batch / validation slice | Tests | Supported |
|---|---:|---:|
| Round 1 / validation 1 | 300 | 128 |
| Round 1 / validation 2 | 300 | 12 |
| Round 2 / validation 1 | 300 | 38 |
| Round 2 / validation 2 | 300 | 0 |
| Total | 1,200 | 178 |

Support requires 30 samples in each arm, eight active weeks, at least ten in
every retained cell, identified training support and valid bootstrap coverage.
The short later slice and sparse intersections frequently fail these fixed
requirements. Final entry-feature decisions are **199 revise, 1 reject, 0
keep**. Only EF-SR1-079 has adequate support in both slices on at least two
assets and still fails replication. `revise` means inadequate evidence under
this design; it does not mean 199 features were proven useless.

The strongest local event contrast is EF-SR2-003 / CB-02 on XAU_USD,
validation 1: matched excess +21.667 bps, pointwise 95% interval
[11.058, 33.664], p=0.000429. Its joint q=**0.597218** and its later slice
lacks support. It is an unreplicated exploratory association, not a winner.
Its cash event result also does not overcome its failing portfolio results.

The final joint BY family contains **6,810 contrasts**: 4,410 prior feature
tests + 1,200 portfolio tests + 1,200 new entry-feature tests. Unsupported
tests remain p=1. Both new layers use 999,999 paired circular four-week
bootstrap draws and a positive one-sided centered-bootstrap p-value. The
original 5,610-family portfolio outputs are preserved; broader joint q-values
are separate files. The broader historical 827-config search, adaptive design
and reused history prevent treating this as a universal error guarantee for
the whole project. Historical fifty-idea decisions remain in their original
study; recomputed broader-family prior q-values are retained separately.

## Three review passes and corrections

1. **Before execution:** checked original findings, feature roles, causal
   availability, early calibration, native decision/fill units, exact
   timestamp alignment, multiplicity budget and full/recent overlap. Fixed
   the potential end-2022 calibration leakage before any portfolio results.
2. **After first-round analysis:** checked cost/churn/empty paths, training-only
   adaptation and episode distinctness. Added a complete-signal guard to
   prevent failure-reversal confirmation on a partial native hour. Original
   round-1 source was archived; its immediate-entry behavior replays unchanged.
   Failure/pullback arming preserves the parent's full setup so the two parent
   contexts do not collapse into one context-free rule. These corrections
   preceded round-2 outcomes.
3. **Final reassessment:** reran both portfolios and the complete event study;
   independently reconstructed trade accounting and every entry-feature
   matched population/mean. Preserved insufficient support as a separate
   result. Added explicit fill times for final forced closes: old raw ledger
   timestamps identify bar opens, while the final forced exit uses the
   candle close. The original frozen ledgers remain unchanged.

Evidence is recorded in
[portfolio/accounting audit](../../research/strategies/SR-20261031-200/validation_audit.json),
[independent feature audit](../../research/strategies/SR-20261031-200/entry_feature_validation_audit.json)
and [regression checks](../../research/strategies/SR-20261031-200/regression_checks.json).
The independent feature audit checks 600 training fits, 88,907 eligible
next-open labels, all 1,200 point estimates, 6,796 matched cells and 200
decisions. The portfolio audit independently checks 3,000 strategy/asset/window
accounting groups and 567,270 recorded fills across overlapping windows;
these are not 567,270 unique or independent market trades. It checks all 600
full position paths, 200 real-data prefixes and 600 entry-feature paths.
Each portfolio replay reproduces all 313 result files byte-for-byte. The event
replay reproduces all nine result files and three event Parquet hashes.
Round 1's only replay source difference is the documented completeness guard;
round 2's source hashes match exactly.

The full suite has **757 passing tests**; existing checker mutation
cases pass **40/40**. The mature S-series checker has zero failures and 22
pre-existing saturation warnings. It does not certify this experimental
namespace; the dedicated audits do that explicitly.

The protected OOS ledger remains empty, SHA256
`3148000cf7f66bc564211610f3423571c484e6eae979963577a3ba6a48236cd6`.
No finalist was nominated and no OOS token was created or consumed.

## Files, replay commands and continuing work

Implementation is additive: `strategy/research_rules.py` supplies causal
entry/state logic; `research_cohort.py` prepares hashed data and runs the
matrix; `research_statistics.py` handles portfolio inference;
`entry_feature_research.py` handles the separate conditional study. The shared
engine only gains optional equity capture, with unchanged default metrics.
Original Gold features and legacy strategy behavior remain covered by the
regression suite.

The configuration tally is **1,027**, starting from 827. The project records
132 mature S-series definitions and 200 experimental definitions; the old
fifty feature hypotheses are not counted again as portfolio configurations.
Related and empty new rules remain in that total. Replays are verification,
not newly selected variants.

The study directory retains protocols, complete registries, event chronology,
all costs/windows, c2 trades, weekly returns, position paths, primary tests,
unsupported cells, training fits, decisions and hashed source snapshots.
`execution_ledger_with_fill_times.csv` supplies actual forced-close fill
times and calendar duration in addition to the preserved raw ledgers.
Prepared/event data lives under the locally ignored
`data/strategy_research/SR-20261031-200/`; prepared hashes are archived in
the study. Source data must be present to rebuild or replay.

```bash
# New, empty output directory; the first command prepares data if absent.
OPENBLAS_NUM_THREADS=1 .venv/bin/python scripts/research_strategies_200.py --round 1 --out /tmp/new-study-200
OPENBLAS_NUM_THREADS=1 .venv/bin/python scripts/research_strategies_200.py --round 2 --out /tmp/new-study-200
# Use a separate copy of the prepared cache for a fully isolated event replay.
cp -a data/strategy_research/SR-20261031-200 /tmp/prepared-cache-copy
OPENBLAS_NUM_THREADS=1 .venv/bin/python scripts/research_entry_features_200.py --root /tmp/new-study-200 --cache /tmp/prepared-cache-copy --out /tmp/new-entry-feature-study

# Execute one registered rule through the shared engine.
.venv/bin/python -m strategy.code.strategy_research --strategy SR2-003 --instrument XAU_USD --timeframe 1h --window validation_2 --cost-bps 2 --json

# Independent checks; use a fresh audit output directory.
mkdir /tmp/new-audit-200
OPENBLAS_NUM_THREADS=1 .venv/bin/python scripts/verify_strategy_research_200.py --replay-root /tmp/new-study-200 --event-replay /tmp/new-entry-feature-study --out /tmp/new-audit-200/portfolio.json
OPENBLAS_NUM_THREADS=1 .venv/bin/python scripts/verify_strategy_entry_features_200.py --out /tmp/new-audit-200/entry-features.json
```

The useful outcome is a verified failure boundary, a reusable causal research
implementation and a clear sample-support gap. Further research should begin
with a fixed target and feasibility/power calculation before another large
batch. A simpler supported matching population or a context/risk target may
be worth a new registered study, but neither is claimed to work here. The
protected holdout stays reserved until a candidate actually clears the
existing development and nomination requirements.
