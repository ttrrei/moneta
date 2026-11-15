# 02 — Execution Performance (space-for-time, parallelism, screening layer)

> Baseline commit `936f7b9`. Read `AGENTS.md` and `01_system_stability.md` (Phase S1–S3) first.
> Goal: make an evaluation cheap enough that **screening comes before rule writing**, and make
> every cell cacheable and parallelisable **without** touching the holdout discipline.

## 0. What the code does today (verified at `936f7b9`)

- `strategy/engine.py` builds positions with one Python call per bar:
  `desired = np.array([rule.desired_position(i) for i in range(n)], dtype=np.int8)`.
  Positions do not depend on the cost tier; `run_matrix` loops over `COST_TIERS = [0.0, 2.0, 5.0]`.
- Each strategy is a hand-written class in `strategy/strategy_*_lib.py`: 133 libs, 19,520 lines; 38 of them are
  exactly 165 lines (one template with different constants); 20 are 16-line adapters; plus 132 CLI wrappers.
- One sweep (20 strategies × 6 variants × 3 instruments × 2 windows) is ~720 position loops over up to ~570k bars.
- **There are no runtime measurements in the repo.** Everything below is gated on measuring first.

## 1. Rules specific to this file

- **OOS stays single-process and serial.** The ledger reserve (file lock) and `oos_token` are per process. No
  worker pool may ever touch a holdout read. `run_matrix` OOS must assert `workers == 1`.
- **No change to any committed number.** The new core must reproduce legacy results; equivalence tests decide.
- **Measure, then optimise.** Do not set a speed target before task E0 produces numbers.
- Cache and scratch directories are git-ignored and must never contain holdout data.

## 2. Decisions (defaults apply unless the owner edits this table)

| # | Decision | Default |
|---|----------|---------|
| P1 | Legacy libs | **Keep them while this file is executed** (deprecated; new work uses the spec-driven core). They are the reference for the equivalence proofs. Removal is `01_*` Phase S6, which needs the proofs from E1/E2, owner approval and no other session running. |
| P2 | Parallel unit | One **cell** = (config, instrument, window) for in-sample only. |
| P3 | Results format | Keep committed CSV/MD for the checker; add git-ignored parquet for bulk sweep output. |

---

## Phase E0 — measure the baseline  [LOCAL DATA]

- Add `scripts/perf_baseline.py`. For 3 representative strategies (a 5m threshold rule, a 1h rule, a
  long/short composite) time, per cell: parquet load, position generation, engine metrics, CSV/MD writing.
  Report wall time, peak RSS, and bars/second.
- Time one complete sweep (e.g. 20 strategies × 6 variants) end to end.
- Write `docs/perf_baseline.md` (numbers only, machine description, command used). Later tasks quote it.

## Phase E1 — vectorised weighted-position core (numba)

This is the keystone. It also unlocks vol-targeting, long/short, cross-sectional portfolios and path-dependent
exits (directions D-A/B/C need fractional weights and stateful exits, which the `{-1,0,+1}` engine cannot express).

- New module `strategy/core/sim.py` (numba, no Python callbacks in the hot loop):
  - inputs per instrument: `open`, `high`, `low`, `close`, target `weight[t]` (decided at close of bar `t`,
    applied at open of `t+1`, exactly the legacy convention), per-instrument cost parameters;
  - cost applied on **turnover** `|w_t − w_{t−1}|`; first **document and test the legacy cost semantics**
    (per side vs round trip — it is not stated in one place) and reproduce them exactly;
  - outputs: per-bar net return series, trades/turnover, and the legacy metric set (reuse `schema.py` fields;
    `sharpe_weekly`, `max_drawdown_pct`, `exposure_pct`, `mean_net_position_pct`, `buyhold_*`).
- Portfolio mode: `weights` as a `T × N` matrix across instruments sharing a calendar; single instrument is `N = 1`.
- Stateful exits (`strategy/core/exits.py`): ATR trailing stop, fixed stop, profit target (R multiple),
  time stop, break-even — implemented as a single-pass numba state machine over bars (needed by direction D-B).
- **Equivalence tests** (hard gate): on synthetic series and, **[LOCAL DATA]**, on S-01 … S-07 and 5 more
  legacy strategies, the new core with `{-1,0,+1}` weights must reproduce the legacy metrics to within `1e-9`
  relative tolerance (`n_trades` exactly). If any differ, stop and report.
- Keep `strategy/engine.py` untouched as the reference implementation.

## Phase E2 — spec-driven rule engine (replaces the template copies)

