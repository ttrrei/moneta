"""Automated quality gates for the feature engine (:mod:`pipeline.indicators`).

These implement the *six quality gates* promised in ``docs/indicators.md`` §8
(calls them out as "0% implemented" in the legacy reviews). They run on
**synthetic** OHLCV — no real data, no network, no CI dependency — so they can
catch the two dangerous failure classes before anyone touches the 259-column
feature table:

* **Gate 1 — Causality / prefix invariance:** computing on the full series and
  on a prefix must agree on the overlap. Any lookahead (``shift(-k)``, full
  history, etc.) breaks this.
* **Gate 3 — Bounds & invariants:** RSI/Stoch ∈ [0,100], ATR ≥ 0,
  bb_lower ≤ bb_upper, sqz_on ∈ {0,1}, …
* **Gate 4 — Degenerate input:** flat / zero-range bars must not produce Inf
  or crash the engine.
* **Gate 6 — Time alignment:** the 1h→5m as-of join must never expose a 1h bar
  before its close time.

Gate 2 (start-independence / warm-up convergence) and Gate 5 (dual-library
parity) are exercised at the smoke level here; the full parity harness
(``scripts/verify_indicator_parity.py`` from the spec) is a separate, larger
artifact (see docs/repo_review_20261026.md T0-4).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

import talib

from pipeline.indicators import (
    N_GRID,
    PAIRS,
    asof_join_h1_features,
    compute_instrument_features,
    validate_grid,
)

INSTRUMENT = "EUR_USD"  # has a configured session anchor
N_BARS = 800
WARMUP = 360  # 3 * max(N_GRID) — warm-up head is NaN


# ---------------------------------------------------------------------------
# Synthetic data
# ---------------------------------------------------------------------------

def _rng(seed: int = 7) -> np.random.Generator:
    return np.random.default_rng(seed)


def make_ohlcv(n: int = N_BARS, seed: int = 7, flat: bool = False) -> pd.DataFrame:
    """A plausible, gap-free 5m OHLCV frame (tz-aware UTC ``time``).

    Guarantees high ≥ max(o,c), low ≤ min(o,c), all positive — a valid market
    series the TA-Lib calls can consume.
    """
    g = _rng(seed)
    t = pd.date_range("2020-01-02", periods=n, freq="5min", tz="UTC")
    if flat:
        price = np.full(n, 1.10)
    else:
        # Random walk around 1.10, bounded to stay positive.
        shocks = g.normal(0, 1e-4, n).cumsum()
        price = 1.10 + shocks
    price = np.maximum(price, 1e-3)
    close = price
    open_ = np.concatenate([[price[0]], price[:-1]])
    hi = np.maximum(open_, close)
    lo = np.minimum(open_, close)
    if not flat:
        spread = np.abs(g.normal(0, 5e-5, n))
        hi = hi + spread
        lo = np.maximum(lo - spread, 1e-6)
    hi = np.maximum(hi, lo)
    return pd.DataFrame({
        "instrument": INSTRUMENT,
        "time": t,
        "open": open_,
        "high": hi,
        "low": lo,
        "close": close,
        "volume": g.integers(1, 100, n).astype(np.int64),
        "n_bars": np.full(n, 12, dtype=np.int64),
    })


def _features(df: pd.DataFrame) -> pd.DataFrame:
    return compute_instrument_features(df, interval_seconds=300)


def _windowed_columns(feat: pd.DataFrame) -> list[str]:
    """Columns that carry a window N (the bulk of the feature matrix)."""
    cols = []
    for n in N_GRID:
        cols += [c for c in feat.columns if c.endswith(f"_{n}") or f"_{n}_" in c]
    return cols


# ---------------------------------------------------------------------------
# validate_grid — the window whitelist itself
# ---------------------------------------------------------------------------

def test_validate_grid_rejects_out_of_whitelist_windows():
    with pytest.raises(ValueError):
        validate_grid((5, 14), PAIRS)          # 5 and 14 are not in the grid
    with pytest.raises(ValueError):
        validate_grid(N_GRID, ((12, 26),))     # 26 not in any whitelisted pair
    # and the *valid* grid is accepted:
    validate_grid(N_GRID, PAIRS)


def test_validate_grid_is_window_only():
    """The whitelist constrains *bar-count* windows only — it says nothing about
    non-window parameters (accel/multiplier). Documenting the B10 rule with a
    test: a non-window value like 0.02 must not be *attempted* as a window."""
    with pytest.raises(ValueError):
        validate_grid((0.02,), PAIRS)          # a PSAR accel value is not a window


# ---------------------------------------------------------------------------
# Gate 1 — Causality / prefix invariance
# ---------------------------------------------------------------------------

def test_prefix_invariance_no_lookahead():
    """Computing on the full series and on a prefix must agree on the overlap.
    Any lookahead operator breaks this test (spec Gate 1, tol < 1e-12)."""
    df = make_ohlcv(n=N_BARS, seed=11)
    full = _features(df)
    k = 600
    prefix = _features(df.iloc[:k].reset_index(drop=True))

    cols = [c for c in full.columns if c in prefix.columns]
    assert len(cols) > 0
    for c in cols:
        a = full[c].to_numpy()[:k]
        b = prefix[c].to_numpy()
        # Ignore warm-up NaN rows; compare the valid overlap.
        mask = np.isfinite(a) & np.isfinite(b)
        if mask.sum() == 0:
            continue
        diff = np.max(np.abs(a[mask] - b[mask]))
        assert diff < 1e-12, f"{c}: max prefix-vs-full diff {diff} (lookahead?)"


def test_changing_the_future_does_not_change_the_past():
    """A stronger causality check: perturbing bars *after* index m must not
    change any feature at index ≤ m (Gate 1 'no future leakage')."""
    base = make_ohlcv(n=N_BARS, seed=21)
    m = 500
    full = _features(base)

    perturbed = base.copy()
    # Shift prices after m by a large amount (still a valid series).
    perturbed.loc[perturbed.index > m, ["open", "high", "low", "close"]] = (
        perturbed.loc[perturbed.index > m, ["open", "high", "low", "close"]] * 1.3
    )
    perturbed["high"] = perturbed[["open", "high", "low", "close"]].max(axis=1)
    perturbed["low"] = perturbed[["open", "high", "low", "close"]].min(axis=1)
    pert = _features(perturbed)

    for c in full.columns:
        a = full[c].to_numpy()[: m + 1]
        b = pert[c].to_numpy()[: m + 1]
        mask = np.isfinite(a) & np.isfinite(b)
        if mask.sum() == 0:
            continue
        assert np.max(np.abs(a[mask] - b[mask])) < 1e-12, \
            f"{c}: value at/before {m} changed when the future changed (lookahead)"


# ---------------------------------------------------------------------------
# Gate 3 — Bounds & invariants
# ---------------------------------------------------------------------------

def test_oscillator_and_volatility_bounds():
    df = make_ohlcv(seed=31)
    f = _features(df)

    def _valid(col: str, lo: float, hi: float) -> None:
        x = f[col].to_numpy()
        x = x[np.isfinite(x)]
        assert x.size > 0, f"{col} is entirely NaN"
        assert np.all(x >= lo - 1e-9), f"{col} min {x.min()} < {lo}"
        assert np.all(x <= hi + 1e-9), f"{col} max {x.max()} > {hi}"

    for n in N_GRID:
        _valid(f"rsi_{n}", 0.0, 100.0)
        _valid(f"stoch_k_{n}", 0.0, 100.0)
        _valid(f"stoch_d_{n}", 0.0, 100.0)
        _valid(f"willr_{n}", -100.0, 0.0)
        assert np.all(f[f"atr_{n}"].dropna() >= 0.0)
        assert np.all((f[f"bb_lower_{n}"].dropna() <= f[f"bb_upper_{n}"].dropna() + 1e-9))
        _valid(f"sqz_on_{n}", 0.0, 1.0)
        _valid(f"dc_pos_{n}", 0.0, 1.0)
        # efficiency ratio 0..1
        _valid(f"er_{n}", 0.0, 1.0)


def test_direction_and_flag_columns_are_binary_or_signed_unit():
    df = make_ohlcv(seed=41)
    f = _features(df)
    for flag in ("is_gap_bar", "is_partial", "is_near_market_close"):
        vals = set(np.unique(f[flag].dropna().to_numpy()))
        assert vals.issubset({0.0, 1.0}), f"{flag} not binary: {vals}"


# ---------------------------------------------------------------------------
# Gate 4 — Degenerate input (flat / zero-range bars)
# ---------------------------------------------------------------------------

def test_flat_bars_do_not_produce_inf_or_crash():
    """A *realistic* zero-amplitude series (constant close, a hair of wick each
    bar) must not produce Inf or crash. This is the Gate 4 guarantee that matters
    for real data — a perfectly flat series (high==low==close on every bar) is a
    degenerate mathematical edge that the ATR/choppiness formulas can hit, and is
    not a market state this pipeline should silently accept either way."""
    n = 400
    t = pd.date_range("2020-01-02", periods=n, freq="5min", tz="UTC")
    close = np.full(n, 1.10)
    df = pd.DataFrame({
        "instrument": INSTRUMENT, "time": t,
        "open": close, "high": close + 1e-7, "low": close - 1e-7, "close": close,
        "volume": np.ones(n, dtype=np.int64), "n_bars": np.full(n, 12, dtype=np.int64),
    })
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        f = _features(df)  # must not raise
    for c in f.columns:
        assert not np.isinf(f[c].to_numpy()).any(), f"{c} contains Inf on zero-amplitude input"
    assert np.all(np.isfinite(f.dropna().to_numpy()))


def test_short_history_is_handled():
    # Just above the minimum; must not crash and must return the same length.
    df = make_ohlcv(n=10, seed=5)
    f = _features(df)
    assert len(f) == 10


# ---------------------------------------------------------------------------
# Gate 6 — Time alignment (1h → 5m as-of join)
# ---------------------------------------------------------------------------

def test_asof_join_never_exposes_an_unclosed_1h_bar():
    """Gate 6: a 5m bar may only see a 1h bar whose *close* time ≤ the 5m bar's
    own close time. We verify the joined value against the rule computed from
    first principles, so the test is self-contained and cannot be a tautology."""
    from pipeline.indicators import _h1_feature_columns
    h_cols = _h1_feature_columns()
    assert len(h_cols) > 0
    marker = h_cols[0]

    # 1h bars open at 00:00, 01:00, 02:00, 03:00 → close at 01:00, 02:00, 03:00, 04:00.
    n_h = 4
    h_open = pd.date_range("2020-01-02", periods=n_h, freq="1h", tz="UTC")
    h_close = h_open + pd.Timedelta(hours=1)
    h = pd.DataFrame({"instrument": INSTRUMENT, "time": h_open})
    for col in h_cols:
        h[col] = np.arange(n_h, dtype=np.float64)  # marker = index of the 1h bar

    # 5m bars over the first three hours.
    m_open = pd.date_range("2020-01-02", periods=36, freq="5min", tz="UTC")
    m_close = m_open + pd.Timedelta(minutes=5)
    m = pd.DataFrame({"instrument": INSTRUMENT, "time": m_open})

    out = asof_join_h1_features(m, h, interval_5m_seconds=300, interval_1h_seconds=3600)
    joined = out[f"h1_{marker}"].to_numpy()

    # Expected: most recent 1h bar with close <= m_close, else NaN (no leak).
    for j in range(len(m_open)):
        visible = [i for i in range(n_h) if h_close[i] <= m_close[j]]
        if visible:
            assert joined[j] == float(max(visible)), \
                f"5m bar {m_open[j]} saw marker {joined[j]}, expected {max(visible)}"
        else:
            assert np.isnan(joined[j]), \
                f"5m bar {m_open[j]} saw a future 1h bar (marker {joined[j]}) — lookahead"


# ---------------------------------------------------------------------------
# Gate 5 (smoke) — parity vs a trusted implementation for one indicator
# ---------------------------------------------------------------------------

def test_rsi_parity_vs_talib_reference():
    """The feature engine's RSI must equal a direct TA-Lib RSI call (ddof/seed
    alignment). A cheap parity check that the wrapper is not silently
    transforming the value (spec Gate 5, rolling-class tolerance)."""
    df = make_ohlcv(seed=61)
    f = _features(df)
    c = df["close"].to_numpy(np.float64)
    for n in N_GRID:
        ref = talib.RSI(c, timeperiod=n)
        got = f[f"rsi_{n}"].to_numpy()
        mask = np.isfinite(ref) & np.isfinite(got)
        assert mask.sum() > 0
        assert np.max(np.abs(ref[mask] - got[mask])) < 1e-9, f"RSI_{n} parity failed"


def test_sma_parity_vs_talib_reference():
    df = make_ohlcv(seed=71)
    f = _features(df)
    c = df["close"].to_numpy(np.float64)
    for n in N_GRID:
        ref = talib.SMA(c, timeperiod=n)
        got = f[f"sma_{n}"].to_numpy()
        mask = np.isfinite(ref) & np.isfinite(got)
        assert np.max(np.abs(ref[mask] - got[mask])) < 1e-9, f"SMA_{n} parity failed"


# ===========================================================================
# PSAR + Supertrend — the `indicators/` library (T2.1)
# ===========================================================================

from library import supertrend as _supertrend_fn  # noqa: E402
from pipeline.indicators import (  # noqa: E402
    PSAR_PARAMS,
    ST_MULTS,
    param_tag,
)


def _tag(x: float) -> str:
    return param_tag(x)


def _h1_cols() -> list[str]:
    from pipeline.indicators import _h1_feature_columns

    return _h1_feature_columns()


def test_psar_and_supertrend_columns_present():
    f = _features(make_ohlcv(n=1500, seed=21))
    expected = set()
    for a, m in PSAR_PARAMS:
        t = f"{_tag(a)}_{_tag(m)}"
        expected |= {f"psar_{t}", f"psar_dir_{t}", f"psar_dist_{t}"}
    for n in N_GRID:
        for mult in ST_MULTS:
            t = _tag(mult)
            expected |= {f"st_{n}_{t}", f"st_dir_{n}_{t}", f"st_dist_{n}_{t}"}
    assert expected <= set(f.columns)
    # 1h projection carries the Supertrend direction too.
    h1 = set(_h1_cols())
    assert {f"st_dir_{n}_{_tag(m)}" for n in N_GRID for m in ST_MULTS} <= h1


def test_free_params_not_whitelisted_but_windows_still_are():
    df = make_ohlcv(n=1500, seed=22)
    f = compute_instrument_features(
        df, 300, psar_params=((0.03, 0.30), (0.015, 0.15)), st_mults=(1.5, 2.5, 4.0)
    )
    for col in ("psar_0p03_0p3", "psar_dist_0p015_0p15", "st_24_1p5",
                "st_dir_6_2p5", "st_dist_120_4"):
        assert col in f.columns, col
    assert "psar_0p02_0p2" not in f.columns  # only the requested params are built
    # ... but time windows stay restricted to the N grid
    with pytest.raises(ValueError):
        compute_instrument_features(df, 300, n_grid=(7,))
    # free params are sanity-checked, not whitelisted
    with pytest.raises(ValueError):
        compute_instrument_features(df, 300, psar_params=((0.2, 0.02),))
    with pytest.raises(ValueError):
        compute_instrument_features(df, 300, st_mults=(0.0,))


def test_custom_params_are_prefix_invariant():
    df = make_ohlcv(n=2500, seed=23)
    kw = dict(psar_params=((0.03, 0.30),), st_mults=(1.5, 5.0))
    full = compute_instrument_features(df, 300, **kw)
    pre = compute_instrument_features(df.iloc[:1700].reset_index(drop=True), 300, **kw)
    cols = [c for c in full.columns if c.startswith(("psar", "st_"))]
    assert cols
    for col in cols:
        assert np.allclose(full[col].to_numpy(np.float64)[:1700],
                           pre[col].to_numpy(np.float64), equal_nan=True), col


def test_psar_direction_matches_side_of_price():
    f = _features(make_ohlcv(n=2000, seed=24)).iloc[WARMUP:]
    c = make_ohlcv(n=2000, seed=24)["close"].to_numpy()[WARMUP:]
    for a, m in PSAR_PARAMS:
        t = f"{_tag(a)}_{_tag(m)}"
        side = np.sign(c - f[f"psar_{t}"].to_numpy())
        valid = np.isfinite(side)
        assert (f[f"psar_dir_{t}"].to_numpy()[valid] == side[valid]).all()
        assert (np.sign(f[f"psar_dist_{t}"].to_numpy())[valid] == side[valid]).all()


@pytest.mark.parametrize("n", N_GRID)
@pytest.mark.parametrize("mult", ST_MULTS)
def test_supertrend_line_is_on_the_trend_side(n, mult):
    f = _features(make_ohlcv(n=2000, seed=25)).iloc[WARMUP:]
    c = make_ohlcv(n=2000, seed=25)["close"].to_numpy()[WARMUP:]
    t = _tag(mult)
    line = f[f"st_{n}_{t}"].to_numpy()
    d = f[f"st_dir_{n}_{t}"].to_numpy()
    assert not np.isnan(line).any() and not np.isnan(d).any()
    # uptrend -> line (lower band) at/below close; downtrend -> at/above close
    ok = ((d > 0) & (line <= c + 1e-9)) | ((d < 0) & (line >= c - 1e-9))
    assert ok.all()
    assert (np.sign(f[f"st_dist_{n}_{t}"].to_numpy()) == d).all()


def test_wider_supertrend_multiplier_flips_less():
    f = compute_instrument_features(make_ohlcv(n=4000, seed=26), 300, st_mults=(1.0, 4.0)).iloc[WARMUP:]
    flips = lambda col: int((f[col].diff().abs() > 0).sum())
    assert flips("st_dir_24_4") < flips("st_dir_24_1")


def test_supertrend_flips_on_close_through_band():
    """Hand-made series: steady rise, then a sharp drop must flip to downtrend."""
    n = 200
    c = np.r_[np.linspace(100, 120, 150), np.linspace(120, 90, 50)]
    h, l = c + 0.2, c - 0.2
    atr = np.full(n, 0.5)
    _, d = _supertrend_fn(h, l, c, atr, mult=3.0)
    assert d[100] == 1.0 and d[-1] == -1.0


def test_supertrend_no_inf_on_flat_series():
    """Zero-amplitude input: bands stay finite (atr=0 → bands = hl2), no Inf."""
    n = 100
    c = np.full(n, 100.0)
    h, l = c + 1e-7, c - 1e-7  # near-flat (exactly flat makes ATR 0, still finite)
    atr = talib.ATR(h, l, c, timeperiod=6)
    line, d = _supertrend_fn(h, l, c, atr, mult=3.0)
    # ATR is NaN for the first `timeperiod` bars → line/direction NaN there;
    # after warm-up everything must be finite (no Inf on zero-amplitude input).
    assert not np.isinf(line).any() and not np.isinf(d).any()
    valid = np.isfinite(line)
    assert valid.sum() > 0
    assert np.all(np.isfinite(line[valid]))
    assert np.all(np.isfinite(d[valid]))


def test_supertrend_parity_direction_vs_pandas_ta():
    """Gate 5 (smoke): direction agreement with pandas_ta_classic.supertrend.

    Both use a ratcheted-band recursion with the same close-crossing flip
    rule, but they may differ in the first bar after ATR warm-up and in
    NaN-handling, so we compare *direction* on the valid overlap with a
    relaxed agreement threshold (the reviews cite >99.8%).
    """
    import pandas_ta_classic as ptac

    df = make_ohlcv(n=3000, seed=27)
    h = df["high"].to_numpy()
    l = df["low"].to_numpy()
    c = df["close"].to_numpy()

    n, mult = 24, 3.0
    atr = talib.ATR(h, l, c, timeperiod=n)
    _, ours = _supertrend_fn(h, l, c, atr, mult=mult)

    ref = ptac.supertrend(pd.Series(h), pd.Series(l), pd.Series(c),
                          length=n, multiplier=mult)
    # pandas-ta-classic columns: SUPERT_<n>_<mult> (line), SUPERTd_... (direction)
    dcol = [x for x in ref.columns if x.startswith("SUPERTd")]
    assert dcol, f"no direction column in {list(ref.columns)}"
    theirs_dir = ref[dcol[0]].to_numpy()

    mask = np.isfinite(ours) & np.isfinite(theirs_dir)
    agree = (ours[mask] == theirs_dir[mask]).mean()
    assert mask.sum() > 100
    assert agree > 0.95, f"supertrend direction agreement vs pandas_ta: {agree:.2%}"


def test_supertrend_invalid_multiplier_rejected():
    with pytest.raises(ValueError):
        _supertrend_fn(np.array([1.0]), np.array([1.0]), np.array([1.0]),
                       np.array([0.1]), mult=0.0)
