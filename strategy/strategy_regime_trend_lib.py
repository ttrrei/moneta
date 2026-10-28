"""S-07 Regime-gated slow-trend follower as a reusable library (signal only).

The rule (long **and** short, 1h): follow the **slow** SuperTrend direction
(``st_dir_120_2`` — SuperTrend 120-bar / 2.0×ATR), but only take a new
direction when the market is actually trending, measured by ``adx_24 > 25``.
The gate is what distinguishes S-07 from S-05 (the un-gated 24-bar follower
that churned to ~10k trades):

  * **Enter / re-direction** on a **SuperTrend-120 flip** (``st_dir_120_2``
    changes bar-to-bar) **only when the flip bar's** ``adx_24 > 25`` — long if
    the new direction is up, short if it is down.
  * **Flat on a flip in a weak regime** — if the flip happens while
    ``adx_24 <= 25`` (no clear trend), stand aside.
  * **Hold** the position through the non-flip bars — ride the trend move to
    the next flip. So the trade count is driven by SuperTrend-120 *flips*,
    which on 1h bars are ~280/yr before the gate and ~70–100/yr after it.

Why this is a *new* hypothesis (not a retune of a rejected one): S-03's
"trend filter" (``close > ema_24``) turned out to be an *empty* predicate
intersection; here the gate is a **regime** measure (ADX) applied to a **slow**
trend signal (120-bar SuperTrend) on a **coarse** clock (1h) — three different
mechanisms than any of S-01…S-06, all chosen to sit in the low-frequency band
that the cost×frequency rejections (S-01/S-04/S-05) say is required.

``st_dir_120_2`` and ``adx_24`` are pre-computed columns defined once in
:mod:`pipeline.indicators` — no indicator code is duplicated here. Data
loading, the timeframe guard, and the shared accounting/metrics live in
:mod:`strategy.strategy_lib` / :mod:`strategy.engine`. All timestamps are UTC.
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

DIR_COL = "st_dir_120_2"      # slow trend: +1 up / -1 down (120-bar SuperTrend, 2.0×ATR)
REGIME_COL = "adx_24"         # regime gate: trend strength (ADX over 24 bars)
ADX_THRESHOLD = 25.0          # conventional "trending" threshold
COST_BPS = 2.0                # one-way transaction cost, basis points


def build_rule(df) -> "RegimeTrendState":
    return RegimeTrendState(
        direction=df[DIR_COL].to_numpy(np.float64),
        adx=df[REGIME_COL].to_numpy(np.float64),
        threshold=ADX_THRESHOLD,
    )


def load_regime_trend_bars(parquet: str, instrument: str, since: str | None = None,
                           until: str | None = None):
    """Load the slow-trend + regime columns (plus base pricing) for one window."""
    return strategy_lib.load_bars(
        parquet, instrument, feature_cols=[DIR_COL, REGIME_COL],
        not_null_cols=[DIR_COL, REGIME_COL], since=since, until=until)


class RegimeTrendState:
    """Regime-gated slow-trend follower (long/short).

    ``desired_position(i)`` = the position to hold at the open of bar ``i``,
    decided from the *previous* closed bar ``i-1``. On a SuperTrend flip the
    position is re-taken (long/short by the new direction) **only** if the
    regime (ADX) is trending; otherwise we stand flat. Between flips we hold.
    """

    def __init__(self, direction: np.ndarray, adx: np.ndarray,
                 threshold: float = ADX_THRESHOLD) -> None:
        self.direction = direction
        self.adx = adx
        self.threshold = threshold
        self.state = 0  # -1 short, 0 flat, 1 long

    def desired_position(self, i: int) -> int:
        if i < 2:
            return 0
        p = i - 1           # the closed bar that generates the signal
        cur, prev = self.direction[p], self.direction[p - 1]
        if not (np.isfinite(cur) and np.isfinite(prev) and np.isfinite(self.adx[p])):
            return self.state
        flipped = (cur != prev) and cur in (-1.0, 1.0)
        if flipped:
            # A direction change: take it only while trending, else stand aside.
            if self.adx[p] > self.threshold:
                self.state = 1 if cur > 0 else -1
            else:
                self.state = 0
        # else: hold the existing position (ride the trend to the next flip).
        return self.state


def run_regime_trend(
    parquet: str,
    instrument: str,
    timeframe: str = "1h",
    since: str | None = None,
    until: str | None = None,
    cost_bps: float = COST_BPS,
    entry_guard: bool = False,
) -> dict:
    """Run the S-07 rule for one instrument / window / cost tier.

    Two-sided (long/short). ``entry_guard`` defaults to OFF to match the
    S-01 baseline convention. Returns the full result dict.
    """
    df = load_regime_trend_bars(parquet, instrument, since, until)
    if len(df) < 1_000:
        raise SystemExit(f"Only {len(df)} bars loaded for {instrument} "
                         f"(window {since or 'start'}..{until or 'latest'}); not enough to backtest.")

    bars = make_bars(df, timeframe, entry_guard=entry_guard)
    meta = {
        "strategy_id": "S-07",
        "instrument": instrument,
        "timeframe": timeframe,
        "window_since": since,
        "window_until": until,
        "start": str(df["time"].iloc[0]),
        "end": str(df["time"].iloc[-1]),
        "cost_bps": cost_bps,
        "entry_guard": "off" if not entry_guard else "gap_bar|near_market_close",
    }
    return run_strategy(build_rule(df), bars, cost_bps, long_only=False, meta=meta)


def run(
    parquet: str,
    instrument: str,
    timeframe: str = "1h",
    since: str | None = None,
    until: str | None = None,
    cost_bps: float = COST_BPS,
    entry_guard: bool = False,
) -> dict:
    """Matrix-runner entry point (keyword-compatible with :func:`run_regime_trend`)."""
    return run_regime_trend(parquet, instrument, timeframe, since, until, cost_bps, entry_guard)


__all__ = [
    "RegimeTrendState",
    "build_rule",
    "load_regime_trend_bars",
    "run_regime_trend",
    "run",
    "DIR_COL",
    "REGIME_COL",
    "ADX_THRESHOLD",
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
