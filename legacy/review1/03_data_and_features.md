# 03 — Data and Features (prerequisites for the new directions)

> Baseline commit `936f7b9`. Read `AGENTS.md` first. The three registered directions need data the repo
> does not have today: **slower bars, more instruments, structure features, per-instrument costs**. This file
> produces them. It adds *inputs*, never strategies, and it never exposes holdout data.

## 0. What exists today

- Feature tables: `data/ohlcv_5m_features/ohlcv_5m_features.parquet` and
  `data/ohlcv_1h_features/ohlcv_1h_features.parquet`, built by `pipeline/` (see `pipeline/indicators.py`,
  `config/indicators.yml`). Instruments in the strategy config: `EUR_USD`, `XAU_USD`, `BTC_USD` only.
- 1h-native columns reach 5m rows through a point-in-time as-of join keyed on the 1h bar's **close** time
  (verified causal). Rows carry gap/market-close flags (`is_gap_bar`, `is_near_market_close`).
- Cost model in strategy runs: one uniform tier set `0 / 2 / 5 bps` for all three instruments.

## 1. Rules specific to this file

- **Causality is a tested property.** Every new feature gets a truncation test: computing it on data cut at time `T`
  must give the same values for all rows `<= T` as computing it on the full series.
- **Swing/pivot features need a confirmation lag** (a swing high is only known `n` bars later). Stamp the feature
  at the confirmation bar, never at the pivot bar.
- **No holdout exposure.** New tables are built on the full series, then split exactly as in `01_*` S2.1 (holdout
  rows go to the separate file, never to the default in-sample table).
- **Do not guess costs.** The owner supplies real spreads/financing (task D7). Until then run all three legacy tiers
  and label results "uniform-cost, not instrument-specific".
- Tasks tagged **[LOCAL DATA]** need the source data. If you cannot reach it, skip, list it, and fabricate nothing.

## 2. Decisions (defaults apply unless the owner edits this table)

| # | Decision | Default |
|---|----------|---------|
| Q1 | Daily bar boundary | **21:00 UTC** (FX convention, matches the session anchors already used for VWAP). Document DST handling explicitly. |
| Q2 | Rebalance timestamp for cross-sectional/daily work | Daily bar close at the Q1 boundary; weekly = last daily close of the ISO week. |
| Q3 | Instrument universe for D-C | All instruments for which the source has ≥ 5 years of M1 history and acceptable gap statistics (D0 decides); report the list. |

---

## Phase D0 — inventory  [LOCAL DATA]

- Document the full path **raw data → feature parquet** (source system/table, extraction script, aggregation to
  5m/1h, indicator step, as-of join). Write `docs/data_lineage.md`.
- Produce `docs/instrument_inventory.md`: for every instrument available in the source — first/last timestamp,
  bar count, gap statistics (share of gap bars, longest gap), trading-hours pattern (24/7, FX weekly close, metals
  breaks), and whether M1/5m/1h tables exist. This decides Q3.
- State which instruments the current feature tables contain and what is missing for the others.

## Phase D1 — multi-instrument feature tables  [LOCAL DATA]

- Extend the pipeline so the **same schema** is produced for every instrument selected in Q3, for 5m and 1h.
  Keep the existing three instruments' values **byte-identical** (regression test on a sample of rows).
- Parameterise the pipeline by an instrument list in config (no hard-coded three).
- Add per-instrument data-quality checks to the pipeline output (duplicates, non-monotonic time, zero/negative
  prices, impossible OHLC, extreme returns); fail the build on violations and write a short quality report.

## Phase D2 — daily and weekly bars

- Resample from the 1h table (not from 5m) using the Q1 boundary. Columns: `open, high, low, close, volume`,
  `n_bars`, `is_partial` (incomplete session), `session_date`. Weekend/holiday handling must be explicit and
  documented per instrument class.
