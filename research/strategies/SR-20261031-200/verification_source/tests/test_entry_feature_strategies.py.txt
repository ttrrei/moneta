"""Independent temporal and sampling checks for the 200 composed entry features."""
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
import yaml

from test_research_strategies import fixture
from strategy.entry_feature_research import decision_events,fit_event_population,analyze_entry_features


@pytest.mark.parametrize('episode',['immediate','persistent_context','delayed_confirmation','failure_reversal','pullback_confirmation'])
def test_entry_feature_is_a_closed_bar_prefix_invariant_event(episode):
    f,x,s,fit=fixture(180);s.update(episode=episode,arm_hours=6,persistence_hours=6)
    full=decision_events(f,x,s,fit);cut=85
    np.testing.assert_array_equal(full[:cut],decision_events(f.iloc[:cut],x.iloc[:cut],s,fit))
    changed=f.copy();changed.loc[cut:,'close']*=1.1
    future=x.copy();future.loc[cut:,'score']=1e9
    np.testing.assert_array_equal(full[:cut],decision_events(changed,future,s,fit)[:cut])


def test_failure_event_emits_only_after_observed_failure_and_requires_complete_hour():
    f,x,s,fit=fixture(40);s.update(episode='failure_reversal',arm_hours=6)
    f.loc[1,['open','close']]=[100.,99.]
    events=decision_events(f,x,s,fit)
    assert events[0]==0 and events[1]==-1
    f.loc[1,'n_bars']=59
    assert decision_events(f,x,s,fit)[1]==0


def test_feature_events_are_separate_from_positions_and_cooldowns():
    from strategy.research_rules import entry_arrays
    f,x,s,fit=fixture()
    _,_,fresh,_=entry_arrays(f,x,s,fit)
    np.testing.assert_array_equal(decision_events(f,x,s,fit),np.where(fresh,1,0))
    s['cooldown_hours']=120
    np.testing.assert_array_equal(decision_events(f,x,s,fit),np.where(fresh,1,0))


def test_training_matching_population_does_not_read_validation_covariates():
    f,x,s,fit=fixture(2200)
    cfg=yaml.safe_load(Path('config/strategy_event_research_200.yml').read_text())
    cfg['matching'].update(train_start='2021-01-01',train_end='2021-03-01',minimum_training_event_samples_per_stratum=2)
    events=decision_events(f,x,s,fit);first=fit_event_population(f,x,events,cfg)
    changed=f.copy();changed.loc[changed.time>=pd.Timestamp('2021-03-01',tz='UTC'),'atr_24']=1e6
    assert first==fit_event_population(changed,x,events,cfg)


def test_joined_family_reserves_portfolio_and_entry_feature_trials():
    cfg=yaml.safe_load(Path('config/strategy_event_research_200.yml').read_text())
    st=cfg['statistics'];assert st['planned_total_tests']==st['prior_feature_tests']+st['portfolio_tests']+st['new_entry_feature_tests']==6810
    m=st['planned_total_tests'];minimum=m*sum(1/i for i in range(1,m+1))/(st['bootstrap_replicates']+1)
    assert minimum<=st['q_limit']
