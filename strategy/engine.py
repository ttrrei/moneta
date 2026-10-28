"""Shared backtest engine — the single source of truth for accounting & metrics.

Why this exists
---------------
The reference strategy (:mod:`strategy.code.strategy_rsi`) previously embedded
its own ~120-line event loop and its own metric definitions. That meant every
new strategy re-implemented accounting (and could silently diverge), and the
``sharpe`` figure was *per-trade Sharpe scaled by ``sqrt(n_trades * 12)``* — a
number that grows with the sample's *length* (trade count) rather than with the
*rate* of trading, so it cannot be compared across strategies or windows
(legacy reviews, finding B2).

This module centralises the two things that must be identical everywhere:

1.  **Accounting** — one event loop: a signal computed on a *closed* bar ``T``
    fills at the *open of bar T+1*; one-way cost is applied at **both** legs;
    one position at a time; an open position is force-closed at the last bar's
    close. Long and short are both supported (``long_only`` clamps shorts).
2.  **Metrics** — one definition of every headline number. ``METRIC_FORMULAS``
    is the documented contract and must stay in sync with SAD §7.2.

A strategy file therefore only declares *what signal* it trades (a
:func:`SignalRule`) and hands the bars to :func:`run_backtest`. It never
re-implements the loop or the metrics.

Determinism
-----------
The engine is pure: same bars + same rule + same cost → same
:class:`BacktestResult`. No clock, no network, no global state (SAD §5 #5).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, Sequence

import numpy as np

#: One unit (1 USD notional / 1 FX base unit / 1 coin). Metrics are returns, so
#: size cancels out, but every strategy uses the same unit so long/short stay
#: comparable.
UNIT_SIZE = 1.0


@dataclass(frozen=True)
class BarFrame:
    """One instrument's bars in time order, as the engine consumes them.

    Attributes
    ----------
    open / close : float64 1-D arrays aligned to ``time``.
    time         : tz-aware UTC datetime array (or None); used only to derive
                   the annualisation span, never for pricing.
    bar_seconds  : nominal bar interval (300 for 5m, 3600 for 1h).
    no_entry_mask: optional boolean array; bars where **no new entry** may be
                   filled (STRATEGY_BACKGROUND rule: no entries on gap bars /
                   near market close). Exits are *not* blocked by this mask —
                   only fresh position openings.
    """

    open: np.ndarray
    close: np.ndarray
    time: np.ndarray | None = None
    bar_seconds: int = 300
    no_entry_mask: np.ndarray | None = None


@dataclass(frozen=True)
class Trade:
    """A single closed round-trip (entry filled, then exit filled)."""

    direction: int          # +1 long, -1 short
    entry_time: int         # index of the bar whose open was the entry fill
    entry_price: float
    exit_time: int          # index of the bar whose open (or final close) exited
    exit_price: float
    net_pnl: float          # P&L after costs, in units of UNIT_SIZE
    bars_held: int


@dataclass
class BacktestResult:
    """The standard metrics block — the exact shape every strategy reports.

    Public (``*_pct``, ``sharpe``) fields are rounded for the report/JSON.
    The ``raw_*`` fields hold the *unrounded* values, used by the golden tests
    (``tests/test_metrics.py``) to pin exact metric definitions.

    Field names are the public contract (SAD §7.1) and must not change.
    """

    n_bars: int
    n_trades: int
    total_return_pct: float
    buyhold_return_pct: float
    max_drawdown_pct: float
    win_rate_pct: float
    avg_trade_return_pct: float
    sharpe: float                 # annualised, trade-rate based (NOT comparable across strategies — see METRIC_FORMULAS)
    exposure_pct: float
    span_years: float             # observed window length in (fractional) years
    trades: Sequence[Trade] = field(default_factory=list, repr=False)
    # Unrounded (test-internal) values:
    raw_total_return_pct: float = 0.0
    raw_buyhold_return_pct: float = 0.0
    raw_max_drawdown_pct: float = 0.0
    raw_win_rate_pct: float = 0.0
    raw_avg_trade_return_pct: float = 0.0
    raw_sharpe: float = 0.0
    raw_exposure_pct: float = 0.0

    def to_dict(self) -> dict:
        """JSON-serialisable metrics block (the ``trades`` ledger is omitted)."""
        return {
            "n_bars": self.n_bars,
            "n_trades": self.n_trades,
            "total_return_pct": self.total_return_pct,
            "buyhold_return_pct": self.buyhold_return_pct,
            "max_drawdown_pct": self.max_drawdown_pct,
            "win_rate_pct": self.win_rate_pct,
            "avg_trade_return_pct": self.avg_trade_return_pct,
            "sharpe": self.sharpe,
            "exposure_pct": self.exposure_pct,
            "span_years": round(self.span_years, 4),
        }


class SignalRule(Protocol):
    """A strategy's declarative signal.

    ``desired_position(i)`` returns the position to be *held at the open of bar
    i*, computed only from information available at the **close of bar i-1**
    (the engine fills at bar i's open, so a rule reading ``*_{i-1}`` never has
    same-bar lookahead).

    Returns:
        ``+1`` long, ``-1`` short, ``0`` flat.
    """

    def desired_position(self, i: int) -> int: ...


@dataclass
class FlatRule:
    """A rule that is always flat — a baseline / test fixture."""

    def desired_position(self, i: int) -> int:
        return 0


def _span_years(time: np.ndarray | None, n_bars: int, bar_seconds: int = 300) -> float:
    """Observed window length in fractional years, from the timestamps.

    Falls back to the nominal bar cadence (24/7) when ``time`` is unavailable;
    the fallback uses the frame's ``bar_seconds`` so 1h bars are not annualised
    as 5m (legacy review: ``_span_years`` hard-coded 300s and
    ``BarFrame.bar_seconds`` was never read).
    """
    if time is not None and len(time) > 1:
        diff = time[-1] - time[0]
        span_seconds = float(diff.total_seconds()
                             if hasattr(diff, "total_seconds")
                             else (int(time[-1]) - int(time[0])) / 1_000_000_000.0)
        return span_seconds / (365.25 * 86_400.0)
    # Fallback: n bars at bar_seconds apart.
    return (n_bars * float(bar_seconds)) / (365.25 * 86_400.0)


def annualised_sharpe(per_trade_returns: Sequence[float], span_years: float) -> float:
    """Annualised, *trade-rate-based* Sharpe (0.0 when it is undefined).

    ``sharpe = mean(tr) / std(tr, ddof=1) * sqrt(n_trades / span_years)``.

    This is the annualised t-statistic of the mean trade: it depends on the
    *rate* of trading (trades per year), not the total count. The *same* edge
    over a longer sample therefore yields the *same* Sharpe — unlike the old
    reference formula ``* sqrt(n_trades * 12)``, which inflated with sample
    length. See :data:`METRIC_FORMULAS`.

    .. note::
       Because it scales with trades/year, two strategies with the *same*
       per-trade edge but *different* trade counts will NOT have comparable
       Sharpes (the higher-frequency one scores higher). Use it to compare the
       SAME strategy across windows/cost tiers only — not to rank strategies
       against each other.
    """
    x = np.asarray(list(per_trade_returns), dtype=np.float64)
    if x.size < 2:
        return 0.0
    sd = x.std(ddof=1)
    if sd <= 0.0:
        return 0.0
    trades_per_year = x.size / span_years if span_years > 0 else 0.0
    return float(x.mean() / sd * np.sqrt(trades_per_year))


def _max_drawdown(equity: np.ndarray) -> float:
    """Max drawdown as a fraction (>= 0) of peak equity."""
    peak = np.maximum.accumulate(equity)
    return float(np.max((peak - equity) / peak))


def run_backtest(
    bars: BarFrame,
    rule: SignalRule,
    cost_bps: float = 2.0,
    long_only: bool = False,
) -> BacktestResult:
    """Run the shared accounting over ``bars`` for ``rule`` at ``cost_bps``.

    Model (must stay consistent with SAD §7.2 and docs/indicators.md §3.3):

    * A signal computed on a *closed* bar ``T`` fills at the **open of bar T+1**.
    * One-way cost ``cost_bps`` is charged at **both** entry and exit.
    * One position at a time; size ``UNIT_SIZE``. Long and short allowed unless
      ``long_only``.
    * An open position is force-closed at the **last bar's close** (counted as a
      trade), so no return is left unbooked.
    * If ``bars.no_entry_mask`` is set, bars flagged there do not accept a
      **new entry from flat** (STRATEGY_BACKGROUND rule: no entries on gap
      bars / near market close); closing an open position is never blocked.

    The per-bar account equity is the compounded value of closed trades times
    the mark-to-market of any open trade — this drives ``total_return_pct`` and
    ``max_drawdown_pct``.
    """
    o = np.asarray(bars.open, dtype=np.float64)
    c = np.asarray(bars.close, dtype=np.float64)
    n = len(c)
    if n < 2:
        raise ValueError("need at least 2 bars to backtest")

    no_entry = bars.no_entry_mask
    if no_entry is not None and len(no_entry) != n:
        raise ValueError("no_entry_mask length must match number of bars")

    cost = cost_bps / 10_000.0
    span_years = _span_years(bars.time, n, bars.bar_seconds)

    # desired[i] = position intended at the open of bar i, from close-of-(i-1)
    # info. ``desired_position`` is called *exactly once per bar* — the old
    # clamp ``0 if long_only and rule(...) < 0 else rule(...)`` evaluated it
    # twice whenever the answer was >= 0, which silently broke any rule with
    # side effects (legacy review 1.6).
    desired = np.array([rule.desired_position(i) for i in range(n)], dtype=np.int8)
    if long_only:
        desired = np.maximum(desired, 0)

    def _trade_ret(px_exit: float, px_entry: float, direction: float) -> float:
        """Return on entry notional, one-way cost at both legs (S-01 convention).

        Long:  buy at px_entry*(1+cost), sell at px_exit*(1-cost)  →
            px_exit*(1-cost) / (px_entry*(1+cost)) - 1
        Short: sell at px_entry*(1-cost), buy back at px_exit*(1+cost) →
            px_entry*(1-cost) / (px_exit*(1+cost)) - 1
        (The pre-fix short formula ``px_entry*(1+cost)/(px_exit*(1-cost)) - 1``
        had the *direction* of the cost effect inverted: higher cost gave a
        higher short return. Legacy review 1.2.)
        """
        if direction > 0:
            return px_exit * (1.0 - cost) / (px_entry * (1.0 + cost)) - 1.0
        return px_entry * (1.0 - cost) / (px_exit * (1.0 + cost)) - 1.0

    pos = 0.0            # signed position held during the bar (after the open fill)
    entry_px = np.nan
    entry_idx = -1
    trades: list[Trade] = []

    equity = np.empty(n)
    in_trade = np.zeros(n, dtype=bool)
    bars_in_market = 0
    base = 1.0           # compounded value of closed trades
    pending_ret: float | None = None  # a trade closed at this bar's open, not yet booked

    for t in range(n):
        px_open = o[t]
        # 1) Fill the intended position change at this bar's open.
        want = int(desired[t])
        if want != pos:
            if no_entry is not None and pos == 0.0 and want != 0 and no_entry[t]:
                # B6 rule: no *new* entries on this bar (gap / near-close).
                # Exits and re-entries (closing + flipping) are not blocked,
                # because the open here already closes an existing position.
                want = 0
        if want != pos:
            if pos != 0.0:  # close the existing position at this bar's open
                direction = 1.0 if pos > 0 else -1.0
                ret = _trade_ret(px_open, entry_px, direction)
                pending_ret = ret
                trades.append(Trade(
                    direction=int(direction),
                    entry_time=entry_idx,
                    entry_price=float(entry_px),
                    exit_time=t,
                    exit_price=float(px_open),
                    net_pnl=float(ret * entry_px * UNIT_SIZE),
                    bars_held=int(t - entry_idx),
                ))
            if want != 0:  # open the new position at this bar's open
                pos = float(want)
                entry_px = px_open
                entry_idx = t
            else:
                pos = 0.0
                entry_px = np.nan
                entry_idx = -1

        # 2) Book any trade that closed at this bar's open (advances `base`).
        if pending_ret is not None:
            base *= 1.0 + pending_ret
            pending_ret = None

        # 3) Mark-to-market at this bar's close.
        if pos != 0.0:
            bars_in_market += 1
            direction = 1.0 if pos > 0 else -1.0
            equity[t] = base * (1.0 + _trade_ret(c[t], entry_px, direction))
        else:
            equity[t] = base
        in_trade[t] = pos != 0.0

    # Force-close an open position at the last close (counted as a trade).
    if pos != 0.0:
        direction = 1.0 if pos > 0 else -1.0
        ret = _trade_ret(c[-1], entry_px, direction)
        base *= 1.0 + ret
        equity[-1] = base
        trades.append(Trade(
            direction=int(direction),
            entry_time=entry_idx,
            entry_price=float(entry_px),
            exit_time=n - 1,
            exit_price=float(c[-1]),
            net_pnl=float(ret * entry_px * UNIT_SIZE),
            bars_held=int(n - 1 - entry_idx),
        ))

    total_return = base - 1.0
    buyhold = c[-1] / o[0] - 1.0
    max_dd = _max_drawdown(equity)

    if trades:
        per_trade_ret = np.array([tr.net_pnl for tr in trades]) / np.array(
            [tr.entry_price for tr in trades]) / UNIT_SIZE
        win_rate = float((per_trade_ret > 0).sum() / len(trades) * 100)
        avg_trade_ret = float(np.mean(per_trade_ret) * 100)
        sharpe = annualised_sharpe(per_trade_ret, span_years)
    else:
        per_trade_ret = np.array([])
        win_rate = 0.0
        avg_trade_ret = 0.0
        sharpe = 0.0

    exposure_raw = bars_in_market / n * 100
    return BacktestResult(
        n_bars=int(n),
        n_trades=int(len(trades)),
        total_return_pct=round(total_return * 100, 2),
        buyhold_return_pct=round(buyhold * 100, 2),
        max_drawdown_pct=round(max_dd * 100, 2),
        win_rate_pct=round(win_rate, 2),
        avg_trade_return_pct=round(avg_trade_ret, 4),
        sharpe=round(sharpe, 2),
        exposure_pct=round(exposure_raw, 2),
        span_years=span_years,
        trades=trades,
        raw_total_return_pct=total_return * 100,
        raw_buyhold_return_pct=buyhold * 100,
        raw_max_drawdown_pct=max_dd * 100,
        raw_win_rate_pct=win_rate,
        raw_avg_trade_return_pct=avg_trade_ret,
        raw_sharpe=sharpe,
        raw_exposure_pct=exposure_raw,
    )


# ---------------------------------------------------------------------------
# Metric definitions — the single, documented source of truth (mirrors SAD §7.2).
# Keep this in sync with docs/SAD.md §7.2 when any formula changes.
# ---------------------------------------------------------------------------
METRIC_FORMULAS: dict[str, str] = {
    "total_return_pct": "Compounded account equity over the window, in %. "
                        "Equity per bar = (product of 1 + closed-trade return) "
                        "x (1 + mark-to-market of the open trade, if any).",
    "buyhold_return_pct": "(close[-1] / open[0]) - 1, in %. Cost-free reference "
                          "for the *identical* window. Caveat: the baseline is "
                          "not cost-bearing while the strategy is.",
    "max_drawdown_pct": "max over bars of (peak_equity - equity) / peak_equity, in %.",
    "win_rate_pct": "fraction of closed trades with net return > 0, in %.",
    "avg_trade_return_pct": "mean per-trade net return (net_pnl / entry notional), in %.",
    "sharpe": "Annualised, trade-rate-based Sharpe: "
              "mean(tr)/std(tr, ddof=1) * sqrt(n_trades / span_years). "
              "WARNING: this REWARDS trade frequency (same per-trade edge with "
              "30x the trades yields ~sqrt(30) higher Sharpe), so it is NOT "
              "comparable across strategies with different trade counts. Use it "
              "only to compare the SAME strategy across windows/cost tiers. "
              "For cross-strategy ranking prefer return-vs-buyhold at 2bps and "
              "max drawdown. A daily-equity Sharpe is a policy change not yet made.",
    "exposure_pct": "fraction of bars with a non-zero position, in %.",
}


__all__ = [
    "BarFrame",
    "Trade",
    "BacktestResult",
    "SignalRule",
    "FlatRule",
    "run_backtest",
    "annualised_sharpe",
    "METRIC_FORMULAS",
    "UNIT_SIZE",
]
