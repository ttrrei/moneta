# AGENTS.md — moneta (read this first, every session)

> Place this file at the **repo root**. It is deliberately short. Long documents are
> easy to skip; these rules are not negotiable and several are enforced by CI.
> Baseline when written: commit `936f7b9` (493 pytest, 37/37 self-test, checker PASS,
> `strategy/oos_ledger.json` = `{"version":1,"consumptions":[]}`).

## Hard rules

1. **Never run an OOS / holdout evaluation and never write `strategy/oos_ledger.json`.**
   Only the owner starts an OOS run. Tests use `tmp_path` + `monkeypatch`.
2. **Register before you run.** A strategy or sweep may only be executed if it is
   enumerated in a *direction file* (`docs/plan/05_*.md` … ) whose registration block was
   **committed before** the first result. No ad-hoc strategies, no "one more variant".
   New ideas go to `docs/plan/ideas.md` only (they cannot be executed from there).
3. **Legacy freeze.** The conventional-indicator search (S-01 … S-132) is closed. Do not
   add single/dual-indicator threshold strategies on 5m/1h.
4. **Do not change committed numbers.** New columns are allowed; existing values must stay
   byte-identical. Never edit a result file by hand.
5. **Do not weaken a check to make it pass.** Fix the code, the data, or a stale fixture.
6. **One source of truth.** Thresholds and criteria live in `config/strategies.yml` (and the
   registration blocks). Docs reference them; they never restate numbers.
7. **Before every commit** run, from the repo root:
   `python -m pytest tests/ -q`, `python scripts/test_check_results.py`,
   `python scripts/check_results.py`. All green. One commit per task group.
8. **No numbers without a source.** Every figure in a report must trace to a committed result.
9. **If anything is ambiguous or conflicts with the code: stop and ask.**
10. Tasks tagged **[LOCAL DATA]** need the git-ignored `data/` parquet. If it is absent,
    skip them, say so in your final message, and never fabricate results.
11. **One writer at a time.** Never run two AI sessions that can commit to the same branch.
    Before starting: `git fetch`, confirm the branch is up to date and no other session is mid-run.
    Work on a branch named `plan/<task>`; merge only when CI is green. Mass moves or deletions
    (cleanup, `01_*` Phase S6) require that no other session is running at all.
12. **Cleanup keeps the evidence.** Registry rows, `trial_log.md`, results and `iterations_*.csv`,
    the ledger and all holdout code are never deleted by cleanup. Code that only reproduces closed
    legacy strategies may be removed only through `01_*` Phase S6.

## Where things are

| Need | File |
|---|---|
| Technical hardening | `docs/plan/01_system_stability.md` |
| Speed, caching, parallelism, screening layer | `docs/plan/02_execution_performance.md` |
| New data / feature tables / cost model | `docs/plan/03_data_and_features.md` |
| Strategy master plan, success criteria, stage gates | `docs/plan/04_strategy_master_plan.md` |
| Directions (pre-registered) | `docs/plan/05_direction_slow_trend_voltarget.md`, `06_direction_exit_asymmetric.md`, `07_direction_cross_sectional.md` |
| Idea parking lot | `docs/plan/ideas.md` |
| Registry / trial log | `strategy/STRATEGY_REGISTRY.md`, `strategy/trial_log.md` |

## Order of work

`01 → 02 → 03 → (04 is the contract; read it before touching any direction) → 05/06/07`.
Do not start a direction before the infrastructure it lists under "Prerequisites" exists.

## Final message of every session

List changed files, any rule you had to interpret, every task you skipped (with reason), and
confirm the ledger file is unchanged.
