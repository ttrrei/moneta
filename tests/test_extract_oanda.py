"""Unit tests for OANDA historical extraction."""

from __future__ import annotations

import csv
from pathlib import Path
from unittest.mock import MagicMock

import pytest

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


def test_fetch_candles_paginates_and_requests_all_price_components(monkeypatch) -> None:
    monkeypatch.setattr(extract_oanda, "PAGE_SIZE", 2)
    session = MagicMock()
    first = MagicMock()
    first.json.return_value = {
        "instrument": "GBP_USD",
        "granularity": "M1",
        "candles": [
            _candle("2026-07-08T02:25:00.000000000Z"),
            _candle("2026-07-08T02:26:00.000000000Z"),
        ],
    }
    second = MagicMock()
    second.json.return_value = {
        "instrument": "GBP_USD",
        "granularity": "M1",
        "candles": [_candle("2026-07-08T02:27:00.000000000Z")],
    }
    session.get.side_effect = [first, second]

    payload = extract_oanda.fetch_candles(
        "GBP_USD",
        "2026-07-08T02:25:00Z",
        "2026-07-08T02:27:00Z",
        token="test-token",
        session=session,
    )

    assert len(payload["candles"]) == 3
    assert session.get.call_count == 2
    first_call, second_call = session.get.call_args_list
    assert first_call.kwargs["params"]["price"] == "MBA"
    assert "count" not in first_call.kwargs["params"]
    assert first_call.kwargs["params"]["to"] == "2026-07-08T02:26:00Z"
    assert first_call.kwargs["headers"]["Authorization"] == "Bearer test-token"
    assert second_call.kwargs["params"]["from"] == "2026-07-08T02:27:00Z"
    session.close.assert_not_called()


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
