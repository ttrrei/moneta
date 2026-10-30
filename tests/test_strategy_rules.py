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
# Batch 3 (S-28 .. S-40)
from strategy.strategy_candle_lib import CandleClvState
from strategy.strategy_volconverge_lib import VolConvergeState
from strategy.strategy_atrbandpct_lib import AtrBandPctState
from strategy.strategy_stdist_lib import StDistTrendState
from strategy.strategy_psardist_lib import PsarDistState
from strategy.strategy_kcbreak_lib import KcBreakState
from strategy.strategy_bb_pctb_lib import BbPctbTurnState
from strategy.strategy_bb_width_lib import BbWidthTurnState
from strategy.strategy_dcpos_lib import DcPosState
from strategy.strategy_dcmid_lib import DcMidState
from strategy.strategy_distlow_lib import DistLowState
from strategy.strategy_dcwidth_lib import DcWidthState
from strategy.strategy_stdist_hyst_lib import StDistHystState


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


# ===========================================================================
# Batch 3 (S-28 .. S-40): deterministic rule tests
# ===========================================================================

# --- S-28 CandleClvState: fresh up-cross of bar_clv above k_in -------------

def test_candle_flat_on_bar_zero():
    s = CandleClvState(np.array([0.9]))
    assert s.desired_position(0) == 0


def test_candle_enters_on_fresh_upcross_and_exits_below_k_exit():
    clv = np.array([-0.5, 0.5, 0.5, 0.5, 0.0])
    s = CandleClvState(clv, k_in=0.4, k_exit=0.1)
    assert s.desired_position(1) == 0   # bar0 -0.5 (prev flat)
    assert s.desired_position(2) == 1   # bar1 0.5 > k_in, prev -0.5 -> fresh cross
    assert s.desired_position(3) == 1   # bar2 0.5 still >= k_exit
    assert s.desired_position(4) == 1   # bar3 0.5 still >= k_exit
    assert s.desired_position(5) == 0   # bar4 0.0 < k_exit 0.1 -> exit


def test_candle_requires_fresh_cross():
    clv = np.array([0.6, 0.6])
    s = CandleClvState(clv, k_in=0.4, k_exit=0.1)
    assert s.desired_position(2) == 0   # already above at bar0 -> no fresh cross


def test_candle_nan_safe():
    clv = np.array([np.nan, 0.5, 0.5, 0.0])
    s = CandleClvState(clv, k_in=0.4, k_exit=0.1)
    assert s.desired_position(1) == 0   # bar0 NaN -> flat preserved
    assert s.desired_position(2) == 1   # bar1 0.5, prev NaN -> enter
    assert s.desired_position(3) == 1
    assert s.desired_position(4) == 0   # exit below k_exit


# --- S-29 VolConvergeState: vol_rel below vmin and close>ema ---------------

def test_volconverge_enters_on_contraction_in_uptrend():
    volr = np.array([1.5, 0.9, 0.9, 1.8])
    close = np.array([1.0, 1.1, 1.1, 1.1])
    ema = np.array([1.0, 1.0, 1.0, 1.0])
    s = VolConvergeState(volr, close, ema, vmin=1.0, vmax=1.5)
    assert s.desired_position(1) == 0   # bar0 volr 1.5 not < vmin
    assert s.desired_position(2) == 1   # bar1 volr 0.9<1.0, close>ema
    assert s.desired_position(3) == 1   # still volr<1.5
    assert s.desired_position(4) == 0   # bar3 volr 1.8>1.5 -> exit


def test_volconverge_blocked_when_close_below_ema():
    volr = np.array([1.5, 0.9])
    close = np.array([1.0, 0.9])
    ema = np.array([1.0, 1.0])
    s = VolConvergeState(volr, close, ema, vmin=1.0, vmax=1.5)
    assert s.desired_position(2) == 0   # close<ema -> no entry


def test_volconverge_nan_safe():
    volr = np.array([np.nan, 0.9, 0.9])
    close = np.array([1.0, 1.1, 1.1])
    ema = np.array([1.0, 1.0, 1.0])
    s = VolConvergeState(volr, close, ema, vmin=1.0, vmax=1.5)
    assert s.desired_position(1) == 0
    assert s.desired_position(2) == 1
    assert s.desired_position(3) == 1


# --- S-30 AtrBandPctState: fresh up-cross of ema_dist --------------------

def test_atrbandpct_fresh_cross_entry_and_hysteresis_exit():
    dist = np.array([-1.0, 1.5, 1.5, -0.5])
    s = AtrBandPctState(dist, k_in=1.0, k_exit=0.0)
    assert s.desired_position(1) == 0
    assert s.desired_position(2) == 1   # fresh cross above 1.0
    assert s.desired_position(3) == 1   # 1.5 >= k_exit
    assert s.desired_position(4) == 0   # -0.5 < k_exit -> exit


def test_atrbandpct_requires_fresh_cross():
    dist = np.array([1.5, 1.5])
    s = AtrBandPctState(dist, k_in=1.0, k_exit=0.0)
    assert s.desired_position(2) == 0


# --- S-31 StDistTrendState: hold while st_dist > th_in ---------------------

def test_stdist_hold_and_hysteresis_exit():
    st = np.array([-1.0, 1.0, 0.0, -2.0])
    s = StDistTrendState(st, th_in=0.5, th_exit=-0.5)
    assert s.desired_position(1) == 0   # bar0 below th_in
    assert s.desired_position(2) == 1   # bar1 1.0 > 0.5
    assert s.desired_position(3) == 1   # bar2 0.0: not < -0.5, still long
    assert s.desired_position(4) == 0   # bar3 -2.0 < -0.5 -> exit


# --- S-32 PsarDistState: same shape as S-31 -------------------------------

def test_psardist_hold_and_hysteresis_exit():
    pd = np.array([-1.0, 1.0, 0.0, -2.0])
    s = PsarDistState(pd, th_in=0.5, th_exit=-0.5)
    assert s.desired_position(1) == 0
    assert s.desired_position(2) == 1
    assert s.desired_position(3) == 1
    assert s.desired_position(4) == 0


# --- S-33 KcBreakState: fresh close up-cross of kc_upper ------------------

def test_kcbreak_fresh_cross_entry_exit_at_mid():
    close = np.array([1.0, 2.0, 2.0, 0.9])
    upper = np.array([1.5, 1.5, 1.5, 1.5])
    mid = np.array([1.2, 1.2, 1.2, 1.2])
    s = KcBreakState(close, upper, mid)
    assert s.desired_position(1) == 0   # bar0 close 1.0 < upper 1.5
    assert s.desired_position(2) == 1   # bar1 close 2.0 > upper, prev 1.0 <= upper
    assert s.desired_position(3) == 1   # still above mid
    assert s.desired_position(4) == 0   # bar3 close 0.9 <= mid -> exit


def test_kcbreak_no_entry_without_fresh_cross():
    close = np.array([2.0, 2.0])
    upper = np.array([1.5, 1.5])
    mid = np.array([1.2, 1.2])
    s = KcBreakState(close, upper, mid)
    assert s.desired_position(2) == 0   # already above at bar0 -> no fresh cross


# --- S-34 BbPctbTurnState: fresh down-cross of %B -------------------------

def test_bbpctb_fresh_downcross_entry_exit():
    pctb = np.array([0.9, 0.1, 0.1, 0.6])
    s = BbPctbTurnState(pctb, k_in=0.2, k_exit=0.5)
    assert s.desired_position(1) == 0
    assert s.desired_position(2) == 1   # fresh down-cross below 0.2
    assert s.desired_position(3) == 1   # 0.1 < k_exit
    assert s.desired_position(4) == 0   # 0.6 >= 0.5 -> exit


# --- S-35 BbWidthTurnState: fresh compression, exit on expansion ----------

def test_bbwidth_compression_entry_exit():
    width = np.array([0.10, 0.02, 0.02, 0.12])
    pctb = np.array([0.5, 0.5, 0.5, 0.5])
    s = BbWidthTurnState(width, pctb, low=0.03, high=0.10)
    assert s.desired_position(1) == 0
    assert s.desired_position(2) == 1   # fresh compression below 0.03, pctb>0
    assert s.desired_position(3) == 1   # 0.02 < 0.10
    assert s.desired_position(4) == 0   # 0.12 > 0.10 -> exit


def test_bbwidth_blocked_when_pctb_nonpositive():
    width = np.array([0.10, 0.02])
    pctb = np.array([0.5, -0.1])
    s = BbWidthTurnState(width, pctb, low=0.03, high=0.10)
    assert s.desired_position(2) == 0   # pctb <= 0 -> no entry


# --- S-36 DcPosState: fresh up-cross of dc_pos ----------------------------

def test_dcpos_fresh_cross_entry_exit():
    pos = np.array([0.3, 0.85, 0.85, 0.3])
    s = DcPosState(pos, k_in=0.8, k_exit=0.4)
    assert s.desired_position(1) == 0
    assert s.desired_position(2) == 1   # fresh cross above 0.8
    assert s.desired_position(3) == 1   # 0.85 >= 0.4
    assert s.desired_position(4) == 0   # 0.3 < 0.4 -> exit


# --- S-37 DcMidState: fresh close up-cross of dc_mid ----------------------

def test_dcmid_fresh_cross_entry_exit():
    close = np.array([1.0, 1.2, 1.2, 1.0])
    mid = np.array([1.1, 1.1, 1.1, 1.1])
    s = DcMidState(close, mid)
    assert s.desired_position(1) == 0
    assert s.desired_position(2) == 1   # fresh up-cross
    assert s.desired_position(3) == 1
    assert s.desired_position(4) == 0   # close <= mid -> exit


def test_dcmid_no_entry_without_fresh_cross():
    close = np.array([1.2, 1.2])
    mid = np.array([1.1, 1.1])
    s = DcMidState(close, mid)
    assert s.desired_position(2) == 0


# --- S-38 DistLowState: fresh up-cross of dist_low ------------------------

def test_distlow_fresh_cross_entry_exit():
    dl = np.array([0.1, 1.5, 1.5, 0.1])
    s = DistLowState(dl, k_in=1.0, k_exit=0.2)
    assert s.desired_position(1) == 0
    assert s.desired_position(2) == 1
    assert s.desired_position(3) == 1
    assert s.desired_position(4) == 0


# --- S-39 DcWidthState: fresh channel compression -------------------------

