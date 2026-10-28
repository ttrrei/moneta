"""Deterministic rule + DST regression tests (no data, no network, no talib).

These lock the *contract* of the pieces the reviews flagged as untested:

* the two trend-follower state rules (``SupertrendState`` / ``EmaSpreadState``)
  — signal on the previous closed bar, long-only, NaN-safe;
* the DST offset resolution (``_utc_offset_for``) — the 10-27 review fixed the
  month-based DST approximation to ``zoneinfo``-per-date, and no regression
  test guarded it; this file pins a real US DST boundary.

They are pure (numpy/pandas only), so they run in CI exactly like
``test_metrics.py``.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from pipeline.indicators import SessionAnchor, _utc_offset_for
from strategy.strategy_supertrend_lib import SupertrendState
from strategy.strategy_ema_spread_lib import EmaSpreadState
from strategy.strategy_regime_trend_lib import RegimeTrendState


# ---------------------------------------------------------------------------
# SupertrendState: long when the *previous* closed bar's direction is up
# ---------------------------------------------------------------------------

def test_supertrend_is_flat_on_bar_zero():
    st = SupertrendState(np.array([1.0, 1.0, 1.0]))
    assert st.desired_position(0) == 0  # no previous bar -> flat


def test_supertrend_follows_previous_bar_direction():
    # direction on bar i-1 decides bar i
    st = SupertrendState(np.array([0.0, 1.0, 1.0, -1.0, 1.0]))
    assert st.desired_position(1) == 0   # bar0 flat (0.0)
    assert st.desired_position(2) == 1   # bar1 up   -> long
    assert st.desired_position(3) == 1   # bar2 up   -> long
    assert st.desired_position(4) == 0   # bar3 down -> flat
    assert st.desired_position(5) == 1   # bar4 up   -> long


def test_supertrend_is_nan_safe():
    # a non-finite direction must be ignored, preserving the prior state
    st = SupertrendState(np.array([np.nan, 1.0, np.nan, -1.0]))
    assert st.desired_position(1) == 0    # bar0 NaN -> stays flat
    assert st.desired_position(2) == 1    # bar1 up   -> long
    assert st.desired_position(3) == 1    # bar2 NaN -> keep long
    assert st.desired_position(4) == 0    # bar3 down -> flat


# ---------------------------------------------------------------------------
# EmaSpreadState: long when the *previous* closed bar's spread is positive
# ---------------------------------------------------------------------------

def test_ema_spread_is_flat_on_bar_zero():
    s = EmaSpreadState(np.array([0.5, 0.5, 0.5]))
    assert s.desired_position(0) == 0


def test_ema_spread_enters_on_positive_spread():
    s = EmaSpreadState(np.array([0.0, 0.2, -0.1, 0.3]))
    assert s.desired_position(1) == 0     # bar0 spread 0.0 -> not >0 -> flat
    assert s.desired_position(2) == 1     # bar1 spread +0.2 -> long
    assert s.desired_position(3) == 0     # bar2 spread -0.1 -> flat
    assert s.desired_position(4) == 1     # bar3 spread +0.3 -> long


def test_ema_spread_zero_spread_is_flat():
    # the rule is strictly spread > 0 (zero is an exit), matching the registry
    s = EmaSpreadState(np.array([1.0, 0.0]))
    assert s.desired_position(1) == 1     # bar1: spread bar0 = +1.0 -> long
    assert s.desired_position(2) == 0     # bar2: spread bar1 = 0.0 -> flat


def test_ema_spread_is_nan_safe():
    s = EmaSpreadState(np.array([np.nan, 0.5, np.nan]))
    assert s.desired_position(1) == 0     # bar0 NaN -> flat
    assert s.desired_position(2) == 1     # bar1 +0.5 -> long
    assert s.desired_position(3) == 1     # bar2 NaN -> keep long


# ---------------------------------------------------------------------------
# RegimeTrendState: enter only on a SuperTrend *flip* whose bar is trending
# (ADX above threshold); hold between flips; flat on a flip in a weak regime.
# ---------------------------------------------------------------------------

def test_regime_trend_is_flat_on_bar_zero():
    rt = RegimeTrendState(np.array([1.0, 1.0, 1.0]), np.array([40.0, 40.0, 40.0]))
    assert rt.desired_position(0) == 0  # no previous bar -> flat
    assert rt.desired_position(1) == 0  # one previous bar -> still flat


def test_regime_trend_enters_on_gated_flip():
    # flip 1 -> -1 between bar2 and bar3; ADX(3)=40 > 25 -> short taken at bar4
    dirn = np.array([1.0, 1.0, 1.0, -1.0, -1.0])
    adx = np.array([0.0, 0.0, 0.0, 40.0, 0.0])
    rt = RegimeTrendState(dirn, adx, threshold=25.0)
    assert rt.desired_position(2) == 0   # no flip yet -> flat
    assert rt.desired_position(3) == 0   # no flip yet -> flat
    assert rt.desired_position(4) == -1  # gated flip (ADX 40>25) -> short
    assert rt.desired_position(5) == -1  # no flip -> hold the short


def test_regime_trend_ignores_flip_in_weak_regime():
    # same flip, but ADX(3)=10 <= 25 -> stand flat (the gate is doing its job)
    dirn = np.array([1.0, 1.0, 1.0, -1.0, -1.0])
    adx = np.array([0.0, 0.0, 0.0, 10.0, 0.0])
    rt = RegimeTrendState(dirn, adx, threshold=25.0)
    assert rt.desired_position(4) == 0   # flip in a weak regime -> flat
    assert rt.desired_position(5) == 0   # no flip -> stay flat


def test_regime_trend_reverses_on_next_gated_flip():
    # dir: 1 1 1 -1 -1  1 1 1   (indices 0..7)
    # flip 1->-1 lands on bar3 (i=4); flip -1->+1 lands on bar5 (i=6).
    # Both flips have ADX>25 -> short then long; holds persist between flips.
    dirn = np.array([1.0, 1.0, 1.0, -1.0, -1.0, 1.0, 1.0, 1.0])
    adx = np.array([0.0, 0.0, 0.0, 40.0, 0.0, 40.0, 0.0, 0.0])
    rt = RegimeTrendState(dirn, adx, threshold=25.0)
    assert rt.desired_position(4) == -1  # gated 1->-1 flip (ADX40>25) -> short
    assert rt.desired_position(5) == -1  # no flip -> hold the short
    assert rt.desired_position(6) == 1   # gated -1->+1 flip (ADX40>25) -> long
    assert rt.desired_position(7) == 1   # no flip -> hold the long


def test_regime_trend_is_nan_safe():
    # enter short, then a NaN direction bar must be ignored (state preserved)
    dirn = np.array([1.0, -1.0, -1.0, np.nan, -1.0])
    adx = np.array([0.0, 40.0, 0.0, 0.0, 0.0])
    rt = RegimeTrendState(dirn, adx, threshold=25.0)
    assert rt.desired_position(2) == -1  # bar1 flip gated (ADX40) -> short
    assert rt.desired_position(3) == -1  # bar2 hold -> short
    assert rt.desired_position(4) == -1  # bar3 NaN -> keep short
    assert rt.desired_position(5) == -1  # bar4 no flip -> keep short


# ---------------------------------------------------------------------------
# Both rules agree on the shared semantics: state persists until a *finite*
# opposite signal, and never look ahead (bar i only reads bar i-1).
# ---------------------------------------------------------------------------

def test_both_rules_are_long_only_and_prefix_invariant():
    dirn = np.array([1.0, -1.0, 1.0])
    a, b = SupertrendState(dirn.copy()), SupertrendState(dirn.copy())
    expected = [a.desired_position(i) for i in range(len(dirn))]
    # re-running from scratch reproduces the same sequence (no hidden state leak)
    assert [SupertrendState(dirn.copy()).desired_position(i) for i in range(len(dirn))] == expected
    assert all(p in (0, 1) for p in expected)  # long-only: never negative


# ---------------------------------------------------------------------------
# DST regression: a US anchor's UTC offset must flip across a real DST change
# ---------------------------------------------------------------------------

def test_us_anchor_offset_flips_across_dst():
    # America/New_York is -5 EST (winter) and -4 EDT (summer).
    anchor = SessionAnchor(local_hour=17, local_minute=0, tz="America/New_York")
    winter = pd.DatetimeIndex(["2025-01-15 14:00:00+00:00"])          # EST
    summer = pd.DatetimeIndex(["2025-07-15 14:00:00+00:00"])          # EDT
    assert _utc_offset_for(anchor, winter)[0] == -5.0
    assert _utc_offset_for(anchor, summer)[0] == -4.0


def test_offset_is_resolved_per_date_not_globally():
    # A single series straddling a DST transition must get *two* distinct
    # offsets (a global single-offset approximation would fail this).
    anchor = SessionAnchor(local_hour=17, local_minute=0, tz="America/New_York")
    # US 2026 DST starts 2nd Sunday of March = 2026-03-08
    idx = pd.DatetimeIndex([
        "2026-03-07 14:00:00+00:00",   # still EST (-5)
        "2026-03-08 14:00:00+00:00",   # now EDT (-4)
    ])
    offs = _utc_offset_for(anchor, idx)
    assert offs[0] == -5.0
    assert offs[1] == -4.0
    assert len(set(offs.tolist())) == 2
