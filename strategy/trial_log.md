# Strategy Trial Log

> **Purpose:** the cumulative record of *every* strategy attempt — tested,
> parked, **and rejected** — so the multiple-testing burden of "best of N" is
> always visible. This is the OOS discipline from `config/strategies.yml`
> (`trial_log.required_fields`). A `tested` result earned after many rejections
> is worth far less than one earned on the first try; this table makes that
> difference explicit and auditable.
>
> **Rules:**
> - Add a row for **every** Step 6 evaluation (Step 7 close-out), regardless of
>   outcome. Rejected outcomes are *mandatory* here (the registry's
>   "Rejected combinations" table stays; this log adds the *running count*).
> - `n_tried_before` = how many distinct strategies were attempted **before**
>   this one (0 for the first). It is the honest denominator for "best of N".
> - `window` ∈ `full` | `last_12m` | `oos`. The **`oos`** row is the single,
>   final out-of-sample check and may be written **at most once** per strategy
>   (`config/strategies.yml` → `oos.usage = finalist_only_once`).
> - If a strategy is re-opened with a *new hypothesis*, it gets a **new ID** and
>   a new row — never a retune of the same row (see `generated_strategy.md` §6).

> **Legacy date correction (2026-10-31):** S-18..S-102 previously used future
> batch labels as dates. Their `date` and registry `Last run` now record the
> Sydney date of the commit that first contains their sweep evidence. This is
> a **recorded-by bound**, not a recovered execution timestamp. Exact legacy run
> times are unavailable. Historical filenames remain stable batch identifiers.
> See [independent verification](../docs/review_verification_20261031.md).

