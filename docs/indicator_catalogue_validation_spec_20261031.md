# Fifty-idea catalogue: implementation and validation contract

Date: 2026-10-31. Catalogue:
[50 hypotheses](indicator_idea_catalogue_20261031.md).
Measured outcomes: [implementation report](indicator_catalogue_results_20261031.md).
Machine plan: [indicator_catalogue_plan.yml](../config/indicator_catalogue_plan.yml).

## Scope and stages

All 50 ideas are implemented in additive research stages. Each has one primary
comparison per asset, development slice and horizon. Signals use **5m bars**;
completed **1h bars provide context**, rather than a second set of outcomes.
This tests one operational version of each idea, not every possible variant
or parameter combination. The default 305/270-column Gold tables are unchanged.

| Batch | Trend | Mean reversion | Compression / breakout | Candle / structure | Persistence / session |
|---|---|---|---|---|---|
| 1 | TR-01, TR-02 | MR-01, MR-02 | CB-01, CB-07 | PA-02, PA-09 | PS-01, PS-05 |
| 2 | TR-03, TR-04 | MR-03, MR-04 | CB-02, CB-03 | PA-01, PA-03 | PS-02, PS-03 |
| 3 | TR-05, TR-07 | MR-05, MR-07 | CB-04, CB-05 | PA-04, PA-05 | PS-04, PS-06 |
| 4 | TR-08, TR-09 | MR-08, MR-09 | CB-06, CB-08 | PA-06, PA-07 | PS-07, PS-08 |
| 5 | TR-06, TR-10 | MR-06, MR-10 | CB-09, CB-10 | PA-08, PA-10 | PS-09, PS-10 |

Each batch's YAML fixes the score, control, outcome target, direction, tail or
event comparison and expected sign. The implementation registry in the final
results records those fields for every idea. The code is authoritative for
exact arithmetic; this contract explains its evaluation semantics.

Assets: EUR_USD, XAU_USD, BTC_USD. MR-06 additionally uses the fixed peers
GBP_USD, XAG_USD and ETH_USD, respectively. Assets are loaded separately through
the existing data gate. No price is imputed or forward-filled. Peer prices join
on exact timestamps; missing or incomplete peer observations invalidate the
corresponding return/model window.

## Timing and data quality

`time` is bar open. Signals become available at bar close; entry is the next
clock-adjacent observed open, with exit after 6/12/24/60/120 observed bars.
The study reuses the existing `forward_labels` function, including the exit
opening fill in MFE/MAE but excluding the exit bar's later high/low. Future
session gaps and partial candles remain in descriptive labels, with their
elapsed duration and incidence reported. Partial bars can miss true intrabar
extremes; these are observed-bar labels rather than full tick-path guarantees.

New rolling features require contiguous complete input observations and
rewarm after interruptions. ATR/EMA and other reused Gold inputs retain their
existing causal initialization. The first 258 source rows are excluded from
analysis. Longer intrinsic warm-up, six-session history, unavailable pivots,
zero scales and missing peers remain null. Undefined is different from a
defined zero or a non-occurring event.

HTF changes are computed on native hourly rows. Join on completed close time
and require a complete source bar with age in `[0,3600)` seconds. Source close,
age and completeness accompany the outputs. The original strict structural
gap-reset policy is retained, including on hourly pivots. This deliberately
exposes low coverage instead of assuming an unverified market calendar.

## Calendar and event refinements

These choices make the catalogue's sketches operational and are recorded in
code/source snapshots before the corresponding batch outcomes:

- **DST/session anchors:** the latest anchor is selected by its local calendar
  date and then localized. Reusing midnight's offset or subtracting 24 UTC
  hours on a transition date is incorrect. `session_anchor_ns` now supplies
  both the pipeline's session grouping and new research features. New research
  VWAP uses observed typical price times tick activity under these corrected
  groups. Existing stored Gold VWAP has not been silently replaced or rebuilt.
- **Session coverage:** the first observed session bar must be within 120
  minutes of the configured anchor for displacement/initial-range episodes.
  This is a declared coverage tolerance, not an assertion about exchange open
  times. Delay is retained. PS-09 waits for six contiguous complete initial
  bars. PS-08 uses the preceding six observed sessions at the same elapsed
  slot, requiring all six historical slot observations; no empty session or
  missing slot is synthesized.