def test_dcwidth_fresh_compression_entry_exit():
    upper = np.array([12.0, 10.5, 10.5, 14.0])
    lower = np.array([10.0, 10.0, 10.0, 10.0])
    atr = np.array([1.0, 1.0, 1.0, 1.0])
    s = DcWidthState(upper, lower, atr, w_in=2.0, w_exit=4.0)
    assert s.desired_position(1) == 0   # bar0 width 2.0 not < 2.0
    assert s.desired_position(2) == 1   # bar1 width 0.5 < 2.0, prev 2.0 >= 2.0
    assert s.desired_position(3) == 1   # bar2 width 0.5 < 4.0, still long
    assert s.desired_position(4) == 1   # bar3 width 4.0 not > 4.0 -> still long


def test_dcwidth_nan_safe():
    # bar0 NaN in the width series; entry at bar2 requires bar1 (finite)
    upper = np.array([np.nan, 12.0, 10.5, 15.0])
    lower = np.array([10.0, 10.0, 10.0, 10.0])
    atr = np.array([1.0, 1.0, 1.0, 1.0])
    s = DcWidthState(upper, lower, atr, w_in=2.0, w_exit=4.0)
    assert s.desired_position(1) == 0   # bar0 NaN -> flat
    assert s.desired_position(2) == 0   # bar1 width 2.0 not < 2.0 -> still flat
    assert s.desired_position(3) == 1   # bar2 width 0.5 < 2.0, bar1 2.0 >= 2.0 -> entry
    assert s.desired_position(4) == 0   # bar3 width 5.0 > 4.0 -> exit


# --- S-40 StDistHystState: side + distance hysteresis --------------------

def test_stdisthyst_entry_requires_side_up_and_dist_above_th_in():
    side = np.array([-1.0, 1.0, 1.0, -1.0])
    dist = np.array([0.5, 1.5, 0.3, 0.3])
    s = StDistHystState(side, dist, th_in=1.0, th_exit=0.2)
    assert s.desired_position(1) == 0   # bar0 side down
    assert s.desired_position(2) == 1   # bar1 side up, dist 1.5 > 1.0 (fresh)
    assert s.desired_position(3) == 1   # bar2 dist 0.3 >= th_exit 0.2
    assert s.desired_position(4) == 0   # bar3 side down -> exit


def test_stdisthyst_no_entry_when_dist_below_th_in():
    side = np.array([-1.0, 1.0])
    dist = np.array([0.5, 0.8])
    s = StDistHystState(side, dist, th_in=1.0, th_exit=0.2)
    assert s.desired_position(2) == 0   # dist 0.8 < th_in 1.0 -> no entry


def test_stdisthyst_reentry_needs_dist_above_th_in_again():
    # after exit, dist must rise above th_in again for a fresh entry
    side = np.array([-1.0, 1.0, -1.0, 1.0])
    dist = np.array([0.5, 1.5, 0.1, 0.3])
    s = StDistHystState(side, dist, th_in=1.0, th_exit=0.2)
    assert s.desired_position(2) == 1   # entry at bar1
    assert s.desired_position(3) == 0   # side down -> exit
    assert s.desired_position(4) == 0   # side up again but dist 0.3 < th_in -> no fresh entry

from strategy.strategy_hvconverge_lib import HvConvergeState
from strategy.strategy_barbody_lib import BarBodyState


# --- S-41 HvConvergeState: hold while hv below k_in -----------------------

def test_hvconverge_hold_when_realized_vol_low():
    hv = np.array([0.001, 0.0002, 0.0002, 0.002])
    s = HvConvergeState(hv, k_in=0.0003, k_exit=0.0006)
    assert s.desired_position(1) == 0   # bar0 hv 0.001 not < k_in
    assert s.desired_position(2) == 1   # bar1 0.0002 < 0.0003
    assert s.desired_position(3) == 1   # bar2 0.0002 < k_exit 0.0006
    assert s.desired_position(4) == 0   # bar3 0.002 > 0.0006 -> exit


def test_hvconverge_nan_safe():
    hv = np.array([np.nan, 0.0002, 0.0002])
    s = HvConvergeState(hv, k_in=0.0003, k_exit=0.0006)
    assert s.desired_position(1) == 0
    assert s.desired_position(2) == 1
    assert s.desired_position(3) == 1


# --- S-42 BarBodyState: fresh up-cross of bar_body_ratio ------------------

def test_barbody_fresh_cross_entry_exit():
    body = np.array([0.2, 0.7, 0.7, 0.2])
    s = BarBodyState(body, k_in=0.6, k_exit=0.3)
    assert s.desired_position(1) == 0   # bar0 0.2 not above k_in
    assert s.desired_position(2) == 1   # bar1 0.7 > 0.6 fresh cross
    assert s.desired_position(3) == 1   # 0.7 >= k_exit 0.3
    assert s.desired_position(4) == 0   # 0.2 < 0.3 -> exit


def test_barbody_requires_fresh_cross():
    body = np.array([0.8, 0.8])
    s = BarBodyState(body, k_in=0.6, k_exit=0.3)
    assert s.desired_position(2) == 0   # already above at bar0 -> no fresh cross


def test_barbody_nan_safe():
    body = np.array([np.nan, 0.7, 0.7, 0.2])
    s = BarBodyState(body, k_in=0.6, k_exit=0.3)
    assert s.desired_position(1) == 0
    assert s.desired_position(2) == 1   # bar1 0.7 fresh (prev NaN)
    assert s.desired_position(3) == 1
    assert s.desired_position(4) == 0   # exit below k_exit


# =====================================================================
# Batch 4 (S-43 .. S-57)
# =====================================================================

from strategy.strategy_dispread_lib import DiSpreadState
from strategy.strategy_dualsma_lib import DualSmaState
from strategy.strategy_macdsig_lib import MacdSigState
from strategy.strategy_atrpct_lib import AtrPctState
from strategy.strategy_disthigh_lib import DistHighState
from strategy.strategy_volratio_lib import VolRatioState
from strategy.strategy_kclower_lib import KcLowerState
from strategy.strategy_bbmid_lib import BbMidState
from strategy.strategy_upwick_lib import UpWickState
from strategy.strategy_clv_lib import ClvState
from strategy.strategy_macdhist6_lib import MacdHist6State
from strategy.strategy_h1adx_lib import H1AdxState
from strategy.strategy_h1rsi_lib import H1RsiState
from strategy.strategy_h1er_lib import H1ErState
from strategy.strategy_h1edist_lib import H1EdistState
from strategy.strategy_roc_lib import RocState
from strategy.strategy_stochkd_lib import StochKdState
from strategy.strategy_aroondn_lib import AroonDnState
from strategy.strategy_momsign_lib import MomSignState
from strategy.strategy_hvup_lib import HvUpState
from strategy.strategy_bbupper_lib import BbUpperState
from strategy.strategy_dcupper_lib import DcUpperState
from strategy.strategy_lowwick_lib import LowWickState
from strategy.strategy_volbb_lib import VolBbState
from strategy.strategy_h1adxst_lib import H1AdxStState
from strategy.strategy_dualst_lib import DualStState
from strategy.strategy_stok_lib import StochKState
from strategy.strategy_h1vol_lib import H1VolState
from strategy.strategy_aroondnstoch_lib import AroonStochState
from strategy.strategy_rocvol_lib import RocVolState
from strategy.strategy_aroonup60_lib import AroonUp60State
from strategy.strategy_willr60_lib import Willr60State
from strategy.strategy_cci120_lib import Cci120State
from strategy.strategy_stochk60_lib import StochK60State
from strategy.strategy_mfi60_lib import Mfi60State
from strategy.strategy_atrpct120_lib import AtrPct120State
from strategy.strategy_roc120_lib import Roc120State
from strategy.strategy_hoursin_lib import HourSinState
from strategy.strategy_dowsin_lib import DowSinState
from strategy.strategy_trcollapse_lib import TrState
from strategy.strategy_psar002_lib import Psar002State
from strategy.strategy_stdual120_lib import StDual120State
from strategy.strategy_h1st120_lib import H1St120State
from strategy.strategy_timeconf_lib import TimeConfluenceState
from strategy.strategy_roc120vol_lib import Roc120VolState
from strategy.strategy_rsi12_lib import Rsi12State
from strategy.strategy_aroon12spread_lib import Aroon12SpreadState
from strategy.strategy_macdh624_lib import MacdHist624State
from strategy.strategy_stochd12_lib import StochD12State
from strategy.strategy_mfi12_lib import Mfi12State
from strategy.strategy_willr12_lib import Willr12State
from strategy.strategy_er12_lib import Er12State
from strategy.strategy_hv120_lib import Hv120State
from strategy.strategy_bbw60_lib import BbW60State
from strategy.strategy_triosc_lib import TriOscState
from strategy.strategy_quadosc_lib import QuadOscState
from strategy.strategy_roc6volr_lib import Roc6VolrState
from strategy.strategy_macdcross624_lib import MacdCross624State
from strategy.strategy_roc120ema120_lib import Roc120Ema120State
from strategy.strategy_dcpos12_lib import DcPos12State


# --- S-43 DiSpreadState: fresh up-cross of (plus_di - minus_di) -----------

def test_dispread_entry_exit():
    pdi = np.array([10.0, 20.0, 25.0, 15.0, 10.0])
    mdi = np.array([15.0, 12.0, 10.0, 20.0, 30.0])
    # spread: -5, +8, +15, -5, -20
    s = DiSpreadState(pdi, mdi, k_in=5.0, k_exit=2.0)
    assert s.desired_position(1) == 0   # bar0 spread -5 not fresh > 5
    assert s.desired_position(2) == 1   # bar1 spread +8 fresh > 5
    assert s.desired_position(3) == 1   # +15 still > -2 exit level
    assert s.desired_position(4) == 0   # -5 < -2 -> exit
    assert s.desired_position(5) == 0   # -20 no fresh entry


def test_dispread_nan_safe():
    pdi = np.array([np.nan, 20.0, 25.0, 15.0])
    mdi = np.array([15.0, 12.0, 10.0, 20.0])
    s = DiSpreadState(pdi, mdi, k_in=5.0, k_exit=2.0)
    assert s.desired_position(1) == 0
    # NaN warmup bar: the prev-spread finite guard suppresses the fresh cross
    assert s.desired_position(2) == 0
    assert s.desired_position(3) == 0   # not entered, so no position


# --- S-44 DualSmaState: fresh (close > fast > slow) alignment -------------

def test_dualsma_entry_exit():
    close = np.array([100.0, 110.0, 115.0, 90.0])
    fast = np.array([100.0, 105.0, 110.0, 108.0])
    slow = np.array([100.0, 100.0, 102.0, 100.0])
    s = DualSmaState(close, fast, slow)
    assert s.desired_position(1) == 0   # bar0 not aligned
    assert s.desired_position(2) == 1   # bar1 110>105>100 fresh
    assert s.desired_position(3) == 1   # 115>110>102 holds
    assert s.desired_position(4) == 0   # 90 < slow 100 -> exit


