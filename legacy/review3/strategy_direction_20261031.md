# moneta — Strategy Direction Plan (after 132 strategies)

> **Written 2026-10-31, against commit `936f7b9`.**
> This is a **strategy-research direction** document, not an execution checklist
> (execution fixes live in `docs/repo_review_20261030_followup3.md`).
>
> All numbers below are computed from the committed sweep artifacts
> (`strategy/results/iterations_*.csv`, 14,040 rows) and the committed per-strategy
> results (`strategy/results/S*/summary.csv`). Reproduce with the queries in §7.

---

## 0. The situation in one paragraph

132 strategies, 720 distinct `(strategy, variant)` configurations, 12,960
distinct evaluation cells — and **no strategy has beaten buy-hold across
markets on a defensible margin**. Every strategy is a 1–3 indicator rule
scored on raw return vs a buy-hold benchmark that is itself dominated by a
+1,288 % BTC bull run. The failure taxonomy is stable and the per-family hit
rates are wildly different — which means the search is **not** undifferentiated
noise: some hypothesis classes work slightly, most are provably dead. This
plan says which to kill, which to keep, and which two axes have never been
touched at all.

---

## 1. What actually killed the 132 strategies

Taxonomy over all 1,360 `(strategy, variant, window)` groups at 2 bps:

| Failure mode | Share | Meaning |
|---|---:|---|
| **Cost × frequency** | **79.7 %** | trade count high enough that 4 bps round-trip eats the per-trade edge |
| Signal quality | 13.9 % | low frequency, still loses → the signal itself has no edge |
| BTC-only (1 instrument) | 4.6 % | wins on BTC only → long-only beta artifact, not a strategy |
| Empty signal (0 trades) | 1.1 % | the entry predicate never co-occurs (e.g. S-03) |
| **Pass (≥ 2 instruments)** | **0.7 %** | — |

**Read this as a search-efficiency problem, not a bad-luck problem.** 79.7 % of
the budget was spent re-testing the same wall.

---

## 2. Per-family hit rate — where the signal is, and where it is not

Fraction of `(strategy, variant, window)` groups in which the strategy beat
buy-hold on **≥ 1 instrument** at 2 bps, with the degenerate wins removed
(≤ 2 trades — see §3):

| Family | Groups | Real-win groups | Rate | Verdict |
|---|---:|---:|---:|---|
| `bb_width` (band width) | 16 | 6 | **37.5 %** | live, thin evidence (16 groups) |
| `chop` (choppiness) | 16 | 5 | **31.2 %** | live, thin evidence (16 groups) |
| `adx` (trend strength) | 28 | 8 | **28.6 %** | **live** |
| `dow_sin` (day-of-week) | 32 | 9 | **28.1 %** | suspicious — needs a placebo test (§6) |
| `h1_rsi` (HTF RSI) | 16 | 4 | **25.0 %** | **live** — this is S-55's family |
| `hv` (realized vol) | 48 | 11 | **22.9 %** | **live** (best-measured live family) |
| `macd` | 32 | 4 | 12.5 % | marginal |
| `bb_pctb` | 44 | 3 | 6.8 % | marginal |
| `atr_pct` | 32 | 2 | 6.2 % | marginal |
| `h1_ema_dist` | 16 | 1 | 6.2 % | thin |
| `ema` | 56 | 2 | 3.6 % | dead |
| `dc_pos`, `rsi` | 32 each | 1 each | 3.1 % | dead |
| `stoch_d` | 44 | 1 | 2.3 % | dead |
| `willr` | 60 | 1 | 1.7 % | dead |
| `atr` | 64 | 1 | 1.6 % | dead |
| **36 zero-win families** (`mfi`, `roc`, `st_dir`, `aroon_down`, `stoch_k`, `close`, `bar_clv`, `h1_adx`, `bb_upper`, `er`, `cmf`, `dc_mid`, `macd_hist_atr`, `aroon_up`, `cci`, `sqz_on`, `dist_high/low`, `ema_dist`, `hour_sin`, `vol_ratio`, …) | **792** | **0** | **0.0 %** | **provably dead** |

> Both the numerator and the denominator here are **groups**
> (`(strategy, variant, window)`), not cells. Counting cells in the denominator
> while counting groups in the numerator inflates every rate by 3× — an easy
> mistake; see the reproduction script in `docs/master_plan_20261031.md` §11.3.

