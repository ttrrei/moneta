# Strategy Generation Brief

> **Mission:** Design, implement, backtest, register, and report **one** new
> candidate strategy for this repo. Do not invent data, features, or rules that
> aren't in the docs below. If anything is missing from them, stop and ask.
>
> **Execution:** this file defines *what* to generate. The *how* — the ordered
> action list with commands and gates — is in [WORKFLOW.md](WORKFLOW.md).
> Read this file first, then execute WORKFLOW.md end to end.

## 1. Read before you think (in this order, all required)

1. `docs/README.md` — project index, the 6 non-negotiable rules, repo map.
2. `strategy/STRATEGY_BACKGROUND.md` — data contract, feature columns, hard rules §4.
3. `strategy/STRATEGY_REGISTRY.md` — **every strategy already tried.** Your idea
   must not duplicate any row (same key indicators + timeframe + entry logic =
   duplicate, regardless of parameter tweaks).
4. `strategy/docs/strategy_rsi_report.md` — the rejected baseline and WHY it
   failed (cost × frequency boundary).
5. `config/indicators.yml` — the exact feature column list + parameter grid.
   (If it disagrees with `pipeline/indicators.py`, the code wins.)

## 2. Hard constraints (violation = automatic reject)

- **Causality:** signal on a CLOSED bar T → fill at open of bar T+1. Never
  same-bar fill, never `shift(-k)`, never repaint.
- **Features:** only columns that exist in `ohlcv_5m_features` /
  `ohlcv_1h_features`. Windows only from `{6,12,24,60,120}`. No new indicators.
- **Data:** no synthetic filling. `is_gap_bar` / `is_partial` are inputs, not
  things to fix. `h1_*` columns are already lookahead-safe; use them as-is.
- **Cost:** 2 bps one-way at entry AND exit.
- **No duplicate of registry rows** (including rejected ones — a rejected row
  needs a NEW hypothesis, not a retune).

## 3. Design requirements (the bar to clear)

The S-01 baseline showed: ~1,000 trades × 4 bps round-trip ≈ 40% of equity paid
in spread while edge/trade ≈ 0.03%. Your strategy must structurally beat that:

- **Trade count target:** ≤ ~150 trades over full history on a primary
  instrument (sparse signals: squeeze releases, regime gates,
  higher-timeframe triggers, multi-condition entries). State your expected
  frequency in the registry row BEFORE running.
- **Prefer:** conditions combining ≥2 feature families (e.g. volatility
  `sqz_on_*` + trend `er_*`/`ema_dist_*` + momentum), a 1h context gate via
  `h1_*` columns, or a 1h entry with a 5m exit.
- **Both sides:** long and short rules are preferred; if long-only, justify
  why in the report.
- **State your hypothesis in one sentence:** why this should have edge, in
  what regime it works, when it will bleed.

## 4. Output contract (exact shape)

1. **Register first:** append a `candidate` row to [STRATEGY_REGISTRY.md](STRATEGY_REGISTRY.md)
   (next `S-NN`, never reuse a rejected ID); update the indicator usage map.
2. **Code:** `code/strategy_<name>.py` — self-contained CLI with
   `--instrument --since --parquet --cost-bps --json`, DuckDB-filtered load,
   same JSON metrics block as `strategy_rsi.py` (n_trades, win_rate_pct,
   total_return_pct, buyhold_return_pct, max_drawdown_pct,
   avg_trade_return_pct, sharpe, exposure_pct).
3. **Run protocol (mandatory, all of it):**
   - Instruments: **EUR_USD + BTC_USD + XAU_USD**
   - Windows: **full history** and **last 12 months**
   - Costs: **0 / 2 / 5 bps** sensitivity table
4. **Report:** `docs/strategy_<name>_report.md` with:
   hypothesis → results vs buy-and-hold → why it wins/loses → cost sensitivity →
   regime breakdown → honest caveats (in-sample, no slippage, per-instrument).
5. **Update registry:** status (`tested`/`rejected`/`parked`), last run,
   result (ret vs BH). A failure is a valid, valuable output — record it.

## 5. Stop & report (don't force a result)

Stop and report as `rejected` with diagnosis if ANY of:
- total_return < buyhold AND avg_trade < round-trip cost at 0/2/5 bps;
- trade count > 300 (structurally uneconomic, see §3);
- edge appears on < 1 of 3 instruments OR only in < 1 of 2 windows
  (likely overfit, not alpha).

## 6. Anti-patterns (instant reject)

- Hand-rolled indicators instead of the feature columns.
- Optimizing thresholds until the curve looks good (the report must show a
  pre-registered rule chosen from the design, not from the results).
- Long-only dip-buying in strong downtrends with no regime filter (S-01).
- Treating `volume` as real volume (it is OANDA tick count = activity proxy).
