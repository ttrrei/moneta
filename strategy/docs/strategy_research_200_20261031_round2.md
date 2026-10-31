# Second 100 executable strategies — results and reassessment

Date: 2026-10-31. Attempt: `SR-20261031-200/round2`.

The [first round](strategy_research_200_20261031_round1.md) completed before
these children were registered. A fixed policy used only its
`development_train` rows: 50 failure reversals, 32 persistent-context rules
and 18 pullback confirmations. Each keeps its parent's source idea/context
but changes the causal entry episode. Cooldown increases from six to twelve
observations. They are related follow-up configurations, not independent
mechanisms or a clean experiment isolating one design change.

## Result

All 100 completed all 4,500 matrix cells. **All 100 are rejected for
promotion.** None beat buy-and-hold on any asset over the full window at
2 bps per leg. Twenty-nine exceeded the maximum of 300 full-history trades
on at least one asset. Five rules were empty across all three assets;
32 of 300 full strategy/asset combinations were empty. Empty results remain
in the trial counts and statistical family.

There are 600 primary portfolio contrasts; 356 meet trade/week support.
The minimum positive-outperformance p-value is 0.266439; all q-values are
1.0, including the subsequently expanded joint family. Configuration trials
now total **827 + 100 + 100 = 1,027**. The experiment contributes 200 related
rules, 9,000 backtest cells and 1,200 portfolio primary contrasts.

## What changed

| Full-history diagnostic at c2 | First 100 | Second 100 |
|---|---:|---:|
| Median trades across 300 strategy/asset combinations | 549.5 | 106.0 |
| Median exposure across those combinations | 15.265% | 2.655% |
| Median maximum drawdown across those combinations | 29.105% | 9.385% |
| Median across rules of arithmetic mean asset return | -14.607% | -1.268% |
| Mean training c0 minus c2 return, percentage points | 11.341 | 4.245 |
| Rules over 300 trades on any full asset | 69 | 29 |
| Empty full strategy/asset combinations | 7 | 32 |
| Full benchmark wins, out of 300 | 0 | 0 |

The main observable improvement is lower activity and exposure. These are
descriptive aggregates, not a combined portfolio, matched-risk comparison or
proof that timing improved. Different episode choices, longer cooldowns and
more empty paths all contribute. Smaller losses near cash are not alpha.

| New episode | Rules | Median across-rule mean asset return c2 | Median maximum full trades |
|---|---:|---:|---:|
| Failure reversal | 50 | -6.263% | 335.0 |
| Persistent context | 32 | -0.768% | 30.5 |
| Pullback confirmation | 18 | +0.420% | 8.0 |

The positive pullback median is especially sparse. Its median maximum trade
count is only eight over the full history. It cannot establish repeated
cross-asset/time profitability. The categories were selected from training
outcomes and contain different parents; their performance is not a randomized
comparison between entry models.

| Asset | Median full trades | Median full c2 return | Positive-return rules / 100 | Full buy/hold |
|---|---:|---:|---:|---:|
| EUR_USD | 100.0 | -3.55% | 7 | +2.96% |
| BTC_USD | 105.5 | 0.00% | 44 | +1257.33% |
| XAU_USD | 110.0 | -2.55% | 22 | +110.43% |

Twenty rules represent each original style in each round:

| Source style | First-round median mean asset return | Second-round median mean asset return | Second-round empty asset combinations |
|---|---:|---:|---:|
| Candle structure | -11.938% | -0.787% | 10 |
| Compression | -20.220% | -1.233% | 3 |
| Mean reversion | -8.802% | -0.030% | 13 |
| Persistence | -18.722% | -2.265% | 6 |
| Trend | -15.647% | -6.030% | 0 |

These summaries do not identify a winning style. Most seemingly better
groups also lose sample size and exposure. Behavioral duplicate paths,
including zero-trade paths, are recorded per asset; semantically distinct
definitions are not assumed to be independent observations.

## Separate entry-feature research

Following the user's clarification to do **both execution and research**, all
200 composite entry signals were also studied independently of portfolio
holdings/cooldowns. The entry-feature protocol was fixed before its own
forward-label analysis, after the portfolio outcomes were already available.
This is exploratory work on reused development history.

Of 1,200 entry-feature contrasts, 178 meet fixed matching/sample support:
128/300 and 12/300 for round 1's validation slices; 38/300 and 0/300 for
round 2. No new contrast survives the final 6,810-test joint correction.
The minimum entry-feature q-value is 0.597218. Decisions are **199 revise,
1 reject, 0 keep**. `revise` records inadequate two-asset/two-time support;
it does not establish that all these inputs have no information.

The short validation slice, 24-observation non-overlap rule and six frozen
direction/volatility matching strata leave many empty or too-small cells.
Increasing sample requirements after results or silently dropping those
cells would change the target population. The study retains them explicitly.

## What this supports next

Retain the full failure evidence. Do not nominate an OOS finalist or select
a sparse highest-return example. The next useful development step is to
design an adequately powered conditional-information study before adding
more entry intersections. Any simpler matching population, different target,
horizon or risk budget needs a new recorded hypothesis and trial accounting;
it must not overwrite this attempt. PS-08 remains an original movement-context
lead, without a demonstrated executable edge from either new round.

The [combined report](strategy_research_200_20261031_results.md),
[all-rule index](strategy_research_200_20261031_index.md) and
[progress CSV](../../research/strategies/SR-20261031-200/strategy_progress.csv)
connect every definition to its costs, validation results and decision.
