# S-124: Squeeze release with activity-confirmed break

## Pre-registered hypothesis

A 60-bar squeeze release with activity and an extreme break may avoid low-energy false breaks.

Expected full-history EUR_USD trade count: **5–100**.  
Difference from prior work: Compression release, tick-activity proxy, and prior-channel break.

## Evaluation

Fixed rule; selected config/variant: **pre-registered fixed rule**. The selected
variant for S-103..S-112 is the highest mean edge across the 18 sweep cells at
2 bps, selected after the sweep; treat its performance as selection-biased.
S-113..S-132 use the one pre-registered rule with no parameter sweep.

| Instrument | Window | Cost bps | Return % | Buy-hold % | Trades | Trades/yr | Max DD % | Weekly Sharpe |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| EUR_USD | full | 0 | -0.51 | 2.32 | 267 | 47.90 | 4.12 | -0.060 |
| EUR_USD | full | 2 | -10.59 | 2.32 | 267 | 47.90 | 12.33 | -1.410 |
| EUR_USD | full | 5 | -23.83 | 2.32 | 267 | 47.90 | 24.23 | -3.090 |
| EUR_USD | last_12m | 0 | 2.82 | 5.62 | 37 | 37.13 | 1.06 | 1.220 |
| EUR_USD | last_12m | 2 | 1.30 | 5.62 | 37 | 37.13 | 1.60 | 0.580 |
| EUR_USD | last_12m | 5 | -0.92 | 5.62 | 37 | 37.13 | 2.42 | -0.390 |
| BTC_USD | full | 0 | 2.29 | 1538.05 | 242 | 43.42 | 21.67 | 0.090 |
| BTC_USD | full | 2 | -7.15 | 1538.05 | 242 | 43.42 | 24.38 | -0.090 |
| BTC_USD | full | 5 | -19.70 | 1538.05 | 242 | 43.42 | 31.39 | -0.360 |
| BTC_USD | last_12m | 0 | 3.79 | 82.36 | 30 | 30.10 | 5.52 | 0.500 |
| BTC_USD | last_12m | 2 | 2.55 | 82.36 | 30 | 30.10 | 6.12 | 0.350 |
| BTC_USD | last_12m | 5 | 0.72 | 82.36 | 30 | 30.10 | 7.02 | 0.130 |
| XAU_USD | full | 0 | 0.30 | 113.27 | 237 | 42.52 | 5.48 | 0.030 |
| XAU_USD | full | 2 | -8.77 | 113.27 | 237 | 42.52 | 10.23 | -0.690 |
| XAU_USD | full | 5 | -20.87 | 113.27 | 237 | 42.52 | 21.15 | -1.730 |
| XAU_USD | last_12m | 0 | 1.52 | 34.41 | 47 | 47.16 | 1.62 | 0.850 |
| XAU_USD | last_12m | 2 | -0.37 | 34.41 | 47 | 47.16 | 2.06 | 0.000 |
| XAU_USD | last_12m | 5 | -3.14 | 34.41 | 47 | 47.16 | 3.59 | -1.310 |

At EUR_USD/full/2 bps: 267 trades, return
-10.59% versus buy-hold
+2.32%. The full-window 2 bps edge count
is 0/3 instruments; last-12-month edge count is 0/3.

## Outcome

**REJECTED** — A pre-registered stop condition is met (trade count or no positive edge in a required window).

This is in-sample evidence only. No strategy was run on or promoted using the
OOS holdout. A candidate status is not a finalist nomination; human review is
required before any OOS eligibility change.

## Regime / opportunity distribution

Full-window 2 bps entry trades by month (all instruments): `[65, 69, 67, 76, 72, 63, 62, 64, 47, 52, 58, 51]`.

Full-window 2 bps entry trades by weekday, Mon–Sun (all instruments): `[132, 168, 146, 138, 157, 0, 5]`.

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

N strategies tried before this one: **123**.
