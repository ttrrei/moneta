"""Run the fixed P1 indicator study on gated development data only.

Writes a protocol/source snapshot BEFORE reading outcomes. Existing Gold
tables, strategy results, statuses and the holdout ledger are read-only.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import duckdb
import numpy as np
import pandas as pd
import yaml

from pipeline.research_features import compute_research_features
from strategy.feature_research import analyze_frame, by_adjust
from strategy.oos_token import assert_access, holdout_start_date
from strategy.strategy_lib import load_bars, TIMEFRAME_PARQUET

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/indicator_research.yml"
SOURCE_FILES = ("config/indicator_research.yml", "library/market_structure.py",
                "pipeline/research_features.py", "strategy/feature_research.py",
                "scripts/research_indicators.py", "strategy/strategy_lib.py", "strategy/oos_token.py",
                "pipeline/indicators.py", "library/supertrend.py", "library/psar.py", "requirements.lock")
INPUT_FEATURES = ("instrument", "high", "low", "n_bars", "is_partial", "atr_24",
                  "dc_upper_24", "dc_lower_24", "bar_upper_wick_ratio", "bar_lower_wick_ratio",
                  "bar_clv", "vol_ratio_6_24", "vol_ratio_12_60", "vol_ratio_24_120")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def clean(value):
    if isinstance(value, (float, np.floating)) and not math.isfinite(value):
        return ""
    return value.item() if isinstance(value, np.generic) else value


def write_csv(path, rows):
    if not rows:
        raise ValueError(f"no records for {path}")
    with Path(path).open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: clean(value) for key, value in row.items()})


def source_inventory():
    # Discover producer names by exercising the existing named feature
    # groups on synthetic bars; prefix guesses misclassify e.g. `tr`/`natr`.
    from pipeline.indicators import compute_instrument_features, FEATURE_GROUPS, N_GRID, PAIRS
    n = 800
    c = 100 + np.sin(np.arange(n) / 12.)
    sample = pd.DataFrame({"instrument": "EUR_USD", "time": pd.date_range("2020-01-01", periods=n, freq="5min", tz="UTC"),
                           "open": c, "high": c + 1, "low": c - 1, "close": c, "volume": 10, "n_bars": 5})
    existing = compute_instrument_features(sample, 300)
    aux = {name: existing[name].to_numpy() for name in existing}
    aux["atr_norm"] = aux["atr_24"]
    producers = {}
    arrays = [sample[name].to_numpy(float) for name in ("open", "high", "low", "close", "volume")]
    for group in FEATURE_GROUPS:
        for name in group().compute(*arrays, N_GRID, PAIRS, aux):
            producers[name] = group.__name__
    rows = []
    conn = duckdb.connect()
    try:
        for tf, path in TIMEFRAME_PARQUET.items():
            for name, dtype, *_ in conn.execute("DESCRIBE SELECT * FROM read_parquet(?)", [str(ROOT / path)]).fetchall():
                if name in ("instrument", "time", "open", "high", "low", "close", "volume", "n_bars"):
                    source = "OHLCV_COLS"
                elif name.startswith("h1_"):
                    source = "asof_join_h1_features"
                elif name.startswith("is_"):
                    source = "compute_instrument_features:quality_flags"
                else:
                    source = producers[name]
                rows.append({"timeframe": tf, "column": name, "dtype": dtype,
                             "formula_source": f"pipeline/indicators.py:{source}",
                             "definition_reference": "docs/indicators.md"})
    finally:
        conn.close()
    return rows


def decisions(comparisons, cfg):
    rows = []
    for name in list(cfg["continuous"]) + list(cfg["events"]):
        selected = [r for r in comparisons if r["feature"] == name]
        supported_settings = replicated_settings = 0
        for tf in cfg["timeframes"]:
            for h in cfg["horizons"]:
                supported_assets = replicated_assets = 0
                for instrument in cfg["instruments"]:
                    matches = {r["split"]: r for r in selected if r["instrument"] == instrument
                               and r["timeframe"] == tf and r["horizon"] == h}
                    if set(matches) != set(cfg["splits"]):
                        raise ValueError("missing planned comparison")
                    if all(r["supported"] for r in matches.values()):
                        supported_assets += 1
                        orientation = 1 if name in cfg["events"] or matches["train"]["effect_bps"] >= 0 else -1
                        stable = all((r["ci_low_bps"] if orientation == 1 else -r["ci_high_bps"]) > 0
                                     and r["q_value"] <= cfg["statistics"]["q_limit"]
                                     for split, r in matches.items() if split != "train")
                        if stable:
                            replicated_assets += 1
                supported_settings += supported_assets >= 2
                replicated_settings += replicated_assets >= 2
        decision = "keep" if replicated_settings else "reject" if supported_settings else "revise"
        reason = ("Replicated conditional association; retain for further research, no strategy claim."
                  if decision == "keep" else
                  "Adequate coverage but no preregistered cross-asset/time replication after global adjustment."
                  if decision == "reject" else
                  "Insufficient independent support in both validation slices; revise study design before retesting.")
        rows.append({"feature": name, "feature_id": cfg["continuous"].get(name) or cfg["events"][name]["feature_id"],
                     "decision": decision, "supported_tf_horizon_settings": supported_settings,
                     "replicated_tf_horizon_settings": replicated_settings, "reason": reason})
    return rows


def run(out: Path, data_out: Path):
    cfg = yaml.safe_load(CONFIG.read_text())
    holdout = pd.Timestamp(holdout_start_date(), tz="UTC")
    splits = list(cfg["splits"].values())
    for index, spec in enumerate(splits):
        start, end = pd.Timestamp(spec["start"], tz="UTC"), pd.Timestamp(spec["end"], tz="UTC")
        if start >= end or end > holdout or (index and start < pd.Timestamp(splits[index - 1]["end"], tz="UTC")):
            raise ValueError("invalid, overlapping or protected research split")
    if out.exists() or data_out.exists():
        raise ValueError("refusing to overwrite an existing research attempt")
    out.mkdir(parents=True)
    data_out.mkdir(parents=True)
    ledger = ROOT / "strategy/oos_ledger.json"
    ledger_before = sha(ledger)
    source_hashes = {path: sha(ROOT / path) for path in SOURCE_FILES}
    planned = ((len(cfg["continuous"]) + len(cfg["events"])) * len(cfg["instruments"])
               * len(cfg["timeframes"]) * len(cfg["horizons"]) * len(cfg["splits"]))
    manifest = {"research_id": cfg["research_id"], "status": "started", "protocol_sha256": sha(CONFIG),
                "source_sha256": source_hashes, "planned_comparisons": planned,
                "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
                "dirty": bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True)),
                "registration": "local protocol/source snapshot before outcomes; not externally preregistered",
                "started_at_utc": datetime.now(timezone.utc).isoformat(), "ledger_sha256": ledger_before,
                "python": platform.python_version(), "numpy": np.__version__, "pandas": pd.__version__}
    (out / "protocol.yml").write_text(CONFIG.read_text())
    (out / "manifest.yml").write_text(yaml.safe_dump(manifest, sort_keys=True))
    conditional, comparisons, distributions, fitted, inputs = [], [], [], [], []
    try:
        write_csv(out / "existing_feature_inventory.csv", source_inventory())
        # Explicit instant: the holdout boundary is exclusive, so the latest
        # development bound is represented by the preceding inclusive instant.
        until = (holdout - pd.Timedelta(microseconds=1)).isoformat()
        assert_access(until)
        for tf, seconds in cfg["timeframes"].items():
            for instrument in cfg["instruments"]:
                start = datetime.now(timezone.utc)
                frame = load_bars(str(ROOT / TIMEFRAME_PARQUET[tf]), instrument,
                                  INPUT_FEATURES, since=cfg["splits"]["train"]["start"], until=until)
                if frame.empty or (pd.DatetimeIndex(frame["time"]) >= holdout).any():
                    raise ValueError("empty or protected source rows")
                price = frame[["open", "high", "low", "close"]].to_numpy(float)
                if not np.isfinite(price).all() or (price <= 0).any() \
                        or (frame["high"] < frame[["open", "close"]].max(axis=1)).any() \
                        or (frame["low"] > frame[["open", "close"]].min(axis=1)).any():
                    raise ValueError("invalid OHLC input")
                digest = hashlib.sha256(str(list(zip(frame.columns, frame.dtypes.astype(str)))).encode())
                digest.update(pd.util.hash_pandas_object(frame, index=False).to_numpy().tobytes())
                extra = compute_research_features(frame, seconds, **cfg["parameters"])
                if set(frame.columns) & set(extra.columns):
                    raise ValueError("research feature collides with existing column")
                enriched = pd.concat([frame, extra], axis=1)
                target = data_out / f"{instrument}_{tf}.parquet"
                enriched.to_parquet(target, index=False)
                result = analyze_frame(frame, enriched, cfg, instrument, tf)
                for destination, records in zip((conditional, comparisons, distributions, fitted), result):
                    destination.extend(records)
                inputs.append({"instrument": instrument, "timeframe": tf, "rows": len(frame),
                               "start": str(frame["time"].iloc[0]), "end": str(frame["time"].iloc[-1]),
                               "development_frame_sha256": digest.hexdigest(),
                               "derived_file": str(target), "derived_sha256": sha(target),
                               "seconds": (datetime.now(timezone.utc) - start).total_seconds()})
                print(f"{instrument}/{tf}: {len(frame)} source rows; {len(comparisons)}/{planned} comparisons", flush=True)
        if len(comparisons) != planned:
            raise ValueError("incomplete registered comparison grid")
        qvalues = by_adjust([r["p_value"] for r in comparisons])
        for row, q in zip(comparisons, qvalues):
            row["q_value"] = q
        write_csv(out / "conditional_returns.csv", conditional)
        write_csv(out / "comparisons.csv", comparisons)
        write_csv(out / "distributions.csv", distributions)
        write_csv(out / "decisions.csv", decisions(comparisons, cfg))
        (out / "training_buckets.yml").write_text(yaml.safe_dump(fitted, sort_keys=True))
        for path, digest in source_hashes.items():
            if sha(ROOT / path) != digest:
                raise ValueError(f"research implementation changed during run: {path}")
        if sha(ledger) != ledger_before:
            raise ValueError("holdout ledger changed during research")
        manifest.update(status="completed", completed_comparisons=len(comparisons), inputs=inputs,
                        finished_at_utc=datetime.now(timezone.utc).isoformat(),
                        artifacts={path.name: sha(path) for path in sorted(out.iterdir()) if path.name != "manifest.yml"})
        (out / "manifest.yml").write_text(yaml.safe_dump(manifest, sort_keys=True))
        return manifest
    except BaseException as exc:
        manifest.update(status="failed", error=repr(exc), completed_comparisons=len(comparisons))
        (out / "manifest.yml").write_text(yaml.safe_dump(manifest, sort_keys=True))
        raise


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--data-out", required=True, type=Path)
    args = ap.parse_args()
    run(args.out, args.data_out)


if __name__ == "__main__":
    main()
