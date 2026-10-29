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
from strategy.strategy_cci_reversion_lib import CciReversionState
from strategy.strategy_willr_lib import WillRState
from strategy.strategy_stoch_lib import StochState
from strategy.strategy_macd_lib import MacdState
from strategy.strategy_dual_velocity_lib import DualVelocityState
from strategy.strategy_psar_lib import PsarState
from strategy.strategy_donchian_lib import DonchianState
from strategy.strategy_aroon_lib import AroonState
from strategy.strategy_mfi_lib import MfiState
from strategy.strategy_rsi_slow_lib import RsiSlowState
from strategy.strategy_rsi_lib import RsiState
from strategy.strategy_rsi_trend_lib import RsiTrendState
from strategy.strategy_squeeze_lib import SqueezeState
from strategy.strategy_vwap_stretch_lib import VwapStretchState
from strategy.strategy_cmf_lib import CmfState
from strategy.strategy_multiscale_lib import MultiScaleState
from strategy.strategy_squeeze_slow_lib import SqueezeSlowState
from strategy.strategy_er_lib import ErState
from strategy.strategy_macd_slow_lib import MacdSlowState
from strategy.strategy_atr_band_lib import AtrBandState
from strategy.strategy_chop_lib import ChopReversionState
from strategy.strategy_spread_lib import EmaSpread12State
from strategy.strategy_volmom_lib import VolMomState


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
# RsiState (S-01/S-02): long when the *previous* closed bar's RSI-24 < 30,
# exit when RSI > 55. Long-only, NaN-safe, no lookahead.
# ---------------------------------------------------------------------------

def test_rsi_is_flat_on_bar_zero():
    r = RsiState(np.array([25.0, 25.0]))
    assert r.desired_position(0) == 0  # no previous bar -> flat


def test_rsi_enters_below_30_and_exits_above_55():
    # position at bar i decided from RSI on bar i-1
    r = RsiState(np.array([50.0, 25.0, 40.0, 60.0]))
    assert r.desired_position(1) == 0   # bar0 50  -> flat
    assert r.desired_position(2) == 1   # bar1 25 (<30) -> long
    assert r.desired_position(3) == 1   # bar2 40 (30-55) -> hold long
    assert r.desired_position(4) == 0   # bar3 60 (>55) -> exit flat


def test_rsi_boundary_is_strict():
    # 30.0 is not < 30.0 (no entry); 55.0 is not > 55.0 (no exit)
    r = RsiState(np.array([50.0, 30.0, 29.0, 55.0, 56.0]))
    assert r.desired_position(1) == 0   # bar0 50
    assert r.desired_position(2) == 0   # bar1 30.0 -> not <30 -> flat
    assert r.desired_position(3) == 1   # bar2 29.0 -> <30 -> long
    assert r.desired_position(4) == 1   # bar3 55.0 -> not >55 -> hold
    assert r.desired_position(5) == 0   # bar4 56.0 -> >55 -> exit


def test_rsi_is_nan_safe():
    r = RsiState(np.array([np.nan, 25.0, np.nan, 60.0]))
    assert r.desired_position(1) == 0    # bar0 NaN -> flat
    assert r.desired_position(2) == 1    # bar1 25 -> long
    assert r.desired_position(3) == 1    # bar2 NaN -> hold long
    assert r.desired_position(4) == 0    # bar3 60 -> exit


def test_rsi_is_long_only():
    r = RsiState(np.array([50.0, 25.0, 25.0]))
    assert all(p in (0, 1) for p in [r.desired_position(i) for i in range(3)])


# ---------------------------------------------------------------------------
# RsiTrendState (S-03): long when prev bar RSI-24 < 30 AND close > EMA-24;
# exit when prev bar RSI > 55. The trend filter must gate the entry.
# ---------------------------------------------------------------------------

def test_rsi_trend_is_flat_on_bar_zero():
    s = RsiTrendState(np.array([40.0]), np.array([100.0]), np.array([101.0]))
    assert s.desired_position(0) == 0


def test_rsi_trend_requires_oversold_and_uptrend():
    # entry needs BOTH rsi<30 AND close>ema; either alone must not enter
    rsi = np.array([50.0, 25.0, 25.0, 60.0])
    ema = np.array([100.0, 100.0, 100.0, 100.0])
    close = np.array([101.0, 99.0, 101.0, 101.0])  # bar1 below ema, bar2 above
    s = RsiTrendState(rsi, ema, close)
    assert s.desired_position(1) == 0   # bar0 50 -> flat
    assert s.desired_position(2) == 0   # bar1 rsi25<30 BUT close99<ema100 -> no entry
    assert s.desired_position(3) == 1   # bar2 rsi25<30 AND close101>ema100 -> long
    assert s.desired_position(4) == 0   # bar3 rsi60>55 -> exit


def test_rsi_trend_is_nan_safe():
    s = RsiTrendState(
        np.array([np.nan, 25.0, np.nan, 60.0]),
        np.array([100.0, 100.0, 100.0, 100.0]),
        np.array([101.0, 101.0, 101.0, 101.0]))
    assert s.desired_position(1) == 0   # bar0 NaN -> flat
    assert s.desired_position(2) == 1   # bar1 rsi25<30, close>ema -> long
    assert s.desired_position(3) == 1   # bar2 NaN -> hold
    assert s.desired_position(4) == 0   # bar3 rsi60>55 -> exit


def test_rsi_trend_is_long_only():
    s = RsiTrendState(np.array([50.0, 25.0, 25.0]),
                      np.array([100.0, 100.0, 100.0]),
                      np.array([101.0, 101.0, 101.0]))
    assert all(p in (0, 1) for p in [s.desired_position(i) for i in range(3)])


# ---------------------------------------------------------------------------
# SqueezeState (S-04): two-sided squeeze-onset follower. Enter on the 0->1
# onset taking direction by close-vs-bb_mid at onset; hold for the episode;
# flat once the squeeze turns off. This is the only long/short rule.
# ---------------------------------------------------------------------------

def test_squeeze_is_flat_on_bar_zero():
    q = SqueezeState(np.array([0.0]), np.array([100.0]), np.array([101.0]))
    assert q.desired_position(0) == 0


def test_squeeze_enters_direction_by_close_vs_mid():
    # onset (0->1) decides direction by close vs bb_mid at that bar
    sqz = np.array([0.0, 1.0, 1.0, 0.0, 1.0, 1.0])
    bbmid = np.array([100.0, 100.0, 100.0, 100.0, 100.0, 100.0])
    close = np.array([101.0, 99.0, 101.0, 101.0, 101.0, 101.0])
    q = SqueezeState(sqz, bbmid, close)
    assert q.desired_position(1) == 0     # bar0 squeeze off -> flat
    assert q.desired_position(2) == -1    # bar1 onset, close99<mid100 -> short
    assert q.desired_position(3) == -1    # bar2 squeeze on, hold short (no flip)
    assert q.desired_position(4) == 0     # bar3 squeeze off -> flat
    assert q.desired_position(5) == 1     # bar4 onset, close101>mid100 -> long
    assert q.desired_position(6) == 1     # bar5 squeeze on, hold long


