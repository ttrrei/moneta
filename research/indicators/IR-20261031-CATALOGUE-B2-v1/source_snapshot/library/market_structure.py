"""Causal, finite-memory swing and frozen-boundary event primitives.

Arrays describe CLOSED bars. Confirmation indices refer to the bar that made
an event observable, never its earlier pivot/breakout. Undefined values use
NaN, following the existing indicator library contract.
"""
from __future__ import annotations

import numpy as np

WINDOWS = frozenset((6, 12, 24, 60, 120))


def _window(value):
    if type(value) is not int or value not in WINDOWS:
        raise ValueError(f"time window outside CFD grid: {value}")


def confirmed_structure(high, low, close, atr, valid, reset, *, left=6, right=6, max_age=120):
    """Leftmost equal extreme wins: strict left, non-strict right.

    Levels expire at confirmation age max_age. Bad/partial/gap bars reset
    history; their rows are undefined. HH/HL compare only unexpired confirmed
    pivots. Break events cross a level available BEFORE the current bar.
    """
    for value in (left, right, max_age):
        _window(value)
    h, l, c, a = [np.asarray(x, dtype=float) for x in (high, low, close, atr)]
    n = len(c)
    if any(np.ndim(x) != 1 or len(x) != n for x in (h, l, c, a, valid, reset)):
        raise ValueError("aligned one-dimensional arrays required")
    names = ("swing_high_confirmed", "swing_low_confirmed", "swing_high_pivot_index",
             "swing_low_pivot_index", "last_confirmed_swing_high", "last_confirmed_swing_low",
             "bars_since_swing_high", "bars_since_swing_low", "structure_hh", "structure_lh",
             "structure_hl", "structure_ll", "structure_break_up", "structure_break_down",
             "structure_break_strength_up", "structure_break_strength_down",
             "structure_reference_high", "structure_reference_low")
    out = {name: np.full(n, np.nan) for name in names}
    last_h = last_l = np.nan
    ih = il = -max_age
    segment = 0
    for t in range(n):
        if reset[t] or not valid[t]:
            last_h = last_l = np.nan
            ih = il = -max_age
            segment = t + 1
            continue
        if t - ih >= max_age:
            last_h = np.nan
        if t - il >= max_age:
            last_l = np.nan
        # The reference is frozen from the previous close, before a pivot
        # that might be confirmed on this bar updates the available levels.
        out["structure_reference_high"][t] = last_h
        out["structure_reference_low"][t] = last_l
        if t > segment and np.isfinite(a[t]) and a[t] > 0:
            if np.isfinite(last_h):
                out["structure_break_strength_up"][t] = (c[t] - last_h) / a[t]
                out["structure_break_up"][t] = float(c[t] > last_h and c[t - 1] <= last_h)
            if np.isfinite(last_l):
                out["structure_break_strength_down"][t] = (last_l - c[t]) / a[t]
                out["structure_break_down"][t] = float(c[t] < last_l and c[t - 1] >= last_l)
        if t - segment >= left + right:
            for name in ("swing_high_confirmed", "swing_low_confirmed", "structure_hh",
                         "structure_lh", "structure_hl", "structure_ll"):
                out[name][t] = 0.
            p = t - right
            if h[p] > np.max(h[p - left:p]) and h[p] >= np.max(h[p + 1:t + 1]):
                out["swing_high_confirmed"][t] = 1.
                out["swing_high_pivot_index"][t] = p
                out["structure_hh"][t] = float(h[p] > last_h) if np.isfinite(last_h) else np.nan
                out["structure_lh"][t] = float(h[p] < last_h) if np.isfinite(last_h) else np.nan
                last_h, ih = h[p], t
            if l[p] < np.min(l[p - left:p]) and l[p] <= np.min(l[p + 1:t + 1]):
                out["swing_low_confirmed"][t] = 1.
                out["swing_low_pivot_index"][t] = p
                out["structure_hl"][t] = float(l[p] > last_l) if np.isfinite(last_l) else np.nan
                out["structure_ll"][t] = float(l[p] < last_l) if np.isfinite(last_l) else np.nan
                last_l, il = l[p], t
        if np.isfinite(last_h):
            out["last_confirmed_swing_high"][t], out["bars_since_swing_high"][t] = last_h, t - ih
        if np.isfinite(last_l):
            out["last_confirmed_swing_low"][t], out["bars_since_swing_low"][t] = last_l, t - il
    return out


