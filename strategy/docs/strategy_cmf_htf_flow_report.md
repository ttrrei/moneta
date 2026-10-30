# S-127: Money-flow zero-cross with 1h trend alignment

## Pre-registered hypothesis

A shorter money-flow regime change may be useful only when closed 1h price trend agrees.

Expected full-history EUR_USD trade count: **10–150**.  
Difference from prior work: CMF crossing with independent higher-timeframe trend gate.

## Evaluation

Fixed rule; selected config/variant: **pre-registered fixed rule**. The selected
variant for S-103..S-112 is the highest mean edge across the 18 sweep cells at
2 bps, selected after the sweep; treat its performance as selection-biased.
S-113..S-132 use the one pre-registered rule with no parameter sweep.

| Instrument | Window | Cost bps | Return % | Buy-hold % | Trades | Trades/yr | Max DD % | Weekly Sharpe |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| EUR_USD | full | 0 | -38.46 | 3.06 | 27824 | 5040.92 | 41.34 | -1.800 |
| EUR_USD | full | 2 | -100.00 | 3.06 | 27824 | 5040.92 | 100.00 | -32.300 |
| EUR_USD | full | 5 | -100.00 | 3.06 | 27824 | 5040.92 | 100.00 | -50.240 |
| EUR_USD | last_12m | 0 | 2.28 | 5.62 | 4834 | 4850.60 | 5.85 | 0.380 |
| EUR_USD | last_12m | 2 | -85.21 | 5.62 | 4834 | 4850.60 | 85.34 | -23.640 |
| EUR_USD | last_12m | 5 | -99.19 | 5.62 | 4834 | 4850.60 | 99.19 | -38.440 |
| BTC_USD | full | 0 | -84.41 | 1289.48 | 27768 | 5031.60 | 92.09 | -0.740 |
| BTC_USD | full | 2 | -100.00 | 1289.48 | 27768 | 5031.60 | 100.00 | -6.270 |
| BTC_USD | full | 5 | -100.00 | 1289.48 | 27768 | 5031.60 | 100.00 | -14.270 |
| BTC_USD | last_12m | 0 | 16.33 | 82.36 | 4839 | 4855.62 | 24.95 | 0.510 |
| BTC_USD | last_12m | 2 | -83.21 | 82.36 | 4839 | 4855.62 | 85.94 | -6.240 |
| BTC_USD | last_12m | 5 | -99.08 | 82.36 | 4839 | 4855.62 | 99.21 | -15.630 |
| XAU_USD | full | 0 | -40.80 | 110.58 | 27180 | 4926.79 | 59.56 | -0.800 |
| XAU_USD | full | 2 | -100.00 | 110.58 | 27180 | 4926.79 | 100.00 | -17.390 |
| XAU_USD | full | 5 | -100.00 | 110.58 | 27180 | 4926.79 | 100.00 | -35.880 |
| XAU_USD | last_12m | 0 | 9.48 | 34.41 | 4854 | 4870.67 | 8.27 | 1.010 |
| XAU_USD | last_12m | 2 | -84.29 | 34.41 | 4854 | 4870.67 | 84.36 | -17.050 |
| XAU_USD | last_12m | 5 | -99.15 | 34.41 | 4854 | 4870.67 | 99.15 | -36.550 |

At EUR_USD/full/2 bps: 27824 trades, return
-100.00% versus buy-hold
+3.06%. The full-window 2 bps edge count
is 0/3 instruments; last-12-month edge count is 0/3.

## Outcome

**REJECTED** — A pre-registered stop condition is met (trade count or no positive edge in a required window).

This is in-sample evidence only. No strategy was run on or promoted using the
OOS holdout. A candidate status is not a finalist nomination; human review is
required before any OOS eligibility change.

## Regime / opportunity distribution

Full-window 2 bps entry trades by month (all instruments): `[6604, 7159, 7675, 7441, 7858, 7441, 7447, 6555, 6169, 6300, 6084, 6039]`.

Full-window 2 bps entry trades by weekday, Mon–Sun (all instruments): `[16210, 16660, 16762, 16797, 14774, 0, 1569]`.

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

N strategies tried before this one: **126**.
