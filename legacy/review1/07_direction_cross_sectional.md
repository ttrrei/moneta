# 07 — Direction D-C: Cross-Sectional (Many Instruments, Dollar-Neutral)

> **Status: DRAFT v1 — not registered until the owner fills the universe, reviews and commits this file**
> (`04_*` §6). Immutable after the first result commit except via a `version` bump. Inherits
> `04_strategy_master_plan.md` §3–§7. Read `AGENTS.md` first.

## Hypothesis

Ranking instruments against each other and holding the strongest long / weakest short, dollar-neutral, produces
returns that do **not** depend on the market's direction. That removes the problem that sank the legacy search
(every result was a bet on one instrument, mostly `BTC_USD`) and the buy-and-hold yardstick no longer applies.
Using many instruments also increases the number of independent observations per period, which is the only way
small edges become statistically visible. Momentum (strong stays strong) and reversal (short-term overshoot) are
tested at several horizons; a volatility-adjusted momentum variant guards against ranking only by volatility.

Caution built into the design: FX pairs share currency legs, so the effective number of independent bets is smaller
than the instrument count. Exposure caps per currency and portfolio-level bootstrap statistics handle this.

## Prerequisites (all required before the first run)

- `03_*` D0 and the owner's decision Q3: `docs/instrument_inventory.md` lists the instruments with ≥ 5 years of
  history and acceptable gaps. **The owner copies that final list into `universe.instruments` below before committing.**
  While the list is empty, R1 fails and `run_direction.py` refuses to run — that is intentional.
- `03_*` D1 (multi-instrument tables), D2 (daily bars), D4 (calendar and staleness), D5 (return matrices).
- `02_*` E1 portfolio mode.
- `config/costs.yml` filled by the owner for **every** instrument in the universe (M4): turnover costs differ
  greatly across instruments, so this direction does **not** run on the uniform tiers.

## Registration

```yaml
direction_id: D-C
version: 1
title: Cross-sectional momentum / reversal, dollar-neutral
status: draft
hypothesis: >
  Rank-based long/short portfolios across many instruments earn positive net absolute return that is independent of
  market direction and survives instrument-specific costs.
universe:
  instruments: []                    # OWNER MUST FILL from docs/instrument_inventory.md (Q3) before committing
  timeframe: "1d"
  bar_boundary_utc: "21:00"
  min_eligible_per_rebalance: 6      # skip a rebalance with fewer eligible instruments
  evaluation_unit: dollar_neutral_portfolio
data_requires:
  - daily_bars_with_features
  - multi_instrument_tables
  - calendar_alignment_and_staleness
  - return_matrices
  - instrument_cost_model
  - weighted_position_core
signals:
  xsm_20:  {type: xs_momentum, lookback_days: 20}
  xsm_60:  {type: xs_momentum, lookback_days: 60}
  xsm_120: {type: xs_momentum, lookback_days: 120}
  xsm_250: {type: xs_momentum, lookback_days: 250}
  xsr_1:   {type: xs_reversal, lookback_days: 1}
  xsr_5:   {type: xs_reversal, lookback_days: 5}
  xsv_60:  {type: xs_vol_adj_momentum, lookback_days: 60, vol_window_days: 20}
  xsv_120: {type: xs_vol_adj_momentum, lookback_days: 120, vol_window_days: 20}
grid:
  signal: [xsm_20, xsm_60, xsm_120, xsm_250, xsr_1, xsr_5, xsv_60, xsv_120]
  rebalance: [daily, weekly]
  weighting: [equal_risk, rank_weighted]
excluded_combos:
  - {signal: xsr_1, rebalance: weekly}   # 1-day reversal is meaningless at a weekly rebalance (2 combos: one per weighting)
max_configs: 30                       # 8 x 2 x 2 - 2; must equal the enumerated grid
sizing:
  selection_fraction: 0.33            # long top third, short bottom third of eligible instruments
  dollar_neutral: true                # sum of long weights = sum of short weights; total gross = 1.0
  per_instrument_cap: 0.25            # of gross
  per_currency_cap: 0.30              # of gross; FX pairs decomposed into currency legs
  equal_risk: {weight_proportional_to: inverse_realised_vol_20d}
  rank_weighted: {weight_proportional_to: rank_distance_from_median}
costs: instrument_model_required
windows: [full, last_12m]             # never oos
kill: >
  Closed if, after G2, no registered config has positive net return on the full window with a Holm-corrected
  p-value <= 0.10 (over 30 configs).
```

## Definitions

- **Eligible instrument at a rebalance:** has a valid, non-stale price at the rebalance timestamp (`03_*` D4).
- `xsm_L`: rank by the `L`-day return; `xsr_L`: rank by the **negative** `L`-day return; `xsv_L`: rank by the `L`-day
  return divided by 20-day realised volatility. Longs = top third, shorts = bottom third.
- `daily`: rebalance at every daily close (21:00 UTC boundary); `weekly`: at the last daily close of the ISO week.
- Weights are applied at the next open. Turnover costs use the instrument model on every changed weight.
- Portfolio beta (S-2) is measured against the equal-weight basket of the **same universe** (≈ 0 by construction;
  reported to confirm).

## Evaluation procedure

1. Confirm `universe.instruments` is filled and `config/costs.yml` has no `null` for them; otherwise stop and report.
2. `python scripts/run_direction.py --direction D-C --dry-run` — prints 30 configs, exit 0.
3. G1 diagnostic (`02_*` E6): per-instrument rank IC and cost ratio for each signal.
4. G2: run the 30 configs on `full`/`last_12m` (in-sample only, cached, parallel); net return, `sharpe_weekly`,
   max drawdown, turnover, per-currency exposure, PnL share by instrument; Holm p-values (S-1) and S-7.
5. G3 on survivors: S-2 … S-6, S-8.
6. Generate `docs/directions/D-C_report.md` from result files; update the registry (`Direction = D-C`) and
   `trial_log.md`. **Do not set `finalist`.**

## Not allowed

- Adding signals, horizons, fractions or weightings; dropping instruments after seeing results; filling missing costs
  with guesses; looking at `oos`.

## Definition of done

- [ ] Universe and costs filled by the owner; dry run prints exactly 30 configs.
- [ ] All outputs generated from the registered grid; report, registry and trial-log rows committed; checker green;
      ledger file unchanged.
