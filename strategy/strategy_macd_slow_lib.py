"""S-23 Slow MACD (24/120) histogram follower (signal only).

Data loading, the timeframe guard, and the shared accounting/metrics live in
:mod:`strategy.strategy_lib` / :mod:`strategy.engine`; this file only declares
the signal and the run wrapper (same contract as S-05/S-06/S-07).

Base rule (long-only, 5m): follow the sign of the *previous closed bar's*
``macd_hist_atr_24_120`` (slow MACD histogram, ATR-normalised so the
threshold is comparable across instruments) — hold long while it is above ``th`` (0 = sign rule), flat below ``th_exit``. Distinct from S-11 (fast 12/60 *zero-cross* with an ATR
magnitude gate): this is a *slow* 24/120 histogram level rule, a different
parameter family from S-11's. ``macd_hist_atr_24_120`` is computed and tested in
:mod:`pipeline.indicators`; no indicator code is duplicated here.

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


class MacdSlowState:
    """Slow (24/120) MACD histogram follower, long-only.

    ``desired_position(i)`` = the position to hold at the open of bar ``i``,
    decided from the *previous* closed bar ``i-1``:

    * hold long: prev ``macd_hist_atr_24_120`` > ``th``;
    * exit:      prev histogram <= ``th_exit`` (0 = sign rule; ``th_exit < th``
      gives hysteresis).
    """

    def __init__(self, hist: np.ndarray, th: float = 0.0, th_exit: float = 0.0) -> None:
        self.hist = hist
        self.th = th
        self.th_exit = th_exit
        self.state = 0

    def desired_position(self, i: int) -> int:
        if i == 0:
            return 0
        h = self.hist[i - 1]
        if not np.isfinite(h):
            return self.state
        if self.state == 0:
            self.state = 1 if h > self.th else 0
        elif h <= self.th_exit:
            self.state = 0
        return self.state


def build_rule(df, th: float = 0.0, th_exit: float = 0.0) -> "MacdSlowState":
    return MacdSlowState(df["macd_hist_atr_24_120"].to_numpy(np.float64),
                         th=th, th_exit=th_exit)


def load_macd_slow_bars(parquet: str, instrument: str, since: str | None = None,
                        until: str | None = None, oos_token: object | None = None):
    """Load the slow-MACD histogram column for one window.

    ``oos_token`` is required for any window that reaches the OOS holdout
    (the data-layer gate in :func:`strategy_lib.load_bars`); in-sample windows
    load with no token.
    """
    return strategy_lib.load_bars(
        parquet, instrument, feature_cols=["macd_hist_atr_24_120"],
        not_null_cols=["macd_hist_atr_24_120"],
        since=since, until=until, oos_token=oos_token)


def run_macd_slow(
    parquet: str,
    instrument: str,
    timeframe: str = "5m",
    since: str | None = None,
    until: str | None = None,
    cost_bps: float = COST_BPS,
    entry_guard: bool = False,
    th: float = 0.0,
    th_exit: float = 0.0,
    oos_token: object | None = None,
) -> dict:
    """Run the S-23 rule for one instrument / window / cost tier.

    Returns the full result dict (metadata + engine metrics + distribution).
    """
    df = load_macd_slow_bars(parquet, instrument, since, until, oos_token=oos_token)
    if len(df) < 1_000:
        raise SystemExit(f"Only {len(df)} bars loaded for {instrument} "
                         f"(window {since or 'start'}..{until or 'latest'}); not enough to backtest.")

    bars = make_bars(df, timeframe, entry_guard=entry_guard)
    meta = {
        "strategy_id": "S-23",
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
    th: float = 0.0,
    th_exit: float = 0.0,
    oos_token: object | None = None,
) -> dict:
    """Matrix-runner entry point (keyword-compatible with :func:`run_macd_slow`)."""
    return run_macd_slow(parquet, instrument, timeframe, since, until, cost_bps,
                         entry_guard, th, th_exit, oos_token=oos_token)


__all__ = [
    "MacdSlowState",
    "build_rule",
    "load_macd_slow_bars",
    "run_macd_slow",
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
