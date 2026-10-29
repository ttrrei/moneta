"""S-15 Aroon-24 fresh-trend buyer (signal only).

Data loading, the timeframe guard, and the shared accounting/metrics live in
:mod:`strategy.strategy_lib` / :mod:`strategy.engine`; this file only declares
the signal and the run wrapper (same contract as S-05/S-06/S-07).

Base rule (long-only, 5m): enter long when the *previous closed bar's*
``aroon_up_24`` crosses up through ``up_at`` (a fresh 24-bar high just
printed) while ``aroon_down_24`` < ``down_below`` (no fresh 24-bar low
competing); exit when ``aroon_up_24`` falls back to/below ``up_exit``.
Distinct from every prior strategy: an *Aroon* freshness pair — neither a
momentum oscillator, a channel, nor a trend engine. Both columns are computed
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


class AroonState:
    """Aroon-24 fresh-trend buyer, long-only.

    ``desired_position(i)`` = the position to hold at the open of bar ``i``,
    decided from indicators on the *previous* closed bar ``i-1`` (and the
    current bar's ``close`` / ``ema_24`` for the optional trend gate — both
    known at the bar's close, so no lookahead).

    * enter long: prev ``aroon_up`` crossed up through ``up_at`` while prev
      ``aroon_down`` < ``down_below``;
    * exit:       prev ``aroon_up`` <= ``up_exit``;
    * optional:  ``ema_gate`` requires prev ``close`` > prev ``ema_24`` to enter.
    """

    def __init__(self, up: np.ndarray, down: np.ndarray, close: np.ndarray,
                 ema: np.ndarray, up_at: float = 70.0, up_exit: float = 70.0,
                 down_below: float = 30.0, ema_gate: bool = False) -> None:
        self.up = up
        self.down = down
        self.close = close
        self.ema = ema
        self.up_at = up_at
        self.up_exit = up_exit
        self.down_below = down_below
        self.ema_gate = ema_gate
        self.state = 0

    def desired_position(self, i: int) -> int:
        if i == 0:
            return 0
        j = i - 1
        u = self.up[j]
        if not np.isfinite(u):
            return self.state
        if self.state == 0:
            u0 = self.up[j - 1] if j > 0 else np.nan
            crossed = u >= self.up_at and (u0 < self.up_at if np.isfinite(u0) else True)
            d = self.down[j]
            down_ok = (d < self.down_below) if np.isfinite(d) else False
            gate_ok = True
            if self.ema_gate and np.isfinite(self.ema[j]):
                gate_ok = self.close[j] > self.ema[j]
            if crossed and down_ok and gate_ok:
                self.state = 1
        elif u <= self.up_exit:
            self.state = 0
        return self.state


def build_rule(df, up_at: float = 70.0, up_exit: float = 70.0,
               down_below: float = 30.0, ema_gate: bool = False) -> "AroonState":
    return AroonState(
        df["aroon_up_24"].to_numpy(np.float64),
        df["aroon_down_24"].to_numpy(np.float64),
        df["close"].to_numpy(np.float64),
        df["ema_24"].to_numpy(np.float64),
        up_at=up_at, up_exit=up_exit, down_below=down_below, ema_gate=ema_gate)


def load_aroon_bars(parquet: str, instrument: str, since: str | None = None,
                    until: str | None = None, oos_token: object | None = None):
    """Load the Aroon columns (plus base pricing) for one window.

    ``oos_token`` is required for any window that reaches the OOS holdout
    (the data-layer gate in :func:`strategy_lib.load_bars`); in-sample windows
    load with no token.
    """
    return strategy_lib.load_bars(
        parquet, instrument,
        feature_cols=["aroon_up_24", "aroon_down_24", "ema_24"],
        not_null_cols=["aroon_up_24", "aroon_down_24"],
        since=since, until=until, oos_token=oos_token)


def run_aroon(
    parquet: str,
    instrument: str,
    timeframe: str = "5m",
    since: str | None = None,
    until: str | None = None,
    cost_bps: float = COST_BPS,
    entry_guard: bool = False,
    up_at: float = 70.0,
    up_exit: float = 70.0,
    down_below: float = 30.0,
    ema_gate: bool = False,
    oos_token: object | None = None,
) -> dict:
    """Run the S-15 rule for one instrument / window / cost tier.

    Returns the full result dict (metadata + engine metrics + distribution).
    """
    df = load_aroon_bars(parquet, instrument, since, until, oos_token=oos_token)
    if len(df) < 1_000:
        raise SystemExit(f"Only {len(df)} bars loaded for {instrument} "
                         f"(window {since or 'start'}..{until or 'latest'}); not enough to backtest.")

    bars = make_bars(df, timeframe, entry_guard=entry_guard)
    meta = {
        "strategy_id": "S-15",
        "instrument": instrument,
        "timeframe": timeframe,
        "window_since": since,
        "window_until": until,
        "start": str(df["time"].iloc[0]),
        "end": str(df["time"].iloc[-1]),
        "cost_bps": cost_bps,
        "entry_guard": "off" if not entry_guard else "gap_bar|near_market_close",
        "up_at": up_at,
        "up_exit": up_exit,
        "down_below": down_below,
        "ema_gate": ema_gate,
    }
    return run_strategy(build_rule(df, up_at, up_exit, down_below, ema_gate),
                        bars, cost_bps, long_only=True, meta=meta)


def run(
    parquet: str,
    instrument: str,
    timeframe: str = "5m",
    since: str | None = None,
    until: str | None = None,
    cost_bps: float = COST_BPS,
    entry_guard: bool = False,
    up_at: float = 70.0,
    up_exit: float = 70.0,
    down_below: float = 30.0,
    ema_gate: bool = False,
    oos_token: object | None = None,
) -> dict:
    """Matrix-runner entry point (keyword-compatible with :func:`run_aroon`)."""
    return run_aroon(parquet, instrument, timeframe, since, until, cost_bps,
                     entry_guard, up_at, up_exit, down_below, ema_gate,
                     oos_token=oos_token)


__all__ = [
    "AroonState",
    "build_rule",
    "load_aroon_bars",
    "run_aroon",
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
