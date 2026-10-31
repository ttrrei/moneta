"""Remaining forty catalogue ideas, with explicit causal calibration and state.

All thresholds are fitted to training covariates only, then passed unchanged
to prefix/validation computation. Existing Gold columns remain untouched.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from library.catalogue import capped_age
from library.market_structure import confirmed_structure
from pipeline.catalogue_features import (compute_catalogue_features as compute_first,
                                        quality, INPUT_COLUMNS as FIRST_INPUTS, HTF_COLUMNS as FIRST_HTF)
from pipeline.indicators import session_anchor, session_anchor_ns

INPUT_COLUMNS = tuple(dict.fromkeys(FIRST_INPUTS + ('is_gap_bar','volume','rsi_6','er_60','hv_24','cmf_24','vol_rel_24',
                        'vol_ratio_6_24','ema_6','ema_12','ema_60','ema_120')))
HTF_COLUMNS = tuple(dict.fromkeys(FIRST_HTF + ('adx_24','plus_di_24','minus_di_24','dc_mid_24','er_24')))


def lag(x, n=1):
    x=np.asarray(x,dtype=float);out=np.full(len(x),np.nan)
    if len(x)>n:out[n:]=x[:-n]
    return out


def divide(a,b):
    a,b=np.broadcast_arrays(np.asarray(a,float),np.asarray(b,float))
    return np.divide(a,b,out=np.full(a.shape,np.nan),where=np.isfinite(b)&(b!=0))


def rolling(x,n,method):
    return getattr(pd.Series(x).rolling(n,min_periods=n),method)().to_numpy()


def fit_calibration(frame, training):
    good,_,_=quality(frame,300)
    mask=np.asarray(training)&good&(np.arange(len(frame))>=258)&(frame.is_gap_bar.to_numpy()==0)
    def quantile(name,q,absolute=False):
        x=frame[name].to_numpy(float);x=np.abs(x) if absolute else x
        available=x[mask&np.isfinite(x)]
        return float(np.quantile(available,q)) if len(available) else np.nan
    # True range includes previous-close displacement, as the existing ATR input does.
    cprev=lag(frame.close)
    tr=np.maximum(frame.high-frame.low,np.maximum(abs(frame.high-cprev),abs(frame.low-cprev)))
    shock=divide(tr,lag(frame.atr_24))
    values=shock[mask&np.isfinite(shock)]
    return {'bb_low':quantile('bb_width_24',.2),
            'rsi_abs_extreme':float(np.quantile(abs(frame.rsi_6.to_numpy()[mask]-50),.8)) if mask.any() else np.nan,
            'clv_low':quantile('bar_clv',.2),'clv_high':quantile('bar_clv',.8),
            'shock_high':float(np.quantile(values,.8)) if len(values) else np.nan}


def session_ids(times, instrument):
    """Local anchor date resolved BEFORE timezone localization (DST-safe)."""
    return session_anchor_ns(times,session_anchor(instrument))


def session_features(frame,good,adjacent):
    n=len(frame);time=pd.DatetimeIndex(frame.time).as_unit('ns').asi8
    ids=session_ids(frame.time,frame.instrument.iloc[0]);codes,unique=pd.factorize(ids,sort=True)
    phase=(time-ids)/3.6e12
    c,o,h,l,v,a=(frame[name].to_numpy(float) for name in ('close','open','high','low','volume','atr_24'))
    tp=(h+l+c)/3
    valid_price=np.isfinite(tp)&(l>0)&np.isfinite(v)&(v>=0)
    table=pd.DataFrame({'session':codes,'pv':np.where(valid_price,tp*v,np.nan),'volume':np.where(valid_price,v,np.nan)})
    group=table.groupby('session',sort=False)
    vwap=divide(group.pv.cumsum(),group.volume.cumsum())
    # A separate research VWAP uses corrected local anchor instants; no Gold column changes.
    out={'session_phase':phase,'research_session_vwap':vwap,'session_vwap_stretch':divide(c-vwap,a),
         'session_reversal_direction':np.full(n,np.nan),'session_displacement_remaining':np.full(n,np.nan),
         'initial_range_usage':np.full(n,np.nan),'session_anchor_delay_minutes':np.full(n,np.nan)}
    out['vwap_reversal_direction']=-np.sign(out['session_vwap_stretch'])
    slot=((time-ids)//(300*1_000_000_000)).astype(int)
    activity=pd.DataFrame({'session':codes,'slot':slot,'v':np.where(good,v,np.nan)})
    # Distinct observed sessions, with no synthetic rows for closed calendar days.
    pivot=activity.pivot(index='session',columns='slot',values='v')
    historical=pivot.shift(1).rolling(6,min_periods=6).median()
    expected=historical.to_numpy()[codes,np.searchsorted(historical.columns.to_numpy(),slot)]
    out['session_activity_surprise']=divide(v,expected)
    starts=np.r_[0,np.flatnonzero(np.diff(codes)!=0)+1]
    ends=np.r_[starts[1:],n]
    for start,end in zip(starts,ends):
        ix=np.arange(start,end)
        delay=(time[start]-ids[start])/6e10
        out['session_anchor_delay_minutes'][ix]=delay
        anchored=delay<=120 and good[start]
        if anchored and start and good[start-1] and np.isfinite(a[start-1]) and a[start-1]>0:
            base=c[start-1];displacement=o[start]-base;sign=np.sign(displacement)
            for i in ix[:24]:
                if not good[i] or (i>start and not adjacent[i]):break
                if sign==0 or np.sign(c[i]-base)!=sign:break
                out['session_reversal_direction'][i]=-sign
                out['session_displacement_remaining'][i]=(c[i]-base)/a[start-1]
        first=ix[:6]
        if anchored and len(first)==6 and good[first].all() and adjacent[first[1:]].all():
            scale=np.max(h[first])-np.min(l[first])
            if scale>0:
                current_hi=np.maximum.accumulate(h[ix]);current_lo=np.minimum.accumulate(l[ix])
                out['initial_range_usage'][ix[5:]]=(current_hi[5:]-current_lo[5:])/scale
    return out


def hourly_features(frame,hourly):
    good,adjacent,run=quality(hourly,3600)
    a=hourly.atr_24.to_numpy(float);c=hourly.close.to_numpy(float)
    strength=divide(hourly.plus_di_24-hourly.minus_di_24,hourly.plus_di_24+hourly.minus_di_24)
    acceleration=(hourly.adx_24.to_numpy()-lag(hourly.adx_24,6))*abs(strength)
    migration=divide(hourly.dc_mid_24.to_numpy()-lag(hourly.dc_mid_24,6),a)
    acceleration[run<7]=np.nan;migration[run<7]=np.nan
    structure=confirmed_structure(hourly.high,hourly.low,c,a,good,np.r_[False,~adjacent[1:]],left=6,right=6,max_age=120)
    values={'strength_acceleration_along_direction':acceleration,'htf_di_direction':np.sign(strength),
            'htf_adx':hourly.adx_24.to_numpy(float),'htf_atr':a,'htf_range_migration':migration,
            'migration_direction':np.sign(migration),'htf_atr_pct':divide(a,c),
            'htf_er':hourly.er_24.to_numpy(float),
            'htf_confirmed_high':structure['last_confirmed_swing_high'],
            'htf_confirmed_low':structure['last_confirmed_swing_low']}
    for name in values:values[name]=np.where(good,values[name],np.nan)
    right=pd.DataFrame(values);right['source_close']=pd.DatetimeIndex(hourly.time).tz_convert('UTC').as_unit('ns')+pd.Timedelta(hours=1)
    left=pd.DataFrame({'decision_close':pd.DatetimeIndex(frame.time).tz_convert('UTC').as_unit('ns')+pd.Timedelta(minutes=5)})
    joined=pd.merge_asof(left,right,left_on='decision_close',right_on='source_close',direction='backward')
    age=(joined.decision_close-joined.source_close).dt.total_seconds().to_numpy()
    return {name:np.where((age>=0)&(age<3600),joined[name].to_numpy(float),np.nan) for name in values}


def peer_features(frame,peer,good,adjacent):
    n=len(frame);empty={'peer_residual_stretch':np.full(n,np.nan),'peer_reversal_direction':np.full(n,np.nan)}
    if peer is None:return empty
    pg,pa,_=quality(peer,300)
    rpeer=np.log(peer.close.to_numpy(float)/lag(peer.close))
    rpeer[~pg|~np.r_[False,pg[:-1]]|~pa]=np.nan
    left=pd.DataFrame({'time':pd.DatetimeIndex(frame.time).tz_convert('UTC').as_unit('ns')})
    right=pd.DataFrame({'time':pd.DatetimeIndex(peer.time).tz_convert('UTC').as_unit('ns'),'r':rpeer})
    x=left.merge(right,on='time',how='left',sort=False).r
    y=pd.Series(np.log(frame.close.to_numpy(float)/lag(frame.close)))
    y[~good|~np.r_[False,good[:-1]]|~adjacent]=np.nan
    both=x.notna()&y.notna();x=x.where(both);y=y.where(both)
    mx=x.rolling(60,min_periods=60).mean().shift(1);my=y.rolling(60,min_periods=60).mean().shift(1)
    vx=x.rolling(60,min_periods=60).var(ddof=0).shift(1)
    vy=y.rolling(60,min_periods=60).var(ddof=0).shift(1)
    cov=x.rolling(60,min_periods=60).cov(y,ddof=0).shift(1)
    beta=divide(cov,vx);alpha=my-beta*mx
    residual=y-alpha-beta*x
    scale=np.sqrt(np.maximum(vy-beta*cov,0)*6)
    score=divide(residual.rolling(6,min_periods=6).sum(),np.where(scale>1e-15,scale,np.nan))
    return {'peer_residual_stretch':score,'peer_reversal_direction':-np.sign(score)}


def event_features(frame,good,adjacent,run,calibration,structure,upper,lower,break_direction):
    n=len(frame);o,h,l,c,a=(frame[name].to_numpy(float) for name in ('open','high','low','close','atr_24'))
    names=('compressed_break_state','shock_decay','shock_size','shock_reversal_direction','break_acceptance',
           'break_observed_size','acceptance_direction','mean_reclaim_state','mean_episode_age','mean_reclaim_direction',
           'first_revisit_state','revisit_distance','revisit_direction','level_cluster_density','nearest_level_distance')
    out={name:np.full(n,np.nan) for name in names}
    width=frame.bb_width_24.to_numpy(float)
    tr=np.maximum(h-l,np.maximum(abs(h-lag(c)),abs(l-lag(c))))
    shock_ratio=divide(tr,lag(a));mean=frame.ema_24.to_numpy(float)
    compression=acceptance=shock=reclaim=None
    stretched=None;stretch_count=0;levels=[];visits={1:None,-1:None}
    for t in range(n):
        if not good[t] or not adjacent[t]:
            compression=acceptance=shock=reclaim=None;stretched=None;stretch_count=0;levels=[];visits={1:None,-1:None}
        if not good[t]:continue
        if break_direction[t]!=0 and np.isfinite(break_direction[t]):out['compressed_break_state'][t]=0.
        if compression is not None:
            start,u,d=compression;age=t-start
            side=1 if c[t]>u else -1 if c[t]<d else 0
            if age>6:compression=None
            elif side and age>0:
                if break_direction[t]==side:out['compressed_break_state'][t]=1.
                compression=None
        if (t and run[t]>=25 and width[t]<=calibration['bb_low'] and width[t-1]>calibration['bb_low']):
            compression=(t,upper[t],lower[t])
        if acceptance is not None:
            start,side,level,scale,initial,accepted=acceptance
            accepted+=int(c[t]>level if side==1 else c[t]<level)
            if t-start==6:
                out['break_acceptance'][t]=accepted/6
                out['acceptance_direction'][t]=side;out['break_observed_size'][t]=initial
                acceptance=None
            else:acceptance=(start,side,level,scale,initial,accepted)
        if acceptance is None and break_direction[t] in (-1,1) and a[t]>0:
            side=break_direction[t];level=upper[t] if side==1 else lower[t]
            acceptance=(t,side,level,a[t],abs(c[t]-level)/a[t],0)
        if shock is not None:
            start,side,price,scale,size=shock
            if t-start==6:
                out['shock_decay'][t]=-side*(c[t]-price)/(scale*size)
                out['shock_size'][t]=size;out['shock_reversal_direction'][t]=-side;shock=None
        if shock is None and run[t]>=2 and shock_ratio[t]>=calibration['shock_high'] and shock_ratio[t]>0 and c[t]!=c[t-1]:
            shock=(t,np.sign(c[t]-c[t-1]),c[t],a[t-1],shock_ratio[t])
        if reclaim is not None:
            start,side,level=reclaim;age=t-start
            if age>6:reclaim=None
            else:
                crossed=c[t]>level if side==1 else c[t]<level
                out['mean_reclaim_state'][t]=float(crossed)
                out['mean_episode_age'][t]=age;out['mean_reclaim_direction'][t]=side
                if crossed:reclaim=None
        if reclaim is None and stretched is None and t and np.isfinite(mean[t-1]):
            stretched=(mean[t-1],-np.sign(c[t]-mean[t-1]));stretch_count=0
        if reclaim is None and stretched is not None:
            level,side=stretched
            stayed=c[t]<level if side==1 else c[t]>level
            stretch_count=stretch_count+1 if stayed and side!=0 else 0
            if not stayed:stretched=None
            elif stretch_count==6:reclaim=(t,side,level);stretched=None
        # Contact freshness and level clustering use only confirmed pivots.
        revisit_candidates=[]
        for side,name in ((1,'low'),(-1,'high')):
            pending=visits[side]
            if pending is not None:
                start,level,scale,seen=pending;age=t-start
                if age>=120:visits[side]=None;continue
                extreme=l[t] if side==1 else h[t]
                contact=age>0 and scale>0 and abs(extreme-level)<=.25*scale
                if age>=6 and not seen and scale>0 and abs(extreme-level)<=scale:
                    # Wider near-contact controls are compared with first zone contacts.
                    revisit_candidates.append((float(contact),side,abs(c[t]-level)/scale))
                visits[side]=(start,level,scale,seen or contact)
        if len(revisit_candidates)==1:
            state,side,distance=revisit_candidates[0]
            out['first_revisit_state'][t]=state;out['revisit_direction'][t]=side;out['revisit_distance'][t]=distance
        for side,name in ((1,'low'),(-1,'high')):
            if structure[f'swing_{name}_confirmed'][t]==1:
                p=int(structure[f'swing_{name}_pivot_index'][t]);price=l[p] if side==1 else h[p]
                levels.append((t,price));visits[side]=(t,price,a[t],False)
        levels=[item for item in levels if t-item[0]<120]
        if levels and a[t]>0:
            distance=np.array([abs(price-c[t])/a[t] for _,price in levels])
            out['level_cluster_density'][t]=np.mean(distance<=.25)
            out['nearest_level_distance'][t]=np.min(distance)
    return out


def compute_catalogue_features(frame,hourly,*,window=24,age_cap=120,slope_lag=6,contact_tolerance_atr=.25,
                               calibration=None,peer=None):
    if calibration is None:raise ValueError('frozen training calibration required')
    missing=set(INPUT_COLUMNS)-set(frame);missing_h=set(HTF_COLUMNS)-set(hourly)
    if missing or missing_h:raise ValueError(f'missing extended inputs: {sorted(missing|missing_h)}')
    base=compute_first(frame,hourly,window=window,age_cap=age_cap,slope_lag=slope_lag,contact_tolerance_atr=contact_tolerance_atr)
    good,adjacent,run=quality(frame,300);n=len(frame)
    o,h,l,c,a=(frame[name].to_numpy(float) for name in ('open','high','low','close','atr_24'))
    r=np.log(c/lag(c));r[(run<2)|~adjacent]=np.nan
    extra=hourly_features(frame,hourly)
    extra.update(session_features(frame,good,adjacent));extra.update(peer_features(frame,peer,good,adjacent))
    e=frame.ema_24.to_numpy(float);slope=divide(e-lag(e,6),a);slope[run<7]=np.nan
    curvature=slope-lag(slope,6);curvature[run<13]=np.nan
    extra.update(slope_direction=np.sign(slope),slope_magnitude=abs(slope),oriented_trend_curvature=curvature*np.sign(slope))
    breadth=np.mean([np.sign(c-frame[f'ema_{w}'].to_numpy(float)) for w in (6,12,24,60,120)],axis=0)
    extra.update(trend_breadth=breadth,breadth_direction=np.sign(breadth))
    direction=base.ltf_direction.to_numpy(float)
    same=(direction==lag(direction)).astype(float)
    trend_age=np.full(n,np.nan);age=0
    return_age=np.full(n,np.nan);r_age=0
    for t in range(n):
        if not good[t]:age=r_age=0;continue
        age=min(120,age+1) if adjacent[t] and same[t] else 1
        trend_age[t]=age
        r_age=min(120,r_age+1) if t and adjacent[t] and np.sign(r[t])==np.sign(r[t-1]) and r[t]!=0 else 1
        if np.isfinite(r[t]) and r[t]!=0:return_age[t]=np.sign(r[t])*r_age
        else:r_age=0
    extra.update(trend_age=trend_age,return_run_age=return_age)
    aligned=base.trend_alignment.to_numpy(float)
    alignment_age=capped_age(aligned,good,adjacent,120)
    previous=lag(aligned);previous_direction=lag(direction)
    eligible=(previous==1)&np.isfinite(aligned)&adjacent
    extra.update(agreement_loss_state=np.where(eligible,(aligned==0).astype(float),np.nan),
                 prior_alignment_age=np.where(eligible,lag(alignment_age),np.nan),
                 prior_alignment_direction=np.where(eligible,previous_direction,np.nan),
                 trend_quality_mismatch=extra['htf_er']-frame.er_24.to_numpy(float))
    rsi=frame.rsi_6.to_numpy(float);extreme=abs(rsi-50)
    er60=frame.er_60.to_numpy(float)
    extra.update(rsi_extremity=extreme,rsi_reversal_direction=-np.sign(rsi-50),
                 oscillator_regime=np.where(extreme>=calibration['rsi_abs_extreme'],-er60,np.nan))
    price6=c-lag(c,6);change_rsi=rsi-lag(rsi,6)
    valid6=(run>=7)&(price6!=0)&(change_rsi!=0)
    extra.update(price_reversal_direction=np.where(valid6,-np.sign(price6),np.nan),
                 oscillator_disagreement=np.where(valid6,(np.sign(price6)!=np.sign(change_rsi)).astype(float),np.nan),
                 rsi_change_magnitude=np.where(valid6,abs(change_rsi),np.nan),
                 activity_disagreement=np.where(valid6&(frame.cmf_24.to_numpy()!=0),
                     (np.sign(price6)!=np.sign(frame.cmf_24)).astype(float),np.nan),
                 cmf_magnitude=abs(frame.cmf_24.to_numpy(float)))
    upper=lag(frame.dc_upper_24);lower=lag(frame.dc_lower_24)
    prior=lag(c)
    breaks=np.where((c>upper)&(prior<=upper),1.,np.where((c<lower)&(prior>=lower),-1.,0.))
    breaks[(run<25)|~np.isfinite(upper)|~np.isfinite(lower)]=np.nan
    break_mask=np.isin(breaks,[-1,1]);level=np.where(breaks==1,upper,lower)
    extra.update(range_break_direction=np.where(break_mask,breaks,np.nan),
                 break_distance=np.where(break_mask,divide(abs(c-level),a),np.nan),
                 break_activity=np.where(break_mask,frame.vol_rel_24,np.nan),
                 atr_ratio=frame.vol_ratio_6_24.to_numpy(float))
    small=rolling(h,6,'max')-rolling(l,6,'min');large=rolling(h,24,'max')-rolling(l,24,'min')
    extra['range_compression']=np.where(run>=24,-divide(small,large),np.nan)
    tr=np.maximum(h-l,np.maximum(abs(h-prior),abs(l-prior)));tr[run<2]=np.nan
    body_sum=rolling(c-o,6,'sum');body_ratio=divide(body_sum,rolling(tr,6,'sum'))
    extra.update(body_expansion=np.where((run>=7)&(frame.vol_ratio_6_24.to_numpy()>1),body_ratio,np.nan),
                 body_expansion_direction=np.sign(body_sum),
                 range_close_volatility=divide(divide(a,c),frame.hv_24),
                 volatility_instability=np.where(run>=24,rolling(frame.vol_ratio_6_24,24,'std'),np.nan))
    ups=rolling(np.where(np.isfinite(breaks),(breaks==1).astype(float),np.nan),24,'sum')
    downs=rolling(np.where(np.isfinite(breaks),(breaks==-1).astype(float),np.nan),24,'sum')
    balance=divide(ups-downs,ups+downs)
    extra.update(break_sequence_balance=balance,break_sequence_count=ups+downs,break_sequence_direction=np.sign(balance))
    wick_up=h-np.maximum(o,c);wick_down=np.minimum(o,c)-l
    wick=divide(rolling(wick_up-wick_down,6,'sum'),rolling(h-l,6,'sum'));wick[run<6]=np.nan
    extra.update(wick_imbalance=wick,wick_reversal_direction=-np.sign(wick),
                 last_wick_imbalance=abs(divide(wick_up-wick_down,h-l)))
    contained=np.zeros(n,bool);mother_side=np.full(n,np.nan)
    if n>=7:
        hv=np.lib.stride_tricks.sliding_window_view(h,5)
        lv=np.lib.stride_tricks.sliding_window_view(l,5)
        contained[6:]=(hv[1:-1]<=h[:-6,None]).all(axis=1)&(lv[1:-1]>=l[:-6,None]).all(axis=1)
        mother_side=np.where(contained&(c>lag(h,6)),1.,np.where(contained&(c<lag(l,6)),-1.,np.nan))
    mother_side[run<7]=np.nan
    extra.update(mother_release_direction=mother_side,
                 containment_release_state=np.where(break_mask,(mother_side==breaks).astype(float),np.nan))
    outside=(h>lag(h))&(l<lag(l))&(run>=2)
    clv=frame.bar_clv.to_numpy(float)
    extra.update(outside_settlement=np.where(outside,clv,np.nan),outside_direction=np.where(outside,np.sign(clv),np.nan),
                 outside_prior_position=np.where(outside,abs(divide(c-(lag(h)+lag(l))/2,lag(h)-lag(l))),np.nan))
    f_upper,f_lower,scale=lag(upper,6),lag(lower,6),lag(a,6)
    top_count=np.full(n,np.nan);bottom_count=top_count.copy()
    if n>=6:
        hv=np.lib.stride_tricks.sliding_window_view(h,6);lv=np.lib.stride_tricks.sliding_window_view(l,6);cv=np.lib.stride_tricks.sliding_window_view(c,6)
        inside=(cv>=f_lower[5:,None])&(cv<=f_upper[5:,None])
        top_count[5:]=np.sum(inside&(abs(hv-f_upper[5:,None])<=.25*scale[5:,None]),axis=1)
        bottom_count[5:]=np.sum(inside&(abs(lv-f_lower[5:,None])<=.25*scale[5:,None]),axis=1)
    contact_side=np.where(top_count>bottom_count,-1.,np.where(bottom_count>top_count,1.,np.nan))
    contact_side[run<31]=np.nan
    extra.update(boundary_tests=np.where(np.isfinite(contact_side),np.maximum(top_count,bottom_count),np.nan),
                 contact_reversal_direction=contact_side,
                 contact_distance=divide(np.where(contact_side==-1,abs(c-f_upper),abs(c-f_lower)),scale))
    strong=(lag(clv)<=calibration['clv_low'])|(lag(clv)>=calibration['clv_high'])
    previous_clv_direction=np.sign(lag(clv));confirmed=np.where(strong&(run>=2),divide(previous_clv_direction*(c-lag(c)),lag(a)),np.nan)
    extra.update(close_confirmation=confirmed,prior_clv_direction=previous_clv_direction,prior_clv_magnitude=abs(lag(clv)))
    body_share=divide(rolling(abs(c-o),6,'sum'),rolling(h-l,6,'sum'))
    extra.update(body_share_transition=np.where(run>=12,body_share-lag(body_share,6),np.nan),
                 recent_body_direction=np.sign(body_sum),prior_wick_magnitude=abs(lag(wick,6)))
    signs=np.sign(r);prev_sign=lag(signs);joint=[]
    for old in (-1,0,1):
        for new in (-1,0,1):
            state=np.where(np.isfinite(signs)&np.isfinite(prev_sign),((prev_sign==old)&(signs==new)).astype(float),np.nan)
            joint.append(rolling(state,24,'sum')/24)
    probabilities=np.stack(joint,axis=1).reshape(n,3,3)
    marginal=np.sum(probabilities,axis=2,keepdims=True)
    conditional=divide(probabilities,marginal)
    with np.errstate(divide='ignore',invalid='ignore'):
        terms=np.where(probabilities>0,probabilities*np.log(conditional),0.)
    entropy=-np.sum(terms,axis=(1,2))/np.log(3)
    entropy[~np.isfinite(probabilities).all(axis=(1,2))]=np.nan
    persistence=probabilities[:,0,0]+probabilities[:,2,2]-probabilities[:,0,2]-probabilities[:,2,0]
    extra.update(transition_entropy=entropy,transition_persistence=persistence,
                 turning_intensity=divide(rolling(abs(r-lag(r)),24,'sum'),rolling(abs(r),24,'sum')),
                 six_return_direction=np.sign(c-lag(c,6)))
    variance120=pd.Series(r).rolling(120,min_periods=120).var(ddof=0).to_numpy()
    sums6=rolling(r,6,'sum');sumvar=pd.Series(sums6).rolling(120,min_periods=120).var(ddof=0).to_numpy()
    extra.update(return_variance_120=variance120,return_scaling=divide(sumvar,6*variance120),
                 volatility_memory=pd.Series(abs(r)).rolling(24,min_periods=24).corr(pd.Series(abs(r)).shift(1)).clip(-1,1).to_numpy())
    g=np.log(o/lag(c));b=np.log(c/o);valid_pair=good&np.r_[False,good[:-1]]
    g[~valid_pair]=np.nan;b[~good]=np.nan
    between=rolling(g*g,24,'sum');within=rolling(b*b,24,'sum')
    extra['between_bar_share']=divide(between,between+within)
    observed_return=np.log(c/lag(c));observed_return[~valid_pair]=np.nan
    extra['observed_return_variance_24']=pd.Series(observed_return).rolling(24,min_periods=24).var(ddof=0).to_numpy()
    structure=confirmed_structure(h,l,c,a,good,np.r_[False,~adjacent[1:]],left=6,right=6,max_age=120)
    extra.update(event_features(frame,good,adjacent,run,calibration,structure,upper,lower,breaks))
    local_distance=np.fmin(abs(c-structure['last_confirmed_swing_high']),abs(c-structure['last_confirmed_swing_low']))
    high_distance=abs(c-extra['htf_confirmed_high']);low_distance=abs(c-extra['htf_confirmed_low'])
    htf_distance=np.fmin(high_distance,low_distance)
    extra.update(htf_structure_pressure=-divide(htf_distance,extra['htf_atr']),local_structure_distance=divide(local_distance,a))
    for name in ('hv_24','vol_rel_24'):extra[name]=frame[name].to_numpy(float)
    additions=pd.DataFrame(extra,index=frame.index)
    additions.loc[~good,:]=np.nan
    # Infinities are a formula error; do not silently turn them into plausible signals.
    if np.isinf(additions.to_numpy(float)).any():raise ValueError('infinite extended catalogue output')
    return pd.concat([base,additions],axis=1)
