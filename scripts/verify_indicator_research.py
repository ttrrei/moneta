"""Audit an indicator study, with independent label/formula checks and replay.

Reads only the run's development-only derived files; never queries protected
Gold rows. A failed assertion exits nonzero and does not write a passing audit.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import pandas as pd
import yaml

from pipeline.research_features import compute_research_features
from strategy.feature_research import forward_labels
from strategy.oos_token import holdout_start_date

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify(run, replay=None):
    manifest = yaml.safe_load((run / "manifest.yml").read_text())
    cfg = yaml.safe_load((run / "protocol.yml").read_text())
    assert manifest["status"] == "completed"
    assert digest(run / "protocol.yml") == manifest["protocol_sha256"]
    for name, expected in manifest["artifacts"].items():
        assert digest(run / name) == expected, name
    for name, expected in manifest["source_sha256"].items():
        frozen = run / "source_snapshot" / name
        assert digest(frozen if frozen.exists() else ROOT / name) == expected, f"source drift: {name}"
    # Real-data checks below execute these modules from the working tree.
    for name in ("pipeline/research_features.py", "library/market_structure.py", "strategy/feature_research.py"):
        assert digest(ROOT / name) == manifest["source_sha256"][name], f"audit implementation drift: {name}"
    assert digest(ROOT / "strategy/oos_ledger.json") == manifest["ledger_sha256"]
    c = pd.read_csv(run / "comparisons.csv")
    s = pd.read_csv(run / "conditional_returns.csv")
    dist = pd.read_csv(run / "distributions.csv")
    keys = ["feature", "instrument", "timeframe", "horizon", "split"]
    expected = set(itertools.product(list(cfg["continuous"]) + list(cfg["events"]),
                                    cfg["instruments"], cfg["timeframes"], cfg["horizons"], cfg["splits"]))
    assert not c.duplicated(keys).any()
    assert set(c[keys].itertuples(index=False, name=None)) == expected
    assert len(c) == manifest["planned_comparisons"] == manifest["completed_comparisons"]
    assert (c.loc[~c.supported, "p_value"] == 1).all()
    assert not np.isinf(c.select_dtypes(include="number").to_numpy()).any()
    assert not np.isinf(s.select_dtypes(include="number").to_numpy()).any()
    # Independent BY implementation: minimum over every later sorted rank.
    ordered = sorted(enumerate(c.p_value), key=lambda item: item[1])
    m = len(ordered)
    harmonic = sum(1 / rank for rank in range(1, m + 1))
    q = np.ones(m)
    tail = 1.
    for rank in range(m, 0, -1):
        original, value = ordered[rank - 1]
        tail = min(tail, value * m * harmonic / rank)
        q[original] = tail
    np.testing.assert_allclose(c.q_value, q, rtol=1e-12)
    for cost in cfg["cost_bps_one_way"]:
        np.testing.assert_allclose(s[f"long_net_c{cost}_bps"], s.mean_bps * (1 - cost / 10000) - 2 * cost,
                                   equal_nan=True, atol=1e-10)
        np.testing.assert_allclose(s[f"short_net_c{cost}_bps"], -s.mean_bps * (1 + cost / 10000) - 2 * cost,
                                   equal_nan=True, atol=1e-10)
    populated = s.n > 0
    assert (s.loc[populated, "mean_mae_bps"] <= s.loc[populated, "mean_bps"] + 1e-9).all()
    assert (s.loc[populated, "mean_mfe_bps"] >= s.loc[populated, "mean_bps"] - 1e-9).all()
    buckets = yaml.safe_load((run / "training_buckets.yml").read_text())
    checked_labels = checked_percentiles = 0
    data_checks = []
    holdout = pd.Timestamp(holdout_start_date(), tz="UTC")
    for item in manifest["inputs"]:
        path = Path(item["derived_file"])
        if not path.is_absolute():
            path = ROOT / path
        assert digest(path) == item["derived_sha256"]
        f = pd.read_parquet(path)
        tf, instrument = item["timeframe"], item["instrument"]
        seconds = cfg["timeframes"][tf]
        time = pd.DatetimeIndex(f.time).as_unit("ns")
        assert len(f) == item["rows"] and f.instrument.unique().tolist() == [instrument]
        assert time.is_monotonic_increasing and not time.has_duplicates and (time < holdout).all()
        assert not np.isinf(f.select_dtypes(include="number").to_numpy()).any()
        close = time + pd.Timedelta(seconds=seconds)
        # Independent training cohort and percentile fit, including quality exclusions.
        train = ((close >= pd.Timestamp(cfg["splits"]["train"]["start"], tz="UTC"))
                 & (close < pd.Timestamp(cfg["splits"]["train"]["end"], tz="UTC"))
                 & (np.arange(len(f)) >= 258) & (f.n_bars.to_numpy() == seconds // 60)
                 & (f.is_gap_bar.to_numpy() == 0))
        for record in buckets:
            if record["instrument"] != instrument or record["timeframe"] != tf:
                continue
            available = f.loc[train, record["feature"]].dropna().to_numpy()
            expected_edges = np.unique(np.quantile(available, [.2, .4, .6, .8])) if np.unique(available).size > 1 else []
            np.testing.assert_allclose(record["cutpoints"], expected_edges)
        for side in ("high", "low"):
            event = f[f"swing_{side}_confirmed"] == 1
            pd.testing.assert_series_equal(f.loc[event, f"swing_{side}_confirmed_time"].reset_index(drop=True),
                                           pd.Series(close[event]).reset_index(drop=True), check_names=False)
            pivots = f.loc[event, f"swing_{side}_pivot_index"].to_numpy(int)
            assert (np.flatnonzero(event) - pivots == cfg["parameters"]["swing_right"]).all()
        for window in (60, 120):
            a = f.atr_24.to_numpy(float)
            for t in np.linspace(258, len(f) - 1, 100, dtype=int):
                reference = np.mean(a[t - window + 1:t + 1] <= a[t])
                assert np.isclose(f[f"atr_percentile_{window}"].iloc[t], reference)
                checked_percentiles += 1
        # Causality and serialization parity on real source prefixes.
        source = f.iloc[:2048]
        extra = compute_research_features(source, seconds, **cfg["parameters"])
        pd.testing.assert_frame_equal(extra, source[extra.columns])
        prefix = compute_research_features(source.iloc[:1024], seconds, **cfg["parameters"])
        pd.testing.assert_frame_equal(extra.iloc[:1024], prefix)
        # Independent direct indexing of forward returns and excursion boundaries.
        for h in cfg["horizons"]:
            labels = forward_labels(f, h, seconds)
            eligible = np.flatnonzero(np.isfinite(labels["return_bps"]))
            for t in eligible[np.linspace(0, len(eligible) - 1, 100, dtype=int)]:
                entry = f.open.iloc[t + 1]
                exit_price = f.open.iloc[t + h + 1]
                hi = max(f.high.iloc[t + 1:t + h + 1].max(), exit_price)
                lo = min(f.low.iloc[t + 1:t + h + 1].min(), exit_price)
                assert np.isclose(labels["return_bps"][t], (exit_price / entry - 1) * 10000)
                assert np.isclose(labels["mfe_bps"][t], (hi / entry - 1) * 10000)
                assert np.isclose(labels["mae_bps"][t], (lo / entry - 1) * 10000)
                checked_labels += 1
        data_checks.append({"instrument": instrument, "timeframe": tf, "rows": len(f),
                            "last_source_bar": str(time[-1]), "checks": "passed"})
    replay_checks = {}
    if replay:
        other = yaml.safe_load((replay / "manifest.yml").read_text())
        assert other["status"] == "completed" and other["source_sha256"] == manifest["source_sha256"]
        assert other["protocol_sha256"] == manifest["protocol_sha256"]
        for name, expected_hash in manifest["artifacts"].items():
            assert digest(replay / name) == expected_hash, f"replay differs: {name}"
            replay_checks[name] = "byte-identical"
        assert len(other["inputs"]) == len(manifest["inputs"])
        for first, second in zip(manifest["inputs"], other["inputs"]):
            for name in ("instrument", "timeframe", "rows", "development_frame_sha256", "derived_sha256"):
                assert first[name] == second[name], f"replay input differs: {name}"
            replay_checks[f"{first['instrument']}_{first['timeframe']}.parquet"] = "byte-identical"
        for name, expected_hash in manifest["source_sha256"].items():
            assert digest(replay / "source_snapshot" / name) == expected_hash
    return {"status": "passed", "research_id": cfg["research_id"],
            "verification_script_sha256": digest(Path(__file__)),
            "comparisons": len(c), "conditional_rows": len(s), "distribution_rows": len(dist),
            "supported_comparisons": int(c.supported.sum()), "minimum_q": float(c.q_value.min()),
            "significant_global_q_0_1": int((c.q_value <= .1).sum()),
            "direct_forward_label_checks": checked_labels, "independent_atr_rank_checks": checked_percentiles,
            "data_checks": data_checks, "replay": replay_checks,
            "ledger_sha256": manifest["ledger_sha256"], "run_manifest_sha256": digest(run / "manifest.yml")}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", required=True, type=Path)
    parser.add_argument("--replay", type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    if args.out.exists():
        raise ValueError("refusing to overwrite an audit record")
    result = verify(args.run, args.replay)
    args.out.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
