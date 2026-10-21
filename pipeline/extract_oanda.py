"""Download historical OANDA candles into the raw CSV format used by Moneta.

Single window (a gap fill or one instrument)::

    python -m pipeline.extract_oanda --instrument GBP_USD \\
        --from 2026-07-08T02:25:00Z --to 2026-07-08T20:47:00Z

Backfill earlier history for many instruments from a map file
(``config/history_map.yml``; one entry per instrument)::

    python -m pipeline.extract_oanda --map config/history_map.yml --dry-run
    python -m pipeline.extract_oanda --map config/history_map.yml
    python -m pipeline.extract_oanda --map config/history_map.yml --only GBP_USD,EUR_USD

Backfill output is one CSV per instrument per calendar month under
``data/raw_csv/<instrument>/``.  Finished months are skipped on re-run, so an
interrupted backfill simply resumes.
"""

from __future__ import annotations

import argparse
import calendar
import csv
import json
import os
import sys
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests
import yaml
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "setting.yml"
DEFAULT_CSV_DIR = PROJECT_ROOT / "data" / "raw_csv"
DEFAULT_MAP_PATH = PROJECT_ROOT / "config" / "history_map.yml"
DEFAULT_PARQUET = PROJECT_ROOT / "data" / "all_data" / "all_data.parquet"
PAGE_SIZE = 5000
PRACTICE_HOST = "api-fxpractice.oanda.com"
LIVE_HOST = "api-fxtrade.oanda.com"

GRANULARITY_MINUTES = {
    "S5": 5 / 60,
    "S10": 10 / 60,
    "S15": 15 / 60,
    "S30": 30 / 60,
    "M1": 1,
    "M2": 2,
    "M4": 4,
    "M5": 5,
    "M10": 10,
    "M15": 15,
    "M30": 30,
    "H1": 60,
    "H2": 120,
    "H3": 180,
    "H4": 240,
    "H6": 360,
    "H8": 480,
    "H12": 720,
    "D": 1440,
    "W": 10080,
    "M": 43200,
}

RAW_COLUMNS = [
    "instrument",
    "is_complete",
    "time",
    "volume",
    "mid_o",
    "mid_h",
    "mid_l",
    "mid_c",
    "bid_o",
    "bid_h",
    "bid_l",
    "bid_c",
    "ask_o",
    "ask_h",
    "ask_l",
    "ask_c",
]
PRICE_CHOICES = ("M", "B", "A", "MB", "MA", "BA", "MBA")


def _parse_time(value: str) -> datetime:
    """Parse an ISO-8601 timestamp and normalize it to UTC."""
    text = value.strip()
    if text.endswith(("Z", "z")):
        text = text[:-1] + "+00:00"
    result = datetime.fromisoformat(text)
    if result.tzinfo is None:
        result = result.replace(tzinfo=timezone.utc)
    return result.astimezone(timezone.utc)


