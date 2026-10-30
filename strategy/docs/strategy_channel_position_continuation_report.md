# S-119: Channel-position continuation

## Pre-registered hypothesis

A break of the prior 60-bar extreme may continue when the closed 1h context agrees.

Expected full-history EUR_USD trade count: **10–140**.  
Difference from prior work: 60-bar prior-extreme breakout with explicit 1h direction and bilateral entries.

## Evaluation

Fixed rule; selected config/variant: **pre-registered fixed rule**. The selected
variant for S-103..S-112 is the highest mean edge across the 18 sweep cells at
2 bps, selected after the sweep; treat its performance as selection-biased.
S-113..S-132 use the one pre-registered rule with no parameter sweep.

| Instrument | Window | Cost bps | Return % | Buy-hold % | Trades | Trades/yr | Max DD % | Weekly Sharpe |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| EUR_USD | full | 0 | 4.88 | 3.06 | 8603 | 1558.62 | 17.08 | 0.150 |
| EUR_USD | full | 2 | -96.64 | 3.06 | 8603 | 1558.62 | 96.65 | -10.710 |
| EUR_USD | full | 5 | -99.98 | 3.06 | 8603 | 1558.62 | 99.98 | -26.860 |
| EUR_USD | last_12m | 0 | 6.66 | 5.62 | 1575 | 1580.41 | 5.32 | 0.760 |
| EUR_USD | last_12m | 2 | -43.19 | 5.62 | 1575 | 1580.41 | 43.83 | -9.300 |
| EUR_USD | last_12m | 5 | -77.92 | 5.62 | 1575 | 1580.41 | 77.97 | -28.590 |
| BTC_USD | full | 0 | 1314.19 | 1289.48 | 7287 | 1320.42 | 60.01 | 1.190 |
| BTC_USD | full | 2 | -23.33 | 1289.48 | 7287 | 1320.42 | 80.14 | 0.150 |
| BTC_USD | full | 5 | -99.03 | 1289.48 | 7287 | 1320.42 | 99.26 | -1.540 |
| BTC_USD | last_12m | 0 | 32.88 | 82.36 | 1472 | 1477.05 | 26.69 | 1.120 |
| BTC_USD | last_12m | 2 | -26.25 | 82.36 | 1472 | 1477.05 | 36.34 | -0.260 |
| BTC_USD | last_12m | 5 | -69.51 | 82.36 | 1472 | 1477.05 | 70.10 | -2.520 |
| XAU_USD | full | 0 | 81.23 | 110.58 | 8148 | 1476.95 | 20.79 | 0.780 |
| XAU_USD | full | 2 | -93.04 | 110.58 | 8148 | 1476.95 | 93.41 | -3.530 |
| XAU_USD | full | 5 | -99.95 | 110.58 | 8148 | 1476.95 | 99.95 | -11.740 |
| XAU_USD | last_12m | 0 | 26.67 | 34.41 | 1624 | 1629.58 | 9.64 | 1.450 |
| XAU_USD | last_12m | 2 | -33.85 | 34.41 | 1624 | 1629.58 | 34.92 | -2.630 |
| XAU_USD | last_12m | 5 | -75.03 | 34.41 | 1624 | 1629.58 | 75.26 | -10.580 |

At EUR_USD/full/2 bps: 8603 trades, return
-96.64% versus buy-hold
+3.06%. The full-window 2 bps edge count
is 0/3 instruments; last-12-month edge count is 0/3.

## Outcome

**REJECTED** — A pre-registered stop condition is met (trade count or no positive edge in a required window).

This is in-sample evidence only. No strategy was run on or promoted using the
OOS holdout. A candidate status is not a finalist nomination; human review is
required before any OOS eligibility change.

## Regime / opportunity distribution

Full-window 2 bps entry trades by month (all instruments): `[2013, 1947, 2275, 2114, 2212, 2003, 2283, 1859, 1765, 1846, 1923, 1798]`.

Full-window 2 bps entry trades by weekday, Mon–Sun (all instruments): `[4607, 4897, 4787, 4832, 4431, 0, 484]`.

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

N strategies tried before this one: **118**.