- A rule is **data**: `entry` and `exit` expressions over feature columns (`col op threshold`, `cross_up/down`,
  `and/or`, optional `gate`), `side`, `timeframe`, `hysteresis`. A single numba routine turns entry/exit masks
  into positions (`state = ffill(set on entry, clear on exit)`).
- Express the 38 template libs as spec entries; prove **byte-identical position arrays** against each legacy lib
  (all instruments, both windows) **[LOCAL DATA]**. Do not delete anything (P1).
- All new direction work (05–07) defines configs as specs generated from its registration block.

## Phase E3 — result cache ("make" for cells)

- Cell key = `sha256(config_hash, data_fingerprint(in-sample slice), core_code_hash, cost_model_hash, window)`.
  `core_code_hash` covers `strategy/core/*`, `strategy_lib.py`, the feature column versions used.
- Store results under `.cache/cells/` (git-ignored). On a hit, skip compute. `--no-cache` forces recompute.
- Tests: change of config, data fingerprint, core code or cost model each invalidates; identical rerun is a hit
  and returns byte-identical rows.
- The cache never stores or serves OOS cells.

## Phase E4 — data layout (space for time)

- Load each feature table **once per (instrument, timeframe)** into a memory-mapped Arrow/`.npy` store under
  `.cache/arrays/`; workers map it read-only. Precompute shared arrays once per instrument (returns, ATR windows,
  rolling vol) instead of per strategy.
- Add the used feature columns to the cache key via column-version hashes from the pipeline.
- Tests: values equal the parquet read; a changed parquet invalidates the store.

## Phase E5 — parallel in-sample runner

- `scripts/run_parallel.py` (or a `--workers N` flag on `run_direction.py`): process pool, `spawn` start method,
  default `workers = cpu_count − 1`, cell-level tasks, memory guard (refuse to start if the estimated footprint
  exceeds available RAM), failure isolation (a failed cell is recorded, the pool continues, exit code non-zero).
- **Deterministic merge:** sort results by `(strategy, variant, instrument, window, cost_bps)` before writing.
  Test: serial vs `N = 4` output files are byte-identical.
- Hard refusal: any request that includes the `oos` window with `workers != 1` exits with an error.

## Phase E6 — screening layer ("signal before rule")

- `scripts/screen_features.py --direction D-X`. For every feature column (and each registered transformation),
  every instrument, and each horizon `h` in the registration block:
  - target: forward return from `open[t+1]` to `open[t+1+h]` (the same fill convention as the simulator);
  - statistics: Spearman rank IC, top-minus-bottom bucket spread (bps), hit rate, number of **non-overlapping**
    observations; p-values from a **block bootstrap** (or HAC) because returns overlap and are autocorrelated;
  - cost adjustment: net spread = gross spread − round-trip cost from the cost model, assuming one trade per
    non-overlapping horizon; report the ratio gross-edge ÷ round-trip-cost;
  - multiple testing: Benjamini–Hochberg FDR across **all** tests of the direction; output q-values.
- Output a git-ignored parquet and a committed top-N CSV (`screen_<direction>_<date>.csv`) with the registered
  columns only. In-sample data only; the screening layer cannot read holdout data (S2.1).
- Tests: a planted signal is found; pure noise produces a false-discovery fraction `<= q` (seeded); features are
  causal (computed from data `<= t`; truncating the future does not change a row).
- Use DuckDB for the heavy aggregation (window functions over parquet), numpy for bootstrap.

## Phase E7 — outputs and generated artefacts

- Strategy reports, registry rows and CLI wrappers for **new** work are generated from the spec and result files
  (`scripts/generate_artifacts.py`); do not hand-write them. The checker verifies generated rows match results.
- Sweep outputs: bulk parquet (git-ignored) plus a compact committed summary CSV per direction; keep the checker's
  schema version rules (S3.3).

## Targets (set only after E0)

Write the numeric targets into `docs/perf_baseline.md` after E0, e.g. "complete sweep ≥ N× faster than baseline" and
"re-running an unchanged sweep ≥ M× faster (cache)". Do not invent targets before the baseline exists.

## Out of scope

- GPU / distributed compute; changing legacy committed results; parallel or cached OOS.

## Definition of done

- [ ] `docs/perf_baseline.md` exists (or the task is marked skipped for missing local data).
- [ ] Core sim passes the equivalence tests; legacy engine untouched.
- [ ] Spec engine reproduces the 38 template libs byte-identically (local data) — nothing deleted.
- [ ] Cache invalidation tests, array-store tests, serial-vs-parallel byte-identical test green.
- [ ] OOS parallelism refused by test; screening layer tests (planted signal, noise FDR, causality) green.
- [ ] pytest, self-test and checker green; ledger file unchanged.
