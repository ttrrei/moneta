"""Independent formulas, causal timing and boundary checks for catalogue batch 1."""
import numpy as np
import pandas as pd
import pytest

from library.catalogue import center_stretch, capped_age
from pipeline.catalogue_features import compute_catalogue_features, context_features, quality


def frame(n=1500, freq="5min", instrument="EUR_USD"):
    rng = np.random.default_rng(19)
    c = 100 + np.cumsum(rng.normal(0, .1, n))
    o = np.r_[c[0], c[:-1]]
    h, l = np.maximum(o, c) + .1, np.minimum(o, c) - .1
    return pd.DataFrame({"instrument": instrument, "time": pd.date_range("2020-01-01", periods=n, freq=freq, tz="UTC"),
                         "open": o, "high": h, "low": l, "close": c, "n_bars": 60 if freq == "1h" else 5,
                         "atr_24": 1., "ema_24": pd.Series(c).ewm(span=24).mean(),
                         "ema_dist_24": (c - pd.Series(c).ewm(span=24).mean()),
                         "sqz_on_24": (np.arange(n) % 35 < 20).astype(float),
                         "bb_width_24": .01, "er_24": .5, "st_dir_24_2": np.where(np.arange(n) % 50 < 25, 1., -1.),
                         "bar_clv": ((c - l) - (h - c)) / (h - l),
                         "dc_upper_24": pd.Series(h).rolling(24).max(),
                         "dc_lower_24": pd.Series(l).rolling(24).min()})


def test_centers_match_independent_median_and_lstsq_oracles():
    c = frame(150).close.to_numpy()
    median, regression = center_stretch(c)
    for t in range(23, len(c)):
        a = c[t-23:t+1]
        med = np.median(a)
        assert median[t] == pytest.approx((a[-1] - med) / np.median(abs(a - med)))
        y = np.log(a)
        design = np.column_stack([np.ones(24), np.arange(24)])
        residual = y - design @ np.linalg.lstsq(design, y, rcond=None)[0]
        assert regression[t] == pytest.approx(residual[-1] / np.sqrt(np.mean(residual ** 2)), abs=1e-10)
    assert np.isnan(median[:23]).all()
    for c in (np.ones(100), np.exp(np.arange(100) * .01)):
        _, residual = center_stretch(c)
        assert np.isnan(residual).all()


def test_hourly_availability_and_freshness_at_exact_boundaries():
    f, h = frame(48), frame(4, "1h")
    h.st_dir_24_2 = [1., -1., 1., -1.]
    result = context_features(f, h)
    assert result.htf_direction.iloc[:11].isna().all()
    assert result.htf_direction.iloc[11] == 1
    assert result.htf_direction.iloc[22] == 1
    assert result.htf_direction.iloc[23] == -1
    missing_hour = h.drop(index=1)
    stale = context_features(f, missing_hour)
    assert np.isnan(stale.htf_direction.iloc[23])
    changed = h.copy()
    changed.loc[1:, "st_dir_24_2"] *= -1
    pd.testing.assert_frame_equal(result.iloc[:23], context_features(f, changed).iloc[:23])
    partial = h.copy()
    partial.loc[1, "n_bars"] = 59
    assert np.isnan(context_features(f, partial).htf_direction.iloc[23])


def test_native_hour_slope_and_timezone_conversion():
    f, h = frame(150), frame(15, "1h")
    result = context_features(f, h)
    t = 83  # 07:00 close: native hour beginning 06:00 becomes available.
    assert result.htf_slope.iloc[t] == pytest.approx(h.ema_24.iloc[6] - h.ema_24.iloc[0])
    local = h.copy()
    local.time = local.time.dt.tz_convert("Australia/Sydney")
    pd.testing.assert_frame_equal(result, context_features(f, local))


@pytest.mark.parametrize("cut", [12, 26, 137, 701])
def test_all_outputs_are_prefix_invariant_and_future_independent(cut):
    f, h = frame(), frame(150, "1h")
    full = compute_catalogue_features(f, h)
    pd.testing.assert_frame_equal(full.iloc[:cut], compute_catalogue_features(f.iloc[:cut], h))
    changed = f.copy()
    names = changed.select_dtypes(include="number").columns.difference(["n_bars"])
    changed.loc[cut:, names] *= 1.1
    future_h = h.copy()
    cutoff = f.time.iloc[cut - 1] + pd.Timedelta(minutes=5)
    future_h.loc[future_h.time + pd.Timedelta(hours=1) > cutoff, "close"] *= 1.1
    pd.testing.assert_frame_equal(full.iloc[:cut], compute_catalogue_features(changed, future_h).iloc[:cut])


