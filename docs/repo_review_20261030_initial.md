# moneta — Follow-up Fix Plan #3 (baseline commit `e6350d5`)

> **For the AI executing this file (VS Code).** This plan comes from a review of
> commit `e6350d5` (strategies S-08 … S-27, the two sweeps, and the second round of
> OOS-gate fixes). Read `config/strategies.yml`, `strategy/WORKFLOW.md`,
> `strategy/oos_token.py` and `scripts/check_results.py` first. Execute the phases
> **in order**: A (make CI green), B (finish the OOS gate), C (fix the evidence).

## 0. Baseline you are starting from (verify first)

- `python -m pytest tests/ -q` → 265 passed.
- `python scripts/check_results.py` → **FAIL** (4 failures: S1, S2, S3, X8, all on `S-22`; plus warning G5).
- `python scripts/test_check_results.py` → **30/32** mutation cases pass. The two failing ones are
  `config strategy missing from the registry -> X3` and `OOS tested status on a failing holdout -> X13`.
- `strategy/oos_ledger.json` is `{"version":1,"consumptions":[]}`. It must still be exactly that when you finish.

## 1. Rules of engagement

- **Never run any OOS / holdout evaluation** (`--windows oos`). Tests must use `tmp_path` + `monkeypatch`
  and never write a real ledger entry.
- **Do not change any committed in-sample number.** New columns are allowed; existing values must stay
  byte-identical (verify with a diff before committing regenerated CSVs).
- **Do not weaken a check to make it pass.** If a check fails, fix the data or the stale fixture.
- **One commit per phase.** Before each commit run, from the repo root:
  `python -m pytest tests/ -q`, `python scripts/test_check_results.py`, `python scripts/check_results.py`.
  All three must be green (after Phase A they must stay green).
- Tasks tagged **[LOCAL DATA]** need the git-ignored `data/` parquet. If it is not present, skip those tasks,
  list them in your final message, and do not fake results.
- If anything here is ambiguous or conflicts with the code, **stop and ask**.
- Finish with a message listing changed files and every decision you defaulted.

## 2. Decisions (defaults apply unless the owner edits this table)

| # | Decision | Default |
|---|----------|---------|
| D5 | How to fix the 5m vs 1h buy-hold baseline mismatch | **Do not change the committed `full`/`last_12m` windows** (that would change S-01…S-07 numbers). Add a *common-window* mode to the sweep harness and report both views (task C1). |
| D6 | Add a risk-adjusted co-criterion to `oos.pass_criteria`? | **Not in this plan.** Add the metrics report-only (task C2). The owner decides before the first finalist enters OOS, records it in `trial_log.md`, then freezes it. |
| D7 | `S-22` has committed results but no report | Write the short report (task A1). Do not delete `strategy/results/S22/`. |
| D8 | Keep the `--skip-preflight` flag? | **Remove it** (task B3). |

---

## Phase A — make CI green and the registry honest

### A1. Fix the registry for S-08 … S-27 · `strategy/STRATEGY_REGISTRY.md`
- Every one of S-08 … S-27 is `candidate` in the registry but `rejected` in `strategy/trial_log.md`
  (rows 8–27). Set all 20 to **`rejected`**. Keep the Result/Report links to the sweep docs.
- `S-22` (the only one with `strategy/results/S22/`) currently fails S1/S2/S3 because of the stale
  `candidate` status; flipping it to `rejected` fixes those three.
- **X8:** write `strategy/docs/strategy_er_report.md` (follow the existing report layout, e.g.
  `strategy_ema_spread_report.md` or whichever sibling exists) and point S-22's Report cell at it.
  Base it only on numbers in `strategy/results/S22/` and the sweep CSV; invent nothing.
- **G5 warning:** S-22's Result cell quotes a number ("2026") that does not trace to a matrix cell. Reword it
  so every number in it appears in `strategy/results/S22/`.
- Run the checker after each edit. If flipping the other 19 to `rejected` triggers new checks that need a
  results directory, **do not generate 19 results directories**; stop and use task C5 instead.

### A2. Fix the two stale self-test fixtures · `scripts/test_check_results.py`
- `config strategy missing from the registry -> X3` appends **`S-09`** to the config, but `S-09` now exists in
  the registry, so nothing is missing. Use an ID that cannot exist (e.g. `S-99`).
