"""Training-only fits, matching, targets and cumulative trial accounting."""
from pathlib import Path
import numpy as np
import pandas as pd
import yaml
import pytest

from strategy.catalogue_research import (CatalogueBootstrap, fit_comparison, group_assignment,
                                         matched_inference, target_values, describe, analyze_catalogue)
from strategy.feature_research import WeekBootstrap


def settings():
    return {"seed": 7, "bootstrap_replicates": 99, "bootstrap_block_weeks": 4,
            "min_samples": 30, "min_active_weeks": 8, "min_cell_samples": 10,
            "tail_quantiles": [.2,.8], "control_quantiles": [1/3,2/3]}


def test_chunked_bootstrap_exactly_matches_existing_block_design():
    cfg = settings(); cfg["bootstrap_replicates"] = 4300
    first = CatalogueBootstrap("2020-01-01", "2021-01-01", cfg, "same")
    other = WeekBootstrap("2020-01-01", "2021-01-01", cfg, "same")
    np.testing.assert_array_equal(first.weights, other.weights)


def test_fit_uses_covariates_in_training_only_and_weights_sum_to_one():
    rng = np.random.default_rng(52)
    f = pd.DataFrame({"x": rng.normal(size=1000), "control": rng.normal(size=1000), "d": 1.})
    spec = {"score":"x", "control":"control", "direction":"d", "target":"directed_return", "kind":"tails"}
    training = np.arange(len(f)) < 700
    fit = fit_comparison(f, spec, training, settings())
    assert fit["identified"] and sum(fit["weights"]) == pytest.approx(1)
    f.loc[700:, ["x","control"]] = 1e6
    assert fit == fit_comparison(f, spec, training, settings())
    zero = f.copy(); zero.x = 1.
    assert not fit_comparison(zero, spec, training, settings())["identified"]


def test_nonoverlap_in_covariates_is_not_silently_claimed_as_matched():
    f = pd.DataFrame({"x": np.tile([0.,1.],100), "control":np.tile([0.,100.],100), "d":1.})
    spec = {"score":"x", "control":"control", "direction":"d", "target":"directed_return", "kind":"categorical"}
    fit = fit_comparison(f,spec,np.ones(len(f),bool),settings())
    assert not fit["identified"] and fit["training_common_support_mass"] == 0


def test_paired_matched_inference_agrees_with_hand_weighted_contrast():
    cfg = settings()
    b = CatalogueBootstrap("2020-01-01","2020-07-01",cfg,"cells")
    times = pd.date_range("2020-01-01",periods=24,freq="7D",tz="UTC").as_unit("ns").asi8
    close = np.repeat(times,4)
    group = np.tile([0,1,0,1],24); strata = np.tile([0,0,1,1],24)
    target = np.tile([1.,3.,10.,14.],24)
    fit = {"identified":True,"strata":[0,1],"weights":[.25,.75]}
    result, means, samples, cells = matched_inference(np.arange(96),group,strata,target,close,b,fit,cfg)
    assert result["supported"] and result["effect_bps"] == 3.5
    assert means == [7.75,11.25]
    np.testing.assert_allclose(samples[:,1]-samples[:,0],3.5)
    assert result["ci_low_bps"] == result["ci_high_bps"] == 3.5
    # A missing retained cell invalidates inference rather than changing weights.
    bad = np.flatnonzero(~((strata==1)&(group==1)))
    result,*_ = matched_inference(bad,group,strata,target,close,b,fit,cfg)
    assert not result["supported"] and result["p_value"] == 1


def test_targets_and_side_dependent_cash_fees():
    labels = {"return_bps":np.array([100.,-100.]),"mae_bps":np.array([-20.,-130.]),
              "mfe_bps":np.array([150.,30.]),"hours":np.ones(2),"gap_path":np.zeros(2),"partial_path":np.zeros(2)}
    d = np.array([1.,-1.])
    np.testing.assert_array_equal(target_values(labels,d,"directed_return"),[100,100])
    np.testing.assert_array_equal(target_values(labels,d,"absolute_return"),[100,100])
    np.testing.assert_array_equal(target_values(labels,d,"adverse_excursion"),[20,30])
    out = describe(np.arange(2),labels,d,target_values(labels,d,"directed_return"))
    assert out["directed_net_c2_bps"] == pytest.approx(96.)
    with pytest.raises(ValueError): target_values(labels,d,"invented")


def test_complete_grid_and_purged_label_counts_on_short_fixture():
    cfg = yaml.safe_load(Path('config/indicator_catalogue_batch1.yml').read_text())
    cfg['statistics'].update(bootstrap_replicates=19,min_samples=2,min_active_weeks=1,min_cell_samples=1)
    cfg['ideas']={'test':{'score':'x','control':'control','direction':'d','target':'directed_return','kind':'categorical'}}
    cfg['horizons']=[6,24]
    cfg['splits']={'train':{'start':'2020-01-01','end':'2020-01-04'},'validation_1':{'start':'2020-01-04','end':'2020-01-06'},'validation_2':{'start':'2020-01-06','end':'2020-01-08'}}
    n=2200; p=100+np.arange(n)*.01
    f=pd.DataFrame({'time':pd.date_range('2020-01-01',periods=n,freq='5min',tz='UTC'),'open':p,'close':p,'high':p+.01,'low':p-.01,'n_bars':5,'is_gap_bar':0})
    features=pd.DataFrame({'x':np.arange(n)%2,'control':np.arange(n)%3,'d':1.})
    c,g,cells,coverage,fitted=analyze_catalogue(f,features,cfg,'EUR_USD')
    assert len(c)==6 and len(g)==12 and len(coverage)==3
    for row in c:
        bound=pd.Timestamp(cfg['splits'][row['split']]['end'],tz='UTC')
        start=pd.Timestamp(cfg['splits'][row['split']]['start'],tz='UTC')
        available=sum((f.time+pd.Timedelta(minutes=5)>=start)&(f.time+pd.Timedelta(minutes=5)<bound))
        assert row['n_control']+row['n_treated'] <= available
    changed=features.copy();changed.loc[f.time>=pd.Timestamp('2020-01-04',tz='UTC'),'control']=1e9
    assert fitted==analyze_catalogue(f,changed,cfg,'EUR_USD')[-1]


def test_precision_covers_prior_p1_and_all_fifty_ideas():
    cfg=yaml.safe_load(Path('config/indicator_catalogue_batch1.yml').read_text())
    m=cfg['statistics']['prior_expected_tests']+cfg['statistics']['planned_catalogue_tests']
    minimum_q=m*sum(1/i for i in range(1,m+1))/(cfg['statistics']['bootstrap_replicates']+1)
    assert m==4410 and minimum_q<=cfg['statistics']['q_limit']