def test_variance_memory_and_jump_match_direct_window_calculation():
    f, h = frame(), frame(150, "1h")
    result = compute_catalogue_features(f, h)
    r = np.r_[np.nan, np.diff(np.log(f.close.to_numpy()))]
    for t in (26, 400, 900):
        a = r[t-23:t+1]
        positive, negative = np.sum(a[a > 0]**2), np.sum(a[a < 0]**2)
        assert result.variance_imbalance.iloc[t] == pytest.approx((positive-negative)/(positive+negative))
        assert result.jump_concentration.iloc[t] == pytest.approx(np.max(a*a)/np.sum(a*a))
        assert result.sign_memory.iloc[t] == pytest.approx(np.corrcoef(np.sign(a), np.sign(r[t-24:t]))[0,1])
        assert result.jump_direction.iloc[t] == np.sign(a[np.argmax(a*a)])


def test_candle_engulfing_doji_equality_and_sweep_ambiguity():
    f, h = frame(100), frame(20, "1h")
    f.loc[30, ["open", "close", "high", "low"]] = [100., 99., 100.1, 98.9]
    f.loc[31, ["open", "close", "high", "low"]] = [98.5, 100.5, 100.6, 98.4]
    f.loc[40:, ["dc_upper_24", "dc_lower_24"]] = [101., 99.]
    f.loc[41, ["open", "close", "high", "low"]] = [100., 100.2, 101.5, 99.9]
    f.loc[42, ["open", "close", "high", "low"]] = [100., 100.2, 101.5, 98.5]
    f.loc[50, ["open", "close", "high", "low"]] = [100., 100., 100.1, 99.9]
    result = compute_catalogue_features(f, h)
    assert result.engulfing_state.iloc[31] == 1
    assert result.body_direction.iloc[31] == 1
    assert result.sweep_state.iloc[41] == 1 and result.rejection_direction.iloc[41] == -1
    assert result.sweep_ambiguous.iloc[42] == 1 and np.isnan(result.sweep_state.iloc[42])
    assert np.isnan(result.engulfing_state.iloc[50])


def test_gaps_partial_bars_and_flat_inputs_rewarm_without_infinity():
    f, h = frame(), frame(150, "1h")
    f.loc[300:, "time"] += pd.Timedelta(days=2)
    f.loc[600, "n_bars"] = 4
    result = compute_catalogue_features(f, h)
    assert result.median_stretch.iloc[300:323].isna().all()
    assert result.sign_memory.iloc[600:626].isna().all()
    f[["open", "high", "low", "close", "ema_24", "dc_upper_24", "dc_lower_24"]] = 100.
    f.atr_24 = 0.
    result = compute_catalogue_features(f, h)
    assert not np.isinf(result.select_dtypes(include="number").to_numpy()).any()
    assert result.median_stretch.isna().all()
    assert result.regression_residual.isna().all()


def test_input_immutability_identity_and_later_start():
    f, h = frame(), frame(150, "1h")
    before = f.copy(deep=True)
    full = compute_catalogue_features(f, h)
    pd.testing.assert_frame_equal(f, before)
    later = compute_catalogue_features(f.iloc[200:], h)
    pd.testing.assert_frame_equal(full.loc[500:], later.loc[500:])
    other = h.copy(); other.instrument = "XAU_USD"
    with pytest.raises(ValueError, match="mismatch"):
        compute_catalogue_features(f, other)
    with pytest.raises(ValueError, match="timestamps"):
        quality(f.iloc[::-1], 300)


def test_capped_age_resets_and_caps():
    state = np.ones(150)
    good, adjacent = np.ones(150, bool), np.ones(150, bool)
    good[130] = False; adjacent[140] = False
    age = capped_age(state, good, adjacent)
    assert age[119] == age[129] == 120
    assert np.isnan(age[130]) and age[131] == age[140] == 1
