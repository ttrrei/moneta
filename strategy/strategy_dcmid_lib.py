"""S-37 Donchian midline fresh-cross (signal only).

Data loading, the timeframe guard, and the shared accounting/metrics live in
:mod:`strategy.strategy_lib` / :mod:`strategy.engine`; this file only declares
the signal and the run wrapper (same contract as S-05/S-06/S-07).

Base rule (long-only): enter long on the *fresh* up-cross of ``dc_mid_24`` (close vs the Donchian midline — the same reference line S-14 uses, but S-14 *holds* through all time above the line while S-37 only re-enters on a new cross, so its trade frequency and holding periods differ); exit when close falls back to/below ``dc_mid_24``.

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


class DcMidState:
    """Donchian midline fresh-cross, long-only.
    ``desired_position(i)`` = the position to hold at the open of bar ``i``,
    decided from the *previous* closed bar ``i-1``:
    * enter long: prev close_sig > prev ``dc_mid_24`` and the bar before had close_sig <= mid;
    * exit:       prev close_sig <= prev ``dc_mid_24``."""

    def __init__(self, close_sig: np.ndarray, mid: np.ndarray, ema_gate: bool = False, gate_ema: np.ndarray | None = None, gate_close: np.ndarray | None = None) -> None:
        self.close_sig = close_sig
        self.mid = mid
        self.ema_gate = ema_gate
        self.gate_ema = gate_ema
        self.gate_close = gate_close
        self.state = 0

    def desired_position(self, i: int) -> int:
        if i == 0:
            return 0
        j = i - 1
        if not np.isfinite(self.close_sig[j]):
            return self.state
        if not np.isfinite(self.mid[j]):
            return self.state
        if j >= 1:
            if not (np.isfinite(self.close_sig[j-1]) and np.isfinite(self.mid[j-1])):
                return self.state

        if self.state == 0 and not strategy_lib.entry_gate_allows(
                self.ema_gate, self.gate_close, self.gate_ema, j):
            return self.state
        if self.state == 0:
            if j >= 1 and self.close_sig[j] > self.mid[j] and self.close_sig[j-1] <= self.mid[j-1]:
                self.state = 1

        elif self.close_sig[j] <= self.mid[j]:
            self.state = 0
        return self.state


def build_rule(df, ema_gate: bool = False) -> "DcMidState":
    return DcMidState(df["close"].to_numpy(np.float64), df["dc_mid_24"].to_numpy(np.float64), ema_gate=ema_gate,
                 gate_ema=df["ema_24"].to_numpy(np.float64),
                 gate_close=df["close"].to_numpy(np.float64))


def load_dcmid_bars(parquet: str, instrument: str, since: str | None = None,
                     until: str | None = None, oos_token: object | None = None):
    """Load the dc_mid_24, ema_24 column(s) (plus base pricing) for one window.

    ``oos_token`` is required for any window that reaches the OOS holdout
    (the data-layer gate in :func:`strategy_lib.load_bars`); in-sample windows
    load with no token.
    """
    return strategy_lib.load_bars(
        parquet, instrument, feature_cols=['dc_mid_24', 'ema_24'],
        not_null_cols=['dc_mid_24'],
        since=since, until=until, oos_token=oos_token)


def run_dcmid(
    parquet: str,
    instrument: str,
    timeframe: str = "5m",
    since: str | None = None,
    until: str | None = None,
    cost_bps: float = COST_BPS,
    entry_guard: bool = False,
    ema_gate: bool = False,

    oos_token: object | None = None,
) -> dict:
    """Run the S-37 rule for one instrument / window / cost tier.

    Returns the full result dict (metadata + engine metrics + distribution).
    """
    df = load_dcmid_bars(parquet, instrument, since, until, oos_token=oos_token)
    if len(df) < 1_000:
        raise SystemExit(f"Only {len(df)} bars loaded for {instrument} "
                         f"(window {since or 'start'}..{until or 'latest'}); not enough to backtest.")

    bars = make_bars(df, timeframe, entry_guard=entry_guard)
    meta = {
        "strategy_id": "S-37",
        "instrument": instrument,
        "timeframe": timeframe,
        "window_since": since,
        "window_until": until,
        "start": str(df["time"].iloc[0]),
        "end": str(df["time"].iloc[-1]),
        "cost_bps": cost_bps,
        "entry_guard": "off" if not entry_guard else "gap_bar|near_market_close",
        "ema_gate": ema_gate,

    }
    return run_strategy(build_rule(df, ema_gate=ema_gate), bars, cost_bps,
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

    oos_token: object | None = None,
) -> dict:
    """Matrix-runner entry point (keyword-compatible with :func:`run_dcmid`)."""
    return run_dcmid(parquet, instrument, timeframe, since, until, cost_bps,
                      entry_guard, ema_gate, oos_token=oos_token)


__all__ = [
    "DcMidState",
    "build_rule",
    "load_dcmid_bars",
    "run_dcmid",
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
