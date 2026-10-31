"""S-09 Williams %R-24 rebound buyer with post-exit cooldown (signal only).

Data loading, the timeframe guard, and the shared accounting/metrics live in
:mod:`strategy.strategy_lib` / :mod:`strategy.engine`; this file only declares
the signal and the run wrapper (same contract as S-05/S-06/S-07).

Base rule (long-only, 5m): enter long when the *previous closed bar's*
``willr_24`` crosses from >= ``enter_below`` down below it (a short-term
washout), exit when it crosses up through ``exit_above``; a ``cooldown``
count of bars must elapse after an exit before re-entry. ``willr_24`` is
computed and tested in :mod:`pipeline.indicators`; no indicator code is
duplicated here.

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


class WillRState:
    """Williams %R-24 rebound buyer, long-only, with post-exit cooldown.

    ``desired_position(i)`` = the position to hold at the open of bar ``i``,
    decided from indicators on the *previous* closed bar ``i-1`` (and the
    current bar's ``close`` / ``ema_24`` for the optional trend gate — both
    known at the bar's close, so no lookahead).

    * enter long: prev ``willr`` crossed down through ``enter_below``,
      cooldown elapsed, and (if ``ema_gate``) prev ``close`` > prev ``ema_24``;
    * exit:       prev ``willr`` crossed up through ``exit_above``;
    * ``cooldown``: minimum bars between an exit and the next entry.
    """

    def __init__(self, willr: np.ndarray, close: np.ndarray, ema: np.ndarray,
                 enter_below: float = -70.0, exit_above: float = -40.0,
                 cooldown: int = 0, ema_gate: bool = False) -> None:
        self.willr = willr
        self.close = close
        self.ema = ema
        self.enter_below = enter_below
        self.exit_above = exit_above
        self.cooldown = int(cooldown)
        self.ema_gate = ema_gate
        self.state = 0
        self.cooldown_until = -1  # bar index until which re-entry is refused

    def desired_position(self, i: int) -> int:
        if i == 0:
            return 0
        j = i - 1
        w = self.willr[j]
        if not np.isfinite(w):
            return self.state
        w0 = self.willr[j - 1] if j > 0 else np.nan
        if self.state == 0:
            if i >= self.cooldown_until:
                crossed = w < self.enter_below and (w0 >= self.enter_below
                                                    if np.isfinite(w0) else True)
                gate_ok = True
                if self.ema_gate:
                    gate_ok = strategy_lib.entry_gate_allows(True, self.close, self.ema, j)
                if crossed and gate_ok:
                    self.state = 1
        elif np.isfinite(w0) and w > self.exit_above and w0 <= self.exit_above:
            self.state = 0
            self.cooldown_until = i + self.cooldown
        return self.state


def build_rule(df, enter_below: float = -70.0, exit_above: float = -40.0,
               cooldown: int = 0, ema_gate: bool = False) -> "WillRState":
    return WillRState(
        df["willr_24"].to_numpy(np.float64),
        df["close"].to_numpy(np.float64),
        df["ema_24"].to_numpy(np.float64),
        enter_below=enter_below, exit_above=exit_above,
        cooldown=cooldown, ema_gate=ema_gate)


def load_willr_bars(parquet: str, instrument: str, since: str | None = None,
                    until: str | None = None, oos_token: object | None = None):
    """Load the Williams-%R column (plus base pricing) for one window.

    ``oos_token`` is required for any window that reaches the OOS holdout
    (the data-layer gate in :func:`strategy_lib.load_bars`); in-sample windows
    load with no token.
    """
    return strategy_lib.load_bars(
        parquet, instrument, feature_cols=["willr_24", "ema_24"],
        not_null_cols=["willr_24"],
        since=since, until=until, oos_token=oos_token)


def run_willr(
    parquet: str,
    instrument: str,
    timeframe: str = "5m",
    since: str | None = None,
    until: str | None = None,
    cost_bps: float = COST_BPS,
    entry_guard: bool = False,
    enter_below: float = -70.0,
    exit_above: float = -40.0,
    cooldown: int = 0,
    ema_gate: bool = False,
    oos_token: object | None = None,
) -> dict:
    """Run the S-09 rule for one instrument / window / cost tier.

    Returns the full result dict (metadata + engine metrics + distribution).
    """
    df = load_willr_bars(parquet, instrument, since, until, oos_token=oos_token)
    if len(df) < 1_000:
        raise SystemExit(f"Only {len(df)} bars loaded for {instrument} "
                         f"(window {since or 'start'}..{until or 'latest'}); not enough to backtest.")

    bars = make_bars(df, timeframe, entry_guard=entry_guard)
    meta = {
        "strategy_id": "S-09",
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
        "cooldown": cooldown,
        "ema_gate": ema_gate,
    }
    return run_strategy(build_rule(df, enter_below, exit_above, cooldown, ema_gate),
                        bars, cost_bps, long_only=True, meta=meta)


def run(
    parquet: str,
    instrument: str,
    timeframe: str = "5m",
    since: str | None = None,
    until: str | None = None,
    cost_bps: float = COST_BPS,
    entry_guard: bool = False,
    enter_below: float = -70.0,
    exit_above: float = -40.0,
    cooldown: int = 0,
    ema_gate: bool = False,
    oos_token: object | None = None,
) -> dict:
    """Matrix-runner entry point (keyword-compatible with :func:`run_willr`)."""
    return run_willr(parquet, instrument, timeframe, since, until, cost_bps,
                     entry_guard, enter_below, exit_above, cooldown, ema_gate,
                     oos_token=oos_token)


__all__ = [
    "WillRState",
    "build_rule",
    "load_willr_bars",
    "run_willr",
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
