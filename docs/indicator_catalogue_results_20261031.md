# Fifty-idea catalogue — implementation, tests and validation results

Date: 2026-10-31. **All 50 ideas have been implemented and evaluated in five
stages.** Software checks pass. Under the fixed research criteria, **43 ideas
are rejected for promotion and 7 require revision** because of insufficient
common support. No idea met the complete replication rule, and no strategy was
nominated.

This is the first operational version of each idea, not a claim that every
possible variant has been exhausted. The experiments use development history
previously researched elsewhere in this project; they are not fresh OOS tests.

- [Original catalogue](indicator_idea_catalogue_20261031.md)
- [Exact implementation/validation contract](indicator_catalogue_validation_spec_20261031.md)
- [All-50 progress and measured decisions](../research/indicators/CATALOGUE-50-20261031/idea_progress.csv)
- [Independent numerical/replay audit](../research/indicators/CATALOGUE-50-20261031/validation_audit.json)

## What is complete

| Step | Result |
|---|---|
| Define and implement catalogue ideas | 50 / 50, two ideas per style in each of five batches |
| Software quality gates | 734 tests passed, including 34 new catalogue tests |
| Planned catalogue comparisons | 2,250 / 2,250 recorded |
| Comparisons meeting matched-sample/inference support | 1,708 / 2,250; 542 unsupported and retained with `p=1` |
| Complete correction family | 4,410 tests: 2,160 prior P1 + 2,250 catalogue |
| Catalogue rows with global `q<=0.10` | 22 individual cells across seven ideas |
| Ideas passing both validation slices on at least two assets | 0 / 50 |
| Final decisions | 43 reject; 7 revise; 0 keep |
| Strategy promotion / OOS consumption | None |

Each idea has 45 planned comparisons: three assets, three slices and five
holding horizons. The two arms are also described in 4,500 conditional group
records. Training covariates determine the cuts, control strata and fixed
matching weights; forward returns never fit those choices.

## Data and run design

Signals use **5m** bars for EUR_USD, XAU_USD and BTC_USD. Completed **1h** bars
provide context. This run does not claim validation of every idea as an hourly
signal. The three target datasets contain **1,220,681 5m rows** and their
context datasets contain **100,906 1h rows**. These inputs are reused across
batches, not counted as new independent data each time. MR-06 additionally
uses GBP_USD, XAG_USD and ETH_USD as fixed exact-time peers.

Training is 2020–2022; development validation is 2023–2024 and January–July
2025. All split ends are exclusive UTC boundaries. Every label exits before
its own split end. Holding horizons are 6/12/24/60/120 observed bars, with
next-open entry. Actual wall time and future gap/partial-bar incidence are
recorded. No price is imputed.

There is one primary target per idea: 36 directional-return ideas, 7 movement-
magnitude ideas and 7 adverse-excursion ideas. A magnitude or risk association
is not a directional entry signal. The primary effect compares treatment and
control within frozen training strata; it is not a compounded strategy P&L.

Use 499,999 paired four-calendar-week block resamples, including empty weeks,
and one fixed 4,410-test BY family. Earlier batches included unrun catalogue
cells as `p=1`; final q-values incorporate all fifty ideas. All results,
including unsupported comparisons and every earlier interim decision, remain
recorded. The aggregate final comparison file recalculates q-values without
rewriting those earlier artifacts.

## Results by style and batch

| Style | Implemented | Supported / 450 comparisons | Adjusted catalogue findings |
|---|---:|---:|---:|
| Trend / multi-timeframe | 10 | 386 | 2 |
| Mean reversion | 10 | 319 | 0 |
| Compression / expansion | 10 | 319 | 12 |
| Candle / structure | 10 | 323 | 1 |
| Persistence / sessions | 10 | 361 | 7 |

| Batch | Ideas | Supported / 450 |
|---|---:|---:|
| 1 | 10 | 416 |
| 2 | 10 | 354 |
| 3 | 10 | 333 |
| 4 | 10 | 345 |
| 5 | 10 | 260 |

The 22 adjusted catalogue findings concern CB-01, CB-07, CB-08, CB-09, PA-06,
PS-08 and TR-08. **21 of those cells concern movement magnitude or adverse
excursion; one concerns directional return.** They do not reproduce in the
required combination of same horizon, both validation slices and two assets.
The [complete adjusted-findings table](../research/indicators/CATALOGUE-50-20261031/adjusted_findings.csv)
includes all 22, rather than only favorable examples.

