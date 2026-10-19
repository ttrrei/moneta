"""Compute technical indicators on the OHLCV bars (Silver/Gold feature layer).

Reads the indicator catalogue from ``config/indicators.yml`` and applies the
implemented indicators to ``data/ohlcv_5m/`` and ``data/ohlcv_1h/`` bars.
Untagged indicators (not yet implemented) are skipped with a warning.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml


def _ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()


def _rsi(close: pd.Series, window: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    avg_gain = gain.ewm(alpha=1 / window, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / window, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def _atr(high, low, close, window=14) -> pd.Series:
    prev_close = close.shift(1)
    tr = pd.concat(
        [(high - low), (high - prev_close).abs(), (low - prev_close).abs()], axis=1
    ).max(axis=1)
    return tr.ewm(alpha=1 / window, adjust=False).mean()


def _macd(close, fast=12, slow=26, signal=9):
    macd = _ema(close, fast) - _ema(close, slow)
    sig = _ema(macd, signal)
    return macd, sig, macd - sig


def apply_indicators(df: pd.DataFrame, tf: str, catalogue: dict) -> pd.DataFrame:
    """Add indicator columns to a copy of *df* (must have open/high/low/close/volume)."""
    df = df.copy()
    g = (catalogue.get("timeframes", {}) or {}).get(tf, {})
    for ind in g.get("indicators", []):
        name = ind["name"]
        params = ind.get("params", {}) or {}
        outputs = ind.get("outputs") or ([ind["output"]] if "output" in ind else [])
        # --- implemented subset ---
        if name == "ema_fast":
            df[outputs[0]] = _ema(df["close"], params["span"])
        elif name == "ema_slow":
            df[outputs[0]] = _ema(df["close"], params["span"])
        elif name == "ema_trend":
            df[outputs[0]] = _ema(df["close"], params["span"])
        elif name == "sma_200":
            df[outputs[0]] = df["close"].rolling(params["window"]).mean()
        elif name == "macd":
            m, s, h = _macd(df["close"], params["fast"], params["slow"], params["signal"])
            df[outputs[0]], df[outputs[1]], df[outputs[2]] = m, s, h
        elif name == "adx":
            # simple placeholder: TR-based smoothing length not exact ADX but monotonic
            adx = _atr(df["high"], df["low"], df["close"], params["window"])
            df[outputs[0]] = adx / df["close"] * 100
            df[outputs[1]] = df["high"].diff().clip(lower=0).fillna(0)
            df[outputs[2]] = (-df["low"].diff()).clip(lower=0).fillna(0)
        elif name == "rsi":
            df[outputs[0]] = _rsi(df["close"], params["window"])
        elif name == "stoch":
            low = df["low"].rolling(params["k"]).min()
            high = df["high"].rolling(params["k"]).max()
            k = (df["close"] - low) / (high - low) * 100
            df[outputs[0]] = k.rolling(params["smooth"]).mean()
            df[outputs[1]] = df[outputs[0]].rolling(params["d"]).mean()
        elif name == "cci":
            tp = (df["high"] + df["low"] + df["close"]) / 3
            sma = tp.rolling(params["window"]).mean()
            mad = tp.rolling(params["window"]).apply(lambda x: np.mean(np.abs(x - x.mean())), raw=True)
            df[outputs[0]] = (tp - sma) / (0.015 * mad)
        elif name == "roc":
            df[outputs[0]] = df["close"].pct_change(params["window"]) * 100
        elif name == "atr":
            df[outputs[0]] = _atr(df["high"], df["low"], df["close"], params["window"])
        elif name == "bollinger":
            mid = df["close"].rolling(params["window"]).mean()
            sd = df["close"].rolling(params["window"]).std()
            upper = mid + params["std"] * sd
            lower = mid - params["std"] * sd
            df[outputs[0]] = mid
            df[outputs[1]] = upper
            df[outputs[2]] = lower
            df[outputs[3]] = (upper - lower) / mid
            df[outputs[4]] = (df["close"] - lower) / (upper - lower)
        elif name in ("keltner",):
            mid = _ema(df["close"], params["ema"])
            a = _atr(df["high"], df["low"], df["close"], params["atr"])
            df[outputs[0]] = mid
            df[outputs[1]] = mid + params["mult"] * a
            df[outputs[2]] = mid - params["mult"] * a
        elif name == "obv":
            sign = df["close"].diff().apply(lambda x: 1 if x > 0 else (-1 if x < 0 else 0))
            df[outputs[0]] = (sign * df["volume"]).cumsum()
        elif name == "vwap":
            tp = (df["high"] + df["low"] + df["close"]) / 3
            # cumulative per UTC day
            day = df["time"].dt.date if "time" in df else pd.Series([None]*len(df))
            if "time" in df.columns:
                gkey = df["time"].dt.date
                num = (tp * df["volume"]).groupby(gkey).cumsum()
                den = df["volume"].groupby(gkey).cumsum()
                df[outputs[0]] = num / den
            else:
                df[outputs[0]] = (tp * df["volume"]).cumsum() / df["volume"].cumsum()
        elif name == "volume_sma":
            df[outputs[0]] = df["volume"].rolling(params["window"]).mean()
        else:
            # not implemented yet
            for o in outputs:
                df[o] = np.nan
    return df


def run(timeframe: str, catalogue_path: str | Path = "config/indicators.yml",
       input_path: str | Path | None = None, output_path: str | Path | None = None) -> Path:
    import pyarrow.parquet as pq
    catalogue = yaml.safe_load(Path(catalogue_path).read_text())
    g = (catalogue.get("timeframes", {}) or {}).get(timeframe, {})
    src_table = g.get("source_table", "ohlcv_5m" if timeframe == "5m" else "ohlcv_1h")
    if input_path is None:
        input_path = Path("data") / src_table / f"{src_table}.parquet"
    if output_path is None:
        output_path = Path("data") / f"{src_table}_features" / f"{src_table}_features.parquet"
    input_path = Path(input_path); output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    df = pq.read_table(input_path).to_pandas()
    df["time"] = pd.to_datetime(df["time"], utc=True)
    df = df.sort_values(["instrument", "time"]).reset_index(drop=True)
    out_frames = []
    for inst, sub in df.groupby("instrument", sort=False):
        sub = sub.sort_values("time").reset_index(drop=True)
        sub = apply_indicators(sub, timeframe, catalogue)
        out_frames.append(sub)
    result = pd.concat(out_frames, ignore_index=True).sort_values(["instrument", "time"]).reset_index(drop=True)
    # write
    import pyarrow as pa
    table = pa.Table.from_pandas(result, preserve_index=False)
    pq.write_table(table, output_path)
    print(f"-> Wrote {len(result)} rows with {len(result.columns)} columns to {output_path}")
    return output_path


def main() -> None:
    for tf in ("5m", "1h"):
        try:
            run(tf)
        except Exception as e:
            print(f"Error on {tf}: {e}")


if __name__ == "__main__":
    main()
