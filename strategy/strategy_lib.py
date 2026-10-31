"""Shared strategy data + evaluation core (one place every strategy uses).

Why this exists
---------------
Each strategy previously re-implemented parquet loading, the timeframe guard,
and the metric glue. That duplicated the same ~60 lines and let the pieces drift
(see the legacy reviews' "per-strategy accounting / metric drift" findings).

This module owns only the *shared* bits:

* :func:`load_bars` — read a strategy's columns from the feature parquet with a
  ``since``/``until`` window (the ``until`` cap is what keeps in-sample runs
  off the OOS holdout).
* :func:`make_bars` — build the engine :class:`~strategy.engine.BarFrame`,
  including the B1 timeframe guard and the B6 entry-guard mask.
* :func:`run_strategy` — run the shared :func:`~strategy.engine.run_backtest`
  over an already-built frame and rule, and attach the trade distribution.
* :func:`trade_distribution` — bucket each closed trade by its entry bar's
  calendar month (1-12) and weekday (Mon=0..Thu=4), the check the strategy
  review asks for: are the opportunities spread across the year/week, or
  clustered? (A cluster would mean the edge — if any — is seasonal.)

Strategy files (``strategy_rsi_lib.py``, ``strategy_supertrend_lib.py``,
``strategy_ema_spread_lib.py``, ...) therefore only declare *what signal* to
trade: a rule builder plus the columns they read. They never re-implement
loading, the guard, or the metrics.

Note:
   ``run_strategy`` intentionally builds a **fresh rule** per cell. The engine
   calls ``rule.desired_position`` once per bar in a single sequential pass, so
   a stateful rule's internal state is meaningful *within* a run but is not
   reset between separate ``run_backtest`` calls — reusing one rule object
   across cost tiers would leak leftover state. Keep rules fresh even when
   their input frames are shared by a scoped in-sample cache.
"""

from __future__ import annotations

from collections.abc import Sequence
from collections import OrderedDict
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path

import numpy as np
import pandas as pd

from strategy.engine import BarFrame, run_backtest

FEATURES_PARQUET = "data/ohlcv_5m_features/ohlcv_5m_features.parquet"
FEATURES_1H_PARQUET = "data/ohlcv_1h_features/ohlcv_1h_features.parquet"

#: Expected bar interval per timeframe (used to *reject* loading the wrong
#: table by accident — the B1 silent 1h-on-5m failure from the legacy reviews).
TIMEFRAME_SECONDS = {"5m": 300, "1h": 3600}
TIMEFRAME_PARQUET = {"5m": FEATURES_PARQUET, "1h": FEATURES_1H_PARQUET}

#: Columns every strategy's data load always needs (pricing + entry-guard flags).
BASE_COLS = ("time", "open", "close", "is_gap_bar", "is_near_market_close")


def entry_gate_allows(enabled: bool, close: np.ndarray | None,
                      ema: np.ndarray | None, index: int) -> bool:
    """An enabled trend gate needs both finite inputs; missing data blocks entry."""
    return not enabled or bool(close is not None and ema is not None
                               and np.isfinite(close[index]) and np.isfinite(ema[index])
                               and close[index] > ema[index])

_BAR_CACHE: ContextVar = ContextVar("in_sample_bar_cache", default=None)


@contextmanager
def cache_bars(max_bytes: int = 128 * 1024 * 1024):
    """Bounded, thread-local reuse within one in-sample evaluation group.

    Every read still passes the holdout gate. No holdout frame is cached, and
    callers receive copies so a rule cannot mutate another cell's inputs.
    File identity and timestamps invalidate entries after a data replacement.
    The cache is discarded on leaving this scope; nothing is persisted.
    """
    token = _BAR_CACHE.set({"frames": OrderedDict(), "bytes": 0, "limit": max_bytes})
    try:
        yield
    finally:
        _BAR_CACHE.reset(token)


def detect_bar_seconds(df: pd.DataFrame) -> int:
    """Median bar interval in seconds, from consecutive ``time`` diffs.

    Robust to gaps/holidays (median, not mean) and used to verify the loaded
    table matches the requested timeframe.
    """
    if len(df) < 3:
        return 0
    ns = np.asarray(pd.to_datetime(df["time"], utc=True),
                    dtype="datetime64[ns]").view("int64")
    diffs = np.diff(ns) // 1_000_000_000  # ns -> s
    diffs = diffs[diffs > 0]
    if len(diffs) == 0:
        return 0
    return int(np.median(diffs))