- `OOS tested status on a failing holdout -> X13`: find out why it now exits 0 (the fixture probably relies
  on a registry/trial-log state that changed with the new rows) and repair the *fixture*. Confirm the real
  X13 logic still fails on a failing holdout by running the mutation by hand.
- Goal: **32/32** (or all cases, if you add more).

**Commit A. Done when:** `check_results.py` → PASS, self-test all green, pytest green.

---

## Phase B — finish the OOS gate

### B1. Timezone-offset bypass of the data-layer gate · `strategy/oos_token.py`, `strategy/strategy_lib.py`, `strategy/strategy_rsi_lib.py`
- Today `_window_reaches_holdout()` compares only `str(until)[:10]` as a date. An `until` such as
  `"2025-07-31 23:00:00-0500"` (= 2025-08-01 04:00 UTC) is treated as in-sample and allowed, while DuckDB
  interprets the offset and reads holdout bars. Verified: `assert_access("2025-07-31 23:00:00-0500", None)` is allowed.
- Fix by **normalising once and using the same value for the gate and the SQL**:
  1. Add `normalize_bound(value) -> str | None` in `oos_token.py`: parse date-only strings (midnight UTC),
     naive datetimes (treated as UTC) and offset-aware datetimes (converted with `astimezone(timezone.utc)`).
     Unparseable input → `SystemExit` (fail-closed). Return a canonical UTC ISO string.
  2. `_window_reaches_holdout` compares the normalised instant against `holdout_start` 00:00 UTC.
  3. `load_bars` (and the RSI loader) must pass the **normalised** `since`/`until` into the SQL, so what was
     gated is exactly what is queried.
- Tests (new): `"2025-07-31 23:00:00-0500"` and `"2025-07-31T23:00:00-05:00"` → refused;
  `"2025-07-31 20:00:00-0500"` (= 01:00Z Aug 1) → refused; `"2025-07-31 18:00:00-0500"` (= 23:00Z Jul 31) → allowed;
  `"2025-07-31"` → allowed; `"2025-08-01"` → refused; `"garbage"` → refused; `None` → refused.
- Check `strategy/run_matrix.py::_data_fingerprint` still counts exactly the bars the loader reads.

### B2. The "void needs no OOS output" check never fires in CI · `scripts/check_results.py` (L1c)
- It counts only `*.json` files under `strategy/results/<sid>_oos/`, but `strategy/results/**/*.json` is
  git-ignored, so a clean CI checkout has none.
- Make it count **any committed file** in that directory (`summary.csv`, `matrix.md`, anything), and also
  treat an `oos` row for that strategy in `trial_log.md` as OOS output.
- Add a mutation case: a `voided` record whose strategy has `strategy/results/S05_oos/summary.csv` → `L1` failure.

### B3. Remove `--skip-preflight` · `strategy/run_matrix.py`
- Preflight must always run before a holdout reservation. Remove the CLI flag. Keep an internal
  parameter only if tests need it, and never expose it on the command line.
- Update the docstring/WORKFLOW text that mentions the flag.

**Commit B. Done when:** the B1 tests pass, the B2 mutation fails as expected, and no CLI path can skip preflight.

---

## Phase C — fix the evidence the sweeps produced

### C1. Common-window comparison · `scripts/strategy_variants.py`, `scripts/strategy_variants_report.py`  [LOCAL DATA]
- **Finding.** Buy-hold differs by table: in both sweep CSVs BTC full-window buy-hold is **+1538.0%** for
  5m variants and **+1288.4%** for 1h variants (EUR_USD 3.1% vs 2.3%, XAU_USD 113% vs 110%). The loaded spans
  differ, so "edge vs buy-hold" is not comparable across timeframes. The published conclusion
  "1h is the best iteration for 9/10 (batch 1) and 10/10 (batch 2)" is therefore partly an artifact of the smaller 1h baseline.
- **Diagnose first.** For each instrument, print the first and last bar of the 5m and 1h feature parquet and the
  first row remaining after each strategy's `not_null_cols` filter. Write the result to
  `strategy/docs/baseline_mismatch_note.md`.
- **Fix (D5 default).** Add `--common-window` to the harness: per instrument, `since = max(first valid bar across
  the two tables)`, same `until`. Re-run the full sweep in that mode to **new** files
  (`iterations_<date>_common.csv`); never overwrite the originals. Make the report script print both views.
