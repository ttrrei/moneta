"""Research 200 new composite entry features and join their trial accounting."""
from __future__ import annotations

import argparse
from datetime import datetime,timezone
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
import pandas as pd
import yaml

from scripts.research_indicators import write_csv
from strategy.research_cohort import sha
from strategy.feature_research import by_adjust
from strategy.entry_feature_research import analyze_entry_features

ROOT=Path(__file__).resolve().parents[1]


def run(root,cache,out):
    if out.exists():raise ValueError('refusing existing entry-feature attempt')
    config=ROOT/'config/strategy_event_research_200.yml';protocol=yaml.safe_load(config.read_text())
    portfolio=yaml.safe_load((root/'protocol.yml').read_text())
    specs=[]
    for number in (1,2):
        manifest=yaml.safe_load((root/f'round{number}/manifest.yml').read_text())
        if manifest['status']!='completed':raise ValueError('both portfolio rounds must complete first')
        specs.extend(yaml.safe_load((root/f'round{number}_registry.yml').read_text()))
    if len(specs)!=200:raise ValueError('expected 200 registered composite rules')
    out.mkdir(parents=True)
    sources=('config/strategy_event_research_200.yml','strategy/entry_feature_research.py',
             'strategy/research_rules.py','strategy/catalogue_research.py','strategy/feature_research.py','scripts/research_entry_features_200.py')
    hashes={name:sha(ROOT/name) for name in sources}
    for name in sources:
        target=out/'source_snapshot'/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes((ROOT/name).read_bytes())
    (out/'protocol.yml').write_text(config.read_text())
    registry=[{'entry_feature_id':'EF-'+s['id'],'strategy_id':s['id'],'source_idea':s['idea_id'],'round':s['round'],
               'entry_model':s['entry_model'],'episode':s['episode'],'available_at':'native hour close',
               'output':'-1 short intent / 0 withhold / +1 long intent','source_score':s['score'],
               'source_direction':s['source_direction'],'source_role':s['target_role'],'research_status':'registered_before_entry_label_analysis'} for s in specs]
    (out/'registry.yml').write_text(yaml.safe_dump(registry,sort_keys=False))
    (out/'manifest.yml').write_text(yaml.safe_dump({'status':'started','started_at_utc':datetime.now(timezone.utc).isoformat(),'source_sha256':hashes,
         'registration':'User requested both layers after portfolio research began; fixed before this event study; adaptive reused development data, not external preregistration.'}))
    rows=[];cells=[];coverage=[];fits=[];event_files=[]
    cache_manifest=yaml.safe_load((cache/'manifest.yml').read_text())
    for instrument in portfolio['instruments']:
        for name in (f'{instrument}_bars.parquet',f'{instrument}_features.parquet',f'{instrument}_cuts.yml'):
            if sha(cache/name)!=cache_manifest['files'][name]:raise ValueError('prepared source changed')
        frame=pd.read_parquet(cache/f'{instrument}_bars.parquet');features=pd.read_parquet(cache/f'{instrument}_features.parquet')
        cuts=yaml.safe_load((cache/f'{instrument}_cuts.yml').read_text())
        result=analyze_entry_features(frame,features,specs,cuts,portfolio,protocol,instrument)
        for destination,items in zip((rows,cells,coverage,fits),result[:4]):
            destination.extend(({'instrument':instrument,**item} if destination is fits else item) for item in items)
        path=cache/f'{instrument}_entry_features_200.parquet';result[4].to_parquet(path,index=False)
        event_files.append({'instrument':instrument,'file':str(path),'sha256':sha(path)})
    if len(rows)!=1200:raise ValueError('incomplete entry-feature primary grid')
    prior=pd.read_csv(ROOT/portfolio['prior_tests'])
    strategies=pd.read_csv(root/'round2/cumulative_strategy_tests.csv')
    q=by_adjust(np.r_[prior.p_value,strategies.p_value,[r['p_value'] for r in rows]])
    if len(q)!=protocol['statistics']['planned_total_tests']:raise ValueError('incorrect joint research family')
    strategies['q_both_layers']=q[len(prior):len(prior)+len(strategies)]
    for row,value in zip(rows,q[len(prior)+len(strategies):]):row['q_both_layers']=float(value)
    write_csv(out/'entry_feature_tests.csv',rows);write_csv(out/'matched_cells.csv',cells);write_csv(out/'coverage.csv',coverage)
    write_csv(out/'portfolio_tests_joint_q.csv',strategies.to_dict('records'))
    prior['q_both_layers']=q[:len(prior)];prior.to_csv(out/'prior_feature_tests_joint_q.csv',index=False,lineterminator='\n')
    (out/'training_fits.yml').write_text(yaml.safe_dump(fits,sort_keys=True))
    decisions=[]
    f=pd.DataFrame(rows)
    for spec in specs:
        subset=f[f.strategy_id==spec['id']];passing=0;supported=0
        for instrument in portfolio['instruments']:
            s=subset[subset.instrument==instrument]
            adequate=len(s)==2 and s.supported.all();supported+=adequate
            passing+=bool(adequate and (s.ci_low_bps>0).all() and (s.q_both_layers<=.1).all())
        decisions.append({'strategy_id':spec['id'],'entry_feature_id':'EF-'+spec['id'],'round':spec['round'],
             'supported_assets':int(supported),'replicated_assets':int(passing),
             'decision':'keep_for_further_research' if passing>=2 else 'reject' if supported>=2 else 'revise',
             'portfolio_profitability_implied':False})
    write_csv(out/'entry_feature_decisions.csv',decisions)
    for name,value in hashes.items():
        if sha(ROOT/name)!=value:raise ValueError('feature research source changed')
    (out/'manifest.yml').write_text(yaml.safe_dump({'status':'completed','source_sha256':hashes,'primary_tests':1200,
         'joint_family_tests':6810,'event_files':event_files,'finished_at_utc':datetime.now(timezone.utc).isoformat(),
         'registration':'Feature analysis follows portfolio scope; exploratory/adaptive reused development history.',
         'artifacts':{p.name:sha(p) for p in sorted(out.iterdir()) if p.is_file() and p.name!='manifest.yml'}}))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=Path('research/strategies/SR-20261031-200'))
    parser.add_argument('--cache',type=Path,default=Path('data/strategy_research/SR-20261031-200'))
    parser.add_argument('--out',type=Path,default=Path('research/strategies/SR-20261031-200/entry_feature_research'))
    a=parser.parse_args();run(a.root,a.cache,a.out)
