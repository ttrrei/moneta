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
> 4. Status vocabulary (lifecycle order): `candidate` (designed, not yet run) · `finalist` (passed the in-sample bar, **OOS pending** — the only status that may consume the holdout) · `tested` (passed the single OOS evaluation) · `parked` (deprioritized) · `rejected` (failed, do not re-test without a new hypothesis).
>    A row is promoted to `finalist` **by a human** only when no §5 stop condition triggered AND total_return > buy-hold at 2 bps on **≥ 2 of 3 instruments on both `full` and `last_12m`** (see `config/strategies.yml → oos.pass_criteria`). `tested` is reached only by passing the single OOS evaluation.

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
| S-08 | CCI-24 dip-buying | 5m | `cci_24`, `bb_pctb_24` | CCI down-cross < 100 while bb_pctb < 0.5 | CCI ≥ exit level | long | **rejected** | [code/strategy_cci_reversion.py](code/strategy_cci_reversion.py) | [docs/strategy_sweep_2026-10-30.md](docs/strategy_sweep_2026-10-30.md) | 2026-10-30 | best variant `1h` (edge −261.95 @2bps); no variant beat BH on ≥2/3 instruments — see sweep report |
| S-09 | Williams %R-24 rebound buyer | 5m | `willr_24` | %R down-cross < −70 | %R up-cross > −40 | long | **rejected** | [code/strategy_willr.py](code/strategy_willr.py) | [docs/strategy_sweep_2026-10-30.md](docs/strategy_sweep_2026-10-30.md) | 2026-10-30 | 6-iteration sweep in `results/iterations_2026-10-30.csv` — see sweep report |
| S-10 | Stochastic-24 oversold-turn | 5m | `stoch_k_24`, `stoch_d_24` | K up-cross of D with K < 30 | K down-cross of D | long | **rejected** | [code/strategy_stoch.py](code/strategy_stoch.py) | [docs/strategy_sweep_2026-10-30.md](docs/strategy_sweep_2026-10-30.md) | 2026-10-30 | 6-iteration sweep in `results/iterations_2026-10-30.csv` — see sweep report |
| S-11 | MACD-12/60 momentum turn | 5m | `macd_12_60`, `macd_hist_12_60`, `atr_24` | MACD up-cross of 0 with hist/ATR ≥ 0.05 | MACD down-cross of 0 | long | **rejected** | [code/strategy_macd.py](code/strategy_macd.py) | [docs/strategy_sweep_2026-10-30.md](docs/strategy_sweep_2026-10-30.md) | 2026-10-30 | 6-iteration sweep in `results/iterations_2026-10-30.csv` — see sweep report |
| S-12 | Dual-velocity (ROC + slow-EMA slope) | 5m | `roc_24`, `ema_120` | roc_24 > 0 and ema_120 rising over lag 24 | either condition fails | long | **rejected** | [code/strategy_dual_velocity.py](code/strategy_dual_velocity.py) | [docs/strategy_sweep_2026-10-30.md](docs/strategy_sweep_2026-10-30.md) | 2026-10-30 | 6-iteration sweep in `results/iterations_2026-10-30.csv` — see sweep report |
| S-13 | Slow PSAR-0.01/0.1 direction follower | 5m | `psar_dir_0p01_0p1` | PSAR direction up | PSAR direction down | long | **rejected** | [code/strategy_psar.py](code/strategy_psar.py) | [docs/strategy_sweep_2026-10-30.md](docs/strategy_sweep_2026-10-30.md) | 2026-10-30 | 6-iteration sweep in `results/iterations_2026-10-30.csv` — see sweep report |
| S-14 | Donchian-24 channel follower | 5m | `dc_mid_24`, `dc_upper_24` | close > dc_mid_24 (+ optional hysteresis) | close ≤ dc_mid_24 | long | **rejected** | [code/strategy_donchian.py](code/strategy_donchian.py) | [docs/strategy_sweep_2026-10-30.md](docs/strategy_sweep_2026-10-30.md) | 2026-10-30 | 6-iteration sweep in `results/iterations_2026-10-30.csv` — see sweep report |
| S-15 | Aroon-24 fresh-trend buyer | 5m | `aroon_up_24`, `aroon_down_24` | aroon_up up-cross ≥ 70 while aroon_down < 30 | aroon_up ≤ 70 | long | **rejected** | [code/strategy_aroon.py](code/strategy_aroon.py) | [docs/strategy_sweep_2026-10-30.md](docs/strategy_sweep_2026-10-30.md) | 2026-10-30 | 6-iteration sweep in `results/iterations_2026-10-30.csv` — see sweep report |
| S-16 | MFI-24 volume-exhaustion dip-buyer | 5m | `mfi_24` | MFI down-cross < 20 | MFI ≥ 50 | long | **rejected** | [code/strategy_mfi.py](code/strategy_mfi.py) | [docs/strategy_sweep_2026-10-30.md](docs/strategy_sweep_2026-10-30.md) | 2026-10-30 | 6-iteration sweep in `results/iterations_2026-10-30.csv` — see sweep report |
| S-17 | Slow RSI-60 (1h) with regime gate | 1h | `rsi_60`, `st_dir_120_3`, `adx_24` | rsi_60 < 30 (gated by ST-120 / ADX variants) | rsi_60 ≥ 50 | long | **rejected** | [code/strategy_rsi_slow.py](code/strategy_rsi_slow.py) | [docs/strategy_sweep_2026-10-30.md](docs/strategy_sweep_2026-10-30.md) | 2026-10-30 | 6-iteration sweep in `results/iterations_2026-10-30.csv` — see sweep report |
| S-18 | VWAP-stretch reversion | 5m | `vwap`, `atr_24` | (close−vwap)/atr up-cross > k | ratio < k_exit | long | **rejected** | [code/strategy_vwap_stretch.py](code/strategy_vwap_stretch.py) | [docs/strategy_sweep_2026-11-01.md](docs/strategy_sweep_2026-11-01.md) | 2026-11-01 | 6-iteration sweep in `results/iterations_2026-11-01.csv` — see sweep report |
| S-19 | CMF-24 accumulation follower | 5m | `cmf_24` | cmf_24 up-cross > k | cmf_24 down-cross < 0 | long | **rejected** | [code/strategy_cmf.py](code/strategy_cmf.py) | [docs/strategy_sweep_2026-11-01.md](docs/strategy_sweep_2026-11-01.md) | 2026-11-01 | 6-iteration sweep in `results/iterations_2026-11-01.csv` — see sweep report |
| S-20 | Multi-scale SuperTrend alignment | 5m | `st_dir_60_2`, `st_dir_120_2` (gated) | short ST up-flip while long-scale ST up | short ST down-flip | long | **rejected** | [code/strategy_multiscale.py](code/strategy_multiscale.py) | [docs/strategy_sweep_2026-11-01.md](docs/strategy_sweep_2026-11-01.md) | 2026-11-01 | 6-iteration sweep in `results/iterations_2026-11-01.csv` — see sweep report |
| S-21 | Slow squeeze-expansion (60-bar) regime | 5m | `sqz_on_60`, `bb_mid_60` | sqz_60 on + close > bb_mid_60 | sqz_60 off or close ≤ bb_mid_60 | long | **rejected** | [code/strategy_squeeze_slow.py](code/strategy_squeeze_slow.py) | [docs/strategy_sweep_2026-11-01.md](docs/strategy_sweep_2026-11-01.md) | 2026-11-01 | 6-iteration sweep in `results/iterations_2026-11-01.csv` — see sweep report |
| S-22 | Efficiency-ratio regime follower | 5m | `er_24`, `ema_24` | er_24 > k and close > ema_24 | either condition fails | long | **rejected** | [code/strategy_er.py](code/strategy_er.py) | [docs/strategy_er_report.md](docs/strategy_er_report.md) | 2026-11-01 | last_12m c2: −56.01% vs +5.62% (EUR_USD); 1,945 trades — cost × frequency (see report §3) |
| S-23 | Slow ATR-normalized MACD follower | 5m | `macd_hist_atr_24_120` | hist/atr > th | hist/atr ≤ th_exit | long | **rejected** | [code/strategy_macd_slow.py](code/strategy_macd_slow.py) | [docs/strategy_sweep_2026-11-01.md](docs/strategy_sweep_2026-11-01.md) | 2026-11-01 | 6-iteration sweep in `results/iterations_2026-11-01.csv` — see sweep report |
| S-24 | ATR-band breakout follower | 5m | `ema_24`, `atr_24` | (close−ema)/atr ≥ k | ratio < k_exit | long | **rejected** | [code/strategy_atr_band.py](code/strategy_atr_band.py) | [docs/strategy_sweep_2026-11-01.md](docs/strategy_sweep_2026-11-01.md) | 2026-11-01 | 6-iteration sweep in `results/iterations_2026-11-01.csv` — see sweep report |
| S-25 | Chop-regime mean-reversion | 5m | `chop_24`, `ema_24`, `atr_24` | (close−ema)/atr ≤ −k while chop_24 > chop_at | close ≥ ema_24 | long | **rejected** | [code/strategy_chop.py](code/strategy_chop.py) | [docs/strategy_sweep_2026-11-01.md](docs/strategy_sweep_2026-11-01.md) | 2026-11-01 | 6-iteration sweep in `results/iterations_2026-11-01.csv` — see sweep report |
| S-26 | EMA-12/60-spread follower | 5m | `ema_spread_12_60` | spread up-cross > th | spread < th_exit | long | **rejected** | [code/strategy_spread.py](code/strategy_spread.py) | [docs/strategy_sweep_2026-11-01.md](docs/strategy_sweep_2026-11-01.md) | 2026-11-01 | 6-iteration sweep in `results/iterations_2026-11-01.csv` — see sweep report |
| S-27 | Volume-confirmed momentum | 5m | `mom_24`, `vol_rel_24` | mom_24 > 0 and vol_rel_24 ≥ vmin | mom_24 ≤ 0 | long | **rejected** | [code/strategy_volmom.py](code/strategy_volmom.py) | [docs/strategy_sweep_2026-11-01.md](docs/strategy_sweep_2026-11-01.md) | 2026-11-01 | 6-iteration sweep in `results/iterations_2026-11-01.csv` — see sweep report |

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
| `adx_24` | S-07, S-17 |
| `ema_spread_24_120` | S-06 |
| `cci_24`, `bb_pos_24` | S-08 |
| `willr_24` | S-09 |
| `stoch_k_24`, `stoch_d_24` | S-10 |
| `macd_12_60`, `macd_hist_12_60` | S-11 |
| `roc_24`, `ema_120` | S-12 |
| `psar_dir_0p01_0p1` | S-13 |
| `dc_mid_24`, `dc_upper_24` | S-14 |
| `aroon_up_24`, `aroon_down_24` | S-15 |
| `mfi_24` | S-16 |
| `rsi_60`, `st_dir_120_3` | S-17 |
| `vwap` | S-18 |
| `atr_24` | S-18, S-24, S-25 |
| `ema_24` | S-03, S-22, S-24, S-25 |
| `cmf_24` | S-19 |
| `st_dir_60_2` | S-20 |
| `sqz_on_60`, `bb_mid_60` | S-21 |
| `er_24` | S-22 |
| `macd_hist_atr_24_120` | S-23 |
| `ema_spread_12_60` | S-26 |
| `chop_24` | S-25 |
| `mom_24`, `vol_rel_24` | S-27 |

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