def test_squeeze_holds_onset_direction_no_mid_episode_flip():
    # direction is set at onset only; a close crossing mid mid-episode must NOT flip
    sqz = np.array([0.0, 1.0, 1.0])
    bbmid = np.array([100.0, 100.0, 100.0])
    close = np.array([101.0, 99.0, 101.0])  # onset bar1 short (close<mid), bar2 close>mid
    q = SqueezeState(sqz, bbmid, close)
    assert q.desired_position(2) == -1    # onset short
    assert q.desired_position(3) == -1    # bar2 close>mid but already short -> hold (no churn)


def test_squeeze_is_nan_safe():
    q = SqueezeState(
        np.array([np.nan, 1.0, np.nan, 1.0]),
        np.array([100.0, 100.0, 100.0, 100.0]),
        np.array([101.0, 99.0, 101.0, 101.0]))
    assert q.desired_position(1) == 0     # bar0 NaN -> flat
    assert q.desired_position(2) == -1    # bar1 onset close<mid -> short
    assert q.desired_position(3) == -1    # bar2 NaN -> hold short
    assert q.desired_position(4) == -1    # bar3 squeeze on, already short -> hold


def test_squeeze_is_two_sided():
    # unlike the long-only rules, this one may be short (-1)
    q = SqueezeState(np.array([0.0, 1.0, 1.0]),
                     np.array([100.0, 100.0, 100.0]),
                     np.array([101.0, 99.0, 99.0]))
    assert q.desired_position(2) == -1    # onset short is legal
    assert q.desired_position(3) == -1    # and stays short


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


# ---------------------------------------------------------------------------
# S-08 CciReversionState: enter on CCI down-cross below enter_below while
# bb_pos < 0.5; exit on CCI >= exit_above
# ---------------------------------------------------------------------------

def test_cci_is_flat_on_bar_zero():
    r = CciReversionState(np.array([50.0, 50.0, 50.0]), np.array([0.2, 0.2, 0.2]),
                          np.array([1.0, 1.0, 1.0]), np.array([1.0, 1.0, 1.0]))
    assert r.desired_position(0) == 0


def test_cci_enters_on_dip_and_exits_on_recovery():
    # enter_below=100, exit_above=200 (exit fires when CCI rises back >= 200)
    # bar0=120 (prior), bar1=90 (down-cross below 100 -> enter), bar2=95 (hold), bar3=250 (exit)
    cci = np.array([120.0, 90.0, 95.0, 250.0])
    bb = np.array([0.4, 0.4, 0.4, 0.4])
    r = CciReversionState(cci, bb, np.array([1.0] * 4), np.array([1.0] * 4),
                          enter_below=100.0, exit_above=200.0)
    assert r.desired_position(1) == 0   # bar0=120, not below 100 -> flat
    assert r.desired_position(2) == 1   # bar1: 120->90 down-cross below 100, bb 0.4<0.5 -> long
    assert r.desired_position(3) == 1   # bar2: 95 < 200, not exited -> hold
    assert r.desired_position(4) == 0   # bar3: 250 >= 200 -> exit


def test_cci_requires_band_lower_half():
    cci = np.array([120.0, 90.0])
    bb = np.array([0.9, 0.9])  # upper half -> must not enter
    r = CciReversionState(cci, bb, np.array([1.0, 1.0]), np.array([1.0, 1.0]))
    assert r.desired_position(1) == 0


def test_cci_is_nan_safe():
    # bar0=NaN, bar1=90 (entry, prior NaN treated as entry-eligible), bar2=120 (exit)
    cci = np.array([np.nan, 90.0, 120.0])
    r = CciReversionState(cci, np.array([0.2, 0.2, 0.2]),
                          np.array([1.0, 1.0, 1.0]), np.array([1.0, 1.0, 1.0]))
    assert r.desired_position(1) == 0    # bar0 NaN -> no signal
    assert r.desired_position(2) == 1    # bar1=90 < 100, prior NaN -> entry
    assert r.desired_position(3) == 0    # bar2=120 >= exit_above(-100) -> exit


def test_cci_is_long_only_and_prefix_invariant():
    cci = np.array([120.0, 90.0, -120.0, 150.0])
    bb = np.array([0.2, 0.2, 0.2, 0.2])
    def seq():
        r = CciReversionState(cci.copy(), bb.copy(), np.array([1.0]*4), np.array([1.0]*4))
        return [r.desired_position(i) for i in range(4)]
    assert seq() == seq()
    assert all(p in (0, 1) for p in seq())


# ---------------------------------------------------------------------------
# S-09 WillRState: enter on willr down-cross below enter_below; exit on
# up-cross above exit_above; cooldown blocks immediate re-entry
# ---------------------------------------------------------------------------

def test_willr_is_flat_on_bar_zero():
    w = WillRState(np.array([-80.0, -80.0, -80.0]), np.array([1.0]*3), np.array([1.0]*3))
    assert w.desired_position(0) == 0


def test_willr_enters_on_washout_and_exits_on_recovery():
    # bar0=-50 (prior), bar1=-80 (down-cross below -70), bar2=-75 (hold), bar3=-30 (exit)
    willr = np.array([-50.0, -80.0, -75.0, -30.0])
    w = WillRState(willr, np.array([1.0]*4), np.array([1.0]*4),
                   enter_below=-70.0, exit_above=-40.0)
    assert w.desired_position(1) == 0   # bar0=-50, not below -70 -> flat
    assert w.desired_position(2) == 1   # bar1: -50->-80 down-cross below -70 -> long
    assert w.desired_position(3) == 1   # bar2: -75 still below -70, not exited -> hold
    assert w.desired_position(4) == 0   # bar3: -75->-30 up-cross above -40 -> exit


def test_willr_cooldown_blocks_immediate_reentry():
    # bar0=-50, bar1=-80 (enter), bar2=-30 (exit, cooldown=3 blocks i=3,4,5),
    # bar3=-80 (fresh washout but re-entry refused during cooldown)
    willr = np.array([-50.0, -80.0, -30.0, -80.0, -80.0])
    w = WillRState(willr, np.array([1.0]*5), np.array([1.0]*5),
                   enter_below=-70.0, exit_above=-40.0, cooldown=3)
    assert w.desired_position(1) == 0   # bar0=-50 -> flat
    assert w.desired_position(2) == 1   # bar1 washout -> enter
    assert w.desired_position(3) == 0   # bar2 recovery -> exit; cooldown blocks i=3,4,5
    assert w.desired_position(4) == 0   # bar3 washout, but i=4 < cooldown_until(6) -> blocked


def test_willr_is_nan_safe():
    willr = np.array([np.nan, -80.0, -30.0])
    w = WillRState(willr, np.array([1.0]*3), np.array([1.0]*3))
    assert w.desired_position(1) == 0
    assert w.desired_position(2) == 1    # -80 entry
    assert w.desired_position(3) == 0    # -30 exit


