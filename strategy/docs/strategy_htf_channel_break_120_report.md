# S-129: 1h SuperTrend with 5m 120-bar breakout

## Pre-registered hypothesis

A long-window 5m extreme break may persist when the closed 1h SuperTrend agrees.

Expected full-history EUR_USD trade count: **10–120**.  
Difference from prior work: 120-bar prior-extreme breakout gated by 1h SuperTrend; distinct from the 24-bar ADX-gated break.

## Evaluation

Fixed rule; selected config/variant: **pre-registered fixed rule**. The selected
variant for S-103..S-112 is the highest mean edge across the 18 sweep cells at
2 bps, selected after the sweep; treat its performance as selection-biased.
S-113..S-132 use the one pre-registered rule with no parameter sweep.

| Instrument | Window | Cost bps | Return % | Buy-hold % | Trades | Trades/yr | Max DD % | Weekly Sharpe |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| EUR_USD | full | 0 | -14.09 | 3.06 | 2236 | 405.10 | 19.38 | -0.620 |
| EUR_USD | full | 2 | -64.87 | 3.06 | 2236 | 405.10 | 65.40 | -4.140 |
| EUR_USD | full | 5 | -90.82 | 3.06 | 2236 | 405.10 | 90.93 | -8.790 |
| EUR_USD | last_12m | 0 | -0.86 | 5.62 | 378 | 379.30 | 6.28 | -0.310 |
| EUR_USD | last_12m | 2 | -14.77 | 5.62 | 378 | 379.30 | 16.56 | -3.260 |
| EUR_USD | last_12m | 5 | -32.07 | 5.62 | 378 | 379.30 | 33.28 | -7.140 |
| BTC_USD | full | 0 | 299.64 | 1289.48 | 1909 | 345.91 | 52.93 | 0.880 |
| BTC_USD | full | 2 | 86.23 | 1289.48 | 1909 | 345.91 | 57.46 | 0.480 |
| BTC_USD | full | 5 | -40.76 | 1289.48 | 1909 | 345.91 | 65.89 | -0.110 |
| BTC_USD | last_12m | 0 | 26.20 | 82.36 | 380 | 381.30 | 19.47 | 0.910 |
| BTC_USD | last_12m | 2 | 8.41 | 82.36 | 380 | 381.30 | 21.86 | 0.460 |
| BTC_USD | last_12m | 5 | -13.69 | 82.36 | 380 | 381.30 | 27.38 | -0.210 |
| XAU_USD | full | 0 | 38.62 | 110.58 | 1965 | 356.19 | 9.47 | 0.630 |
| XAU_USD | full | 2 | -36.84 | 110.58 | 1965 | 356.19 | 43.96 | -0.800 |
| XAU_USD | full | 5 | -80.57 | 110.58 | 1965 | 356.19 | 81.50 | -2.840 |
| XAU_USD | last_12m | 0 | 11.98 | 34.41 | 350 | 351.20 | 7.38 | 1.450 |
| XAU_USD | last_12m | 2 | -2.65 | 34.41 | 350 | 351.20 | 10.83 | -0.020 |
| XAU_USD | last_12m | 5 | -21.09 | 34.41 | 350 | 351.20 | 23.94 | -2.070 |

At EUR_USD/full/2 bps: 2236 trades, return
-64.87% versus buy-hold
+3.06%. The full-window 2 bps edge count
is 0/3 instruments; last-12-month edge count is 0/3.

## Outcome

**REJECTED** — A pre-registered stop condition is met (trade count or no positive edge in a required window).

This is in-sample evidence only. No strategy was run on or promoted using the
OOS holdout. A candidate status is not a finalist nomination; human review is
required before any OOS eligibility change.

## Regime / opportunity distribution

Full-window 2 bps entry trades by month (all instruments): `[503, 532, 530, 536, 560, 566, 544, 483, 469, 463, 451, 473]`.

Full-window 2 bps entry trades by weekday, Mon–Sun (all instruments): `[1078, 1251, 1305, 1190, 1176, 0, 110]`.

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

N strategies tried before this one: **128**.
