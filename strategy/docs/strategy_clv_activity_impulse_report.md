# S-131: Close-location impulse with tick-activity confirmation

## Pre-registered hypothesis

Directional close-location with elevated tick activity may indicate an impulse in an established regime.

Expected full-history EUR_USD trade count: **10–160**.  
Difference from prior work: Candle close-location and tick-activity proxy with independent 1h regime gate.

## Evaluation

Fixed rule; selected config/variant: **pre-registered fixed rule**. The selected
variant for S-103..S-112 is the highest mean edge across the 18 sweep cells at
2 bps, selected after the sweep; treat its performance as selection-biased.
S-113..S-132 use the one pre-registered rule with no parameter sweep.

| Instrument | Window | Cost bps | Return % | Buy-hold % | Trades | Trades/yr | Max DD % | Weekly Sharpe |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| EUR_USD | full | 0 | -21.07 | 3.06 | 11425 | 2069.88 | 23.02 | -2.090 |
| EUR_USD | full | 2 | -99.18 | 3.06 | 11425 | 2069.88 | 99.18 | -11.200 |
| EUR_USD | full | 5 | -100.00 | 3.06 | 11425 | 2069.88 | 100.00 | -11.610 |
| EUR_USD | last_12m | 0 | -2.31 | 5.62 | 1830 | 1836.28 | 2.95 | -0.960 |
| EUR_USD | last_12m | 2 | -53.02 | 5.62 | 1830 | 1836.28 | 53.13 | -10.610 |
| EUR_USD | last_12m | 5 | -84.33 | 5.62 | 1830 | 1836.28 | 84.33 | -11.330 |
| BTC_USD | full | 0 | -40.76 | 1289.48 | 11039 | 2000.28 | 53.49 | -0.500 |
| BTC_USD | full | 2 | -99.28 | 1289.48 | 11039 | 2000.28 | 99.29 | -5.070 |
| BTC_USD | full | 5 | -100.00 | 1289.48 | 11039 | 2000.28 | 100.00 | -8.790 |
| BTC_USD | last_12m | 0 | -10.32 | 82.36 | 1332 | 1336.57 | 15.22 | -0.690 |
| BTC_USD | last_12m | 2 | -47.36 | 82.36 | 1332 | 1336.57 | 47.70 | -3.750 |
| BTC_USD | last_12m | 5 | -76.33 | 82.36 | 1332 | 1336.57 | 76.39 | -6.090 |
| XAU_USD | full | 0 | -32.57 | 110.58 | 12502 | 2266.18 | 36.73 | -1.330 |
| XAU_USD | full | 2 | -99.55 | 110.58 | 12502 | 2266.18 | 99.55 | -9.920 |
| XAU_USD | full | 5 | -100.00 | 110.58 | 12502 | 2266.18 | 100.00 | -11.470 |
| XAU_USD | last_12m | 0 | 1.39 | 34.41 | 2287 | 2294.85 | 4.87 | 0.540 |
| XAU_USD | last_12m | 2 | -59.38 | 34.41 | 2287 | 2294.85 | 59.39 | -11.080 |
| XAU_USD | last_12m | 5 | -89.70 | 34.41 | 2287 | 2294.85 | 89.70 | -13.300 |

At EUR_USD/full/2 bps: 11425 trades, return
-99.18% versus buy-hold
+3.06%. The full-window 2 bps edge count
is 0/3 instruments; last-12-month edge count is 0/3.

## Outcome

**REJECTED** — A pre-registered stop condition is met (trade count or no positive edge in a required window).

This is in-sample evidence only. No strategy was run on or promoted using the
OOS holdout. A candidate status is not a finalist nomination; human review is
required before any OOS eligibility change.

## Regime / opportunity distribution

Full-window 2 bps entry trades by month (all instruments): `[2578, 3137, 3427, 3258, 3283, 2882, 3073, 2535, 2845, 2847, 2882, 2219]`.

Full-window 2 bps entry trades by weekday, Mon–Sun (all instruments): `[7230, 6485, 6973, 7336, 6067, 0, 875]`.

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

N strategies tried before this one: **130**.