def test_willr_is_long_only_and_prefix_invariant():
    willr = np.array([-50.0, -80.0, -30.0, -85.0])
    def seq():
        w = WillRState(willr.copy(), np.array([1.0]*4), np.array([1.0]*4))
        return [w.desired_position(i) for i in range(4)]
    assert seq() == seq()
    assert all(p in (0, 1) for p in seq())


# ---------------------------------------------------------------------------
# S-10 StochState: enter on K up-cross of D while K < k_below; exit on
# K down-cross of D
# ---------------------------------------------------------------------------

def test_stoch_is_flat_on_bar_zero():
    s = StochState(np.array([10.0, 20.0, 30.0]), np.array([15.0, 20.0, 25.0]),
                   np.array([1.0]*3), np.array([1.0]*3))
    assert s.desired_position(0) == 0


def test_stoch_enters_on_oversold_turn_and_exits_on_downcross():
    k = np.array([50.0, 40.0, 22.0, 28.0])
    d = np.array([45.0, 42.0, 28.0, 25.0])
    s = StochState(k, d, np.array([1.0]*4), np.array([1.0]*4), k_below=30.0)
    assert s.desired_position(1) == 0   # bar0: no prior bar -> no cross
    assert s.desired_position(2) == 0   # bar1: K40>D42? no -> no cross
    assert s.desired_position(3) == 0   # bar2: K22>D28? no -> no cross
    assert s.desired_position(4) == 1   # bar3: K28>D25 cross up, K28<30 -> long


def test_stoch_requires_oversold_region():
    k = np.array([60.0, 55.0, 80.0])
    d = np.array([55.0, 60.0, 78.0])
    s = StochState(k, d, np.array([1.0]*3), np.array([1.0]*3), k_below=30.0)
    # bar1 crosses up through D but K=55 is far above k_below=30 -> no entry
    assert s.desired_position(1) == 0
    assert s.desired_position(2) == 0
    assert s.desired_position(3) == 0


def test_stoch_is_nan_safe():
    k = np.array([np.nan, 25.0, 28.0])
    d = np.array([np.nan, 30.0, 25.0])
    s = StochState(k, d, np.array([1.0]*3), np.array([1.0]*3), k_below=30.0)
    assert s.desired_position(1) == 0   # bar0 NaN -> no signal
    assert s.desired_position(2) == 0   # bar1 has no prior finite bar -> no cross
    assert s.desired_position(3) == 1   # bar2 K28>D25 cross up, K28<30 -> long


# ---------------------------------------------------------------------------
# S-11 MacdState: enter on MACD up-cross of 0 with ATR-normalised magnitude;
# exit on down-cross of 0
# ---------------------------------------------------------------------------

def test_macd_is_flat_on_bar_zero():
    m = MacdState(np.array([0.1, 0.1, 0.1]), np.array([0.1, 0.1, 0.1]),
                  np.array([1.0, 1.0, 1.0]), np.array([1.0]*3), np.array([1.0]*3))
    assert m.desired_position(0) == 0


def test_macd_enters_on_positive_cross_and_exits_on_negative_cross():
    macd = np.array([-0.5, 0.5, 0.4, -0.3])
    hist = np.array([-0.5, 0.5, 0.4, -0.3])
    atr = np.array([1.0, 1.0, 1.0, 1.0])
    m = MacdState(macd, hist, atr, np.array([1.0]*4), np.array([1.0]*4), atr_min=0.05)
    assert m.desired_position(1) == 0   # bar0 no prior
    assert m.desired_position(2) == 1   # bar1 -0.5->0.5 cross up, |0.5|/1.0>=0.05 -> long
    assert m.desired_position(3) == 1   # 0.4 still >0, hold
    assert m.desired_position(4) == 0   # 0.4 -> -0.3 cross down -> exit


def test_macd_atr_filter_blocks_noise_cross():
    macd = np.array([-0.001, 0.001])
    hist = np.array([-0.001, 0.001])
    atr = np.array([1.0, 1.0])
    m = MacdState(macd, hist, atr, np.array([1.0, 1.0]), np.array([1.0, 1.0]), atr_min=0.05)
    # |0.001|/1.0 = 0.001 < 0.05 -> must NOT enter
    assert m.desired_position(1) == 0


def test_macd_is_nan_safe():
    # bar0=NaN, bar1=0.5 (up-cross from NaN -> entry), bar2=-0.5 (down-cross -> exit)
    macd = np.array([np.nan, 0.5, -0.5])
    hist = np.array([np.nan, 0.5, -0.5])
    m = MacdState(macd, hist, np.array([1.0, 1.0, 1.0]),
                  np.array([1.0]*3), np.array([1.0]*3), atr_min=0.05)
    assert m.desired_position(1) == 0   # bar0 NaN -> no signal
    assert m.desired_position(2) == 1   # bar1 up-cross, |0.5|/1>=0.05 -> long
    assert m.desired_position(3) == 0   # bar2 down-cross -> exit


def test_macd_is_long_only_and_prefix_invariant():
    macd = np.array([-0.5, 0.5, -0.5, 0.5])
    def seq():
        m = MacdState(macd.copy(), macd.copy(), np.array([1.0]*4),
                      np.array([1.0]*4), np.array([1.0]*4))
        return [m.desired_position(i) for i in range(4)]
    assert seq() == seq()
    assert all(p in (0, 1) for p in seq())


# ---------------------------------------------------------------------------
# S-12 DualVelocityState: hold long while roc>0 AND slow-ema rising
# ---------------------------------------------------------------------------

def test_dual_velocity_is_flat_on_bar_zero():
    dv = DualVelocityState(np.array([0.1, 0.1, 0.1]), np.array([1.0, 1.0, 1.0]),
                           np.array([1.0]*3), np.array([1.0]*3))
    assert dv.desired_position(0) == 0


def test_dual_velocity_requires_both_velocities():
    roc = np.array([0.1, 0.1, -0.1, 0.1])
    ema_slow = np.array([100.0, 100.0, 101.0, 100.5])  # rising then falling
    # slope_lag=24 > len, so slow slope not computable -> flat throughout (guard)
    dv = DualVelocityState(roc, ema_slow, np.array([1.0]*4), np.array([1.0]*4),
                           slope_lag=24)
    for i in range(1, 4):
        assert dv.desired_position(i) == 0  # slope not computable (short array)


