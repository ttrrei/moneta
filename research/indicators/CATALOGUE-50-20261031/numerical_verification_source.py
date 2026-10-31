"""Audit all catalogue batches, source archives, matched estimates and replays.

Only archived development inputs are read. No protected market rows or
network access are needed. Assertions fail closed and no passing audit is
written when a check fails.
"""
from __future__ import annotations

import argparse
import importlib
import itertools
import json
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
import pandas as pd
import yaml

from scripts.research_indicators import sha
from scripts.research_catalogue import frame_digest
from strategy.feature_research import forward_labels
from strategy.strategy_lib import TIMEFRAME_PARQUET
from strategy.oos_token import holdout_start_date

ROOT=Path(__file__).resolve().parents[1]


def same(a,b):
    return bool(np.isclose(a,b,equal_nan=True,atol=1e-9,rtol=1e-9))


def independent_fit(features,spec,training,settings):
    score=features[spec['score']].to_numpy(float)
    if spec.get('transform')=='absolute':score=abs(score)
    direction=features[spec['direction']].to_numpy(float)
    control=features[spec['control']].to_numpy(float)
    valid=np.isfinite(score)&np.isfinite(control)
    if spec['target']!='absolute_return':valid&=np.isin(direction,[-1,1])
    if spec['score']=='squeeze_age':valid&=score>0
    mask=training&valid
    edges=[];tails=[];strata=np.zeros(len(score),int);groups=np.full(len(score),-1,int)
    if mask.any():
        if spec['control']=='ltf_direction':strata=(control>0).astype(int)
        else:
            edges=np.unique(np.quantile(control[mask],settings['control_quantiles'])).tolist()
            strata=np.searchsorted(edges,control,side='right')
        if spec['kind']=='categorical':
            groups[valid&(score==0)]=0;groups[valid&(score==1)]=1
        else:
            tails=np.quantile(score[mask],settings['tail_quantiles']).tolist()
            if tails[0]<tails[1]:
                groups[valid&(score<=tails[0])]=0;groups[valid&(score>=tails[1])]=1
    candidates=mask&(groups>=0);retained=[];counts=[]
    for s in sorted(set(strata[candidates])):
        cell=candidates&(strata==s)
        if min(sum(cell&(groups==0)),sum(cell&(groups==1)))>=settings['min_samples']:
            retained.append(int(s));counts.append(int(sum(cell)))
    mass=sum(counts)/max(1,sum(candidates))
    weights=(np.array(counts)/max(1,sum(counts))).tolist()
    fit={'control_edges':edges,'tail_edges':tails,'strata':retained,'weights':weights,
         'training_common_support_mass':mass,'identified':bool(retained) and mass>=settings['min_training_support_mass']}
    return fit,groups,strata,direction,valid


