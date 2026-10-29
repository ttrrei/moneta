# Repo Review — 2026-10-29 (Follow-up 2)

> Round-2 fixes for the three follow-up reviews posted after `b5f10cf`.
> All issues are fixed; the holdout ledger is still
> `{"consumptions": []}` and the committed in-sample results are unchanged
> (byte-identical — the boundary fix is half-open **only** for the OOS
> window, so no in-sample cell had to be regenerated).

| Review | § | Severity | Issue | Status |
|---|---|---|---|---|
| 1 | 1.1 | 必须修 | Token usable after first consumption (reserved/completed/voided all granted reads) | ✅ fixed |
| 1 | 1.2 | 必须修 | Fail-open when `oos.holdout_start` is missing/unparseable | ✅ fixed |
| 1 | 1.3 | 必须修 | Void flow conflicts with append-only L1 (status in record key) | ✅ fixed |
| 1 | 1.4 | 必须修 | CI base-ledger check silently skipped (`git show main:` + `|| true`) | ✅ fixed |
| 2 | 2.1 | critical | `load_rsi_1h_bars` missing `oos_token` param → `TypeError` (in-sample too) | ✅ fixed |
| 3 | 3.1 | P0 | `_reserve_oos` not atomic — two concurrent processes can both pass D1 | ✅ fixed |
| 3 | 3.2 | P1 | `time <= until` includes the 2026-10-23 00:00 boundary bar | ✅ fixed |
| 3 | 3.3 | P1 | Preflight was optional (`--preflight`) | ✅ fixed |
| 3 | 3.4 | P1 | Record identity coupled to status + direct-push-to-main bypass | ✅ fixed |

## 1. What changed

### 1.1 Token gate now requires an *active `reserved`* record (review 1.1, 3.4)

**Before**: `assert_access` accepted tokens backed by `reserved`, `completed`
*and* `voided` ledger records — so after S-01 consumed the holdout, any
script borrowing the name `OOSToken("S-01", "oos1")` could re-read the holdout
indefinitely. `OOSToken` is a public class; nothing in the old code prevented
free construction.

**After**: `strategy/oos_token.py` rewritten.

- `OOSToken` is still public (it carries no secret), but it is now
  **checked against the ledger on every read** — a borrowed name without an
  *active* reservation is refused.
- A read is allowed only when the **latest** ledger status for
  `(strategy, holdout_id)` is `reserved` (the active window between
  `_reserve_oos` and `_complete_oos`). `completed` and `voided` both grant
  **no** read access — `create_token` also refuses to mint for either, so the
  run path never produces a token that outlives the reservation.
- `assert_access` additionally validates the *read window*: an in-sample
  `until` (< `holdout_start`) is allowed without a token; `until >=
  holdout_start` (or `None`) is a holdout read and requires an active
  reservation for the token's `(strategy, holdout_id)`.
- New tests: `test_completed_token_refuses_read`, `test_voided_token_refuses_read`,
  `test_holdout_read_window_at_boundary_needs_token`, and an updated
  `test_fabricated_token_without_ledger_record_refuses` (now covers both
  `create_token` and a hand-built `OOSToken`).

### 1.2 Fail-closed on missing/invalid holdout config (review 1.2)

**Before**: `holdout_start_date()` returned `None` when the field was missing
or unparseable, and `_window_reaches_holdout` treated `None` as "no holdout
to protect" — a read went through. Deleting or mis-typing one config field
disabled the entire data-layer gate.

