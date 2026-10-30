# S-115: Higher-timeframe-gated channel break

## Pre-registered hypothesis

A break of the prior 24-bar extreme may persist when closed 1h ADX confirms trend strength.

Expected full-history EUR_USD trade count: **10–160**.  
Difference from prior work: Prior-extreme break plus 1h regime confirmation; distinct from raw channel followers.

## Evaluation

Fixed rule; selected config/variant: **pre-registered fixed rule**. The selected
variant for S-103..S-112 is the highest mean edge across the 18 sweep cells at
2 bps, selected after the sweep; treat its performance as selection-biased.
S-113..S-132 use the one pre-registered rule with no parameter sweep.

| Instrument | Window | Cost bps | Return % | Buy-hold % | Trades | Trades/yr | Max DD % | Weekly Sharpe |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| EUR_USD | full | 0 | -32.58 | 3.06 | 6263 | 1134.68 | 34.05 | -1.820 |
| EUR_USD | full | 2 | -94.49 | 3.06 | 6263 | 1134.68 | 94.54 | -8.920 |
| EUR_USD | full | 5 | -99.87 | 3.06 | 6263 | 1134.68 | 99.87 | -11.230 |
| EUR_USD | last_12m | 0 | -10.55 | 5.62 | 1103 | 1106.79 | 11.77 | -2.570 |
| EUR_USD | last_12m | 2 | -42.46 | 5.62 | 1103 | 1106.79 | 42.91 | -8.910 |
| EUR_USD | last_12m | 5 | -70.32 | 5.62 | 1103 | 1106.79 | 70.48 | -11.250 |
| BTC_USD | full | 0 | -86.45 | 1289.48 | 6997 | 1267.87 | 90.56 | -1.170 |
| BTC_USD | full | 2 | -99.17 | 1289.48 | 6997 | 1267.87 | 99.18 | -2.940 |
| BTC_USD | full | 5 | -99.99 | 1289.48 | 6997 | 1267.87 | 99.99 | -5.300 |
| BTC_USD | last_12m | 0 | -10.36 | 82.36 | 1100 | 1103.78 | 28.95 | -0.590 |
| BTC_USD | last_12m | 2 | -42.27 | 82.36 | 1100 | 1103.78 | 52.15 | -2.540 |
| BTC_USD | last_12m | 5 | -70.16 | 82.36 | 1100 | 1103.78 | 74.82 | -5.060 |
| XAU_USD | full | 0 | -15.73 | 110.58 | 5958 | 1079.98 | 28.48 | -0.330 |
| XAU_USD | full | 2 | -92.23 | 110.58 | 5958 | 1079.98 | 92.38 | -4.810 |
| XAU_USD | full | 5 | -99.78 | 110.58 | 5958 | 1079.98 | 99.78 | -8.510 |
| XAU_USD | last_12m | 0 | 2.85 | 34.41 | 1170 | 1174.02 | 9.87 | 0.240 |
| XAU_USD | last_12m | 2 | -35.59 | 34.41 | 1170 | 1174.02 | 38.09 | -4.890 |
| XAU_USD | last_12m | 5 | -68.08 | 34.41 | 1170 | 1174.02 | 68.97 | -10.090 |

At EUR_USD/full/2 bps: 6263 trades, return
-94.49% versus buy-hold
+3.06%. The full-window 2 bps edge count
is 0/3 instruments; last-12-month edge count is 0/3.

## Outcome

**REJECTED** — A pre-registered stop condition is met (trade count or no positive edge in a required window).

This is in-sample evidence only. No strategy was run on or promoted using the
OOS holdout. A candidate status is not a finalist nomination; human review is
required before any OOS eligibility change.

## Regime / opportunity distribution

Full-window 2 bps entry trades by month (all instruments): `[1519, 1688, 1893, 1767, 1851, 1573, 1737, 1382, 1497, 1538, 1567, 1206]`.

Full-window 2 bps entry trades by weekday, Mon–Sun (all instruments): `[3828, 3664, 3873, 4029, 3471, 0, 353]`.

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

N strategies tried before this one: **114**.
