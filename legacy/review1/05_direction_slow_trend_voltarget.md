# 05 — Direction D-A: Slow Trend + Volatility Targeting

> **Status: DRAFT v1 — not registered until the owner reviews and commits this file** (`04_*` §6). After the first
> result commit this file is immutable except via a dedicated `version` bump. Inherits `04_strategy_master_plan.md`
> §3 (success), §4 (gates), §5 (budgets), §7 (cost/metrics rules). Read `AGENTS.md` first.

## Hypothesis (why this should work)

Time-series momentum — holding the sign of the past return, scaled by risk — is the best-documented, persistent
return source across futures, currencies, metals and crypto. At **daily horizons** it trades a few to a few dozen
times per year, so the cost wall that killed 5m/1h indicator rules (median ~721 trades/year, per-trade edge well
below round-trip cost) does not apply. Risk scaling keeps the contribution of each instrument comparable and avoids
the dominance of one instrument's trend. Long/short positions mean the result is not "be long BTC".

What this direction deliberately does **not** claim: that it beats buy-and-hold. The criterion is positive net
absolute return with the guardrails of `04` §3 (notably beta ≤ 0.30 to the universe basket, which long-biased
variants will often fail — that is the guardrail working, not a bug).

## Prerequisites

- `03_*` D2 (daily bars with the Q1 21:00 UTC boundary and the daily feature set) — **required**.
- `02_*` E1 (weighted-position core). `03_*` D4/D5 only for the portfolio aggregation across instruments.
- `config/costs.yml` preferred (M4); otherwise run the uniform tiers and label "uniform-cost".

## Registration

```yaml
direction_id: D-A
version: 1
title: Slow trend + volatility targeting
status: draft            # informational only; git history is the authority
hypothesis: >
  Sign of past return at daily horizons, risk-scaled and long/short, earns a positive net return that is not
  explained by market beta and survives costs because turnover is low.
universe:
  instruments: [EUR_USD, XAU_USD, BTC_USD]
  timeframe: "1d"
  bar_boundary_utc: "21:00"
  evaluation_unit: equal_risk_portfolio      # also report per instrument
data_requires:
  - daily_bars_with_features                 # 03_* D2
  - weighted_position_core                   # 02_* E1
signals:
  tsmom_20:  {type: tsmom, lookback_days: 20}
  tsmom_60:  {type: tsmom, lookback_days: 60}
  tsmom_120: {type: tsmom, lookback_days: 120}
  tsmom_250: {type: tsmom, lookback_days: 250}
  tsmom_ens: {type: tsmom_ensemble, lookbacks_days: [20, 60, 120, 250]}   # mean of the four signs
  ma_10_50:  {type: ma_cross, fast_days: 10, slow_days: 50}
  ma_20_100: {type: ma_cross, fast_days: 20, slow_days: 100}
  ma_50_200: {type: ma_cross, fast_days: 50, slow_days: 200}
  don_20:    {type: donchian, n_days: 20}
  don_55:    {type: donchian, n_days: 55}
  don_100:   {type: donchian, n_days: 100}
  don_200:   {type: donchian, n_days: 200}
grid:
  signal: [tsmom_20, tsmom_60, tsmom_120, tsmom_250, tsmom_ens, ma_10_50, ma_20_100, ma_50_200, don_20, don_55, don_100, don_200]
  vol_target: [off, on]
  side: [long_short, short_half]      # short_half = short leg at 0.5 of the long-leg weight
excluded_combos: []
max_configs: 48                       # 12 x 2 x 2; must equal the enumerated grid
sizing:
  vol_target_on: {target_annual_vol: 0.10, realised_vol_window_days: 20, weight_cap: 2.0}
  vol_target_off: {unit_weight: 1.0}
  no_trade_band: 0.10                 # rebalance an instrument only if |target - current| > 0.10 of weight
  rebalance: daily_close              # decided at the 21:00 UTC close, applied at the next open
costs: instrument_model_if_available_else_uniform_tiers
windows: [full, last_12m]             # never oos
kill: >
  Closed if, after G2, no registered config has positive net return on the full window with a Holm-corrected
  p-value <= 0.10 (family-wise, over 48 configs).
```

## Signal definitions (all use bars up to and including day `t`, positions applied at the open of `t+1`)

- `tsmom_L`: `+1` if close[t] > close[t−L], else `−1` (`0` if fewer than `L` bars exist). `tsmom_ens`: mean of the four signs.
- `ma_f_s`: `+1` if SMA(f) > SMA(s), else `−1`.
- `don_N`: stateful. Go long when close[t] exceeds the highest high of the previous `N` days (excluding day `t`);
  go short when it breaks the lowest low; otherwise keep the previous side.
- `short_half`: when the signal is `−1`, the weight is half the magnitude it would have as a long.

## Evaluation procedure

1. `python scripts/run_direction.py --direction D-A --dry-run` — must print 48 configs and exit 0.
2. G1 screening (diagnostic only for this direction): record rank IC and gross-edge ÷ cost per signal (`02_*` E6).
3. G2: run all 48 configs on `full` and `last_12m` (cached, in-sample parallel; **never `oos`**); compute net return,
   `sharpe_weekly`, max drawdown, turnover, mean net position; Holm-corrected p-values (S-1) and S-7.
4. G3 on survivors: S-2 beta to the equal-weight basket, S-3 concentration, S-4 calendar years, S-5 2× cost,
   S-6 grid neighbours (for each parameter ±1 step; for `vol_target`/`side` the other value), S-8.
5. Generate `docs/directions/D-A_report.md` from result files (`02_*` E7). Every number must trace to committed results.
6. Update the registry (`Direction = D-A`) and `trial_log.md` (`direction`, `n_configs_direction_before`,
   `n_configs_global_before`). **Do not set `finalist`** — that is the owner's step (G4).

## Not allowed

- Adding a signal, lookback, parameter value or variant that is not in the grid (use `ideas.md`).
- Looking at `oos`; changing criteria after seeing results; re-running with a different grid under the same version.

## Definition of done

- [ ] Dry run prints exactly 48 configs; all G2/G3 outputs generated from the registered grid only.
- [ ] Report, registry rows and trial-log rows committed; checker (R1–R7) green; ledger file unchanged.
