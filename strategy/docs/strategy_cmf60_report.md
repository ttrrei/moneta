# S-104: Slow CMF accumulation

## Pre-registered hypothesis

cross above 0.05

Expected full-history EUR_USD trade count: **see sweep results**.  
Difference from prior work: This was the registered strategy hypothesis; the report selects the best-of-eight variant after evaluation.

## Evaluation

Fixed rule; selected config/variant: **1h**. The selected
variant for S-103..S-112 is the highest mean edge across the 18 sweep cells at
2 bps, selected after the sweep; treat its performance as selection-biased.
S-113..S-132 use the one pre-registered rule with no parameter sweep.

| Instrument | Window | Cost bps | Return % | Buy-hold % | Trades | Trades/yr | Max DD % | Weekly Sharpe |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| EUR_USD | full | 0 | -10.16 | 3.07 | 296 | 53.63 | 23.30 | -0.360 |
| EUR_USD | full | 2 | -20.19 | 3.07 | 296 | 53.63 | 30.71 | -0.780 |
| EUR_USD | full | 5 | -33.18 | 3.07 | 296 | 53.63 | 40.58 | -1.380 |
| EUR_USD | last_12m | 0 | 2.15 | 5.64 | 51 | 51.18 | 6.02 | 0.290 |
| EUR_USD | last_12m | 2 | 0.09 | 5.64 | 51 | 51.18 | 6.70 | -0.050 |
| EUR_USD | last_12m | 5 | -2.93 | 5.64 | 51 | 51.18 | 7.92 | -0.550 |
| BTC_USD | full | 0 | 938.61 | 1288.41 | 255 | 46.21 | 41.01 | 1.190 |
| BTC_USD | full | 2 | 837.89 | 1288.41 | 255 | 46.21 | 41.38 | 1.140 |
| BTC_USD | full | 5 | 704.83 | 1288.41 | 255 | 46.21 | 43.38 | 1.080 |
| BTC_USD | last_12m | 0 | 29.03 | 83.28 | 53 | 53.18 | 33.83 | 0.970 |
| BTC_USD | last_12m | 2 | 26.32 | 83.28 | 53 | 53.18 | 34.33 | 0.900 |
| BTC_USD | last_12m | 5 | 22.37 | 83.28 | 53 | 53.18 | 35.07 | 0.800 |
| XAU_USD | full | 0 | 66.86 | 110.29 | 266 | 48.22 | 16.50 | 0.800 |
| XAU_USD | full | 2 | 50.02 | 110.29 | 266 | 48.22 | 17.80 | 0.640 |
| XAU_USD | full | 5 | 27.89 | 110.29 | 266 | 48.22 | 25.27 | 0.400 |
| XAU_USD | last_12m | 0 | 29.87 | 34.37 | 36 | 36.12 | 8.43 | 2.240 |
| XAU_USD | last_12m | 2 | 28.01 | 34.37 | 36 | 36.12 | 8.54 | 2.120 |
| XAU_USD | last_12m | 5 | 25.28 | 34.37 | 36 | 36.12 | 8.70 | 1.940 |

At EUR_USD/full/2 bps: 296 trades, return
-20.19% versus buy-hold
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

N strategies tried before this one: **103**.
