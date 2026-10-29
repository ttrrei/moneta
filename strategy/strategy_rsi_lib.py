"""S-01 RSI strategy as a reusable library (signal + data loading).

Split out of ``strategy/code/strategy_rsi.py`` (the CLI) so that
``strategy/run_matrix.py`` can run the same rule across instruments / windows /
cost tiers without duplicating the rule or the parquet loading.

The rule itself is unchanged (S-01, registry): long when ``rsi_24`` on the
previous closed bar < 30, exit when > 55. All accounting and metrics live in
``strategy/engine.py``.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from strategy.engine import BarFrame, run_backtest

FEATURES_PARQUET = "data/ohlcv_5m_features/ohlcv_5m_features.parquet"
FEATURES_1H_PARQUET = "data/ohlcv_1h_features/ohlcv_1h_features.parquet"
RSI_COL = "rsi_24"
COST_BPS = 2.0  # one-way transaction cost, basis points

#: Expected bar interval per timeframe (used to *reject* loading the wrong
#: table by accident — the B1 silent 1h-on-5m failure from the legacy reviews).
TIMEFRAME_SECONDS = {"5m": 300, "1h": 3600}
TIMEFRAME_PARQUET = {"5m": FEATURES_PARQUET, "1h": FEATURES_1H_PARQUET}


class RsiState:
    """Long-only RSI-24 mean-reversion signal (the S-01 rule).

    ``desired_position(i)`` = the position to hold at the open of bar ``i``,
    decided from the RSI value on the *previous* closed bar ``i-1``.
    """

    def __init__(self, rsi: np.ndarray) -> None:
        self.rsi = rsi
        self.state = 0  # 0 flat, 1 long

    def desired_position(self, i: int) -> int:
        if i == 0:
            return 0
        r = self.rsi[i - 1]
        if np.isfinite(r):
            if r < 30.0:
                self.state = 1
            elif r > 55.0:
                self.state = 0
        return self.state


def load_bars(
    parquet: str,
    instrument: str,
    since: str | None = None,
    until: str | None = None,
    oos_token: object | None = None,
) -> pd.DataFrame:
    """Load ``time, open, close, is_gap_bar, is_near_market_close, rsi_24``.

    The flag columns feed the B6 entry guard (no new entries on gap / near
    market-close bars); strategies that do not want the guard can ignore them.

    ``until`` caps the window at the day before the OOS holdout for
    in-sample windows (config/strategies.yml), so in-sample runs can never
    tune on holdout data (repo_review_20261027 §1.1).

    The holdout gate lives here in the data layer (follow-up review): a window
    that reaches the holdout (``until`` unset, or on/after
    ``oos.holdout_start``) is **refused** unless ``oos_token`` is a valid
    :class:`strategy.oos_token.OOSToken` minted by ``run_matrix`` after a
    committed ledger reservation. A direct ``load_bars(until=None)`` call
    cannot read the holdout.
    """
    import duckdb

    from strategy import oos_token as _oos
    _oos.assert_access(until, oos_token)

    conn = duckdb.connect()
    try:
        # Pin the session timezone so the ``until`` date bound is interpreted
        # identically on every machine (review 2026-10-28 §4.1).
        conn.execute("SET TimeZone = 'UTC'")
        where = ["instrument = ?", RSI_COL + " IS NOT NULL"]
        params: list = [parquet, instrument]
        if since:
            where.append("time >= ?")
            params.append(since)
        if until:
            if _oos.is_holdout_until(until):
                # OOS/holdout read: exclusive end (first day after the
                # holdout) → ``time < until`` excludes that day's first bar.
                where.append("time < ?")
            else:
                # In-sample read: ``until`` is the *inclusive* last bar's date.
                where.append("time <= ?")
            params.append(until)
        sql = (
            "SELECT time, open, close, is_gap_bar, is_near_market_close, " + RSI_COL +
            " FROM read_parquet(?) WHERE " + " AND ".join(where) +
            " ORDER BY time"
        )
        return conn.execute(sql, params).fetch_df()
    finally:
        conn.close()


def detect_bar_seconds(df: pd.DataFrame) -> int:
    """Median bar interval in seconds, from consecutive ``time`` diffs.

    Robust to gaps/holidays (median, not mean) and used to verify the loaded
    table matches the requested timeframe.
    """
    if len(df) < 3:
        return 0
    t = df["time"]
    # Convert to int64 nanoseconds (robust for tz-aware Timestamps).
    ns = np.asarray(pd.to_datetime(t, utc=True), dtype="datetime64[ns]").view("int64")
    diffs = np.diff(ns) // 1_000_000_000  # ns -> s
    diffs = diffs[diffs > 0]
    if len(diffs) == 0:
        return 0
    return int(np.median(diffs))


def make_bars(df: pd.DataFrame, timeframe: str, entry_guard: bool = False) -> BarFrame:
    """Build an engine :class:`BarFrame` from a loaded frame.

    ``entry_guard=True`` enables the B6 rule: no *new* entries on
    ``is_gap_bar`` / ``is_near_market_close`` bars (exits are never blocked).
    Default OFF to match the documented S-01 baseline (the registry and the
    published report both record entry-guard **off**).
    """
    expected_seconds = TIMEFRAME_SECONDS[timeframe]

    # B1 guard: refuse to run a 1h rule on 5m data (or vice versa).
    observed = detect_bar_seconds(df)
    if observed and abs(observed - expected_seconds) > expected_seconds / 2:
        raise SystemExit(
            f"Timeframe mismatch: timeframe {timeframe} expects ~"
            f"{expected_seconds}s bars, but the loaded table has ~{observed}s bars. "
            f"Pass the matching parquet or the matching timeframe."
        )

    no_entry = None
    if entry_guard:
        no_entry = (
            (df["is_gap_bar"].fillna(0).to_numpy(np.float64) > 0)
            | (df["is_near_market_close"].fillna(0).to_numpy(np.float64) > 0)
        )

    return BarFrame(
        open=df["open"].to_numpy(np.float64),
        close=df["close"].to_numpy(np.float64),
        time=df["time"].to_numpy(),
        bar_seconds=expected_seconds,
        no_entry_mask=no_entry,
    )


def run_rsi(
    parquet: str,
    instrument: str,
    timeframe: str = "5m",
    since: str | None = None,
    until: str | None = None,
    cost_bps: float = COST_BPS,
    entry_guard: bool = False,
    oos_token: object | None = None,
) -> dict:
    """Run the S-01 rule for one instrument / window / cost tier.

    ``entry_guard`` defaults to OFF, matching the documented S-01 baseline
    (registry + report both record entry-guard off) and the CLI.

    ``oos_token`` is required for a window that reaches the OOS holdout (the
    data-layer gate); in-sample windows load with no token.

    Returns the full result dict (metadata + engine metrics block) in the same
    shape the CLI prints — ready to serialise to JSON.
    """
    df = load_bars(parquet, instrument, since, until, oos_token=oos_token)
    if len(df) < 1_000:
        raise SystemExit(f"Only {len(df)} bars loaded for {instrument} "
                         f"(window {since or 'start'}..{until or 'latest'}); not enough to backtest.")

    bars = make_bars(df, timeframe, entry_guard=entry_guard)
    result = run_backtest(bars, RsiState(df[RSI_COL].to_numpy(np.float64)),
                          cost_bps=cost_bps, long_only=True)
    return {
        "strategy_id": "S-01",
        "instrument": instrument,
        "timeframe": timeframe,
        "window_since": since,
        "window_until": until,
        "start": str(df["time"].iloc[0]),
        "end": str(df["time"].iloc[-1]),
        "cost_bps": cost_bps,
        "entry_guard": "off" if not entry_guard else "gap_bar|near_market_close",
        "n_bars_blocked": int(bars.no_entry_mask.sum()) if bars.no_entry_mask is not None else 0,
        **result.to_dict(),
    }


__all__ = [
    "RsiState",
    "load_bars",
    "detect_bar_seconds",
    "make_bars",
    "run_rsi",
    "FEATURES_PARQUET",
    "FEATURES_1H_PARQUET",
    "RSI_COL",
    "COST_BPS",
    "TIMEFRAME_SECONDS",
    "TIMEFRAME_PARQUET",
]