def _format_time(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load_config(path: str | Path) -> dict[str, Any]:
    config_path = Path(path)
    if not config_path.is_file():
        raise FileNotFoundError(f"Configuration file not found: {config_path.resolve()}")
    with config_path.open(encoding="utf-8") as handle:
        config = yaml.safe_load(handle) or {}
    if not isinstance(config, dict):
        raise ValueError(f"Expected a YAML mapping in {config_path}")
    return config


def _build_session() -> requests.Session:
    retry = Retry(
        total=5,
        connect=5,
        read=5,
        backoff_factor=1.0,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET"}),
        raise_on_status=False,
    )
    session = requests.Session()
    session.mount("https://", HTTPAdapter(max_retries=retry))
    return session


def _granularity_minutes(granularity: str) -> float:
    key = granularity.upper()
    if key not in GRANULARITY_MINUTES:
        raise ValueError(f"Unsupported OANDA granularity: {granularity}")
    return GRANULARITY_MINUTES[key]


def _advance_candles(value: datetime, granularity: str, count: int) -> datetime:
    """Advance by a number of candle intervals."""
    if granularity == "M":
        month_index = value.year * 12 + value.month - 1 + count
        year, month_offset = divmod(month_index, 12)
        month = month_offset + 1
        day = min(value.day, calendar.monthrange(year, month)[1])
        return value.replace(year=year, month=month, day=day)
    return value + timedelta(minutes=_granularity_minutes(granularity) * count)


def fetch_candles(
    instrument: str,
    time_from: str,
    time_to: str,
    *,
    token: str,
    granularity: str = "M1",
    price: str = "MBA",
    smooth: bool = False,
    practice: bool = True,
    session: requests.Session | None = None,
) -> dict[str, Any]:
    """Fetch candles in the inclusive UTC range ``[time_from, time_to]``.

    OANDA caps a response at 5000 candles and rejects ``count`` together with
    both ``from`` and ``to``, so the range is requested in windows of at most
    ``PAGE_SIZE`` candles using ``from`` + ``to``.  The API docs do not say
    whether the candle stamped exactly ``to`` is returned, so the code does not
    depend on it: every window starts at the previous window's last timestamp
    (one candle of deliberate overlap, removed by de-duplication) and the final
    window reaches one candle past ``time_to``; results are then filtered to
    the requested range.
    """
    if not token.strip():
        raise ValueError("An OANDA API token is required")
    start, end = _parse_time(time_from), _parse_time(time_to)
    if end < start:
        raise ValueError("--to must be at or after --from")
    granularity = granularity.upper()
    _granularity_minutes(granularity)
    price = price.upper()
    if price not in PRICE_CHOICES:
        raise ValueError(f"Unsupported OANDA price component: {price}")
    if not instrument or "/" in instrument:
        raise ValueError("Instrument must be an OANDA instrument name such as GBP_USD")

    close_session = session is None
    http = session or _build_session()
    host = PRACTICE_HOST if practice else LIVE_HOST
    url = f"https://{host}/v3/instruments/{instrument}/candles"
    headers = {"Authorization": f"Bearer {token}"}
    collected: list[dict[str, Any]] = []
    seen: set[str] = set()
    last_wanted = _advance_candles(end, granularity, 1)
    cursor = start
    try:
        while True:
            window_end = _advance_candles(cursor, granularity, PAGE_SIZE - 1)
            chunk_to = min(window_end, last_wanted)
            params = {
                "from": _format_time(cursor),
                "to": _format_time(chunk_to),
                "granularity": granularity,
                "price": price,
                "smooth": str(smooth).lower(),
            }
            response = http.get(url, params=params, headers=headers, timeout=60)
            try:
                response.raise_for_status()
            except requests.HTTPError as exc:
                detail = response.text.strip()
                message = f"OANDA returned HTTP {response.status_code} {response.reason}"
                if detail:
                    message += f": {detail}"
                raise requests.HTTPError(message, response=response) from exc

            payload = response.json()
            if not isinstance(payload, dict):
                raise RuntimeError(f"Unexpected OANDA response: {payload!r}")
            if payload.get("errorMessage"):
                raise RuntimeError(f"OANDA error: {payload['errorMessage']}")
            candles = payload.get("candles")
            if not isinstance(candles, list):
                raise RuntimeError(f"Unexpected OANDA response: {payload!r}")

            for candle in candles:
                candle_time = candle.get("time")
                if not candle_time or candle_time in seen:
                    continue
                parsed_time = _parse_time(candle_time)
                if parsed_time < start or parsed_time > end:
                    continue
                collected.append(candle)
                seen.add(candle_time)

            if chunk_to >= last_wanted:
                break
            if chunk_to <= cursor:
                raise RuntimeError("OANDA time window did not advance")
            cursor = chunk_to
    finally:
        if close_session:
            http.close()

    collected.sort(key=lambda candle: candle["time"])
    return {
        "instrument": instrument,
        "granularity": granularity,
        "price": price,
        "smooth": smooth,
        "from": _format_time(start),
        "to": _format_time(end),
        "candles": collected,
    }


def _number(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def candles_to_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Convert OANDA candle values to the shared raw-candle CSV schema."""
    instrument = payload["instrument"]
    rows = []
    for candle in payload.get("candles", []):
        row: dict[str, Any] = {
            "instrument": instrument,
            "is_complete": bool(candle.get("complete", True)),
            "time": candle.get("time"),
            "volume": candle.get("volume", 0),
        }
        for component in ("mid", "bid", "ask"):
            values = candle.get(component) or {}
            for field in ("o", "h", "l", "c"):
                row[f"{component}_{field}"] = _number(values.get(field))
        rows.append(row)
    rows.sort(key=lambda row: row["time"] or "")
    return rows


def write_csv(rows: list[dict[str, Any]], path: str | Path) -> Path:
    """Atomically write candle rows to a CSV compatible with load_data.py."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    try:
        with temporary.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=RAW_COLUMNS)
            writer.writeheader()
            for row in rows:
                writer.writerow({column: row.get(column, "") for column in RAW_COLUMNS})
        temporary.replace(target)
    except OSError:
        temporary.unlink(missing_ok=True)
        raise
    return target


def _default_output(instrument: str, granularity: str, start: datetime, end: datetime) -> Path:
    return _chunk_path(DEFAULT_CSV_DIR, instrument, granularity, start, end)


def _chunk_path(csv_dir: Path, instrument: str, granularity: str, start: datetime, end: datetime) -> Path:
    filename = f"{instrument}_{granularity}_{start:%Y%m%dT%H%M%S}_{end:%Y%m%dT%H%M%S}Z.csv"
    return Path(csv_dir) / instrument / filename


# --------------------------------------------------------------------------- history map
MAP_KEYS = {"from", "to", "granularity"}


@dataclass(frozen=True)
class BackfillJob:
    instrument: str
    granularity: str
    start: datetime
    end: datetime  # inclusive


def _as_datetime(value: Any, label: str) -> datetime:
    """Accept ISO strings and the datetime/date objects YAML produces for unquoted timestamps."""
    if isinstance(value, datetime):
        return (value if value.tzinfo else value.replace(tzinfo=timezone.utc)).astimezone(timezone.utc)
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day, tzinfo=timezone.utc)
    if isinstance(value, str):
        try:
            return _parse_time(value)
        except ValueError as exc:
            raise ValueError(f"{label}: cannot parse timestamp {value!r}") from exc
    raise ValueError(f"{label}: expected an ISO-8601 timestamp, got {value!r}")


