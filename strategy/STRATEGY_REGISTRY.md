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
| S-01 | RSI mean-reversion (base) | 5m | `rsi_24` | RSI_24 < 30 | RSI_24 > 55 | long | **rejected** | [code/strategy_rsi.py](code/strategy_rsi.py) | [docs/strategy_rsi_report.md](docs/strategy_rsi_report.md) | 2026-10-26 | −21.6% vs +0.3% (EUR_USD); −41.9% vs +1031% (BTC_USD); entry-guard **off** (see matrix [results/S01](results/S01/matrix.md)) |
| S-02 | RSI mean-reversion (1h) | 1h | `rsi_24` | RSI_24 < 30 | RSI_24 > 55 | long | candidate | — | — | — | (planned: same rule, 1/12 the trade count & cost of S-01) |
| S-03 | RSI + trend filter | 5m | `rsi_24`, `ema_24` | RSI_24 < 30 AND close > ema_24 | RSI_24 > 55 | long | candidate | — | — | — | (planned: trade only with the trend) |
| S-04 | Squeeze release | 5m | `sqz_on_24`, `bb_mid_24` | sqz_on_24 = 1 + direction vs bb_mid_24 | RSI-style or time stop | long/short | candidate | — | — | — | (planned: volatility-compression event, far fewer trades) |
| S-05 | SuperTrend follower | 5m | `st_dir_24_2` | st_dir_24_2 up | st_dir_24_2 down | long | **rejected** | [strategy_supertrend_lib.py](strategy_supertrend_lib.py) | [results/S05/matrix.md](results/S05/matrix.md) | 2026-10-27 | Loses on all 3 instruments once cost ≥ 2 bps (BTC last-12m c0 +28.7% vs BH +77%, c2 −38%); ~1,900 trades over-trades. Slower 60/3 & 120/3 never beat buy-hold either → cost × frequency, reject. |
| S-06 | EMA-spread trend follower | 5m | `ema_spread_24_120` | spread > 0 | spread ≤ 0 | long | **rejected** | [strategy_ema_spread_lib.py](strategy_ema_spread_lib.py) | [results/S06/matrix.md](results/S06/matrix.md) | 2026-10-27 | **BTC-only edge**: beats buy-hold on BTC across all 3 cost tiers (full c0/c2/c5 = +2421/+911/+157% vs BH +1536%), but **loses on EUR and XAU** (full c2/c5 −66/−92%, −33/−83%) — single-instrument, not cross-market → not promotable. |

## Indicator usage map

Which key indicators are already *claimed* by tested/candidate strategies (helps spot overlap fast):

| Indicator | Used by |
|---|---|
| `rsi_24` | S-01, S-02, S-03 |
| `ema_24` | S-03 |
| `sqz_on_24` | S-04 |
| `bb_mid_24` | S-04 |
| `st_dir_24_2` | S-05 |
| `ema_spread_24_120` | S-06 |

## Rejected combinations — do not re-test without a new hypothesis

| Combination | Why rejected |
|---|---|
| 5m RSI_24 30/55 long-only (S-01) | Cost × frequency: ~1,000 trades × 4 bps round-trip ≈ 40% of equity paid in spread; per-trade edge (±0.03%) smaller than per-trade cost. See [S-01 report](docs/strategy_rsi_report.md) §3. |
| 5m SuperTrend 24/2 follower (S-05) | Cost × frequency: ~1,900 trades (last-12m); only c0 is even positive, and never beats buy-hold; slower 60/3 & 120/3 variants never beat buy-hold either. [matrix](results/S05/matrix.md) |
| 5m EMA-spread 24/120 follower (S-06) | Not cross-market: beats buy-hold on BTC only; loses on EUR/XAU at cost ≥ 2 bps. Single-instrument fit, not a general edge. [matrix](results/S06/matrix.md) |

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
