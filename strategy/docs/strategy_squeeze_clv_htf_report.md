# S-116: Squeeze release with close-location direction

## Pre-registered hypothesis

Compression release with close-location aligned with 1h direction may filter weak breakouts.

Expected full-history EUR_USD trade count: **10–160**.  
Difference from prior work: Squeeze release requires close-location and 1h trend alignment.

## Evaluation

Fixed rule; selected config/variant: **pre-registered fixed rule**. The selected
variant for S-103..S-112 is the highest mean edge across the 18 sweep cells at
2 bps, selected after the sweep; treat its performance as selection-biased.
S-113..S-132 use the one pre-registered rule with no parameter sweep.

| Instrument | Window | Cost bps | Return % | Buy-hold % | Trades | Trades/yr | Max DD % | Weekly Sharpe |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| EUR_USD | full | 0 | -8.31 | 3.06 | 2996 | 542.79 | 11.96 | -0.450 |
| EUR_USD | full | 2 | -72.34 | 3.06 | 2996 | 542.79 | 72.57 | -6.570 |
| EUR_USD | full | 5 | -95.42 | 3.06 | 2996 | 542.79 | 95.44 | -13.490 |
| EUR_USD | last_12m | 0 | 0.11 | 5.62 | 534 | 535.83 | 3.41 | -0.100 |
| EUR_USD | last_12m | 2 | -19.14 | 5.62 | 534 | 535.83 | 20.39 | -5.420 |
| EUR_USD | last_12m | 5 | -41.31 | 5.62 | 534 | 535.83 | 41.87 | -11.230 |
| BTC_USD | full | 0 | 76.50 | 1289.48 | 2848 | 516.06 | 46.91 | 0.530 |
| BTC_USD | full | 2 | -43.51 | 1289.48 | 2848 | 516.06 | 64.63 | -0.270 |
| BTC_USD | full | 5 | -89.77 | 1289.48 | 2848 | 516.06 | 91.93 | -1.460 |
| BTC_USD | last_12m | 0 | 25.59 | 82.36 | 577 | 578.98 | 11.21 | 1.480 |
| BTC_USD | last_12m | 2 | -0.29 | 82.36 | 577 | 578.98 | 16.13 | 0.320 |
| BTC_USD | last_12m | 5 | -29.47 | 82.36 | 577 | 578.98 | 30.64 | -1.400 |
| XAU_USD | full | 0 | -12.31 | 110.58 | 2717 | 492.50 | 20.46 | -0.330 |
| XAU_USD | full | 2 | -70.42 | 110.58 | 2717 | 492.50 | 70.50 | -3.370 |
| XAU_USD | full | 5 | -94.21 | 110.58 | 2717 | 492.50 | 94.21 | -7.690 |
| XAU_USD | last_12m | 0 | -0.60 | 34.41 | 483 | 484.66 | 4.90 | -0.080 |
| XAU_USD | last_12m | 2 | -18.06 | 34.41 | 483 | 484.66 | 19.50 | -3.280 |
| XAU_USD | last_12m | 5 | -38.68 | 34.41 | 483 | 484.66 | 39.65 | -7.690 |

At EUR_USD/full/2 bps: 2996 trades, return
-72.34% versus buy-hold
+3.06%. The full-window 2 bps edge count
is 0/3 instruments; last-12-month edge count is 0/3.

## Outcome

**REJECTED** — A pre-registered stop condition is met (trade count or no positive edge in a required window).

This is in-sample evidence only. No strategy was run on or promoted using the
OOS holdout. A candidate status is not a finalist nomination; human review is
required before any OOS eligibility change.

## Regime / opportunity distribution

Full-window 2 bps entry trades by month (all instruments): `[718, 762, 762, 737, 776, 709, 832, 675, 645, 672, 659, 614]`.

Full-window 2 bps entry trades by weekday, Mon–Sun (all instruments): `[1684, 1711, 1700, 1711, 1595, 0, 160]`.

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

N strategies tried before this one: **115**.