def test_dualsma_requires_alignment():
    close = np.array([110.0, 110.0])
    fast = np.array([105.0, 105.0])
    slow = np.array([100.0, 115.0])
    s = DualSmaState(close, fast, slow)
    assert s.desired_position(2) == 0   # 110>105 but 105 < 115 -> not aligned


def test_dualsma_nan_safe():
    close = np.array([np.nan, 110.0, 115.0, 90.0])
    fast = np.array([100.0, 105.0, 110.0, 108.0])
    slow = np.array([100.0, 100.0, 102.0, 100.0])
    s = DualSmaState(close, fast, slow)
    assert s.desired_position(1) == 0
    assert s.desired_position(2) == 1


# --- S-45 MacdSigState: fresh macd > signal --------------------------------

def test_macdsig_entry_exit():
    macd = np.array([-2.0, 1.0, 3.0, -5.0, 2.0])
    sig = np.array([-1.0, 0.5, 1.0, -2.0, 0.5])
    s = MacdSigState(macd, sig)
    assert s.desired_position(1) == 0   # bar0 macd < sig
    assert s.desired_position(2) == 1   # bar1 1 > 0.5 fresh
    assert s.desired_position(3) == 1   # 3 > 1 holds
    assert s.desired_position(4) == 0   # -5 < -2 -> exit
    assert s.desired_position(5) == 1   # 2 > 0.5, prev -5 < -2 -> fresh re-entry


def test_macdsig_fresh_cross_only():
    # after exit, must up-cross signal again for a fresh entry
    macd = np.array([-2.0, 1.0, -5.0, 3.0])
    sig = np.array([-1.0, 0.5, -2.0, 1.0])
    s = MacdSigState(macd, sig)
    assert s.desired_position(2) == 1   # bar1 1 > 0.5 fresh
    assert s.desired_position(3) == 0   # -5 < -2 -> exit
    assert s.desired_position(4) == 1   # 3 > 1 fresh (prev -5 < -2)


def test_macdsig_nan_safe():
    macd = np.array([np.nan, 1.0, 3.0, -5.0])
    sig = np.array([0.5, 0.5, 1.0, -2.0])
    s = MacdSigState(macd, sig)
    assert s.desired_position(1) == 0
    # NaN warmup bar: the prev finite guard suppresses the fresh cross
    assert s.desired_position(2) == 0
    assert s.desired_position(3) == 0


# --- S-46 AtrPctState: low atr_pct with close > ema ------------------------

def test_atrpct_entry_exit():
    apct = np.array([0.005, 0.002, 0.002, 0.006])
    close = np.array([100.0, 101.0, 102.0, 103.0])
    ema = np.array([99.0, 100.0, 101.0, 102.0])
    s = AtrPctState(apct, close, ema, k_in=0.0025, k_exit=0.0045)
    assert s.desired_position(1) == 0   # bar0 0.005 > k_in
    assert s.desired_position(2) == 1   # bar1 0.002 < 0.0025, close 101 > ema 100 fresh
    assert s.desired_position(3) == 1   # 0.002 < k_exit 0.0045 holds
    assert s.desired_position(4) == 0   # 0.006 > 0.0045 -> exit


def test_atrpct_requires_close_above_ema():
    apct = np.array([0.005, 0.002, 0.002])
    close = np.array([100.0, 99.0, 100.0])
    ema = np.array([99.0, 100.0, 101.0])
    s = AtrPctState(apct, close, ema, k_in=0.0025, k_exit=0.0045)
    assert s.desired_position(2) == 0   # close 99 < ema 100 -> no entry


def test_atrpct_nan_safe():
    apct = np.array([np.nan, 0.002, 0.002, 0.006])
    close = np.array([100.0, 101.0, 102.0, 103.0])
    ema = np.array([99.0, 100.0, 101.0, 102.0])
    s = AtrPctState(apct, close, ema, k_in=0.0025, k_exit=0.0045)
    assert s.desired_position(1) == 0
    assert s.desired_position(2) == 1


# --- S-47 DistHighState: fresh up-cross of dist_high -----------------------

def test_disthigh_entry_exit():
    dh = np.array([0.5, 2.0, 2.5, 0.3])
    s = DistHighState(dh, k_in=1.5, k_exit=0.5)
    assert s.desired_position(1) == 0   # 0.5 not > 1.5
    assert s.desired_position(2) == 1   # 2.0 fresh > 1.5
    assert s.desired_position(3) == 1   # 2.5 > 0.5 holds
    assert s.desired_position(4) == 0   # 0.3 < 0.5 -> exit


def test_disthigh_nan_safe():
    dh = np.array([np.nan, 2.0, 2.5, 0.3])
    s = DistHighState(dh, k_in=1.5, k_exit=0.5)
    assert s.desired_position(1) == 0
    assert s.desired_position(2) == 1   # fresh (prev NaN)


# --- S-48 VolRatioState: fresh up-cross of vol_ratio -----------------------

def test_volratio_entry_exit():
    vr = np.array([0.8, 1.2, 1.4, 0.7])
    s = VolRatioState(vr, k_in=1.05, k_exit=0.85)
    assert s.desired_position(1) == 0
    assert s.desired_position(2) == 1   # 1.2 fresh > 1.05
    assert s.desired_position(3) == 1   # 1.4 > 0.85
    assert s.desired_position(4) == 0   # 0.7 < 0.85


def test_volratio_nan_safe():
    vr = np.array([np.nan, 1.2, 1.4, 0.7])
    s = VolRatioState(vr, k_in=1.05, k_exit=0.85)
    assert s.desired_position(1) == 0
    assert s.desired_position(2) == 1
# --- S-49 KcLowerState: fresh close > kc_lower ------------------------------

def test_kclower_entry_exit():
    close = np.array([99.0, 98.0, 105.0, 102.0])
    lo = np.array([100.0, 99.0, 101.0, 103.0])
    mid = np.array([102.0, 101.0, 103.0, 104.0])
    s = KcLowerState(close, lo, mid)
    assert s.desired_position(1) == 0   # bar0 99 < lo 100 -> below
    assert s.desired_position(2) == 0   # 98 < 99 -> below
    assert s.desired_position(3) == 1   # 105 > 101 fresh (prev below)
    assert s.desired_position(4) == 0   # 102 < mid 104 -> exit


def test_kclower_nan_safe():
    close = np.array([np.nan, 98.0, 105.0, 102.0])
    lo = np.array([100.0, 99.0, 101.0, 103.0])
    mid = np.array([102.0, 101.0, 103.0, 104.0])
    s = KcLowerState(close, lo, mid)
    assert s.desired_position(1) == 0
    assert s.desired_position(3) == 1   # bar2 105 > 101 fresh


# --- S-50 BbMidState: fresh close > bb_mid (above lower) -------------------

def test_bbmid_entry_exit():
    close = np.array([99.0, 98.0, 105.0, 102.0])
    mid = np.array([100.0, 99.0, 101.0, 103.0])
    lo = np.array([98.0, 97.0, 99.0, 101.0])
    s = BbMidState(close, mid, lo)
    assert s.desired_position(1) == 0   # bar0 99 < mid 100
    assert s.desired_position(2) == 0   # 98 < 99
    assert s.desired_position(3) == 1   # 105 > 101 and > 99 fresh
    assert s.desired_position(4) == 1   # 102 > 103? no: 102 < 103 -> wait, holds because exit is close < lo 101; 102 > 101 -> hold


def test_bbmid_nan_safe():
    close = np.array([np.nan, 98.0, 105.0, 102.0])
    mid = np.array([100.0, 99.0, 101.0, 103.0])
    lo = np.array([98.0, 97.0, 99.0, 101.0])
    s = BbMidState(close, mid, lo)
    assert s.desired_position(1) == 0
    assert s.desired_position(3) == 1   # bar2 105 > 101 fresh


# --- S-51 UpWickState: fresh down-cross of bar_upper_wick ------------------

def test_upwick_entry_exit():
    uw = np.array([0.5, 0.1, 0.1, 0.6])
    s = UpWickState(uw, k_in=0.15, k_exit=0.45)
    assert s.desired_position(1) == 0   # bar0 0.5 > k_in 0.15
    assert s.desired_position(2) == 1   # 0.1 < 0.15 fresh
    assert s.desired_position(3) == 1   # 0.1 < k_exit 0.45 holds
    assert s.desired_position(4) == 0   # 0.6 > 0.45 -> exit


def test_upwick_nan_safe():
    uw = np.array([np.nan, 0.1, 0.1, 0.6])
    s = UpWickState(uw, k_in=0.15, k_exit=0.45)
    assert s.desired_position(1) == 0
    assert s.desired_position(2) == 1   # fresh (prev NaN)


# --- S-52 ClvState: fresh up-cross of bar_clv -------------------------------

def test_clv_entry_exit():
    clv = np.array([-0.5, 0.4, 0.5, -0.3])
    s = ClvState(clv, k_in=0.3, k_exit=-0.1)
    assert s.desired_position(1) == 0   # bar0 -0.5 < 0.3
    assert s.desired_position(2) == 1   # 0.4 > 0.3 fresh
    assert s.desired_position(3) == 1   # 0.5 > -0.1 holds
    assert s.desired_position(4) == 0   # -0.3 < -0.1 -> exit


def test_clv_nan_safe():
    clv = np.array([np.nan, 0.4, 0.5, -0.3])
    s = ClvState(clv, k_in=0.3, k_exit=-0.1)
    assert s.desired_position(1) == 0
    assert s.desired_position(2) == 1


# --- S-53 MacdHist6State: fresh up-cross of macd_hist_atr -------------------

def test_macdhist6_entry_exit():
    h = np.array([-0.1, 0.1, 0.2, -0.2])
    s = MacdHist6State(h, k_in=0.0, k_exit=-0.05)
    assert s.desired_position(1) == 0   # bar0 -0.1 < 0.0
    assert s.desired_position(2) == 1   # 0.1 > 0.0 fresh
    assert s.desired_position(3) == 1   # 0.2 > -0.05 holds
    assert s.desired_position(4) == 0   # -0.2 < -0.05 -> exit


def test_macdhist6_nan_safe():
    h = np.array([np.nan, 0.1, 0.2, -0.2])
    s = MacdHist6State(h, k_in=0.0, k_exit=-0.05)
    assert s.desired_position(1) == 0
    assert s.desired_position(2) == 1


# --- S-54 H1AdxState: h1_adx up-cross with close > ema ----------------------

