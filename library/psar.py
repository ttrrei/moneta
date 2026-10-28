"""Parabolic SAR — causal Wilder SAR via TA-Lib, plus our direction convention.

The SAR line itself is computed by ``talib.SAR`` (Wilder's original
acceleration-based trailing stop). TA-Lib returns only the line; the
*direction* (uptrend = close above SAR) and the parameter sanity rules are
ours, so they live here to keep one convention, tested the same way as
Supertrend:

* ``psar_dir`` = +1 when ``close > sar`` (uptrend), -1 otherwise, NaN where
  SAR is undefined.
* ``accel`` must be in ``(0, 1)`` and ``accel <= maximum`` (Wilder's
  constraint); both are **free** parameters — explicitly passed, never
  defaulted to library values (B10/B11).

Causality: TA-Lib's SAR is a causal recursion (each value uses prior bars
only); it is path-dependent, so the pipeline drops the leading warm-up rows
(reducing but not eliminating the start-point dependence — a fixed warmup is
not proof the state has converged).
"""

from __future__ import annotations

import numpy as np

__all__ = ["psar_line", "psar_direction"]


def psar_line(
    h: np.ndarray, l: np.ndarray, accel: float = 0.02, maximum: float = 0.20
) -> np.ndarray:
    """Wilder Parabolic SAR line via TA-Lib (NaN where undefined).

    ``accel`` / ``maximum`` are free (non-window) parameters; they are only
    sanity-checked, never whitelisted.
    """
    import talib

    if not (0 < accel <= maximum < 1.0):
        raise ValueError(
            f"PSAR needs 0 < acceleration <= maximum < 1, got ({accel}, {maximum})"
        )
    return talib.SAR(h, l, acceleration=accel, maximum=maximum)


def psar_direction(c: np.ndarray, sar: np.ndarray) -> np.ndarray:
    """+1 when close is above the SAR line (uptrend), -1 below, NaN where SAR is NaN."""
    return np.where(np.isfinite(sar), np.where(c > sar, 1.0, -1.0), np.nan)
