"""S-25 Chop-regime mean-reversion (signal only).

Data loading, the timeframe guard, and the shared accounting/metrics live in
:mod:`strategy.strategy_lib` / :mod:`strategy.engine`; this file only declares
the signal and the run wrapper (same contract as S-05/S-06/S-07).

Base rule (long-only, 5m): enter long when the *previous closed bar's* close
is stretched below its ``ema_24`` by at least ``k * atr_24`` **and** the
regime is choppy (``chop_24`` > ``chop_at``); exit when the close recovers
back to/above ``ema_24``. The complement of S-24: S-24 trades *momentum* in
efficient (trending) markets, S-25 trades *reversion* in inefficient
(range-bound) ones — the chop index is the regime switch. ``chop_24`` /
``ema_24`` / ``atr_24`` are computed and tested in :mod:`pipeline.indicators`.

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


class ChopReversionState:
    """Chop-regime mean-reversion, long-only.

    ``desired_position(i)`` = the position to hold at the open of bar ``i``,
    decided from the *previous* closed bar ``i-1``:

    * enter long: prev ``(close - ema_24) / atr_24`` <= ``-k`` (stretched
      down) and prev ``chop_24`` > ``chop_at`` (choppy regime);
    * exit:       prev ``close`` >= prev ``ema_24`` (recovered).
    """

    def __init__(self, close: np.ndarray, ema: np.ndarray, atr: np.ndarray,
                 chop: np.ndarray, k: float = 1.0, chop_at: float = 60.0) -> None:
        self.close = close
        self.ema = ema
        self.atr = atr
        self.chop = chop
        self.k = k
        self.chop_at = chop_at
        self.state = 0

    def desired_position(self, i: int) -> int:
        if i == 0:
            return 0
        j = i - 1
        if not (np.isfinite(self.close[j]) and np.isfinite(self.ema[j])
                and np.isfinite(self.atr[j]) and self.atr[j] > 0):
            return self.state
        if self.state == 0:
            r = (self.close[j] - self.ema[j]) / self.atr[j]
            chop_ok = (self.chop[j] > self.chop_at) if np.isfinite(self.chop[j]) else False
            if r <= -self.k and chop_ok:
                self.state = 1
        elif self.close[j] >= self.ema[j]:
            self.state = 0
        return self.state


def build_rule(df, k: float = 1.0, chop_at: float = 60.0) -> "ChopReversionState":
    return ChopReversionState(
        df["close"].to_numpy(np.float64),
        df["ema_24"].to_numpy(np.float64),
        df["atr_24"].to_numpy(np.float64),
        df["chop_24"].to_numpy(np.float64),
        k=k, chop_at=chop_at)


def load_chop_bars(parquet: str, instrument: str, since: str | None = None,
                   until: str | None = None, oos_token: object | None = None):
    """Load the chop/EMA/ATR columns (plus base pricing) for one window.

    ``oos_token`` is required for any window that reaches the OOS holdout
    (the data-layer gate in :func:`strategy_lib.load_bars`); in-sample windows
    load with no token.
    """
    return strategy_lib.load_bars(
        parquet, instrument, feature_cols=["chop_24", "ema_24", "atr_24"],
        not_null_cols=["chop_24", "atr_24"],
        since=since, until=until, oos_token=oos_token)


def run_chop(
    parquet: str,
    instrument: str,
    timeframe: str = "5m",
    since: str | None = None,
    until: str | None = None,
    cost_bps: float = COST_BPS,
    entry_guard: bool = False,
    k: float = 1.0,
    chop_at: float = 60.0,
    oos_token: object | None = None,
) -> dict:
    """Run the S-25 rule for one instrument / window / cost tier.

    Returns the full result dict (metadata + engine metrics + distribution).
    """
    df = load_chop_bars(parquet, instrument, since, until, oos_token=oos_token)
    if len(df) < 1_000:
        raise SystemExit(f"Only {len(df)} bars loaded for {instrument} "
                         f"(window {since or 'start'}..{until or 'latest'}); not enough to backtest.")

    bars = make_bars(df, timeframe, entry_guard=entry_guard)
    meta = {
        "strategy_id": "S-25",
        "instrument": instrument,
        "timeframe": timeframe,
        "window_since": since,
        "window_until": until,
        "start": str(df["time"].iloc[0]),
        "end": str(df["time"].iloc[-1]),
        "cost_bps": cost_bps,
        "entry_guard": "off" if not entry_guard else "gap_bar|near_market_close",
        "k": k,
        "chop_at": chop_at,
    }
    return run_strategy(build_rule(df, k, chop_at), bars,
                        cost_bps, long_only=True, meta=meta)


def run(
    parquet: str,
    instrument: str,
    timeframe: str = "5m",
    since: str | None = None,
    until: str | None = None,
    cost_bps: float = COST_BPS,
    entry_guard: bool = False,
    k: float = 1.0,
    chop_at: float = 60.0,
    oos_token: object | None = None,
) -> dict:
    """Matrix-runner entry point (keyword-compatible with :func:`run_chop`)."""
    return run_chop(parquet, instrument, timeframe, since, until, cost_bps,
                    entry_guard, k, chop_at, oos_token=oos_token)


__all__ = [
    "ChopReversionState",
    "build_rule",
    "load_chop_bars",
    "run_chop",
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
