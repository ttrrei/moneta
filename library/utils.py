"""Shared helpers for the moneta indicator library.

Pure (NumPy-only) utilities used by the individual indicator modules and by
``pipeline/indicators.py`` when it registers our custom indicators as feature
columns. Nothing in this package imports pandas, duckdb, or talib — only
NumPy — so it is trivially unit-testable in isolation.
"""

from __future__ import annotations

from typing import Iterable


def param_tag(x: float) -> str:
    """Column-name tag for a float parameter: 0.02 -> '0p02', 3.0 -> '3', 2.5 -> '2p5'."""
    return f"{x:g}".replace(".", "p").replace("-", "m")


def validate_free_params(
    psar_params: Iterable[tuple[float, float]], st_mults: Iterable[float]
) -> None:
    """Sanity-check (NOT whitelist) the free PSAR / Supertrend parameters.

    Only *time-window* parameters are restricted to the N grid
    (``pipeline.indicators.validate_grid``). These free parameters must simply
    be well-formed, and they must be *named explicitly by the caller* — never
    silently defaulted to a library value (B10/B11).
    """
    for accel, mx in psar_params:
        if not (0 < accel <= mx):
            raise ValueError(f"PSAR needs 0 < acceleration <= maximum, got ({accel}, {mx})")
    for m in st_mults:
        if not m > 0:
            raise ValueError(f"Supertrend multiplier must be > 0, got {m}")
