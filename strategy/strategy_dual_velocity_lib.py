"""S-12 Dual-velocity momentum: ROC-24 up + slow EMA slope up (signal only).

Data loading, the timeframe guard, and the shared accounting/metrics live in
:mod:`strategy.strategy_lib` / :mod:`strategy.engine`; this file only declares
the signal and the run wrapper (same contract as S-05/S-06/S-07).

Base rule (long-only, 5m): hold long while the *previous closed bar's*
``roc_24`` (24-bar rate of change) is above 0 **and** the previous closed
bar's ``ema_120`` is above the bar-24-ago ``ema_120`` (the slow EMA itself is
rising — slow-trend confirmation). Exit when either condition fails.
Different family from S-06/S-07: a fast/slow *velocity* pair (ROC + EMA
slope) instead of a single spread or SuperTrend. ``roc_24`` / ``ema_120`` are
computed and tested in :mod:`pipeline.indicators`.

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

COST_BPS = 2.0  # one-way transaction cost, basis points (same convention as S-01)


class DualVelocityState:
    """ROC-24 / slow-EMA-slope dual-velocity follower, long-only.

    ``desired_position(i)`` = the position to hold at the open of bar ``i``,
    decided from indicators on the *previous* closed bar ``i-1`` (and the
    current bar's ``close`` / ``ema_24`` for the optional trend gate — both
    known at the bar's close, so no lookahead).

    * hold long: prev ``roc_24`` > 0 and prev ``ema_120`` > ``ema_120`` of
      bar ``i-1-slope_lag``;
    * exit:      either condition fails (state drops to 0);
    * optional:  ``ema_gate`` requires prev ``close`` > prev ``ema_24`` to *enter*
      (exits are never gated).
    """

    def __init__(self, roc: np.ndarray, ema_slow: np.ndarray, close: np.ndarray,
                 ema_fast: np.ndarray, slope_lag: int = 24, ema_gate: bool = False) -> None:
        self.roc = roc
        self.ema_slow = ema_slow
        self.close = close
        self.ema_fast = ema_fast
        self.slope_lag = int(slope_lag)
        self.ema_gate = ema_gate
        self.state = 0

    def desired_position(self, i: int) -> int:
        if i == 0:
            return 0
        j = i - 1
        if not (np.isfinite(self.roc[j]) and np.isfinite(self.ema_slow[j])):
            return self.state
        slow_i = j - self.slope_lag
        if slow_i < 0 or not np.isfinite(self.ema_slow[slow_i]):
            return self.state
        cond = self.roc[j] > 0 and self.ema_slow[j] > self.ema_slow[slow_i]
        if self.state == 0:
            if cond and self.ema_gate:
                cond = strategy_lib.entry_gate_allows(True, self.close, self.ema_fast, j)
            if cond:
                self.state = 1
        elif not cond:
            self.state = 0
        return self.state


def build_rule(df, slope_lag: int = 24, ema_gate: bool = False) -> "DualVelocityState":
    return DualVelocityState(
        df["roc_24"].to_numpy(np.float64),
        df["ema_120"].to_numpy(np.float64),
        df["close"].to_numpy(np.float64),
        df["ema_24"].to_numpy(np.float64),
        slope_lag=slope_lag, ema_gate=ema_gate)


def load_dual_velocity_bars(parquet: str, instrument: str, since: str | None = None,
                            until: str | None = None, oos_token: object | None = None):
    """Load the ROC / slow-EMA columns (plus base pricing) for one window.

    ``oos_token`` is required for any window that reaches the OOS holdout
    (the data-layer gate in :func:`strategy_lib.load_bars`); in-sample windows
    load with no token.
    """
    return strategy_lib.load_bars(
        parquet, instrument, feature_cols=["roc_24", "ema_120", "ema_24"],
        not_null_cols=["roc_24", "ema_120"],
        since=since, until=until, oos_token=oos_token)


def run_dual_velocity(
    parquet: str,
    instrument: str,
    timeframe: str = "5m",
    since: str | None = None,
    until: str | None = None,
    cost_bps: float = COST_BPS,
    entry_guard: bool = False,
    slope_lag: int = 24,
    ema_gate: bool = False,
    oos_token: object | None = None,
) -> dict:
    """Run the S-12 rule for one instrument / window / cost tier.

    Returns the full result dict (metadata + engine metrics + distribution).
    """
    df = load_dual_velocity_bars(parquet, instrument, since, until, oos_token=oos_token)
    if len(df) < 1_000:
        raise SystemExit(f"Only {len(df)} bars loaded for {instrument} "
                         f"(window {since or 'start'}..{until or 'latest'}); not enough to backtest.")

    bars = make_bars(df, timeframe, entry_guard=entry_guard)
    meta = {
        "strategy_id": "S-12",
        "instrument": instrument,
        "timeframe": timeframe,
        "window_since": since,
        "window_until": until,
        "start": str(df["time"].iloc[0]),
        "end": str(df["time"].iloc[-1]),
        "cost_bps": cost_bps,
        "entry_guard": "off" if not entry_guard else "gap_bar|near_market_close",
        "slope_lag": slope_lag,
        "ema_gate": ema_gate,
    }
    return run_strategy(build_rule(df, slope_lag, ema_gate), bars,
                        cost_bps, long_only=True, meta=meta)


def run(
    parquet: str,
    instrument: str,
    timeframe: str = "5m",
    since: str | None = None,
    until: str | None = None,
    cost_bps: float = COST_BPS,
    entry_guard: bool = False,
    slope_lag: int = 24,
    ema_gate: bool = False,
    oos_token: object | None = None,
) -> dict:
    """Matrix-runner entry point (keyword-compatible with :func:`run_dual_velocity`)."""
    return run_dual_velocity(parquet, instrument, timeframe, since, until, cost_bps,
                             entry_guard, slope_lag, ema_gate, oos_token=oos_token)


__all__ = [
    "DualVelocityState",
    "build_rule",
    "load_dual_velocity_bars",
    "run_dual_velocity",
    "run",
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
