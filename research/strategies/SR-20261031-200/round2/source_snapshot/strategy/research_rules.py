"""Causal portfolio rules for the explicitly requested 100 + 100 research cohort.

Signal features retain their native computation units. Decisions/fills are on
native 1h bars. All pricing and return accounting remain in strategy.engine.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd


class PositionRule:
    def __init__(self, positions):
        self.positions = np.asarray(positions, dtype=np.int8)

    def desired_position(self, i):
        return int(self.positions[i])


def semantic_hash(spec):
    fields = ('idea_id','entry_model','episode','score','transform','tail','source_direction',
              'direction_multiplier','target_role','style','hold_hours','cooldown_hours','stop_atr','take_profit_atr',
              'arm_hours','persistence_hours')
    body={key:spec.get(key) for key in fields}
    return hashlib.sha256(json.dumps(body,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def round1_registry(feature_records, protocol):
    """Register the entire first round before strategy code sees outcomes."""
    records=[]
    for feature in sorted(feature_records,key=lambda row:row['idea_id']):
        idea=feature['idea_id'];role=feature['target']
        for model in ('trend_alignment','candle_confirmation'):
            direction_multiplier=-1 if idea in ('PS-02','PS-03','PS-05') and role=='directed_return' else 1
            tail='low' if role=='adverse_excursion' or idea=='PS-09' else 'high'
            spec={'id':f'SR1-{len(records)+1:03}','round':1,'idea_id':idea,'name':f"{feature['name']} / {model}",
                  'score':feature['score'],'transform':feature['transform'],'comparison_kind':feature['comparison_kind'],
                  'source_direction':feature['direction'],'style':feature['style'],'target_role':role,
                  'direction_multiplier':direction_multiplier,'tail':tail,'entry_model':model,'episode':'immediate',
                  **protocol['round1'],'hypothesis':hypothesis(idea,role,model,'immediate'),
                  'difference':'New catalogue feature/context and exact hourly execution; differs from prior S-series raw-indicator rules.',
                  'expected_full_history_trades':'20-150; empirical breaches remain failures',
                  'status':'registered_before_outcomes','parent':None}
            spec['semantic_hash']=semantic_hash(spec);records.append(spec)
    if len(records)!=100 or len({x['semantic_hash'] for x in records})!=100:
        raise ValueError('first round must have 100 semantically distinct rules')
    return records


def hypothesis(idea,role,model,episode):
    purpose='entry direction' if role=='directed_return' else 'movement/risk context for an independent direction model'
    return f'{idea} supplies {purpose}; {model} with {episode} may filter weak entries, and may fail through delay, costs or regime change.'


def adapt_registry(parents,training_rows,protocol,analysis_hash):
    if 'window' in training_rows and not (training_rows.window=='development_train').all():
        raise ValueError('round-two adaptation may only read development_train outcomes')
    records=[]
    for parent in parents:
        rows=training_rows[training_rows.strategy_id==parent['id']]
        gross=rows[rows.cost_bps==0];net=rows[rows.cost_bps==2]
        if len(gross)!=3 or len(net)!=3:raise ValueError('adaptation needs all three training assets and costs')
        count=int(gross.n_trades.sum())
        gross_mean=float(gross.avg_trade_return_pct.mean())
        drag=float((gross.total_return_pct.to_numpy()-net.total_return_pct.to_numpy()).mean())
        if count==0:episode='delayed_confirmation'
        elif gross_mean<0:episode='failure_reversal'
        elif gross.n_trades.max()>300 or drag>max(2.,abs(float(gross.total_return_pct.mean()))):episode='persistent_context'
        else:episode='pullback_confirmation'
        spec={**parent,**{k:v for k,v in protocol['round2'].items() if k not in ('arm_hours','persistence_hours')},
              'id':f'SR2-{len(records)+1:03}','round':2,'parent':parent['id'],'episode':episode,
              'arm_hours':protocol['round2']['arm_hours'],'persistence_hours':protocol['round2']['persistence_hours'],
              'hypothesis':hypothesis(parent['idea_id'],parent['target_role'],parent['entry_model'],episode),
              'adaptation_source':'development_train only','parent_training_trades':count,
              'parent_training_mean_gross_trade_pct':gross_mean,'parent_training_cost_drag_pct':drag,
              'parent_analysis_sha256':analysis_hash,'status':'registered_before_outcomes'}
        spec['semantic_hash']=semantic_hash(spec);records.append(spec)
    if len(records)!=100 or len({x['semantic_hash'] for x in records})!=100:
        raise ValueError('second round must have 100 semantically distinct rules')
    return records


def fit_cuts(features,training,records):
    """Fits covariates only, before the first live decision; no forward label."""
    fits={}
    for spec in records:
        x=features[spec['score']].to_numpy(float)
        if spec['transform']=='absolute':x=abs(x)
        available=x[training&np.isfinite(x)]
        er=features.htf_er.to_numpy(float)
        er_train=er[training&np.isfinite(er)]
        fits[spec['id']]={'low':float(np.quantile(available,.2)) if len(available) else np.nan,
                           'high':float(np.quantile(available,.8)) if len(available) else np.nan,
                           'htf_er_median':float(np.median(er_train)) if len(er_train) else np.nan,
                           'calibration_rows':len(available)}
    return fits


def primary_condition(features,spec,fit):
    x=features[spec['score']].to_numpy(float)
    if spec['transform']=='absolute':x=abs(x)
    valid=np.isfinite(x)
    if spec['comparison_kind']=='categorical':
        condition=x==(0 if spec['tail']=='low' else 1)
    else:
        threshold=fit['low' if spec['tail']=='low' else 'high']
        condition=x<=threshold if spec['tail']=='low' else x>=threshold
    if spec['idea_id']=='CB-01':valid&=x>0
    return condition&valid


def entry_arrays(frame,features,spec,fit):
    n=len(frame);condition=primary_condition(features,spec,fit)
    htf=features.htf_direction.to_numpy(float)
    body=np.sign(frame.close.to_numpy()-frame.open.to_numpy())
    # The confirming body is the already completed native hourly candle.
    er=features.htf_er.to_numpy(float)
    if spec['target_role']=='directed_return':
        direction=features[spec['source_direction']].to_numpy(float)*spec['direction_multiplier']
    elif spec['entry_model']=='trend_alignment':direction=htf.copy()
    else:direction=-np.sign(features.median_stretch.to_numpy(float))
    valid_direction=np.isin(direction,[-1,1])
    if spec['entry_model']=='trend_alignment':
        context=(direction==htf)&np.isin(htf,[-1,1])
        if spec['target_role']!='directed_return':
            context&=features.six_return_direction.to_numpy()==direction
    else:
        efficient=spec['style'] in ('trend','compression')
        regime=er>=fit['htf_er_median'] if efficient else er<=fit['htf_er_median']
        context=(body==direction)&regime
    signal_good=(frame.n_bars.to_numpy()==60)&features.signal_complete.to_numpy(bool)
    # Context sources are complete, already closed and less than one hour old.
    context_good=features.source_complete.to_numpy(bool)&(features.htf_age_seconds.to_numpy()>=0)&(features.htf_age_seconds.to_numpy()<3600)
    primary=condition&valid_direction&signal_good&context_good
    setup=primary&context
    same=np.r_[False,(direction[1:]==direction[:-1])&setup[:-1]]
    fresh=setup&~same
    primary_fresh=primary&~np.r_[False,(direction[1:]==direction[:-1])&primary[:-1]]
    clean_direction=np.where(np.isin(direction,[-1,1]),direction,0).astype(np.int8)
    return clean_direction,context&signal_good&context_good,fresh,primary_fresh


def build_positions(frame,features,spec,fit,activation):
    """Closed-bar decisions with frozen entry ATR and causal episode lifetimes.

    Only price/feature information from j=i-1 is consulted for the fill at i.
    Current i's gap/near-close clocks are known at its open; its eventual
    completeness/high/low/close are never used to accept that entry.
    """
    n=len(frame);directions,context,fresh,primary=entry_arrays(frame,features,spec,fit)
    pos=np.zeros(n,dtype=np.int8)
    times=pd.DatetimeIndex(frame.time).as_unit('ns').asi8
    activation=pd.Timestamp(activation,tz='UTC').value
    prices=frame.close.to_numpy(float);opens=frame.open.to_numpy(float);atr=frame.atr_24.to_numpy(float)
    blocked=(frame.is_gap_bar.to_numpy()!=0)|(frame.is_near_market_close.to_numpy()!=0)
    entry_ready=(frame.n_bars.to_numpy()==60)&features.signal_complete.to_numpy(bool)&features.source_complete.to_numpy(bool)
    entry_ready&=(features.htf_age_seconds.to_numpy()>=0)&(features.htf_age_seconds.to_numpy()<3600)
    adjacent=np.r_[False,np.diff(times)==3600_000_000_000]
    side=0;entry=-1;entry_price=scale=np.nan;cooldown_until=-1;armed=None
    context_run=np.zeros(n,dtype=int)
    for j in range(n):
        context_run[j]=(context_run[j-1]+1 if j and adjacent[j] else 1) if context[j] else 0
    for i in range(1,n):
        j=i-1;want=side
        if side:
            progress=side*(prices[j]-entry_price)
            held=i-entry
            stop=progress<=-spec['stop_atr']*scale
            take=progress>=spec['take_profit_atr']*scale
            if stop or take or held>=spec['hold_hours']:
                want=0;cooldown_until=i+spec['cooldown_hours'];armed=None
        elif i>=cooldown_until and times[i]>=activation and adjacent[i] and not blocked[i] and entry_ready[j]:
            candidate=0
            episode=spec['episode']
            if episode=='immediate':candidate=int(directions[j]) if fresh[j] else 0
            elif episode=='persistent_context':
                candidate=int(directions[j]) if fresh[j] and context_run[j]>=spec['persistence_hours'] else 0
            else:
                if armed is not None:
                    start,d,reference,reference_atr=armed;age=j-start
                    if age>spec['arm_hours'] or not adjacent[j]:armed=None
                    elif age>0:
                        progress=d*(prices[j]-reference)
                        if episode=='failure_reversal':
                            confirmed=progress<=-.5*reference_atr and (prices[j]-frame.open.iloc[j])*d<0
                            if confirmed:candidate=-d;armed=None
                        elif episode=='delayed_confirmation':
                            if context[j] and directions[j]==d:candidate=d;armed=None
                        else:
                            # A later pullback near the trigger close, with the
                            # current completed body resuming the frozen side.
                            if abs(progress)<=.5*reference_atr and (prices[j]-frame.open.iloc[j])*d>0 and context[j]:
                                candidate=d;armed=None
                trigger=primary[j] if episode=='delayed_confirmation' else fresh[j]
                if armed is None and trigger and directions[j]!=0 and np.isfinite(atr[j]) and atr[j]>0:
                    armed=(j,int(directions[j]),prices[j],atr[j])
            if candidate and np.isfinite(atr[j]) and atr[j]>0:
                want=candidate;entry=i;entry_price=opens[i];scale=atr[j];armed=None
        if not adjacent[i]:armed=None
        side=want;pos[i]=side
    return pos
