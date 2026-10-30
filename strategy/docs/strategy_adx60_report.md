# S-109: Slow ADX range-regime rule

## Pre-registered hypothesis

cross below 20

Expected full-history EUR_USD trade count: **see sweep results**.  
Difference from prior work: This was the registered strategy hypothesis; the report selects the best-of-eight variant after evaluation.

## Evaluation

Fixed rule; selected config/variant: **wide_exit**. The selected
variant for S-103..S-112 is the highest mean edge across the 18 sweep cells at
2 bps, selected after the sweep; treat its performance as selection-biased.
S-113..S-132 use the one pre-registered rule with no parameter sweep.

| Instrument | Window | Cost bps | Return % | Buy-hold % | Trades | Trades/yr | Max DD % | Weekly Sharpe |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| EUR_USD | full | 0 | 2.32 | 2.32 | 1 | 0.18 | 22.75 | 0.090 |
| EUR_USD | full | 2 | 2.27 | 2.32 | 1 | 0.18 | 22.75 | 0.090 |
| EUR_USD | full | 5 | 2.21 | 2.32 | 1 | 0.18 | 22.75 | 0.090 |
| EUR_USD | last_12m | 0 | 5.60 | 5.62 | 1 | 1.00 | 9.17 | 0.560 |
| EUR_USD | last_12m | 2 | 5.56 | 5.62 | 1 | 1.00 | 9.17 | 0.560 |
| EUR_USD | last_12m | 5 | 5.49 | 5.62 | 1 | 1.00 | 9.17 | 0.560 |
| BTC_USD | full | 0 | 1510.62 | 1538.05 | 1 | 0.18 | 77.33 | 1.120 |
| BTC_USD | full | 2 | 1509.98 | 1538.05 | 1 | 0.18 | 77.33 | 1.120 |
| BTC_USD | full | 5 | 1509.01 | 1538.05 | 1 | 0.18 | 77.33 | 1.120 |
| BTC_USD | last_12m | 0 | 82.19 | 82.36 | 1 | 1.00 | 31.60 | 1.860 |
| BTC_USD | last_12m | 2 | 82.11 | 82.36 | 1 | 1.00 | 31.60 | 1.860 |
| BTC_USD | last_12m | 5 | 82.01 | 82.36 | 1 | 1.00 | 31.60 | 1.860 |
| XAU_USD | full | 0 | 112.25 | 113.27 | 1 | 0.18 | 22.01 | 0.890 |
| XAU_USD | full | 2 | 112.17 | 113.27 | 1 | 0.18 | 22.01 | 0.890 |
| XAU_USD | full | 5 | 112.04 | 113.27 | 1 | 0.18 | 22.01 | 0.890 |
| XAU_USD | last_12m | 0 | 34.54 | 34.41 | 1 | 1.00 | 10.64 | 1.910 |
| XAU_USD | last_12m | 2 | 34.49 | 34.41 | 1 | 1.00 | 10.64 | 1.910 |
| XAU_USD | last_12m | 5 | 34.41 | 34.41 | 1 | 1.00 | 10.64 | 1.910 |

At EUR_USD/full/2 bps: 1 trades, return
+2.27% versus buy-hold
+2.32%. The full-window 2 bps edge count
is 0/3 instruments; last-12-month edge count is 1/3.

## Outcome

**REJECTED** — A pre-registered stop condition is met (trade count or no positive edge in a required window).

This is in-sample evidence only. No strategy was run on or promoted using the
OOS holdout. A candidate status is not a finalist nomination; human review is
required before any OOS eligibility change.

## Regime / opportunity distribution

Monthly and weekday distribution was not included in the committed matrix output.

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

N strategies tried before this one: **108**.
