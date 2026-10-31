"""Pure NumPy primitives for the first ten catalogue ideas.

Trailing windows only. Inputs are aligned, complete observations; callers
mask/reset windows that cross invalid observations or timestamp gaps.
"""
from __future__ import annotations

import numpy as np


def center_stretch(close, window=24):
    """Median/MAD stretch and trailing log-OLS endpoint residual / RMS.

    MAD deviations all use the SAME window median. Regression RMS divides
    by N, not degrees of freedom. Numerically zero residual scale is null.
    Chunking bounds scratch memory without changing window definitions.
    """
    if type(window) is not int or window not in (6, 12, 24, 60, 120):
        raise ValueError("window outside CFD grid")
    c = np.asarray(close, dtype=float)
    if c.ndim != 1:
        raise ValueError("one-dimensional close required")
    median_score = np.full(len(c), np.nan)
    regression_score = np.full(len(c), np.nan)
    if len(c) < window:
        return median_score, regression_score
    views = np.lib.stride_tricks.sliding_window_view(c, window)
    x = np.arange(window, dtype=float) - (window - 1) / 2
    xx = np.dot(x, x)
    for start in range(0, len(views), 16384):
        raw = views[start:start + 16384]
        med = np.median(raw, axis=1)
        mad = np.median(np.abs(raw - med[:, None]), axis=1)
        stretch = np.divide(raw[:, -1] - med, mad, out=np.full(len(raw), np.nan), where=mad > 0)
        with np.errstate(invalid="ignore", divide="ignore"):
            y = np.log(raw)
        centered = y - np.mean(y, axis=1)[:, None]
        slope = (centered @ x) / xx
        residual = centered - slope[:, None] * x
        rms = np.sqrt(np.mean(residual ** 2, axis=1))
        tolerance = np.finfo(float).eps * np.maximum(1., np.max(np.abs(y), axis=1)) * 8
        score = np.divide(residual[:, -1], rms, out=np.full(len(raw), np.nan), where=rms > tolerance)
        end = start + len(raw)
        median_score[start + window - 1:end + window - 1] = stretch
        regression_score[start + window - 1:end + window - 1] = score
    return median_score, regression_score


def capped_age(state, complete, adjacent, cap=120):
    """Run age, capped at cap; invalid rows are null, a new segment seeds age 1."""
    if type(cap) is not int or cap not in (6, 12, 24, 60, 120):
        raise ValueError("cap outside CFD grid")
    out = np.full(len(state), np.nan)
    age = 0
    for t in range(len(out)):
        if not complete[t] or not np.isfinite(state[t]):
            age = 0
            continue
        if not adjacent[t]:
            age = 0
        age = min(cap, age + 1) if state[t] == 1 else 0
        out[t] = age
    return out
