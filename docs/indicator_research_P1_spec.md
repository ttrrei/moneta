# P1 indicator definitions and fixed study protocol

Implementation date: 2026-10-31. Brief: [Indicator Research Draft 1](idicator_reasearch.md).
Protocol: [config/indicator_research.yml](../config/indicator_research.yml).
Results and limitations: [research report](indicator_research_20261031_report.md).

This is feature research. It does not generate strategies or change the shared
backtest engine. The original 305-column 5m and 270-column 1h Gold tables remain
unchanged. A separate additive stage writes development-only derived tables.

## Inventory and scope

The run inventories every physical Gold column, including dtype, timeframe and
actual producing feature group, in `existing_feature_inventory.csv`. Producer
names are discovered from the existing pipeline on synthetic fixtures; market
outcomes are not used for that inventory. Synthetic fixtures are for testing
only, never substituted for real research prices.

| ID | Family | Action and primary research outputs |
|---|---|---|
| MS-01 | Confirmed swing | New: `swing_high_confirmed`, `swing_low_confirmed`; level, age, pivot identity and confirmation-time auxiliaries |
| MS-02 | HH/HL/LH/LL | New: `structure_hh`, `structure_lh`, `structure_hl`, `structure_ll` |
| MS-03 | Structure break | New: `structure_break_up/down`, `structure_break_strength_up/down`; frozen reference levels |
| MS-04 | Breakout retest | New: `breakout_retest_up/down`; distance, age and original breakout identity |
| VR-01 | ATR percentile | New: `atr_percentile_60/120`, using existing `atr_24` |
| VR-02 | Volatility expansion | Reuse: `vol_ratio_6_24`, `vol_ratio_12_60`, `vol_ratio_24_120` |
| FR-01 | Wick rejection / close position | Reuse: `bar_upper_wick_ratio`, `bar_lower_wick_ratio`, `bar_clv` |
| FR-02 | Range re-entry | New: `range_reentry_from_above/below`; frozen range and breakout identity |
| FR-03 | Failed breakout | New: `failed_breakout_up/down`; failure age, excursion and re-entry distance |

There are 24 primary outputs: ten continuous and fourteen events. These are
outputs of nine families, not 24 independent economic hypotheses. P2 HTF/exit
research and P3 session/statistical research remain outside this first batch.

## Shared timing, validity and warm-up

`time` identifies the UTC bar **open**. All features become available at
`time + interval`; a decision can enter only at the following observed bar's
open. Numeric undefined values are NaN and undefined timestamps are NaT. A
defined event with no occurrence is zero. First-pivot comparisons, absent or
expired reference levels, invalid normalization and detector warm-up are
undefined; these are not silently converted to zero.

The additive stage accepts exactly one instrument with unique, ascending,
timezone-aware timestamps. Complete bars have `n_bars=5` or `60`. Nonfinite,
nonpositive or inconsistent OHLC, partial bars and timestamp discontinuities
reset structural state; their structural outputs are undefined. The first bar
after a timestamp discontinuity is also excluded from the swing detector.
Detection resumes after 6 left + 6 right contiguous complete observations.
Range/ATR inputs retain the existing pipeline's observed-row rolling semantics
across sessions; resetting an episode does not recompute the underlying ATR or
Donchian windows. No missing prices are imputed.

Swing levels expire at 120 observed bars after confirmation. Event episodes
also have finite lifetimes, which makes computation independent of an
arbitrarily distant initialization. Research excludes the first 258 source
rows as a conservative combined-state burn-in. Existing Gold ATR retains its
original recursive initialization; the additive stage does not reinitialize it.
ATR rank needs 60 or 120 finite ATR observations and can be unavailable again
after an invalid ATR input. The derived files retain these nulls.

## Formulas and event lifecycles

Let `H,L,C` be bar high, low and close, `A=atr_24`, and `t` the bar whose close
is now known. All integer indices refer to observed bars.

**MS-01.** With `left=right=6`, candidate `p=t-6` confirms a high if
`H[p] > max(H[p-6:p])` and `H[p] >= max(H[p+1:t+1])`; lows reverse the
inequalities. This selects the leftmost equal extreme. No event or level is
written on the earlier pivot row. Confirmation age is zero on row `t` and the
level expires before calculations when its age reaches 120. Pivot timestamps
and confirmation timestamps are separate columns; local row indices are
auxiliaries, not portable identities across sliced inputs.

