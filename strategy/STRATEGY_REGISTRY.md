# Strategy Registry

> **Read first:** [STRATEGY_BACKGROUND.md](STRATEGY_BACKGROUND.md) — data contract,
> hard rules, and the new-strategy checklist.
>
> **Purpose:** single source of truth for every strategy in this project.
> Before starting a new strategy, check this registry so no strategy duplicates
> an existing indicator + timeframe + rule combination.
>
> **Rules of use:**
> 1. Every new strategy **must** get a row in the table below (update at creation, again after each major result change).
> 2. "Key indicators" lists the *decision-driving* features (not every column read).
> 3. Two strategies are considered **duplicates** if they share the same key indicators + timeframe + entry logic, regardless of parameter tweaks.
> 4. Status: `tested` (backtest run & reported) · `candidate` (designed, not yet run) · `rejected` (tested, failed, do not re-test without new hypothesis) · `parked` (deprioritized).

## Registry

| ID | Name | Timeframe | Key indicators | Entry logic (short) | Exit logic (short) | Side | Status | Code | Report | Last run | Result (ret vs BH) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| S-01 | RSI mean-reversion (base) | 5m | `rsi_24` | RSI_24 < 30 | RSI_24 > 55 | long | **rejected** | [code/strategy_rsi.py](code/strategy_rsi.py) | [docs/strategy_rsi_report.md](docs/strategy_rsi_report.md) | 2026-10-28 | full c2: −19.2% vs BH +2.3% (EUR_USD); −34.8% vs +1538% (BTC_USD) — 777 trades; cost × frequency (see report) |
| S-02 | RSI mean-reversion (1h) | 1h | `rsi_24` | RSI_24 < 30 | RSI_24 > 55 | long | **rejected** | [code/strategy_rsi_1h.py](code/strategy_rsi_1h.py) | [docs/strategy_rsi_1h_report.md](docs/strategy_rsi_1h_report.md) | 2026-10-29 | slower than S-01 (74–79 trades vs ~270) and less negative, but below buy-hold at every cost tier (full c2 EUR −7.93% vs +3.1%; BTC +17.1% vs +1288%; XAU +3.9% vs +110%) — signal quality, not frequency. See report §3. |
| S-03 | RSI + trend filter | 5m | `rsi_24`, `ema_24` | RSI_24 < 30 AND close > ema_24 | RSI_24 > 55 | long | **rejected** | [code/strategy_rsi_trend.py](code/strategy_rsi_trend.py) | [docs/strategy_rsi_trend_report.md](docs/strategy_rsi_trend_report.md) | 2026-10-29 | **0 trades** in all 18 cells: `rsi_24<30` and `close>ema_24` never co-occur on this data (verified intersection = 0 on EUR/BTC/XAU) — empty signal, not a bug. See report §3. |
| S-04 | Squeeze-onset follower | 5m | `sqz_on_24`, `bb_mid_24` | sqz onset (0→1) + direction by close vs bb_mid_24, held through episode | squeeze-off (1→0) | long/short | **rejected** | [code/strategy_squeeze.py](code/strategy_squeeze.py) | [docs/strategy_squeeze_report.md](docs/strategy_squeeze_report.md) | 2026-10-29 | cost × frequency: ~10,500 trades (full), ~1,900/yr — the "low-frequency" premise is false at 5m; below buy-hold at every cost tier incl. 0 bps (full c0 EUR −7.8% vs +2.3%; BTC −57.8% vs +1538%; XAU −20.9% vs +113%). See report §3. |
| S-05 | SuperTrend-24 direction follower | 5m | `st_dir_24_2` | st_dir_24_2 up | st_dir_24_2 down | long | **rejected** | [code/strategy_supertrend.py](code/strategy_supertrend.py) | [docs/strategy_supertrend_report.md](docs/strategy_supertrend_report.md) | 2026-10-28 | cost × frequency: 10,402 trades (full), below buy-hold at every cost tier on all 3 instruments (full c2 EUR −98.95% vs +2.3%; BTC −96.73% vs +1538%; XAU −98.23% vs +113%) → reject. See report §3. |
| S-06 | EMA-spread trend follower | 5m | `ema_spread_24_120` | spread > 0 | spread ≤ 0 | long | **rejected** | [code/strategy_ema_spread.py](code/strategy_ema_spread.py) | [docs/strategy_ema_spread_report.md](docs/strategy_ema_spread_report.md) | 2026-10-28 | not a cross-market edge: above buy-hold on BTC at **0 bps only** (full c0 +2402% vs BH +1538%), below buy-hold at 2/5 bps (+903/+154%); below buy-hold on EUR at every tier; below buy-hold on XAU at every tier. Long-only beta on a bullish BTC sample — see report §3. |
| S-07 | Regime-gated slow-trend follower | 1h | `st_dir_120_2`, `adx_24` | ST-120 flip while adx_24 > 25 | next ST-120 flip (or adx-weak flip → flat) | long/short | **rejected** | [code/strategy_regime_trend.py](code/strategy_regime_trend.py) | [docs/strategy_regime_trend_report.md](docs/strategy_regime_trend_report.md) | 2026-10-29 | low-frequency (~68/yr) as intended, but below buy-hold at **every** cost tier incl. 0 bps (full c0 EUR −5.1% vs +3.1%; BTC +73.6% vs +1288%; XAU −16.2% vs +110%) — signal quality, not frequency. See report §3. |

