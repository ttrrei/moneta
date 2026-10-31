"""Execute one fixed catalogue batch on development data; preserve every attempt."""
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
import pandas as pd
import yaml

from scripts.research_indicators import sha, write_csv
from strategy.catalogue_research import analyze_catalogue
from strategy.feature_research import by_adjust
from strategy.oos_token import holdout_start_date, assert_access
from strategy.strategy_lib import load_bars, TIMEFRAME_PARQUET

ROOT = Path(__file__).resolve().parents[1]


def frame_digest(frame):
    h = hashlib.sha256(str(list(zip(frame.columns, frame.dtypes.astype(str)))).encode())
    h.update(pd.util.hash_pandas_object(frame, index=False).to_numpy().tobytes())
    return h.hexdigest()


def cumulative_results(current, cfg, prior, plan):
    old = [pd.read_csv(ROOT / path / 'comparisons.csv') for path in cfg['previous_batches']]
    completed = pd.concat(old + [pd.DataFrame(current)], ignore_index=True)
    key = ['idea_id','instrument','timeframe','split','horizon']
    if completed.duplicated(key).any():
        raise ValueError('duplicate catalogue trial identity')
    pending = plan['planned_catalogue_tests'] - len(completed)
    if pending < 0: raise ValueError('expanded catalogue trial family')
    p = np.r_[prior.p_value, completed.p_value, np.ones(pending)]
    if len(p) != plan['planned_total_tests']: raise ValueError('trial family drift')
    q = by_adjust(p)
    completed['q_global'] = q[len(prior):len(prior)+len(completed)]
    rows = []
    for i, row in prior.iterrows():
        rows.append({'study':'P1','idea_id':row.feature,'instrument':row.instrument,'timeframe':row.timeframe,
                     'split':row.split,'horizon':int(row.horizon),'target':'P1_original_return_contrast',
                     'status':'completed','p_value':row.p_value,'q_global':q[i]})
    for _, row in completed.iterrows():
        rows.append({name:row[name] for name in ('idea_id','instrument','timeframe','split','horizon','target')}
                    | {'study':'catalogue','status':'completed','p_value':row.p_value,'q_global':row.q_global})
    completed_ids = set(completed.idea_id)
    for ids in plan['batch_ideas'].values():
        for idea in ids:
            if idea in completed_ids: continue
            for instrument in cfg['instruments']:
                for split in cfg['splits']:
                    for horizon in cfg['horizons']:
                        rows.append({'study':'catalogue','idea_id':idea,'instrument':instrument,'timeframe':'5m',
                                     'split':split,'horizon':horizon,'target':'planned_in_batch_protocol',
                                     'status':'pending','p_value':1.,'q_global':1.})
    if len(rows) != len(p): raise ValueError('missing pending trial identities')
    return completed, rows


def decisions(completed, cfg):
    rows=[]
    for batch in range(1,cfg['batch']+1):
        definitions=yaml.safe_load((ROOT/f'config/indicator_catalogue_batch{batch}.yml').read_text())
        for idea,spec in definitions['ideas'].items():
            selected=completed[completed.idea_id==idea]
            supported=replicated=0
            for horizon in cfg['horizons']:
                covered=passed=0
                for instrument in cfg['instruments']:
                    subset=selected[(selected.instrument==instrument)&(selected.horizon==horizon)].set_index('split')
                    if set(subset.index)!=set(cfg['splits']):raise ValueError('incomplete idea evidence')
                    if not subset.supported.all():continue
                    covered+=1
                    orientation=1 if spec['expected']=='positive' or subset.loc['train','effect_bps']>=0 else -1
                    validation=subset.loc[['validation_1','validation_2']]
                    lower=validation.ci_low_bps if orientation==1 else -validation.ci_high_bps
                    passed+=bool((lower>0).all() and (validation.q_global<=cfg['statistics']['q_limit']).all())
                supported+=covered>=2;replicated+=passed>=2
            decision='keep_context' if replicated and spec['target']!='directed_return' else 'keep_research' if replicated else 'reject' if supported else 'revise'
            rows.append({'idea_id':idea,'batch':batch,'target':spec['target'],'decision':decision,
                         'supported_horizons':supported,'replicated_horizons':replicated,
                         'strategy_promotion':False,'status':'final' if cfg['batch']==5 else 'interim'})
    return rows