The final family also has one adjusted prior-P1 cell: XAU_USD `structure_hl`,
validation 1, horizon 6, `q=0.077387`. BY ranks change when the prespecified
catalogue family is completed. This is not new independent P1 evidence;
the original P1 result files and original q-values remain intact. It does not
meet the replication rule either.

### Clearest within-asset finding: session-phase activity surprise

PS-08 measures current tick activity relative to the same elapsed slot in the
preceding six observed sessions, controlling approximately for recent activity
through training strata of `vol_rel_24`. At **horizon 6**, EUR_USD shows a
consistent increase in future absolute price movement for the high-surprise
group versus the low-surprise group:

| Slice | Control / treatment samples | Matched difference in future absolute return, bps | Pointwise 95% CI | Global q |
|---|---:|---:|---|---:|
| Train | 6,257 / 6,242 | 1.360 | 0.928–1.797 | 0.006592 |
| Validation 1 | 3,766 / 3,641 | 1.465 | 1.137–1.827 | 0.006592 |
| Validation 2 | 1,346 / 1,416 | 2.886 | 1.475–4.293 | 0.055840 |

For XAU_USD, the same effect is positive in all slices, but validation 2 has
`q=0.655643`, so it fails the fixed threshold. BTC_USD has too little matched
common support under the training-frozen activity thresholds. **PS-08 therefore
remains rejected for catalogue promotion.** The EUR result is a useful
asset-specific follow-up question about movement/risk context, not evidence of
a profitable long/short rule. The bps in this table are not trading profits.

CB-09 volatility instability also has several positive magnitude findings,
but across different assets/slices rather than complete replication. Other
isolated findings should be read with the same distinction between a cell and
a retained idea. No thresholds or asset requirements were loosened afterward.

## Why seven ideas need revision

`revise` means the declared comparison could not achieve adequate common
support across the required assets/slices. It is different from observing a
well-supported null result.

| Idea | Measured obstacle |
|---|---|
| PA-03 containment release | The controlled subset also requires a fresh range break. EUR_USD has no retained training common-support strata; XAU_USD retains only 33.3% of training candidates. |
| PA-04 outside-bar settlement | Matched tail samples do not provide supported comparisons across all three slices on two assets at any horizon. |
| MR-09 session displacement | EUR_USD has only 28 defined training observations under the actual-displacement/first-24-bar definition; the other assets do not supply complete joint support. |
| CB-10 break sequence balance | The discrete tail comparison has no retained training common-support strata on any asset. More raw rows do not resolve that contrast design. |
| PA-10 level clustering | Retained matching strata cover about 24%–29% of training candidates, below the fixed 50% minimum. |
| PS-09 initial-range utilisation | Complete initial blocks and matched phase/usage tails are too scarce jointly across assets/slices. |
| PS-10 move attribution | Known closure displacement is retained, but the frozen matched tails still lack stable cross-slice support on two assets. |

For PS-09, a direct source check found only **45 of 1,449** EUR_USD observed
session starts had a complete first bar. Only about **0.28%** had six initial
complete, contiguous bars. The strict initial-range definition must therefore
remain largely undefined on this input. Filling missing minutes or treating
partial initial ranges as complete would manufacture evidence.

Any alternative event/threshold, support rule, asset set or session definition
is a new registered experiment. This report does not hide these failures by
retuning the existing study.

## All fifty measured decisions

`Supported` is the number of supported comparisons out of 45. An engineering
pass does not imply empirical usefulness. Exact score/control/target mappings,
reasons and evidence links are in the machine-readable registry.