## Indicator usage map

Which key indicators are already *claimed* by tested/candidate strategies (helps spot overlap fast):

| Indicator | Used by |
|---|---|
| `rsi_24` | S-01, S-02, S-03 |
| `ema_24` | S-03 |
| `sqz_on_24` | S-04 |
| `bb_mid_24` | S-04 |
| `st_dir_24_2` | S-05 |
| `st_dir_120_2` | S-07 |
| `adx_24` | S-07 |
| `ema_spread_24_120` | S-06 |

## Rejected combinations — do not re-test without a new hypothesis

| Combination | Why rejected |
|---|---|
| 5m RSI_24 30/55 long-only (S-01) | Cost × frequency: 777 trades × 4 bps round-trip; per-trade edge (±0.03%) smaller than per-trade cost; below buy-hold at 2 bps on all 3 instruments. See [S-01 report](docs/strategy_rsi_report.md) §3. |
| 1h RSI_24 30/55 long-only (S-02) | Slower and less negative than S-01, but below buy-hold at every cost tier (0 bps: EUR −5.2%, BTC +21%, XAU +6.7% all < buy-hold). Signal quality, not frequency. See [S-02 report](docs/strategy_rsi_1h_report.md) §3. |
| 5m RSI_24 < 30 AND close > ema_24 (S-03) | Empty signal: the two predicates never co-occur on this data (verified intersection = 0 on all 3 instruments). Not re-testable without a new, mismatched-window rule. See [S-03 report](docs/strategy_rsi_trend_report.md) §3. |
| 5m squeeze-onset long/short (S-04) | Cost × frequency: ~10,500 trades (full); below buy-hold at every cost tier incl. 0 bps. The "low-frequency" premise is false at 5m (the squeeze fires ~1,900 times/yr, not rarely). [matrix](results/S04/matrix.md) |
| 1h ADX-gated SuperTrend-120 (S-07) | Signal quality: low-frequency (~68/yr) as intended, but below buy-hold at every cost tier incl. 0 bps on all 3 instruments. See [S-07 report](docs/strategy_regime_trend_report.md) §3. |
| 5m SuperTrend 24/2 follower (S-05) | Cost × frequency: 10,402 trades (full); below buy-hold at every cost tier on all 3 instruments. [matrix](results/S05/matrix.md) |
| 5m EMA-spread 24/120 follower (S-06) | Not cross-market: above buy-hold on BTC only, and only at 0 bps; below buy-hold on EUR/XAU at every cost tier. Single-instrument fit, not a general edge. [matrix](results/S06/matrix.md) |

## Conventions

- **ID scheme:** `S-NN`, never reuse a rejected ID; open a new one and reference the old in the row notes.
- **Shared engine (required):** every strategy must run its backtest through
  [`engine.py`](engine.py) (`run_backtest`) for accounting + metrics, rather than
  re-implementing fills/costs/Sharpe inline. This keeps fill-at-open-T+1, both-legs cost,
  long/short handling, force-close and the annualised Sharpe identical across strategies —
  the source of the T0 fixes (see `docs/SAD.md` §7.2 for the locked formulas).
- **Shared strategy core (required):** every new strategy builds on
  [`strategy_lib.py`](strategy_lib.py) for parquet loading, the timeframe guard,
  the bar-frame build and the run wrapper (plus the trade-distribution metric),
  and only declares *what signal* it trades (a rule builder + the columns it
  reads). See [`strategy_supertrend_lib.py`](strategy_supertrend_lib.py) and
  [`strategy_ema_spread_lib.py`](strategy_ema_spread_lib.py) as references.
  (S-01's [`strategy_rsi_lib.py`](strategy_rsi_lib.py) predates the core but
  exposes the same `run`/`load_bars` surface.)
- **Shared strategy lib (preferred):** keep the signal rule in a
  `strategy/strategy_<name>_lib.py` module and expose it as a thin CLI in
  `strategy/code/strategy_<name>.py`. The lib is also what `run_matrix.py`
  calls, so the matrix runner and the CLI never diverge.
- **Result column:** latest full-history result for the *primary* instrument, plus buy-hold reference. State the cost tier(s) and the entry-guard setting used.
- **Cost assumption:** 2 bps one-way (OANDA CFD spread) unless the report states otherwise.
- **No-lookahead:** every strategy must signal on a closed bar and fill at the next bar's open (spec §3.3); the engine enforces the fill convention.
- **Timeframe:** state the bar frequency in the row (5m or 1h); the code must accept `--timeframe` and guard bar length (B1) so a 1h strategy can never silently run on 5m data.
- **Report location (B3):** strategy reports live under `strategy/docs/` (linked from the Report column); the report is written **after** the OOS gate (Step 6) passes.
- **Trial log (best-of-N discipline):** every attempt is a row in [`trial_log.md`](trial_log.md) **before** tuning stops; OOS holdout usage follows `config/strategies.yml` (`finalist_only_once`).
- **Matrix runner:** the standard 3×2×3 evaluation is automated by [`run_matrix.py`](run_matrix.py)
  (18 cells → `strategy/results/<ID>/` JSON + `matrix.md` + `summary.csv`); G5 traceability
  means every report number is copied from those artifacts.
