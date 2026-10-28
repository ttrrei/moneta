"""Minimal squeeze-onset backtest (S-04, long/short, not an alpha claim).

Registered rules (default on 5m bars, one instrument at a time):
  * A *squeeze* is the Bollinger bands inside the Keltner channel
    (``sqz_on_24 = 1``), i.e. a volatility compression.
  * Enter at the **squeeze onset** (the 0->1 transition), taking direction by
    ``close vs bb_mid_24`` (long if above, short if below), then hold that
    direction for the whole episode. Enters are NOT re-evaluated on every bar
    — this keeps the rule from re-firing each time the direction flips, which
    on this data churns to ~19k trades.
  * Exit at the **squeeze-off** (the 1->0 transition).
  * One position at a time, long AND short, position size = 1 unit.
  * One-way cost applied at entry and exit (default 2 bps).
  * B6 entry guard (default OFF). Enable with ``--entry-guard``.

Honest outcome (rejected): at 5m the squeeze fires very often (~10.5k episodes
in 5 years), so the rule trades far more often than the "low-frequency"
premise the idea was built on, and is eaten alive by the cost model (see the
report).

Execution model: a signal computed on a closed bar T is traded at the next
bar's open (no same-bar fill, no lookahead).

Accounting & metrics are owned by the **shared engine** (``strategy/engine.py``);
this file is a thin CLI over :mod:`strategy.strategy_squeeze_lib`.

Run from the repo root::

    python strategy/code/strategy_squeeze.py                      # EUR_USD, 5m, all history
    python strategy/code/strategy_squeeze.py --instrument BTC_USD --since 2023-01-01
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO_ROOT = str(Path(__file__).resolve().parents[2])
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from strategy.strategy_squeeze_lib import (  # noqa: E402
    COST_BPS,
    TIMEFRAME_PARQUET,
    run_squeeze,
)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--instrument", default="EUR_USD")
    ap.add_argument("--timeframe", default="5m", choices=sorted(TIMEFRAME_PARQUET),
                    help="bar timeframe; selects the matching feature parquet")
    ap.add_argument("--since", default=None, help="ISO date, e.g. 2023-01-01")
    ap.add_argument("--until", default=None,
                    help="ISO date, inclusive upper bound. For in-sample runs use "
                         "config/strategies.yml windows (until: 2025-07-31) so the "
                         "holdout is never touched by a manual run.")
    ap.add_argument("--parquet", default=None, help="override feature parquet")
    ap.add_argument("--cost-bps", type=float, default=COST_BPS,
                    help="one-way transaction cost in basis points (default 2)")
    ap.add_argument("--json", default=None, help="also write results JSON to path")
    ap.add_argument("--entry-guard", action="store_true",
                    help="enable the B6 rule (no new entries on gap / near-market-close bars).")
    args = ap.parse_args()

    out = run_squeeze(
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
