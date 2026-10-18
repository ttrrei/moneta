"""Load raw CSV market data into a clean, deduplicated 1-minute Parquet table.

This module upgrades the legacy ``legacy/load_to_duckdb.py`` and
``legacy/clean_data.py`` scripts into a single Bronze→Silver load step:

* Every ``*.csv`` under ``data/raw_csv/`` is read (recursively).
* Rows with ``is_complete`` falsy are dropped.
* Rows are deduplicated on ``(instrument, time)``.
* The resulting 1-minute bars are written to
  ``data/<table_name>/<table_name>.parquet``.
* ``data/metadata.duckdb`` is used only for metadata/tracking; the parquet
  file is the source of truth for the data itself.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import duckdb

DEFAULT_CSV_DIR = Path("data/raw_csv")
DEFAULT_DATA_DIR = Path("data")
DEFAULT_DB_PATH = Path("data/metadata.duckdb")
DEFAULT_TABLE_NAME = "all_data"


def ensure_data_dirs(data_dir: str | Path = DEFAULT_DATA_DIR) -> Path:
    """Ensure the root data directory exists."""
    path = Path(data_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path


def ensure_table_dir(table_name: str, data_dir: str | Path = DEFAULT_DATA_DIR) -> Path:
    """Create and return ``data_dir/<table_name>/`` for a table's parquet files."""
    path = Path(data_dir) / table_name
    path.mkdir(parents=True, exist_ok=True)
    return path


def _csv_glob(csv_dir: str | Path) -> str:
    return (Path(csv_dir) / "**" / "*.csv").as_posix()


def _parquet_path(
    table_name: str,
    data_dir: str | Path,
    parquet_output_path: str | Path | None = None,
) -> Path:
    if parquet_output_path is not None:
        return Path(parquet_output_path)
    return Path(data_dir) / table_name / f"{table_name}.parquet"


