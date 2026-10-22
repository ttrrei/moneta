# Indicator Spec (moneta / Nova)

Scope: OANDA CFDs only (FX, metals, crude, equity indices, crypto). Bars are 1-minute mid-price candles aggregated into **5m** and **1h** OHLCV (UTC). Strategies are designed **per instrument**.

This document defines **which indicators to build** and the rules every indicator follows. The old indicator files are discarded; nothing from them is carried over.

- **Batch 1:** the common, widely used indicators, in their usual form (price-level or bounded, as published).
- **Batch 2:** second-level and less common indicators: ratios of Batch 1 outputs (e.g. EMA divided by ATR), candle structure, time features, and 1h context attached to 5m.

---

## 1. Data facts that affect indicator definitions

- Bar `time` is the interval **start** (UTC). A 5m bar with `time = 00:55` closes at 01:00.
- Only mid prices are aggregated. Spread features are out of scope.
- `volume` is OANDA **tick volume** (number of price updates), not traded volume. Volume-based indicators are therefore activity proxies.
- Each bar has `n_bars` (1m rows in the bucket), so partial bars can be flagged.
- Data is sparse: minutes with no quotes have no row. Windows count **rows**, not clock time, so they span weekends and index session breaks.

---

## 2. Rules for every indicator

### 2.1 Parameter grid

Window parameters come only from **`6 / 12 / 24 / 60`** (bars of the target timeframe):

| Window | on 5m | on 1h |
|---|---|---|
| 6 | 30 min | 6 h |
| 12 | 1 h | 12 h |
| 24 | 2 h | 1 day (FX) |
| 60 | 5 h | 2.5 days |

- Single-window indicators are built for all four values.
- Two-window indicators use only the pairs **(6, 24)** and **(12, 60)**.
- Any secondary window inside an indicator also comes from the grid (e.g. the Stochastic %D smoothing is 6).
- Non-window constants are fixed: Bollinger σ = `2.0`, Keltner multiplier = `2.0`, CCI constant = `0.015`, and the ATR window used to scale price distances in Batch 2 is `NORM_ATR = 24`.

### 2.2 No look-ahead

- A feature computed on bar `T` is usable only after that bar closes (`T + period`). Signals fill on the **next** bar's open.
- Use only rows `≤` the current row. No `shift(-k)`, no full-sample mean/std/quantile. Any standardisation uses a rolling or expanding window.
- 1h features are attached to 5m bars with an as-of join on **close time**: a 5m bar may only see 1h bars that have already closed.

```sql
-- add close_time to both tables first: time + INTERVAL '5 minutes' / '1 hour'
SELECT m.*, h.ema_dist_24 AS h1_ema_dist_24
FROM m5 m
ASOF LEFT JOIN h1 h
  ON m.instrument = h.instrument
 AND m.close_time >= h.close_time;
```

Example: the 5m bar `00:55–01:00` may use the 1h bar `00:00` (closed at 01:00). The 5m bar `01:00–01:05` still sees the `00:00` bar, because the 1h bar starting at 01:00 closes at 02:00. Do **not** join on `m.time >= h.time`.

### 2.3 Warm-up

The first rows of every indicator are `NaN`:

- Rolling windows (`rolling(n)`, `shift(n)`): first `n` rows.
- Recursive smoothing (EMA, Wilder ATR/RSI/ADX, MACD): first `3 × n` rows (for MACD, `3 × slow`), so that backfilling older history does not change today's values.

### 2.4 Which kind of column to use in a rule

- Batch 1 indicators are in their usual units. Comparing **price against a price-level indicator** (`close > ema_24`, `close < bb_lower_24`) or sizing a stop with `atr_24` works directly.
- Comparing an indicator against a **constant threshold** is different: price level and volatility regime drift over years, so `atr_24 > 5.0` means something different in each walk-forward window. For constant thresholds use bounded oscillators (`rsi`, `stoch_k`, `adx`, `bb_pctb`) or the scale-free Batch 2 versions (`atr_pct`, `ema_dist`).

