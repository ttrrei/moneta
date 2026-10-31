# Two sequential 100-strategy research rounds

Date: 2026-10-31. Authorization: the user explicitly requested analysis of the
completed fifty ideas, then 100 strategies with analysis, followed by another
100 with analysis and continuous documentation.

The previous fifty are **indicator hypotheses**, not fifty portfolio
backtests. Their historical 43 reject/7 revise decisions and 22 isolated
adjusted findings remain preserved in the original study. Movement magnitude and adverse-risk features supply context;
they do not become directional predictors merely by being used in a strategy.

## Registration, scope and accounting

This explicitly requested bulk experiment is registered as a linked research
cohort, with IDs `SR1-001`–`SR1-100` and `SR2-001`–`SR2-100`. Its complete YAML
registries and immutable result manifests are the trial memory. These are
exploratory candidates using newly researched features. They do not bypass or
modify the mature S-series saturation, finalist, implementation-freeze or OOS
gates; any future S-series nomination requires those existing gates separately.
The S-series registry and trial log link this cohort and its configuration
tally, so it is not an unrecorded search.

The user's requested two-round scope supersedes the generic one-strategy/no-
new-feature generation brief for this experiment. Existing catalogue features
are reused through the shared engine, rather than added to default Gold. All
200 definitions and all attempted results will be retained. Related rules
remain related configurations; the count is not a claim of 200 independent
economic hypotheses.

## What the fifty-idea analysis changes

- Directional evidence is weak: none of the fifty passed the original complete
  replication rule. All new strategies are explicitly exploratory.
- 21 of 22 catalogue findings concern magnitude or risk. Those inputs gate
  independently specified trend or mean-reversion direction models.
- EUR_USD PS-08 is a movement-context lead, not a predicted buy/sell direction.
- Seven ideas have sparse or non-overlapping populations. Empty strategies
  stay visible instead of being rescued with undisclosed threshold changes.
- The previous 132 registered strategies and 827 configurations often failed
  through turnover, costs, empty intersections or one-asset beta. New rules
  use hourly decisions, fresh events and bounded holding/cooldown state.

## Data and causal calibration

Use the archived, hashed development inputs from catalogue batch 5. Recompute
the fifty features using covariate calibration ending **2020-07-01**. Do not
reuse the original feature-study's end-2022 cuts to trade in 2020–2022. Fit new
strategy feature tails and context cuts to that same early calibration only.
No position opens before calibration ends.

Observe the last completed 5m feature snapshot at each native 1h close, using
an exact timestamp match. Execute at the next native hourly open through
`strategy.engine.run_backtest`. Feature windows retain their original 5m/1h
units; they are not relabeled as hourly indicators. Require complete signal
bars and verified context. Gaps block new entries; exits remain executable
at the next observed price. No future partial-bar count is used to decide an
entry at that bar's open.

Native-hourly close-to-close marking does not reveal intrahour drawdown. Stops
and profit targets are **close-confirmed**, filled at the following open,
not fictitious intrabar fills. ATR references are frozen native 1h ATR-24.
One position and one notional unit are used, with the shared engine's existing
long/reciprocal-short accounting and two-leg costs. Cost-free buy-and-hold is
reported for every identical window, alongside 0/2/5 bps strategy costs.

The configured `full` and `last_12m` windows retain their original bounds;
full includes initial calibration cash. Three additional non-overlapping
development windows provide diagnostics. Full/recent overlap and are not
independent validations. All data ends before the protected holdout.

## Round 1: one hundred fully specified rules

Two genuinely different entry mechanisms per source idea:

1. A fresh primary event or extreme with higher-timeframe direction alignment.
   Magnitude/risk inputs instead gate an explicit trend direction model.
2. A fresh primary event or extreme with candle confirmation and an efficiency
   regime. Magnitude/risk inputs instead gate an explicit mean-reversion model.

The two models have different directional/context clauses, not merely another
threshold or exit period. Every rule states its role, primary feature, fixed
context, expected failure mode and relationship to the existing registry.

## Round 1 analysis -> Round 2 registration

Analyze every result, not just the highest return. Report turnover, cost drag,
gross/net expectancy, exposure, zero-trade rules, drawdown, benchmark wins and
asset/time stability. Build round 2 only after round 1 is complete.

The deterministic adaptation policy consumes **only development_train**
outcomes, even though all windows are reported:

- Negative gross expectancy -> a newly defined causal failure-reversal episode.
- Empty entries -> delayed confirmation within six native hourly observations.
- Excessive turnover/cost drag -> six-hour persistent context confirmation.
- Otherwise -> a causal pullback-and-resumption episode after the trigger.

Each parent produces one new registered child, yielding 100 more rules. An
episode is evaluated as observations arrive, never labeled in retrospect.
Round 2's parameters, input analysis hash and all definitions are frozen before
its outcomes. This is adaptive development on already researched history;
round 2 is not fresh OOS evidence.

## Statistical and promotion limits

Primary tests compare mean weekly log equity return with buy-and-hold at 2 bps
in validation 1 and validation 2, per asset: `200*3*2=1200` tests. One BY family
contains those 1,200 and the 4,410 prior feature tests. Pending or unsupported
tests are `p=1`; cost scenarios and overlapping diagnostic windows are not
claimed as additional independent confirmations. Fixed paired circular
four-week resampling uses 999,999 draws; Monte Carlo resolution is checked
against the entire planned family.
Strategy p-values test positive outperformance (one-sided centered bootstrap);
large negative benchmark-relative returns do not count as alpha discoveries.

Require adequate trades/weeks, positive confidence interval and corrected
q-value on at least two assets in both validation slices, plus the existing
full/recent cross-market and trade-count bar. Passing development research
still does not authorize or nominate an OOS finalist. No OOS data or token is
used in either round. The broader legacy 827-configuration search remains a
disclosed limitation, not a retroactive universal error guarantee.

## Scope clarification: both feature research and execution

The user clarified “both, execute and research.” This extension was recorded
after the portfolio rounds completed, before the separate entry-feature label
study. Its fixed contract is `config/strategy_event_research_200.yml`, archived
under `research/strategies/SR-20261031-200/entry_feature_research/`.

Study each of the 200 **composite entry features** derived from the original
50 families. These are new feature hypotheses about conditional entry intent;
they are not 200 independent new primitive indicators. Outputs are -1/0/+1
at native hour close, with source missingness tracked separately. Episodes
ignore portfolio holdings, cooldowns and entry-clock blocking. Forward labels
require an adjacent next open and exit after 24 observed hourly bars, purged
at validation boundaries; later session gaps remain in labels.

Freeze ATR-percentage tertiles, direction strata and event-count weights on
2020-07-01–2023-01-01 training covariates. Keep only strata with 30 training
event samples and at least 50% training common-support mass. Greedily thin
events to non-overlapping 24-observation holdings. Compare with a fixed
non-overlapping grid in both directions, using the same paired calendar-week
resamples. Opposite-direction controls sharing a clock share bootstrap blocks;
they are not independent observations. Require 30 per arm, eight active weeks
and ten per retained cell. Unsupported tests stay at p=1.

The entry-feature target is signed cash return excess over matched controls,
separate from portfolio weekly benchmark excess and engine short accounting.
Add 1,200 primary entry-feature tests to the 4,410 prior and 1,200 portfolio
tests: final family **6,810**. Preserve the original 5,610-family outputs and
save new joint q-values separately. Original feature-study decisions remain
historical; expanded-family q-values can differ. The extension is fixed before
its own labels, not an external preregistration before all prior outcomes.
