"""S-31 Supertrend-distance follower (signal only).

Data loading, the timeframe guard, and the shared accounting/metrics live in
:mod:`strategy.strategy_lib` / :mod:`strategy.engine`; this file only declares
the signal and the run wrapper (same contract as S-05/S-06/S-07).

Base rule (long-only): hold long while the *previous closed bar's* ``st_dist_24_2`` (close distance from the SuperTrend line, ATR-normalised and side-signed — a derived column no earlier strategy used) stays above ``th_in``; exit when it falls below ``th_exit``. Distinct from S-05/S-20 (which follow the SuperTrend *direction*): S-31 trades the signed *distance to the stop line*.

The optional ``ema_gate`` (available on every batch-3 strategy as an
improvement-iteration knob) blocks a *fresh* entry while the previous closed
bar's close is at/below ``ema_24``; it never blocks an exit.

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


class StDistTrendState:
    """Supertrend-distance follower, long-only.
    ``desired_position(i)`` = the position to hold at the open of bar ``i``,
    decided from the *previous* closed bar ``i-1``:
    * hold long: prev ``st_dist_24_2`` > ``th_in``;
    * exit:      prev ``st_dist_24_2`` < ``th_exit`` (hysteresis)."""

    def __init__(self, st: np.ndarray, th_in: float = 0.5, th_exit: float = -0.5, ema_gate: bool = False, gate_ema: np.ndarray | None = None, gate_close: np.ndarray | None = None) -> None:
        self.st = st
        self.th_in = th_in
        self.th_exit = th_exit
        self.ema_gate = ema_gate
        self.gate_ema = gate_ema
        self.gate_close = gate_close
        self.state = 0

    def desired_position(self, i: int) -> int:
        if i == 0:
            return 0
        j = i - 1
        if not np.isfinite(self.st[j]):
            return self.state

        if self.ema_gate and self.gate_close is not None and self.gate_ema is not None and self.state == 0:
            if (np.isfinite(self.gate_close[j]) and np.isfinite(self.gate_ema[j])
                    and self.gate_close[j] <= self.gate_ema[j]):
                return self.state
        if self.state == 0:
            if self.st[j] > self.th_in:
                self.state = 1

        elif self.st[j] < self.th_exit:
            self.state = 0
        return self.state


def build_rule(df, ema_gate: bool = False, th_in: float = 0.5, th_exit: float = -0.5) -> "StDistTrendState":
    return StDistTrendState(df["st_dist_24_2"].to_numpy(np.float64), ema_gate=ema_gate,
                 gate_ema=df["ema_24"].to_numpy(np.float64),
                 gate_close=df["close"].to_numpy(np.float64), th_in=th_in, th_exit=th_exit)


def load_stdist_bars(parquet: str, instrument: str, since: str | None = None,
                     until: str | None = None, oos_token: object | None = None):
    """Load the st_dist_24_2, ema_24 column(s) (plus base pricing) for one window.

    ``oos_token`` is required for any window that reaches the OOS holdout
    (the data-layer gate in :func:`strategy_lib.load_bars`); in-sample windows
    load with no token.
    """
    return strategy_lib.load_bars(
        parquet, instrument, feature_cols=['st_dist_24_2', 'ema_24'],
        not_null_cols=['st_dist_24_2'],
        since=since, until=until, oos_token=oos_token)


def run_stdist(
    parquet: str,
    instrument: str,
    timeframe: str = "5m",
    since: str | None = None,
    until: str | None = None,
    cost_bps: float = COST_BPS,
    entry_guard: bool = False,
    ema_gate: bool = False,
    th_in: float = 0.5,
    th_exit: float = -0.5,

    oos_token: object | None = None,
) -> dict:
    """Run the S-31 rule for one instrument / window / cost tier.

    Returns the full result dict (metadata + engine metrics + distribution).
    """
    df = load_stdist_bars(parquet, instrument, since, until, oos_token=oos_token)
    if len(df) < 1_000:
        raise SystemExit(f"Only {len(df)} bars loaded for {instrument} "
                         f"(window {since or 'start'}..{until or 'latest'}); not enough to backtest.")

    bars = make_bars(df, timeframe, entry_guard=entry_guard)
    meta = {
        "strategy_id": "S-31",
        "instrument": instrument,
        "timeframe": timeframe,
        "window_since": since,
        "window_until": until,
        "start": str(df["time"].iloc[0]),
        "end": str(df["time"].iloc[-1]),
        "cost_bps": cost_bps,
        "entry_guard": "off" if not entry_guard else "gap_bar|near_market_close",
        "ema_gate": ema_gate,
        "th_in": th_in,
        "th_exit": th_exit,

    }
    return run_strategy(build_rule(df, ema_gate=ema_gate, th_in=th_in, th_exit=th_exit), bars, cost_bps,
                        long_only=True, meta=meta)


def run(
    parquet: str,
    instrument: str,
    timeframe: str = "5m",
    since: str | None = None,
    until: str | None = None,
    cost_bps: float = COST_BPS,
    entry_guard: bool = False,
    ema_gate: bool = False,
    th_in: float = 0.5,
    th_exit: float = -0.5,

    oos_token: object | None = None,
) -> dict:
    """Matrix-runner entry point (keyword-compatible with :func:`run_stdist`)."""
    return run_stdist(parquet, instrument, timeframe, since, until, cost_bps,
                      entry_guard, ema_gate, th_in, th_exit, oos_token=oos_token)


__all__ = [
    "StDistTrendState",
    "build_rule",
    "load_stdist_bars",
    "run_stdist",
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