**792 of 1,360 groups — 58.2 % of the entire search budget — went to families
that produced not a single winning cell.** Of those, 13 families were measured
deeply enough (≥ 30 groups) to be *closed* rather than merely *unmeasured*;
they hold 584 groups = **42.9 %** of the budget. That budget is recoverable.

---

## 3. ⚠️ The pass criteria are currently satisfiable by noise

`config/strategies.yml → oos.pass_criteria` sets a **ceiling**
(`max_trades_per_year: 54`) but **no floor**. A strategy that trades once in
5.5 years is trivially ≈ buy-hold and "beats" it by a rounding error.

Measured across all 83 winning cells:

```
17 of 83 wins (20 %) come from strategies with ≤ 2 trades
 9 of those have an edge < 1 %  (i.e. they simply under-invested at the end)
```

**Concrete example — `s109 / ema_gate`:**

| Instrument | Window | Strategy | Buy-hold | Edge | Trades |
|---|---|---:|---:|---:|---:|
| BTC_USD | full | +1510.62 % | +1538.05 % | **−27.4 %** | **1** |
| XAU_USD | full | +112.25 % | +113.27 % | **−1.0 %** | **1** |
| XAU_USD | last_12m | +34.54 % | +34.41 % | **+0.13 %** | **1** |

It counts as "beats buy-hold on 2 instruments" because a one-trade strategy that
stays in the market misses the last close by a rounding error. This is the
same failure the registry called `S-06` (BTC-only beta), wearing a different hat.

**S-55 is partly the same issue:** its `XAU last_12m` win is **+0.6 % on 4
trades**. The `BTC full` win (+246.7 %) is the only one with real margin.

> **Fix before anything else.** Add to `oos.pass_criteria`:
> ```yaml
> min_trades: 10                # a cell must have enough trades for the edge to mean anything
> min_exposure_pct: 20         # and enough time in the market to be a strategy, not a fluke
> min_edge_pct: 5.0            # and a margin that is not a rounding error
> ```
> Enforce them in `strategy/schema.py::oos_pass_fields` (shared by the runner and
> the checker) so the in-sample bar and the OOS bar use one definition.

---

## 4. The decisive experiment: multi-factor ≠ multi-direction

The 20 pre-registered rules `S-113 … S-132` (`strategy/strategy_diverse_lib.py`,
2–5 indicators each, HTF-gated) are the **cleanest experiment in the repo** —
one fixed rule per strategy, no variant sweep, therefore no selection bias.

**Result: 0 winning cells out of 120 at 2 bps.** Median trade count 1,624;
`S-127` (CMF flow) ran 4,834 trades; `S-125` 2,605.

They failed for the same reason as everything else: **cost × frequency**.

**Conclusion:** the intuition "we need to search in more directions" is right,
but "more directions" was implemented as *more combinations of the same
indicator pool*. Those are correlated hypotheses, not diverse ones — and they
scored **worse** than the swept single-indicator families.

**Diversity has to come from a different economic claim, not a new indicator
combination.** That is §6.

---

## 5. The taxonomy that the evidence supports

Classify by **what the strategy claims about the market**, not by indicator
name. The existing registry's "Key indicators" column cannot express this; add
a `Class` column.

| Class | Economic claim | Families | Evidence | Status |
|---|---|---|---|---|
| **A. Directional trend** | price has momentum | `st_dir`, `aroon`, `macd`, `ema_spread`, `psar`, `roc`, `dmi` | 0–3.6 % | **retire** |
| **B. Directional mean-reversion** | price overshoots and reverts | `rsi`, `cci`, `willr`, `stoch_k/d`, `bb_pctb` | 1.7–3.1 % | **retire** |
| **C. Volatility state** | vol expansion precedes continuation | `hv`, `bb_width`, `atr_pct`, `sqz_on` | `hv` 22.9 % (11 real), `bb_width` 37.5 % (6 real) | **invest** |
| **D. Trend-strength regime** | only trade when the market is trending | `adx`, `chop` | `adx` 28.6 % (8 real), `chop` 31.2 % (5 real) | **invest** |
| **E. Calendar / session** | there is an intraday/weekly effect | `dow_sin`, `hour_sin` | `dow_sin` 28.1 % (9 real) | **placebo-test first** |
| **F. Volume / flow** | volume leads price | `mfi`, `cmf`, `vol_rel`, `vwap` | 0 % | **retire** |
| **G. Candle structure** | wick / CLV patterns predict | `bar_clv`, wick ratios | 0 % | **retire** |
| **H. Multi-factor + HTF gate** | direction, confirmed by the 1h | `S-113…S-132` | **0 / 120** | **retire** |
| **I. Asymmetric / market-neutral** | the *spread* between instruments, not the direction | — | **never searched** | **new axis** |
| **J. Position sizing / risk overlay** | the edge is *how much* to hold, not *when* | — | **not implementable today** | **new axis** |

