"""Produce per-rule research cards and progress from frozen study outputs."""
from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
STUDY = ROOT / 'research/strategies/SR-20261031-200'
CARDS = ROOT / 'strategy/docs/strategy_research_200_reports'


def number(value, precision=2):
    return f'{value:.{precision}f}' if np.isfinite(value) else 'unavailable'


def build():
    CARDS.mkdir(exist_ok=True)
    specs = [s for n in (1, 2) for s in yaml.safe_load((STUDY / f'round{n}/registry.yml').read_text())]
    metrics = pd.concat([pd.read_csv(STUDY / f'round{n}/metrics.csv') for n in (1, 2)])
    analysis = pd.concat([pd.read_csv(STUDY / f'round{n}/analysis.csv') for n in (1, 2)]).set_index('strategy_id')
    decisions = pd.read_csv(STUDY / 'round2/decisions.csv').set_index('strategy_id')
    event = STUDY / 'entry_feature_research'
    feature_decisions = pd.read_csv(event / 'entry_feature_decisions.csv').set_index('strategy_id')
    feature_tests = pd.read_csv(event / 'entry_feature_tests.csv')
    portfolio_tests = pd.read_csv(event / 'portfolio_tests_joint_q.csv')
    fits = {a: yaml.safe_load((ROOT / f'data/strategy_research/SR-20261031-200/{a}_cuts.yml').read_text())
            for a in ('EUR_USD', 'BTC_USD', 'XAU_USD')}
    progress = []
    index = ['# All 200 executable strategy and entry-feature records', '',
             'Date: 2026-10-31. See the [combined report](strategy_research_200_20261031_results.md).', '',
             'Each card records the source hypothesis, operational rules, cost sensitivity,',
             'all six portfolio and six entry-feature primary contrasts, and both decisions.',
             'Returns below are arithmetic diagnostic means across assets, not portfolio returns.', '',
             '| Rule / card | Source | Style | Episode | Full mean return c2 | Maximum full trades | Portfolio decision | Entry-feature decision |',
             '|---|---|---|---|---:|---:|---|---|']
    for ordinal, spec in enumerate(specs):
        sid = spec['id']
        a, d, fd = analysis.loc[sid], decisions.loc[sid], feature_decisions.loc[sid]
        ptests = portfolio_tests[portfolio_tests.strategy_id == sid]
        ftests = feature_tests[feature_tests.strategy_id == sid]
        own = metrics[metrics.strategy_id == sid]
        path = CARDS / f'{sid}.md'
        record = {**spec, **a.to_dict(), 'strategy_id': sid,
                  'portfolio_status': d.status, 'portfolio_reason': d.reason,
                  'feature_status': fd.decision, 'feature_supported_assets': int(fd.supported_assets),
                  'feature_replicated_assets': int(fd.replicated_assets),
                  'portfolio_supported_tests': int(ptests.supported.sum()),
                  'feature_supported_tests': int(ftests.supported.sum()),
                  'minimum_portfolio_joint_q': float(ptests.q_both_layers.min()),
                  'minimum_feature_joint_q': float(ftests.q_both_layers.min()),
                  'n_strategies_tried_before': 132 + ordinal,
                  'n_configurations_tried_before': 827 + ordinal,
                  'report': str(path.relative_to(ROOT)), 'oos_eligible': False}
        progress.append(record)
        index.append(f'| [{sid}](strategy_research_200_reports/{sid}.md) | {spec["idea_id"]} | {spec["style"]} | {spec["episode"]} | {a.full_mean_return_c2_pct:+.3f}% | {int(a.full_max_trades)} | {d.status} | {fd.decision} |')
        lines = [f'# {sid}: {spec["name"]}', '', 'Date: 2026-10-31. Development research only.', '',
                 f'**Portfolio: {d.status}. Entry feature: {fd.decision}. OOS eligible: no.**', '',
                 f'N strategies tried before this one: {132 + ordinal}.',
                 f'Configuration tally before this one: {827 + ordinal}.',
                 'These numbers use registry order; each batch was registered together before its outcomes.', '',
                 '## Hypothesis and relationship', '', spec['hypothesis'], '',
                 f'Source: {spec["idea_id"]}; style: `{spec["style"]}`; score: `{spec["score"]}`;',
                 f'original target: `{spec["target_role"]}`; transform: `{spec["transform"]}`;',
                 f'event kind: `{spec["comparison_kind"]}`; tail: `{spec["tail"]}`.', '',
                 spec['difference'], '',
                 f'Parent: {spec["parent"] or "original fifty-idea feature"}. Semantic hash: `{spec["semantic_hash"]}`.', '',
                 'This is a related composite entry hypothesis, not a newly independent primitive indicator.', '',
                 '## Executable contract', '',
                 'Read the exact completed 5m feature snapshot at a completed native 1h close.',
                 'Hourly context must be complete and less than one hour old. Early covariate',
                 'calibration ends 2020-07-01; no position opens earlier. Gaps and known',
                 'near-close clocks block entries. Future fill-bar completeness is not consulted.', '']
        if spec['target_role'] == 'directed_return':
            lines += [f'Initial setup direction is `{spec["source_direction"]} * {spec["direction_multiplier"]}`.']
        elif spec['entry_model'] == 'trend_alignment':
            lines += ['Initial setup direction is the higher-timeframe trend, also confirmed by the six-observation return direction.']
        else:
            lines += ['Initial setup direction is opposite the sign of median stretch; magnitude/risk does not itself choose a side.']
        if spec['entry_model'] == 'trend_alignment':
            lines += ['Require agreement with higher-timeframe direction.']
        else:
            regime = 'at least' if spec['style'] in ('trend', 'compression') else 'at most'
            lines += [f'Require completed candle body in the chosen direction and hourly efficiency {regime} its early-calibration median.']
        episodes = {
            'immediate': 'Enter on a fresh qualifying setup, including a fresh direction change.',
            'persistent_context': 'Enter on a fresh setup only after six consecutive qualifying context observations.',
            'failure_reversal': 'Arm on the parent fresh full setup. Within six observed hours, enter the opposite side after a move of at least 0.5 trigger ATR against it and an opposing completed body.',
            'pullback_confirmation': 'Arm on the parent fresh full setup. Within six observed hours, enter its original side after a later close within 0.5 trigger ATR of the reference and a confirming body/context.',
            'delayed_confirmation': 'Arm on a fresh primary event, then require matching context and direction within six observed hours.'}
        lines += ['Categorical sources use exact 1 for the high tail or 0 for the low tail;',
                  'continuous sources use the early upper/lower tail cut below. CB-01 also',
                  'requires positive squeeze age. The score transform is applied first.',
                  episodes[spec['episode']], '',
                  f'One unit long or short; no pyramiding or direct flips. Freeze ATR24 at entry.',
                  f'Close-confirmed stop {spec["stop_atr"]} ATR; profit {spec["take_profit_atr"]} ATR;',
                  f'maximum {spec["hold_hours"]} observed hourly bars; cooldown {spec["cooldown_hours"]} observations.',
                  'Fill decisions at the following native open. Force-close the final open position',
                  'at the final candle close. Observed bars may span weekend/session gaps.', '',
                  'Shared-engine shorts use reciprocal equity factors; the separate feature',
                  'study uses cash returns per entry notional. No financing/slippage model is included.', '',
                  '| Asset | Early lower tail | Early upper tail | Early ER median | Score calibration rows |',
                  '|---|---:|---:|---:|---:|']
        for asset in fits:
            fit = fits[asset][spec['parent'] or sid]
            lines.append(f'| {asset} | {number(fit["low"], 6)} | {number(fit["high"], 6)} | {number(fit["htf_er_median"], 6)} | {fit["calibration_rows"]} |')
        if spec['round'] == 2:
            lines += ['', 'The fixed adaptation policy consumed only parent development-training outcomes:',
                      f'{spec["parent_training_trades"]} training trades, mean gross trade return',
                      f'{spec["parent_training_mean_gross_trade_pct"]:+.6f}%, and mean cost drag',
                      f'{spec["parent_training_cost_drag_pct"]:.4f} percentage points.',
                      f'Parent analysis SHA256: `{spec["parent_analysis_sha256"]}`.',
                      'Validation outcomes did not select the episode. Reused development history remains exploratory.']
        lines += ['', '## Portfolio cost sensitivity', '',
                  'Costs are basis points per leg. Full includes the initial cash/calibration period.',
                  'Full/recent overlap; they are not independent confirmations.', '',
                  '| Asset | Window | Trades | Return c0 | Return c2 | Return c5 | Buy/hold | Max DD c2 | Exposure c2 |',
                  '|---|---|---:|---:|---:|---:|---:|---:|---:|']
        for asset in fits:
            for window in ('full', 'last_12m'):
                rows = own[(own.instrument == asset) & (own.window == window)].set_index('cost_bps')
                net = rows.loc[2]
                lines.append(f'| {asset} | {window} | {int(net.n_trades)} | {rows.loc[0,"total_return_pct"]:+.2f}% | {net.total_return_pct:+.2f}% | {rows.loc[5,"total_return_pct"]:+.2f}% | {net.buyhold_return_pct:+.2f}% | {net.max_drawdown_pct:.2f}% | {net.exposure_pct:.2f}% |')
        lines += ['', '## All primary contrasts', '',
                  'Portfolio target is weekly log return excess over cost-free buy/hold at c2.',
                  'Feature target is direction-signed next-open cash return over 24 observed hours,',
                  'relative to training-weighted direction/volatility controls. Feature episodes',
                  'are independent of holdings, cooldowns and portfolio entry blocking; labels',
                  'require an adjacent next open. Their returns are not strategy P&L.',
                  'Both use paired four-week blocks, 999,999 draws and the final joint 6,810-test BY family.', '',
                  '| Layer | Asset | Validation slice | Supported | Effect (bps) | 95% CI (bps) | Positive one-sided p | Joint q |',
                  '|---|---|---|---|---:|---|---:|---:|']
        for layer, tests, effect in (('portfolio', ptests, 'effect_weekly_log_bps'), ('entry feature', ftests, 'effect_bps')):
            for _, row in tests.iterrows():
                lines.append(f'| {layer} | {row.instrument} | {row.window} | {bool(row.supported)} | {number(row[effect], 4)} | [{number(row.ci_low_bps, 4)}, {number(row.ci_high_bps, 4)}] | {row.p_value:.6f} | {row.q_both_layers:.6f} |')
        lines += ['', '## Decision and review', '',
                  f'Portfolio rejected: {d.reason}. Full benchmark wins: {int(d.full_benchmark_wins)}/3;',
                  f'recent wins: {int(d.recent_benchmark_wins)}/3; full maximum trades: {int(d.full_max_trades)};',
                  f'empty full asset combinations: {int(a.empty_full_assets)}.', '',
                  f'Entry-feature status `{fd.decision}`: {int(fd.supported_assets)} assets supported in both',
                  f'validation slices, {int(fd.replicated_assets)} replicated. `revise` means incomplete',
                  'sample/matching support, not established uselessness. No new feature survives',
                  'the joint correction. Positive descriptive returns do not override those results.', '',
                  'Review pass 1 checked causality/calibration; pass 2 checked execution, costs,',
                  'sample support and accounting; pass 3 replayed both rounds and both research',
                  'layers and independently rebuilt entry-feature samples/means.', '',
                  f'Run: `.venv/bin/python -m strategy.code.strategy_research --strategy {sid} --instrument EUR_USD --timeframe 1h --window validation_2 --cost-bps 2 --json`.', '',
                  'All five windows and all three cost tiers are retained in the machine-readable',
                  f'[`round{spec["round"]}/metrics.csv`](../../../research/strategies/SR-20261031-200/round{spec["round"]}/metrics.csv).',
                  'See the [combined report](../strategy_research_200_20261031_results.md) for study-wide limitations.', '']
        path.write_text('\n'.join(lines))
    pd.DataFrame(progress).to_csv(STUDY / 'strategy_progress.csv', index=False, lineterminator='\n')
    (ROOT / 'strategy/docs/strategy_research_200_20261031_index.md').write_text('\n'.join(index) + '\n')
    registry = ['## Experimental cohort: all 200 completed rules', '',
                'This separate namespace records the user-authorized bulk research cohort.',
                'The mature S-series checker remains scoped to its 132 definitions; the',
                '[cohort audit](../research/strategies/SR-20261031-200/validation_audit.json)',
                'checks every experimental definition and result. Related configurations',
                'and behavioral duplicates remain counted. No rule is a finalist.', '',
                '| Research ID | Name / parent | Style | Key score | Entry model / episode | Status | Code | Report | Last run |',
                '|---|---|---|---|---|---|---|---|---|']
    trials = ['## Experimental cohort trial log: 2026-10-31', '',
              'All 200 outcomes are retained below. Native 1h execution; five development',
              'windows and three costs per rule. None used OOS. Counts follow registration',
              'order within each simultaneously registered batch, including all rejections.',
              'The S-series parser covers the earlier table; this cohort has its own complete audit.', '',
              '| Research ID | Date | Hypothesis: source / model / episode | Windows | Outcome | Full benchmark wins c2 | Max full trades | n_tried_before | Configurations before | Report |',
              '|---|---|---|---|---|---:|---:|---:|---:|---|']
    for row in progress:
        sid = row['strategy_id']
        registry.append(f'| {sid} | {row["name"]}; parent {row["parent"] or row["idea_id"]} | {row["style"]} | `{row["score"]}` | {row["entry_model"]} / {row["episode"]} | rejected | [shared runner](code/strategy_research.py) | [report](docs/strategy_research_200_reports/{sid}.md) | 2026-10-31 |')
        trials.append(f'| {sid} | 2026-10-31 | {row["idea_id"]} / {row["entry_model"]} / {row["episode"]} | full, recent, training, validation 1/2 | rejected | {row["full_benchmark_wins"]}/3 | {row["full_max_trades"]} | {row["n_strategies_tried_before"]} | {row["n_configurations_tried_before"]} | [report](docs/strategy_research_200_reports/{sid}.md) |')
    for name, block in (('STRATEGY_REGISTRY.md', registry), ('trial_log.md', trials)):
        path = ROOT / 'strategy' / name
        marker = '<!-- BEGIN SR-20261031-200 GENERATED RECORDS -->'
        body = path.read_text().split(marker)[0].rstrip()
        path.write_text(body + '\n\n' + marker + '\n\n' + '\n'.join(block) + '\n')
    print(f'Wrote {len(specs)} strategy cards and the joint progress index.')


if __name__ == '__main__':
    build()