def load_history_map(path: str | Path) -> dict[str, Any]:
    """Read and validate the history map: ``{"defaults": {...}, "instruments": {name: {...}}}``."""
    config = _load_config(path)
    defaults = config.get("defaults") or {}
    instruments = config.get("instruments")
    if not isinstance(defaults, dict) or not isinstance(instruments, dict) or not instruments:
        raise ValueError(f"{path}: needs a 'defaults' mapping and a non-empty 'instruments' mapping")
    for label, spec in [("defaults", defaults)] + list(instruments.items()):
        spec = spec or {}
        if not isinstance(spec, dict):
            raise ValueError(f"{path}: '{label}' must be a mapping (or empty)")
        unknown = set(spec) - MAP_KEYS
        if unknown:
            raise ValueError(f"{path}: '{label}' has unknown key(s) {sorted(unknown)}; allowed: {sorted(MAP_KEYS)}")
    return {"defaults": defaults, "instruments": {k: (v or {}) for k, v in instruments.items()}}


def _earliest_by_instrument(parquet_path: str | Path) -> dict[str, datetime] | None:
    """First candle time per instrument already ingested, or None if there is no parquet yet."""
    path = Path(parquet_path)
    if not path.is_file():
        return None
    import duckdb

    conn = duckdb.connect()
    try:
        rows = conn.execute(
            f"SELECT instrument, epoch(min(time)) FROM read_parquet('{path.as_posix()}') GROUP BY 1"
        ).fetchall()
    finally:
        conn.close()
    return {name: datetime.fromtimestamp(seconds, tz=timezone.utc) for name, seconds in rows}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def build_jobs(
    history: dict[str, Any],
    earliest: dict[str, datetime] | None,
    only: set[str] | None = None,
    now: datetime | None = None,
) -> tuple[list[BackfillJob], list[str]]:
    """Turn the map into jobs.  ``to: auto`` stops one candle before the earliest ingested
    candle, or (when nothing is ingested yet) fills from ``from`` up to ``now``."""
    if now is None:
        now = _now()
    jobs: list[BackfillJob] = []
    notes: list[str] = []
    unknown = (only or set()) - set(history["instruments"])
    if unknown:
        raise ValueError(f"--only names not in the map: {sorted(unknown)}")
    for instrument, spec in history["instruments"].items():
        if only and instrument not in only:
            continue
        merged = {**history["defaults"], **spec}
        if "from" not in merged:
            raise ValueError(f"{instrument}: no 'from' (set it per instrument or under 'defaults')")
        granularity = str(merged.get("granularity", "M1")).upper()
        _granularity_minutes(granularity)
        start = _as_datetime(merged["from"], f"{instrument}.from")
        target = merged.get("to", "auto")
        if isinstance(target, str) and target.strip().lower() == "auto":
            anchor = earliest.get(instrument) if earliest else None
            if anchor is not None:
                end = _advance_candles(anchor, granularity, -1)
            else:
                # No ingested data to anchor on (empty/missing parquet): fill up
                # to "now", so a fresh start works with any 'from' in the past.
                end = now.replace(second=0, microsecond=0)
                notes.append(
                    f"{instrument}: no ingested data to anchor 'to: auto'; filling from "
                    f"{_format_time(start)} to now ({_format_time(end)})")
        else:
            end = _as_datetime(target, f"{instrument}.to")
        if end < start:
            notes.append(f"{instrument}: nothing earlier than {_format_time(start)} to fetch (skipped)")
            continue
        jobs.append(BackfillJob(instrument, granularity, start, end))
    return jobs, notes


