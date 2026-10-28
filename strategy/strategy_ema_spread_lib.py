"""S-06 EMA-spread trend follower as a reusable library (signal only).

Data loading, the timeframe guard, and the shared accounting/metrics all live
in :mod:`strategy.strategy_lib` / :mod:`strategy.engine`; this file only
declares the signal and the run wrapper, so the CLI and the matrix runner call
the exact same code path as every other strategy.

The rule (long-only, 5m): hold long while the previous closed bar's
``ema_spread_24_120`` (EMA-24 minus EMA-120, signed) is positive, flat when it
goes negative. ``ema_spread`` is already computed and tested in
:mod:`pipeline.indicators`, so no indicator code is duplicated here. This is a
different trend family from S-05 (SuperTrend) — a slow-moving spread that
reverses far less often, giving fewer, longer trades.

All timestamps are UTC.
"""

from __future__ import annotations

import numpy as np

from strategy import strategy_lib
from strategy.strategy_lib import (  # noqa: F401  (re-exported public API)
    FEATURES_1H_PARQUET,
    FEATURES_PARQUET,
    TIMEFRAME_PARQUET,
    TIMEFRAME_SECONDS,
    detect_bar_seconds,
    load_bars,
    make_bars,
    run_strategy,
)

SPREAD_COL = "ema_spread_24_120"
COST_BPS = 2.0  # one-way transaction cost, basis points (same convention as S-01)


def build_rule(df) -> "EmaSpreadState":
    return EmaSpreadState(df[SPREAD_COL].to_numpy(np.float64))


def load_ema_spread_bars(parquet: str, instrument: str, since: str | None = None,
                         until: str | None = None):
    """Load the EMA-spread column (plus base pricing) for one window."""
    return strategy_lib.load_bars(
        parquet, instrument, feature_cols=[SPREAD_COL], not_null_cols=[SPREAD_COL],
        since=since, until=until)


class EmaSpreadState:
    """Long-only EMA-spread trend follower.

    ``desired_position(i)`` = the position to hold at the open of bar ``i``,
    decided from the spread on the *previous* closed bar ``i-1``.
    """

    def __init__(self, spread: np.ndarray) -> None:
        self.spread = spread
        self.state = 0  # 0 flat, 1 long

    def desired_position(self, i: int) -> int:
        if i == 0:
            return 0
        s = self.spread[i - 1]
        if np.isfinite(s):
            if s > 0:
                self.state = 1
            else:
                self.state = 0
        return self.state


def run_ema_spread(
    parquet: str,
    instrument: str,
    timeframe: str = "5m",
    since: str | None = None,
    until: str | None = None,
    cost_bps: float = COST_BPS,
    entry_guard: bool = False,
) -> dict:
    """Run the S-06 rule for one instrument / window / cost tier.

    ``entry_guard`` defaults to OFF to match the S-01 baseline convention.
    Returns the full result dict (metadata + engine metrics + distribution).
    """
    df = load_ema_spread_bars(parquet, instrument, since, until)
    if len(df) < 1_000:
        raise SystemExit(f"Only {len(df)} bars loaded for {instrument} "
                         f"(window {since or 'start'}..{until or 'latest'}); not enough to backtest.")

    bars = make_bars(df, timeframe, entry_guard=entry_guard)
    meta = {
        "strategy_id": "S-06",
        "instrument": instrument,
        "timeframe": timeframe,
        "window_since": since,
        "window_until": until,
        "start": str(df["time"].iloc[0]),
        "end": str(df["time"].iloc[-1]),
        "cost_bps": cost_bps,
        "entry_guard": "off" if not entry_guard else "gap_bar|near_market_close",
    }
    return run_strategy(build_rule(df), bars, cost_bps, long_only=True, meta=meta)


def run(
    parquet: str,
    instrument: str,
    timeframe: str = "5m",
    since: str | None = None,
    until: str | None = None,
    cost_bps: float = COST_BPS,
    entry_guard: bool = False,
) -> dict:
    """Matrix-runner entry point (keyword-compatible with :func:`run_ema_spread`)."""
    return run_ema_spread(parquet, instrument, timeframe, since, until, cost_bps, entry_guard)


__all__ = [
    "EmaSpreadState",
    "build_rule",
    "load_ema_spread_bars",
    "run_ema_spread",
    "run",
    "SPREAD_COL",
    "COST_BPS",
    "FEATURES_PARQUET",
    "FEATURES_1H_PARQUET",
    "TIMEFRAME_SECONDS",
    "TIMEFRAME_PARQUET",
    "load_bars",
    "make_bars",
    "detect_bar_seconds",
    "run_strategy",
]
