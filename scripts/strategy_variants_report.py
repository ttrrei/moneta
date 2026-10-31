"""Summarise the 6-iteration sweep (``iterations_*.csv``) into a report.

For each strategy it ranks the 6 variants by mean edge-vs-buy-hold at 2 bps
(the adjudication cost tier) across the 3 instruments, and prints a compact
per-strategy table plus an overall "any variant that beat buy-hold" ledger.

Run from the repo root::

    venv/bin/python scripts/strategy_variants_report.py \
        --csv strategy/results/iterations_2026-10-30.csv
"""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from strategy.schema import validate_cell_grid


def load(path: str) -> list[dict]:
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def _f(x: str) -> float:
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0


def aggregate(rows: list[dict], cost: float) -> dict[tuple[str, str], dict]:
    """Mean edge/trades per (strategy, variant) at ``cost`` bps, 3 instruments."""
    cells: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for r in rows:
        if _f(r["cost_bps"]) != cost or r.get("error", "").strip():
            continue
        cells[(r["strategy"], r["variant"])].append(r)
    out: dict[tuple[str, str], dict] = {}
    for key, cs in cells.items():
        n = len(cs)
        out[key] = {
            "mean_edge": sum(_f(c["edge_vs_bh_pct"]) for c in cs) / n,
            "mean_trades": sum(_f(c["n_trades"]) for c in cs) / n,
            "mean_tpy": sum(_f(c["trades_per_year"]) for c in cs) / n,
            "mean_win": sum(_f(c["win_rate_pct"]) for c in cs) / n,
            "win_instr": len({c["instrument"] for c in cs if _f(c["edge_vs_bh_pct"]) > 0}),
            "win_instr_by_window": {
                window: len({c["instrument"] for c in cs
                             if c["window"] == window and _f(c["edge_vs_bh_pct"]) > 0})
                for window in ("full", "last_12m")
            },
        }
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--csv", default="strategy/results/iterations_2026-10-30.csv")
    args = ap.parse_args()

    rows = load(args.csv)
    validate_cell_grid(rows, ("EUR_USD", "BTC_USD", "XAU_USD"),
                       ("full", "last_12m"), (0, 2, 5), ("strategy", "variant"))
    print("full and last_12m overlap; they are descriptive slices, not independent validations.")
    errs = [r for r in rows if r.get("error", "").strip()]
    print(f"Loaded {len(rows)} cells ({len(errs)} with errors)\n")

    if errs:
        print("ERRORS:")
        for r in errs[:20]:
            print(f"  {r['strategy']} {r['variant']}: {r['error'][:70]}")
        if len(errs) > 20:
            print(f"  ... {len(errs) - 20} more")
        print()

    for cost in (2.0, 0.0):
        agg = aggregate(rows, cost)
        sids = sorted({k[0] for k in agg})
        print(f"=== {int(cost)} bps — variants ranked by mean edge vs buy-hold (3 instruments) ===")
        print(f"{'sid':<6} {'variant':<20} {'edge':>9} {'trades':>8} {'tpy':>7} {'win%':>6} {'>BH':>4}")
        for sid in sids:
            ranked = sorted(((v, m) for (s, v), m in agg.items() if s == sid),
                            key=lambda x: -x[1]["mean_edge"])
            for v, m in ranked:
                flag = " *" if m["win_instr"] >= 1 else ""
                print(f"{sid:<6} {v:<20} {m['mean_edge']:>+9.2f} "
                      f"{m['mean_trades']:>8.0f} {m['mean_tpy']:>7.1f} "
                      f"{m['mean_win']:>6.1f} {m['win_instr']}/3{flag}")
            print()

    # Ledger: any single cell that beat buy-hold at 2 bps on >= 2 instruments.
    print("=== Cells beating buy-hold on >= 2 of 3 instruments (2 bps) ===")
    bycell = defaultdict(list)
    for r in rows:
        if _f(r["cost_bps"]) == 2.0 and not r.get("error", "").strip() \
                and _f(r["edge_vs_bh_pct"]) > 0:
            bycell[(r["strategy"], r["variant"], r["window"])].append(r["instrument"])
    found = False
    for (sid, v, w), instrs in sorted(bycell.items()):
        if len(instrs) >= 2:
            found = True
            print(f"  {sid} {v} ({w}): {len(instrs)}/3  {', '.join(instrs)}")
    if not found:
        print("  (none — no variant beat buy-hold on 2+ instruments at 2 bps)")


if __name__ == "__main__":
    main()
