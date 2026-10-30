# Strategy Registry

> **Read first:** [STRATEGY_BACKGROUND.md](STRATEGY_BACKGROUND.md) — data contract,
> hard rules, and the new-strategy checklist.
>
> **Purpose:** single source of truth for every strategy in this project.
> Before starting a new strategy, check this registry so no strategy duplicates
> an existing indicator + timeframe + rule combination.
>
> **Latest batch design:** S-113–S-132 were pre-registered together in
> [strategy_batch_20261030_design.md](docs/strategy_batch_20261030_design.md).
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
| S-28 | Candle close-location turn | 5m | `bar_clv` | bar_clv up-cross > k_in (fresh) | bar_clv < k_exit | long | **rejected** | [code/strategy_candle.py](code/strategy_candle.py) | [docs/strategy_sweep_2026-11-02.md](docs/strategy_sweep_2026-11-02.md) | 2026-11-02 | 8-iteration sweep in `results/iterations_2026-11-02.csv` — see sweep report |
| S-29 | Volume-contraction trend buyer | 5m | `vol_rel_24`, `ema_24` | vol_rel_24 < vmin and close > ema_24 | vol_rel_24 > vmax | long | **rejected** | [code/strategy_volconverge.py](code/strategy_volconverge.py) | [docs/strategy_sweep_2026-11-02.md](docs/strategy_sweep_2026-11-02.md) | 2026-11-02 | 8-iteration sweep in `results/iterations_2026-11-02.csv` — see sweep report |
| S-30 | ATR-band EMA-distance turn | 5m | `ema_dist_24` | ema_dist_24 up-cross > k_in (fresh) | ema_dist_24 < k_exit | long | **rejected** | [code/strategy_atrbandpct.py](code/strategy_atrbandpct.py) | [docs/strategy_sweep_2026-11-02.md](docs/strategy_sweep_2026-11-02.md) | 2026-11-02 | 8-iteration sweep in `results/iterations_2026-11-02.csv` — see sweep report |
| S-31 | Supertrend-distance follower | 5m | `st_dist_24_2` | st_dist_24_2 > th_in | st_dist_24_2 < th_exit | long | **rejected** | [code/strategy_stdist.py](code/strategy_stdist.py) | [docs/strategy_sweep_2026-11-02.md](docs/strategy_sweep_2026-11-02.md) | 2026-11-02 | 8-iteration sweep in `results/iterations_2026-11-02.csv` — see sweep report |
| S-32 | PSAR-distance follower | 5m | `psar_dist_0p01_0p1` | psar_dist > th_in | psar_dist < th_exit | long | **rejected** | [code/strategy_psardist.py](code/strategy_psardist.py) | [docs/strategy_sweep_2026-11-02.md](docs/strategy_sweep_2026-11-02.md) | 2026-11-02 | 8-iteration sweep in `results/iterations_2026-11-02.csv` — see sweep report |
| S-33 | Keltner upper-band breakout | 5m | `kc_upper_24`, `kc_mid_24` | close up-cross > kc_upper_24 (fresh) | close <= kc_mid_24 | long | **rejected** | [code/strategy_kcbreak.py](code/strategy_kcbreak.py) | [docs/strategy_sweep_2026-11-02.md](docs/strategy_sweep_2026-11-02.md) | 2026-11-02 | 8-iteration sweep in `results/iterations_2026-11-02.csv` — see sweep report |
| S-34 | Bollinger %B dip turn | 5m | `bb_pctb_24` | bb_pctb_24 down-cross < k_in (fresh) | bb_pctb_24 >= k_exit | long | **rejected** | [code/strategy_bb_pctb.py](code/strategy_bb_pctb.py) | [docs/strategy_sweep_2026-11-02.md](docs/strategy_sweep_2026-11-02.md) | 2026-11-02 | 8-iteration sweep in `results/iterations_2026-11-02.csv` — see sweep report |
| S-35 | Bollinger-width compression dip | 5m | `bb_width_24`, `bb_pctb_24` | bb_width_24 down-cross < low (fresh) and pctb>0 | bb_width_24 > high | long | **rejected** | [code/strategy_bb_width.py](code/strategy_bb_width.py) | [docs/strategy_sweep_2026-11-02.md](docs/strategy_sweep_2026-11-02.md) | 2026-11-02 | 8-iteration sweep in `results/iterations_2026-11-02.csv` — see sweep report |
| S-36 | Donchian-position turn | 5m | `dc_pos_24` | dc_pos_24 up-cross > k_in (fresh) | dc_pos_24 < k_exit | long | **rejected** | [code/strategy_dcpos.py](code/strategy_dcpos.py) | [docs/strategy_sweep_2026-11-02.md](docs/strategy_sweep_2026-11-02.md) | 2026-11-02 | 8-iteration sweep in `results/iterations_2026-11-02.csv` — see sweep report |
| S-37 | Donchian midline fresh-cross | 5m | `dc_mid_24` | close up-cross > dc_mid_24 (fresh) | close <= dc_mid_24 | long | **rejected** | [code/strategy_dcmid.py](code/strategy_dcmid.py) | [docs/strategy_sweep_2026-11-02.md](docs/strategy_sweep_2026-11-02.md) | 2026-11-02 | 8-iteration sweep in `results/iterations_2026-11-02.csv` — see sweep report |
| S-38 | Distance-from-low turn | 5m | `dist_low_24` | dist_low_24 up-cross > k_in (fresh) | dist_low_24 < k_exit | long | **rejected** | [code/strategy_distlow.py](code/strategy_distlow.py) | [docs/strategy_sweep_2026-11-02.md](docs/strategy_sweep_2026-11-02.md) | 2026-11-02 | 8-iteration sweep in `results/iterations_2026-11-02.csv` — see sweep report |
| S-39 | Donchian-width compression dip | 5m | `dc_upper_24`, `dc_lower_24`, `atr_24` | width down-cross < w_in*atr (fresh) | width > w_exit*atr | long | **rejected** | [code/strategy_dcwidth.py](code/strategy_dcwidth.py) | [docs/strategy_sweep_2026-11-02.md](docs/strategy_sweep_2026-11-02.md) | 2026-11-02 | 8-iteration sweep in `results/iterations_2026-11-02.csv` — see sweep report |
| S-40 | SuperTrend side + distance hysteresis | 5m | `st_dir_24_2`, `st_dist_24_2` | side up and st_dist > th_in (fresh) | side down or st_dist < th_exit | long | **rejected** | [code/strategy_stdist_hyst.py](code/strategy_stdist_hyst.py) | [docs/strategy_sweep_2026-11-02.md](docs/strategy_sweep_2026-11-02.md) | 2026-11-02 | 8-iteration sweep in `results/iterations_2026-11-02.csv` — see sweep report |
| S-41 | Realized-volatility contraction | 5m | `hv_24` | hv_24 < k_in (realized vol compressing) | hv_24 > k_exit | long | **rejected** | [code/strategy_hvconverge.py](code/strategy_hvconverge.py) | [docs/strategy_sweep_2026-11-02.md](docs/strategy_sweep_2026-11-02.md) | 2026-11-02 | 8-iteration sweep in `results/iterations_2026-11-02.csv` — see sweep report |
| S-42 | Bar-body momentum turn | 5m | `bar_body_ratio` | bar_body_ratio up-cross > k_in (fresh) | bar_body_ratio < k_exit | long | **rejected** | [code/strategy_barbody.py](code/strategy_barbody.py) | [docs/strategy_sweep_2026-11-02.md](docs/strategy_sweep_2026-11-02.md) | 2026-11-02 | 8-iteration sweep in `results/iterations_2026-11-02.csv` — see sweep report |
| S-43 | Directional-Index spread turn | 5m | `plus_di_24`, `minus_di_24` | plus_di−minus_di up-cross > k_in (fresh) | spread < −k_exit | long | **rejected** | [code/strategy_dispread.py](code/strategy_dispread.py) | [docs/strategy_sweep_2026-11-03.md](docs/strategy_sweep_2026-11-03.md) | 2026-11-03 | 8-iteration sweep in `results/iterations_2026-11-03.csv` — see sweep report |
| S-44 | Dual-SMA trend follower | 5m | `close`, `sma_24`, `sma_60` | close > sma_24 > sma_60 (fresh) | close < sma_60 | long | **rejected** | [code/strategy_dualsma.py](code/strategy_dualsma.py) | [docs/strategy_sweep_2026-11-03.md](docs/strategy_sweep_2026-11-03.md) | 2026-11-03 | 8-iteration sweep in `results/iterations_2026-11-03.csv` — see sweep report |
| S-45 | MACD signal-line cross | 5m | `macd_12_60`, `macd_signal_12_60` | macd up-cross > signal (fresh) | macd < signal | long | **rejected** | [code/strategy_macdsig.py](code/strategy_macdsig.py) | [docs/strategy_sweep_2026-11-03.md](docs/strategy_sweep_2026-11-03.md) | 2026-11-03 | 8-iteration sweep in `results/iterations_2026-11-03.csv` — see sweep report |
| S-46 | ATR-% low-volatility trend | 5m | `atr_pct_24` | atr_pct < k_in and close > ema (fresh) | atr_pct > k_exit | long | **rejected** | [code/strategy_atrpct.py](code/strategy_atrpct.py) | [docs/strategy_sweep_2026-11-03.md](docs/strategy_sweep_2026-11-03.md) | 2026-11-03 | 8-iteration sweep in `results/iterations_2026-11-03.csv` — see sweep report |
| S-47 | Distance-to-prior-high room | 5m | `dist_high_24` | dist_high up-cross > k_in (fresh) | dist_high < k_exit | long | **rejected** | [code/strategy_disthigh.py](code/strategy_disthigh.py) | [docs/strategy_sweep_2026-11-03.md](docs/strategy_sweep_2026-11-03.md) | 2026-11-03 | 8-iteration sweep in `results/iterations_2026-11-03.csv` — see sweep report |
| S-48 | ATR vol-ratio expansion | 5m | `vol_ratio_12_60` | vol_ratio up-cross > k_in (fresh) | vol_ratio < k_exit | long | **rejected** | [code/strategy_volratio.py](code/strategy_volratio.py) | [docs/strategy_sweep_2026-11-03.md](docs/strategy_sweep_2026-11-03.md) | 2026-11-03 | 8-iteration sweep in `results/iterations_2026-11-03.csv` — see sweep report |
| S-49 | Keltner lower-band bounce | 5m | `close`, `kc_lower_24`, `kc_mid_24` | close up-cross > kc_lower (fresh) | close < kc_mid | long | **rejected** | [code/strategy_kclower.py](code/strategy_kclower.py) | [docs/strategy_sweep_2026-11-03.md](docs/strategy_sweep_2026-11-03.md) | 2026-11-03 | 8-iteration sweep in `results/iterations_2026-11-03.csv` — see sweep report |
| S-50 | Bollinger midline pullback | 5m | `close`, `bb_mid_24`, `bb_lower_24` | close up-cross > bb_mid (fresh) | close < bb_lower | long | **rejected** | [code/strategy_bbmid.py](code/strategy_bbmid.py) | [docs/strategy_sweep_2026-11-03.md](docs/strategy_sweep_2026-11-03.md) | 2026-11-03 | 8-iteration sweep in `results/iterations_2026-11-03.csv` — see sweep report |
| S-51 | Low upper-wick strong close | 5m | `bar_upper_wick_ratio` | bar_upper_wick down-cross < k_in (fresh) | bar_upper_wick > k_exit | long | **rejected** | [code/strategy_upwick.py](code/strategy_upwick.py) | [docs/strategy_sweep_2026-11-03.md](docs/strategy_sweep_2026-11-03.md) | 2026-11-03 | 8-iteration sweep in `results/iterations_2026-11-03.csv` — see sweep report |
| S-52 | Close-location (CLV) turn | 5m | `bar_clv` | bar_clv up-cross > k_in (fresh) | bar_clv < k_exit | long | **rejected** | [code/strategy_clv.py](code/strategy_clv.py) | [docs/strategy_sweep_2026-11-03.md](docs/strategy_sweep_2026-11-03.md) | 2026-11-03 | 8-iteration sweep in `results/iterations_2026-11-03.csv` — see sweep report |
| S-53 | Fast MACD histogram turn | 5m | `macd_hist_atr_6_24` | macd_hist_atr up-cross > k_in (fresh) | macd_hist_atr < k_exit | long | **rejected** | [code/strategy_macdhist6.py](code/strategy_macdhist6.py) | [docs/strategy_sweep_2026-11-03.md](docs/strategy_sweep_2026-11-03.md) | 2026-11-03 | 8-iteration sweep in `results/iterations_2026-11-03.csv` — see sweep report |
| S-54 | 1h ADX trend regime | 5m | `h1_adx_24` | h1_adx up-cross > k_in and close > ema (fresh) | h1_adx < k_exit | long | **rejected** | [code/strategy_h1adx.py](code/strategy_h1adx.py) | [docs/strategy_sweep_2026-11-03.md](docs/strategy_sweep_2026-11-03.md) | 2026-11-03 | 8-iteration sweep in `results/iterations_2026-11-03.csv` — see sweep report |
| S-55 | 1h RSI momentum | 5m | `h1_rsi_24` | h1_rsi up-cross > k_in (fresh) | h1_rsi < k_exit | long | **parked** | [code/strategy_h1rsi.py](code/strategy_h1rsi.py) | [docs/strategy_sweep_2026-11-03.md](docs/strategy_sweep_2026-11-03.md) | 2026-11-03 | **in-sample finalist candidate**: `looser` (k_in=33/k_exit=27) beats buy-hold at 2 bps on 2/3 instruments (BTC, XAU) on **both** `full` and `last_12m` (~11 tpy, 98% exposure). S1 forces a terminal status because the `base` variant hits 360 full-window trades (EUR); held as `parked` for the human-nominated one-shot OOS gate — see sweep report |
| S-56 | 1h efficiency-ratio regime | 5m | `h1_er_24` | h1_er up-cross > k_in (fresh) | h1_er < k_exit | long | **rejected** | [code/strategy_h1er.py](code/strategy_h1er.py) | [docs/strategy_sweep_2026-11-03.md](docs/strategy_sweep_2026-11-03.md) | 2026-11-03 | 8-iteration sweep in `results/iterations_2026-11-03.csv` — see sweep report |
| S-57 | 1h EMA-distance pullback | 5m | `h1_ema_dist_24` | h1_ema_dist enters 0<k_in band (fresh) | h1_ema_dist < −k_exit | long | **rejected** | [code/strategy_h1edist.py](code/strategy_h1edist.py) | [docs/strategy_sweep_2026-11-03.md](docs/strategy_sweep_2026-11-03.md) | 2026-11-03 | 8-iteration sweep in `results/iterations_2026-11-03.csv` — see sweep report |
| S-58 | Rate-of-change hysteresis | 5m | `roc_24` | roc_24 up-cross > k_in (fresh) | roc_24 < k_exit | long | **rejected** | [code/strategy_roc.py](code/strategy_roc.py) | [docs/strategy_sweep_2026-11-04.md](docs/strategy_sweep_2026-11-04.md) | 2026-11-04 | 8-iteration sweep in `results/iterations_2026-11-04.csv` — see sweep report |
| S-59 | Stochastic K/D-turn rebound | 5m | `stoch_k_24`, `stoch_d_24` | k>d and k<k_in (fresh) | k > k_exit | long | **rejected** | [code/strategy_stochkd.py](code/strategy_stochkd.py) | [docs/strategy_sweep_2026-11-04.md](docs/strategy_sweep_2026-11-04.md) | 2026-11-04 | 8-iteration sweep in `results/iterations_2026-11-04.csv` — see sweep report |
| S-60 | Aroon-Down collapse | 5m | `aroon_down_24` | aroon_down down-cross < k_in (fresh) | aroon_down > k_exit | long | **rejected** | [code/strategy_aroondn.py](code/strategy_aroondn.py) | [docs/strategy_sweep_2026-11-04.md](docs/strategy_sweep_2026-11-04.md) | 2026-11-04 | 8-iteration sweep in `results/iterations_2026-11-04.csv` — see sweep report |
| S-61 | Momentum sign-turn | 5m | `mom_24` | mom up-cross > k_in (fresh) | mom < k_exit | long | **rejected** | [code/strategy_momsign.py](code/strategy_momsign.py) | [docs/strategy_sweep_2026-11-04.md](docs/strategy_sweep_2026-11-04.md) | 2026-11-04 | 8-iteration sweep in `results/iterations_2026-11-04.csv` — see sweep report |
| S-62 | Realized-vol expansion + trend | 5m | `hv_24` | hv_24 up-cross > k_in and close>ema (fresh) | hv_24 < k_exit | long | **rejected** | [code/strategy_hvup.py](code/strategy_hvup.py) | [docs/strategy_sweep_2026-11-04.md](docs/strategy_sweep_2026-11-04.md) | 2026-11-04 | 8-iteration sweep in `results/iterations_2026-11-04.csv` — see sweep report |
| S-63 | Bollinger-upper breakout | 5m | `close`, `bb_upper_24` | close up-cross > bb_upper (fresh) | close < bb_upper | long | **rejected** | [code/strategy_bbupper.py](code/strategy_bbupper.py) | [docs/strategy_sweep_2026-11-04.md](docs/strategy_sweep_2026-11-04.md) | 2026-11-04 | 8-iteration sweep in `results/iterations_2026-11-04.csv` — see sweep report |
| S-64 | Donchian-upper breakout | 5m | `close`, `dc_upper_24` | close up-cross > dc_upper (fresh) | close < bb_mid | long | **rejected** | [code/strategy_dcupper.py](code/strategy_dcupper.py) | [docs/strategy_sweep_2026-11-04.md](docs/strategy_sweep_2026-11-04.md) | 2026-11-04 | 8-iteration sweep in `results/iterations_2026-11-04.csv` — see sweep report |
| S-65 | Lower-wick rejection | 5m | `bar_lower_wick_ratio` | lower_wick up-cross > k_in (fresh) | lower_wick < k_exit | long | **rejected** | [code/strategy_lowwick.py](code/strategy_lowwick.py) | [docs/strategy_sweep_2026-11-04.md](docs/strategy_sweep_2026-11-04.md) | 2026-11-04 | 8-iteration sweep in `results/iterations_2026-11-04.csv` — see sweep report |
| S-66 | Volume-confirmed band breakout | 5m | `close`, `bb_upper_24`, `vol_rel_24` | close>bb_upper and vol_rel>vmin (fresh) | close < bb_upper | long | **rejected** | [code/strategy_volbb.py](code/strategy_volbb.py) | [docs/strategy_sweep_2026-11-04.md](docs/strategy_sweep_2026-11-04.md) | 2026-11-04 | 8-iteration sweep in `results/iterations_2026-11-04.csv` — see sweep report |
| S-67 | 1h ADX + 1h SuperTrend alignment | 5m | `h1_adx_24`, `h1_st_dir_24_3` | h1_adx>k_in and h1_st>0 (fresh) | h1_adx<k_exit or h1_st≤0 | long | **rejected** | [code/strategy_h1adxst.py](code/strategy_h1adxst.py) | [docs/strategy_sweep_2026-11-04.md](docs/strategy_sweep_2026-11-04.md) | 2026-11-04 | 8-iteration sweep in `results/iterations_2026-11-04.csv` — see sweep report |
| S-68 | Dual-SuperTrend alignment | 5m | `st_dir_24_3`, `st_dir_120_2` | st24>0 and st120>0 (fresh) | st24≤0 or st120≤0 | long | **rejected** | [code/strategy_dualst.py](code/strategy_dualst.py) | [docs/strategy_sweep_2026-11-04.md](docs/strategy_sweep_2026-11-04.md) | 2026-11-04 | 8-iteration sweep in `results/iterations_2026-11-04.csv` — see sweep report |
| S-69 | Stochastic-K mid-turn + trend | 5m | `stoch_k_24` | stoch_k up-cross > k_in (fresh) | stoch_k < k_exit | long | **rejected** | [code/strategy_stok.py](code/strategy_stok.py) | [docs/strategy_sweep_2026-11-04.md](docs/strategy_sweep_2026-11-04.md) | 2026-11-04 | 8-iteration sweep in `results/iterations_2026-11-04.csv` — see sweep report |
| S-70 | 1h low-vol coil + trend | 5m | `h1_atr_pct_24` | h1_atr_pct < k_in and close>ema (fresh) | h1_atr_pct > k_exit or close≤ema | long | **rejected** | [code/strategy_h1vol.py](code/strategy_h1vol.py) | [docs/strategy_sweep_2026-11-04.md](docs/strategy_sweep_2026-11-04.md) | 2026-11-04 | 8-iteration sweep in `results/iterations_2026-11-04.csv` — see sweep report |
| S-71 | Aroon-Down + Stochastic confluence | 5m | `aroon_down_24`, `stoch_k_24` | aroon<k_in, k>d_in, close>ema (fresh) | aroon>k_exit or k<d_exit | long | **rejected** | [code/strategy_aroondnstoch.py](code/strategy_aroondnstoch.py) | [docs/strategy_sweep_2026-11-04.md](docs/strategy_sweep_2026-11-04.md) | 2026-11-04 | 8-iteration sweep in `results/iterations_2026-11-04.csv` — see sweep report |
| S-72 | ROC + volume confluence | 5m | `roc_24`, `vol_rel_24` | roc>k_in and vol_rel>vmin (fresh) | roc<k_exit or vol_rel<vexit | long | **rejected** | [code/strategy_rocvol.py](code/strategy_rocvol.py) | [docs/strategy_sweep_2026-11-04.md](docs/strategy_sweep_2026-11-04.md) | 2026-11-04 | 8-iteration sweep in `results/iterations_2026-11-04.csv` — see sweep report |
| S-73 | Slow Aroon-Up trend | 5m | `aroon_up_60` | aroon_up_60 up-cross > k_in (fresh) | aroon_up_60 < k_exit | long | **rejected** | [code/strategy_aroonup60.py](code/strategy_aroonup60.py) | [docs/strategy_sweep_2026-11-05.md](docs/strategy_sweep_2026-11-05.md) | 2026-11-05 | 8-iteration sweep in `results/iterations_2026-11-05.csv` — best `1h` −252%; no variant beat BH on ≥2/3 instruments |
| S-74 | Slow Williams-%R rebound | 5m | `willr_60` | willr_60 up-cross > k_in (fresh) | willr_60 < k_exit | long | **rejected** | [code/strategy_willr60.py](code/strategy_willr60.py) | [docs/strategy_sweep_2026-11-05.md](docs/strategy_sweep_2026-11-05.md) | 2026-11-05 | 8-iteration sweep in `results/iterations_2026-11-05.csv` — best `1h` −116%; no variant beat BH on ≥2/3 instruments |
| S-75 | Slow CCI momentum | 5m | `cci_120` | cci_120 up-cross > k_in (fresh) | cci_120 < k_exit | long | **rejected** | [code/strategy_cci120.py](code/strategy_cci120.py) | [docs/strategy_sweep_2026-11-05.md](docs/strategy_sweep_2026-11-05.md) | 2026-11-05 | 8-iteration sweep in `results/iterations_2026-11-05.csv` — best `1h` −44%; no variant beat BH on ≥2/3 instruments |
| S-76 | Slow Stochastic-K turn | 5m | `stoch_k_60` | stoch_k_60 up-cross > k_in (fresh) | stoch_k_60 < k_exit | long | **rejected** | [code/strategy_stochk60.py](code/strategy_stochk60.py) | [docs/strategy_sweep_2026-11-05.md](docs/strategy_sweep_2026-11-05.md) | 2026-11-05 | 8-iteration sweep in `results/iterations_2026-11-05.csv` — best `1h` −150%; no variant beat BH on ≥2/3 instruments |
| S-77 | Slow MFI accumulation | 5m | `mfi_60` | mfi_60 up-cross > k_in (fresh) | mfi_60 < k_exit | long | **rejected** | [code/strategy_mfi60.py](code/strategy_mfi60.py) | [docs/strategy_sweep_2026-11-05.md](docs/strategy_sweep_2026-11-05.md) | 2026-11-05 | 8-iteration sweep in `results/iterations_2026-11-05.csv` — best `1h` −255%; no variant beat BH on ≥2/3 instruments |
| S-78 | Slow ATR-% expansion | 5m | `atr_pct_120` | atr_pct_120 up-cross > k_in and close>ema (fresh) | atr_pct_120 < k_exit or close≤ema | long | **rejected** | [code/strategy_atrpct120.py](code/strategy_atrpct120.py) | [docs/strategy_sweep_2026-11-05.md](docs/strategy_sweep_2026-11-05.md) | 2026-11-05 | 8-iteration sweep in `results/iterations_2026-11-05.csv` — best `1h` −249%; no variant beat BH on ≥2/3 instruments |
| S-79 | Slow ROC momentum | 5m | `roc_120` | roc_120 up-cross > k_in (fresh) | roc_120 < k_exit | long | **rejected** | [code/strategy_roc120.py](code/strategy_roc120.py) | [docs/strategy_sweep_2026-11-05.md](docs/strategy_sweep_2026-11-05.md) | 2026-11-05 | 8-iteration sweep in `results/iterations_2026-11-05.csv` — best `1h` −160%; no variant beat BH on ≥2/3 instruments |
| S-80 | Time-of-day (hour_sin) regime | 5m | `hour_sin` | hour_sin up-cross > k_in (fresh) | hour_sin < k_exit | long | **rejected** | [code/strategy_hoursin.py](code/strategy_hoursin.py) | [docs/strategy_sweep_2026-11-05.md](docs/strategy_sweep_2026-11-05.md) | 2026-11-05 | 8-iteration sweep in `results/iterations_2026-11-05.csv` — best `1h` −249%; no variant beat BH on ≥2/3 instruments |
| S-81 | Day-of-week (dow_sin) regime | 5m | `dow_sin` | dow_sin up-cross > k_in (fresh) | dow_sin < k_exit | long | **rejected** | [code/strategy_dowsin.py](code/strategy_dowsin.py) | [docs/strategy_sweep_2026-11-05.md](docs/strategy_sweep_2026-11-05.md) | 2026-11-05 | 8-iteration sweep in `results/iterations_2026-11-05.csv` — best `1h` −12%; **BTC-only** near-miss (BTC `last_12m` +15 to +29%, loses on EUR/XAU and BTC `full`); no variant beat BH on ≥2/3 instruments |
| S-82 | True-range collapse | 5m | `tr` | tr down-cross < k_in (fresh) | tr > k_exit | long | **rejected** | [code/strategy_trcollapse.py](code/strategy_trcollapse.py) | [docs/strategy_sweep_2026-11-05.md](docs/strategy_sweep_2026-11-05.md) | 2026-11-05 | 8-iteration sweep in `results/iterations_2026-11-05.csv` — best `1h` −258%; no variant beat BH on ≥2/3 instruments |
| S-83 | Slow-PSAR direction follower | 5m | `psar_dir_0p02_0p2` | psar_dir up-flip > 0 (fresh) | psar_dir <= 0 | long | **rejected** | [code/strategy_psar002.py](code/strategy_psar002.py) | [docs/strategy_sweep_2026-11-05.md](docs/strategy_sweep_2026-11-05.md) | 2026-11-05 | 8-iteration sweep in `results/iterations_2026-11-05.csv` — best `1h` −160%; no variant beat BH on ≥2/3 instruments |
| S-84 | Dual SuperTrend 120/24 alignment | 5m | `st_dir_120_3`, `st_dir_24_3` | st120>0 and st24>0 (fresh) | st120≤0 or st24≤0 | long | **rejected** | [code/strategy_stdual120.py](code/strategy_stdual120.py) | [docs/strategy_sweep_2026-11-05.md](docs/strategy_sweep_2026-11-05.md) | 2026-11-05 | 8-iteration sweep in `results/iterations_2026-11-05.csv` — best `1h_ema_guard` −190%; no variant beat BH on ≥2/3 instruments |
| S-85 | 1h SuperTrend-120 two-scale | 5m | `h1_st_dir_120_3`, `st_dir_24_3` | h1_st120>0 and st24>0 (fresh) | h1_st120≤0 or st24≤0 | long | **rejected** | [code/strategy_h1st120.py](code/strategy_h1st120.py) | [docs/strategy_sweep_2026-11-05.md](docs/strategy_sweep_2026-11-05.md) | 2026-11-05 | 8-iteration sweep in `results/iterations_2026-11-05.csv` — best `ema_only` −272%; no variant beat BH on ≥2/3 instruments |
| S-86 | Dual time-of-day confluence | 5m | `hour_sin`, `dow_sin` | hour_sin>k_in and dow_sin>d_in (fresh) | hour_sin<k_exit or dow_sin<d_exit | long | **rejected** | [code/strategy_timeconf.py](code/strategy_timeconf.py) | [docs/strategy_sweep_2026-11-05.md](docs/strategy_sweep_2026-11-05.md) | 2026-11-05 | 8-iteration sweep in `results/iterations_2026-11-05.csv` — best `looser` −173%; no variant beat BH on ≥2/3 instruments |
| S-87 | Slow-ROC + volume confluence | 5m | `roc_120`, `vol_rel_24` | roc_120>k_in and vol_rel>vmin (fresh) | roc_120<k_exit or vol_rel<vexit | long | **rejected** | [code/strategy_roc120vol.py](code/strategy_roc120vol.py) | [docs/strategy_sweep_2026-11-05.md](docs/strategy_sweep_2026-11-05.md) | 2026-11-05 | 8-iteration sweep in `results/iterations_2026-11-05.csv` — best `1h` −261%; no variant beat BH on ≥2/3 instruments |
| S-88 | Fast RSI-12 rebound | 5m | `rsi_12` | rsi_12>k_in (fresh) | rsi_12<k_exit | long | **rejected** | [code/strategy_rsi12.py](code/strategy_rsi12.py) | [docs/strategy_sweep_2026-11-06.md](docs/strategy_sweep_2026-11-06.md) | 2026-11-06 | 8-iteration sweep in `results/iterations_2026-11-06.csv` — best `1h` +16% (BTC-only artifact, 567 trades); no variant beat BH on ≥2/3 instruments in both windows |
| S-89 | Aroon-12 spread | 5m | `aroon_up_12`, `aroon_down_12` | (au−ad)>k_in (fresh) | (au−ad)<k_exit | long | **rejected** | [code/strategy_aroon12spread.py](code/strategy_aroon12spread.py) | [docs/strategy_sweep_2026-11-06.md](docs/strategy_sweep_2026-11-06.md) | 2026-11-06 | 8-iteration sweep in `results/iterations_2026-11-06.csv` — best `1h` −261%; no variant beat BH on ≥2/3 instruments |
| S-90 | Fast MACD hist (6/24) | 5m | `macd_hist_6_24` | hist>0 and close>ema_24 (fresh) | hist<0 | long | **rejected** | [code/strategy_macdh624.py](code/strategy_macdh624.py) | [docs/strategy_sweep_2026-11-06.md](docs/strategy_sweep_2026-11-06.md) | 2026-11-06 | 8-iteration sweep in `results/iterations_2026-11-06.csv` — best `1h_ema_guard` −223%; no variant beat BH on ≥2/3 instruments |
| S-91 | Fast Stochastic-D turn | 5m | `stoch_d_12` | stoch_d_12>k_in (fresh) | stoch_d_12<k_exit | long | **rejected** | [code/strategy_stochd12.py](code/strategy_stochd12.py) | [docs/strategy_sweep_2026-11-06.md](docs/strategy_sweep_2026-11-06.md) | 2026-11-06 | 8-iteration sweep in `results/iterations_2026-11-06.csv` — best `1h` −36%; no variant beat BH on ≥2/3 instruments |
| S-92 | Fast MFI-12 accumulation | 5m | `mfi_12` | mfi_12>k_in (fresh) | mfi_12<k_exit | long | **rejected** | [code/strategy_mfi12.py](code/strategy_mfi12.py) | [docs/strategy_sweep_2026-11-06.md](docs/strategy_sweep_2026-11-06.md) | 2026-11-06 | 8-iteration sweep in `results/iterations_2026-11-06.csv` — best `1h` −169%; no variant beat BH on ≥2/3 instruments |
| S-93 | Fast Williams-%R rebound | 5m | `willr_12` | willr_12>k_in (fresh) | willr_12<k_exit | long | **rejected** | [code/strategy_willr12.py](code/strategy_willr12.py) | [docs/strategy_sweep_2026-11-06.md](docs/strategy_sweep_2026-11-06.md) | 2026-11-06 | 8-iteration sweep in `results/iterations_2026-11-06.csv` — best `1h` −21% (BTC-only artifact); no variant beat BH on ≥2/3 instruments |
| S-94 | Fast Efficiency-Ratio regime | 5m | `er_12` | er_12>k_in (fresh) | er_12<k_exit | long | **rejected** | [code/strategy_er12.py](code/strategy_er12.py) | [docs/strategy_sweep_2026-11-06.md](docs/strategy_sweep_2026-11-06.md) | 2026-11-06 | 8-iteration sweep in `results/iterations_2026-11-06.csv` — best `1h` −256%; no variant beat BH on ≥2/3 instruments |
| S-95 | Slow-HV-120 low-vol regime | 5m | `hv_120` | hv_120<k_in (fresh) | hv_120>k_exit | long | **rejected** | [code/strategy_hv120.py](code/strategy_hv120.py) | [docs/strategy_sweep_2026-11-06.md](docs/strategy_sweep_2026-11-06.md) | 2026-11-06 | 8-iteration sweep in `results/iterations_2026-11-06.csv` — best `stronger` −44% (XAU-only, BTC −1506%); no variant beat BH on ≥2/3 instruments |
| S-96 | BB-Width-60 squeeze release | 5m | `bb_width_60` | bb_width_60>k_in (fresh) | bb_width_60<k_exit | long | **rejected** | [code/strategy_bbw60.py](code/strategy_bbw60.py) | [docs/strategy_sweep_2026-11-06.md](docs/strategy_sweep_2026-11-06.md) | 2026-11-06 | 8-iteration sweep in `results/iterations_2026-11-06.csv` — best `combo` +31% (BTC-only +342%, XAU −129%); `1h` 3/3 wins are 1–25-trade artifacts; no variant beat BH on ≥2/3 instruments in both windows |
| S-97 | Triple-oscillator confluence | 5m | `rsi_12`, `stoch_k_12`, `mfi_12` | all 3 above entry (fresh) | any below exit | long | **rejected** | [code/strategy_triosc.py](code/strategy_triosc.py) | [docs/strategy_sweep_2026-11-06.md](docs/strategy_sweep_2026-11-06.md) | 2026-11-06 | 8-iteration sweep in `results/iterations_2026-11-06.csv` — best `1h` −216%; no variant beat BH on ≥2/3 instruments |
| S-98 | Quad-oscillator confluence | 5m | `rsi_12`, `willr_12`, `stoch_d_12`, `mfi_12` | all 4 above entry (fresh) | any below exit | long | **rejected** | [code/strategy_quadosc.py](code/strategy_quadosc.py) | [docs/strategy_sweep_2026-11-06.md](docs/strategy_sweep_2026-11-06.md) | 2026-11-06 | 8-iteration sweep in `results/iterations_2026-11-06.csv` — best `1h` −205%; no variant beat BH on ≥2/3 instruments |
| S-99 | Fast-ROC + vol-ratio breakout | 5m | `roc_6`, `vol_ratio_6_24` | roc_6>k_in, vr>vmin, close>ema (fresh) | roc_6<k_exit or vr<vexit | long | **rejected** | [code/strategy_roc6volr.py](code/strategy_roc6volr.py) | [docs/strategy_sweep_2026-11-06.md](docs/strategy_sweep_2026-11-06.md) | 2026-11-06 | 8-iteration sweep in `results/iterations_2026-11-06.csv` — best `1h` −248%; no variant beat BH on ≥2/3 instruments |
| S-100 | Fast MACD signal cross (6/24) | 5m | `macd_6_24`, `macd_signal_6_24` | macd>signal (fresh) | macd≤signal | long | **rejected** | [code/strategy_macdcross624.py](code/strategy_macdcross624.py) | [docs/strategy_sweep_2026-11-06.md](docs/strategy_sweep_2026-11-06.md) | 2026-11-06 | 8-iteration sweep in `results/iterations_2026-11-06.csv` — best `1h` −169%; no variant beat BH on ≥2/3 instruments |
| S-101 | Slow-ROC-120 + EMA-120 confluence | 5m | `roc_120`, `ema_120` | roc_120>k_in and close>ema_120 (fresh) | roc_120<k_exit or close≤ema_120 | long | **rejected** | [code/strategy_roc120ema120.py](code/strategy_roc120ema120.py) | [docs/strategy_sweep_2026-11-06.md](docs/strategy_sweep_2026-11-06.md) | 2026-11-06 | 8-iteration sweep in `results/iterations_2026-11-06.csv` — best `1h` −138%; no variant beat BH on ≥2/3 instruments |
| S-102 | Slow Donchian-Pos-12 regime | 5m | `dc_pos_12` | dc_pos_12>k_in (fresh) | dc_pos_12<k_exit | long | **rejected** | [code/strategy_dcpos12.py](code/strategy_dcpos12.py) | [docs/strategy_sweep_2026-11-06.md](docs/strategy_sweep_2026-11-06.md) | 2026-11-06 | 8-iteration sweep in `results/iterations_2026-11-06.csv` — best `1h` −129%; no variant beat BH on ≥2/3 instruments |