def test_h1adx_entry_exit():
    a = np.array([20.0, 28.0, 30.0, 18.0])
    close = np.array([100.0, 101.0, 102.0, 103.0])
    ema = np.array([99.0, 100.0, 101.0, 102.0])
    s = H1AdxState(a, close, ema, k_in=25.0, k_exit=20.0)
    assert s.desired_position(1) == 0   # bar0 20 < 25
    assert s.desired_position(2) == 1   # 28 > 25, close 101 > ema 100 fresh
    assert s.desired_position(3) == 1   # 30 > 20 holds
    assert s.desired_position(4) == 0   # 18 < 20 -> exit


def test_h1adx_requires_close_above_ema():
    a = np.array([20.0, 28.0, 30.0])
    close = np.array([100.0, 99.0, 100.0])
    ema = np.array([99.0, 100.0, 101.0])
    s = H1AdxState(a, close, ema, k_in=25.0, k_exit=20.0)
    assert s.desired_position(2) == 0   # close 99 < ema 100 -> no entry


def test_h1adx_nan_safe():
    a = np.array([np.nan, 28.0, 30.0, 18.0])
    close = np.array([100.0, 101.0, 102.0, 103.0])
    ema = np.array([99.0, 100.0, 101.0, 102.0])
    s = H1AdxState(a, close, ema, k_in=25.0, k_exit=20.0)
    assert s.desired_position(1) == 0
    assert s.desired_position(2) == 1


# --- S-55 H1RsiState: fresh h1_rsi up-cross ---------------------------------

def test_h1rsi_entry_exit():
    r = np.array([50.0, 58.0, 60.0, 42.0])
    s = H1RsiState(r, k_in=55.0, k_exit=45.0)
    assert s.desired_position(1) == 0   # bar0 50 < 55
    assert s.desired_position(2) == 1   # 58 > 55 fresh
    assert s.desired_position(3) == 1   # 60 > 45 holds
    assert s.desired_position(4) == 0   # 42 < 45 -> exit


def test_h1rsi_nan_safe():
    r = np.array([np.nan, 58.0, 60.0, 42.0])
    s = H1RsiState(r, k_in=55.0, k_exit=45.0)
    assert s.desired_position(1) == 0
    assert s.desired_position(2) == 1


# --- S-56 H1ErState: fresh h1_er up-cross -----------------------------------

def test_h1er_entry_exit():
    e = np.array([0.1, 0.4, 0.5, 0.15])
    s = H1ErState(e, k_in=0.35, k_exit=0.2)
    assert s.desired_position(1) == 0   # bar0 0.1 < 0.35
    assert s.desired_position(2) == 1   # 0.4 > 0.35 fresh
    assert s.desired_position(3) == 1   # 0.5 > 0.2 holds
    assert s.desired_position(4) == 0   # 0.15 < 0.2 -> exit


def test_h1er_nan_safe():
    e = np.array([np.nan, 0.4, 0.5, 0.15])
    s = H1ErState(e, k_in=0.35, k_exit=0.2)
    assert s.desired_position(1) == 0
    assert s.desired_position(2) == 1


# --- S-57 H1EdistState: h1_ema_dist enters 0..k_in band ---------------------

def test_h1edist_entry_exit():
    ed = np.array([3.0, 1.5, 1.0, -1.5])
    s = H1EdistState(ed, k_in=2.0, k_exit=1.0)
    assert s.desired_position(1) == 0   # bar0 3.0 > k_in 2.0 -> out of band
    assert s.desired_position(2) == 1   # 1.5 in (0,2.0) fresh (prev 3.0 out)
    assert s.desired_position(3) == 1   # 1.0 in band holds (exit needs < -1.0)
    assert s.desired_position(4) == 0   # -1.5 < -1.0 -> exit


def test_h1edist_nan_safe():
    ed = np.array([np.nan, 1.5, 1.0, -1.5])
    s = H1EdistState(ed, k_in=2.0, k_exit=1.0)
    assert s.desired_position(1) == 0
    assert s.desired_position(2) == 1   # bar1 in band, prev NaN -> not in band -> fresh

# --- S-58 RocState: fresh roc up-cross ---------------------------------------

def test_roc_entry_exit():
    r = np.array([0.001, 0.006, 0.008, -0.002])
    s = RocState(r, k_in=0.004, k_exit=0.0)
    assert s.desired_position(1) == 0   # bar0 0.001 < 0.004
    assert s.desired_position(2) == 1   # 0.006 > 0.004 fresh
    assert s.desired_position(3) == 1   # 0.008 > 0.0 holds
    assert s.desired_position(4) == 0   # -0.002 < 0.0 -> exit


def test_roc_nan_safe():
    r = np.array([np.nan, 0.006, 0.008, -0.002])
    s = RocState(r, k_in=0.004, k_exit=0.0)
    assert s.desired_position(1) == 0
    assert s.desired_position(2) == 1   # NaN prev treated as fresh


# --- S-59 StochKdState: k>d fresh with k<k_in --------------------------------

def test_stochkd_entry_exit():
    k = np.array([20.0, 25.0, 24.0, 75.0])
    d = np.array([30.0, 20.0, 26.0, 70.0])
    s = StochKdState(k, d, k_in=30.0, k_exit=70.0)
    assert s.desired_position(1) == 0   # bar0 20 < 30 not fresh
    assert s.desired_position(2) == 1   # 25>20, 25<30 fresh
    assert s.desired_position(3) == 1   # 24<26 no exit yet
    assert s.desired_position(4) == 0   # 75 > 70 -> exit


def test_stochkd_nan_safe():
    k = np.array([np.nan, 25.0, 24.0, 75.0])
    d = np.array([30.0, 20.0, 26.0, 70.0])
    s = StochKdState(k, d, k_in=30.0, k_exit=70.0)
    assert s.desired_position(1) == 0
    assert s.desired_position(2) == 0   # jguard: prev NaN -> suppressed


# --- S-60 AroonDnState: fresh aroon_down collapse ----------------------------

def test_aroondn_entry_exit():
    a = np.array([50.0, 25.0, 20.0, 75.0])
    s = AroonDnState(a, k_in=30.0, k_exit=70.0)
    assert s.desired_position(1) == 0   # bar0 50 > 30
    assert s.desired_position(2) == 1   # 25 < 30 fresh
    assert s.desired_position(3) == 1   # 20 < 70 holds
    assert s.desired_position(4) == 0   # 75 > 70 -> exit


def test_aroondn_nan_safe():
    a = np.array([np.nan, 25.0, 20.0, 75.0])
    s = AroonDnState(a, k_in=30.0, k_exit=70.0)
    assert s.desired_position(1) == 0
    assert s.desired_position(2) == 1   # NaN prev treated as fresh


# --- S-61 MomSignState: fresh mom up-cross -----------------------------------

def test_momsign_entry_exit():
    m = np.array([-1.0, 1.5, 2.0, -1.0])
    s = MomSignState(m, k_in=0.5, k_exit=-0.5)
    assert s.desired_position(1) == 0   # bar0 -1 < 0.5
    assert s.desired_position(2) == 1   # 1.5 > 0.5 fresh
    assert s.desired_position(3) == 1   # 2.0 > -0.5 holds
    assert s.desired_position(4) == 0   # -1.0 < -0.5 -> exit


def test_momsign_nan_safe():
    m = np.array([np.nan, 1.5, 2.0, -1.0])
    s = MomSignState(m, k_in=0.5, k_exit=-0.5)
    assert s.desired_position(1) == 0
    assert s.desired_position(2) == 1


# --- S-62 HvUpState: fresh hv up-cross with close > ema -----------------------

def test_hvup_entry_exit():
    hv = np.array([0.001, 0.003, 0.004, 0.001])
    close = np.array([100.0, 102.0, 103.0, 104.0])
    ema = np.array([99.0, 100.0, 101.0, 102.0])
    s = HvUpState(hv, close, ema, k_in=0.0025, k_exit=0.0015)
    assert s.desired_position(1) == 0   # bar0 0.001 < 0.0025
    assert s.desired_position(2) == 1   # 0.003 > 0.0025, close 102 > ema 100 fresh
    assert s.desired_position(3) == 1   # 0.004 > 0.0015 holds
    assert s.desired_position(4) == 0   # 0.001 < 0.0015 -> exit


def test_hvup_requires_close_above_ema():
    hv = np.array([0.001, 0.003, 0.004])
    close = np.array([100.0, 99.0, 100.0])
    ema = np.array([99.0, 101.0, 102.0])
    s = HvUpState(hv, close, ema, k_in=0.0025, k_exit=0.0015)
    assert s.desired_position(2) == 0   # close 99 < ema 101 -> no entry


def test_hvup_nan_safe():
    hv = np.array([np.nan, 0.003, 0.004, 0.001])
    close = np.array([100.0, 102.0, 103.0, 104.0])
    ema = np.array([99.0, 100.0, 101.0, 102.0])
    s = HvUpState(hv, close, ema, k_in=0.0025, k_exit=0.0015)
    assert s.desired_position(1) == 0
    assert s.desired_position(2) == 1


# --- S-63 BbUpperState: fresh close>bb_upper ---------------------------------

def test_bbupper_entry_exit():
    close = np.array([100.0, 110.0, 115.0, 95.0])
    up = np.array([105.0, 108.0, 112.0, 100.0])
    s = BbUpperState(close, up)
    assert s.desired_position(1) == 0   # bar0 100 < 105
    assert s.desired_position(2) == 1   # 110 > 108 fresh
    assert s.desired_position(3) == 1   # 115 > 112 holds
    assert s.desired_position(4) == 0   # 95 < 100 -> exit


def test_bbupper_nan_safe():
    close = np.array([np.nan, 110.0, 115.0, 95.0])
    up = np.array([105.0, 108.0, 112.0, 100.0])
    s = BbUpperState(close, up)
    assert s.desired_position(1) == 0
    assert s.desired_position(2) == 0   # jguard: prev NaN -> suppressed


# --- S-64 DcUpperState: fresh close>dc_upper, exit < bb_mid ------------------

def test_dcupper_entry_exit():
    close = np.array([100.0, 110.0, 115.0, 95.0])
    up = np.array([105.0, 108.0, 112.0, 100.0])
    mid = np.array([102.0, 104.0, 106.0, 104.0])
    s = DcUpperState(close, up, mid)
    assert s.desired_position(1) == 0   # bar0 100 < 105
    assert s.desired_position(2) == 1   # 110 > 108 fresh
    assert s.desired_position(3) == 1   # 115 > 106 holds
    assert s.desired_position(4) == 0   # 95 < 104 -> exit


