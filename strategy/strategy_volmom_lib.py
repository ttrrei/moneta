"""S-27 Volume-confirmed momentum (signal only).

Data loading, the timeframe guard, and the shared accounting/metrics live in
:mod:`strategy.strategy_lib` / :mod:`strategy.engine`; this file only declares
the signal and the run wrapper (same contract as S-05/S-06/S-07).

Base rule (long-only, 5m): enter long when the *previous closed bar's*
``mom_24`` (24-bar return) is positive **and** ``vol_rel_24`` (volume relative
to its 24-bar average) is at least ``vmin`` — momentum confirmed by an
active volume. Exit when ``mom_24`` turns non-positive. ``mom_24`` and
``vol_rel_24`` are computed and tested in :mod:`pipeline.indicators` and
exist in both feature tables.

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


class VolMomState:
    """Volume-confirmed momentum, long-only."""

    def __init__(self, mom: np.ndarray, vol_rel: np.ndarray,
                 vmin: float = 1.0) -> None:
        self.mom = mom
        self.vol_rel = vol_rel
        self.vmin = vmin
        self.state = 0

    def desired_position(self, i: int) -> int:
        if i == 0:
            return 0
        j = i - 1
        if not (np.isfinite(self.mom[j]) and np.isfinite(self.vol_rel[j])):
            return self.state
        if self.state == 0:
            if self.mom[j] > 0.0 and self.vol_rel[j] >= self.vmin:
                self.state = 1
        elif self.mom[j] <= 0.0:
            self.state = 0
        return self.state


def build_rule(df, vmin: float = 1.0) -> "VolMomState":
    return VolMomState(
        df["mom_24"].to_numpy(np.float64),
        df["vol_rel_24"].to_numpy(np.float64),
        vmin=vmin)


def load_volmom_bars(parquet: str, instrument: str, since: str | None = None,
                     until: str | None = None, oos_token: object | None = None):
    """Load the momentum / volume columns (plus base pricing) for one window.

    ``oos_token`` is required for any window that reaches the OOS holdout
    (the data-layer gate in :func:`strategy_lib.load_bars`); in-sample windows
    load with no token.
    """
    return strategy_lib.load_bars(
        parquet, instrument, feature_cols=["mom_24", "vol_rel_24"],
        not_null_cols=["mom_24", "vol_rel_24"],
        since=since, until=until, oos_token=oos_token)


def run_volmom(
    parquet: str,
    instrument: str,
    timeframe: str = "5m",
    since: str | None = None,
    until: str | None = None,
    cost_bps: float = COST_BPS,
    entry_guard: bool = False,
    vmin: float = 1.0,
    oos_token: object | None = None,
) -> dict:
    """Run the S-27 rule for one instrument / window / cost tier.

    Returns the full result dict (metadata + engine metrics + distribution).
    """
    df = load_volmom_bars(parquet, instrument, since, until, oos_token=oos_token)
    if len(df) < 1_000:
        raise SystemExit(f"Only {len(df)} bars loaded for {instrument} "
                         f"(window {since or 'start'}..{until or 'latest'}); not enough to backtest.")

    bars = make_bars(df, timeframe, entry_guard=entry_guard)
    meta = {
        "strategy_id": "S-27",
        "instrument": instrument,
        "timeframe": timeframe,
        "window_since": since,
        "window_until": until,
        "start": str(df["time"].iloc[0]),
        "end": str(df["time"].iloc[-1]),
        "cost_bps": cost_bps,
        "entry_guard": "off" if not entry_guard else "gap_bar|near_market_close",
        "vmin": vmin,
    }
    return run_strategy(build_rule(df, vmin), bars,
                        cost_bps, long_only=True, meta=meta)


def run(
    parquet: str,
    instrument: str,
    timeframe: str = "5m",
    since: str | None = None,
    until: str | None = None,
    cost_bps: float = COST_BPS,
    entry_guard: bool = False,
    vmin: float = 1.0,
    oos_token: object | None = None,
) -> dict:
    """Matrix-runner entry point (keyword-compatible with :func:`run_volmom`)."""
    return run_volmom(parquet, instrument, timeframe, since, until, cost_bps,
                      entry_guard, vmin, oos_token=oos_token)


__all__ = [
    "VolMomState",
    "build_rule",
    "load_volmom_bars",
    "run_volmom",
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
