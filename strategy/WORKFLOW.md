# Strategy Workflow (execution playbook)

> **How to use:** an AI (or human) is given the task *"generate a strategy"*.
> It reads [generated_strategy.md](generated_strategy.md) for the *what*,
> then executes this file top to bottom. Every step has an action, a command
> (where applicable), a **gate** that must pass before continuing, and a
> defined failure path. Do not skip gates; do not continue past a failed
> gate on its own — follow its failure path.
>
> All commands run from the **repo root**, using `.venv/bin/python`.

## The loop at a glance

```
 ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
 │ 0 PREREQ     │ →  │ 1 SELECT     │ →  │ 2 REGISTER   │
 │ checks       │    │ & hypothesize│    │ (before code)│
 └──────────────┘    └──────────────┘    └──────┬───────┘
        ▲                                       │
        │                                       ▼
 ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
 │ 7 CLOSE OUT  │ ←  │ 6 EVALUATE   │ ←  │ 3 CODE + 4   │
 │ update docs  │    │ (gates)      │    │ RUN (protocol)│
 └──────┬───────┘    └──────────────┘    └──────────────┘
        │
        ▼
  registry holds one MORE verified fact
  → next run starts from step 1 with stronger constraints
```

## Step 0 — Prerequisites (once per session)

**Action:** verify the environment and data are ready.

```bash
ls data/ohlcv_5m_features/ohlcv_5m_features.parquet   # must exist (5m layer)
ls data/ohlcv_1h_features/ohlcv_1h_features.parquet   # must exist (1h layer — 1h strategies need it)
.venv/bin/python -c "import talib, duckdb, pandas"      # must not raise
.venv/bin/python -m pipeline.sanity_check && echo OK    # must print OK / exit 0
```

- **Gate G0:** all four succeed. A strategy on **either** timeframe must have
  *its* feature table present (B5: G0 previously only checked the 5m table, so a
  1h strategy would only fail at Step 4). If a feature Parquet is missing or
  sanity fails → **STOP.** Tell the user which pipeline stage to run
  (`load_data` → `aggregate_ohlcv` → `indicators`). Do not run multi-minute
  pipeline stages yourself without asking.
- **Note:** close any VS Code DuckDB panel before anything writes
  `data/metadata.duckdb` (single-user lock).

## Step 1 — Select idea & state hypothesis

**Action:**
1. Read the files in generated_strategy.md §1 (order matters).
2. List the registry rows. For your candidate, write one line:
   *"This differs from S-01..S-NN because <specific difference>."*
3. Write the **hypothesis** (one sentence) and the **expected trade count**
   range on the primary instrument over full history.

- **Gate G1:** the difference line names a concrete difference (indicator
  set, timeframe, or entry logic — not a threshold tweak). Hypothesis +
  expected trade count are written down.
- **Failure path:** no genuinely new combination is available → **STOP** and
  report: the registry is saturated for the current feature set. Suggest
  either (a) a feature-engine change (out of scope here) or (b) which
  rejected row could be re-opened with a specific new hypothesis, and ask.

## Step 2 — Register (BEFORE writing any code)

**Action:** edit `STRATEGY_REGISTRY.md`:
1. Add row `S-NN` (next free ID) with: name, timeframe, key indicators,
   entry logic, exit logic, side, status = `candidate`, expected trade count.
2. Add every key indicator to the *Indicator usage map* with `S-NN`.

- **Gate G2:** the file parses as a valid table (column count matches the
  header) and the usage map is consistent with the new row.
- **Failure path:** a duplicate is discovered at this moment → delete the
  row, go back to Step 1. (This gate exists so a duplicate can never reach
  a backtest and be mistaken for new evidence.)

## Step 3 — Implement

