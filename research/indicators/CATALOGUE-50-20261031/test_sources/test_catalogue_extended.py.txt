"""Formula oracles, event timelines and session/peer boundaries for the other 40 ideas."""
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
import yaml

from test_catalogue_features import frame as first_frame
from pipeline.catalogue_extended import (compute_catalogue_features,fit_calibration,session_ids,
                                         peer_features,quality,event_features)
from pipeline.indicators import session_reset_index,session_anchor


def frame(n=3000,freq='5min',instrument='EUR_USD'):
    f=first_frame(n,freq,instrument);x=np.arange(n)
    f['is_gap_bar']=0;f['volume']=10.+x%17
    f['rsi_6']=50+30*np.sin(x/13);f['er_60']=.5+.25*np.sin(x/19)
    f['hv_24']=.001+.0005*np.cos(x/17);f['cmf_24']=.5*np.sin(x/11)
    f['vol_rel_24']=f.volume/f.volume.rolling(24).mean();f['vol_ratio_6_24']=.5+abs(np.sin(x/15))
    for w in (6,12,60,120):f[f'ema_{w}']=f.close.ewm(span=w,adjust=False).mean()
    f['adx_24']=22+2*np.sin(x/19);f['plus_di_24']=20+5*np.sin(x/11);f['minus_di_24']=20-5*np.sin(x/11)
    f['dc_mid_24']=(f.dc_upper_24+f.dc_lower_24)/2
    return f