- Add a correction note to both sweep docs (do not delete the originals): state the baseline mismatch and the
  corrected ranking. Re-state the "1h is best" claim only if it survives the common window.

### C2. Buy-hold Sharpe and drawdown (report-only) · `strategy/engine.py`, `strategy/schema.py`
- Add additive fields `buyhold_sharpe_weekly` and `buyhold_max_drawdown_pct`, computed on the buy-hold equity
  curve with exactly the same formulas as the strategy's `sharpe_weekly` / `max_drawdown_pct`.
- Add them to `METRIC_FORMULAS`, the shared CSV field list in `schema.py`, and tests (monotonic series, a known
  drawdown, flat series). No existing metric value may change.
- Regenerate the committed results for S-01…S-07 [LOCAL DATA] and the sweep CSVs; verify existing columns are byte-identical.
- The report script gains columns: strategy Sharpe minus buy-hold Sharpe, and strategy drawdown / buy-hold drawdown.
  **Do not change `oos.pass_criteria`** (D6).

### C3. Count configurations, not only strategies · `strategy/trial_log.md`
- `n_strategies_tried_before` (26) counts strategies, but each of S-08…S-27 was evaluated with 6 variants, and each
  strategy's best variant was picked in-sample. Add a **separate** tally section to `trial_log.md` (outside the
  table the X4 parser reads) with: strategies tried, configurations tried (distinct `(strategy, variant)` pairs in
  `strategy/results/iterations_*.csv`, plus earlier hand-run variants where known), and a one-paragraph statement
  that the finalist bar is not corrected for multiple testing.
- Add a rule to WORKFLOW Step 6: the finalist's tally and the specific variant nominated must be written into
  the trial log before promotion.

### C4. Pin the exact config a finalist will run in OOS · `strategy/run_matrix.py`, `config/strategies.yml`, `strategy/oos_ledger.json` schema
- The sweeps use named variants in `scripts/strategy_variants.py`, but the OOS path is `run_matrix`. A finalist's
  OOS run must use exactly the nominated variant (timeframe, parameters, entry_guard).
- Add a `config_hash` (sha256 of the canonical JSON of timeframe + rule parameters + entry_guard) to the ledger
  record at reserve time, and make `run_matrix` refuse to start if the registry's pinned variant does not hash to
  the same value. Add tests with a synthetic strategy. This is additive: do not alter existing ledger semantics
  or the empty committed ledger.

### C5. Let the checker verify the strategies that have no results directory · `scripts/check_results.py`
- S-08…S-27 (except S-22) have no `strategy/results/<id>/`, so S1–S3 never evaluate them. Teach the checker to
  validate each `strategy/results/iterations_*.csv` (schema, no `error` values, every registered strategy from
  S-08 up has rows) and to evaluate S1–S3 for those strategies from the CSV (2 bps rows, `full` window).
- Add mutation cases: a `candidate` status on a strategy the CSV shows losing everywhere → `S2`;
  a CSV with a missing strategy → new check code (document it in the checker header).

**Commit C. Done when:** the common-window sweep files exist, the new fields are in the schema with tests, the trial
log has the configuration tally, `config_hash` is enforced, and the checker covers the CSV evidence.

---

## Out of scope (do NOT do)

- Changing `oos.pass_criteria` or the committed in-sample windows (D5/D6).
- Adding more strategies or more sweeps. The next step after this plan is a human decision on the benchmark,
  not another batch of rules.
- Rewriting the engine beyond the additive fields in C2.

## Definition of done

- [ ] `check_results.py` PASS; `test_check_results.py` all green; pytest green.
- [ ] All 20 of S-08…S-27 are `rejected` in the registry; `S-22` has its report.
- [ ] Offset-aware `until` values cannot reach the holdout; the gate and the SQL use one normalised value.
- [ ] A void with committed OOS output is caught in CI; `--skip-preflight` is gone.
- [ ] Sweep conclusions are restated on a common window; buy-hold Sharpe/drawdown are reported.
- [ ] Trial log shows configuration-level tallies; `config_hash` is recorded and enforced.
- [ ] `strategy/oos_ledger.json` is still `{"version":1,"consumptions":[]}`.
- [ ] Final message lists changed files, defaulted decisions, and any [LOCAL DATA] task not done.
