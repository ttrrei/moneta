"""6-iteration improvement harness for S-08 .. S-27.

For each of the new strategies, evaluate 6 improvement *iterations* (variants)
over the in-sample matrix: 3 instruments (EUR_USD / BTC_USD / XAU_USD) x 2
windows (full, last_12m) x 3 cost tiers (0 / 2 / 5 bps) = 18 cells.

All variants run on **in-sample data only** (``until <= 2025-07-31``) — no
OOS holdout is touched (the holdout is a one-shot gate reserved for the single
finalist under ``config/strategies.yml → oos.pass_criteria``).

Each row of the CSV records one cell:
  strategy, variant, instrument, window, cost_bps,
  n_trades, trades_per_year, total_return_pct, buyhold_return_pct,
  win_rate_pct, sharpe_weekly, max_drawdown_pct, exposure_pct.

Run from the repo root::

    venv/bin/python scripts/strategy_variants.py --workers 6
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

INSTRUMENTS = ["EUR_USD", "BTC_USD", "XAU_USD"]
COST_TIERS = [0.0, 2.0, 5.0]
WINDOWS = {
    "full": {"since": None, "until": "2025-07-31"},
    "last_12m": {"since": "2024-08-01", "until": "2025-07-31"},
}
PARQUET_5M = "data/ohlcv_5m_features/ohlcv_5m_features.parquet"
PARQUET_1H = "data/ohlcv_1h_features/ohlcv_1h_features.parquet"

STRATEGIES = {
    "s08": "strategy_cci_reversion_lib",
    "s09": "strategy_willr_lib",
    "s10": "strategy_stoch_lib",
    "s11": "strategy_macd_lib",
    "s12": "strategy_dual_velocity_lib",
    "s13": "strategy_psar_lib",
    "s14": "strategy_donchian_lib",
    "s15": "strategy_aroon_lib",
    "s16": "strategy_mfi_lib",
    "s17": "strategy_rsi_slow_lib",
    # batch 2
    "s18": "strategy_vwap_stretch_lib",
    "s19": "strategy_cmf_lib",
    "s20": "strategy_multiscale_lib",
    "s21": "strategy_squeeze_slow_lib",
    "s22": "strategy_er_lib",
    "s23": "strategy_macd_slow_lib",
    "s24": "strategy_atr_band_lib",
    "s25": "strategy_chop_lib",
    "s26": "strategy_spread_lib",
    "s27": "strategy_volmom_lib",
}

#: Per-strategy list of (variant_name, kwargs) — the 6 improvement iterations.
VARIANTS: dict[str, list[tuple[str, dict]]] = {
    "s08": [
        ("base", {}),
        ("ema_gate", {"ema_gate": True}),
        ("slower", {"enter_below": 150.0, "exit_above": 250.0}),
        ("1h", {"timeframe": "1h"}),
        ("entry_guard", {"entry_guard": True}),
        ("band_wide", {"enter_below": 200.0, "exit_above": 300.0}),
    ],
    "s09": [
        ("base", {}),
        ("ema_gate", {"ema_gate": True}),
        ("slower", {"enter_below": -85.0, "exit_above": -30.0}),
        ("1h", {"timeframe": "1h"}),
        ("entry_guard", {"entry_guard": True}),
        ("cooldown_24", {"cooldown": 24}),
    ],
    "s10": [
        ("base", {}),
        ("ema_gate", {"ema_gate": True}),
        ("slower", {"k_below": 20.0}),
        ("1h", {"timeframe": "1h"}),
        ("entry_guard", {"entry_guard": True}),
        ("band_wide", {"k_below": 40.0}),
    ],
    "s11": [
        ("base", {}),
        ("ema_gate", {"ema_gate": True}),
        ("atr_strict", {"atr_min": 0.15}),
        ("1h", {"timeframe": "1h"}),
        ("entry_guard", {"entry_guard": True}),
        ("atr_loose", {"atr_min": 0.02}),
    ],
    "s12": [
        ("base", {}),
        ("ema_gate", {"ema_gate": True}),
        ("slower_lag", {"slope_lag": 120}),
        ("1h", {"timeframe": "1h"}),
        ("entry_guard", {"entry_guard": True}),
        ("fast_lag", {"slope_lag": 6}),
    ],
    "s13": [
        ("base", {}),
        ("hysteresis", {"up_th": 0.9}),
        ("hysteresis_strict", {"up_th": 0.95}),
        ("1h", {"timeframe": "1h"}),
        ("entry_guard", {"entry_guard": True}),
        ("near_flat", {"up_th": 0.2}),
    ],
    "s14": [
        ("base", {}),
        ("hysteresis", {"th": 0.5}),
        ("hysteresis_strict", {"th": 0.8}),
        ("1h", {"timeframe": "1h"}),
        ("entry_guard", {"entry_guard": True}),
        ("band_tight", {"th": 0.2}),
    ],
    "s15": [
        ("base", {}),
        ("ema_gate", {"ema_gate": True}),
        ("slower", {"up_at": 85.0, "up_exit": 85.0, "down_below": 20.0}),
        ("1h", {"timeframe": "1h"}),
        ("entry_guard", {"entry_guard": True}),
        ("band_wide", {"up_at": 50.0, "up_exit": 50.0, "down_below": 50.0}),
    ],
    "s16": [
        ("base", {}),
        ("ema_gate", {"ema_gate": True}),
        ("slower", {"enter_below": 10.0, "exit_above": 60.0}),
        ("1h", {"timeframe": "1h"}),
        ("entry_guard", {"entry_guard": True}),
        ("band_wide", {"enter_below": 30.0, "exit_above": 70.0}),
    ],
    "s17": [
        ("base", {}),
        ("st_gate", {"st_gate": True}),
        ("adx_gate", {"adx_gate": True, "adx_at": 20.0}),
        ("both_gates", {"st_gate": True, "adx_gate": True, "adx_at": 20.0}),
        ("slower", {"enter_below": 20.0, "exit_above": 45.0}),
        ("entry_guard", {"entry_guard": True}),
    ],
    # ---- batch 2 (S-18 .. S-27) ----
    "s18": [
        ("base", {}),
        ("ema_gate", {"ema_gate": True}),
        ("looser", {"k": 0.5, "k_exit": 0.0}),
        ("tight_exit", {"k": 0.25, "k_exit": 0.1}),
        ("1h", {"timeframe": "1h"}),
        ("entry_guard", {"entry_guard": True}),
    ],
    "s19": [
        ("base", {}),
        ("ema_gate", {"ema_gate": True}),
        ("looser", {"k": 0.10}),
        ("tighter", {"k": 0.02}),
        ("1h", {"timeframe": "1h"}),
        ("entry_guard", {"entry_guard": True}),
    ],
    "s20": [
        ("base", {}),
        ("gate_120_3", {"gate_cols": ("st_dir_120_3",)}),
        ("dual_gate", {"gate_cols": ("st_dir_120_2", "st_dir_120_3")}),
        ("h1_align", {"gate_cols": ("st_dir_120_2", "h1_st_dir_120_3")}),
        ("1h", {"timeframe": "1h"}),
        ("entry_guard", {"entry_guard": True}),
    ],
    "s21": [
        ("base", {}),
        ("ema_gate", {"ema_gate": True}),
        ("onset_only", {"onset_only": True}),
        ("onset_ema", {"onset_only": True, "ema_gate": True}),
        ("1h", {"timeframe": "1h"}),
        ("entry_guard", {"entry_guard": True}),
    ],
    "s22": [
        ("base", {}),
        ("lower_k", {"k": 0.20}),
        ("higher_k", {"k": 0.40}),
        ("1h", {"timeframe": "1h"}),
        ("entry_guard", {"entry_guard": True}),
        ("slower", {"k": 0.50}),
    ],
    "s23": [
        ("base", {}),
        ("pos_th", {"th": 0.1, "th_exit": 0.0}),
        ("hysteresis", {"th": 0.0, "th_exit": -0.1}),
        ("1h", {"timeframe": "1h"}),
        ("entry_guard", {"entry_guard": True}),
        ("tight", {"th": 0.2, "th_exit": 0.0}),
    ],
    "s24": [
        ("base", {}),
        ("wider", {"k": 1.5, "k_exit": 0.75}),
        ("narrower", {"k": 0.5, "k_exit": 0.25}),
        ("1h", {"timeframe": "1h"}),
        ("entry_guard", {"entry_guard": True}),
        ("slower_exit", {"k": 1.0, "k_exit": 0.25}),
    ],
    "s25": [
        ("base", {}),
        ("chop_higher", {"chop_at": 65.0}),
        ("chop_lower", {"chop_at": 55.0}),
        ("wider_stretch", {"k": 1.5}),
        ("1h", {"timeframe": "1h"}),
        ("entry_guard", {"entry_guard": True}),
    ],
    "s26": [
        ("base", {}),
        ("wider", {"th": 1.0, "th_exit": 0.0}),
        ("narrower", {"th": 0.25, "th_exit": 0.0}),
        ("hysteresis", {"th": 0.5, "th_exit": 0.2}),
        ("1h", {"timeframe": "1h"}),
        ("entry_guard", {"entry_guard": True}),
    ],
    "s27": [
        ("base", {}),
        ("vol_stronger", {"vmin": 1.5}),
        ("vol_looser", {"vmin": 0.8}),
        ("1h", {"timeframe": "1h"}),
        ("entry_guard", {"entry_guard": True}),
        ("vol_2x", {"vmin": 2.0}),
    ],
}

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
    lib = importlib.import_module(f"strategy.{STRATEGIES[sid]}")
    tf = kw.get("timeframe", "5m" if sid != "s17" else "1h")
    parquet = PARQUET_1H if tf == "1h" else PARQUET_5M
    try:
        res = lib.run(
            parquet=parquet,
            instrument=instrument,
            timeframe=tf,
            since=wcfg["since"],
            until=wcfg["until"],
            cost_bps=cost,
            entry_guard=kw.get("entry_guard", False),
            **{k: v for k, v in kw.items()
               if k not in ("timeframe", "entry_guard")},
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


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--out", default="strategy/results/iterations_2026-10-30.csv")
    ap.add_argument("--strategies", default=None,
                    help="comma-separated subset (e.g. s08,s09)")
    ap.add_argument("--variants", default=None,
                    help="comma-separated variant names to run (default: all 6)")
    args = ap.parse_args()

    sids = args.strategies.split(",") if args.strategies else list(STRATEGIES)
    varnames = args.variants.split(",") if args.variants else None

    tasks = []
    for sid in sids:
        for variant, kw in VARIANTS[sid]:
            if varnames and variant not in varnames:
                continue
            for instrument in INSTRUMENTS:
                for window, wcfg in WINDOWS.items():
                    for cost in COST_TIERS:
                        tasks.append((sid, variant, kw, instrument, window,
                                     wcfg, cost))

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"Running {len(tasks)} cells with {args.workers} workers "
          f"(10 strategies x 6 variants x 3 instruments x 2 windows x 3 costs)...",
          file=sys.stderr)
    t0 = time.time()

    rows: list[dict] = []
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(_run_one, *t): t for t in tasks}
        done = 0
        for fut in as_completed(futs):
            rows.append(fut.result())
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
