"""Run a declarative :class:`~strategy.rule_spec.RuleSpec` through the engine.

Why this module exists
-----------------------
Every strategy used to own its own copy of "load the bars, build the frame,
build the rule, call the engine, attach the distribution". :mod:`strategy.
strategy_lib` already owns most of that, but the *signal* was still rebuilt
per call, so a cost-tier sweep recomputed the identical signal three times.

This module is the single place where a spec becomes a result:

* the bars are loaded once (through the OOS gate in
  :func:`strategy.strategy_lib.load_bars`);
* the **positions array is computed once** by
  :func:`strategy.rule_engine.positions_from_spec`;
* the engine then accounts for that same array at each cost tier.

It is the concrete form of the "space for time" trade: materialise the
signal, reuse it everywhere.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from strategy import strategy_lib
from strategy.engine import BarFrame
from strategy.rule_engine import positions_from_spec
from strategy.rule_spec import RuleSpec

#: Where the spec catalogue lives (repo-root relative).
SPEC_PATH = Path("config/strategy_specs.yml")


def load_spec_bars(
    spec: RuleSpec,
    parquet: str | None,
    instrument: str,
    since: str | None = None,
    until: str | None = None,
    oos_token: object | None = None,
) -> pd.DataFrame:
    """Load the columns a spec reads, windowed, behind the OOS gate."""
    path = parquet or strategy_lib.TIMEFRAME_PARQUET[spec.timeframe]
    return strategy_lib.load_bars(
        path, instrument,
        feature_cols=list(spec.columns),
        not_null_cols=list(spec.columns),
        since=since, until=until, oos_token=oos_token,
    )


def positions_for(spec: RuleSpec, df: pd.DataFrame) -> np.ndarray:
    """The desired-position array for a spec over a loaded frame."""
    values = {column: df[column].to_numpy(dtype=np.float64) for column in spec.columns}
    return positions_from_spec(spec, values)


def spec_meta(spec: RuleSpec, instrument: str, timeframe: str, since: str | None,
              until: str | None, cost_bps: float, entry_guard: bool) -> dict:
    """The standard metadata block every result carries."""
    return {
        "strategy_id": spec.sid,
        "name": spec.name,
        "family": spec.family,
        "role": spec.role,
        "side": spec.side,
        "horizon": spec.horizon,
        "instrument": instrument,
        "timeframe": timeframe,
        "window_since": since,
        "window_until": until,
        "cost_bps": cost_bps,
        "entry_guard": "off" if not entry_guard else "gap_bar|near_market_close",
    }


def run_spec(
    spec: RuleSpec,
    instrument: str,
    parquet: str | None = None,
    timeframe: str | None = None,
    since: str | None = None,
    until: str | None = None,
    cost_bps: float = 2.0,
    entry_guard: bool = False,
    oos_token: object | None = None,
    *,
    positions: np.ndarray | None = None,
    df: pd.DataFrame | None = None,
    bars: BarFrame | None = None,
    long_only: bool = False,
    extra_meta: dict | None = None,
) -> dict:
    """Evaluate one spec on one (instrument, window, cost tier).

    ``df`` / ``bars`` / ``positions`` may be supplied by a caller that is
    sweeping several specs or several cost tiers over the same data — the
    point of the exercise is to load and compute **once** and reuse.
    """
    tf = timeframe or spec.timeframe
    if tf != spec.timeframe:
        raise SystemExit(f"{spec.sid} is registered for {spec.timeframe}, not {tf}")

    if df is None:
        df = load_spec_bars(spec, parquet, instrument, since, until, oos_token)
    if len(df) < 1_000:
        raise SystemExit(f"Only {len(df)} bars loaded for {instrument}; need at least 1,000.")
    if bars is None:
        bars = strategy_lib.make_bars(df, tf, entry_guard=entry_guard)
    if positions is None:
        positions = positions_for(spec, df)

    meta = spec_meta(spec, instrument, tf, since, until, cost_bps, entry_guard)
    if df is not None:
        meta["start"] = str(df["time"].iloc[0])
        meta["end"] = str(df["time"].iloc[-1])
    if extra_meta:
        meta.update(extra_meta)
    return strategy_lib.run_strategy(None, bars, cost_bps, long_only=long_only,
                                     meta=meta, positions=positions)


def run_spec_costs(
    spec: RuleSpec,
    instrument: str,
    cost_bps_list: list[float],
    parquet: str | None = None,
    timeframe: str | None = None,
    since: str | None = None,
    until: str | None = None,
    entry_guard: bool = False,
    oos_token: object | None = None,
    *,
    long_only: bool = False,
) -> list[dict]:
    """Evaluate one spec across several cost tiers, loading once.

    The signal is computed a single time and reused for every tier — the
    concrete win over the old per-tier rule rebuild.
    """
    tf = timeframe or spec.timeframe
    df = load_spec_bars(spec, parquet, instrument, since, until, oos_token)
    bars = strategy_lib.make_bars(df, tf, entry_guard=entry_guard)
    positions = positions_for(spec, df)
    return [
        run_spec(spec, instrument, timeframe=tf, since=since, until=until,
                 cost_bps=cost, entry_guard=entry_guard, oos_token=oos_token,
                 positions=positions, df=df, bars=bars, long_only=long_only)
        for cost in cost_bps_list
    ]


__all__ = [
    "SPEC_PATH",
    "load_spec_bars",
    "positions_for",
    "run_spec",
    "run_spec_costs",
    "spec_meta",
]
