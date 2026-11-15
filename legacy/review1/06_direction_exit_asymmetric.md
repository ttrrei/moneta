# 06 — Direction D-B: Exit Design and Payoff Asymmetry

> **Status: DRAFT v1 — not registered until the owner reviews and commits this file** (`04_*` §6). Immutable after
> the first result commit except via a `version` bump. Inherits `04_strategy_master_plan.md` §3–§7 plus the
> direction-specific guardrail **S-9** below (recorded in `oos.success_criteria_by_direction` at registration).
> Read `AGENTS.md` first.

## Hypothesis

Entry rules carry little edge on their own; much of a trading system's payoff shape comes from **how positions are
closed**: cutting losers (stops), letting winners run (trailing stops), limiting dead time (time stops) and capping
variance (targets). Long and short sides may deserve **different** treatment (short moves are faster and more
violent). The danger: exit rules applied to a trending asset can look good simply because the asset trended. So every
exit design is compared with **the same exit applied to random entries** — an exit "adds value" only if it beats
what the exit alone produces on entries that contain no information.

## Prerequisites

- `03_*` D2 (daily bars and features: ATR 20d, realised vol 20d), D3 optional.
- `02_*` E1 including `strategy/core/exits.py` (ATR trailing, fixed stop, target in R, time stop) — **required**.
- Random-entry control generator (part of `scripts/run_direction.py`, seeded, deterministic).

## Registration

```yaml
direction_id: D-B
version: 1
title: Exit design and payoff asymmetry
status: draft
hypothesis: >
  Exit design (trailing stop, time stop, target) and long/short asymmetry improve net absolute return and
  drawdown relative to signal-reversal exits, beyond what the same exits earn on random entries.
universe:
  instruments: [EUR_USD, XAU_USD, BTC_USD]
  timeframe: "1d"
  bar_boundary_utc: "21:00"
  evaluation_unit: equal_risk_portfolio
data_requires:
  - daily_bars_with_features
  - weighted_position_core
  - exit_state_machine
signals:
  don_55_ls:    {type: donchian_entry, n_days: 55}      # entry event = fresh breakout of the prior 55-day extreme
  tsmom_120_ls: {type: tsmom_entry, lookback_days: 120} # entry event = sign change of 120-day return
exits:
  signal_reversal: {type: reverse_on_opposite_signal}      # baseline; no stop
  atr_trail_2: {type: atr_trailing, atr_days: 20, k: 2}
  atr_trail_3: {type: atr_trailing, atr_days: 20, k: 3}
  atr_trail_4: {type: atr_trailing, atr_days: 20, k: 4}
  time_10d: {type: time_stop, days: 10}
  time_20d: {type: time_stop, days: 20}
  time_40d: {type: time_stop, days: 40}
  target_2R: {type: stop_and_target, stop_atr_k: 2, target_r: 2}   # 1R = 2 x ATR20 at entry
  target_3R: {type: stop_and_target, stop_atr_k: 2, target_r: 3}
asymmetry:
  sym: {}
  short_tight: {short_distance_multiplier: 0.75, short_time_stop_multiplier: 0.5}
grid:
  signal: [don_55_ls, tsmom_120_ls]
  exit: [signal_reversal, atr_trail_2, atr_trail_3, atr_trail_4, time_10d, time_20d, time_40d, target_2R, target_3R]
  asymmetry: [sym, short_tight]
excluded_combos:
  - {exit: signal_reversal, asymmetry: short_tight}   # no distances to tighten; identical to sym (2 entries -> 2 combos)
max_configs: 34                       # 2 x 9 x 2 - 2; must equal the enumerated grid
sizing:
  vol_target: {target_annual_vol: 0.10, realised_vol_window_days: 20, weight_cap: 2.0}
  rebalance: daily_close
controls:
  random_entry: {draws_per_config: 200, seed: 20261101, match: [entries_per_instrument, side_mix]}   # diagnostic; not counted as configs
costs: instrument_model_if_available_else_uniform_tiers
windows: [full, last_12m]             # never oos
kill: >
  Closed if, after G2, no registered config has positive net return on the full window with a Holm-corrected
  p-value <= 0.10 (over 34 configs) AND S-9 satisfied.
```

## Mechanics (fixed; do not vary)

- Positions are decided at the close of day `t` and applied at the open of `t+1`. Sizing = vol-target weight at entry.
- **After a stop, target or time exit the position stays flat until the entry signal produces its next fresh event**
  (a new breakout or a new sign change). No immediate re-entry into the same state.
- Stop/target logic on daily bars: if the day's range touches the level, fill at the level; if the open gaps beyond it,
  fill at the open. **If stop and target are both touched on the same day, assume the stop hit first** (conservative).
- `atr_trailing`: stop = highest close since entry − k×ATR20 (long) / lowest close since entry + k×ATR20 (short),
  updated at each close, effective the next day.
- `short_tight`: all short-side stop/target distances ×0.75 and short time stops ×0.5 (rounded up).
- Costs apply on turnover for every exit as for entries.

## Direction-specific guardrail

- **S-9 (control):** a config's net return on the `full` window must exceed the **95th percentile** of the
  random-entry control distribution for the **same exit design, asymmetry and sizing**. Report the percentile rank.
  Also report, as a diagnostic, the improvement of each exit over `signal_reversal` for the same entry.

## Evaluation procedure

1. `python scripts/run_direction.py --direction D-B --dry-run` — prints 34 configs, exit 0.
2. G2: run the 34 configs plus the random-entry controls (200 draws each, deterministic, cached) on `full`/`last_12m`.
3. G3: S-1 (Holm over 34), S-2 … S-8, S-9.
4. Generate `docs/directions/D-B_report.md` from result files; update registry (`Direction = D-B`) and `trial_log.md`.
5. **Do not set `finalist`.**

## Not allowed

- New exit types, new multipliers or extra entries (use `ideas.md`); using exits chosen from the legacy sweeps;
  looking at `oos`; changing mechanics after seeing results.

## Definition of done

- [ ] Dry run prints exactly 34 configs; controls generated deterministically; S-9 reported for every config.
- [ ] Report, registry rows, trial-log rows committed; checker green; ledger file unchanged.