### 2.5 Gaps and partial bars

- Do not drop or fill rows at gaps; windows run over rows.
- Keep two flag columns alongside the features so downstream code can exclude affected samples: `is_partial` (`n_bars` below a full bar: <5 on 5m, <60 on 1h) and `gap_before` (time since the previous row is more than one bar).

### 2.6 Naming

```
{name}_{n}                 ema_24, rsi_12, atr_6
{name}_{field}_{n}         bb_upper_24, stoch_k_12
{name}_{fast}_{slow}       macd_hist_6_24
h1_{name}_{n}              1h feature attached to 5m
no-parameter features      tr, vwap, hour_sin
```

Lowercase with underscores. The same indicator has the same column name in the 5m and 1h tables.

---

## 3. Batch 1: common indicators

All computed on both **5m and 1h**. `n` ∈ {6, 12, 24, 60} unless stated.

### Trend

| Indicator | Output columns | Definition |
|---|---|---|
| Simple moving average | `sma_{n}` | SMA of close |
| Exponential moving average | `ema_{n}` | EMA of close, `span = n`, `adjust=False` |
| MACD | `macd_{f}_{s}`, `macd_signal_{f}_{s}`, `macd_hist_{f}_{s}` | `macd = EMA_f − EMA_s`; `signal = EMA(macd, span = f)`; `hist = macd − signal`. Pairs (6,24), (12,60). *Signal window = the fast window is my choice; change it if you prefer another grid value.* |
| ADX / DI | `adx_{n}`, `plus_di_{n}`, `minus_di_{n}` | Wilder ADX and ±DI, 0–100 |
| Aroon | `aroon_up_{n}`, `aroon_down_{n}` | Standard Aroon with period n, 0–100 |
| Donchian channel | `dc_upper_{n}`, `dc_lower_{n}`, `dc_mid_{n}` | Highest high / lowest low of the last n bars **including the current bar**; mid is their average |

Note on Donchian: the current bar's own channel always contains its close, so a breakout rule compares `close` with the **previous** bar's `dc_upper` / `dc_lower`.

### Momentum / oscillators

| Indicator | Output columns | Definition |
|---|---|---|
| RSI | `rsi_{n}` | Wilder RSI, 0–100 |
| Rate of change | `roc_{n}` | `100 × (close_t / close_{t−n} − 1)` |
| Momentum | `mom_{n}` | `close_t − close_{t−n}` (price units) |
| Stochastic | `stoch_k_{n}`, `stoch_d_{n}` | `%K = 100 × (close − LL_n) / (HH_n − LL_n)`; `%D = SMA(%K, 6)` |
| CCI | `cci_{n}` | `(TP − SMA_n(TP)) / (0.015 × mean absolute deviation_n(TP))`, `TP = (high + low + close) / 3` |

### Volatility

| Indicator | Output columns | Definition |
|---|---|---|
| True range | `tr` | `max(high − low, abs(high − prev_close), abs(low − prev_close))` |
| ATR | `atr_{n}` | Wilder ATR (price units) |
| Bollinger Bands | `bb_mid_{n}`, `bb_upper_{n}`, `bb_lower_{n}`, `bb_width_{n}`, `bb_pctb_{n}` | SMA(close, n) ± 2.0 × sample std; `width = (upper − lower) / mid`; `%B = (close − lower) / (upper − lower)` |
| Keltner Channel | `kc_mid_{n}`, `kc_upper_{n}`, `kc_lower_{n}` | `EMA_n(close) ± 2.0 × ATR_n` |
| Historical volatility | `hv_{n}` | Sample std of 1-bar log returns over the last n bars |

### Volume (tick volume)

| Indicator | Output columns | Definition |
|---|---|---|
| Volume SMA | `vol_sma_{n}` | SMA of tick volume |
| VWAP | `vwap` | Cumulative `typical price × volume / volume`, **reset at 00:00 UTC** (no parameter) |
| Money Flow Index | `mfi_{n}` | Standard MFI on typical price × tick volume, 0–100 |
| Chaikin Money Flow | `cmf_{n}` | `Σ(CLV × volume, n) / Σ(volume, n)`, `CLV = ((close − low) − (high − close)) / (high − low)`, −1 to 1 |

