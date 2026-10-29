"""S-26 EMA-spread follower (signal only).

Data loading, the timeframe guard, and the shared accounting/metrics live in
:mod:`strategy.strategy_lib` / :mod:`strategy.engine`; this file only declares
the signal and the run wrapper (same contract as S-05/S-06/S-07).

Base rule (long-only, 5m): enter long when the *previous closed bar's*
``ema_spread_12_60`` (fast/slow EMA distance in ATR units) crosses above
``th``; exit when it falls back below ``th_exit`` (hysteresis keeps the
position through small pullbacks). ``ema_spread_12_60`` is computed and tested
in :mod:`pipeline.indicators` and exists in both feature tables.

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


class EmaSpread12State:
    """EMA-spread follower with hysteresis, long-only."""

    def __init__(self, spread: np.ndarray,
                 th: float = 0.5, th_exit: float = 0.0) -> None:
        self.spread = spread
        self.th = th
        self.th_exit = th_exit
        self.state = 0

    def desired_position(self, i: int) -> int:
        if i == 0:
            return 0
        j = i - 1
        s = self.spread[j]
        if not np.isfinite(s):
            return self.state
        if self.state == 0 and s > self.th:
            self.state = 1
        elif self.state == 1 and s < self.th_exit:
            self.state = 0
        return self.state


def build_rule(df, th: float = 0.5, th_exit: float = 0.0) -> "EmaSpread12State":
    return EmaSpread12State(
        df["ema_spread_12_60"].to_numpy(np.float64),
        th=th, th_exit=th_exit)


def load_spread_bars(parquet: str, instrument: str, since: str | None = None,
                     until: str | None = None, oos_token: object | None = None):
    """Load the EMA-spread column (plus base pricing) for one window.

    ``oos_token`` is required for any window that reaches the OOS holdout
    (the data-layer gate in :func:`strategy_lib.load_bars`); in-sample windows
    load with no token.
    """
    return strategy_lib.load_bars(
        parquet, instrument, feature_cols=["ema_spread_12_60"],
        not_null_cols=["ema_spread_12_60"],
        since=since, until=until, oos_token=oos_token)


def run_spread(
    parquet: str,
    instrument: str,
    timeframe: str = "5m",
    since: str | None = None,
    until: str | None = None,
    cost_bps: float = COST_BPS,
    entry_guard: bool = False,
    th: float = 0.5,
    th_exit: float = 0.0,
    oos_token: object | None = None,
) -> dict:
    """Run the S-26 rule for one instrument / window / cost tier.

    Returns the full result dict (metadata + engine metrics + distribution).
    """
    df = load_spread_bars(parquet, instrument, since, until, oos_token=oos_token)
    if len(df) < 1_000:
        raise SystemExit(f"Only {len(df)} bars loaded for {instrument} "
                         f"(window {since or 'start'}..{until or 'latest'}); not enough to backtest.")

    bars = make_bars(df, timeframe, entry_guard=entry_guard)
    meta = {
        "strategy_id": "S-26",
        "instrument": instrument,
        "timeframe": timeframe,
        "window_since": since,
        "window_until": until,
        "start": str(df["time"].iloc[0]),
        "end": str(df["time"].iloc[-1]),
        "cost_bps": cost_bps,
        "entry_guard": "off" if not entry_guard else "gap_bar|near_market_close",
        "th": th,
        "th_exit": th_exit,
    }
    return run_strategy(build_rule(df, th, th_exit), bars,
                        cost_bps, long_only=True, meta=meta)


def run(
    parquet: str,
    instrument: str,
    timeframe: str = "5m",
    since: str | None = None,
    until: str | None = None,
    cost_bps: float = COST_BPS,
    entry_guard: bool = False,
    th: float = 0.5,
    th_exit: float = 0.0,
    oos_token: object | None = None,
) -> dict:
    """Matrix-runner entry point (keyword-compatible with :func:`run_spread`)."""
    return run_spread(parquet, instrument, timeframe, since, until, cost_bps,
                      entry_guard, th, th_exit, oos_token=oos_token)


__all__ = [
    "EmaSpread12State",
    "build_rule",
    "load_spread_bars",
    "run_spread",
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
