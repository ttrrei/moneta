# S-110: Slow Stochastic-K (120-bar)

## Pre-registered hypothesis

cross above 55

Expected full-history EUR_USD trade count: **see sweep results**.  
Difference from prior work: This was the registered strategy hypothesis; the report selects the best-of-eight variant after evaluation.

## Evaluation

Fixed rule; selected config/variant: **wide_exit**. The selected
variant for S-103..S-112 is the highest mean edge across the 18 sweep cells at
2 bps, selected after the sweep; treat its performance as selection-biased.
S-113..S-132 use the one pre-registered rule with no parameter sweep.

| Instrument | Window | Cost bps | Return % | Buy-hold % | Trades | Trades/yr | Max DD % | Weekly Sharpe |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| EUR_USD | full | 0 | -11.52 | 2.32 | 2731 | 489.97 | 21.48 | -0.360 |
| EUR_USD | full | 2 | -70.32 | 2.32 | 2731 | 489.97 | 70.42 | -3.550 |
| EUR_USD | full | 5 | -94.24 | 2.32 | 2731 | 489.97 | 94.25 | -7.560 |
| EUR_USD | last_12m | 0 | 0.61 | 5.62 | 470 | 471.61 | 7.20 | 0.010 |
| EUR_USD | last_12m | 2 | -16.63 | 5.62 | 470 | 471.61 | 17.72 | -2.750 |
| EUR_USD | last_12m | 5 | -37.12 | 5.62 | 470 | 471.61 | 37.75 | -6.230 |
| BTC_USD | full | 0 | 3569.20 | 1538.05 | 2342 | 420.19 | 53.19 | 1.640 |
| BTC_USD | full | 2 | 1337.89 | 1538.05 | 2342 | 420.19 | 59.80 | 1.260 |
| BTC_USD | full | 5 | 252.74 | 1538.05 | 2342 | 420.19 | 70.19 | 0.710 |
| BTC_USD | last_12m | 0 | 112.20 | 82.36 | 432 | 433.48 | 14.03 | 2.660 |
| BTC_USD | last_12m | 2 | 78.53 | 82.36 | 432 | 433.48 | 15.97 | 2.100 |
| BTC_USD | last_12m | 5 | 37.77 | 82.36 | 432 | 433.48 | 20.13 | 1.260 |
| XAU_USD | full | 0 | 101.65 | 113.27 | 2404 | 431.32 | 15.03 | 1.110 |
| XAU_USD | full | 2 | -22.91 | 113.27 | 2404 | 431.32 | 50.55 | -0.360 |
| XAU_USD | full | 5 | -81.78 | 113.27 | 2404 | 431.32 | 84.49 | -2.420 |
| XAU_USD | last_12m | 0 | 39.17 | 34.41 | 392 | 393.35 | 5.45 | 2.820 |
| XAU_USD | last_12m | 2 | 18.98 | 34.41 | 392 | 393.35 | 6.31 | 1.500 |
| XAU_USD | last_12m | 5 | -5.96 | 34.41 | 392 | 393.35 | 15.98 | -0.320 |

At EUR_USD/full/2 bps: 2731 trades, return
-70.32% versus buy-hold
+2.32%. The full-window 2 bps edge count
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

N strategies tried before this one: **109**.
