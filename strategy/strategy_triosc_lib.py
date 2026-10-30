"""S-97 Triple-oscillator confluence (signal only).

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


class TriOscState:
    """"""

    def __init__(self, r: np.ndarray, k: np.ndarray, m: np.ndarray, r_in: float = 55.0, r_exit: float = 45.0, k_in: float = 55.0, k_exit: float = 45.0, m_in: float = 55.0, m_exit: float = 45.0, ema_gate: bool = False, gate_ema: np.ndarray | None = None, gate_close: np.ndarray | None = None) -> None:
        self.r = r
        self.k = k
        self.m = m
        self.r_in = r_in
        self.r_exit = r_exit
        self.k_in = k_in
        self.k_exit = k_exit
        self.m_in = m_in
        self.m_exit = m_exit
        self.ema_gate = ema_gate
        self.gate_ema = gate_ema
        self.gate_close = gate_close
        self.state = 0

    def desired_position(self, i: int) -> int:
        if i == 0:
            return 0
        j = i - 1
        if not np.isfinite(self.r[j]):
            return self.state
        if not np.isfinite(self.k[j]):
            return self.state
        if not np.isfinite(self.m[j]):
            return self.state

        if self.ema_gate and self.gate_close is not None and self.gate_ema is not None and self.state == 0:
            if (np.isfinite(self.gate_close[j]) and np.isfinite(self.gate_ema[j])
                    and self.gate_close[j] <= self.gate_ema[j]):
                return self.state
        if self.state == 0:
            prev_ok = (self.r[j-1] > self.r_in and self.k[j-1] > self.k_in and self.m[j-1] > self.m_in) if j >= 1 else False
            if self.r[j] > self.r_in and self.k[j] > self.k_in and self.m[j] > self.m_in and not prev_ok:
                self.state = 1

        elif (self.r[j] < self.r_exit) or (self.k[j] < self.k_exit) or (self.m[j] < self.m_exit):
            self.state = 0
        return self.state


def build_rule(df, ema_gate: bool = False, r_in: float = 55.0, r_exit: float = 45.0, k_in: float = 55.0, k_exit: float = 45.0, m_in: float = 55.0, m_exit: float = 45.0) -> "TriOscState":
    return TriOscState(df["rsi_12"].to_numpy(np.float64), df["stoch_k_12"].to_numpy(np.float64), df["mfi_12"].to_numpy(np.float64), ema_gate=ema_gate,
                 gate_ema=df["ema_24"].to_numpy(np.float64),
                 gate_close=df["close"].to_numpy(np.float64), r_in=r_in, r_exit=r_exit, k_in=k_in, k_exit=k_exit, m_in=m_in, m_exit=m_exit)


def load_triosc_bars(parquet: str, instrument: str, since: str | None = None,
                     until: str | None = None, oos_token: object | None = None):
    """Load the rsi_12, stoch_k_12, mfi_12, ema_24 column(s) (plus base pricing) for one window.

    ``oos_token`` is required for any window that reaches the OOS holdout
    (the data-layer gate in :func:`strategy_lib.load_bars`); in-sample windows
    load with no token.
    """
    return strategy_lib.load_bars(
        parquet, instrument, feature_cols=['rsi_12', 'stoch_k_12', 'mfi_12', 'ema_24'],
        not_null_cols=['rsi_12', 'stoch_k_12', 'mfi_12'],
        since=since, until=until, oos_token=oos_token)


def run_triosc(
    parquet: str,
    instrument: str,
    timeframe: str = "5m",
    since: str | None = None,
    until: str | None = None,
    cost_bps: float = COST_BPS,
    entry_guard: bool = False,
    ema_gate: bool = False,
    r_in: float = 55.0,
    r_exit: float = 45.0,
    k_in: float = 55.0,
    k_exit: float = 45.0,
    m_in: float = 55.0,
    m_exit: float = 45.0,

    oos_token: object | None = None,
) -> dict:
    """Run the S-97 rule for one instrument / window / cost tier.

    Returns the full result dict (metadata + engine metrics + distribution).
    """
    df = load_triosc_bars(parquet, instrument, since, until, oos_token=oos_token)
    if len(df) < 1_000:
        raise SystemExit(f"Only {len(df)} bars loaded for {instrument} "
                         f"(window {since or 'start'}..{until or 'latest'}); not enough to backtest.")

    bars = make_bars(df, timeframe, entry_guard=entry_guard)
    meta = {
        "strategy_id": "S-97",
        "instrument": instrument,
        "timeframe": timeframe,
        "window_since": since,
        "window_until": until,
        "start": str(df["time"].iloc[0]),
        "end": str(df["time"].iloc[-1]),
        "cost_bps": cost_bps,
        "entry_guard": "off" if not entry_guard else "gap_bar|near_market_close",
        "ema_gate": ema_gate,
        "r_in": r_in,
        "r_exit": r_exit,
        "k_in": k_in,
        "k_exit": k_exit,
        "m_in": m_in,
        "m_exit": m_exit,

    }
    return run_strategy(build_rule(df, ema_gate=ema_gate, r_in=r_in, r_exit=r_exit, k_in=k_in, k_exit=k_exit, m_in=m_in, m_exit=m_exit), bars, cost_bps,
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
    r_in: float = 55.0,
    r_exit: float = 45.0,
    k_in: float = 55.0,
    k_exit: float = 45.0,
    m_in: float = 55.0,
    m_exit: float = 45.0,

    oos_token: object | None = None,
) -> dict:
    """Matrix-runner entry point (keyword-compatible with :func:`run_triosc`)."""
    return run_triosc(parquet, instrument, timeframe, since, until, cost_bps,
                      entry_guard, ema_gate, r_in, r_exit, k_in, k_exit, m_in, m_exit, oos_token=oos_token)


__all__ = [
    "TriOscState",
    "build_rule",
    "load_triosc_bars",
    "run_triosc",
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