**MS-02.** On a new high confirmation compare its price with the previous
unexpired confirmed high: `HH = new > previous`, `LH = new < previous`.
For lows: `HL = new > previous`, `LL = new < previous`. Equal prices set both
flags to zero. The first confirmation has no predecessor and is undefined for
that comparison. Non-confirmation rows after detector warm-up are zero.

**MS-03.** Freeze `U,D`, the unexpired high/low levels available before this
bar updates swing state. Up-break: `C[t] > U and C[t-1] <= U`; down-break:
`C[t] < D and C[t-1] >= D`. With positive finite ATR, continuous strengths are
`(C[t]-U)/A[t]` and `(D-C[t])/A[t]`; negative values mean price remains on the
unbroken side. Continuous strengths are defined wherever a reference exists,
not only on break events. New pivots confirmed on this bar cannot substitute
for the reference crossed on this bar.

**MS-04.** Arm an episode on an MS-03 break and freeze its direction, level
and ATR. A later up retest requires `abs(L[t]-level) <= 0.25*break_ATR` and
`C[t] > level`; a down retest uses `H[t]` and `C[t] < level`. Ages 1 through 6
are eligible, inclusively. Confirmation emits once; a new structural break
replaces the pending retest. A contact that closes on the wrong side does not
confirm. This definition requires the bar extreme itself to lie in the zone;
a deep penetration through the zone is not a successful retest.

**VR-01.** For `N=60,120`, empirical CDF rank
`sum(A[j] <= A[t], j=t-N+1..t)/N`, including the current closed bar. Ties use
the maximum rank. Constant finite ATR, including zero, has rank one; NaN ATR
invalidates any window containing it. This is an observed-row volatility
regime label, not a directional signal.

**VR-02.** Existing Wilder ATR fast/slow ratios with pairs `(6,24)`, `(12,60)`,
`(24,120)`. A zero slow ATR yields NaN; existing float32 serialization semantics remain
authoritative. These are reused verbatim rather than renamed or recalculated.

**FR-01.** Existing upper wick `(H-max(O,C))/(H-L)`, lower wick
`(min(O,C)-L)/(H-L)`, and close location `((C-L)-(H-C))/(H-L)`, with the existing
EPS guard. A zero-range candle maps to zero. The study uses continuous
training-fitted buckets; it does not add an optimized rejection threshold.

**FR-02.** `U[t]=dc_upper_24[t-1]`, `D[t]=dc_lower_24[t-1]`; the existing
Donchian columns include their own current bar, so the shift is essential.
Arm on a fresh close crossing (`C[t]>U[t], C[t-1]<=U[t]`, or the inverse for
`D`). Freeze both bounds, breakout index and positive ATR at that moment.
Emit at the first later close inside the **original** `[D,U]`, with age
strictly less than 120. Moving range edges cannot manufacture re-entry.
Ignore same-direction fresh crossings while pending; a fresh opposite crossing
replaces the episode. Reset, expiry or confirmation clears it. Overshooting
past the opposite frozen boundary does not count as an inside close.

**FR-03.** A confirmed FR-02 return is a failed breakout if its age is 1..6.
No retrospective flag is added to the breakout bar. Failure excursion is the
maximum breakout-side high/low displacement from its frozen boundary, including
the failure bar, divided by breakout ATR. Re-entry distance is displacement
inside the original boundary divided by that same ATR. Late re-entries remain
FR-02 events and have no FR-03 age/excursion auxiliaries.

## Fixed empirical protocol

The v1 hypothesis/protocol/source hashes were recorded **before** reading
outcomes. Review 2 increased bootstrap precision from 1,999 to 199,999 in v2
after seeing v1, without changing the hypothesis grid, features, buckets,
splits, block length or promotion thresholds. Both attempts are retained with
their source snapshots; v2 is the final numerical analysis. This is a local
freeze and disclosed numerical refinement, not external preregistration.
Date ranges are half-open UTC
intervals applied to decision close and label exit:

| Slice | Start inclusive | End exclusive | Role |
|---|---|---|---|
| train | 2020-01-01 | 2023-01-01 | Fit feature bucket cutpoints; orient continuous contrasts |
| validation_1 | 2023-01-01 | 2025-01-01 | First development validation |
| validation_2 | 2025-01-01 | 2025-08-01 | Later development validation |

