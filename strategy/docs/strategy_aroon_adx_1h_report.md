# S-113: 1h Aroon direction with ADX regime

## Pre-registered hypothesis

Aroon direction changes may persist longer when 1h ADX confirms a directional regime.

Expected full-history EUR_USD trade count: **20–180**.  
Difference from prior work: 1h Aroon cross plus ADX confirmation; not a single-indicator Aroon flip.

## Evaluation

Fixed rule; selected config/variant: **pre-registered fixed rule**. The selected
variant for S-103..S-112 is the highest mean edge across the 18 sweep cells at
2 bps, selected after the sweep; treat its performance as selection-biased.
S-113..S-132 use the one pre-registered rule with no parameter sweep.

| Instrument | Window | Cost bps | Return % | Buy-hold % | Trades | Trades/yr | Max DD % | Weekly Sharpe |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| EUR_USD | full | 0 | -3.56 | 3.07 | 493 | 89.32 | 13.08 | -0.120 |
| EUR_USD | full | 2 | -20.82 | 3.07 | 493 | 89.32 | 21.82 | -0.890 |
| EUR_USD | full | 5 | -41.09 | 3.07 | 493 | 89.32 | 41.62 | -2.010 |
| EUR_USD | last_12m | 0 | -4.12 | 5.64 | 89 | 89.31 | 6.53 | -0.940 |
| EUR_USD | last_12m | 2 | -7.48 | 5.64 | 89 | 89.31 | 9.07 | -1.700 |
| EUR_USD | last_12m | 5 | -12.29 | 5.64 | 89 | 89.31 | 13.15 | -2.700 |
| BTC_USD | full | 0 | -18.95 | 1288.41 | 602 | 109.08 | 73.89 | 0.130 |
| BTC_USD | full | 2 | -36.29 | 1288.41 | 602 | 109.08 | 77.12 | 0.030 |
| BTC_USD | full | 5 | -55.61 | 1288.41 | 602 | 109.08 | 81.93 | -0.130 |
| BTC_USD | last_12m | 0 | -12.59 | 83.28 | 84 | 84.29 | 33.10 | -0.020 |
| BTC_USD | last_12m | 2 | -15.47 | 83.28 | 84 | 84.29 | 34.11 | -0.100 |
| BTC_USD | last_12m | 5 | -19.63 | 83.28 | 84 | 84.29 | 35.59 | -0.220 |
| XAU_USD | full | 0 | -3.52 | 110.29 | 501 | 90.81 | 21.15 | -0.030 |
| XAU_USD | full | 2 | -21.04 | 110.29 | 501 | 90.81 | 31.01 | -0.440 |
| XAU_USD | full | 5 | -41.54 | 110.29 | 501 | 90.81 | 47.91 | -1.050 |
| XAU_USD | last_12m | 0 | 7.14 | 34.37 | 93 | 93.32 | 9.05 | 0.800 |
| XAU_USD | last_12m | 2 | 3.23 | 34.37 | 93 | 93.32 | 10.81 | 0.370 |
| XAU_USD | last_12m | 5 | -2.37 | 34.37 | 93 | 93.32 | 13.68 | -0.280 |

At EUR_USD/full/2 bps: 493 trades, return
-20.82% versus buy-hold
+3.07%. The full-window 2 bps edge count
is 0/3 instruments; last-12-month edge count is 0/3.

## Outcome

**REJECTED** — A pre-registered stop condition is met (trade count or no positive edge in a required window).

This is in-sample evidence only. No strategy was run on or promoted using the
OOS holdout. A candidate status is not a finalist nomination; human review is
required before any OOS eligibility change.

## Regime / opportunity distribution

Full-window 2 bps entry trades by month (all instruments): `[124, 136, 167, 136, 152, 145, 139, 103, 135, 115, 151, 93]`.

Full-window 2 bps entry trades by weekday, Mon–Sun (all instruments): `[271, 327, 341, 331, 297, 0, 29]`.

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

N strategies tried before this one: **112**.