### The two structural findings behind this table

**Finding 1 — every surviving family is a *state* family, not a *direction*
family.** `hv`, `adx`, `chop`, `bb_width`, `h1_rsi` all answer **"when is a
trend likely to persist?"**, none answers **"which way?"**. Classes A and B —
the two the repo has spent 132 strategies on — are exactly the two that fail.

**Finding 2 — the benchmark is the problem.** 110 of 132 strategies are
long-only, and the long-only benchmark is `BTC +1,288 % / EUR +3 %`. Every
"winner" so far (`S-06`, `S-18`, `S-35`, `S-36`, `S-45`, `S-55`, `S-88`,
`s109/ema_gate`) is BTC-only or degenerate. On this sample, a long-only rule
cannot easily beat a benchmark that one instrument dominates — **so a large
part of the "no edge" conclusion is a benchmark-composition artifact, not
evidence that the signals are worthless.**

---

## 6. Direction plan

### Step 0 — Fix the yardstick *(do this first; it de-noises everything else)*

1. Add `min_trades` / `min_exposure_pct` / `min_edge_pct` to
   `config/strategies.yml → oos.pass_criteria` (§3).
2. Enforce them in `strategy/schema.py::oos_pass_fields` — the single shared
   definition used by both the runner and `check_results.py` (X13).
3. Re-evaluate S-55 and `s109/ema_gate` against the corrected bar. Expect
   `s109/ema_gate` to fail (1 trade) and S-55 to be **much** weaker than
   reported (+0.6 % on 4 trades).

### Step 1 — Retire the dead classes *(the biggest efficiency win)*

- Add a `Class` column to `STRATEGY_REGISTRY.md` and tag all 132 rows.
- Add a machine check: **a family with 0 wins over ≥ 100 `(strategy, variant,
  window)` groups is closed** — new IDs in that family are refused by the
  checker, with the group tally printed. This mirrors the existing X15
  saturation guard but keys on *measured* deadness rather than family size.
- Remove the dead families from `scripts/strategy_variants.py::STRATEGIES`
  → **42.9 % of the search budget is freed** (the 13 deeply-measured closed
  families; 58.2 % if the shallower zero-win families are closed too).

### Step 2 — Re-base the bar on risk-adjusted performance

The engine already computes `buyhold_sharpe_weekly` and
`buyhold_max_drawdown_pct` (commit `4b8ab26`) — **they are not used by any
pass criterion yet.**

For classes C and D the honest hypothesis is **not** "beat buy-hold's
return" — it is **"keep the return, cut the drawdown"**. Propose (do not
implement unilaterally — owner sign-off) an additional criterion:

```yaml
# candidate criterion, for owner decision
risk_adjusted:
  min_sharpe_weekly_ratio: 1.0   # strategy sharpe_weekly >= buyhold_sharpe_weekly
  max_drawdown_ratio: 0.75       # strategy maxDD <= 0.75 x buyhold maxDD
```

A long-only rule that holds through a choppy regime and sits out a crash can
be genuinely valuable **without** beating the raw return — and that is a claim
the current bar cannot express, which is why 132 strategies all failed the
same way.

### Step 3 — Open the two axes that have never been searched

**Axis I — asymmetric / market-neutral (Class I).**
110 long-only vs 22 long/short. The engine supports shorts
(`long_only=False`), but almost nothing uses them. The natural experiment:
long the instrument with the stronger relative regime, short the weaker one
(a cross-sectional spread), which removes the BTC-beta domination from the
benchmark. This directly attacks the failure mode that produced every
"winner" so far. It needs **no new features** — only a different comparison
baseline than the current per-instrument buy-hold.

**Axis J — position sizing (Class J).**
`strategy/engine.py` fixes `UNIT_SIZE = 1.0`; there is **no position sizing
at all**. Volatility-targeted sizing (size ∝ 1/ATR) is the classic way to
convert a raw-return edge into a risk-adjusted one, and it is exactly what
Step 2's criterion would reward. This requires a **small, additive engine
change** (a per-bar size, not a fixed one) — it is the only engine change
worth making, and it should be done behind a flag with a test that a
constant-size run is bit-identical to today.

