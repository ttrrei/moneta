"""Unit tests for OANDA historical extraction."""

from __future__ import annotations

import csv
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock

import duckdb
import pytest
import requests

from pipeline import extract_oanda


def _candle(time: str, close: str = "1.25") -> dict:
    return {
        "time": time,
        "complete": True,
        "volume": 7,
        "mid": {"o": "1.2", "h": "1.3", "l": "1.1", "c": close},
        "bid": {"o": "1.19", "h": "1.29", "l": "1.09", "c": "1.24"},
        "ask": {"o": "1.21", "h": "1.31", "l": "1.11", "c": "1.26"},
    }


UTC = timezone.utc


def _t(text: str) -> datetime:
    return datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)


def _stamp(moment: datetime) -> str:
    return moment.strftime("%Y-%m-%dT%H:%M:%S.000000000Z")


def _series(start: str, count: int, step_minutes: int = 1, skip=lambda moment: False) -> list[datetime]:
    first = _t(start)
    moments = (first + timedelta(minutes=step_minutes * i) for i in range(count))
    return [moment for moment in moments if not skip(moment)]


class _Resp:
    def __init__(self, status: int, body: dict) -> None:
        self.status_code, self._body, self.text = status, body, str(body)
        self.reason = "OK" if status == 200 else "Error"

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(self.text, response=self)

    def json(self) -> dict:
        return self._body


class FakeOanda:
    """OANDA stand-in that enforces the documented limits.

    * rejects ``count`` together with ``from`` and ``to``;
    * rejects windows holding more than ``limit`` candles (OANDA: 5000);
    * the docs do not say whether the candle stamped exactly ``to`` is returned,
      so ``to_inclusive`` switches between both behaviours;
    * ``fail`` maps an instrument to an HTTP status to return instead of data.
    """

    def __init__(self, series, *, to_inclusive: bool, limit: int = 5000, fail=None, flaky=None) -> None:
        self.series, self.to_inclusive, self.limit = sorted(series), to_inclusive, limit
        self.fail = fail or {}
        self.flaky = flaky or {}  # {instrument: {1-based call numbers for that instrument that return 503}}
        self.calls: list[tuple[str, dict]] = []

    def get(self, url, params, headers, timeout):
        instrument = url.split("/instruments/")[1].split("/")[0]
        self.calls.append((instrument, dict(params)))
        if instrument in self.fail:
            return _Resp(self.fail[instrument], {"errorMessage": "simulated failure"})
        if sum(1 for name, _ in self.calls if name == instrument) in self.flaky.get(instrument, ()):
            return _Resp(503, {"errorMessage": "temporarily unavailable"})
        assert "count" not in params, "OANDA rejects count together with from and to"
        lower, upper = _t(params["from"]), _t(params["to"])
        picked = [m for m in self.series if lower <= m < upper or (self.to_inclusive and m == upper)]
        if len(picked) > self.limit:
            return _Resp(400, {"errorMessage": "Maximum value for 'count' exceeded"})
        candles = [dict(_candle(_stamp(m))) for m in picked]
        return _Resp(200, {"candles": candles})

    def close(self) -> None:
        pass


@pytest.mark.parametrize("to_inclusive", [True, False])
@pytest.mark.parametrize("page_size", [7, 300, 5000])
def test_fetch_candles_is_complete_whether_or_not_to_is_inclusive(monkeypatch, to_inclusive, page_size) -> None:
    """No candle may be lost at a page boundary or at the end of the range, and none duplicated."""
    monkeypatch.setattr(extract_oanda, "PAGE_SIZE", page_size)
    # weekday-style series with a 3 hour hole in the middle (a real gap must stay a gap)
    series = _series("2026-07-06T00:00:00Z", 3000, skip=lambda m: m.hour == 10)
    fake = FakeOanda(series, to_inclusive=to_inclusive, limit=page_size)

    payload = extract_oanda.fetch_candles(
        "GBP_USD", "2026-07-06T00:30:00Z", "2026-07-07T20:47:00Z", token="t", session=fake,
    )

    wanted = [_stamp(m) for m in series if _t("2026-07-06T00:30:00Z") <= m <= _t("2026-07-07T20:47:00Z")]
    got = [c["time"] for c in payload["candles"]]
    assert got == wanted
    assert all(params["price"] == "MBA" for _, params in fake.calls)


