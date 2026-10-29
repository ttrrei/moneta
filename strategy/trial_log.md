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
| 18 | 2026-11-01 | S-18 | VWAP-stretch reversion: enter when (close−vwap)/atr up-crosses > k, exit below k_exit (6-variant: base/ema_gate/looser/tight_exit/1h/entry_guard) | full | **rejected** | best `1h` mean edge **+24%** @2bps is BTC-only (full +459 on BTC, −70/−146 on EUR/XAU; last_12m 0/3) — single-instrument fit, not cross-market; 5m variants 441–2,112 tpy (cost × frequency) | 17 |
| 19 | 2026-11-01 | S-19 | CMF-24 accumulation follower: cmf_24 up-cross > k, exit below 0 (6-variant incl. tighter/looser) | full | **rejected** | best `1h` mean edge −121%; 5m variants 140–2,850 tpy (cost × frequency); no variant beat BH on ≥2/3 instruments | 18 |
| 20 | 2026-11-01 | S-20 | Multi-scale SuperTrend alignment: short ST up-flip gated by long-scale ST (6-variant incl. `h1_st_dir_120_3` HTF gate) | full | **rejected** | best `1h` mean edge −162%; 5m variants 127–1,543 tpy; gating (dual/HTF) cuts trades but no cross-market edge | 19 |
| 21 | 2026-11-01 | S-21 | Slow 60-bar squeeze regime: long while sqz_on_60 on + close>bb_mid_60 (6-variant incl. onset_only) | full | **rejected** | best `1h` mean edge −253%; fewest trades of batch (1h ~15/yr) yet most negative — selective long-only rule sits in the EUR/XAU drawdown | 20 |
| 22 | 2026-11-01 | S-22 | Efficiency-ratio regime: long while er_24 > k and close > ema_24 (6-variant k-sweep 0.20–0.50) | full | **rejected** | best `1h` mean edge −224%; 5m variants 173–3,039 tpy (cost × frequency); no variant beat BH on ≥2/3 instruments | 21 |
| 23 | 2026-11-01 | S-23 | Slow ATR-normalised MACD: long while macd_hist_atr_24_120 > th (6-variant incl. hysteresis) | full | **rejected** | best `1h` mean edge −130%; 5m variants 88–1,075 tpy; hysteresis/pos_th reduce trades without a cross-market edge | 22 |
| 24 | 2026-11-01 | S-24 | ATR-band breakout: long while (close−ema)/atr ≥ k, exit < k_exit (6-variant band 0.5–1.5) | full | **rejected** | best `1h` mean edge −138%; 5m variants 183–3,501 tpy (cost × frequency); no variant beat BH on ≥2/3 instruments | 23 |
| 25 | 2026-11-01 | S-25 | Chop-regime mean-reversion: stretched-below-ema while chop_24 > chop_at (6-variant chop_at 55–65) | full | **rejected** | best `1h` mean edge −254%; low-frequency (1h ~19/yr) but long-only in down-trending EUR/XAU; no variant beat BH on ≥2/3 instruments | 24 |
| 26 | 2026-11-01 | S-26 | EMA-12/60-spread follower: spread up-cross > th, hysteresis exit (6-variant incl. hysteresis) | full | **rejected** | best `1h` mean edge −170%; 5m variants 49–685 tpy; same cost×frequency signature as S-06 (EMA-spread family) | 25 |
| 27 | 2026-11-01 | S-27 | Volume-confirmed momentum: mom_24 > 0 and vol_rel_24 ≥ vmin (6-variant vol 0.8–2.0) | full | **rejected** | best `1h` mean edge −230%; 5m variants 195–2,976 tpy (cost × frequency); volume gate reduces trades without a cross-market edge | 26 |

<!--
Append a new row for every attempt. Keep `n_tried_before` = (previous max #) so
the running count is always the true number of strategies tried so far.
Example next row:
| 2 | 2026-11-02 | S-02 | same RSI rule on 1h bars (1/12 the cost) | full | <outcome> | <ret vs BH> | 1 |
-->
