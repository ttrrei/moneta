# S-121: 1h MACD momentum in efficient regimes

## Pre-registered hypothesis

A normalized 1h MACD zero-cross may persist when the path is directionally efficient.

Expected full-history EUR_USD trade count: **10–140**.  
Difference from prior work: 1h normalized MACD cross confirmed by efficiency ratio.

## Evaluation

Fixed rule; selected config/variant: **pre-registered fixed rule**. The selected
variant for S-103..S-112 is the highest mean edge across the 18 sweep cells at
2 bps, selected after the sweep; treat its performance as selection-biased.
S-113..S-132 use the one pre-registered rule with no parameter sweep.

| Instrument | Window | Cost bps | Return % | Buy-hold % | Trades | Trades/yr | Max DD % | Weekly Sharpe |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| EUR_USD | full | 0 | 10.96 | 3.07 | 562 | 101.82 | 8.78 | 0.470 |
| EUR_USD | full | 2 | -11.38 | 3.07 | 562 | 101.82 | 14.68 | -0.490 |
| EUR_USD | full | 5 | -36.75 | 3.07 | 562 | 101.82 | 37.01 | -1.840 |
| EUR_USD | last_12m | 0 | -3.17 | 5.64 | 101 | 101.35 | 6.27 | -1.130 |
| EUR_USD | last_12m | 2 | -7.00 | 5.64 | 101 | 101.35 | 9.18 | -2.080 |
| EUR_USD | last_12m | 5 | -12.47 | 5.64 | 101 | 101.35 | 14.20 | -3.290 |
| BTC_USD | full | 0 | -25.52 | 1288.41 | 495 | 89.69 | 71.86 | 0.050 |
| BTC_USD | full | 2 | -38.90 | 1288.41 | 495 | 89.69 | 74.02 | -0.050 |
| BTC_USD | full | 5 | -54.60 | 1288.41 | 495 | 89.69 | 76.94 | -0.190 |
| BTC_USD | last_12m | 0 | -21.64 | 83.28 | 81 | 81.28 | 34.65 | -0.960 |
| BTC_USD | last_12m | 2 | -24.14 | 83.28 | 81 | 81.28 | 36.20 | -1.120 |
| BTC_USD | last_12m | 5 | -27.74 | 83.28 | 81 | 81.28 | 38.50 | -1.360 |
| XAU_USD | full | 0 | 0.92 | 110.29 | 466 | 84.47 | 16.97 | 0.060 |
| XAU_USD | full | 2 | -16.24 | 110.29 | 466 | 84.47 | 22.43 | -0.360 |
| XAU_USD | full | 5 | -36.67 | 110.29 | 466 | 84.47 | 40.06 | -0.990 |
| XAU_USD | last_12m | 0 | 2.13 | 34.37 | 81 | 81.28 | 4.99 | 0.320 |
| XAU_USD | last_12m | 2 | -1.13 | 34.37 | 81 | 81.28 | 7.00 | -0.120 |
| XAU_USD | last_12m | 5 | -5.82 | 34.37 | 81 | 81.28 | 10.02 | -0.770 |

At EUR_USD/full/2 bps: 562 trades, return
-11.38% versus buy-hold
+3.07%. The full-window 2 bps edge count
is 0/3 instruments; last-12-month edge count is 0/3.

## Outcome

**REJECTED** — A pre-registered stop condition is met (trade count or no positive edge in a required window).

This is in-sample evidence only. No strategy was run on or promoted using the
OOS holdout. A candidate status is not a finalist nomination; human review is
required before any OOS eligibility change.

## Regime / opportunity distribution

Full-window 2 bps entry trades by month (all instruments): `[113, 139, 124, 149, 110, 131, 161, 122, 120, 119, 127, 108]`.

Full-window 2 bps entry trades by weekday, Mon–Sun (all instruments): `[280, 315, 312, 282, 313, 0, 21]`.

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

N strategies tried before this one: **120**.