| # | date | strategy_id | hypothesis (one line) | window | outcome | ret vs BH (primary) | n_tried_before |
|---|------|-------------|-----------------------|--------|---------|---------------------|----------------|
| 1 | 2026-10-28 | S-01 | 5m RSI-24 30/55 long-only mean reversion | full | **rejected** | full c2 −19.2% vs +2.3% (EUR_USD); −34.8% vs +1538% (BTC_USD); 777 trades — cost × frequency | 0 |
| 2 | 2026-10-28 | S-05 | 5m SuperTrend(24, 2.0) `st_dir_24_2` flip trend-following (long-only) | full | **rejected** | 10,402 trades (full); below buy-hold at every cost tier on all 3 instruments (full c2 EUR −99%/BTC −97%/XAU −98%) — cost × frequency | 1 |
| 3 | 2026-10-28 | S-06 | 5m EMA-spread 24/120 `ema_spread_24_120` trend follower (long-only) | full | **rejected** | full c0 +2402% vs BH +1538% (BTC only), below buy-hold at 2/5 bps (+903/+154%); loses on EUR at every tier — single-instrument, not cross-market | 2 |
| 4 | 2026-10-29 | S-02 | same RSI-24 30/55 rule on 1h bars (1/12 the cost of S-01) | full | **rejected** | 74–79 trades (full), below buy-hold at every cost tier (c0 EUR −5.2%/BTC +21%/XAU +6.7% all < buy-hold) — signal quality, not frequency | 3 |
| 5 | 2026-10-29 | S-03 | RSI-24 < 30 AND close > ema_24 (buy dips in an uptrend) | full | **rejected** | **0 trades** in all 18 cells: `rsi_24<30` and `close>ema_24` never co-occur on this data (verified intersection = 0 on all 3 instruments) — empty signal, not a bug | 4 |
| 6 | 2026-10-29 | S-04 | Bollinger squeeze-onset follower (long/short, enter on 0→1 onset, exit on 1→0) | full | **rejected** | ~10,500 trades (full), ~1,900/yr; below buy-hold at every cost tier incl. 0 bps (c0 EUR −7.8%/BTC −57.8%/XAU −20.9%) — cost × frequency, "low-frequency" premise false at 5m | 5 |
| 7 | 2026-10-29 | S-07 | Regime-gated slow trend: ST-120 flips taken only while ADX-24>25 (1h, long/short) | full | **rejected** | ~68–105/yr (low-freq ✓) but below buy-hold at every cost tier incl. 0 bps (c0 EUR −5.1%/BTC +73.6%/XAU −16.2% vs +3.1/+1288/+110); win 33–37% — signal quality, not frequency | 6 |
| 8 | 2026-10-30 | S-08 | CCI-24 dip-buying (6-variant sweep: base/ema_gate/slower/1h/entry_guard/band_wide) | full | **rejected** | no variant beat BH on ≥2/3 instruments @2bps; best cell S-08 slower EUR full edge −1.3% (116 trades) — cost × frequency (206–1,700/yr on 5m) | 7 |
| 9 | 2026-10-30 | S-09 | Williams %R-24 rebound buyer (6-variant sweep incl. cooldown) | full | **rejected** | no variant beat BH on ≥2/3 instruments @2bps; 5m variants 4,000–5,900 trades (cost × frequency); 1h best −268% | 8 |
| 10 | 2026-10-30 | S-10 | Stochastic-24 oversold-turn (6-variant sweep) | full | **rejected** | no variant beat BH on ≥2/3 instruments @2bps; 5m variants 8,900–12,500 trades (cost × frequency) | 9 |
| 11 | 2026-10-30 | S-11 | MACD-12/60 momentum turn with ATR-normalised entry (6-variant sweep) | full | **rejected** | no variant beat BH on ≥2/3 instruments @2bps; 5m variants ~2,600–2,750 trades (cost × frequency) | 10 |
| 12 | 2026-10-30 | S-12 | Dual-velocity (ROC-24 + slow-EMA slope) (6-variant sweep) | full | **rejected** | no variant beat BH on ≥2/3 instruments @2bps; 5m variants 5,800–7,500 trades (cost × frequency) | 11 |
| 13 | 2026-10-30 | S-13 | Slow PSAR 0.01/0.1 direction follower (6-variant sweep) | full | **rejected** | no variant beat BH on ≥2/3 instruments @2bps; ~6,480 trades (cost × frequency); best 1h −142% | 12 |
| 14 | 2026-10-30 | S-14 | Donchian-24 channel follower (6-variant sweep incl. hysteresis) | full | **rejected** | no variant beat BH on ≥2/3 instruments @2bps; 5m variants 7,100–13,200 trades (cost × frequency); best 1h −86% | 13 |
| 15 | 2026-10-30 | S-15 | Aroon-24 fresh-trend buyer (6-variant sweep) | full | **rejected** | no variant beat BH on ≥2/3 instruments @2bps; 274–3,323 trades; best 1h −265% | 14 |
| 16 | 2026-10-30 | S-16 | MFI-24 volume-exhaustion dip-buyer (6-variant sweep) | full | **rejected** | no variant beat BH on ≥2/3 instruments @2bps; 30–941 trades; best 1h −254% | 15 |
| 17 | 2026-10-30 | S-17 | Slow RSI-60 (1h) with ST/ADX regime gate (6-variant sweep) | full | **rejected** | no variant beat BH on ≥2/3 instruments @2bps; 0–2 trades (extremely selective); best edge −249% | 16 |
| 18 | 2026-10-30 | S-18 | VWAP-stretch reversion: enter when (close−vwap)/atr up-crosses > k, exit below k_exit (6-variant: base/ema_gate/looser/tight_exit/1h/entry_guard) | full | **rejected** | best `1h` mean edge **+24%** @2bps is BTC-only (full +459 on BTC, −70/−146 on EUR/XAU; last_12m 0/3) — single-instrument fit, not cross-market; 5m variants 441–2,112 tpy (cost × frequency) | 17 |
| 19 | 2026-10-30 | S-19 | CMF-24 accumulation follower: cmf_24 up-cross > k, exit below 0 (6-variant incl. tighter/looser) | full | **rejected** | best `1h` mean edge −121%; 5m variants 140–2,850 tpy (cost × frequency); no variant beat BH on ≥2/3 instruments | 18 |
| 20 | 2026-10-30 | S-20 | Multi-scale SuperTrend alignment: short ST up-flip gated by long-scale ST (6-variant incl. `h1_st_dir_120_3` HTF gate) | full | **rejected** | best `1h` mean edge −162%; 5m variants 127–1,543 tpy; gating (dual/HTF) cuts trades but no cross-market edge | 19 |
| 21 | 2026-10-30 | S-21 | Slow 60-bar squeeze regime: long while sqz_on_60 on + close>bb_mid_60 (6-variant incl. onset_only) | full | **rejected** | best `1h` mean edge −253%; fewest trades of batch (1h ~15/yr) yet most negative — selective long-only rule sits in the EUR/XAU drawdown | 20 |
| 22 | 2026-10-30 | S-22 | Efficiency-ratio regime: long while er_24 > k and close > ema_24 (6-variant k-sweep 0.20–0.50) | full | **rejected** | best `1h` mean edge −224%; 5m variants 173–3,039 tpy (cost × frequency); no variant beat BH on ≥2/3 instruments | 21 |
| 23 | 2026-10-30 | S-23 | Slow ATR-normalised MACD: long while macd_hist_atr_24_120 > th (6-variant incl. hysteresis) | full | **rejected** | best `1h` mean edge −130%; 5m variants 88–1,075 tpy; hysteresis/pos_th reduce trades without a cross-market edge | 22 |
| 24 | 2026-10-30 | S-24 | ATR-band breakout: long while (close−ema)/atr ≥ k, exit < k_exit (6-variant band 0.5–1.5) | full | **rejected** | best `1h` mean edge −138%; 5m variants 183–3,501 tpy (cost × frequency); no variant beat BH on ≥2/3 instruments | 23 |
| 25 | 2026-10-30 | S-25 | Chop-regime mean-reversion: stretched-below-ema while chop_24 > chop_at (6-variant chop_at 55–65) | full | **rejected** | best `1h` mean edge −254%; low-frequency (1h ~19/yr) but long-only in down-trending EUR/XAU; no variant beat BH on ≥2/3 instruments | 24 |
| 26 | 2026-10-30 | S-26 | EMA-12/60-spread follower: spread up-cross > th, hysteresis exit (6-variant incl. hysteresis) | full | **rejected** | best `1h` mean edge −170%; 5m variants 49–685 tpy; same cost×frequency signature as S-06 (EMA-spread family) | 25 |
| 27 | 2026-10-30 | S-27 | Volume-confirmed momentum: mom_24 > 0 and vol_rel_24 ≥ vmin (6-variant vol 0.8–2.0) | full | **rejected** | best `1h` mean edge −230%; 5m variants 195–2,976 tpy (cost × frequency); volume gate reduces trades without a cross-market edge | 26 |
| 28 | 2026-10-30 | S-28 | Candle-close momentum: long while `close > ema` (k-in/exit, `ema_gate`), 8-variant incl. 1h | full | **rejected** | best `1h` mean edge −323%; 5m ~1,290 tpy (cost × frequency); no variant beat BH on ≥2/3 instruments | 27 |
| 29 | 2026-10-30 | S-29 | Vol-convergence: close/EMA separation with `ema_std_ratio_20` hysteresis, 8-variant incl. 1h | full | **rejected** | best `1h` mean edge −19% (full win 1/3); 5m ~226 tpy; no cross-market edge on ≥2/3 instruments | 28 |
| 30 | 2026-10-30 | S-30 | ATR-band % move: `atr_range_position_pct` vs prior-13, 8-variant incl. 1h | full | **rejected** | best `1h` mean edge −127%; 5m ~139 tpy (cost × frequency); no variant beat BH on ≥2/3 instruments | 29 |
| 31 | 2026-10-30 | S-31 | Std-dev distance: `ema_std_ratio_20` vs prior-13, 8-variant incl. 1h | full | **rejected** | best `1h` mean edge −95%; 5m ~136 tpy (cost × frequency); no variant beat BH on ≥2/3 instruments | 30 |
| 32 | 2026-10-30 | S-32 | Parabolic-SAR distance: `parabolic_sar_distance` vs prior-13, 8-variant incl. 1h | full | **rejected** | best `1h` mean edge −145%; 5m ~157 tpy (cost × frequency); no variant beat BH on ≥2/3 instruments | 31 |
| 33 | 2026-10-30 | S-33 | Keltner close breakout: `keltner_close_breakout` flag, 8 flag-variants incl. 1h | full | **rejected** | best `1h` mean edge −211%; 5m ~73 tpy (cost × frequency); no variant beat BH on ≥2/3 instruments | 32 |
| 34 | 2026-10-30 | S-34 | Bollinger %B: `bb_pctb` vs prior-13, 8-variant incl. 1h | full | **rejected** | best `1h` mean edge −276%; 5m ~178 tpy (cost × frequency); no variant beat BH on ≥2/3 instruments | 33 |
| 35 | 2026-10-30 | S-35 | Bollinger width: `bb_width` vs prior-13, 8-variant incl. 1h | full | **rejected** | best `1h` mean edge +33% (full win 2/3, last-12m 1/3) but BTC-only, 18 full trades; fails ≥2/3-instruments + both-windows rule | 34 |
| 36 | 2026-10-30 | S-36 | Donchian position: `dc_position` vs prior-13, 8-variant incl. 1h | full | **rejected** | best `1h` mean edge +48% (full win 1/3, BTC +416% on 630 trades); fails ≥2/3-instruments + both-windows rule | 35 |
| 37 | 2026-10-30 | S-37 | Donchian-mid cross: `donchian_mid_cross` flag, 8 flag-variants incl. 1h+guard | full | **rejected** | best `1h_guard` mean edge −78%; 5m ~292 tpy (cost × frequency); no variant beat BH on ≥2/3 instruments | 36 |
| 38 | 2026-10-30 | S-38 | Distance to 20-bar low: `dist_low_20` vs prior-13, 8-variant incl. 1h | full | **rejected** | best `1h` mean edge −158%; 5m ~156 tpy (cost × frequency); no variant beat BH on ≥2/3 instruments | 37 |
| 39 | 2026-10-30 | S-39 | Donchian width: `dc_width` vs prior-13, 8-variant incl. 1h | full | **rejected** | best `1h` mean edge −248%; near-flat exposure (~0.1 tpy); no variant beat BH on ≥2/3 instruments | 38 |
| 40 | 2026-10-30 | S-40 | Std-dev distance hysteresis band: `ema_std_ratio_20` band, 8-variant incl. 1h | full | **rejected** | best `1h` mean edge −86%; 5m ~152 tpy (cost × frequency); no variant beat BH on ≥2/3 instruments | 39 |
| 41 | 2026-10-30 | S-41 | Realized-vol contraction: `hv_24` vs prior-13, 8-variant incl. 1h | full | **rejected** | best `1h` mean edge −248%; near-flat exposure (~0.5 tpy); no variant beat BH on ≥2/3 instruments | 40 |
| 42 | 2026-10-30 | S-42 | Bar-body momentum: `bar_body_ratio` vs prior-13, 8-variant incl. 1h | full | **rejected** | best `1h` mean edge −221%; 5m ~988 tpy (cost × frequency); no variant beat BH on ≥2/3 instruments | 41 |
| 43 | 2026-10-30 | S-43 | Directional-Index spread: `plus_di_24`−`minus_di_24` up-cross > k_in (fresh), 8-variant incl. 1h | full | **rejected** | best `1h` mean edge −175%; 5m ~97 tpy; no variant beat BH on ≥2/3 instruments | 42 |
| 44 | 2026-10-30 | S-44 | Dual-SMA trend: close > `sma_24` > `sma_60` (fresh), exit close < `sma_60`, 8 flag-variants | full | **rejected** | best `1h_ema` mean edge −157%; 5m ~90 tpy; no variant beat BH on ≥2/3 instruments | 43 |
| 45 | 2026-10-30 | S-45 | MACD signal-line cross: `macd_12_60` > `macd_signal_12_60` (fresh), 8 flag-variants | full | **rejected** | best `1h_guard` mean edge +147% but **BTC-only** (full +1,068 on 182 tpy, XAU −71); fails ≥2/3-instruments on both windows | 44 |
| 46 | 2026-10-30 | S-46 | ATR-% low-vol trend: `atr_pct_24` < k_in and close > ema, 8-variant incl. 1h | full | **rejected** | best `looser` mean edge −27%; near-flat (~5 tpy); no variant beat BH on ≥2/3 instruments | 45 |
| 47 | 2026-10-30 | S-47 | Distance-to-prior-high: `dist_high_24` up-cross > k_in (fresh), 8-variant incl. 1h | full | **rejected** | best `1h` mean edge −247%; 5m ~163 tpy; no variant beat BH on ≥2/3 instruments | 46 |
| 48 | 2026-10-30 | S-48 | ATR vol-ratio: `vol_ratio_12_60` up-cross > k_in (fresh), 8-variant incl. 1h | full | **rejected** | best `wide_exit` mean edge −69%; 5m ~90 tpy; no variant beat BH on ≥2/3 instruments | 47 |
| 49 | 2026-10-30 | S-49 | Keltner lower-band bounce: close > `kc_lower_24` (fresh), 8 flag-variants | full | **rejected** | best `1h_ema` mean edge −255%; near-flat (~2 tpy); no variant beat BH on ≥2/3 instruments | 48 |
| 50 | 2026-10-30 | S-50 | Bollinger midline pullback: close > `bb_mid_24` (fresh), 8 flag-variants | full | **rejected** | best `1h_ema_guard` mean edge −164%; 5m ~63 tpy; no variant beat BH on ≥2/3 instruments | 49 |
| 51 | 2026-10-30 | S-51 | Low upper-wick: `bar_upper_wick_ratio` < k_in (fresh), 8-variant incl. 1h | full | **rejected** | best `1h` mean edge −291%; 5m ~784 tpy (cost × frequency); no variant beat BH on ≥2/3 instruments | 50 |
| 52 | 2026-10-30 | S-52 | Close-location: `bar_clv` up-cross > k_in (fresh), 8-variant incl. 1h | full | **rejected** | best `1h` mean edge −323%; 5m ~1,294 tpy (cost × frequency); no variant beat BH on ≥2/3 instruments | 51 |
| 53 | 2026-10-30 | S-53 | Fast MACD histogram: `macd_hist_atr_6_24` up-cross > k_in (fresh), 8-variant incl. 1h | full | **rejected** | best `1h` mean edge −178%; 5m ~313 tpy; no variant beat BH on ≥2/3 instruments | 52 |
| 54 | 2026-10-30 | S-54 | 1h ADX regime: `h1_adx_24` up-cross > k_in and close > ema, 8-variant | full | **rejected** | best `entry_ema` mean edge −113%; 5m ~20 tpy; no variant beat BH on ≥2/3 instruments | 53 |
| 55 | 2026-10-30 | S-55 | 1h RSI momentum: `h1_rsi_24` up-cross > k_in (fresh), 8-variant | full | **parked** | **in-sample finalist candidate**: `looser` (k_in=33/k_exit=27) beats BH at 2 bps on **BTC & XAU, both `full` and `last_12m`** (~11 tpy, 98% exposure) — clears the in-sample bar; S1 forces a terminal status because the `base` variant hits 360 full-window trades (EUR), so held `parked` for the human-nominated one-shot OOS gate (NOT consumed) | 54 |
| 56 | 2026-10-30 | S-56 | 1h efficiency-ratio regime: `h1_er_24` up-cross > k_in (fresh), 8-variant | full | **rejected** | best `looser` mean edge −178%; 5m ~247 tpy; no variant beat BH on ≥2/3 instruments | 55 |
| 57 | 2026-10-30 | S-57 | 1h EMA-distance pullback: `h1_ema_dist_24` enters 0..k_in band, 8-variant | full | **rejected** | best `entry_guard` mean edge −31%; 5m ~141 tpy; no variant beat BH on ≥2/3 instruments | 56 |
| 58 | 2026-10-30 | S-58 | Rate-of-change hysteresis: `roc_24` up-cross > k_in (fresh), 8-variant incl. 1h | full | **rejected** | best `1h` mean edge −87%; 5m base ~3,400 tpy; no variant beat BH on ≥2/3 instruments in any window | 57 |
| 59 | 2026-10-30 | S-59 | Stochastic K/D-turn rebound: `stoch_k_24`/`stoch_d_24` k>d & k<k_in (fresh), 8-variant incl. 1h | full | **rejected** | best `1h` mean edge −236%; no variant beat BH on ≥2/3 instruments in any window | 58 |
| 60 | 2026-10-30 | S-60 | Aroon-Down collapse: `aroon_down_24` down-cross < k_in (fresh), 8-variant incl. 1h | full | **rejected** | best `1h` mean edge −252%; no variant beat BH on ≥2/3 instruments in any window | 59 |
| 61 | 2026-10-30 | S-61 | Momentum sign-turn: `mom_24` up-cross > k_in (fresh), 8-variant incl. 1h | full | **rejected** | best `1h` mean edge −83%; no variant beat BH on ≥2/3 instruments in any window | 60 |
| 62 | 2026-10-30 | S-62 | Realized-vol expansion + trend: `hv_24` up-cross & close>ema (fresh), 8-variant incl. 1h | full | **rejected** | best `1h` mean edge −138%; near-miss on EUR `full` (−1.5% edge, 1 trade); no variant beat BH on ≥2/3 instruments | 61 |
| 63 | 2026-10-30 | S-63 | Bollinger-upper breakout: close up-cross > `bb_upper_24` (fresh), 8 flag-variants incl. 1h | full | **rejected** | best `1h` mean edge −126%; no variant beat BH on ≥2/3 instruments in any window | 62 |
| 64 | 2026-10-30 | S-64 | Donchian-upper breakout: close up-cross > `dc_upper_24` (fresh), exit < `bb_mid_24`, 8 flag-variants incl. 1h | full | **rejected** | best `1h_ema_guard` mean edge −254%; no variant beat BH on ≥2/3 instruments in any window | 63 |
| 65 | 2026-10-30 | S-65 | Lower-wick rejection: `bar_lower_wick_ratio` up-cross > k_in (fresh), 8-variant incl. 1h | full | **rejected** | best `1h` mean edge −306%; no variant beat BH on ≥2/3 instruments in any window | 64 |
| 66 | 2026-10-30 | S-66 | Volume-confirmed band breakout: close>`bb_upper_24` & `vol_rel_24`>vmin (fresh), 8-variant incl. 1h | full | **rejected** | best `1h` mean edge −240%; no variant beat BH on ≥2/3 instruments in any window | 65 |
| 67 | 2026-10-30 | S-67 | 1h ADX + 1h SuperTrend alignment: `h1_adx_24`>k_in & `h1_st_dir_24_3`>0 (fresh), 8-variant | full | **rejected** | best `looser` mean edge −226%; closest single cell EUR `last_12m` −0.14% (27 trades); no variant beat BH on ≥2/3 instruments | 66 |
| 68 | 2026-10-30 | S-68 | Dual-SuperTrend alignment: `st_dir_24_3`>0 & `st_dir_120_2`>0 (fresh), 8 flag-variants incl. 1h | full | **rejected** | best `1h_ema` mean edge −192%; no variant beat BH on ≥2/3 instruments in any window | 67 |
| 69 | 2026-10-30 | S-69 | Stochastic-K mid-turn + trend: `stoch_k_24` up-cross > k_in (fresh), 8-variant incl. 1h | full | **rejected** | best `1h` mean edge −49%; no variant beat BH on ≥2/3 instruments in any window | 68 |
| 70 | 2026-10-30 | S-70 | 1h low-vol coil + trend: `h1_atr_pct_24`<k_in & close>ema (fresh), 8-variant | full | **rejected** | best `base` mean edge −247%; no variant beat BH on ≥2/3 instruments in any window | 69 |
| 71 | 2026-10-30 | S-71 | Aroon-Down + Stochastic confluence: `aroon_down_24`<k_in & `stoch_k_24`>d_in & close>ema (fresh), 8-variant incl. 1h | full | **rejected** | best `1h` mean edge −273%; no variant beat BH on ≥2/3 instruments in any window | 70 |
| 72 | 2026-10-30 | S-72 | ROC + volume confluence: `roc_24`>k_in & `vol_rel_24`>vmin (fresh), 8-variant incl. 1h | full | **rejected** | best `1h` mean edge −267%; no variant beat BH on ≥2/3 instruments in any window | 71 |
| 73 | 2026-10-30 | S-73 | Slow Aroon-Up trend: `aroon_up_60` up-cross > k_in (fresh), 8-variant incl. 1h | full | **rejected** | best `1h` mean edge −252%; no variant beat BH on ≥2/3 instruments in any window | 72 |
| 74 | 2026-10-30 | S-74 | Slow Williams-%R rebound: `willr_60` up-cross > k_in (fresh), 8-variant incl. 1h | full | **rejected** | best `1h` mean edge −116%; no variant beat BH on ≥2/3 instruments in any window | 73 |
| 75 | 2026-10-30 | S-75 | Slow CCI momentum: `cci_120` up-cross > k_in (fresh), 8-variant incl. 1h | full | **rejected** | best `1h` mean edge −44%; no variant beat BH on ≥2/3 instruments in any window | 74 |
| 76 | 2026-10-30 | S-76 | Slow Stochastic-K turn: `stoch_k_60` up-cross > k_in (fresh), 8-variant incl. 1h | full | **rejected** | best `1h` mean edge −150%; no variant beat BH on ≥2/3 instruments in any window | 75 |
| 77 | 2026-10-30 | S-77 | Slow MFI accumulation: `mfi_60` up-cross > k_in (fresh), 8-variant incl. 1h | full | **rejected** | best `1h` mean edge −255%; no variant beat BH on ≥2/3 instruments in any window | 76 |
| 78 | 2026-10-30 | S-78 | Slow ATR-% expansion: `atr_pct_120` up-cross & close>ema (fresh), 8-variant incl. 1h | full | **rejected** | best `1h` mean edge −249%; no variant beat BH on ≥2/3 instruments in any window | 77 |
| 79 | 2026-10-30 | S-79 | Slow ROC momentum: `roc_120` up-cross > k_in (fresh), 8-variant incl. 1h | full | **rejected** | best `1h` mean edge −160%; no variant beat BH on ≥2/3 instruments in any window | 78 |
| 80 | 2026-10-30 | S-80 | Time-of-day regime: `hour_sin` up-cross > k_in (fresh), 8-variant incl. 1h | full | **rejected** | best `1h` mean edge −249%; no variant beat BH on ≥2/3 instruments in any window | 79 |
| 81 | 2026-10-30 | S-81 | Day-of-week regime: `dow_sin` up-cross > k_in (fresh), 8-variant incl. 1h | full | **rejected** | best `1h` mean edge −12%; **BTC-only** near-miss (BTC `last_12m` +15 to +29%, loses on EUR/XAU and BTC `full`) — same single-instrument artifact the ≥2/3 bar excludes | 80 |
| 82 | 2026-10-30 | S-82 | True-range collapse: `tr` down-cross < k_in (fresh), 8-variant incl. 1h | full | **rejected** | best `1h` mean edge −258%; no variant beat BH on ≥2/3 instruments in any window | 81 |
| 83 | 2026-10-30 | S-83 | Slow-PSAR direction follower: `psar_dir_0p02_0p2` up-flip > 0 (fresh), 8 flag-variants incl. 1h | full | **rejected** | best `1h` mean edge −160%; no variant beat BH on ≥2/3 instruments in any window | 82 |
| 84 | 2026-10-30 | S-84 | Dual SuperTrend 120/24 alignment: `st_dir_120_3`>0 & `st_dir_24_3`>0 (fresh), 8 flag-variants incl. 1h | full | **rejected** | best `1h_ema_guard` mean edge −190%; no variant beat BH on ≥2/3 instruments in any window | 83 |
| 85 | 2026-10-30 | S-85 | 1h SuperTrend-120 two-scale: `h1_st_dir_120_3`>0 & `st_dir_24_3`>0 (fresh), 8 flag-variants | full | **rejected** | best `ema_only` mean edge −272%; no variant beat BH on ≥2/3 instruments in any window | 84 |
| 86 | 2026-10-30 | S-86 | Dual time-of-day confluence: `hour_sin`>k_in & `dow_sin`>d_in (fresh), 8-variant incl. 1h | full | **rejected** | best `looser` mean edge −173%; no variant beat BH on ≥2/3 instruments in any window | 85 |
| 87 | 2026-10-30 | S-87 | Slow-ROC + volume confluence: `roc_120`>k_in & `vol_rel_24`>vmin (fresh), 8-variant incl. 1h | full | **rejected** | best `1h` mean edge −261%; no variant beat BH on ≥2/3 instruments in any window | 86 |
| 88 | 2026-10-30 | S-88 | Fast RSI-12 rebound: `rsi_12`>k_in (fresh), 8-variant incl. 1h | full | **rejected** | best `1h` mean edge +16% (BTC-only +256% full-window artifact, −61% on last_12m; EUR/XAU negative); no variant beat BH on ≥2/3 instruments in both windows | 87 |
| 89 | 2026-10-30 | S-89 | Aroon-12 spread: (aroon_up_12−aroon_down_12)>k_in (fresh), 8-variant incl. 1h | full | **rejected** | best `1h` mean edge −261%; no variant beat BH on ≥2/3 instruments in any window | 88 |
| 90 | 2026-10-30 | S-90 | Fast MACD hist (6/24): `macd_hist_6_24`>0 & close>ema_24 (fresh), 8 flag-variants incl. 1h | full | **rejected** | best `1h_ema_guard` mean edge −223%; no variant beat BH on ≥2/3 instruments in any window | 89 |
| 91 | 2026-10-30 | S-91 | Fast Stochastic-D turn: `stoch_d_12`>k_in (fresh), 8-variant incl. 1h | full | **rejected** | best `1h` mean edge −36%; no variant beat BH on ≥2/3 instruments in any window | 90 |
| 92 | 2026-10-30 | S-92 | Fast MFI-12 accumulation: `mfi_12`>k_in (fresh), 8-variant incl. 1h | full | **rejected** | best `1h` mean edge −169%; no variant beat BH on ≥2/3 instruments in any window | 91 |
| 93 | 2026-10-30 | S-93 | Fast Williams-%R rebound: `willr_12`>k_in (fresh), 8-variant incl. 1h | full | **rejected** | best `1h` mean edge −21% (BTC-only +88% full-window artifact); no variant beat BH on ≥2/3 instruments in both windows | 92 |
| 94 | 2026-10-30 | S-94 | Fast Efficiency-Ratio regime: `er_12`>k_in (fresh), 8-variant incl. 1h | full | **rejected** | best `1h` mean edge −256%; no variant beat BH on ≥2/3 instruments in any window | 93 |
| 95 | 2026-10-30 | S-95 | Slow-HV-120 low-vol regime: `hv_120`<k_in (fresh), 8-variant incl. 1h | full | **rejected** | best `looser` mean edge −44% (XAU-only +34% full; BTC −1506% on same variant); no variant beat BH on ≥2/3 instruments in any window | 94 |
| 96 | 2026-10-30 | S-96 | BB-Width-60 squeeze release: `bb_width_60`>k_in (fresh), 8-variant incl. 1h | full | **rejected** | best `combo` mean edge +31% (BTC +342% full only; XAU −129%, EUR −5%); `1h` 3/3 full-window wins are 1–25-trade artifacts (BTC 1 trade +3.7%, XAU 1 trade +0.2%); no variant beat BH on ≥2/3 instruments in both windows | 95 |
| 97 | 2026-10-30 | S-97 | Triple-oscillator confluence: `rsi_12`,`stoch_k_12`,`mfi_12` all > entry (fresh), 8-variant incl. 1h | full | **rejected** | best `1h` mean edge −216%; no variant beat BH on ≥2/3 instruments in any window | 96 |
| 98 | 2026-10-30 | S-98 | Quad-oscillator confluence: `rsi_12`,`willr_12`,`stoch_d_12`,`mfi_12` all > entry (fresh), 8-variant incl. 1h | full | **rejected** | best `1h` mean edge −205%; no variant beat BH on ≥2/3 instruments in any window | 97 |
| 99 | 2026-10-30 | S-99 | Fast-ROC + vol-ratio breakout: `roc_6`>k_in & `vol_ratio_6_24`>vmin & close>ema (fresh), 8-variant incl. 1h | full | **rejected** | best `1h` mean edge −248%; no variant beat BH on ≥2/3 instruments in any window | 98 |
| 100 | 2026-10-30 | S-100 | Fast MACD signal cross (6/24): `macd_6_24`>`macd_signal_6_24` (fresh), 8 flag-variants incl. 1h | full | **rejected** | best `1h` mean edge −169%; no variant beat BH on ≥2/3 instruments in any window | 99 |
| 101 | 2026-10-30 | S-101 | Slow-ROC-120 + EMA-120 confluence: `roc_120`>k_in & close>ema_120 (fresh), 8-variant incl. 1h | full | **rejected** | best `1h` mean edge −138%; no variant beat BH on ≥2/3 instruments in any window | 100 |
| 102 | 2026-10-30 | S-102 | Slow Donchian-Pos-12 regime: `dc_pos_12`>k_in (fresh), 8-variant incl. 1h | full | **rejected** | best `1h` mean edge −129%; no variant beat BH on ≥2/3 instruments in any window | 101 |