def test_dcupper_nan_safe():
    close = np.array([np.nan, 110.0, 115.0, 95.0])
    up = np.array([105.0, 108.0, 112.0, 100.0])
    mid = np.array([102.0, 104.0, 106.0, 104.0])
    s = DcUpperState(close, up, mid)
    assert s.desired_position(1) == 0
    assert s.desired_position(2) == 0   # jguard


# --- S-65 LowWickState: fresh lower-wick rejection ----------------------------

def test_lowwick_entry_exit():
    lw = np.array([0.2, 0.6, 0.7, 0.1])
    s = LowWickState(lw, k_in=0.5, k_exit=0.15)
    assert s.desired_position(1) == 0   # bar0 0.2 < 0.5
    assert s.desired_position(2) == 1   # 0.6 > 0.5 fresh
    assert s.desired_position(3) == 1   # 0.7 > 0.15 holds
    assert s.desired_position(4) == 0   # 0.1 < 0.15 -> exit


def test_lowwick_nan_safe():
    lw = np.array([np.nan, 0.6, 0.7, 0.1])
    s = LowWickState(lw, k_in=0.5, k_exit=0.15)
    assert s.desired_position(1) == 0
    assert s.desired_position(2) == 1


# --- S-66 VolBbState: fresh close>bb_upper with vol_rel>vmin ------------------

def test_volbb_entry_exit():
    close = np.array([100.0, 110.0, 115.0, 95.0])
    up = np.array([105.0, 108.0, 112.0, 100.0])
    vr = np.array([0.9, 1.2, 1.3, 1.1])
    s = VolBbState(close, up, vr, vmin=1.0)
    assert s.desired_position(1) == 0   # bar0 100 < 105
    assert s.desired_position(2) == 1   # 110>108, 1.2>1.0 fresh
    assert s.desired_position(3) == 1   # holds
    assert s.desired_position(4) == 0   # 95 < 100 -> exit


def test_volbb_requires_vol_confirm():
    close = np.array([100.0, 110.0, 115.0])
    up = np.array([105.0, 108.0, 112.0])
    vr = np.array([0.9, 0.9, 1.1])
    s = VolBbState(close, up, vr, vmin=1.0)
    assert s.desired_position(2) == 0   # vol 0.9 < 1.0 -> no entry


def test_volbb_nan_safe():
    close = np.array([np.nan, 110.0, 115.0, 95.0])
    up = np.array([105.0, 108.0, 112.0, 100.0])
    vr = np.array([0.9, 1.2, 1.3, 1.1])
    s = VolBbState(close, up, vr, vmin=1.0)
    assert s.desired_position(1) == 0
    assert s.desired_position(2) == 0   # jguard


# --- S-67 H1AdxStState: fresh h1_adx>k_in and h1_st>0 -------------------------

def test_h1adxst_entry_exit():
    a = np.array([20.0, 28.0, 30.0, 18.0])
    st = np.array([0.0, 1.0, 1.0, 1.0])
    s = H1AdxStState(a, st, k_in=25.0, k_exit=20.0)
    assert s.desired_position(1) == 0   # bar0 20 < 25
    assert s.desired_position(2) == 1   # 28 > 25, st 1 > 0 fresh
    assert s.desired_position(3) == 1   # 30 > 20, st 1 holds
    assert s.desired_position(4) == 0   # 18 < 20 -> exit


def test_h1adxst_nan_safe():
    a = np.array([np.nan, 28.0, 30.0, 18.0])
    st = np.array([0.0, 1.0, 1.0, 1.0])
    s = H1AdxStState(a, st, k_in=25.0, k_exit=20.0)
    assert s.desired_position(1) == 0
    assert s.desired_position(2) == 0   # jguard


# --- S-68 DualStState: fresh st24>0 and st120>0 --------------------------------

def test_dualst_entry_exit():
    st24 = np.array([0.0, 1.0, 1.0, -1.0])
    st120 = np.array([0.0, 1.0, 1.0, 1.0])
    s = DualStState(st24, st120)
    assert s.desired_position(1) == 0   # bar0 st24 0 not > 0
    assert s.desired_position(2) == 1   # st24 1, st120 1 fresh
    assert s.desired_position(3) == 1   # holds
    assert s.desired_position(4) == 0   # st24 -1 -> exit


def test_dualst_nan_safe():
    st24 = np.array([np.nan, 1.0, 1.0, -1.0])
    st120 = np.array([0.0, 1.0, 1.0, 1.0])
    s = DualStState(st24, st120)
    assert s.desired_position(1) == 0
    assert s.desired_position(2) == 0   # jguard


# --- S-69 StochKState: fresh stoch_k up-cross ---------------------------------

def test_stok_entry_exit():
    k = np.array([40.0, 55.0, 60.0, 35.0])
    close = np.array([100.0, 102.0, 103.0, 104.0])
    ema = np.array([99.0, 100.0, 101.0, 102.0])
    s = StochKState(k, close, ema, k_in=50.0, k_exit=40.0)
    assert s.desired_position(1) == 0   # bar0 40 < 50
    assert s.desired_position(2) == 1   # 55 > 50 fresh
    assert s.desired_position(3) == 1   # 60 > 40 holds
    assert s.desired_position(4) == 0   # 35 < 40 -> exit


def test_stok_nan_safe():
    k = np.array([np.nan, 55.0, 60.0, 35.0])
    close = np.array([100.0, 102.0, 103.0, 104.0])
    ema = np.array([99.0, 100.0, 101.0, 102.0])
    s = StochKState(k, close, ema, k_in=50.0, k_exit=40.0)
    assert s.desired_position(1) == 0
    assert s.desired_position(2) == 1   # NaN prev treated as fresh


# --- S-70 H1VolState: fresh h1_atr_pct low-vol coil -----------------------------

def test_h1vol_entry_exit():
    apct = np.array([0.01, 0.007, 0.006, 0.02])
    close = np.array([100.0, 102.0, 103.0, 104.0])
    ema = np.array([99.0, 100.0, 101.0, 102.0])
    s = H1VolState(apct, close, ema, k_in=0.008, k_exit=0.015)
    assert s.desired_position(1) == 0   # bar0 0.01 > 0.008
    assert s.desired_position(2) == 1   # 0.007 < 0.008, close 102 > ema 100 fresh
    assert s.desired_position(3) == 1   # 0.006 < 0.015 holds
    assert s.desired_position(4) == 0   # 0.02 > 0.015 -> exit


def test_h1vol_nan_safe():
    apct = np.array([np.nan, 0.007, 0.006, 0.02])
    close = np.array([100.0, 102.0, 103.0, 104.0])
    ema = np.array([99.0, 100.0, 101.0, 102.0])
    s = H1VolState(apct, close, ema, k_in=0.008, k_exit=0.015)
    assert s.desired_position(1) == 0
    assert s.desired_position(2) == 1   # NaN prev treated as fresh


# --- S-71 AroonStochState: fresh aroon+k+close/ema confluence ------------------

def test_aroondnstoch_entry_exit():
    a = np.array([50.0, 25.0, 20.0, 75.0])
    k = np.array([20.0, 30.0, 35.0, 10.0])
    close = np.array([100.0, 102.0, 103.0, 104.0])
    ema = np.array([99.0, 100.0, 101.0, 102.0])
    s = AroonStochState(a, k, close, ema, k_in=30.0, k_exit=70.0, d_in=25.0, d_exit=15.0)
    assert s.desired_position(1) == 0   # bar0 aroon 50 not < 30
    assert s.desired_position(2) == 1   # 25<30, 30>25, close>ema fresh
    assert s.desired_position(3) == 1   # aroon 20<70, k 35>15 holds
    assert s.desired_position(4) == 0   # aroon 75 > 70 -> exit


def test_aroondnstoch_nan_safe():
    a = np.array([np.nan, 25.0, 20.0, 75.0])
    k = np.array([np.nan, 30.0, 35.0, 10.0])
    close = np.array([100.0, 102.0, 103.0, 104.0])
    ema = np.array([99.0, 100.0, 101.0, 102.0])
    s = AroonStochState(a, k, close, ema, k_in=30.0, k_exit=70.0, d_in=25.0, d_exit=15.0)
    assert s.desired_position(1) == 0
    assert s.desired_position(2) == 0   # jguard: prev NaN -> suppresses fresh entry


# --- S-72 RocVolState: fresh roc up-cross with vol_rel>vmin -------------------

def test_rocvol_entry_exit():
    r = np.array([0.001, 0.006, 0.008, -0.002])
    vr = np.array([0.9, 1.2, 1.3, 1.1])
    s = RocVolState(r, vr, k_in=0.004, k_exit=0.0, vmin=1.0, vexit=0.8)
    assert s.desired_position(1) == 0   # bar0 0.001 < 0.004
    assert s.desired_position(2) == 1   # 0.006>0.004, vol 1.2>1.0 fresh
    assert s.desired_position(3) == 1   # holds
    assert s.desired_position(4) == 0   # -0.002 < 0.0 -> exit


def test_rocvol_requires_vol_confirm():
    r = np.array([0.001, 0.006, 0.008])
    vr = np.array([0.9, 0.9, 1.1])
    s = RocVolState(r, vr, k_in=0.004, k_exit=0.0, vmin=1.0, vexit=0.8)
    assert s.desired_position(2) == 0   # vol 0.9 < 1.0 -> no entry


def test_rocvol_nan_safe():
    r = np.array([np.nan, 0.006, 0.008, -0.002])
    vr = np.array([0.9, 1.2, 1.3, 1.1])
    s = RocVolState(r, vr, k_in=0.004, k_exit=0.0, vmin=1.0, vexit=0.8)
    assert s.desired_position(1) == 0
    assert s.desired_position(2) == 1   # NaN prev treated as fresh

# --- S-73 AroonUp60State: fresh aroon_up_60 up-cross -------------------------

def test_aroonup60_entry_exit():
    au = np.array([50.0, 75.0, 80.0, 35.0])
    s = AroonUp60State(au, k_in=70.0, k_exit=40.0)
    assert s.desired_position(1) == 0   # bar0 50 < 70
    assert s.desired_position(2) == 1   # 75 > 70 fresh
    assert s.desired_position(3) == 1   # 80 > 40 holds
    assert s.desired_position(4) == 0   # 35 < 40 -> exit


def test_aroonup60_nan_safe():
    au = np.array([np.nan, 75.0, 80.0, 35.0])
    s = AroonUp60State(au, k_in=70.0, k_exit=40.0)
    assert s.desired_position(1) == 0
    assert s.desired_position(2) == 1


# --- S-74 Willr60State: fresh willr_60 up-cross (rebound) --------------------

