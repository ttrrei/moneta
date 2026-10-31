# Indicator idea catalogue — 50 hypotheses across five styles

Date: 2026-10-31. Status: **all 50 first versions implemented and evaluated**.
See the [measured results](indicator_catalogue_results_20261031.md) and
[implementation contract](indicator_catalogue_validation_spec_20261031.md).
The sketches below record the original ideas; frozen batch protocols define
their precise operational comparisons. Final decisions: 43 reject, 7 revise,
none qualified under the full replication rule.
Scope: ten ideas for each of the five styles discussed after the
[first P1 study](indicator_research_20261031_report.md).

These are 50 different research questions. Some require new mathematical
features; others compose existing features or describe their temporal state.
They are not 50 statistically independent hypotheses or 50 proven sources of
alpha. Existing P1 definitions keep their recorded results; changing context
or normalization does not erase those earlier attempts.

The catalogue was checked against `pipeline/indicators.py`,
`config/indicators.yml`, the [575-column inventory](../research/indicators/IR-20261031-P1-v2/existing_feature_inventory.csv)
and the [P1 feature definitions](indicator_research_P1_spec.md). Plain EMA
distance/spread, RSI, ATR ratios, BB width, squeeze flags, ER, CHOP, wick ratios,
CLV, confirmed pivots and failed breakouts already exist. They are inputs to
these ideas rather than new indicators to duplicate.

## Shared definitions and implementation boundaries

- `O,H,L,C,V` mean observed bar open/high/low/close/tick activity. `A=atr_24`,
  `E=ema_24`, `r=log(C/C_previous)`. `previous` means an already closed bar;
  it is an alignment operator, not an additional tunable rolling period.
- Every feature is available at its confirmation bar's close. Any return
  label starts at the next eligible open. A multi-bar pattern is emitted
  when it is confirmed, with no event backfill onto an earlier bar.
- Rolling/time-window parameters use `6,12,24,60,120`. Each row below gives
  one initial configuration; it does not authorize a parameter grid search.
  Calendar session boundaries are anchors, not extra rolling periods.
- A division with a zero or undefined scale produces null. Ties and neutral
  states must be explicitly specified before implementation. No synthetic
  prices, forced event zeros during undefined periods, or future interpolation.
- New rolling paths require complete, clock-adjacent observations by default;
  reset and rewarm at partial/missing observations. Returns spanning a closure
  are used only in ideas that explicitly measure such displacement. Session
  references use actual observed bars, with missing coverage reported.
- `LTF=5m`, `HTF=1h`. Compute HTF changes on the native 1h series **before**
  joining. Use the last completed, complete 1h bar by backward as-of close time;
  require source age in `[0,1h)`. Preserve source close/age for audit. Existing
  `h1_*` columns can be reused only where alignment and freshness are verified.
  Unfinished hours and stale context after closures remain unavailable.
- Positive/negative counterparts are one idea, not two. All event definitions
  include the symmetric version unless the data contract prevents it.
- `D` means directional continuation/reversal research; `V` means future
  volatility/magnitude; `R` means excursion/execution-risk context. A V/R
  feature need not predict signed mean return to be useful. Its evaluation
  target must be specified before a study runs.
- Any quantile threshold, bucket boundary, conditioning cut or nuisance model
  must be fixed from training only. Fit and retain the full planned comparison
  family before inspecting validation outcomes.

These are initial definitions for review, not frozen experiment protocols.
Before coding, each chosen ID needs exact inputs, output names, warm-up,
state reset/expiry, timestamp semantics, primary target and rejection criteria.

## 1. Trend and multi-timeframe alignment — TR-01 to TR-10