def test_dual_velocity_enters_when_both_hold_and_exits_when_rock_turns():
    # slope_lag=1: j reads ema_slow[j-1] as the comparison base.
    # i=1: j=0, roc[0]>0, ema_slow[0]=100 vs ema_slow[0] -> not rising -> flat
    # i=2: j=1, roc[1]>0, ema_slow[1]=101 > ema_slow[0]=100 -> enter
    # i=3: j=2, roc[2]=-0.1 -> exit
    # i=4: j=3, roc[3]>0, ema_slow[3]=101 vs ema_slow[2]=102 -> not rising -> flat
    # i=5: j=4, roc[4]>0, ema_slow[4]=102 > ema_slow[3]=101 -> enter
    roc = np.array([0.1, 0.1, -0.1, 0.1, 0.1])
    ema_slow = np.array([100.0, 101.0, 102.0, 101.0, 102.0])
    dv = DualVelocityState(roc, ema_slow, np.array([1.0]*5), np.array([1.0]*5),
                           slope_lag=1)
    assert dv.desired_position(1) == 0
    assert dv.desired_position(2) == 1
    assert dv.desired_position(3) == 0
    assert dv.desired_position(4) == 0
    assert dv.desired_position(5) == 1


def test_dual_velocity_is_nan_safe():
    roc = np.array([np.nan, 0.1, -0.1])
    dv = DualVelocityState(roc, np.array([100.0, 101.0, 100.0]),
                           np.array([1.0]*3), np.array([1.0]*3), slope_lag=1)
    assert dv.desired_position(1) == 0
    assert dv.desired_position(2) == 1
    assert dv.desired_position(3) == 0


# ---------------------------------------------------------------------------
# S-13 PsarState: long while previous bar's PSAR direction is up
# ---------------------------------------------------------------------------

def test_psar_is_flat_on_bar_zero():
    p = PsarState(np.array([1.0, 1.0, 1.0]))
    assert p.desired_position(0) == 0


def test_psar_follows_previous_direction():
    p = PsarState(np.array([-1.0, 1.0, 1.0, -1.0, 1.0]))
    assert p.desired_position(1) == 0   # bar0 down
    assert p.desired_position(2) == 1   # bar1 up -> long
    assert p.desired_position(3) == 1   # bar2 up -> long
    assert p.desired_position(4) == 0   # bar3 down -> flat
    assert p.desired_position(5) == 1   # bar4 up -> long


def test_psar_is_nan_safe():
    p = PsarState(np.array([np.nan, 1.0, np.nan, -1.0]))
    assert p.desired_position(1) == 0
    assert p.desired_position(2) == 1
    assert p.desired_position(3) == 1
    assert p.desired_position(4) == 0


def test_psar_is_long_only_and_prefix_invariant():
    d = np.array([-1.0, 1.0, -1.0, 1.0])
    def seq():
        p = PsarState(d.copy())
        return [p.desired_position(i) for i in range(4)]
    assert seq() == seq()
    assert all(x in (0, 1) for x in seq())


# ---------------------------------------------------------------------------
# S-14 DonchianState: long while close > dc_mid; th adds entry hysteresis
# ---------------------------------------------------------------------------

def test_donchian_is_flat_on_bar_zero():
    dn = DonchianState(np.array([1.0, 1.0, 1.0]), np.array([1.0, 1.0, 1.0]),
                       np.array([1.0, 1.0, 1.0]))
    assert dn.desired_position(0) == 0


def test_donchian_enters_above_mid_and_exits_at_or_below_mid():
    close = np.array([10.0, 11.0, 9.5, 11.0])
    mid = np.array([10.0, 10.5, 10.0, 10.5])
    upper = np.array([11.0, 11.5, 11.0, 11.5])
    dn = DonchianState(close, mid, upper)
    assert dn.desired_position(1) == 0   # bar0 close 10 == mid 10 -> not > -> flat
    assert dn.desired_position(2) == 1   # bar1 close 11 > mid 10.5 -> long
    assert dn.desired_position(3) == 0   # bar2 close 9.5 <= mid 10 -> exit
    assert dn.desired_position(4) == 1   # bar3 close 11 > mid 10.5 -> re-enter


def test_donchian_hysteresis_th_blocks_entry_in_upper_half_below_threshold():
    # half = 0.5*(upper-mid) = 1.0; threshold = mid + th*half = 10 + th
    # th=0.7 -> threshold 10.7: bar1=10.6 blocked, bar2=11.5 enters
    close = np.array([10.0, 10.6, 11.5])
    mid = np.array([10.0, 10.0, 10.0])
    upper = np.array([12.0, 12.0, 12.0])
    dn = DonchianState(close, mid, upper, th=0.7)
    assert dn.desired_position(1) == 0   # bar0 10 not > 10.7 -> flat
    assert dn.desired_position(2) == 0   # bar1 10.6 not > 10.7 -> still flat
    assert dn.desired_position(3) == 1   # bar2 11.5 > 10.7 -> long


def test_donchian_is_nan_safe():
    dn = DonchianState(np.array([10.0, 11.0, 9.0]),
                       np.array([np.nan, 10.0, 10.0]),
                       np.array([np.nan, 11.0, 11.0]))
    assert dn.desired_position(1) == 0   # bar0 mid NaN
    assert dn.desired_position(2) == 1   # bar1 11>10 -> long
    assert dn.desired_position(3) == 0   # bar2 9<=10 -> exit


def test_donchian_is_long_only_and_prefix_invariant():
    close = np.array([10.0, 11.0, 9.0, 11.0])
    mid = np.array([10.0, 10.5, 10.0, 10.5])
    upper = np.array([11.0, 11.5, 11.0, 11.5])
    def seq():
        dn = DonchianState(close.copy(), mid.copy(), upper.copy())
        return [dn.desired_position(i) for i in range(4)]
    assert seq() == seq()
    assert all(x in (0, 1) for x in seq())


# ---------------------------------------------------------------------------
# S-15 AroonState: enter on aroon_up up-cross through up_at while aroon_down
# < down_below; exit on aroon_up falling to/below up_exit
# ---------------------------------------------------------------------------

def test_aroon_is_flat_on_bar_zero():
    a = AroonState(np.array([80.0, 80.0, 80.0]), np.array([20.0, 20.0, 20.0]),
                   np.array([1.0]*3), np.array([1.0]*3))
    assert a.desired_position(0) == 0


def test_aroon_enters_on_fresh_high_and_exits_on_fade():
    up = np.array([50.0, 80.0, 75.0, 60.0])
    down = np.array([20.0, 20.0, 20.0, 20.0])
    a = AroonState(up, down, np.array([1.0]*4), np.array([1.0]*4),
                   up_at=70.0, up_exit=70.0, down_below=30.0)
    assert a.desired_position(1) == 0   # bar0 up 50 no cross
    assert a.desired_position(2) == 1   # bar1 50->80 cross up >=70, down 20<30 -> long
    assert a.desired_position(3) == 1   # bar2 up 75 still >= up_exit 70 -> hold
    assert a.desired_position(4) == 0   # bar3 up 60 <= 70 -> exit


def test_aroon_requires_low_down_indicator():
    up = np.array([50.0, 80.0])
    down = np.array([20.0, 40.0])  # bar1 down 40 >= 30 -> blocked
    a = AroonState(up, down, np.array([1.0, 1.0]), np.array([1.0, 1.0]))
    assert a.desired_position(1) == 0   # bar0 no cross
    assert a.desired_position(2) == 0   # bar1 cross but down too high -> no entry


