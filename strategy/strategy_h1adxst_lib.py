"""S-67 1h ADX + 1h SuperTrend alignment (signal only).

Data loading, the timeframe guard, and the shared accounting/metrics live in
:mod:`strategy.strategy_lib` / :mod:`strategy.engine`; this file only declares
the signal and the run wrapper (same contract as S-05/S-06/S-07).



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


class H1AdxStState:
    """"""

    def __init__(self, a: np.ndarray, st1: np.ndarray, k_in: float = 25.0, k_exit: float = 20.0, ema_gate: bool = False, gate_ema: np.ndarray | None = None, gate_close: np.ndarray | None = None) -> None:
        self.a = a
        self.st1 = st1
        self.k_in = k_in
        self.k_exit = k_exit
        self.ema_gate = ema_gate
        self.gate_ema = gate_ema
        self.gate_close = gate_close
        self.state = 0

    def desired_position(self, i: int) -> int:
        if i == 0:
            return 0
        j = i - 1
        if not np.isfinite(self.a[j]):
            return self.state
        if not np.isfinite(self.st1[j]):
            return self.state
        if j >= 1:
            if not (np.isfinite(self.a[j-1]) and np.isfinite(self.st1[j-1])):
                return self.state

        if self.state == 0 and not strategy_lib.entry_gate_allows(
                self.ema_gate, self.gate_close, self.gate_ema, j):
            return self.state
        if self.state == 0:
            prev_ok = (self.a[j-1] > self.k_in and self.st1[j-1] > 0) if j >= 1 else False
            if self.a[j] > self.k_in and self.st1[j] > 0 and not prev_ok:
                self.state = 1

        elif (self.a[j] < self.k_exit) or (self.st1[j] <= 0):
            self.state = 0
        return self.state


def build_rule(df, ema_gate: bool = False, k_in: float = 25.0, k_exit: float = 20.0) -> "H1AdxStState":
    return H1AdxStState(df["h1_adx_24"].to_numpy(np.float64), df["h1_st_dir_24_3"].to_numpy(np.float64), ema_gate=ema_gate,
                 gate_ema=df["ema_24"].to_numpy(np.float64),
                 gate_close=df["close"].to_numpy(np.float64), k_in=k_in, k_exit=k_exit)


def load_h1adxst_bars(parquet: str, instrument: str, since: str | None = None,
                     until: str | None = None, oos_token: object | None = None):
    """Load the h1_adx_24, h1_st_dir_24_3, ema_24 column(s) (plus base pricing) for one window.

    ``oos_token`` is required for any window that reaches the OOS holdout
    (the data-layer gate in :func:`strategy_lib.load_bars`); in-sample windows
    load with no token.
    """
    return strategy_lib.load_bars(
        parquet, instrument, feature_cols=['h1_adx_24', 'h1_st_dir_24_3', 'ema_24'],
        not_null_cols=['h1_adx_24', 'h1_st_dir_24_3'],
        since=since, until=until, oos_token=oos_token)


def run_h1adxst(
    parquet: str,
    instrument: str,
    timeframe: str = "5m",
    since: str | None = None,
    until: str | None = None,
    cost_bps: float = COST_BPS,
    entry_guard: bool = False,
    ema_gate: bool = False,
    k_in: float = 25.0,
    k_exit: float = 20.0,

    oos_token: object | None = None,
) -> dict:
    """Run the S-67 rule for one instrument / window / cost tier.

    Returns the full result dict (metadata + engine metrics + distribution).
    """
    df = load_h1adxst_bars(parquet, instrument, since, until, oos_token=oos_token)
    if len(df) < 1_000:
        raise SystemExit(f"Only {len(df)} bars loaded for {instrument} "
                         f"(window {since or 'start'}..{until or 'latest'}); not enough to backtest.")

    bars = make_bars(df, timeframe, entry_guard=entry_guard)
    meta = {
        "strategy_id": "S-67",
        "instrument": instrument,
        "timeframe": timeframe,
        "window_since": since,
        "window_until": until,
        "start": str(df["time"].iloc[0]),
        "end": str(df["time"].iloc[-1]),
        "cost_bps": cost_bps,
        "entry_guard": "off" if not entry_guard else "gap_bar|near_market_close",
        "ema_gate": ema_gate,
        "k_in": k_in,
        "k_exit": k_exit,

    }
    return run_strategy(build_rule(df, ema_gate=ema_gate, k_in=k_in, k_exit=k_exit), bars, cost_bps,
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
    k_in: float = 25.0,
    k_exit: float = 20.0,

    oos_token: object | None = None,
) -> dict:
    """Matrix-runner entry point (keyword-compatible with :func:`run_h1adxst`)."""
    return run_h1adxst(parquet, instrument, timeframe, since, until, cost_bps,
                      entry_guard, ema_gate, k_in, k_exit, oos_token=oos_token)


__all__ = [
    "H1AdxStState",
    "build_rule",
    "load_h1adxst_bars",
    "run_h1adxst",
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
