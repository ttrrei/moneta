# S-114: Higher-timeframe trend pullback

## Pre-registered hypothesis

A 5m pullback recovery aligned with closed 1h direction may avoid counter-trend entries.

Expected full-history EUR_USD trade count: **20–220**.  
Difference from prior work: Pullback recovery in ATR-normalized EMA distance with a closed 1h context gate.

## Evaluation

Fixed rule; selected config/variant: **pre-registered fixed rule**. The selected
variant for S-103..S-112 is the highest mean edge across the 18 sweep cells at
2 bps, selected after the sweep; treat its performance as selection-biased.
S-113..S-132 use the one pre-registered rule with no parameter sweep.

| Instrument | Window | Cost bps | Return % | Buy-hold % | Trades | Trades/yr | Max DD % | Weekly Sharpe |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| EUR_USD | full | 0 | -22.00 | 3.06 | 14657 | 2655.43 | 30.68 | -0.780 |
| EUR_USD | full | 2 | -99.78 | 3.06 | 14657 | 2655.43 | 99.78 | -18.460 |
| EUR_USD | full | 5 | -100.00 | 3.06 | 14657 | 2655.43 | 100.00 | -36.210 |
| EUR_USD | last_12m | 0 | 2.53 | 5.62 | 2636 | 2645.05 | 4.54 | 0.480 |
| EUR_USD | last_12m | 2 | -64.28 | 5.62 | 2636 | 2645.05 | 64.45 | -14.080 |
| EUR_USD | last_12m | 5 | -92.65 | 5.62 | 2636 | 2645.05 | 92.68 | -28.890 |
| BTC_USD | full | 0 | -21.62 | 1289.48 | 13825 | 2505.11 | 64.12 | 0.030 |
| BTC_USD | full | 2 | -99.69 | 1289.48 | 13825 | 2505.11 | 99.71 | -2.850 |
| BTC_USD | full | 5 | -100.00 | 1289.48 | 13825 | 2505.11 | 100.00 | -7.180 |
| BTC_USD | last_12m | 0 | 2.53 | 82.36 | 2502 | 2510.59 | 31.19 | 0.020 |
| BTC_USD | last_12m | 2 | -62.31 | 82.36 | 2502 | 2510.59 | 68.94 | -3.330 |
| BTC_USD | last_12m | 5 | -91.60 | 82.36 | 2502 | 2510.59 | 92.83 | -8.520 |
| XAU_USD | full | 0 | -19.57 | 110.58 | 13499 | 2446.90 | 37.80 | -0.400 |
| XAU_USD | full | 2 | -99.64 | 110.58 | 13499 | 2446.90 | 99.64 | -10.720 |
| XAU_USD | full | 5 | -100.00 | 110.58 | 13499 | 2446.90 | 100.00 | -24.000 |
| XAU_USD | last_12m | 0 | 4.68 | 34.41 | 2330 | 2338.00 | 8.19 | 0.680 |
| XAU_USD | last_12m | 2 | -58.78 | 34.41 | 2330 | 2338.00 | 59.55 | -10.840 |
| XAU_USD | last_12m | 5 | -89.81 | 34.41 | 2330 | 2338.00 | 89.88 | -26.040 |

At EUR_USD/full/2 bps: 14657 trades, return
-99.78% versus buy-hold
+3.06%. The full-window 2 bps edge count
is 0/3 instruments; last-12-month edge count is 0/3.

## Outcome

**REJECTED** — A pre-registered stop condition is met (trade count or no positive edge in a required window).

This is in-sample evidence only. No strategy was run on or promoted using the
OOS holdout. A candidate status is not a finalist nomination; human review is
required before any OOS eligibility change.

## Regime / opportunity distribution

Full-window 2 bps entry trades by month (all instruments): `[3310, 3568, 3706, 3667, 3800, 3785, 3865, 3350, 3279, 3312, 3185, 3154]`.

Full-window 2 bps entry trades by weekday, Mon–Sun (all instruments): `[8199, 8594, 8457, 8389, 7649, 0, 693]`.

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

N strategies tried before this one: **113**.
