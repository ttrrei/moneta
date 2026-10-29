"""S-19 Chaikin Money Flow-24 accumulation follower (signal only).

Data loading, the timeframe guard, and the shared accounting/metrics live in
:mod:`strategy.strategy_lib` / :mod:`strategy.engine`; this file only declares
the signal and the run wrapper (same contract as S-05/S-06/S-07).

Base rule (long-only, 5m): enter long when the *previous closed bar's*
``cmf_24`` (24-bar Chaikin Money Flow, range -1..+1) crosses from <= ``k``
above ``k`` — net money flow has just turned to accumulation; exit when
``cmf_24`` crosses back below 0. Distinct from S-16 (MFI *exhaustion*
dip-buying, entry on a down-cross): this is a *continuation* rule on a
different money-flow indicator. ``cmf_24`` is computed and tested in
:mod:`pipeline.indicators`; no indicator code is duplicated here.

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


class CmfState:
    """CMF-24 accumulation follower, long-only.

    ``desired_position(i)`` = the position to hold at the open of bar ``i``,
    decided from indicators on the *previous* closed bar ``i-1`` (and the
    current bar's ``close`` / ``ema_24`` for the optional trend gate — both
    known at the bar's close, so no lookahead).

    * enter long: prev ``cmf`` crossed from <= ``k`` above ``k``;
    * exit:       prev ``cmf`` crossed from >= 0 below 0;
    * optional:  ``ema_gate`` requires prev ``close`` > prev ``ema_24`` to enter.
    """

    def __init__(self, cmf: np.ndarray, close: np.ndarray, ema: np.ndarray,
                 k: float = 0.05, ema_gate: bool = False) -> None:
        self.cmf = cmf
        self.close = close
        self.ema = ema
        self.k = k
        self.ema_gate = ema_gate
        self.state = 0

    def desired_position(self, i: int) -> int:
        if i == 0:
            return 0
        j = i - 1
        c = self.cmf[j]
        if not np.isfinite(c):
            return self.state
        c0 = self.cmf[j - 1] if j > 0 else np.nan
        if self.state == 0:
            crossed = c > self.k and (not np.isfinite(c0) or c0 <= self.k)
            if crossed:
                gate_ok = True
                if self.ema_gate and np.isfinite(self.ema[j]):
                    gate_ok = self.close[j] > self.ema[j]
                if gate_ok:
                    self.state = 1
        elif np.isfinite(c0) and c < 0 and c0 >= 0:
            self.state = 0
        return self.state


def build_rule(df, k: float = 0.05, ema_gate: bool = False) -> "CmfState":
    return CmfState(
        df["cmf_24"].to_numpy(np.float64),
        df["close"].to_numpy(np.float64),
        df["ema_24"].to_numpy(np.float64),
        k=k, ema_gate=ema_gate)


def load_cmf_bars(parquet: str, instrument: str, since: str | None = None,
                  until: str | None = None, oos_token: object | None = None):
    """Load the CMF column (plus base pricing) for one window.

    ``oos_token`` is required for any window that reaches the OOS holdout
    (the data-layer gate in :func:`strategy_lib.load_bars`); in-sample windows
    load with no token.
    """
    return strategy_lib.load_bars(
        parquet, instrument, feature_cols=["cmf_24", "ema_24"],
        not_null_cols=["cmf_24"],
        since=since, until=until, oos_token=oos_token)


def run_cmf(
    parquet: str,
    instrument: str,
    timeframe: str = "5m",
    since: str | None = None,
    until: str | None = None,
    cost_bps: float = COST_BPS,
    entry_guard: bool = False,
    k: float = 0.05,
    ema_gate: bool = False,
    oos_token: object | None = None,
) -> dict:
    """Run the S-19 rule for one instrument / window / cost tier.

    Returns the full result dict (metadata + engine metrics + distribution).
    """
    df = load_cmf_bars(parquet, instrument, since, until, oos_token=oos_token)
    if len(df) < 1_000:
        raise SystemExit(f"Only {len(df)} bars loaded for {instrument} "
                         f"(window {since or 'start'}..{until or 'latest'}); not enough to backtest.")

    bars = make_bars(df, timeframe, entry_guard=entry_guard)
    meta = {
        "strategy_id": "S-19",
        "instrument": instrument,
        "timeframe": timeframe,
        "window_since": since,
        "window_until": until,
        "start": str(df["time"].iloc[0]),
        "end": str(df["time"].iloc[-1]),
        "cost_bps": cost_bps,
        "entry_guard": "off" if not entry_guard else "gap_bar|near_market_close",
        "k": k,
        "ema_gate": ema_gate,
    }
    return run_strategy(build_rule(df, k, ema_gate), bars,
                        cost_bps, long_only=True, meta=meta)


def run(
    parquet: str,
    instrument: str,
    timeframe: str = "5m",
    since: str | None = None,
    until: str | None = None,
    cost_bps: float = COST_BPS,
    entry_guard: bool = False,
    k: float = 0.05,
    ema_gate: bool = False,
    oos_token: object | None = None,
) -> dict:
    """Matrix-runner entry point (keyword-compatible with :func:`run_cmf`)."""
    return run_cmf(parquet, instrument, timeframe, since, until, cost_bps,
                   entry_guard, k, ema_gate, oos_token=oos_token)


__all__ = [
    "CmfState",
    "build_rule",
    "load_cmf_bars",
    "run_cmf",
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
