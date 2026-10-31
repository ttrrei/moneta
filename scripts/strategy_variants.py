"""In-sample variant sweep for the registered legacy strategies S-08..S-112.

For each selected strategy, evaluate its declared variants
over the in-sample matrix: 3 instruments (EUR_USD / BTC_USD / XAU_USD) x 2
windows (full, last_12m) x 3 cost tiers (0 / 2 / 5 bps) = 18 cells.

All variants run on **in-sample data only** (window ``until`` is read from
``config/strategies.yml → windows`` and always stops before the holdout) — no
OOS holdout is touched (the holdout is a one-shot gate reserved for the single
finalist under ``config/strategies.yml → oos.pass_criteria``). This file is a
sweep-only helper, NOT the canonical execution path (see the comment near the
imports).

Each row of the CSV records one cell:
  strategy, variant, instrument, window, cost_bps,
  n_trades, trades_per_year, total_return_pct, buyhold_return_pct,
  win_rate_pct, sharpe_weekly, max_drawdown_pct, exposure_pct.

Run from the repo root::

    venv/bin/python scripts/strategy_variants.py --workers 4 --out /tmp/moneta_sweep.csv
"""

from __future__ import annotations

import argparse
import csv
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# This is a **sweep-only helper**, NOT the canonical execution path.
#   * Canonical path: `strategy/run_matrix.py` — it owns the OOS gate, the
#     one-shot ledger reservation, the manifest, and the trial-log bookkeeping.
#   * Any holdout read is forbidden here: this harness evaluates the
#     in-sample windows only (full / last_12m) and must never touch the holdout.
# The evaluation windows and the instrument/cost axes are read from the SAME
# config the runner uses, so re-anchoring a window in `config/strategies.yml`
# can no longer silently desynchronise the two execution paths
# (review follow-up #3 §D).
from strategy.run_matrix import (
    INSTRUMENTS,
    COST_TIERS,
    _load_config,
    _window_bounds,
)

_CFG = _load_config()
WINDOWS = {
    name: {"since": _window_bounds(_CFG, name)[0],
           "until": _window_bounds(_CFG, name)[1]}
    for name in ("full", "last_12m")
}
PARQUET_5M = "data/ohlcv_5m_features/ohlcv_5m_features.parquet"
PARQUET_1H = "data/ohlcv_1h_features/ohlcv_1h_features.parquet"

from strategy.variants import STRATEGIES, VARIANTS, resolve


def _default_tf(sid: str) -> str:
    return resolve(sid, cfg=_CFG).timeframe


FIELDS = [
    "strategy", "variant", "instrument", "window", "cost_bps",
    "n_trades", "trades_per_year",
    "total_return_pct", "buyhold_return_pct", "edge_vs_bh_pct",
    "win_rate_pct", "sharpe_weekly", "max_drawdown_pct", "exposure_pct",
    "error",
]


def _run_one(sid: str, variant: str, kw: dict, instrument: str,
             window: str, wcfg: dict, cost: float) -> dict:
    import importlib
    try:
        lib = importlib.import_module(f"strategy.{STRATEGIES[sid]}")
        resolved = resolve(sid, variant, cfg=_CFG)
        if kw != dict(VARIANTS[sid])[variant]:
            raise ValueError("cell parameters differ from the registered variant")
        tf = resolved.timeframe
        parquet = PARQUET_1H if tf == "1h" else PARQUET_5M
        res = lib.run(
            parquet=parquet,
            instrument=instrument,
            timeframe=tf,
            since=wcfg["since"],
            until=wcfg["until"],
            cost_bps=cost,
            entry_guard=resolved.entry_guard,
            **resolved.run_kwargs,
        )
        edge = res["total_return_pct"] - res["buyhold_return_pct"]
        return {
            "strategy": sid, "variant": variant, "instrument": instrument,
            "window": window, "cost_bps": cost,
            "n_trades": res["n_trades"],
            "trades_per_year": res["trades_per_year"],
            "total_return_pct": res["total_return_pct"],
            "buyhold_return_pct": res["buyhold_return_pct"],
            "edge_vs_bh_pct": round(edge, 2),
            "win_rate_pct": res["win_rate_pct"],
            "sharpe_weekly": res["sharpe_weekly"],
            "max_drawdown_pct": res["max_drawdown_pct"],
            "exposure_pct": res["exposure_pct"],
            "error": "",
        }
    except SystemExit as e:
        return {f: ("" if isinstance(f, str) else 0) for f in FIELDS} | {
            "strategy": sid, "variant": variant, "instrument": instrument,
            "window": window, "cost_bps": cost,
            "error": f"SystemExit: {e}",
        }
    except Exception as e:  # pragma: no cover - surfaced in the CSV
        return {f: ("" if isinstance(f, str) else 0) for f in FIELDS} | {
            "strategy": sid, "variant": variant, "instrument": instrument,
            "window": window, "cost_bps": cost,
            "error": f"{type(e).__name__}: {e}",
        }


