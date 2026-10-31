"""Audit portfolio accounting, causal inputs, both research layers and replays."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys
import json

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
import pandas as pd
import yaml

from strategy.research_cohort import sha,positions_for_window
from strategy.research_rules import adapt_registry,semantic_hash,build_positions,fit_cuts
from strategy.entry_feature_research import decision_events
from strategy.oos_token import holdout_start_date

ROOT=Path(__file__).resolve().parents[1]


def independent_q(p):
    p=np.asarray(p,float);m=len(p);order=np.argsort(p,kind='stable');out=np.ones(m)
    harmonic=sum(1/i for i in range(1,m+1));tail=1.
    for rank in range(m,0,-1):
        i=order[rank-1];tail=min(tail,p[i]*m*harmonic/rank);out[i]=tail
    return out


def verify(root,cache,replay=None,event_replay=None):
    protocol=yaml.safe_load((root/'protocol.yml').read_text())
    ledger=sha(ROOT/'strategy/oos_ledger.json');holdout=pd.Timestamp(holdout_start_date(),tz='UTC')
    prepared=yaml.safe_load((cache/'manifest.yml').read_text())
    for name,digest in prepared['files'].items():assert sha(cache/name)==digest,name
    all_specs=[];all_metrics=[];corrected=[];parent_comparisons=[];replays=[]
    accounting_groups=fill_checks=prefix_checks=0
    for number in (1,2):
        out=root/f'round{number}';m=yaml.safe_load((out/'manifest.yml').read_text())
        assert m['status']=='completed' and m['strategies']==100 and m['matrix_cells']==4500
        assert m['ledger_sha256']==ledger and m['prepared_manifest_sha256']==sha(cache/'manifest.yml')
        for name,digest in m['source_sha256'].items():assert sha(out/'source_snapshot'/name)==digest
        for name,digest in m['artifacts'].items():assert sha(out/name)==digest,(number,name)
        specs=yaml.safe_load((out/'registry.yml').read_text());assert len(specs)==100
        assert len({s['semantic_hash'] for s in specs})==100
        for spec in specs:assert semantic_hash(spec)==spec['semantic_hash']
        all_specs.extend(specs)
        metrics=pd.read_csv(out/'metrics.csv');all_metrics.append(metrics)
        expected={(s['id'],a,w,c) for s in specs for a in protocol['instruments'] for w in protocol['windows'] for c in protocol['cost_bps_one_way']}
        keys=['strategy_id','instrument','window','cost_bps']
        assert len(metrics)==4500 and not metrics.duplicated(keys).any()
        assert set(metrics[keys].itertuples(index=False,name=None))==expected
        trades=pd.read_csv(out/'trades_c2.csv');weekly=pd.read_csv(out/'weekly_c2.csv')
        for instrument in protocol['instruments']:
            frame=pd.read_parquet(cache/f'{instrument}_bars.parquet');features=pd.read_parquet(cache/f'{instrument}_features.parquet')
            fits=yaml.safe_load((cache/f'{instrument}_cuts.yml').read_text())
            time=pd.DatetimeIndex(frame.time)
            assert (time<holdout).all() and time.is_monotonic_increasing and not time.has_duplicates
            good=features.signal_complete.to_numpy(bool)
            assert (features.loc[good,'feature_close']==features.loc[good,'decision_close']).all()
            hour_close=time.as_unit('ns')+pd.Timedelta(hours=1)
            assert (features.feature_close==hour_close).all()
            training=(hour_close>=pd.Timestamp(protocol['calibration']['start'],tz='UTC'))&(hour_close<pd.Timestamp(protocol['calibration']['end'],tz='UTC'))&(frame.n_bars.to_numpy()==60)&good
            originals=yaml.safe_load((root/'round1_registry.yml').read_text())
            recalibrated=fit_cuts(features,training,originals)
            for sid,fit in recalibrated.items():
                for key,value in fit.items():assert np.isclose(value,fits[sid][key],equal_nan=True),('calibration',sid,key)
            for spec in specs:
                fit=fits[spec['parent'] or spec['id']]
                for window,bounds in protocol['windows'].items():
                    f,x,p,bars=positions_for_window(frame,features,spec,fit,protocol['calibration']['end'],bounds)
                    assert p[0]==0 and not ((p[1:]*p[:-1])==-1).any()
                    entries=np.flatnonzero((p!=0)&(np.r_[0,p[:-1]]==0))
                    for i in entries:
                        assert i>0 and f.n_bars.iloc[i-1]==60 and x.signal_complete.iloc[i-1]
                        assert not bars.no_entry_mask[i]
                        assert f.time.iloc[i]>=pd.Timestamp(protocol['calibration']['end'],tz='UTC')
                        assert f.time.iloc[i]-f.time.iloc[i-1]==pd.Timedelta(hours=1)
                    group=trades[(trades.strategy_id==spec['id'])&(trades.instrument==instrument)&(trades.window==window)]
                    cell=metrics[(metrics.strategy_id==spec['id'])&(metrics.instrument==instrument)&(metrics.window==window)].set_index('cost_bps')
                    assert len(group)==len(entries)==cell.loc[2,'n_trades']
                    assert cell.n_trades.nunique()==1 and cell.position_hash.nunique()==1
                    assert cell.loc[0,'total_return_pct']>=cell.loc[2,'total_return_pct']-1e-8>=cell.loc[5,'total_return_pct']-2e-8
                    equity=np.ones(len(f));base=1.;last=0;factors={c:[] for c in (0,2,5)}
                    for ordinal,(_,tr) in enumerate(group.iterrows()):
                        entry=int(tr.entry_index);exit_=int(tr.exit_index);d=int(tr.direction)
                        assert entry==entries[ordinal] and d==p[entry]
                        forced=ordinal==len(group)-1 and p[-1]!=0
                        assert not forced or exit_==len(f)-1
                        entry_price=float(f.open.iloc[entry]);exit_price=float(f.close.iloc[-1] if forced else f.open.iloc[exit_])
                        assert np.isclose(entry_price,tr.entry_price) and np.isclose(exit_price,tr.exit_price)
                        assert int(tr.bars_held)==exit_-entry<=spec['hold_hours']
                        for cost in (0,2,5):
                            fee=cost/10000
                            factor=(exit_price*(1-fee)/(entry_price*(1+fee))) if d==1 else (entry_price*(1-fee)/(exit_price*(1+fee)))
                            factors[cost].append(factor)
                        equity[last:entry]=base
                        held_end=exit_+1 if forced else exit_
                        close_prices=f.close.to_numpy()[entry:held_end]
                        marked=close_prices*(1-.0002)/(entry_price*(1+.0002)) if d==1 else entry_price*(1-.0002)/(close_prices*(1+.0002))
                        equity[entry:held_end]=base*marked
                        factor=factors[2][-1]
                        assert np.isclose(tr.net_pnl,(factor-1)*entry_price,rtol=1e-9,atol=1e-9)
                        base*=factor;last=exit_
                        actual_exit=f.time.iloc[exit_]+(pd.Timedelta(hours=1) if forced else pd.Timedelta(0))
                        corrected.append({'strategy_id':spec['id'],'round':number,'instrument':instrument,'window':window,'direction':d,
                          'entry_fill_time':str(f.time.iloc[entry]),'exit_bar_open_time':str(f.time.iloc[exit_]),
                          'exit_fill_time':str(actual_exit),'exit_fill_kind':'forced_final_close' if forced else 'next_open',
                          'entry_price':entry_price,'exit_price':exit_price,'net_pnl_c2':tr.net_pnl,
                          'observed_bars_held':int(tr.bars_held),'elapsed_hours':(actual_exit-f.time.iloc[entry]).total_seconds()/3600})
                        fill_checks+=1
                    equity[last:]=base
                    for cost in (0,2,5):
                        compound=float(np.prod(factors[cost])) if factors[cost] else 1.
                        assert abs((compound-1)*100-cell.loc[cost,'total_return_pct'])<=.0050001
                    benchmark=(f.close.iloc[-1]/f.open.iloc[0]-1)*100
                    assert abs(benchmark-cell.loc[2,'buyhold_return_pct'])<=.0050001
                    dd=np.max((np.maximum.accumulate(equity)-equity)/np.maximum.accumulate(equity))*100
                    assert abs(dd-cell.loc[2,'max_drawdown_pct'])<=.0050001
                    assert abs(np.mean(p!=0)*100-cell.loc[2,'exposure_pct'])<=.0050001
                    assert abs(np.mean(p)*100-cell.loc[2,'mean_net_position_pct'])<=.0050001
                    if window in ('validation_1','validation_2'):
                        weeks=pd.Series(equity,index=pd.DatetimeIndex(f.time)).resample('W').last().ffill().dropna()
                        calculated=np.log(weeks.to_numpy()[1:]/weeks.to_numpy()[:-1])*10000
                        stored=weekly[(weekly.strategy_id==spec['id'])&(weekly.instrument==instrument)&(weekly.window==window)]
                        np.testing.assert_allclose(stored.strategy_log_bps,calculated,rtol=1e-7,atol=1e-7)
                    if window=='full':
                        stored=np.load(out/f'{spec["id"]}_{instrument}_positions.npy',allow_pickle=False)
                        np.testing.assert_array_equal(stored,p)
                        if instrument=='EUR_USD':
                            cutoff=14000
                            prefix=build_positions(f.iloc[:cutoff],x.iloc[:cutoff],spec,fit,protocol['calibration']['end'])
                            np.testing.assert_array_equal(prefix,p[:cutoff]);prefix_checks+=1
                    accounting_groups+=1
        if replay:
            other=replay/f'round{number}';m2=yaml.safe_load((other/'manifest.yml').read_text())
            assert m2['status']=='completed' and m2['registry_sha256']==m['registry_sha256']
            for name,digest in m['artifacts'].items():assert sha(other/name)==digest,(number,'replay',name)
            changed=[name for name,value in m['source_sha256'].items() if m2['source_sha256'][name]!=value]
            assert set(changed)<=({'strategy/research_rules.py'} if number==1 else set())
            replays.append({'round':number,'artifact_files':len(m['artifacts']),'status':'byte-identical','source_context_differences':changed})
    assert len({s['id'] for s in all_specs})==len({s['semantic_hash'] for s in all_specs})==200
    first=pd.read_csv(root/'round1/metrics.csv');training=first[first.window=='development_train']
    children=adapt_registry(all_specs[:100],training,protocol,sha(root/'round1/analysis.csv'))
    assert children==all_specs[100:]
    # Poison validation results; the explicit training input is unchanged.
    poisoned=first.copy();poisoned.loc[poisoned.window!='development_train','total_return_pct']=1e9
    assert adapt_registry(all_specs[:100],poisoned[poisoned.window=='development_train'],protocol,sha(root/'round1/analysis.csv'))==children
    feature=root/'entry_feature_research';fm=yaml.safe_load((feature/'manifest.yml').read_text())
    assert fm['status']=='completed' and fm['primary_tests']==1200
    for name,digest in fm['artifacts'].items():assert sha(feature/name)==digest
    for name,digest in fm['source_sha256'].items():assert sha(feature/'source_snapshot'/name)==digest
    feature_tests=pd.read_csv(feature/'entry_feature_tests.csv');portfolio_tests=pd.read_csv(feature/'portfolio_tests_joint_q.csv')
    prior=pd.read_csv(feature/'prior_feature_tests_joint_q.csv')
    p=np.r_[prior.p_value,portfolio_tests.p_value,feature_tests.p_value]
    q=independent_q(p)
    assert len(p)==6810 and len(feature_tests)==len(portfolio_tests)==1200
    np.testing.assert_allclose(prior.q_both_layers,q[:4410],atol=1e-12)
    np.testing.assert_allclose(portfolio_tests.q_both_layers,q[4410:5610],atol=1e-12)
    np.testing.assert_allclose(feature_tests.q_both_layers,q[5610:],atol=1e-12)
    assert not portfolio_tests.duplicated(['strategy_id','instrument','window']).any()
    assert not feature_tests.duplicated(['strategy_id','instrument','window']).any()
    assert (portfolio_tests.loc[~portfolio_tests.supported,'p_value']==1).all()
    assert (feature_tests.loc[~feature_tests.supported,'p_value']==1).all()
    events_verified=0
    for item in fm['event_files']:
        assert sha(Path(item['file']))==item['sha256']
        instrument=item['instrument'];events=pd.read_parquet(item['file'])
        frame=pd.read_parquet(cache/f'{instrument}_bars.parquet');x=pd.read_parquet(cache/f'{instrument}_features.parquet')
        cuts=yaml.safe_load((cache/f'{instrument}_cuts.yml').read_text())
        assert (events.available_at==pd.DatetimeIndex(frame.time).as_unit('ns')+pd.Timedelta(hours=1)).all()
        for spec in all_specs:
            fit=cuts[spec['parent'] or spec['id']]
            expected=decision_events(frame,x,spec,fit)
            np.testing.assert_array_equal(events[spec['id']],expected);events_verified+=1
        if event_replay:
            other=yaml.safe_load((event_replay/'manifest.yml').read_text())
            repeat=next(r for r in other['event_files'] if r['instrument']==instrument)
            assert repeat['sha256']==item['sha256']
    if event_replay:
        for name,digest in fm['artifacts'].items():assert sha(event_replay/name)==digest,('feature replay',name)
    decisions=pd.read_csv(root/'round2/decisions.csv')
    assert len(decisions)==200 and not decisions.oos_eligible.any()
    # Final broader family cannot turn a failed full/recent return bar into a finalist.
    assert not decisions.passed_development_criteria.any()
    assert sha(ROOT/'strategy/oos_ledger.json')==ledger
    return {'status':'passed','portfolio_rules':200,'matrix_cells':9000,'independent_accounting_groups':accounting_groups,
      'independent_trade_fill_checks':fill_checks,'native_prefix_rule_checks':prefix_checks,'entry_feature_paths_verified':events_verified,
      'feature_tests':1200,'portfolio_tests':1200,'joint_test_family':6810,'round2_training_only_adaptation':'verified',
      'portfolio_replays':replays,'entry_feature_replay':'byte-identical' if event_replay else 'not requested',
      'entry_feature_replay_result_files':len(fm['artifacts']) if event_replay else 0,
      'ledger_sha256':ledger,'verification_source_sha256':sha(Path(__file__))},corrected


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=Path('research/strategies/SR-20261031-200'))
    parser.add_argument('--cache',type=Path,default=Path('data/strategy_research/SR-20261031-200'))
    parser.add_argument('--replay-root',type=Path);parser.add_argument('--event-replay',type=Path);parser.add_argument('--out',type=Path,required=True)
    a=parser.parse_args()
    if a.out.exists():raise ValueError('refusing existing audit record')
    result,ledger=verify(a.root,a.cache,a.replay_root,a.event_replay)
    path=a.out.parent/'execution_ledger_with_fill_times.csv'
    if path.exists():raise ValueError('refusing existing audited execution ledger')
    pd.DataFrame(ledger).to_csv(path,index=False,lineterminator='\n')
    a.out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
