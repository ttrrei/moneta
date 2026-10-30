# S-132: Band-width expansion aligned with 1h trend

## Pre-registered hypothesis

Short-window volatility expansion may signal a phase change when price location and 1h trend agree.

Expected full-history EUR_USD trade count: **10–150**.  
Difference from prior work: Relative bandwidth expansion, channel location, and independent 1h direction.

## Evaluation

Fixed rule; selected config/variant: **pre-registered fixed rule**. The selected
variant for S-103..S-112 is the highest mean edge across the 18 sweep cells at
2 bps, selected after the sweep; treat its performance as selection-biased.
S-113..S-132 use the one pre-registered rule with no parameter sweep.

| Instrument | Window | Cost bps | Return % | Buy-hold % | Trades | Trades/yr | Max DD % | Weekly Sharpe |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| EUR_USD | full | 0 | -3.54 | 3.06 | 2641 | 478.47 | 8.64 | -0.210 |
| EUR_USD | full | 2 | -66.46 | 3.06 | 2641 | 478.47 | 66.69 | -6.300 |
| EUR_USD | full | 5 | -93.12 | 3.06 | 2641 | 478.47 | 93.15 | -13.180 |
| EUR_USD | last_12m | 0 | -1.33 | 5.62 | 450 | 451.55 | 4.03 | -0.670 |
| EUR_USD | last_12m | 2 | -17.58 | 5.62 | 450 | 451.55 | 18.74 | -5.950 |
| EUR_USD | last_12m | 5 | -37.08 | 5.62 | 450 | 451.55 | 37.65 | -11.630 |
| BTC_USD | full | 0 | 362.25 | 1289.48 | 2475 | 448.47 | 28.55 | 1.300 |
| BTC_USD | full | 2 | 71.76 | 1289.48 | 2475 | 448.47 | 30.55 | 0.530 |
| BTC_USD | full | 5 | -61.10 | 1289.48 | 2475 | 448.47 | 71.17 | -0.620 |
| BTC_USD | last_12m | 0 | 7.50 | 82.36 | 425 | 426.46 | 22.55 | 0.320 |
| BTC_USD | last_12m | 2 | -9.31 | 82.36 | 425 | 426.46 | 29.83 | -0.660 |
| BTC_USD | last_12m | 5 | -29.72 | 82.36 | 425 | 426.46 | 39.50 | -2.140 |
| XAU_USD | full | 0 | 20.16 | 110.58 | 2353 | 426.52 | 9.75 | 0.590 |
| XAU_USD | full | 2 | -53.12 | 110.58 | 2353 | 426.52 | 55.98 | -2.320 |
| XAU_USD | full | 5 | -88.57 | 110.58 | 2353 | 426.52 | 88.71 | -6.480 |
| XAU_USD | last_12m | 0 | 14.03 | 34.41 | 401 | 402.38 | 3.62 | 2.090 |
| XAU_USD | last_12m | 2 | -2.87 | 34.41 | 401 | 402.38 | 6.62 | -0.320 |
| XAU_USD | last_12m | 5 | -23.64 | 34.41 | 401 | 402.38 | 24.45 | -3.820 |

At EUR_USD/full/2 bps: 2641 trades, return
-66.46% versus buy-hold
+3.06%. The full-window 2 bps edge count
is 0/3 instruments; last-12-month edge count is 0/3.

## Outcome

**REJECTED** — A pre-registered stop condition is met (trade count or no positive edge in a required window).

This is in-sample evidence only. No strategy was run on or promoted using the
OOS holdout. A candidate status is not a finalist nomination; human review is
required before any OOS eligibility change.

## Regime / opportunity distribution

Full-window 2 bps entry trades by month (all instruments): `[602, 628, 644, 656, 697, 689, 728, 577, 571, 584, 564, 529]`.

Full-window 2 bps entry trades by weekday, Mon–Sun (all instruments): `[1332, 1507, 1528, 1468, 1414, 0, 220]`.

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

N strategies tried before this one: **131**.