def test_fetch_candles_header_and_session_handling() -> None:
    fake = FakeOanda(_series("2026-07-08T02:25:00Z", 10), to_inclusive=True)
    fake.close = MagicMock()
    extract_oanda.fetch_candles(
        "GBP_USD", "2026-07-08T02:25:00Z", "2026-07-08T02:27:00Z", token="test-token", session=fake,
    )
    fake.close.assert_not_called()  # a session passed in by the caller is not closed


def test_fetch_candles_rejects_invalid_range() -> None:
    with pytest.raises(ValueError, match="at or after"):
        extract_oanda.fetch_candles(
            "GBP_USD",
            "2026-07-08T02:27:00Z",
            "2026-07-08T02:25:00Z",
            token="test-token",
        )


def test_candles_to_rows_and_csv_match_raw_schema(tmp_path: Path) -> None:
    payload = {
        "instrument": "GBP_USD",
        "candles": [_candle("2026-07-08T02:25:00.000000000Z")],
    }
    rows = extract_oanda.candles_to_rows(payload)
    output = extract_oanda.write_csv(rows, tmp_path / "candles.csv")

    with output.open(newline="", encoding="utf-8") as handle:
        csv_rows = list(csv.DictReader(handle))
    assert csv_rows[0]["instrument"] == "GBP_USD"
    assert csv_rows[0]["mid_c"] == "1.25"
    assert csv_rows[0]["bid_c"] == "1.24"
    assert csv_rows[0]["ask_c"] == "1.26"
    assert csv_rows[0]["is_complete"] == "True"


def test_config_token_is_available_in_yaml(tmp_path: Path) -> None:
    config_path = tmp_path / "setting.yml"
    config_path.write_text("oanda:\n  api_token: test-token\n", encoding="utf-8")
    config = extract_oanda._load_config(config_path)
    assert config["oanda"]["api_token"] == "test-token"


# ------------------------------------------------------------------ history map / backfill
def _write_parquet(path: Path, rows: list[tuple[str, str]]) -> Path:
    conn = duckdb.connect()
    values = ", ".join(f"('{name}', TIMESTAMPTZ '{when}+00')" for name, when in rows)
    conn.execute(f"COPY (SELECT * FROM (VALUES {values}) t(instrument, time)) TO '{path.as_posix()}' (FORMAT PARQUET)")
    conn.close()
    return path


