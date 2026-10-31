"""Run one registered experimental SR1/SR2 strategy through the shared engine."""
from pathlib import Path
import argparse
import json
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
import pandas as pd
import yaml

from strategy.engine import run_backtest
from strategy.research_rules import PositionRule
from strategy.research_cohort import positions_for_window,sha
from strategy.oos_token import assert_access


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--strategy',required=True)
    parser.add_argument('--instrument',default='EUR_USD',choices=['EUR_USD','BTC_USD','XAU_USD'])
    parser.add_argument('--timeframe',default='1h',choices=['1h'])
    parser.add_argument('--window',default='validation_2',choices=['full','last_12m','development_train','validation_1','validation_2'])
    parser.add_argument('--cost-bps',type=float,default=2)
    parser.add_argument('--json',action='store_true')
    args=parser.parse_args()
    assert_access('2025-07-31')
    root=Path(__file__).resolve().parents[2]
    protocol=yaml.safe_load((root/'config/strategy_research_200.yml').read_text())
    specs=[]
    for number in (1,2):
        path=root/f'research/strategies/SR-20261031-200/round{number}_registry.yml'
        if path.exists():specs.extend(yaml.safe_load(path.read_text()))
    matches=[s for s in specs if s['id']==args.strategy]
    if len(matches)!=1:raise SystemExit('Unknown or unregistered research strategy')
    spec=matches[0];cache=root/'data/strategy_research/SR-20261031-200'
    manifest=yaml.safe_load((cache/'manifest.yml').read_text())
    for name in (f'{args.instrument}_bars.parquet',f'{args.instrument}_features.parquet',f'{args.instrument}_cuts.yml'):
        if sha(cache/name)!=manifest['files'][name]:raise SystemExit('Prepared input hash mismatch')
    frame=pd.read_parquet(cache/f'{args.instrument}_bars.parquet')
    features=pd.read_parquet(cache/f'{args.instrument}_features.parquet')
    fit=yaml.safe_load((cache/f'{args.instrument}_cuts.yml').read_text())[spec['parent'] or spec['id']]
    _,_,positions,bars=positions_for_window(frame,features,spec,fit,protocol['calibration']['end'],protocol['windows'][args.window])
    result=run_backtest(bars,PositionRule(positions),cost_bps=args.cost_bps)
    print(json.dumps({'strategy_id':args.strategy,'instrument':args.instrument,'window':args.window,
                      'timeframe':'1h','cost_bps':args.cost_bps,'research_only':True,**result.to_dict()},indent=2))


if __name__=='__main__':main()
