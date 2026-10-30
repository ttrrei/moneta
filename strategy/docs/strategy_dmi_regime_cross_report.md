# S-120: Directional-movement cross with ADX filter

## Pre-registered hypothesis

A slow directional-movement cross may reduce false starts when 60-bar ADX is established.

Expected full-history EUR_USD trade count: **10–160**.  
Difference from prior work: DI cross paired with a slow ADX regime gate.

## Evaluation

Fixed rule; selected config/variant: **pre-registered fixed rule**. The selected
variant for S-103..S-112 is the highest mean edge across the 18 sweep cells at
2 bps, selected after the sweep; treat its performance as selection-biased.
S-113..S-132 use the one pre-registered rule with no parameter sweep.

| Instrument | Window | Cost bps | Return % | Buy-hold % | Trades | Trades/yr | Max DD % | Weekly Sharpe |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| EUR_USD | full | 0 | 2.79 | 2.32 | 212 | 38.04 | 1.64 | 0.320 |
| EUR_USD | full | 2 | -5.57 | 2.32 | 212 | 38.04 | 5.76 | -0.620 |
| EUR_USD | full | 5 | -16.85 | 2.32 | 212 | 38.04 | 16.97 | -1.700 |
| EUR_USD | last_12m | 0 | -1.32 | 5.62 | 37 | 37.13 | 1.64 | -1.260 |
| EUR_USD | last_12m | 2 | -2.77 | 5.62 | 37 | 37.13 | 2.77 | -2.070 |
| EUR_USD | last_12m | 5 | -4.90 | 5.62 | 37 | 37.13 | 4.90 | -2.660 |
| BTC_USD | full | 0 | -5.85 | 1538.05 | 453 | 81.27 | 30.32 | 0.000 |
| BTC_USD | full | 2 | -21.45 | 1538.05 | 453 | 81.27 | 33.74 | -0.210 |
| BTC_USD | full | 5 | -40.15 | 1538.05 | 453 | 81.27 | 44.15 | -0.520 |
| BTC_USD | last_12m | 0 | -11.70 | 82.36 | 55 | 55.19 | 14.90 | -3.310 |
| BTC_USD | last_12m | 2 | -13.62 | 82.36 | 55 | 55.19 | 16.68 | -3.620 |
| BTC_USD | last_12m | 5 | -16.43 | 82.36 | 55 | 55.19 | 19.29 | -3.970 |
| XAU_USD | full | 0 | -2.40 | 113.27 | 309 | 55.44 | 8.20 | -0.280 |
| XAU_USD | full | 2 | -13.75 | 113.27 | 309 | 55.44 | 17.01 | -1.110 |
| XAU_USD | full | 5 | -28.34 | 113.27 | 309 | 55.44 | 30.24 | -2.120 |
| XAU_USD | last_12m | 0 | -2.93 | 34.41 | 74 | 74.25 | 5.00 | -0.860 |
| XAU_USD | last_12m | 2 | -5.76 | 34.41 | 74 | 74.25 | 6.77 | -1.670 |
| XAU_USD | last_12m | 5 | -9.86 | 34.41 | 74 | 74.25 | 9.87 | -2.590 |

At EUR_USD/full/2 bps: 212 trades, return
-5.57% versus buy-hold
+2.32%. The full-window 2 bps edge count
is 0/3 instruments; last-12-month edge count is 0/3.

## Outcome

**REJECTED** — A pre-registered stop condition is met (trade count or no positive edge in a required window).

This is in-sample evidence only. No strategy was run on or promoted using the
OOS holdout. A candidate status is not a finalist nomination; human review is
required before any OOS eligibility change.

## Regime / opportunity distribution

Full-window 2 bps entry trades by month (all instruments): `[98, 82, 90, 130, 80, 79, 76, 75, 50, 53, 88, 73]`.

Full-window 2 bps entry trades by weekday, Mon–Sun (all instruments): `[251, 179, 161, 192, 158, 0, 33]`.

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

N strategies tried before this one: **119**.
