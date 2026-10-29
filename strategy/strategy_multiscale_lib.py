"""S-20 Multi-scale SuperTrend alignment follower (signal only).

Data loading, the timeframe guard, and the shared accounting/metrics live in
:mod:`strategy.strategy_lib` / :mod:`strategy.engine`; this file only declares
the signal and the run wrapper (same contract as S-05/S-06/S-07).

Base rule (long-only, 5m): follow the *short* SuperTrend direction
(``st_dir_60_2``) but only while the *long* SuperTrend direction
(``st_dir_120_2``) agrees — two scales of the **same** indicator family,
versus the single-scale followers S-05 (24) and S-13 (slow PSAR). A
``h1_gate`` variant additionally requires the republished 1h SuperTrend
(``h1_st_dir_120_3``) to agree, i.e. a genuine higher-timeframe alignment
(5m-native only: the ``h1_*`` columns exist on the 5m table only).

The rule is fully parameterised on which direction columns gate entries vs
drive exits so the iteration sweep can swap scales:

* ``short_col`` — the trend whose flips *drive* the position (entry on an up
  flip, exit on a down flip);
* ``gate_cols`` — direction series that must read "up" on the *previous*
  closed bar for an entry to be allowed (exits are never gated).

All columns are computed and tested in :mod:`pipeline.indicators`; no
indicator code is duplicated here. All timestamps are UTC.
"""

from __future__ import annotations

from typing import Sequence

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

#: Every SuperTrend-direction column this rule may be parameterised with.
ALL_COLS = ("st_dir_60_2", "st_dir_60_3", "st_dir_120_2", "st_dir_120_3",
            "h1_st_dir_120_3")


class MultiScaleState:
    """Multi-scale SuperTrend alignment follower, long-only.

    ``desired_position(i)`` = the position to hold at the open of bar ``i``,
    decided from the *previous* closed bar ``i-1``:

    * enter long: prev short direction up, prev bar-2 short direction down
      (a flip just happened), and every gate column reads up;
    * exit:       prev short direction down.
    """

    def __init__(self, short: np.ndarray,
                 gates: Sequence[np.ndarray]) -> None:
        self.short = short
        self.gates = [g for g in gates if g is not None]
        self.state = 0

    def desired_position(self, i: int) -> int:
        if i == 0:
            return 0
        j = i - 1
        if not np.isfinite(self.short[j]):
            return self.state
        if self.short[j] <= 0.5:
            self.state = 0
            return 0
        if self.state == 1:
            return 1
        if j == 0 or not np.isfinite(self.short[j - 1]) or self.short[j - 1] > 0.5:
            return 0  # not a fresh up-flip
        for g in self.gates:
            if not (np.isfinite(g[j]) and g[j] > 0.5):
                return 0
        self.state = 1
        return 1


def build_rule(df, short_col: str = "st_dir_60_2",
               gate_cols: tuple[str, ...] = ("st_dir_120_2",)) -> "MultiScaleState":
    gates = [df[c].to_numpy(np.float64) for c in gate_cols if c in df.columns]
    return MultiScaleState(df[short_col].to_numpy(np.float64), gates)


def load_multiscale_bars(parquet: str, instrument: str, short_col: str,
                         gate_cols: tuple[str, ...],
                         since: str | None = None, until: str | None = None,
                         oos_token: object | None = None):
    """Load the direction columns (plus base pricing) for one window.

    ``oos_token`` is required for any window that reaches the OOS holdout
    (the data-layer gate in :func:`strategy_lib.load_bars`); in-sample windows
    load with no token.
    """
    cols = [short_col] + [c for c in gate_cols if c not in (short_col,)]
    return strategy_lib.load_bars(
        parquet, instrument, feature_cols=cols,
        not_null_cols=[short_col],
        since=since, until=until, oos_token=oos_token)


def run_multiscale(
    parquet: str,
    instrument: str,
    timeframe: str = "5m",
    since: str | None = None,
    until: str | None = None,
    cost_bps: float = COST_BPS,
    entry_guard: bool = False,
    short_col: str = "st_dir_60_2",
    gate_cols: tuple[str, ...] = ("st_dir_120_2",),
    oos_token: object | None = None,
) -> dict:
    """Run the S-20 rule for one instrument / window / cost tier.

    Returns the full result dict (metadata + engine metrics + distribution).
    """
    df = load_multiscale_bars(parquet, instrument, short_col, gate_cols,
                              since, until, oos_token=oos_token)
    if len(df) < 1_000:
        raise SystemExit(f"Only {len(df)} bars loaded for {instrument} "
                         f"(window {since or 'start'}..{until or 'latest'}); not enough to backtest.")

    bars = make_bars(df, timeframe, entry_guard=entry_guard)
    meta = {
        "strategy_id": "S-20",
        "instrument": instrument,
        "timeframe": timeframe,
        "window_since": since,
        "window_until": until,
        "start": str(df["time"].iloc[0]),
        "end": str(df["time"].iloc[-1]),
        "cost_bps": cost_bps,
        "entry_guard": "off" if not entry_guard else "gap_bar|near_market_close",
        "short_col": short_col,
        "gate_cols": list(gate_cols),
    }
    return run_strategy(build_rule(df, short_col, gate_cols), bars,
                        cost_bps, long_only=True, meta=meta)


def run(
    parquet: str,
    instrument: str,
    timeframe: str = "5m",
    since: str | None = None,
    until: str | None = None,
    cost_bps: float = COST_BPS,
    entry_guard: bool = False,
    short_col: str = "st_dir_60_2",
    gate_cols: tuple[str, ...] = ("st_dir_120_2",),
    oos_token: object | None = None,
) -> dict:
    """Matrix-runner entry point (keyword-compatible with :func:`run_multiscale`)."""
    return run_multiscale(parquet, instrument, timeframe, since, until, cost_bps,
                          entry_guard, short_col, gate_cols, oos_token=oos_token)


__all__ = [
    "MultiScaleState",
    "build_rule",
    "load_multiscale_bars",
    "run_multiscale",
    "run",
    "ALL_COLS",
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