Protected holdout starts 2025-08-01. The existing gated loader enforces a
precise inclusive upper instant immediately before that boundary. No protected
rows or OOS token are used. These development periods have previously been
used by other strategy work: they are not fresh independent OOS evidence.

Assets are EUR_USD (FX), XAU_USD (metal), BTC_USD (crypto), each on 5m and 1h.
Horizons are 6/12/24/60/120 **observed** bars. Entry `O[t+1]`, exit
`O[t+1+h]`; gross long return is `10,000*(exit/entry-1)` bps. Entry must be
clock-adjacent to the signal. Later gaps remain in the return; elapsed hours
and the fraction of paths with gaps or partial bars are recorded. MFE/MAE use
high/low in held bars plus the exit opening fill, excluding the exit bar's
subsequent high/low. Short cash returns/excursions mirror long simple returns.
Labels crossing a slice's end are purged. No price or label is forward-filled.
Partial future bars can miss intrabar extremes: these are observed-bar
excursions, not a guarantee of the full tick path's actual MFE/MAE.

Continuous cutpoints are the finite training 20/40/60/80 percentiles; ties
collapse duplicate edges, so bucket counts can be smaller than five. They are
frozen for both validation slices. A constant feature has no valid top-minus-
bottom contrast. The comparison is high bucket minus low bucket on a fixed
non-overlapping horizon grid independent of feature values. Rank IC is a
descriptive Spearman statistic without a separate significance test.

Events have fixed directions in the protocol. Their occurrences are greedily
thinned to non-overlapping holdings. Compare their directional mean return
with an unconditional mean on the same split's fixed non-overlapping grid.
This is a regime association, not a matched causal experiment: intraday timing
and other market states can confound it. Baseline means/counts accompany every
comparison. All bucket/event groups report sample count, active weeks,
mean/median/std/quantiles, positive rates, excursions and path-quality rates.

Uncertainty uses 199,999 deterministic paired circular moving-block resamples of
four consecutive UTC calendar weeks. Empty weeks are retained. There must be
at least 30 samples and 8 active weeks per comparison arm. CIs are pointwise
95% percentile intervals; p-values use a two-sided centered bootstrap with a
finite Monte Carlo +1 correction. Fewer than 90% finite resamples invalidates
inference. Block bootstrap is approximate and assumes sufficient stability
within each split; sparse events have limited power.

All `24*3*2*5*3 = 2,160` planned tests, including training and unsupported
comparisons (assigned `p=1`), enter one Benjamini–Yekutieli adjustment. The
1/200000 p-value resolution can resolve an isolated `q<=0.10` discovery in this
family (the initial 1/2000 resolution could not). Dependence correction and
finite Monte Carlo precision still limit detection. A
failure to pass is not proof that a feature has no information. No unadjusted
winner is promoted after inspecting this study.

Cash P&L labels report 0/2/5 bps one-way costs on entry **and exit notional**.
For gross return `r` bps and cost `c` bps, long net is
`r*(1-c/10000)-2*c`; short net is `-r*(1+c/10000)-2*c`. No financing, spread
model, slippage, compounding, sizing or executable strategy is simulated.
These short labels use entry-notional cash P&L; the existing engine's reciprocal
short convention is different. Bucket spreads are not funded portfolio P&L.

## Decisions and promotion limits

`keep` requires the same timeframe/horizon to replicate across at least two
assets in both validation slices: both arms supported in all three slices,
validation pointwise CI in the training-oriented direction, and global
`q<=0.10` in each validation slice. Event direction is fixed in the protocol;
continuous direction is fixed from training. `reject` means sufficient common
coverage but no such replication in this study; `revise` means insufficient
support. These decisions apply to tested output definitions and the stated
promotion criterion, not universal usefulness. `keep` would permit further
research only; cost viability and a separately governed strategy study would
still be required before strategy generation or OOS use.

Quality gates are formula/hand examples, warm-up and finite context,
prefix/future-perturbation causality, grouping and time alignment, independent
reference parity, and deterministic/regression checks. Swing and ATR-rank
parity use independent brute-force oracles; frozen event state uses hand
fixtures and directional symmetry, since no standard external library defines
these exact events. This is not a claim of TA-Lib parity for bespoke events.