def _month_chunks(start: datetime, end: datetime, granularity: str):
    """Yield inclusive (chunk_start, chunk_end) windows that never cross a UTC month boundary."""
    cursor = start
    while cursor <= end:
        year, month = (cursor.year + 1, 1) if cursor.month == 12 else (cursor.year, cursor.month + 1)
        next_month = datetime(year, month, 1, tzinfo=timezone.utc)
        chunk_end = min(end, _advance_candles(next_month, granularity, -1))
        yield cursor, chunk_end
        following = _advance_candles(chunk_end, granularity, 1)
        if following <= cursor:
            raise RuntimeError("chunking did not advance")
        cursor = following


def _empty_marker(path: Path) -> Path:
    return path.with_name(path.name + ".empty")


def run_backfill(
    jobs: list[BackfillJob],
    *,
    token: str | None,
    practice: bool,
    price: str,
    smooth: bool,
    csv_dir: str | Path = DEFAULT_CSV_DIR,
    dry_run: bool = False,
    session: requests.Session | None = None,
    retries: int = 2,
    retry_wait: float = 60.0,
    sleep=time.sleep,
) -> int:
    """Download every job month by month.  Returns the number of instruments still failing.

    A finished month is a CSV in ``csv_dir/<instrument>/``; a month OANDA returned
    no candles for gets an ``.empty`` marker instead (a header-only CSV could make the
    loader infer wrong column types).  Both are skipped on re-run.

    Failure handling, from small to large: each HTTP request is retried by the
    session (5 attempts with backoff); an instrument that still fails is parked and
    retried after *retry_wait* seconds, up to *retries* more passes (finished months
    are skipped, so a pass resumes where the last one stopped); whatever is still
    failing is reported and counted.  An auth error (401/403) aborts the whole run.
    """
    csv_dir = Path(csv_dir)
    close_session = session is None and not dry_run
    http = session or (None if dry_run else _build_session())
    pending = list(jobs)
    try:
        for attempt in range(retries + 1):
            pending = _run_pass(pending, http, token, practice, price, smooth, csv_dir, dry_run)
            if not pending or dry_run or attempt == retries:
                break
            print(f"\n{len(pending)} instrument(s) failed ({', '.join(j.instrument for j in pending)}); "
                  f"retrying in {retry_wait:.0f}s (pass {attempt + 2} of {retries + 1})", file=sys.stderr, flush=True)
            sleep(retry_wait)
    finally:
        if close_session and http is not None:
            http.close()
    if pending:
        print(f"\n{len(pending)} instrument(s) still failing: {', '.join(j.instrument for j in pending)} "
              "- rerun to resume.", file=sys.stderr)
    return len(pending)


