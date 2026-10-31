"""Replay the existing S-18/S-33/S-37/S-39 variants into separate evidence.

No new hypotheses, threshold selection, status updates or holdout reads. The
original 936f7b9 rules and midnight bound reproduce the committed 2-bps cells
before their trade times are compared with the repaired implementation.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib
import inspect
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd
import numpy as np
import yaml
from strategy.engine import run_backtest
from strategy.strategy_lib import make_bars, TIMEFRAME_PARQUET
from strategy.variants import STRATEGIES, VARIANTS, resolve

ROOT = Path(__file__).resolve().parents[1]
IDS = ("s18", "s33", "s37", "s39")
METRICS = ("n_trades", "total_return_pct", "buyhold_return_pct", "max_drawdown_pct",
           "win_rate_pct", "sharpe_weekly", "trades_per_year", "exposure_pct")


def trade_key(trade, times) -> tuple:
    return (trade.direction, str(times[trade.entry_time]), str(times[trade.exit_time]),
            trade.entry_price, trade.exit_price)


class PositionReplay:
    """Immutable decisions from a fresh rule; these legacy rules ignore costs."""
    def __init__(self, rule, length):
        self.positions = np.array([rule.desired_position(i) for i in range(length)], dtype=np.int8)

    def desired_position(self, index):
        return self.positions[index]


def recompute(out: Path, strategies=IDS) -> dict:
    if out.exists():
        raise ValueError(f"refusing to overwrite existing replay directory: {out}")
    if set(strategies) - set(IDS):
        raise ValueError("only the four repaired legacy strategies are supported")
    cfg = yaml.safe_load((ROOT / "config/strategies.yml").read_text())
    committed = {}
    sources = {}
    for path in sorted((ROOT / "strategy/results").glob("iterations_*.csv")):
        sources[str(path.relative_to(ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
        with path.open(newline="") as fh:
            for row in csv.DictReader(fh):
                if row["strategy"] in strategies:
                    key = (row["strategy"], row["variant"], row["instrument"],
                           row["window"], float(row["cost_bps"]))
                    if key in committed and committed[key] != row:
                        raise ValueError(f"conflicting original cell: {key}")
                    committed[key] = row
    rows, changes = [], []
    code_paths = [ROOT / "strategy" / name for name in
                  ("engine.py", "strategy_lib.py", "oos_token.py", "variants.py")]
    code_paths += [ROOT / "strategy" / (STRATEGIES[sid] + ".py") for sid in strategies]
    code_paths += [Path(__file__)]
    code_hashes = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in code_paths}
    started = datetime.now(timezone.utc).isoformat()
    out.mkdir(parents=True)
    try:
        for sid in strategies:
            module = importlib.import_module("strategy." + STRATEGIES[sid])
            rel = f"strategy/{STRATEGIES[sid]}.py"
            original_source = subprocess.check_output(["git", "show", f"936f7b9:{rel}"], cwd=ROOT, text=True)
            original = {"__name__": "historical_" + sid}
            exec(compile(original_source, rel + "@936f7b9", "exec"), original)
            loader = next(fn for name, fn in vars(module).items()
                          if name.startswith("load_") and name != "load_bars"
                          and inspect.isfunction(fn) and fn.__module__ == module.__name__)
            for timeframe in ("5m", "1h"):
                variants = [resolve(sid, name, cfg=cfg) for name, _ in VARIANTS[sid]
                            if resolve(sid, name, cfg=cfg).timeframe == timeframe]
                if not variants:
                    continue
                for instrument in ("EUR_USD", "BTC_USD", "XAU_USD"):
                    for window in ("full", "last_12m"):
                        bound = cfg["windows"][window]
                        frame = loader(str(ROOT / TIMEFRAME_PARQUET[timeframe]), instrument,
                                       since=bound["since"], until=bound["until"])
                        legacy = frame.loc[frame["time"] <= pd.Timestamp(bound["until"], tz="UTC")]
                        legacy_times = legacy["time"].to_numpy()
                        current_times = frame["time"].to_numpy()
                        for variant in variants:
                            before = run_backtest(make_bars(legacy, timeframe, variant.entry_guard),
                                                  original["build_rule"](legacy, **variant.run_kwargs),
                                                  cost_bps=2., long_only=True)
                            old_row = committed[sid, variant.variant, instrument, window, 2.]
                            mismatches = {field: (float(old_row[field]), before.to_dict()[field])
                                          for field in METRICS
                                          if float(old_row[field]) != before.to_dict()[field]}
                            if mismatches:
                                raise ValueError(f"legacy reproduction mismatch {sid}/{variant.variant}/{instrument}/{window}: {mismatches}")
                            decisions = PositionReplay(module.build_rule(frame, **variant.run_kwargs), len(frame))
                            for cost in (0., 2., 5.):
                                result = run_backtest(make_bars(frame, timeframe, variant.entry_guard),
                                                      decisions,
                                                      cost_bps=cost, long_only=True)
                                prior = committed[sid, variant.variant, instrument, window, cost]
                                row = {"strategy": sid, "variant": variant.variant,
                                       "instrument": instrument, "window": window, "timeframe": timeframe,
                                       "cost_bps": cost, "start": str(frame["time"].iloc[0]),
                                       "end": str(frame["time"].iloc[-1]), "n_bars": len(frame),
                                       "legacy_2bps_reproduced": True}
                                for field in METRICS:
                                    row["before_" + field] = float(prior[field])
                                    row[field] = result.to_dict()[field]
                                    row["delta_" + field] = round(row[field] - float(prior[field]), 8)
                                row["edge_vs_bh_pct"] = round(result.total_return_pct - result.buyhold_return_pct, 2)
                                row["before_edge_vs_bh_pct"] = float(prior["edge_vs_bh_pct"])
                                rows.append(row)
                                if cost == 2.:
                                    old_keys = {trade_key(trade, legacy_times) for trade in before.trades}
                                    new_keys = {trade_key(trade, current_times) for trade in result.trades}
                                    for kind, keys in (("removed", old_keys - new_keys), ("added", new_keys - old_keys)):
                                        for key in sorted(keys):
                                            changes.append({"strategy": sid, "variant": variant.variant,
                                                            "instrument": instrument, "window": window, "change": kind,
                                                            **dict(zip(("direction", "entry_time", "exit_time", "entry_price", "exit_price"), key))})
                        print(f"replayed {sid}/{timeframe}/{instrument}/{window}: {len(rows)} cells", flush=True)
        for path in code_paths:
            if hashlib.sha256(path.read_bytes()).hexdigest() != code_hashes[str(path.relative_to(ROOT))]:
                raise ValueError(f"implementation changed during replay: {path}")
        for name, records in (("comparison.csv", rows), ("trade_changes.csv", changes)):
            with (out / name).open("w", newline="") as fh:
                writer = csv.DictWriter(fh, fieldnames=list(records[0]) if records else ["change"])
                writer.writeheader()
                writer.writerows(records)
        summary = {"schema_version": 1, "scope": "existing configurations; in-sample only",
                   "historical_implementation": "936f7b9", "strategies": list(strategies),
                   "cells": len(rows), "legacy_2bps_cells_reproduced": len(rows) // 3,
                   "metric_changed_cells": sum(any(r["delta_" + field] for field in METRICS) for r in rows),
                   "trade_changes_at_2bps": len(changes), "implementation_sha256": code_hashes,
                   "original_csv_sha256": sources, "started_at_utc": started,
                   "finished_at_utc": datetime.now(timezone.utc).isoformat(),
                   "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
                   "dirty": bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True)),
                   "status_policy": "historical statuses retained; no finalist nomination"}
        (out / "manifest.yml").write_text(yaml.safe_dump(summary, sort_keys=True))
        return summary
    except BaseException as exc:
        (out / "FAILED.txt").write_text(str(exc))
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(recompute(args.out), indent=2))


if __name__ == "__main__":
    main()