**After**: `holdout_start_date()` **raises `SystemExit`** on a missing file,
missing `oos:` block, missing/invalid `holdout_start`, or missing `holdout_id`
(fail-closed). `assert_access` explicitly forces the boundary check for
`until=None` reads (where the earlier comparison didn't run it). New tests:
`test_missing_holdout_start_is_config_error`,
`test_missing_config_file_is_config_error`.

### 1.3 Void flow is now append-only-safe (review 1.3, 3.4)

**Before**: `_rec_key` included `status` in the record identity, so the
legal `reserved → voided` transition (the void flow documented in WORKFLOW)
looked to L1 like a "record removal" — the reviewer reproduced this.

**After** (`scripts/check_results.py`):

- `_rec_key` drops `status` — identity is now
  `(strategy, holdout_id, holdout_start, holdout_end)`. The append-only
  diff sees a `reserved → voided` change as the *same record with a different
  status*, not a removal.
- L1 adds a **status state machine**: a base `reserved` record may legally
  become `reserved | completed | voided`; a base `completed` record must
  still have a `completed` record remaining (terminal — no re-open); a base
  `voided` record must still have a `voided` record remaining (terminal —
  no re-running a voided holdout).
- **L1b** (new): a `voided` record must carry a non-empty `reason` — a void
  without a written reason is a backdoor.
- **L1c** (new): a `voided` record is only valid when **no** OOS output file
  exists under `strategy/results/<ID>_oos/` — "void a result that was read,
  then re-run" is the specific backdoor the reviewer flagged.
- WORKFLOW Step 7.5 (item 3) rewritten to describe the new void protocol:
  flip `reserved → voided` **and** add a `reason`; never void a reservation
  that produced a result; the identity is `(strategy, holdout_id, window)`.
- New self-test cases (all passing):
  `reserved -> voided with a reason is append-only-safe -> ok`,
  `voided record without a reason -> L1`,
  `voided record with OOS output files -> L1`,
  `completed record re-opened to reserved -> L1`.

### 1.4 CI base-ledger resolution now actually works (review 1.4, 3.4)

**Before**: `git fetch --depth=1 origin main` + `git show main:strategy/oos_ledger.json`
fails in a PR checkout (there is no local `main` branch); the failure was
swallowed by `|| true` + a silent "no baseline" fallback, so L1 was never
enforced. Pushes to main (this repo's actual workflow per `git log`) had no
baseline at all.

**After** (`.github/workflows/ci.yml`):

- **PR**: `BASE_BRANCH` = `github.event.pull_request.base.ref`, fetched as
  `origin/$BASE_BRANCH`, read via `git show origin/$BASE_BRANCH:strategy/oos_ledger.json`.
- **Push**: baseline = `github.event.before` (the commit *before* this one),
  fetched and read the same way — so a direct push to main is **diffed
  against the previous commit**, not skipped.
- If a baseline was *expected* but could not be obtained, the job now
  **fails** (fail-closed). Only a genuine bootstrap (base branch has no
  ledger file at all) skips L1, and says so on the log.
- Note: to fully close the "direct push to main" path, the GitHub repo
  should enable branch protection on `main` requiring PRs. The CI change
  makes the push path auditable (diffed against `github.event.before`), but
  branch protection is the real gate.

### 1.5 S-02 `TypeError` regression fixed (review 2)

**Before**: `strategy/strategy_rsi_1h_lib.py:40` — `load_rsi_1h_bars()`
declared **no** `oos_token` parameter, but the caller at line 88 passed
`oos_token=oos_token`. Both `run_matrix --strategy s02` and the S-02 CLI
crashed with `TypeError: load_rsi_1h_bars() got an unexpected keyword
argument 'oos_token'` *before* reading any data — in-sample included.

**After**: `load_rsi_1h_bars` now accepts `oos_token: object | None = None`
and forwards it to `strategy_lib.load_bars`. New regression test
`test_rsi_1h_accepts_oos_token_kwarg` calls the loader with the `oos_token`
kwarg (the exact call that used to raise) and asserts both the in-sample read
and the holdout-refusal path behave correctly.

### 1.6 Reserve is now atomic (review 3.1 — P0)

**Before**: `run_matrix` called `_check_oos_once()` then `_reserve_oos()`;
`_reserve_oos` loaded the ledger fresh and appended without re-checking the
D1 cap. Two concurrent processes could both pass the check and both append a
reservation, bypassing `max_strategies_per_holdout: 1`.

**After** (`strategy/run_matrix.py`):

- New `_LedgerLock` class: `fcntl.flock` on a side file
  (`strategy/oos_ledger.json.lock`) on POSIX; falls back to a process-local
  `threading.Lock` when `fcntl` is unavailable (still correct within a
  single process).
- `_reserve_oos` and `_complete_oos` now run their entire
  *load → re-validate → append/mutate → save* transaction under the lock.
- **Re-validation inside the lock**: `_reserve_oos` now re-checks the
  once-per-`(strategy, holdout)` rule *and* the D1 cap against the ledger
  as it currently stands, so a concurrent reservation that landed between the
  caller's earlier check and this lock is seen and refused.
- New test `test_reserve_oos_concurrent_only_one_wins` (2 threads, `Barrier`
  to release them simultaneously) — exactly one reservation succeeds and the
  ledger ends with one record.
- The pre-existing test `test_oos_gate_refuses_after_any_consumption_walk_all_records`
  previously depended on the old (buggy) `_reserve_oos` letting a second
  strategy through; it now appends the extra records directly to the ledger
  (a second strategy cannot reserve a D1=1 holdout by design).

### 1.7 Holdout read is half-open (review 3.2 — P1)

**Before**: `load_bars` used `time <= until` for every window. With
`windows.oos.until = 2026-10-23` (the day *after* the last fully-closed
holdout day 2026-10-22), the bound included the single 2026-10-23 00:00 bar
of the partial day. The engine fills entries at `open[T+1]`, so that one
boundary bar could affect the result.

**After**: `strategy/strategy_lib.py::load_bars` and the S-01 copy in
`strategy/strategy_rsi_lib.py::load_bars` now branch on the bound:

- **In-sample** reads (in-sample `until` < `holdout_start`) keep the
  inclusive `time <= until` — the committed 126 in-sample cells are
  **byte-identical** (no regeneration required).
- **Holdout** reads (`until >= holdout_start`) use the half-open
  `time < until` — the 2026-10-23 00:00 bar (and everything after it) is
  excluded. The data fingerprint in `run_matrix.py::_data_fingerprint` is
  made consistent (`time < holdout_until`).
- `strategy/oos_token.py::is_holdout_until(until)` is the single helper the
  loader uses to pick the branch; it fails closed on a missing/invalid
  holdout boundary.
- `config/strategies.yml` comment updated to describe the new half-open
  semantics for the OOS window (and the inclusive semantics for in-sample).
- `scripts/check_results.py::check_oos_end_field` (L0) docstring updated to
  reflect the half-open bound; the L0 rule (`until == holdout_end + 1 day`)
  is unchanged and still passes.
- New test `test_load_bars_half_open_excludes_until_day` builds a tiny
  parquet with bars on 07-30 / 08-01 / 08-02 and asserts the holdout read
  with `until=2025-08-02` returns only the 08-01 bar, while an in-sample
  read with `until=2025-07-30` returns the 07-30 bar.

### 1.8 Preflight is mandatory by default (review 3.3 — P1)

**Before**: `--preflight` was opt-in; forgetting it let a broken pipeline
reserve the holdout and then crash, burning the only holdout.

**After**: `run_matrix` for an OOS window runs the preflight **by default**
(one cheap EUR_USD/full@2bps in-sample cell through the *same* code path,
before reserving). To opt out, pass the new explicit `--skip-preflight`
flag — the CLI help text explains that the holder is then responsible for
having verified the pipeline independently. WORKFLOW Step 7.5 item 1
rewritten accordingly.

## 2. Verification

| Check | Before | After |
|---|---|---|
| `pytest tests/` | 153 passed | **161 passed** |
| `scripts/test_check_results.py` | 28/28 | **32/32** |
| `scripts/check_results.py` (real repo) | PASS | **PASS** |
| `strategy/oos_ledger.json` | `{"consumptions": []}` | `{"consumptions": []}` (unchanged) |
| `strategy/code/strategy_rsi_1h.py --until 2025-07-31` | `TypeError` | **runs, produces result** |
| `strategy/code/strategy_rsi_1h.py` (no `--until`) | `TypeError` | **gate-refused, exit 1** |
| `strategy/run_matrix.py --help` | `--preflight` | `--skip-preflight` |
| In-sample committed cells (126) | — | **byte-identical** (no regeneration) |

New tests added this round:

- `test_completed_token_refuses_read`
- `test_voided_token_refuses_read`
- `test_missing_holdout_start_is_config_error`
- `test_missing_config_file_is_config_error`
- `test_holdout_read_window_at_boundary_needs_token`
- `test_load_bars_half_open_excludes_until_day`
- `test_reserve_oos_concurrent_only_one_wins`
- `test_rsi_1h_accepts_oos_token_kwarg`
- 4 new self-test cases in `scripts/test_check_results.py` (void-flow)

## 3. Files touched

| File | Change |
|---|---|
| `strategy/oos_token.py` | Reserved-only gate, fail-closed missing config, window validation, `is_holdout_until` helper |
| `strategy/strategy_lib.py` | `load_bars` half-open for holdout reads |
| `strategy/strategy_rsi_lib.py` | `load_bars` half-open for holdout reads (S-01) |
| `strategy/strategy_rsi_1h_lib.py` | `load_rsi_1h_bars` accepts `oos_token` kwarg (S-02 regression fix) |
| `strategy/run_matrix.py` | `_LedgerLock`, atomic `_reserve_oos`/`_complete_oos`, preflight default-on, `--skip-preflight`, half-open `_data_fingerprint` |
| `scripts/check_results.py` | `_rec_key` drops status, L1 status state machine, L1b (reason) + L1c (no output), L0 docstring |
| `scripts/test_check_results.py` | 4 new self-test cases + `_ledger_json`/`_one_rec`/`_set_ledgers`/`_void_with_output` helpers |
| `tests/test_metrics.py` | 8 new tests (token, fail-closed, boundary, concurrency, S-02) + update of the "walk-all-records" test |
| `strategy/WORKFLOW.md` | Step 7.5 rewritten (preflight default, void protocol) |
| `config/strategies.yml` | OOS-window comment updated to half-open semantics |
| `.github/workflows/ci.yml` | PR + push baseline resolution, fail-closed on expected-but-missing baseline |
| `docs/repo_review_20261029_followup2.md` | This document |

## 4. Open items (not fixed here)

1. **Branch protection on `main`** — the CI change makes a direct push to
   main diff-able (against `github.event.before`), but the only way to
   *prevent* direct pushes is a GitHub branch-protection rule requiring
   PRs. That is a repo setting, not code; see
   https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches-about-branch-protection.
2. **Physical holdout split** (review 1's "更彻底的做法") — splitting the
   holdout rows into a separate parquet the in-sample path cannot read is a
   bigger change (new data layout, new loading path, new fingerprint). The
   token gate + ledger + half-open bound already close the concrete
   bypasses the reviewer demonstrated; the physical split is a
   defence-in-depth option for a later round.