def _write_map(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


def test_history_map_rejects_unknown_keys_and_accepts_unquoted_timestamps(tmp_path: Path) -> None:
    bad = _write_map(tmp_path / "bad.yml", "defaults: {from: '2025-01-01T00:00:00Z', frm: x}\ninstruments: {GBP_USD: }\n")
    with pytest.raises(ValueError, match="unknown key"):
        extract_oanda.load_history_map(bad)

    # PyYAML turns an unquoted ISO timestamp into a datetime object; that must work.
    ok = _write_map(tmp_path / "ok.yml",
                    "defaults: {from: 2025-01-01T00:00:00Z, to: 2025-02-01T00:00:00Z}\ninstruments: {GBP_USD: , EUR_USD: {from: 2025-01-15}}\n")
    jobs, notes = extract_oanda.build_jobs(extract_oanda.load_history_map(ok), earliest=None)
    assert [(j.instrument, j.start, j.end) for j in jobs] == [
        ("GBP_USD", _t("2025-01-01T00:00:00Z"), _t("2025-02-01T00:00:00Z")),
        ("EUR_USD", _t("2025-01-15T00:00:00Z"), _t("2025-02-01T00:00:00Z")),
    ]
    assert notes == []


def test_to_auto_stops_one_candle_before_earliest_ingested_candle(tmp_path: Path) -> None:
    parquet = _write_parquet(tmp_path / "all.parquet", [
        ("GBP_USD", "2025-11-18 00:31:00"), ("GBP_USD", "2026-01-01 00:00:00"), ("EUR_USD", "2025-11-18 00:20:00"),
    ])
    earliest = extract_oanda._earliest_by_instrument(parquet)
    assert earliest["GBP_USD"] == _t("2025-11-18T00:31:00Z")

    history = {"defaults": {"from": "2025-11-01T00:00:00Z", "to": "auto"},
               "instruments": {"GBP_USD": {}, "EUR_USD": {"from": "2025-12-01T00:00:00Z"}}}
    jobs, notes = extract_oanda.build_jobs(history, earliest)
    assert [(j.instrument, j.end) for j in jobs] == [("GBP_USD", _t("2025-11-18T00:30:00Z"))]
    assert "EUR_USD: nothing earlier" in notes[0]  # asked-for start is after what we already have

    with pytest.raises(ValueError, match="run load_data first"):
        extract_oanda.build_jobs(history, None)
    with pytest.raises(ValueError, match="no ingested data"):
        extract_oanda.build_jobs({"defaults": {"from": "2025-01-01T00:00:00Z"}, "instruments": {"XAU_USD": {}}}, earliest)
    with pytest.raises(ValueError, match="not in the map"):
        extract_oanda.build_jobs(history, earliest, only={"NOPE"})


def test_month_chunks_never_cross_a_utc_month_boundary() -> None:
    chunks = list(extract_oanda._month_chunks(_t("2025-01-30T12:00:00Z"), _t("2025-03-02T00:10:00Z"), "M1"))
    assert chunks == [
        (_t("2025-01-30T12:00:00Z"), _t("2025-01-31T23:59:00Z")),
        (_t("2025-02-01T00:00:00Z"), _t("2025-02-28T23:59:00Z")),
        (_t("2025-03-01T00:00:00Z"), _t("2025-03-02T00:10:00Z")),
    ]


def _job(instrument: str = "GBP_USD", start: str = "2026-01-15T00:00:00Z", end: str = "2026-02-10T23:00:00Z"):
    return extract_oanda.BackfillJob(instrument, "H1", _t(start), _t(end))


def _backfill(jobs, fake, tmp_path: Path, **kwargs) -> int:
    kwargs.setdefault("retries", 0)
    return extract_oanda.run_backfill(
        jobs, token="t", practice=True, price="MBA", smooth=False, csv_dir=tmp_path, session=fake, **kwargs,
    )


def test_backfill_writes_one_file_per_month_and_resumes_without_refetching(tmp_path: Path) -> None:
    series = _series("2026-01-01T00:00:00Z", 24 * 60, step_minutes=60)  # hourly, Jan 1 -> Mar 1
    fake = FakeOanda(series, to_inclusive=False)

    assert _backfill([_job()], fake, tmp_path) == 0
    files = sorted((tmp_path / "GBP_USD").glob("*.csv"))
    assert [f.name for f in files] == [
        "GBP_USD_H1_20260115T000000_20260131T230000Z.csv",
        "GBP_USD_H1_20260201T000000_20260210T230000Z.csv",
    ]
    total = sum(len(list(csv.DictReader(f.open(encoding="utf-8")))) for f in files)
    assert total == len([m for m in series if _t("2026-01-15T00:00:00Z") <= m <= _t("2026-02-10T23:00:00Z")])

    calls_before = len(fake.calls)
    assert _backfill([_job()], fake, tmp_path) == 0
    assert len(fake.calls) == calls_before  # finished months are skipped


def test_backfill_empty_month_gets_a_marker_not_a_header_only_csv(tmp_path: Path) -> None:
    fake = FakeOanda(_series("2026-01-01T00:00:00Z", 24 * 20, step_minutes=60), to_inclusive=True)  # Jan only
    assert _backfill([_job()], fake, tmp_path) == 0
    names = sorted(p.name for p in (tmp_path / "GBP_USD").iterdir())
    assert names == [
        "GBP_USD_H1_20260115T000000_20260131T230000Z.csv",
        "GBP_USD_H1_20260201T000000_20260210T230000Z.csv.empty",
    ]
    calls_before = len(fake.calls)
    _backfill([_job()], fake, tmp_path)
    assert len(fake.calls) == calls_before


def test_backfill_auth_error_aborts_but_other_errors_only_skip_that_instrument(tmp_path: Path) -> None:
    series = _series("2026-01-01T00:00:00Z", 24 * 60, step_minutes=60)
    jobs = [_job("EUR_USD"), _job("BCO_USD"), _job("XAU_USD")]

    fake = FakeOanda(series, to_inclusive=True, fail={"BCO_USD": 500})
    assert _backfill(jobs, fake, tmp_path) == 1  # one instrument failed
    assert list((tmp_path / "EUR_USD").glob("*.csv")) and list((tmp_path / "XAU_USD").glob("*.csv"))
    assert not (tmp_path / "BCO_USD").exists()

    fake = FakeOanda(series, to_inclusive=True, fail={"EUR_USD": 401})
    with pytest.raises(requests.HTTPError, match="401"):
        _backfill([_job("EUR_USD", end="2026-01-20T00:00:00Z"), _job("AUD_USD")], fake, tmp_path / "auth")
    assert {instrument for instrument, _ in fake.calls} == {"EUR_USD"}  # stopped at once


def test_backfill_dry_run_downloads_nothing(tmp_path: Path, capsys) -> None:
    assert extract_oanda.run_backfill([_job()], token=None, practice=True, price="MBA",
                                      smooth=False, csv_dir=tmp_path, dry_run=True) == 0
    assert "2 to fetch" in capsys.readouterr().out
    assert not list(tmp_path.iterdir())


def test_main_map_dry_run_end_to_end(tmp_path: Path, capsys) -> None:
    parquet = _write_parquet(tmp_path / "all.parquet", [("GBP_USD", "2025-11-18 00:31:00")])
    map_file = _write_map(tmp_path / "map.yml",
                          "defaults: {from: '2025-10-01T00:00:00Z'}\ninstruments: {GBP_USD: }\n")
    code = extract_oanda.main(["--map", str(map_file), "--dry-run", "--parquet", str(parquet),
                               "--config", str(tmp_path / "missing.yml"), "--csv-dir", str(tmp_path / "out")])
    out = capsys.readouterr().out
    assert code == 0
    assert "GBP_USD: 2025-10-01T00:00:00Z -> 2025-11-18T00:30:00Z | 2 month file(s)" in out


def test_failed_instrument_is_retried_in_the_same_run_and_resumes_where_it_stopped(tmp_path: Path) -> None:
    series = _series("2026-01-01T00:00:00Z", 24 * 60, step_minutes=60)
    sleeps: list[float] = []
    # BCO_USD: call 1 (January) succeeds, call 2 (February) hits a 503
    fake = FakeOanda(series, to_inclusive=True, flaky={"BCO_USD": {2}})

    failures = _backfill([_job("EUR_USD"), _job("BCO_USD")], fake, tmp_path,
                         retries=2, retry_wait=7, sleep=sleeps.append)

    assert failures == 0
    assert sleeps == [7]  # one extra pass was enough
    assert len(list((tmp_path / "BCO_USD").glob("*.csv"))) == 2
    bco_calls = [p for name, p in fake.calls if name == "BCO_USD"]
    assert len(bco_calls) == 3  # Jan, Feb (failed), Feb again - January was not downloaded twice
    assert sum(1 for name, _ in fake.calls if name == "EUR_USD") == 2  # healthy instrument not re-run


def test_instrument_that_never_recovers_is_reported_after_the_retries_run_out(tmp_path: Path, capsys) -> None:
    sleeps: list[float] = []
    fake = FakeOanda(_series("2026-01-01T00:00:00Z", 24 * 60, step_minutes=60), to_inclusive=True,
                     fail={"BCO_USD": 503})
    failures = _backfill([_job("BCO_USD"), _job("EUR_USD")], fake, tmp_path,
                         retries=2, retry_wait=1, sleep=sleeps.append)
    assert failures == 1
    assert sleeps == [1, 1]  # two extra passes, then give up
    assert "still failing: BCO_USD" in capsys.readouterr().err
    assert list((tmp_path / "EUR_USD").glob("*.csv"))


def test_auth_error_is_never_retried(tmp_path: Path) -> None:
    sleeps: list[float] = []
    fake = FakeOanda([], to_inclusive=True, fail={"EUR_USD": 401})
    with pytest.raises(requests.HTTPError, match="401"):
        _backfill([_job("EUR_USD")], fake, tmp_path, retries=3, retry_wait=1, sleep=sleeps.append)
    assert sleeps == [] and len(fake.calls) == 1


def test_session_retries_are_generous_enough_to_ride_out_a_short_outage() -> None:
    adapter = extract_oanda._build_session().get_adapter("https://api-fxpractice.oanda.com")
    assert adapter.max_retries.total >= 5 and adapter.max_retries.backoff_factor >= 1.0
