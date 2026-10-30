# S-108: Ultra-fast RSI-6 turn

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
| EUR_USD | full | 0 | -15.15 | 3.07 | 1488 | 269.58 | 23.33 | -0.480 |
| EUR_USD | full | 2 | -53.21 | 3.07 | 1488 | 269.58 | 54.01 | -2.290 |
| EUR_USD | full | 5 | -80.84 | 3.07 | 1488 | 269.58 | 80.84 | -4.750 |
| EUR_USD | last_12m | 0 | -0.76 | 5.64 | 278 | 278.95 | 8.67 | -0.230 |
| EUR_USD | last_12m | 2 | -11.20 | 5.64 | 278 | 278.95 | 13.09 | -1.830 |
| EUR_USD | last_12m | 5 | -24.84 | 5.64 | 278 | 278.95 | 25.60 | -4.080 |
| BTC_USD | full | 0 | 1425.03 | 1288.41 | 1372 | 248.60 | 49.00 | 1.290 |
| BTC_USD | full | 2 | 780.92 | 1288.41 | 1372 | 248.60 | 54.60 | 1.070 |
| BTC_USD | full | 5 | 286.75 | 1288.41 | 1372 | 248.60 | 64.54 | 0.750 |
| BTC_USD | last_12m | 0 | 52.37 | 83.28 | 254 | 254.87 | 17.36 | 1.520 |
| BTC_USD | last_12m | 2 | 37.65 | 83.28 | 254 | 254.87 | 18.28 | 1.220 |
| BTC_USD | last_12m | 5 | 18.19 | 83.28 | 254 | 254.87 | 19.65 | 0.770 |
| XAU_USD | full | 0 | 85.64 | 110.29 | 1354 | 245.43 | 19.22 | 1.000 |
| XAU_USD | full | 2 | 8.01 | 110.29 | 1354 | 245.43 | 37.60 | 0.160 |
| XAU_USD | full | 5 | -52.07 | 110.29 | 1354 | 245.43 | 61.50 | -1.050 |
| XAU_USD | last_12m | 0 | 31.05 | 34.37 | 232 | 232.80 | 4.93 | 2.360 |
| XAU_USD | last_12m | 2 | 19.43 | 34.37 | 232 | 232.80 | 6.07 | 1.600 |
| XAU_USD | last_12m | 5 | 3.91 | 34.37 | 232 | 232.80 | 10.08 | 0.510 |

At EUR_USD/full/2 bps: 1488 trades, return
-53.21% versus buy-hold
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

N strategies tried before this one: **107**.
