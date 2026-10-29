# moneta — OOS Gate Hardening: Follow-up Fixes (2026-10-29)

> **For the reader.** This records the five issues found by the follow-up
> review of the Phase 1–3 OOS-gate work (this same date), in order of severity,
> and how each was fixed. The prior plan is `repo_review_20261029.md`; the
> earlier reviews are `repo_review_2026102{6,7,8}.md`. The holdout ledger was
> **never** consumed by any of this work — `strategy/oos_ledger.json` still
> reads `{"consumptions": []}`.

## Summary of fixes

| # | Issue (severity) | Fix |
|---|------------------|-----|
| 1 | **Bypass: the gate only lived in `run_matrix.py`; the data layer had no holdout check** (必须修) | `strategy/oos_token.py` — `strategy_lib.load_bars` (and S-01's own `load_bars`) now call `assert_access(until, token)` and **refuse** any window that reaches the holdout (`until=None` or `until >= holdout_start`) unless the caller holds an `OOSToken`. Only `run_matrix` mints a token, and only *after* a committed ledger reservation; `assert_access` re-verifies the token against the ledger so a fabricated token object cannot open the holdout. |
| 2 | **Renaming `holdout_id` (or shifting the window to overlap) reset the lock for every strategy** (必须修) | `_check_holdout_window` in `run_matrix.py`, run inside the gate before reservation. Same id → the dates must match every ledger record under that id (any drift is refused); new id → it must start **strictly after the latest `holdout_end`** already consumed (no overlap). |
| 3 | **The append-only ledger was never enforced (CI / checker)** (强烈推荐) | `scripts/check_results.py` gains **L1** (committed ledger is a *superset* of the base ledger — pass `--base-ledger`; the CI workflow now fetches the base branch's ledger and passes it) and **L2** (ledger ↔ trial_log agree: every adjudicated `oos` trial row has a ledger record, and every `completed` ledger record has an adjudicated `oos` trial row). |
| 4 | **A plain crash permanently burned the only holdout** (强烈推荐) | (a) `run_matrix.py --preflight` runs one small in-sample cell through the *same* code path **before** reserving, so an infrastructure failure fails before the holdout is touched. (b) The lock now **skips `voided` records**: a human, reviewed ledger edit (`reserved` → `voided`, commit explaining the crash + that no holdout number was seen) does not count as consumed, so a later corrected re-run is legal. Documented as **WORKFLOW Step 7.5**. |
| 5 | **Two independent end-date fields, and the comment was wrong** (推荐) | `windows.oos.until` is now documented as **derived** from `oos.holdout_end` (`until = holdout_end + 1 day`); the checker enforces this as **L0** (`until == holdout_end + 1 day`) so the two cannot drift; the incorrect config comment (which claimed the `until` bar was excluded) is corrected — `time <= until` actually *includes* the 00:00 bar of `until`. |

## Files changed / created

- **`strategy/oos_token.py`** (new) — the data-layer gate + token capability
  (stdlib-only; `yaml` imported lazily).
- **`strategy/strategy_lib.py`** — `load_bars` takes `oos_token` and calls
  `assert_access` before reading the parquet.
- **`strategy/strategy_rsi_lib.py`** — S-01's own `load_bars` + `run_rsi` take
  the token and call `assert_access`.
- **`strategy/strategy_{supertrend,ema_spread,regime_trend,rsi_1h,rsi_trend,squeeze}_lib.py`** —
  the per-strategy `load_*_bars` wrappers, `run_*` and the `run()` entry points
  thread `oos_token` through to `strategy_lib.load_bars`.
- **`strategy/run_matrix.py`** — mints the token only after `_reserve_oos`;
  passes it to `run()`; new `_check_holdout_window` (issue 2) called inside
  `_check_oos_once`; the once-per-strategy lock and D1 cap now skip `voided`
  records (issue 4); new `_preflight` + `--preflight` (issue 4).
- **`scripts/check_results.py`** — new `check_oos_end_field` (L0) and
  `check_oos_ledger` (L1/L2); new `--base-ledger` flag.
- **`scripts/test_check_results.py`** — 5 new mutation cases (L0, L1 ×2, L2 ×2);
  the fixture now copies `oos_ledger.json`; the X13 OOS cases add a matching
  ledger record so they test X13 (not L2).
- **`tests/test_metrics.py`** — new suite: data-layer gate (incl. the review's
  `load_bars(until=None)` must-raise test, against a real parquet), the window
  identity lock (4 cases), and the void flow (2 cases). 140 → **153** tests.
- **`strategy/WORKFLOW.md`** — new **Step 7.5** (preflight + the void
  invalidation flow).
- **`config/strategies.yml`** — the `windows.oos.until` comment corrected and
  `until` documented as `holdout_end + 1 day` (issue 5).
- **`strategy/code/*.py`** (7 CLIs) — `--until` help text now states an uncapped
  manual run is refused by the data-layer gate.
- **`.github/workflows/ci.yml`** — the results-check job now passes the base
  branch's ledger via `--base-ledger` (enforces L1 in CI).
- **`README.md`** — test count (120/140 → 153) and the strategy-layer
  description updated to mention `oos_token.py` and the data-layer gate.

## Verification

- `pytest tests/ -q` → **153 passed**.
- `scripts/test_check_results.py` → **28/28** mutation cases.
- `scripts/check_results.py` → **PASS** (0 failures).
- Ledger remains unconsumed: `strategy/oos_ledger.json` = `{"consumptions": []}`.
- End-to-end on real data: a direct `load_bars(until=None)` and a
  `since=2025-08-01..until=2026-10-23` (holdout) read are both **refused**
  without a token, while an in-sample `until=2025-07-31` read succeeds
  (415,820 bars, ending 2025-07-31). An OOS `--windows oos` attempt by a
  non-finalist is refused before any reservation, leaving the ledger empty.
