# 01 — System Stability (technical hardening)

> Baseline commit `936f7b9`. Read `AGENTS.md` first. This file is the *technical* track:
> close the open gaps, make results reproducible, and make the research rules enforceable by
> machine. Nothing here adds strategies.

## 0. Baseline to verify before starting

- `python -m pytest tests/ -q` → 493 passed; `python scripts/test_check_results.py` → 37/37;
  `python scripts/check_results.py` → PASS.
- `strategy/oos_ledger.json` is exactly `{"version": 1, "consumptions": []}`. **It must be identical
  when you finish.**
- Open items carried over from earlier reviews (all still open at `936f7b9`): no `strategy/variants.py`,
  `config_hash` still hashes `rule_params = {}`, pin is optional, no freeze rule, no first-bar wrap-around fix.

## 1. Decisions (defaults apply unless the owner edits this table)

| # | Decision | Default |
|---|----------|---------|
| H1 | Holdout budget across directions | `oos.max_strategies_per_holdout` stays **1**. Directions compete: the owner nominates at most one finalist (across all directions) for `oos1`. Later finalists wait for `oos2` (a new holdout that accrues after 2026-10-22). |
| H2 | Success criteria per direction | Legacy `oos.pass_criteria` stays for legacy strategies only. New directions use `success_criteria` in `docs/plan/04_*.md` §3. Changing criteria is allowed **once, now**, because the ledger is empty (S2.2). After that they are frozen. |
| H3 | Physical split of the holdout data | **Yes** (S2.1). |

## Phase S1 — close the open items

### S1.1 Freeze legacy and require a direction · `config/strategies.yml`, `scripts/check_results.py`
- Config: `research: { legacy_freeze_after: "S-132" }`.
- Registry gains a `Direction` column. Every strategy id `> S-132` must name a registered direction id
  (e.g. `D-A`). Checker rule (next free code): fail on an id `> S-132` without a valid direction.
- Mutation cases: `S-133` without a direction → fail; with an unknown direction → fail.

### S1.2 `config_hash` must cover resolved parameters · `strategy/run_matrix.py`, new `strategy/variants.py`
- Today `config_hash(timeframe, entry_guard, {})` cannot tell variants apart, and `run_matrix` runs only the
  base parameters. Create `strategy/variants.py` as the **single resolver** `resolve(strategy_id, variant)
  -> {timeframe, entry_guard, rule_params}`. Legacy variants move here from `scripts/strategy_variants.py`
  (results must stay byte-identical **[LOCAL DATA]**); direction configs are generated from the registration
  block (see S4).
- `run_matrix --variant NAME` (default `base`); the hash receives the resolved params; hash + variant go into the
  ledger record at reserve time (additive fields only).

### S1.3 Pin mandatory for a finalist · `config/strategies.yml`, `strategy/run_matrix.py`, `scripts/check_results.py`
- `strategies.<id>.oos_variant` and `oos_config_hash`. OOS refuses unless both are present, `--variant` matches
  and the recomputed hash equals the pin. Remove the "absent pin → nothing refused" path.
- Checker: registry status `finalist` ⇒ both pin fields present and valid. Add `scripts/pin_finalist.py ID VARIANT`
  (prints the hash and YAML snippet; never edits status or ledger).
- Tests: two variants → two hashes; unpinned finalist refused; wrong variant refused; hash mismatch refused.

### S1.4 Consistency leftovers
- `strategy/strategy_rsi_lib.py` passes the raw `until` into SQL while `load_bars` passes the normalised value.
  Use `normalize_bound` for both so the gated value is exactly the queried value.
- First-bar wrap-around: some generated rules read `[j-1]` before the `j >= 1` guard
  (`strategy_aroon12spread_lib.py` ~line 57, `strategy_aroondnstoch_lib.py` ~line 65). Write a scan script that
  lists every affected `strategy_*_lib.py`, fix the generator templates (`scripts/_gen_*.py`) and patch only the
  affected libs. Verify no committed result changes; if one does, stop and report.
- Add `tests/test_rules_causality.py`: for every `strategy_*_lib.py`, perturb all bars at indices ≥ k and assert
  `desired_position(i)` is unchanged for all `i ≤ k`.

**Commit S1. Done when:** all above tests pass and the freeze/direction rules are enforced by the checker.

## Phase S2 — holdout hardening