def test_aroon_is_nan_safe():
    up = np.array([np.nan, 80.0, 60.0])
    down = np.array([np.nan, 20.0, 20.0])
    a = AroonState(up, down, np.array([1.0]*3), np.array([1.0]*3))
    assert a.desired_position(1) == 0
    assert a.desired_position(2) == 1   # 80 entry (prior nan treated as cross)
    assert a.desired_position(3) == 0   # 60 <= 70 exit


def test_aroon_is_long_only_and_prefix_invariant():
    up = np.array([50.0, 80.0, 60.0, 80.0])
    down = np.array([20.0, 20.0, 20.0, 20.0])
    def seq():
        a = AroonState(up.copy(), down.copy(), np.array([1.0]*4), np.array([1.0]*4))
        return [a.desired_position(i) for i in range(4)]
    assert seq() == seq()
    assert all(x in (0, 1) for x in seq())


# ---------------------------------------------------------------------------
# S-16 MfiState: enter on MFI down-cross below enter_below; exit on MFI >=
# exit_above
# ---------------------------------------------------------------------------

def test_mfi_is_flat_on_bar_zero():
    m = MfiState(np.array([15.0, 15.0, 15.0]), np.array([1.0]*3), np.array([1.0]*3))
    assert m.desired_position(0) == 0


def test_mfi_enters_on_volume_exhaustion_and_exits_on_recovery():
    mfi = np.array([30.0, 15.0, 20.0, 55.0])
    m = MfiState(mfi, np.array([1.0]*4), np.array([1.0]*4),
                 enter_below=20.0, exit_above=50.0)
    assert m.desired_position(1) == 0   # bar0 no prior
    assert m.desired_position(2) == 1   # bar1 30->15 cross down <20 -> long
    assert m.desired_position(3) == 1   # bar2 20 >= 20? no (>=exit? 20<50) hold
    assert m.desired_position(4) == 0   # bar3 55 >= 50 -> exit


def test_mfi_is_nan_safe():
    mfi = np.array([np.nan, 15.0, 55.0])
    m = MfiState(mfi, np.array([1.0]*3), np.array([1.0]*3))
    assert m.desired_position(1) == 0
    assert m.desired_position(2) == 1
    assert m.desired_position(3) == 0


def test_mfi_is_long_only_and_prefix_invariant():
    mfi = np.array([30.0, 15.0, 55.0, 15.0])
    def seq():
        m = MfiState(mfi.copy(), np.array([1.0]*4), np.array([1.0]*4))
        return [m.desired_position(i) for i in range(4)]
    assert seq() == seq()
    assert all(x in (0, 1) for x in seq())


# ---------------------------------------------------------------------------
# S-17 RsiSlowState: enter on rsi_60 < enter_below (gated); exit on rsi >=
# exit_above
# ---------------------------------------------------------------------------

def test_rsi_slow_is_flat_on_bar_zero():
    r = RsiSlowState(np.array([25.0, 25.0, 25.0]), np.array([30.0]*3),
                     np.array([1.0]*3))
    assert r.desired_position(0) == 0


def test_rsi_slow_enters_below_30_and_exits_above_50():
    rsi = np.array([40.0, 25.0, 45.0, 55.0])
    r = RsiSlowState(rsi, np.array([30.0]*4), np.array([1.0]*4),
                     enter_below=30.0, exit_above=50.0)
    assert r.desired_position(1) == 0   # bar0 40 not <30
    assert r.desired_position(2) == 1   # bar1 25 <30 -> long
    assert r.desired_position(3) == 1   # bar2 45 <50 -> hold
    assert r.desired_position(4) == 0   # bar3 55 >=50 -> exit


def test_rsi_slow_st_gate_blocks_entry_when_direction_down():
    rsi = np.array([40.0, 25.0])
    adx = np.array([30.0, 30.0])
    st = np.array([-1.0, -1.0])  # direction down -> st_gate blocks
    r = RsiSlowState(rsi, adx, st, enter_below=30.0, exit_above=50.0, st_gate=True)
    assert r.desired_position(1) == 0
    assert r.desired_position(2) == 0


def test_rsi_slow_adx_gate_blocks_entry_when_adx_weak():
    rsi = np.array([40.0, 25.0])
    adx = np.array([30.0, 15.0])  # bar1 adx 15 <= 20 -> adx_gate blocks
    st = np.array([1.0, 1.0])
    r = RsiSlowState(rsi, adx, st, enter_below=30.0, exit_above=50.0,
                     adx_gate=True, adx_at=20.0)
    assert r.desired_position(1) == 0
    assert r.desired_position(2) == 0


def test_rsi_slow_is_nan_safe():
    rsi = np.array([np.nan, 25.0, 55.0])
    r = RsiSlowState(rsi, np.array([30.0]*3), np.array([1.0]*3))
    assert r.desired_position(1) == 0
    assert r.desired_position(2) == 1
    assert r.desired_position(3) == 0


def test_rsi_slow_is_long_only_and_prefix_invariant():
    rsi = np.array([40.0, 25.0, 55.0, 25.0])
    def seq():
        r = RsiSlowState(rsi.copy(), np.array([30.0]*4), np.array([1.0]*4))
        return [r.desired_position(i) for i in range(4)]
    assert seq() == seq()
    assert all(x in (0, 1) for x in seq())


# ---------------------------------------------------------------------------
# Optional ema_gate variants (used by improvement iterations): a gate that
# requires the *previous* bar's close > ema_24 to enter.
# ---------------------------------------------------------------------------

def test_cci_ema_gate_blocks_entry_when_close_below_ema():
    # bar1 is the cross; close[1]=0.9 <= ema[1]=1.0 -> entry blocked
    r = CciReversionState(
        np.array([120.0, 90.0, 90.0]), np.array([0.2, 0.2, 0.2]),
        close=np.array([1.0, 0.9, 1.0]), ema=np.array([1.0, 1.0, 1.0]),
        ema_gate=True)
    assert r.desired_position(2) == 0


def test_cci_ema_gate_allows_entry_when_close_above_ema():
    r = CciReversionState(
        np.array([120.0, 90.0, 90.0]), np.array([0.2, 0.2, 0.2]),
        close=np.array([1.0, 1.1, 1.0]), ema=np.array([1.0, 1.0, 1.0]),
        ema_gate=True)
    assert r.desired_position(2) == 1


def test_willr_ema_gate_blocks_entry_when_close_below_ema():
    w = WillRState(np.array([-50.0, -80.0, -80.0]), close=np.array([1.0, 0.9, 1.0]),
                   ema=np.array([1.0, 1.0, 1.0]), ema_gate=True)
    assert w.desired_position(2) == 0


