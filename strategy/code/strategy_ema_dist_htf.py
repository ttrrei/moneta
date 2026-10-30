"""Thin CLI for S-125: ATR-normalized EMA trend with 1h SuperTrend."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = str(Path(__file__).resolve().parents[2])
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from strategy.strategy_diverse_lib import cli_main


if __name__ == "__main__":
    cli_main("s125")
