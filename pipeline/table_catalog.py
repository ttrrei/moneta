"""Register Parquet-backed data tables in DuckDB metadata and SQL views."""

from __future__ import annotations

import json
import re
from pathlib import Path

import duckdb


def _quote_ident(name: str) -> str:
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
        raise ValueError(f"Invalid table name: {name!r}")
    return '"' + name + '"'


def _quote_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def ensure_catalog(conn: duckdb.DuckDBPyConnection) -> None:
    """Create the metadata registry, leaving ingestion history intact."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS data_tables (
            table_name VARCHAR PRIMARY KEY,
            parquet_path VARCHAR NOT NULL,
            row_count BIGINT NOT NULL,
            schema_json JSON NOT NULL,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )


def register_parquet_table(
    conn: duckdb.DuckDBPyConnection,
    table_name: str,
    parquet_path: str | Path,
    row_count: int | None = None,
) -> int:
    """Record Parquet metadata and expose the data as a DuckDB view.

    The view is only a pointer to the Parquet file; it does not copy the data
    into the DuckDB database file.
    """
    quoted_name = _quote_ident(table_name)
    path = Path(parquet_path).resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Parquet file not found: {path}")
    path_sql = _quote_literal(path.as_posix())

    schema_rows = conn.execute(
        f"DESCRIBE SELECT * FROM read_parquet({path_sql})"
    ).fetchall()
    schema = [
        {"name": row[0], "type": row[1], "nullable": row[2]}
        for row in schema_rows
    ]
    if row_count is None:
        row_count = int(
            conn.execute(f"SELECT COUNT(*) FROM read_parquet({path_sql})").fetchone()[0]
        )

    ensure_catalog(conn)
    conn.execute(
        """
        INSERT INTO data_tables (table_name, parquet_path, row_count, schema_json, updated_at)
        VALUES (?, ?, ?, ?, now())
        ON CONFLICT (table_name) DO UPDATE SET
            parquet_path = excluded.parquet_path,
            row_count = excluded.row_count,
            schema_json = excluded.schema_json,
            updated_at = now()
        """,
        [table_name, path.as_posix(), row_count, json.dumps(schema)],
    )

    existing = conn.execute(
        """
        SELECT table_type FROM information_schema.tables
        WHERE table_schema = 'main' AND table_name = ?
        """,
        [table_name],
    ).fetchone()
    if existing:
        if existing[0] == "VIEW":
            conn.execute(f"DROP VIEW main.{quoted_name}")
        else:
            conn.execute(f"DROP TABLE main.{quoted_name}")
    conn.execute(
        f"CREATE VIEW main.{quoted_name} AS "
        f"SELECT * FROM read_parquet({path_sql})"
    )
    return row_count
