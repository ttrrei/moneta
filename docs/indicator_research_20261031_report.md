# P1 indicator research — results and next move

Date: 2026-10-31. Final attempt: **IR-20261031-P1-v2**, definition version 1.

All nine P1 families in [your research brief](idicator_reasearch.md) now have
implemented or explicitly reused outputs, quality checks and real-data results.
**No tested output qualifies for promotion into strategy generation.** This
means the stated evidence threshold was not met; it does not prove that the
features are universally useless.

The work includes an initial implementation/run, a second review with fixes,
and a third audit/reproducibility review. See the
[three-pass review record](indicator_research_20261031_reviews.md) and
[formulas, timing and protocol](indicator_research_P1_spec.md).

## What was built

- `library/market_structure.py`: confirmed swings, structural comparisons,
  prior-level breaks and frozen-boundary retest/re-entry/failure events.
- `pipeline/research_features.py`: a pure, one-instrument additive stage with
  ATR ranks and explicit pivot/confirmation timestamps.
- `strategy/feature_research.py`: next-open labels, non-overlapping studies,
  frozen training buckets, conditional distributions, paired week-block
  uncertainty and global multiple-testing correction.
- `scripts/research_indicators.py`: bounded data loading, fixed protocol,
  archived sources, full-attempt recording and no-overwrite output handling.
- `scripts/verify_indicator_research.py`: independent real-data formula,
  timing, cost, grid and replay checks.

The original wick/CLV and three ATR-ratio columns are reused verbatim. Existing
ATR-24 and shifted Donchian-24 provide inputs. The inventory covers all 575
physical Gold columns across both timeframes. Each derived research file has
62 columns: 19 selected original inputs and 43 new primary/auxiliary columns.
The default Gold tables retain their original 305/270 columns.

## Data and experiment size

| Instrument / class | 5m source rows | 1h source rows |
|---|---:|---:|
| EUR_USD / FX | 416,107 | 34,410 |
| XAU_USD / metal | 395,556 | 32,655 |
| BTC_USD / crypto | 409,018 | 33,841 |
| Total | 1,220,681 | 100,906 |

Total source rows: **1,321,587**. Available data starts in January 2020; exact
per-input bounds and filtered development-frame hashes are in the manifest.
The last source bar opens on 2025-07-31; decision/label eligibility applies
stricter split-close/exit boundaries.

Training is 2020–2022. Development validation is 2023–2024 and then January–July
2025. All periods are UTC, end-exclusive. The protected holdout starts
2025-08-01 and was not used. These development periods have previously been
used for other strategy research and are not fresh OOS evidence.

Ten continuous outputs and fourteen events were tested at horizons
6/12/24/60/120 observed bars on both timeframes. Every planned combination was
recorded: **2,160 primary comparisons**, **5,760 conditional group summaries**,
and **432 feature-distribution records**. No parameter Cartesian search was
performed. Buckets use training quantiles only; events use fixed directions.

## What the data says

**1,602 of 2,160 comparisons meet the minimum sample/week support rule.** All
1,080 5m comparisons are supported; 522 of 1,080 hourly comparisons are
supported. At least 30 samples and 8 active weeks are required per arm.
Unsupported tests remain in the global family with `p=1`.

| Family | Supported 5m / planned | Supported 1h / planned | Promotion decision |
|---|---:|---:|---|
| MS-01 confirmed swings | 90 / 90 | 84 / 90 | Reject this tested definition for promotion |
| MS-02 HH/HL/LH/LL | 180 / 180 | 20 / 180 | Reject; hourly coverage needs a future revised definition |
| MS-03 structure break/strength | 180 / 180 | 28 / 180 | Reject; hourly coverage needs a future revised definition |
| MS-04 breakout retest | 90 / 90 | 10 / 90 | Reject; hourly coverage needs a future revised definition |
| VR-01 ATR percentile | 90 / 90 | 58 / 90 | Reject this tested definition for promotion |
| VR-02 ATR ratios | 135 / 135 | 82 / 135 | Reject this tested definition for promotion |
| FR-01 wick/CLV | 135 / 135 | 88 / 135 | Reject this tested definition for promotion |
| FR-02 range re-entry | 90 / 90 | 78 / 90 | Reject this tested definition for promotion |
| FR-03 failed breakout | 90 / 90 | 74 / 90 | Reject this tested definition for promotion |

There are 140 nominal `p<0.05` rows before correcting for the complete research
family. The smallest final p-value is **0.000045**; the smallest global
Benjamini–Yekutieli adjusted q-value is **0.802416**, above the fixed **0.10**
threshold. Thus there are **zero adjusted discoveries**, and none of the 24
outputs meets the additional requirement to replicate in both validation
slices on at least two assets at the same timeframe/horizon.

This conclusion uses the corrected 199,999-resample analysis, not the initial
coarse 1,999-resample run. The numerical refinement left every sample count,
point estimate, fitted bucket, input frame and derived feature unchanged.
The initial attempt remains available; the change and its checks are recorded
in `numerical_refinement_audit.json`.

### Costs can exceed the observed conditional effect

For a concrete fixed illustration, the table below shows **every asset and
slice** for `failed_breakout_up`, 5m, horizon 24. Its predefined direction is
short after a confirmed failure. This setting illustrates interpretation; it
was not selected as a profitable result and has no adjusted discovery.

