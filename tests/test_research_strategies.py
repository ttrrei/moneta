"""Research-strategy registration, causal execution and equity-trace regression."""
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
import yaml

from strategy.engine import BarFrame,run_backtest
from strategy.research_rules import (PositionRule,build_positions,entry_arrays,fit_cuts,
                                     round1_registry,adapt_registry,semantic_hash)
from strategy.research_cohort import weekly_trace
from strategy.research_statistics import combine_tests


def protocol():return yaml.safe_load(Path('config/strategy_research_200.yml').read_text())
def records():return yaml.safe_load(Path('research/indicators/CATALOGUE-50-20261031/feature_registry.yml').read_text())


def fixture(n=150):
    c=100+np.sin(np.arange(n)/5)
    f=pd.DataFrame({'time':pd.date_range('2021-01-01',periods=n,freq='1h',tz='UTC'),
       'open':np.r_[100,c[:-1]],'close':c,'n_bars':60,'atr_24':1.,'is_gap_bar':0,'is_near_market_close':0})
    x=pd.DataFrame({'score':np.where(np.arange(n)%12<4,2.,0.),'direction':1.,'htf_direction':1.,'htf_er':.6,
       'median_stretch':-1.,'six_return_direction':1.,'signal_complete':True,'source_complete':True,'htf_age_seconds':0.})
    s={'id':'x','idea_id':'TR-01','score':'score','transform':'identity','comparison_kind':'tails','source_direction':'direction',
       'direction_multiplier':1,'target_role':'directed_return','style':'trend','entry_model':'trend_alignment','episode':'immediate',
       'hold_hours':6,'stop_atr':1.,'take_profit_atr':2.,'cooldown_hours':6,'tail':'high'}
    fit={'low':.1,'high':1.,'htf_er_median':.5}
    return f,x,s,fit


def test_complete_registry_has_one_hundred_unique_actual_rules():
    specs=round1_registry(records(),protocol())
    assert len(specs)==100 and len({s['id'] for s in specs})==100
    assert len({semantic_hash(s) for s in specs})==100
    assert {s['idea_id'] for s in specs}=={r['idea_id'] for r in records()}
    assert sum(s['target_role']=='directed_return' for s in specs)==72


def test_capture_equity_does_not_change_engine_results():
    f,x,s,fit=fixture();positions=build_positions(f,x,s,fit,'2020-07-01')
    bars=BarFrame(f.open.to_numpy(),f.close.to_numpy(),f.time.to_numpy(),3600)
    for cost in (0,2,5):
        plain=run_backtest(bars,PositionRule(positions),cost_bps=cost)
        traced=run_backtest(bars,PositionRule(positions),cost_bps=cost,capture_equity=True)
        assert plain.to_dict()==traced.to_dict() and plain.trades==traced.trades
        assert plain.equity_curve is None
        assert traced.equity_curve[-1]==pytest.approx(1+traced.raw_total_return_pct/100)


@pytest.mark.parametrize('episode',['immediate','delayed_confirmation','persistent_context','failure_reversal','pullback_confirmation'])
def test_positions_have_prefix_and_future_invariance(episode):
    f,x,s,fit=fixture();s.update(episode=episode,arm_hours=6,persistence_hours=6)
    full=build_positions(f,x,s,fit,'2020-07-01');cut=85
    np.testing.assert_array_equal(full[:cut],build_positions(f.iloc[:cut],x.iloc[:cut],s,fit,'2020-07-01'))
    changed=f.copy();changed.loc[cut:,'close']*=1.1
    future=x.copy();future.loc[cut:,'score']=100
    np.testing.assert_array_equal(full[:cut+1],build_positions(changed,future,s,fit,'2020-07-01')[:cut+1])