| ID | Idea | First definition / existing inputs | Question and primary use |
|---|---|---|---|
| TR-01 | **Cross-timeframe direction agreement** | Reuse `st_dir_24_2` on 5m and completed 1h. Emit +1 for both up, -1 for both down, 0 for disagreement; missing context remains null. | **D:** Does a low-timeframe move continue differently when both directions agree? Compare with the same 5m state under disagreement. |
| TR-02 | **HTF trend with an LTF pullback** | Pair native 1h `(E[t]-E[t-6])/A[t]` with 5m `ema_dist_24`; retain the continuous two-dimensional state. | **D:** Does a temporary move against the broader slope recover differently from an equally deep move aligned with it? This tests context, not another EMA distance. |
| TR-03 | **Directional trend-strength acceleration** | On 1h, multiply `adx_24[t]-adx_24[t-6]` by `(plus_di_24-minus_di_24)/(plus_di_24+minus_di_24)`, then join to 5m. | **D:** Does strengthening directional organization differ from a high but fading ADX reading? |
| TR-04 | **Multi-scale trend breadth** | Equal-weight mean of `sign(C-ema_N)` for `N=6,12,24,60,120`, on each native timeframe. No optimized weights. | **D:** Is broad agreement across scales more stable than a single fast/slow crossing? Require incremental evidence beyond existing EMA spreads. |
| TR-05 | **Trend age versus trend quality** | Count consecutive `st_dir_24_2` observations, capped at 120; pair with `er_24`. Reset on undefined direction or input discontinuity. | **D/R:** Does an old efficient trend behave differently from an equally old noisy one? Age is not evidence of exhaustion by itself. |
| TR-06 | **Pressure against confirmed HTF structure** | At each 5m close, measure distance to the last unexpired confirmed 1h swing high/low in 1h ATR units; retain level identity and age. | **D/R:** Do approaches to confirmed higher-timeframe levels differ from approaches to local-only levels? Depends on resolving hourly swing coverage before use. |
| TR-07 | **Trend curvature** | With `s[t]=(E[t]-E[t-6])/A[t]`, emit `s[t]-s[t-6]`. Start on 5m; retain slope as a conditioning input. | **D:** Does accelerating versus decelerating trend speed change subsequent continuation at comparable current slope? |
| TR-08 | **Timeframe agreement breakdown** | Emit when a previously aligned TR-01 state first becomes disagreement; record which timeframe changed and the earlier aligned-state age, capped at 120. | **D/R:** Does loss of agreement precede reversal or wider adverse excursions? This is a transition study rather than the static TR-01 comparison. |
| TR-09 | **Higher-timeframe range migration** | Native 1h `(dc_mid_24[t]-dc_mid_24[t-6])/A[t]`, conditioned on where the 5m close lies relative to the latest completed 1h range. | **D:** Does movement of the whole trading range add information beyond moving-average direction? A single new extreme must not be mistaken for broad migration. |
| TR-10 | **Trend quality mismatch across timeframes** | Pair `h1_er_24` with 5m `er_24`, retaining the completed 1h directional state separately. | **D/V:** Is low-timeframe disorder inside an efficient higher-timeframe trend a pause, while disorder on both scales is a different regime? |

**Distinctness check:** direction, pullback context, strength acceleration,
breadth, age, structural proximity, curvature, transition, range migration and
quality mismatch measure different aspects of a trend. TR-01/TR-08 share a
parent hypothesis and must remain linked in trial accounting.

## 2. Mean reversion and price stretch — MR-01 to MR-10

