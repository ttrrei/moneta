"""Independent checks of labels, sampling, split purging and inference."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

from strategy.feature_research import (forward_labels, non_overlapping, fit_buckets, by_adjust,
                                        WeekBootstrap, interval, contrast_pvalue, summarize, analyze_frame)


def prices(n=1100):
    p = 100 + np.arange(n) * .01
    return pd.DataFrame({"time": pd.date_range("2020-01-01", periods=n, freq="5min", tz="UTC"),
                         "open": p, "high": p + .005, "low": p - .005, "close": p,
                         "n_bars": 5, "is_gap_bar": 0})


def settings():
    return {"seed": 7, "bootstrap_replicates": 99, "bootstrap_block_weeks": 4,
            "min_samples": 30, "min_active_weeks": 8}


def test_protocol_monte_carlo_resolution_can_resolve_an_isolated_by_discovery():
    cfg = yaml.safe_load((Path(__file__).resolve().parents[1] / "config/indicator_research.yml").read_text())
    m = ((len(cfg["continuous"]) + len(cfg["events"])) * len(cfg["instruments"])
         * len(cfg["timeframes"]) * len(cfg["horizons"]) * len(cfg["splits"]))
    minimum_p = 1 / (1 + cfg["statistics"]["bootstrap_replicates"])
    isolated_q = minimum_p * m * sum(1 / rank for rank in range(1, m + 1))
    assert isolated_q <= cfg["statistics"]["q_limit"]


def test_next_open_labels_and_excursions_match_hand_calculation():
    f = prices()
    t, h = 300, 6
    label = forward_labels(f, h, 300)
    opening, closing = f["open"].iloc[t + 1], f["open"].iloc[t + h + 1]
    assert label["return_bps"][t] == pytest.approx((closing / opening - 1) * 10000)
    assert label["mfe_bps"][t] == pytest.approx((max(f["high"].iloc[t + h], closing) / opening - 1) * 10000)
    assert label["mae_bps"][t] == pytest.approx((f["low"].iloc[t + 1] / opening - 1) * 10000)
    assert label["hours"][t] == .5
    # Exit-bar range is not part of the held interval.
    f.loc[t + h + 1, "high"] = 10000
    assert forward_labels(f, h, 300)["mfe_bps"][t] == label["mfe_bps"][t]
    assert np.isnan(label["return_bps"][-h - 1:]).all()


def test_excursions_include_adverse_gap_into_exit_fill():
    f = prices()
    f.loc[307, "open"] = 90.
    label = forward_labels(f, 6, 300)
    assert label["mae_bps"][300] == pytest.approx((90. / f["open"].iloc[301] - 1) * 10000)
    assert label["mae_bps"][300] <= label["return_bps"][300] <= label["mfe_bps"][300]


def test_labels_include_later_session_gaps_and_report_wall_time():
    f = prices()
    f.loc[304:, "time"] += pd.Timedelta(days=2)
    labels = forward_labels(f, 6, 300)
    assert labels["gap_path"][300] == 1
    assert labels["hours"][300] == 48.5
    assert np.isnan(labels["return_bps"][303])  # Entry itself cannot jump a gap.


def test_greedy_sampling_does_not_overlap_holdings():
    np.testing.assert_array_equal(non_overlapping([1, 2, 4, 7, 8, 13], 6), [1, 7, 13])


def test_bucket_thresholds_never_use_validation_values():
    x = np.arange(100, dtype=float)
    train = np.arange(100) < 40
    edges = fit_buckets(x, train, [.2, .4, .6, .8])
    x[40:] = -100000
    np.testing.assert_array_equal(edges, fit_buckets(x, train, [.2, .4, .6, .8]))
    assert len(fit_buckets(np.ones(100), train, [.2, .4, .6, .8])) == 0


def test_by_adjustment_matches_independent_three_test_example():
    np.testing.assert_allclose(by_adjust([.001, .1, 1.]), [.0055, .275, 1.])
    np.testing.assert_allclose(by_adjust([1., .001, .1]), [1., .0055, .275])
    with pytest.raises(ValueError):
        by_adjust([np.nan])


def test_paired_block_resampling_is_deterministic_and_includes_empty_weeks():
    b = WeekBootstrap("2020-01-01", "2020-07-01", settings(), "fixture")
    other = WeekBootstrap("2020-01-01", "2020-07-01", settings(), "fixture")
    np.testing.assert_array_equal(b.weights, other.weights)
    assert (b.weights.sum(axis=1) == b.weeks).all()
    times = pd.date_range("2020-01-01", "2020-06-30", freq="7D", tz="UTC").as_unit("ns").asi8
    boot, weeks = b.samples(np.ones(len(times)) * 7, times)
    np.testing.assert_allclose(boot, 7.)
    assert weeks == len(times)
    assert interval(boot) == (7., 7.)
    assert contrast_pvalue(0, np.zeros(99), True) == 1.
    assert contrast_pvalue(7, boot, True) == .01
    assert contrast_pvalue(7, boot, False) == 1.


def test_cost_scenarios_are_cash_pnl_per_entry_notional():
    b = WeekBootstrap("2020-01-01", "2020-07-01", settings(), "cash")
    times = pd.date_range("2020-01-01", "2020-06-30", freq="7D", tz="UTC").as_unit("ns").asi8
    n = len(times)
    labels = {key: np.ones(n) * value for key, value in
              {"return_bps": 100., "mfe_bps": 200., "mae_bps": -50., "hours": 1., "gap_path": 0., "partial_path": 0.}.items()}
    stats, _ = summarize(np.arange(n), labels, times, b)
    assert stats["long_net_c2_bps"] == pytest.approx(95.98)
    assert stats["short_net_c2_bps"] == pytest.approx(-104.02)
    assert stats["short_mfe_bps"] == 50.
    assert stats["short_mae_bps"] == -200.


def test_complete_planned_grid_and_labels_purged_at_split_boundaries():
    cfg = yaml.safe_load((Path(__file__).resolve().parents[1] / "config/indicator_research.yml").read_text())
    cfg["statistics"].update(bootstrap_replicates=19)
    cfg["horizons"] = [6, 24]
    cfg["continuous"] = {"bar_clv": "FR-01"}
    cfg["events"] = {"event": {"feature_id": "test", "direction": 1}}
    cfg["splits"] = {"train": {"start": "2020-01-01", "end": "2020-01-03"},
                      "validation_1": {"start": "2020-01-03", "end": "2020-01-04"},
                      "validation_2": {"start": "2020-01-04", "end": "2020-01-05"}}
    f = prices()
    features = pd.DataFrame({"bar_clv": np.sin(np.arange(len(f)) / 8), "event": 1.})
    first = analyze_frame(f, features, cfg, "EUR_USD", "5m")
    assert len(first[1]) == 12
    assert len({(r["feature"], r["split"], r["horizon"]) for r in first[1]}) == 12
    changed = features.copy()
    changed.loc[f["time"] >= pd.Timestamp("2020-01-03", tz="UTC"), "bar_clv"] = 10000
    assert first[3] == analyze_frame(f, changed, cfg, "EUR_USD", "5m")[3]
    # Every retained baseline label's exit precedes its own split end.
    labels = forward_labels(f, 24, 300)
    cutoff = pd.Timestamp("2020-01-03", tz="UTC").value
    close = (pd.DatetimeIndex(f["time"]) + pd.Timedelta(minutes=5)).as_unit("ns").asi8
    indices = np.flatnonzero(np.isfinite(labels["return_bps"]) & (close < cutoff)
                              & (labels["exit_ns"] < cutoff))
    assert len(indices) > 0
    assert (labels["exit_ns"][indices] < cutoff).all()
    for row in first[1]:
        start = pd.Timestamp(cfg["splits"][row["split"]]["start"], tz="UTC").value
        end = pd.Timestamp(cfg["splits"][row["split"]]["end"], tz="UTC").value
        expected = []
        first_row = next((i for i in range(258, len(f)) if start <= close[i] < end), 0)
        for i in range(first_row, len(f), row["horizon"]):
            exit_row = i + 1 + row["horizon"]
            if start <= close[i] < end and exit_row < len(f) and f["time"].iloc[exit_row].value < end:
                expected.append(i)
        assert row["baseline_n"] == len(expected)