def _run_costs(sid: str, variant: str, kw: dict, instrument: str,
               window: str, wcfg: dict) -> list[dict]:
    from strategy.strategy_lib import cache_bars
    with cache_bars():
        return [_run_one(sid, variant, kw, instrument, window, wcfg, cost)
                for cost in COST_TIERS]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--out", required=True, help="explicit destination for the new sweep CSV")
    ap.add_argument("--strategies", default=None,
                    help="comma-separated subset (e.g. s08,s09)")
    ap.add_argument("--variants", default=None,
                    help="comma-separated variant names to run (default: all declared variants)")
    args = ap.parse_args()

    sids = args.strategies.split(",") if args.strategies else list(STRATEGIES)
    varnames = args.variants.split(",") if args.variants else None
    if unknown := set(sids) - set(STRATEGIES):
        ap.error(f"unknown strategies: {sorted(unknown)}")

    tasks = []
    for sid in sids:
        for variant, kw in VARIANTS[sid]:
            if varnames and variant not in varnames:
                continue
            for instrument in INSTRUMENTS:
                for window, wcfg in WINDOWS.items():
                    tasks.append((sid, variant, kw, instrument, window, wcfg))
    if not tasks:
        ap.error("no declared variants matched the selection")

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"Running {len(tasks) * len(COST_TIERS)} cells with {args.workers} workers "
          f"({len(sids)} strategies; declared variants x instruments x windows x costs)...",
          file=sys.stderr)
    t0 = time.time()

    rows: list[dict] = []
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(_run_costs, *t): t for t in tasks}
        done = 0
        for fut in as_completed(futs):
            rows.extend(fut.result())
            done += 1
            if done % 100 == 0 or done == len(futs):
                print(f"  {done}/{len(futs)} done "
                      f"({time.time() - t0:.1f}s)", file=sys.stderr)
    rows.sort(key=lambda r: (r["strategy"], r["variant"], r["instrument"],
                             r["window"], r["cost_bps"]))

    with out_path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in FIELDS})
    print(f"Wrote {len(rows)} rows -> {out_path}", file=sys.stderr)

    # Console summary: best variant per strategy at 2 bps (edge vs buy-hold,
    # averaged over the 3 instruments, both windows combined).
    _print_summary(rows)
    if any(row.get("error") for row in rows):
        raise SystemExit("One or more sweep cells failed; see the error column.")


def _print_summary(rows: list[dict]) -> None:
    from collections import defaultdict
    agg: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for r in rows:
        if r["cost_bps"] != 2.0 or r.get("error"):
            continue
        agg[(r["strategy"], r["variant"])].append(r)

    print("\n=== Best variant per strategy (2 bps, mean edge vs buy-hold across 3 instruments) ===")
    print(f"{'sid':<6} {'variant':<22} {'mean_edge':>10} {'n_trades':>9} {'tpy':>7}")
    by_sid: dict[str, list[tuple[str, float, float, float]]] = defaultdict(list)
    for (sid, variant), cells in agg.items():
        mean_edge = sum(c["edge_vs_bh_pct"] for c in cells) / len(cells)
        mean_trades = sum(c["n_trades"] for c in cells) / len(cells)
        mean_tpy = sum(c["trades_per_year"] for c in cells) / len(cells)
        by_sid[sid].append((variant, mean_edge, mean_trades, mean_tpy))
    for sid in sorted(by_sid):
        ranked = sorted(by_sid[sid], key=lambda x: -x[1])
        for i, (v, me, mt, mtpy) in enumerate(ranked, 1):
            print(f"{sid:<6} {v:<22} {me:>+10.2f} {mt:>9.0f} {mtpy:>7.1f}")
        print()


if __name__ == "__main__":
    main()
