# Repo Review — 2026-10-28 (consolidated)

> **What this is:** a synthesis of the four AI review passes on the current
> tree (2026-10-28), plus the status of each finding **as of this commit**.
> It is the single active review going forward. `repo_review_20261026.md` is
> now historical; `repo_review_20261027.md` is its predecessor. If you are
> an AI session starting work here, **read this file first**.
>
> **Sources:** `legacy/review1.md` (CN, loop/completion audit), `legacy/review2.md`
> (EN, static source review), `legacy/review3.md` (CN, evidence-integrity audit,
> numpy probes on `engine.py`), `legacy/review4.md` (CN, loop-gap + cost-model
> audit). Note: `legacy/` is git-ignored, so on a fresh clone only **this file**
> survives — that is deliberate; this doc is the durable record.

---

## 0. State of the loop (verdict)

All four reviews agree on the headline:

- **The first half of the loop is closed and correct** —构思 → 注册 → 实现 →
  run the 18-cell matrix — and the P0 engine defects from the 10-27 review are
  genuinely fixed in code (short-cost direction, single rule-call per bar,
  `_span_years` bar cadence, DST via `zoneinfo`, 2h near-close, timeframe
  binding, fail-closed partial matrices, data fingerprints, trial-log ID
  normalisation). Review3 verified 7/7 engine behaviours with numpy probes.
- **The second half — 评估 → OOS → 定案 → 报告 — was never actually run.**
  All three strategies (S-01/05/06) were rejected **in-sample**, so the one-shot
  OOS lock was only exercised by unit tests, and the "why it lost" report step
  (WORKFLOW Step 5) was skipped for S-05/S-06. That is the load-bearing gap.
- **Killing bad ideas works.** All three strategies were correctly rejected
  for cost × frequency / single-instrument beta. That is *evidence the loop
  functions*, not evidence it is broken.

The one **fatal** finding (review3 §1) — S-01's committed results ran **over the
OOS holdout** — is now fixed (S-01 re-run on the capped window, registry /
trial_log / report realigned). The second fatal one (review2 §P0.2, review3 §2) —
the CLI had **no `--until`**, so the documented manual path *had* to cross the
holdout — is now fixed (all three CLIs expose `--until`).

---

## 1. Findings, and their status in this tree

Legend: ✅ fixed now · 🟡 fixed-with-caveat · ⬜ deliberately not done (see §3)

### A. Evidence integrity (the "fatal" class)

| # | Finding | Status |
|---|---|---|
| A1 | S-01 `full`/`last_12m` ran over the OOS holdout (2025-08-01+); numbers in registry/trial_log/report were contaminated (review3 §1) | ✅ S-01 re-run capped at `until: 2025-07-31`; registry, trial_log, report realigned |
| A2 | CLI had no `--until`; WORKFLOW manual path *had* to cross the holdout (review2 P0.2, review3 §2) | ✅ `--until` added to all three CLIs (`strategy_rsi`, `strategy_supertrend`, `strategy_ema_spread`) |
| A3 | `_check_oos_once` locks on the **label** (a `window=oos` row), not the data — a strategy already seen on the holdout could still "cleanly" run `--windows oos` (review3 §1, §8.11; review4 §2) | ✅ **Fixed (2026-10-28).** `_data_fingerprint` now binds the ledger to the *data* (holdout_start + row count + bar range + order-independent content hash of `(time, close)` over the holdout interval), not to path/mtime/rows. A rebuild of the same data — even to a new path — keeps the same lock key, so the once-per-dataset rule survives a rebuild. `_fingerprint_key` deliberately excludes path/file metadata. Covered by `test_oos_data_bound_lock` (rebuild-to-new-path case) in `tests/test_metrics.py`. |
| A4 | Registry/trial_log/report numbers must trace to the matrix | ✅ `scripts/check_results.py` enforces this (G5/W/X/S families); 9 previously-broken cells now PASS |
| A5 | "60/3 & 120/3 never beat buy-hold" claim had **zero evidence** (not in results/, trial_log, or any report) — violated G5 (review3 §7.1) | ✅ Removed. The registry row no longer cites un-run variants. If they are ever tested they get fresh S-IDs. |

### B. Reproducibility

