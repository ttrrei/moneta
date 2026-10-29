"""Minimal regime-gated slow-trend backtest (S-07, long/short, not an alpha claim).

Registered rules (default on 1h bars, one instrument at a time):
  * Follow the **slow** SuperTrend direction (``st_dir_120_2``, 120-bar /
    2.0×ATR) — long while up, short while down.
  * Take a **new** direction only on a SuperTrend flip that happens while the
    market is trending (``adx_24 > 25``). A flip in a weak regime (``adx_24
    <= 25``) makes the strategy stand flat.
  * Between flips, hold the position and ride the trend to the next flip.
  * One position at a time, long AND short, position size = 1 unit.
  * One-way cost applied at entry and exit (default 2 bps).
  * B6 entry guard (default OFF). Enable with ``--entry-guard``.

Why 1h + 120-bar: at 5m this rule still flips ~25k times (S-05's failure was
exactly that); on 1h bars the SuperTrend-120 flips ~1.8k times and the ADX
gate brings it to ~70–100 entries a year — the low-frequency band the earlier
cost×frequency rejections (S-01/S-04/S-05) require. See the report for the
honest diagnosis.

Execution model: a signal computed on a closed bar T is traded at the next
bar's open (no same-bar fill, no lookahead).

Accounting & metrics are owned by the **shared engine** (``strategy/engine.py``);
this file is a thin CLI over :mod:`strategy.strategy_regime_trend_lib`.

Run from the repo root::

    python strategy/code/strategy_regime_trend.py                     # EUR_USD, 1h, all history
    python strategy/code/strategy_regime_trend.py --instrument BTC_USD --since 2023-01-01
    python strategy/code/strategy_regime_trend.py --cost-bps 0        # cost sensitivity (0/2/5)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO_ROOT = str(Path(__file__).resolve().parents[2])
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from strategy.strategy_regime_trend_lib import (  # noqa: E402
    COST_BPS,
    TIMEFRAME_PARQUET,
    run_regime_trend,
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

    out = run_regime_trend(
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
