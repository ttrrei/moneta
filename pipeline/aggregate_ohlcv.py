"""Aggregate clean 1-minute OHLCV bars into 5-minute and 1-hour bars.

The Bronze 1-minute bars in ``data/all_data/all_data.parquet`` (UTC
timestamptz) are bucketed on UTC boundaries.  Open/close are taken from the
first/last 1-minute bar in each bucket; high/low and volume are aggregated
normally.  Every output bar carries ``n_bars`` (how many 1-minute bars were
available) so partial bars caused by gaps or session edges can be identified
downstream.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import duckdb

DEFAULT_DB_PATH = Path("data/metadata.duckdb")
DEFAULT_INPUT_PARQUET = Path("data/all_data/all_data.parquet")
DEFAULT_5M_OUTPUT = Path("data/ohlcv_5m/ohlcv_5m.parquet")
DEFAULT_1H_OUTPUT = Path("data/ohlcv_1h/ohlcv_1h.parquet")

REQUIRED_COLUMNS = ("instrument", "time", "mid_o", "mid_h", "mid_l", "mid_c", "volume")
INTERVALS = (("main.ohlcv_5m", "5 minutes"), ("main.ohlcv_1h", "1 hour"))


def _quote_ident(name: str) -> str:
    """Quote a single SQL identifier."""
    return '"' + name.replace('"', '""') + '"'


def _quote_literal(value: str) -> str:
    """Quote a single SQL string literal."""
    return "'" + value.replace("'", "''") + "'"


def _connect(db_path: str | Path | None) -> duckdb.DuckDBPyConnection:
    """Connect to *db_path* if it exists; otherwise use an in-memory database."""
    if db_path is not None and Path(db_path).exists():
        return duckdb.connect(str(db_path))
    return duckdb.connect()


def _metadata_parquet_path(conn: duckdb.DuckDBPyConnection) -> Optional[Path]:
    """Best-effort lookup of the loaded 1-minute parquet path from metadata.duckdb."""
    try:
        rows = conn.execute(
            "SELECT parquet_path FROM loaded_tables "
            "WHERE table_name = 'all_data' ORDER BY loaded_at DESC LIMIT 1;"
        ).fetchall()
    except duckdb.Error:
        try:
            rows = conn.execute(
                "SELECT parquet_path FROM loaded_tables ORDER BY loaded_at DESC LIMIT 1;"
            ).fetchall()
        except duckdb.Error:
            return None

    if not rows or not rows[0] or not rows[0][0]:
        return None
    return Path(rows[0][0])


def _resolve_source(
    conn: duckdb.DuckDBPyConnection,
    db_path: str | Path | None,
    input_parquet_path: str | Path | None,
) -> str:
    """Return the SQL object name (table or TEMP view) holding the 1-minute rows."""
    if input_parquet_path is not None:
        path = Path(input_parquet_path)
        if not path.exists():
            raise FileNotFoundError(f"Input parquet not found: {path.resolve()}")
        conn.execute(
            f"CREATE OR REPLACE TEMP VIEW _moneta_one_minute AS "
            f"SELECT * FROM read_parquet({_quote_literal(path.as_posix())});"
        )
        return "_moneta_one_minute"

    # Fall back to a persisted all_data table if the caller put data in DuckDB.
    try:
        exists = conn.execute(
            "SELECT COUNT(*) FROM information_schema.tables "
            "WHERE table_schema = 'main' AND table_name = 'all_data';"
        ).fetchone()[0]
    except duckdb.Error:
        exists = 0
    if exists:
        return "main.all_data"

    # Fall back to the path recorded by load_data.py, then to the conventional path.
    path = _metadata_parquet_path(conn) or DEFAULT_INPUT_PARQUET
    if not path.exists():
        raise FileNotFoundError(
            "Could not locate the 1-minute parquet. "
            f"Tried {path.resolve()} (and metadata.duckdb). "
            "Run pipeline.load_data first or pass input_parquet_path."
        )
    conn.execute(
        f"CREATE OR REPLACE TEMP VIEW _moneta_one_minute AS "
        f"SELECT * FROM read_parquet({_quote_literal(path.as_posix())});"
    )
    return "_moneta_one_minute"


def _resolve_columns(conn: duckdb.DuckDBPyConnection, source: str) -> dict[str, str]:
    """Map each required column to its actual name in *source* (case-insensitive)."""
    rows = conn.execute(f"DESCRIBE {source};").fetchall()
    actual = {row[0].lower(): row[0] for row in rows if row}
    missing = [col for col in REQUIRED_COLUMNS if col not in actual]
    if missing:
        raise ValueError(
            f"Required columns {missing} not found in {source} "
            f"(have {sorted(actual.values())})"
        )
    resolved = {col: actual[col] for col in REQUIRED_COLUMNS}
    # Optional: filter incomplete rows if the column is present.
    if "is_complete" in actual:
        resolved["_is_complete"] = actual["is_complete"]
    return resolved


def _build_bars(
    conn: duckdb.DuckDBPyConnection,
    table: str,
    interval: str,
    source: str,
    cols: dict[str, str],
) -> int:
    """Create *table* with OHLCV bars of *interval* from the 1-minute rows."""
    inst = _quote_ident(cols["instrument"])
    time_col = _quote_ident(cols["time"])
    open_col = _quote_ident(cols["mid_o"])
    high_col = _quote_ident(cols["mid_h"])
    low_col = _quote_ident(cols["mid_l"])
    close_col = _quote_ident(cols["mid_c"])
    volume_col = _quote_ident(cols["volume"])

    where_clause = ""
    if "_is_complete" in cols:
        complete_col = _quote_ident(cols["_is_complete"])
        where_clause = f"WHERE {complete_col} = TRUE"

    conn.execute(
        f"""
        CREATE OR REPLACE TABLE {table} AS
        SELECT
            instrument,
            CAST(bucket AS TIMESTAMPTZ) AS time,
            arg_min(mid_o, ts) AS open,
            MAX(mid_h) AS high,
            MIN(mid_l) AS low,
            arg_max(mid_c, ts) AS close,
            SUM(volume) AS volume,
            COUNT(*) AS n_bars
        FROM (
            SELECT
                {inst} AS instrument,
                CAST({time_col} AS TIMESTAMP) AS ts,
                CAST({open_col} AS DOUBLE) AS mid_o,
                CAST({high_col} AS DOUBLE) AS mid_h,
                CAST({low_col} AS DOUBLE) AS mid_l,
                CAST({close_col} AS DOUBLE) AS mid_c,
                CAST({volume_col} AS DOUBLE) AS volume,
                time_bucket(INTERVAL '{interval}', CAST({time_col} AS TIMESTAMP)) AS bucket
            FROM {source}
            {where_clause}
        )
        GROUP BY instrument, bucket
        ORDER BY instrument, bucket;
        """
    )
    return int(conn.execute(f"SELECT COUNT(*) FROM {table};").fetchone()[0])


def aggregate_ohlcv_data(
    db_path: str | Path | None = DEFAULT_DB_PATH,
    parquet_5m_path: str | Path = DEFAULT_5M_OUTPUT,
    parquet_1h_path: str | Path = DEFAULT_1H_OUTPUT,
    input_parquet_path: str | Path | None = None,
) -> dict[str, int]:
    """Build and export the 5-minute and 1-hour OHLCV bars.

    Args:
        db_path: DuckDB file to connect to.  If it does not exist an in-memory
            database is used and only ``input_parquet_path`` / the conventional
            parquet path is needed.
        parquet_5m_path: Destination Parquet file for the 5-minute bars.
        parquet_1h_path: Destination Parquet file for the 1-hour bars.
        input_parquet_path: Explicit 1-minute input Parquet; overrides any
            source resolved from ``db_path`` or metadata.

    Returns:
        Row count per output table (``main.ohlcv_5m`` / ``main.ohlcv_1h``).

    Raises:
        FileNotFoundError: If no 1-minute input can be located.
        ValueError: If ``main.all_data`` or a required column is missing.
    """
    outputs = [
        ("main.ohlcv_5m", "5 minutes", Path(parquet_5m_path)),
        ("main.ohlcv_1h", "1 hour", Path(parquet_1h_path)),
    ]

    conn = _connect(db_path)
    counts: dict[str, int] = {}
    try:
        conn.execute("SET TimeZone = 'UTC'")
        source = _resolve_source(conn, db_path, input_parquet_path)
        cols = _resolve_columns(conn, source)

        for table, interval, target in outputs:
            _build_bars(conn, table, interval, source, cols)
            target.parent.mkdir(parents=True, exist_ok=True)
            conn.execute(
                f"COPY (SELECT * FROM {table} ORDER BY instrument, time) "
                f"TO {_quote_literal(target.as_posix())} (FORMAT PARQUET);"
            )
            counts[table] = int(conn.execute(f"SELECT COUNT(*) FROM {table};").fetchone()[0])
            print(f"-> Created {table} with {counts[table]} rows; saved to {target}")
    finally:
        conn.close()

    return counts


# Backwards-friendly aliases.
def aggregate_ohlcv(*args, **kwargs) -> dict[str, int]:
    return aggregate_ohlcv_data(*args, **kwargs)


aggregate = aggregate_ohlcv_data


def main() -> None:
    counts = aggregate_ohlcv_data()
    print(f"OHLCV aggregation completed: {counts}")


if __name__ == "__main__":
    main()
