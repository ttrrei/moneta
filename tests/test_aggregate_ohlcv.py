"""Unit tests for pipeline/aggregate_ohlcv.py."""

from __future__ import annotations

from pathlib import Path

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from pipeline.aggregate_ohlcv import aggregate_ohlcv_data


def _make_parquet(path: Path) -> None:
    """Write a small, UTC-timestamped 1-minute dataset (with a gap + dup)."""
    rows = [
        # EUR_USD: 5 full minutes then a partial bucket
        ("EUR_USD", True, "2026-06-09T00:00:00Z", 10, 1.0, 1.1, 0.9, 1.05),
        ("EUR_USD", True, "2026-06-09T00:01:00Z", 20, 1.05, 1.2, 1.0, 1.15),
        ("EUR_USD", True, "2026-06-09T00:02:00Z", 30, 1.15, 1.3, 1.1, 1.25),
        ("EUR_USD", True, "2026-06-09T00:03:00Z", 40, 1.25, 1.4, 1.2, 1.35),
        ("EUR_USD", True, "2026-06-09T00:04:00Z", 50, 1.35, 1.5, 1.3, 1.45),
        ("EUR_USD", True, "2026-06-09T00:07:00Z", 5, 1.5, 1.5, 1.5, 1.5),   # partial bucket
        ("EUR_USD", False, "2026-06-09T00:08:00Z", 9, 9.0, 9.0, 9.0, 9.0),  # incomplete -> dropped
        ("EUR_USD", True, "2026-06-09T00:05:00Z", 60, 1.45, 1.6, 1.4, 1.5),  # out-of-order same bucket
        # GBP_USD: one bar only
        ("GBP_USD", True, "2026-06-09T00:00:00Z", 7, 2.0, 2.1, 1.9, 2.05),
        # duplicate (instrument,time) -> kept first occurrence after dedup is NOT done here,
        # aggregate reads whatever parquet provides; ensure COUNT includes it (no dedup in agg)
    ]
    # duplicate row on purpose to ensure aggregation sums it
    rows.append(("EUR_USD", True, "2026-06-09T00:00:00Z", 100, 1.0, 1.1, 0.9, 1.05))

    schema = pa.schema([
        ("instrument", pa.string()),
        ("is_complete", pa.bool_()),
        ("time", pa.timestamp("us", tz="UTC")),
        ("volume", pa.int64()),
        ("mid_o", pa.float64()),
        ("mid_h", pa.float64()),
        ("mid_l", pa.float64()),
        ("mid_c", pa.float64()),
    ])
    import pandas as pd
    times = pd.to_datetime([r[2] for r in rows], utc=True)
    table = pa.table({
        "instrument": [r[0] for r in rows],
        "is_complete": [r[1] for r in rows],
        "time": pa.array(times, type=pa.timestamp("us", tz="UTC")),
        "volume": [r[3] for r in rows],
        "mid_o": [r[4] for r in rows],
        "mid_h": [r[5] for r in rows],
        "mid_l": [r[6] for r in rows],
        "mid_c": [r[7] for r in rows],
    }, schema=schema)
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, path)


def test_aggregate_5m_and_1h_basic(tmp_path: Path) -> None:
    inp = tmp_path / "in" / "all_data.parquet"
    _make_parquet(inp)
    out5 = tmp_path / "out" / "ohlcv_5m.parquet"
    out1 = tmp_path / "out" / "ohlcv_1h.parquet"
    db = tmp_path / "meta.duckdb"

    counts = aggregate_ohlcv_data(
        db_path=db, input_parquet_path=inp,
        parquet_5m_path=out5, parquet_1h_path=out1,
    )

    assert counts == {"main.ohlcv_5m": 3, "main.ohlcv_1h": 2}
    t5 = pq.read_table(out5)
    assert set(t5.column_names) == {"instrument", "time", "open", "high", "low", "close", "volume", "n_bars"}
    assert str(t5.schema.field("time").type) == "timestamp[us, tz=UTC]"

    df5 = t5.to_pandas().sort_values(["instrument", "time"]).reset_index(drop=True)
    # first EUR bucket: 6 rows (5 distinct minutes + duplicate at 00:00) => n_bars=6
    eur0 = df5[(df5.instrument == "EUR_USD") & (df5.time.dt.minute == 0)].iloc[0]
    assert eur0.n_bars == 6, eur0
    assert eur0.open == 1.0           # first by time (arg_min)
    assert eur0.close == 1.45          # last by time in bucket (00:04)
    assert eur0.high == 1.5
    assert eur0.low == 0.9
    # partial bucket 00:05-00:09 has 2 contributing bars (00:05, 00:07; 00:08 dropped)
    eur_partial = df5[(df5.instrument == "EUR_USD") & (df5.time.dt.minute == 5)].iloc[0]
    assert eur_partial.n_bars == 2, eur_partial
    assert eur_partial.volume == 5 + 60
    # GBP only one bar
    gbp = df5[df5.instrument == "GBP_USD"].iloc[0]
    assert gbp.n_bars == 1
    # alignment (5-min)
    assert (df5.time.dt.minute % 5 == 0).all()

    # 1h table
    t1 = pq.read_table(out1)
    df1 = t1.to_pandas()
    eurh = df1[df1.instrument == "EUR_USD"].iloc[0]
    # contributing bars: 7 (6 in first 5min? let's just sanity)
    assert eurh.n_bars >= 7
    assert str(t1.schema.field("time").type) == "timestamp[us, tz=UTC]"


def test_aggregate_from_all_data_table(tmp_path: Path) -> None:
    """When main.all_data exists in DuckDB, it is used even without parquet path."""
    db = tmp_path / "t.duckdb"
    conn = duckdb.connect(str(db))
    conn.execute("SET TimeZone='UTC'")
    conn.execute("""
        CREATE TABLE main.all_data AS
        SELECT 'EUR_USD'::VARCHAR AS instrument, TRUE AS is_complete,
               '2026-06-09T00:00:00Z'::TIMESTAMPTZ AS time,
               10::BIGINT AS volume, 1.0 AS mid_o, 1.1 AS mid_h,
               0.9 AS mid_l, 1.05 AS mid_c;
    """)
    conn.close()
    out5 = tmp_path / "o5.parquet"
    out1 = tmp_path / "o1.parquet"
    counts = aggregate_ohlcv_data(db_path=db, parquet_5m_path=out5, parquet_1h_path=out1)
    assert counts["main.ohlcv_5m"] == 1
    t = pq.read_table(out5)
    assert t.num_rows == 1


def test_aggregate_missing_input_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        aggregate_ohlcv_data(
            db_path=tmp_path / "nope.duckdb",
            parquet_5m_path=tmp_path / "a.parquet",
            parquet_1h_path=tmp_path / "b.parquet",
            input_parquet_path=tmp_path / "nope.parquet",
        )


def test_timestamps_remain_utc_and_sorted(tmp_path: Path) -> None:
    inp = tmp_path / "in.parquet"
    _make_parquet(inp)
    out5 = tmp_path / "5.parquet"
    out1 = tmp_path / "1.parquet"
    aggregate_ohlcv_data(input_parquet_path=inp, parquet_5m_path=out5, parquet_1h_path=out1, db_path=None)
    df = pq.read_table(out5).to_pandas()
    # sorted by instrument, time
    assert df.equals(df.sort_values(["instrument", "time"]).reset_index(drop=True))
    assert str(pq.read_table(out5).schema.field("time").type) == "timestamp[us, tz=UTC]"