| ID | Idea | Target | Supported / 45 | Decision |
|---|---|---|---:|---|
| CB-01 | Squeeze episode age | Magnitude | 38 | reject |
| CB-02 | Nested-range compression | Magnitude | 42 | reject |
| CB-03 | Compression-conditioned range release | Direction | 40 | reject |
| CB-04 | Acceptance beyond a broken range | Direction | 18 | reject |
| CB-05 | Breakout activity participation | Direction | 18 | reject |
| CB-06 | Body-led versus wick-led expansion | Direction | 42 | reject |
| CB-07 | Upside/downside variance imbalance | Risk | 45 | reject |
| CB-08 | Range versus close-volatility disagreement | Risk | 34 | reject |
| CB-09 | Volatility instability | Magnitude | 42 | reject |
| CB-10 | Directional range-break sequence balance | Direction | 0 | revise |
| MR-01 | Robust median stretch | Direction | 19 | reject |
| MR-02 | Causal regression residual | Direction | 45 | reject |
| MR-03 | Session-VWAP stretch by session phase | Direction | 42 | reject |
| MR-04 | Oscillator extremes conditional on trend efficiency | Direction | 36 | reject |
| MR-05 | Price–oscillator disagreement | Direction | 39 | reject |
| MR-06 | Cross-asset residual stretch | Direction | 43 | reject |
| MR-07 | Post-shock loss of speed | Direction | 25 | reject |
| MR-08 | Price–activity-pressure disagreement | Direction | 45 | reject |
| MR-09 | Session-open displacement recovery | Direction | 1 | revise |
| MR-10 | Mean reclaim after persistent stretch | Direction | 24 | reject |
| PA-01 | Accumulated wick imbalance | Direction | 44 | reject |
| PA-02 | Body-engulfing reversal strength | Direction | 44 | reject |
| PA-03 | Mother-bar containment release | Direction | 4 | revise |
| PA-04 | Outside-bar settlement | Direction | 14 | revise |
| PA-05 | Repeated tests of a frozen boundary | Direction | 45 | reject |
| PA-06 | First revisit of confirmed structure | Direction | 40 | reject |
| PA-07 | Next-bar confirmation of a strong close | Direction | 42 | reject |
| PA-08 | Wick-to-body transition | Direction | 45 | reject |
| PA-09 | Prior-extreme sweep with inside close | Direction | 45 | reject |
| PA-10 | Confirmed-level clustering | Risk | 0 | revise |
| PS-01 | Return-sign memory | Direction | 45 | reject |
| PS-02 | Directional run age | Direction | 45 | reject |
| PS-03 | Sign-transition entropy | Direction | 38 | reject |
| PS-04 | Path turning intensity | Risk | 45 | reject |
| PS-05 | Jump concentration | Direction | 45 | reject |
| PS-06 | Return scaling across observation lengths | Magnitude | 39 | reject |
| PS-07 | Volatility memory | Magnitude | 43 | reject |
| PS-08 | Session-phase activity surprise | Magnitude | 27 | reject |
| PS-09 | Session-initial-range utilisation | Magnitude | 14 | revise |
| PS-10 | Between-bar versus within-bar move share | Risk | 20 | revise |
| TR-01 | Cross-timeframe direction agreement | Direction | 45 | reject |
| TR-02 | HTF trend with an LTF pullback | Direction | 45 | reject |
| TR-03 | Directional trend-strength acceleration | Direction | 39 | reject |
| TR-04 | Multi-scale trend breadth | Direction | 24 | reject |
| TR-05 | Trend age versus trend quality | Direction | 45 | reject |
| TR-06 | Pressure against confirmed HTF structure | Risk | 34 | reject |
| TR-07 | Trend curvature | Direction | 45 | reject |
| TR-08 | Timeframe agreement breakdown | Risk | 34 | reject |
| TR-09 | Higher-timeframe range migration | Direction | 37 | reject |
| TR-10 | Trend quality mismatch across timeframes | Direction | 38 | reject |

## Code and correctness improvements

The implementation is additive:

- `library/catalogue.py`: robust median/MAD stretch, trailing log-regression
  residuals and finite capped state.
- `pipeline/catalogue_features.py`: first ten ideas, explicit hourly source
  times/freshness, candle controls, variance and path features.
- `pipeline/catalogue_extended.py`: the remaining forty, calibrated event
  lifecycles, session history, exact-time peer models and confirmed structure.
- `strategy/catalogue_research.py`: covariate-only common-support fitting,
  non-overlapping samples, matched effects and memory-bounded paired bootstrap.
- `scripts/research_catalogue.py`: five fixed protocols, source/prior archives,
  protected-data bounds, no-overwrite attempts and cumulative trial accounting.
- `scripts/verify_catalogue.py`: independent fit/sample/effect/decision audit
  and complete deterministic replays.

Review found and corrected concrete issues before their affected runs:

1. Stable boolean context-completeness dtype, including a source prefix with
   no hourly observations yet; explicit UTC/nanosecond joins across timezones.
2. Mother-bar containment window indexing and ATR normalization of HTF
   structural distance using HTF ATR.
3. Old-reference first revisits evaluated before same-bar new pivot updates;
   ambiguous simultaneous candidates have no invented direction.
4. A closure-sensitive PS-10 control that actually retains observed closure
   displacement, instead of filtering it through a contiguous-only control.
