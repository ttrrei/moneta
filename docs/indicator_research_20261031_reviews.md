# Indicator research: three review passes

Date: 2026-10-31. This is a record of sequential self-review, not three
independent reviewers. Brief: [Draft 1](idicator_reasearch.md).
Definitions: [P1 spec](indicator_research_P1_spec.md).
Findings: [final research report](indicator_research_20261031_report.md).

## Pass 1 — implement, validate, run the fixed P1 grid

Read the project architecture, feature engine/library, Gold data contract,
evaluation windows and protected-data gate before implementing the brief's P1
scope. Inspected the current branch rather than relying on legacy column lists.
The inventory discovered 305 5m and 270 1h columns and their actual producers.
Reused wick/CLV, the three ATR ratios, ATR-24 and prior Donchian-24 boundaries.
Added a separate feature stage so the original Gold tables and strategy
semantics stay intact.

Resolved these issues before empirical outcomes:

| Finding | Correction and evidence |
|---|---|
| A swing's pivot time precedes its observability | Emit only at `pivot+right`; retain separate pivot/open and confirmation/close timestamps. Hand example, tie handling and brute-force oracle tests. |
| A current-bar Donchian range can absorb the breakout | Shift source boundaries by one bar, then freeze both at breakout. Moving-boundary hand fixture. |
| A new pivot can change the very reference being tested | Cross the level known before this bar updates pivot state. Prior-reference hand fixture. |
| Event labels can accidentally repaint earlier breakout rows | Emit only on the later retest/re-entry confirmation; one confirmation per episode. Prefix and future-perturbation checks. |
| Rolling percentile tie conventions are ambiguous | Explicit `<=` empirical CDF, including current ATR; independent brute-force parity including flat/zero ATR. |
| A slice can retain labels extending into the next period | Require label exit before the slice end. Next-open/exit indexing and split-boundary tests. |
| Holding-period excursion omitted a gap into the exit fill | Include exit opening price, exclude exit bar's later range. Added favorable/adverse fill-boundary checks. |
| Prefix-based inventory guessed the wrong producer for some columns | Discover actual outputs from each named feature group on a synthetic test fixture. Full 575-column inventory succeeds. |
| Training/distribution cohorts could include signal rows excluded by outcome analysis | Use the same complete-bar, non-gap signal quality rule for calibration and descriptive coverage. |

The v1 protocol and source hashes were frozen locally before outcomes. The
complete run analyzed 1,321,587 source bars and wrote all 2,160 comparisons,
5,760 conditional group summaries and 432 distribution records. Nothing was
selected out of the results because it looked unpromising.

## Pass 2 — challenge semantics, coverage and inference; fill gaps

Added directional-reflection tests covering high/low, HH/LL, LH/HL, breaks,
strengths, retests, re-entries and failures. Added exact age-6/age-7 event
boundaries, age-120 level expiry, partial-bar episode resets and NaN ATR
recovery. Strengthened the split-purge test: convert Pandas timestamps explicitly
to nanoseconds, require a nonempty audited cohort, and compare actual baseline
counts against a separate direct-index calculation.

Re-examined hourly missingness. Its high structural null rates follow the
declared reset-and-rewarm semantics: daily session gaps and partial candles
frequently interrupt the required contiguous pivot window. Unknown structure
must remain unknown. These results do not justify silently relaxing the rule
after seeing outcomes; a session-aware variant needs a separately frozen
future definition.

Found and corrected a material **Monte Carlo precision gap**. With 1,999
resamples, minimum attainable `p=1/2000`; the isolated-test BY bound over 2,160
comparisons is greater than one. That precision cannot resolve an isolated
discovery at `q<=0.10`. Preserved v1 and its verified source files. Increased
only resample count to 199,999 in v2; minimum `p=1/200000` gives an isolated
adjusted value about 0.0892. Added a regression test enforcing that resolution
condition. This is a disclosed numerical refinement after v1, not a claim
that the v2 protocol was fully frozen before any outcomes were seen.

The feature definitions, economic hypotheses, assets, timeframes, horizons,
split dates, bucket fits, bootstrap block length, fixed seed and acceptance
thresholds did not change. v2 sources are archived automatically at startup.
The runner refuses to overwrite an existing attempt. v1, including its more
coarse statistical results, remains available for inspection.

Also corrected the new specification's ATR-ratio description: the original
pipeline maps a zero slow ATR to NaN; EPS applies to wick range normalization,
not to that ratio. Clarified that short research labels are cash P&L per entry
notional and differ from the engine's reciprocal short-return convention.
Partial future candles can understate tick-path excursions; both partial-path
and gap-path rates accompany the observed-bar labels.

## Pass 3 — reproducibility, independent audit and recap

The first run's complete development replay was byte-identical for seven
result/protocol files and all six derived Parquets. A real-data audit checked
3,000 direct forward-return/excursion calculations, 1,200 independent ATR-rank
calculations, exact training cutpoints, pivot availability, real-prefix
causality, costs, full comparison-grid coverage and an independent BY formula.
That v1 audit is retained with its original run. The final v2 audit passed the
same checks at the corrected numerical precision: all seven result/protocol
files and all six derived Parquets were byte-identical in the complete replay.
The v1-to-v2 refinement audit separately confirms unchanged economic settings,
data, feature values, sample counts, fitted buckets and point estimates.

Final regression results: 700 tests passed (30 new focused tests), 40/40
registry mutation cases passed, zero existing-strategy checker failures,
and the same 22 X15 saturation warnings. Compile and whitespace checks passed;
all new documentation links resolved. The ledger hash agrees with both run
manifests. No protected-data authorization was requested or consumed.

The final machine-readable evidence and exact test counts are linked from the
[research report](indicator_research_20261031_report.md). Original strategy
results, statuses and OOS ledger are checked separately from the new study.
Source hashes and filtered development-frame hashes record what was computed;
they are not claims that the entire large source Parquets were hashed or that
their protected partitions were inspected.

Remaining scientific limits are explicit: three assets, reused development
periods, no matched event controls, observed-bar horizons with session gaps,
partial future candles, approximate block-bootstrap inference, finite Monte
Carlo resolution, and no executable strategy/financing/slippage simulation.
They constrain interpretation; they are not filled with invented prices or
post-result parameter searches. P2/P3 remain future work under the brief.