def test_willr60_entry_exit():
    w = np.array([-90.0, -45.0, -40.0, -85.0])
    s = Willr60State(w, k_in=-50.0, k_exit=-80.0)
    assert s.desired_position(1) == 0   # bar0 -90 < -50
    assert s.desired_position(2) == 1   # -45 > -50 fresh
    assert s.desired_position(3) == 1   # -40 > -80 holds
    assert s.desired_position(4) == 0   # -85 < -80 -> exit


def test_willr60_nan_safe():
    w = np.array([np.nan, -45.0, -40.0, -85.0])
    s = Willr60State(w, k_in=-50.0, k_exit=-80.0)
    assert s.desired_position(1) == 0
    assert s.desired_position(2) == 1


# --- S-75 Cci120State: fresh cci_120 up-cross --------------------------------

def test_cci120_entry_exit():
    c = np.array([50.0, 120.0, 150.0, 40.0])
    s = Cci120State(c, k_in=100.0, k_exit=50.0)
    assert s.desired_position(1) == 0   # bar0 50 < 100
    assert s.desired_position(2) == 1   # 120 > 100 fresh
    assert s.desired_position(3) == 1   # 150 > 50 holds
    assert s.desired_position(4) == 0   # 40 < 50 -> exit


def test_cci120_nan_safe():
    c = np.array([np.nan, 120.0, 150.0, 40.0])
    s = Cci120State(c, k_in=100.0, k_exit=50.0)
    assert s.desired_position(1) == 0
    assert s.desired_position(2) == 1


# --- S-76 StochK60State: fresh stoch_k_60 up-cross ---------------------------

def test_stochk60_entry_exit():
    k = np.array([60.0, 85.0, 90.0, 45.0])
    s = StochK60State(k, k_in=80.0, k_exit=50.0)
    assert s.desired_position(1) == 0   # bar0 60 < 80
    assert s.desired_position(2) == 1   # 85 > 80 fresh
    assert s.desired_position(3) == 1   # 90 > 50 holds
    assert s.desired_position(4) == 0   # 45 < 50 -> exit


def test_stochk60_nan_safe():
    k = np.array([np.nan, 85.0, 90.0, 45.0])
    s = StochK60State(k, k_in=80.0, k_exit=50.0)
    assert s.desired_position(1) == 0
    assert s.desired_position(2) == 1


# --- S-77 Mfi60State: fresh mfi_60 up-cross ----------------------------------

def test_mfi60_entry_exit():
    m = np.array([50.0, 85.0, 90.0, 50.0])
    s = Mfi60State(m, k_in=80.0, k_exit=55.0)
    assert s.desired_position(1) == 0   # bar0 50 < 80
    assert s.desired_position(2) == 1   # 85 > 80 fresh
    assert s.desired_position(3) == 1   # 90 > 55 holds
    assert s.desired_position(4) == 0   # 50 < 55 -> exit


def test_mfi60_nan_safe():
    m = np.array([np.nan, 85.0, 90.0, 50.0])
    s = Mfi60State(m, k_in=80.0, k_exit=55.0)
    assert s.desired_position(1) == 0
    assert s.desired_position(2) == 1


# --- S-78 AtrPct120State: fresh atr_pct_120 up-cross with close>ema ----------

def test_atrpct120_entry_exit():
    ap = np.array([0.002, 0.007, 0.009, 0.002])
    close = np.array([100.0, 102.0, 103.0, 104.0])
    ema = np.array([99.0, 100.0, 101.0, 102.0])
    s = AtrPct120State(ap, close, ema, k_in=0.006, k_exit=0.003)
    assert s.desired_position(1) == 0   # bar0 0.002 < 0.006
    assert s.desired_position(2) == 1   # 0.007 > 0.006, close 102 > ema 100 fresh
    assert s.desired_position(3) == 1   # 0.009 > 0.003 holds
    assert s.desired_position(4) == 0   # 0.002 < 0.003 -> exit


def test_atrpct120_requires_close_above_ema():
    ap = np.array([0.002, 0.007, 0.009])
    close = np.array([100.0, 99.0, 100.0])
    ema = np.array([99.0, 101.0, 102.0])
    s = AtrPct120State(ap, close, ema, k_in=0.006, k_exit=0.003)
    assert s.desired_position(2) == 0   # close 99 < ema 101 -> no entry


def test_atrpct120_nan_safe():
    ap = np.array([np.nan, 0.007, 0.009, 0.002])
    close = np.array([100.0, 102.0, 103.0, 104.0])
    ema = np.array([99.0, 100.0, 101.0, 102.0])
    s = AtrPct120State(ap, close, ema, k_in=0.006, k_exit=0.003)
    assert s.desired_position(1) == 0
    assert s.desired_position(2) == 1


# --- S-79 Roc120State: fresh roc_120 up-cross --------------------------------

def test_roc120_entry_exit():
    r = np.array([0.01, 0.03, 0.04, -0.01])
    s = Roc120State(r, k_in=0.02, k_exit=0.0)
    assert s.desired_position(1) == 0   # bar0 0.01 < 0.02
    assert s.desired_position(2) == 1   # 0.03 > 0.02 fresh
    assert s.desired_position(3) == 1   # 0.04 > 0.0 holds
    assert s.desired_position(4) == 0   # -0.01 < 0.0 -> exit


def test_roc120_nan_safe():
    r = np.array([np.nan, 0.03, 0.04, -0.01])
    s = Roc120State(r, k_in=0.02, k_exit=0.0)
    assert s.desired_position(1) == 0
    assert s.desired_position(2) == 1


# --- S-80 HourSinState: fresh hour_sin up-cross ------------------------------

def test_hoursin_entry_exit():
    h = np.array([-0.2, 0.6, 0.8, -0.6])
    s = HourSinState(h, k_in=0.5, k_exit=-0.5)
    assert s.desired_position(1) == 0   # bar0 -0.2 < 0.5
    assert s.desired_position(2) == 1   # 0.6 > 0.5 fresh
    assert s.desired_position(3) == 1   # 0.8 > -0.5 holds
    assert s.desired_position(4) == 0   # -0.6 < -0.5 -> exit


def test_hoursin_nan_safe():
    h = np.array([np.nan, 0.6, 0.8, -0.6])
    s = HourSinState(h, k_in=0.5, k_exit=-0.5)
    assert s.desired_position(1) == 0
    assert s.desired_position(2) == 1


# --- S-81 DowSinState: fresh dow_sin up-cross --------------------------------

def test_dowsin_entry_exit():
    d = np.array([-0.2, 0.6, 0.8, -0.6])
    s = DowSinState(d, k_in=0.5, k_exit=-0.5)
    assert s.desired_position(1) == 0   # bar0 -0.2 < 0.5
    assert s.desired_position(2) == 1   # 0.6 > 0.5 fresh
    assert s.desired_position(3) == 1   # 0.8 > -0.5 holds
    assert s.desired_position(4) == 0   # -0.6 < -0.5 -> exit


def test_dowsin_nan_safe():
    d = np.array([np.nan, 0.6, 0.8, -0.6])
    s = DowSinState(d, k_in=0.5, k_exit=-0.5)
    assert s.desired_position(1) == 0
    assert s.desired_position(2) == 1


# --- S-82 TrState: fresh true-range collapse ---------------------------------

def test_trcollapse_entry_exit():
    tr_ = np.array([0.002, 0.0008, 0.0006, 0.003])
    s = TrState(tr_, k_in=0.001, k_exit=0.002)
    assert s.desired_position(1) == 0   # bar0 0.002 > 0.001
    assert s.desired_position(2) == 1   # 0.0008 < 0.001 fresh
    assert s.desired_position(3) == 1   # 0.0006 < 0.002 holds
    assert s.desired_position(4) == 0   # 0.003 > 0.002 -> exit


def test_trcollapse_nan_safe():
    tr_ = np.array([np.nan, 0.0008, 0.0006, 0.003])
    s = TrState(tr_, k_in=0.001, k_exit=0.002)
    assert s.desired_position(1) == 0
    assert s.desired_position(2) == 1


# --- S-83 Psar002State: fresh slow-PSAR up-flip ------------------------------

def test_psar002_entry_exit():
    p = np.array([-1.0, 1.0, 1.0, -1.0])
    s = Psar002State(p)
    assert s.desired_position(1) == 0   # bar0 -1 not > 0
    assert s.desired_position(2) == 1   # 1 > 0 fresh
    assert s.desired_position(3) == 1   # 1 > 0 holds
    assert s.desired_position(4) == 0   # -1 <= 0 -> exit


def test_psar002_nan_safe():
    p = np.array([np.nan, 1.0, 1.0, -1.0])
    s = Psar002State(p)
    assert s.desired_position(1) == 0
    assert s.desired_position(2) == 1   # NaN prev treated as fresh


# --- S-84 StDual120State: fresh st120>0 and st24>0 ---------------------------

def test_stdual120_entry_exit():
    st120 = np.array([0.0, 1.0, 1.0, -1.0])
    st24 = np.array([0.0, 1.0, 1.0, 1.0])
    s = StDual120State(st120, st24)
    assert s.desired_position(1) == 0   # bar0 st120 0 not > 0
    assert s.desired_position(2) == 1   # both 1 fresh
    assert s.desired_position(3) == 1   # holds
    assert s.desired_position(4) == 0   # st120 -1 -> exit


def test_stdual120_nan_safe():
    st120 = np.array([np.nan, 1.0, 1.0, -1.0])
    st24 = np.array([0.0, 1.0, 1.0, 1.0])
    s = StDual120State(st120, st24)
    assert s.desired_position(1) == 0
    assert s.desired_position(2) == 0   # jguard: prev NaN -> suppressed


# --- S-85 H1St120State: fresh h1_st120>0 and st24>0 --------------------------

def test_h1st120_entry_exit():
    h1st = np.array([0.0, 1.0, 1.0, -1.0])
    st24 = np.array([0.0, 1.0, 1.0, 1.0])
    s = H1St120State(h1st, st24)
    assert s.desired_position(1) == 0   # bar0 h1st 0 not > 0
    assert s.desired_position(2) == 1   # both 1 fresh
    assert s.desired_position(3) == 1   # holds
    assert s.desired_position(4) == 0   # h1st -1 -> exit


def test_h1st120_nan_safe():
    h1st = np.array([np.nan, 1.0, 1.0, -1.0])
    st24 = np.array([0.0, 1.0, 1.0, 1.0])
    s = H1St120State(h1st, st24)
    assert s.desired_position(1) == 0
    assert s.desired_position(2) == 0   # jguard


# --- S-86 TimeConfluenceState: fresh hour+dow confluence ----------------------

