"""Registered analysis -> 100 portfolio rules -> analysis -> 100 children -> analysis."""
from __future__ import annotations

import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
import pandas as pd
import yaml

from scripts.research_indicators import write_csv
from strategy.research_rules import round1_registry,adapt_registry
from strategy.research_cohort import load_prepared,evaluate_round,analyze_round,sha
from strategy.research_statistics import infer_round,combine_tests,decisions

ROOT=Path(__file__).resolve().parents[1]
SOURCES=('config/strategy_research_200.yml','strategy/research_rules.py','strategy/research_cohort.py',
         'strategy/research_statistics.py','strategy/engine.py','strategy/metrics.py','strategy/strategy_lib.py',
         'strategy/oos_token.py','strategy/catalogue_research.py','strategy/feature_research.py','scripts/research_strategies_200.py',
         'scripts/research_indicators.py','pipeline/catalogue_features.py','pipeline/catalogue_extended.py',
         'pipeline/indicators.py','library/catalogue.py','library/market_structure.py','config/strategies.yml','requirements.lock')


def event(root,kind,**fields):
    with (root/'events.jsonl').open('a') as f:f.write(json.dumps({'time_utc':datetime.now(timezone.utc).isoformat(),'event':kind,**fields})+'\n')


def source_snapshot(out):
    hashes={name:sha(ROOT/name) for name in SOURCES}
    for name in SOURCES:
        target=out/'source_snapshot'/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes((ROOT/name).read_bytes())
    return hashes


def verify_grid(rows,specs,protocol):
    f=pd.DataFrame(rows);expected=len(specs)*len(protocol['instruments'])*len(protocol['windows'])*len(protocol['cost_bps_one_way'])
    if len(f)!=expected or f.duplicated(['strategy_id','instrument','window','cost_bps']).any():raise ValueError('incomplete/duplicate portfolio matrix')
    for name in ('total_return_pct','buyhold_return_pct','n_trades','max_drawdown_pct','sharpe_weekly'):
        if not np.isfinite(f[name]).all():raise ValueError(f'nonfinite portfolio metric: {name}')


