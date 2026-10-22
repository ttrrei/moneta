"""Compute technical indicators on the OHLCV bars (Silver/Gold feature layer).

Implements the Indicator Spec (moneta / Nova). The previous catalogue-driven
implementation is discarded; indicators are defined entirely by docs/indicators.md.

Usage:
    python -m pipeline.indicators            # builds both 5m and 1h features
    python -m pipeline.indicators --tf 5m    # one timeframe only
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq


N_GRID = [6, 12, 24, 60]
PAIRS = [(6, 24), (12, 60)]
NORM_ATR = 24


# ---------------------------------------------------------------------------
# Batch 1 helpers
# ---------------------------------------------------------------------------


def _mask(s: pd.Series, n: int) -> pd.Series:
    """Set the first ``n`` entries of *s* to NaN (warm-up)."""
    s = s.copy()
    k = min(n, len(s))
    s.iloc[:k] = np.nan
    return s


def _ema(series: pd.Series, span: int) -> pd.Series:
    """EMA with span, adjust=False; first 3*span rows masked as warm-up."""
    s = series.ewm(span=span, adjust=False).mean()
    return _mask(s, 3 * span)


def _sma(series: pd.Series, window: int) -> pd.Series:
    s = series.rolling(window=window, min_periods=window).mean()
    return _mask(s, window)


def _rsi(series: pd.Series, window: int) -> pd.Series:
    """Wilder's RSI."""
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    avg_gain = gain.ewm(alpha=1 / window, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / window, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return _mask(rsi, 3 * window)


def _atr(high: pd.Series, low: pd.Series, close: pd.Series, window: int) -> pd.Series:
    """Wilder's ATR."""
    prev_close = close.shift(1)
    tr = pd.concat(
        [
            (high - low),
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    atr = tr.ewm(alpha=1 / window, adjust=False).mean()
    return _mask(atr, 3 * window)


def _macd(close: pd.Series, fast: int, slow: int):
    """MACD line / signal / hist. Signal span = fast. First 3*slow rows NaN."""
    macd_line = _ema(close, fast) - _ema(close, slow)
    signal_line = _ema(macd_line, fast)
    hist = macd_line - signal_line
    warm = 3 * slow
    return _mask(macd_line, warm), _mask(signal_line, warm), _mask(hist, warm)


def _adx(high, low, close, n):
    """Wilder ADX and +/-DI."""
    prev_close = close.shift(1)
    tr = pd.concat(
        [
            (high - low),
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)

    up_move = high.diff()
    down_move = (-low.diff())

    plus_dm = up_move.where((up_move > down_move) & (up_move > 0), 0.0)
    minus_dm = down_move.where((down_move > up_move) & (down_move > 0), 0.0)

    tr_smooth = tr.ewm(alpha=1 / n, adjust=False).mean()
    plus_smooth = plus_dm.ewm(alpha=1 / n, adjust=False).mean()
    minus_smooth = minus_dm.ewm(alpha=1 / n, adjust=False).mean()

    dx = 100 * (plus_smooth - minus_smooth).abs() / (plus_smooth + minus_smooth).replace(
        0, np.nan
    )
    adx = dx.ewm(alpha=1 / n, adjust=False).mean()
    plus_di = 100 * plus_smooth / tr_smooth.replace(0, np.nan)
    minus_di = 100 * minus_smooth / tr_smooth.replace(0, np.nan)

    warm = 3 * n
    return _mask(adx, warm), _mask(plus_di, warm), _mask(minus_di, warm)


def _aroon(high, low, n):
    """Standard Aroon, 0-100."""

    def _up(x):
        last_idx = len(x) - 1 - np.argmax(x[::-1])
        return 100.0 * last_idx / n

    def _down(x):
        last_idx = len(x) - 1 - np.argmax(-x[::-1])
        return 100.0 * last_idx / n

    up = high.rolling(window=n + 1, min_periods=n + 1).apply(_up, raw=True)
    down = low.rolling(window=n + 1, min_periods=n + 1).apply(_down, raw=True)
    # first n rows are NaN by construction (min_periods=n+1 gives first valid at n)
    return up, down


def _donchian(high, low, n):
    upper = high.rolling(window=n, min_periods=n).max()
    lower = low.rolling(window=n, min_periods=n).min()
    mid = (upper + lower) / 2.0
    return _mask(upper, n), _mask(lower, n), _mask(mid, n)


def _stochastic(high, low, close, n, smooth=6):
    ll = low.rolling(window=n, min_periods=n).min()
    hh = high.rolling(window=n, min_periods=n).max()
    k = 100.0 * (close - ll) / (hh - ll).replace(0, np.nan)
    d = k.rolling(window=smooth, min_periods=smooth).mean()
    return _mask(k, n), d  # d retains its own (later) warm-up naturally


def _cci(high, low, close, n):
    tp = (high + low + close) / 3.0
    sma = tp.rolling(window=n, min_periods=n).mean()
    mad = tp.rolling(window=n, min_periods=n).apply(
        lambda x: np.mean(np.abs(x - np.mean(x))), raw=True
    )
    cci = (tp - sma) / (0.015 * mad).replace(0, np.nan)
    return _mask(cci, n)


def _bollinger(close, n, std=2.0):
    mid = close.rolling(window=n, min_periods=n).mean()
    sd = close.rolling(window=n, min_periods=n).std(ddof=1)
    upper = mid + std * sd
    lower = mid - std * sd
    width = (upper - lower) / mid.replace(0, np.nan)
    pct_b = (close - lower) / (upper - lower).replace(0, np.nan)
    return (
        _mask(mid, n),
        _mask(upper, n),
        _mask(lower, n),
        _mask(width, n),
        _mask(pct_b, n),
    )


def _keltner(close, atr_series, n, mult=2.0):
    mid = _ema(close, n)
    upper = mid + mult * atr_series
    lower = mid - mult * atr_series
    return mid, upper, lower


def _hv(close, n):
    log_ret = np.log(close / close.shift(1))
    hv = log_ret.rolling(window=n, min_periods=n).std(ddof=1)
    return _mask(hv, n)


def _vwap(high, low, close, volume, time):
    tp = (high + low + close) / 3.0
    day = time.dt.date
    cum_pv = (tp * volume).groupby(day).cumsum()
    cum_v = volume.groupby(day).cumsum()
    return cum_pv / cum_v.replace(0, np.nan)


def _mfi(high, low, close, volume, n):
    """Standard MFI (rolling sums of money flow)."""
    tp = (high + low + close) / 3.0
    mf = tp * volume
    tp_diff = tp.diff()
    pos_mf = mf.where(tp_diff > 0, 0.0)
    neg_mf = mf.where(tp_diff < 0, 0.0).abs()
    pos_sum = pos_mf.rolling(window=n, min_periods=n).sum()
    neg_sum = neg_mf.rolling(window=n, min_periods=n).sum()
    rmf = pos_sum / neg_sum.replace(0, np.nan)
    mfi = 100 - (100 / (1 + rmf))
    return _mask(mfi, n)


def _cmf(high, low, close, volume, n):
    denom = (high - low).replace(0, np.nan)
    clv = ((close - low) - (high - close)) / denom
    mf_vol = clv * volume
    num = mf_vol.rolling(window=n, min_periods=n).sum()
    den = volume.rolling(window=n, min_periods=n).sum()
    cmf = num / den.replace(0, np.nan)
    return _mask(cmf, n)


# ---------------------------------------------------------------------------
# Batch 1 / 2 application
# ---------------------------------------------------------------------------


def apply_batch1(df: pd.DataFrame) -> pd.DataFrame:
    out: dict[str, Any] = {}

    # Trend
    for n in N_GRID:
        out[f"sma_{n}"] = _sma(df["close"], n)
        out[f"ema_{n}"] = _ema(df["close"], n)

    for fast, slow in PAIRS:
        m, s, h = _macd(df["close"], fast, slow)
        out[f"macd_{fast}_{slow}"] = m
        out[f"macd_signal_{fast}_{slow}"] = s
        out[f"macd_hist_{fast}_{slow}"] = h

    for n in N_GRID:
        adx, pdi, mdi = _adx(df["high"], df["low"], df["close"], n)
        out[f"adx_{n}"] = adx
        out[f"plus_di_{n}"] = pdi
        out[f"minus_di_{n}"] = mdi

    for n in N_GRID:
        up, down = _aroon(df["high"], df["low"], n)
        out[f"aroon_up_{n}"] = up
        out[f"aroon_down_{n}"] = down

    for n in N_GRID:
        up, lo, mid = _donchian(df["high"], df["low"], n)
        out[f"dc_upper_{n}"] = up
        out[f"dc_lower_{n}"] = lo
        out[f"dc_mid_{n}"] = mid

    # Momentum
    for n in N_GRID:
        out[f"rsi_{n}"] = _rsi(df["close"], n)
        out[f"roc_{n}"] = _mask(df["close"].pct_change(n) * 100.0, n)
        out[f"mom_{n}"] = _mask(df["close"] - df["close"].shift(n), n)
        k, d = _stochastic(df["high"], df["low"], df["close"], n, smooth=6)
        out[f"stoch_k_{n}"] = k
        out[f"stoch_d_{n}"] = d
        out[f"cci_{n}"] = _cci(df["high"], df["low"], df["close"], n)

    # Volatility
    prev_close = df["close"].shift(1)
    tr = pd.concat(
        [
            df["high"] - df["low"],
            (df["high"] - prev_close).abs(),
            (df["low"] - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    out["tr"] = tr

    for n in N_GRID:
        out[f"atr_{n}"] = _atr(df["high"], df["low"], df["close"], n)
        bb_mid, bb_up, bb_lo, bb_wid, bb_pct = _bollinger(df["close"], n)
        out[f"bb_mid_{n}"] = bb_mid
        out[f"bb_upper_{n}"] = bb_up
        out[f"bb_lower_{n}"] = bb_lo
        out[f"bb_width_{n}"] = bb_wid
        out[f"bb_pctb_{n}"] = bb_pct

        kc_mid, kc_up, kc_lo = _keltner(df["close"], out[f"atr_{n}"], n, 2.0)
        out[f"kc_mid_{n}"] = kc_mid
        out[f"kc_upper_{n}"] = kc_up
        out[f"kc_lower_{n}"] = kc_lo

        out[f"hv_{n}"] = _hv(df["close"], n)

    # Volume
    for n in N_GRID:
        out[f"vol_sma_{n}"] = _sma(df["volume"], n)
        out[f"mfi_{n}"] = _mfi(df["high"], df["low"], df["close"], df["volume"], n)
        out[f"cmf_{n}"] = _cmf(df["high"], df["low"], df["close"], df["volume"], n)

    out["vwap"] = _vwap(df["high"], df["low"], df["close"], df["volume"], df["time"])

    df = pd.concat([df, pd.DataFrame(out)], axis=1)
    return df


def apply_batch2(df: pd.DataFrame, timeframe: str) -> pd.DataFrame:
    out: dict[str, Any] = {}
    atr_24 = df["atr_24"]

    for n in N_GRID:
        ema_n = _ema(df["close"], n)
        out[f"ema_dist_{n}"] = (df["close"] - ema_n) / atr_24.replace(0, np.nan)

    for fast, slow in PAIRS:
        ema_f = _ema(df["close"], fast)
        ema_s = _ema(df["close"], slow)
        out[f"ema_spread_{fast}_{slow}"] = (ema_f - ema_s) / atr_24.replace(0, np.nan)

    for fast, slow in PAIRS:
        _, _, hist = _macd(df["close"], fast, slow)
        out[f"macd_hist_atr_{fast}_{slow}"] = hist / atr_24.replace(0, np.nan)

    for n in N_GRID:
        out[f"atr_pct_{n}"] = df[f"atr_{n}"] / df["close"].replace(0, np.nan)

    for a, b in PAIRS:
        out[f"vol_ratio_{a}_{b}"] = out[f"atr_pct_{a}"] / out[f"atr_pct_{b}"].replace(
            0, np.nan
        )

    for n in N_GRID:
        diff = df["close"].diff().abs()
        num = (df["close"] - df["close"].shift(n)).abs()
        den = diff.rolling(window=n, min_periods=n).sum()
        er = num / den.replace(0, np.nan)
        out[f"er_{n}"] = _mask(er, n)

    for n in N_GRID:
        out[f"vol_rel_{n}"] = df["volume"] / df[f"vol_sma_{n}"].replace(0, np.nan)

    # Candle structure
    rng = (df["high"] - df["low"]).replace(0, np.nan)
    out["body_ratio"] = (df["close"] - df["open"]).abs() / rng
    out["upper_wick"] = (df["high"] - df[["open", "close"]].max(axis=1)) / rng
    out["lower_wick"] = (df[["open", "close"]].min(axis=1) - df["low"]) / rng
    out["clv"] = ((df["close"] - df["low"]) - (df["high"] - df["close"])) / rng

    # Time features (5m only)
    if timeframe == "5m":
        hour = df["time"].dt.hour + df["time"].dt.minute / 60.0
        out["hour_sin"] = np.sin(2 * np.pi * hour / 24.0)
        out["hour_cos"] = np.cos(2 * np.pi * hour / 24.0)
        out["dow"] = df["time"].dt.dayofweek

    df = pd.concat([df, pd.DataFrame(out)], axis=1)
    return df


def add_flags(df: pd.DataFrame, timeframe: str) -> pd.DataFrame:
    if timeframe == "5m":
        partial_thresh = 5
        gap_thresh = pd.Timedelta("5min")
        fill_td = pd.Timedelta("5min")
    else:
        partial_thresh = 60
        gap_thresh = pd.Timedelta("1h")
        fill_td = pd.Timedelta("1h")

    if "n_bars" in df.columns:
        is_partial = df["n_bars"] < partial_thresh
    else:
        is_partial = pd.Series(False, index=df.index)
    df["is_partial"] = is_partial

    time_diff = df["time"].diff().fillna(fill_td)
    df["gap_before"] = time_diff > gap_thresh
    return df


def apply_indicators(
    df: pd.DataFrame, timeframe: str, catalogue: Optional[Any] = None
) -> pd.DataFrame:
    """Add indicator columns to a copy of *df*.

    ``catalogue`` is retained for backwards compatibility and is ignored; the
    indicator set is fixed by docs/indicators.md.
    """
    df = df.copy()
    df = apply_batch1(df)
    df = apply_batch2(df, timeframe)
    df = add_flags(df, timeframe)
    return df


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------


def run(
    timeframe: str,
    catalogue_path: Optional[str | Path] = None,
    input_path: Optional[str | Path] = None,
    output_path: Optional[str | Path] = None,
) -> Path:
    if timeframe not in ("5m", "1h"):
        raise ValueError("timeframe must be '5m' or '1h'")

    src_table = "ohlcv_5m" if timeframe == "5m" else "ohlcv_1h"

    if input_path is None:
        input_path = Path("data") / src_table / f"{src_table}.parquet"
    input_path = Path(input_path)

    if output_path is None:
        output_path = Path("data") / f"{src_table}_features" / f"{src_table}_features.parquet"
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    df = pq.read_table(input_path).to_pandas()
    df["time"] = pd.to_datetime(df["time"], utc=True)
    if timeframe == "5m":
        df["close_time"] = df["time"] + pd.Timedelta("5min")
    else:
        df["close_time"] = df["time"] + pd.Timedelta("1h")

    df = df.sort_values(["instrument", "time"]).reset_index(drop=True)

    out_frames = []
    for inst, sub in df.groupby("instrument", sort=False):
        sub = sub.sort_values("time").reset_index(drop=True)
        sub = apply_indicators(sub, timeframe)
        out_frames.append(sub)

    result = pd.concat(out_frames, ignore_index=True).sort_values(
        ["instrument", "time"]
    ).reset_index(drop=True)

    # 5m: attach selected 1h features with as-of join on close_time
    if timeframe == "5m":
        h1_path = Path("data") / "ohlcv_1h_features" / "ohlcv_1h_features.parquet"
        if not h1_path.exists():
            raise FileNotFoundError(
                f"1h features not found at {h1_path}; run 1h first."
            )
        h1_df = pq.read_table(h1_path).to_pandas()
        h1_df["time"] = pd.to_datetime(h1_df["time"], utc=True)
        h1_df["close_time"] = h1_df["time"] + pd.Timedelta("1h")

        h1_cols_needed = []
        for n in N_GRID:
            h1_cols_needed += [
                f"ema_dist_{n}",
                f"adx_{n}",
                f"rsi_{n}",
                f"er_{n}",
                f"atr_pct_{n}",
            ]
        h1_cols_needed = [c for c in h1_cols_needed if c in h1_df.columns]

        keep = ["instrument", "close_time"] + h1_cols_needed
        h1_sub = h1_df[keep].copy()
        rename = {c: f"h1_{c}" for c in h1_cols_needed}
        h1_sub = h1_sub.rename(columns=rename)

        result = pd.merge_asof(
            result.sort_values("close_time"),
            h1_sub.sort_values("close_time"),
            on="close_time",
            by="instrument",
            direction="backward",
        )
        result = result.sort_values(["instrument", "time"]).reset_index(drop=True)

    # drop helper close_time column from final feature table
    if "close_time" in result.columns:
        result = result.drop(columns=["close_time"])

    table = pa.Table.from_pandas(result, preserve_index=False)
    pq.write_table(table, output_path)
    print(f"-> Wrote {len(result)} rows with {len(result.columns)} columns to {output_path}")
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tf", choices=["5m", "1h", "both"], default="both")
    args = parser.parse_args()

    if args.tf == "both":
        run("1h")
        run("5m")
    else:
        run(args.tf)


if __name__ == "__main__":
    main()
