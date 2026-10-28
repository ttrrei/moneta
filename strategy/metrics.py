"""Cross-strategy-comparable metric helpers (pure numpy/pandas — no data).

The existing ``sharpe`` (engine ``annualised_sharpe``) is *trade-rate* based and
rewards trade frequency, so it cannot be used to rank strategies against each
other (see ``METRIC_FORMULAS``). Two metrics that *do* compare across strategies
are defined here:

* ``sharpe_weekly``  — Sharpe of the equity curve resampled to **weekly** closes,
  annualised by ``sqrt(52)``. It depends on the *equity path* (drawups and
  drawdowns), not on how many trades produced it, so two strategies with the
  same equity trajectory get the same Sharpe regardless of trade count. Weekly
  is used (rather than daily) because a sparse strategy can produce too few
  daily samples for a stable estimate (review 2026-10-29, item 3).
* ``trades_per_year`` — how often the strategy trades, surfaced explicitly so a
  strategy that barely trades (few opportunities over the window) is visible and
  not mistaken for a "good" one (review 2026-10-29, item 4).

Both are pure functions of the bar timestamps + equity, so they are unit-testable
without any parquet / data dependency.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def _weekly_equity(equity: np.ndarray, time: np.ndarray | None) -> np.ndarray:
    """Last equity value per (calendar) week, most recent first.

    Falls back to a uniform 5-bar bucket when timestamps are unavailable so the
    helper stays total (never raises) — the engine always supplies timestamps,
    so this path is only a defensive guard.
    """
    n = int(np.size(equity))
    if n < 2 or time is None or np.size(time) != n:
        if n < 2:
            return np.asarray([])
        # No usable timestamps: bucket by 5 bars as a stand-in "week".
        idx = np.arange(n) // 5
        order = np.argsort(idx, kind="stable")
        _, uniq_last = np.unique(idx[order], return_index=True)
        return equity[order][uniq_last[::-1]]

    s = pd.Series(np.asarray(equity, dtype=np.float64),
                  index=pd.DatetimeIndex(pd.to_datetime(time, utc=True)))
    # Last equity within each calendar week, then forward-fill any empty week so
    # percentage change is defined across the full span.
    weekly = s.resample("W").last().ffill().dropna()
    return weekly.to_numpy()


def sharpe_weekly(equity: np.ndarray, time: np.ndarray | None) -> float:
    """Annualised Sharpe of the equity curve on a **weekly** close basis.

    ``mean(weekly_ret) / std(weekly_ret, ddof=1) * sqrt(52)``. Returns 0.0 when
    fewer than 2 weekly returns or zero variance — mirroring the trade-rate
    Sharpe's convention — so a sparse strategy simply scores 0 rather than
    raising.
    """
    weekly = _weekly_equity(equity, time)
    if len(weekly) < 2:
        return 0.0
    rets = np.diff(weekly) / weekly[:-1]
    rets = rets[np.isfinite(rets)]
    if rets.size < 2:
        return 0.0
    sd = rets.std(ddof=1)
    if not np.isfinite(sd) or sd <= 0.0:
        return 0.0
    return float(rets.mean() / sd * np.sqrt(52.0))


def trades_per_year(n_trades: int, span_years: float) -> float:
    """Opportunity frequency: trades per year over the observed window.

    0.0 when the span is unknown/zero. A low value here means the strategy
    produced very few tradable opportunities in the window — useful context the
    raw ``total_return_pct`` alone does not convey (item 4).
    """
    if span_years <= 0:
        return 0.0
    return float(n_trades) / float(span_years)