def fixture(n=3000):
    f,h=frame(n),frame(max(300,n//12+10),'1h')
    cal=fit_calibration(f,np.arange(len(f))<max(500,n//2))
    return f,h,cal


def test_all_fifty_ids_have_concrete_inputs_and_frozen_configs():
    f,h,cal=fixture();peer=frame(len(f),instrument='GBP_USD')
    out=compute_catalogue_features(f,h,calibration=cal,peer=peer)
    ids=[]
    for i in range(1,6):
        cfg=yaml.safe_load(Path(f'config/indicator_catalogue_batch{i}.yml').read_text())
        for idea,spec in cfg['ideas'].items():
            ids.append(idea)
            assert {spec['score'],spec['control'],spec['direction']} <= set(out),idea
    assert len(set(ids))==len(ids)==50
    assert not out.columns.duplicated().any()
    assert not np.isinf(out.select_dtypes(include='number').to_numpy()).any()


@pytest.mark.parametrize('cut',[80,500,1200,2500])
def test_all_extended_outputs_have_prefix_and_future_invariance(cut):
    f,h,cal=fixture();peer=frame(len(f),instrument='GBP_USD')
    full=compute_catalogue_features(f,h,calibration=cal,peer=peer)
    prefix=compute_catalogue_features(f.iloc[:cut],h,calibration=cal,peer=peer)
    pd.testing.assert_frame_equal(full.iloc[:cut],prefix,atol=1e-10,rtol=1e-10)
    changed=f.copy();names=changed.select_dtypes(include='number').columns.difference(['n_bars'])
    changed.loc[cut:,names]*=1.01
    changed_peer=peer.copy();changed_peer.loc[cut:,'close']*=1.02
    future=compute_catalogue_features(changed,h,calibration=cal,peer=changed_peer)
    pd.testing.assert_frame_equal(full.iloc[:cut],future.iloc[:cut],atol=1e-10,rtol=1e-10)


def test_calibration_never_uses_validation_covariates():
    f,_,_=fixture();train=np.arange(len(f))<1500
    first=fit_calibration(f,train)
    f.loc[1500:,'bb_width_24']=1000;f.loc[1500:,'rsi_6']=100;f.loc[1500:,'bar_clv']=-1
    assert first==fit_calibration(f,train)


def test_dst_anchor_uses_its_own_local_date_and_contiguous_session_identity():
    times=pd.Series(pd.to_datetime(['2024-03-10T10:00Z','2024-03-10T21:00Z',
                                    '2024-11-03T10:00Z','2024-11-03T22:00Z']))
    expected=pd.to_datetime(['2024-03-09T22:00Z','2024-03-10T21:00Z',
                             '2024-11-02T21:00Z','2024-11-03T22:00Z']).as_unit('ns').asi8
    np.testing.assert_array_equal(session_ids(times,'EUR_USD'),expected)
    hours=pd.Series(pd.date_range('2024-03-09T00:00Z','2024-03-12T00:00Z',freq='1h'))
    ids=session_reset_index(hours,session_anchor('EUR_USD'))
    assert np.diff(ids).min()>=0
    counts=np.unique(ids,return_counts=True)[1]
    assert 23 in counts  # spring-transition local session is 23 real hours


def test_session_activity_and_opening_range_do_not_read_later_session_values():
    f,h,cal=fixture(5000);f.instrument='BTC_USD';h.instrument='BTC_USD'
    out=compute_catalogue_features(f,h,calibration=cal)
    t=7*288+12
    earlier=[f.volume.iloc[t-k*288] for k in range(1,7)]
    assert out.session_activity_surprise.iloc[t]==pytest.approx(f.volume.iloc[t]/np.median(earlier))
    start=7*288
    initial=f.high.iloc[start:start+6].max()-f.low.iloc[start:start+6].min()
    assert out.initial_range_usage.iloc[start:start+5].isna().all()
    assert out.initial_range_usage.iloc[t]==pytest.approx((f.high.iloc[start:t+1].max()-f.low.iloc[start:t+1].min())/initial)
    price=(f.high+f.low+f.close)/3
    assert out.research_session_vwap.iloc[t]==pytest.approx((price.iloc[start:t+1]*f.volume.iloc[start:t+1]).sum()/f.volume.iloc[start:t+1].sum())


def test_peer_beta_and_residual_score_match_independent_lstsq():
    f=frame(300);peer=frame(300,instrument='GBP_USD')
    peer.close=peer.close+np.sin(np.arange(300)/6)*.01
    peer.high=np.maximum(peer.open,peer.close)+.1;peer.low=np.minimum(peer.open,peer.close)-.1
    good,adj,_=quality(f,300);out=peer_features(f,peer,good,adj)
    y=np.r_[np.nan,np.diff(np.log(f.close))];x=np.r_[np.nan,np.diff(np.log(peer.close))]
    t=200;residuals=[]
    for i in range(t-5,t+1):
        design=np.column_stack([np.ones(60),x[i-60:i]])
        coef=np.linalg.lstsq(design,y[i-60:i],rcond=None)[0]
        residuals.append(y[i]-np.array([1.,x[i]])@coef)
    past_design=np.column_stack([np.ones(60),x[t-60:t]])
    beta=np.linalg.lstsq(past_design,y[t-60:t],rcond=None)[0]
    scale=np.sqrt(np.mean((y[t-60:t]-past_design@beta)**2)*6)
    assert out['peer_residual_stretch'][t]==pytest.approx(sum(residuals)/scale,rel=1e-7)
    missing=peer.drop(index=190)
    assert np.isnan(peer_features(f,missing,good,adj)['peer_residual_stretch'][t])


def test_vector_formulas_for_ranges_wicks_scaling_and_path_features():
    f,h,cal=fixture();out=compute_catalogue_features(f,h,calibration=cal)
    r=np.r_[np.nan,np.diff(np.log(f.close))]
    for t in (200,700,1700):
        recent=slice(t-5,t+1);prior=slice(t-11,t-5)
        small=f.high.iloc[recent].max()-f.low.iloc[recent].min()
        large=f.high.iloc[t-23:t+1].max()-f.low.iloc[t-23:t+1].min()
        assert out.range_compression.iloc[t]==pytest.approx(-small/large)
        uw=f.high-np.maximum(f.open,f.close);lw=np.minimum(f.open,f.close)-f.low
        assert out.wick_imbalance.iloc[t]==pytest.approx((uw.iloc[recent]-lw.iloc[recent]).sum()/(f.high.iloc[recent]-f.low.iloc[recent]).sum())
        body=abs(f.close-f.open);span=f.high-f.low
        expected=body.iloc[recent].sum()/span.iloc[recent].sum()-body.iloc[prior].sum()/span.iloc[prior].sum()
        assert out.body_share_transition.iloc[t]==pytest.approx(expected)
        sums=np.array([r[i-5:i+1].sum() for i in range(t-119,t+1)])
        assert out.return_scaling.iloc[t]==pytest.approx(np.var(sums)/(6*np.var(r[t-119:t+1])))
        g=np.log(f.open/ f.close.shift(1));b=np.log(f.close/f.open)
        assert out.between_bar_share.iloc[t]==pytest.approx(np.sum(g.iloc[t-23:t+1]**2)/np.sum(g.iloc[t-23:t+1]**2+b.iloc[t-23:t+1]**2))
        table=np.zeros((3,3))
        for i in range(t-23,t+1):table[int(np.sign(r[i-1]))+1,int(np.sign(r[i]))+1]+=1
        prob=table/24;expected=0.
        for i in range(3):
            for j in range(3):
                if prob[i,j]>0:expected-=prob[i,j]*np.log(prob[i,j]/prob[i].sum())/np.log(3)
        assert out.transition_entropy.iloc[t]==pytest.approx(expected)


def test_gap_reset_and_start_independence_after_session_history():
    f,h,cal=fixture(6000)
    full=compute_catalogue_features(f,h,calibration=cal)
    later=compute_catalogue_features(f.iloc[300:],h,calibration=cal)
    pd.testing.assert_frame_equal(full.loc[4000:],later.loc[4000:],atol=1e-8,rtol=1e-8)
    f.loc[3000:,'time']+=pd.Timedelta(hours=2)
    reset=compute_catalogue_features(f,h,calibration=cal)
    assert reset.return_scaling.iloc[3000:3124].isna().all()
    assert reset.break_acceptance.iloc[3000:3006].isna().all()


def test_containment_release_and_six_bar_acceptance_are_confirmed_late():
    f,h,cal=fixture(200)
    f.loc[50,['high','low','open','close']]=[110,90,100,100]
    f.loc[51:55,['high','low','open','close']]=[105,95,100,101]
    f.loc[56,['high','low','open','close']]=[112,100,101,111]
    out=compute_catalogue_features(f,h,calibration=cal)
    assert out.mother_release_direction.iloc[56]==1
    good,adj,run=quality(f,300)
    upper=np.ones(len(f))*100;lower=np.ones(len(f))*90
    breaks=np.zeros(len(f));breaks[70]=1
    empty={name:np.zeros(len(f)) for name in ['swing_low_confirmed','swing_high_confirmed','swing_low_pivot_index','swing_high_pivot_index']}
    f.loc[70:76,'close']=101.;f.loc[70:76,'high']=102.;f.loc[70:76,'low']=99.;f.loc[70:76,'open']=100.
    events=event_features(f,good,adj,run,cal,empty,upper,lower,breaks)
    assert np.isnan(events['break_acceptance'][70:76]).all()
    assert events['break_acceptance'][76]==1
    assert events['acceptance_direction'][76]==1


def test_constant_prices_and_zero_scales_produce_no_infinite_values():
    f,h,cal=fixture()
    for table in (f,h):
        for name in ('open','high','low','close','ema_6','ema_12','ema_24','ema_60','ema_120','dc_upper_24','dc_lower_24','dc_mid_24'):table[name]=100.
        table.atr_24=0.;table.hv_24=0.;table.rsi_6=50.;table.vol_ratio_6_24=1.
    out=compute_catalogue_features(f,h,calibration=cal)
    assert not np.isinf(out.select_dtypes(include='number').to_numpy()).any()
    assert out.return_scaling.isna().all()


def test_between_bar_share_control_retains_real_closure_displacement():
    f,h,cal=fixture()
    f.loc[1000:,'time']+=pd.Timedelta(days=2)
    f.loc[1000:,'open']+=1.;f.loc[1000:,'close']+=1.;f.loc[1000:,'high']+=1.;f.loc[1000:,'low']+=1.
    f.loc[1000,'is_gap_bar']=1
    out=compute_catalogue_features(f,h,calibration=cal)
    assert np.isfinite(out.between_bar_share.iloc[1001])
    assert np.isfinite(out.observed_return_variance_24.iloc[1001])
    assert np.isnan(out.return_variance_24.iloc[1001])  # ordinary contiguous-path control intentionally differs


def test_event_state_oracles_for_compression_shock_reclaim_and_confirmed_levels():
    f=frame(180);good,adj,run=quality(f,300)
    f[['open','close','high','low','ema_24']]=[99.,99.,99.2,98.8,100.]
    f.atr_24=1.;f.bb_width_24=.02
    upper=np.ones(180)*100;lower=np.ones(180)*90;breaks=np.zeros(180)
    empty={name:np.zeros(180) for name in ['swing_low_confirmed','swing_high_confirmed','swing_low_pivot_index','swing_high_pivot_index']}
    cal={'bb_low':.01,'shock_high':2.}
    # Compression begins at 40 and releases at 43; the episode's range stays fixed.
    f.loc[40:45,'bb_width_24']=.005
    f.loc[43,['open','close','high','low']]=[99.,101.,101.2,98.8];breaks[43]=1
    # A shock at 70 can only have a six-bar decay observation on 76.
    f.loc[70,['open','close','high','low']]=[99.,103.,103.2,98.8]
    f.loc[71:76,['open','close','high','low']]=[103.,103.,103.2,102.8]
    # Freeze EMA=100 through six closes below it, then reclaim after arming.
    f.loc[100:105,['open','close','high','low']]=[99.,99.,99.2,98.8]
    f.loc[106,['open','close','high','low']]=[99.,101.,101.2,98.8]
    # A confirmed low at 120 is first approached after its six-bar exclusion.
    empty['swing_low_confirmed'][120]=1;empty['swing_low_pivot_index'][120]=114
    f.loc[114,'low']=97.;f.loc[126,'low']=97.1
    # An interruption gives a clean mean-reclaim timeline near 100.
    adj[99]=False
    out=event_features(f,good,adj,run,cal,empty,upper,lower,breaks)
    assert out['compressed_break_state'][43]==1
    assert np.isnan(out['shock_decay'][70:76]).all()
    assert out['shock_decay'][76]==pytest.approx(0.)
    assert out['mean_reclaim_state'][106]==1
    assert out['first_revisit_state'][126]==1 and out['revisit_direction'][126]==1
    assert out['level_cluster_density'][126]==0.  # level is 2 ATR from the closing price
