"""Six P1 quality gates, with hand examples and independent reference formulas."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from library.market_structure import confirmed_structure, frozen_events
from pipeline.research_features import compute_research_features


def frame(n=700):
    rng = np.random.default_rng(73)
    close = 100 + rng.normal(0, .5, n).cumsum()
    opening = np.r_[close[0], close[:-1]]
    high = np.maximum(opening, close) + rng.uniform(.1, .5, n)
    low = np.minimum(opening, close) - rng.uniform(.1, .5, n)
    return pd.DataFrame({"instrument": "EUR_USD", "time": pd.date_range("2020-01-01", periods=n, freq="5min", tz="UTC"),
                         "open": opening, "high": high, "low": low, "close": close, "n_bars": 5,
                         "atr_24": rng.uniform(.5, 2., n),
                         "dc_upper_24": pd.Series(high).rolling(24).max(),
                         "dc_lower_24": pd.Series(low).rolling(24).min()})


def structure(h, l=None, c=None, **kwargs):
    h = np.asarray(h, dtype=float)
    n = len(h)
    return confirmed_structure(h, np.ones(n) if l is None else l,
                               np.ones(n) * 1.5 if c is None else c,
                               np.ones(n), np.ones(n, bool), np.zeros(n, bool), **kwargs)


def test_pivot_is_visible_only_at_confirmation_and_tie_chooses_leftmost():
    high = np.ones(35) * 2
    high[6] = high[8] = 10
    result = structure(high)
    assert np.isnan(result["swing_high_confirmed"][:12]).all()
    assert result["swing_high_confirmed"][12] == 1
    assert result["swing_high_pivot_index"][12] == 6
    assert result["swing_high_confirmed"][14] == 0
    assert np.isnan(result["last_confirmed_swing_high"][:12]).all()


def test_confirmed_hh_hl_and_prior_level_break():
    h = np.ones(55) * 2
    l = np.ones(55)
    c = np.ones(55) * 1.5
    h[6], h[24] = 10, 12
    l[15], l[33] = .5, .8
    c[42], h[42] = 13, 14
    out = structure(h, l, c)
    assert np.isnan(out["structure_hh"][12])
    assert out["structure_hh"][30] == 1
    assert out["structure_hl"][39] == 1
    assert out["structure_break_up"][42] == 1
    assert out["structure_reference_high"][42] == 12
    assert out["structure_break_strength_up"][42] == 1


def event_inputs(close):
    c = np.asarray(close, dtype=float)
    n = len(c)
    return dict(high=c + .2, low=c - .2, close=c, atr=np.ones(n), prior_upper=np.ones(n) * 10,
                prior_lower=np.ones(n) * 5, valid=np.ones(n, bool), reset=np.zeros(n, bool),
                structure={"structure_break_up": np.zeros(n), "structure_break_down": np.zeros(n),
                           "structure_reference_high": np.ones(n) * 10,
                           "structure_reference_low": np.ones(n) * 5})


def test_failed_breakout_freezes_original_boundaries_and_confirms_once():
    inputs = event_inputs([9, 11, 12, 9, 9, 9])
    inputs["prior_upper"][2:] = 20
    out = frozen_events(**inputs)
    assert out["failed_breakout_up"][3] == 1
    assert out["range_frozen_upper"][3] == 10
    assert out["range_breakout_index"][3] == 1
    assert out["failed_breakout_age_bars"][3] == 2
    assert out["failed_breakout_excursion_atr"][3] == pytest.approx(2.2)
    assert np.nansum(out["failed_breakout_up"]) == 1


def test_late_range_reentry_is_not_a_failed_breakout_in_the_registered_window():
    out = frozen_events(**event_inputs([9, 11, 11, 11, 11, 11, 11, 11, 9]))
    assert out["range_reentry_from_above"][8] == 1
    assert out["failed_breakout_up"][8] == 0
    assert np.isnan(out["failed_breakout_age_bars"][8])


def test_retest_is_later_than_breakout_and_uses_frozen_atr_once():
    inputs = event_inputs([9, 11, 11, 11])
    inputs["structure"]["structure_break_up"][1] = 1
    inputs["low"][1:] = 10.1
    inputs["atr"][2:] = 100
    out = frozen_events(**inputs)
    assert out["breakout_retest_up"][1] == 0
    assert out["breakout_retest_up"][2] == 1
    assert out["breakout_retest_distance_atr"][2] == pytest.approx(.1)
    assert out["retest_breakout_index"][2] == 1
    assert out["breakout_retest_up"][3] == 0


def test_gap_and_invalid_bar_reset_events_and_pivots():
    inputs = event_inputs([9, 11, 11, 9, 9])
    inputs["reset"][2] = True
    out = frozen_events(**inputs)
    assert np.nansum(out["range_reentry_from_above"]) == 0
    f = frame()
    f.loc[300:, "time"] += pd.Timedelta(days=2)
    out = compute_research_features(f, 300)
    assert out["last_confirmed_swing_high"].iloc[300:313].isna().all()


def test_zero_atr_and_flat_prices_never_produce_infinity():
    f = frame()
    f[["open", "high", "low", "close", "dc_upper_24", "dc_lower_24"]] = 10.
    f["atr_24"] = 0.
    out = compute_research_features(f, 300)
    assert not np.isinf(out.select_dtypes(include="number").to_numpy()).any()
    assert out["atr_percentile_60"].iloc[59] == 1.
    assert out["structure_break_strength_up"].isna().all()


@pytest.mark.parametrize("cut", [6, 13, 80, 301, 550])
def test_every_output_has_prefix_invariance_and_future_perturbation(cut):
    f = frame()
    full = compute_research_features(f, 300)
    prefix = compute_research_features(f.iloc[:cut], 300)
    pd.testing.assert_frame_equal(full.iloc[:cut], prefix)
    changed = f.copy()
    numeric = changed.select_dtypes(include="number").columns.difference(["n_bars"])
    changed.loc[cut:, numeric] *= 1.5
    changed.loc[cut:, "n_bars"] = 0
    future = compute_research_features(changed, 300)
    pd.testing.assert_frame_equal(full.iloc[:cut], future.iloc[:cut])


def test_finite_context_converges_after_a_later_start():
    f = frame(1200)
    full = compute_research_features(f, 300)
    later = compute_research_features(f.iloc[200:], 300)
    # Index auxiliaries are local row offsets; timestamps preserve identity.
    names = [name for name in full if not name.endswith("_index")]
    pd.testing.assert_frame_equal(full.loc[600:, names], later.loc[600:, names])


def test_percentile_matches_independent_empirical_cdf_including_ties():
    f = frame()
    f["atr_24"] = np.arange(len(f)) % 7
    out = compute_research_features(f, 300)
    for n in (60, 120):
        reference = np.full(len(f), np.nan)
        a = f["atr_24"].to_numpy()
        for t in range(n - 1, len(f)):
            reference[t] = np.mean(a[t - n + 1:t + 1] <= a[t])
        np.testing.assert_allclose(out[f"atr_percentile_{n}"], reference, equal_nan=True)


def test_confirmed_swing_indices_match_a_brute_force_oracle():
    f = frame(250)
    out = compute_research_features(f, 300)
    for side, comparison in (("high", 1), ("low", -1)):
        a = f[side].to_numpy() * comparison
        oracle = np.full(len(a), np.nan)
        for t in range(12, len(a)):
            p = t - 6
            oracle[t] = float(all(a[p] > x for x in a[p - 6:p]) and all(a[p] >= x for x in a[p + 1:t + 1]))
        np.testing.assert_allclose(out[f"swing_{side}_confirmed"], oracle, equal_nan=True)


def test_asset_isolation_validation_and_determinism():
    f = frame()
    before = f.copy(deep=True)
    a = compute_research_features(f, 300)
    pd.testing.assert_frame_equal(a, compute_research_features(f, 300))
    pd.testing.assert_frame_equal(before, f)
    other = f.copy()
    other["instrument"] = "XAU_USD"
    pd.testing.assert_frame_equal(a, compute_research_features(other, 300))
    with pytest.raises(ValueError, match="one nonempty instrument"):
        compute_research_features(pd.concat([f, other]), 300)
    with pytest.raises(ValueError, match="timestamps"):
        compute_research_features(f.iloc[::-1], 300)
    with pytest.raises(ValueError, match="timestamps"):
        compute_research_features(pd.concat([f.iloc[:1], f]), 300)
    with pytest.raises(ValueError, match="CFD grid"):
        compute_research_features(f, 300, swing_left=5)


def test_availability_timestamps_equal_confirmation_close_not_pivot():
    f = frame()
    out = compute_research_features(f, 300)
    for side in ("high", "low"):
        mask = out[f"swing_{side}_confirmed"] == 1
        assert mask.any()
        assert (out.loc[mask, f"swing_{side}_confirmed_time"].to_numpy()
                == (f.loc[mask, "time"] + pd.Timedelta(minutes=5)).to_numpy()).all()
        assert (out.loc[mask, f"swing_{side}_confirmed_time"]
                > out.loc[mask, f"swing_{side}_pivot_time"]).all()


def test_price_reflection_swaps_all_structural_directions():
    f = frame()
    mirrored = f.copy()
    mirrored["open"], mirrored["close"] = 300 - f["open"], 300 - f["close"]
    mirrored["high"], mirrored["low"] = 300 - f["low"], 300 - f["high"]
    mirrored["dc_upper_24"], mirrored["dc_lower_24"] = 300 - f["dc_lower_24"], 300 - f["dc_upper_24"]
    first, second = compute_research_features(f, 300), compute_research_features(mirrored, 300)
    for up, down in (("swing_high_confirmed", "swing_low_confirmed"), ("structure_hh", "structure_ll"),
                     ("structure_lh", "structure_hl"), ("structure_break_up", "structure_break_down"),
                     ("structure_break_strength_up", "structure_break_strength_down"),
                     ("breakout_retest_up", "breakout_retest_down"),
                     ("range_reentry_from_above", "range_reentry_from_below"),
                     ("failed_breakout_up", "failed_breakout_down")):
        np.testing.assert_allclose(first[up], second[down], atol=1e-12, equal_nan=True)
        np.testing.assert_allclose(first[down], second[up], atol=1e-12, equal_nan=True)


def test_exact_event_window_boundary_and_expired_swing_level():
    for age in (6, 7):
        c = [9, 11] + [11] * (age - 1) + [9]
        result = frozen_events(**event_inputs(c))
        assert result["range_reentry_from_above"][-1] == 1
        assert result["failed_breakout_up"][-1] == (age == 6)
        inputs = event_inputs([9, 11] + [11] * age)
        inputs["structure"]["structure_break_up"][1] = 1
        inputs["low"][-1] = 10.
        result = frozen_events(**inputs)
        assert result["breakout_retest_up"][-1] == (age == 6)
    high = np.ones(150) * 2
    high[6] = 10
    result = structure(high)
    assert result["last_confirmed_swing_high"][131] == 10
    assert np.isnan(result["last_confirmed_swing_high"][132])


def test_partial_bar_resets_pending_episode_and_nan_atr_invalidates_full_rank_window():
    inputs = event_inputs([9, 11, 11, 9])
    inputs["valid"][2] = False
    assert np.nansum(frozen_events(**inputs)["failed_breakout_up"]) == 0
    f = frame()
    f.loc[200, "atr_24"] = np.nan
    result = compute_research_features(f, 300)
    assert result["atr_percentile_60"].iloc[200:260].isna().all()
    assert np.isfinite(result["atr_percentile_60"].iloc[260])