def _run_pass(jobs, http, token, practice, price, smooth, csv_dir, dry_run) -> list[BackfillJob]:
    """One pass over *jobs*; returns the jobs that failed."""
    failed: list[BackfillJob] = []
    for job in jobs:
        chunks = list(_month_chunks(job.start, job.end, job.granularity))
        paths = {c: _chunk_path(csv_dir, job.instrument, job.granularity, *c) for c in chunks}
        todo = [c for c in chunks if not (paths[c].exists() or _empty_marker(paths[c]).exists())]
        print(f"{job.instrument}: {_format_time(job.start)} -> {_format_time(job.end)} | "
              f"{len(chunks)} month file(s), {len(chunks) - len(todo)} already done, {len(todo)} to fetch")
        if dry_run:
            continue
        try:
            for chunk_start, chunk_end in todo:
                payload = fetch_candles(
                    job.instrument, _format_time(chunk_start), _format_time(chunk_end),
                    token=token or "", granularity=job.granularity, price=price,
                    smooth=smooth, practice=practice, session=http,
                )
                rows = candles_to_rows(payload)
                target = paths[(chunk_start, chunk_end)]
                if rows:
                    write_csv(rows, target)
                else:
                    _empty_marker(target).parent.mkdir(parents=True, exist_ok=True)
                    _empty_marker(target).touch()
                print(f"  {chunk_start:%Y-%m}: {len(rows):,} candle(s)", flush=True)
        except requests.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else None
            if status in (401, 403):
                raise
            print(f"  FAILED {job.instrument}: {exc}", file=sys.stderr)
            failed.append(job)
        except (requests.RequestException, RuntimeError, OSError) as exc:
            print(f"  FAILED {job.instrument}: {exc}", file=sys.stderr)
            failed.append(job)
    return failed


# ---------------------------------------------------------------------------------- CLI
def _credentials(parser: argparse.ArgumentParser, args: argparse.Namespace, oanda_config: dict[str, Any]):
    env_token = os.environ.get("OANDA_API_TOKEN")
    token = args.token or env_token or oanda_config.get("api_token")
    if not isinstance(token, str) or not token.strip():
        parser.error("Set oanda.api_token in config/setting.yml, OANDA_API_TOKEN, or --token")
    source = "--token" if args.token else "env OANDA_API_TOKEN" if env_token else "config file"
    environment = str(oanda_config.get("environment", "practice")).lower()
    if environment not in ("practice", "live"):
        raise ValueError("'oanda.environment' must be 'practice' or 'live'")
    return token.strip(), source, (not args.live and environment == "practice")


