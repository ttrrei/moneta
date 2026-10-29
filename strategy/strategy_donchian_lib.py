"""S-14 Donchian-24 breakout follower (signal only).

Data loading, the timeframe guard, and the shared accounting/metrics live in
:mod:`strategy.strategy_lib` / :mod:`strategy.engine`; this file only declares
the signal and the run wrapper (same contract as S-05/S-06/S-07).

Base rule (long-only, 5m): hold long while the *previous closed bar's* close
is above the mid of its 24-bar Donchian range (``dc_mid_24`` = midpoint of
the 24-bar high/low channel — i.e. the close sits in the upper half of its
own recent range). Exit when it falls to/below the mid. Distinct family from
S-04 (Squeeze-onset) and S-05 (SuperTrend): a pure channel-position rule on
``dc_mid_24``. The column is computed and tested in
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


class DonchianState:
    """Donchian-24 channel-position follower, long-only.

    ``desired_position(i)`` = the position to hold at the open of bar ``i``,
    decided from bar ``i-1``: long while prev ``close`` > prev
    ``dc_mid_24 + th * (dc_upper_24 - dc_mid_24)``; flat otherwise.
    ``th`` (0.0 = plain mid-cross) gives the entry-only hysteresis variant
    (entry above mid + th × half-range, exit at/below mid).
    """

    def __init__(self, close: np.ndarray, mid: np.ndarray, upper: np.ndarray,
                 th: float = 0.0) -> None:
        self.close = close
        self.mid = mid
        self.upper = upper
        self.th = float(th)
        self.state = 0

    def desired_position(self, i: int) -> int:
        if i == 0:
            return 0
        j = i - 1
        if not (np.isfinite(self.mid[j]) and np.isfinite(self.upper[j])):
            return self.state
        half = 0.5 * (self.upper[j] - self.mid[j])
        if self.state == 0:
            if self.close[j] > self.mid[j] + self.th * half:
                self.state = 1
        elif self.close[j] <= self.mid[j]:
            self.state = 0
        return self.state


def build_rule(df, th: float = 0.0) -> "DonchianState":
    return DonchianState(
        df["close"].to_numpy(np.float64),
        df["dc_mid_24"].to_numpy(np.float64),
        df["dc_upper_24"].to_numpy(np.float64),
        th=th)


def load_donchian_bars(parquet: str, instrument: str, since: str | None = None,
                       until: str | None = None, oos_token: object | None = None):
    """Load the Donchian columns (plus base pricing) for one window.

    ``oos_token`` is required for any window that reaches the OOS holdout
    (the data-layer gate in :func:`strategy_lib.load_bars`); in-sample windows
    load with no token.
    """
    return strategy_lib.load_bars(
        parquet, instrument, feature_cols=["dc_mid_24", "dc_upper_24"],
        not_null_cols=["dc_mid_24", "dc_upper_24"],
        since=since, until=until, oos_token=oos_token)


def run_donchian(
    parquet: str,
    instrument: str,
    timeframe: str = "5m",
    since: str | None = None,
    until: str | None = None,
    cost_bps: float = COST_BPS,
    entry_guard: bool = False,
    th: float = 0.0,
    oos_token: object | None = None,
) -> dict:
    """Run the S-14 rule for one instrument / window / cost tier.

    Returns the full result dict (metadata + engine metrics + distribution).
    """
    df = load_donchian_bars(parquet, instrument, since, until, oos_token=oos_token)
    if len(df) < 1_000:
        raise SystemExit(f"Only {len(df)} bars loaded for {instrument} "
                         f"(window {since or 'start'}..{until or 'latest'}); not enough to backtest.")

    bars = make_bars(df, timeframe, entry_guard=entry_guard)
    meta = {
        "strategy_id": "S-14",
        "instrument": instrument,
        "timeframe": timeframe,
        "window_since": since,
        "window_until": until,
        "start": str(df["time"].iloc[0]),
        "end": str(df["time"].iloc[-1]),
        "cost_bps": cost_bps,
        "entry_guard": "off" if not entry_guard else "gap_bar|near_market_close",
        "th": th,
    }
    return run_strategy(build_rule(df, th), bars, cost_bps, long_only=True, meta=meta)


def run(
    parquet: str,
    instrument: str,
    timeframe: str = "5m",
    since: str | None = None,
    until: str | None = None,
    cost_bps: float = COST_BPS,
    entry_guard: bool = False,
    th: float = 0.0,
    oos_token: object | None = None,
) -> dict:
    """Matrix-runner entry point (keyword-compatible with :func:`run_donchian`)."""
    return run_donchian(parquet, instrument, timeframe, since, until, cost_bps,
                        entry_guard, th, oos_token=oos_token)


__all__ = [
    "DonchianState",
    "build_rule",
    "load_donchian_bars",
    "run_donchian",
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
