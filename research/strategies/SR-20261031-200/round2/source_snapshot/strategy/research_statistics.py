"""Accumulated, positive-outperformance inference for both 100-strategy rounds."""
from __future__ import annotations

import numpy as np
import pandas as pd

from strategy.catalogue_research import CatalogueBootstrap
from strategy.feature_research import by_adjust,MONDAY_NS,WEEK_NS


def infer_round(weekly,metrics,protocol,identities):
    weekly=pd.DataFrame(weekly);metrics=pd.DataFrame(metrics);rows=[]
    settings=protocol['statistics']
    for instrument in protocol['instruments']:
        for window in ('validation_1','validation_2'):
            bounds=protocol['windows'][window]
            blocks=CatalogueBootstrap(bounds['start'],bounds['end'],settings,f'strategy200:{instrument}:{window}')
            eligible=[];sums=[];counts=[];meta=[]
            for sid in identities:
                observations=weekly[(weekly.strategy_id==sid)&(weekly.instrument==instrument)&(weekly.window==window)]
                cell=metrics[(metrics.strategy_id==sid)&(metrics.instrument==instrument)&(metrics.window==window)&(metrics.cost_bps==2)]
                if len(cell)!=1:raise ValueError('missing or duplicate primary portfolio cell')
                active=int((observations.strategy_log_bps.abs()>1e-12).sum())
                y=observations.excess_log_bps.to_numpy(float)
                effect=float(np.mean(y)) if len(y) else np.nan
                support=bool(cell.n_trades.iloc[0]>=settings['minimum_validation_trades'] and active>=settings['minimum_active_weeks'] and len(y)>=8 and np.isfinite(y).all())
                record={'strategy_id':sid,'instrument':instrument,'window':window,'n_trades':int(cell.n_trades.iloc[0]),
                        'active_weeks':active,'weekly_observations':len(y),'supported':support,'effect_weekly_log_bps':effect,
                        'ci_low_bps':np.nan,'ci_high_bps':np.nan,'p_value':1.}
                meta.append(record)
                if support:
                    time=pd.DatetimeIndex(observations.week_end).as_unit('ns').asi8
                    week=((time-MONDAY_NS)//WEEK_NS-blocks.start_week).astype(int)
                    if (week<0).any() or (week>=blocks.weeks).any():raise ValueError('weekly inference outside calendar blocks')
                    eligible.append(len(meta)-1)
                    sums.append(np.bincount(week,weights=y,minlength=blocks.weeks))
                    counts.append(np.bincount(week,minlength=blocks.weeks))
            # Process at most twenty strategies at once; retain paired blocks
            # while bounding output/scratch memory for a million resamples.
            for start in range(0,len(eligible),20):
                end=min(start+20,len(eligible))
                numerator=blocks.weights@np.array(sums[start:end]).T
                denominator=blocks.weights@np.array(counts[start:end]).T
                sampled=np.divide(numerator,denominator,out=np.full_like(numerator,np.nan),where=denominator>0)
                for j,index in enumerate(eligible[start:end]):
                    record=meta[index];valid=sampled[:,j];valid=valid[np.isfinite(valid)]
                    if len(valid)<.9*settings['bootstrap_replicates']:
                        record['supported']=False;continue
                    record['ci_low_bps'],record['ci_high_bps']=np.quantile(valid,[.025,.975]).tolist()
                    effect=record['effect_weekly_log_bps']
                    record['p_value']=float((1+np.sum(valid-effect>=effect))/(len(valid)+1))
            rows.extend(meta)
            print(f'Primary inference {instrument}/{window}: {len(eligible)}/100 strategies have support',flush=True)
    return rows


def combine_tests(prior,completed,protocol):
    completed=pd.DataFrame(completed)
    keys=['strategy_id','instrument','window']
    if completed.duplicated(keys).any():raise ValueError('duplicate strategy primary hypothesis')
    if len(prior)!=protocol['prior_test_count']:raise ValueError('prior feature test family drift')
    pending=protocol['statistics']['planned_strategy_tests']-len(completed)
    if pending<0:raise ValueError('expanded strategy trial budget')
    p=np.r_[prior.p_value,completed.p_value,np.ones(pending)]
    if len(p)!=protocol['statistics']['planned_total_tests']:raise ValueError('wrong accumulated family')
    q=by_adjust(p);completed['q_global']=q[len(prior):len(prior)+len(completed)]
    inherited=prior.copy();inherited['q_strategy_family']=q[:len(prior)]
    return completed,inherited,pending


def decisions(all_metrics,all_tests,protocol):
    metrics=pd.DataFrame(all_metrics);tests=pd.DataFrame(all_tests);rows=[]
    for sid in sorted(metrics.strategy_id.unique()):
        m=metrics[(metrics.strategy_id==sid)&(metrics.cost_bps==2)]
        full=m[m.window=='full'];recent=m[m.window=='last_12m']
        full_wins=int((full.total_return_pct>full.buyhold_return_pct).sum())
        recent_wins=int((recent.total_return_pct>recent.buyhold_return_pct).sum())
        passing=[]
        for inst in protocol['instruments']:
            t=tests[(tests.strategy_id==sid)&(tests.instrument==inst)]
            if set(t.window)!= {'validation_1','validation_2'}:raise ValueError('incomplete strategy test evidence')
            if t.supported.all() and (t.ci_low_bps>0).all() and (t.q_global<=protocol['statistics']['q_limit']).all():passing.append(inst)
        under_ceiling=bool(full.n_trades.max()<=protocol['promotion']['maximum_full_history_trades'])
        legacy=bool(full_wins>=2 and recent_wins>=2 and under_ceiling)
        passed=bool(legacy and len(passing)>=protocol['promotion']['minimum_assets'])
        reason='development criteria met; manual S-series review still required' if passed else \
            'frequency ceiling' if not under_ceiling else 'insufficient cross-asset/time benchmark replication'
        rows.append({'strategy_id':sid,'status':'research_review_only' if passed else 'rejected',
            'full_benchmark_wins':full_wins,'recent_benchmark_wins':recent_wins,'full_max_trades':int(full.n_trades.max()),
            'replicated_assets':len(passing),'replicated_asset_names':','.join(passing),'legacy_in_sample_bar':legacy,
            'passed_development_criteria':passed,'reason':reason,'oos_eligible':False})
    return rows
