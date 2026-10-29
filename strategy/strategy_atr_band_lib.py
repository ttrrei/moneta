"""S-24 ATR-band momentum breakout (signal only).

Data loading, the timeframe guard, and the shared accounting/metrics live in
:mod:`strategy.strategy_lib` / :mod:`strategy.engine`; this file only declares
the signal and the run wrapper (same contract as S-05/S-06/S-07).

Base rule (long-only, 5m): hold long while the *previous closed bar's*
distance of close above its ``ema_24`` is at least ``k * atr_24`` (a
scale-free, volatility-adjusted momentum band); flat when it falls below.
Distinct from S-12 (ROC + slow-EMA *slope*) and S-06 (EMA *spread*): a
*distance-from-EMA scaled by ATR* rule. ``ema_24`` / ``atr_24`` are computed
and tested in :mod:`pipeline.indicators`; no indicator code is duplicated
here.

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


class AtrBandState:
    """ATR-band momentum breakout, long-only.

    ``desired_position(i)`` = the position to hold at the open of bar ``i``,
    decided from the *previous* closed bar ``i-1``:

    * hold long: prev ``(close - ema_24) / atr_24`` >= ``k``;
    * exit:      the ratio drops below ``k_exit`` (``k_exit < k`` gives
      hysteresis; 0 exits back through the entry band).
    """

    def __init__(self, close: np.ndarray, ema: np.ndarray, atr: np.ndarray,
                 k: float = 1.0, k_exit: float = 0.5) -> None:
        self.close = close
        self.ema = ema
        self.atr = atr
        self.k = k
        self.k_exit = k_exit
        self.state = 0

    def desired_position(self, i: int) -> int:
        if i == 0:
            return 0
        j = i - 1
        if not (np.isfinite(self.close[j]) and np.isfinite(self.ema[j])
                and np.isfinite(self.atr[j]) and self.atr[j] > 0):
            return self.state
        r = (self.close[j] - self.ema[j]) / self.atr[j]
        if self.state == 0:
            self.state = 1 if r >= self.k else 0
        elif r < self.k_exit:
            self.state = 0
        return self.state


def build_rule(df, k: float = 1.0, k_exit: float = 0.5) -> "AtrBandState":
    return AtrBandState(
        df["close"].to_numpy(np.float64),
        df["ema_24"].to_numpy(np.float64),
        df["atr_24"].to_numpy(np.float64),
        k=k, k_exit=k_exit)


def load_atr_band_bars(parquet: str, instrument: str, since: str | None = None,
                       until: str | None = None, oos_token: object | None = None):
    """Load the ATR/EMA columns (plus base pricing) for one window.

    ``oos_token`` is required for any window that reaches the OOS holdout
    (the data-layer gate in :func:`strategy_lib.load_bars`); in-sample windows
    load with no token.
    """
    return strategy_lib.load_bars(
        parquet, instrument, feature_cols=["ema_24", "atr_24"],
        not_null_cols=["atr_24"],
        since=since, until=until, oos_token=oos_token)


def run_atr_band(
    parquet: str,
    instrument: str,
    timeframe: str = "5m",
    since: str | None = None,
    until: str | None = None,
    cost_bps: float = COST_BPS,
    entry_guard: bool = False,
    k: float = 1.0,
    k_exit: float = 0.5,
    oos_token: object | None = None,
) -> dict:
    """Run the S-24 rule for one instrument / window / cost tier.

    Returns the full result dict (metadata + engine metrics + distribution).
    """
    df = load_atr_band_bars(parquet, instrument, since, until, oos_token=oos_token)
    if len(df) < 1_000:
        raise SystemExit(f"Only {len(df)} bars loaded for {instrument} "
                         f"(window {since or 'start'}..{until or 'latest'}); not enough to backtest.")

    bars = make_bars(df, timeframe, entry_guard=entry_guard)
    meta = {
        "strategy_id": "S-24",
        "instrument": instrument,
        "timeframe": timeframe,
        "window_since": since,
        "window_until": until,
        "start": str(df["time"].iloc[0]),
        "end": str(df["time"].iloc[-1]),
        "cost_bps": cost_bps,
        "entry_guard": "off" if not entry_guard else "gap_bar|near_market_close",
        "k": k,
        "k_exit": k_exit,
    }
    return run_strategy(build_rule(df, k, k_exit), bars,
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
    k_exit: float = 0.5,
    oos_token: object | None = None,
) -> dict:
    """Matrix-runner entry point (keyword-compatible with :func:`run_atr_band`)."""
    return run_atr_band(parquet, instrument, timeframe, since, until, cost_bps,
                        entry_guard, k, k_exit, oos_token=oos_token)


__all__ = [
    "AtrBandState",
    "build_rule",
    "load_atr_band_bars",
    "run_atr_band",
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
