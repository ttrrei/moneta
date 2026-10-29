# moneta — OOS Gate Hardening: Consolidated Fix Plan

> **For the AI executing this file (VS Code).** This merges two independent
> reviews of the repo at commit `f3cb718` (2026-10-29) into one ordered plan.
> Read `docs/repo_review_20261028.md`, `strategy/WORKFLOW.md` and
> `config/strategies.yml` first. Then execute the phases **in order**.

## 0. Rules of engagement (read before touching anything)

- **Never run any OOS / holdout evaluation** (`--windows oos`) during this work.
  No strategy may touch the holdout until Phase 1 is complete and the owner says so.
  All tests must use `tmp_path` + `monkeypatch`; nothing in this plan may write a
  real ledger entry.
- **Do not rewrite the backtest engine.** Only the additive change in task 2.2 is
  allowed there. No existing metric value may change.
- **Do not change in-sample window semantics** (`windows.full`, `windows.last_12m`)
  or any committed in-sample number. If you find an off-by-one in them, report it; don't fix it.
- **One commit per phase.** Before every commit run, from the repo root:
  `.venv/bin/python -m pytest tests/ -q` and
  `python scripts/test_check_results.py && python scripts/check_results.py`.
  Both must be green.
- **Fail closed.** Wherever a guard cannot read its inputs (ledger, trial log,
  registry, config), it refuses to run. It never defaults to "allowed".
- If anything here is ambiguous or conflicts with the code, **stop and ask** rather than guess.
- Finish with a message listing every changed/created file and every decision defaulted.

## 1. Owner decisions (defaults apply unless the owner edits this table)

| # | Decision | Default used by the executor |
|---|----------|------------------------------|
| D1 | How many strategies may look at one holdout? | **1.** Once one finalist consumes a holdout, that holdout is spent for every other strategy. Further research needs a new, unseen holdout window under a new id. Implement as `oos.max_strategies_per_holdout: 1` in config so it is a one-line change later. |
| D2 | Holdout end date | The last **fully closed UTC day that exists in the data for all 3 instruments** at the time you edit. (A reviewer suggested `2026-10-24`; verify with `SELECT max(time)` per instrument on both the 5m and 1h parquet, and report the value you picked.) |
| D3 | Trade ceiling for OOS | Take the `> 300 trades` rule in `generated_strategy.md` §3/§5 (full-history span) and convert it to a **trades-per-year ceiling** using the full-history span. Write the resulting number explicitly in config with a comment showing the derivation. |
| D4 | Who promotes a strategy to `finalist` | A **human**, by editing the registry row. The machine only verifies consistency (task 1.6, 2.4). |

---

## Phase 1 — P0: the holdout can only be consumed once (MUST be done before any OOS use)

### 1.1 Fix the holdout window · `config/strategies.yml`
- Replace `oos.until: null` (and `windows.oos.until: null`) with the fixed date from D2.
  Give the holdout an explicit id, e.g. `oos.holdout_id: "oos1"`.
- Bars that arrive after the end date never enter this holdout; they belong to a future
  `oos2` window under a new id.