def run(root,cache,round_number):
    protocol=yaml.safe_load((ROOT/'config/strategy_research_200.yml').read_text())
    root.mkdir(parents=True,exist_ok=True)
    out=root/f'round{round_number}'
    if out.exists():raise ValueError('refusing to overwrite a research round')
    features=yaml.safe_load((ROOT/protocol['feature_registry']).read_text())
    if round_number==1:
        registry=round1_registry(features,protocol)
        initial=root/'round1_registry.yml'
        if initial.exists() and yaml.safe_load(initial.read_text())!=registry:raise ValueError('registered round 1 changed')
        initial.write_text(yaml.safe_dump(registry,sort_keys=False))
        (root/'protocol.yml').write_text((ROOT/'config/strategy_research_200.yml').read_text())
        event(root,'round1_registered',strategies=100,prior_strategy_configurations=protocol['prior_strategy_configurations'])
        if not cache.exists():load_prepared(protocol,cache,registry)
    else:
        parent=root/'round1';m=yaml.safe_load((parent/'manifest.yml').read_text())
        if m['status']!='completed':raise ValueError('round 1 must finish before round 2 design')
        parents=yaml.safe_load((root/'round1_registry.yml').read_text())
        f=pd.read_csv(parent/'metrics.csv');training=f[f.window=='development_train']
        analysis_hash=sha(parent/'analysis.csv')
        registry=adapt_registry(parents,training,protocol,analysis_hash)
        (root/'round2_registry.yml').write_text(yaml.safe_dump(registry,sort_keys=False))
        event(root,'round2_registered_after_round1_analysis',strategies=100,parent_analysis_sha256=analysis_hash,
              adaptation_windows=['development_train'],episode_counts=pd.Series([s['episode'] for s in registry]).value_counts().to_dict())
    cache_manifest=yaml.safe_load((cache/'manifest.yml').read_text())
    for filename,digest in cache_manifest['files'].items():
        if sha(cache/filename)!=digest:raise ValueError('prepared input changed')
    out.mkdir()
    hashes=source_snapshot(out);ledger=sha(ROOT/'strategy/oos_ledger.json')
    prior=pd.read_csv(ROOT/protocol['prior_tests'])
    manifest={'research_id':protocol['research_id'],'round':round_number,'status':'started','strategies':100,
              'source_sha256':hashes,'registry_sha256':sha(root/f'round{round_number}_registry.yml'),
              'prepared_manifest_sha256':sha(cache/'manifest.yml'),'prior_tests_sha256':sha(ROOT/protocol['prior_tests']),
              'ledger_sha256':ledger,'started_at_utc':datetime.now(timezone.utc).isoformat(),
              'registration':'locally fixed, exploratory; all periods previously researched; not external preregistration'}
    (out/'registry.yml').write_text(yaml.safe_dump(registry,sort_keys=False))
    (out/'manifest.yml').write_text(yaml.safe_dump(manifest))
    event(root,f'round{round_number}_started')
    try:
        rows,trades,weeks,paths=evaluate_round(registry,protocol,cache,out,round_number)
        verify_grid(rows,registry,protocol)
        write_csv(out/'metrics.csv',rows)
        if trades:write_csv(out/'trades_c2.csv',trades)
        write_csv(out/'weekly_c2.csv',weeks);write_csv(out/'position_paths.csv',paths)
        analysis=analyze_round(rows,registry);write_csv(out/'analysis.csv',analysis)
        event(root,f'round{round_number}_portfolio_analysis_complete',matrix_cells=len(rows),
              legacy_bar_met=sum(x['legacy_in_sample_bar'] for x in analysis),empty_assets=sum(x['empty_full_assets'] for x in analysis))
        tests=infer_round(weeks,rows,protocol,[r['id'] for r in registry])
        prior_strategy_tests=[]
        if round_number==2:prior_strategy_tests=pd.read_csv(root/'round1/primary_tests.csv').to_dict('records')
        combined,inherited,pending=combine_tests(prior,prior_strategy_tests+tests,protocol)
        write_csv(out/'primary_tests.csv',combined[combined.strategy_id.isin([s['id'] for s in registry])].to_dict('records'))
        write_csv(out/'cumulative_strategy_tests.csv',combined.to_dict('records'))
        inherited.to_csv(out/'prior_feature_tests_with_current_q.csv',index=False,lineterminator='\n')
        all_metrics=rows if round_number==1 else pd.read_csv(root/'round1/metrics.csv').to_dict('records')+rows
        verdicts=decisions(all_metrics,combined,protocol);write_csv(out/'decisions.csv',verdicts)
        for filename,digest in hashes.items():
            if sha(ROOT/filename)!=digest:raise ValueError(f'source changed during round: {filename}')
        if sha(ROOT/'strategy/oos_ledger.json')!=ledger:raise ValueError('OOS ledger changed')
        manifest.update(status='completed',matrix_cells=len(rows),primary_tests=len(tests),pending_strategy_tests=pending,
                        finished_at_utc=datetime.now(timezone.utc).isoformat(),
                        artifacts={p.name:sha(p) for p in sorted(out.iterdir()) if p.is_file() and p.name!='manifest.yml'})
        (out/'manifest.yml').write_text(yaml.safe_dump(manifest,sort_keys=True))
        event(root,f'round{round_number}_completed',passed=sum(v['passed_development_criteria'] for v in verdicts),
              strategy_configurations_tried=protocol['prior_strategy_configurations']+round_number*100)
    except BaseException as error:
        manifest.update(status='failed',error=repr(error));(out/'manifest.yml').write_text(yaml.safe_dump(manifest))
        event(root,f'round{round_number}_failed',error=repr(error));raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--round',required=True,type=int,choices=[1,2]);parser.add_argument('--out',type=Path,default=Path('research/strategies/SR-20261031-200'))
    parser.add_argument('--cache',type=Path,default=Path('data/strategy_research/SR-20261031-200'))
    args=parser.parse_args();run(args.out,args.cache,args.round)