| S-103 | Slow Choppiness trend-regime entry | 5m | `chop_120` | cross below 40 | above 60 | long | **parked** | [code/strategy_chop120.py](code/strategy_chop120.py) | [docs/strategy_chop120_report.md](docs/strategy_chop120_report.md) | 2026-10-30 | +2.5% vs +2.3% (EUR_USD); variant=wide_exit; see report |
| S-104 | Slow CMF accumulation | 5m | `cmf_60` | cross above 0.05 | below 0 | long | **rejected** | [code/strategy_cmf60.py](code/strategy_cmf60.py) | [docs/strategy_cmf60_report.md](docs/strategy_cmf60_report.md) | 2026-10-30 | -20.2% vs +3.1% (EUR_USD); variant=1h; see report |
| S-105 | 60-bar HV low-volatility regime | 5m | `hv_60` | cross below 0.0005 | above 0.001 | long | **rejected** | [code/strategy_hv60.py](code/strategy_hv60.py) | [docs/strategy_hv60_report.md](docs/strategy_hv60_report.md) | 2026-10-30 | +2.3% vs +2.3% (EUR_USD); variant=looser; see report |
| S-106 | Slow Stochastic-D turn | 5m | `stoch_d_60` | cross above 55 | below 40 | long | **rejected** | [code/strategy_stochd60.py](code/strategy_stochd60.py) | [docs/strategy_stochd60_report.md](docs/strategy_stochd60_report.md) | 2026-10-30 | -9.6% vs +3.1% (EUR_USD); variant=1h; see report |
| S-107 | Slow Bollinger squeeze state | 5m | `sqz_on_120` | enter at squeeze onset | squeeze off | long | **rejected** | [code/strategy_sqz120.py](code/strategy_sqz120.py) | [docs/strategy_sqz120_report.md](docs/strategy_sqz120_report.md) | 2026-10-30 | -0.3% vs +3.1% (EUR_USD); variant=1h; see report |
| S-108 | Ultra-fast RSI-6 turn | 5m | `rsi_6` | cross above 55 | below 40 | long | **rejected** | [code/strategy_rsi6.py](code/strategy_rsi6.py) | [docs/strategy_rsi6_report.md](docs/strategy_rsi6_report.md) | 2026-10-30 | -53.2% vs +3.1% (EUR_USD); variant=1h; see report |
| S-109 | Slow ADX range-regime rule | 5m | `adx_60` | cross below 20 | above 35 | long | **rejected** | [code/strategy_adx60.py](code/strategy_adx60.py) | [docs/strategy_adx60_report.md](docs/strategy_adx60_report.md) | 2026-10-30 | +2.3% vs +2.3% (EUR_USD); variant=wide_exit; see report |
| S-110 | Slow Stochastic-K (120-bar) | 5m | `stoch_k_120` | cross above 55 | below 40 | long | **rejected** | [code/strategy_stochk120.py](code/strategy_stochk120.py) | [docs/strategy_stochk120_report.md](docs/strategy_stochk120_report.md) | 2026-10-30 | -70.3% vs +2.3% (EUR_USD); variant=wide_exit; see report |
| S-111 | Ultra-fast Williams-%R rebound | 5m | `willr_6` | cross above −60 | below −80 | long | **rejected** | [code/strategy_willr6.py](code/strategy_willr6.py) | [docs/strategy_willr6_report.md](docs/strategy_willr6_report.md) | 2026-10-30 | -66.6% vs +3.1% (EUR_USD); variant=1h; see report |
| S-112 | Slow Efficiency-Ratio trend | 5m | `er_60` | cross above 0.3 | below 0.15 | long | **rejected** | [code/strategy_er60.py](code/strategy_er60.py) | [docs/strategy_er60_report.md](docs/strategy_er60_report.md) | 2026-10-30 | -19.9% vs +3.1% (EUR_USD); variant=1h; see report |
| S-113 | 1h Aroon direction with ADX regime | 1h | `aroon_up_24`, `aroon_down_24`, `adx_24` | directional Aroon cross with ADX > 20 | reverse Aroon cross | long/short | **rejected** | [code/strategy_aroon_adx_1h.py](code/strategy_aroon_adx_1h.py) | [docs/strategy_aroon_adx_1h_report.md](docs/strategy_aroon_adx_1h_report.md) | 2026-10-30 | -20.8% vs +3.1% (EUR_USD); variant=pre-registered fixed rule; see report |
| S-114 | Higher-timeframe trend pullback | 5m | `ema_dist_24`, `h1_ema_dist_24` | recover through −0.5/+0.5 in matching 1h trend | exit on EMA-distance zero-cross | long/short | **rejected** | [code/strategy_htf_ema_pullback.py](code/strategy_htf_ema_pullback.py) | [docs/strategy_htf_ema_pullback_report.md](docs/strategy_htf_ema_pullback_report.md) | 2026-10-30 | -99.8% vs +3.1% (EUR_USD); variant=pre-registered fixed rule; see report |
| S-115 | Higher-timeframe-gated channel break | 5m | `dist_high_24`, `dist_low_24`, `h1_adx_24`, `dc_pos_24` | prior-extreme break with 1h ADX > 20 | exit at channel midpoint | long/short | **rejected** | [code/strategy_htf_channel_break.py](code/strategy_htf_channel_break.py) | [docs/strategy_htf_channel_break_report.md](docs/strategy_htf_channel_break_report.md) | 2026-10-30 | -94.5% vs +3.1% (EUR_USD); variant=pre-registered fixed rule; see report |
| S-116 | Squeeze release with close-location direction | 5m | `sqz_on_24`, `bar_clv`, `h1_ema_dist_24` | squeeze release + close-location aligned with 1h trend | renewed squeeze or 1h reversal | long/short | **rejected** | [code/strategy_squeeze_clv_htf.py](code/strategy_squeeze_clv_htf.py) | [docs/strategy_squeeze_clv_htf_report.md](docs/strategy_squeeze_clv_htf_report.md) | 2026-10-30 | -72.3% vs +3.1% (EUR_USD); variant=pre-registered fixed rule; see report |
| S-117 | Low-trend VWAP reclaim | 5m | `vwap`, `h1_adx_24` | VWAP cross while 1h ADX < 20 | reverse VWAP cross | long/short | **rejected** | [code/strategy_vwap_range_reclaim.py](code/strategy_vwap_range_reclaim.py) | [docs/strategy_vwap_range_reclaim_report.md](docs/strategy_vwap_range_reclaim_report.md) | 2026-10-30 | -99.9% vs +3.1% (EUR_USD); variant=pre-registered fixed rule; see report |
| S-118 | Band re-entry in a choppy regime | 5m | `bb_pctb_24`, `chop_24`, `h1_adx_24` | outer 5% re-entry with high chop and weak 1h ADX | exit at band midpoint | long/short | **rejected** | [code/strategy_bb_chop_reversion.py](code/strategy_bb_chop_reversion.py) | [docs/strategy_bb_chop_reversion_report.md](docs/strategy_bb_chop_reversion_report.md) | 2026-10-30 | -85.5% vs +3.1% (EUR_USD); variant=pre-registered fixed rule; see report |
| S-119 | 60-bar prior-extreme breakout | 5m | `dist_high_60`, `dist_low_60`, `h1_ema_dist_24` | prior-extreme break in matching 1h direction | exit on recross of the broken extreme | long/short | **rejected** | [code/strategy_channel_position_continuation.py](code/strategy_channel_position_continuation.py) | [docs/strategy_channel_position_continuation_report.md](docs/strategy_channel_position_continuation_report.md) | 2026-10-30 | -96.6% vs +3.1% (EUR_USD); variant=pre-registered fixed rule; see report |
| S-120 | Directional-movement cross with ADX filter | 5m | `plus_di_60`, `minus_di_60`, `adx_60` | slow DI cross with ADX > 20 | reverse DI cross | long/short | **rejected** | [code/strategy_dmi_regime_cross.py](code/strategy_dmi_regime_cross.py) | [docs/strategy_dmi_regime_cross_report.md](docs/strategy_dmi_regime_cross_report.md) | 2026-10-30 | -5.6% vs +2.3% (EUR_USD); variant=pre-registered fixed rule; see report |
| S-121 | 1h MACD momentum in efficient regimes | 1h | `macd_hist_atr_12_60`, `er_24` | normalized MACD zero-cross with ER > 0.25 | reverse MACD cross | long/short | **rejected** | [code/strategy_macd_er_1h.py](code/strategy_macd_er_1h.py) | [docs/strategy_macd_er_1h_report.md](docs/strategy_macd_er_1h_report.md) | 2026-10-30 | -11.4% vs +3.1% (EUR_USD); variant=pre-registered fixed rule; see report |
| S-122 | PSAR reversal aligned with 1h trend | 5m | `psar_dir_0p01_0p1`, `h1_st_dir_24_3` | slow PSAR flip only in same 1h SuperTrend direction | exit on PSAR flip | long/short | **rejected** | [code/strategy_psar_htf_alignment.py](code/strategy_psar_htf_alignment.py) | [docs/strategy_psar_htf_alignment_report.md](docs/strategy_psar_htf_alignment_report.md) | 2026-10-30 | -99.2% vs +3.1% (EUR_USD); variant=pre-registered fixed rule; see report |
| S-123 | Wick rejection at Bollinger extremes | 5m | `bar_lower_wick_ratio`, `bar_upper_wick_ratio`, `bar_clv`, `bb_pctb_60` | rejection wick at outer band with confirming close location | exit at band midpoint | long/short | **rejected** | [code/strategy_wick_band_reversal.py](code/strategy_wick_band_reversal.py) | [docs/strategy_wick_band_reversal_report.md](docs/strategy_wick_band_reversal_report.md) | 2026-10-30 | -85.0% vs +2.3% (EUR_USD); variant=pre-registered fixed rule; see report |
| S-124 | Squeeze release with activity-confirmed break | 5m | `sqz_on_60`, `dist_high_60`, `dist_low_60`, `vol_rel_60`, `dc_pos_60` | release + activity > 1.2 + prior-extreme break | exit at midpoint | long/short | **rejected** | [code/strategy_squeeze_volume_break.py](code/strategy_squeeze_volume_break.py) | [docs/strategy_squeeze_volume_break_report.md](docs/strategy_squeeze_volume_break_report.md) | 2026-10-30 | -10.6% vs +2.3% (EUR_USD); variant=pre-registered fixed rule; see report |
| S-125 | ATR-normalized EMA trend with 1h SuperTrend | 5m | `ema_dist_60`, `h1_st_dir_120_3` | slow EMA-distance zero-cross in matching 1h regime | exit on zero-cross | long/short | **rejected** | [code/strategy_ema_dist_htf.py](code/strategy_ema_dist_htf.py) | [docs/strategy_ema_dist_htf_report.md](docs/strategy_ema_dist_htf_report.md) | 2026-10-30 | -99.9% vs +3.1% (EUR_USD); variant=pre-registered fixed rule; see report |
| S-126 | ATR expansion plus prior-extreme breakout | 5m | `atr_pct_24`, `atr_pct_60`, `dist_high_24`, `dist_low_24`, `dc_pos_24` | relative ATR expansion plus prior-extreme break | exit at midpoint | long/short | **rejected** | [code/strategy_atr_expansion_break.py](code/strategy_atr_expansion_break.py) | [docs/strategy_atr_expansion_break_report.md](docs/strategy_atr_expansion_break_report.md) | 2026-10-30 | -22.2% vs +2.3% (EUR_USD); variant=pre-registered fixed rule; see report |
| S-127 | Money-flow zero-cross with 1h trend alignment | 5m | `cmf_12`, `h1_ema_dist_24` | CMF zero-cross only with matching 1h direction | reverse flow cross | long/short | **rejected** | [code/strategy_cmf_htf_flow.py](code/strategy_cmf_htf_flow.py) | [docs/strategy_cmf_htf_flow_report.md](docs/strategy_cmf_htf_flow_report.md) | 2026-10-30 | -100.0% vs +3.1% (EUR_USD); variant=pre-registered fixed rule; see report |
| S-128 | VWAP reclaim in strong 1h trend | 5m | `vwap`, `h1_adx_24`, `h1_ema_dist_24` | VWAP cross with ADX > 25 and matching 1h direction | reverse VWAP cross | long/short | **rejected** | [code/strategy_vwap_trend_reclaim.py](code/strategy_vwap_trend_reclaim.py) | [docs/strategy_vwap_trend_reclaim_report.md](docs/strategy_vwap_trend_reclaim_report.md) | 2026-10-30 | -81.9% vs +3.1% (EUR_USD); variant=pre-registered fixed rule; see report |
| S-129 | 1h SuperTrend with 5m 120-bar breakout | 5m | `h1_st_dir_24_3`, `dist_high_120`, `dist_low_120`, `dc_pos_120` | 120-bar prior-extreme breakout gated by 1h SuperTrend | exit at channel midpoint | long/short | **rejected** | [code/strategy_htf_channel_break_120.py](code/strategy_htf_channel_break_120.py) | [docs/strategy_htf_channel_break_120_report.md](docs/strategy_htf_channel_break_120_report.md) | 2026-10-30 | -64.9% vs +3.1% (EUR_USD); variant=pre-registered fixed rule; see report |
| S-130 | 1h channel-position break in efficient trend | 1h | `dc_pos_60`, `er_60` | channel position beyond 0.8/0.2 with ER > 0.3 | exit at midpoint | long/short | **rejected** | [code/strategy_channel_efficiency_1h.py](code/strategy_channel_efficiency_1h.py) | [docs/strategy_channel_efficiency_1h_report.md](docs/strategy_channel_efficiency_1h_report.md) | 2026-10-30 | -9.8% vs +3.1% (EUR_USD); variant=pre-registered fixed rule; see report |
| S-131 | Close-location impulse with activity confirmation | 5m | `bar_clv`, `vol_rel_6`, `h1_adx_24` | strong close-location + activity > 1.2 + 1h ADX > 20 | exit on CLV sign reversal | long/short | **rejected** | [code/strategy_clv_activity_impulse.py](code/strategy_clv_activity_impulse.py) | [docs/strategy_clv_activity_impulse_report.md](docs/strategy_clv_activity_impulse_report.md) | 2026-10-30 | -99.2% vs +3.1% (EUR_USD); variant=pre-registered fixed rule; see report |
| S-132 | Band-width expansion aligned with 1h trend | 5m | `bb_width_12`, `bb_width_60`, `h1_ema_dist_24`, `dc_pos_24` | width cross with channel location and matching 1h direction | exit at midpoint | long/short | **rejected** | [code/strategy_bandwidth_expansion_htf.py](code/strategy_bandwidth_expansion_htf.py) | [docs/strategy_bandwidth_expansion_htf_report.md](docs/strategy_bandwidth_expansion_htf_report.md) | 2026-10-30 | -66.5% vs +3.1% (EUR_USD); variant=pre-registered fixed rule; see report |

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
| `bar_clv` | S-28 |
| `vol_rel_24` | S-27, S-29 |
| `ema_dist_24` | S-30 |
| `st_dist_24_2` | S-31, S-40 |
| `psar_dist_0p01_0p1` | S-32 |
| `kc_upper_24`, `kc_mid_24` | S-33 |
| `bb_pctb_24` | S-34, S-35 |
| `bb_width_24` | S-35 |
| `dc_pos_24` | S-36 |
| `dc_mid_24` | S-14, S-37 |
| `dist_low_24` | S-38 |
| `dc_upper_24`, `dc_lower_24` | S-39 |
| `st_dir_24_2` | S-05, S-40 |
| `hv_24` | S-41 |
| `bar_body_ratio` | S-42 |
| `minus_di_24`, `plus_di_24` | S-43 |
| `sma_24`, `sma_60` | S-44 |
| `macd_12_60`, `macd_signal_12_60` | S-45 |
| `atr_pct_24` | S-46 |
| `dist_high_24` | S-47 |
| `vol_ratio_12_60` | S-48 |
| `kc_lower_24`, `kc_mid_24` | S-49 |
| `bb_lower_24`, `bb_mid_24` | S-50 |
| `bar_upper_wick_ratio` | S-51 |
| `bar_clv` | S-52 |
| `macd_hist_atr_6_24` | S-53 |
| `h1_adx_24` | S-54 |
| `h1_rsi_24` | S-55 |
| `h1_er_24` | S-56 |
| `h1_ema_dist_24` | S-57 |
| `roc_24` | S-12, S-58, S-72 |
| `stoch_k_24`, `stoch_d_24` | S-10, S-59, S-71 |
| `aroon_down_24` | S-15, S-60, S-71 |
| `mom_24` | S-27, S-61 |
| `hv_24` | S-41, S-62 |
| `bb_upper_24` | S-63, S-66 |
| `dc_upper_24` | S-14, S-39, S-64 |
| `bar_lower_wick_ratio` | S-65 |
| `vol_rel_24` | S-27, S-29, S-66, S-72, S-87 |
| `h1_adx_24`, `h1_st_dir_24_3` | S-67 |
| `st_dir_24_3`, `st_dir_120_2` | S-68 |
| `h1_atr_pct_24` | S-70 |
| `aroon_up_60` | S-73 |
| `willr_60` | S-74 |
| `cci_120` | S-75 |
| `stoch_k_60` | S-76 |
| `mfi_60` | S-77 |
| `atr_pct_120` | S-78 |
| `roc_120` | S-79, S-87, S-101 |
| `hour_sin` | S-80, S-86 |
| `dow_sin` | S-81, S-86 |
| `tr` | S-82 |
| `psar_dir_0p02_0p2` | S-83 |
| `st_dir_120_3`, `st_dir_24_3` | S-84 |
| `h1_st_dir_120_3`, `st_dir_24_3` | S-85 |
| `rsi_12` | S-88 |
| `aroon_up_12`, `aroon_down_12` | S-89 |
| `macd_hist_6_24` | S-90 |
| `stoch_d_12` | S-91 |
| `mfi_12` | S-92 |
| `willr_12` | S-93 |
| `er_12` | S-94 |
| `hv_120` | S-95 |
| `bb_width_60` | S-96 |
| `rsi_12`, `stoch_k_12`, `mfi_12` | S-97 |
| `rsi_12`, `willr_12`, `stoch_d_12`, `mfi_12` | S-98 |
| `roc_6`, `vol_ratio_6_24` | S-99 |
| `macd_6_24`, `macd_signal_6_24` | S-100 |
| `ema_120` | S-101 |
| `dc_pos_12` | S-102 |
| `chop_120` | S-103 |
| `cmf_60` | S-104 |
| `hv_60` | S-105 |
| `stoch_d_60` | S-106 |
| `sqz_on_120` | S-107 |
| `rsi_6` | S-108 |
| `adx_60` | S-109 |
| `stoch_k_120` | S-110 |
| `willr_6` | S-111 |
| `er_60` | S-112, S-130 |
| `aroon_up_24`, `aroon_down_24`, `adx_24` | S-113 |
| `ema_dist_24`, `h1_ema_dist_24` | S-114 |
| `dist_high_24`, `dist_low_24`, `h1_adx_24`, `dc_pos_24` | S-115 |
| `sqz_on_24`, `bar_clv`, `h1_ema_dist_24` | S-116 |
| `vwap`, `h1_adx_24` | S-117 |
| `bb_pctb_24`, `chop_24`, `h1_adx_24` | S-118 |
| `dist_high_60`, `dist_low_60`, `h1_ema_dist_24` | S-119 |
| `plus_di_60`, `minus_di_60`, `adx_60` | S-120 |
| `macd_hist_atr_12_60`, `er_24` | S-121 |
| `psar_dir_0p01_0p1`, `h1_st_dir_24_3` | S-122 |
| `bar_lower_wick_ratio`, `bar_upper_wick_ratio`, `bar_clv`, `bb_pctb_60` | S-123 |
| `sqz_on_60`, `dist_high_60`, `dist_low_60`, `vol_rel_60`, `dc_pos_60` | S-124 |
| `ema_dist_60`, `h1_st_dir_120_3` | S-125 |
| `atr_pct_24`, `atr_pct_60`, `dist_high_24`, `dist_low_24`, `dc_pos_24` | S-126 |
| `cmf_12`, `h1_ema_dist_24` | S-127 |
| `vwap`, `h1_adx_24`, `h1_ema_dist_24` | S-128 |
| `h1_st_dir_24_3`, `dist_high_120`, `dist_low_120`, `dc_pos_120` | S-129 |
| `dc_pos_60`, `er_60` | S-130 |
| `bar_clv`, `vol_rel_6`, `h1_adx_24` | S-131 |
| `bb_width_12`, `bb_width_60`, `h1_ema_dist_24`, `dc_pos_24` | S-132 |

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
