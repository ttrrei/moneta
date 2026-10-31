"""Additive P1 research features over the existing, unchanged feature table.

Uses the same one-instrument DataFrame / named float-array interface as the
feature pipeline. No IO, strategy rules or full-table rebuilds occur here.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from library.market_structure import confirmed_structure, frozen_events

REQUIRED = ("instrument", "time", "open", "high", "low", "close", "n_bars",
            "atr_24", "dc_upper_24", "dc_lower_24")


def compute_research_features(frame: pd.DataFrame, interval_seconds: int, *,
                              swing_left=6, swing_right=6, level_max_age=120,
                              event_window=6, retest_tolerance_atr=0.25,
                              atr_percentile_windows=(60, 120), range_window=24) -> pd.DataFrame:
    if interval_seconds not in (300, 3600) or range_window != 24:
        raise ValueError("v1 supports 5m/1h and the existing Donchian-24 boundary")
    missing = set(REQUIRED) - set(frame.columns)
    if missing:
        raise ValueError(f"missing research inputs: {sorted(missing)}")
    if frame.empty or frame["instrument"].nunique(dropna=False) != 1:
        raise ValueError("one nonempty instrument frame required")
    times = pd.DatetimeIndex(frame["time"])
    if times.tz is None or times.hasnans or not times.is_monotonic_increasing or times.has_duplicates:
        raise ValueError("unique increasing timezone-aware timestamps required")
    arr = {name: frame[name].to_numpy(dtype=float) for name in REQUIRED if name not in ("time", "instrument")}
    o, h, l, c, a = (arr[name] for name in ("open", "high", "low", "close", "atr_24"))
    valid = (np.isfinite(o) & np.isfinite(h) & np.isfinite(l) & np.isfinite(c)
             & (l > 0) & (h >= np.maximum(o, c)) & (l <= np.minimum(o, c))
             & (arr["n_bars"] == interval_seconds // 60))
    gaps = np.r_[False, np.diff(times.as_unit("ns").asi8) != interval_seconds * 1_000_000_000]
    # Structural episodes require consecutive complete observations; rolling
    # volatility ranks below explicitly count observed rows across sessions.
    structure = confirmed_structure(h, l, c, a, valid, gaps, left=swing_left,
                                     right=swing_right, max_age=level_max_age)
    upper = np.r_[np.nan, arr["dc_upper_24"][:-1]]
    lower = np.r_[np.nan, arr["dc_lower_24"][:-1]]
    events = frozen_events(h, l, c, a, upper, lower, structure, valid, gaps,
                           window=event_window, max_age=level_max_age, tolerance=retest_tolerance_atr)
    out = pd.DataFrame(structure | events, index=frame.index)
    for window in atr_percentile_windows:
        if window not in (60, 120):
            raise ValueError("v1 ATR percentile windows are 60 and 120")
        series = pd.Series(np.where(np.isfinite(a) & (a >= 0), a, np.nan))
        out[f"atr_percentile_{window}"] = series.rolling(window, min_periods=window).rank(
            method="max", pct=True).to_numpy()
    # Keep pivot/bar identity separate from feature availability at bar close.
    for side in ("high", "low"):
        indices = out[f"swing_{side}_pivot_index"].to_numpy()
        pivot = pd.Series(pd.NaT, index=frame.index, dtype="datetime64[ns, UTC]")
        mask = np.isfinite(indices)
        pivot.loc[mask] = times.tz_convert("UTC")[indices[mask].astype(int)]
        out[f"swing_{side}_pivot_time"] = pivot
        confirmed = pd.Series(pd.NaT, index=frame.index, dtype="datetime64[ns, UTC]")
        confirmed.loc[mask] = times.tz_convert("UTC")[mask] + pd.Timedelta(seconds=interval_seconds)
        out[f"swing_{side}_confirmed_time"] = confirmed
    for prefix, index_col in (("range", "range_breakout_index"), ("retest", "retest_breakout_index")):
        indices = out[index_col].to_numpy()
        stamp = pd.Series(pd.NaT, index=frame.index, dtype="datetime64[ns, UTC]")
        mask = np.isfinite(indices)
        stamp.loc[mask] = times.tz_convert("UTC")[indices[mask].astype(int)] + pd.Timedelta(seconds=interval_seconds)
        out[f"{prefix}_breakout_confirmed_time"] = stamp
    if any(np.isinf(out[name].to_numpy(dtype=float)).any() for name in out.select_dtypes(include="number")):
        raise ValueError("unhandled infinite feature output")
    return out