- **Session VWAP:** weights actual observed typical prices by reported tick
  activity, including observed partial candles. It is not exchange-volume
  VWAP. Missing observations cannot reveal the unobserved session path.
- **PA-09 ambiguity:** bars contacting both range edges have no unique
  direction and form an explicit excluded ambiguity stratum. Controls are
  one-sided ordinary contacts within 0.25 ATR of a prior range edge; treatment
  penetrates that edge and closes back inside.
- **PA-03 containment:** raw mother-bar releases are retained. The primary
  controlled comparison uses releases that also make a fresh Donchian-24
  close break, versus ordinary Donchian breaks. Thus the primary estimate is
  about this specified subset, not every possible containment release.
- **CB-03 compression:** low BB width uses its training 20th percentile.
  Freeze the preceding range on entry into that state; confirm a later
  release within six bars. The controlled primary cohort compares qualifying
  releases that also make the ordinary range break with other range breaks.
- **PA-06 first revisit:** evaluate a previously known level before applying
  a new confirmation on the same bar. Early zone contacts mark the level as
  visited, so a later contact cannot claim freshness. After six bars, compare
  a first contact within 0.25 confirmation ATR with an ordinary near approach
  within one confirmation ATR. Ambiguous simultaneous candidates remain null.
- **MR-07 and CB-04:** shock decay and breakout acceptance are emitted only
  after six subsequent observations. Pending episodes reset at interruptions;
  event information is never written on the original trigger bar.
- **MR-10:** freeze the preceding EMA, observe six closes on one side, and
  then allow six later bars for a confirmed reclaim. Compare actual reclaim
  with still-pending observations at comparable episode age. One active mean
  episode is used; it does not retrospectively label all overlapping blocks.
- **MR-06:** each current residual uses a regression fitted on the preceding
  60 synchronized returns, excluding that current return. Sum six already
  observed residuals and normalize by the current preceding-window fitted
  residual scale times `sqrt(6)`.
- **PS-10:** between-bar returns intentionally include observed displacement
  across real closures. Its control is explicitly the observed-return
  variance, including that known displacement. Using the ordinary contiguous
  variance control would accidentally discard the very closure periods this
  idea is meant to study. This was corrected before batch 5 outcomes.

Training covariate thresholds for compression, shock size, RSI extremes and
CLV extremes are fitted once per instrument. The stored calibration names
its training dates. Training features using these fitted constants are
retrospective diagnostics; those constants become usable for validation only
after training ends. Causality checks hold calibration fixed while truncating
or perturbing later observations. No outcome is used to fit a feature cut.

## Primary outcomes and comparison populations

There are three declared outcomes:

| Target | Units and definition | Permitted interpretation |
|---|---|---|
| `directed_return` | `direction * gross_next_open_return_bps` | Conditional continuation/reversal evidence |
| `absolute_return` | Absolute gross next-open return, bps | Movement-magnitude context |
| `adverse_excursion` | Against the declared direction: `-long_MAE` or `long_MFE`, bps | Direction-conditioned risk context |

For tail comparisons, fit the score's training 20th/80th percentiles and
compare high versus low tails. The specified absolute transforms apply before
fitting. Ties may collapse the contrast; a constant score is unidentifiable.
For categorical comparisons, treatment is 1 and control is 0 within the
explicit eligible event population. Null/non-candidate rows are not controls.

Match approximately on each idea's declared control using training terciles;
TR-01 uses the exact LTF direction categories instead. Retain strata with at
least 30 **training covariate observations** in each arm, and require those
strata to cover at least 50% of the training candidate population. Freeze their
weights proportional to their combined training candidate counts. Neither
strata nor weights use forward labels. Estimates concern this common-support
population; coarse matching does not remove every confounder or establish a
causal effect.

During each slice/horizon, require at least 30 retained samples and 8 active
weeks in each arm, plus at least 10 samples in every retained arm/stratum cell.
Continuous comparisons use a fixed horizon grid anchored to the slice's first
eligible signal row. Event comparisons greedily thin the union of treatment
and control candidates, without preferring either arm. Holdings do not overlap.
All label exits must precede the slice end. A missing cell invalidates
inference; weights are never refitted to whichever cells survived validation.

