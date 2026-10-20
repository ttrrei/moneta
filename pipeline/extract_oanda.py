"""Download historical OANDA candles into the raw CSV format used by Moneta.

Examples:
    python -m pipeline.extract_oanda --instrument GBP_USD \
        --from 2026-07-08T02:25:00Z --to 2026-07-08T20:47:00Z
    python -m pipeline.extract_oanda --instrument EUR_USD \
        --from 2025-01-01T00:00:00Z --to 2025-12-31T23:59:00Z
"""

from __future__ import annotations

import argparse
import csv
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests
import yaml
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "setting.yml"
DEFAULT_CSV_DIR = PROJECT_ROOT / "data" / "raw_csv"
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
        total=3,
        connect=3,
        read=3,
        backoff_factor=0.5,
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


def _next_cursor(last_time: datetime, granularity: str) -> datetime:
    """Return the timestamp immediately after the last candle in a page."""
    if granularity == "M":
        if last_time.month == 12:
            return last_time.replace(year=last_time.year + 1, month=1, day=1)
        return last_time.replace(month=last_time.month + 1, day=1)
    return last_time + timedelta(minutes=_granularity_minutes(granularity))


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
    """Fetch candles in the inclusive UTC range, paging at OANDA's 5000 limit."""
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
    cursor = start
    try:
        while cursor <= end:
            params = {
                "from": _format_time(cursor),
                "to": _format_time(end),
                "granularity": granularity,
                "price": price,
                "smooth": str(smooth).lower(),
                "count": PAGE_SIZE,
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

            new_times: list[datetime] = []
            for candle in candles:
                candle_time = candle.get("time")
                if not candle_time or candle_time in seen:
                    continue
                parsed_time = _parse_time(candle_time)
                if parsed_time < start or parsed_time > end:
                    continue
                collected.append(candle)
                seen.add(candle_time)
                new_times.append(parsed_time)

            if len(candles) < PAGE_SIZE or not new_times:
                break
            next_cursor = _next_cursor(max(new_times), granularity)
            if next_cursor <= cursor:
                raise RuntimeError("OANDA pagination did not advance")
            cursor = next_cursor
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
    filename = (
        f"{instrument}_{granularity}_{start:%Y%m%dT%H%M%S}_"
        f"{end:%Y%m%dT%H%M%S}Z.csv"
    )
    return DEFAULT_CSV_DIR / instrument / filename


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("--instrument", default="GBP_USD")
    parser.add_argument("--from", dest="time_from", required=True, help="UTC ISO-8601 start time")
    parser.add_argument("--to", dest="time_to", required=True, help="UTC ISO-8601 end time (inclusive)")
    parser.add_argument("--granularity", default="M1")
    parser.add_argument("--price", choices=PRICE_CHOICES)
    parser.add_argument("--smooth", action=argparse.BooleanOptionalAction, default=None)
    parser.add_argument("--live", action="store_true", help="use the OANDA live host")
    parser.add_argument("--token", help="override the configured token")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG_PATH))
    parser.add_argument("--output", help="CSV destination (default: data/raw_csv/<instrument>/...)")
    parser.add_argument("--json-out", help="also save the raw OANDA response as JSON")
    args = parser.parse_args(argv)

    config = _load_config(args.config)
    oanda_config = config.get("oanda", {}) or {}
    if not isinstance(oanda_config, dict):
        raise ValueError("'oanda' configuration must be a YAML mapping")
    token = args.token or os.environ.get("OANDA_API_TOKEN") or oanda_config.get("api_token")
    if not isinstance(token, str) or not token.strip():
        parser.error("Set oanda.api_token in config/setting.yml, OANDA_API_TOKEN, or --token")
    environment = str(oanda_config.get("environment", "practice")).lower()
    if environment not in ("practice", "live"):
        raise ValueError("'oanda.environment' must be 'practice' or 'live'")

    payload = fetch_candles(
        args.instrument,
        args.time_from,
        args.time_to,
        token=token,
        granularity=args.granularity,
        price=args.price or str(oanda_config.get("price", "MBA")),
        smooth=args.smooth if args.smooth is not None else bool(oanda_config.get("smooth", False)),
        practice=not args.live and environment == "practice",
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
        json_path = Path(args.json_out)
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
