# Indicator catalogue (moneta)

Source of truth: `config/indicators.yml`. This document explains conventions and how to add indicators.

## Conventions

- Timezone: UTC. Bars come from `data/ohlcv_5m/` and `data/ohlcv_1h/`.
- `lookback`: minimum number of bars required for a valid value; earlier bars are NaN (warm-up).
- One output column per `output`; multi-output indicators list several (`outputs`).
- Indicator type: `trend | momentum | volatility | volume`.
- Params: units are in *bars of the target timeframe* (e.g. `window: 20` on 5m means 20 five-minute bars ≈ 100 minutes).
- Inputs reference OHLCV columns: `open, high, low, close, volume, n_bars, time, instrument`.

## Implemented indicator families

### Trend
- `ema_fast` (EMA 9), `ema_slow` (EMA 21), `ema_trend` (EMA 50), `sma_200`
- `macd` (12/26/9) → macd, macd_signal, macd_hist
- `adx` (14) → adx, plus_di, minus_di

### Momentum
- `rsi` (14), `stoch` (14/3/3), `cci` (20), `roc` (10)

### Volatility
- `atr` (14), `bollinger` (20, 2σ), `keltner` (20 EMA, 14 ATR, 2×)

### Volume / microstructure
- `obv`, `vwap` (cumulative per UTC day), `volume_sma` (20)

## Adding a new indicator

1. Add an entry under `timeframes.<tf>.indicators` in `config/indicators.yml` with `name, type, inputs, params, output(s), lookback`.
2. Implement the computation (prefer vectorised, closed-form or numba) in `pipeline/indicators.py`.
3. Add a unit test (parity against pandas-ta or ta-lib where available).
4. Update this doc.

## Future (Gold layer)

Multi-timeframe join: attach 1h trend context to 5m bars via as-of join on UTC time (last fully closed 1h bar), avoiding look-ahead.
