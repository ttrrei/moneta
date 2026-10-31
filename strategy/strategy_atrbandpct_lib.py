"""S-30 ATR-band EMA-distance turn (signal only).

Data loading, the timeframe guard, and the shared accounting/metrics live in
:mod:`strategy.strategy_lib` / :mod:`strategy.engine`; this file only declares
the signal and the run wrapper (same contract as S-05/S-06/S-07).

Base rule (long-only): enter long when the *previous closed bar's* ``ema_dist_24`` (close distance from ``ema_24``, ATR-normalised — the derived scale-free distance no earlier strategy used) up-crosses ``k_in`` (a fresh turn, not a stale level); exit when it falls below ``k_exit``. Distinct from S-24 (band level follower: hold whenever distance >= k) — S-30 trades the *turn* of the distance with hysteresis exits.

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


class AtrBandPctState:
    """ATR-band EMA-distance turn, long-only.
    ``desired_position(i)`` = the position to hold at the open of bar ``i``,
    decided from the *previous* closed bar ``i-1``:
    * enter long: prev ``ema_dist_24`` > ``k_in`` (fresh up-cross);
    * exit:       prev ``ema_dist_24`` < ``k_exit``."""

    def __init__(self, dist: np.ndarray, k_in: float = 1.0, k_exit: float = 0.0, ema_gate: bool = False, gate_ema: np.ndarray | None = None, gate_close: np.ndarray | None = None) -> None:
        self.dist = dist
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
        if not np.isfinite(self.dist[j]):
            return self.state

        if self.state == 0 and not strategy_lib.entry_gate_allows(
                self.ema_gate, self.gate_close, self.gate_ema, j):
            return self.state
        if self.state == 0:
            prev = self.dist[j - 1] if j >= 1 else np.nan
            if self.dist[j] > self.k_in and (not np.isfinite(prev) or prev <= self.k_in):
                self.state = 1

        elif self.dist[j] < self.k_exit:
            self.state = 0
        return self.state


def build_rule(df, ema_gate: bool = False, k_in: float = 1.0, k_exit: float = 0.0) -> "AtrBandPctState":
    return AtrBandPctState(df["ema_dist_24"].to_numpy(np.float64), ema_gate=ema_gate,
                 gate_ema=df["ema_24"].to_numpy(np.float64),
                 gate_close=df["close"].to_numpy(np.float64), k_in=k_in, k_exit=k_exit)


def load_atrbandpct_bars(parquet: str, instrument: str, since: str | None = None,
                     until: str | None = None, oos_token: object | None = None):
    """Load the ema_dist_24, ema_24 column(s) (plus base pricing) for one window.

    ``oos_token`` is required for any window that reaches the OOS holdout
    (the data-layer gate in :func:`strategy_lib.load_bars`); in-sample windows
    load with no token.
    """
    return strategy_lib.load_bars(
        parquet, instrument, feature_cols=['ema_dist_24', 'ema_24'],
        not_null_cols=['ema_dist_24'],
        since=since, until=until, oos_token=oos_token)


def run_atrbandpct(
    parquet: str,
    instrument: str,
    timeframe: str = "5m",
    since: str | None = None,
    until: str | None = None,
    cost_bps: float = COST_BPS,
    entry_guard: bool = False,
    ema_gate: bool = False,
    k_in: float = 1.0,
    k_exit: float = 0.0,

    oos_token: object | None = None,
) -> dict:
    """Run the S-30 rule for one instrument / window / cost tier.

    Returns the full result dict (metadata + engine metrics + distribution).
    """
    df = load_atrbandpct_bars(parquet, instrument, since, until, oos_token=oos_token)
    if len(df) < 1_000:
        raise SystemExit(f"Only {len(df)} bars loaded for {instrument} "
                         f"(window {since or 'start'}..{until or 'latest'}); not enough to backtest.")

    bars = make_bars(df, timeframe, entry_guard=entry_guard)
    meta = {
        "strategy_id": "S-30",
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
    k_in: float = 1.0,
    k_exit: float = 0.0,

    oos_token: object | None = None,
) -> dict:
    """Matrix-runner entry point (keyword-compatible with :func:`run_atrbandpct`)."""
    return run_atrbandpct(parquet, instrument, timeframe, since, until, cost_bps,
                      entry_guard, ema_gate, k_in, k_exit, oos_token=oos_token)


__all__ = [
    "AtrBandPctState",
    "build_rule",
    "load_atrbandpct_bars",
    "run_atrbandpct",
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
