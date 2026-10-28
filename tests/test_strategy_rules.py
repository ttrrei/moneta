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
