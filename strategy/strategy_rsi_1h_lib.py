"""S-02 RSI mean-reversion (1h) as a reusable library (signal only).

The *rule* is identical to S-01 (RSI-24 < 30 in, > 55 out, long-only) — the
only difference is the **timeframe**: S-02 evaluates it on **1h** bars instead
of 5m, which is ~1/12 the trade count and ~1/12 the cost (the "slow the signal"
hypothesis from the S-01 report §5, and the cheapest test of it in the registry).

Data loading, the timeframe guard, and the shared accounting/metrics all live in
:mod:`strategy.strategy_lib` / :mod:`strategy.engine`; this file only declares
the signal and the run wrapper, so the CLI and the matrix runner call the exact
same code path as every other strategy.

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

RSI_COL = "rsi_24"
COST_BPS = 2.0  # one-way transaction cost, basis points (same convention as S-01)


def build_rule(df) -> "RsiState":
    return RsiState(df[RSI_COL].to_numpy(np.float64))


def load_rsi_1h_bars(parquet: str, instrument: str, since: str | None = None,
                     until: str | None = None):
    """Load the RSI column (plus base pricing) for one window."""
    return strategy_lib.load_bars(
        parquet, instrument, feature_cols=[RSI_COL], not_null_cols=[RSI_COL],
        since=since, until=until)


class RsiState:
    """Long-only RSI-24 mean-reversion signal (the S-01/S-02 rule).

    ``desired_position(i)`` = the position to hold at the open of bar ``i``,
    decided from the RSI value on the *previous* closed bar ``i-1``.
    """

    def __init__(self, rsi: np.ndarray) -> None:
        self.rsi = rsi
        self.state = 0  # 0 flat, 1 long

    def desired_position(self, i: int) -> int:
        if i == 0:
            return 0
        r = self.rsi[i - 1]
        if np.isfinite(r):
            if r < 30.0:
                self.state = 1
            elif r > 55.0:
                self.state = 0
        return self.state


def run_rsi_1h(
    parquet: str,
    instrument: str,
    timeframe: str = "1h",
    since: str | None = None,
    until: str | None = None,
    cost_bps: float = COST_BPS,
    entry_guard: bool = False,
    oos_token: object | None = None,
) -> dict:
    """Run the S-02 rule for one instrument / window / cost tier.

    ``entry_guard`` defaults to OFF to match the S-01 baseline convention.
    ``oos_token`` is required for a window that reaches the OOS holdout (the
    data-layer gate). Returns the full result dict (metadata + engine metrics
    + distribution).
    """
    df = load_rsi_1h_bars(parquet, instrument, since, until, oos_token=oos_token)
    if len(df) < 1_000:
        raise SystemExit(f"Only {len(df)} bars loaded for {instrument} "
                         f"(window {since or 'start'}..{until or 'latest'}); not enough to backtest.")

    bars = make_bars(df, timeframe, entry_guard=entry_guard)
    meta = {
        "strategy_id": "S-02",
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
    timeframe: str = "1h",
    since: str | None = None,
    until: str | None = None,
    cost_bps: float = COST_BPS,
    entry_guard: bool = False,
    oos_token: object | None = None,
) -> dict:
    """Matrix-runner entry point (keyword-compatible with :func:`run_rsi_1h`)."""
    return run_rsi_1h(parquet, instrument, timeframe, since, until,
                      cost_bps, entry_guard, oos_token=oos_token)


__all__ = [
    "RsiState",
    "build_rule",
    "load_rsi_1h_bars",
    "run_rsi_1h",
    "run",
    "RSI_COL",
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
