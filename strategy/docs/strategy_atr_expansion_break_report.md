# S-126: ATR expansion plus prior-extreme breakout

## Pre-registered hypothesis

Local volatility expansion relative to its slower baseline may confirm a channel break.

Expected full-history EUR_USD trade count: **5–120**.  
Difference from prior work: Relative volatility expansion and prior-extreme break, distinct from fixed ATR bands.

## Evaluation

Fixed rule; selected config/variant: **pre-registered fixed rule**. The selected
variant for S-103..S-112 is the highest mean edge across the 18 sweep cells at
2 bps, selected after the sweep; treat its performance as selection-biased.
S-113..S-132 use the one pre-registered rule with no parameter sweep.

| Instrument | Window | Cost bps | Return % | Buy-hold % | Trades | Trades/yr | Max DD % | Weekly Sharpe |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| EUR_USD | full | 0 | -6.25 | 2.32 | 467 | 83.79 | 6.29 | -0.830 |
| EUR_USD | full | 2 | -22.22 | 2.32 | 467 | 83.79 | 22.22 | -3.120 |
| EUR_USD | full | 5 | -41.23 | 2.32 | 467 | 83.79 | 41.23 | -5.550 |
| EUR_USD | last_12m | 0 | -1.98 | 5.62 | 100 | 100.34 | 2.36 | -1.400 |
| EUR_USD | last_12m | 2 | -5.82 | 5.62 | 100 | 100.34 | 5.92 | -4.030 |
| EUR_USD | last_12m | 5 | -11.31 | 5.62 | 100 | 100.34 | 11.31 | -7.000 |
| BTC_USD | full | 0 | -36.38 | 1538.05 | 1061 | 190.36 | 48.89 | -0.450 |
| BTC_USD | full | 2 | -58.38 | 1538.05 | 1061 | 190.36 | 62.99 | -0.940 |
| BTC_USD | full | 5 | -77.98 | 1538.05 | 1061 | 190.36 | 79.45 | -1.670 |
| BTC_USD | last_12m | 0 | -5.15 | 82.36 | 146 | 146.50 | 18.45 | -0.480 |
| BTC_USD | last_12m | 2 | -10.53 | 82.36 | 146 | 146.50 | 20.03 | -1.070 |
| BTC_USD | last_12m | 5 | -18.03 | 82.36 | 146 | 146.50 | 23.15 | -1.970 |
| XAU_USD | full | 0 | -1.05 | 113.27 | 707 | 126.85 | 8.24 | -0.040 |
| XAU_USD | full | 2 | -25.43 | 113.27 | 707 | 126.85 | 27.88 | -1.530 |
| XAU_USD | full | 5 | -51.21 | 113.27 | 707 | 126.85 | 51.43 | -3.620 |
| XAU_USD | last_12m | 0 | -1.12 | 34.41 | 149 | 149.51 | 5.18 | -0.240 |
| XAU_USD | last_12m | 2 | -6.84 | 34.41 | 149 | 149.51 | 9.30 | -1.740 |
| XAU_USD | last_12m | 5 | -14.80 | 34.41 | 149 | 149.51 | 15.17 | -3.800 |

At EUR_USD/full/2 bps: 467 trades, return
-22.22% versus buy-hold
+2.32%. The full-window 2 bps edge count
is 0/3 instruments; last-12-month edge count is 0/3.

## Outcome

**REJECTED** — A pre-registered stop condition is met (trade count or no positive edge in a required window).

This is in-sample evidence only. No strategy was run on or promoted using the
OOS holdout. A candidate status is not a finalist nomination; human review is
required before any OOS eligibility change.

## Regime / opportunity distribution

Full-window 2 bps entry trades by month (all instruments): `[192, 168, 194, 224, 242, 209, 205, 166, 165, 154, 160, 156]`.

Full-window 2 bps entry trades by weekday, Mon–Sun (all instruments): `[446, 422, 475, 457, 353, 0, 82]`.

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

N strategies tried before this one: **125**.
