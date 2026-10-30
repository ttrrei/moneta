# S-107: Slow Bollinger squeeze state

## Pre-registered hypothesis

enter at squeeze onset

Expected full-history EUR_USD trade count: **see sweep results**.  
Difference from prior work: This was the registered strategy hypothesis; the report selects the best-of-eight variant after evaluation.

## Evaluation

Fixed rule; selected config/variant: **1h**. The selected
variant for S-103..S-112 is the highest mean edge across the 18 sweep cells at
2 bps, selected after the sweep; treat its performance as selection-biased.
S-113..S-132 use the one pre-registered rule with no parameter sweep.

| Instrument | Window | Cost bps | Return % | Buy-hold % | Trades | Trades/yr | Max DD % | Weekly Sharpe |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| EUR_USD | full | 0 | 0.75 | 3.07 | 27 | 4.89 | 3.71 | 0.130 |
| EUR_USD | full | 2 | -0.34 | 3.07 | 27 | 4.89 | 3.79 | -0.050 |
| EUR_USD | full | 5 | -1.94 | 3.07 | 27 | 4.89 | 4.36 | -0.310 |
| EUR_USD | last_12m | 0 | 2.52 | 5.64 | 6 | 6.02 | 0.66 | 1.900 |
| EUR_USD | last_12m | 2 | 2.27 | 5.64 | 6 | 6.02 | 0.67 | 1.760 |
| EUR_USD | last_12m | 5 | 1.90 | 5.64 | 6 | 6.02 | 0.73 | 1.520 |
| BTC_USD | full | 0 | 43.67 | 1288.41 | 35 | 6.34 | 12.38 | 0.780 |
| BTC_USD | full | 2 | 41.67 | 1288.41 | 35 | 6.34 | 12.42 | 0.750 |
| BTC_USD | full | 5 | 38.73 | 1288.41 | 35 | 6.34 | 12.47 | 0.710 |
| BTC_USD | last_12m | 0 | 13.81 | 83.28 | 11 | 11.04 | 4.82 | 1.620 |
| BTC_USD | last_12m | 2 | 13.31 | 83.28 | 11 | 11.04 | 4.89 | 1.570 |
| BTC_USD | last_12m | 5 | 12.56 | 83.28 | 11 | 11.04 | 5.01 | 1.510 |
| XAU_USD | full | 0 | 2.83 | 110.29 | 39 | 7.07 | 2.75 | 0.230 |
| XAU_USD | full | 2 | 1.23 | 110.29 | 39 | 7.07 | 3.16 | 0.070 |
| XAU_USD | full | 5 | -1.11 | 110.29 | 39 | 7.07 | 3.91 | -0.170 |
| XAU_USD | last_12m | 0 | -0.89 | 34.37 | 10 | 10.03 | 2.54 | -0.480 |
| XAU_USD | last_12m | 2 | -1.29 | 34.37 | 10 | 10.03 | 2.66 | -0.700 |
| XAU_USD | last_12m | 5 | -1.88 | 34.37 | 10 | 10.03 | 2.86 | -1.000 |

At EUR_USD/full/2 bps: 27 trades, return
-0.34% versus buy-hold
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

N strategies tried before this one: **106**.
