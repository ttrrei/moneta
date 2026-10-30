# S-128: VWAP reclaim in strong 1h trend

## Pre-registered hypothesis

A session VWAP reclaim may be trend resumption when the closed 1h regime is strong and aligned.

Expected full-history EUR_USD trade count: **10–120**.  
Difference from prior work: Session VWAP crossing with strong-ADX and 1h direction.

## Evaluation

Fixed rule; selected config/variant: **pre-registered fixed rule**. The selected
variant for S-103..S-112 is the highest mean edge across the 18 sweep cells at
2 bps, selected after the sweep; treat its performance as selection-biased.
S-113..S-132 use the one pre-registered rule with no parameter sweep.

| Instrument | Window | Cost bps | Return % | Buy-hold % | Trades | Trades/yr | Max DD % | Weekly Sharpe |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| EUR_USD | full | 0 | -14.32 | 3.06 | 3886 | 704.03 | 17.05 | -1.090 |
| EUR_USD | full | 2 | -81.89 | 3.06 | 3886 | 704.03 | 82.12 | -6.390 |
| EUR_USD | full | 5 | -98.24 | 3.06 | 3886 | 704.03 | 98.26 | -7.140 |
| EUR_USD | last_12m | 0 | -1.21 | 5.62 | 676 | 678.32 | 3.69 | -0.390 |
| EUR_USD | last_12m | 2 | -24.62 | 5.62 | 676 | 678.32 | 25.96 | -5.440 |
| EUR_USD | last_12m | 5 | -49.75 | 5.62 | 676 | 678.32 | 50.47 | -6.560 |
| BTC_USD | full | 0 | 24.20 | 1289.48 | 4446 | 805.62 | 46.44 | 0.270 |
| BTC_USD | full | 2 | -79.02 | 1289.48 | 4446 | 805.62 | 80.91 | -0.970 |
| BTC_USD | full | 5 | -98.54 | 1289.48 | 4446 | 805.62 | 98.62 | -2.680 |
| BTC_USD | last_12m | 0 | -1.38 | 82.36 | 633 | 635.17 | 22.72 | 0.010 |
| BTC_USD | last_12m | 2 | -23.44 | 82.36 | 633 | 635.17 | 37.62 | -1.510 |
| BTC_USD | last_12m | 5 | -47.63 | 82.36 | 633 | 635.17 | 55.74 | -3.580 |
| XAU_USD | full | 0 | -11.33 | 110.58 | 3565 | 646.21 | 25.63 | -0.420 |
| XAU_USD | full | 2 | -78.70 | 110.58 | 3565 | 646.21 | 79.02 | -4.970 |
| XAU_USD | full | 5 | -97.49 | 110.58 | 3565 | 646.21 | 97.50 | -7.040 |
| XAU_USD | last_12m | 0 | 6.85 | 34.41 | 692 | 694.38 | 4.31 | 1.680 |
| XAU_USD | last_12m | 2 | -18.99 | 34.41 | 692 | 694.38 | 19.24 | -3.790 |
| XAU_USD | last_12m | 5 | -46.52 | 34.41 | 692 | 694.38 | 46.62 | -7.130 |

At EUR_USD/full/2 bps: 3886 trades, return
-81.89% versus buy-hold
+3.06%. The full-window 2 bps edge count
is 0/3 instruments; last-12-month edge count is 0/3.

## Outcome

**REJECTED** — A pre-registered stop condition is met (trade count or no positive edge in a required window).

This is in-sample evidence only. No strategy was run on or promoted using the
OOS holdout. A candidate status is not a finalist nomination; human review is
required before any OOS eligibility change.

## Regime / opportunity distribution

Full-window 2 bps entry trades by month (all instruments): `[929, 1157, 1263, 1052, 1090, 902, 1019, 800, 978, 974, 1056, 677]`.

Full-window 2 bps entry trades by weekday, Mon–Sun (all instruments): `[2241, 2386, 2461, 2324, 1883, 0, 602]`.

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

N strategies tried before this one: **127**.
