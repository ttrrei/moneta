"""Research the 200 composite entry features separately from portfolio exits.

Signal episodes are causal but independent of portfolio holdings/cooldowns.
This tests conditional forward information rather than using portfolio P&L
as evidence that a primitive indicator predicts direction.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from strategy.research_rules import entry_arrays
from strategy.feature_research import forward_labels,non_overlapping
from strategy.catalogue_research import CatalogueBootstrap,matched_inference


def decision_events(frame,features,spec,fit):
    direction,context,fresh,primary=entry_arrays(frame,features,spec,fit)
    n=len(frame);events=np.zeros(n,dtype=np.int8)
    times=pd.DatetimeIndex(frame.time).as_unit('ns').asi8
    adjacent=np.r_[False,np.diff(times)==3600_000_000_000]
    ready=(frame.n_bars.to_numpy()==60)&features.signal_complete.to_numpy(bool)&features.source_complete.to_numpy(bool)
    ready&=(features.htf_age_seconds.to_numpy()>=0)&(features.htf_age_seconds.to_numpy()<3600)
    close=frame.close.to_numpy(float);opening=frame.open.to_numpy(float);atr=frame.atr_24.to_numpy(float)
    if spec['episode']=='immediate':return np.where(ready&fresh,direction,0).astype(np.int8)
    armed=None;run=0
    for j in range(n):
        if not adjacent[j] or not ready[j]:armed=None;run=0
        if not ready[j]:continue
        run=run+1 if context[j] else 0
        episode=spec['episode']
        if episode=='persistent_context':
            if fresh[j] and run>=spec['persistence_hours']:events[j]=direction[j]
            continue
        if armed is not None:
            start,d,reference,scale=armed;age=j-start
            if age>spec['arm_hours']:armed=None
            elif age>0:
                progress=d*(close[j]-reference)
                if episode=='failure_reversal':
                    if progress<=-.5*scale and (close[j]-opening[j])*d<0:events[j]=-d;armed=None
                elif episode=='delayed_confirmation':
                    if context[j] and direction[j]==d:events[j]=d;armed=None
                elif abs(progress)<=.5*scale and (close[j]-opening[j])*d>0 and context[j]:events[j]=d;armed=None
        trigger=primary[j] if episode=='delayed_confirmation' else fresh[j]
        if not events[j] and armed is None and trigger and direction[j] and np.isfinite(atr[j]) and atr[j]>0:
            armed=(j,int(direction[j]),close[j],atr[j])
    return events


def fit_event_population(frame,features,events,protocol):
    time=pd.DatetimeIndex(frame.time).as_unit('ns')+pd.Timedelta(hours=1)
    m=protocol['matching']
    ready=(frame.n_bars.to_numpy()==60)&features.signal_complete.to_numpy(bool)&(frame.is_gap_bar.to_numpy()==0)
    train=ready&(time>=pd.Timestamp(m['train_start'],tz='UTC'))&(time<pd.Timestamp(m['train_end'],tz='UTC'))
    volatility=frame.atr_24.to_numpy(float)/frame.close.to_numpy(float)
    available=volatility[train&np.isfinite(volatility)]
    edges=np.unique(np.quantile(available,m['volatility_quantiles'])).tolist() if len(available) else []
    bins=np.searchsorted(edges,volatility,side='right')
    candidates=train&np.isin(events,[-1,1])
    strata=2*bins+(events==1).astype(int)
    retained=[];counts=[]
    for s in sorted(np.unique(strata[candidates])):
        count=int(np.sum(candidates&(strata==s)))
        controls=int(np.sum(train&(bins==s//2)))
        if min(count,controls)>=m['minimum_training_event_samples_per_stratum']:
            retained.append(int(s));counts.append(count)
    mass=sum(counts)/max(1,int(candidates.sum()))
    return {'control_edges':edges,'strata':retained,'weights':(np.array(counts)/max(1,sum(counts))).tolist(),
            'training_common_support_mass':mass,'identified':bool(retained) and mass>=m['minimum_common_support_mass']}


def analyze_entry_features(frame,features,specs,fits,portfolio_protocol,protocol,instrument):
    events_by_id={s['id']:decision_events(frame,features,s,fits[s['parent'] or s['id']]) for s in specs}
    population={sid:fit_event_population(frame,features,event,protocol) for sid,event in events_by_id.items()}
    labels=forward_labels(frame,protocol['holding_horizon_native_hours'],3600)
    r=labels['return_bps'];h=protocol['holding_horizon_native_hours']
    close=(pd.DatetimeIndex(frame.time).as_unit('ns')+pd.Timedelta(hours=1)).asi8
    volatility=frame.atr_24.to_numpy(float)/frame.close.to_numpy(float)
    rows=[];cells=[];coverage=[]
    for window in ('validation_1','validation_2'):
        bounds=portfolio_protocol['windows'][window]
        start,end=(pd.Timestamp(bounds[k],tz='UTC').value for k in ('start','end'))
        ready=(frame.n_bars.to_numpy()==60)&features.signal_complete.to_numpy(bool)&(frame.is_gap_bar.to_numpy()==0)
        mask=ready&(close>=start)&(close<end)
        eligible=mask&np.isfinite(r)&(labels['exit_ns']<end)
        bootstrap=CatalogueBootstrap(bounds['start'],bounds['end'],protocol['statistics'],f'entry_features:{instrument}:{window}')
        first=np.flatnonzero(mask);anchor=first[0] if len(first) else 0
        grid=(np.arange(len(frame))-anchor)%h==0
        for spec in specs:
            sid=spec['id'];events=events_by_id[sid];fit=population[sid]
            bins=np.searchsorted(fit['control_edges'],volatility,side='right')
            event_strata=2*bins+(events==1).astype(int)
            treated=non_overlapping(np.flatnonzero(eligible&np.isin(events,[-1,1])&np.isin(event_strata,fit['strata'])),h)
            control=np.flatnonzero(eligible&grid)
            indices=[];group=[];strata=[];direction=[]
            for d in (-1,1):
                s=2*bins[control]+int(d==1);keep=np.isin(s,fit['strata']);ix=control[keep]
                indices.extend(ix.tolist());group.extend([0]*len(ix));strata.extend(s[keep].tolist());direction.extend([d]*len(ix))
            indices.extend(treated.tolist());group.extend([1]*len(treated));strata.extend(event_strata[treated].tolist());direction.extend(events[treated].tolist())
            indices=np.array(indices,int);group=np.array(group,int);strata=np.array(strata,int);direction=np.array(direction,int)
            y=direction*r[indices]
            result,means,samples,cell_rows=matched_inference(np.arange(len(indices)),group,strata,y,close[indices],bootstrap,fit,protocol['statistics'])
            if result['supported']:
                effects=samples[:,1]-samples[:,0];valid=effects[np.isfinite(effects)]
                result['p_value']=float((1+np.sum(valid-result['effect_bps']>=result['effect_bps']))/(len(valid)+1))
            key={'strategy_id':sid,'entry_feature_id':'EF-'+sid,'round':spec['round'],'idea_id':spec['idea_id'],
                 'instrument':instrument,'window':window,'horizon_native_hours':h}
            row=key|result|{'matched_control_bps':means[0],'matched_event_bps':means[1],
                 'training_common_support_mass':fit['training_common_support_mass'],
                 'event_mean_cash_bps':float(np.mean(events[treated]*r[treated])) if len(treated) else np.nan,
                 'event_count_unthinned':int(np.sum(mask&np.isin(events,[-1,1])))}
            for cost in (0,2,5):
                raw_mean=float(np.mean(r[treated])) if len(treated) else np.nan
                row[f'event_net_cash_c{cost}_bps']=row['event_mean_cash_bps']-cost*raw_mean/10000-2*cost
            rows.append(row);cells.extend(key|cell for cell in cell_rows)
            coverage.append(key|{'closed_ready_hours':int(mask.sum()),'entry_events':int(np.sum(mask&np.isin(events,[-1,1]))),
                   'source_score_defined':int(np.sum(mask&np.isfinite(features[spec['score']].to_numpy(float)))),
                   'training_common_support_mass':fit['training_common_support_mass'],'identified':fit['identified']})
        print(f'Entry-feature research {instrument}/{window}: {len(specs)} composed features',flush=True)
    events=pd.DataFrame({'available_at':pd.to_datetime(close,utc=True),**events_by_id})
    return rows,cells,coverage,[{'strategy_id':sid,**fit} for sid,fit in population.items()],events
