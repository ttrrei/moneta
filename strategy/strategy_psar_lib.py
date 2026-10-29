"""S-13 Parabolic-SAR 0.01/0.1 direction follower (signal only).

Data loading, the timeframe guard, and the shared accounting/metrics live in
:mod:`strategy.strategy_lib` / :mod:`strategy.engine`; this file only declares
the signal and the run wrapper (same contract as S-05/S-06/S-07).

Base rule (long-only, 5m): hold long while the *previous closed bar's*
``psar_dir_0p01_0p1`` (slow step / fast acceleration) is up; flat when down.
Distinct from S-05 (SuperTrend): a different trend engine (Parabolic SAR with
a *slower* acceleration — 0.01 step, 0.1 max — so it flips materially less
often than ``st_dir_24_2``). ``psar_dir_0p01_0p1`` is computed and tested in
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
DIR_COL = "psar_dir_0p01_0p1"


class PsarState:
    """Slow Parabolic-SAR direction follower, long-only.

    ``desired_position(i)`` = the position to hold at the open of bar ``i``,
    decided from the direction on the *previous* closed bar ``i-1``.
    ``up_th`` / ``down_th`` allow hysteresis variants (the direction column is
    +1 / -1, so ``up_th=0.5, down_th=-0.5`` is the plain rule).
    """

    def __init__(self, direction: np.ndarray,
                 up_th: float = 0.5, down_th: float = -0.5) -> None:
        self.direction = direction
        self.up_th = up_th
        self.down_th = down_th
        self.state = 0

    def desired_position(self, i: int) -> int:
        if i == 0:
            return 0
        d = self.direction[i - 1]
        if np.isfinite(d):
            if d > self.up_th:
                self.state = 1
            elif d < self.down_th:
                self.state = 0
        return self.state


def build_rule(df, up_th: float = 0.5, down_th: float = -0.5) -> "PsarState":
    return PsarState(df[DIR_COL].to_numpy(np.float64), up_th=up_th, down_th=down_th)


def load_psar_bars(parquet: str, instrument: str, since: str | None = None,
                   until: str | None = None, oos_token: object | None = None):
    """Load the PSAR-direction column (plus base pricing) for one window.

    ``oos_token`` is required for any window that reaches the OOS holdout
    (the data-layer gate in :func:`strategy_lib.load_bars`); in-sample windows
    load with no token.
    """
    return strategy_lib.load_bars(
        parquet, instrument, feature_cols=[DIR_COL], not_null_cols=[DIR_COL],
        since=since, until=until, oos_token=oos_token)


def run_psar(
    parquet: str,
    instrument: str,
    timeframe: str = "5m",
    since: str | None = None,
    until: str | None = None,
    cost_bps: float = COST_BPS,
    entry_guard: bool = False,
    up_th: float = 0.5,
    down_th: float = -0.5,
    oos_token: object | None = None,
) -> dict:
    """Run the S-13 rule for one instrument / window / cost tier.

    Returns the full result dict (metadata + engine metrics + distribution).
    """
    df = load_psar_bars(parquet, instrument, since, until, oos_token=oos_token)
    if len(df) < 1_000:
        raise SystemExit(f"Only {len(df)} bars loaded for {instrument} "
                         f"(window {since or 'start'}..{until or 'latest'}); not enough to backtest.")

    bars = make_bars(df, timeframe, entry_guard=entry_guard)
    meta = {
        "strategy_id": "S-13",
        "instrument": instrument,
        "timeframe": timeframe,
        "window_since": since,
        "window_until": until,
        "start": str(df["time"].iloc[0]),
        "end": str(df["time"].iloc[-1]),
        "cost_bps": cost_bps,
        "entry_guard": "off" if not entry_guard else "gap_bar|near_market_close",
        "up_th": up_th,
        "down_th": down_th,
    }
    return run_strategy(build_rule(df, up_th, down_th), bars,
                        cost_bps, long_only=True, meta=meta)


def run(
    parquet: str,
    instrument: str,
    timeframe: str = "5m",
    since: str | None = None,
    until: str | None = None,
    cost_bps: float = COST_BPS,
    entry_guard: bool = False,
    up_th: float = 0.5,
    down_th: float = -0.5,
    oos_token: object | None = None,
) -> dict:
    """Matrix-runner entry point (keyword-compatible with :func:`run_psar`)."""
    return run_psar(parquet, instrument, timeframe, since, until, cost_bps,
                    entry_guard, up_th, down_th, oos_token=oos_token)


__all__ = [
    "PsarState",
    "build_rule",
    "load_psar_bars",
    "run_psar",
    "run",
    "DIR_COL",
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
