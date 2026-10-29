"""S-03 RSI + trend filter as a reusable library (signal only).

Rule (long-only, 5m — the "trade only with the trend" variant from the
registry):
  * **Entry** when the previous closed bar has ``rsi_24 < 30`` **and**
    ``close > ema_24`` (the oscillator says oversold *and* the trend agrees).
  * **Exit**  when the previous closed bar has ``rsi_24 > 55``.

Compared to S-01, the extra ``close > ema_24`` condition should cut trade
count and — more importantly — filter out the "buying a falling knife" trades
that the S-01 report §5.3 blamed on long-only mean reversion in downtrends.

Data loading, the timeframe guard, and the shared accounting/metrics all live in
:mod:`strategy.strategy_lib` / :mod:`strategy.engine`; this file only declares
the signal and the run wrapper.

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

RSI_COL = "rsi_24"
EMA_COL = "ema_24"
COST_BPS = 2.0  # one-way transaction cost, basis points (same convention as S-01)


def build_rule(df) -> "RsiTrendState":
    return RsiTrendState(
        rsi=df[RSI_COL].to_numpy(np.float64),
        ema=df[EMA_COL].to_numpy(np.float64),
        close=df["close"].to_numpy(np.float64),
    )


def load_rsi_trend_bars(parquet: str, instrument: str, since: str | None = None,
                        until: str | None = None, oos_token: object | None = None):
    """Load the RSI + EMA columns (plus base pricing) for one window.

    ``oos_token`` is required for any window that reaches the OOS holdout
    (the data-layer gate in :func:`strategy_lib.load_bars`).
    """
    return strategy_lib.load_bars(
        parquet, instrument, feature_cols=[RSI_COL, EMA_COL],
        not_null_cols=[RSI_COL, EMA_COL], since=since, until=until,
        oos_token=oos_token)


class RsiTrendState:
    """Long-only RSI-24 mean-reversion gated by a trend filter.

    ``desired_position(i)`` = the position to hold at the open of bar ``i``,
    decided from bar ``i-1``: enter when RSI < 30 *and* close > EMA; exit when
    RSI > 55.
    """

    def __init__(self, rsi: np.ndarray, ema: np.ndarray, close: np.ndarray) -> None:
        self.rsi = rsi
        self.ema = ema
        self.close = close
        self.state = 0  # 0 flat, 1 long

    def desired_position(self, i: int) -> int:
        if i == 0:
            return 0
        p = i - 1
        r, e, c = self.rsi[p], self.ema[p], self.close[p]
        if not (np.isfinite(r) and np.isfinite(e) and np.isfinite(c)):
            return self.state
        if r < 30.0 and c > e:
            self.state = 1
        elif r > 55.0:
            self.state = 0
        return self.state


def run_rsi_trend(
    parquet: str,
    instrument: str,
    timeframe: str = "5m",
    since: str | None = None,
    until: str | None = None,
    cost_bps: float = COST_BPS,
    entry_guard: bool = False,
    oos_token: object | None = None,
) -> dict:
    """Run the S-03 rule for one instrument / window / cost tier.

    ``entry_guard`` defaults to OFF to match the S-01 baseline convention.
    ``oos_token`` is required for a window that reaches the OOS holdout (the
    data-layer gate).
    """
    df = load_rsi_trend_bars(parquet, instrument, since, until, oos_token=oos_token)
    if len(df) < 1_000:
        raise SystemExit(f"Only {len(df)} bars loaded for {instrument} "
                         f"(window {since or 'start'}..{until or 'latest'}); not enough to backtest.")

    bars = make_bars(df, timeframe, entry_guard=entry_guard)
    meta = {
        "strategy_id": "S-03",
        "instrument": instrument,
        "timeframe": timeframe,
        "window_since": since,
        "window_until": until,
        "start": str(df["time"].iloc[0]),
        "end": str(df["time"].iloc[-1]),
        "cost_bps": cost_bps,
        "entry_guard": "off" if not entry_guard else "gap_bar|near_market_close",
    }
    return run_strategy(build_rule(df), bars, cost_bps, long_only=True, meta=meta)


def run(
    parquet: str,
    instrument: str,
    timeframe: str = "5m",
    since: str | None = None,
    until: str | None = None,
    cost_bps: float = COST_BPS,
    entry_guard: bool = False,
    oos_token: object | None = None,
) -> dict:
    """Matrix-runner entry point (keyword-compatible with :func:`run_rsi_trend`)."""
    return run_rsi_trend(parquet, instrument, timeframe, since, until,
                         cost_bps, entry_guard, oos_token=oos_token)


__all__ = [
    "RsiTrendState",
    "build_rule",
    "load_rsi_trend_bars",
    "run_rsi_trend",
    "run",
    "RSI_COL",
    "EMA_COL",
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
