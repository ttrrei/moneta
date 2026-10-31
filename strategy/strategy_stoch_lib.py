"""S-10 Stochastic-24 oversold-turn buyer (signal only).

Data loading, the timeframe guard, and the shared accounting/metrics live in
:mod:`strategy.strategy_lib` / :mod:`strategy.engine`; this file only declares
the signal and the run wrapper (same contract as S-05/S-06/S-07).

Base rule (long-only, 5m): enter long when the *previous closed bar's*
``stoch_k_24`` crosses up through ``stoch_d_24`` while K is below ``k_below``
(an oversold turn), exit when K crosses back down through D.
``stoch_k_24`` / ``stoch_d_24`` are computed and tested in
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


class StochState:
    """Stochastic-24 oversold-turn buyer, long-only.

    ``desired_position(i)`` = the position to hold at the open of bar ``i``,
    decided from indicators on the *previous* closed bar ``i-1`` (and the
    current bar's ``close`` / ``ema_24`` for the optional trend gate — both
    known at the bar's close, so no lookahead).

    * enter long: prev K crossed up through D while K < ``k_below``;
    * exit:       prev K crossed down through D;
    * optional:  ``ema_gate`` requires prev ``close`` > prev ``ema_24`` to enter.
    """

    def __init__(self, k: np.ndarray, d: np.ndarray, close: np.ndarray,
                 ema: np.ndarray, k_below: float = 30.0, ema_gate: bool = False) -> None:
        self.k = k
        self.d = d
        self.close = close
        self.ema = ema
        self.k_below = k_below
        self.ema_gate = ema_gate
        self.state = 0

    def desired_position(self, i: int) -> int:
        if i == 0:
            return 0
        j = i - 1
        if not (np.isfinite(self.k[j]) and np.isfinite(self.d[j])):
            return self.state
        if j == 0 or not (np.isfinite(self.k[j - 1]) and np.isfinite(self.d[j - 1])):
            return self.state
        k, d, k0, d0 = self.k[j], self.d[j], self.k[j - 1], self.d[j - 1]
        if self.state == 0:
            crossed_up = k > d and k0 <= d0
            gate_ok = True
            if self.ema_gate:
                gate_ok = strategy_lib.entry_gate_allows(True, self.close, self.ema, j)
            if crossed_up and k < self.k_below and gate_ok:
                self.state = 1
        elif k < d and k0 >= d0:
            self.state = 0
        return self.state


def build_rule(df, k_below: float = 30.0, ema_gate: bool = False) -> "StochState":
    return StochState(
        df["stoch_k_24"].to_numpy(np.float64),
        df["stoch_d_24"].to_numpy(np.float64),
        df["close"].to_numpy(np.float64),
        df["ema_24"].to_numpy(np.float64),
        k_below=k_below, ema_gate=ema_gate)


def load_stoch_bars(parquet: str, instrument: str, since: str | None = None,
                    until: str | None = None, oos_token: object | None = None):
    """Load the stochastic columns (plus base pricing) for one window.

    ``oos_token`` is required for any window that reaches the OOS holdout
    (the data-layer gate in :func:`strategy_lib.load_bars`); in-sample windows
    load with no token.
    """
    return strategy_lib.load_bars(
        parquet, instrument, feature_cols=["stoch_k_24", "stoch_d_24", "ema_24"],
        not_null_cols=["stoch_k_24", "stoch_d_24"],
        since=since, until=until, oos_token=oos_token)


def run_stoch(
    parquet: str,
    instrument: str,
    timeframe: str = "5m",
    since: str | None = None,
    until: str | None = None,
    cost_bps: float = COST_BPS,
    entry_guard: bool = False,
    k_below: float = 30.0,
    ema_gate: bool = False,
    oos_token: object | None = None,
) -> dict:
    """Run the S-10 rule for one instrument / window / cost tier.

    Returns the full result dict (metadata + engine metrics + distribution).
    """
    df = load_stoch_bars(parquet, instrument, since, until, oos_token=oos_token)
    if len(df) < 1_000:
        raise SystemExit(f"Only {len(df)} bars loaded for {instrument} "
                         f"(window {since or 'start'}..{until or 'latest'}); not enough to backtest.")

    bars = make_bars(df, timeframe, entry_guard=entry_guard)
    meta = {
        "strategy_id": "S-10",
        "instrument": instrument,
        "timeframe": timeframe,
        "window_since": since,
        "window_until": until,
        "start": str(df["time"].iloc[0]),
        "end": str(df["time"].iloc[-1]),
        "cost_bps": cost_bps,
        "entry_guard": "off" if not entry_guard else "gap_bar|near_market_close",
        "k_below": k_below,
        "ema_gate": ema_gate,
    }
    return run_strategy(build_rule(df, k_below, ema_gate), bars,
                        cost_bps, long_only=True, meta=meta)


def run(
    parquet: str,
    instrument: str,
    timeframe: str = "5m",
    since: str | None = None,
    until: str | None = None,
    cost_bps: float = COST_BPS,
    entry_guard: bool = False,
    k_below: float = 30.0,
    ema_gate: bool = False,
    oos_token: object | None = None,
) -> dict:
    """Matrix-runner entry point (keyword-compatible with :func:`run_stoch`)."""
    return run_stoch(parquet, instrument, timeframe, since, until, cost_bps,
                     entry_guard, k_below, ema_gate, oos_token=oos_token)


__all__ = [
    "StochState",
    "build_rule",
    "load_stoch_bars",
    "run_stoch",
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