- Check how `until` is applied (`strategy/strategy_lib.py` uses `time <= ?` with a date-only
  string at UTC midnight, so the end *day's* bars after 00:00 are excluded). Document the
  exact convention in a config comment and cover it with a test. Note for the owner (do not
  change it): the existing in-sample `until: 2025-07-31` therefore leaves a one-day gap before
  `oos.since: 2025-08-01`. This is harmless (no overlap or leak) but should be reported.
- The OOS loader must apply both `since` and `until`.

### 1.2 Bind the lock to (strategy, holdout), not to data content · `strategy/run_matrix.py`
- A strategy id may consume a given `holdout_id` **once**. Rebuilt data, a new file path,
  appended rows or a restart must not matter.
- Apply D1: if `max_strategies_per_holdout` distinct strategies have already consumed this
  holdout, refuse any further strategy.
- Replace the current `ledger[sid] = entry` + `superseded` design with an **append-only
  `consumptions` list** (schema in 1.3). The chain-walking bug (`reserve(A)` → `reserve(B)` →
  `check(A)` was allowed) disappears because every record is checked.
- Keep "reserve before loading the holdout": a crash mid-run still counts as consumed.
  There is no CLI flag to undo this; the only override is a reviewed git commit of the ledger.
- The data fingerprint becomes an **audit field only**, not part of the lock key (see 2.3).

### 1.3 Make the ledger durable · `.gitignore` + new path
- Move it to `strategy/oos_ledger.json`. It must **not** match `strategy/results/**/*.json`.
  Verify with `git check-ignore -v strategy/oos_ledger.json` (expect no match; add a `!` exception if needed).
- Commit an initial file: `{"version": 1, "consumptions": []}`.
- Each consumption record: `strategy`, `holdout_id`, `holdout_start`, `holdout_end`,
  `reserved_at`, `status` (`reserved` | `completed`), `fingerprint` (audit), `manifest`.
- The old path `strategy/results/oos_consumption.json` is retired. If it exists, refuse to run and say so.

### 1.4 Fail closed on any bad input · `strategy/run_matrix.py`
- `_load_oos_ledger()` must raise `SystemExit` when the file is missing, unreadable, invalid JSON,
  or has the wrong `version`/shape. Remove the `return {}` fallbacks.
- `_check_oos_once()` must also raise when `strategy/trial_log.md` or the registry is missing or
  unparseable. Remove the `if not TRIAL_LOG.exists(): pass` branch.

### 1.5 Walk every record · `strategy/run_matrix.py`
- Even with the new list design, `_check_oos_once` iterates **all** consumption records, not just the latest.

### 1.6 A real finalist-only gate · `strategy/run_matrix.py`, `strategy/STRATEGY_REGISTRY.md`, `strategy/WORKFLOW.md`, `scripts/check_results.py`
- Introduce an explicit registry status **`finalist`** = "passed the in-sample bar, OOS pending".
  Status vocabulary becomes: `candidate · finalist · tested · parked · rejected`.
  - `finalist` is set (by a human, D4) only when no §5 stop condition triggered **and**
    total_return > buy-hold at 2 bps on ≥ 2 of 3 instruments on **both** `full` and `last_12m`.
  - `tested` is reached only by passing the single OOS evaluation. Update WORKFLOW Step 6/7 so
    the wording is no longer circular.
- `_check_oos_once` allows a run only if **all** hold:
  - registry status of the strategy is exactly `finalist`;
  - `config/strategies.yml` has an entry for it;
  - `trial_log.md` has in-sample rows (`full`, `last_12m`) with a real outcome (not `<TBD>`);
  - no earlier `oos` consumption (1.2) and no adjudicated `oos` row (existing label lock — keep it).
- `rejected`, `parked`, `candidate`, unregistered, or `<TBD>` strategies are all refused.
  S-01 … S-07 are all `rejected`, so none can touch the holdout.
- Reuse the existing registry/trial-log parsing in `scripts/check_results.py` or factor it into one
  small shared module. Do not duplicate the regexes.
- `check_results.py`: allow `finalist` in the status checks, and add a check that a `finalist`
  row's committed in-sample results really satisfy the bar above.

### 1.7 Tests (`tests/test_metrics.py` or a new `tests/test_oos_gate.py`) — each must pass
- ledger missing → refuse; ledger corrupt JSON → refuse; ledger wrong version → refuse.
- `trial_log.md` missing → refuse; registry missing/unparseable → refuse.
- strategy `rejected` / `parked` / `candidate` / unregistered / `<TBD>` in-sample row → refuse.
- `finalist` with valid in-sample rows and an empty ledger → allowed.
- `reserve(A)` → `reserve(B)` → `check(A)` → refuse; and the same with 3+ records.
- same strategy, same holdout, after the data file is rebuilt / path changed / rows appended → refuse.
- D1: a second *different* strategy on a consumed holdout → refuse (when `max_strategies_per_holdout: 1`).
- crash after `reserve` (no completion) → still refuses.
- the fixed-window boundary test from 1.1.

**Done when:** all of 1.1–1.7 are merged, tests are green, and the repo has a committed ledger file.

---

## Phase 2 — P1: machine-enforce the pass rule and strengthen the audit trail

### 2.1 Single source of truth for the criteria
- `config/strategies.yml → oos.pass_criteria` is the **only** definition. Make
  `WORKFLOW.md` Step 6 and `generated_strategy.md` §5 *reference* it instead of restating it.
- Make `respect_trade_ceiling` concrete: add the numeric `max_trades_per_year` (D3) and state
  which cells it applies to (all OOS cells).

### 2.2 Engine: signed average position (additive only) · `strategy/engine.py`
- The engine tracks a signed position but only exports `exposure_pct` (fraction of bars non-zero).
  Add **`mean_net_position_pct`** (time-weighted signed mean). If positions are always in
  {−1, 0, +1}, `mean |position|` equals `exposure_pct` — do not add a redundant field; document the equality.
- Add it to `METRIC_FORMULAS` and to the result dict/CSV schema.
- Tests: long-only, short-only, flat, mixed long/short. Assert no pre-existing metric changes.
- Report-only: it is shown next to buy-hold's +100% for a sanity check and is **not** a pass/fail gate.

### 2.3 Stronger data fingerprint (audit only) · `strategy/run_matrix.py`
- Hash `instrument, time, open, high, low, close, volume` (whichever exist; fail loudly if
  `open` or `close` is missing) over `[holdout_start, holdout_end]` only.
- Use DuckDB's 64-bit `hash()` with an order-independent aggregate (e.g. `sum(hash(...)::HUGEINT)`)
  instead of `mod(..., 1e9+7)`. The engine fills at `open[T+1]`, so `open` must be covered.
- Also record: row count, first/last bar, `sha256` of `config/indicators.yml`, the git commit of
  `pipeline/indicators.py`, and the TA-Lib version (so a feature-code change is visible).
- Test: changing only `open` changes the fingerprint; reordering rows does not.

### 2.4 OOS pass/fail computed and checked by machine
- `run_matrix` OOS output must write, into **committed** files (`summary.csv`, `matrix.md`),
  not only the git-ignored per-cell JSON: per-instrument beat-buy-hold flag at 2 bps,
  `instruments_beating` count, `mean_net_position_pct`, trade-ceiling check, and the overall `pass`.
- `scripts/check_results.py` (data-free; new check family `X13`, plus a self-test mutation case):
  - recompute pass/fail from the committed OOS CSV using `pass_criteria`;
  - require it to agree with the registry final status (`tested` if pass, else `rejected`)
    and with the trial-log `oos` row;
  - fail on trade count above the ceiling.
- Verify that the runner's OOS output directory (`<id>_oos`) is accepted by check X1
  (dir name == strategy id). A valid OOS directory must pass; a mislabelled one must fail. Add a mutation case.

**Done when:** a synthetic fixture OOS result (in the test fixtures, never the real ledger)
passes and fails correctly under the checker.

---

## Phase 3 — Sharpe and results schema cleanup (must be done before any cross-strategy ranking)

State today: `engine.py` already documents `sharpe` (trade-rate) as **not** comparable and
`sharpe_weekly` as comparable, and `matrix.md` prints both. The remaining work is labelling,
schema drift and docs.

- **3.1** In `matrix.md` headers, rename `Sharpe` → `Sharpe (trade-rate, not for ranking)` and
  keep `Sharpe (weekly)`. Keep the CSV column names unchanged. Add a line to WORKFLOW Step 6 saying
  cross-strategy ranking uses `sharpe_weekly` only.
- **3.2** Put the summary CSV field list in one dependency-free module (e.g. `strategy/schema.py`)
  used by both `run_matrix.py` and `scripts/check_results.py`.
- **3.3** Add a checker rule: every committed `summary.csv` header must equal that field list.
  (Currently S01, S05 and S06 are on the old schema without `sharpe_weekly` / `trades_per_year`;
  CI did not catch it.) Add a mutation case.
- **3.4** Regenerate the in-sample results for **all 7 strategies** after 2.2 and 3.1 so every
  committed `summary.csv` / `matrix.md` is on the new schema. **This needs the local parquet data
  (`data/` is git-ignored) — run it on the owner's machine.** Use the existing commands
  (`.venv/bin/python strategy/run_matrix.py --strategy s01` … `s07`), never with `oos`.
  Existing metric values must be identical; only new columns may appear. If any existing value
  differs, **stop and report**.
- **3.5** Update `docs/repo_review_20261028.md` (C1, Batch 2-1, A3, B2 and anything else now done),
  `docs/README.md` read-order, root `README.md` (test count, status), and the WORKFLOW /
  `generated_strategy.md` wording changed above, so the next AI session starts from the true state.

---

## Out of scope (do NOT do)

- Strategy DSL, multi-agent orchestration, vectorized/DuckDB-only engine, full walk-forward harness,
  extra indicators, or any rewrite of the backtest engine. These are over-engineering at 0 survivors.
- Changing the benchmark (raw buy-and-hold vs a risk-adjusted one). Decide this with the owner
  **before the first finalist enters OOS**, record it in `trial_log.md`, then freeze it.
- Merging `strategy_rsi_lib.py` into the shared core (a previous attempt was reverted for a state leak).

## Definition of done

- [ ] Phase 1 merged; a committed `strategy/oos_ledger.json` exists; every Phase 1 test passes.
- [ ] No `rejected` / `parked` / `candidate` / unregistered strategy can start an OOS run.
- [ ] The holdout has a fixed start **and** end; new market data cannot reopen it.
- [ ] Phase 2: pass criteria are config-defined and machine-checked; fingerprint covers OHLCV.
- [ ] Phase 3: all 7 results on one schema; checker enforces it; docs reflect reality.
- [ ] pytest and `check_results.py` green; final message lists changed files and defaulted decisions.

## Provenance (what was merged, for the owner)

- Both reviews agreed on: fixed `oos.until`, ledger out of `.gitignore` and fail-closed, finalist-only gate,
  walking the whole `superseded` history, `pass_criteria` as machine checks, stronger fingerprint, Sharpe labelling.
- Conflicts resolved: *chain walk vs. re-key* → both (re-key to (strategy, holdout) and walk all records);
  *"latest trial not rejected"* vs. *explicit eligibility* → explicit `finalist` status; *per-strategy lock*
  vs. *whole-holdout consumed* → D1 default of one strategy per holdout, configurable.
- Not adopted: the "birthday-bound" collision argument against the `mod 1e9+7` hash. The real weakness is
  missing `open` coverage, not hash width. The 64-bit hash is a cheap improvement, nothing more.