---

## 4. Batch 2: second-level and less common indicators

`NORM_ATR = 24`. TF "both" means 5m and 1h.

| Indicator | Definition | Parameters | TF | What it captures |
|---|---|---|---|---|
| `ema_dist_{n}` | `(close − ema_n) / atr_24` | n ∈ grid | both | Stretch from the trend line in ATR units |
| `ema_spread_{f}_{s}` | `(ema_f − ema_s) / atr_24` (the MACD line in ATR units) | (6,24), (12,60) | both | Trend strength from two averages, comparable over time |
| `macd_hist_atr_{f}_{s}` | `macd_hist_{f}_{s} / atr_24` | (6,24), (12,60) | both | Momentum change in ATR units |
| `atr_pct_{n}` | `atr_n / close` | n ∈ grid | both | Volatility level relative to price |
| `vol_ratio_{a}_{b}` | `atr_pct_a / atr_pct_b` | (6,24), (12,60) | both | Volatility expansion / contraction |
| `er_{n}` | Kaufman efficiency ratio: `abs(close_t − close_{t−n}) / Σ abs(close_i − close_{i−1})` over the last n bars, 0–1 | n ∈ grid | both | Trending (near 1) vs choppy (near 0) |
| `vol_rel_{n}` | `volume / vol_sma_n` | n ∈ grid | both | Relative tick-volume activity |
| `body_ratio` | `abs(close − open) / (high − low)` | none | both | Candle conviction |
| `upper_wick`, `lower_wick` | `(high − max(open, close)) / (high − low)`; `(min(open, close) − low) / (high − low)` | none | both | Rejection at highs / lows |
| `clv` | `((close − low) − (high − close)) / (high − low)`, −1 to 1 | none | both | Where the bar closed within its range |
| `hour_sin`, `hour_cos` | `sin / cos(2π · (hour + minute/60) / 24)` of the bar start time, UTC | none | 5m | Time-of-day effects (CFDs are very session-sensitive) |
| `dow` | Day of week of the bar start time, UTC (Mon = 0) | none | 5m | Day-of-week effects |
| `h1_ema_dist_{n}`, `h1_adx_{n}`, `h1_rsi_{n}`, `h1_er_{n}`, `h1_atr_pct_{n}` | The 1h indicator of the same name, attached to 5m with the as-of join in §2.2 | n ∈ grid | 5m | 1h trend / volatility context for 5m entries |

Notes:

- Bars with `high = low` give `NaN` for the candle-structure columns (zero range).
- If London / New York session flags are added later, derive them from **local time** (`Europe/London`, `America/New_York`), not fixed UTC hours, so daylight-saving changes do not shift them.

---

## 5. Not in this list, on purpose

- `obv`: it is cumulative, so every value shifts with the length of history. A rolling-window version can be added if wanted.
- SuperTrend and Parabolic SAR: their flip state depends on where the series starts.
- Ichimoku: its standard periods (9/26/52) are not on the grid.
- Williams %R: it equals `stoch_k − 100`.
- Spread features, cross-instrument features, and anything that depends on trade state (bars held, unrealised PnL, MFE/MAE), which belongs to the exit logic.

---

## 6. Acceptance checks for each indicator

1. **No look-ahead (truncation test):** values computed from the first `k` rows equal the first `k` rows of values computed from the full data.
2. **Warm-up:** the first `n` (or `3n`) rows are `NaN`, and every row after is not.
3. **Start-independence:** dropping the oldest rows (simulating a shorter history) leaves values after warm-up essentially unchanged.
4. **Hypothesis:** for Batch 2, the "What it captures" sentence is the hypothesis. Any indicator added later needs one.
5. **Trial count:** Batch 1 is roughly 130 output columns per timeframe. Count trials by (indicator, parameters, timeframe), not by output column; `bb_upper_24` and `bb_pctb_24` are one trial.