| # | Finding | Status |
|---|---|---|
| B1 | `duckdb.connect()` in `strategy_lib.py` / `strategy_rsi_lib.py` had no `SET TimeZone`, so date bounds were read in local tz (review3 §4.1) | ✅ Both pinned to UTC. `run_matrix.py:172` does only a `count(*)` (no date filter), so it is left unpinned deliberately. |
| B2 | `requirement.txt` has bare package names; TA-Lib (ATR/SAR/RSI) drift would silently change every result (review3 §5, review4 §1) | ✅ **Fixed (2026-10-28).** `requirements.lock` (pip freeze) is committed and is the CI install source (`.github/workflows/ci.yml` `pytest` job installs `-r requirements.lock` only). |
| B3 | S-01 still uses its own `strategy_rsi_lib.py` `load_bars/make_bars`, duplicating the shared core — two places to fix any future bug (review3 §7.5, review4 §1) | 🟡 Acknowledged. Merging is **not** safe yet (a stateful-rule reuse was attempted and reverted for a state-leak bug). Left as-is; tracked. |

### C. The Sharpe metric (the one "policy" item)

| # | Finding | Status |
|---|---|---|
| C1 | Sharpe = `mean(tr)/std(tr)*sqrt(n_trades/span)` — it **rewards trade frequency** (same per-trade edge ×30 trades ⇒ Sharpe ×5.48 = √30), yet `engine.py` documented it as "comparable across strategies". That sentence is false (review3 §3, review4 §1, review1 §1.9) | 🟡 The **false docstring line is being removed/qualified now** (minimal fix). Changing the *formula* to a daily-equity Sharpe is **not** done — it is a policy decision (see §3). |

### D. Loop completeness (S-05/S-06)

| # | Finding | Status |
|---|---|---|
| D1 | S-05/S-06 had **no Step-5 report** and **no thin CLI** (review3 §6, §7) | ✅ Both `strategy/docs/strategy_supertrend_report.md` + `strategy_ema_spread_report.md` and `strategy/code/strategy_supertrend.py` + `strategy_ema_spread.py` created |
| D2 | S-06 "BTC-only +2402%" is long-only beta on a bullish BTC sample, not a cross-market edge (all reviews) | ✅ Stated plainly in the report §3 + registry; the number is **not** presented as a lead to retune |
| D3 | `trade_distribution` was computed but dropped from `summary.csv` (`DictWriter` `extrasaction="ignore"`) — "well-distributed" conclusion had no traceable source (review3 §7.4) | ⬜ **Open.** Computed, not persisted. Minor; queued with the summary schema. |

### E. Missing automation (the "safeguards, not over-engineering" class)

| # | Finding | Status |
|---|---|---|
| E1 | No CI; no machine check on registry/trial_log/results format — autopilot's biggest trust hole (review1 §四, review3 §5, review4 §1) | ✅ `scripts/check_results.py` (data-free, 16 self-test mutations, incl. X12 trial-log-timeframe) + `.github/workflows/ci.yml` added |
| E2 | No `requirements.lock` | ✅ Done (see B2) — `requirements.lock` committed and used by CI |

### F. Documentation drift

| # | Finding | Status |
|---|---|---|
| F1 | Test count: root `README.md` says 86, `docs/README.md` says 80 (review2 §4, review3 §4.5) | ✅ Reconciled and re-verified: all READMEs now state **104** (the current suite size, 2026-10-28; +1 for the OOS wiring E2E test). |
| F2 | `docs/README.md` read-order pointed at the obsolete 10-26 review (review2 §1, review4 §1) | ✅ Points at the consolidated 10-27 → now this file. |
| F3 | `supertrend.py` docstring still claimed "global warmup removes start-point dependence" (review3 §4.5, review4 §1) | 🟡 See §3 — the correct fix is a one-line honest note, not a code change. |
| F4 | `library/README.md:30` / `supertrend.py:20` same WARMUP_DROP overclaim (review3 §4.5) | ✅ **Fixed (2026-10-28).** Both now state honestly that dropping `WARMUP_DROP` leading rows *reduces but does not eliminate* start-point dependence (a fixed warmup is not proof of start-point independence). |

---

## 2. What the reviews got **wrong** / that I did not act on

To be transparent about what was *not* taken as a bug:

- **"Register S-07/S-08 for the 60/3 & 120/3 variants" (review3 §7.1).** These
  variants were **never run** — that is the whole problem; inventing registry
  rows for results that don't exist would be *fabrication*. Correct action was
  to delete the false claim (A5), not to back-fill rows.
