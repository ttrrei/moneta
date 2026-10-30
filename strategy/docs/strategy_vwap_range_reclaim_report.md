# S-117: Low-trend VWAP reclaim

## Pre-registered hypothesis

In weak 1h trend regimes, a VWAP reclaim may capture intraday mean reversion.

Expected full-history EUR_USD trade count: **30–240**.  
Difference from prior work: VWAP crossing only under low 1h ADX; not a VWAP-stretch threshold retune.

## Evaluation

Fixed rule; selected config/variant: **pre-registered fixed rule**. The selected
variant for S-103..S-112 is the highest mean edge across the 18 sweep cells at
2 bps, selected after the sweep; treat its performance as selection-biased.
S-113..S-132 use the one pre-registered rule with no parameter sweep.

| Instrument | Window | Cost bps | Return % | Buy-hold % | Trades | Trades/yr | Max DD % | Weekly Sharpe |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| EUR_USD | full | 0 | -12.99 | 3.06 | 17014 | 3082.45 | 16.93 | -0.460 |
| EUR_USD | full | 2 | -99.90 | 3.06 | 17014 | 3082.45 | 99.90 | -9.550 |
| EUR_USD | full | 5 | -100.00 | 3.06 | 17014 | 3082.45 | 100.00 | -11.600 |
| EUR_USD | last_12m | 0 | -0.79 | 5.62 | 3090 | 3100.61 | 5.84 | -0.260 |
| EUR_USD | last_12m | 2 | -71.18 | 5.62 | 3090 | 3100.61 | 71.60 | -9.940 |
| EUR_USD | last_12m | 5 | -95.49 | 5.62 | 3090 | 3100.61 | 95.55 | -12.340 |
| BTC_USD | full | 0 | 18511.00 | 1289.48 | 11409 | 2067.33 | 23.88 | 2.900 |
| BTC_USD | full | 2 | 94.01 | 1289.48 | 11409 | 2067.33 | 54.50 | 0.500 |
| BTC_USD | full | 5 | -99.79 | 1289.48 | 11409 | 2067.33 | 99.81 | -2.350 |
| BTC_USD | last_12m | 0 | 107.04 | 82.36 | 2396 | 2404.23 | 14.87 | 2.560 |
| BTC_USD | last_12m | 2 | -20.60 | 82.36 | 2396 | 2404.23 | 21.07 | -0.520 |
| BTC_USD | last_12m | 5 | -81.14 | 82.36 | 2396 | 2404.23 | 81.17 | -3.900 |
| XAU_USD | full | 0 | -20.72 | 110.58 | 15116 | 2740.00 | 32.84 | -0.430 |
| XAU_USD | full | 2 | -99.81 | 110.58 | 15116 | 2740.00 | 99.82 | -6.960 |
| XAU_USD | full | 5 | -100.00 | 110.58 | 15116 | 2740.00 | 100.00 | -9.640 |
| XAU_USD | last_12m | 0 | 4.55 | 34.41 | 2425 | 2433.33 | 7.94 | 0.490 |
| XAU_USD | last_12m | 2 | -60.37 | 34.41 | 2425 | 2433.33 | 61.50 | -5.300 |
| XAU_USD | last_12m | 5 | -90.75 | 34.41 | 2425 | 2433.33 | 90.88 | -8.000 |

At EUR_USD/full/2 bps: 17014 trades, return
-99.90% versus buy-hold
+3.06%. The full-window 2 bps edge count
is 0/3 instruments; last-12-month edge count is 0/3.

## Outcome

**REJECTED** — A pre-registered stop condition is met (trade count or no positive edge in a required window).

This is in-sample evidence only. No strategy was run on or promoted using the
OOS holdout. A candidate status is not a finalist nomination; human review is
required before any OOS eligibility change.

## Regime / opportunity distribution

Full-window 2 bps entry trades by month (all instruments): `[3500, 3582, 3521, 3801, 3649, 4445, 4043, 3672, 3275, 3357, 2859, 3835]`.

Full-window 2 bps entry trades by weekday, Mon–Sun (all instruments): `[7897, 9247, 9025, 8312, 6889, 0, 2169]`.

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

N strategies tried before this one: **116**.