def _write_json(payload: dict[str, Any], path: str | Path) -> None:
    json_path = Path(path)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = json_path.with_suffix(json_path.suffix + ".tmp")
    try:
        with temporary.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
            handle.write("\n")
        temporary.replace(json_path)
    except OSError:
        temporary.unlink(missing_ok=True)
        raise
    print(f"Wrote OANDA response JSON: {json_path}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("--map", dest="map_path", nargs="?", const=str(DEFAULT_MAP_PATH),
                        help="backfill earlier history for the instruments in this map file "
                             "(default config/history_map.yml)")
    parser.add_argument("--only", help="with --map: comma-separated instruments to process")
    parser.add_argument("--dry-run", action="store_true", help="with --map: print the plan, download nothing")
    parser.add_argument("--parquet", default=str(DEFAULT_PARQUET),
                        help="with --map: parquet used to resolve 'to: auto' (earliest ingested candle)")
    parser.add_argument("--csv-dir", default=str(DEFAULT_CSV_DIR), help="with --map: output root")
    parser.add_argument("--retries", type=int, default=2,
                        help="with --map: extra passes over instruments that failed (default 2)")
    parser.add_argument("--retry-wait", type=float, default=60.0,
                        help="with --map: seconds to wait before each extra pass (default 60)")
    parser.add_argument("--instrument", default="GBP_USD")
    parser.add_argument("--from", dest="time_from", help="UTC ISO-8601 start time")
    parser.add_argument("--to", dest="time_to", help="UTC ISO-8601 end time (inclusive)")
    parser.add_argument("--granularity", default="M1")
    parser.add_argument("--price", choices=PRICE_CHOICES)
    parser.add_argument("--smooth", action=argparse.BooleanOptionalAction, default=None)
    parser.add_argument("--live", action="store_true", help="use the OANDA live host")
    parser.add_argument("--token", help="override the configured token")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG_PATH))
    parser.add_argument("--output", help="CSV destination (default: data/raw_csv/<instrument>/...)")
    parser.add_argument("--json-out", help="also save the raw OANDA response as JSON")
    args = parser.parse_args(argv)

    if args.map_path:
        if args.time_from or args.time_to:
            parser.error("--from/--to are for single-window mode; with --map put the dates in the map file")
        history = load_history_map(args.map_path)
        only = {name.strip() for name in args.only.split(",")} if args.only else None
        jobs, notes = build_jobs(history, _earliest_by_instrument(args.parquet), only)
        for note in notes:
            print(note)
        oanda_config = (_load_config(args.config).get("oanda", {}) or {}) if Path(args.config).is_file() else {}
        token = None
        practice = not args.live and str(oanda_config.get("environment", "practice")).lower() == "practice"
        if not args.dry_run:
            token, source, practice = _credentials(parser, args, oanda_config)
            print(f"OANDA {'practice' if practice else 'live'} host; token from {source} "
                  f"(ends ...{token[-4:]})", file=sys.stderr)
        failures = run_backfill(
            jobs, token=token, practice=practice,
            price=args.price or str(oanda_config.get("price", "MBA")),
            smooth=args.smooth if args.smooth is not None else bool(oanda_config.get("smooth", False)),
            csv_dir=args.csv_dir, dry_run=args.dry_run,
            retries=args.retries, retry_wait=args.retry_wait,
        )
        return 1 if failures else 0

    if not (args.time_from and args.time_to):
        parser.error("--from and --to are required unless --map is used")
    config = _load_config(args.config)
    oanda_config = config.get("oanda", {}) or {}
    if not isinstance(oanda_config, dict):
        raise ValueError("'oanda' configuration must be a YAML mapping")
    token, source, practice = _credentials(parser, args, oanda_config)
    print(f"OANDA {'practice' if practice else 'live'} host; token from {source} (ends ...{token[-4:]})",
          file=sys.stderr)
    payload = fetch_candles(
        args.instrument,
        args.time_from,
        args.time_to,
        token=token,
        granularity=args.granularity,
        price=args.price or str(oanda_config.get("price", "MBA")),
        smooth=args.smooth if args.smooth is not None else bool(oanda_config.get("smooth", False)),
        practice=practice,
    )
    rows = candles_to_rows(payload)
    output = Path(args.output) if args.output else _default_output(
        args.instrument,
        args.granularity.upper(),
        _parse_time(args.time_from),
        _parse_time(args.time_to),
    )
    write_csv(rows, output)
    print(
        f"Downloaded {len(rows)} candle(s) for {args.instrument} "
        f"({payload['from']} through {payload['to']}); wrote {output}"
    )
    if args.json_out:
        _write_json(payload, args.json_out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
