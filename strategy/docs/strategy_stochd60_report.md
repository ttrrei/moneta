# S-106: Slow Stochastic-D turn

## Pre-registered hypothesis

cross above 55

Expected full-history EUR_USD trade count: **see sweep results**.  
Difference from prior work: This was the registered strategy hypothesis; the report selects the best-of-eight variant after evaluation.

## Evaluation

Fixed rule; selected config/variant: **1h**. The selected
variant for S-103..S-112 is the highest mean edge across the 18 sweep cells at
2 bps, selected after the sweep; treat its performance as selection-biased.
S-113..S-132 use the one pre-registered rule with no parameter sweep.

| Instrument | Window | Cost bps | Return % | Buy-hold % | Trades | Trades/yr | Max DD % | Weekly Sharpe |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| EUR_USD | full | 0 | 2.38 | 3.07 | 312 | 56.52 | 16.90 | 0.100 |
| EUR_USD | full | 2 | -9.63 | 3.07 | 312 | 56.52 | 23.90 | -0.290 |
| EUR_USD | full | 5 | -25.06 | 3.07 | 312 | 56.52 | 34.70 | -0.870 |
| EUR_USD | last_12m | 0 | 4.46 | 5.64 | 58 | 58.20 | 4.57 | 0.790 |
| EUR_USD | last_12m | 2 | 2.06 | 5.64 | 58 | 58.20 | 5.24 | 0.420 |
| EUR_USD | last_12m | 5 | -1.43 | 5.64 | 58 | 58.20 | 6.34 | -0.130 |
| BTC_USD | full | 0 | 575.66 | 1288.41 | 311 | 56.35 | 54.58 | 0.980 |
| BTC_USD | full | 2 | 496.63 | 1288.41 | 311 | 56.35 | 55.87 | 0.930 |
| BTC_USD | full | 5 | 395.07 | 1288.41 | 311 | 56.35 | 57.73 | 0.850 |
| BTC_USD | last_12m | 0 | 17.62 | 83.28 | 60 | 60.21 | 45.12 | 0.670 |
| BTC_USD | last_12m | 2 | 14.83 | 83.28 | 60 | 60.21 | 45.53 | 0.600 |
| BTC_USD | last_12m | 5 | 10.77 | 83.28 | 60 | 60.21 | 46.15 | 0.510 |
| XAU_USD | full | 0 | 100.83 | 110.29 | 283 | 51.30 | 17.95 | 1.040 |
| XAU_USD | full | 2 | 79.33 | 110.29 | 283 | 51.30 | 21.83 | 0.880 |
| XAU_USD | full | 5 | 51.33 | 110.29 | 283 | 51.30 | 28.02 | 0.630 |
| XAU_USD | last_12m | 0 | 39.62 | 34.37 | 42 | 42.14 | 6.73 | 2.700 |
| XAU_USD | last_12m | 2 | 37.30 | 34.37 | 42 | 42.14 | 6.84 | 2.560 |
| XAU_USD | last_12m | 5 | 33.88 | 34.37 | 42 | 42.14 | 7.01 | 2.350 |

At EUR_USD/full/2 bps: 312 trades, return
-9.63% versus buy-hold
+3.07%. The full-window 2 bps edge count
is 0/3 instruments; last-12-month edge count is 1/3.

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

N strategies tried before this one: **105**.
