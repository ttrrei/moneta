"""Manual extraction of missing 1-minute candles from the Oanda practice API.

The data profile found one GBP_USD gap (2026-07-08 02:29 -> 20:42 UTC) that
looks like *lost* data: peer instruments kept trading through it.  This module
re-pulls that window as M1 mid-price candles and writes them in the project's
raw CSV schema so they can be dropped into ``data/raw_csv/`` and re-ingested
by :mod:`pipeline.load_data`.

It can also convert an already-downloaded Oanda JSON file (the output of the
``curl`` shown in ``docs/profile_output.txt``) into the same CSV form without
touching the network.

Run::

    OANDA_API_TOKEN=<token> python -m pipeline.extract_oanda_gap
    python -m pipeline.extract_oanda_gap --token <token> --from-file gbp_usd_gap.json
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

DEFAULT_INSTRUMENT = "GBP_USD"
DEFAULT_FROM = "2026-07-08T02:25:00Z"
DEFAULT_TO = "2026-07-08T20:47:00Z"
DEFAULT_GRANULARITY = "M1"
DEFAULT_PRICE = "M"
DEFAULT_JSON_OUTPUT = Path("gbp_usd_gap.json")
DEFAULT_CSV_OUTPUT = Path("gbp_usd_gap.csv")
DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "setting.yml"
PRACTICE_HOST = "api-fxpractice.oanda.com"
LIVE_HOST = "api-fxtrade.oanda.com"
PAGE_SIZE = 5000

# Common Oanda candlestick granularities -> bar length in minutes, used to
# advance the pagination cursor.
GRANULARITY_MINUTES = {
    "S5": 5.0 / 60.0,
    "S10": 10.0 / 60.0,
    "S15": 15.0 / 60.0,
    "S30": 30.0 / 60.0,
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


def _build_session() -> requests.Session:
    """HTTP session with retry/backoff for transient Oanda failures."""
    retry = Retry(
        total=3,
        connect=3,
        read=3,
        backoff_factor=0.5,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET"}),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry, pool_connections=2, pool_maxsize=2)
    session = requests.Session()
    session.mount("https://", adapter)
    return session


def _parse_time(value: str) -> datetime:
    """Parse an Oanda/RFC3339 timestamp into a tz-aware UTC datetime."""
    text = value.strip()
    if text.endswith("Z") or text.endswith("z"):
        text = text[:-1] + "+00:00"
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _format_time(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _num(value: Any) -> float | None:
    """Coerce an Oanda price field (str/number) into a float."""
    if value is None:
        return None
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _granularity_minutes(granularity: str) -> float:
    return float(GRANULARITY_MINUTES.get(granularity.upper(), 1))


def _base_url(practice: bool) -> str:
    host = PRACTICE_HOST if practice else LIVE_HOST
    return f"https://{host}"


def fetch_candles(
    instrument: str,
    time_from: str,
    time_to: str,
    *,
    granularity: str = DEFAULT_GRANULARITY,
    price: str = DEFAULT_PRICE,
    smooth: bool = False,
    practice: bool = True,
    token: str | None = None,
    session: requests.Session | None = None,
) -> dict[str, Any]:
    """Fetch every M1 candle in ``[time_from, time_to]`` from Oanda.

    Handles Oanda's 5000-candle cap by advancing the ``from`` cursor.  Returns a
    dict of the form ``{"instrument", "granularity", "candles": [...]}``.
    """
    if token is None:
        raise ValueError("an Oanda API token is required")

    close_session = session is None
    session = session or _build_session()
    start = _parse_time(time_from)
    end = _parse_time(time_to)
    step = timedelta(minutes=_granularity_minutes(granularity))

    collected: list[dict[str, Any]] = []
    seen_times: set[str] = set()
    instrument_out = instrument
    granularity_out = granularity
    url = f"{_base_url(practice)}/v3/instruments/{instrument}/candles"

    try:
        cursor = start
        # Guard against runaway loops.
        guard = 0
        while cursor < end and guard < 1000:
            guard += 1
            params = {
                "from": _format_time(cursor),
                "to": _format_time(end),
                "granularity": granularity,
                "price": price,
                "smooth": "true" if smooth else "false",
                "count": PAGE_SIZE,
            }
            resp = session.get(
                url,
                params=params,
                headers={"Authorization": f"Bearer {token}"},
                timeout=60,
            )
            try:
                resp.raise_for_status()
            except requests.exceptions.HTTPError as exc:
                msg = f"{resp.status_code} {resp.reason}: {resp.text}"
                raise requests.exceptions.HTTPError(msg, response=resp) from exc
            payload = resp.json()
            instrument_out = payload.get("instrument", instrument_out)
            granularity_out = payload.get("granularity", granularity_out)

            if isinstance(payload, dict) and payload.get("errorMessage"):
                raise RuntimeError(str(payload.get("errorMessage")))
            candles = payload.get("candles") if isinstance(payload, dict) else None
            if candles is None:
                raise RuntimeError(f"unexpected Oanda response: {payload!r}")
            new_count = 0
            for candle in candles:
                t = candle.get("time")
                if t is None or t in seen_times:
                    continue
                try:
                    cdt = _parse_time(t)
                except ValueError:
                    continue
                if cdt < start or cdt >= end:
                    continue
                seen_times.add(t)
                collected.append(candle)
                new_count += 1

            if not candles:
                break
            # Oanda returns at most ``count`` (default 500 / max 5000) candles.
            if len(candles) < PAGE_SIZE and new_count == 0:
                break
            if not collected:
                break
            last_time = _parse_time(collected[-1]["time"])
            next_cursor = last_time + step
            if next_cursor <= cursor:
                break
            cursor = next_cursor
            # If the page was short we are done.
            if len(candles) < PAGE_SIZE:
                break
    finally:
        if close_session:
            session.close()

    collected.sort(key=lambda c: c.get("time", ""))
    return {
        "instrument": instrument_out,
        "granularity": granularity_out,
        "price": price,
        "smooth": bool(smooth),
        "from": _format_time(start),
        "to": _format_time(end),
        "candles": collected,
    }


def candle_to_row(instrument: str, candle: dict[str, Any]) -> dict[str, Any]:
    """Convert a single Oanda candle into the project's raw 1-minute row."""
    complete = bool(candle.get("complete", True))
    time_str = candle.get("time")
    volume = candle.get("volume", 0)
    try:
        volume = int(volume)
    except (TypeError, ValueError):
        volume = 0

    mid = candle.get("mid") or {}
    bid = candle.get("bid") or {}
    ask = candle.get("ask") or {}

    return {
        "instrument": instrument,
        "is_complete": complete,
        "time": time_str,
        "volume": volume,
        "mid_o": _num(mid.get("o")),
        "mid_h": _num(mid.get("h")),
        "mid_l": _num(mid.get("l")),
        "mid_c": _num(mid.get("c")),
        "bid_o": _num(bid.get("o")),
        "bid_h": _num(bid.get("h")),
        "bid_l": _num(bid.get("l")),
        "bid_c": _num(bid.get("c")),
        "ask_o": _num(ask.get("o")),
        "ask_h": _num(ask.get("h")),
        "ask_l": _num(ask.get("l")),
        "ask_c": _num(ask.get("c")),
    }