## Configuration tally (multiple-testing burden)

The user authorized an additional experimental cohort of 100 then 100
strategies on 2026-10-31. Its [registered design](docs/strategy_research_200_20261031_design.md)
and `research/strategies/SR-20261031-200/` preserve all planned/attempted
definitions. Both rounds completed: 200 new configurations and 9,000 matrix
cells. All 200 fail promotion; none accessed OOS. The project tally is now
**1,027 configurations** (827 legacy + 200 experimental), represented by
132 mature and 200 experimental definitions. The fifty source feature
hypotheses are not counted again as portfolio configurations. Every new
trial appears in the experimental table below and in the
[joint progress CSV](../research/strategies/SR-20261031-200/strategy_progress.csv).
See the [analysis](docs/strategy_research_200_20261031_results.md).
This cohort does not grant finalist or OOS eligibility.

> `n_tried_before` above counts **strategies**, but the sweeps evaluated each of
> S-08…S-27 with **6 variants**, and each strategy's *best variant* was picked
> in-sample. The honest denominator for "best of N" is the number of
> **configurations** tried, not strategies. This section is outside the X4
> parser (which reads only the table above) so it can state the burden
> explicitly (review follow-up #3 §C3).

| Quantity | Count | Basis |
|---|---:|---|
| **Strategies tried** (S-01 … S-132) | **132** | rows 1–132 above |
| **Configurations tried** (distinct `(strategy, variant)` pairs) | **827** | 727 prior configs + 80 sweep variants for S-103…S-112 + 20 fixed rules S-113…S-132 |
| **Cells per configuration** | 18 | 3 instruments × 2 windows × 3 cost tiers |
| **Total cells evaluated** | **≥ 14,886** | 827 × 18 |

The table above describes the historical S-series scope. Add 200 experimental
configurations and 9,000 cells: **1,027 configurations, at least 23,886 cells**
overall. The 1,200 additional entry-feature contrasts are statistical research
comparisons, not additional portfolio configurations or backtest cells.

**The finalist bar is *not* corrected for multiple testing.** A configuration
that "beats" the in-sample bar may have done so by chance among ~727
independent tries (the bar itself, `oos.pass_criteria`, is a single unadjusted
threshold). The single OOS holdout (`oos.usage = finalist_only_once`) is the
one unadjusted check that survives, which is exactly why it is reserved for a
*human-nominated* finalist and consumed at most once. When a finalist is
nominated, its tally (which row / which variant) **must** be written into this
log before promotion (WORKFLOW Step 6).

<!--
Append a new row for every attempt. Keep `n_tried_before` = (previous max #) so
the running count is always the true number of strategies tried so far.
Example next row:
| 2 | 2026-10-30 | S-02 | same RSI rule on 1h bars (1/12 the cost) | full | <outcome> | <ret vs BH> | 1 |
-->

| 103 | 2026-10-30 | S-103 | 5m strategy; 8-variant sweep; +2.5% vs +2.3% (EUR_USD) | full | **parked** | +2.5% vs +2.3% (EUR_USD) | 102 |
| 104 | 2026-10-30 | S-104 | 5m strategy; 8-variant sweep; -20.2% vs +3.1% (EUR_USD) | full | **rejected** | -20.2% vs +3.1% (EUR_USD) | 103 |
| 105 | 2026-10-30 | S-105 | 5m strategy; 8-variant sweep; +2.3% vs +2.3% (EUR_USD) | full | **rejected** | +2.3% vs +2.3% (EUR_USD) | 104 |
| 106 | 2026-10-30 | S-106 | 5m strategy; 8-variant sweep; -9.6% vs +3.1% (EUR_USD) | full | **rejected** | -9.6% vs +3.1% (EUR_USD) | 105 |
| 107 | 2026-10-30 | S-107 | 5m strategy; 8-variant sweep; -0.3% vs +3.1% (EUR_USD) | full | **rejected** | -0.3% vs +3.1% (EUR_USD) | 106 |
| 108 | 2026-10-30 | S-108 | 5m strategy; 8-variant sweep; -53.2% vs +3.1% (EUR_USD) | full | **rejected** | -53.2% vs +3.1% (EUR_USD) | 107 |
| 109 | 2026-10-30 | S-109 | 5m strategy; 8-variant sweep; +2.3% vs +2.3% (EUR_USD) | full | **rejected** | +2.3% vs +2.3% (EUR_USD) | 108 |
| 110 | 2026-10-30 | S-110 | 5m strategy; 8-variant sweep; -70.3% vs +2.3% (EUR_USD) | full | **rejected** | -70.3% vs +2.3% (EUR_USD) | 109 |
| 111 | 2026-10-30 | S-111 | 5m strategy; 8-variant sweep; -66.6% vs +3.1% (EUR_USD) | full | **rejected** | -66.6% vs +3.1% (EUR_USD) | 110 |
| 112 | 2026-10-30 | S-112 | 5m strategy; 8-variant sweep; -19.9% vs +3.1% (EUR_USD) | full | **rejected** | -19.9% vs +3.1% (EUR_USD) | 111 |
| 113 | 2026-10-30 | S-113 | 1h strategy; Aroon direction changes may persist longer when 1h ADX confirms a directional regime. | full | **rejected** | -20.8% vs +3.1% (EUR_USD) | 112 |
| 114 | 2026-10-30 | S-114 | 5m strategy; A 5m pullback recovery aligned with closed 1h direction may avoid counter-trend entries. | full | **rejected** | -99.8% vs +3.1% (EUR_USD) | 113 |
| 115 | 2026-10-30 | S-115 | 5m strategy; A break of the prior 24-bar extreme may persist when closed 1h ADX confirms trend strength. | full | **rejected** | -94.5% vs +3.1% (EUR_USD) | 114 |
| 116 | 2026-10-30 | S-116 | 5m strategy; Compression release with close-location aligned with 1h direction may filter weak breakouts. | full | **rejected** | -72.3% vs +3.1% (EUR_USD) | 115 |
| 117 | 2026-10-30 | S-117 | 5m strategy; In weak 1h trend regimes, a VWAP reclaim may capture intraday mean reversion. | full | **rejected** | -99.9% vs +3.1% (EUR_USD) | 116 |
| 118 | 2026-10-30 | S-118 | 5m strategy; Band re-entry may mean-revert when both local and 1h regimes are non-trending. | full | **rejected** | -85.5% vs +3.1% (EUR_USD) | 117 |
| 119 | 2026-10-30 | S-119 | 5m strategy; A break of the prior 60-bar extreme may continue when the closed 1h context agrees. | full | **rejected** | -96.6% vs +3.1% (EUR_USD) | 118 |
| 120 | 2026-10-30 | S-120 | 5m strategy; A slow directional-movement cross may reduce false starts when 60-bar ADX is established. | full | **rejected** | -5.6% vs +2.3% (EUR_USD) | 119 |
| 121 | 2026-10-30 | S-121 | 1h strategy; A normalized 1h MACD zero-cross may persist when the path is directionally efficient. | full | **rejected** | -11.4% vs +3.1% (EUR_USD) | 120 |
| 122 | 2026-10-30 | S-122 | 5m strategy; A slow PSAR reversal may be more selective when the closed 1h SuperTrend agrees. | full | **rejected** | -99.2% vs +3.1% (EUR_USD) | 121 |
| 123 | 2026-10-30 | S-123 | 5m strategy; Extreme band location plus rejection wick and close location may identify failed extensions. | full | **rejected** | -85.0% vs +2.3% (EUR_USD) | 122 |
| 124 | 2026-10-30 | S-124 | 5m strategy; A 60-bar squeeze release with activity and an extreme break may avoid low-energy false breaks. | full | **rejected** | -10.6% vs +2.3% (EUR_USD) | 123 |
| 125 | 2026-10-30 | S-125 | 5m strategy; A sustained normalized EMA-distance transition may carry when the slower 1h SuperTrend agrees. | full | **rejected** | -99.9% vs +3.1% (EUR_USD) | 124 |
| 126 | 2026-10-30 | S-126 | 5m strategy; Local volatility expansion relative to its slower baseline may confirm a channel break. | full | **rejected** | -22.2% vs +2.3% (EUR_USD) | 125 |
| 127 | 2026-10-30 | S-127 | 5m strategy; A shorter money-flow regime change may be useful only when closed 1h price trend agrees. | full | **rejected** | -100.0% vs +3.1% (EUR_USD) | 126 |
| 128 | 2026-10-30 | S-128 | 5m strategy; A session VWAP reclaim may be trend resumption when the closed 1h regime is strong and aligned. | full | **rejected** | -81.9% vs +3.1% (EUR_USD) | 127 |
| 129 | 2026-10-30 | S-129 | 5m strategy; A long-window 5m extreme break may persist when the closed 1h SuperTrend agrees. | full | **rejected** | -64.9% vs +3.1% (EUR_USD) | 128 |
| 130 | 2026-10-30 | S-130 | 1h strategy; A sustained 1h channel-position break may be more reliable when path efficiency is high. | full | **rejected** | -9.8% vs +3.1% (EUR_USD) | 129 |
| 131 | 2026-10-30 | S-131 | 5m strategy; Directional close-location with elevated tick activity may indicate an impulse in an established regime. | full | **rejected** | -99.2% vs +3.1% (EUR_USD) | 130 |
| 132 | 2026-10-30 | S-132 | 5m strategy; Short-window volatility expansion may signal a phase change when price location and 1h trend agree. | full | **rejected** | -66.5% vs +3.1% (EUR_USD) | 131 |

<!-- BEGIN SR-20261031-200 GENERATED RECORDS -->

## Experimental cohort trial log: 2026-10-31

All 200 outcomes are retained below. Native 1h execution; five development
windows and three costs per rule. None used OOS. Counts follow registration
order within each simultaneously registered batch, including all rejections.
The S-series parser covers the earlier table; this cohort has its own complete audit.

| Research ID | Date | Hypothesis: source / model / episode | Windows | Outcome | Full benchmark wins c2 | Max full trades | n_tried_before | Configurations before | Report |
|---|---|---|---|---|---:|---:|---:|---:|---|
| SR1-001 | 2026-10-31 | CB-01 / trend_alignment / immediate | full, recent, training, validation 1/2 | rejected | 0/3 | 1213 | 132 | 827 | [report](docs/strategy_research_200_reports/SR1-001.md) |
| SR1-002 | 2026-10-31 | CB-01 / candle_confirmation / immediate | full, recent, training, validation 1/2 | rejected | 0/3 | 301 | 133 | 828 | [report](docs/strategy_research_200_reports/SR1-002.md) |
| SR1-003 | 2026-10-31 | CB-02 / trend_alignment / immediate | full, recent, training, validation 1/2 | rejected | 0/3 | 1185 | 134 | 829 | [report](docs/strategy_research_200_reports/SR1-003.md) |
| SR1-004 | 2026-10-31 | CB-02 / candle_confirmation / immediate | full, recent, training, validation 1/2 | rejected | 0/3 | 342 | 135 | 830 | [report](docs/strategy_research_200_reports/SR1-004.md) |
| SR1-005 | 2026-10-31 | CB-03 / trend_alignment / immediate | full, recent, training, validation 1/2 | rejected | 0/3 | 48 | 136 | 831 | [report](docs/strategy_research_200_reports/SR1-005.md) |
| SR1-006 | 2026-10-31 | CB-03 / candle_confirmation / immediate | full, recent, training, validation 1/2 | rejected | 0/3 | 43 | 137 | 832 | [report](docs/strategy_research_200_reports/SR1-006.md) |
| SR1-007 | 2026-10-31 | CB-04 / trend_alignment / immediate | full, recent, training, validation 1/2 | rejected | 0/3 | 252 | 138 | 833 | [report](docs/strategy_research_200_reports/SR1-007.md) |
| SR1-008 | 2026-10-31 | CB-04 / candle_confirmation / immediate | full, recent, training, validation 1/2 | rejected | 0/3 | 195 | 139 | 834 | [report](docs/strategy_research_200_reports/SR1-008.md) |
| SR1-009 | 2026-10-31 | CB-05 / trend_alignment / immediate | full, recent, training, validation 1/2 | rejected | 0/3 | 276 | 140 | 835 | [report](docs/strategy_research_200_reports/SR1-009.md) |
| SR1-010 | 2026-10-31 | CB-05 / candle_confirmation / immediate | full, recent, training, validation 1/2 | rejected | 0/3 | 219 | 141 | 836 | [report](docs/strategy_research_200_reports/SR1-010.md) |
| SR1-011 | 2026-10-31 | CB-06 / trend_alignment / immediate | full, recent, training, validation 1/2 | rejected | 0/3 | 1049 | 142 | 837 | [report](docs/strategy_research_200_reports/SR1-011.md) |
| SR1-012 | 2026-10-31 | CB-06 / candle_confirmation / immediate | full, recent, training, validation 1/2 | rejected | 0/3 | 787 | 143 | 838 | [report](docs/strategy_research_200_reports/SR1-012.md) |
| SR1-013 | 2026-10-31 | CB-07 / trend_alignment / immediate | full, recent, training, validation 1/2 | rejected | 0/3 | 1210 | 144 | 839 | [report](docs/strategy_research_200_reports/SR1-013.md) |
| SR1-014 | 2026-10-31 | CB-07 / candle_confirmation / immediate | full, recent, training, validation 1/2 | rejected | 0/3 | 334 | 145 | 840 | [report](docs/strategy_research_200_reports/SR1-014.md) |
| SR1-015 | 2026-10-31 | CB-08 / trend_alignment / immediate | full, recent, training, validation 1/2 | rejected | 0/3 | 1238 | 146 | 841 | [report](docs/strategy_research_200_reports/SR1-015.md) |
| SR1-016 | 2026-10-31 | CB-08 / candle_confirmation / immediate | full, recent, training, validation 1/2 | rejected | 0/3 | 293 | 147 | 842 | [report](docs/strategy_research_200_reports/SR1-016.md) |
| SR1-017 | 2026-10-31 | CB-09 / trend_alignment / immediate | full, recent, training, validation 1/2 | rejected | 0/3 | 1181 | 148 | 843 | [report](docs/strategy_research_200_reports/SR1-017.md) |
| SR1-018 | 2026-10-31 | CB-09 / candle_confirmation / immediate | full, recent, training, validation 1/2 | rejected | 0/3 | 268 | 149 | 844 | [report](docs/strategy_research_200_reports/SR1-018.md) |
| SR1-019 | 2026-10-31 | CB-10 / trend_alignment / immediate | full, recent, training, validation 1/2 | rejected | 0/3 | 1588 | 150 | 845 | [report](docs/strategy_research_200_reports/SR1-019.md) |
| SR1-020 | 2026-10-31 | CB-10 / candle_confirmation / immediate | full, recent, training, validation 1/2 | rejected | 0/3 | 1279 | 151 | 846 | [report](docs/strategy_research_200_reports/SR1-020.md) |
| SR1-021 | 2026-10-31 | MR-01 / trend_alignment / immediate | full, recent, training, validation 1/2 | rejected | 0/3 | 1092 | 152 | 847 | [report](docs/strategy_research_200_reports/SR1-021.md) |
| SR1-022 | 2026-10-31 | MR-01 / candle_confirmation / immediate | full, recent, training, validation 1/2 | rejected | 0/3 | 6 | 153 | 848 | [report](docs/strategy_research_200_reports/SR1-022.md) |
| SR1-023 | 2026-10-31 | MR-02 / trend_alignment / immediate | full, recent, training, validation 1/2 | rejected | 0/3 | 1186 | 154 | 849 | [report](docs/strategy_research_200_reports/SR1-023.md) |
| SR1-024 | 2026-10-31 | MR-02 / candle_confirmation / immediate | full, recent, training, validation 1/2 | rejected | 0/3 | 440 | 155 | 850 | [report](docs/strategy_research_200_reports/SR1-024.md) |
| SR1-025 | 2026-10-31 | MR-03 / trend_alignment / immediate | full, recent, training, validation 1/2 | rejected | 0/3 | 205 | 156 | 851 | [report](docs/strategy_research_200_reports/SR1-025.md) |
| SR1-026 | 2026-10-31 | MR-03 / candle_confirmation / immediate | full, recent, training, validation 1/2 | rejected | 0/3 | 256 | 157 | 852 | [report](docs/strategy_research_200_reports/SR1-026.md) |
| SR1-027 | 2026-10-31 | MR-04 / trend_alignment / immediate | full, recent, training, validation 1/2 | rejected | 0/3 | 602 | 158 | 853 | [report](docs/strategy_research_200_reports/SR1-027.md) |
| SR1-028 | 2026-10-31 | MR-04 / candle_confirmation / immediate | full, recent, training, validation 1/2 | rejected | 0/3 | 5 | 159 | 854 | [report](docs/strategy_research_200_reports/SR1-028.md) |
| SR1-029 | 2026-10-31 | MR-05 / trend_alignment / immediate | full, recent, training, validation 1/2 | rejected | 0/3 | 1139 | 160 | 855 | [report](docs/strategy_research_200_reports/SR1-029.md) |
| SR1-030 | 2026-10-31 | MR-05 / candle_confirmation / immediate | full, recent, training, validation 1/2 | rejected | 0/3 | 167 | 161 | 856 | [report](docs/strategy_research_200_reports/SR1-030.md) |
| SR1-031 | 2026-10-31 | MR-06 / trend_alignment / immediate | full, recent, training, validation 1/2 | rejected | 0/3 | 1116 | 162 | 857 | [report](docs/strategy_research_200_reports/SR1-031.md) |
| SR1-032 | 2026-10-31 | MR-06 / candle_confirmation / immediate | full, recent, training, validation 1/2 | rejected | 0/3 | 454 | 163 | 858 | [report](docs/strategy_research_200_reports/SR1-032.md) |
| SR1-033 | 2026-10-31 | MR-07 / trend_alignment / immediate | full, recent, training, validation 1/2 | rejected | 0/3 | 175 | 164 | 859 | [report](docs/strategy_research_200_reports/SR1-033.md) |
| SR1-034 | 2026-10-31 | MR-07 / candle_confirmation / immediate | full, recent, training, validation 1/2 | rejected | 0/3 | 130 | 165 | 860 | [report](docs/strategy_research_200_reports/SR1-034.md) |
| SR1-035 | 2026-10-31 | MR-08 / trend_alignment / immediate | full, recent, training, validation 1/2 | rejected | 0/3 | 1504 | 166 | 861 | [report](docs/strategy_research_200_reports/SR1-035.md) |
| SR1-036 | 2026-10-31 | MR-08 / candle_confirmation / immediate | full, recent, training, validation 1/2 | rejected | 0/3 | 911 | 167 | 862 | [report](docs/strategy_research_200_reports/SR1-036.md) |
| SR1-037 | 2026-10-31 | MR-09 / trend_alignment / immediate | full, recent, training, validation 1/2 | rejected | 0/3 | 6 | 168 | 863 | [report](docs/strategy_research_200_reports/SR1-037.md) |
| SR1-038 | 2026-10-31 | MR-09 / candle_confirmation / immediate | full, recent, training, validation 1/2 | rejected | 0/3 | 2 | 169 | 864 | [report](docs/strategy_research_200_reports/SR1-038.md) |
| SR1-039 | 2026-10-31 | MR-10 / trend_alignment / immediate | full, recent, training, validation 1/2 | rejected | 0/3 | 219 | 170 | 865 | [report](docs/strategy_research_200_reports/SR1-039.md) |
| SR1-040 | 2026-10-31 | MR-10 / candle_confirmation / immediate | full, recent, training, validation 1/2 | rejected | 0/3 | 185 | 171 | 866 | [report](docs/strategy_research_200_reports/SR1-040.md) |
| SR1-041 | 2026-10-31 | PA-01 / trend_alignment / immediate | full, recent, training, validation 1/2 | rejected | 0/3 | 1211 | 172 | 867 | [report](docs/strategy_research_200_reports/SR1-041.md) |
| SR1-042 | 2026-10-31 | PA-01 / candle_confirmation / immediate | full, recent, training, validation 1/2 | rejected | 0/3 | 713 | 173 | 868 | [report](docs/strategy_research_200_reports/SR1-042.md) |
| SR1-043 | 2026-10-31 | PA-02 / trend_alignment / immediate | full, recent, training, validation 1/2 | rejected | 0/3 | 1009 | 174 | 869 | [report](docs/strategy_research_200_reports/SR1-043.md) |
| SR1-044 | 2026-10-31 | PA-02 / candle_confirmation / immediate | full, recent, training, validation 1/2 | rejected | 0/3 | 630 | 175 | 870 | [report](docs/strategy_research_200_reports/SR1-044.md) |
| SR1-045 | 2026-10-31 | PA-03 / trend_alignment / immediate | full, recent, training, validation 1/2 | rejected | 0/3 | 11 | 176 | 871 | [report](docs/strategy_research_200_reports/SR1-045.md) |
| SR1-046 | 2026-10-31 | PA-03 / candle_confirmation / immediate | full, recent, training, validation 1/2 | rejected | 0/3 | 7 | 177 | 872 | [report](docs/strategy_research_200_reports/SR1-046.md) |
| SR1-047 | 2026-10-31 | PA-04 / trend_alignment / immediate | full, recent, training, validation 1/2 | rejected | 0/3 | 266 | 178 | 873 | [report](docs/strategy_research_200_reports/SR1-047.md) |
| SR1-048 | 2026-10-31 | PA-04 / candle_confirmation / immediate | full, recent, training, validation 1/2 | rejected | 0/3 | 163 | 179 | 874 | [report](docs/strategy_research_200_reports/SR1-048.md) |
| SR1-049 | 2026-10-31 | PA-05 / trend_alignment / immediate | full, recent, training, validation 1/2 | rejected | 0/3 | 1069 | 180 | 875 | [report](docs/strategy_research_200_reports/SR1-049.md) |
| SR1-050 | 2026-10-31 | PA-05 / candle_confirmation / immediate | full, recent, training, validation 1/2 | rejected | 0/3 | 286 | 181 | 876 | [report](docs/strategy_research_200_reports/SR1-050.md) |
| SR1-051 | 2026-10-31 | PA-06 / trend_alignment / immediate | full, recent, training, validation 1/2 | rejected | 0/3 | 248 | 182 | 877 | [report](docs/strategy_research_200_reports/SR1-051.md) |
| SR1-052 | 2026-10-31 | PA-06 / candle_confirmation / immediate | full, recent, training, validation 1/2 | rejected | 0/3 | 35 | 183 | 878 | [report](docs/strategy_research_200_reports/SR1-052.md) |
| SR1-053 | 2026-10-31 | PA-07 / trend_alignment / immediate | full, recent, training, validation 1/2 | rejected | 0/3 | 777 | 184 | 879 | [report](docs/strategy_research_200_reports/SR1-053.md) |
| SR1-054 | 2026-10-31 | PA-07 / candle_confirmation / immediate | full, recent, training, validation 1/2 | rejected | 0/3 | 543 | 185 | 880 | [report](docs/strategy_research_200_reports/SR1-054.md) |
| SR1-055 | 2026-10-31 | PA-08 / trend_alignment / immediate | full, recent, training, validation 1/2 | rejected | 0/3 | 1288 | 186 | 881 | [report](docs/strategy_research_200_reports/SR1-055.md) |
| SR1-056 | 2026-10-31 | PA-08 / candle_confirmation / immediate | full, recent, training, validation 1/2 | rejected | 0/3 | 974 | 187 | 882 | [report](docs/strategy_research_200_reports/SR1-056.md) |
| SR1-057 | 2026-10-31 | PA-09 / trend_alignment / immediate | full, recent, training, validation 1/2 | rejected | 0/3 | 743 | 188 | 883 | [report](docs/strategy_research_200_reports/SR1-057.md) |
| SR1-058 | 2026-10-31 | PA-09 / candle_confirmation / immediate | full, recent, training, validation 1/2 | rejected | 0/3 | 22 | 189 | 884 | [report](docs/strategy_research_200_reports/SR1-058.md) |
| SR1-059 | 2026-10-31 | PA-10 / trend_alignment / immediate | full, recent, training, validation 1/2 | rejected | 0/3 | 1731 | 190 | 885 | [report](docs/strategy_research_200_reports/SR1-059.md) |
| SR1-060 | 2026-10-31 | PA-10 / candle_confirmation / immediate | full, recent, training, validation 1/2 | rejected | 0/3 | 682 | 191 | 886 | [report](docs/strategy_research_200_reports/SR1-060.md) |
| SR1-061 | 2026-10-31 | PS-01 / trend_alignment / immediate | full, recent, training, validation 1/2 | rejected | 0/3 | 1308 | 192 | 887 | [report](docs/strategy_research_200_reports/SR1-061.md) |
| SR1-062 | 2026-10-31 | PS-01 / candle_confirmation / immediate | full, recent, training, validation 1/2 | rejected | 0/3 | 894 | 193 | 888 | [report](docs/strategy_research_200_reports/SR1-062.md) |
| SR1-063 | 2026-10-31 | PS-02 / trend_alignment / immediate | full, recent, training, validation 1/2 | rejected | 0/3 | 1253 | 194 | 889 | [report](docs/strategy_research_200_reports/SR1-063.md) |
| SR1-064 | 2026-10-31 | PS-02 / candle_confirmation / immediate | full, recent, training, validation 1/2 | rejected | 0/3 | 549 | 195 | 890 | [report](docs/strategy_research_200_reports/SR1-064.md) |
| SR1-065 | 2026-10-31 | PS-03 / trend_alignment / immediate | full, recent, training, validation 1/2 | rejected | 0/3 | 1185 | 196 | 891 | [report](docs/strategy_research_200_reports/SR1-065.md) |
| SR1-066 | 2026-10-31 | PS-03 / candle_confirmation / immediate | full, recent, training, validation 1/2 | rejected | 0/3 | 679 | 197 | 892 | [report](docs/strategy_research_200_reports/SR1-066.md) |
| SR1-067 | 2026-10-31 | PS-04 / trend_alignment / immediate | full, recent, training, validation 1/2 | rejected | 0/3 | 1380 | 198 | 893 | [report](docs/strategy_research_200_reports/SR1-067.md) |
| SR1-068 | 2026-10-31 | PS-04 / candle_confirmation / immediate | full, recent, training, validation 1/2 | rejected | 0/3 | 355 | 199 | 894 | [report](docs/strategy_research_200_reports/SR1-068.md) |
| SR1-069 | 2026-10-31 | PS-05 / trend_alignment / immediate | full, recent, training, validation 1/2 | rejected | 0/3 | 820 | 200 | 895 | [report](docs/strategy_research_200_reports/SR1-069.md) |
| SR1-070 | 2026-10-31 | PS-05 / candle_confirmation / immediate | full, recent, training, validation 1/2 | rejected | 0/3 | 472 | 201 | 896 | [report](docs/strategy_research_200_reports/SR1-070.md) |
| SR1-071 | 2026-10-31 | PS-06 / trend_alignment / immediate | full, recent, training, validation 1/2 | rejected | 0/3 | 921 | 202 | 897 | [report](docs/strategy_research_200_reports/SR1-071.md) |
| SR1-072 | 2026-10-31 | PS-06 / candle_confirmation / immediate | full, recent, training, validation 1/2 | rejected | 0/3 | 265 | 203 | 898 | [report](docs/strategy_research_200_reports/SR1-072.md) |
| SR1-073 | 2026-10-31 | PS-07 / trend_alignment / immediate | full, recent, training, validation 1/2 | rejected | 0/3 | 1306 | 204 | 899 | [report](docs/strategy_research_200_reports/SR1-073.md) |
| SR1-074 | 2026-10-31 | PS-07 / candle_confirmation / immediate | full, recent, training, validation 1/2 | rejected | 0/3 | 330 | 205 | 900 | [report](docs/strategy_research_200_reports/SR1-074.md) |
| SR1-075 | 2026-10-31 | PS-08 / trend_alignment / immediate | full, recent, training, validation 1/2 | rejected | 0/3 | 975 | 206 | 901 | [report](docs/strategy_research_200_reports/SR1-075.md) |
| SR1-076 | 2026-10-31 | PS-08 / candle_confirmation / immediate | full, recent, training, validation 1/2 | rejected | 0/3 | 118 | 207 | 902 | [report](docs/strategy_research_200_reports/SR1-076.md) |
| SR1-077 | 2026-10-31 | PS-09 / trend_alignment / immediate | full, recent, training, validation 1/2 | rejected | 0/3 | 683 | 208 | 903 | [report](docs/strategy_research_200_reports/SR1-077.md) |
| SR1-078 | 2026-10-31 | PS-09 / candle_confirmation / immediate | full, recent, training, validation 1/2 | rejected | 0/3 | 146 | 209 | 904 | [report](docs/strategy_research_200_reports/SR1-078.md) |
| SR1-079 | 2026-10-31 | PS-10 / trend_alignment / immediate | full, recent, training, validation 1/2 | rejected | 0/3 | 1451 | 210 | 905 | [report](docs/strategy_research_200_reports/SR1-079.md) |
| SR1-080 | 2026-10-31 | PS-10 / candle_confirmation / immediate | full, recent, training, validation 1/2 | rejected | 0/3 | 566 | 211 | 906 | [report](docs/strategy_research_200_reports/SR1-080.md) |
| SR1-081 | 2026-10-31 | TR-01 / trend_alignment / immediate | full, recent, training, validation 1/2 | rejected | 0/3 | 1743 | 212 | 907 | [report](docs/strategy_research_200_reports/SR1-081.md) |
| SR1-082 | 2026-10-31 | TR-01 / candle_confirmation / immediate | full, recent, training, validation 1/2 | rejected | 0/3 | 1363 | 213 | 908 | [report](docs/strategy_research_200_reports/SR1-082.md) |
| SR1-083 | 2026-10-31 | TR-02 / trend_alignment / immediate | full, recent, training, validation 1/2 | rejected | 0/3 | 1404 | 214 | 909 | [report](docs/strategy_research_200_reports/SR1-083.md) |
| SR1-084 | 2026-10-31 | TR-02 / candle_confirmation / immediate | full, recent, training, validation 1/2 | rejected | 0/3 | 435 | 215 | 910 | [report](docs/strategy_research_200_reports/SR1-084.md) |
| SR1-085 | 2026-10-31 | TR-03 / trend_alignment / immediate | full, recent, training, validation 1/2 | rejected | 0/3 | 497 | 216 | 911 | [report](docs/strategy_research_200_reports/SR1-085.md) |
| SR1-086 | 2026-10-31 | TR-03 / candle_confirmation / immediate | full, recent, training, validation 1/2 | rejected | 0/3 | 468 | 217 | 912 | [report](docs/strategy_research_200_reports/SR1-086.md) |
| SR1-087 | 2026-10-31 | TR-04 / trend_alignment / immediate | full, recent, training, validation 1/2 | rejected | 0/3 | 1728 | 218 | 913 | [report](docs/strategy_research_200_reports/SR1-087.md) |
| SR1-088 | 2026-10-31 | TR-04 / candle_confirmation / immediate | full, recent, training, validation 1/2 | rejected | 0/3 | 1393 | 219 | 914 | [report](docs/strategy_research_200_reports/SR1-088.md) |
| SR1-089 | 2026-10-31 | TR-05 / trend_alignment / immediate | full, recent, training, validation 1/2 | rejected | 0/3 | 1192 | 220 | 915 | [report](docs/strategy_research_200_reports/SR1-089.md) |
| SR1-090 | 2026-10-31 | TR-05 / candle_confirmation / immediate | full, recent, training, validation 1/2 | rejected | 0/3 | 929 | 221 | 916 | [report](docs/strategy_research_200_reports/SR1-090.md) |
| SR1-091 | 2026-10-31 | TR-06 / trend_alignment / immediate | full, recent, training, validation 1/2 | rejected | 0/3 | 475 | 222 | 917 | [report](docs/strategy_research_200_reports/SR1-091.md) |
| SR1-092 | 2026-10-31 | TR-06 / candle_confirmation / immediate | full, recent, training, validation 1/2 | rejected | 0/3 | 137 | 223 | 918 | [report](docs/strategy_research_200_reports/SR1-092.md) |
| SR1-093 | 2026-10-31 | TR-07 / trend_alignment / immediate | full, recent, training, validation 1/2 | rejected | 0/3 | 1414 | 224 | 919 | [report](docs/strategy_research_200_reports/SR1-093.md) |
| SR1-094 | 2026-10-31 | TR-07 / candle_confirmation / immediate | full, recent, training, validation 1/2 | rejected | 0/3 | 1131 | 225 | 920 | [report](docs/strategy_research_200_reports/SR1-094.md) |
| SR1-095 | 2026-10-31 | TR-08 / trend_alignment / immediate | full, recent, training, validation 1/2 | rejected | 0/3 | 1634 | 226 | 921 | [report](docs/strategy_research_200_reports/SR1-095.md) |
| SR1-096 | 2026-10-31 | TR-08 / candle_confirmation / immediate | full, recent, training, validation 1/2 | rejected | 0/3 | 530 | 227 | 922 | [report](docs/strategy_research_200_reports/SR1-096.md) |
| SR1-097 | 2026-10-31 | TR-09 / trend_alignment / immediate | full, recent, training, validation 1/2 | rejected | 0/3 | 652 | 228 | 923 | [report](docs/strategy_research_200_reports/SR1-097.md) |
| SR1-098 | 2026-10-31 | TR-09 / candle_confirmation / immediate | full, recent, training, validation 1/2 | rejected | 0/3 | 564 | 229 | 924 | [report](docs/strategy_research_200_reports/SR1-098.md) |
| SR1-099 | 2026-10-31 | TR-10 / trend_alignment / immediate | full, recent, training, validation 1/2 | rejected | 0/3 | 1023 | 230 | 925 | [report](docs/strategy_research_200_reports/SR1-099.md) |
| SR1-100 | 2026-10-31 | TR-10 / candle_confirmation / immediate | full, recent, training, validation 1/2 | rejected | 0/3 | 926 | 231 | 926 | [report](docs/strategy_research_200_reports/SR1-100.md) |
| SR2-001 | 2026-10-31 | CB-01 / trend_alignment / failure_reversal | full, recent, training, validation 1/2 | rejected | 0/3 | 642 | 232 | 927 | [report](docs/strategy_research_200_reports/SR2-001.md) |
| SR2-002 | 2026-10-31 | CB-01 / candle_confirmation / failure_reversal | full, recent, training, validation 1/2 | rejected | 0/3 | 144 | 233 | 928 | [report](docs/strategy_research_200_reports/SR2-002.md) |
| SR2-003 | 2026-10-31 | CB-02 / trend_alignment / failure_reversal | full, recent, training, validation 1/2 | rejected | 0/3 | 618 | 234 | 929 | [report](docs/strategy_research_200_reports/SR2-003.md) |
| SR2-004 | 2026-10-31 | CB-02 / candle_confirmation / failure_reversal | full, recent, training, validation 1/2 | rejected | 0/3 | 181 | 235 | 930 | [report](docs/strategy_research_200_reports/SR2-004.md) |
| SR2-005 | 2026-10-31 | CB-03 / trend_alignment / failure_reversal | full, recent, training, validation 1/2 | rejected | 0/3 | 23 | 236 | 931 | [report](docs/strategy_research_200_reports/SR2-005.md) |
| SR2-006 | 2026-10-31 | CB-03 / candle_confirmation / pullback_confirmation | full, recent, training, validation 1/2 | rejected | 0/3 | 3 | 237 | 932 | [report](docs/strategy_research_200_reports/SR2-006.md) |
| SR2-007 | 2026-10-31 | CB-04 / trend_alignment / persistent_context | full, recent, training, validation 1/2 | rejected | 0/3 | 0 | 238 | 933 | [report](docs/strategy_research_200_reports/SR2-007.md) |
| SR2-008 | 2026-10-31 | CB-04 / candle_confirmation / failure_reversal | full, recent, training, validation 1/2 | rejected | 0/3 | 111 | 239 | 934 | [report](docs/strategy_research_200_reports/SR2-008.md) |
| SR2-009 | 2026-10-31 | CB-05 / trend_alignment / pullback_confirmation | full, recent, training, validation 1/2 | rejected | 0/3 | 20 | 240 | 935 | [report](docs/strategy_research_200_reports/SR2-009.md) |
| SR2-010 | 2026-10-31 | CB-05 / candle_confirmation / pullback_confirmation | full, recent, training, validation 1/2 | rejected | 0/3 | 8 | 241 | 936 | [report](docs/strategy_research_200_reports/SR2-010.md) |
| SR2-011 | 2026-10-31 | CB-06 / trend_alignment / failure_reversal | full, recent, training, validation 1/2 | rejected | 0/3 | 529 | 242 | 937 | [report](docs/strategy_research_200_reports/SR2-011.md) |
| SR2-012 | 2026-10-31 | CB-06 / candle_confirmation / failure_reversal | full, recent, training, validation 1/2 | rejected | 0/3 | 447 | 243 | 938 | [report](docs/strategy_research_200_reports/SR2-012.md) |
| SR2-013 | 2026-10-31 | CB-07 / trend_alignment / persistent_context | full, recent, training, validation 1/2 | rejected | 0/3 | 45 | 244 | 939 | [report](docs/strategy_research_200_reports/SR2-013.md) |
| SR2-014 | 2026-10-31 | CB-07 / candle_confirmation / failure_reversal | full, recent, training, validation 1/2 | rejected | 0/3 | 180 | 245 | 940 | [report](docs/strategy_research_200_reports/SR2-014.md) |
| SR2-015 | 2026-10-31 | CB-08 / trend_alignment / persistent_context | full, recent, training, validation 1/2 | rejected | 0/3 | 33 | 246 | 941 | [report](docs/strategy_research_200_reports/SR2-015.md) |
| SR2-016 | 2026-10-31 | CB-08 / candle_confirmation / failure_reversal | full, recent, training, validation 1/2 | rejected | 0/3 | 151 | 247 | 942 | [report](docs/strategy_research_200_reports/SR2-016.md) |
| SR2-017 | 2026-10-31 | CB-09 / trend_alignment / failure_reversal | full, recent, training, validation 1/2 | rejected | 0/3 | 649 | 248 | 943 | [report](docs/strategy_research_200_reports/SR2-017.md) |
| SR2-018 | 2026-10-31 | CB-09 / candle_confirmation / failure_reversal | full, recent, training, validation 1/2 | rejected | 0/3 | 140 | 249 | 944 | [report](docs/strategy_research_200_reports/SR2-018.md) |
| SR2-019 | 2026-10-31 | CB-10 / trend_alignment / failure_reversal | full, recent, training, validation 1/2 | rejected | 0/3 | 868 | 250 | 945 | [report](docs/strategy_research_200_reports/SR2-019.md) |
| SR2-020 | 2026-10-31 | CB-10 / candle_confirmation / persistent_context | full, recent, training, validation 1/2 | rejected | 0/3 | 13 | 251 | 946 | [report](docs/strategy_research_200_reports/SR2-020.md) |
| SR2-021 | 2026-10-31 | MR-01 / trend_alignment / persistent_context | full, recent, training, validation 1/2 | rejected | 0/3 | 21 | 252 | 947 | [report](docs/strategy_research_200_reports/SR2-021.md) |
| SR2-022 | 2026-10-31 | MR-01 / candle_confirmation / pullback_confirmation | full, recent, training, validation 1/2 | rejected | 0/3 | 2 | 253 | 948 | [report](docs/strategy_research_200_reports/SR2-022.md) |
| SR2-023 | 2026-10-31 | MR-02 / trend_alignment / failure_reversal | full, recent, training, validation 1/2 | rejected | 0/3 | 592 | 254 | 949 | [report](docs/strategy_research_200_reports/SR2-023.md) |
| SR2-024 | 2026-10-31 | MR-02 / candle_confirmation / pullback_confirmation | full, recent, training, validation 1/2 | rejected | 0/3 | 126 | 255 | 950 | [report](docs/strategy_research_200_reports/SR2-024.md) |
| SR2-025 | 2026-10-31 | MR-03 / trend_alignment / failure_reversal | full, recent, training, validation 1/2 | rejected | 0/3 | 107 | 256 | 951 | [report](docs/strategy_research_200_reports/SR2-025.md) |
| SR2-026 | 2026-10-31 | MR-03 / candle_confirmation / persistent_context | full, recent, training, validation 1/2 | rejected | 0/3 | 0 | 257 | 952 | [report](docs/strategy_research_200_reports/SR2-026.md) |
| SR2-027 | 2026-10-31 | MR-04 / trend_alignment / failure_reversal | full, recent, training, validation 1/2 | rejected | 0/3 | 285 | 258 | 953 | [report](docs/strategy_research_200_reports/SR2-027.md) |
| SR2-028 | 2026-10-31 | MR-04 / candle_confirmation / pullback_confirmation | full, recent, training, validation 1/2 | rejected | 0/3 | 1 | 259 | 954 | [report](docs/strategy_research_200_reports/SR2-028.md) |
| SR2-029 | 2026-10-31 | MR-05 / trend_alignment / failure_reversal | full, recent, training, validation 1/2 | rejected | 0/3 | 577 | 260 | 955 | [report](docs/strategy_research_200_reports/SR2-029.md) |
| SR2-030 | 2026-10-31 | MR-05 / candle_confirmation / pullback_confirmation | full, recent, training, validation 1/2 | rejected | 0/3 | 49 | 261 | 956 | [report](docs/strategy_research_200_reports/SR2-030.md) |
| SR2-031 | 2026-10-31 | MR-06 / trend_alignment / persistent_context | full, recent, training, validation 1/2 | rejected | 0/3 | 28 | 262 | 957 | [report](docs/strategy_research_200_reports/SR2-031.md) |
| SR2-032 | 2026-10-31 | MR-06 / candle_confirmation / failure_reversal | full, recent, training, validation 1/2 | rejected | 0/3 | 246 | 263 | 958 | [report](docs/strategy_research_200_reports/SR2-032.md) |
| SR2-033 | 2026-10-31 | MR-07 / trend_alignment / pullback_confirmation | full, recent, training, validation 1/2 | rejected | 0/3 | 3 | 264 | 959 | [report](docs/strategy_research_200_reports/SR2-033.md) |
| SR2-034 | 2026-10-31 | MR-07 / candle_confirmation / pullback_confirmation | full, recent, training, validation 1/2 | rejected | 0/3 | 4 | 265 | 960 | [report](docs/strategy_research_200_reports/SR2-034.md) |
| SR2-035 | 2026-10-31 | MR-08 / trend_alignment / failure_reversal | full, recent, training, validation 1/2 | rejected | 0/3 | 818 | 266 | 961 | [report](docs/strategy_research_200_reports/SR2-035.md) |
| SR2-036 | 2026-10-31 | MR-08 / candle_confirmation / persistent_context | full, recent, training, validation 1/2 | rejected | 0/3 | 1 | 267 | 962 | [report](docs/strategy_research_200_reports/SR2-036.md) |
| SR2-037 | 2026-10-31 | MR-09 / trend_alignment / pullback_confirmation | full, recent, training, validation 1/2 | rejected | 0/3 | 1 | 268 | 963 | [report](docs/strategy_research_200_reports/SR2-037.md) |
| SR2-038 | 2026-10-31 | MR-09 / candle_confirmation / pullback_confirmation | full, recent, training, validation 1/2 | rejected | 0/3 | 0 | 269 | 964 | [report](docs/strategy_research_200_reports/SR2-038.md) |
| SR2-039 | 2026-10-31 | MR-10 / trend_alignment / persistent_context | full, recent, training, validation 1/2 | rejected | 0/3 | 1 | 270 | 965 | [report](docs/strategy_research_200_reports/SR2-039.md) |
| SR2-040 | 2026-10-31 | MR-10 / candle_confirmation / failure_reversal | full, recent, training, validation 1/2 | rejected | 0/3 | 95 | 271 | 966 | [report](docs/strategy_research_200_reports/SR2-040.md) |
| SR2-041 | 2026-10-31 | PA-01 / trend_alignment / failure_reversal | full, recent, training, validation 1/2 | rejected | 0/3 | 643 | 272 | 967 | [report](docs/strategy_research_200_reports/SR2-041.md) |
| SR2-042 | 2026-10-31 | PA-01 / candle_confirmation / failure_reversal | full, recent, training, validation 1/2 | rejected | 0/3 | 374 | 273 | 968 | [report](docs/strategy_research_200_reports/SR2-042.md) |
| SR2-043 | 2026-10-31 | PA-02 / trend_alignment / failure_reversal | full, recent, training, validation 1/2 | rejected | 0/3 | 537 | 274 | 969 | [report](docs/strategy_research_200_reports/SR2-043.md) |
| SR2-044 | 2026-10-31 | PA-02 / candle_confirmation / failure_reversal | full, recent, training, validation 1/2 | rejected | 0/3 | 328 | 275 | 970 | [report](docs/strategy_research_200_reports/SR2-044.md) |
| SR2-045 | 2026-10-31 | PA-03 / trend_alignment / failure_reversal | full, recent, training, validation 1/2 | rejected | 0/3 | 6 | 276 | 971 | [report](docs/strategy_research_200_reports/SR2-045.md) |
| SR2-046 | 2026-10-31 | PA-03 / candle_confirmation / failure_reversal | full, recent, training, validation 1/2 | rejected | 0/3 | 4 | 277 | 972 | [report](docs/strategy_research_200_reports/SR2-046.md) |
| SR2-047 | 2026-10-31 | PA-04 / trend_alignment / failure_reversal | full, recent, training, validation 1/2 | rejected | 0/3 | 132 | 278 | 973 | [report](docs/strategy_research_200_reports/SR2-047.md) |
| SR2-048 | 2026-10-31 | PA-04 / candle_confirmation / pullback_confirmation | full, recent, training, validation 1/2 | rejected | 0/3 | 8 | 279 | 974 | [report](docs/strategy_research_200_reports/SR2-048.md) |
| SR2-049 | 2026-10-31 | PA-05 / trend_alignment / failure_reversal | full, recent, training, validation 1/2 | rejected | 0/3 | 556 | 280 | 975 | [report](docs/strategy_research_200_reports/SR2-049.md) |
| SR2-050 | 2026-10-31 | PA-05 / candle_confirmation / pullback_confirmation | full, recent, training, validation 1/2 | rejected | 0/3 | 26 | 281 | 976 | [report](docs/strategy_research_200_reports/SR2-050.md) |
| SR2-051 | 2026-10-31 | PA-06 / trend_alignment / persistent_context | full, recent, training, validation 1/2 | rejected | 0/3 | 0 | 282 | 977 | [report](docs/strategy_research_200_reports/SR2-051.md) |
| SR2-052 | 2026-10-31 | PA-06 / candle_confirmation / failure_reversal | full, recent, training, validation 1/2 | rejected | 0/3 | 16 | 283 | 978 | [report](docs/strategy_research_200_reports/SR2-052.md) |
| SR2-053 | 2026-10-31 | PA-07 / trend_alignment / failure_reversal | full, recent, training, validation 1/2 | rejected | 0/3 | 400 | 284 | 979 | [report](docs/strategy_research_200_reports/SR2-053.md) |
| SR2-054 | 2026-10-31 | PA-07 / candle_confirmation / persistent_context | full, recent, training, validation 1/2 | rejected | 0/3 | 18 | 285 | 980 | [report](docs/strategy_research_200_reports/SR2-054.md) |
| SR2-055 | 2026-10-31 | PA-08 / trend_alignment / persistent_context | full, recent, training, validation 1/2 | rejected | 0/3 | 57 | 286 | 981 | [report](docs/strategy_research_200_reports/SR2-055.md) |
| SR2-056 | 2026-10-31 | PA-08 / candle_confirmation / persistent_context | full, recent, training, validation 1/2 | rejected | 0/3 | 171 | 287 | 982 | [report](docs/strategy_research_200_reports/SR2-056.md) |
| SR2-057 | 2026-10-31 | PA-09 / trend_alignment / persistent_context | full, recent, training, validation 1/2 | rejected | 0/3 | 0 | 288 | 983 | [report](docs/strategy_research_200_reports/SR2-057.md) |
| SR2-058 | 2026-10-31 | PA-09 / candle_confirmation / pullback_confirmation | full, recent, training, validation 1/2 | rejected | 0/3 | 1 | 289 | 984 | [report](docs/strategy_research_200_reports/SR2-058.md) |
| SR2-059 | 2026-10-31 | PA-10 / trend_alignment / failure_reversal | full, recent, training, validation 1/2 | rejected | 0/3 | 924 | 290 | 985 | [report](docs/strategy_research_200_reports/SR2-059.md) |
| SR2-060 | 2026-10-31 | PA-10 / candle_confirmation / failure_reversal | full, recent, training, validation 1/2 | rejected | 0/3 | 386 | 291 | 986 | [report](docs/strategy_research_200_reports/SR2-060.md) |
| SR2-061 | 2026-10-31 | PS-01 / trend_alignment / failure_reversal | full, recent, training, validation 1/2 | rejected | 0/3 | 668 | 292 | 987 | [report](docs/strategy_research_200_reports/SR2-061.md) |
| SR2-062 | 2026-10-31 | PS-01 / candle_confirmation / persistent_context | full, recent, training, validation 1/2 | rejected | 0/3 | 45 | 293 | 988 | [report](docs/strategy_research_200_reports/SR2-062.md) |
| SR2-063 | 2026-10-31 | PS-02 / trend_alignment / failure_reversal | full, recent, training, validation 1/2 | rejected | 0/3 | 630 | 294 | 989 | [report](docs/strategy_research_200_reports/SR2-063.md) |
| SR2-064 | 2026-10-31 | PS-02 / candle_confirmation / failure_reversal | full, recent, training, validation 1/2 | rejected | 0/3 | 294 | 295 | 990 | [report](docs/strategy_research_200_reports/SR2-064.md) |
| SR2-065 | 2026-10-31 | PS-03 / trend_alignment / persistent_context | full, recent, training, validation 1/2 | rejected | 0/3 | 27 | 296 | 991 | [report](docs/strategy_research_200_reports/SR2-065.md) |
| SR2-066 | 2026-10-31 | PS-03 / candle_confirmation / persistent_context | full, recent, training, validation 1/2 | rejected | 0/3 | 10 | 297 | 992 | [report](docs/strategy_research_200_reports/SR2-066.md) |
| SR2-067 | 2026-10-31 | PS-04 / trend_alignment / persistent_context | full, recent, training, validation 1/2 | rejected | 0/3 | 56 | 298 | 993 | [report](docs/strategy_research_200_reports/SR2-067.md) |
| SR2-068 | 2026-10-31 | PS-04 / candle_confirmation / failure_reversal | full, recent, training, validation 1/2 | rejected | 0/3 | 182 | 299 | 994 | [report](docs/strategy_research_200_reports/SR2-068.md) |
| SR2-069 | 2026-10-31 | PS-05 / trend_alignment / failure_reversal | full, recent, training, validation 1/2 | rejected | 0/3 | 419 | 300 | 995 | [report](docs/strategy_research_200_reports/SR2-069.md) |
| SR2-070 | 2026-10-31 | PS-05 / candle_confirmation / persistent_context | full, recent, training, validation 1/2 | rejected | 0/3 | 1 | 301 | 996 | [report](docs/strategy_research_200_reports/SR2-070.md) |
| SR2-071 | 2026-10-31 | PS-06 / trend_alignment / persistent_context | full, recent, training, validation 1/2 | rejected | 0/3 | 16 | 302 | 997 | [report](docs/strategy_research_200_reports/SR2-071.md) |
| SR2-072 | 2026-10-31 | PS-06 / candle_confirmation / failure_reversal | full, recent, training, validation 1/2 | rejected | 0/3 | 130 | 303 | 998 | [report](docs/strategy_research_200_reports/SR2-072.md) |
| SR2-073 | 2026-10-31 | PS-07 / trend_alignment / failure_reversal | full, recent, training, validation 1/2 | rejected | 0/3 | 669 | 304 | 999 | [report](docs/strategy_research_200_reports/SR2-073.md) |
| SR2-074 | 2026-10-31 | PS-07 / candle_confirmation / failure_reversal | full, recent, training, validation 1/2 | rejected | 0/3 | 160 | 305 | 1000 | [report](docs/strategy_research_200_reports/SR2-074.md) |
| SR2-075 | 2026-10-31 | PS-08 / trend_alignment / failure_reversal | full, recent, training, validation 1/2 | rejected | 0/3 | 554 | 306 | 1001 | [report](docs/strategy_research_200_reports/SR2-075.md) |
| SR2-076 | 2026-10-31 | PS-08 / candle_confirmation / failure_reversal | full, recent, training, validation 1/2 | rejected | 0/3 | 55 | 307 | 1002 | [report](docs/strategy_research_200_reports/SR2-076.md) |
| SR2-077 | 2026-10-31 | PS-09 / trend_alignment / failure_reversal | full, recent, training, validation 1/2 | rejected | 0/3 | 342 | 308 | 1003 | [report](docs/strategy_research_200_reports/SR2-077.md) |
| SR2-078 | 2026-10-31 | PS-09 / candle_confirmation / failure_reversal | full, recent, training, validation 1/2 | rejected | 0/3 | 85 | 309 | 1004 | [report](docs/strategy_research_200_reports/SR2-078.md) |
| SR2-079 | 2026-10-31 | PS-10 / trend_alignment / persistent_context | full, recent, training, validation 1/2 | rejected | 0/3 | 40 | 310 | 1005 | [report](docs/strategy_research_200_reports/SR2-079.md) |
| SR2-080 | 2026-10-31 | PS-10 / candle_confirmation / failure_reversal | full, recent, training, validation 1/2 | rejected | 0/3 | 293 | 311 | 1006 | [report](docs/strategy_research_200_reports/SR2-080.md) |
| SR2-081 | 2026-10-31 | TR-01 / trend_alignment / failure_reversal | full, recent, training, validation 1/2 | rejected | 0/3 | 969 | 312 | 1007 | [report](docs/strategy_research_200_reports/SR2-081.md) |
| SR2-082 | 2026-10-31 | TR-01 / candle_confirmation / persistent_context | full, recent, training, validation 1/2 | rejected | 0/3 | 248 | 313 | 1008 | [report](docs/strategy_research_200_reports/SR2-082.md) |
| SR2-083 | 2026-10-31 | TR-02 / trend_alignment / persistent_context | full, recent, training, validation 1/2 | rejected | 0/3 | 882 | 314 | 1009 | [report](docs/strategy_research_200_reports/SR2-083.md) |
| SR2-084 | 2026-10-31 | TR-02 / candle_confirmation / pullback_confirmation | full, recent, training, validation 1/2 | rejected | 0/3 | 252 | 315 | 1010 | [report](docs/strategy_research_200_reports/SR2-084.md) |
| SR2-085 | 2026-10-31 | TR-03 / trend_alignment / pullback_confirmation | full, recent, training, validation 1/2 | rejected | 0/3 | 267 | 316 | 1011 | [report](docs/strategy_research_200_reports/SR2-085.md) |
| SR2-086 | 2026-10-31 | TR-03 / candle_confirmation / pullback_confirmation | full, recent, training, validation 1/2 | rejected | 0/3 | 264 | 317 | 1012 | [report](docs/strategy_research_200_reports/SR2-086.md) |
| SR2-087 | 2026-10-31 | TR-04 / trend_alignment / failure_reversal | full, recent, training, validation 1/2 | rejected | 0/3 | 947 | 318 | 1013 | [report](docs/strategy_research_200_reports/SR2-087.md) |
| SR2-088 | 2026-10-31 | TR-04 / candle_confirmation / persistent_context | full, recent, training, validation 1/2 | rejected | 0/3 | 325 | 319 | 1014 | [report](docs/strategy_research_200_reports/SR2-088.md) |
| SR2-089 | 2026-10-31 | TR-05 / trend_alignment / persistent_context | full, recent, training, validation 1/2 | rejected | 0/3 | 88 | 320 | 1015 | [report](docs/strategy_research_200_reports/SR2-089.md) |
| SR2-090 | 2026-10-31 | TR-05 / candle_confirmation / persistent_context | full, recent, training, validation 1/2 | rejected | 0/3 | 133 | 321 | 1016 | [report](docs/strategy_research_200_reports/SR2-090.md) |
| SR2-091 | 2026-10-31 | TR-06 / trend_alignment / persistent_context | full, recent, training, validation 1/2 | rejected | 0/3 | 13 | 322 | 1017 | [report](docs/strategy_research_200_reports/SR2-091.md) |
| SR2-092 | 2026-10-31 | TR-06 / candle_confirmation / failure_reversal | full, recent, training, validation 1/2 | rejected | 0/3 | 62 | 323 | 1018 | [report](docs/strategy_research_200_reports/SR2-092.md) |
| SR2-093 | 2026-10-31 | TR-07 / trend_alignment / failure_reversal | full, recent, training, validation 1/2 | rejected | 0/3 | 740 | 324 | 1019 | [report](docs/strategy_research_200_reports/SR2-093.md) |
| SR2-094 | 2026-10-31 | TR-07 / candle_confirmation / persistent_context | full, recent, training, validation 1/2 | rejected | 0/3 | 218 | 325 | 1020 | [report](docs/strategy_research_200_reports/SR2-094.md) |
| SR2-095 | 2026-10-31 | TR-08 / trend_alignment / persistent_context | full, recent, training, validation 1/2 | rejected | 0/3 | 59 | 326 | 1021 | [report](docs/strategy_research_200_reports/SR2-095.md) |
| SR2-096 | 2026-10-31 | TR-08 / candle_confirmation / failure_reversal | full, recent, training, validation 1/2 | rejected | 0/3 | 277 | 327 | 1022 | [report](docs/strategy_research_200_reports/SR2-096.md) |
| SR2-097 | 2026-10-31 | TR-09 / trend_alignment / persistent_context | full, recent, training, validation 1/2 | rejected | 0/3 | 290 | 328 | 1023 | [report](docs/strategy_research_200_reports/SR2-097.md) |
| SR2-098 | 2026-10-31 | TR-09 / candle_confirmation / pullback_confirmation | full, recent, training, validation 1/2 | rejected | 0/3 | 270 | 329 | 1024 | [report](docs/strategy_research_200_reports/SR2-098.md) |
| SR2-099 | 2026-10-31 | TR-10 / trend_alignment / persistent_context | full, recent, training, validation 1/2 | rejected | 0/3 | 772 | 330 | 1025 | [report](docs/strategy_research_200_reports/SR2-099.md) |
| SR2-100 | 2026-10-31 | TR-10 / candle_confirmation / persistent_context | full, recent, training, validation 1/2 | rejected | 0/3 | 15 | 331 | 1026 | [report](docs/strategy_research_200_reports/SR2-100.md) |
