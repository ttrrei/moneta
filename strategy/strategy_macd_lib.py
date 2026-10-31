"""S-11 MACD-12/60 momentum turn with ATR normalisation (signal only).

Data loading, the timeframe guard, and the shared accounting/metrics live in
:mod:`strategy.strategy_lib` / :mod:`strategy.engine`; this file only declares
the signal and the run wrapper (same contract as S-05/S-06/S-07).

Base rule (long-only, 5m): enter long when the *previous closed bar's*
``macd_12_60`` crosses from <= 0 above 0 **and** the cross magnitude
``|macd_hist_12_60| / atr_24`` exceeds ``atr_min`` (a genuine momentum turn,
not noise); exit when the histogram crosses back below 0.
``macd_12_60`` / ``macd_hist_12_60`` / ``atr_24`` are computed and tested in
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


class MacdState:
    """MACD-12/60 momentum-turn buyer, long-only, ATR-normalised entry.

    ``desired_position(i)`` = the position to hold at the open of bar ``i``,
    decided from indicators on the *previous* closed bar ``i-1`` (and the
    current bar's ``close`` / ``ema_24`` for the optional trend gate — both
    known at the bar's close, so no lookahead).

    * enter long: prev ``macd`` crossed from <= 0 above 0, prev
      ``|macd_hist| / atr_24`` >= ``atr_min``, and (if ``ema_gate``) prev
      ``close`` > prev ``ema_24``;
    * exit:       prev ``macd`` crossed from >= 0 below 0.
    """

    def __init__(self, macd: np.ndarray, hist: np.ndarray, atr: np.ndarray,
                 close: np.ndarray, ema: np.ndarray, atr_min: float = 0.05,
                 ema_gate: bool = False) -> None:
        self.macd = macd
        self.hist = hist
        self.atr = atr
        self.close = close
        self.ema = ema
        self.atr_min = atr_min
        self.ema_gate = ema_gate
        self.state = 0

    def desired_position(self, i: int) -> int:
        if i == 0:
            return 0
        j = i - 1
        m = self.macd[j]
        if not np.isfinite(m) or j == 0:
            return self.state
        m0 = self.macd[j - 1]  # may be NaN (warm-up); the cross logic handles it
        if self.state == 0:
            # A NaN prior (warm-up) must not block the entry — treat it as
            # "not below 0" so the up-cross is recognised.
            crossed_up = m > 0 and not (np.isfinite(m0) and m0 > 0)
            ok = crossed_up
            h, a = self.hist[j], self.atr[j]
            if ok and self.atr_min > 0 and (not (np.isfinite(h) and np.isfinite(a) and a > 0)):
                ok = False
            elif ok and self.atr_min > 0 and a > 0:
                ok = abs(h) / a >= self.atr_min
            if ok and self.ema_gate:
                ok = strategy_lib.entry_gate_allows(True, self.close, self.ema, j)
            if ok:
                self.state = 1
        else:
            if m < 0 and m0 >= 0:
                self.state = 0
        return self.state


def build_rule(df, atr_min: float = 0.05, ema_gate: bool = False) -> "MacdState":
    return MacdState(
        df["macd_12_60"].to_numpy(np.float64),
        df["macd_hist_12_60"].to_numpy(np.float64),
        df["atr_24"].to_numpy(np.float64),
        df["close"].to_numpy(np.float64),
        df["ema_24"].to_numpy(np.float64),
        atr_min=atr_min, ema_gate=ema_gate)


def load_macd_bars(parquet: str, instrument: str, since: str | None = None,
                   until: str | None = None, oos_token: object | None = None):
    """Load the MACD/ATR columns (plus base pricing) for one window.

    ``oos_token`` is required for any window that reaches the OOS holdout
    (the data-layer gate in :func:`strategy_lib.load_bars`); in-sample windows
    load with no token.
    """
    return strategy_lib.load_bars(
        parquet, instrument,
        feature_cols=["macd_12_60", "macd_hist_12_60", "atr_24", "ema_24"],
        not_null_cols=["macd_12_60", "macd_hist_12_60"],
        since=since, until=until, oos_token=oos_token)


def run_macd(
    parquet: str,
    instrument: str,
    timeframe: str = "5m",
    since: str | None = None,
    until: str | None = None,
    cost_bps: float = COST_BPS,
    entry_guard: bool = False,
    atr_min: float = 0.05,
    ema_gate: bool = False,
    oos_token: object | None = None,
) -> dict:
    """Run the S-11 rule for one instrument / window / cost tier.

    Returns the full result dict (metadata + engine metrics + distribution).
    """
    df = load_macd_bars(parquet, instrument, since, until, oos_token=oos_token)
    if len(df) < 1_000:
        raise SystemExit(f"Only {len(df)} bars loaded for {instrument} "
                         f"(window {since or 'start'}..{until or 'latest'}); not enough to backtest.")

    bars = make_bars(df, timeframe, entry_guard=entry_guard)
    meta = {
        "strategy_id": "S-11",
        "instrument": instrument,
        "timeframe": timeframe,
        "window_since": since,
        "window_until": until,
        "start": str(df["time"].iloc[0]),
        "end": str(df["time"].iloc[-1]),
        "cost_bps": cost_bps,
        "entry_guard": "off" if not entry_guard else "gap_bar|near_market_close",
        "atr_min": atr_min,
        "ema_gate": ema_gate,
    }
    return run_strategy(build_rule(df, atr_min, ema_gate), bars,
                        cost_bps, long_only=True, meta=meta)


def run(
    parquet: str,
    instrument: str,
    timeframe: str = "5m",
    since: str | None = None,
    until: str | None = None,
    cost_bps: float = COST_BPS,
    entry_guard: bool = False,
    atr_min: float = 0.05,
    ema_gate: bool = False,
    oos_token: object | None = None,
) -> dict:
    """Matrix-runner entry point (keyword-compatible with :func:`run_macd`)."""
    return run_macd(parquet, instrument, timeframe, since, until, cost_bps,
                    entry_guard, atr_min, ema_gate, oos_token=oos_token)


__all__ = [
    "MacdState",
    "build_rule",
    "load_macd_bars",
    "run_macd",
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
