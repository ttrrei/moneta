"""S-21 Slow squeeze-expansion follower (60-bar, signal only).

Data loading, the timeframe guard, and the shared accounting/metrics live in
:mod:`strategy.strategy_lib` / :mod:`strategy.engine`; this file only declares
the signal and the run wrapper (same contract as S-05/S-06/S-07).

Base rule (long-only, 5m): while the *previous closed bar's* ``sqz_on_60``
is on **and** close is above its ``bb_mid_60`` (direction), stay long; exit
when the squeeze turns off or the close drops back to/below ``bb_mid_60``.
``onset_only=True` instead enters only on a fresh 0 -> 1 turn of
``sqz_on_60`` (the stricter, rarer trigger). Distinct from S-04: a *slower*
squeeze (60-bar lookback vs 24). ``sqz_on_60`` and ``bb_mid_60`` are
computed and tested in :mod:`pipeline.indicators`.

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


class SqueezeSlowState:
    """Slow (60-bar) squeeze-expansion follower, long-only.

    ``desired_position(i)`` = the position to hold at the open of bar ``i``,
    decided from the *previous* closed bar ``i-1`` (and the optional EMA
    trend gate — all known at the bar's close, so no lookahead).

    * enter long: prev ``sqz`` is on (``> 0.5``) and prev ``close`` > prev
      ``bb_mid``; optional ``ema_gate`` also requires prev ``close`` >
      prev ``ema_24``; when ``onset_only`` is set, entry additionally
      requires prev ``sqz`` to have turned 0 -> 1 on this bar (the rarer,
      stricter trigger).
    * exit:       prev ``sqz`` is off, or prev ``close`` <= prev ``bb_mid``.
    """

    def __init__(self, sqz: np.ndarray, mid: np.ndarray, close: np.ndarray,
                 ema: np.ndarray, ema_gate: bool = False,
                 onset_only: bool = False) -> None:
        self.sqz = sqz
        self.mid = mid
        self.close = close
        self.ema = ema
        self.ema_gate = ema_gate
        self.onset_only = onset_only
        self.state = 0

    def _direction_ok(self, j: int) -> bool:
        above_mid = (self.close[j] > self.mid[j]) if np.isfinite(self.mid[j]) else False
        if not above_mid:
            return False
        if self.ema_gate and np.isfinite(self.ema[j]):
            return self.close[j] > self.ema[j]
        return True

    def desired_position(self, i: int) -> int:
        if i == 0:
            return 0
        j = i - 1
        if not np.isfinite(self.sqz[j]):
            return self.state
        if self.sqz[j] <= 0.5:
            self.state = 0
            return 0
        # squeeze is on: stay in unless the close reverts to/below mid
        if self.state == 1:
            if np.isfinite(self.mid[j]) and self.close[j] <= self.mid[j]:
                self.state = 0
            return self.state
        # flat and squeeze is on: enter on the direction turn
        if self.onset_only:
            if j == 0 or not np.isfinite(self.sqz[j - 1]) or self.sqz[j - 1] > 0.5:
                return 0  # not a fresh 0 -> 1 turn
        if self._direction_ok(j):
            self.state = 1
        return self.state


def build_rule(df, ema_gate: bool = False, onset_only: bool = False) -> "SqueezeSlowState":
    return SqueezeSlowState(
        df["sqz_on_60"].to_numpy(np.float64),
        df["bb_mid_60"].to_numpy(np.float64),
        df["close"].to_numpy(np.float64),
        df["ema_24"].to_numpy(np.float64),
        ema_gate=ema_gate, onset_only=onset_only)


def load_squeeze_slow_bars(parquet: str, instrument: str, since: str | None = None,
                           until: str | None = None, oos_token: object | None = None):
    """Load the slow-squeeze columns (plus base pricing) for one window.

    ``oos_token`` is required for any window that reaches the OOS holdout
    (the data-layer gate in :func:`strategy_lib.load_bars`); in-sample windows
    load with no token.
    """
    return strategy_lib.load_bars(
        parquet, instrument, feature_cols=["sqz_on_60", "bb_mid_60", "ema_24"],
        not_null_cols=["sqz_on_60"],
        since=since, until=until, oos_token=oos_token)


def run_squeeze_slow(
    parquet: str,
    instrument: str,
    timeframe: str = "5m",
    since: str | None = None,
    until: str | None = None,
    cost_bps: float = COST_BPS,
    entry_guard: bool = False,
    ema_gate: bool = False,
    onset_only: bool = False,
    oos_token: object | None = None,
) -> dict:
    """Run the S-21 rule for one instrument / window / cost tier.

    Returns the full result dict (metadata + engine metrics + distribution).
    """
    df = load_squeeze_slow_bars(parquet, instrument, since, until, oos_token=oos_token)
    if len(df) < 1_000:
        raise SystemExit(f"Only {len(df)} bars loaded for {instrument} "
                         f"(window {since or 'start'}..{until or 'latest'}); not enough to backtest.")

    bars = make_bars(df, timeframe, entry_guard=entry_guard)
    meta = {
        "strategy_id": "S-21",
        "instrument": instrument,
        "timeframe": timeframe,
        "window_since": since,
        "window_until": until,
        "start": str(df["time"].iloc[0]),
        "end": str(df["time"].iloc[-1]),
        "cost_bps": cost_bps,
        "entry_guard": "off" if not entry_guard else "gap_bar|near_market_close",
        "ema_gate": ema_gate,
        "onset_only": onset_only,
    }
    return run_strategy(build_rule(df, ema_gate, onset_only), bars,
                        cost_bps, long_only=True, meta=meta)


def run(
    parquet: str,
    instrument: str,
    timeframe: str = "5m",
    since: str | None = None,
    until: str | None = None,
    cost_bps: float = COST_BPS,
    entry_guard: bool = False,
    ema_gate: bool = False,
    onset_only: bool = False,
    oos_token: object | None = None,
) -> dict:
    """Matrix-runner entry point (keyword-compatible with :func:`run_squeeze_slow`)."""
    return run_squeeze_slow(parquet, instrument, timeframe, since, until, cost_bps,
                            entry_guard, ema_gate, onset_only, oos_token=oos_token)


__all__ = [
    "SqueezeSlowState",
    "build_rule",
    "load_squeeze_slow_bars",
    "run_squeeze_slow",
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