- Feature set for slow work (all causal): returns over 1/5/20/60/120/250 days; realised volatility (20/60 days,
  close-to-close and range-based); ATR (20 days); moving averages (20/50/100/200 days) and distances; Donchian
  highs/lows (20/55/100 days); rolling skew and drawdown from the 250-day high.
- Tests: aggregation of 1h→daily equals a direct computation on a hand-built example; partial days flagged.

## Phase D3 — structure features (point-in-time)

- Prior day / prior week / prior month: high, low, close; distance of the current price to each in ATR units.
- Session ranges (Asia / London / New York, UTC definitions in config): current-session high/low so far, prior
  session high/low/close, opening-range (first N minutes) high/low.
- Pivot points from prior-period H/L/C; distance to the nearest round number (per instrument tick-size rule in
  config).
- Swing highs/lows with a configurable confirmation lag `n` (e.g. 3, 5, 10 bars) and the distance to the last
  *confirmed* swing high/low. **Stamp at confirmation time** (see rules).
- Tests: causality truncation test for every feature; a hand-built example for swing confirmation lag.

## Phase D4 — calendar alignment for cross-sectional work

- A single calendar object: for each rebalance timestamp (Q2) and each instrument, the last valid bar at or before
  it, with a staleness flag (`bars_since_last_trade`). Instruments that do not trade at the timestamp (FX weekend,
  holidays) are excluded from that rebalance by rule, not silently filled.
- Tests: Friday close, weekend, and a holiday case for an FX pair vs `BTC_USD`.

## Phase D5 — return matrices for the portfolio core

- Produce aligned `T × N` matrices (open, close, high, low, return) on the Q2 calendar for the Q3 universe, stored
  under `.cache/arrays/` (see `02_*` E4). Include the staleness mask. These feed `strategy/core/sim.py`.

## Phase D6 — data-split and fingerprint integration

- Apply the physical holdout split (`01_*` S2.1) to every new table (daily, weekly, structure, multi-instrument).
- Extend `data_fingerprint` to cover the new tables; the manifest (`01_*` S3.1) records them.

## Phase D7 — cost model (owner supplies numbers)

- Config structure in `config/costs.yml` (new):
  ```yaml
  costs:
    EUR_USD: {half_spread_bps: null, slippage_bps: null, financing_bps_per_day_long: null, financing_bps_per_day_short: null}
    # one entry per instrument in the universe
  ```
  `null` means "owner has not supplied"; the simulator then refuses to run a direction that requires the
  instrument-specific model and tells the owner what is missing.
- The simulator charges: half-spread + slippage on turnover; financing/rollover on held notional if provided.
- Until the owner fills it in, directions run with the uniform `0 / 2 / 5 bps` tiers and every report carries the
  label "uniform-cost".

## Phase D8 — documentation and checks

- `docs/feature_catalogue.md`: every new column — definition, window, causality note, source table. Generated from
  a machine-readable manifest (`config/features.yml`), verified by a checker rule (every produced column is
  catalogued; every catalogued column exists).
- Checker additions: new tables have no row `>= holdout_start`; every new feature has a registered causality test.

## Dependencies

| Direction | Needs |
|---|---|
| D-A slow trend + vol-target | D2 (daily features), D4/D5 only for portfolio aggregation |
| D-B exit / asymmetric design | D2, D3 (ATR/structure for stops), `02_*` E1 exits |
| D-C cross-sectional | D0, D1, D2, D4, D5, D7 (instrument-specific costs strongly preferred) |

## Out of scope

- Any strategy logic; alternative data (news, order flow) — not available; changing holdout dates.

## Definition of done

- [ ] `docs/data_lineage.md`, `docs/instrument_inventory.md` exist (local data).
- [ ] Multi-instrument tables, daily/weekly bars, structure features built; existing values byte-identical.
- [ ] Causality truncation test for every new feature; calendar tests; split applied to all new tables.
- [ ] `config/costs.yml` structure present with `null`s; simulator refuses silently-missing costs.
- [ ] pytest, self-test and checker green; ledger file unchanged.
