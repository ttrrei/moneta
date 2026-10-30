# S-130: 1h channel-position break in efficient trend

## Pre-registered hypothesis

A sustained 1h channel-position break may be more reliable when path efficiency is high.

Expected full-history EUR_USD trade count: **5–100**.  
Difference from prior work: 60-bar channel position and efficiency ratio on 1h bars.

## Evaluation

Fixed rule; selected config/variant: **pre-registered fixed rule**. The selected
variant for S-103..S-112 is the highest mean edge across the 18 sweep cells at
2 bps, selected after the sweep; treat its performance as selection-biased.
S-113..S-132 use the one pre-registered rule with no parameter sweep.

| Instrument | Window | Cost bps | Return % | Buy-hold % | Trades | Trades/yr | Max DD % | Weekly Sharpe |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| EUR_USD | full | 0 | -8.01 | 3.07 | 50 | 9.06 | 11.51 | -0.760 |
| EUR_USD | full | 2 | -9.83 | 3.07 | 50 | 9.06 | 13.09 | -0.920 |
| EUR_USD | full | 5 | -12.49 | 3.07 | 50 | 9.06 | 15.41 | -1.160 |
| EUR_USD | last_12m | 0 | -4.19 | 5.64 | 13 | 13.04 | 6.48 | -1.690 |
| EUR_USD | last_12m | 2 | -4.69 | 5.64 | 13 | 13.04 | 6.86 | -1.850 |
| EUR_USD | last_12m | 5 | -5.43 | 5.64 | 13 | 13.04 | 7.41 | -2.070 |
| BTC_USD | full | 0 | 78.31 | 1288.41 | 82 | 14.86 | 33.02 | 0.520 |
| BTC_USD | full | 2 | 72.55 | 1288.41 | 82 | 14.86 | 33.18 | 0.500 |
| BTC_USD | full | 5 | 64.27 | 1288.41 | 82 | 14.86 | 33.42 | 0.460 |
| BTC_USD | last_12m | 0 | 3.97 | 83.28 | 13 | 13.04 | 15.39 | 0.300 |
| BTC_USD | last_12m | 2 | 3.43 | 83.28 | 13 | 13.04 | 15.53 | 0.270 |
| BTC_USD | last_12m | 5 | 2.63 | 83.28 | 13 | 13.04 | 15.73 | 0.230 |
| XAU_USD | full | 0 | 10.58 | 110.29 | 58 | 10.51 | 6.49 | 0.420 |
| XAU_USD | full | 2 | 8.04 | 110.29 | 58 | 10.51 | 7.35 | 0.330 |
| XAU_USD | full | 5 | 4.35 | 110.29 | 58 | 10.51 | 8.62 | 0.190 |
| XAU_USD | last_12m | 0 | 1.24 | 34.37 | 12 | 12.04 | 4.92 | 0.460 |
| XAU_USD | last_12m | 2 | 0.75 | 34.37 | 12 | 12.04 | 5.04 | 0.360 |
| XAU_USD | last_12m | 5 | 0.03 | 34.37 | 12 | 12.04 | 5.21 | 0.220 |

At EUR_USD/full/2 bps: 50 trades, return
-9.83% versus buy-hold
+3.07%. The full-window 2 bps edge count
is 0/3 instruments; last-12-month edge count is 0/3.

## Outcome

**REJECTED** — A pre-registered stop condition is met (trade count or no positive edge in a required window).

This is in-sample evidence only. No strategy was run on or promoted using the
OOS holdout. A candidate status is not a finalist nomination; human review is
required before any OOS eligibility change.

## Regime / opportunity distribution

Full-window 2 bps entry trades by month (all instruments): `[15, 19, 24, 16, 19, 17, 19, 13, 12, 13, 14, 9]`.

Full-window 2 bps entry trades by weekday, Mon–Sun (all instruments): `[38, 37, 43, 32, 36, 0, 4]`.

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

N strategies tried before this one: **129**.
