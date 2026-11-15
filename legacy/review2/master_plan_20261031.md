# moneta — Master Plan (2026-10-31)

> **One self-contained master document.** It specifies the whole documentation
> system, the strategy taxonomy, the yardstick, the research protocol, the
> infrastructure work-list and the owner-decision log.
>
> **For the AI executing this file (VS Code):** you are expected to *split* this
> into the individual files described in §2 and then execute them **in the order
> of §12**. Do not start editing strategy code before §9 (infrastructure) is
> green, and do not run any strategy before §7 (pre-registration) is machine-enforced.
>
> Baseline: commit `936f7b9` (2026-10-31), 132 registered strategies, 720 distinct
> `(strategy, variant)` configurations, 12,960 distinct evaluation cells, OOS
> holdout **never consumed**.
>
> Companion documents (do not duplicate their content — link to them):
> * `docs/repo_review_20261030_followup3.md` — the executable fix checklist (Phases A–E)
> * `docs/strategy_direction_20261031.md` — the empirical analysis behind §4–§5

---

## 0. Executive summary

**The engineering is in good shape. The research process is not.**

| Observation | Evidence |
|---|---|
| The OOS gate is correct and tested | every bypass attempt (gap-fill re-open, superseded reuse, corrupt/missing ledger, forged token, timezone-offset trick) is blocked |
| The code is clean at scale | 132 libs: **zero** invalid feature columns, **zero** lookahead, every state class has a rule test |
| The search is *not* undifferentiated noise | 79.7 % of all failures have one cause (cost × frequency); per-family hit rates range 0 % → 37.5 % |
| **58 % of the search budget was spent on families with literally zero wins** | 792 of 1,360 `(strategy, variant, window)` groups |
| The pass criteria are satisfiable by noise | `oos.pass_criteria` has a **ceiling but no floor**; 20 % of all "wins" come from ≤ 2-trade strategies |
| The latest, cleanest experiment scored **zero** | the 20 pre-registered multi-factor rules (`S-113…S-132`): **0 winning cells out of 120** |
| Two axes have never been searched | long/short asymmetry (110 of 132 strategies are long-only) and position sizing (the engine fixes `UNIT_SIZE = 1.0`) |

**Three things must happen, in this order:**

1. **Fix the yardstick** (§5) — until the bar cannot be met by a one-trade
   strategy, "which candidate is best" is not a meaningful question.
2. **Impose a research protocol** (§7) — pre-registration, per-class budget,
   mandatory analysis gate between batches. *Not* more parallelism.
3. **Re-base the search onto the two untouched axes** (§8) — asymmetric/neutral
   and position sizing — instead of re-treading the 0 %-hit families.

---

## 1. What this document system is for

The repo has a chronic failure mode that is **not** a coding problem:

> Documents drift from code, and the next session reads the documents and
> repeats work that is already done — or worse, repeats work that was
> **rejected**.

Every incident so far has been that: the review doc saying "A3 is open" when
it was fixed; `README.md` saying "no CI" when CI existed; a trial-log date
invented as `2026-11-06` when the run happened on `2026-10-30`; 86 rows in a
best-of-N audit trail dated in the future.

**This document system exists to make that failure mode structurally impossible
for strategy research**, by:

1. giving every fact exactly one home (§3);
2. making the *pre-registration* of a strategy machine-checkable (§7.1);
3. making the *judgement* of a strategy a single shared definition (§5);
4. making *dead ends* machine-enforced, not merely written down (§6);
5. putting every owner decision on the record with a date and a reason (§10).

---

## 2. The file set

```
docs/plan/
├── README.md                      ← ENTRY POINT. Read-order map, precedence rules, status board.
├── 00_infrastructure.md           ← A. Technical work-list: correctness & stability first.
├── 01_research_protocol.md        ← B. The search protocol: prereg, budget, cadence, stop rules.
├── 02_taxonomy.md                 ← C. The taxonomy + THE yardstick + per-class summaries.
├── directions/
│   ├── C_volatility_state.md
│   ├── D_trend_strength_regime.md
│   ├── E_calendar_session.md
│   ├── I_asymmetric_neutral.md
│   └── J_position_sizing.md
└── decisions.md                   ← Owner decision log (dated, attributed, rationale).

config/
├── strategy_plan.yml              ← MACHINE-READABLE: preregistration ledger + closed families.
```

### 2.1 Design rules for the file set

| Rule | Why |
|---|---|
| **One fact, one home.** Everything else links. | This is the drift cure. |
| **Direction files are small and stable.** They describe *how to search a class*, never *which hypotheses exist*. | A direction file that lists hypotheses grows forever and drifts. Hypotheses live in `config/strategy_plan.yml`. |
| **The yardstick is defined once**, in `02_taxonomy.md`, and referenced — never restated — elsewhere. | Four restatements of a pass rule is four drift surfaces. |
| **Preregistration is machine-readable**, not prose. | The repo's whole discipline is machine-enforced (`check_results.py`). A prose prereg drifts within a week. |
| **Dead ends are machine-enforced**, not merely recorded. | 58 % of the budget went to families with zero wins. Prose did not stop that. |
| **Every owner decision is logged** with date + rationale. | So the next session can tell "decided" from "considered". |

### 2.2 Why the plan is split across files at all

