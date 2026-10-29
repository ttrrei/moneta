"""Minimal EMA-spread-24/120 trend follower backtest (reference strategy, not an alpha claim).

Rule (default on 5m bars, one instrument at a time):
  * Hold long   when the previous closed bar's EMA spread (ema_spread_24_120) is positive.
  * Flat        when it goes negative.
  * One position at a time, long only, position size = 1 unit.
  * One-way cost of 2 bps applied at entry and exit (typical OANDA CFD spread).
  * B6 entry guard (default OFF, to match the S-01 baseline convention): no
    *new* entries on gap bars or near market close (exits are never blocked).
    Enable with ``--entry-guard``.

Execution model follows the indicator spec: a signal computed on a closed bar
T is traded at the next bar's open (no same-bar fill, no lookahead).

Accounting & metrics are owned by the **shared engine** (``strategy/engine.py``);
this file is a thin CLI over :mod:`strategy.strategy_ema_spread_lib`.

S-06 was **rejected** in the matrix as a general strategy: it is above
buy-hold on BTC at 0 bps only and below it at 2/5 bps, and loses on EUR/XAU —
a single-instrument fit, not a cross-market edge. See
``strategy/docs/strategy_ema_spread_report.md`` for the diagnosis.

Run from the repo root::

    python strategy/code/strategy_ema_spread.py
    python strategy/code/strategy_ema_spread.py --instrument BTC_USD --cost-bps 0
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Make ``strategy.*`` importable both from the repo root and when this file is
# run directly (``python strategy/code/strategy_ema_spread.py``).
_REPO_ROOT = str(Path(__file__).resolve().parents[2])
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from strategy.strategy_ema_spread_lib import (  # noqa: E402
    COST_BPS,
    TIMEFRAME_PARQUET,
    TIMEFRAME_SECONDS,
    run_ema_spread,
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

    out = run_ema_spread(
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