def test_timeconf_entry_exit():
    h = np.array([-0.2, 0.6, 0.8, -0.6])
    d = np.array([0.1, 0.3, 0.4, -0.7])
    s = TimeConfluenceState(h, d, k_in=0.5, k_exit=-0.5, d_in=0.0, d_exit=-0.5)
    assert s.desired_position(1) == 0   # bar0 h -0.2 < 0.5
    assert s.desired_position(2) == 1   # h 0.6>0.5, d 0.3>0 fresh
    assert s.desired_position(3) == 1   # holds (h 0.8>-0.5, d 0.4>-0.5)
    assert s.desired_position(4) == 0   # d -0.7 < -0.5 -> exit


def test_timeconf_nan_safe():
    h = np.array([np.nan, 0.6, 0.8, -0.6])
    d = np.array([np.nan, 0.3, 0.4, -0.7])
    s = TimeConfluenceState(h, d, k_in=0.5, k_exit=-0.5, d_in=0.0, d_exit=-0.5)
    assert s.desired_position(1) == 0
    assert s.desired_position(2) == 1   # NaN prev -> fresh


# --- S-87 Roc120VolState: fresh roc_120 up-cross with vol_rel>vmin -----------

def test_roc120vol_entry_exit():
    r = np.array([0.01, 0.03, 0.04, -0.01])
    vr = np.array([0.9, 1.2, 1.3, 1.1])
    s = Roc120VolState(r, vr, k_in=0.02, k_exit=0.0, vmin=1.0, vexit=0.8)
    assert s.desired_position(1) == 0   # bar0 0.01 < 0.02
    assert s.desired_position(2) == 1   # 0.03>0.02, vol 1.2>1.0 fresh
    assert s.desired_position(3) == 1   # holds
    assert s.desired_position(4) == 0   # -0.01 < 0.0 -> exit


def test_roc120vol_requires_vol_confirm():
    r = np.array([0.01, 0.03, 0.04])
    vr = np.array([0.9, 0.9, 1.1])
    s = Roc120VolState(r, vr, k_in=0.02, k_exit=0.0, vmin=1.0, vexit=0.8)
    assert s.desired_position(2) == 0   # vol 0.9 < 1.0 -> no entry


def test_roc120vol_nan_safe():
    r = np.array([np.nan, 0.03, 0.04, -0.01])
    vr = np.array([0.9, 1.2, 1.3, 1.1])
    s = Roc120VolState(r, vr, k_in=0.02, k_exit=0.0, vmin=1.0, vexit=0.8)
    assert s.desired_position(1) == 0
    assert s.desired_position(2) == 1


# ================= Round 5: S-88..S-102 =================

# --- S-88 Rsi12State: fresh rsi_12 up-cross ----------------------------------

def test_rsi12_entry_exit():
    r = np.array([40.0, 60.0, 65.0, 35.0])
    s = Rsi12State(r, k_in=55.0, k_exit=40.0)
    assert s.desired_position(1) == 0   # 40 < 55
    assert s.desired_position(2) == 1   # 60 > 55 fresh
    assert s.desired_position(3) == 1   # 65 holds
    assert s.desired_position(4) == 0   # 35 < 40 exit


def test_rsi12_nan_safe():
    r = np.array([np.nan, 60.0, 65.0, 35.0])
    s = Rsi12State(r, k_in=55.0, k_exit=40.0)
    assert s.desired_position(1) == 0
    assert s.desired_position(2) == 1


def test_rsi12_no_reentry_while_holding():
    r = np.array([30.0, 70.0, 68.0, 67.0])
    s = Rsi12State(r, k_in=65.0, k_exit=60.0)
    assert s.desired_position(2) == 1   # 70 > 65 fresh
    assert s.desired_position(3) == 1   # 68 holds
    assert s.desired_position(4) == 1   # 67 > 60 holds


# --- S-89 Aroon12SpreadState: fresh up-cross of (au - ad) --------------------

def test_aroon12spread_entry_exit():
    au = np.array([40.0, 80.0, 85.0, 50.0])
    ad = np.array([55.0, 30.0, 20.0, 60.0])
    s = Aroon12SpreadState(au, ad, k_in=30.0, k_exit=5.0)
    assert s.desired_position(1) == 0   # spread -15
    assert s.desired_position(2) == 1   # spread 50 fresh > 30
    assert s.desired_position(3) == 1   # spread 65 holds
    assert s.desired_position(4) == 0   # spread -10 < 5 exit


def test_aroon12spread_nan_safe():
    au = np.array([np.nan, 20.0, 90.0])
    ad = np.array([55.0, 10.0, 10.0])
    s = Aroon12SpreadState(au, ad, k_in=30.0, k_exit=5.0)
    assert s.desired_position(1) == 0   # NaN bar
    assert s.desired_position(2) == 0   # spread +10 < 30
    assert s.desired_position(3) == 1   # spread +80 > 30 fresh (prev +10 finite)


def test_aroon12spread_requires_spread_confirm():
    au = np.array([40.0, 65.0, 80.0])
    ad = np.array([55.0, 50.0, 20.0])
    s = Aroon12SpreadState(au, ad, k_in=30.0, k_exit=5.0)
    assert s.desired_position(2) == 0   # spread 15 < 30
    assert s.desired_position(3) == 1   # spread 60 > 30 fresh


# --- S-90 MacdHist624State: fresh h>0 with close>EMA -------------------------

def test_macdh624_entry_exit():
    h = np.array([-1.0, 0.5, 0.3, -0.5])
    close_sig = np.array([100.0, 101.0, 102.0, 103.0])
    ema_sig = np.array([99.0, 99.5, 100.0, 101.0])
    s = MacdHist624State(h, close_sig, ema_sig)
    assert s.desired_position(1) == 0   # h -1 < 0
    assert s.desired_position(2) == 1   # h 0.5 > 0, close>ema fresh
    assert s.desired_position(3) == 1   # h 0.3 holds
    assert s.desired_position(4) == 0   # h -0.5 exit


def test_macdh624_nan_safe():
    h = np.array([np.nan, 0.5, 0.3, -0.5])
    close_sig = np.array([100.0, 101.0, 102.0, 103.0])
    ema_sig = np.array([99.0, 99.5, 100.0, 101.0])
    s = MacdHist624State(h, close_sig, ema_sig)
    assert s.desired_position(1) == 0
    assert s.desired_position(2) == 1


def test_macdh624_requires_close_above_ema():
    # fresh cross bar (h from -0.5 to +0.5) but close < ema -> rejected
    s = MacdHist624State(np.array([-1.0, -0.5, 0.5]),
                         np.array([100.0, 101.0, 98.0]),
                         np.array([99.0, 100.0, 99.5]))
    assert s.desired_position(3) == 0
    # same fresh cross, close > ema -> accepted
    s2 = MacdHist624State(np.array([-1.0, -0.5, 0.5]),
                          np.array([100.0, 101.0, 102.0]),
                          np.array([99.0, 100.0, 101.0]))
    assert s2.desired_position(3) == 1


# --- S-91 StochD12State: fresh stoch_d_12 up-cross ---------------------------

def test_stochd12_entry_exit():
    d = np.array([40.0, 60.0, 65.0, 35.0])
    s = StochD12State(d, k_in=55.0, k_exit=40.0)
    assert s.desired_position(1) == 0
    assert s.desired_position(2) == 1
    assert s.desired_position(3) == 1
    assert s.desired_position(4) == 0


def test_stochd12_nan_safe():
    d = np.array([np.nan, 60.0, 65.0, 35.0])
    s = StochD12State(d, k_in=55.0, k_exit=40.0)
    assert s.desired_position(1) == 0
    assert s.desired_position(2) == 1


def test_stochd12_threshold_strict():
    d = np.array([50.0, 55.0, 56.0])
    s = StochD12State(d, k_in=55.0, k_exit=40.0)
    assert s.desired_position(2) == 0   # 55 not > 55
    assert s.desired_position(3) == 1   # 56 > 55 fresh


# --- S-92 Mfi12State: fresh mfi_12 up-cross ----------------------------------

def test_mfi12_entry_exit():
    m = np.array([40.0, 65.0, 70.0, 42.0])
    s = Mfi12State(m, k_in=60.0, k_exit=45.0)
    assert s.desired_position(1) == 0
    assert s.desired_position(2) == 1
    assert s.desired_position(3) == 1
    assert s.desired_position(4) == 0


def test_mfi12_nan_safe():
    m = np.array([np.nan, 65.0, 70.0, 42.0])
    s = Mfi12State(m, k_in=60.0, k_exit=45.0)
    assert s.desired_position(1) == 0
    assert s.desired_position(2) == 1


def test_mfi12_exit_wide():
    m = np.array([30.0, 80.0, 50.0])
    s = Mfi12State(m, k_in=60.0, k_exit=55.0)
    assert s.desired_position(2) == 1
    assert s.desired_position(3) == 0   # 50 < 55 exit


# --- S-93 Willr12State: fresh willr_12 rebound up-cross ----------------------

def test_willr12_entry_exit():
    w = np.array([-90.0, -50.0, -45.0, -85.0])
    s = Willr12State(w, k_in=-60.0, k_exit=-80.0)
    assert s.desired_position(1) == 0
    assert s.desired_position(2) == 1
    assert s.desired_position(3) == 1
    assert s.desired_position(4) == 0


def test_willr12_nan_safe():
    w = np.array([np.nan, -50.0, -45.0, -85.0])
    s = Willr12State(w, k_in=-60.0, k_exit=-80.0)
    assert s.desired_position(1) == 0
    assert s.desired_position(2) == 1


def test_willr12_rebound_required():
    w = np.array([-95.0, -85.0, -55.0])
    s = Willr12State(w, k_in=-60.0, k_exit=-80.0)
    assert s.desired_position(2) == 0   # -85 < -60 -> no entry
    assert s.desired_position(3) == 1   # -55 > -60 fresh (prev -85 <= -60)


# --- S-94 Er12State: fresh er_12 up-cross ------------------------------------

def test_er12_entry_exit():
    e = np.array([0.1, 0.5, 0.55, 0.15])
    s = Er12State(e, k_in=0.4, k_exit=0.2)
    assert s.desired_position(1) == 0
    assert s.desired_position(2) == 1
    assert s.desired_position(3) == 1
    assert s.desired_position(4) == 0


def test_er12_nan_safe():
    e = np.array([np.nan, 0.5, 0.55, 0.15])
    s = Er12State(e, k_in=0.4, k_exit=0.2)
    assert s.desired_position(1) == 0
    assert s.desired_position(2) == 1


def test_er12_holds_above_exit():
    e = np.array([0.1, 0.6, 0.25])
    s = Er12State(e, k_in=0.4, k_exit=0.2)
    assert s.desired_position(2) == 1
    assert s.desired_position(3) == 1   # 0.25 > 0.2 holds


