"""S-35 Bollinger-width compression dip (signal only).

Data loading, the timeframe guard, and the shared accounting/metrics live in
:mod:`strategy.strategy_lib` / :mod:`strategy.engine`; this file only declares
the signal and the run wrapper (same contract as S-05/S-06/S-07).

Base rule (long-only): enter long when the *previous closed bar's* ``bb_width_24`` (normalised Bollinger band width — the squeeze *magnitude*, which S-04/S-21 only read as the on/off flag ``sqz_on``) down-crosses ``low`` (volatility compressing) **and** the close is within its band (``bb_pctb_24`` > 0); exit when the width expands back above ``high``.

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


class BbWidthTurnState:
    """Bollinger-width compression dip, long-only.
    ``desired_position(i)`` = the position to hold at the open of bar ``i``,
    decided from the *previous* closed bar ``i-1``:
    * enter long: prev ``bb_width_24`` < ``low`` (fresh) and prev ``bb_pctb_24`` > 0;
    * exit:       prev ``bb_width_24`` > ``high``."""

    def __init__(self, width: np.ndarray, pctb: np.ndarray, low: float = 0.03, high: float = 0.1, ema_gate: bool = False, gate_ema: np.ndarray | None = None, gate_close: np.ndarray | None = None) -> None:
        self.width = width
        self.pctb = pctb
        self.low = low
        self.high = high
        self.ema_gate = ema_gate
        self.gate_ema = gate_ema
        self.gate_close = gate_close
        self.state = 0

    def desired_position(self, i: int) -> int:
        if i == 0:
            return 0
        j = i - 1
        if not np.isfinite(self.width[j]):
            return self.state
        if not np.isfinite(self.pctb[j]):
            return self.state

        if self.ema_gate and self.gate_close is not None and self.gate_ema is not None and self.state == 0:
            if (np.isfinite(self.gate_close[j]) and np.isfinite(self.gate_ema[j])
                    and self.gate_close[j] <= self.gate_ema[j]):
                return self.state
        if self.state == 0:
            prev = self.width[j - 1] if j >= 1 else np.nan
            if self.width[j] < self.low and self.pctb[j] > 0 and (not np.isfinite(prev) or prev >= self.low):
                self.state = 1

        elif self.width[j] > self.high:
            self.state = 0
        return self.state


def build_rule(df, ema_gate: bool = False, low: float = 0.03, high: float = 0.1) -> "BbWidthTurnState":
    return BbWidthTurnState(df["bb_width_24"].to_numpy(np.float64), df["bb_pctb_24"].to_numpy(np.float64), ema_gate=ema_gate,
                 gate_ema=df["ema_24"].to_numpy(np.float64),
                 gate_close=df["close"].to_numpy(np.float64), low=low, high=high)


def load_bbwidth_bars(parquet: str, instrument: str, since: str | None = None,
                     until: str | None = None, oos_token: object | None = None):
    """Load the bb_width_24, bb_pctb_24, ema_24 column(s) (plus base pricing) for one window.

    ``oos_token`` is required for any window that reaches the OOS holdout
    (the data-layer gate in :func:`strategy_lib.load_bars`); in-sample windows
    load with no token.
    """
    return strategy_lib.load_bars(
        parquet, instrument, feature_cols=['bb_width_24', 'bb_pctb_24', 'ema_24'],
        not_null_cols=['bb_width_24', 'bb_pctb_24'],
        since=since, until=until, oos_token=oos_token)


def run_bbwidth(
    parquet: str,
    instrument: str,
    timeframe: str = "5m",
    since: str | None = None,
    until: str | None = None,
    cost_bps: float = COST_BPS,
    entry_guard: bool = False,
    ema_gate: bool = False,
    low: float = 0.03,
    high: float = 0.1,

    oos_token: object | None = None,
) -> dict:
    """Run the S-35 rule for one instrument / window / cost tier.

    Returns the full result dict (metadata + engine metrics + distribution).
    """
    df = load_bbwidth_bars(parquet, instrument, since, until, oos_token=oos_token)
    if len(df) < 1_000:
        raise SystemExit(f"Only {len(df)} bars loaded for {instrument} "
                         f"(window {since or 'start'}..{until or 'latest'}); not enough to backtest.")

    bars = make_bars(df, timeframe, entry_guard=entry_guard)
    meta = {
        "strategy_id": "S-35",
        "instrument": instrument,
        "timeframe": timeframe,
        "window_since": since,
        "window_until": until,
        "start": str(df["time"].iloc[0]),
        "end": str(df["time"].iloc[-1]),
        "cost_bps": cost_bps,
        "entry_guard": "off" if not entry_guard else "gap_bar|near_market_close",
        "ema_gate": ema_gate,
        "low": low,
        "high": high,

    }
    return run_strategy(build_rule(df, ema_gate=ema_gate, low=low, high=high), bars, cost_bps,
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
    low: float = 0.03,
    high: float = 0.1,

    oos_token: object | None = None,
) -> dict:
    """Matrix-runner entry point (keyword-compatible with :func:`run_bbwidth`)."""
    return run_bbwidth(parquet, instrument, timeframe, since, until, cost_bps,
                      entry_guard, ema_gate, low, high, oos_token=oos_token)


__all__ = [
    "BbWidthTurnState",
    "build_rule",
    "load_bbwidth_bars",
    "run_bbwidth",
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