def test_willr_ema_gate_allows_entry_when_close_above_ema():
    w = WillRState(np.array([-50.0, -80.0, -80.0]), close=np.array([1.0, 1.1, 1.0]),
                   ema=np.array([1.0, 1.0, 1.0]), ema_gate=True)
    assert w.desired_position(2) == 1


def test_stoch_ema_gate_blocks_entry_when_close_below_ema():
    s = StochState(np.array([50.0, 28.0, 28.0]), np.array([55.0, 25.0, 25.0]),
                   close=np.array([1.0, 0.9, 1.0]), ema=np.array([1.0, 1.0, 1.0]),
                   k_below=30.0, ema_gate=True)
    assert s.desired_position(2) == 0


def test_stoch_ema_gate_allows_entry_when_close_above_ema():
    s = StochState(np.array([50.0, 28.0, 28.0]), np.array([55.0, 25.0, 25.0]),
                   close=np.array([1.0, 1.1, 1.0]), ema=np.array([1.0, 1.0, 1.0]),
                   k_below=30.0, ema_gate=True)
    assert s.desired_position(2) == 1


def test_macd_ema_gate_blocks_entry_when_close_below_ema():
    m = MacdState(np.array([-0.5, 0.5, 0.5]), np.array([-0.5, 0.5, 0.5]),
                  np.array([1.0, 1.0, 1.0]),
                  close=np.array([1.0, 0.9, 1.0]), ema=np.array([1.0, 1.0, 1.0]),
                  atr_min=0.05, ema_gate=True)
    assert m.desired_position(2) == 0


def test_macd_ema_gate_allows_entry_when_close_above_ema():
    m = MacdState(np.array([-0.5, 0.5, 0.5]), np.array([-0.5, 0.5, 0.5]),
                  np.array([1.0, 1.0, 1.0]),
                  close=np.array([1.0, 1.1, 1.0]), ema=np.array([1.0, 1.0, 1.0]),
                  atr_min=0.05, ema_gate=True)
    assert m.desired_position(2) == 1


def test_dual_velocity_ema_gate_blocks_entry_when_close_below_ema():
    dv = DualVelocityState(np.array([0.1, 0.1, 0.1]), np.array([100.0, 101.0, 101.0]),
                           close=np.array([1.0, 0.9, 1.0]),
                           ema_fast=np.array([1.0, 1.0, 1.0]),
                           slope_lag=1, ema_gate=True)
    assert dv.desired_position(2) == 0


def test_dual_velocity_ema_gate_allows_entry_when_close_above_ema():
    dv = DualVelocityState(np.array([0.1, 0.1, 0.1]), np.array([100.0, 101.0, 101.0]),
                           close=np.array([1.0, 1.1, 1.0]),
                           ema_fast=np.array([1.0, 1.0, 1.0]),
                           slope_lag=1, ema_gate=True)
    assert dv.desired_position(2) == 1


def test_aroon_ema_gate_blocks_entry_when_close_below_ema():
    a = AroonState(np.array([50.0, 80.0, 80.0]), np.array([20.0, 20.0, 20.0]),
                   close=np.array([1.0, 0.9, 1.0]), ema=np.array([1.0, 1.0, 1.0]),
                   ema_gate=True)
    assert a.desired_position(2) == 0


def test_aroon_ema_gate_allows_entry_when_close_above_ema():
    a = AroonState(np.array([50.0, 80.0, 80.0]), np.array([20.0, 20.0, 20.0]),
                   close=np.array([1.0, 1.1, 1.0]), ema=np.array([1.0, 1.0, 1.0]),
                   ema_gate=True)
    assert a.desired_position(2) == 1


def test_mfi_ema_gate_blocks_entry_when_close_below_ema():
    m = MfiState(np.array([30.0, 15.0, 15.0]), close=np.array([1.0, 0.9, 1.0]),
                 ema=np.array([1.0, 1.0, 1.0]), ema_gate=True)
    assert m.desired_position(2) == 0


def test_mfi_ema_gate_allows_entry_when_close_above_ema():
    m = MfiState(np.array([30.0, 15.0, 15.0]), close=np.array([1.0, 1.1, 1.0]),
                 ema=np.array([1.0, 1.0, 1.0]), ema_gate=True)
    assert m.desired_position(2) == 1


# ===========================================================================
# Batch 2 (S-18 .. S-27): deterministic rule tests
# ===========================================================================

# --- S-18 VwapStretchState: cross of (close-vwap)/atr above k ---------------

def test_vwap_flat_on_bar_zero():
    s = VwapStretchState(np.array([0.0]), np.array([1.0]),
                         np.array([1.0]), np.array([1.0]))
    assert s.desired_position(0) == 0


def test_vwap_enters_on_upward_cross_of_k():
    d = np.array([-1.0, 0.4, 0.4, -0.5])
    atr = np.ones(4)
    s = VwapStretchState(d, atr, np.ones(4), np.ones(4), k=0.25)
    assert s.desired_position(1) == 0  # bar0 -1.0 not above k
    assert s.desired_position(2) == 1  # bar1 0.4 crossed above 0.25
    assert s.desired_position(3) == 1  # bar2 0.4 stays >= k_exit 0.0
    assert s.desired_position(4) == 0  # bar3 -0.5 < k_exit -> exit


def test_vwap_requires_a_cross_not_just_above():
    # already above k at bar0 -> no fresh cross at bar1 -> no entry
    d = np.array([0.5, 0.5, 0.5])
    s = VwapStretchState(d, np.ones(3), np.ones(3), np.ones(3), k=0.25)
    assert s.desired_position(2) == 0


def test_vwap_ema_gate_blocks_entry_when_close_below_ema():
    s = VwapStretchState(np.array([-0.5, 0.4]), np.ones(2),
                         close=np.array([1.0, 0.9]), ema=np.array([1.0, 1.0]),
                         k=0.25, ema_gate=True)
    assert s.desired_position(2) == 0


def test_vwap_nan_safe():
    d = np.array([np.nan, 0.4, 0.4, -0.6])
    s = VwapStretchState(d, np.ones(4), np.ones(4), np.ones(4), k=0.25)
    assert s.desired_position(1) == 0   # bar0 NaN -> flat preserved
    assert s.desired_position(2) == 1   # bar1 0.4 > k (prev non-finite) -> enter
    assert s.desired_position(3) == 1   # bar2 0.4 still >= k_exit
    assert s.desired_position(4) == 0   # bar3 -0.6 < k_exit -> exit


# --- S-19 CmfState: cross of cmf above k, exit below 0 ----------------------

def test_cmf_flat_on_bar_zero():
    s = CmfState(np.array([0.0]), np.array([1.0]), np.array([1.0]))
    assert s.desired_position(0) == 0


def test_cmf_enters_on_upward_cross_above_k_and_exits_below_zero():
    cmf = np.array([-0.1, 0.10, 0.05, -0.2])
    s = CmfState(cmf, np.ones(4), np.ones(4), k=0.05)
    assert s.desired_position(1) == 0   # bar0 -0.1 not above k
    assert s.desired_position(2) == 1   # bar1 0.10 crossed above 0.05
    assert s.desired_position(3) == 1   # bar2 0.05 still >= 0
    assert s.desired_position(4) == 0   # bar3 crossed below 0


