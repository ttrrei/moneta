"""Causal additive features for catalogue batch 1; no IO or outcome labels."""
from __future__ import annotations

import numpy as np
import pandas as pd

from library.catalogue import capped_age, center_stretch

INPUT_COLUMNS = ("instrument", "high", "low", "n_bars", "atr_24", "ema_24", "ema_dist_24",
                 "sqz_on_24", "bb_width_24", "dc_upper_24", "dc_lower_24", "bar_clv",
                 "er_24", "st_dir_24_2")
HTF_COLUMNS = ("instrument", "high", "low", "n_bars", "atr_24", "ema_24", "st_dir_24_2")


def quality(frame, seconds):
    required = {"instrument", "time", "open", "high", "low", "close", "n_bars"}
    if required - set(frame):
        raise ValueError(f"missing inputs: {sorted(required - set(frame))}")
    if frame.empty or frame.instrument.nunique(dropna=False) != 1:
        raise ValueError("one nonempty instrument required")
    time = pd.DatetimeIndex(frame.time)
    if time.tz is None or time.hasnans or time.has_duplicates or not time.is_monotonic_increasing:
        raise ValueError("unique increasing timezone-aware timestamps required")
    p = frame[["open", "high", "low", "close"]].to_numpy(float)
    good = (np.isfinite(p).all(axis=1) & (p > 0).all(axis=1)
            & (p[:, 1] >= np.maximum(p[:, 0], p[:, 3])) & (p[:, 2] <= np.minimum(p[:, 0], p[:, 3]))
            & (frame.n_bars.to_numpy() == seconds // 60))
    adjacent = np.r_[False, np.diff(time.as_unit("ns").asi8) == seconds * 1_000_000_000]
    run = np.zeros(len(frame), dtype=int)
    for i in range(len(frame)):
        run[i] = (run[i - 1] + 1 if i and adjacent[i] else 1) if good[i] else 0
    return good, adjacent, run


def context_features(frame, hourly, slope_lag=6):
    """Native-hour changes, backward close-time as-of and strict one-hour freshness."""
    if slope_lag != 6:
        raise ValueError("batch 1 slope lag is 6 native hours")
    if frame.instrument.iloc[0] != hourly.instrument.iloc[0]:
        raise ValueError("context instrument mismatch")
    good, _, run = quality(hourly, 3600)
    a = hourly.atr_24.to_numpy(float)
    e = hourly.ema_24.to_numpy(float)
    slope = np.full(len(hourly), np.nan)
    numerator = e[6:] - e[:-6]
    slope[6:] = np.divide(numerator, a[6:], out=np.full(len(numerator), np.nan), where=a[6:] > 0)
    slope[run < 7] = np.nan
    right = pd.DataFrame({"source_close": pd.DatetimeIndex(hourly.time).tz_convert("UTC").as_unit("ns") + pd.Timedelta(hours=1),
                          "htf_slope": slope, "htf_direction": hourly.st_dir_24_2.to_numpy(float),
                          "source_complete": good})
    left = pd.DataFrame({"decision_close": pd.DatetimeIndex(frame.time).tz_convert("UTC").as_unit("ns") + pd.Timedelta(minutes=5)})
    merged = pd.merge_asof(left, right, left_on="decision_close", right_on="source_close", direction="backward")
    merged["source_complete"] = merged.source_complete.fillna(False).astype(bool)
    age = (merged.decision_close - merged.source_close).dt.total_seconds()
    usable = (age >= 0) & (age < 3600) & merged.source_complete.fillna(False)
    for name in ("htf_slope", "htf_direction"):
        merged.loc[~usable, name] = np.nan
    merged["htf_age_seconds"] = age
    return merged.set_axis(frame.index)


def compute_catalogue_features(frame, hourly, *, window=24, age_cap=120, slope_lag=6,
                               contact_tolerance_atr=0.25):
    if window != 24 or age_cap != 120 or slope_lag != 6 or contact_tolerance_atr != .25:
        raise ValueError("batch 1 parameters are frozen")
    missing = set(INPUT_COLUMNS) - set(frame)
    if missing or set(HTF_COLUMNS) - set(hourly):
        raise ValueError("missing catalogue input columns")
    good, adjacent, run = quality(frame, 300)
    # Validate identity/time in the HTF before reading its first row.
    quality(hourly, 3600)
    out = context_features(frame, hourly, slope_lag)
    o, h, l, c, a = (frame[name].to_numpy(float) for name in ("open", "high", "low", "close", "atr_24"))
    valid_close = np.where(good, c, np.nan)
    median, residual = center_stretch(valid_close, window)
    median[run < 24] = residual[run < 24] = np.nan
    out["median_stretch"], out["regression_residual"] = median, residual
    out["median_reversal_direction"] = -np.sign(median)
    out["regression_reversal_direction"] = -np.sign(residual)
    d = frame.st_dir_24_2.to_numpy(float).copy()
    d[~good | ~np.isin(d, [-1, 1])] = np.nan
    hd = out.htf_direction.to_numpy(float)
    out["ltf_direction"] = d
    out["trend_alignment"] = np.where(np.isfinite(d) & np.isin(hd, [-1, 1]), (d == hd).astype(float), np.nan)
    slope_direction = np.sign(out.htf_slope.to_numpy(float))
    slope_direction[slope_direction == 0] = np.nan
    distance = frame.ema_dist_24.to_numpy(float)
    signed_distance = slope_direction * distance
    out["htf_slope_direction"] = slope_direction
    out["pullback_depth"] = np.abs(distance)
    out["pullback_state"] = np.where(np.isfinite(signed_distance) & (signed_distance != 0),
                                     (signed_distance < 0).astype(float), np.nan)
    out["ema_distance_abs"] = np.abs(distance)
    out["squeeze_age"] = capped_age(frame.sqz_on_24.to_numpy(float), good, adjacent, age_cap)
    out["no_direction"] = 0.
    returns = np.full(len(frame), np.nan)
    returns[1:] = np.log(c[1:] / c[:-1])
    returns[(run < 2) | ~adjacent] = np.nan
    r = pd.Series(returns)
    squared = r ** 2
    total = squared.rolling(24, min_periods=24).sum()
    up = squared.where(r > 0, 0).where(r.notna()).rolling(24, min_periods=24).sum()
    down = squared.where(r < 0, 0).where(r.notna()).rolling(24, min_periods=24).sum()
    imbalance = ((up - down) / total.where(total > 0)).to_numpy()
    out["variance_imbalance"] = imbalance
    out["variance_direction"] = np.sign(imbalance)
    out["return_variance_24"] = r.rolling(24, min_periods=24).var(ddof=0).to_numpy()
    out["absolute_return_24"] = np.abs(np.log(c / np.r_[np.full(24, np.nan), c[:-24]])) if len(c) >= 24 else np.nan
    out.loc[run < 25, "absolute_return_24"] = np.nan
    signs = np.sign(r)
    memory = signs.rolling(24, min_periods=24).corr(signs.shift(1)).clip(-1, 1)
    out["sign_memory"] = memory.to_numpy()
    out["last_return_direction"] = np.sign(returns)
    jump = (squared.rolling(24, min_periods=24).max() / total.where(total > 0)).to_numpy()
    out["jump_concentration"] = jump
    jump_direction = np.full(len(frame), np.nan)
    if len(frame) >= 24:
        windows = np.lib.stride_tricks.sliding_window_view(returns, 24)
        # Earliest equally large move wins, with window validity checked below.
        j = np.argmax(np.nan_to_num(windows ** 2, nan=-1), axis=1)
        values = np.sign(windows[np.arange(len(windows)), j])
        values[~np.isfinite(jump[23:])] = np.nan
        jump_direction[23:] = values
    out["jump_direction"] = jump_direction
    prev_o, prev_c = np.r_[np.nan, o[:-1]], np.r_[np.nan, c[:-1]]
    body_direction = np.sign(c - o)
    opposite = (body_direction * np.sign(prev_c - prev_o) == -1) & (run >= 2)
    current_lo, current_hi = np.minimum(o, c), np.maximum(o, c)
    prior_lo, prior_hi = np.minimum(prev_o, prev_c), np.maximum(prev_o, prev_c)
    engulf = ((current_lo <= prior_lo) & (current_hi >= prior_hi)
              & ((current_lo < prior_lo) | (current_hi > prior_hi)))
    out["body_direction"] = np.where(opposite, body_direction, np.nan)
    out["engulfing_state"] = np.where(opposite, engulf.astype(float), np.nan)
    out["body_atr"] = np.divide(np.abs(c - o), a, out=np.full(len(c), np.nan), where=a > 0)
    upper = np.r_[np.nan, frame.dc_upper_24.to_numpy(float)[:-1]]
    lower = np.r_[np.nan, frame.dc_lower_24.to_numpy(float)[:-1]]
    inside = (c >= lower) & (c <= upper) & (run >= 25) & np.isfinite(a) & (a > 0)
    top_contact = inside & (h >= upper - .25 * a)
    bottom_contact = inside & (l <= lower + .25 * a)
    # Both-edge contacts have no defensible unique direction; retain a diagnostic flag.
    top, bottom = top_contact & ~bottom_contact, bottom_contact & ~top_contact
    out["sweep_ambiguous"] = np.where(inside, (top_contact & bottom_contact).astype(float), np.nan)
    out["rejection_direction"] = np.where(top, -1., np.where(bottom, 1., np.nan))
    out["sweep_state"] = np.where(top, (h > upper).astype(float), np.where(bottom, (l < lower).astype(float), np.nan))
    out["rejection_clv"] = out.rejection_direction * frame.bar_clv.to_numpy(float)
    for name in ("bb_width_24", "er_24"):
        out[name] = frame[name].to_numpy(float)
    numeric = out.select_dtypes(include="number").columns
    out.loc[~good, numeric] = np.nan
    if np.isinf(out[numeric].to_numpy()).any():
        raise ValueError("infinite catalogue feature")
    return out