| File | Audience | Cadence | Failure mode it prevents |
|---|---|---|---|
| `README.md` | any AI session | read first, every time | reading the wrong doc; missing a decision |
| `00_infrastructure.md` | implementer | changes rarely | running research on an unstable harness |
| `01_research_protocol.md` | any AI session running strategies | changes rarely | burning budget without a protocol |
| `02_taxonomy.md` | any AI session proposing a strategy | changes when a class is added/closed | proposing a duplicate class |
| `directions/*.md` | an AI session working one class | changes when the class's approach changes | re-running a closed class |
| `decisions.md` | everyone | append-only | "we discussed it" vs "we decided it" |
| `config/strategy_plan.yml` | the checker + the runner | append-only, machine-read | running an unregistered strategy; re-running a dead one |

---

## 3. Precedence rules (conflict resolution)

When two sources disagree, the higher number wins. **This must be stated in
`docs/plan/README.md`.**

| # | Source | Authority over |
|---|---|---|
| 1 | `config/*.yml` (machine-readable) | everything below |
| 2 | `config/strategy_plan.yml` | the registry, the trial log, direction files |
| 3 | `docs/plan/02_taxonomy.md` | direction files, registry prose |
| 4 | `docs/plan/directions/*.md` | the registry prose, sweep reports |
| 5 | `strategy/STRATEGY_REGISTRY.md` + `strategy/trial_log.md` | sweep reports, per-strategy reports |
| 6 | the code | **nothing** — code never overrides a decision; a code/doc conflict is a *bug to report*, not a licence to pick one |

> **Exception, inherited from the repo's existing rule:** if the **code** and
> `config/` disagree, the *code* is wrong and `config/` is right — the code must
> be corrected. But a code vs. `docs/plan/` disagreement is resolved by the
> table above (a doc wins over code), because the doc records the *decision* and
> the code may simply not have been updated yet.

---

## 4. The taxonomy (总纲)

### 4.1 Failure taxonomy — what actually killed 132 strategies

Computed over all 1,360 `(strategy, variant, window)` groups at 2 bps
(4,080 distinct cells; the sweep CSVs overlap by 1,080 rows — see §11):

| Failure mode | Count | Share |
|---|---:|---:|
| **Cost × frequency** (`trades_per_year > 54`) | 1,084 | **79.7 %** |
| Signal quality (low frequency, still loses) | 189 | 13.9 % |
| BTC-only (beats buy-hold on 1 instrument) | 62 | 4.6 % |
| Empty signal (0 trades — predicate never co-occurs) | 15 | 1.1 % |
| **Pass (≥ 2 instruments)** | **10** | **0.7 %** |

**Read as a search-efficiency problem, not bad luck.** Four fifths of the
budget was spent re-testing the same wall.

### 4.2 Per-family hit rate — the signal map

Fraction of groups where the strategy beat buy-hold on **≥ 1 instrument** at
2 bps. *Real wins* = degenerate wins (≤ 2 trades, see §5.1) removed.

| Family | Groups | Real-win groups | Rate | Verdict |
|---|---:|---:|---:|---|
| `bb_width` (band width) | 16 | 6 | **37.5 %** | live, but thin evidence (16 groups) |
| `chop` (choppiness) | 16 | 5 | **31.2 %** | live, but thin evidence (16 groups) |
| `adx` (trend strength) | 28 | 8 | **28.6 %** | **live** |
| `dow_sin` (day-of-week) | 32 | 9 | **28.1 %** | suspicious → placebo test (§8.E) |
| `h1_rsi` (HTF RSI) | 16 | 4 | **25.0 %** | live — this is S-55's family |
| `hv` (realized volatility) | 48 | 11 | **22.9 %** | **live** (best-measured live family) |
| `macd` | 32 | 4 | 12.5 % | marginal |
| `bb_pctb` (band position) | 44 | 3 | 6.8 % | marginal |
| `atr_pct` | 32 | 2 | 6.2 % | marginal |
| `h1_ema_dist` | 16 | 1 | 6.2 % | thin |
| `ema` | 56 | 2 | 3.6 % | dead |
| `dc_pos`, `rsi` | 32 each | 1 each | 3.1 % | dead |
| `stoch_d` | 44 | 1 | 2.3 % | dead |
| `willr` | 60 | 1 | 1.7 % | dead |
| `atr` | 64 | 1 | 1.6 % | dead |
| **`mfi`, `roc`, `st_dir`, `aroon_down`, `stoch_k`, `close`, `bar_clv`, `h1_adx`, `bb_upper`, `er`, `cmf`, `dc_mid`, `macd_hist_atr`, `aroon_up`, `cci`, `sqz_on`, `dist_high/low`, `ema_dist`, `hour_sin`, `vol_ratio`, … (36 families total)** | **792** | **0** | **0.0 %** | **provably dead — 58.2 % of the budget** |

**Note the two axes.** A family with a high rate but few groups (`bb_width`,
`chop`, `h1_rsi` — 16 groups each) is *suggestive*, not established; a family
with a low rate but many groups (`atr` 64 groups → 1 win) is *established
dead*. §6.1 therefore closes on **both** criteria, not the rate alone.

### 4.3 The classes

**A `class` column must be added to `strategy/STRATEGY_REGISTRY.md`** and every
one of the 132 rows tagged. The classification axis is **the economic claim the
strategy makes**, not the indicator name — the evidence shows that indicator
name predicts nothing, while claim type predicts a lot.

