# S-111: Ultra-fast Williams-%R rebound

## Pre-registered hypothesis

cross above −60

Expected full-history EUR_USD trade count: **see sweep results**.  
Difference from prior work: This was the registered strategy hypothesis; the report selects the best-of-eight variant after evaluation.

## Evaluation

Fixed rule; selected config/variant: **1h**. The selected
variant for S-103..S-112 is the highest mean edge across the 18 sweep cells at
2 bps, selected after the sweep; treat its performance as selection-biased.
S-113..S-132 use the one pre-registered rule with no parameter sweep.

| Instrument | Window | Cost bps | Return % | Buy-hold % | Trades | Trades/yr | Max DD % | Weekly Sharpe |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| EUR_USD | full | 0 | -9.36 | 3.07 | 2494 | 451.83 | 24.59 | -0.230 |
| EUR_USD | full | 2 | -66.58 | 3.07 | 2494 | 451.83 | 67.30 | -2.870 |
| EUR_USD | full | 5 | -92.52 | 3.07 | 2494 | 451.83 | 92.52 | -6.350 |
| EUR_USD | last_12m | 0 | 3.18 | 5.64 | 441 | 442.51 | 8.97 | 0.350 |
| EUR_USD | last_12m | 2 | -13.51 | 5.64 | 441 | 442.51 | 16.51 | -1.880 |
| EUR_USD | last_12m | 5 | -33.62 | 5.64 | 441 | 442.51 | 33.99 | -4.900 |
| BTC_USD | full | 0 | 2833.79 | 1288.41 | 2184 | 395.74 | 50.46 | 1.430 |
| BTC_USD | full | 2 | 1124.70 | 1288.41 | 2184 | 395.74 | 57.87 | 1.120 |
| BTC_USD | full | 5 | 230.32 | 1288.41 | 2184 | 395.74 | 71.97 | 0.670 |
| BTC_USD | last_12m | 0 | 74.10 | 83.28 | 411 | 412.41 | 19.78 | 1.780 |
| BTC_USD | last_12m | 2 | 47.71 | 83.28 | 411 | 412.41 | 21.29 | 1.310 |
| BTC_USD | last_12m | 5 | 15.43 | 83.28 | 411 | 412.41 | 25.78 | 0.610 |
| XAU_USD | full | 0 | 51.99 | 110.29 | 2194 | 397.69 | 28.54 | 0.590 |
| XAU_USD | full | 2 | -36.81 | 110.29 | 2194 | 397.69 | 53.03 | -0.510 |
| XAU_USD | full | 5 | -83.06 | 110.29 | 2194 | 397.69 | 83.68 | -2.070 |
| XAU_USD | last_12m | 0 | 24.85 | 34.37 | 381 | 382.31 | 7.65 | 1.880 |
| XAU_USD | last_12m | 2 | 7.20 | 34.37 | 381 | 382.31 | 8.79 | 0.730 |
| XAU_USD | last_12m | 5 | -14.71 | 34.37 | 381 | 382.31 | 15.01 | -0.870 |

At EUR_USD/full/2 bps: 2494 trades, return
-66.58% versus buy-hold
+3.07%. The full-window 2 bps edge count
is 0/3 instruments; last-12-month edge count is 0/3.

## Outcome

**REJECTED** — A pre-registered stop condition is met (trade count or no positive edge in a required window).

This is in-sample evidence only. No strategy was run on or promoted using the
OOS holdout. A candidate status is not a finalist nomination; human review is
required before any OOS eligibility change.

## Regime / opportunity distribution

Monthly and weekday distribution was not included in the committed matrix output.

## Causality checklist

- Rule reads only index `i - 1` (the last closed bar).
- Cross conditions compare the current closed bar to the preceding closed bar;
  no negative shifts or future indexing are used.
- The shared engine executes fills at the next bar's open and applies costs to
  entry and exit.
- Only feature columns in the committed 5m/1h feature tables are loaded.
- No OOS window was requested; the configured in-sample windows are
  `full` and `last_12m`.

## Caveats

- The matrices are in-sample and the batch tests 20 additional hypotheses;
  observed best-of-batch performance is subject to multiple-testing bias.
- Buy-hold is a cost-free benchmark while strategy costs are charged at each
  fill, making the comparison conservative on the cost side.
- Results do not model slippage or live execution constraints and are
  instrument-specific.

N strategies tried before this one: **110**.
