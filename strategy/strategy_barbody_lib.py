"""S-42 Bar-body momentum turn (signal only).

Data loading, the timeframe guard, and the shared accounting/metrics live in
:mod:`strategy.strategy_lib` / :mod:`strategy.engine`; this file only declares
the signal and the run wrapper (same contract as S-05/S-06/S-07).

Base rule (long-only): enter long when the *previous closed bar's* ``bar_body_ratio`` (body / range, 0..1 — a no-window *candle structure* feature; high values are close-driven, near-unidirectional bars, a feature no earlier strategy used) up-crosses ``k_in`` (a fresh strong body, not a stale one); exit when it falls below ``k_exit``. Distinct from S-28 (which trades the close *location* ``bar_clv``): S-42 trades bar-body *size* (conviction), not position.

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


class BarBodyState:
    """Bar-body momentum turn, long-only.
    ``desired_position(i)`` = the position to hold at the open of bar ``i``,
    decided from the *previous* closed bar ``i-1``:
    * enter long: prev ``bar_body_ratio`` > ``k_in`` (fresh up-cross);
    * exit:       prev ``bar_body_ratio`` < ``k_exit``."""

    def __init__(self, body: np.ndarray, k_in: float = 0.6, k_exit: float = 0.3, ema_gate: bool = False, gate_ema: np.ndarray | None = None, gate_close: np.ndarray | None = None) -> None:
        self.body = body
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
        if not np.isfinite(self.body[j]):
            return self.state

        if self.ema_gate and self.gate_close is not None and self.gate_ema is not None and self.state == 0:
            if (np.isfinite(self.gate_close[j]) and np.isfinite(self.gate_ema[j])
                    and self.gate_close[j] <= self.gate_ema[j]):
                return self.state
        if self.state == 0:
            prev = self.body[j - 1] if j >= 1 else np.nan
            if self.body[j] > self.k_in and (not np.isfinite(prev) or prev <= self.k_in):
                self.state = 1

        elif self.body[j] < self.k_exit:
            self.state = 0
        return self.state


def build_rule(df, ema_gate: bool = False, k_in: float = 0.6, k_exit: float = 0.3) -> "BarBodyState":
    return BarBodyState(df["bar_body_ratio"].to_numpy(np.float64), ema_gate=ema_gate,
                 gate_ema=df["ema_24"].to_numpy(np.float64),
                 gate_close=df["close"].to_numpy(np.float64), k_in=k_in, k_exit=k_exit)


def load_barbody_bars(parquet: str, instrument: str, since: str | None = None,
                     until: str | None = None, oos_token: object | None = None):
    """Load the bar_body_ratio, ema_24 column(s) (plus base pricing) for one window.

    ``oos_token`` is required for any window that reaches the OOS holdout
    (the data-layer gate in :func:`strategy_lib.load_bars`); in-sample windows
    load with no token.
    """
    return strategy_lib.load_bars(
        parquet, instrument, feature_cols=['bar_body_ratio', 'ema_24'],
        not_null_cols=['bar_body_ratio'],
        since=since, until=until, oos_token=oos_token)


def run_barbody(
    parquet: str,
    instrument: str,
    timeframe: str = "5m",
    since: str | None = None,
    until: str | None = None,
    cost_bps: float = COST_BPS,
    entry_guard: bool = False,
    ema_gate: bool = False,
    k_in: float = 0.6,
    k_exit: float = 0.3,

    oos_token: object | None = None,
) -> dict:
    """Run the S-42 rule for one instrument / window / cost tier.

    Returns the full result dict (metadata + engine metrics + distribution).
    """
    df = load_barbody_bars(parquet, instrument, since, until, oos_token=oos_token)
    if len(df) < 1_000:
        raise SystemExit(f"Only {len(df)} bars loaded for {instrument} "
                         f"(window {since or 'start'}..{until or 'latest'}); not enough to backtest.")

    bars = make_bars(df, timeframe, entry_guard=entry_guard)
    meta = {
        "strategy_id": "S-42",
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
    k_in: float = 0.6,
    k_exit: float = 0.3,

    oos_token: object | None = None,
) -> dict:
    """Matrix-runner entry point (keyword-compatible with :func:`run_barbody`)."""
    return run_barbody(parquet, instrument, timeframe, since, until, cost_bps,
                      entry_guard, ema_gate, k_in, k_exit, oos_token=oos_token)


__all__ = [
    "BarBodyState",
    "build_rule",
    "load_barbody_bars",
    "run_barbody",
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
