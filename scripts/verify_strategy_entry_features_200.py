"""Independently reconstruct all entry-feature samples and matched means.

Deliberately does not call the study's label, sampling, fitting or inference
functions. Bootstrap reproducibility and global q-values are audited by the
companion portfolio audit; this verifies their underlying point estimates.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import yaml


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def same(left, right):
    np.testing.assert_allclose(left, right, rtol=1e-10, atol=1e-8, equal_nan=True)


def audit(root, cache):
    feature = root / 'entry_feature_research'
    cfg = yaml.safe_load((feature / 'protocol.yml').read_text())
    portfolio = yaml.safe_load((root / 'protocol.yml').read_text())
    manifest = yaml.safe_load((feature / 'manifest.yml').read_text())
    fits = yaml.safe_load((feature / 'training_fits.yml').read_text())
    tests = pd.read_csv(feature / 'entry_feature_tests.csv')
    cells = pd.read_csv(feature / 'matched_cells.csv')
    decisions = pd.read_csv(feature / 'entry_feature_decisions.csv')
    specs = [s for n in (1, 2) for s in yaml.safe_load((root / f'round{n}_registry.yml').read_text())]
    h = cfg['holding_horizon_native_hours']
    matching = cfg['matching']
    week = 7 * 86400 * 10**9
    monday = pd.Timestamp('1970-01-05', tz='UTC').value
    checked_fits = checked_tests = checked_cells = eligible_labels = 0
    for instrument in portfolio['instruments']:
        bars = pd.read_parquet(cache / f'{instrument}_bars.parquet')
        features = pd.read_parquet(cache / f'{instrument}_features.parquet')
        event_file = next(x for x in manifest['event_files'] if x['instrument'] == instrument)
        assert digest(event_file['file']) == event_file['sha256']
        events = pd.read_parquet(event_file['file'])
        times = pd.DatetimeIndex(bars.time).as_unit('ns').asi8
        close = times + 3600 * 10**9
        ready = ((bars.n_bars.to_numpy() == 60) & features.signal_complete.to_numpy(bool)
                 & (bars.is_gap_bar.to_numpy() == 0))
        training = (ready & (close >= pd.Timestamp(matching['train_start'], tz='UTC').value)
                    & (close < pd.Timestamp(matching['train_end'], tz='UTC').value))
        vol = bars.atr_24.to_numpy(float) / bars.close.to_numpy(float)
        edges = np.unique(np.quantile(vol[training & np.isfinite(vol)], matching['volatility_quantiles']))
        bins = np.searchsorted(edges, vol, side='right')
        n = len(bars)
        returns = np.full(n, np.nan)
        exits = np.full(n, np.nan)
        # Explicit close(t) -> open(t+1) -> open(t+1+h) prices.
        opening = bars.open.to_numpy(float)
        high, low = bars.high.to_numpy(float), bars.low.to_numpy(float)
        for j in range(258, n - h - 1):
            if (bars.n_bars.iat[j] != 60 or bars.is_gap_bar.iat[j] != 0
                    or times[j+1] - times[j] != 3600 * 10**9):
                continue
            entry, exit_ = j + 1, j + h + 1
            if (not np.isfinite(opening[[entry, exit_]]).all()
                    or np.any(opening[[entry, exit_]] <= 0)
                    or not np.isfinite(high[entry:exit_]).all()
                    or not np.isfinite(low[entry:exit_]).all()):
                continue
            returns[j] = (opening[exit_] / opening[entry] - 1) * 10000
            exits[j] = times[exit_]
        eligible_labels += int(np.isfinite(returns).sum())
        for spec in specs:
            sid = spec['id']
            event = events[sid].to_numpy(int)
            fit = next(x for x in fits if x['instrument'] == instrument and x['strategy_id'] == sid)
            strata = 2 * bins + (event == 1)
            candidate = training & np.isin(event, [-1, 1])
            retained, counts = [], []
            for s in sorted(set(strata[candidate])):
                count = int(np.sum(candidate & (strata == s)))
                controls = int(np.sum(training & (bins == s // 2)))
                if min(count, controls) >= matching['minimum_training_event_samples_per_stratum']:
                    retained.append(int(s))
                    counts.append(count)
            weights = np.asarray(counts) / max(1, sum(counts))
            mass = sum(counts) / max(1, int(candidate.sum()))
            assert fit['strata'] == retained
            same(fit['control_edges'], edges)
            same(fit['weights'], weights)
            same(fit['training_common_support_mass'], mass)
            assert fit['identified'] == bool(retained and mass >= matching['minimum_common_support_mass'])
            checked_fits += 1
            for window in ('validation_1', 'validation_2'):
                bounds = portfolio['windows'][window]
                start, end = (pd.Timestamp(bounds[k], tz='UTC').value for k in ('start', 'end'))
                mask = ready & (close >= start) & (close < end)
                eligible = mask & np.isfinite(returns) & (exits < end)
                candidates = np.flatnonzero(eligible & np.isin(event, [-1, 1]) & np.isin(strata, retained))
                selected = []
                for index in candidates:
                    if not selected or index - selected[-1] >= h:
                        selected.append(index)
                treated = np.asarray(selected, dtype=int)
                first = np.flatnonzero(mask)
                anchor = int(first[0]) if len(first) else 0
                control = np.flatnonzero(eligible & ((np.arange(n) - anchor) % h == 0))
                arms = [[], treated]
                directions = [[], event[treated]]
                stratum_arms = [[], strata[treated]]
                for d in (-1, 1):
                    s = 2 * bins[control] + int(d == 1)
                    ix = control[np.isin(s, retained)]
                    arms[0].extend(ix.tolist())
                    directions[0].extend([d] * len(ix))
                    stratum_arms[0].extend((2 * bins[ix] + int(d == 1)).tolist())
                row = tests[(tests.strategy_id == sid) & (tests.instrument == instrument) & (tests.window == window)]
                assert len(row) == 1
                row = row.iloc[0]
                observed = []
                cell_rows = cells[(cells.strategy_id == sid) & (cells.instrument == instrument) & (cells.window == window)]
                assert len(cell_rows) == 2 * len(retained)
                for arm in (0, 1):
                    ix = np.asarray(arms[arm], dtype=int)
                    d = np.asarray(directions[arm], dtype=int)
                    s = np.asarray(stratum_arms[arm], dtype=int)
                    assert len(ix) == row['n_control' if arm == 0 else 'n_treated']
                    active_weeks = len(set((close[ix] - monday) // week))
                    assert active_weeks == row['weeks_control' if arm == 0 else 'weeks_treated']
                    means = []
                    for stratum in retained:
                        keep = s == stratum
                        mean = float(np.mean(d[keep] * returns[ix[keep]])) if keep.any() else np.nan
                        means.append(mean)
                        cell = cell_rows[(cell_rows.stratum == stratum) & (cell_rows.arm == arm)]
                        assert len(cell) == 1 and cell.iloc[0]['n'] == keep.sum()
                        same(mean, cell.iloc[0].target_mean_bps)
                        checked_cells += 1
                    observed.append(float(np.dot(weights, means)) if len(weights) else np.nan)
                same(row.matched_control_bps, observed[0])
                same(row.matched_event_bps, observed[1])
                same(row.effect_bps, observed[1] - observed[0])
                mean = float(np.mean(event[treated] * returns[treated])) if len(treated) else np.nan
                raw = float(np.mean(returns[treated])) if len(treated) else np.nan
                same(row.event_mean_cash_bps, mean)
                for cost in (0, 2, 5):
                    same(row[f'event_net_cash_c{cost}_bps'], mean - cost * raw / 10000 - 2 * cost)
                assert row.event_count_unthinned == np.sum(mask & np.isin(event, [-1, 1]))
                checked_tests += 1
    for spec in specs:
        subset = tests[tests.strategy_id == spec['id']]
        supported = passing = 0
        for _, rows in subset.groupby('instrument'):
            adequate = len(rows) == 2 and rows.supported.all()
            supported += adequate
            passing += bool(adequate and (rows.ci_low_bps > 0).all() and (rows.q_both_layers <= .1).all())
        actual = decisions[decisions.strategy_id == spec['id']].iloc[0]
        assert actual.supported_assets == supported and actual.replicated_assets == passing
        assert actual.decision == ('keep_for_further_research' if passing >= 2 else 'reject' if supported >= 2 else 'revise')
    return {'status': 'passed', 'independent_training_fits': checked_fits,
            'independent_next_open_labels': eligible_labels, 'independent_primary_point_estimates': checked_tests,
            'independent_matched_cells': checked_cells, 'independent_feature_decisions': len(specs),
            'verification_source_sha256': digest(__file__)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path('research/strategies/SR-20261031-200'))
    parser.add_argument('--cache', type=Path, default=Path('data/strategy_research/SR-20261031-200'))
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        raise ValueError('refusing to overwrite audit evidence')
    result = audit(args.root, args.cache)
    args.out.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))
