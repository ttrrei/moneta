"""S-18 VWAP-stretch reversion with ATR-normalised threshold (signal only).

Data loading, the timeframe guard, and the shared accounting/metrics live in
:mod:`strategy.strategy_lib` / :mod:`strategy.engine`; this file only declares
the signal and the run wrapper (same contract as S-05/S-06/S-07).

Base rule (long-only, 5m): the signed distance of close from session VWAP,
``d = close - vwap``, is computed on the *previous closed bar*; enter long
when ``d / atr_24`` crosses from <= 0 above ``k`` (a volume-anchored stretch
has just snapped through the threshold), exit when it falls to/below 0.
Distinct from S-06/S-26 (EMA spreads): an *anchor* rule (close vs session
VWAP) rather than a *trend* rule (fast EMA vs slow EMA). ``vwap`` and
``atr_24`` are computed and tested in :mod:`pipeline.indicators`; no
indicator code is duplicated here.

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


class VwapStretchState:
    """VWAP-stretch reversion, long-only.

    ``desired_position(i)`` = the position to hold at the open of bar ``i``,
    decided from bar ``i-1``: ``d = close - vwap`` normalised by ``atr_24``.
    * enter long: prev ``d/atr`` crossed from <= ``k`` above ``k`` (a
      volume-anchored stretch just snapped through the threshold);
    * exit:       prev ``d/atr`` < ``k_exit`` (0 = exit back through the
      threshold; ``k_exit < k`` gives exit hysteresis);
    * optional:  ``ema_gate`` requires prev ``close`` > prev ``ema_24`` to enter.
    """

    def __init__(self, d: np.ndarray, atr: np.ndarray, close: np.ndarray,
                 ema: np.ndarray, k: float = 0.25, k_exit: float = 0.0,
                 ema_gate: bool = False) -> None:
        self.d = d
        self.atr = atr
        self.close = close
        self.ema = ema
        self.k = k
        self.k_exit = k_exit
        self.ema_gate = ema_gate
        self.state = 0

    def desired_position(self, i: int) -> int:
        if i == 0:
            return 0
        j = i - 1
        if not (np.isfinite(self.d[j]) and np.isfinite(self.atr[j])
                and self.atr[j] > 0):
            return self.state
        norm = self.d[j] / self.atr[j]
        if self.state == 0:
            prev = (self.d[j - 1] / self.atr[j - 1]
                    if j > 0 and np.isfinite(self.d[j - 1])
                    and np.isfinite(self.atr[j - 1]) and self.atr[j - 1] > 0 else np.nan)
            crossed = norm > self.k and (not np.isfinite(prev) or prev <= self.k)
            if crossed:
                gate_ok = True
                if self.ema_gate:
                    gate_ok = strategy_lib.entry_gate_allows(True, self.close, self.ema, j)
                if gate_ok:
                    self.state = 1
        elif norm < self.k_exit:
            self.state = 0
        return self.state


def build_rule(df, k: float = 0.25, k_exit: float = 0.0,
               ema_gate: bool = False) -> "VwapStretchState":
    d = df["close"].to_numpy(np.float64) - df["vwap"].to_numpy(np.float64)
    return VwapStretchState(
        d,
        df["atr_24"].to_numpy(np.float64),
        df["close"].to_numpy(np.float64),
        df["ema_24"].to_numpy(np.float64),
        k=k, k_exit=k_exit, ema_gate=ema_gate)


def load_vwap_bars(parquet: str, instrument: str, since: str | None = None,
                   until: str | None = None, oos_token: object | None = None):
    """Load the VWAP/ATR columns (plus base pricing) for one window.

    ``oos_token`` is required for any window that reaches the OOS holdout
    (the data-layer gate in :func:`strategy_lib.load_bars`); in-sample windows
    load with no token.
    """
    return strategy_lib.load_bars(
        parquet, instrument, feature_cols=["vwap", "atr_24", "ema_24"],
        not_null_cols=["vwap", "atr_24"],
        since=since, until=until, oos_token=oos_token)


def run_vwap_stretch(
    parquet: str,
    instrument: str,
    timeframe: str = "5m",
    since: str | None = None,
    until: str | None = None,
    cost_bps: float = COST_BPS,
    entry_guard: bool = False,
    k: float = 0.25,
    k_exit: float = 0.0,
    ema_gate: bool = False,
    oos_token: object | None = None,
) -> dict:
    """Run the S-18 rule for one instrument / window / cost tier.

    Returns the full result dict (metadata + engine metrics + distribution).
    """
    df = load_vwap_bars(parquet, instrument, since, until, oos_token=oos_token)
    if len(df) < 1_000:
        raise SystemExit(f"Only {len(df)} bars loaded for {instrument} "
                         f"(window {since or 'start'}..{until or 'latest'}); not enough to backtest.")

    bars = make_bars(df, timeframe, entry_guard=entry_guard)
    meta = {
        "strategy_id": "S-18",
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
        "ema_gate": ema_gate,
    }
    return run_strategy(build_rule(df, k, k_exit, ema_gate), bars,
                        cost_bps, long_only=True, meta=meta)


def run(
    parquet: str,
    instrument: str,
    timeframe: str = "5m",
    since: str | None = None,
    until: str | None = None,
    cost_bps: float = COST_BPS,
    entry_guard: bool = False,
    k: float = 0.25,
    k_exit: float = 0.0,
    ema_gate: bool = False,
    oos_token: object | None = None,
) -> dict:
    """Matrix-runner entry point (keyword-compatible with :func:`run_vwap_stretch`)."""
    return run_vwap_stretch(parquet, instrument, timeframe, since, until, cost_bps,
                            entry_guard, k, k_exit, ema_gate, oos_token=oos_token)


__all__ = [
    "VwapStretchState",
    "build_rule",
    "load_vwap_bars",
    "run_vwap_stretch",
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