def verify(root,replay_root=None):
    holdout=pd.Timestamp(holdout_start_date(),tz='UTC');ledger=sha(ROOT/'strategy/oos_ledger.json')
    overall=[];raw_label_checks=0;matched_checks=0;prefix_checks=0;source_differences={}
    for batch in range(1,6):
        name=f'IR-20261031-CATALOGUE-B{batch}-v1';run=root/name
        manifest=yaml.safe_load((run/'manifest.yml').read_text());cfg=yaml.safe_load((run/'protocol.yml').read_text())
        assert manifest['status']=='completed' and manifest['completed_comparisons']==450
        assert manifest['ledger_sha256']==ledger
        assert sha(run/'protocol.yml')==manifest['protocol_sha256']
        for file,digest in manifest['artifacts'].items():assert sha(run/file)==digest,(batch,file)
        for file,digest in manifest['source_sha256'].items():assert sha(run/'source_snapshot'/file)==digest,(batch,file)
        for file,digest in manifest['prior_sha256'].items():assert sha(run/'prior_snapshot'/file)==digest,(batch,file)
        comparisons=pd.read_csv(run/'comparisons.csv');groups_csv=pd.read_csv(run/'conditional_returns.csv')
        keys=['idea_id','instrument','split','horizon']
        expected=set(itertools.product(cfg['ideas'],cfg['instruments'],cfg['splits'],cfg['horizons']))
        assert set(comparisons[keys].itertuples(index=False,name=None))==expected and not comparisons.duplicated(keys).any()
        assert (comparisons.loc[~comparisons.supported,'p_value']==1).all()
        assert not np.isinf(comparisons.select_dtypes(include='number').to_numpy()).any()
        assert len(groups_csv)==900
        fits=yaml.safe_load((run/'training_fits.yml').read_text());calibrations=yaml.safe_load((run/'calibrations.yml').read_text())
        module=importlib.import_module(cfg['feature_module'])
        for instrument in cfg['instruments']:
            records=[item for item in manifest['inputs'] if item['instrument']==instrument and item['role'].startswith('source')]
            data={}
            for item in records:
                file=Path(item['file']);assert sha(file)==item['sha256']
                f=pd.read_parquet(file);time=pd.DatetimeIndex(f.time)
                assert len(f)==item['rows'] and f.instrument.unique().tolist()==[instrument]
                assert time.is_monotonic_increasing and not time.has_duplicates and (time<holdout).all()
                assert frame_digest(f)==item['frame_sha256']
                stat=(ROOT/TIMEFRAME_PARQUET[item['timeframe']]).stat()
                assert stat.st_size==item['gold_size'] and stat.st_mtime_ns==item['gold_mtime_ns']
                data[item['role']]=f
            frame,hourly=data['source5m'],data['source1h']
            derived=next(x for x in manifest['derived'] if x['instrument']==instrument)
            assert sha(Path(derived['file']))==derived['sha256']
            features=pd.read_parquet(derived['file']);assert len(features)==len(frame)
            kwargs=dict(cfg['parameters'])
            if cfg.get('calibration'):
                saved=next(x for x in calibrations if x['instrument']==instrument)
                train_close=pd.DatetimeIndex(frame.time)+pd.Timedelta(minutes=5)
                train=(train_close>=pd.Timestamp(saved['train_start'],tz='UTC'))&(train_close<pd.Timestamp(saved['train_end'],tz='UTC'))
                fresh=module.fit_calibration(frame,train)
                for key,value in fresh.items():assert same(value,saved[key])
                kwargs['calibration']=saved
            if instrument in cfg.get('peer_instruments',{}):
                peer_id=cfg['peer_instruments'][instrument]
                record=next(x for x in manifest['inputs'] if x['instrument']==peer_id and x['role']=='peer5m')
                assert sha(Path(record['file']))==record['sha256']
                peer=pd.read_parquet(record['file']);assert (pd.DatetimeIndex(peer.time)<holdout).all()
                kwargs['peer']=peer
            prefix=module.compute_catalogue_features(frame.iloc[:10000],hourly,**kwargs)
            pd.testing.assert_frame_equal(features.iloc[:10000],prefix,atol=1e-10,rtol=1e-10)
            shorter=module.compute_catalogue_features(frame.iloc[:5000],hourly,**kwargs)
            pd.testing.assert_frame_equal(prefix.iloc[:5000],shorter,atol=1e-10,rtol=1e-10);prefix_checks+=1
            usable=features.trend_alignment.notna()
            assert (features.loc[usable,'source_close']<=features.loc[usable,'decision_close']).all()
            assert ((features.loc[usable,'htf_age_seconds']>=0)&(features.loc[usable,'htf_age_seconds']<3600)).all()
            close=(pd.DatetimeIndex(frame.time).as_unit('ns')+pd.Timedelta(minutes=5)).asi8
            ready=(np.arange(len(frame))>=cfg['context_rows'])&(frame.n_bars.to_numpy()==5)&(frame.is_gap_bar.to_numpy()==0)
            training=ready&(close>=pd.Timestamp(cfg['splits']['train']['start'],tz='UTC').value)&(close<pd.Timestamp(cfg['splits']['train']['end'],tz='UTC').value)
            labels={h:forward_labels(frame,h,300) for h in cfg['horizons']}
            if batch==1:
                for h,label in labels.items():
                    available=np.flatnonzero(np.isfinite(label['return_bps']))
                    for t in available[np.linspace(0,len(available)-1,200,dtype=int)]:
                        opening=frame.open.iloc[t+1];exit_price=frame.open.iloc[t+h+1]
                        hi=max(frame.high.iloc[t+1:t+h+1].max(),exit_price);lo=min(frame.low.iloc[t+1:t+h+1].min(),exit_price)
                        assert same(label['return_bps'][t],(exit_price/opening-1)*10000)
                        assert same(label['mfe_bps'][t],(hi/opening-1)*10000)
                        assert same(label['mae_bps'][t],(lo/opening-1)*10000);raw_label_checks+=1
            for idea,spec in cfg['ideas'].items():
                fit,assignment,strata,direction,valid=independent_fit(features,spec,training,cfg['statistics'])
                saved=next(x for x in fits if x['instrument']==instrument and x['idea_id']==idea)
                for key in fit:
                    if key in ('identified','strata'):assert saved[key]==fit[key]
                    else:np.testing.assert_allclose(saved[key],fit[key],atol=1e-12)
                domain=valid&np.isin(strata,fit['strata'])&(assignment>=0)
                for split,bounds in cfg['splits'].items():
                    start,end=(pd.Timestamp(bounds[k],tz='UTC').value for k in ('start','end'))
                    mask=ready&(close>=start)&(close<end)
                    for h,label in labels.items():
                        r=label['return_bps']
                        target=direction*r if spec['target']=='directed_return' else abs(r) if spec['target']=='absolute_return' else np.where(direction==1,-label['mae_bps'],label['mfe_bps'])
                        eligible=mask&domain&np.isfinite(r)&np.isfinite(target)&(label['exit_ns']<end)
                        if spec['kind']=='categorical':
                            selected=[];next_row=-1
                            for i in np.flatnonzero(eligible):
                                if i>=next_row:selected.append(i);next_row=i+h
                            ix=np.asarray(selected,dtype=int)
                        else:
                            first=np.flatnonzero(mask);anchor=first[0] if len(first) else 0
                            ix=np.flatnonzero(eligible&((np.arange(len(frame))-anchor)%h==0))
                        assert len(ix)<2 or np.diff(ix).min()>=h
                        row=comparisons[(comparisons.idea_id==idea)&(comparisons.instrument==instrument)&(comparisons.split==split)&(comparisons.horizon==h)].iloc[0]
                        means=[]
                        for arm in (0,1):
                            arm_ix=ix[assignment[ix]==arm]
                            assert len(arm_ix)==row['n_control' if arm==0 else 'n_treated']
                            record=groups_csv[(groups_csv.idea_id==idea)&(groups_csv.instrument==instrument)&(groups_csv.split==split)&(groups_csv.horizon==h)&(groups_csv.arm==arm)].iloc[0]
                            raw_mean=np.mean(r[arm_ix]) if len(arm_ix) else np.nan
                            assert same(record.raw_mean_bps,raw_mean)
                            matched=0. if fit['strata'] else np.nan
                            for s,w in zip(fit['strata'],fit['weights']):
                                cell=arm_ix[strata[arm_ix]==s]
                                matched+=w*(np.mean(target[cell]) if len(cell) else np.nan)
                            assert same(record.target_matched_mean_bps,matched);means.append(matched)
                            for cost in (0,2,5):
                                assert same(record[f'long_net_c{cost}_bps'],raw_mean*(1-cost/10000)-2*cost)
                                assert same(record[f'short_net_c{cost}_bps'],-raw_mean*(1+cost/10000)-2*cost)
                        assert same(row.effect_bps,means[1]-means[0]);matched_checks+=1
        replay={}
        if replay_root:
            other=replay_root/name;second=yaml.safe_load((other/'manifest.yml').read_text())
            assert second['status']=='completed' and second['protocol_sha256']==manifest['protocol_sha256']
            for file,digest in manifest['artifacts'].items():assert sha(other/file)==digest,(batch,'replay',file)
            for original,repeat in zip(manifest['inputs']+manifest['derived'],second['inputs']+second['derived']):
                digest_key='sha256';assert original[digest_key]==repeat[digest_key]
            differences=[k for k,v in manifest['source_sha256'].items() if second['source_sha256'].get(k)!=v]
            if batch==1:
                assert set(differences)<={'config/indicator_catalogue_batch5.yml','scripts/research_catalogue.py'}
            else:assert not differences
            source_differences[name]=differences
            replay={'artifact_files':len(manifest['artifacts']),'data_files':len(manifest['inputs'])+len(manifest['derived']),'status':'byte-identical'}
        overall.append({'batch':batch,'ideas':len(cfg['ideas']),'comparisons':len(comparisons),'supported':int(comparisons.supported.sum()),'replay':replay})
    final=pd.read_csv(root/'IR-20261031-CATALOGUE-B5-v1/cumulative_tests.csv')
    assert len(final)==4410 and (final.status=='completed').all()
    catalogue=final[final.study=='catalogue']
    assert len(catalogue)==2250 and catalogue.idea_id.nunique()==50
    order=np.argsort(final.p_value.to_numpy(),kind='stable');m=len(final)
    harmonic=sum(1/i for i in range(1,m+1));adjusted=np.ones(m);tail=1.
    for rank in range(m,0,-1):
        original=order[rank-1];tail=min(tail,final.p_value.iloc[original]*m*harmonic/rank);adjusted[original]=tail
    np.testing.assert_allclose(final.q_global,adjusted,atol=1e-12)
    completed=pd.concat([pd.read_csv(root/f'IR-20261031-CATALOGUE-B{b}-v1/comparisons.csv') for b in range(1,6)],ignore_index=True)
    q_lookup=catalogue.set_index(['idea_id','instrument','split','horizon']).q_global
    decision_rows=pd.read_csv(root/'IR-20261031-CATALOGUE-B5-v1/catalogue_decisions.csv').set_index('idea_id')
    assert len(decision_rows)==50 and not decision_rows.strategy_promotion.any()
    for batch in range(1,6):
        cfg=yaml.safe_load((root/f'IR-20261031-CATALOGUE-B{batch}-v1/protocol.yml').read_text())
        for idea,spec in cfg['ideas'].items():
            supported_h=replicated_h=0
            for h in cfg['horizons']:
                covered=replicated=0
                for instrument in cfg['instruments']:
                    rows=completed[(completed.idea_id==idea)&(completed.instrument==instrument)&(completed.horizon==h)].set_index('split')
                    if not rows.supported.all():continue
                    covered+=1
                    sign=1 if spec['expected']=='positive' or rows.loc['train','effect_bps']>=0 else -1
                    passed=True
                    for split in ('validation_1','validation_2'):
                        lower=rows.loc[split,'ci_low_bps'] if sign==1 else -rows.loc[split,'ci_high_bps']
                        passed &= bool(lower>0 and q_lookup.loc[(idea,instrument,split,h)]<=cfg['statistics']['q_limit'])
                    replicated+=passed
                supported_h+=covered>=2;replicated_h+=replicated>=2
            expected='keep_context' if replicated_h and spec['target']!='directed_return' else 'keep_research' if replicated_h else 'reject' if supported_h else 'revise'
            row=decision_rows.loc[idea]
            assert row.decision==expected and row.supported_horizons==supported_h and row.replicated_horizons==replicated_h
    assert sha(ROOT/'strategy/oos_ledger.json')==ledger
    return {'status':'passed','batches':overall,'catalogue_ideas':50,'catalogue_comparisons':2250,'family_comparisons':4410,
            'direct_forward_label_checks':raw_label_checks,'independent_matched_estimate_checks':matched_checks,
            'real_prefix_checks':prefix_checks,'independent_decision_checks':50,
            'ledger_sha256':ledger,'replay_source_context_differences':source_differences,
            'source_difference_explanation':'Batch 1 predates a later-batch closure-control correction and calibration-provenance metadata; active protocol/math and every result/data artifact replay identically.',
            'verification_script_sha256':sha(Path(__file__))}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--root',type=Path,default=Path('research/indicators'))
    parser.add_argument('--replay-root',type=Path);parser.add_argument('--out',type=Path,required=True);args=parser.parse_args()
    if args.out.exists():raise ValueError('refusing existing audit path')
    result=verify(args.root,args.replay_root);args.out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
