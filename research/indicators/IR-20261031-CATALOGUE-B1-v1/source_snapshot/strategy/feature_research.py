"""Descriptive, development-only feature studies; no strategy execution.

Features are causal inputs. Forward labels deliberately use the future, in a
separate function. Inferential rows use non-overlapping holdings, frozen
training buckets and four-week moving-block resampling; no IID trade t-tests.
"""
from __future__ import annotations

import hashlib
import numpy as np
import pandas as pd

WEEK_NS = 7 * 86400 * 1_000_000_000
MONDAY_NS = pd.Timestamp("1970-01-05", tz="UTC").value
CONTEXT_ROWS = 258  # conservative finite-state burn-in: 2*120 + 2*6 + 6


def forward_labels(frame: pd.DataFrame, horizon: int, seconds: int) -> dict[str, np.ndarray]:
    """Close(t) decision -> open(t+1) entry -> open(t+1+h) exit.

    Horizons count OBSERVED bars. Later session gaps stay in the return and
    elapsed duration; they are reported. Entry must be adjacent to the signal.
    MFE/MAE use held bars [t+1, t+1+h) plus the exit fill's open, excluding
    the exit bar's later high/low. This includes gaps into the exit fill.
    """
    if horizon not in (6, 12, 24, 60, 120):
        raise ValueError("forward horizon outside CFD grid")
    n = len(frame)
    result = {name: np.full(n, np.nan) for name in
              ("return_bps", "mfe_bps", "mae_bps", "hours", "gap_path", "partial_path", "exit_ns")}
    if n <= horizon + 1:
        return result
    times = pd.DatetimeIndex(frame["time"]).as_unit("ns").asi8
    o, high, low = (frame[name].to_numpy(float) for name in ("open", "high", "low"))
    t = np.arange(n - horizon - 1)
    entry, exit_ = t + 1, t + horizon + 1
    hi = pd.Series(high).rolling(horizon, min_periods=horizon).max().to_numpy()[t + horizon]
    lo = pd.Series(low).rolling(horizon, min_periods=horizon).min().to_numpy()[t + horizon]
    hi = np.maximum(hi, o[exit_])
    lo = np.minimum(lo, o[exit_])
    eligible = (t >= CONTEXT_ROWS) & (frame["n_bars"].to_numpy()[t] == seconds // 60)
    eligible &= (times[entry] - times[t] == seconds * 1_000_000_000)
    eligible &= (np.isfinite(o[entry]) & (o[entry] > 0) & np.isfinite(o[exit_]) & (o[exit_] > 0)
                 & np.isfinite(hi) & np.isfinite(lo))
    if "is_gap_bar" in frame:
        eligible &= frame["is_gap_bar"].to_numpy()[t] == 0
    indices = t[eligible]
    r = o[exit_] / o[entry] - 1.
    gap = np.r_[False, np.diff(times) != seconds * 1_000_000_000]
    gap_sum = np.r_[0, np.cumsum(gap)]
    partial = frame["n_bars"].to_numpy() != seconds // 60
    partial_sum = np.r_[0, np.cumsum(partial)]
    values = {"return_bps": r * 10000, "mfe_bps": (hi / o[entry] - 1) * 10000,
              "mae_bps": (lo / o[entry] - 1) * 10000,
              "hours": (times[exit_] - times[entry]) / 3.6e12,
              "gap_path": (gap_sum[exit_ + 1] - gap_sum[entry + 1] > 0).astype(float),
              "partial_path": (partial_sum[exit_] - partial_sum[entry] > 0).astype(float),
              "exit_ns": times[exit_].astype(float)}
    for name, value in values.items():
        result[name][indices] = value[eligible]
    return result


def non_overlapping(indices, horizon):
    selected, next_index = [], -1
    for index in indices:
        if index >= next_index:
            selected.append(index)
            next_index = index + horizon
    return np.asarray(selected, dtype=int)


def fit_buckets(values, training_mask, quantiles):
    values = np.asarray(values, dtype=float)
    available = values[training_mask & np.isfinite(values)]
    if len(available) == 0 or np.unique(available).size < 2:
        return np.array([], dtype=float)
    return np.unique(np.quantile(available, quantiles))


def by_adjust(pvalues):
    """Benjamini–Yekutieli adjustment across the COMPLETE planned family."""
    p = np.asarray(pvalues, dtype=float)
    if not np.isfinite(p).all() or ((p < 0) | (p > 1)).any():
        raise ValueError("p-values must be finite in [0,1]")
    if not len(p):
        return p
    order = np.argsort(p, kind="stable")
    m = len(p)
    adjusted = p[order] * m * np.sum(1 / np.arange(1, m + 1)) / np.arange(1, m + 1)
    adjusted = np.minimum.accumulate(adjusted[::-1])[::-1].clip(0, 1)
    out = np.empty(m)
    out[order] = adjusted
    return out


class WeekBootstrap:
    def __init__(self, start, end, settings, identity):
        self.start_week = (pd.Timestamp(start, tz="UTC").value - MONDAY_NS) // WEEK_NS
        last = (pd.Timestamp(end, tz="UTC").value - 1 - MONDAY_NS) // WEEK_NS
        self.weeks = int(last - self.start_week + 1)
        seed = int.from_bytes(hashlib.sha256(f"{settings['seed']}:{identity}".encode()).digest()[:8], "little")
        rng = np.random.default_rng(seed)
        count, block = settings["bootstrap_replicates"], settings["bootstrap_block_weeks"]
        # Circular moving blocks keep empty calendar weeks and paired group
        # counts. The same resamples are used for both arms of a contrast.
        starts = rng.integers(0, self.weeks, (count, (self.weeks + block - 1) // block))
        selected = (starts[:, :, None] + np.arange(block)) % self.weeks
        selected = selected.reshape(count, -1)[:, :self.weeks]
        self.weights = np.zeros((count, self.weeks), dtype=float)
        np.add.at(self.weights, (np.repeat(np.arange(count), self.weeks), selected.ravel()), 1.)
        self.settings = settings

    def samples(self, values, timestamps):
        values = np.asarray(values, dtype=float)
        week = ((np.asarray(timestamps, dtype=np.int64) - MONDAY_NS) // WEEK_NS - self.start_week).astype(int)
        if ((week < 0) | (week >= self.weeks)).any() or not np.isfinite(values).all():
            raise ValueError("bootstrap inputs outside split or non-finite")
        sums = np.bincount(week, weights=values, minlength=self.weeks)
        counts = np.bincount(week, minlength=self.weeks)
        denominator = self.weights @ counts
        numerator = self.weights @ sums
        boot = np.divide(numerator, denominator, out=np.full(len(denominator), np.nan), where=denominator > 0)
        return boot, int(np.count_nonzero(counts))

    def supported(self, n, weeks):
        return n >= self.settings["min_samples"] and weeks >= self.settings["min_active_weeks"]


def interval(bootstrap, supported=True):
    valid = np.asarray(bootstrap)[np.isfinite(bootstrap)]
    if not supported or len(valid) < .9 * len(bootstrap):
        return np.nan, np.nan
    return tuple(np.quantile(valid, [.025, .975]))


def contrast_pvalue(effect, bootstrap, supported):
    valid = np.asarray(bootstrap)[np.isfinite(bootstrap)]
    if not supported or len(valid) < .9 * len(bootstrap):
        return 1.
    # Recenter the bootstrap distribution at the null, with a finite-MC +1.
    return float((1 + np.sum(np.abs(valid - effect) >= abs(effect))) / (len(valid) + 1))


def summarize(indices, labels, close_ns, bootstrap: WeekBootstrap):
    r = labels["return_bps"][indices]
    boot, weeks = bootstrap.samples(r, close_ns[indices])
    n = len(r)
    supported = bootstrap.supported(n, weeks)
    lower, upper = interval(boot, supported)
    out = {"n": n, "active_weeks": weeks, "supported": supported,
           "mean_bps": float(np.mean(r)) if n else np.nan,
           "median_bps": float(np.median(r)) if n else np.nan,
           "std_bps": float(np.std(r, ddof=1)) if n > 1 else np.nan,
           "positive_rate": float(np.mean(r > 0)) if n else np.nan,
           "short_positive_rate": float(np.mean(r < 0)) if n else np.nan,
           "ci_low_bps": lower, "ci_high_bps": upper}
    for name, q in (("q05_bps", .05), ("q25_bps", .25), ("q75_bps", .75), ("q95_bps", .95)):
        out[name] = float(np.quantile(r, q)) if n else np.nan
    for name in ("mfe_bps", "mae_bps", "hours", "gap_path", "partial_path"):
        out["mean_" + name] = float(np.mean(labels[name][indices])) if n else np.nan
    out["short_mfe_bps"] = -out["mean_mae_bps"]
    out["short_mae_bps"] = -out["mean_mfe_bps"]
    # Cash P&L per entry notional, fees charged on entry and exit notional.
    # Short = sign-mirrored simple price return, not the legacy engine's
    # reciprocal short convention. No financing/slippage is simulated.
    for cost in (0, 2, 5):
        factor = cost / 10000.
        out[f"long_net_c{cost}_bps"] = out["mean_bps"] * (1 - factor) - 2 * cost
        out[f"short_net_c{cost}_bps"] = -out["mean_bps"] * (1 + factor) - 2 * cost
    return out, boot


def analyze_frame(frame, features, cfg, instrument, timeframe):
    seconds = cfg["timeframes"][timeframe]
    close_ns = (pd.DatetimeIndex(frame["time"]) + pd.Timedelta(seconds=seconds)).as_unit("ns").asi8
    all_features = list(cfg["continuous"]) + list(cfg["events"])
    if set(all_features) - set(features):
        raise ValueError("planned feature missing")
    splits = {name: (pd.Timestamp(spec["start"], tz="UTC").value, pd.Timestamp(spec["end"], tz="UTC").value)
              for name, spec in cfg["splits"].items()}
    train_start, train_end = splits["train"]
    ready = (np.arange(len(frame)) >= CONTEXT_ROWS) & (frame["n_bars"].to_numpy() == seconds // 60)
    if "is_gap_bar" in frame:
        ready &= frame["is_gap_bar"].to_numpy() == 0
    training = (close_ns >= train_start) & (close_ns < train_end) & ready
    cuts = {name: fit_buckets(features[name].to_numpy(), training, cfg["statistics"]["bucket_quantiles"])
            for name in cfg["continuous"]}
    conditional, comparisons, distributions, fitted = [], [], [], []
    for name, edges in cuts.items():
        fitted.append({"instrument": instrument, "timeframe": timeframe, "feature": name,
                       "train_start": cfg["splits"]["train"]["start"], "train_end": cfg["splits"]["train"]["end"],
                       "cutpoints": edges.tolist(), "bucket_count": len(edges) + 1})
    labels_by_h = {h: forward_labels(frame, h, seconds) for h in cfg["horizons"]}
    for split, (start, end) in splits.items():
        mask = (close_ns >= start) & (close_ns < end) & ready
        b = WeekBootstrap(cfg["splits"][split]["start"], cfg["splits"][split]["end"],
                          cfg["statistics"], f"{instrument}:{timeframe}:{split}")
        for name in all_features:
            x = features[name].to_numpy(float)
            available = x[mask & np.isfinite(x)]
            distributions.append({"instrument": instrument, "asset_class": cfg["instruments"][instrument],
                                  "timeframe": timeframe, "split": split, "feature": name,
                                  "rows": int(mask.sum()), "non_null": len(available),
                                  "null_fraction": 1 - len(available) / max(1, int(mask.sum())),
                                  "minimum": float(available.min()) if len(available) else np.nan,
                                  "maximum": float(available.max()) if len(available) else np.nan,
                                  "median": float(np.median(available)) if len(available) else np.nan,
                                  "events": int(np.sum(available == 1)) if name in cfg["events"] else 0})
        for h, labels in labels_by_h.items():
            eligible = mask & np.isfinite(labels["return_bps"]) & (labels["exit_ns"] < end)
            # Fixed grid is independent of all feature values and bucket labels.
            first = np.flatnonzero(mask)
            grid = (np.arange(len(frame)) - (first[0] if len(first) else 0)) % h == 0
            baseline_indices = np.flatnonzero(eligible & grid)
            baseline, baseline_boot = summarize(baseline_indices, labels, close_ns, b)
            for name in all_features:
                x = features[name].to_numpy(float)
                event = name in cfg["events"]
                feature_id = cfg["events"][name]["feature_id"] if event else cfg["continuous"][name]
                identity = {"instrument": instrument, "asset_class": cfg["instruments"][instrument],
                            "timeframe": timeframe, "split": split, "horizon": h,
                            "feature_id": feature_id, "feature": name}
                if event:
                    ix = non_overlapping(np.flatnonzero(eligible & (x == 1)), h)
                    stats, boot = summarize(ix, labels, close_ns, b)
                    conditional.append(identity | {"group": "event"} | stats)
                    direction = cfg["events"][name]["direction"]
                    effect = direction * (stats["mean_bps"] - baseline["mean_bps"])
                    sampled = direction * (boot - baseline_boot)
                    supported = stats["supported"] and baseline["supported"]
                    n_low, n_high = stats["n"], baseline["n"]
                    net = stats[f"long_net_c2_bps" if direction == 1 else "short_net_c2_bps"]
                    ic = np.nan
                else:
                    edges = cuts[name]
                    buckets = np.searchsorted(edges, x, side="right")
                    summaries, boots = [], []
                    for group in range(len(edges) + 1):
                        ix = np.flatnonzero(eligible & grid & np.isfinite(x) & (buckets == group))
                        stats, boot = summarize(ix, labels, close_ns, b)
                        conditional.append(identity | {"group": f"q{group + 1}"} | stats)
                        summaries.append(stats)
                        boots.append(boot)
                    low, high = summaries[0], summaries[-1]
                    effect = high["mean_bps"] - low["mean_bps"] if len(edges) else np.nan
                    sampled = boots[-1] - boots[0]
                    supported = low["supported"] and high["supported"] and len(edges) > 0
                    n_low, n_high = low["n"], high["n"]
                    net = np.nan  # A bucket spread is not a funded portfolio.
                    ix = np.flatnonzero(eligible & grid & np.isfinite(x))
                    if len(ix) > 2 and np.unique(x[ix]).size > 1:
                        ic = pd.Series(x[ix]).rank().corr(pd.Series(labels["return_bps"][ix]).rank())
                    else:
                        ic = np.nan
                lower, upper = interval(sampled, supported)
                comparisons.append(identity | {"kind": "event_minus_baseline" if event else "top_minus_bottom",
                                                "n_low": n_low, "n_high": n_high, "supported": bool(supported),
                                                "effect_bps": effect, "ci_low_bps": lower, "ci_high_bps": upper,
                                                "p_value": contrast_pvalue(effect, sampled, supported),
                                                "rank_ic": ic, "event_net_c2_bps": net,
                                                "baseline_mean_bps": baseline["mean_bps"],
                                                "baseline_n": baseline["n"]})
    return conditional, comparisons, distributions, fitted