def load_bars(
    parquet: str,
    instrument: str,
    feature_cols: list[str] | tuple[str, ...],
    not_null_cols: list[str] | tuple[str, ...] | None = None,
    since: str | None = None,
    until: str | None = None,
    oos_token: object | None = None,
) -> pd.DataFrame:
    """Load a strategy's columns from the feature parquet, windowed.

    ``feature_cols`` are the *extra* (beyond :data:`BASE_COLS`) columns the
    strategy reads. ``not_null_cols`` are dropped where NaN (each indicator has
    a warm-up / NaN head). ``until`` caps the window at the day before the OOS
    holdout for in-sample windows (config/strategies.yml), so in-sample runs can
    never tune on holdout data (repo_review_20261027 §1.1).

    The holdout gate now lives here, in the data layer (follow-up review of
    repo_review_20261029): a window that reaches the holdout (``until`` unset,
    i.e. "read everything", or ``until`` on/after ``oos.holdout_start``) is
    **refused** unless ``oos_token`` is a valid :class:`strategy.oos_token.
    OOSToken`. That token is only ever minted by ``run_matrix`` after it has
    appended a committed ledger reservation — so a new script or an AI session
    calling ``load_bars`` directly cannot read the holdout (``assert_access``
    is fail-closed and re-verifies the token against the ledger).
    """
    import duckdb

    from strategy import oos_token as _oos
    _oos.assert_access(until, oos_token)
    # Normalise ONCE and use that exact value in the SQL (review follow-up #3
    # §B1): what the gate checked is what DuckDB reads. An offset-aware bound
    # is converted to a UTC instant, so the gate and the query can never
    # disagree about the window.
    _since = _oos.normalize_bound(since) if since else None
    _until, exclusive = _oos.query_until(until)

    cache = _BAR_CACHE.get() if not _oos.is_holdout_until(until) else None
    key = None
    if cache is not None:
        try:
            path = Path(parquet).resolve()
            stat = path.stat()
            key = (str(path), stat.st_dev, stat.st_ino, stat.st_size,
                   stat.st_mtime_ns, stat.st_ctime_ns, instrument,
                   tuple(feature_cols), tuple(not_null_cols or ()), _since, _until, exclusive)
        except OSError:
            pass  # Globs/remote paths remain normal uncached DuckDB reads.
        if key in cache["frames"]:
            cache["frames"].move_to_end(key)
            return cache["frames"][key].copy(deep=True)

    cols = list(BASE_COLS) + [c for c in feature_cols if c not in BASE_COLS]
    conn = duckdb.connect()
    try:
        # Pin the session timezone so the ``until`` date bound is interpreted
        # identically on every machine (review 2026-10-28 §4.1: a date-only
        # bound is otherwise read in the local timezone and the "fixed anchor"
        # drifts ~10h between machines). The pipeline does the same.
        conn.execute("SET TimeZone = 'UTC'")
        where = ["instrument = ?"]
        params: list = [parquet, instrument]
        for col in (not_null_cols or ()):
            where.append(f"{col} IS NOT NULL")
        if _since:
            where.append("time >= ?")
            params.append(_since)
        if _until:
            where.append("time < ?" if exclusive else "time <= ?")
            params.append(_until)
        sql = (
            "SELECT " + ", ".join(cols) +
            " FROM read_parquet(?) WHERE " + " AND ".join(where) +
            " ORDER BY time"
        )
        frame = conn.execute(sql, params).fetch_df()
    finally:
        conn.close()
    if cache is not None and key is not None:
        size = int(frame.memory_usage(index=True, deep=True).sum())
        if size <= cache["limit"]:
            while cache["frames"] and cache["bytes"] + size > cache["limit"]:
                _, previous = cache["frames"].popitem(last=False)
                cache["bytes"] -= int(previous.memory_usage(index=True, deep=True).sum())
            cache["frames"][key] = frame.copy(deep=True)
            cache["bytes"] += size
    return frame


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


def trade_distribution(bars: BarFrame, trades: Sequence) -> dict:
    """Bucket each closed trade by the *entry* bar's calendar month (1-12) and
    weekday (Mon=0 .. Sun=6, all seven days).

    This is the check the strategy review asks for: are the trading
    opportunities spread across the year / the week, or clustered in a few
    months or days? (A cluster means the edge — if any — is seasonal, not
    general.) All seven weekdays are reported because crypto is a 24/7 market —
    folding the weekend into a weekday would hide real weekend volume.
    ``entry_time`` is the index of the bar whose open filled the entry, so we
    read it back off ``bars.time``.
    """
    if not trades or len(bars.time) == 0:
        return {"by_month": [0] * 12, "by_weekday": [0] * 7}
    times = pd.DatetimeIndex(bars.time, tz="UTC")  # DatetimeIndex has .month/.weekday
    months = times.month
    weekdays = times.weekday  # Mon=0 .. Sun=6
    idx = [t.entry_time for t in trades if t.entry_time < len(bars.time)]
    by_month = [0] * 12
    by_weekday = [0] * 7
    for i in idx:
        by_month[months[i] - 1] += 1
        by_weekday[weekdays[i]] += 1
    return {"by_month": by_month, "by_weekday": by_weekday}


def run_strategy(
    rule: object,
    bars: BarFrame,
    cost_bps: float,
    long_only: bool,
    meta: dict | None = None,
) -> dict:
    """Run the shared engine over an already-built ``bars``/``rule`` pair.

    A frame can be reused across cost tiers, but each evaluation must receive
    a fresh rule. Signals and accounting are currently evaluated per cost tier;
    the scoped cache only removes repeated data reads.
    """
    result = run_backtest(bars, rule, cost_bps=cost_bps, long_only=long_only)
    out = dict(meta or {})
    out["n_bars_blocked"] = int(bars.no_entry_mask.sum()) if bars.no_entry_mask is not None else 0
    out.update(result.to_dict())
    out["trade_distribution"] = trade_distribution(bars, result.trades)
    return out
