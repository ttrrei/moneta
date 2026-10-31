"""Data preparation, shared-engine evaluation and analysis for the 200-rule cohort."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from pipeline.catalogue_extended import compute_catalogue_features,fit_calibration
from strategy.engine import BarFrame,run_backtest
from strategy.metrics import _weekly_equity
from strategy.oos_token import assert_access,holdout_start_date
from strategy.research_rules import PositionRule,build_positions,fit_cuts

ROOT=Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_prepared(protocol,cache,records):
    """Prepare new early-calibrated features; never reuse end-2022 fitted cuts."""
    if cache.exists():raise ValueError('refusing existing prepared-data directory')
    end=pd.Timestamp(protocol['windows']['full']['end'],tz='UTC')
    assert_access((end-pd.Timedelta(microseconds=1)).isoformat())
    holdout=pd.Timestamp(holdout_start_date(),tz='UTC')
    if pd.Timestamp(protocol['windows']['full']['end'],tz='UTC')>holdout:raise ValueError('unsafe experiment boundary')
    source=ROOT/protocol['source_batch'];manifest=yaml.safe_load((source/'manifest.yml').read_text())
    if manifest['status']!='completed':raise ValueError('source catalogue attempt incomplete')
    cache.mkdir(parents=True)
    prepared=[]
    def read(item):
        path=ROOT/item['file'] if not Path(item['file']).is_absolute() else Path(item['file'])
        if sha(path)!=item['sha256']:raise ValueError('source cache drift')
        f=pd.read_parquet(path);times=pd.DatetimeIndex(f.time)
        if f.empty or not times.is_monotonic_increasing or times.has_duplicates or (times>=holdout).any():
            raise ValueError('invalid/protected input cache')
        if not np.isfinite(f[['open','close']].to_numpy()).all() or (f[['open','close']].to_numpy()<=0).any():raise ValueError('invalid prices')
        return f
    calibration_start=pd.Timestamp(protocol['calibration']['start'],tz='UTC')
    calibration_end=pd.Timestamp(protocol['calibration']['end'],tz='UTC')
    for instrument in protocol['instruments']:
        items=[x for x in manifest['inputs'] if x['instrument']==instrument]
        five=read(next(x for x in items if x['role']=='source5m'))
        hourly=read(next(x for x in items if x['role']=='source1h'))
        peer_name={'EUR_USD':'GBP_USD','BTC_USD':'ETH_USD','XAU_USD':'XAG_USD'}[instrument]
        peer=read(next(x for x in manifest['inputs'] if x['instrument']==peer_name and x['role']=='peer5m'))
        decision=pd.DatetimeIndex(five.time).tz_convert('UTC').as_unit('ns')+pd.Timedelta(minutes=5)
        training=(decision>=calibration_start)&(decision<calibration_end)
        calibration=fit_calibration(five,training)
        features=compute_catalogue_features(five,hourly,calibration=calibration,peer=peer)
        features['signal_complete']=(five.n_bars.to_numpy()==5)
        features['feature_close']=decision
        hour_close=pd.DatetimeIndex(hourly.time).tz_convert('UTC').as_unit('ns')+pd.Timedelta(hours=1)
        match=pd.DataFrame({'feature_close':hour_close}).merge(features,on='feature_close',how='left',sort=False,validate='one_to_one')
        for col in ('signal_complete','source_complete'):
            match[col]=match[col].fillna(False).astype(bool)
        if ((match.feature_close!=hour_close)).any():raise ValueError('hourly feature projection changed order')
        training_hour=(hour_close>=calibration_start)&(hour_close<calibration_end)&(hourly.n_bars.to_numpy()==60)&match.signal_complete.to_numpy()
        cuts=fit_cuts(match,training_hour,records)
        price_path=cache/f'{instrument}_bars.parquet';feature_path=cache/f'{instrument}_features.parquet'
        hourly.to_parquet(price_path,index=False);match.to_parquet(feature_path,index=False)
        (cache/f'{instrument}_cuts.yml').write_text(yaml.safe_dump(cuts))
        (cache/f'{instrument}_calibration.yml').write_text(yaml.safe_dump({'train_start':str(calibration_start),'train_end':str(calibration_end),**calibration}))
        prepared.append({'instrument':instrument,'bars':str(price_path),'features':str(feature_path),
                         'bars_sha256':sha(price_path),'features_sha256':sha(feature_path),'rows':len(hourly),
                         'source_5m_rows':len(five),'native_timeframe':'1h','source_feature_timeframe':'5m',
                         'first':str(hourly.time.iloc[0]),'last':str(hourly.time.iloc[-1])})
        print(f'Prepared {instrument}: {len(hourly)} native hours from {len(five)} source feature rows',flush=True)
    (cache/'manifest.yml').write_text(yaml.safe_dump({'source_manifest_sha256':sha(source/'manifest.yml'),
       'calibration':protocol['calibration'],'inputs':prepared,'files':{p.name:sha(p) for p in sorted(cache.iterdir()) if p.is_file()}}))
    return prepared


def positions_for_window(frame,features,spec,fit,activation,bounds):
    time=pd.DatetimeIndex(frame.time)
    start,end=(pd.Timestamp(bounds[key],tz='UTC') for key in ('start','end'))
    mask=(time>=start)&(time<end)
    f=frame.loc[mask].reset_index(drop=True);x=features.loc[mask].reset_index(drop=True)
    if len(f)<2:raise ValueError('empty/short evaluation window')
    positions=build_positions(f,x,spec,fit,activation)
    no_entry=(f.is_gap_bar.to_numpy()!=0)|(f.is_near_market_close.to_numpy()!=0)
    bars=BarFrame(open=f.open.to_numpy(float),close=f.close.to_numpy(float),time=f.time.to_numpy(),bar_seconds=3600,no_entry_mask=no_entry)
    return f,x,positions,bars


def weekly_trace(equity,bars):
    time=pd.DatetimeIndex(pd.to_datetime(bars.time,utc=True))
    strategy=pd.Series(equity,index=time).resample('W').last().ffill().dropna()
    benchmark=pd.Series(bars.close/bars.open[0],index=time).resample('W').last().ffill().dropna()
    # Exact weekly-close convention used by the shared engine's weekly Sharpe.
    np.testing.assert_array_equal(strategy.to_numpy(),_weekly_equity(equity,bars.time))
    if not strategy.index.equals(benchmark.index):raise ValueError('weekly benchmark misalignment')
    strategy_log=np.log(strategy.to_numpy()[1:]/strategy.to_numpy()[:-1])
    bh_log=np.log(benchmark.to_numpy()[1:]/benchmark.to_numpy()[:-1])
    return pd.DataFrame({'week_end':strategy.index[1:],'strategy_log_bps':strategy_log*10000,
                          'buyhold_log_bps':bh_log*10000,'excess_log_bps':(strategy_log-bh_log)*10000})


def evaluate_round(records,protocol,cache,out,round_number):
    rows=[];trades=[];weeks=[];paths=[]
    for instrument in protocol['instruments']:
        frame=pd.read_parquet(cache/f'{instrument}_bars.parquet');features=pd.read_parquet(cache/f'{instrument}_features.parquet')
        cuts=yaml.safe_load((cache/f'{instrument}_cuts.yml').read_text())
        behavior={}
        for number,spec in enumerate(records,1):
            # Children inherit only covariate calibration, never a fitted return target.
            fit=cuts[spec['parent'] or spec['id']]
            for window,bounds in protocol['windows'].items():
                f,x,positions,bars=positions_for_window(frame,features,spec,fit,protocol['calibration']['end'],bounds)
                if window=='full':
                    digest=hashlib.sha256(positions.tobytes()).hexdigest()
                    behavior.setdefault(digest,[]).append(spec['id'])
                    path=out/f'{spec["id"]}_{instrument}_positions.npy'
                    # Position paths are small native-hour traces and contain no market prices.
                    np.save(path,positions,allow_pickle=False);paths.append({'strategy_id':spec['id'],'instrument':instrument,'sha256':sha(path),'file':path.name})
                for cost in protocol['cost_bps_one_way']:
                    capture=cost==2
                    result=run_backtest(bars,PositionRule(positions),cost_bps=cost,capture_equity=capture)
                    identity={'strategy_id':spec['id'],'idea_id':spec['idea_id'],'round':round_number,'instrument':instrument,'window':window,'cost_bps':cost}
                    rows.append(identity|{'start':str(f.time.iloc[0]),'end':str(f.time.iloc[-1]),'timeframe':'1h',
                                          'entry_guard':True,'position_hash':hashlib.sha256(positions.tobytes()).hexdigest()}|result.to_dict())
                    if cost==2:
                        for trade in result.trades:
                            trades.append(identity|{'direction':trade.direction,'entry_time':str(f.time.iloc[trade.entry_time]),
                             'exit_time':str(f.time.iloc[trade.exit_time]),'entry_index':trade.entry_time,'exit_index':trade.exit_time,
                             'entry_price':trade.entry_price,'exit_price':trade.exit_price,'net_pnl':trade.net_pnl,'bars_held':trade.bars_held})
                        if window in ('validation_1','validation_2'):
                            trace=weekly_trace(result.equity_curve,bars)
                            weeks.extend(identity|r for r in trace.to_dict('records'))
            if number%20==0:print(f'Round {round_number} {instrument}: {number}/100 strategies evaluated',flush=True)
        (out/f'{instrument}_behavioral_duplicates.yml').write_text(yaml.safe_dump([ids for ids in behavior.values() if len(ids)>1]))
    return rows,trades,weeks,paths


def analyze_round(rows,records):
    f=pd.DataFrame(rows);summaries=[]
    for spec in records:
        s=f[f.strategy_id==spec['id']];c2=s[s.cost_bps==2]
        full=c2[c2.window=='full'];recent=c2[c2.window=='last_12m']
        win=lambda a:int((a.total_return_pct>a.buyhold_return_pct).sum())
        gross=s[(s.cost_bps==0)&(s.window=='development_train')]
        net=c2[c2.window=='development_train']
        summaries.append({'strategy_id':spec['id'],'idea_id':spec['idea_id'],'round':spec['round'],'entry_model':spec['entry_model'],
           'episode':spec['episode'],'full_benchmark_wins':win(full),'recent_benchmark_wins':win(recent),
           'full_max_trades':int(full.n_trades.max()),'full_mean_return_c2_pct':float(full.total_return_pct.mean()),
           'full_mean_weekly_sharpe_c2':float(full.sharpe_weekly.mean()),'full_worst_drawdown_c2_pct':float(full.max_drawdown_pct.max()),
           'training_mean_gross_trade_pct':float(gross.avg_trade_return_pct.mean()),
           'training_mean_cost_drag_pct':float((gross.total_return_pct.to_numpy()-net.total_return_pct.to_numpy()).mean()),
           'empty_full_assets':int((full.n_trades==0).sum()),'legacy_in_sample_bar':bool(win(full)>=2 and win(recent)>=2 and full.n_trades.max()<=300),
           'status':'rejected' if full.n_trades.max()>300 or win(full)==0 or win(recent)==0 else 'research_review_only',
           'oos_eligible':False})
    return summaries