| Class | Economic claim | Representative families | Evidence | Status |
|---|---|---|---|---|
| **A** | Directional trend — price has momentum | `st_dir`, `aroon`, `macd`, `ema_spread`, `psar`, `roc`, `dmi` | 0–3.6 % | **retired** |
| **B** | Directional mean-reversion — price overshoots and reverts | `rsi`, `cci`, `willr`, `stoch_k/d`, `bb_pctb` | 1.7–6.8 % | **retired** |
| **C** | Volatility state — vol expansion precedes continuation | `hv`, `bb_width`, `atr_pct`, `sqz_on` | `hv` 22.9 % (11 real), `bb_width` 37.5 % (6 real) | **open** |
| **D** | Trend-strength regime — trade only when the market is trending | `adx`, `chop` | `adx` 28.6 % (8 real), `chop` 31.2 % (5 real) | **open** |
| **E** | Calendar / session — intraday or weekly effect | `dow_sin`, `hour_sin` | `dow_sin` 28.1 % (9 real), 0 degenerate | **open, placebo first** |
| **F** | Volume / flow — volume leads price | `mfi`, `cmf`, `vol_rel`, `vwap` | 0 % | **retired** |
| **G** | Candle structure — wick / CLV patterns predict | `bar_clv`, wick ratios | 0 % | **retired** |
| **H** | Multi-factor + HTF gate — direction confirmed by the 1h | `S-113…S-132` | **0 / 120** | **retired** |
| **I** | **Asymmetric / market-neutral** — the *spread* between instruments | — | **never searched** | **new axis** |
| **J** | **Position sizing / risk overlay** — the edge is *how much* to hold | — | **not implementable today** | **new axis** |

### 4.4 The two structural findings

**Finding 1 — every surviving family is a *state* family, not a *direction* family.**
`hv`, `adx`, `chop`, `bb_width`, `h1_rsi` all answer *"when is a trend likely to
persist?"*. **None answers "which way?"** Classes A and B — the two the repo
spent 132 strategies on — are exactly the two that fail.

**Finding 2 — the benchmark is itself the problem.**
110 of 132 strategies are long-only, and the long-only benchmark is
`BTC +1,288 % / EUR +3 %`. Every "winner" so far (`S-06`, `S-18`, `S-35`,
`S-36`, `S-45`, `S-55`, `S-88`, `s109/ema_gate`) is BTC-only or degenerate.
**A large part of the "no edge" conclusion is a benchmark-composition
artifact**, not evidence that the signals are worthless. This is why class I
exists.

### 4.5 The decisive experiment: multi-factor ≠ multi-direction

The 20 pre-registered rules `S-113…S-132` (`strategy/strategy_diverse_lib.py`,
2–5 indicators each, HTF-gated) are the **cleanest experiment in the repo**:
one fixed rule per strategy, no variant sweep, therefore **no selection bias**.

> **Result: 0 winning cells out of 120 at 2 bps.** Median trade count 1,624;
> `S-127` ran 4,834 trades; `S-125` 2,605.

They failed for the same reason as everything else: **cost × frequency**.

**Conclusion.** The intuition "we need to search in more directions" is
correct, but "more directions" was implemented as *more combinations of the same
indicator pool*. Those are **correlated hypotheses, not diverse ones** — and
they scored *worse* than the swept single-indicator families. **Diversity must
come from a different economic claim (classes I, J), not a new indicator
combination.**

---

## 5. The yardstick (the single source of truth)

**This section is normative.** Direction files, the runner, the checker and the
preregistration ledger all use it. Nothing else may restate it.

### 5.1 The degenerate-win problem (fix first)

`config/strategies.yml → oos.pass_criteria` currently sets a **ceiling**
(`max_trades_per_year: 54`) and **no floor**. A strategy that trades *once* in
5.5 years is trivially ≈ buy-hold and "beats" it by a rounding error.

Measured across all 83 winning cells in the sweep artifacts:

```
17 of 83 wins (20 %) come from strategies with <= 2 trades
 9 of those have an edge < 1 %   (i.e. they simply under-invested at the end)
```

**Concrete case — `s109 / ema_gate`** counts as "beats buy-hold on 2 instruments":

| Instrument | Window | Strategy | Buy-hold | Edge | Trades |
|---|---|---:|---:|---:|---:|
| BTC_USD | full | +1510.62 % | +1538.05 % | **−27.4 %** | **1** |
| XAU_USD | full | +112.25 % | +113.27 % | **−1.0 %** | **1** |
| XAU_USD | last_12m | +34.54 % | +34.41 % | **+0.13 %** | **1** |

One trade, in the market almost the whole time → misses the final close by a
rounding error → "wins". This is the `S-06` BTC-only beta artifact wearing a
different hat.

**S-55 is partly the same issue:** its `XAU last_12m` win is **+0.6 % on 4
trades**. Its only real margin is `BTC full +246.7 %`.

### 5.2 The corrected criteria (proposed — needs owner sign-off, §10)

Add to `config/strategies.yml → oos.pass_criteria`:

```yaml
    # --- floors (fix the degenerate-win hole) ---
    # A strategy cannot "beat" buy-hold by barely trading. These are floors,
    # not preferences: the ceiling above stops cost x frequency, the floors
    # stop a 1-trade strategy from matching buy-hold by rounding error.
    # Evidence: 17 of 83 winning cells (20 %) came from <= 2-trade strategies;
    # s109/ema_gate "passed" both windows with 1 trade and a +0.13 % edge.
    min_trades: 10                # a cell needs enough trades for its edge to mean anything
    min_exposure_pct: 20         # and enough time in the market to be a strategy, not a fluke
    min_edge_pct: 5.0            # and a margin that is not a rounding error
```

