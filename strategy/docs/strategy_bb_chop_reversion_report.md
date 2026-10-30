# S-118: Band re-entry in a choppy regime

## Pre-registered hypothesis

Band re-entry may mean-revert when both local and 1h regimes are non-trending.

Expected full-history EUR_USD trade count: **20–180**.  
Difference from prior work: Bollinger %B re-entry requires local choppiness and weak 1h ADX.

## Evaluation

Fixed rule; selected config/variant: **pre-registered fixed rule**. The selected
variant for S-103..S-112 is the highest mean edge across the 18 sweep cells at
2 bps, selected after the sweep; treat its performance as selection-biased.
S-113..S-132 use the one pre-registered rule with no parameter sweep.

| Instrument | Window | Cost bps | Return % | Buy-hold % | Trades | Trades/yr | Max DD % | Weekly Sharpe |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| EUR_USD | full | 0 | -5.71 | 3.06 | 4690 | 849.69 | 8.76 | -0.330 |
| EUR_USD | full | 2 | -85.55 | 3.06 | 4690 | 849.69 | 85.58 | -9.500 |
| EUR_USD | full | 5 | -99.13 | 3.06 | 4690 | 849.69 | 99.14 | -12.620 |
| EUR_USD | last_12m | 0 | -2.37 | 5.62 | 807 | 809.77 | 6.62 | -0.610 |
| EUR_USD | last_12m | 2 | -29.30 | 5.62 | 807 | 809.77 | 29.45 | -7.730 |
| EUR_USD | last_12m | 5 | -56.44 | 5.62 | 807 | 809.77 | 56.50 | -11.700 |
| BTC_USD | full | 0 | 17.03 | 1289.48 | 3738 | 677.33 | 35.73 | 0.250 |
| BTC_USD | full | 2 | -73.76 | 1289.48 | 3738 | 677.33 | 74.96 | -1.210 |
| BTC_USD | full | 5 | -97.21 | 1289.48 | 3738 | 677.33 | 97.24 | -3.270 |
| BTC_USD | last_12m | 0 | 24.34 | 82.36 | 805 | 807.76 | 8.53 | 2.070 |
| BTC_USD | last_12m | 2 | -9.89 | 82.36 | 805 | 807.76 | 12.48 | -0.920 |
| BTC_USD | last_12m | 5 | -44.41 | 82.36 | 805 | 807.76 | 45.62 | -4.960 |
| XAU_USD | full | 0 | -17.58 | 110.58 | 4353 | 789.05 | 22.11 | -0.640 |
| XAU_USD | full | 2 | -85.55 | 110.58 | 4353 | 789.05 | 85.59 | -6.520 |
| XAU_USD | full | 5 | -98.94 | 110.58 | 4353 | 789.05 | 98.94 | -11.100 |
| XAU_USD | last_12m | 0 | -6.27 | 34.41 | 709 | 711.43 | 11.26 | -1.360 |
| XAU_USD | last_12m | 2 | -29.42 | 34.41 | 709 | 711.43 | 29.55 | -7.440 |
| XAU_USD | last_12m | 5 | -53.87 | 34.41 | 709 | 711.43 | 53.94 | -11.820 |

At EUR_USD/full/2 bps: 4690 trades, return
-85.55% versus buy-hold
+3.06%. The full-window 2 bps edge count
is 0/3 instruments; last-12-month edge count is 0/3.

## Outcome

**REJECTED** — A pre-registered stop condition is met (trade count or no positive edge in a required window).

This is in-sample evidence only. No strategy was run on or promoted using the
OOS holdout. A candidate status is not a finalist nomination; human review is
required before any OOS eligibility change.

## Regime / opportunity distribution

Full-window 2 bps entry trades by month (all instruments): `[1046, 1044, 990, 1095, 1180, 1242, 1222, 1144, 935, 909, 868, 1106]`.

Full-window 2 bps entry trades by weekday, Mon–Sun (all instruments): `[2460, 2730, 2532, 2467, 2450, 0, 142]`.

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

N strategies tried before this one: **117**.
