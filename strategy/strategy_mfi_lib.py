"""S-16 Money-Flow-Index-24 exhaustion dip-buyer (signal only).

Data loading, the timeframe guard, and the shared accounting/metrics live in
:mod:`strategy.strategy_lib` / :mod:`strategy.engine`; this file only declares
the signal and the run wrapper (same contract as S-05/S-06/S-07).

Base rule (long-only, 5m): enter long when the *previous closed bar's*
``mfi_24`` (volume-weighted RSI) crosses from >= ``enter_below`` down below
it — a volume-confirmed dip — and exit when ``mfi_24`` >= ``exit_above``.
Distinct family from S-01 (price-only RSI): MFI weights price by *volume*,
so it marks exhaustion where volume actually shows up. ``mfi_24`` is computed
and tested in :mod:`pipeline.indicators`; no indicator code is duplicated here.

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


class MfiState:
    """MFI-24 volume-exhaustion dip-buyer, long-only.

    ``desired_position(i)`` = the position to hold at the open of bar ``i``,
    decided from indicators on the *previous* closed bar ``i-1`` (and the
    current bar's ``close`` / ``ema_24`` for the optional trend gate — both
    known at the bar's close, so no lookahead).

    * enter long: prev ``mfi`` crossed down through ``enter_below``;
    * exit:       prev ``mfi`` >= ``exit_above``;
    * optional:  ``ema_gate`` requires prev ``close`` > prev ``ema_24`` to enter.
    """

    def __init__(self, mfi: np.ndarray, close: np.ndarray, ema: np.ndarray,
                 enter_below: float = 20.0, exit_above: float = 50.0,
                 ema_gate: bool = False) -> None:
        self.mfi = mfi
        self.close = close
        self.ema = ema
        self.enter_below = enter_below
        self.exit_above = exit_above
        self.ema_gate = ema_gate
        self.state = 0

    def desired_position(self, i: int) -> int:
        if i == 0:
            return 0
        j = i - 1
        m = self.mfi[j]
        if not np.isfinite(m):
            return self.state
        if self.state == 0:
            m0 = self.mfi[j - 1] if j > 0 else np.nan
            crossed = m < self.enter_below and (m0 >= self.enter_below
                                                if np.isfinite(m0) else True)
            gate_ok = True
            if self.ema_gate:
                gate_ok = strategy_lib.entry_gate_allows(True, self.close, self.ema, j)
            if crossed and gate_ok:
                self.state = 1
        elif m >= self.exit_above:
            self.state = 0
        return self.state


def build_rule(df, enter_below: float = 20.0, exit_above: float = 50.0,
               ema_gate: bool = False) -> "MfiState":
    return MfiState(
        df["mfi_24"].to_numpy(np.float64),
        df["close"].to_numpy(np.float64),
        df["ema_24"].to_numpy(np.float64),
        enter_below=enter_below, exit_above=exit_above, ema_gate=ema_gate)


def load_mfi_bars(parquet: str, instrument: str, since: str | None = None,
                  until: str | None = None, oos_token: object | None = None):
    """Load the MFI column (plus base pricing) for one window.

    ``oos_token`` is required for any window that reaches the OOS holdout
    (the data-layer gate in :func:`strategy_lib.load_bars`); in-sample windows
    load with no token.
    """
    return strategy_lib.load_bars(
        parquet, instrument, feature_cols=["mfi_24", "ema_24"],
        not_null_cols=["mfi_24"],
        since=since, until=until, oos_token=oos_token)


def run_mfi(
    parquet: str,
    instrument: str,
    timeframe: str = "5m",
    since: str | None = None,
    until: str | None = None,
    cost_bps: float = COST_BPS,
    entry_guard: bool = False,
    enter_below: float = 20.0,
    exit_above: float = 50.0,
    ema_gate: bool = False,
    oos_token: object | None = None,
) -> dict:
    """Run the S-16 rule for one instrument / window / cost tier.

    Returns the full result dict (metadata + engine metrics + distribution).
    """
    df = load_mfi_bars(parquet, instrument, since, until, oos_token=oos_token)
    if len(df) < 1_000:
        raise SystemExit(f"Only {len(df)} bars loaded for {instrument} "
                         f"(window {since or 'start'}..{until or 'latest'}); not enough to backtest.")

    bars = make_bars(df, timeframe, entry_guard=entry_guard)
    meta = {
        "strategy_id": "S-16",
        "instrument": instrument,
        "timeframe": timeframe,
        "window_since": since,
        "window_until": until,
        "start": str(df["time"].iloc[0]),
        "end": str(df["time"].iloc[-1]),
        "cost_bps": cost_bps,
        "entry_guard": "off" if not entry_guard else "gap_bar|near_market_close",
        "enter_below": enter_below,
        "exit_above": exit_above,
        "ema_gate": ema_gate,
    }
    return run_strategy(build_rule(df, enter_below, exit_above, ema_gate),
                        bars, cost_bps, long_only=True, meta=meta)


def run(
    parquet: str,
    instrument: str,
    timeframe: str = "5m",
    since: str | None = None,
    until: str | None = None,
    cost_bps: float = COST_BPS,
    entry_guard: bool = False,
    enter_below: float = 20.0,
    exit_above: float = 50.0,
    ema_gate: bool = False,
    oos_token: object | None = None,
) -> dict:
    """Matrix-runner entry point (keyword-compatible with :func:`run_mfi`)."""
    return run_mfi(parquet, instrument, timeframe, since, until, cost_bps,
                   entry_guard, enter_below, exit_above, ema_gate,
                   oos_token=oos_token)


__all__ = [
    "MfiState",
    "build_rule",
    "load_mfi_bars",
    "run_mfi",
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