The primary effect is the training-weighted average of within-stratum
treatment-minus-control mean target differences. Group artifacts also retain
unweighted raw/target distributions, quantiles, cost scenarios and path quality.
Do not confuse an unweighted descriptive mean with the matched estimate.

## Uncertainty, accumulated trials and decisions

Training: `[2020-01-01,2023-01-01)`; validation 1:
`[2023-01-01,2025-01-01)`; validation 2:
`[2025-01-01,2025-08-01)`, all UTC. These periods were previously used in
development and are not fresh OOS evidence. The protected holdout was not used.

Use 499,999 paired circular four-calendar-week bootstrap resamples per
asset/slice, including empty weeks, fixed seed 20261031. All arm/stratum cells
share those blocks. A resample with a missing retained cell stays invalid;
require at least 90% finite paired effects. CIs are pointwise percentile 95%
intervals. P-values use the existing centered two-sided bootstrap and finite
Monte Carlo +1 correction. The chunked constructor is tested byte for byte
against the existing bootstrap design. This remains approximate inference
under within-slice stability assumptions, not a guarantee of calibration.

The fixed family is **4,410 tests**: 2,160 recorded P1 comparisons plus
`50 ideas * 3 assets * 3 slices * 5 horizons = 2,250` catalogue comparisons.
Unsupported and not-yet-run tests have `p=1`; each batch does not reset the
trial budget. Final Benjamini–Yekutieli q-values use the complete family.
The new `1/500000` resolution can resolve an isolated `q<=0.10` finding in
this family. Older unrelated strategy searches are not retroactively brought
under a formal universal error guarantee by this correction.

An idea is retained only if the same horizon has supported comparisons in all
three slices on at least two assets, and both validation slices have a CI in
the declared direction and global `q<=0.10`. For explicitly neutral hypotheses,
orientation is set from training; other expected directions are fixed positive
in the YAML. `keep_research` permits further directional research;
`keep_context` permits further magnitude/risk research. Neither nominates a
strategy. `reject` means adequately covered but no replication; `revise` means
insufficient common support under this definition. Earlier batches' decisions
are interim until all fifty ideas have been included.

Cash costs at 0/2/5 bps one-way follow entry-notional simple P&L and fees on
both entry/exit notional, as in the P1 research labels. For raw return `r` bps,
long net is `r*(1-c/10000)-2c`; short net is `-r*(1+c/10000)-2c`.
For varying declared direction `d`, net is `mean(d*r)-c*mean(r)/10000-2c`.
These are descriptive labels, not compounded positions or engine backtests.
Magnitude/adverse-risk associations do not imply executable cash profits.

Numerical conventions: median stretch uses unscaled MAD; regression residual
RMS divides by 24; peer residual scale uses the preceding fitted population
variance; return variances use `ddof=0`; CB-09 rolling instability uses sample
standard deviation (`ddof=1`). PS-05 takes the earliest equally large jump;
sign-transition entropy is normalized by `log(3)`. PS-06's nested six-return
sums and 120-observation variance require 126 contiguous source price bars.

## Provenance and independent validation

Each attempt saves its protocol, source files, prior comparison files,
filtered source-frame hashes, source file metadata, derived files and all
results. Existing destinations are refused. Neither whole protected source
files nor protected partitions need to be read for an audit.

Batch 1 predates two source-context changes: the explicitly corrected PS-10
control in the later batch-5 protocol and additional training-date metadata
for later-batch calibrations. Its active protocol, numerical feature/statistic
modules, all outputs and all data files replay identically. These source
context differences are recorded by the audit rather than hidden by rewriting
the first manifest. Later batches have identical replay source hashes.

Quality gates include hand examples and independent NumPy/lstsq oracles,
prefix/future perturbation, native-hour timestamps, DST transitions, missing
peers, partial/gap rewarm, zero scales, bounded-state convergence and deterministic
replay. The final audit independently recomputes training fits, treatment/control
sample selection, purging, matched effects, costs, BY adjustment and all 50
decisions from archived development data.
