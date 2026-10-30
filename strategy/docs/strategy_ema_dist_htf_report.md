# S-125: ATR-normalized EMA trend with 1h SuperTrend

## Pre-registered hypothesis

A sustained normalized EMA-distance transition may carry when the slower 1h SuperTrend agrees.

Expected full-history EUR_USD trade count: **10–130**.  
Difference from prior work: Slow EMA-distance transition plus higher-timeframe SuperTrend.

## Evaluation

Fixed rule; selected config/variant: **pre-registered fixed rule**. The selected
variant for S-103..S-112 is the highest mean edge across the 18 sweep cells at
2 bps, selected after the sweep; treat its performance as selection-biased.
S-113..S-132 use the one pre-registered rule with no parameter sweep.

| Instrument | Window | Cost bps | Return % | Buy-hold % | Trades | Trades/yr | Max DD % | Weekly Sharpe |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| EUR_USD | full | 0 | -32.60 | 3.06 | 16236 | 2941.50 | 38.08 | -1.350 |
| EUR_USD | full | 2 | -99.90 | 3.06 | 16236 | 2941.50 | 99.90 | -18.170 |
| EUR_USD | full | 5 | -100.00 | 3.06 | 16236 | 2941.50 | 100.00 | -29.380 |
| EUR_USD | last_12m | 0 | -3.84 | 5.62 | 2937 | 2947.09 | 7.04 | -0.660 |
| EUR_USD | last_12m | 2 | -70.30 | 5.62 | 2937 | 2947.09 | 70.65 | -15.580 |
| EUR_USD | last_12m | 5 | -94.90 | 5.62 | 2937 | 2947.09 | 94.95 | -25.490 |
| BTC_USD | full | 0 | 127.25 | 1289.48 | 15952 | 2890.53 | 64.75 | 0.530 |
| BTC_USD | full | 2 | -99.62 | 1289.48 | 15952 | 2890.53 | 99.71 | -2.050 |
| BTC_USD | full | 5 | -100.00 | 1289.48 | 15952 | 2890.53 | 100.00 | -5.750 |
| BTC_USD | last_12m | 0 | 10.96 | 82.36 | 2815 | 2824.67 | 25.15 | 0.530 |
| BTC_USD | last_12m | 2 | -64.01 | 82.36 | 2815 | 2824.67 | 65.79 | -3.210 |
| BTC_USD | last_12m | 5 | -93.35 | 82.36 | 2815 | 2824.67 | 93.57 | -8.710 |
| XAU_USD | full | 0 | -8.52 | 110.58 | 15358 | 2783.87 | 46.26 | -0.110 |
| XAU_USD | full | 2 | -99.80 | 110.58 | 15358 | 2783.87 | 99.80 | -9.270 |
| XAU_USD | full | 5 | -100.00 | 110.58 | 15358 | 2783.87 | 100.00 | -18.670 |
| XAU_USD | last_12m | 0 | 41.90 | 34.41 | 2605 | 2613.95 | 4.70 | 3.200 |
| XAU_USD | last_12m | 2 | -49.94 | 34.41 | 2605 | 2613.95 | 50.67 | -5.450 |
| XAU_USD | last_12m | 5 | -89.51 | 34.41 | 2605 | 2613.95 | 89.55 | -15.130 |

At EUR_USD/full/2 bps: 16236 trades, return
-99.90% versus buy-hold
+3.06%. The full-window 2 bps edge count
is 0/3 instruments; last-12-month edge count is 0/3.

## Outcome

**REJECTED** — A pre-registered stop condition is met (trade count or no positive edge in a required window).

This is in-sample evidence only. No strategy was run on or promoted using the
OOS holdout. A candidate status is not a finalist nomination; human review is
required before any OOS eligibility change.

## Regime / opportunity distribution

Full-window 2 bps entry trades by month (all instruments): `[3721, 4086, 4328, 4201, 4358, 4211, 4310, 3717, 3706, 3671, 3584, 3653]`.

Full-window 2 bps entry trades by weekday, Mon–Sun (all instruments): `[9082, 9614, 9869, 9513, 8681, 0, 787]`.

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

N strategies tried before this one: **124**.