And, for classes C/D where the hypothesis is *"keep the return, cut the
drawdown"* rather than *"beat the return"*:

```yaml
    # --- risk-adjusted comparator (classes C/D) ---
    # The engine already computes buyhold_sharpe_weekly and
    # buyhold_max_drawdown_pct (commit 4b8ab26) but NO pass criterion uses them.
    # A long-only rule that survives a choppy regime and sits out a crash can be
    # genuinely valuable WITHOUT beating raw return - a claim the current bar
    # cannot express, which is why 132 strategies all failed the same way.
    risk_adjusted:
      min_sharpe_weekly_ratio: 1.0   # strategy sharpe_weekly >= buyhold_sharpe_weekly
      max_drawdown_ratio: 0.75       # strategy maxDD <= 0.75 x buyhold maxDD
```

### 5.3 Where the criteria live in code

`strategy/schema.py::oos_pass_fields(rows, min_instruments, max_trades_per_year)`
is **already** the shared definition used by both the runner and
`check_results.py` (X13). The floors and the risk-adjusted comparator must be
added **there**, not in a direction file, so that:

- the in-sample bar (Step 6 of `WORKFLOW.md`) and the OOS bar use **one**
  definition;
- `check_results.py` re-computes the verdict from the committed cells with the
  same code the runner used;
- the checker can enforce `min_trades` / `min_edge_pct` on **committed in-sample
  results** too, which retroactively re-labels `s109/ema_gate` and weakens
  `S-55` — that is the point.

### 5.4 Re-evaluation required after the floors land

| Strategy | Before | After (expected) |
|---|---|---|
| `s109 / ema_gate` | "passes both windows" | **fails** (1 trade < `min_trades: 10`) |
| `S-55 / looser` | in-sample finalist candidate | **much weaker** — `XAU last_12m` +0.6 % on 4 trades fails both floors; only `BTC full +246.7 %` survives |

---

## 6. Dead families and rejected strategies (machine-enforced)

### 6.1 Closed families

`config/strategy_plan.yml → closed_families` holds the families that were
measured **deeply enough and did not produce a single real win**. A new
strategy ID in a closed family is **refused** by the checker, with the group's
measured tally printed.

**Closure rule (both criteria):** `groups >= 30` **and** `real_win_rate <= 0.05`.
The first criterion is a depth requirement — a family with 16 groups and no
wins is *unmeasured*, not dead. The second is the result. 13 families qualify,
holding **584 of 1,360 groups = 42.9 %** of the measured search budget.

(The broader set — **all 36 zero-win families**, 792 groups = 58.2 % — is
listed in §4.2; the shallower ones are recorded as `provisional_closed` in the
ledger until they reach 30 groups.)

```yaml
closed_families:
  # Closure rule (both criteria, not the rate alone):
  #   groups >= 30        (the mean across 52 families is 26.2 groups)
  #   AND real_win_rate <= 0.05   (fraction of groups with >=1 real win)
  # "real win" = a group where some instrument beat buy-hold with > 2 trades
  #              (the degenerate-win filter of §5.1).
  # These 13 families hold 584 of the 1,360 measured groups = 42.9 % of the
  # search budget. Re-derive with §11.3 / §11.4 — do not hand-maintain.
  - {family: "mfi",      timeframe: "5m", groups: 76, real_win_rate: 0.000, closed_at: "2026-10-31"}
  - {family: "atr",      timeframe: "5m", groups: 64, real_win_rate: 0.016, closed_at: "2026-10-31"}
  - {family: "willr",    timeframe: "5m", groups: 60, real_win_rate: 0.017, closed_at: "2026-10-31"}
  - {family: "ema",      timeframe: "5m", groups: 56, real_win_rate: 0.036, closed_at: "2026-10-31"}
  - {family: "roc",      timeframe: "5m", groups: 48, real_win_rate: 0.000, closed_at: "2026-10-31"}
  - {family: "stoch_d",  timeframe: "5m", groups: 44, real_win_rate: 0.023, closed_at: "2026-10-31"}
  - {family: "st_dir",   timeframe: "5m", groups: 44, real_win_rate: 0.000, closed_at: "2026-10-31"}
  - {family: "bar_clv",  timeframe: "5m", groups: 32, real_win_rate: 0.000, closed_at: "2026-10-31"}
  - {family: "dc_pos",   timeframe: "5m", groups: 32, real_win_rate: 0.031, closed_at: "2026-10-31"}
  - {family: "close",    timeframe: "5m", groups: 32, real_win_rate: 0.000, closed_at: "2026-10-31"}
  - {family: "stoch_k",  timeframe: "5m", groups: 32, real_win_rate: 0.000, closed_at: "2026-10-31"}
  - {family: "rsi",      timeframe: "5m", groups: 32, real_win_rate: 0.031, closed_at: "2026-10-31"}
  - {family: "er",       timeframe: "5m", groups: 32, real_win_rate: 0.000, closed_at: "2026-10-31"}
```

