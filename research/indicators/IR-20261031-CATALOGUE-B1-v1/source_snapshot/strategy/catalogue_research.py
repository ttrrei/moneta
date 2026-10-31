"""Fixed, covariate-stratified comparisons for catalogue batch 1.

Uses the existing label timing, bootstrap and cost conventions. Training
fits involve covariates only. All primary targets and controls are declared
in the protocol; unsupported comparisons remain explicit in the trial grid.
"""
from __future__ import annotations

import hashlib
import numpy as np
import pandas as pd

from strategy.feature_research import (WeekBootstrap, forward_labels, interval,
                                      contrast_pvalue, non_overlapping, MONDAY_NS, WEEK_NS)


class CatalogueBootstrap(WeekBootstrap):
    """Same circular week blocks, built in chunks to bound scratch memory."""
    def __init__(self, start, end, settings, identity):
        self.start_week = (pd.Timestamp(start, tz="UTC").value - MONDAY_NS) // WEEK_NS
        last = (pd.Timestamp(end, tz="UTC").value - 1 - MONDAY_NS) // WEEK_NS
        self.weeks = int(last - self.start_week + 1)
        seed = int.from_bytes(hashlib.sha256(f"{settings['seed']}:{identity}".encode()).digest()[:8], "little")
        rng = np.random.default_rng(seed)
        count, block = settings["bootstrap_replicates"], settings["bootstrap_block_weeks"]
        self.weights = np.zeros((count, self.weeks), dtype=float)
        for offset in range(0, count, 4096):
            size = min(4096, count - offset)
            starts = rng.integers(0, self.weeks, (size, (self.weeks + block - 1) // block))
            selected = ((starts[:, :, None] + np.arange(block)) % self.weeks).reshape(size, -1)[:, :self.weeks]
            np.add.at(self.weights[offset:offset + size], (np.repeat(np.arange(size), self.weeks), selected.ravel()), 1.)
        self.settings = settings


def score_and_direction(features, spec):
    score = features[spec["score"]].to_numpy(float).copy()
    if spec.get("transform") == "absolute":
        score = np.abs(score)
    direction = features[spec["direction"]].to_numpy(float)
    valid = np.isfinite(score) & np.isfinite(features[spec["control"]].to_numpy(float))
    if spec["target"] != "absolute_return":
        valid &= np.isin(direction, [-1, 1])
    if spec["score"] == "squeeze_age":
        valid &= score > 0
    return score, direction, valid


def group_assignment(features, spec, fit):
    score, _, valid = score_and_direction(features, spec)
    control = features[spec["control"]].to_numpy(float)
    if spec["control"] == "ltf_direction":
        strata = (control > 0).astype(int)
    else:
        strata = np.searchsorted(fit["control_edges"], control, side="right")
    group = np.full(len(features), -1, dtype=int)
    if spec["kind"] == "categorical":
        group[valid & (score == 0)] = 0
        group[valid & (score == 1)] = 1
    elif fit["tail_edges"] and fit["tail_edges"][0] < fit["tail_edges"][1]:
        lo, hi = fit["tail_edges"]
        group[valid & (score <= lo)] = 0
        group[valid & (score >= hi)] = 1
    return group, strata


def fit_comparison(features, spec, training, settings):
    score, _, valid = score_and_direction(features, spec)
    control = features[spec["control"]].to_numpy(float)
    mask = training & valid
    fit = {"control_edges": [], "tail_edges": [], "strata": [], "weights": [],
           "training_common_support_mass": 0., "identified": False}
    if not mask.any():
        return fit
    if spec["control"] != "ltf_direction":
        fit["control_edges"] = np.unique(np.quantile(control[mask], settings["control_quantiles"])).tolist()
    if spec["kind"] == "tails":
        fit["tail_edges"] = np.quantile(score[mask], settings["tail_quantiles"]).tolist()
    groups, strata = group_assignment(features, spec, fit)
    candidates = mask & (groups >= 0)
    retained, counts = [], []
    for stratum in sorted(np.unique(strata[candidates])):
        cell = candidates & (strata == stratum)
        if all(np.sum(cell & (groups == arm)) >= settings["min_samples"] for arm in (0, 1)):
            retained.append(int(stratum))
            counts.append(int(cell.sum()))
    mass = sum(counts) / max(1, int(candidates.sum()))
    fit.update(strata=retained, weights=(np.asarray(counts) / max(1, sum(counts))).tolist(),
               training_common_support_mass=mass,
               identified=bool(retained) and mass >= settings.get("min_training_support_mass", .5))
    return fit


def target_values(labels, direction, target):
    if target == "directed_return":
        return direction * labels["return_bps"]
    if target == "absolute_return":
        return np.abs(labels["return_bps"])
    if target == "adverse_excursion":
        return np.where(direction == 1, -labels["mae_bps"], labels["mfe_bps"])
    raise ValueError(f"unknown target: {target}")


def matched_inference(indices, group, strata, target, close_ns, bootstrap, fit, settings):
    """Fixed training weights, same paired calendar blocks for all cells.

    One matrix multiplication reads the large resampling weights once per
    comparison. An empty cell invalidates its whole resample, never changes
    the estimated population by silently renormalizing available cells.
    """
    n = np.array([np.sum(group[indices] == arm) for arm in (0, 1)])
    active = []
    for arm in (0, 1):
        ix = indices[group[indices] == arm]
        week = (close_ns[ix] - MONDAY_NS) // WEEK_NS
        active.append(len(np.unique(week)))
    supported = bool(fit["identified"] and all(bootstrap.supported(int(n[a]), active[a]) for a in (0, 1)))
    matrix, cells, means = [], [], [[], []]
    for stratum in fit["strata"]:
        for arm in (0, 1):
            ix = indices[(strata[indices] == stratum) & (group[indices] == arm)]
            y = target[ix]
            week = ((close_ns[ix] - MONDAY_NS) // WEEK_NS - bootstrap.start_week).astype(int)
            if ((week < 0) | (week >= bootstrap.weeks)).any() or not np.isfinite(y).all():
                raise ValueError("invalid matched cell")
            matrix.extend([np.bincount(week, weights=y, minlength=bootstrap.weeks),
                           np.bincount(week, minlength=bootstrap.weeks)])
            means[arm].append(float(np.mean(y)) if len(y) else np.nan)
            cells.append({"stratum": stratum, "arm": arm, "n": len(y),
                          "active_weeks": len(np.unique(week)), "target_mean_bps": means[arm][-1]})
            supported &= len(y) >= settings["min_cell_samples"]
    weights = np.asarray(fit["weights"])
    observed = [float(np.dot(weights, means[a])) if len(weights) else np.nan for a in (0, 1)]
    samples = np.full((len(bootstrap.weights), 2), np.nan)
    if supported:
        draws = bootstrap.weights @ np.asarray(matrix).T
        cell_mean = np.divide(draws[:, ::2], draws[:, 1::2],
                              out=np.full_like(draws[:, ::2], np.nan), where=draws[:, 1::2] > 0)
        for arm in (0, 1):
            samples[:, arm] = cell_mean[:, arm::2] @ weights
        supported &= bool(np.isfinite(samples).all(axis=1).mean() >= .9)
    effect = observed[1] - observed[0]
    distribution = samples[:, 1] - samples[:, 0]
    lower, upper = interval(distribution, supported)
    return {"n_control": int(n[0]), "n_treated": int(n[1]), "weeks_control": active[0],
            "weeks_treated": active[1], "supported": bool(supported), "effect_bps": effect,
            "ci_low_bps": lower, "ci_high_bps": upper,
            "p_value": contrast_pvalue(effect, distribution, supported)}, observed, samples, cells


def describe(indices, labels, direction, target):
    raw = labels["return_bps"][indices]
    y = target[indices]
    mean = lambda values: float(np.mean(values)) if len(values) else np.nan
    d = direction[indices]
    out = {"n": len(indices), "raw_mean_bps": mean(raw), "raw_median_bps": float(np.median(raw)) if len(raw) else np.nan,
           "raw_std_bps": float(np.std(raw, ddof=1)) if len(raw) > 1 else np.nan,
           "raw_positive_rate": mean(raw > 0), "target_unweighted_mean_bps": mean(y),
           "target_median_bps": float(np.median(y)) if len(y) else np.nan,
           "directed_mean_bps": mean(d * raw) if len(d) and np.isin(d, [-1, 1]).all() else np.nan}
    for q in (.05, .25, .75, .95):
        out[f"target_q{int(q * 100):02}_bps"] = float(np.quantile(y, q)) if len(y) else np.nan
    for name in ("mfe_bps", "mae_bps", "hours", "gap_path", "partial_path"):
        out[f"mean_{name}"] = mean(labels[name][indices])
    for cost in (0, 2, 5):
        out[f"long_net_c{cost}_bps"] = mean(raw) * (1 - cost / 10000) - 2 * cost
        out[f"short_net_c{cost}_bps"] = -mean(raw) * (1 + cost / 10000) - 2 * cost
        out[f"directed_net_c{cost}_bps"] = out["directed_mean_bps"] - cost * mean(raw) / 10000 - 2 * cost
    return out


def analyze_catalogue(frame, features, cfg, instrument):
    close_ns = (pd.DatetimeIndex(frame.time).as_unit("ns") + pd.Timedelta(minutes=5)).asi8
    ready = (np.arange(len(frame)) >= cfg["context_rows"]) & (frame.n_bars.to_numpy() == 5)
    ready &= frame.is_gap_bar.to_numpy() == 0
    bounds = {name: (pd.Timestamp(s["start"], tz="UTC").value, pd.Timestamp(s["end"], tz="UTC").value)
              for name, s in cfg["splits"].items()}
    start, end = bounds["train"]
    training = ready & (close_ns >= start) & (close_ns < end)
    settings = cfg["statistics"]
    fits = {idea: fit_comparison(features, spec, training, settings) for idea, spec in cfg["ideas"].items()}
    labels_by_h = {h: forward_labels(frame, h, 300) for h in cfg["horizons"]}
    comparisons, groups, cells, coverage = [], [], [], []
    for split, (start, end) in bounds.items():
        mask = ready & (close_ns >= start) & (close_ns < end)
        bootstrap = CatalogueBootstrap(cfg["splits"][split]["start"], cfg["splits"][split]["end"],
                                  settings, f"catalogue:{instrument}:{split}")
        for idea, spec in cfg["ideas"].items():
            score, direction, valid = score_and_direction(features, spec)
            fit = fits[idea]
            assignment, strata = group_assignment(features, spec, fit)
            domain = valid & np.isin(strata, fit["strata"]) & (assignment >= 0)
            identity = {"instrument": instrument, "asset_class": cfg["instruments"][instrument],
                        "timeframe": "5m", "idea_id": idea, "target": spec["target"], "split": split}
            coverage.append(identity | {"rows": int(mask.sum()), "defined": int(np.sum(mask & valid)),
                                        "candidate_rows": int(np.sum(mask & domain)),
                                        "training_support_mass": fit["training_common_support_mass"],
                                        "identified": fit["identified"]})
            for h, labels in labels_by_h.items():
                eligible = mask & domain & np.isfinite(labels["return_bps"]) & (labels["exit_ns"] < end)
                target = target_values(labels, direction, spec["target"])
                eligible &= np.isfinite(target)
                if spec["kind"] == "categorical":
                    ix = non_overlapping(np.flatnonzero(eligible), h)
                else:
                    first = np.flatnonzero(mask)
                    grid = (np.arange(len(frame)) - (first[0] if len(first) else 0)) % h == 0
                    ix = np.flatnonzero(eligible & grid)
                result, means, samples, cell_rows = matched_inference(ix, assignment, strata, target,
                                                                     close_ns, bootstrap, fit, settings)
                key = identity | {"horizon": h}
                comparisons.append(key | result)
                cells.extend(key | row for row in cell_rows)
                for arm in (0, 1):
                    arm_ix = ix[assignment[ix] == arm]
                    lower, upper = interval(samples[:, arm], result["supported"])
                    groups.append(key | {"arm": arm} | describe(arm_ix, labels, direction, target)
                                  | {"target_matched_mean_bps": means[arm], "target_ci_low_bps": lower,
                                     "target_ci_high_bps": upper})
    return comparisons, groups, cells, coverage, [{"instrument": instrument, "idea_id": k, **v} for k, v in fits.items()]
