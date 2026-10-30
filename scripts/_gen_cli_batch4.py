"""Generate the 15 S-43..S-57 CLI wrappers from the same spec (_gen_batch4).

Run:  venv/bin/python scripts/_gen_cli_batch4.py
"""

from __future__ import annotations

import importlib.util
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]

_spec = importlib.util.spec_from_file_location("g4", str(ROOT / "scripts" / "_gen_batch4.py"))
g4 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(g4)

CLI = '''"""{sid} {title} backtest CLI (reference strategy, not an alpha claim).

Thin CLI over :mod:`strategy.{lib}` — the rule and all accounting live there
(shared engine, shared strategy core). Run from the repo root::

    python strategy/code/{cli}.py
    python strategy/code/{cli}.py --instrument BTC_USD --cost-bps 0
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO_ROOT = str(Path(__file__).resolve().parents[2])
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from strategy.{lib} import (  # noqa: E402
    COST_BPS,
    TIMEFRAME_PARQUET,
    TIMEFRAME_SECONDS,
    {runname},
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
                    help="enable the B6 rule (no new entries on gap / near-market-close bars).")
    ap.add_argument("--ema-gate", action="store_true",
                    help="only enter while the previous closed bar's close > ema_24.")
{params}
    args = ap.parse_args()

    out = {runname}(
        parquet=args.parquet or TIMEFRAME_PARQUET[args.timeframe],
        instrument=args.instrument,
        timeframe=args.timeframe,
        since=args.since,
        until=args.until,
        cost_bps=args.cost_bps,
        entry_guard=args.entry_guard,
        ema_gate=args.ema_gate,
{callparams}
    )

    payload = {{k: v for k, v in out.items() if k != "trades"}}
    if args.json:
        Path(args.json).write_text(json.dumps(payload, indent=2) + "\\n")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
'''


def main() -> None:
    for s in g4.S:
        params = "".join(
            '    ap.add_argument("--%s", type=float, default=%s,\n'
            '                    help="%s (default %s)")\n' % (p[0], p[1], p[0], p[1])
            for p in s["params"])
        call = ", ".join(f"{p[0]}=args.{p[0]}" for p in s["params"])
        if call:
            call += ","
        lib = pathlib.Path(g4.FILES[s["sid"]]).stem
        cli = lib.replace("_lib", "")
        txt = CLI.format(sid=s["sid"], title=s["title"], lib=lib, cli=cli,
                         runname="run_" + s["loadname"], params=params,
                         callparams=call)
        out = ROOT / f"strategy/code/{cli}.py"
        out.write_text(txt)
        print("wrote", out.name, s["sid"])


if __name__ == "__main__":
    main()
