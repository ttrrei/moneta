# S-112: Slow Efficiency-Ratio trend

## Pre-registered hypothesis

cross above 0.3

Expected full-history EUR_USD trade count: **see sweep results**.  
Difference from prior work: This was the registered strategy hypothesis; the report selects the best-of-eight variant after evaluation.

## Evaluation

Fixed rule; selected config/variant: **1h**. The selected
variant for S-103..S-112 is the highest mean edge across the 18 sweep cells at
2 bps, selected after the sweep; treat its performance as selection-biased.
S-113..S-132 use the one pre-registered rule with no parameter sweep.

| Instrument | Window | Cost bps | Return % | Buy-hold % | Trades | Trades/yr | Max DD % | Weekly Sharpe |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| EUR_USD | full | 0 | -12.48 | 3.07 | 220 | 39.86 | 18.47 | -0.700 |
| EUR_USD | full | 2 | -19.85 | 3.07 | 220 | 39.86 | 24.04 | -1.170 |
| EUR_USD | full | 5 | -29.76 | 3.07 | 220 | 39.86 | 32.41 | -1.850 |
| EUR_USD | last_12m | 0 | 4.21 | 5.64 | 47 | 47.16 | 2.32 | 0.960 |
| EUR_USD | last_12m | 2 | 2.27 | 5.64 | 47 | 47.16 | 2.75 | 0.530 |
| EUR_USD | last_12m | 5 | -0.57 | 5.64 | 47 | 47.16 | 3.39 | -0.110 |
| BTC_USD | full | 0 | 306.41 | 1288.41 | 202 | 36.60 | 38.10 | 0.870 |
| BTC_USD | full | 2 | 274.86 | 1288.41 | 202 | 36.60 | 38.23 | 0.830 |
| BTC_USD | full | 5 | 232.07 | 1288.41 | 202 | 36.60 | 38.41 | 0.770 |
| BTC_USD | last_12m | 0 | 27.92 | 83.28 | 35 | 35.12 | 15.17 | 1.260 |
| BTC_USD | last_12m | 2 | 26.15 | 83.28 | 35 | 35.12 | 15.17 | 1.200 |
| BTC_USD | last_12m | 5 | 23.52 | 83.28 | 35 | 35.12 | 15.17 | 1.110 |
| XAU_USD | full | 0 | 16.30 | 110.29 | 194 | 35.16 | 12.25 | 0.380 |
| XAU_USD | full | 2 | 7.61 | 110.29 | 194 | 35.16 | 14.13 | 0.210 |
| XAU_USD | full | 5 | -4.21 | 110.29 | 194 | 35.16 | 22.13 | -0.060 |
| XAU_USD | last_12m | 0 | 8.31 | 34.37 | 38 | 38.13 | 5.85 | 1.130 |
| XAU_USD | last_12m | 2 | 6.68 | 34.37 | 38 | 38.13 | 6.30 | 0.950 |
| XAU_USD | last_12m | 5 | 4.27 | 34.37 | 38 | 38.13 | 6.97 | 0.670 |

At EUR_USD/full/2 bps: 220 trades, return
-19.85% versus buy-hold
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

N strategies tried before this one: **111**.