def candles_to_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Convert an Oanda payload (or its ``candles`` list) into raw rows."""
    instrument = payload.get("instrument", DEFAULT_INSTRUMENT)
    candles = payload.get("candles")
    if candles is None and isinstance(payload, list):
        candles = payload
    candles = candles or []
    rows = [candle_to_row(instrument, c) for c in candles]
    rows.sort(key=lambda r: (r.get("time") or ""))
    return rows


def write_json(payload: dict[str, Any], path: str | Path) -> Path:
    """Atomically write *payload* as JSON to *path*."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(target.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")
    tmp.replace(target)
    return target


def write_csv(rows: list[dict[str, Any]], path: str | Path) -> Path:
    """Atomically write *rows* as the project's raw CSV schema to *path*."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(target.suffix + ".tmp")
    with open(tmp, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=RAW_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow({col: row.get(col, "") for col in RAW_COLUMNS})
    tmp.replace(target)
    return target


def load_json_payload(path: str | Path) -> dict[str, Any]:
    """Load an Oanda JSON response (top-level object or bare candle list)."""
    with open(path, encoding="utf-8") as handle:
        data = json.load(handle)
    if isinstance(data, list):
        return {"instrument": DEFAULT_INSTRUMENT, "granularity": DEFAULT_GRANULARITY, "candles": data}
    if not isinstance(data, dict):
        raise ValueError(f"unexpected JSON shape in {path}")
    return data


def _load_oanda_config(path: str | Path) -> dict[str, Any]:
    """Load OANDA settings from the project YAML configuration."""
    config_path = Path(path)
    if not config_path.is_file():
        return {}
    with config_path.open(encoding="utf-8") as handle:
        config = yaml.safe_load(handle) or {}
    if not isinstance(config, dict):
        raise ValueError(f"Expected a YAML mapping in {config_path}")
    oanda_config = config.get("oanda", {}) or {}
    if not isinstance(oanda_config, dict):
        raise ValueError("'oanda' configuration must be a YAML mapping")
    return oanda_config


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--token", help="override configured token or $OANDA_API_TOKEN")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG_PATH),
                        help="settings YAML path")
    parser.add_argument("--instrument", default=DEFAULT_INSTRUMENT)
    parser.add_argument("--from", dest="time_from", default=DEFAULT_FROM)
    parser.add_argument("--to", dest="time_to", default=DEFAULT_TO)
    parser.add_argument("--granularity", default=DEFAULT_GRANULARITY)
    parser.add_argument("--price")
    parser.add_argument("--smooth", action="store_true", default=False)
    parser.add_argument("--live", action="store_true", help="use the live host instead of practice")
    parser.add_argument("--from-file", dest="from_file",
                        help="convert an existing Oanda JSON file instead of calling the API")
    parser.add_argument("--json-out", dest="json_output", default=str(DEFAULT_JSON_OUTPUT))
    parser.add_argument("--csv-out", dest="csv_output", default=str(DEFAULT_CSV_OUTPUT))
    parser.add_argument("--no-csv", action="store_true", help="do not write the CSV conversion")
    parser.add_argument("--no-json", action="store_true", help="do not write the JSON file")
    args = parser.parse_args(argv)

    if args.from_file:
        payload = load_json_payload(args.from_file)
        # Fill in instrument/from/to if missing so downstream messages are useful.
        payload.setdefault("instrument", args.instrument)
        payload.setdefault("from", args.time_from)
        payload.setdefault("to", args.time_to)
    else:
        oanda_config = _load_oanda_config(args.config)
        token = args.token or os.environ.get("OANDA_API_TOKEN") or oanda_config.get("api_token")
        if not isinstance(token, str) or not token.strip():
            parser.error(
                "Set oanda.api_token in config/setting.yml, OANDA_API_TOKEN, "
                "or --token when not using --from-file"
            )
        price = args.price or str(oanda_config.get("price", DEFAULT_PRICE))
        environment = str(oanda_config.get("environment", "practice")).lower()
        if environment not in ("practice", "live"):
            raise ValueError("'oanda.environment' must be 'practice' or 'live'")
        payload = fetch_candles(
            args.instrument,
            args.time_from,
            args.time_to,
            granularity=args.granularity,
            price=price,
            smooth=args.smooth,
            practice=not args.live and environment == "practice",
            token=token,
        )

    instrument = payload.get("instrument", args.instrument)
    rows = candles_to_rows(payload)
    print(f"Extracted {len(rows)} candle(s) for {instrument} "
          f"({payload.get('from', args.time_from)} -> {payload.get('to', args.time_to)})")

    if not args.no_json and not args.from_file:
        out = write_json(payload, args.json_output)
        print(f"Wrote JSON: {out}")
    elif not args.no_json and args.from_file:
        # Don't clobber the input file unless an explicit output path was given.
        pass
    if not args.no_csv:
        out = write_csv(rows, args.csv_output)
        print(f"Wrote CSV:  {out} ({len(rows)} data rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