**Action:** create the strategy lib + CLI. Build the data loading, timeframe
guard, bar-frame build and run wrapper on the **shared core**
(`strategy/strategy_lib.py`) — do **not** re-implement the parquet load, the
B1 guard or the metric glue (references: `strategy_supertrend_lib.py`,
`strategy_ema_spread_lib.py`); only declare the signal rule and the columns it
reads. Then:
- Thin CLI: `code/strategy_<name>.py` with `--instrument --timeframe --since
  --parquet --cost-bps --json` (defaults: EUR_USD, **5m**, none, 2 bps). Use the
  shared engine (`strategy/engine.py`) for accounting & metrics — do **not**
  re-implement the event loop or the metric formulas.
- **Pin the table to the timeframe (B1).** `--timeframe 5m|1h` selects the
  matching feature parquet; the loader **must** verify the observed bar length
  (median `time` diff) matches the timeframe and **fail loudly** on a mismatch.
  A 1h strategy run on the 5m table produces plausible-but-wrong numbers that
  pass every gate — the loader must make that impossible. (Pattern:
  `strategy_rsi.py` → `detect_bar_seconds`.)
- Load via DuckDB filtered on `instrument` (pattern: `strategy_rsi.py`).
- Execution model: signal on closed bar T → fill at `open[T+1]`; cost applied
  at entry and exit.
- Print the standard JSON metrics block (generated_strategy.md §4.2).

- **Gate G3 (self-review, required):** re-read your own code and check:
  no `shift(-k)` / no same-bar fill; only whitelisted feature columns;
  only whitelisted windows; costs at both legs. Write the checks you
  performed into the report as a "causality checklist".
- **Failure path:** a gate-3 check fails → fix, re-check. If it uses a
  non-existent column → check `config/indicators.yml`, then
  `pipeline/indicators.py`; adapt the rule to existing columns (do not
  add features in this step).

## Step 4 — Run (mandatory protocol)

**Action (preferred — automated):** run the standard matrix in one command.
It reads the windows verbatim from `config/strategies.yml` (fixed anchor, B4 —
never "12 months before today"), runs all 18 cells, and persists per-cell JSON
plus paste-ready tables:

```
.venv/bin/python strategy/run_matrix.py --strategy s01            # S-01: 3 inst × 2 windows × 3 costs
.venv/bin/python strategy/run_matrix.py --strategy s01 --trial-row --hypothesis "<one line>"
```

Output → `strategy/results/<ID>/`: one JSON per cell, `matrix.md` (report tables),
`summary.csv` (flat). Add a new strategy by registering it in `run_matrix.py`
(`_STRATEGIES`), pointing at its `strategy_<name>_lib.py::run_<name>`.

**Manual equivalent** (for one cell / debugging): for each of EUR_USD, BTC_USD,
XAU_USD, pass the strategy's `--timeframe` (5m or 1h) so the loader picks the
correct table:
1. Full history:
   `.venv/bin/python strategy/code/strategy_<name>.py --instrument <SYM> --timeframe <TF> --cost-bps 0`
   … same with `--cost-bps 2` and `--cost-bps 5`
2. Last 12 months: same three commands with the **fixed anchor** from
   `config/strategies.yml` → `windows.last_12m` (`since` + `until`), **not**
   "12 months before today". A fixed anchor is what keeps every strategy — this
   run and the next — evaluating the *identical* span (B4). In practice, prefer
   `strategy/run_matrix.py --windows full last_12m` which applies the config
   bounds (including the `until` cap that keeps both windows in-sample)
   automatically instead of passing `--since` by hand.
3. If the strategy supports the B6 entry guard (`--entry-guard`), run the matrix
   both ways and record which is the reported baseline (S-01 baseline: **off**).

- **Gate G4:** 18 JSON blocks produced (3 × 3 × 2) without exceptions, each
  with `n_bars > 1000` for the full-history runs.
- **Failure path:** crash → debug and re-run only the failed cell. Empty /
  tiny `n_bars` → the rule never fires for that instrument; note it in the
  report as "no signal on <SYM>" (this is informative, not an error).

## Step 5 — Report