# --- S-95 Hv120State: fresh hv_120 down-cross (low-vol regime) ---------------

def test_hv120_entry_exit():
    hv = np.array([0.005, 0.0005, 0.0004, 0.004])
    s = Hv120State(hv, k_in=0.001, k_exit=0.003)
    assert s.desired_position(1) == 0   # 0.005 not < 0.001
    assert s.desired_position(2) == 1   # 0.0005 < 0.001 fresh
    assert s.desired_position(3) == 1   # 0.0004 holds
    assert s.desired_position(4) == 0   # 0.004 > 0.003 exit


def test_hv120_nan_safe():
    hv = np.array([np.nan, 0.0005, 0.0004, 0.004])
    s = Hv120State(hv, k_in=0.001, k_exit=0.003)
    assert s.desired_position(1) == 0
    assert s.desired_position(2) == 1


def test_hv120_looser_threshold():
    hv = np.array([0.01, 0.002, 0.0018])
    s = Hv120State(hv, k_in=0.002, k_exit=0.005)
    assert s.desired_position(2) == 0   # 0.002 not < 0.002
    assert s.desired_position(3) == 1   # 0.0018 < 0.002 fresh


# --- S-96 BbW60State: fresh bb_width_60 up-cross (squeeze release) -----------

def test_bbw60_entry_exit():
    w = np.array([0.001, 0.005, 0.006, 0.0012])
    s = BbW60State(w, k_in=0.004, k_exit=0.0015)
    assert s.desired_position(1) == 0
    assert s.desired_position(2) == 1   # 0.005 > 0.004 fresh
    assert s.desired_position(3) == 1
    assert s.desired_position(4) == 0   # 0.0012 < 0.0015 exit


def test_bbw60_nan_safe():
    w = np.array([np.nan, 0.005, 0.006, 0.0012])
    s = BbW60State(w, k_in=0.004, k_exit=0.0015)
    assert s.desired_position(1) == 0
    assert s.desired_position(2) == 1


def test_bbw60_release_strong():
    w = np.array([0.002, 0.003, 0.008])
    s = BbW60State(w, k_in=0.006, k_exit=0.002)
    assert s.desired_position(2) == 0   # 0.003 < 0.006 -> no entry
    assert s.desired_position(3) == 1   # 0.008 > 0.006 fresh (prev 0.003 <= 0.006)


# --- S-97 TriOscState: all 3 oscillators above entry -------------------------

def test_triosc_entry_exit():
    r = np.array([40.0, 60.0, 65.0, 42.0])
    k = np.array([40.0, 60.0, 65.0, 42.0])
    m = np.array([40.0, 60.0, 65.0, 42.0])
    s = TriOscState(r, k, m)
    assert s.desired_position(1) == 0
    assert s.desired_position(2) == 1
    assert s.desired_position(3) == 1
    assert s.desired_position(4) == 0   # any one below 45 exits


def test_triosc_nan_safe():
    r = np.array([np.nan, 60.0, 65.0])
    k = np.array([40.0, 60.0, 65.0])
    m = np.array([40.0, 60.0, 65.0])
    s = TriOscState(r, k, m)
    assert s.desired_position(1) == 0
    assert s.desired_position(2) == 1


def test_triosc_requires_all_confirm():
    r = np.array([40.0, 70.0, 70.0])
    k = np.array([40.0, 40.0, 70.0])   # bar1 k below 55 -> no entry
    m = np.array([40.0, 70.0, 70.0])
    s = TriOscState(r, k, m)
    assert s.desired_position(2) == 0
    assert s.desired_position(3) == 1   # all above, fresh


# --- S-98 QuadOscState: all 4 oscillators above entry ------------------------

def test_quadosc_entry_exit():
    r = np.array([40.0, 60.0, 65.0, 42.0])
    w = np.array([-90.0, -50.0, -45.0, -85.0])
    d = np.array([40.0, 60.0, 65.0, 42.0])
    m = np.array([40.0, 60.0, 65.0, 42.0])
    s = QuadOscState(r, w, d, m)
    assert s.desired_position(1) == 0
    assert s.desired_position(2) == 1
    assert s.desired_position(3) == 1
    assert s.desired_position(4) == 0


def test_quadosc_nan_safe():
    r = np.array([np.nan, 60.0, 65.0])
    w = np.array([-90.0, -50.0, -45.0])
    d = np.array([40.0, 60.0, 65.0])
    m = np.array([40.0, 60.0, 65.0])
    s = QuadOscState(r, w, d, m)
    assert s.desired_position(1) == 0
    assert s.desired_position(2) == 1


def test_quadosc_requires_willr_rebound():
    r = np.array([40.0, 70.0, 70.0])
    w = np.array([-95.0, -95.0, -40.0])   # bar1 willr too low -> no entry
    d = np.array([40.0, 70.0, 70.0])
    m = np.array([40.0, 70.0, 70.0])
    s = QuadOscState(r, w, d, m)
    assert s.desired_position(2) == 0
    assert s.desired_position(3) == 1


# --- S-99 Roc6VolrState: fresh roc_6 up-cross + vol + close>ema --------------

def test_roc6volr_entry_exit():
    r = np.array([0.001, 0.008, 0.01, -0.001])
    vr = np.array([0.9, 1.2, 1.3, 1.1])
    close_sig = np.array([100.0, 101.0, 102.0, 103.0])
    ema_sig = np.array([99.0, 99.5, 100.0, 101.0])
    s = Roc6VolrState(r, vr, close_sig, ema_sig)
    assert s.desired_position(1) == 0
    assert s.desired_position(2) == 1
    assert s.desired_position(3) == 1
    assert s.desired_position(4) == 0


def test_roc6volr_nan_safe():
    r = np.array([np.nan, 0.008, 0.01, -0.001])
    vr = np.array([0.9, 1.2, 1.3, 1.1])
    close_sig = np.array([100.0, 101.0, 102.0, 103.0])
    ema_sig = np.array([99.0, 99.5, 100.0, 101.0])
    s = Roc6VolrState(r, vr, close_sig, ema_sig)
    assert s.desired_position(1) == 0
    assert s.desired_position(2) == 1


def test_roc6volr_requires_vol_confirm():
    r = np.array([0.001, 0.003, 0.008])
    vr = np.array([1.2, 1.2, 0.9])
    close_sig = np.array([100.0, 101.0, 102.0])
    ema_sig = np.array([99.0, 100.0, 101.0])
    s = Roc6VolrState(r, vr, close_sig, ema_sig)
    assert s.desired_position(2) == 0   # r 0.003 < 0.005 -> no entry
    # fresh cross bar (r 0.008, prev 0.003 <= 0.005) but vol 0.9 < 1.0 -> rejected
    assert s.desired_position(3) == 0


# --- S-100 MacdCross624State: fresh macd > signal ----------------------------

def test_macdcross624_entry_exit():
    m = np.array([90.0, 100.0, 101.0, 89.0])
    sig = np.array([95.0, 98.0, 99.0, 92.0])
    s = MacdCross624State(m, sig)
    assert s.desired_position(1) == 0
    assert s.desired_position(2) == 1   # 100 > 98 fresh
    assert s.desired_position(3) == 1
    assert s.desired_position(4) == 0   # 89 < 92 exit


def test_macdcross624_nan_safe():
    m = np.array([np.nan, 90.0, 110.0])
    sig = np.array([95.0, 92.0, 100.0])
    s = MacdCross624State(m, sig)
    assert s.desired_position(1) == 0   # NaN bar
    assert s.desired_position(2) == 0   # 90 < 92 -> no cross
    assert s.desired_position(3) == 1   # 110 > 100 fresh (prev 90 > 92 false)


def test_macdcross624_no_reentry_while_above():
    m = np.array([80.0, 110.0, 105.0, 102.0])
    sig = np.array([90.0, 95.0, 97.0, 98.0])
    s = MacdCross624State(m, sig)
    assert s.desired_position(2) == 1
    assert s.desired_position(3) == 1
    assert s.desired_position(4) == 1


# --- S-101 Roc120Ema120State: fresh roc_120 + close>ema_120 -----------------

def test_roc120ema120_entry_exit():
    r = np.array([0.01, 0.03, 0.04, -0.01])
    close_sig = np.array([100.0, 102.0, 103.0, 98.0])
    ema120 = np.array([99.0, 101.0, 102.0, 101.0])
    s = Roc120Ema120State(r, close_sig, ema120)
    assert s.desired_position(1) == 0
    assert s.desired_position(2) == 1
    assert s.desired_position(3) == 1
    assert s.desired_position(4) == 0   # close 98 <= ema 101 exit


def test_roc120ema120_nan_safe():
    r = np.array([np.nan, 0.03, 0.04, -0.01])
    close_sig = np.array([100.0, 102.0, 103.0, 98.0])
    ema120 = np.array([99.0, 101.0, 102.0, 101.0])
    s = Roc120Ema120State(r, close_sig, ema120)
    assert s.desired_position(1) == 0
    assert s.desired_position(2) == 1


def test_roc120ema120_requires_close_above_ema():
    # fresh cross bar (r 0.03, prev 0.015 <= 0.02) but close < ema_120 -> rejected
    s = Roc120Ema120State(np.array([0.01, 0.015, 0.03]),
                          np.array([100.0, 101.0, 100.5]),
                          np.array([99.0, 100.5, 101.0]))
    assert s.desired_position(3) == 0
    # same fresh cross, close > ema_120 -> accepted
    s2 = Roc120Ema120State(np.array([0.01, 0.015, 0.03]),
                           np.array([100.0, 101.0, 103.0]),
                           np.array([99.0, 100.5, 102.0]))
    assert s2.desired_position(3) == 1


# --- S-102 DcPos12State: fresh dc_pos_12 up-cross ----------------------------

def test_dcpos12_entry_exit():
    p = np.array([0.3, 0.75, 0.8, 0.35])
    s = DcPos12State(p, k_in=0.7, k_exit=0.4)
    assert s.desired_position(1) == 0
    assert s.desired_position(2) == 1
    assert s.desired_position(3) == 1
    assert s.desired_position(4) == 0


def test_dcpos12_nan_safe():
    p = np.array([np.nan, 0.75, 0.8, 0.35])
    s = DcPos12State(p, k_in=0.7, k_exit=0.4)
    assert s.desired_position(1) == 0
    assert s.desired_position(2) == 1


def test_dcpos12_strict_threshold():
    p = np.array([0.5, 0.7, 0.72])
    s = DcPos12State(p, k_in=0.7, k_exit=0.4)
    assert s.desired_position(2) == 0   # 0.7 not > 0.7
    assert s.desired_position(3) == 1   # 0.72 > 0.7 fresh
