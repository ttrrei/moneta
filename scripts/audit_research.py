"""Recompute review claims from committed CSV/Markdown evidence, without market data.

Artifact filenames remain identifiers; they are not evidence of execution dates.
Git introduction dates bound when evidence was recorded, not when a run began.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from strategy.registry import parse_registry, parse_trial_log
from strategy.schema import validate_cell_grid


def cost_diagnostics(rows: list[dict]) -> tuple[dict, list[dict]]:
    """Pair identical cells at zero/two bps; avoid inferring beta or causation.

    Gross/net refers only to this engine's transaction-cost tiers. Financing
    and live execution costs are not present in the historical results.
    """
    paired = defaultdict(dict)
    for row in rows:
        cost = float(row["cost_bps"])
        if cost in (0., 2.):
            key = tuple(row[name] for name in ("strategy", "variant", "instrument", "window"))
            if cost in paired[key]:
                raise ValueError(f"duplicate cost cell: {key}/{cost}")
            paired[key][cost] = row
    cells, groups = [], defaultdict(list)
    for key, costs in sorted(paired.items()):
        if set(costs) != {0., 2.}:
            raise ValueError(f"missing zero/two-bps pair: {key}")
        gross, net = costs[0.], costs[2.]
        bh = float(gross["buyhold_return_pct"])
        if bh != float(net["buyhold_return_pct"]):
            raise ValueError(f"cost tiers have different benchmarks: {key}")
        gr, nr = float(gross["total_return_pct"]), float(net["total_return_pct"])
        ge, ne = round(gr - bh, 2), round(nr - bh, 2)
        cell = dict(zip(("strategy", "variant", "instrument", "window"), key))
        cell.update(gross_return_pct=gr, net_return_pct=nr, buyhold_return_pct=bh,
                    gross_edge_pct=ge, net_edge_pct=ne,
                    transaction_cost_drag_pp=round(gr - nr, 2),
                    cost_erased_benchmark_edge=ge > 0 and ne <= 0,
                    cost_erased_positive_return=gr > 0 and nr <= 0,
                    n_trades=int(float(net["n_trades"])))
        cells.append(cell)
        groups[key[0], key[1], key[3]].append(cell)
    buckets = Counter()
    e_details = Counter()
    for group in groups.values():
        wins = sum(c["net_edge_pct"] > 0 for c in group)
        if wins >= 2:
            bucket = "two_or_more_net_benchmark_wins"
        elif wins:
            bucket = "one_net_benchmark_win"
        elif not sum(c["n_trades"] for c in group):
            bucket = "empty_signal"
        elif any(c["gross_edge_pct"] > 0 for c in group):
            bucket = "gross_benchmark_win_erased_at_2bps"
        elif any(c["gross_return_pct"] > 0 for c in group):
            bucket = "some_positive_gross_return_without_net_benchmark_wins"
            e_details["any_positive_net_return" if any(c["net_return_pct"] > 0 for c in group)
                      else "no_positive_net_return"] += 1
        else:
            bucket = "no_positive_gross_return"
        buckets[bucket] += 1
    return {"group_buckets": dict(sorted(buckets.items())),
            "positive_gross_bucket_net_outcomes": dict(sorted(e_details.items())),
            "paired_cells": len(cells),
            "cells_with_cost_erased_benchmark_edge": sum(c["cost_erased_benchmark_edge"] for c in cells),
            "cells_with_cost_erased_positive_return": sum(c["cost_erased_positive_return"] for c in cells),
            "interpretation": "rounded historical transaction-cost sensitivity; no beta or statistical-skill inference"}, cells


def audit(root: Path) -> dict:
    files = sorted((root / "strategy/results").glob("iterations_*.csv"))
    merged = {}
    sources = []
    conflicts = []
    for path in files:
        with path.open(newline="", encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        validate_cell_grid(rows, ("EUR_USD", "BTC_USD", "XAU_USD"),
                           ("full", "last_12m"), (0, 2, 5), ("strategy", "variant"))
        sources.append({"path": str(path.relative_to(root)), "rows": len(rows),
                        "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
        for row in rows:
            key = tuple(row[field] for field in ("strategy", "variant", "instrument", "window", "cost_bps"))
            if key in merged and merged[key] != row:
                conflicts.append(list(key))
            merged[key] = row
    if conflicts:
        raise ValueError(f"conflicting repeated cells: {conflicts[:10]}")
    rows = list(merged.values())
    at_two = [row for row in rows if float(row["cost_bps"]) == 2]
    groups = defaultdict(list)
    for row in at_two:
        groups[row["strategy"], row["variant"], row["window"]].append(row)
    categories = Counter()
    winners = []
    cross_market = defaultdict(set)
    for (sid, variant, window), cells in groups.items():
        wins = [row for row in cells if float(row["edge_vs_bh_pct"]) > 0]
        winners.extend(wins)
        if len(wins) >= 2:
            categories["two_or_more_instrument_wins"] += 1
            cross_market[sid, variant].add(window)
        elif wins:
            categories["one_instrument_win"] += 1
        elif sum(int(float(row["n_trades"])) for row in cells) == 0:
            categories["empty_signal"] += 1
        elif max(float(row["trades_per_year"]) for row in cells) > 54:
            # A descriptive bucket matching the reviewers' query, not proof
            # that frequency caused the loss. Gross-vs-net comparison is needed.
            categories["no_win_and_over_54_trades_per_year"] += 1
        else:
            categories["other_no_win"] += 1
    registry = parse_registry(root / "strategy/STRATEGY_REGISTRY.md")
    trials = parse_trial_log(root / "strategy/trial_log.md")
    distinct = sorted({(row["strategy"], row["variant"]) for row in rows})
    diverse = []
    for number in range(113, 133):
        path = root / f"strategy/results/S{number}/summary.csv"
        with path.open(newline="", encoding="utf-8") as fh:
            cells = list(csv.DictReader(fh))
        validate_cell_grid(cells, ("EUR_USD", "BTC_USD", "XAU_USD"),
                           ("full", "last_12m"), (0, 2, 5))
        diverse.extend(row for row in cells if float(row["cost_bps"]) == 2)
    return {
        "scope": "committed research evidence only; no market data or holdout read",
        "registered_strategies": len(registry),
        "statuses": dict(sorted(Counter(row["status"] for row in registry.values()).items())),
        "sweep_sources": sources,
        "sweep_stored_rows": sum(source["rows"] for source in sources),
        "sweep_unique_cells": len(rows),
        "sweep_repeated_identical_cells": sum(source["rows"] for source in sources) - len(rows),
        "sweep_distinct_configs": len(distinct),
        "sweep_cells_at_2bps": len(at_two),
        "sweep_groups_at_2bps": len(groups),
        "descriptive_failure_buckets": dict(sorted(categories.items())),
        "gross_vs_net": cost_diagnostics(rows)[0],
        "winning_cells_at_2bps": len(winners),
        "winning_cells_with_at_most_two_trades": sum(int(float(row["n_trades"])) <= 2 for row in winners),
        "cross_market_configs_in_both_overlapping_windows": [
            {"strategy": sid, "variant": variant} for (sid, variant), windows in sorted(cross_market.items())
            if windows == {"full", "last_12m"}],
        "s109_ema_gate_at_2bps": [row for row in at_two if row["strategy"] == "s109" and row["variant"] == "ema_gate"],
        "diverse_batch_cells_at_2bps": len(diverse),
        "diverse_batch_winning_cells_at_2bps": sum(float(row["total_return_pct"]) > float(row["buyhold_return_pct"]) for row in diverse),
        "trial_rows": len(trials),
        "trial_dates": dict(sorted(Counter(row["date"] for row in trials).items())),
        "ledger_sha256": hashlib.sha256((root / "strategy/oos_ledger.json").read_bytes()).hexdigest(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--cost-csv", type=Path, help="also write per-cell paired cost diagnostics")
    args = parser.parse_args()
    if args.cost_csv:
        merged = {}
        for path in sorted((args.root / "strategy/results").glob("iterations_*.csv")):
            with path.open(newline="") as fh:
                for row in csv.DictReader(fh):
                    key = tuple(row[k] for k in ("strategy", "variant", "instrument", "window", "cost_bps"))
                    if key in merged and merged[key] != row:
                        raise ValueError(f"conflicting repeated cell: {key}")
                    merged[key] = row
        _, cells = cost_diagnostics(list(merged.values()))
        with args.cost_csv.open("w", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(cells[0]))
            writer.writeheader()
            writer.writerows(cells)
    print(json.dumps(audit(args.root.resolve()), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
