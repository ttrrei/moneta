# S-123: Wick rejection at Bollinger extremes

## Pre-registered hypothesis

Extreme band location plus rejection wick and close location may identify failed extensions.

Expected full-history EUR_USD trade count: **10–120**.  
Difference from prior work: Candlestick rejection pattern plus 60-bar band location.

## Evaluation

Fixed rule; selected config/variant: **pre-registered fixed rule**. The selected
variant for S-103..S-112 is the highest mean edge across the 18 sweep cells at
2 bps, selected after the sweep; treat its performance as selection-biased.
S-113..S-132 use the one pre-registered rule with no parameter sweep.

| Instrument | Window | Cost bps | Return % | Buy-hold % | Trades | Trades/yr | Max DD % | Weekly Sharpe |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| EUR_USD | full | 0 | 9.47 | 2.32 | 4970 | 891.68 | 10.21 | 0.350 |
| EUR_USD | full | 2 | -85.01 | 2.32 | 4970 | 891.68 | 85.03 | -6.980 |
| EUR_USD | full | 5 | -99.24 | 2.32 | 4970 | 891.68 | 99.24 | -18.660 |
| EUR_USD | last_12m | 0 | 1.60 | 5.62 | 860 | 862.95 | 4.97 | 0.560 |
| EUR_USD | last_12m | 2 | -27.97 | 5.62 | 860 | 862.95 | 28.07 | -7.520 |
| EUR_USD | last_12m | 5 | -57.01 | 5.62 | 860 | 862.95 | 57.07 | -20.370 |
| BTC_USD | full | 0 | -86.93 | 1538.05 | 4784 | 858.32 | 90.47 | -0.660 |
| BTC_USD | full | 2 | -98.07 | 1538.05 | 4784 | 858.32 | 98.48 | -1.510 |
| BTC_USD | full | 5 | -99.89 | 1538.05 | 4784 | 858.32 | 99.90 | -2.800 |
| BTC_USD | last_12m | 0 | -20.78 | 82.36 | 817 | 819.81 | 42.61 | -0.560 |
| BTC_USD | last_12m | 2 | -42.87 | 82.36 | 817 | 819.81 | 56.26 | -1.620 |
| BTC_USD | last_12m | 5 | -65.01 | 82.36 | 817 | 819.81 | 70.90 | -3.260 |
| XAU_USD | full | 0 | -14.52 | 113.27 | 4732 | 849.01 | 36.55 | -0.200 |
| XAU_USD | full | 2 | -87.12 | 113.27 | 4732 | 849.01 | 87.33 | -3.650 |
| XAU_USD | full | 5 | -99.25 | 113.27 | 4732 | 849.01 | 99.25 | -9.320 |
| XAU_USD | last_12m | 0 | -15.03 | 34.41 | 836 | 838.87 | 23.00 | -1.500 |
| XAU_USD | last_12m | 2 | -39.18 | 34.41 | 836 | 838.87 | 41.32 | -4.770 |
| XAU_USD | last_12m | 5 | -63.17 | 34.41 | 836 | 838.87 | 63.76 | -10.250 |

At EUR_USD/full/2 bps: 4970 trades, return
-85.01% versus buy-hold
+2.32%. The full-window 2 bps edge count
is 0/3 instruments; last-12-month edge count is 0/3.

## Outcome

**REJECTED** — A pre-registered stop condition is met (trade count or no positive edge in a required window).

This is in-sample evidence only. No strategy was run on or promoted using the
OOS holdout. A candidate status is not a finalist nomination; human review is
required before any OOS eligibility change.

## Regime / opportunity distribution

Full-window 2 bps entry trades by month (all instruments): `[1294, 1204, 1282, 1264, 1318, 1300, 1349, 1132, 1131, 1106, 1028, 1078]`.

Full-window 2 bps entry trades by weekday, Mon–Sun (all instruments): `[2753, 2907, 2992, 2859, 2679, 0, 296]`.

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

N strategies tried before this one: **122**.