> A family may be **re-opened** only by an owner decision recorded in
> `decisions.md` with a rationale (e.g. "the class-I rework changes what
> `mfi` means").

### 6.2 The rejected-combinations table

`strategy/STRATEGY_REGISTRY.md` currently has **7** rows in
`## Rejected combinations — do not re-test without a new hypothesis`, and
**0** of the 101 newly rejected strategies. **That table is the only mechanism
that stops a future session from re-testing a dead idea.** The trial log
records *that* something was tried; the table records *what*, and what not to
repeat.

Populate one row per rejected strategy, reusing the reason already written in
its `trial_log.md` row:

```
| <indicator + timeframe + entry logic> (S-NN) | <one-line reason> | [<sweep doc>](docs/strategy_sweep_….md) |
```

---

## 7. The research protocol (B)

> **This file replaces the original "execution process / parallelism" framing.**
> Parallelism is an implementation detail *inside* the protocol, not a goal.
> See §7.6 for why.

### 7.1 Pre-registration (machine-enforced)

**Nothing may be executed that is not pre-registered.** Today this is a human
convention only — there is **no** `registered_at`, no `pre.regist*` and no
"registered before the run" check anywhere in the code.

`config/strategy_plan.yml`:

```yaml
version: 1

# --- the preregistration ledger (APPEND-ONLY) ---
# One entry per strategy that MAY be executed. The checker refuses to run a
# strategy that has no entry here, and refuses an entry whose registered_at is
# later than the run date (i.e. a strategy "registered" after it was already
# run is a protocol violation, not a bookkeeping detail).
preregistrations:
  - id: S-133
    class: C                       # A..J, from docs/plan/02_taxonomy.md
    registered_at: "2026-10-31"    # date the hypothesis was fixed, BEFORE any run
    hypothesis: >-
      Long only while hv_120 is in its lowest decile AND close > ema_120;
      exit when hv_120 leaves the decile.
    expected_trade_band: [8, 60]   # trades/yr expected on the primary instrument
    direction: "docs/plan/directions/C_volatility_state.md"
    status: OPEN                   # OPEN | CLOSED | BLOCKED
```

**Enforcement (to be added to `scripts/check_results.py`):**

- a strategy in `config/strategies.yml` with a committed results directory must
  have a `preregistrations` entry → else **FAIL**;
- the entry's `registered_at` must be ≤ the trial-log date of its run → else
  **FAIL** (this is what makes "pre-registered" mean something);
- the entry's `class` must be a known class → else **FAIL**;
- a `CLOSED` entry may not be executed again → else **FAIL**.

### 7.2 Per-class budget

Each direction has a **hard cap** on the number of hypotheses it may register.
The cap is part of the direction file (§8) and is enforced by the checker
(counting `preregistrations` entries with that `class`).

Rationale: 132 strategies and 720 configurations produced **two** defensible
candidates, one of which is degenerate. Without a cap, a direction becomes an
unbounded sink — the failure mode that produced 58 % waste.

### 7.3 Cadence — a mandatory analysis gate between batches

**All eight batches so far ran in a single session on 2026-10-30.** The
filenames (`iterations_2026-10-30` … `iterations_2026-11-07`) are mechanically
incremented labels, not real dates. There was **no analysis gate between
batches**: batch N+1 started immediately after batch N.

**New rule:** a batch may start only when the previous batch has a written
analysis recorded in `docs/plan/01_research_protocol.md` (or a per-direction
file) that states, for each open class:

1. the per-family hit rate measured on that batch;
2. which families were **closed** as a result (appended to
   `closed_families`);
3. what the next batch will test, and why.

**No batch may exceed the remaining budget of its class.**

### 7.4 One pre-registered rule per hypothesis beats an 8-variant sweep

The 8-variant sweep buys 8 correlated configurations per hypothesis. The same
budget spent on 8 **distinct** hypotheses buys 8× the evidence.

**Prefer:** one pre-registered rule, evaluated as-is.
**Acceptable:** a variant sweep **only** when the variants are *materially*
different mechanisms (e.g. `onset_only` vs `hold_through`), not threshold
retunes — and the selection must be made **before** seeing the results, by
registering the primary variant up front.

The `S-109` report already does this correctly for `S-113…S-132` ("Fixed rule;
selected config/variant: … treat its performance as selection-biased"). Make
that the default.

### 7.5 Stop rules

A class is **closed** when either:

- its hypothesis budget is exhausted without a candidate that passes the
  §5 yardstick; or
- its measured per-family hit rate is 0 % over ≥ 100 groups (→ `closed_families`).

A class is **BLOCKED** when it needs an owner decision (e.g. class I needs a
new benchmark definition; class J needs an engine change).

### 7.6 Parallelism — an implementation detail, and a trap

**Compute is not the bottleneck.**

```
one batch = 2,160 cells, 12 workers, ~1,232 s  ≈ 21 min
all eight batches ≈ 2–3 h of wall time
```

**Parallelism in a search problem is not free.** It multiplies the number of
hypotheses tested, which multiplies the number of *chance* winners. Running
10× more hypotheses in parallel makes the selection-bias problem **10× worse**,
not better. Therefore:

> **Parallelism may only be increased after the protocol in §7.1–§7.5 is
> machine-enforced.** Until then, a larger worker count is a correctness risk.

**The legitimate space-for-time trade here is memory for I/O.** The sweep
harness re-reads the parquet and re-runs the backtest for **every** cell:

```
per strategy: 8 variants x 3 instruments x 2 windows x 3 cost tiers = 144 cells
               -> 144 parquet reads + 144 backtests
               -> only 6 unique (instrument, window) frames are needed
```

`run_matrix.py` already splits build-from-run so a frame can be reused across
cost tiers; the sweep harness does **not**. Caching the loaded frame per
`(instrument, window)` and reusing it across variants **and** cost tiers would
cut reads ~24×.

**But be honest about the payoff:** the bar-by-bar backtest loop dominates
(~6.8 s CPU per cell; a parquet read is ~5–10 % of that), so the realistic
saving is **~20–30 %**, at a cost of ~400 MB RAM for the cached frames.
**This is a rounding-error optimisation next to killing the 58 % dead budget.**

**The real lever is the budget, not the CPU.**

---

## 8. The direction files

### 8.1 Template (every direction file uses exactly this structure)

```markdown
# Class <X> — <name>

## Hypothesis
<the economic claim, in one paragraph>

## Why it is worth trying
<measured evidence: family hit rates, cell counts, from the sweep artifacts>

## How it could be falsified
<the explicit condition under which this class is dead>

## Budget
Maximum <N> hypotheses (enforced against `preregistrations` entries with class <X>)

## Criteria
REFER TO docs/plan/02_taxonomy.md §5 — do not restate the bar here.

## Preregistration
Hypotheses live in `config/strategy_plan.yml` (class: <X>). This file does not
list them.

## Status
OPEN / CLOSED (date) / BLOCKED (awaiting owner decision — see decisions.md)
```

### 8.2 The five direction files, with their content

| File | Class | Hypothesis | Evidence | Falsified when | Budget |
|---|---|---|---|---|---|
| `C_volatility_state.md` | C | Volatility expansion precedes continuation | `hv` 22.9 % (11 real wins, 48 groups), `bb_width` 37.5 % (6 real, 16 groups) | 20 hypotheses with no candidate passing §5 | 20 |
| `D_trend_strength_regime.md` | D | Only trade when the market is trending | `adx` 28.6 % (8 real wins, 28 groups), `chop` 31.2 % (5 real) | 20 hypotheses with no candidate passing §5 | 20 |
| `E_calendar_session.md` | E | Intraday / weekly effects exist | `dow_sin` 28.1 % (9 real wins), **0 degenerate wins** | the placebo test (§8.E) fails | 10 (incl. placebo) |
| `I_asymmetric_neutral.md` | I | The *spread* between instruments, not the direction | never searched; 110/132 strategies are long-only | 20 hypotheses with no candidate passing §5 | 20 |
| `J_position_sizing.md` | J | The edge is *how much* to hold, not *when* | engine fixes `UNIT_SIZE = 1.0`; no sizing exists | 20 hypotheses with no candidate passing §5 | 20 |

#### 8.E — the calendar placebo test (do this before trusting `dow_sin`)

`dow_sin` shows a 28.1 % real-win rate (9 of 32 groups) with **zero** degenerate wins. That is either
a genuine session effect (well documented in FX) or a fitting artifact.

**The cheap discriminator:** re-run the same rule on a **shifted calendar** —
use `dow_sin` of bar *t−1*, or permute the weekday labels. A real calendar
effect stays attached to the calendar; an artifact moves. If the shifted
version performs as well, the class is an artifact and is closed.

#### 8.I — asymmetric / market-neutral

The engine already supports shorts (`long_only=False`), but only **22 of 132**
strategies use them, and the long-only benchmark is `BTC +1,288 % / EUR +3 %`.
The natural experiment: **long the instrument with the stronger relative
regime, short the weaker** — a cross-sectional spread that removes the BTC
beta domination from the benchmark.

This directly attacks the failure mode that produced every "winner" so far.
It needs **no new features** — only a different comparison baseline than the
current per-instrument buy-hold. That baseline change is an owner decision
(§10, D-4).

#### 8.J — position sizing

`strategy/engine.py` fixes `UNIT_SIZE = 1.0`. There is **no position sizing at
all**. Volatility-targeted sizing (size ∝ 1/ATR) is the classic way to convert
a raw-return edge into a risk-adjusted one — and it is exactly what the
§5.2 risk-adjusted criterion would reward.

This requires the **only** engine change worth making: a per-bar size instead
of a fixed one, behind a flag, with a test proving that a constant-size run is
bit-identical to today's.

---

## 9. Infrastructure work-list (A)

> Full executable detail: `docs/repo_review_20261030_followup3.md` (Phases A–E).
> This section is the summary and the ordering rationale.

**Ordering rule: correctness before capacity. Never run a strategy batch on an
unstable harness, and never enlarge the harness while the correctness work is
open.**

| # | Work item | Severity | Why now |
|---|---|---|---|
| **A.1** | CI: add `if: always()` to the results-check step | 🔴 P0 | At `e6350d5` a failing self-test **skipped** the results check, hiding 4 real failures. Already fixed in `936f7b9` — verify it stays fixed. |
| **A.2** | Trial-log dates: 86 rows dated `2026-11-01…11-06` but every batch ran on **2026-10-30** | 🔴 P0 | The best-of-N audit trail is the repo's core honesty mechanism; fabricated dates destroy it. Derivation table in `repo_review_20261030_followup3.md` §C.1. |
| **A.3** | "Rejected combinations" table: 0 of 101 rejected strategies recorded | 🔴 P0 | The only mechanism that prevents re-testing a dead idea (§6.2). |
| **A.4** | X5 hole: `candidate` + `rejected` trial row passes silently | 🟡 P1 | Already fixed in `936f7b9` — verify. |
| **A.5** | Registry saturation guard (X15) | 🟡 P1 | Already added — verify thresholds still hold. |
| **A.6** | Generic test: a rule's **entry condition must be reachable** | 🟡 P1 | `S-03`'s "never co-occurs" failure passed every structural test; only real data revealed it. Add a synthetic test that satisfies each rule's entry conditions and asserts the state enters. |
| **A.7** | One source of truth for the evaluation windows | 🟡 P1 | `scripts/strategy_variants.py` still hardcodes `WINDOWS` and a `sid != "s17"` magic case. Import from `run_matrix`. |
| **A.8** | Second execution path: `s103–s112` ran via the sweep harness, `s113–s132` via `run_matrix` | 🟡 P1 | Two paths, two sets of bookkeeping. `run_matrix` owns the OOS gate, the ledger reservation and the trial-log row; the sweep harness bypasses all three. |
| **A.9** | 20 × 16-line adapter libs = 320 lines of boilerplate | ⚡ efficiency | One generic CLI + a registry entry instead. |
| **A.10** | 112 bespoke `strategy_*_lib.py` → expressible as `RuleSpec` | ⚡ efficiency | The declarative engine already expresses most of them. |
| **A.11** | Sweep-harness frame cache per `(instrument, window)` | ⚡ efficiency | ~20–30 % wall-time saving for ~400 MB RAM (§7.6). |
| **A.12** | 132 per-strategy report files | ✂️ simplify | Generate from one template; the sweep report already holds the numbers. |

---

## 10. Owner decision log (`docs/plan/decisions.md`)

Append-only. Every entry: date, decision, rationale, who, and what it unblocks.

```markdown
| # | date | decision | rationale | owner | unblocks |
|---|---|---|---|---|---|
| D-1 | 2026-10-31 | Add `min_trades` / `min_exposure_pct` / `min_edge_pct` to `oos.pass_criteria` | 20 % of all wins came from ≤ 2-trade strategies; `s109/ema_gate` passed both windows on 1 trade | ttrrei | §5 floors, S-55 re-evaluation |
| D-2 | 2026-10-31 | Adopt the risk-adjusted comparator (`sharpe_weekly` vs buy-hold, `maxDD` ≤ 0.75×) for classes C/D | The engine computes both but no criterion used them; 132 strategies all failed the same way | ttrrei | class C/D candidates |
| D-3 | 2026-10-31 | Close 13 families (groups ≥ 30 AND real-win rate ≤ 5 %) | 42.9 % of the 1,360-group search budget | ttrrei | new-family registration |
| D-4 | 2026-10-31 | *(pending)* Define the class-I benchmark (cross-sectional, not per-instrument buy-hold) | 110/132 strategies are long-only against a BTC-dominated benchmark | ttrrei | class I |
| D-5 | 2026-10-31 | *(pending)* Whether to promote S-55 to `finalist` after D-1/D-2 land | S-55's margins are +0.6 % (4 trades) and +246.7 % | ttrrei | the one-shot OOS |
```

**Open decisions that block work** are listed at the top of the file with their
status, so the next session does not have to re-derive them.

---

## 11. Appendix — reproducing every number in this document

### 11.1 The failure taxonomy (§4.1)

> **The sweep CSVs overlap.** Batch 2 re-ran `s08…s17` from batch 1, so 1,080
> rows are duplicates. **Deduplicate first** or every count is wrong (without
> it the same query reports 67.8 % cost × frequency and 15.9 % empty instead of
> 79.7 % / 1.1 %).

```python
import csv, glob
from collections import defaultdict

seen = {}
for f in glob.glob('strategy/results/iterations_*.csv'):
    for r in csv.DictReader(open(f)):
        if r['cost_bps'] != '2.0':
            continue
        try:
            r['edge'] = float(r['edge_vs_bh_pct'])
            r['tpy']  = float(r['trades_per_year'] or 0)
            r['n']    = int(r['n_trades'] or 0)
        except ValueError:
            continue
        seen[(r['strategy'], r['variant'], r['instrument'], r['window'])] = r
# -> 4,080 distinct cells

grp = defaultdict(list)
for r in seen.values():
    grp[(r['strategy'], r['variant'], r['window'])].append(r)
# -> 1,360 (strategy, variant, window) groups

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

### 11.2 The degenerate-win count (§5.1)

```python
DEGENERATE_MAX_TRADES = 2
wins = [x for v in grp.values() for x in v if x['edge'] > 0]
degenerate = [x for x in wins if x['n'] <= DEGENERATE_MAX_TRADES]
degenerate_and_tiny = [x for x in degenerate if abs(x['edge']) < 1.0]
# -> 83 wins, 17 degenerate (20 %), of which 9 have edge < 1 %
#    (for reference: 24 of ALL 83 wins have edge < 1 %)
```

### 11.3 The per-family map (§4.2) and the closure rule (§6.1)

Family key = the registry's *Key indicators* column, with the window suffix
stripped: `willr_60` → `willr`, `macd_hist_6_24` → `macd_hist`,
`st_dir_24_3` → `st_dir`.

**Both the numerator and the denominator must be GROUPS**
(`(strategy, variant, window)`), not cells. Counting cells in the denominator
while counting groups in the numerator inflates every rate by 3× and changes
the ranking — this is an easy mistake to make.

```python
import csv, glob, re
from collections import defaultdict

DEGENERATE_MAX_TRADES = 2

# 1. dedup the overlapping sweep CSVs, keeping only 2 bps cells
seen = {}
for f in glob.glob('strategy/results/iterations_*.csv'):
    for r in csv.DictReader(open(f)):
        if r['cost_bps'] != '2.0':
            continue
        try:
            r['edge'] = float(r['edge_vs_bh_pct'])
            r['n']    = int(r['n_trades'] or 0)
        except ValueError:
            continue
        seen[(r['strategy'], r['variant'], r['instrument'], r['window'])] = r

# 2. family key per strategy id
fam = {}
for line in open('strategy/STRATEGY_REGISTRY.md'):
    if not re.match(r'^\| S-\d+ \|', line):
        continue
    c = [x.strip() for x in line.split('|')]
    base = sorted({re.sub(r'_\d+(?:_\d+)?$', '', t)
                   for t in re.findall(r'`([a-z0-9_]+)`', c[4])})
    fam['S-' + c[1][2:].zfill(2)] = base[0] if base else '?'

# 3. group the cells, then count GROUPS per family
grp = defaultdict(list)
for r in seen.values():
    grp[(r['strategy'], r['variant'], r['window'])].append(r)

byfam = defaultdict(lambda: [0, 0])          # family -> [groups, real_win_groups]
for (s, v, w), cells in grp.items():
    base = fam.get('S-' + s[1:].zfill(2), '?')
    byfam[base][0] += 1
    if any(c['edge'] > 0 and c['n'] > DEGENERATE_MAX_TRADES for c in cells):
        byfam[base][1] += 1

for base, (g, w) in sorted(byfam.items(), key=lambda x: -x[1][1] / max(x[1][0], 1)):
    if w:
        print(f"{base:14} groups={g:4}  real_win_groups={w:3}  ({100 * w / g:5.1f}%)")
# -> bb_width 16/6 37.5% | chop 16/5 31.2% | adx 28/8 28.6% | dow_sin 32/9 28.1%
#    h1_rsi 16/4 25.0% | hv 48/11 22.9% | macd 32/4 12.5% | bb_pctb 44/3 6.8% | ...
```

### 11.4 The closed-family list (§6.1)

```python
# continues from §11.3 — `byfam` and `TOTAL_GROUPS` come from there

TOTAL_GROUPS = sum(g[0] for g in byfam.values())
MEAN_GROUPS  = TOTAL_GROUPS / len(byfam)          # 1360 / 52 = 26.2

closed = []
for base, (g, w) in byfam.items():
    rate = w / g if g else 1.0
    if g >= 30 and rate <= 0.05:
        closed.append((base, g, rate))
closed.sort(key=lambda x: -x[1])

for base, g, rate in closed:
    print(f"{base:14} groups={g:4}  rate={rate:6.1%}")
print(f"-> {len(closed)} families, {sum(g for _, g, _ in closed)} groups = "
      f"{100 * sum(g for _, g, _ in closed) / TOTAL_GROUPS:.1f}% of the budget")
# -> 13 families, 584 groups = 42.9 % of the budget
```

---

## 12. Execution order

**Do these in order. Do not skip ahead.**

| Step | Deliverable | Gate before the next step |
|---|---|---|
| **1** | `docs/plan/README.md` — entry point, read-order map, §3 precedence rules, status board | — |
| **2** | `docs/plan/02_taxonomy.md` — §4 + §5 of this document, expanded | §5 yardstick is stated once and only here |
| **3** | `config/strategy_plan.yml` — schema + the 10 closed families + an empty prereg ledger | `check_results.py` parses it |
| **4** | `docs/plan/01_research_protocol.md` — §7 | — |
| **5** | `docs/plan/00_infrastructure.md` — §9 (points at `repo_review_20261030_followup3.md` for the executable detail) | — |
| **6** | `docs/plan/directions/*.md` — 5 files, §8 template | each references §5, none restates it |
| **7** | `docs/plan/decisions.md` — log + the 5 pending decisions of §10 | — |
| **8** | Implement §9's work-list (A.1–A.12) | `pytest` green · `test_check_results.py` green · `check_results.py` PASS · CI green |
| **9** | Implement the §5 floors in `strategy/schema.py` + `config/strategies.yml` | S-55 and `s109/ema_gate` re-evaluated under the new bar |
| **10** | Implement the §7.1 preregistration enforcement in `check_results.py` | a strategy with no prereg entry is refused |
| **11** | Implement the §6.1 closed-family guard | a new ID in a closed family is refused |
| **12** | First new batch — **class I only**, under the new protocol | a written analysis gate (§7.3) before any batch after it |

**Explicitly out of scope for all twelve steps:** consuming the OOS holdout,
adding strategies to classes A/B/F/G/H, and the deferred items (walk-forward
harness, dedup engine, vectorised engine, YAML strategy schema).

---

## 13. What this plan explicitly does not do

| Item | Why not |
|---|---|
| Consume the OOS holdout | The holdout is a one-shot resource. It is only spent on a human-nominated finalist, after D-1…D-5 are settled. |
| Add strategies to classes A / B / F / G / H | Measured dead: 0–3.6 % hit rate; 36 families at 0 %. |
| Build a walk-forward harness / dedup engine / vectorised engine / YAML schema | Still deliberately deferred (`repo_review_20261028` §3). |
| Merge `strategy_rsi_lib.py` into the shared core | A state-leak bug was hit and reverted (`repo_review_20261028` §B3). |
| Change `oos.pass_criteria` unilaterally | §5.2 needs owner sign-off (§10, D-1 / D-2). |
| Promote S-55 | §5 changes the bar; re-evaluate under it first (§5.4). |
| Increase parallelism | §7.6 — it amplifies false positives until the protocol is machine-enforced. |