| ID | Idea | First definition / existing inputs | Question and primary use |
|---|---|---|---|
| MR-01 | **Robust median stretch** | Over the latest 24 closes, `m=median(C)` and `MAD=median(abs(C-m))`; emit `(C[t]-m)/MAD`. All deviations use the same current window median. | **D:** Does an extreme displacement from a robust center tend to reverse? Compare with existing `ema_dist_24`; null when MAD is zero. |
| MR-02 | **Causal regression residual** | Fit an OLS line to the latest 24 closed log-prices against observed-bar index. Standardize the current endpoint residual by `sqrt(sum(residual²)/24)`. | **D:** Does deviation from a locally sloping path predict recovery better than deviation from a horizontal center? Fit only trailing data. |
| MR-03 | **Session-VWAP stretch by session phase** | Pair `(C-vwap)/A` with elapsed time from the configured session anchor. Use existing tick-weighted VWAP and past-only phase buckets. | **D:** Does distance from the session's developing activity-weighted center mean something different early versus late in the session? Tick activity is not exchange volume. |
| MR-04 | **Oscillator extremes conditional on trend efficiency** | Reuse `rsi_6` and `er_60`; compare RSI-tail behavior under low and high efficiency using training-defined cuts. | **D:** Are oscillator extremes associated with reversal primarily when the broader path is inefficient? This does not add another RSI column. |
| MR-05 | **Price–oscillator disagreement** | Pair `log(C[t]/C[t-6])` with `rsi_6[t]-rsi_6[t-6]`; identify opposite signs, retaining both magnitudes. | **D:** Does price making progress while its oscillator weakens behave differently from progress with oscillator confirmation? No hindsight-selected pivots. |
| MR-06 | **Cross-asset residual stretch** | Fix one economically related pair before testing, such as EUR_USD/GBP_USD. Compute each bar's residual using intercept/beta fitted on the previous 60 synchronized returns, excluding that bar; sum the latest 6 already observed residuals. | **D:** Does unusually large relative displacement recover? Needs joint data coverage, fitted-residual scale and exact synchronization; a residual is not proof of a tradable hedge. |
| MR-07 | **Post-shock loss of speed** | Identify a large `tr/A_previous` using a training-fitted threshold. Freeze the shock's direction/ATR; after 6 complete bars measure additional directional progress relative to the original shock. One active episode. | **D/R:** Does a large move that subsequently makes little progress reverse more often than a shock that keeps extending? Emit after the six-bar observation, not on the shock bar. |
| MR-08 | **Price–activity-pressure disagreement** | Pair six-bar signed return with existing `cmf_24`; distinguish agreeing and opposing signs and retain activity coverage. | **D:** Does price extension without the same sign of close-location-weighted tick activity show different reversal behavior? CMF is a proxy, not observed order flow. |
| MR-09 | **Session-open displacement recovery** | At the first observed bar after a configured anchor, freeze its open and the previous complete close. Track signed remaining distance to that prior close, normalized by pre-anchor ATR, for at most 24 observed bars. | **D/R:** Does an initial between-session displacement continue or recover as the session develops? Require declared anchor coverage and record closure duration; do not assume an executable gap-fill trade. |
| MR-10 | **Mean reclaim after persistent stretch** | Freeze `E` before a six-bar block. If all six closes remain on one side, keep that level for up to 6 further bars; emit on the first later close crossing it, with original stretch and time-to-reclaim. | **D:** Once a prolonged displacement has actually reclaimed its original mean, is there follow-through or another rejection? Reclaim confirmation differs from MR-01's unconfirmed stretch. |

**Distinctness check:** robust center, sloping center, session-weighted center,
regime-conditioned oscillator, oscillator disagreement, relative value,
shock decay, activity disagreement, session displacement and completed reclaim
are different questions. Alternative centers and oscillator interactions are
related comparisons, not independent discoveries.

## 3. Compression, expansion and breakout behavior — CB-01 to CB-10

| ID | Idea | First definition / existing inputs | Question and primary use |
|---|---|---|---|
| CB-01 | **Squeeze episode age** | Count consecutive `sqz_on_24` observations, capped at 120. Keep BB width as a control; reset on missing source history. | **V:** Does a long squeeze precede different future magnitude from a short squeeze of comparable present width? Age adds temporal information beyond the existing flag. |
| CB-02 | **Nested-range compression** | `(max(H,6)-min(L,6))/(max(H,24)-min(L,24))`, with both windows trailing and inclusive. | **V:** Does concentration of the recent range inside a broader range anticipate expansion? Compare against existing ATR ratios rather than treating both as unrelated hypotheses. |
| CB-03 | **Compression-conditioned range release** | When BB width first enters a training-defined low state, freeze the preceding 24-bar range; emit the first later close outside it within 6 bars. Rearm only after leaving and re-entering the low state. | **D/V:** Does an identical range break behave differently after compression? This is a contextual extension of recorded P1 breakout work. |
| CB-04 | **Acceptance beyond a broken range** | Freeze the prior 24-bar range on a close breakout. After 6 bars, report the fraction of those closes outside the original broken edge and directional displacement. | **D:** Does sustained acceptance differ from a brief penetration? Do not emit a six-bar acceptance score on the original breakout row. |
| CB-05 | **Breakout activity participation** | At a fresh prior-range close breakout, pair `tr/A_previous` with existing `vol_rel_24`, using training-fitted two-dimensional groups. | **D/V:** Do breakouts with greater observed tick participation behave differently from similarly sized low-activity moves? No claim about actual liquidity or institutional participation. |
| CB-06 | **Body-led versus wick-led expansion** | Over 6 bars, divide `sum(C-O)` by `sum(tr)`; condition on existing `vol_ratio_6_24` expansion. | **D/R:** Does expanded movement carried by directional candle bodies persist differently from expansion dominated by wicks and opening displacement? |
| CB-07 | **Upside/downside variance imbalance** | Over 24 returns, `(sum(r² where r>0)-sum(r² where r<0))/sum(r²)`. Retain total variance. | **D/R:** Does the side supplying recent volatility distinguish continuation from asymmetric adverse risk at comparable total volatility? |
| CB-08 | **Range versus close-volatility disagreement** | Reuse `(atr_24/C)/hv_24`; evaluate alongside each component. Null when close-volatility is zero. | **R/V:** Do large intrabar ranges with little close-to-close volatility predict different excursions from ordinary volatility? This ratio is a proxy comparison, not an identity between estimators. |
| CB-09 | **Volatility instability** | Standard deviation over 24 observations of existing `vol_ratio_6_24`; retain its current level separately. | **V/R:** Does an unstable expansion/contraction process carry different future volatility or tail excursions from a stable process at the same level? |
| CB-10 | **Directional range-break sequence balance** | Over 24 bars, count fresh upward and downward close crossings of each bar's prior Donchian-24 edges; emit `(up_count-down_count)/(up_count+down_count)` and total count. | **D:** Does repeated one-sided discovery differ from alternating range breaks? Null if no breaks; do not count every outside close as another fresh crossing. |

