"""S-17 Slow RSI-60 (1h) mean-reversion with ADX/ST regime gate (signal only).

Data loading, the timeframe guard, and the shared accounting/metrics live in
:mod:`strategy.strategy_lib` / :mod:`strategy.engine`; this file only declares
the signal and the run wrapper (same contract as S-05/S-06/S-07).

Base rule (long-only, **1h**): enter long when the *previous closed bar's*
``rsi_60`` (60-bar RSI — 2.5× slower than S-02's ``rsi_24``) is below
``enter_below``; exit when ``rsi_60`` >= ``exit_above``. Optional
``st_gate`` (prev ``st_dir_120_3`` up) and ``adx_gate`` (prev ``adx_24`` >
``adx_at``) restrict entries to a coherent regime — this is the "gated RSI"
family, distinct from S-03 (5m + ema gate on a *different* RSI). All columns
are computed and tested in :mod:`pipeline.indicators`; no indicator code is
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


class RsiSlowState:
    """Slow (60-bar) RSI mean-reversion, long-only, with optional regime gates.

    ``desired_position(i)`` = the position to hold at the open of bar ``i``,
    decided from indicators on the *previous* closed bar ``i-1``.

    * enter long: prev ``rsi_60`` < ``enter_below`` and every enabled gate
      passes on bar ``i-1``;
    * exit:       prev ``rsi_60`` >= ``exit_above``.
    """

    def __init__(self, rsi: np.ndarray, adx: np.ndarray, st_dir: np.ndarray,
                 enter_below: float = 30.0, exit_above: float = 50.0,
                 st_gate: bool = False, adx_gate: bool = False,
                 adx_at: float = 20.0) -> None:
        self.rsi = rsi
        self.adx = adx
        self.st_dir = st_dir
        self.enter_below = enter_below
        self.exit_above = exit_above
        self.st_gate = st_gate
        self.adx_gate = adx_gate
        self.adx_at = adx_at
        self.state = 0

    def desired_position(self, i: int) -> int:
        if i == 0:
            return 0
        j = i - 1
        r = self.rsi[j]
        if not np.isfinite(r):
            return self.state
        if self.state == 0:
            if r < self.enter_below:
                ok = True
                if self.st_gate and np.isfinite(self.st_dir[j]):
                    ok = self.st_dir[j] > 0.5
                if ok and self.adx_gate and np.isfinite(self.adx[j]):
                    ok = self.adx[j] > self.adx_at
                if ok:
                    self.state = 1
        elif r >= self.exit_above:
            self.state = 0
        return self.state


def build_rule(df, enter_below: float = 30.0, exit_above: float = 50.0,
               st_gate: bool = False, adx_gate: bool = False,
               adx_at: float = 20.0) -> "RsiSlowState":
    return RsiSlowState(
        df["rsi_60"].to_numpy(np.float64),
        df["adx_24"].to_numpy(np.float64),
        df["st_dir_120_3"].to_numpy(np.float64),
        enter_below=enter_below, exit_above=exit_above,
        st_gate=st_gate, adx_gate=adx_gate, adx_at=adx_at)


def load_rsi_slow_bars(parquet: str, instrument: str, since: str | None = None,
                       until: str | None = None, oos_token: object | None = None):
    """Load the RSI-60 / ADX / SuperTrend-120-3 columns for one window.

    ``oos_token`` is required for any window that reaches the OOS holdout
    (the data-layer gate in :func:`strategy_lib.load_bars`); in-sample windows
    load with no token.
    """
    return strategy_lib.load_bars(
        parquet, instrument,
        feature_cols=["rsi_60", "adx_24", "st_dir_120_3"],
        not_null_cols=["rsi_60"],
        since=since, until=until, oos_token=oos_token)


def run_rsi_slow(
    parquet: str,
    instrument: str,
    timeframe: str = "1h",
    since: str | None = None,
    until: str | None = None,
    cost_bps: float = COST_BPS,
    entry_guard: bool = False,
    enter_below: float = 30.0,
    exit_above: float = 50.0,
    st_gate: bool = False,
    adx_gate: bool = False,
    adx_at: float = 20.0,
    oos_token: object | None = None,
) -> dict:
    """Run the S-17 rule for one instrument / window / cost tier.

    Returns the full result dict (metadata + engine metrics + distribution).
    """
    df = load_rsi_slow_bars(parquet, instrument, since, until, oos_token=oos_token)
    if len(df) < 1_000:
        raise SystemExit(f"Only {len(df)} bars loaded for {instrument} "
                         f"(window {since or 'start'}..{until or 'latest'}); not enough to backtest.")

    bars = make_bars(df, timeframe, entry_guard=entry_guard)
    meta = {
        "strategy_id": "S-17",
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
        "st_gate": st_gate,
        "adx_gate": adx_gate,
        "adx_at": adx_at,
    }
    return run_strategy(build_rule(df, enter_below, exit_above, st_gate,
                                   adx_gate, adx_at),
                        bars, cost_bps, long_only=True, meta=meta)


def run(
    parquet: str,
    instrument: str,
    timeframe: str = "1h",
    since: str | None = None,
    until: str | None = None,
    cost_bps: float = COST_BPS,
    entry_guard: bool = False,
    enter_below: float = 30.0,
    exit_above: float = 50.0,
    st_gate: bool = False,
    adx_gate: bool = False,
    adx_at: float = 20.0,
    oos_token: object | None = None,
) -> dict:
    """Matrix-runner entry point (keyword-compatible with :func:`run_rsi_slow`)."""
    return run_rsi_slow(parquet, instrument, timeframe, since, until, cost_bps,
                        entry_guard, enter_below, exit_above, st_gate, adx_gate,
                        adx_at, oos_token=oos_token)


__all__ = [
    "RsiSlowState",
    "build_rule",
    "load_rsi_slow_bars",
    "run_rsi_slow",
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