5. Correct local-date DST session anchors in the shared pipeline helper.

The DST defect was reproduced using synthetic timestamps around both 2024
New York transitions. The old grouping introduced an extra UTC-midnight
boundary; spring session IDs could even move backwards. The corrected helper
has the proper local-anchor boundaries. See the
[before/after audit](../research/indicators/CATALOGUE-50-20261031/session_dst_audit.json).
**Existing stored Gold VWAP was not rebuilt.** New session research computes
its own corrected reference; future default data builds use the corrected
helper and must be versioned. Historical stored VWAP needs an audited rebuild
before claiming that its old DST values have been corrected.

## Three review passes and validation evidence

This is sequential self-review, not three independent people reviewing the
work.

1. **Implementation/formula review:** declared all fifty IDs and targets;
   tested independent median/lstsq, variance, path, peer, calendar and event
   examples, zero scales, gap rewarm, timezone handling, prefix invariance and
   fixed-calibration future perturbations. Fixed the issues described above.
2. **Independent numerical review:** reconstructed training cuts, common
   strata, weights, sample thinning/purging, all **2,250 matched primary
   effects**, costs and **50 final decisions** from archived inputs. Also
   checked **3,000 direct forward-label calculations** and **15 real-data
   prefix pairs**, and independently recomputed the 4,410-test adjustment.
3. **Replay/regression recap:** all five full studies were replayed. All
   **45 result/protocol files** and **48 source/derived Parquets** were
   byte-identical. Later batches have identical source snapshots. Batch 1's
   two documented source-context differences concern the not-yet-run PS-10
   control and later calibration-date metadata; its active protocol, numerical
   results and all data files remain identical.

The full suite passed **734 tests**; registry mutation checks passed **40/40**.
The existing strategy checker has **0 failures** and the same **22 X15
family-saturation warnings**. Compilation, whitespace and documentation links
were checked. Evidence is saved beside the progress registry.

The OOS ledger remains unchanged:
`3148000cf7f66bc564211610f3423571c484e6eae979963577a3ba6a48236cd6`.
Existing Gold files, strategy results and statuses were not changed. The code
change to session grouping is recorded separately from those frozen data
artifacts. No OOS token or protected market rows were used.

## Reproduction and artifacts

Aggregate evidence:
[CATALOGUE-50-20261031](../research/indicators/CATALOGUE-50-20261031/).
Individual attempts are `research/indicators/IR-20261031-CATALOGUE-B1-v1/`
through `...-B5-v1/`; derived data is under the existing ignored
`data/indicator_research/` tree. Every attempt retains its source and prior
comparison snapshots, training fits, calibration dates, coverage, matched
cells, raw summaries, p-values and interim/final q-values.

To replay one batch, use fresh destinations and its matching config:

```bash
OPENBLAS_NUM_THREADS=1 .venv/bin/python scripts/research_catalogue.py \
  --config config/indicator_catalogue_batch1.yml \
  --out /tmp/catalogue-replay/IR-20261031-CATALOGUE-B1-v1 \
  --data-out /tmp/catalogue-replay-data/IR-20261031-CATALOGUE-B1-v1
```

Repeat for batches 2–5 with their config/name. Their fixed prior references
use the retained original earlier-batch comparisons. With all replays present:

```bash
OPENBLAS_NUM_THREADS=1 .venv/bin/python scripts/verify_catalogue.py \
  --replay-root /tmp/catalogue-replay --out /tmp/catalogue-audit.json
.venv/bin/python -m pytest tests/ -q
.venv/bin/python scripts/test_check_results.py
.venv/bin/python scripts/check_results.py --json
```

These commands require the existing local data and pinned environment.
No network is needed. Existing output paths are deliberately refused.

## What the next move should be

Keep the tested feature library and the reproducible evidence. Do not turn
the fifty outputs into a large strategy sweep based on these findings.

The most specific follow-up is an explicitly registered **EUR_USD movement-
context** study for PS-08, compared with richer activity/session controls and
an unused evaluation period under the project's governance. CB-09 is another
magnitude-context question with incomplete replication. Neither is presently
a retained directional alpha.

For the seven revisions, first address the measured obstacle: actual session
coverage, rare event populations, collapsed discrete tails, or lack of
overlapping control strata. Preserve those revised definitions as new trials.
Further combinations, execution rules, real costs and portfolio behavior
require their own study. Three assets, reused development history, coarse
matching, approximate block-bootstrap inference and incomplete observed paths
remain material limits of this result.