### S2.1 Physical split of the holdout · `pipeline/`, `strategy/strategy_lib.py`  [LOCAL DATA]
- After the feature tables are built, write the rows with `time >= holdout_start` to a **separate** parquet
  (e.g. `data/holdout/ohlcv_<tf>_features_holdout.parquet`) and **remove them from the default in-sample
  parquet**. Features are computed on the full series first, so values are unchanged.
- The default loaders can no longer read a holdout bar at all; only `run_matrix` OOS (after a successful
  reserve) opens the holdout file. Keep `oos_token` / `assert_access` as defence in depth.
- Fingerprint both files into the ledger record. Tests: in-sample loader on the split table returns no row
  `>= holdout_start`; OOS loader reads only the holdout file; row counts add up to the previous full table.

### S2.2 Per-direction success criteria · `config/strategies.yml`, `strategy/schema.py`, `scripts/check_results.py`
- Add `oos.success_criteria_by_direction` (empty until directions are registered) and keep
  `oos.pass_criteria` as `legacy_long_only`. `schema.py` OOS adjudication selects the criteria by the
  strategy's direction. This is a one-time change made **before** any direction is registered; after the first
  registration commit the criteria are frozen (checker rule: criteria hash recorded in `trial_log.md`).

### S2.3 Holdout budget · `strategy/oos_ledger.json` semantics (no change to the empty file)
- Implement H1: the existing `max_strategies_per_holdout` check already refuses a second strategy; add a test that
  two different directions cannot both consume `oos1`.

**Commit S2. Done when:** split data verified, criteria selected per direction, ledger still empty.

## Phase S3 — reproducibility and safety rails

- **S3.1 Run manifest.** Every results directory gets a committed `manifest.yml` (not JSON — `results/**/*.json`
  is git-ignored): git sha, `dirty` flag, data fingerprint of the in-sample parquet, python and library versions
  (TA-Lib, numpy, pandas, duckdb, numba, pyarrow), command line, UTC start/end. Refuse to write committed
  results from a dirty tree.
- **S3.2 Determinism.** Same cell run twice ⇒ byte-identical CSV rows. Test it. Fix seeds anywhere randomness is used.
- **S3.3 Schema versioning.** `schema_version` in every summary CSV; the checker rejects unknown versions.
- **S3.4 Static checks in CI.** `ruff` (lint+format check) and `mypy` (start with `strategy/` core modules:
  `engine`, `run_matrix`, `oos_token`, `schema`, `strategy_lib`). Add `.pre-commit-config.yaml`.
- **S3.5 Coverage floor** for the load-bearing modules (`engine`, `run_matrix`, `oos_token`, `schema`,
  `scripts/check_results.py`): measure now, then fail CI below that measured value (never lower it).
- **S3.6 Failure visibility.** A failed cell is recorded (`error` column) and the run exits non-zero. No silent skips.
- **S3.7 Dependencies.** Pin Python version; add `numba` and `pyarrow` to `requirements.lock` (needed by
  `02_*`); CI installs from the lock only.
- **S3.8 CI history depth.** The registration checks (S4) need git history: set `fetch-depth: 0` in `ci.yml`.

## Phase S4 — registration enforcement (checker family `R`)

Direction files carry a machine-readable registration block (format in `04_strategy_master_plan.md` §6). Add:

| Code | Rule |
|---|---|
| R1 | Every registered direction file has a valid block (required keys, `max_configs`, explicit config grid). |
| R2 | A direction's first results commit is **later** than the commit that introduced its registration file (git history order). |
| R3 | The registration file is unchanged since its introducing commit unless `version` was bumped in a dedicated commit. |
| R4 | The number of distinct configs recorded for a direction (`results/`, iterations, trial log) is `<= max_configs`. |
| R5 | Every recorded config of a direction is a member of that direction's registered grid. |
| R6 | `trial_log.md` has a `direction` field per row; running counts are per direction **and** global. |
| R7 | The global count of new-work configs is `<= research.global_config_budget` (default 200). |

- Add `scripts/run_direction.py --direction D-X [--dry-run]`: it reads the registration block from the committed
  file, refuses if the file has uncommitted changes or the block is invalid, and can only run configs in the grid.
  This is how "unregistered configs cannot run" is enforced in practice.
- Mutation cases for each of R1–R6. All must be detected.

