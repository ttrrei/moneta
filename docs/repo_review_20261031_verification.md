# Verification of repo_review_20261031_initial.md

The engineering findings are mostly correct and have been addressed. The file
also combines two reviews with a proposed master plan; several of that plan's
numerical interpretations and recommendations remain incorrect. Proposed owner
decisions in its tables are not evidence that the owner adopted those policies.

Baseline: `cc63ac0`. Local baseline validation reproduced 652 passing tests;
the results checker passed with 22 warnings. Remote CI success was not verified.

## Confirmed findings and changes

| Finding | Verification and implemented behavior |
|---|---|
| Date-only development `until` cuts off the final day | Confirmed. `oos_token.query_until()` now resolves a development date to the following UTC midnight with `<`. Explicit datetime bounds remain exact inclusive instants. OOS dates retain exclusive ends. `normalize_bound()` continues to map dates to midnight. The shared loader, RSI loader and fingerprint use the same resolution. |
| S-01 bypasses the scoped cache | Confirmed. Its loader delegates to the shared data loader; the RSI rule and accounting remain separate, with fresh state per run. A regression proves cache hits and distinct cache keys for inclusive/exclusive bounds. |
| Parameters alone do not freeze an implementation | Confirmed. Nomination now prints and OOS verifies `oos_code_commit`, `oos_code_hash`, `oos_dirty: false` and an opaque full-file SHA-256/size `oos_data_fingerprint`, alongside the existing variant/configuration pins. Missing freeze metadata fails checker X16. |
| Historical performance needs replay after signal repairs | Confirmed and completed for every existing S-18/S-33/S-37/S-39 variant: 540 cells in a separate artifact directory. Original code at `936f7b9` and the old midnight bound first reproduced all 180 original 2-bps cells. See the [replay report](../strategy/recomputations/20261031/README.md). |
| Missing-data gate repairs may affect other historical cells | Checked on local development data. Price/EMA inputs are finite for all three evaluation instruments on both timeframes; S-17's ADX/Supertrend inputs are also finite. BTC has twelve null band-position values on each timeframe, which S-08's loader already excludes. These gate repairs therefore do not require additional historical gate-only replays on this snapshot. |
| Gross-versus-net attribution should be explicit | Implemented paired zero/two-bps diagnostics in `audit_research.py`, with [per-cell evidence](research_cost_diagnostics_20261031.csv) and an additive summary in the [existing audit](research_audit_20261031.json). Identical repeated rows are deduplicated; conflicting rows fail. |
| OOS pass calculation is not fully fail-closed | Confirmed independently of policy floors. Required missing/non-finite values, duplicate cells and incomplete matrices now yield `pass=False` and an invalid-data finding; the checker rejects them. A missing/NaN trade frequency can no longer silently avoid the ceiling. Existing numerical pass thresholds were retained. |
| Twenty-two warnings need inspection | All twenty-two are X15 saturation reminders. They remain visible and their thresholds were retained. The English review's assertion of twelve current warnings is stale. |

### Implementation and data freeze

The implementation digest covers tracked Python under `strategy/`, `pipeline/`
and `library/`, the indicator specification, and parsed evaluation configuration.
Only nomination metadata is excluded from the configuration digest, so changing
windows or criteria invalidates the freeze. Feature-file hashes cover all bytes,
including feature columns, without decoding prices or evaluating the holdout.

Nomination and OOS require a clean Git working tree. The pinned implementation
commit must be an ancestor of HEAD and its implementation digest must match.
This allows a subsequent commit containing nomination metadata, avoiding the
self-reference problem of requiring a commit to contain its own SHA. OOS checks
the data fingerprint and rechecks source/file identity after preflight, before
reservation. Development runs may still disclose a dirty working tree.

`scripts/pin_finalist.py` changes no files or statuses. Because full-file data
hashes are computed, it may take time on the large local feature tables. No
nomination was created and no OOS execution occurred during this work. All freeze
tests use isolated Git repositories and synthetic file bytes.

## Corrected statistical interpretation

The proposed gross/net partition reproduces exactly on the committed data:

| Group description | Groups |
|---|---:|
| Two or more net benchmark wins | 10 |
| One net benchmark win | 62 |
| Empty signal | 15 |
| At least one gross benchmark win, with no net benchmark win at 2 bps | 374 |
| Some positive gross return, with no net benchmark wins | 1,062 |
| No positive gross return | 77 |

These categories cover all 1,600 groups, including the winning groups. They do
not establish beta exposure, statistical skill or that a strategy is usable.

The review incorrectly describes the 1,062-group bucket as “made money” after
costs. **583 of those groups have no positive net return on any instrument**;
only 479 have at least one positive net-return cell. Likewise, “only 77 were
genuinely bad” is unsupported. The 374 groups demonstrate a benchmark edge lost
between the tested cost tiers; only 354 also belong to the earlier high-frequency
bucket. The review's “374 of 1,294 frequency-blamed groups” is incorrect.

