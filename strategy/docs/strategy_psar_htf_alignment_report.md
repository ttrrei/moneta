# S-122: PSAR reversal aligned with 1h trend

## Pre-registered hypothesis

A slow PSAR reversal may be more selective when the closed 1h SuperTrend agrees.

Expected full-history EUR_USD trade count: **15–160**.  
Difference from prior work: Slow-PSAR direction flip gated by independent 1h SuperTrend context.

## Evaluation

Fixed rule; selected config/variant: **pre-registered fixed rule**. The selected
variant for S-103..S-112 is the highest mean edge across the 18 sweep cells at
2 bps, selected after the sweep; treat its performance as selection-biased.
S-113..S-132 use the one pre-registered rule with no parameter sweep.

| Instrument | Window | Cost bps | Return % | Buy-hold % | Trades | Trades/yr | Max DD % | Weekly Sharpe |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| EUR_USD | full | 0 | -30.37 | 3.06 | 11095 | 2010.10 | 35.96 | -1.250 |
| EUR_USD | full | 2 | -99.18 | 3.06 | 11095 | 2010.10 | 99.19 | -16.060 |
| EUR_USD | full | 5 | -100.00 | 3.06 | 11095 | 2010.10 | 100.00 | -34.430 |
| EUR_USD | last_12m | 0 | 0.35 | 5.62 | 1983 | 1989.81 | 6.13 | -0.010 |
| EUR_USD | last_12m | 2 | -54.60 | 5.62 | 1983 | 1989.81 | 55.40 | -12.370 |
| EUR_USD | last_12m | 5 | -86.19 | 5.62 | 1983 | 1989.81 | 86.31 | -26.530 |
| BTC_USD | full | 0 | -18.76 | 1289.48 | 9933 | 1799.87 | 66.94 | 0.140 |
| BTC_USD | full | 2 | -98.47 | 1289.48 | 9933 | 1799.87 | 99.09 | -1.370 |
| BTC_USD | full | 5 | -100.00 | 1289.48 | 9933 | 1799.87 | 100.00 | -3.660 |
| BTC_USD | last_12m | 0 | -16.14 | 82.36 | 1990 | 1996.83 | 36.50 | -0.790 |
| BTC_USD | last_12m | 2 | -62.17 | 82.36 | 1990 | 1996.83 | 69.59 | -3.580 |
| BTC_USD | last_12m | 5 | -88.54 | 82.36 | 1990 | 1996.83 | 90.69 | -7.840 |
| XAU_USD | full | 0 | 17.43 | 110.58 | 10405 | 1886.06 | 27.47 | 0.320 |
| XAU_USD | full | 2 | -98.17 | 110.58 | 10405 | 1886.06 | 98.31 | -6.740 |
| XAU_USD | full | 5 | -100.00 | 110.58 | 10405 | 1886.06 | 100.00 | -16.750 |
| XAU_USD | last_12m | 0 | 27.48 | 34.41 | 1922 | 1928.60 | 5.27 | 2.320 |
| XAU_USD | last_12m | 2 | -40.90 | 34.41 | 1922 | 1928.60 | 43.77 | -4.720 |
| XAU_USD | last_12m | 5 | -81.35 | 34.41 | 1922 | 1928.60 | 82.08 | -14.500 |

At EUR_USD/full/2 bps: 11095 trades, return
-99.18% versus buy-hold
+3.06%. The full-window 2 bps edge count
is 0/3 instruments; last-12-month edge count is 0/3.

## Outcome

**REJECTED** — A pre-registered stop condition is met (trade count or no positive edge in a required window).

This is in-sample evidence only. No strategy was run on or promoted using the
OOS holdout. A candidate status is not a finalist nomination; human review is
required before any OOS eligibility change.

## Regime / opportunity distribution

Full-window 2 bps entry trades by month (all instruments): `[2521, 2628, 2786, 2740, 2919, 2806, 2959, 2510, 2365, 2438, 2399, 2362]`.

Full-window 2 bps entry trades by weekday, Mon–Sun (all instruments): `[6101, 6416, 6333, 6332, 5727, 0, 524]`.

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

N strategies tried before this one: **121**.