def frozen_events(high, low, close, atr, prior_upper, prior_lower, structure,
                  valid, reset, *, window=6, max_age=120, tolerance=0.25):
    """One active range episode; re-entry uses the ORIGINAL two boundaries.

    FR-02 confirms the first return within max_age observed bars. FR-03 is its
    subset confirmed within window. Retests use a separate structure episode,
    ages 1..window; the relevant low/high must lie in the frozen ATR zone.
    New opposite breakouts replace a pending episode. Every episode confirms
    at most once. No retrospective event labels are written.
    """
    _window(window)
    _window(max_age)
    if not np.isfinite(tolerance) or tolerance < 0:
        raise ValueError("nonnegative finite ATR tolerance required")
    h, l, c, a, up, lo = [np.asarray(x, dtype=float) for x in
                          (high, low, close, atr, prior_upper, prior_lower)]
    n = len(c)
    if any(np.ndim(x) != 1 or len(x) != n for x in (h, l, c, a, up, lo, valid, reset)):
        raise ValueError("aligned one-dimensional arrays required")
    names = ("range_reentry_from_above", "range_reentry_from_below", "range_reentry_distance_atr",
             "range_breakout_index", "range_frozen_upper", "range_frozen_lower",
             "failed_breakout_up", "failed_breakout_down", "failed_breakout_age_bars",
             "failed_breakout_excursion_atr", "failed_breakout_reentry_distance_atr",
             "breakout_retest_up", "breakout_retest_down", "breakout_retest_distance_atr",
             "retest_breakout_index", "retest_reference_level", "bars_since_breakout")
    out = {name: np.full(n, np.nan) for name in names}
    episode = retest = None
    for t in range(n):
        if reset[t] or not valid[t]:
            episode = retest = None
            continue
        if np.isfinite(up[t]) and np.isfinite(lo[t]):
            for name in ("range_reentry_from_above", "range_reentry_from_below",
                         "failed_breakout_up", "failed_breakout_down"):
                out[name][t] = 0.
        for name in ("breakout_retest_up", "breakout_retest_down"):
            out[name][t] = 0.
        if episode is not None:
            side, start, upper, lower, scale, extreme = episode
            age = t - start
            extreme = max(extreme, h[t]) if side == 1 else min(extreme, l[t])
            episode = (side, start, upper, lower, scale, extreme)
            if age >= max_age:
                episode = None
            elif lower <= c[t] <= upper:
                distance = (upper - c[t]) / scale if side == 1 else (c[t] - lower) / scale
                out["range_reentry_from_above" if side == 1 else "range_reentry_from_below"][t] = 1.
                out["range_reentry_distance_atr"][t] = distance
                out["range_breakout_index"][t] = start
                out["range_frozen_upper"][t], out["range_frozen_lower"][t] = upper, lower
                if age <= window:
                    out["failed_breakout_up" if side == 1 else "failed_breakout_down"][t] = 1.
                    out["failed_breakout_age_bars"][t] = age
                    out["failed_breakout_excursion_atr"][t] = ((extreme - upper) if side == 1 else (lower - extreme)) / scale
                    out["failed_breakout_reentry_distance_atr"][t] = distance
                episode = None
        if t and np.isfinite(a[t]) and a[t] > 0 and np.isfinite(up[t]) and np.isfinite(lo[t]):
            side = 1 if c[t] > up[t] and c[t - 1] <= up[t] else -1 if c[t] < lo[t] and c[t - 1] >= lo[t] else 0
            if side and (episode is None or episode[0] != side):
                episode = (side, t, up[t], lo[t], a[t], h[t] if side == 1 else l[t])
        side = 1 if structure["structure_break_up"][t] == 1 else -1 if structure["structure_break_down"][t] == 1 else 0
        if side:
            level = structure["structure_reference_high" if side == 1 else "structure_reference_low"][t]
            retest = (side, t, level, a[t])
        elif retest is not None:
            side, start, level, scale = retest
            age = t - start
            out["bars_since_breakout"][t] = age
            if age > window:
                retest = None
            else:
                price = l[t] if side == 1 else h[t]
                if abs(price - level) <= tolerance * scale and (c[t] > level if side == 1 else c[t] < level):
                    out["breakout_retest_up" if side == 1 else "breakout_retest_down"][t] = 1.
                    out["breakout_retest_distance_atr"][t] = abs(price - level) / scale
                    out["retest_breakout_index"][t], out["retest_reference_level"][t] = start, level
                    retest = None
    return out