**Distinctness check:** duration, geometry, release context, later acceptance,
activity, candle composition, variance asymmetry, estimator disagreement,
instability and crossing sequence are different observations. CB-01/02/03
share a compression parent; CB-03/04/05/10 share breakout ancestry with P1.

## 4. Candle rejection and price structure — PA-01 to PA-10

| ID | Idea | First definition / existing inputs | Question and primary use |
|---|---|---|---|
| PA-01 | **Accumulated wick imbalance** | Over 6 bars, `sum(upper_wick-lower_wick)/sum(H-L)`. Reuse the existing candle components where precision permits. | **D:** Does persistent one-sided rejection carry information beyond the latest candle's wick ratio? Distinguish repeated rejection from one unusually long wick. |
| PA-02 | **Body-engulfing reversal strength** | Two opposite-color closed bodies; the current body's open/close interval contains the previous body's interval, with at least one strict boundary. Record current body size in ATR units. | **D:** Does a complete reversal of the preceding body add information beyond ordinary opposite-color candles? Explicitly define doji/equality behavior. |
| PA-03 | **Mother-bar containment release** | Fix the mother bar at `t-6`; require the next five complete bars' ranges to remain inside it. At `t`, emit only on a close beyond its frozen high/low. | **D/V:** Does release from a geometrically contained cluster differ from generic low volatility? Confirm at the release close, not when the mother bar formed. |
| PA-04 | **Outside-bar settlement** | Require `H>H_previous` and `L<L_previous`; retain existing CLV and close position relative to the prior midpoint, normalized by prior range. | **D/R:** Does the settlement location of a bar that traverses both prior extremes distinguish direction or risk? OHLC cannot reveal which extreme occurred first. |
| PA-05 | **Repeated tests of a frozen boundary** | Freeze the prior Donchian-24 bounds at the start of a six-bar observation. Count contacts within 0.25 of frozen ATR that close inside; count each bar at most once per side. | **D/R:** Do repeated unsuccessful boundary tests precede rejection or eventual failure differently from a single test? Retain count and contact distance rather than tune a count threshold. |
| PA-06 | **First revisit of confirmed structure** | After a swing confirms, wait at least 6 bars, then mark its first observed contact within 0.25 confirmation ATR, expiring at age 120. Record whether the close holds or crosses the level. | **D:** Does the first revisit behave differently from repeatedly visited structure? Unlike a breakout retest, no preceding close breakout is required. |
| PA-07 | **Next-bar confirmation of a strong close** | Select prior-bar CLV extremes with training cutpoints. On the next complete bar record direction-adjusted close progress in prior ATR units and whether the prior close is retained. | **D:** Does actual confirmation of a strong close differ from the unconfirmed single-candle signal studied in P1? Emit on the confirmation bar. |
| PA-08 | **Wick-to-body transition** | Compare two consecutive six-bar blocks: change in summed body/range share, paired with the earlier block's wick imbalance and the later block's body direction. | **D:** Does a shift from repeated rejection to directional bodies identify a change in price acceptance? This tests temporal change rather than PA-01's static imbalance. |
| PA-09 | **Prior-extreme sweep with inside close** | Compare the current high/low with the previous Donchian-24 range. Emit when an extreme crosses an edge but the same bar closes inside the frozen range; retain penetration/ATR. Both-edges sweeps form a separate ambiguous stratum. | **D/R:** Does an intrabar rejection differ from a close breakout that fails on a later bar? No order-book or “liquidity hunt” interpretation is assumed; do not assign an invented direction to a both-edges sweep. |
| PA-10 | **Confirmed-level clustering** | Keep confirmed swing levels whose confirmation age is below 120. At each close, report the fraction within 0.25 current ATR of price, the count and high/low composition. | **D/R:** Do several nearby confirmed levels behave differently from one isolated reference? Retain confirmation times; never discover the cluster using unconfirmed future pivots. |

