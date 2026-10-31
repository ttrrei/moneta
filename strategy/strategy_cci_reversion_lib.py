"""S-08 CCI-24 dip-buying with band-position context (signal only).

Data loading, the timeframe guard, and the shared accounting/metrics live in
:mod:`strategy.strategy_lib` / :mod:`strategy.engine`; this file only declares
the signal and the run wrapper (same contract as S-05/S-06/S-07).

Base rule (long-only, 5m): enter long when the *previous closed bar's*
``cci_24`` crosses from >= ``enter_below`` down below it while
``bb_pctb_24`` < 0.5 (price in the lower half of its Bollinger band — a real
dip, not a trend), exit when ``cci_24`` >= ``exit_above``. ``cci_24`` /
``bb_pctb_24`` are computed and tested in :mod:`pipeline.indicators`; no
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


class CciReversionState:
    """CCI-24 dip-buying with band-position context, long-only.

    ``desired_position(i)`` = the position to hold at the open of bar ``i``,
    decided from indicators on the *previous* closed bar ``i-1`` (and the
    current bar's ``close`` / ``ema_24`` for the optional trend gate — both
    known at the bar's close, so no lookahead).

    * enter long: prev ``cci`` crossed from >= ``enter_below`` to < it, and
      prev ``bb_pctb`` < 0.5;
    * exit:      prev ``cci`` >= ``exit_above``;
    * optional:  ``ema_gate`` requires prev ``close`` > prev ``ema_24`` to
      *enter* (exits are never gated).
    """

    def __init__(self, cci: np.ndarray, bb_pos: np.ndarray,
                 close: np.ndarray, ema: np.ndarray,
                 enter_below: float = 100.0, exit_above: float = -100.0,
                 ema_gate: bool = False) -> None:
        self.cci = cci
        self.bb_pos = bb_pos
        self.close = close
        self.ema = ema
        self.enter_below = enter_below
        self.exit_above = exit_above
        self.ema_gate = ema_gate
        self.state = 0

    def desired_position(self, i: int) -> int:
        if i == 0:
            return 0
        j = i - 1
        c = self.cci[j]
        if not np.isfinite(c):
            return self.state
        entering = c < self.enter_below
        if j > 0:
            c0 = self.cci[j - 1]
            # A NaN prior (warm-up) must not *block* an entry — treat it as
            # "not below the threshold" so the cross is recognised (consistent
            # with the other oscillator rules).
            entering = entering and not (np.isfinite(c0) and c0 < self.enter_below)
        bb = self.bb_pos[j]
        gate_ok = True
        if self.ema_gate:
            gate_ok = strategy_lib.entry_gate_allows(True, self.close, self.ema, j)
        if self.state == 0:
            self.state = 1 if (entering and bb < 0.5 and gate_ok) else 0
        elif c >= self.exit_above:
            self.state = 0
        return self.state


def build_rule(df, enter_below: float = 100.0, exit_above: float = -100.0,
               ema_gate: bool = False) -> "CciReversionState":
    return CciReversionState(
        df["cci_24"].to_numpy(np.float64),
        df["bb_pctb_24"].to_numpy(np.float64),
        df["close"].to_numpy(np.float64),
        df["ema_24"].to_numpy(np.float64),
        enter_below=enter_below, exit_above=exit_above, ema_gate=ema_gate)


def load_cci_reversion_bars(parquet: str, instrument: str, since: str | None = None,
                            until: str | None = None, oos_token: object | None = None):
    """Load the CCI/band-position columns (plus base pricing) for one window.

    ``oos_token`` is required for any window that reaches the OOS holdout
    (the data-layer gate in :func:`strategy_lib.load_bars`); in-sample windows
    load with no token.
    """
    return strategy_lib.load_bars(
        parquet, instrument,
        feature_cols=["cci_24", "bb_pctb_24", "ema_24"],
        not_null_cols=["cci_24", "bb_pctb_24"],
        since=since, until=until, oos_token=oos_token)


def run_cci_reversion(
    parquet: str,
    instrument: str,
    timeframe: str = "5m",
    since: str | None = None,
    until: str | None = None,
    cost_bps: float = COST_BPS,
    entry_guard: bool = False,
    enter_below: float = 100.0,
    exit_above: float = -100.0,
    ema_gate: bool = False,
    oos_token: object | None = None,
) -> dict:
    """Run the S-08 rule for one instrument / window / cost tier.

    Returns the full result dict (metadata + engine metrics + distribution).
    """
    df = load_cci_reversion_bars(parquet, instrument, since, until, oos_token=oos_token)
    if len(df) < 1_000:
        raise SystemExit(f"Only {len(df)} bars loaded for {instrument} "
                         f"(window {since or 'start'}..{until or 'latest'}); not enough to backtest.")

    bars = make_bars(df, timeframe, entry_guard=entry_guard)
    meta = {
        "strategy_id": "S-08",
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
        "ema_gate": ema_gate,
    }
    return run_strategy(build_rule(df, enter_below, exit_above, ema_gate), bars,
                        cost_bps, long_only=True, meta=meta)


def run(
    parquet: str,
    instrument: str,
    timeframe: str = "5m",
    since: str | None = None,
    until: str | None = None,
    cost_bps: float = COST_BPS,
    entry_guard: bool = False,
    enter_below: float = 100.0,
    exit_above: float = -100.0,
    ema_gate: bool = False,
    oos_token: object | None = None,
) -> dict:
    """Matrix-runner entry point (keyword-compatible with :func:`run_cci_reversion`)."""
    return run_cci_reversion(parquet, instrument, timeframe, since, until, cost_bps,
                             entry_guard, enter_below, exit_above, ema_gate,
                             oos_token=oos_token)


__all__ = [
    "CciReversionState",
    "build_rule",
    "load_cci_reversion_bars",
    "run_cci_reversion",
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
