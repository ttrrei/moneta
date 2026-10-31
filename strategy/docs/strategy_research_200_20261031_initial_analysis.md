# Analysis of the fifty source ideas before the next 100 + 100 strategies

Date: 2026-10-31. This analysis precedes round-1 portfolio outcomes.

The source [fifty-idea study](../../docs/indicator_catalogue_results_20261031.md)
contains feature hypotheses, not portfolio strategies. It recorded 2,250
comparisons, 1,708 supported comparisons, 22 adjusted catalogue findings and
zero fully replicated ideas. Forty-three definitions were rejected for
promotion and seven needed revision. The existing separate S-series has 132
strategies and 827 distinct configurations already tried.

| Finding | Implication for the new experiment |
|---|---|
| 36 directional, 7 magnitude, 7 adverse-risk ideas | Give magnitude/risk ideas an independently specified direction model; do not trade the sign of a risk statistic. |
| 21 of 22 adjusted cells concern magnitude/risk | Treat these primarily as potential context filters, with actual cost-bearing backtests needed. |
| EUR_USD PS-08 repeats within one asset | Report asset-specific behavior, require cross-market evidence, and do not declare an entry alpha. |
| Seven definitions lack common support | Preserve zero/rare entries and count them honestly; do not refit tails after seeing results. |
| Earlier strategies often suffer cost × turnover | Use native-hourly decisions, fresh setups, frozen ATR exits and bounded cooldowns. |
| Feature-study cuts were fitted through end-2022 | Recompute from covariates ending 2020-07-01 before simulating earlier trades; prohibit live positions before that date. |
| Full/recent periods overlap and all history is development-used | Keep their legacy comparison but add disjoint diagnostic slices; no independent OOS claim. |

The fifty source definitions cover ten ideas in each of trend, mean reversion,
compression, candle/structure and persistence/session styles. The first round
registers two different directional/context mechanisms per idea, yielding 100
executable rules. These are related configurations, not a claim of 100 newly
independent market mechanisms. The second round will register a new causal
episode per parent, selected using first-round development-training diagnostics.

## Input and setup checks

The archived development sources have 34,410 EUR_USD, 33,841 BTC_USD and 32,655
XAU_USD native hourly rows. Complete hourly rows are 29,474, 31,981 and 29,214,
respectively. Underlying 5m feature rows are 416,107, 409,018 and 395,556.
Use exact 5m-close to native-1h-close projection, preserving actual gaps and
missingness rather than constructing synthetic hourly candles.

After early recalibration and before any portfolio P&L, the setup preflight
found seven of 300 strategy/asset combinations had no fresh eligible setups.
Those combinations stay in the evaluation. All exact-time feature projections
passed. The preflight records are saved in
`research/strategies/SR-20261031-200/signal_preflight.csv`.

## Frozen next actions

1. Run all 100 registered first-round rules through the shared engine on all
   three assets, five declared windows and 0/2/5 bps costs.
2. Analyze gross/net return, trade frequency, exposure, drawdown, empty cases,
   asset/time stability and dependence-aware benchmark-relative inference.
3. Register 100 children only after the first round completes; retain the
   parent-analysis hash and training-only adaptation decision per child.
4. Repeat the same analysis, retaining all failures and behavioral duplicates.
5. Audit execution, source/time boundaries, accumulated trials and replays;
   document results without automatic finalist promotion or holdout access.

See the [registered design](strategy_research_200_20261031_design.md) and
`config/strategy_research_200.yml` for exact rules and evaluation requirements.