**Distinctness check:** accumulated wick anatomy, two-body reversal, containment,
outside-bar settlement, contact count, first revisit, follow-through,
anatomy transition, same-bar sweep and multi-level geometry are distinct.
PA-01/07/08 remain related to P1 wick/CLV; PA-05/06/09/10 share range or swing
dependencies. Hourly swing-dependent ideas require a documented gap-policy
decision and adequate coverage before a statistical study.

## 5. Persistence, path efficiency and session behavior — PS-01 to PS-10

| ID | Idea | First definition / existing inputs | Question and primary use |
|---|---|---|---|
| PS-01 | **Return-sign memory** | Over 24 consecutive sign-transition pairs, correlate `sign(r[t])` with the preceding sign. Keep zero returns as a separate declared value; null for zero variance. | **D:** Does recent persistence versus alternation change the continuation probability of the latest move? This differs from net-distance ER. |
| PS-02 | **Directional run age** | Count consecutive positive or negative returns, signed by direction and capped at 120; zero/undefined returns end the run. | **D:** Does continuation or reversal depend on the age of an uninterrupted run after controlling for total displacement? |
| PS-03 | **Sign-transition entropy** | From 24 observed transitions among negative/zero/positive returns, estimate conditional transition entropy with a declared zero-count convention; retain the transition table. | **D/V:** Do ordered transitions differ from disordered ones? Low entropy can mean alternation or persistence, so the table must distinguish those cases. |
| PS-04 | **Path turning intensity** | Over 24 observations, `sum(abs(r[t]-r[t-1]))/sum(abs(r[t]))`, with explicitly matched summation bounds. | **D/R:** Do frequent sharp changes in return direction or magnitude distinguish unstable paths even when ER and net return look similar? |
| PS-05 | **Jump concentration** | Over 24 returns, `max(r²)/sum(r²)`, retaining the largest move's sign and location within the window. | **D/R:** Does a move carried by one observation behave differently from distributed progress of comparable size? This measures concentration, not shock-decay confirmation. |
| PS-06 | **Return scaling across observation lengths** | Over 120 observations, compare the variance of trailing six-bar summed log returns with `6*variance(one-bar log returns)`, using only completed six-bar sums. | **V/D:** Is recent return aggregation consistent with persistence or cancellation, and does it persist? Overlap requires dependence-aware inference; do not label this a reliable Hurst estimate. |
| PS-07 | **Volatility memory** | Over 24 consecutive pairs, correlate `abs(r[t])` with `abs(r[t-1])`; retain current realized volatility as a control. | **V/R:** Does persistence of movement magnitude help distinguish calm/volatile continuations beyond the present volatility level? This is separate from PS-01's directional sign memory. |
| PS-08 | **Session-phase activity surprise** | Current tick activity divided by the median at the same elapsed session slot in the previous 6 sessions with complete observed coverage. Build history only from already finished sessions. | **V/R:** Does activity unusually high or low for that session phase carry information beyond existing recent-bar `vol_rel_24`? Missing slot history remains null; audit DST. |
| PS-09 | **Session-initial-range utilisation** | On 5m, freeze the range of the first 6 complete, contiguous bars after the configured anchor. Later report observed session range divided by that initial range, with elapsed phase. | **V/R:** Does an already heavily used initial range imply different remaining expansion? Undefined until the initial block finishes; the anchor need not be a cash-market open. |
| PS-10 | **Between-bar versus within-bar move share** | Let `g=log(O/C_previous)` and `b=log(C/O)`. Over 24 observations report `sum(g²)/(sum(g²)+sum(b²))`, plus actual timestamp-gap/closure flags. | **R/V:** Does movement concentrated between observations carry different adverse excursions or execution risk from movement inside observed bars? Preserve real closure displacement; never impute the missing path. |