def test_activation_and_current_bar_completeness_are_not_future_entry_inputs():
    f,x,s,fit=fixture()
    late=build_positions(f,x,s,fit,'2021-01-03')
    assert not late[:48].any()
    baseline=build_positions(f,x,s,fit,'2020-07-01')
    entry=np.flatnonzero((baseline!=0)&(np.r_[0,baseline[:-1]]==0))[0]
    changed=f.copy();changed.loc[entry,'n_bars']=1
    # The fill at entry cannot know that entry bar will finish partial.
    assert build_positions(changed,x,s,fit,'2020-07-01')[entry]==baseline[entry]
    broken=f.copy();broken.loc[entry,'is_gap_bar']=1
    assert build_positions(broken,x,s,fit,'2020-07-01')[entry]==0


def test_frozen_atr_stops_fill_on_next_open_not_the_signal_close():
    f,x,s,fit=fixture(30)
    f.loc[1:,'close']=95.;f.loc[2:,'open']=94.
    # Later ATR spikes must not widen the stop frozen from the prior close.
    f.loc[1:,'atr_24']=1000.
    desired=build_positions(f,x,s,fit,'2020-07-01')
    assert desired[0]==0 and desired[1]==1 and desired[2]==0
    bars=BarFrame(f.open.to_numpy(),f.close.to_numpy(),f.time.to_numpy(),3600)
    result=run_backtest(bars,PositionRule(desired),cost_bps=2)
    first=result.trades[0]
    assert first.entry_time==1 and first.exit_time==2 and first.exit_price==94.


def test_failure_reversal_confirmation_requires_a_complete_closed_signal_bar():
    f,x,s,fit=fixture(30)
    s.update(episode='failure_reversal',arm_hours=6)
    f.loc[1,['open','close']]=[100.,99.]
    allowed=build_positions(f,x,s,fit,'2020-07-01')
    assert allowed[2]==-1
    f.loc[1,'n_bars']=59
    assert build_positions(f,x,s,fit,'2020-07-01')[2]==0


def test_calibration_cuts_ignore_later_values():
    f,x,s,_=fixture();train=np.arange(len(f))<60
    first=fit_cuts(x,train,[s]);x.loc[60:,'score']=1e9
    assert first==fit_cuts(x,train,[s])


def test_round_two_is_deterministic_and_uses_only_explicit_training_input():
    specs=round1_registry(records(),protocol());rows=[]
    for s in specs:
        for instrument in protocol()['instruments']:
            for cost in (0,2):
                rows.append({'strategy_id':s['id'],'instrument':instrument,'cost_bps':cost,
                 'n_trades':20,'avg_trade_return_pct':-.1,'total_return_pct':-2.-cost})
    children=adapt_registry(specs,pd.DataFrame(rows),protocol(),'a'*64)
    assert len(children)==100 and {c['episode'] for c in children}=={'failure_reversal'}
    assert len({c['semantic_hash'] for c in children})==100
    assert {c['parent'] for c in children}=={s['id'] for s in specs}
    contaminated=pd.DataFrame(rows);contaminated['window']='validation_2'
    with pytest.raises(ValueError,match='development_train'):
        adapt_registry(specs,contaminated,protocol(),'a'*64)


def test_weekly_trace_is_aligned_to_engine_equity_and_benchmark():
    f,x,s,fit=fixture(24*30)
    p=build_positions(f,x,s,fit,'2020-07-01');bars=BarFrame(f.open.to_numpy(),f.close.to_numpy(),f.time.to_numpy(),3600)
    result=run_backtest(bars,PositionRule(p),cost_bps=2,capture_equity=True)
    trace=weekly_trace(result.equity_curve,bars)
    np.testing.assert_allclose(trace.excess_log_bps,trace.strategy_log_bps-trace.buyhold_log_bps)


def test_total_testing_budget_includes_unrun_round_and_prior_feature_search():
    cfg=protocol();prior=pd.DataFrame({'p_value':np.ones(4410)})
    one=[{'strategy_id':'SR1-001','instrument':'EUR_USD','window':'validation_1','p_value':.001}]
    completed,inherited,pending=combine_tests(prior,one,cfg)
    assert len(inherited)==4410 and pending==1199 and len(completed)==1
    m=cfg['statistics']['planned_total_tests']
    minimum_q=m*sum(1/r for r in range(1,m+1))/(cfg['statistics']['bootstrap_replicates']+1)
    assert minimum_q<=cfg['statistics']['q_limit']