**Commit S4. Done when:** all R-rules have a mutation case and a dry-run of an example registration passes.

## Phase S5 — cleanup that is safe now (no dependency on 02)

Cleanup is part of stability, not an afterthought: duplicated code, stale docs and dead paths are what let rules
drift (we have already seen pass criteria restated in three places and stale test counts in READMEs).

- **Archive one-off generators:** move `scripts/_gen_*.py` and `scripts/_variants_batch*.txt` to
  `scripts/archive/` (keep them: they document how the legacy libs were produced).
- **Docs:** keep only the latest `docs/repo_review_*.md`; move older ones to `docs/archive/`. Update `docs/README.md`
  as an index. Remove hand-typed counts that go stale (test counts, strategy counts) or generate them.
- **Single source of truth in docs:** `WORKFLOW.md`, `generated_strategy.md`, READMEs and registry headers must
  reference `config/strategies.yml` for thresholds instead of restating them. List every place that restates a
  number, then replace it with a pointer; the checker gets a rule that flags a restated threshold.
- **Dead code:** run `ruff --select F401,F841,F811` and `vulture` on `strategy/`, `scripts/`, `pipeline/`; delete
  only items with zero references and a green test run. List what you removed in the commit message.
- **Config tidy:** remove config entries and `.gitignore` lines that nothing reads.

## Phase S6 — retire the legacy per-strategy code (only after `02_*` E2 is proven, owner approves)

**Judgement behind this phase:** the repo carries ~133 libs (19,520 lines), 132 CLI wrappers and 38 per-strategy
reports for strategies that are all closed (direction L-0: `rejected` or `parked`). The *evidence* about them
(registry rows, trial log, `iterations_*.csv`, results directories) is valuable and must stay; the *code* that
produced it is a maintenance cost and a place for bugs to hide.

**Preconditions (all required):** `02_*` E1 equivalence tests and E2 byte-identical position proofs are green
for every legacy strategy; the owner has approved in writing; **no other AI session is running** (see AGENTS.md
rule 11); work happens on a branch and is merged only when CI is green.

1. **Tag first:** create the annotated tag `legacy-L0-final` on the last commit that still contains all legacy code.
   Document in `docs/legacy_reproduction.md` how to reproduce any legacy result from that tag.
2. **Keep (never delete):** `strategy/oos_ledger.json`, all OOS/holdout code, `STRATEGY_REGISTRY.md` rows,
   `trial_log.md` rows, `strategy/results/**` and `iterations_*.csv` evidence, the parked strategies S-55 and S-103
   until the owner closes them.
3. **Remove for closed L-0 strategies:** `strategy_*_lib.py`, `strategy/code/*.py` wrappers, per-strategy report
   markdown that only restates registry rows. Keep the spec-engine equivalents from `02_*` E2.
4. **Change the checker in the same commit:** the per-strategy artifact rules (library, wrapper, report existence)
   are required only for strategies that are not `Direction = L-0` with status `rejected`/`parked`. Add mutation
   cases both ways (an L-0 closed strategy without a lib passes; a non-legacy strategy without one fails).
5. **Replace tests:** per-lib rule tests become the spec-engine equivalence tests; keep every behaviour that was
   tested (entry/exit/first-bar/state) via parametrised spec tests.
6. **Accounting must not move:** add a test that the registry still lists 132 strategies, the trial log's
   configuration tally is still 827 configurations / ≥ 14,886 cells, and every `iterations_*.csv` is untouched.
7. One commit per step; the checker, pytest and self-test are green at every commit.

**Done when:** legacy libs/wrappers/reports are gone from the working tree, the tag exists, the accounting test is
green, and a legacy result can be reproduced from the tag following `docs/legacy_reproduction.md`.

## Out of scope

- Adding or running strategies; changing committed in-sample numbers; running any OOS.

## Definition of done

- [ ] Freeze and direction requirement enforced; `config_hash` covers parameters; pin mandatory; causality test green.
- [ ] Holdout physically separated (or skipped with a note if no local data); criteria selectable per direction.
- [ ] Manifests, determinism test, ruff/mypy, coverage floor in CI.
- [ ] R1–R7 enforced with mutation tests; `run_direction.py` exists.
- [ ] S5 cleanup done (archives, single-source docs, dead code); S6 done only after `02_*` E2 and owner approval.
- [ ] pytest, self-test and checker green; ledger file unchanged.
