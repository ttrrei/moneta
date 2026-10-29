"""S-04 Squeeze-onset follower as a reusable library (signal only).

Rule (long **and** short, 5m — the "volatility-compression event" variant from
the registry): a *squeeze* is the Bollinger Bands sitting *inside* the Keltner
channel, i.e. a volatility **compression**, marked ``sqz_on_24 = 1``. The
registered rule trades that compression episode:

  * **Enter** at the **onset** of the squeeze (``sqz_on_24`` 0→1 transition),
    taking direction from ``close`` vs ``bb_mid_24`` at that moment —
    **long** if ``close > bb_mid_24``, else **short** — and **holding** that
    direction for the whole episode (no mid-episode direction flipping, which
    would churn).
  * **Exit** when the squeeze turns **off** (``sqz_on_24`` 1→0), the natural
    end of the compression episode.
  * **Flat** otherwise (``sqz_on_24 == 0`` → no position).

Note: the entry is the *onset* of compression, not its release; this is a
follower of the squeeze cycle. It is *not* a rare event — at 5m it fires
~1,900 times a year (see the report), so the "low-frequency" premise the idea
was built on does not hold.

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

SQZ_COL = "sqz_on_24"
BBMID_COL = "bb_mid_24"
COST_BPS = 2.0  # one-way transaction cost, basis points (same convention as S-01)


def build_rule(df) -> "SqueezeState":
    return SqueezeState(
        sqz=df[SQZ_COL].to_numpy(np.float64),
        bb_mid=df[BBMID_COL].to_numpy(np.float64),
        close=df["close"].to_numpy(np.float64),
    )


def load_squeeze_bars(parquet: str, instrument: str, since: str | None = None,
                      until: str | None = None, oos_token: object | None = None):
    """Load the squeeze + Bollinger-mid columns (plus base pricing) for one window.

    ``oos_token`` is required for any window that reaches the OOS holdout
    (the data-layer gate in :func:`strategy_lib.load_bars`).
    """
    return strategy_lib.load_bars(
        parquet, instrument, feature_cols=[SQZ_COL, BBMID_COL],
        not_null_cols=[SQZ_COL, BBMID_COL], since=since, until=until,
        oos_token=oos_token)


class SqueezeState:
    """Long/short squeeze-onset (compression-episode) follower.

    ``desired_position(i)`` = the position to hold at the open of bar ``i``,
    decided from bar ``i-1``: enter on the squeeze 0→1 onset taking direction
    by ``close`` vs ``bb_mid_24``, hold it for the episode, flat once the
    squeeze turns off.
    """

    def __init__(self, sqz: np.ndarray, bb_mid: np.ndarray, close: np.ndarray) -> None:
        self.sqz = sqz
        self.bb_mid = bb_mid
        self.close = close
        self.state = 0  # -1 short, 0 flat, 1 long

    def desired_position(self, i: int) -> int:
        if i == 0:
            return 0
        p = i - 1
        s, m, c = self.sqz[p], self.bb_mid[p], self.close[p]
        if not (np.isfinite(s) and np.isfinite(m) and np.isfinite(c)):
            return self.state
        if s == 1:
            if self.state == 0:
                # Squeeze onset (just turned on): take direction by the
                # close-vs-mid cross *at the onset* and hold it for the whole
                # episode — no mid-episode direction flipping (which would churn).
                self.state = 1 if c > m else -1
            # else: keep the onset direction for the duration of the episode.
        else:
            self.state = 0  # squeeze off → flat
        return self.state


def run_squeeze(
    parquet: str,
    instrument: str,
    timeframe: str = "5m",
    since: str | None = None,
    until: str | None = None,
    cost_bps: float = COST_BPS,
    entry_guard: bool = False,
    oos_token: object | None = None,
) -> dict:
    """Run the S-04 rule for one instrument / window / cost tier.

    Two-sided (long/short) — the only candidate that trades both sides.
    ``entry_guard`` defaults to OFF to match the S-01 baseline convention.
    ``oos_token`` is required for a window that reaches the OOS holdout (the
    data-layer gate).
    """
    df = load_squeeze_bars(parquet, instrument, since, until, oos_token=oos_token)
    if len(df) < 1_000:
        raise SystemExit(f"Only {len(df)} bars loaded for {instrument} "
                         f"(window {since or 'start'}..{until or 'latest'}); not enough to backtest.")

    bars = make_bars(df, timeframe, entry_guard=entry_guard)
    meta = {
        "strategy_id": "S-04",
        "instrument": instrument,
        "timeframe": timeframe,
        "window_since": since,
        "window_until": until,
        "start": str(df["time"].iloc[0]),
        "end": str(df["time"].iloc[-1]),
        "cost_bps": cost_bps,
        "entry_guard": "off" if not entry_guard else "gap_bar|near_market_close",
    }
    # long_only=False: S-04 trades both sides (the registry says "long/short").
    return run_strategy(build_rule(df), bars, cost_bps, long_only=False, meta=meta)


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
    """Matrix-runner entry point (keyword-compatible with :func:`run_squeeze`)."""
    return run_squeeze(parquet, instrument, timeframe, since, until,
                       cost_bps, entry_guard, oos_token=oos_token)


__all__ = [
    "SqueezeState",
    "build_rule",
    "load_squeeze_bars",
    "run_squeeze",
    "run",
    "SQZ_COL",
    "BBMID_COL",
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