**Action:** write `strategy/docs/strategy_<name>_report.md` (structure =
generated_strategy.md §4.4; note the full path — the repo-root `docs/` is for
spec documents, not strategy reports) containing, at minimum:
- Hypothesis (verbatim from Step 1) + expected trade count vs actual.
- 3×3×2 results tables (instrument × cost × window) with buy-hold on each.
- Why it wins/loses (mechanism, not just numbers).
- Regime breakdown (which sub-periods it lives or dies on).
- Causality checklist from Gate G3.
- **"N strategies tried before this one: <k>"** (from `strategy/trial_log.md`).
- Caveats (in-sample, no slippage, per-instrument loop).

- **Gate G5:** every number in the report can be traced to a Step-4 JSON
  block (copy values, do not retype).

## Step 6 — Evaluate (decision gates)

**Action:** apply generated_strategy.md §5 stop conditions to the
Step-4 results and assign exactly one status. The in-sample pass bar is defined
**once** in `config/strategies.yml → oos.pass_criteria` (beats buy-hold at 2 bps
on ≥ 2 of 3 instruments, **on both `full` and `last_12m`**, and max trade
count ≤ 300) — do not restate it here, reference it.

| Status | Condition |
|---|---|
| `rejected` | ANY stop condition of §5 met. Write the reason into the *Rejected combinations* table. |
| `parked` | No stop condition met, but total_return < buyhold at 2 bps (interesting, insufficient). |
| `finalist` | **No** §5 stop condition met AND the in-sample bar above holds on **both** `full` and `last_12m`. |
| `tested` | A `finalist` that **also** beat buy-hold on the one-shot OOS evaluation (see below). |

- **`finalist` → OOS check (the only path to `tested`, from `config/strategies.yml`):** the
  `full` and `last_12m` windows above are all **in-sample** (they are what the
  hypothesis was tuned against). A `finalist` is promoted to `tested` only by
  being evaluated **once** on the reserved holdout
  (`oos.holdout_start` → `oos.holdout_end`) and passing `oos.pass_criteria`.
  Promotion to `finalist` is a **human** decision (the machine only verifies the
  bar, see `check_results.py` check F). Iterating against the holdout is data
  snooping and is prohibited — that is a new hypothesis, not a re-run. This is
  the single most important guard against the overfitting risk the BRD names as #1.

- **Gate G6:** status assigned and justified in the report; if `tested`, the
  one-shot holdout result is present. A `rejected` outcome with a good
  diagnosis is a **complete, successful run** — do not re-tune to escape it.

## Step 7 — Close out

**Action:**
1. `STRATEGY_REGISTRY.md`: set status, last run date, result (ret vs BH,
   primary instrument); keep the row for all outcomes.
2. **`strategy/trial_log.md`: append one row for THIS attempt** (every outcome,
   including rejected/parked) with `n_tried_before` = the running count. This is
   mandatory — it is the only place the "best of N" burden is visible.
3. If `rejected`: add a row to *Rejected combinations — do not re-test
   without a new hypothesis* with the one-line reason.
4. If `tested`: append the baseline evidence to `STRATEGY_BACKGROUND.md` §7
   (one bullet: what works, on what, at what cost).
5. List all changed/created files in your final message to the user.

- **Gate G7 (definition of done):** all of these are true —
  - [ ] Registry row exists with final status; usage map consistent.
  - [ ] **Trial log row added with the correct `n_tried_before` count.**
  - [ ] Code runs in < 5 s per instrument.
  - [ ] Report has all 18 result cells + diagnosis + caveats.
  - [ ] No lookahead (Gate G3 checklist present in report).
  - [ ] Rejected combinations table updated if rejected.

## Batch mode (optional, only if explicitly requested)

Repeat Steps 1–7 for N ideas **sequentially**. The registry is the memory:
each completed cycle makes the next Step-1 gate stricter. Never run two
cycles in parallel against the registry (edit races), and never let a later
cycle "rescue" an earlier rejected cycle by re-tuning it — that is a new
hypothesis and must open a new `S-NN`.
