# First 100 executable strategies — analysis before round 2

Date: 2026-10-31. Completed attempt: `SR-20261031-200/round1`.
Registry: `research/strategies/SR-20261031-200/round1_registry.yml`.

## Result

All 100 rules completed all 4,500 matrix cells: three assets, five windows
and three costs. **All 100 are rejected for promotion.** None beat buy-and-hold
on any asset over the full window at 2 bps. Sixty-nine rules exceeded the
300-full-history-trade ceiling on at least one asset. None met the legacy
full/recent bar or the added cross-asset/time inference criterion.

The primary test grid has 600 rows; 531 meet the fixed sample/week support
rule. The minimum positive-outperformance p-value is 0.210497; the minimum
accumulated q-value is 1.0. The second round's 600 tests remain reserved with
`p=1` in the same 5,610-test family. The configuration tally is now
827 + 100 = **927**. Repeated windows and cost scenarios are not independent
strategy configurations.

## What failed

| Entry model | Rules | Median across-rule full return averaged across assets, c2 | Median across-rule mean weekly Sharpe | Mean training cost drag, percentage points |
|---|---:|---:|---:|---:|
| Candle confirmation / efficiency regime | 50 | -8.465% | -0.538 | 8.180 |
| Higher-timeframe direction alignment | 50 | -22.908% | -0.903 | 14.502 |

These equal-weight diagnostic averages are not a portfolio or an estimate of
cross-market alpha. In particular, arithmetic BTC return outliers can dominate
mean return; weekly Sharpe, individual asset behavior and benchmark differences
must accompany them.

| Asset | Median full trades | Median full c2 return | Positive-return rules / 100 | Full buy-and-hold |
|---|---:|---:|---:|---:|
| EUR_USD | 496.5 | -20.33% | 4 | +2.96% |
| BTC_USD | 592.5 | -14.79% | 40 | +1257.33% |
| XAU_USD | 546.0 | -15.16% | 11 | +110.43% |

Even native-hour decisions did not make most strategies sparse enough.
Trading fresh feature states with one-day maximum holdings and finite ATR
exits can still generate hundreds of round trips. At 2 bps per side, weak
gross expectancy does not absorb that cost. Positive BTC returns frequently
remain far below its large buy-and-hold move.

Sparse apparent successes are not finalists. For example, SR1-028's maximum
full trade count is only five, and SR1-058's is 22. Their low trade counts and
modest positive averages cannot establish broadly repeated net alpha. No
strategy is fully empty across all assets, but seven individual strategy/asset
combinations are empty and remain included in the evidence.

## What this does and does not say about the fifty features

The backtest tests whether one particular threshold/context/exit system can
turn a feature into trading returns. It does not overturn the original
feature decisions or prove universal uselessness. Magnitude/risk features
were given independent trend/reversion directions rather than treated as
buy/sell predictors. Neither context path produced sufficient benchmark-
relative results under this specification.

The first six months of 2020 supplied covariate calibration. No live position
opens before that calibration ends; full-history benchmark comparisons include
that initial cash period. Stops/profits use completed hourly closes and next
opens, not intrabar fills. Financing/slippage are not simulated and buy-and-hold
is cost-free while strategies pay both legs.

## Registered response for the next hundred

The adaptation rule was fixed before round-1 outcomes and consumes only
`development_train` rows, not validation returns or the leaderboard. Applying
it yields:

| New episode | Parents / new children | Reason |
|---|---:|---|
| Failure reversal | 50 | Negative mean training gross trade expectancy; test a later observed failure instead of immediate continuation. |
| Persistent context | 32 | Excessive training frequency or cost drag; require six consecutive qualifying context observations. |
| Pullback confirmation | 18 | Otherwise require a later pullback/resumption before entry. |
| Delayed confirmation | 0 | No parent is empty across all three training assets under the policy. |

Each parent has one newly registered child, with the same source idea/context
identity and a new causal event lifecycle. These are 100 related follow-up
configurations, not 100 independent mechanisms. Children may also fail or be
empty. No threshold search will be used to rescue them.

Review before round 2 added a completeness check for reversal confirmation:
a failure episode cannot open from a partial signal hour. This correction
does not change round 1's immediate-entry path. The source archive keeps the
original round-1 implementation; replay equality will verify that its active
rules remain numerically unchanged.

The original trade ledger's index/timestamp fields identify native bar opens.
An engine force-close at the final candle uses that candle's **close**, despite
sharing its bar index. The final audit will export explicit fill kind/time and
calendar duration so those boundary trades are not mistaken for open fills.
Accounting remains the shared engine's unchanged calculation.

## Evidence and next analysis

All matrix rows, trades, weekly series, position paths, behavioral-duplicate
groups, tests, source hashes and decisions are under
`research/strategies/SR-20261031-200/round1/`. Source and protocol snapshots are
preserved before subsequent code/context changes. Round 2 will analyze both
improvement and remaining benchmark/cost weaknesses; the protected holdout
remains unused.