def _ensure_metadata_table(conn: duckdb.DuckDBPyConnection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS loaded_tables (
            table_name VARCHAR,
            csv_dir VARCHAR,
            parquet_path VARCHAR,
            row_count BIGINT,
            loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    # The DuckDB file is metadata-only: drop any legacy full-data tables.
    conn.execute("DROP TABLE IF EXISTS main.all_data;")


def load_data(
    csv_dir: str | Path = DEFAULT_CSV_DIR,
    db_path: str | Path = DEFAULT_DB_PATH,
    table_name: str = DEFAULT_TABLE_NAME,
    data_dir: str | Path = DEFAULT_DATA_DIR,
    parquet_output_path: str | Path | None = None,
) -> Optional[Path]:
    """Load, clean, deduplicate and export the 1-minute bars to Parquet.

    Returns the path to the resulting Parquet file, or ``None`` if no CSVs
    were found.
    """
    csv_dir_path = Path(csv_dir)
    db_path_path = Path(db_path)
    data_dir_path = Path(data_dir)

    ensure_data_dirs(data_dir_path)
    ensure_table_dir(table_name, data_dir_path)
    target_parquet = _parquet_path(table_name, data_dir_path, parquet_output_path)
    target_parquet.parent.mkdir(parents=True, exist_ok=True)

    csv_files = sorted(csv_dir_path.rglob("*.csv")) if csv_dir_path.exists() else []
    if not csv_files:
        print(f"No CSV files found in {csv_dir_path.resolve()}")
        return None

    print(f"Found {len(csv_files)} CSV files to load into '{table_name}'.")

    conn = duckdb.connect(str(db_path_path))
    try:
        _ensure_metadata_table(conn)
        csv_glob = _csv_glob(csv_dir_path)

        # Filter incomplete rows, deduplicate by (instrument, time), keep grain = 1 minute.
        conn.execute(
            f"""
            COPY (
                WITH filtered AS (
                    SELECT *
                    FROM read_csv(
                        '{csv_glob}',
                        header = TRUE,
                        auto_detect = TRUE,
                        union_by_name = TRUE
                    )
                    WHERE is_complete = TRUE
                ),
                deduped AS (
                    SELECT *,
                           ROW_NUMBER() OVER (
                               PARTITION BY instrument, time
                               ORDER BY instrument, time
                           ) AS _rn
                    FROM filtered
                )
                SELECT * EXCLUDE (_rn)
                FROM deduped
                WHERE _rn = 1
                ORDER BY instrument, time
            ) TO '{target_parquet.as_posix()}' (FORMAT PARQUET);
            """
        )

        row_count = conn.execute(
            f"SELECT COUNT(*) FROM read_parquet('{target_parquet.as_posix()}');"
        ).fetchone()[0]

        conn.execute(
            "DELETE FROM loaded_tables WHERE table_name = ?;", [table_name]
        )
        conn.execute(
            """
            INSERT INTO loaded_tables (table_name, csv_dir, parquet_path, row_count)
            VALUES (?, ?, ?, ?);
            """,
            (table_name, str(csv_dir_path), str(target_parquet), row_count),
        )

        print(f"-> Done! Cleaned 1-minute table '{table_name}' contains {row_count} rows.")
        print(f"   Parquet: {target_parquet.resolve()}")
    except (duckdb.Error, OSError) as e:
        print(f"-> Error during data loading: {e}")
    finally:
        conn.close()

    return target_parquet


# Backwards-compatible aliases for the legacy scripts.
def load_csvs_to_duckdb(
    csv_dir: str | Path = DEFAULT_CSV_DIR,
    db_path: str | Path = DEFAULT_DB_PATH,
    parquet_output_path: str | Path = "data/parquet/all_data.parquet",
    table_name: str = DEFAULT_TABLE_NAME,
    data_dir: str | Path = DEFAULT_DATA_DIR,
) -> Optional[Path]:
    """Legacy entry point kept for compatibility (now produces a cleaned table)."""
    return load_data(
        csv_dir=csv_dir,
        db_path=db_path,
        table_name=table_name,
        data_dir=data_dir,
        parquet_output_path=parquet_output_path,
    )


def clean_all_data(
    db_path: str | Path = DEFAULT_DB_PATH,
    parquet_output_path: str | Path = None,
    table_name: str = DEFAULT_TABLE_NAME,
    csv_dir: str | Path | None = None,
    data_dir: str | Path = DEFAULT_DATA_DIR,
) -> Optional[Path]:
    """Legacy entry point kept for compatibility.

    When ``csv_dir`` is provided the full load+clean pipeline runs. Otherwise
    an already materialised parquet file is re-cleaned in place.
    """
    if csv_dir is not None:
        return load_data(
            csv_dir=csv_dir,
            db_path=db_path,
            table_name=table_name,
            data_dir=data_dir,
            parquet_output_path=parquet_output_path,
        )

    target = Path(parquet_output_path) if parquet_output_path is not None else _parquet_path(
        table_name, data_dir
    )
    if not target.exists():
        print(f"Parquet file not found at {target.resolve()}. Nothing to clean.")
        return None

    # Re-clean an existing parquet file in place.
    tmp = target.with_suffix(".tmp.parquet")
    conn = duckdb.connect(str(db_path))
    try:
        conn.execute(
            f"""
            COPY (
                WITH filtered AS (
                    SELECT * FROM read_parquet('{target.as_posix()}')
                    WHERE is_complete = TRUE
                ),
                deduped AS (
                    SELECT *,
                           ROW_NUMBER() OVER (
                               PARTITION BY instrument, time
                               ORDER BY instrument, time
                           ) AS _rn
                    FROM filtered
                )
                SELECT * EXCLUDE (_rn)
                FROM deduped
                WHERE _rn = 1
                ORDER BY instrument, time
            ) TO '{tmp.as_posix()}' (FORMAT PARQUET);
            """
        )
        tmp.replace(target)
        print(f"-> Cleaned parquet written to {target.resolve()}.")
    except (duckdb.Error, OSError) as e:
        print(f"-> Error during data cleaning: {e}")
    finally:
        conn.close()
    return target


load_and_clean_data = load_data


def main() -> None:
    target = load_data()
    if target is not None:
        print(f"Loaded and cleaned 1-minute table: {target.resolve()}")


if __name__ == "__main__":
    main()
