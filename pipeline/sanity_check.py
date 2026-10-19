"""Post-load sanity checks for the 1-minute, 5-minute and 1-hour parquet tables.

Run after ``load_data`` / ``aggregate_ohlcv``::

    python -m pipeline.sanity_check

Exit code is 1 if duplicate (instrument, time) keys, self-contradicting OHLC
bars, or over-full aggregated bars are found.  Gaps and partial bars are only
reported: weekends and session breaks are expected, a missing block for one
instrument (e.g. a failed API request) shows up as an unusually large
``max_gap`` / ``gaps_over_6h`` compared with similar instruments.
"""

from __future__ import annotations

import sys
from pathlib import Path

import duckdb

ONE_MIN = Path("data/all_data/all_data.parquet")
BARS = {
    "5m": (Path("data/ohlcv_5m/ohlcv_5m.parquet"), 5),
    "1h": (Path("data/ohlcv_1h/ohlcv_1h.parquet"), 60),
}
MIN_COLS = ("mid_o", "mid_h", "mid_l", "mid_c")
BAR_COLS = ("open", "high", "low", "close")


def _bad_ohlc(o: str, hi: str, lo: str, c: str) -> str:
    return f"({hi} < GREATEST({o}, {c}, {lo}) OR {lo} > LEAST({o}, {c}, {hi}) OR {lo} <= 0)"


def check_table(conn, name: str, path: Path, cols: tuple, full_bars: int | None = None) -> int:
    """Print a report for one table; return the number of hard problems."""
    print(f"\n=== {name}: {path} ===")
    if not path.exists():
        print("MISSING: file not found")
        return 1
    src = f"read_parquet('{path.as_posix()}')"

    # Coverage and gaps per instrument (compare instruments with each other).
    conn.sql(f"""
        WITH g AS (
            SELECT instrument, time,
                   time - lag(time) OVER (PARTITION BY instrument ORDER BY time) AS gap
            FROM {src})
        SELECT instrument, count(*) AS rows, min(time)::VARCHAR AS first,
               max(time)::VARCHAR AS last, max(gap) AS max_gap,
               count(*) FILTER (gap > INTERVAL 6 HOUR) AS gaps_over_6h
        FROM g GROUP BY 1 ORDER BY 1""").show(max_rows=200, max_width=200)

    dups = conn.sql(
        f"SELECT count(*) FROM (SELECT 1 FROM {src} GROUP BY instrument, time HAVING count(*) > 1)"
    ).fetchone()[0]
    bad = conn.sql(f"SELECT count(*) FROM {src} WHERE {_bad_ohlc(*cols)}").fetchone()[0]
    print(f"duplicate (instrument, time) keys: {dups} | bad OHLC bars: {bad}")
    problems = int(dups > 0) + int(bad > 0)

    if full_bars:  # aggregated tables: how many buckets are incomplete?
        conn.sql(f"""
            SELECT instrument, count(*) AS bars,
                   count(*) FILTER (n_bars < {full_bars}) AS partial_bars,
                   round(100.0 * count(*) FILTER (n_bars < {full_bars}) / count(*), 1) AS partial_pct,
                   count(*) FILTER (n_bars > {full_bars}) AS overfull_bars
            FROM {src} GROUP BY 1 ORDER BY 1""").show(max_rows=200, max_width=200)
        overfull = conn.sql(f"SELECT count(*) FROM {src} WHERE n_bars > {full_bars}").fetchone()[0]
        problems += int(overfull > 0)
    return problems


def main() -> int:
    conn = duckdb.connect()
    conn.execute("SET TimeZone = 'UTC'")
    problems = check_table(conn, "1-minute", ONE_MIN, MIN_COLS)
    for name, (path, full) in BARS.items():
        problems += check_table(conn, name, path, BAR_COLS, full_bars=full)
    print(f"\n{'PROBLEMS FOUND: ' + str(problems) if problems else 'OK: no hard problems found'}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())