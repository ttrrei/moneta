# Pre-registered strategy batch: S-113–S-132

Design is recorded before implementation and evaluation. The batch uses one
fixed rule per ID—no post-result threshold tuning. All signals are computed
from closed bars and are filled by the shared engine at the next bar's open.
The evaluation is in-sample only (`full` and `last_12m`; 0/2/5 bps); the OOS
holdout is not read or reserved.

The expected trade-count ranges below are design estimates, not measured
results. The feature column list is checked against the selected Parquet
schema before implementation.

| ID | Name | TF | Key features | Fixed entry/exit concept | Hypothesis | Expected full-history trades |
|---|---|---|---|---|---|---:|
| S-113 | 1h Aroon direction with ADX regime | 1h | `aroon_up_24`, `aroon_down_24`, `adx_24` | Directional Aroon cross with ADX > 20; exit on reverse cross | Aroon direction changes may persist longer when 1h ADX confirms a directional regime. | 20–180 |
| S-114 | Higher-timeframe trend pullback | 5m | `ema_dist_24`, `h1_ema_dist_24` | Recover through −0.5 / +0.5 ATR-distance threshold only in matching 1h trend; exit through zero | A 5m pullback recovery aligned with closed 1h direction may avoid counter-trend entries. | 20–220 |
| S-115 | Higher-timeframe-gated channel break | 5m | `dist_high_24`, `dist_low_24`, `h1_adx_24`, `dc_pos_24` | Prior-extreme break with 1h ADX > 20; exit at channel midpoint | Extreme breaks may persist when the closed 1h regime confirms trend strength. | 10–160 |
| S-116 | Squeeze release with close-location direction | 5m | `sqz_on_24`, `bar_clv`, `h1_ema_dist_24` | Compression release plus strong close-location aligned with 1h direction | Close-location and higher-timeframe alignment may filter weak squeeze releases. | 10–160 |
| S-117 | Low-trend VWAP reclaim | 5m | `vwap`, `h1_adx_24` | VWAP cross only while 1h ADX < 20; exit on reverse VWAP cross | VWAP crossings may mean-revert better when 1h trend strength is weak. | 30–240 |
| S-118 | Band re-entry in a choppy regime | 5m | `bb_pctb_24`, `chop_24`, `h1_adx_24` | Re-enter from the outer 5% of the band when local chop is high and 1h ADX is low; exit at midpoint | A return inside the band may mean-revert when both regimes are non-trending. | 20–180 |
| S-119 | 60-bar prior-extreme breakout | 5m | `dist_high_60`, `dist_low_60`, `h1_ema_dist_24` | Prior-extreme break in matching 1h direction; exit on recross of the broken extreme | A 60-bar extreme break may continue when the 1h EMA context agrees. | 10–140 |
| S-120 | Directional-movement cross with ADX filter | 5m | `plus_di_60`, `minus_di_60`, `adx_60` | 60-bar DI cross with ADX > 20; exit on reverse cross | Slow directional-movement changes may reduce false starts when trend strength is established. | 10–160 |
| S-121 | 1h MACD momentum in efficient regimes | 1h | `macd_hist_atr_12_60`, `er_24` | Normalized MACD zero-cross with ER > 0.25; exit on reverse cross | A normalized 1h momentum cross may persist when the path is directionally efficient. | 10–140 |
| S-122 | PSAR reversal aligned with 1h trend | 5m | `psar_dir_0p01_0p1`, `h1_st_dir_24_3` | Slow PSAR flip only in the same 1h SuperTrend direction; exit on PSAR flip | Higher-timeframe alignment may make PSAR reversals more selective. | 15–160 |
| S-123 | Wick rejection at Bollinger extremes | 5m | `bar_lower_wick_ratio`, `bar_upper_wick_ratio`, `bar_clv`, `bb_pctb_60` | Rejection wick plus close-location at an outer 60-bar band; exit at midpoint | A rejection candle at an extended band location may identify failed moves. | 10–120 |
| S-124 | Squeeze release with activity-confirmed break | 5m | `sqz_on_60`, `dist_high_60`, `dist_low_60`, `vol_rel_60`, `dc_pos_60` | 60-bar release, activity > 1.2, and prior-extreme break; exit at midpoint | Compression breaks accompanied by elevated tick activity may avoid low-energy false breaks. | 5–100 |
| S-125 | ATR-normalized EMA trend with 1h SuperTrend | 5m | `ema_dist_60`, `h1_st_dir_120_3` | Slow EMA-distance zero-cross only in matching 1h SuperTrend direction; exit on zero-cross | Slow normalized trend changes may carry when the 1h regime agrees. | 10–130 |
| S-126 | ATR expansion plus prior-extreme breakout | 5m | `atr_pct_24`, `atr_pct_60`, `dist_high_24`, `dist_low_24`, `dc_pos_24` | Local ATR-percent expansion relative to its slower baseline plus prior-extreme break | Relative volatility expansion may confirm a channel break. | 5–120 |
| S-127 | Money-flow zero-cross with 1h trend alignment | 5m | `cmf_12`, `h1_ema_dist_24` | CMF zero-cross only with matching 1h EMA direction; exit on reverse flow cross | Shorter money-flow changes may be useful only when closed 1h price trend agrees. | 10–150 |
| S-128 | VWAP reclaim in strong 1h trend | 5m | `vwap`, `h1_adx_24`, `h1_ema_dist_24` | VWAP cross with ADX > 25 and matching 1h direction; exit on reverse VWAP cross | Session VWAP reclaim may be trend resumption in a strong, aligned 1h regime. | 10–120 |
| S-129 | 1h SuperTrend with 5m 120-bar breakout | 5m | `h1_st_dir_24_3`, `dist_high_120`, `dist_low_120`, `dc_pos_120` | 120-bar prior-extreme breakout gated by 1h SuperTrend; exit at channel midpoint | A long-window 5m extreme break may persist when the closed 1h SuperTrend agrees. | 10–120 |
| S-130 | 1h channel-position break in efficient trend | 1h | `dc_pos_60`, `er_60` | 60-bar channel-position cross beyond 0.8/0.2 with ER > 0.3; exit at midpoint | A channel break may be more persistent when 1h path efficiency is high. | 5–100 |
| S-131 | Close-location impulse with tick-activity confirmation | 5m | `bar_clv`, `vol_rel_6`, `h1_adx_24` | Strong close-location plus activity > 1.2 and 1h ADX > 20; exit on CLV sign reversal | Directional closes with elevated activity may indicate an impulse in an established regime. | 10–160 |
| S-132 | Band-width expansion aligned with 1h trend | 5m | `bb_width_12`, `bb_width_60`, `h1_ema_dist_24`, `dc_pos_24` | Short-vs-slow width cross with channel location and matching 1h direction; exit at midpoint | Relative band-width expansion may mark a phase change when price location and 1h trend agree. | 10–150 |

## Design and evaluation rules

- Every row is a different indicator combination and entry mechanism; none is a
  parameter-only retune of a rejected strategy.
- Feature windows remain on the configured grid `{6, 12, 24, 60, 120}`.
- Tick-volume fields are activity proxies, not exchange volume.
- No strategy is promoted to `finalist` or run on OOS by this batch. If a
  config clears the in-sample bar, it remains a human nomination decision.
- Each attempt is recorded with its measured outcome and a report containing
  all 18 instrument/window/cost cells. Rejections are retained in the registry
  and rejected-combinations table.