def run(config, out, data_out):
    cfg=yaml.safe_load(config.read_text());plan=yaml.safe_load((ROOT/'config/indicator_catalogue_plan.yml').read_text())
    if set(cfg['ideas'])!=set(plan['batch_ideas'][cfg['batch']]):raise ValueError('batch identity drift')
    holdout=pd.Timestamp(holdout_start_date(),tz='UTC')
    last=None
    for split in cfg['splits'].values():
        start,end=(pd.Timestamp(split[k],tz='UTC') for k in ('start','end'))
        if start>=end or end>holdout or (last is not None and start<last):raise ValueError('unsafe split')
        last=end
    prior_path=ROOT/cfg['statistics']['prior_comparisons'];prior=pd.read_csv(prior_path)
    if len(prior)!=cfg['statistics']['prior_expected_tests']:raise ValueError('prior trial family changed')
    m=plan['planned_total_tests']; minimum=m*np.sum(1/np.arange(1,m+1))/(cfg['statistics']['bootstrap_replicates']+1)
    if minimum>cfg['statistics']['q_limit']:raise ValueError('insufficient Monte Carlo resolution')
    if out.exists() or data_out.exists():raise ValueError('refusing existing attempt directory')
    module=importlib.import_module(cfg['feature_module'])
    sources=['scripts/research_catalogue.py','scripts/research_indicators.py','strategy/catalogue_research.py',
             'strategy/feature_research.py','strategy/strategy_lib.py','strategy/oos_token.py','config/strategies.yml',
             'library/catalogue.py','pipeline/catalogue_features.py','requirements.lock','config/indicator_catalogue_plan.yml']
    sources += [f'config/indicator_catalogue_batch{k}.yml' for k in range(1,6)]
    if cfg['feature_module'].endswith('catalogue_extended'):
        sources+=['pipeline/catalogue_extended.py','library/market_structure.py','pipeline/indicators.py']
    out.mkdir(parents=True);data_out.mkdir(parents=True)
    hashes={name:sha(ROOT/name) for name in sources}
    for name in sources:
        target=out/'source_snapshot'/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes((ROOT/name).read_bytes())
    prior_files=[prior_path]+[ROOT/path/'comparisons.csv' for path in cfg['previous_batches']]
    prior_hashes={str(p.relative_to(ROOT)):sha(p) for p in prior_files}
    for p in prior_files:
        target=out/'prior_snapshot'/p.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(p.read_bytes())
    ledger=sha(ROOT/'strategy/oos_ledger.json')
    manifest={'research_id':cfg['research_id'],'batch':cfg['batch'],'status':'started','planned_comparisons':450,
              'planned_family':m,'protocol_sha256':sha(config),'source_sha256':hashes,'prior_sha256':prior_hashes,
              'ledger_sha256':ledger,'started_at_utc':datetime.now(timezone.utc).isoformat(),
              'registration':'local fixed catalogue and batch protocol; development history previously researched; not external preregistration',
              'source_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
              'python':platform.python_version(),'numpy':np.__version__,'pandas':pd.__version__}
    (out/'protocol.yml').write_text(config.read_text());(out/'manifest.yml').write_text(yaml.safe_dump(manifest))
    comparisons=[];groups=[];cells=[];coverage=[];fits=[];inputs=[];derived=[];calibrations=[]
    until=(holdout-pd.Timedelta(microseconds=1)).isoformat();assert_access(until)
    try:
        def load(instrument,tf,columns,role):
            parquet=ROOT/TIMEFRAME_PARQUET[tf];stat=parquet.stat()
            f=load_bars(str(parquet),instrument,columns,since=cfg['splits']['train']['start'],until=until)
            if f.empty or (pd.DatetimeIndex(f.time)>=holdout).any():raise ValueError('empty/protected rows')
            path=data_out/f'{instrument}_{role}.parquet';f.to_parquet(path,index=False)
            inputs.append({'instrument':instrument,'timeframe':tf,'role':role,'rows':len(f),'start':str(f.time.iloc[0]),'end':str(f.time.iloc[-1]),
                           'frame_sha256':frame_digest(f),'file':str(path),'sha256':sha(path),'gold_size':stat.st_size,'gold_mtime_ns':stat.st_mtime_ns})
            return f
        for instrument in cfg['instruments']:
            frame=load(instrument,'5m',module.INPUT_COLUMNS,'source5m')
            hourly=load(instrument,'1h',module.HTF_COLUMNS,'source1h')
            kwargs=dict(cfg['parameters'])
            if cfg.get('calibration'):
                close=pd.DatetimeIndex(frame.time)+pd.Timedelta(minutes=5)
                train=(close>=pd.Timestamp(cfg['splits']['train']['start'],tz='UTC'))&(close<pd.Timestamp(cfg['splits']['train']['end'],tz='UTC'))
                calibration=module.fit_calibration(frame,train)
                kwargs['calibration']=calibration;calibrations.append({'instrument':instrument,**calibration})
            if instrument in cfg.get('peer_instruments',{}):
                peer=load(cfg['peer_instruments'][instrument],'5m',('instrument','high','low','n_bars'),'peer5m')
                kwargs['peer']=peer
            features=module.compute_catalogue_features(frame,hourly,**kwargs)
            path=data_out/f'{instrument}_features.parquet';features.to_parquet(path,index=False)
            derived.append({'instrument':instrument,'file':str(path),'sha256':sha(path),'rows':len(features)})
            result=analyze_catalogue(frame,features,cfg,instrument)
            for destination,items in zip((comparisons,groups,cells,coverage,fits),result):destination.extend(items)
            print(f"Batch {cfg['batch']} {instrument}: {len(frame)} source rows, {len(comparisons)}/450 comparisons",flush=True)
        if len(comparisons)!=450:raise ValueError('incomplete planned batch')
        completed,cumulative=cumulative_results(comparisons,cfg,prior,plan)
        current=completed[completed.idea_id.isin(cfg['ideas'])].to_dict('records')
        for name,rows in [('comparisons.csv',current),('conditional_returns.csv',groups),('matched_cells.csv',cells),
                          ('coverage.csv',coverage),('cumulative_tests.csv',cumulative),('catalogue_decisions.csv',decisions(completed,cfg))]:
            write_csv(out/name,rows)
        (out/'training_fits.yml').write_text(yaml.safe_dump(fits,sort_keys=True))
        (out/'calibrations.yml').write_text(yaml.safe_dump(calibrations,sort_keys=True))
        for name,h in hashes.items():
            if sha(ROOT/name)!=h:raise ValueError(f'source changed during run: {name}')
        for name,h in prior_hashes.items():
            if sha(ROOT/name)!=h:raise ValueError('prior evidence changed')
        if sha(ROOT/'strategy/oos_ledger.json')!=ledger:raise ValueError('ledger changed')
        manifest.update(status='completed',completed_comparisons=len(comparisons),inputs=inputs,derived=derived,
                        finished_at_utc=datetime.now(timezone.utc).isoformat(),
                        artifacts={p.name:sha(p) for p in sorted(out.iterdir()) if p.is_file() and p.name!='manifest.yml'})
        (out/'manifest.yml').write_text(yaml.safe_dump(manifest,sort_keys=True))
    except BaseException as error:
        manifest.update(status='failed',error=repr(error),completed_comparisons=len(comparisons))
        (out/'manifest.yml').write_text(yaml.safe_dump(manifest,sort_keys=True));raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',required=True,type=Path);parser.add_argument('--out',required=True,type=Path)
    parser.add_argument('--data-out',required=True,type=Path);args=parser.parse_args()
    run(args.config,args.out,args.data_out)