def test_cmf_no_entry_without_cross():
    # already above k at bar0 -> no fresh cross at bar1
    s = CmfState(np.array([0.10, 0.10]), np.ones(2), np.ones(2), k=0.05)
    assert s.desired_position(2) == 0


def test_cmf_ema_gate_blocks_entry_when_close_below_ema():
    s = CmfState(np.array([-0.1, 0.10, -0.10, 0.10]),
                 close=np.array([1.0, 0.9, 0.9, 1.1]),
                 ema=np.array([1.0, 1.0, 1.0, 1.0]),
                 k=0.05, ema_gate=True)
    # bar1 fresh cross above k but close<ema -> blocked
    assert s.desired_position(2) == 0
    # bar3 fresh cross above k (prev -0.10) and close>ema -> allowed
    assert s.desired_position(4) == 1


def test_cmf_nan_safe():
    cmf = np.array([np.nan, 0.10, 0.05, -0.2])
    s = CmfState(cmf, np.ones(4), np.ones(4), k=0.05)
    assert s.desired_position(1) == 0
    assert s.desired_position(2) == 1   # bar1 crossed above k (prev NaN)
    assert s.desired_position(4) == 0   # exit below 0


# --- S-20 MultiScaleState: short up-flip gated by long-scale direction -------

def test_multiscale_flat_on_bar_zero():
    s = MultiScaleState(np.array([1.0]), [])
    assert s.desired_position(0) == 0


def test_multiscale_enters_on_upflip_when_gate_up():
    short = np.array([0.0, 1.0, 1.0, 0.0])
    gate = np.array([1.0, 1.0, 1.0, 1.0])
    s = MultiScaleState(short, [gate])
    assert s.desired_position(1) == 0   # bar0 short 0
    assert s.desired_position(2) == 1   # bar1 upflip, gate up
    assert s.desired_position(3) == 1   # bar2 still up
    assert s.desired_position(4) == 0   # bar3 short down


def test_multiscale_blocked_when_gate_down():
    short = np.array([0.0, 1.0])
    gate = np.array([1.0, 0.0])
    s = MultiScaleState(short, [gate])
    assert s.desired_position(2) == 0   # gate down -> no entry


def test_multiscale_no_entry_without_fresh_flip():
    # short already up at bar0 -> bar1 is not a fresh flip
    short = np.array([1.0, 1.0])
    gate = np.array([1.0, 1.0])
    s = MultiScaleState(short, [gate])
    assert s.desired_position(2) == 0


def test_multiscale_multiple_gates_all_must_agree():
    short = np.array([0.0, 1.0])
    g1 = np.array([1.0, 1.0])
    g2 = np.array([1.0, 0.0])
    s = MultiScaleState(short, [g1, g2])
    assert s.desired_position(2) == 0   # g2 down -> blocked


# --- S-21 SqueezeSlowState: regime on + close above mid ---------------------

def test_squeezeslow_flat_on_bar_zero():
    s = SqueezeSlowState(np.array([1.0]), np.array([1.0]),
                         np.array([1.0]), np.array([1.0]))
    assert s.desired_position(0) == 0


def test_squeezeslow_long_while_on_and_above_mid():
    sqz = np.array([0.0, 1.0, 1.0, 0.0])
    mid = np.array([1.0, 1.0, 1.0, 1.0])
    close = np.array([1.0, 1.1, 0.9, 1.1])
    s = SqueezeSlowState(sqz, mid, close, np.ones(4))
    assert s.desired_position(1) == 0   # bar0 sqz off
    assert s.desired_position(2) == 1   # bar1 on + close>mid
    assert s.desired_position(3) == 0   # bar2 on but close<=mid -> exit
    assert s.desired_position(4) == 0   # bar3 sqz off


def test_squeezeslow_onset_only_requires_fresh_turn():
    # bar0 already on -> bar1 is not a fresh 0->1 turn under onset_only
    sqz = np.array([1.0, 1.0])
    s = SqueezeSlowState(sqz, np.array([1.0, 1.0]),
                         np.array([1.1, 1.1]), np.ones(2), onset_only=True)
    assert s.desired_position(2) == 0


def test_squeezeslow_nan_safe():
    sqz = np.array([np.nan, 1.0, 1.0])
    s = SqueezeSlowState(sqz, np.array([1.0, 1.0, 1.0]),
                         np.array([1.1, 1.1, 1.1]), np.ones(3))
    assert s.desired_position(1) == 0   # bar0 NaN -> flat preserved
    assert s.desired_position(2) == 1   # bar1 on + above mid -> enter
    assert s.desired_position(3) == 1   # bar2 still on + above mid


# --- S-22 ErState: regime er>k and close>ema --------------------------------

def test_er_flat_on_bar_zero():
    s = ErState(np.array([0.5]), np.array([1.0]), np.array([1.0]))
    assert s.desired_position(0) == 0


def test_er_long_while_efficient_and_above_ema():
    er = np.array([0.2, 0.5, 0.4, 0.5])
    close = np.array([1.0, 1.1, 0.9, 1.1])
    ema = np.array([1.0, 1.0, 1.0, 1.0])
    s = ErState(er, close, ema, k=0.30)
    assert s.desired_position(1) == 0   # bar0 er 0.2 < k
    assert s.desired_position(2) == 1   # bar1 er 0.5>k, close>ema
    assert s.desired_position(3) == 0   # bar2 close<=ema -> flat
    assert s.desired_position(4) == 1   # bar1/3 back above


def test_er_blocks_when_below_ema_even_if_efficient():
    s = ErState(np.array([0.5, 0.5]), close=np.array([1.0, 0.9]),
                ema=np.array([1.0, 1.0]), k=0.30)
    assert s.desired_position(2) == 0


def test_er_nan_safe():
    s = ErState(np.array([np.nan, 0.5]), np.array([1.0, 1.1]),
                np.array([1.0, 1.0]), k=0.30)
    assert s.desired_position(1) == 0
    assert s.desired_position(2) == 1


# --- S-23 MacdSlowState: long while hist > th, hysteresis exit --------------

def test_macdslow_flat_on_bar_zero():
    s = MacdSlowState(np.array([0.0]))
    assert s.desired_position(0) == 0


def test_macdslow_long_while_hist_positive():
    s = MacdSlowState(np.array([0.0, 0.2, -0.1, 0.2]))
    assert s.desired_position(1) == 0   # bar0 0.0 not > 0
    assert s.desired_position(2) == 1   # bar1 0.2
    assert s.desired_position(3) == 0   # bar2 -0.1 <= 0
    assert s.desired_position(4) == 1   # bar3 0.2