### Step 4 — Placebo-test the calendar class before believing it

`dow_sin` shows a 28.1 % hit rate with **0 degenerate wins** — that is either
a genuine session effect (well documented in FX) or a fitting artifact. The
cheap discriminator: **re-run the same rule on a shifted calendar** (e.g. use
`dow_sin` of bar *t-1*, or permute the weekday labels). A real calendar effect
stays attached to the calendar; an artifact moves.

### Step 5 — Change the search protocol, not the search volume

The budget is the scarce resource, and the marginal return per batch is ~1
pass for 720 cells — most of it noise.

- **Prefer one pre-registered rule per hypothesis over an 8-variant sweep.**
  The same budget then buys 8× as many *distinct* hypotheses. The variant
  sweep mostly re-rolls correlated configurations (the whole point of the
  8-variant sweep is that they are near-identical).
- **Every rule must be pre-registered in the registry before it is run**, so
  the "selected after the sweep" ambiguity never arises. The `S-109` report
  already does this correctly for S-113…S-132 and should become the default.
- **Report the family tally with every batch** — the sweep reports already do
  this (`727 configurations / ≥13,086 cells`); keep it, and add the
  per-family dead/alive state so the next batch does not re-tread a closed
  family.

---

## 7. Reproducing the numbers

```python
# failure taxonomy over all (strategy, variant, window) groups at 2 bps
#
# NOTE: the sweep CSVs OVERLAP — batch 2 re-ran s08..s17 from batch 1, so
# 1,080 rows are duplicates. Deduplicate on
# (strategy, variant, instrument, window) FIRST, or every count below is wrong
# (without the dedup the same query reports 67.8 % cost x frequency and
# 15.9 % empty instead of 79.7 % / 1.1 %).
import csv, glob
from collections import defaultdict

seen = {}
for f in glob.glob('strategy/results/iterations_*.csv'):
    for r in csv.DictReader(open(f)):
        if r['cost_bps'] != '2.0':
            continue
        try:
            r['edge'] = float(r['edge_vs_bh_pct'])
            r['tpy'] = float(r['trades_per_year'] or 0)
            r['n'] = int(r['n_trades'] or 0)
        except ValueError:
            continue
        seen[(r['strategy'], r['variant'], r['instrument'], r['window'])] = r

grp = defaultdict(list)
for r in seen.values():
    grp[(r['strategy'], r['variant'], r['window'])].append(r)
# -> 4,080 distinct cells, 1,360 (strategy, variant, window) groups

cats = defaultdict(int)
for k, v in grp.items():
    wins = [x for x in v if x['edge'] > 0]
    if len(wins) >= 2:
        cats['pass'] += 1
    elif len(wins) == 1:
        cats['btc-only'] += 1
    elif sum(x['n'] for x in v) == 0:
        cats['empty'] += 1
    elif max(x['tpy'] for x in v) > 54:
        cats['cost x frequency'] += 1
    else:
        cats['signal quality'] += 1
# -> cost x frequency 1084 (79.7 %) | signal quality 189 (13.9 %)
#    btc-only 62 (4.6 %) | empty 15 (1.1 %) | pass 10 (0.7 %)
```

Degenerate-win filter (add to the same loop):

```python
DEGENERATE_MAX_TRADES = 2
real = [x for x in wins if x[3] > DEGENERATE_MAX_TRADES]
```

Per-family family mapping comes from the registry's *Key indicators* column
with the window suffix stripped (`willr_60` → `willr`,
`macd_hist_6_24` → `macd_hist`, `st_dir_24_3` → `st_dir`).

---

## 8. What this plan does not do

| Item | Why not |
|---|---|
| Add more indicator combinations of classes A/B/F/G | Measured dead (0–3.6 % hit rate; 36 zero-win families holding 58.2 % of the budget) |
| Add a walk-forward harness / dedup engine / vectorised engine | Still deliberately deferred (`repo_review_20261028` §3) |
| Touch the OOS gate | It is correct and tested; the holdout stays unspent |
| Promote S-55 | Step 0 changes the bar; re-evaluate under it first |
| Change `oos.pass_criteria` unilaterally | Step 0's floors and Step 2's risk-adjusted criterion need owner sign-off |
| Merge `strategy_rsi_lib.py` into the shared core | State-leak bug was hit and reverted (`repo_review_20261028` §B3) |
