"""Minimal RSI mean-reversion backtest (reference strategy, not an alpha claim).

Rules (default on 5m bars, one instrument at a time):
  * Enter long  at bar T+1 open  when RSI_24(T) <  30 and flat.
  * Exit long   at bar T+1 open  when RSI_24(T) >  55.
  * One position at a time, long only, position size = 1 unit.
  * One-way cost of 2 bps applied at entry and exit (typical OANDA CFD spread).
  * B6 entry guard (default OFF, to match the documented S-01 baseline): no
    *new* entries on gap bars or near market close (exits are never blocked).
    Enable with ``--entry-guard``.

Execution model follows the indicator spec: a signal computed on a closed bar
T is traded at the next bar's open (no same-bar fill, no lookahead).

Accounting & metrics are owned by the **shared engine** (``strategy/engine.py``);
this file is a thin CLI over :mod:`strategy.strategy_rsi_lib`.

Run from the repo root::

    python strategy/code/strategy_rsi.py                     # EUR_USD, 5m, all history
    python strategy/code/strategy_rsi.py --instrument BTC_USD --since 2023-01-01
    python strategy/code/strategy_rsi.py --cost-bps 0        # cost sensitivity (0/2/5)
    python strategy/code/strategy_rsi.py --timeframe 1h      # run the same rule on 1h bars
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Make ``strategy.*`` importable both from the repo root and when this file is
# run directly (``python strategy/code/strategy_rsi.py``).
_REPO_ROOT = str(Path(__file__).resolve().parents[2])
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from strategy.strategy_rsi_lib import (  # noqa: E402
    COST_BPS,
    TIMEFRAME_PARQUET,
    TIMEFRAME_SECONDS,
    run_rsi,
)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--instrument", default="EUR_USD")
    ap.add_argument("--timeframe", default="5m", choices=sorted(TIMEFRAME_SECONDS),
                    help="bar timeframe; selects the matching feature parquet")
    ap.add_argument("--since", default=None, help="ISO date, e.g. 2023-01-01")
    ap.add_argument("--until", default=None,
                    help="ISO date, inclusive upper bound. MUST be strictly before "
                         "oos.holdout_start (config/strategies.yml) — a manual run "
                         "with no --until (or one on/after the holdout) is refused "
                         "by the data-layer gate. Use the in-sample windows "
                         "(until: 2025-07-31) for normal runs.")
    ap.add_argument("--parquet", default=None,
                    help="override feature parquet (defaults by --timeframe)")
    ap.add_argument("--cost-bps", type=float, default=COST_BPS,
                    help="one-way transaction cost in basis points (default 2)")
    ap.add_argument("--json", default=None, help="also write results JSON to path")
    ap.add_argument("--entry-guard", action="store_true",
                    help="enable the B6 rule (no new entries on gap / near-market-close bars). "
                         "Off by default to match the documented S-01 baseline.")
    args = ap.parse_args()

    out = run_rsi(
        parquet=args.parquet or TIMEFRAME_PARQUET[args.timeframe],
        instrument=args.instrument,
        timeframe=args.timeframe,
        since=args.since,
        until=args.until,
        cost_bps=args.cost_bps,
        entry_guard=args.entry_guard,
    )
    print(json.dumps(out, indent=2))
    if args.json:
        Path(args.json).write_text(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