The audit additionally finds 446 individual cells whose gross benchmark edge
is erased at 2 bps, and 2,048 cells whose positive gross return becomes
nonpositive. Transaction costs can matter even when a strategy never beat the
benchmark before costs. These are rounded historical transaction-cost
sensitivities, without financing or an estimate of live execution quality.

For `s109/ema_gate` on BTC/full, the committed **net return is +891.86%** and
buy-and-hold is **+1,538.05%**. The **−646.19 percentage-point edge** is a
benchmark shortfall, not a 646% investment loss. The corresponding gross return
is +929.87%, so the tested transaction-cost drag is 38.01 percentage points.
The review's claim that a margin floor fixes a catastrophic BTC loss is based
on misreading this quantity.

## Recommendations that were not adopted

| Proposal | Assessment |
|---|---|
| Automatically add ten-trade, 20%-exposure and five-point-edge floors | These are proposed research policies, not bug fixes or statistical guarantees. A one-trade near-buy-and-hold strategy already has high exposure, so the exposure floor does not solve that example. Fixed total-return margins also depend on window length. Current thresholds remain unchanged. |
| Retroactively relabel old results under a new yardstick | Preserve their original criteria and evidence; assess any future criterion separately and register it before new experiments. No finalist promotion or historical status change was made. |
| Declare 39 families “provably dead” and close sixteen by fiat | Correlated variants and overlapping windows do not prove a whole economic hypothesis is dead. The first-alphabetical-indicator mapping also misclassifies composites. No family ban or taxonomy was installed. |
| One fixed rule per ID eliminates selection bias | Selecting among multiple fixed rules still creates multiple testing. Prefix-invariance fixtures cover their inputs and sampled scenarios, not all market states or the full feature pipeline. |
| Inspect holdout buy-and-hold to choose whether to nominate S-55 (§6.6) | Rejected: selection would depend on the protected outcome. Baseline inspection can contaminate the holdout. A large bullish benchmark does not automatically make a long-only strategy beat that benchmark. |
| Dollar-neutral relative value needs only a new benchmark | A synchronized calendar, capital/turnover accounting, currency exposures and financing are still required; dollar neutrality does not guarantee beta neutrality. |
| Volatility sizing is a small UNIT_SIZE change | That constant cancels from legacy returns. Fractional allocation needs a separate accounting contract, including the legacy reciprocal-short convention. |
| A one-bar shifted weekday is a decisive placebo | Intraday adjacent bars usually have the same weekday. A meaningful predeclared null needs to change the calendar assignment and preserve appropriate serial dependence. |
| Delete the 1,080 overlapping sweep rows | They are identical repeats already deduplicated by the audit. Preserving the source artifacts retains batch provenance; there is no counting defect to fix by deletion. |
| Run a new class-I batch now | This request concerns verification and repairs. No new strategy search was started; portfolio prerequisites and an adopted experiment contract are still needed. |

The baseline had 132 actual trial rows and 652 tests, not 133 actual rows or
493 tests. Assertions about exact legacy execution times and remote CI require
evidence beyond filenames, commit timestamps or the review's prose.

## Replay results and limits

The replay evaluates the existing grids at 0/2/5 bps, with original numbers
preserved. It reports metric deltas and added/removed entry/exit records at
2 bps. The latest code includes both the signal repairs and full-final-day
development windows, so deltas combine those changes. Original source and the
old window were reproduced first to validate the comparison.

All 540 cells change at least one metric because extending the final day also
changes the benchmark and window span. S-18 has materially larger differences
from its ATR correction. None of the four strategies acquires a configuration
with benchmark wins on two instruments in both windows. Their historical
rejected statuses remain appropriate under the existing cross-market rule.

For other strategies, the old artifacts remain evidence of their original
window semantics. They are not silently rewritten or presented as full-day-v2
results. New matrix manifests record `utc-full-day-date-until-v2` explicitly.
Source/data bytes must be frozen and the nominated configuration reproduced
under current semantics before any future finalist nomination.

The separate replay manifest records the source revision, dirty development
state, implementation digests, original CSV digests and actual UTC run times.
Additional opaque file hashes in `input_provenance.yml` were explicitly recorded
**after** the replay; they are not represented as pre-run captures.

## Validation

Regression coverage includes complete final-day inclusion in both loaders and
fingerprints, exact offset-aware timestamps, unchanged exclusive OOS ends,
single-day windows, S-01 cache reuse and operator-sensitive cache keys,
implementation/data/configuration changes, dirty-tree refusal, nomination
metadata commits, invalid OOS matrices and paired cost diagnostics. The replay's
immutable decisions are tested against fresh rules at each cost tier.

Final local verification: **670 pytest tests passed, 40/40 checker mutation
cases passed, and the results checker passed with zero failures and 22 X15
saturation warnings**. All Python entry points compiled. Remote CI is not represented as verified. The
original result files, criteria values, strategy statuses and real holdout
ledger are preserved. Ledger SHA-256 remains
`3148000cf7f66bc564211610f3423571c484e6eae979963577a3ba6a48236cd6`.