- **"S-01 baseline is 944 trades / −21.58%"** (cited as the "regression" in
  several reviews). That figure is the **old, pre-cutoff** window — exactly the
  contaminated result A1 fixed. The current canonical baseline is the capped
  777-trade run.
- **`run_matrix.py` "18× redundant parquet scans" (review3 §4.2).** True, but at
  3 strategies and ~1s/instrument this is not a bottleneck; a caching layer
  would be premature. Left alone.
- **The `legacy/` "dead link" complaint (review4 §1).** `legacy/` is
  git-ignored by design; this file *is* the clone-surviving record. Not a bug.

---

## 3. Over-engineering verdicts (where all four reviews agree: DON'T)

These are explicitly **not** done, and that is the correct call at
"3 strategies, 0 survivors":

| Item | Why not |
|---|---|
| Strategy DSL / agent framework / multi-agent orchestration | 3 strategies; a DSL is pure overhead now |
| Vectorised / DuckDB-native backtest engine | current count is tiny; the event loop is fast enough |
| Walk-forward framework | no strategy has passed untouched validation yet — nothing to walk forward |
| Bulk-indicator / parameter explosion | already 305 feature columns; more = more data-mining surface, and the project admits it has no multiple-testing correction |
| Docker / packaging / a 4th maintainer guide | not needed |
| Real-market-data fixture in unit tests | synthetic deterministic cases already cover the contract |
| `new_strategy.py` scaffolder / expected-trades column / machine stop-condition checker | nice-to-haves; premature before a *single* clean end-to-end run exists |

**Do keep (safeguards, not over-engineering):** `check_results.py`, a
registry/results consistency check, minimal CI, `requirements.lock`, UTC pin,
one deterministic rule test per strategy, and result manifests.

---

## 4. Ranked plan (what to actually do, in order)

**Batch 0 — already in this commit**
1. ✅ S-01 re-run + registry/trial_log/report realigned (A1)
2. ✅ `--until` on all three CLIs (A2)
3. ✅ S-05/S-06 reports + thin CLIs (D1)
4. ✅ `check_results.py` + self-tests + CI (E1)
5. ✅ UTC pin on the two date-filtering connections (B1)
6. ✅ test-count + doc-link reconciliation (F1/F2)

**Batch 1 — next (cheap, high value)**
1. Remove the false "comparable across strategies" Sharpe line from
   `engine.py` docstring + `METRIC_FORMULAS` (C1) — **docstring only**, do not
   change the formula yet.
2. ✅ `pip freeze > requirements.lock` (B2/E2) — done; CI installs from it.
3. Add one deterministic strategy-rule test per strategy + a DST/timezone
   boundary test, reusing the `verify_engine.py` probe pattern (F3/D-series).
4. Fix the `supertrend.py`/`library` WARMUP_DROP overclaim — one honest line each (F4).

**Batch 2 — before any autopilot run**
1. Decide the Sharpe policy: relabel `sharpe_trade_rate` (and stop ranking by
   it) **or** switch to a daily-equity Sharpe. Do not leave it ambiguous (C1).
2. ✅ Hardened `_check_oos_once` to bind to data (holdout_start + row count +
   bar range + content hash), not just the `window` label (A3) — done
   (see A3; `test_oos_data_bound_lock`).
3. Decide: designate `run_matrix.py` the single canonical execution path and
   treat per-strategy CLIs as thin convenience wrappers (removes the "two
   execution paths" drift risk).
4. ✅ Ran the **untested** registered candidates S-02/S-03/S-04 (all rejected;
   see `strategy/trial_log.md` rows 4-6 and `STRATEGY_REGISTRY.md`). S-07
   (regime-gated slow trend) also tried and rejected.

**Explicitly deferred** — everything in §3, and the Sharpe *formula* change
until the policy in 4.2-1 is chosen.

---

## 5. Autopilot go/no-go

**No-go** until Batch 1 is complete *and* Batch 2-1 (Sharpe policy) is
decided, *and* Batch 2-2 (data-bound OOS lock) is in place. Everything else in
this doc is either done or deliberately deferred. The loop is safe for **one
human-supervised strategy at a time**; it is not yet safe for unattended batch
generation.