def test_macdslow_hysteresis_holds_while_above_exit():
    # th=0.1 entry, th_exit=-0.1: hist 0.05 is below entry but above exit
    s = MacdSlowState(np.array([0.0, 0.2, 0.05]), th=0.1, th_exit=-0.1)
    assert s.desired_position(2) == 1   # bar1 0.2 > 0.1 -> enter
    assert s.desired_position(3) == 1   # bar2 0.05 still > -0.1 (hysteresis)


def test_macdslow_nan_safe():
    s = MacdSlowState(np.array([np.nan, 0.2, -0.2]))
    assert s.desired_position(1) == 0
    assert s.desired_position(2) == 1
    assert s.desired_position(3) == 0


# --- S-24 AtrBandState: long while (close-ema)/atr >= k ---------------------

def test_atrband_flat_on_bar_zero():
    s = AtrBandState(np.array([1.0]), np.array([1.0]), np.array([1.0]))
    assert s.desired_position(0) == 0


def test_atrband_enters_when_band_wide_and_exits_when_narrow():
    close = np.array([1.0, 2.0, 1.3, 1.2])
    ema = np.array([1.0, 1.0, 1.0, 1.0])
    atr = np.ones(4)
    s = AtrBandState(close, ema, atr, k=1.0, k_exit=0.5)
    assert s.desired_position(1) == 0   # bar0 r=0
    assert s.desired_position(2) == 1   # bar1 r=1.0 >= k -> enter
    assert s.desired_position(3) == 0   # bar2 r=0.3 < k_exit(0.5) -> exit


def test_atrband_holds_within_hysteresis_band():
    close = np.array([1.0, 2.0, 1.6])
    ema = np.array([1.0, 1.0, 1.0])
    atr = np.ones(3)
    s = AtrBandState(close, ema, atr, k=1.0, k_exit=0.5)
    assert s.desired_position(2) == 1   # bar1 r=1.0
    assert s.desired_position(3) == 1   # bar2 r=0.6 in [0.5,1.0] -> hold


def test_atrband_nan_safe():
    close = np.array([1.0, np.nan, 2.0])
    s = AtrBandState(close, np.array([1.0, 1.0, 1.0]), np.ones(3),
                     k=1.0, k_exit=0.5)
    assert s.desired_position(1) == 0
    assert s.desired_position(2) == 0  # bar1 NaN -> flat preserved
    assert s.desired_position(3) == 1  # bar2 r=1.0


# --- S-25 ChopReversionState: stretch below ema in choppy regime ------------

def test_chop_flat_on_bar_zero():
    s = ChopReversionState(np.array([1.0]), np.array([1.0]),
                           np.array([1.0]), np.array([60.0]))
    assert s.desired_position(0) == 0


def test_chop_enters_when_stretched_and_choppy():
    close = np.array([1.0, -0.5, 1.1])
    ema = np.array([1.0, 1.0, 1.0])
    atr = np.ones(3)
    chop = np.array([60.0, 65.0, 65.0])
    s = ChopReversionState(close, ema, atr, chop, k=1.0, chop_at=60.0)
    assert s.desired_position(1) == 0   # bar0 r=0
    assert s.desired_position(2) == 1   # bar1 r=-1.5 <= -1, chop 65>60
    assert s.desired_position(3) == 0   # bar2 close>=ema -> exit


def test_chop_blocked_when_regime_not_choppy():
    close = np.array([1.0, -0.5])
    chop = np.array([60.0, 50.0])
    s = ChopReversionState(close, np.array([1.0, 1.0]), np.ones(2),
                           chop, k=1.0, chop_at=60.0)
    assert s.desired_position(2) == 0   # chop 50 <= 60 -> blocked


def test_chop_nan_safe():
    # chop NaN at the would-be entry bar blocks entry; a later valid bar still
    # enters.
    close = np.array([1.0, -0.5, -0.6, 1.1])
    chop = np.array([60.0, np.nan, 65.0, 65.0])
    s = ChopReversionState(close, np.array([1.0, 1.0, 1.0, 1.0]),
                           np.ones(4), chop, k=1.0, chop_at=60.0)
    assert s.desired_position(2) == 0   # bar1 chop NaN -> blocked
    assert s.desired_position(3) == 1   # bar2 chop 65 + stretched -> enter
    assert s.desired_position(4) == 0   # bar3 close>=ema -> exit


# --- S-26 EmaSpread12State: cross above th, hysteresis exit -----------------

def test_emaspread12_flat_on_bar_zero():
    s = EmaSpread12State(np.array([0.5]))
    assert s.desired_position(0) == 0


def test_emaspread12_enters_above_th_and_exits_below_exit():
    s = EmaSpread12State(np.array([0.2, 0.6, 0.4, -0.1]), th=0.5, th_exit=0.0)
    assert s.desired_position(1) == 0   # bar0 0.2
    assert s.desired_position(2) == 1   # bar1 0.6
    assert s.desired_position(3) == 1   # bar2 0.4 (>= exit 0.0)
    assert s.desired_position(4) == 0   # bar3 -0.1


def test_emaspread12_hysteresis_holds():
    s = EmaSpread12State(np.array([0.6, 0.6, 0.3]), th=0.5, th_exit=0.2)
    assert s.desired_position(2) == 1   # bar1 0.6 > th -> enter
    assert s.desired_position(3) == 1   # bar2 0.3 in [th_exit, th] -> hold


def test_emaspread12_nan_safe():
    s = EmaSpread12State(np.array([np.nan, 0.6, -0.1]), th=0.5, th_exit=0.0)
    assert s.desired_position(1) == 0
    assert s.desired_position(2) == 1
    assert s.desired_position(3) == 0


# --- S-27 VolMomState: positive momentum confirmed by volume ---------------

def test_volmom_flat_on_bar_zero():
    s = VolMomState(np.array([0.0]), np.array([1.0]))
    assert s.desired_position(0) == 0


def test_volmom_enters_when_momentum_positive_and_volume_confirmed():
    mom = np.array([-0.001, 0.001, 0.001, -0.001])
    vol = np.array([1.0, 1.5, 1.5, 1.5])
    s = VolMomState(mom, vol, vmin=1.0)
    assert s.desired_position(1) == 0   # bar0 mom<0
    assert s.desired_position(2) == 1   # bar1 mom>0, vol 1.5
    assert s.desired_position(3) == 1   # bar2 mom>0
    assert s.desired_position(4) == 0   # bar3 mom<=0 -> exit


def test_volmom_blocked_when_volume_too_low():
    mom = np.array([-0.001, 0.001])
    vol = np.array([1.0, 0.5])
    s = VolMomState(mom, vol, vmin=1.0)
    assert s.desired_position(2) == 0   # vol 0.5 < 1.0


def test_volmom_nan_safe():
    mom = np.array([np.nan, 0.001, -0.001])
    vol = np.array([1.0, 1.5, 1.5])
    s = VolMomState(mom, vol, vmin=1.0)
    assert s.desired_position(1) == 0
    assert s.desired_position(2) == 1
    assert s.desired_position(3) == 0