**Distinctness check:** directional memory, run age, transition uncertainty,
turning intensity, jump concentration, aggregation scaling, magnitude memory,
seasonally adjusted activity, anchored range usage and move attribution are
different path properties. PS-01/02/03/04/06 are dependent persistence studies;
PS-07/08/09 overlap the volatility research family.

## Initial implementation batch — two per style (completed)

This order reflects data availability, definition clarity and reuse. It is not
a ranking of expected profitability or a claim that these ideas will work.

| Style | First pair | Why start here |
|---|---|---|
| Trend / multi-timeframe | TR-01, TR-02 | Existing direction/distance inputs; tests whether context adds information. Requires audited HTF source timing. |
| Mean reversion | MR-01, MR-02 | Contrasts robust horizontal and locally sloping centers without cross-asset or session infrastructure. |
| Compression / expansion | CB-01, CB-07 | Covers state duration and directional volatility composition rather than another raw ATR ratio. |
| Candle / structure | PA-02, PA-09 | Explicit closed-bar event definitions, minimal state, no dependency on sparse hourly pivots. |
| Persistence / sessions | PS-01, PS-05 | Distinguishes directional memory from single-move concentration using existing OHLC alone. |

The other 40 were subsequently implemented in batches 2–5 at the user's
request. MR-06 uses synchronized peers; session features use audited local
anchors; structural features retain the explicit strict reset policy. The
catalogue runner adds matched comparisons and magnitude/risk targets while
preserving the earlier P1 runner and its results. The results report records
remaining sample-coverage limits rather than treating them as successful tests.

## How the next study should judge these ideas

1. **Inventory and overlap:** retain these IDs, reused inputs, parent families
   and prior P1 results. Confirm that the proposed output adds a different
   observation or a genuinely new conditional question. Deduplicate simple
   algebraic copies before implementation.
2. **Definitions and engineering:** freeze one configuration per selected
   idea, exact timing, null/reset/expiry rules and the primary target. Run
   hand examples, causality, warm-up, grouping, parity and determinism gates.
3. **Incremental information:** compare with the reused base feature and
   matched controls where appropriate. For example, PA-09 requires comparison
   with ordinary range-edge contacts, not merely an unconditional mean.
   Specify matching/conditioning and training fits before validation.
4. **Correct target:** D studies use next-open signed returns and both sides;
   V studies can use future absolute returns or explicitly defined realized
   variance; R studies use defined excursion/tail summaries. Risk/context
   findings do not automatically qualify as standalone directional signals.
5. **Evidence and costs:** report all distributions, counts, missingness,
   calendar duration and dependence-aware uncertainty across assets/slices.
   Apply costs to execution claims; an improvement in volatility prediction
   is not itself a net trading return.
6. **Cumulative trial accounting:** record the exact tested outputs, targets,
   conditioning variants, sides and horizons before running. Account for
   related and earlier searches; a new batch does not automatically provide
   fresh independent evidence. Freeze the multiplicity plan and ensure Monte
   Carlo precision can resolve its threshold.
7. **Evaluation discipline:** use permitted development data only. No OOS
   token or protected rows are needed to create this catalogue. Any later
   untouched evaluation must follow the project's existing governance; no
   new period is assumed available just because a new idea is proposed.

## Catalogue self-review

- Counted exactly five styles and ten unique IDs per style: 50 ideas.
- Removed direct copies of raw EMA distance, ER, ATR ratios, CLV and wick
  ratios; existing atoms are explicitly reused in conditional/temporal ideas.
- Distinguished PA-09's same-bar sweep from P1's later failed close breakout,
  and PA-06's first revisit from an after-break retest.
- Kept HTF differences on native HTF observations, not repeated 5m rows;
  recorded freshness and source-time requirements.
- Separated directional, volatility and risk targets. Additional targets and
  interactions create additional tests and must be counted.
- Flagged session, cross-asset and hourly-structure dependencies. None of
  these proposed ideas inherits an empirical pass from the earlier study.
- At catalogue creation, no implementation or experiment had been performed.
  Subsequent implementation/validation is recorded in the results report;
  no strategy nomination or OOS consumption was performed.