| Instrument | Slice | Non-overlapping events | Mean gross short bps | Mean short net bps, 2 one-way |
|---|---|---:|---:|---:|
| EUR_USD | train | 1,837 | 0.045 | -3.955 |
| EUR_USD | validation_1 | 1,280 | 0.193 | -3.807 |
| EUR_USD | validation_2 | 360 | -0.722 | -4.722 |
| XAU_USD | train | 1,776 | -0.386 | -4.386 |
| XAU_USD | validation_1 | 1,212 | -0.405 | -4.405 |
| XAU_USD | validation_2 | 329 | 2.061 | -1.939 |
| BTC_USD | train | 1,914 | 0.171 | -3.829 |
| BTC_USD | validation_1 | 1,251 | -1.410 | -5.410 |
| BTC_USD | validation_2 | 378 | -3.588 | -7.589 |

All conditional groups include gross return mean/median/std/quantiles,
positive rates, pointwise confidence intervals, observed MFE/MAE, elapsed
hours, path-quality rates, and long/short cost scenarios at 0/2/5 bps one-way.
An event's directional excess over an unconditional baseline is different
from its cash net return. A continuous bucket spread is not portfolio P&L.

### Hourly structural coverage is a separate finding

The swing detector is undefined on roughly **35.5%–69.9%** of otherwise
eligible hourly signal rows across assets/slices. Structural-break references
are undefined on roughly **57.5%–94.7%**, depending on direction and slice.
Session discontinuities and partial bars repeatedly reset the contiguous
6+6 pivot window; many surviving pivots have no valid predecessor or reference.
Unknowns remain null. This is visible in the distribution artifact rather than
hidden by treating missing structure as zero.

For 5m, the corresponding swing-detector null fraction is about 4.4%–13.9%.
That better coverage still does not establish stable adjusted conditional
information. A session-aware hourly definition is a reasonable future study;
changing resets now and presenting it as the same experiment would be unsound.

## Three reviews and verification

The [review record](indicator_research_20261031_reviews.md) explains each pass
and correction. Key fixes included proper availability timestamps, shifted and
frozen range levels, prior structural references, exit-fill excursion handling,
consistent quality cohorts, unambiguous ATR-rank ties, stricter split-purge
tests, and sufficient Monte Carlo resolution for the planned correction.

Final validation evidence is in the [machine audit](../research/indicators/IR-20261031-P1-v2/review_audit.json).
The audit checks 3,000 direct next-open/excursion calculations and 1,200
independent empirical ATR ranks, frozen training cutpoints, real-data prefix
causality, pivot timing, the full comparison grid, costs and an independent
BY calculation. The full replay compares all seven result/protocol files and
six derived Parquets byte for byte. Run timestamps and output paths naturally
differ in the replay manifests.

Software checks: **700 tests passed**, including 30 new focused tests; **40/40**
registry mutation cases passed. The existing strategy checker reports **zero
failures** and the same **22 X15 family-saturation warnings** as before this
study. Compilation and whitespace checks pass. Exact commands/results are in
`regression_checks.json`.

The original OOS ledger remains unchanged, SHA-256
`3148000cf7f66bc564211610f3423571c484e6eae979963577a3ba6a48236cd6`.
No strategy was nominated and no OOS token consumed. Existing strategy results
and statuses were not changed.

## Artifacts and reproduction

Final run: [IR-20261031-P1-v2](../research/indicators/IR-20261031-P1-v2/).
Initial run: [IR-20261031-P1-v1](../research/indicators/IR-20261031-P1-v1/).

| Artifact | Contents |
|---|---|
| `manifest.yml`, `protocol.yml`, `source_snapshot/` | Attempt provenance, exact protocol, hashes and archived implementation |
| `existing_feature_inventory.csv` | All 575 Gold columns, types and producing groups |
| `training_buckets.yml` | All 60 training-only feature/asset/timeframe bucket fits |
| `conditional_returns.csv` | All 5,760 group distributions and cost/excursion summaries |
| `comparisons.csv` | All 2,160 effects, CIs, p/q values, support and baseline information |
| `distributions.csv` | All 432 coverage/range/event-count records |
| `decisions.csv`, `feature_records.yml` | All 24 output decisions and nine family hypothesis/quality records |
| `numerical_refinement_audit.json` | v1/v2 point-estimate, data and economic-protocol identity |
| `review_audit.json`, `regression_checks.json` | Final data/replay audit and software-regression evidence |

Derived development-only Parquets are under
`data/indicator_research/IR-20261031-P1-v2/` and follow the repository's existing
data ignore rule. CSV/YAML results and source snapshots are retained in the
workspace for version control. Use new output directories for another replay:

```bash
OPENBLAS_NUM_THREADS=1 .venv/bin/python scripts/research_indicators.py \
  --out /tmp/indicator-v2-replay \
  --data-out /tmp/indicator-v2-replay-data

OPENBLAS_NUM_THREADS=1 .venv/bin/python scripts/verify_indicator_research.py \
  --run research/indicators/IR-20261031-P1-v2 \
  --replay /tmp/indicator-v2-replay \
  --out /tmp/indicator-v2-audit.json

.venv/bin/python -m pytest tests/ -q
.venv/bin/python scripts/test_check_results.py
.venv/bin/python scripts/check_results.py --json
```

These commands require the existing local Gold data and pinned environment.
The runner deliberately refuses existing destinations. No network is required.

## Recommended next research

Keep the causal feature implementations and audit tools available. Do not
generate strategies from the current outputs on the strength of this study.
A useful next protocol would first define session-aware hourly structure
without synthetic candles, evaluate matched controls for events, and measure
the effect size needed to survive realistic costs. It should reserve a genuinely
unused evaluation period before introducing additional variants.

Inference here remains exploratory: only three assets, reused development
history, approximate four-week block-bootstrap assumptions, unmatched event
baselines, and finite Monte Carlo precision. Horizons count observed bars;
later session gaps lengthen elapsed holdings, and partial bars may miss path
extremes. Financing, slippage, sizing and executable portfolio behavior are
outside this feature study. P2 HTF/exit and P3 session/statistical research
remain separate future batches under the brief.
