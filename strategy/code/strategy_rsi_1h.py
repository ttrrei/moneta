"""Minimal RSI mean-reversion on 1-hour bars (S-02 candidate, not an alpha claim).

Rules (default on 1h bars, one instrument at a time, long-only):
  * Enter long at bar T+1 open when RSI_24(T) <  30 and flat.
  * Exit long  at bar T+1 open when RSI_24(T) >  55.
  * One position at a time, long only, position size = 1 unit.
  * One-way cost applied at entry and exit (default 2 bps).
  * B6 entry guard (default OFF): no *new* entries on gap bars or near market
    close. Enable with ``--entry-guard``.

Why 1h: on 5m bars the same rule churns to ~270 trades / 5 years and is
eaten alive by the cost model (S-01). S-02 is the deliberately slower variant
to test whether a lower trade rate keeps the same edge. It does not: see the
report for the honest diagnosis.

Execution model: a signal computed on a closed bar T is traded at the next
bar's open (no same-bar fill, no lookahead).

Accounting & metrics are owned by the **shared engine** (``strategy/engine.py``);
this file is a thin CLI over :mod:`strategy.strategy_rsi_1h_lib`.

Run from the repo root::

    python strategy/code/strategy_rsi_1h.py                     # EUR_USD, 1h, all history
    python strategy/code/strategy_rsi_1h.py --instrument BTC_USD --since 2023-01-01
    python strategy/code/strategy_rsi_1h.py --cost-bps 0        # cost sensitivity (0/2/5)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO_ROOT = str(Path(__file__).resolve().parents[2])
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from strategy.strategy_rsi_1h_lib import (  # noqa: E402
    COST_BPS,
    TIMEFRAME_PARQUET,
    run_rsi_1h,
)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--instrument", default="EUR_USD")
    ap.add_argument("--timeframe", default="1h", choices=sorted(TIMEFRAME_PARQUET),
                    help="bar timeframe; selects the matching feature parquet (default 1h)")
    ap.add_argument("--since", default=None, help="ISO date, e.g. 2023-01-01")
    ap.add_argument("--until", default=None,
                    help="ISO date, inclusive upper bound. MUST be strictly before "
                         "oos.holdout_start (config/strategies.yml) — a manual run "
                         "with no --until (or one on/after the holdout) is refused "
                         "by the data-layer gate. Use the in-sample windows "
                         "(until: 2025-07-31) for normal runs.")
    ap.add_argument("--parquet", default=None, help="override feature parquet")
    ap.add_argument("--cost-bps", type=float, default=COST_BPS,
                    help="one-way transaction cost in basis points (default 2)")
    ap.add_argument("--json", default=None, help="also write results JSON to path")
    ap.add_argument("--entry-guard", action="store_true",
                    help="enable the B6 rule (no new entries on gap / near-market-close bars).")
    args = ap.parse_args()

    out = run_rsi_1h(
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
