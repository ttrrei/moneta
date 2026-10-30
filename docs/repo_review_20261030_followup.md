# moneta — Execution Checklist #3 (follow-up to `e6350d5` → `84547d8`)

> **For the AI executing this file (VS Code).** This is a *fix list*, not a
> research task. It closes five concrete gaps found by reviewing commits
> `e6350d5`, `070a2bc`, `804964d` and `84547d8` (2026-10-30). It adds **no new
> strategies** and **does not touch the OOS holdout**.
>
> Read `docs/repo_review_20261030_initial.md`, `config/strategies.yml`,
> `strategy/WORKFLOW.md` and `strategy/oos_token.py` first.

---

## 0. Baseline you are starting from (verify first)

Run these **before changing anything** and confirm the numbers match. If they do
not, stop and report — the tree is not what this plan assumes.

```bash
cd <repo root>
python scripts/check_results.py            # expect: 0 failure(s), 0 warning(s), 220 note(s)  -> PASS
python scripts/test_check_results.py       # expect: 35/35 mutation cases passed
python -m pytest tests/ -q                 # expect: all green (count the tests, record it)
cat strategy/oos_ledger.json               # expect: {"version": 1, "consumptions": []}
```

Record these facts:

| Fact | Value at baseline |
|---|---|
| Registered strategies | 102 (`config/strategies.yml` → `strategies:` block) |
| Registry rows | 102 |
| Trial-log rows | 102 real rows (+1 HTML-comment example row) |
| Distinct sweep configs | 720 `(strategy, variant)` pairs |
| Sweep CSV rows | 14,040 total, of which **12,960 distinct** (1,080 are a re-run of `s08..s17`) |
| Outcome split | 101 `rejected`, 1 `parked` (S-55), 0 `finalist`, 0 `tested` |
| OOS ledger | empty — **the holdout has never been consumed** |

> The ledger MUST still be `{"version": 1, "consumptions": []}` when you finish.
> If it is not empty at the start, **stop and ask** — someone consumed the
> one-shot holdout and the rest of this plan changes.

---

## 1. Rules of engagement

- **Never run any OOS / holdout evaluation** (`--windows oos`, `run_matrix.py`
  with `oos`, or any direct read of the holdout parquet). Phase E is
  **read-only analysis** of the holdout *window's buy-hold baseline*; it must
  not run a strategy on the holdout.
- **Do not change any committed in-sample number.** New columns are allowed;
  existing values must stay byte-identical. Verify with a diff before
  committing any regenerated CSV.
- **Do not weaken a check to make it pass.** If a check fails, fix the data or
  the stale fixture.
- **Do not add, remove, rename or re-order any strategy** (`S-NN`). The
  registry, `config/strategies.yml`, `run_matrix.py` and `trial_log.md` must
  keep their current 102 entries in their current order.
- **Do not touch** `strategy/engine.py`, the 102 `strategy_*_lib.py` files, the
  102 `strategy/code/*.py` CLIs, `strategy/oos_token.py`, or anything under
  `strategy/results/iterations_*.csv`. This plan changes **checks, registry
  metadata, CI wiring and one script** — nothing else.
- **One commit per phase.** Before every commit, all three of these must be
  green:
  ```bash
  python -m pytest tests/ -q
  python scripts/test_check_results.py
  python scripts/check_results.py
  ```
- If anything here is ambiguous or conflicts with the code, **stop and ask**
  rather than guess.
- Finish with a message listing every changed/created file and every decision
  you defaulted.

### Owner decisions (defaults apply unless the owner edits this table)

| # | Decision | Default used by the executor |
|---|----------|-------------------------------|
| D1 | Rename the dated sweep artifacts, or keep the filenames? | **Rename** to `iterations_<real-date>_b<N>.csv` / `strategy_sweep_<real-date>_b<N>.md` (see Phase C.2). The current filenames encode dates that never happened; leaving them is a false record. |
| D2 | Saturation-guard thresholds | **WARN at ≥ 4**, **FAIL at ≥ 8** members of one `(base indicator, timeframe)` group. At baseline the max group is 5, so this produces 6 warnings and 0 failures — the build stays green. |
| D3 | Add the 101 rejected strategies to the "Rejected combinations" table? | **Yes**, one row per rejected strategy (Phase C.3). This table is the only mechanism that stops a future session from re-testing a dead idea. |
| D4 | Phase E outcome if the holdout turns out to be a BTC bull-market window | **Report and stop** — do **not** change `oos.pass_criteria` on your own. Propose the change; the owner signs it off. |

---

## 2. Priority map

| Item | Severity | Phase | Needs parquet? |
|---|---|---|---|
| CI self-test failure masks the results check | 🔴 P0 | A | no |
| Trial-log dates are fabricated (86 rows) | 🔴 P0 | C | no |
| "Rejected combinations" table missing 101 rows | 🔴 P0 | C | no |
| X5 hole: `candidate` + `rejected` passes silently | 🟡 P1 | B | no |
| Registry saturation is unenforced | 🟡 P1 | B | no |
| Sweep harness duplicates the evaluation windows | 🟡 P1 | D | no |
| S-55: is the OOS holdout an *informative* arbiter? | 🔴 P0 (before any OOS) | E | **yes** |

---

## 3. Phase A — CI must never mask the results check

**File:** `.github/workflows/ci.yml`

### A.1 The results-check step must run even when the self-test fails

At commit `e6350d5` the CI job failed at step 4 and **skipped step 5**:

```
4. checker self-test (32 mutation cases)   -> failure
5. check the committed results              -> skipped   <-- never ran
```

The four real failures that were hiding (`S1`, `S2`, `S3`, `X8`, all on `S-22`)
were only found by running the checker by hand. The same trap is still armed.

**Change** — add `if: always()` to the results-check step so a failing self-test
can never hide a failing results check:

```yaml
      - name: check the committed results (append-only ledger enforced vs base)
        if: always()          # <-- a failing self-test must not skip this step
        env:
          BASE_BRANCH: ${{ github.event.pull_request.base.ref }}
          EVENT_NAME: ${{ github.event_name }}
          BEFORE_SHA: ${{ github.event.before }}
```

Keep the existing `set -euo pipefail` and the fail-closed baseline resolution
untouched.

### A.2 Fix the stale step label

The step is labelled `checker self-test (32 mutation cases)` but the suite now
has **35** cases. Update the label to 35 (or drop the count — it will drift
again).

### Done criteria

- `grep -n "if: always()" .github/workflows/ci.yml` returns the results-check step.
- Locally: temporarily break one mutation case in `scripts/test_check_results.py`,
  confirm `python scripts/check_results.py` still runs and reports (it is a
  separate command — the point is that CI no longer *skips* it), then restore
  the file. Do not commit the temporary break.
- CI is green after the commit.

---

## 4. Phase B — Checker: close the X5 hole and add a saturation guard

**Files:** `scripts/check_results.py`, `scripts/test_check_results.py`

### B.1 X5 only fires in one direction

Current code (`scripts/check_results.py`, ~line 1031):

```python
if norm_status in {"rejected", "parked", "tested"} and norm_status not in norm_out:
    rep.fail("X5", ...)
```

`candidate` and `finalist` are not in that set, so a row whose registry status
is still `candidate` while its trial-log row says `rejected` **passes
silently**. That is exactly the state 20 strategies were in at `e6350d5`.

**Change** — make X5 two-sided. For a strategy with a registry row and at least
one trial-log row:

- `candidate` / `finalist` → **FAIL** if any trial-log outcome is a *terminal*
  verdict (`rejected` / `parked` / `tested`). The row says "adjudicated" but
  the registry still says "not run" / "OOS pending". Exception: `finalist` may
  carry a `tested` outcome (the OOS just passed and the registry has not been
  updated yet) — that is a transient, not a contradiction.
- `rejected` / `parked` / `tested` → **FAIL** if the status itself is not among
  the trial-log outcomes (existing behaviour, keep it).

Implementation sketch:

```python
_TERMINAL = {"rejected", "parked", "tested"}
# status -> outcomes that are consistent with it
_OK_OUTCOMES = {
    "candidate": set(),                 # only <TBD>/no row is consistent
    "finalist":  {"tested"},            # OOS may have just passed
    "rejected":  {"rejected"},
    "parked":    {"parked"},
    "tested":    {"tested"},
}
# -> for candidate/finalist, FAIL if outcomes & _TERMINAL - allowed != empty
# -> for the terminal statuses, keep the existing "status not in outcomes" FAIL
```

Normalise the outcome the same way the existing code does
(`lower().replace(" ", "").replace("-", "")`), and treat `<TBD>` as "not an
outcome" (it never appears in the committed log today, but the runner writes
it as a default).

### B.2 Add the matching mutation cases

In `scripts/test_check_results.py` add at least two cases to `CASES`:

1. `registry status is 'candidate' but the trial-log row says 'rejected' -> X5`
   — mutate the registry row's status to `candidate` while the trial-log row
   stays `rejected`; expect exactly `{"X5"}`.
2. `registry status is 'parked' but the trial-log row says 'rejected' -> X5`
   — same direction, different status; expect exactly `{"X5"}`.

Use the existing synthetic IDs (`S-999` / `S-998`) — **never** `S-98`/`S-99`,
which are real strategies now.

### B.3 Add a registry-saturation guard

The registry's own rule (`strategy/STRATEGY_REGISTRY.md`):

> "Two strategies are considered **duplicates** if they share the same key
> indicators + timeframe + entry logic, **regardless of parameter tweaks**."

Nothing enforces it. At baseline, 6 groups already hold ≥ 4 members:

```
ema 5m x5 · st_dir 5m x5 · atr 5m x5 · mfi 5m x5 · roc 5m x5 · aroon_down 5m x4
```

and the pattern is explicit — `willr_24 → willr_60 → willr_12`,
`cci_24 → cci_120`, `mfi_24 → mfi_60 → mfi_12`, `roc_24 → roc_120` — i.e. the
same indicator family re-tried at a different window.

**Change** — add a new check (suggest `X15`) in `scripts/check_results.py`:

- Group the registry rows by `(base indicator name set, timeframe)`, where the
  base indicator name is the indicator with its window suffix stripped
  (`willr_60` → `willr`, `macd_hist_6_24` → `macd_hist`, `st_dir_24_3` → `st_dir`).
  Indicators are the backticked tokens in the registry's *Key indicators* column.
- For each group with **≥ 4** members → `rep.warn("X15", ...)`: *"the (X, tf)
  family already has N strategies; the next variant needs a different indicator
  family — see WORKFLOW.md Step 1 (registry saturation)."*
- For each group with **≥ 8** members → `rep.fail("X15", ...)`: *"registry
  saturated for this family — STOP and report per WORKFLOW.md Step 1."*

At baseline this yields **6 warnings and 0 failures**, so the build stays green
(D2). The check exists so the *next* session that tries to add another ROC
variant trips it.

### Done criteria

- `python scripts/test_check_results.py` → **37/37** (35 + your 2 new cases).
- `python scripts/check_results.py` → **0 failures**, warnings increased by the
  X15 saturation warnings (6 at baseline), and the note count ≥ 220.
- No committed in-sample number changed (`git diff --stat` touches only
  `scripts/check_results.py`, `scripts/test_check_results.py`).

---

## 5. Phase C — Registry and trial-log honesty

### C.1 The trial-log dates are fabricated — fix them

**86 of the 102 trial-log rows are dated in the future.** The date column is
mechanically incremented one day per sweep batch, but every batch actually ran
in a single session on **2026-10-30**.

The proof is in the git history — the commit that *adds* each artifact is a hard
upper bound on when the run could have happened:

| Sweep batch | Artifact | Added by | Commit time (local +1100) | Filename date | Real date |
|---|---|---|---|---|---|
| b1 — S-08..S-17 | `iterations_2026-10-30.csv` | `e6350d5` | 2026-10-30 07:44 | 2026-10-30 | **2026-10-30** ✅ |
| b2 — S-08..S-27 | `iterations_2026-11-01.csv` | `e6350d5` | 2026-10-30 07:44 | 2026-11-01 | **2026-10-30** ❌ |
| b3 — S-28..S-42 | `iterations_2026-11-02.csv` | `804964d` | 2026-10-30 16:31 | 2026-11-02 | **2026-10-30** ❌ |
| b4 — S-43..S-57 | `iterations_2026-11-03.csv` | `804964d` | 2026-10-30 16:31 | 2026-11-03 | **2026-10-30** ❌ |
| b5 — S-58..S-72 | `iterations_2026-11-04.csv` | `84547d8` | 2026-10-30 20:58 | 2026-11-04 | **2026-10-30** ❌ |
| b6 — S-73..S-87 | `iterations_2026-11-05.csv` | `84547d8` | 2026-10-30 20:58 | 2026-11-05 | **2026-10-30** ❌ |
| b7 — S-88..S-102 | `iterations_2026-11-06.csv` | `84547d8` | 2026-10-30 20:58 | 2026-11-06 | **2026-10-30** ❌ |

**Change:**

1. In `strategy/trial_log.md`, set the `date` column of **all 86 rows dated
   2026-11-01 … 2026-11-06** to `2026-10-30`. The 10 rows dated 2026-10-30
   (S-08..S-17) are already correct — leave them.
2. In `strategy/STRATEGY_REGISTRY.md`, set the *Last run* column of every
   strategy whose trial-log row you just corrected to `2026-10-30` (the X9
   check cross-validates these two — they must agree).
3. Add one line under the trial-log header explaining that the `date` column
   records the **run** date and that all seven batches ran in one session on
   2026-10-30.

**Do not** change the `n_tried_before` column, the hypothesis text, the
outcomes, or the order of rows.

### C.2 Rename the dated artifacts (D1 = rename)

The filenames encode dates that never happened. Rename them with a batch
suffix so the date is truthful and the batches stay distinguishable:

```
strategy/results/iterations_2026-10-30.csv  → strategy/results/iterations_2026-10-30_b1.csv
strategy/results/iterations_2026-11-01.csv  → strategy/results/iterations_2026-10-30_b2.csv
strategy/results/iterations_2026-11-02.csv  → strategy/results/iterations_2026-10-30_b3.csv
strategy/results/iterations_2026-11-03.csv  → strategy/results/iterations_2026-10-30_b4.csv
strategy/results/iterations_2026-11-04.csv  → strategy/results/iterations_2026-10-30_b5.csv
strategy/results/iterations_2026-11-05.csv  → strategy/results/iterations_2026-10-30_b6.csv
strategy/results/iterations_2026-11-06.csv  → strategy/results/iterations_2026-10-30_b7.csv
strategy/docs/strategy_sweep_2026-10-30.md  → strategy/docs/strategy_sweep_2026-10-30_b1.md
strategy/docs/strategy_sweep_2026-11-01.md  → strategy/docs/strategy_sweep_2026-10-30_b2.md
… through …_b7.md
```

Then update **every** reference. Baseline blast radius: **352 mentions across
13 files** (`scripts/strategy_variants.py`, `scripts/strategy_variants_report.py`,
`scripts/test_check_results.py`, `strategy/STRATEGY_REGISTRY.md` (188 links),
`strategy/trial_log.md`, `strategy/docs/strategy_er_report.md`, and the 7 sweep
docs themselves).

Order the renames so no intermediate state collides (e.g. rename `11-01` →
`10-30_b2` before `10-30` → `10-30_b1`), and use `git mv` so history follows.

After the rename, verify **zero** stale references remain:

```bash
grep -rnE "iterations_2026-11-0[1-6]|strategy_sweep_2026-11-0[1-6]" \
     --include="*.py" --include="*.md" --include="*.yml" . | grep -v "^\./strategy/results/iterations_"
# must print nothing
```

Also update the *titles* and *headers* inside each renamed sweep doc (e.g.
`# 6-Iteration Improvement Sweep — S-28 … S-42 (2026-11-02)` → the real run
date), and the "Reproduce" command blocks, so the doc does not contradict its
own filename.

> If the owner sets D1 = "keep filenames" instead, then instead of renaming you
> must add to each sweep doc's header a line stating the **actual run date** and
> that the filename is a batch label — and you still must do C.1. Leaving a
> false date in the trial-log `date` column is not an option either way.

### C.3 Populate the "Rejected combinations" table

`strategy/STRATEGY_REGISTRY.md` has a section
`## Rejected combinations — do not re-test without a new hypothesis`. At
baseline it lists **7 rows** (S-01..S-07) and **0** of the 101 newly rejected
strategies.

**This table is the only mechanism that stops a future session from re-testing a
dead idea.** The trial log records *that* something was tried; this table
records *what* — and what not to repeat.

**Change** — add one row per rejected strategy (101 rows: S-08..S-54,
S-56..S-102; S-55 is `parked` and gets its own row or is omitted — the table's
title says "rejected combinations", so include it only if you also adjust the
heading).

Each row follows the existing three-column shape:

```
| <indicator + timeframe + entry logic> (S-NN) | <one-line reason> | [<sweep doc>](docs/strategy_sweep_...md) |
```

Example (derive the real numbers from the trial log — do not copy this one):

```
| 5m CCI-24 < 30 dip-buy (S-08) | Cost × frequency: 206–1,700 trades/yr on 5m; no variant beat buy-hold on ≥2/3 instruments @2 bps. See [S-08 row](docs/strategy_sweep_2026-10-30_b1.md) |
```

The reason text for each strategy is already in its `trial_log.md` row — reuse
it, do not invent new diagnostics. Because there are 101 rows, consider writing
a throwaway generator script that reads `trial_log.md` + the registry and emits
the table body; it is fine to keep it under `scripts/` if useful, but it must
not overwrite existing rows.

### Done criteria

- `grep -cE "^\| [0-9]+ \| 2026-11" strategy/trial_log.md` → **0**.
- `grep -c "2026-11-01" strategy/trial_log.md` → 0 (except the HTML-comment
  example row, which is inside `<!-- … -->` and is fine — verify it is still
  inside a comment).
- Every registry *Last run* date equals its strategy's trial-log date (the X9
  check enforces this — confirm `python scripts/check_results.py` still passes).
- The "Rejected combinations" table has ≥ 101 new rows, one per rejected
  strategy, and the X3/X5/G5 checks still pass.

---

## 6. Phase D — One source of truth for the evaluation windows

**File:** `scripts/strategy_variants.py`

### D.1 The sweep harness duplicates the windows

```python
# scripts/strategy_variants.py, ~line 35
WINDOWS = {
    "full": {"since": None, "until": "2025-07-31"},
    "last_12m": {"since": "2024-08-01", "until": "2025-07-31"},
}
```

These are hardcoded copies of `config/strategies.yml → windows`. If anyone
re-anchors a window in the config, the sweep harness keeps using the old
values **silently** — the exact drift this repo keeps having to fix elsewhere.

There is also a magic special case in the same file:

```python
tf = kw.get("timeframe", "5m" if sid != "s17" else "1h")
```

**Change:**

1. Import the canonical window resolution from `strategy/run_matrix.py` instead
   of duplicating it. `run_matrix._load_config()` and `run_matrix._window_bounds(cfg, name)`
   already implement the config-driven bound (including the `until`-cap rule that
   keeps in-sample runs off the holdout). Use them:

   ```python
   from strategy.run_matrix import _load_config, _window_bounds
   _CFG = _load_config()
   _WINDOWS = {name: _window_bounds(_CFG, name) for name in ("full", "last_12m")}
   ```

   Keep the *shape* the harness expects (`since` / `until` per window) — adapt
   the unpacking as needed.

2. Derive the timeframe from `config/strategies.yml → strategies.<ID>.timeframe`
   (the same source `run_matrix` uses to refuse a mismatched timeframe)
   instead of the `sid != "s17"` special case.

3. `INSTRUMENTS` and `COST_TIERS` are also duplicated from `run_matrix.py` —
   import them from there too (`run_matrix.INSTRUMENTS`, `run_matrix.COST_TIERS`).

**Why this matters beyond tidiness:** `scripts/strategy_variants.py` is a
*second execution path*. It bypasses `run_matrix.py`'s runner, its manifest,
its `--trial-row` bookkeeping and its OOS reservation. It happens to be safe
today only because it hardcodes `until = 2025-07-31` — the moment someone edits
the config (or this file), that safety could change without anyone noticing.

### D.2 Consider adding a note about the second path

Do **not** merge the harness into `run_matrix` in this phase — that is a large
change. Instead add a short comment at the top of `strategy_variants.py`
stating:

- it is a **sweep-only** helper;
- it is **not** the canonical execution path;
- the canonical path is `strategy/run_matrix.py` (which owns the OOS gate, the
  ledger reservation and the trial-log row);
- any holdout read is forbidden here.

### Done criteria

- `grep -n "2025-07-31" scripts/strategy_variants.py` → no hardcoded window
  dates (only config-derived values).
- `grep -n "s17" scripts/strategy_variants.py` → the magic special case is gone.
- The harness still produces byte-identical output for a re-run of one batch
  (compare a regenerated CSV against the committed one — `diff` must be empty
  apart from row order).
- `python scripts/check_results.py` and `python scripts/test_check_results.py`
  still green.

---

## 7. Phase E — [LOCAL DATA] Is the OOS holdout an *informative* arbiter for S-55?

> **This phase is read-only analysis.** It must not run any strategy on the
> holdout, and it must not write to `strategy/oos_ledger.json`.

### E.1 Why this check has to happen first

S-55 (`h1_rsi_24` up-cross, the `looser` variant k_in=33 / k_exit=27) is the
**only** configuration in all 12,960 distinct sweep cells that clears the
in-sample cross-market bar (beats buy-hold at 2 bps on ≥ 2 of 3 instruments on
**both** `full` and `last_12m`). A scan of every sweep CSV confirms it: 2 hits
for the both-windows bar (the same config counted in two files) and 43 configs
that clear a **single** instrument — all of them the BTC-only artifact, all
correctly rejected.

That is a genuinely strong result and S-55 is correctly parked rather than
auto-promoted. But look at the margins:

| Instrument | Window | Strategy | Buy-hold | Edge | Trades |
|---|---|---:|---:|---:|---:|
| BTC_USD | full | +1536.2% | +1289.5% | **+246.7%** | 64 |
| BTC_USD | last_12m | +94.9% | +82.4% | +12.6% | 11 |
| EUR_USD | full | −1.4% | +3.1% | −4.5% | 60 |
| EUR_USD | last_12m | +4.2% | +5.6% | −1.4% | 12 |
| XAU_USD | full | +116.9% | +110.6% | +6.3% | 50 |
| XAU_USD | last_12m | +35.0% | +34.4% | **+0.6%** | 4 |

Two of the four wins are razor-thin (+6.3% and **+0.6% on 4 trades**), and the
strategy is **~98% net long** — it is essentially "always long, with 11 timing
decisions".

**The risk:** the holdout window is 2025-08-01 → 2026-10-22, immediately after
the in-sample period in which BTC's buy-hold returned **+1,289%** (full) and
**+82%** (last 12m). If BTC is strongly bullish again inside the holdout, then
a 98%-long BTC-heavy rule will "beat buy-hold" on the holdout **for pure beta
reasons** — reproducing the exact S-06 / S-45 / S-88 trap, but at the most
expensive possible moment: burning the single one-shot holdout to confirm a
false positive.

### E.2 The measurement

With the local parquet (`data/ohlcv_5m_features/` and `data/ohlcv_1h_features/`)
compute, **for the holdout window only**, the **buy-hold** baseline per
instrument — no strategy, no position:

```sql
-- per instrument, over time >= '2025-08-01' AND time < '2026-10-23'
SELECT instrument,
       count(*)            AS n_bars,
       min(time)           AS t0,
       max(time)           AS t1,
       -- buy-hold return: first open -> last close
       arg_min(open, time) AS p0,
       arg_max(close, time) AS p1
FROM read_parquet('data/ohlcv_5m_features/ohlcv_5m_features.parquet')
WHERE time >= '2025-08-01' AND time < '2026-10-23'
GROUP BY instrument;
```

Buy-hold return % = `p1 / p0 * 100 − 100`.

Then, using the **new** engine comparators added at commit `4b8ab26`
(`buyhold_sharpe_weekly`, `buyhold_max_drawdown_pct`), also report for the
holdout window on each instrument:

- `buyhold_sharpe_weekly` — is the holdout's own risk-adjusted return strong
  or flat?
- `buyhold_max_drawdown_pct` — how deep was the holdout's own drawdown?

You can get these without running any strategy by applying the same two
formulas (`sharpe_weekly`, `max_drawdown_pct`) to the buy-hold equity curve
`close / open[0]`, exactly as `strategy/engine.py` does.

### E.3 The decision rule

| Holdout buy-hold picture | Meaning | Action |
|---|---|---|
| BTC strongly bullish again (e.g. buy-hold > +50% over the window) | The holdout is another BTC-bull stretch → a 98%-long rule passes for **beta**, not skill | **Do NOT promote S-55.** Report and stop (D4). |
| BTC flat / mixed, XAU/EUR mixed | The holdout is a *balanced* test → S-55's edge would have to come from timing | S-55 may be promoted to `finalist` by a **human**, then the one-shot OOS run proceeds under the existing gates. |
| BTC sharply negative | A 98%-long rule would lose to buy-hold on BTC → the holdout is a real test, but S-55 will very likely fail it | A human may still promote it (the OOS is a test, not a formality), but be aware the prior is poor. |

Whatever you measure, **write the numbers into the final message** and state
which branch of the table applies. Do **not** change
`config/strategies.yml → oos.pass_criteria` on your own — if you believe a
risk-adjusted criterion should be added (for example: the strategy must also
beat buy-hold on `sharpe_weekly`, not only on raw return), **propose the exact
YAML** and let the owner sign it off (D4).

### E.4 Also state, for the record

- The number of distinct cells scanned and the number of configs that cleared
  each bar (you should reproduce: **1** config on the both-windows bar,
  **43** on the single-instrument bar).
- That the OOS ledger was still empty before and after your analysis.

### Done criteria

- The final message contains the holdout buy-hold table (per instrument:
  return %, `buyhold_sharpe_weekly`, `buyhold_max_drawdown_pct`) and an
  explicit branch decision.
- `strategy/oos_ledger.json` is unchanged: `{"version": 1, "consumptions": []}`.
- No strategy was run on the holdout.

---

## 8. Definition of done

- [ ] `python -m pytest tests/ -q` green
- [ ] `python scripts/test_check_results.py` → **37/37**
- [ ] `python scripts/check_results.py` → **0 failures**; warnings = the X15
      saturation warnings only
- [ ] `strategy/oos_ledger.json` == `{"version": 1, "consumptions": []}`
- [ ] CI green on the branch, with **both** CI steps reported (not skipped)
- [ ] `grep -rnE "iterations_2026-11-0[1-6]|strategy_sweep_2026-11-0[1-6]"` over
      `*.py *.md *.yml` → nothing (outside `strategy/results/iterations_*.csv`,
      which must not exist under those names either)
- [ ] No trial-log row is dated after 2026-10-30
- [ ] "Rejected combinations" table contains ≥ 101 rows for the new strategies
- [ ] The 102 strategies, their order, their IDs and every committed in-sample
      number are **unchanged**
- [ ] Phase E's holdout buy-hold table and branch decision are in the final
      message
- [ ] The final message lists every changed/created file and every defaulted
      decision (D1–D4)

## 9. What this plan explicitly does **not** do

| Item | Why not |
|---|---|
| Add / remove / re-order strategies | Out of scope. The registry is at 102; Phase B.3 makes the *existing* rejections visible instead. |
| Merge `strategy_rsi_lib.py` into the shared core | A state-leak bug was hit and reverted (repo_review_20261028 §B3). Leave it. |
| A walk-forward harness, a dedup engine, a vectorised engine, a YAML strategy schema | Still deliberately deferred (repo_review_20261028 §3). |
| Promote S-55 to `finalist` or run the OOS | **Phase E only measures whether that would be meaningful.** The promotion and the one-shot OOS run are the owner's decision, after seeing the Phase E numbers. |
| Change `oos.pass_criteria` | D4: propose, do not implement. |
| Change the in-sample window anchors in `config/strategies.yml` | The windows are the fixed anchor for every comparison (repo_review_20261027 §B4). |

# moneta — Follow-up Fix Plan #4 (baseline commit `84547d8`)

> **For the AI executing this file (VS Code).** This plan comes from a review of commit
> `84547d8` (S-28 … S-102, five more sweeps). Read `config/strategies.yml`,
> `strategy/WORKFLOW.md`, `strategy/run_matrix.py`, `strategy/oos_token.py`,
> `scripts/strategy_variants.py` and `strategy/trial_log.md` first.
> Execute the phases **in order**. Phases 1–3 are code/doc work; Phases 4–5 need local data.

## 0. Why this plan exists

- The sweeps now cover **102 strategies / 727 configurations / ≥ 13,086 cells**, and the only
  config that clears the in-sample promotion bar is **S-55 `looser`** (1 of 720 sweep configs).
  Measured from `strategy/results/iterations_*.csv` at 2 bps:

  | | `looser` | `base` |
  |---|---|---|
  | BTC full / BH | +1536% / +1289% (64 trades, 98% exposure) | +836% / +1289% |
  | EUR full / BH | −1.4% / +3.1% | −10.6% / +3.1% |
  | XAU full / BH | +117% / +111% | +55% / +111% |

  It is effectively buy-and-hold with a few exits, and its edge is almost entirely BTC.
- **Two gaps from plan #3 are still open** (core files `run_matrix.py`, `oos_token.py`, `engine.py`,
  `check_results.py` are unchanged since `070a2bc`):
  1. `config_hash` always hashes `rule_params = {}` (see `run_matrix.py`, the manifest builder), so it cannot
     tell variants apart, and the pin (`strategies.<id>.oos_config_hash`) is optional and absent for S-55.
     `run_matrix` can only run the *base* parameters, so the nominated variant `looser` **cannot be
     evaluated in OOS as nominated** (base violates the 54 trades/yr ceiling: 61–65 tpy).
  2. The 5m-vs-1h buy-hold baseline mismatch (C1 of plan #3) was never diagnosed or corrected in the sweep docs.

## 1. Baseline (verify first)

- `python -m pytest tests/ -q` → 455 passed.
- `python scripts/test_check_results.py` → 35/35.
- `python scripts/check_results.py` → PASS (0 failures, 0 warnings).
- `strategy/oos_ledger.json` is exactly `{"version": 1, "consumptions": []}` — **it must be identical when you finish.**

## 2. Rules of engagement

- **Never run any OOS / holdout evaluation** (`--windows oos`). Tests use `tmp_path` + `monkeypatch`.
- **Do not change any committed in-sample number.** New columns only; existing values byte-identical.
- **Do not weaken a check to make it pass.** Fix the data, the fixture, or the code.
- **Do not add strategies or sweeps** (see task 1.1).
- **One commit per phase.** Before each commit run `python -m pytest tests/ -q`,
  `python scripts/test_check_results.py`, `python scripts/check_results.py`. All green.
- Tasks tagged **[LOCAL DATA]** need the git-ignored `data/` parquet. If absent, skip them, list them in
  your final message, and do not fabricate numbers.
- If anything is ambiguous or conflicts with the code, **stop and ask**.
- Finish with a message listing changed files and every defaulted decision.

## 3. Decisions (defaults apply unless the owner edits this table)

| # | Decision | Default |
|---|----------|---------|
| D9 | Strategy freeze | **Freeze new strategy IDs after `S-102`** until the owner lifts it (task 1.1). |
| D10 | Is S-55 nominated as `finalist`? | **No.** This plan only makes nomination *possible and correct*. Promotion stays a human edit (D4). |
| D11 | Replication on instruments never used for selection | Run only if the feature tables for such instruments exist locally (task 5.1); otherwise skip and report. |

---

## Phase 1 — Stop the bleeding, fix the record

### 1.1 Freeze new strategy IDs · `config/strategies.yml`, `strategy/WORKFLOW.md`, `scripts/check_results.py`
- Add to config: `research: { strategy_freeze_after: "S-102" }` with a comment explaining the multiple-testing
  reason (727 configs tried; the finalist bar is not corrected).
- New checker rule (next free code, e.g. `X15`): fail if the registry or `trial_log.md` contains a strategy id
  greater than `strategy_freeze_after`. Lifting the freeze means editing that one config line in a reviewed commit.
- Add a mutation case (a row `S-103` in the registry → X15). Add a short WORKFLOW paragraph.

### 1.2 Correct the sweep documents · `strategy/docs/strategy_sweep_2026-10-30.md` … `…-11-06.md`
- Do **not** delete anything. Append a "Correction (follow-up #4)" section to each affected file:
  - batch 1/2: the claim "1h is the best iteration for 9/10 and 10/10" is **not established**, because the
    buy-hold baseline differs between tables (BTC full: +1538% on 5m tables vs +1288% on 1h tables), so
    "edge vs buy-hold" is not comparable across timeframes. Reference task 4.1 for the common-window re-run.
  - `strategy_sweep_2026-11-03.md`: replace the wording "the only genuine in-sample pass" for S-55 `looser`
    with an accurate description: one of 720 configs; ≈98% exposure; BTC-driven; EUR negative in both
    windows; selected from 8 S-55 variants; not corrected for multiple testing.
- Update the S-55 registry note the same way (keep status `parked`).

### 1.3 Template fix for a first-bar wrap-around · `scripts/_gen_*.py` and the affected libs
- A few generated rules read `[j-1]` **before** the `j >= 1` guard (e.g. `strategy_aroon12spread_lib.py`
  line 57, `strategy_aroondnstoch_lib.py` line 65). At `j = 0` numpy wraps to the last element (a one-bar
  look-ahead). Write a small scan script that lists every `strategy_*_lib.py` with this pattern, fix the
  generator templates, and patch only the affected libs. Re-run the unit tests.
- Add one generic **causality test** (`tests/test_rules_causality.py`): for every rule library, build the rule on
  synthetic bars, perturb all bars at indices ≥ k, and assert `desired_position(i)` is unchanged for all
  `i ≤ k`. It must cover every `strategy_*_lib.py`, so future generated rules are checked automatically.
  Check committed in-sample results do not change (only first-bar behaviour may differ; if any result changes, stop and report).

**Commit 1. Done when:** freeze enforced by the checker, sweep docs corrected, causality test green for all libs.

---

## Phase 2 — Make a nominated variant runnable and pinned (closes C4)

### 2.1 One variant registry · new `strategy/variants.py`
- Today variants live in `scripts/strategy_variants.py` and `run_matrix` knows only the base parameters.
  Move the variant definitions (name → resolved rule kwargs + timeframe + entry_guard) into an importable module
  that **both** the sweep harness and `run_matrix` read. The harness must produce byte-identical results
  after the refactor (verify against the committed `iterations_*.csv` for a few strategies **[LOCAL DATA]**).
- API: `resolve(strategy_id, variant) -> {"timeframe":…, "entry_guard":…, "rule_params": {...}}`;
  unknown variant → `SystemExit`.

### 2.2 `run_matrix --variant NAME` (default `base`) · `strategy/run_matrix.py`
- Pass the resolved kwargs into the strategy `run()`.
- `config_hash(timeframe, entry_guard, rule_params)` must receive the **resolved** params (not `{}`). Different
  variants must hash differently; the same variant must hash identically across machines.
- Record the variant name and hash in the ledger record at reserve time (additive fields only).

### 2.3 Make the pin mandatory for a finalist · `config/strategies.yml`, `strategy/run_matrix.py`, `scripts/check_results.py`
- Config per strategy gains `oos_variant` and `oos_config_hash`.
- `run_matrix` OOS: refuse unless **both** are present, `--variant` equals `oos_variant`, and the recomputed hash
  equals `oos_config_hash`. (Today an absent pin means "nothing is refused" — remove that fail-open.)
- Checker: a registry row with status `finalist` must have both pin fields, and the pin must equal the hash
  recomputed from `strategy/variants.py`. Add mutation cases: finalist without a pin → fail; pin that does not
  match → fail.
- Add `scripts/pin_finalist.py STRATEGY VARIANT`: prints the hash and the YAML snippet to paste. It must **not**
  edit the registry status or write the ledger.

### 2.4 Tests (tmp_path + monkeypatch, synthetic strategy, never the real ledger)
- two variants → two hashes; same variant → same hash.
- unpinned finalist → OOS refused; wrong `--variant` → refused; hash mismatch → refused.
- pinned strategy with the matching variant passes the gate (up to, but never consuming, the real holdout).

**Commit 2. Done when:** all Phase 2 tests pass and `--variant looser` is runnable for S-55 on the **in-sample** windows.

---

## Phase 3 — Fix the comparison baseline (closes C1)  [LOCAL DATA]

### 3.1 Diagnose · `strategy/docs/baseline_mismatch_note.md`
- For each instrument print the first/last bar of the 5m and 1h feature parquet, and the first row left after each
  strategy's `not_null_cols` filter. Note that the buy-hold start depends on the warm-up of the columns each strategy
  uses (S-55's own buy-hold is +1289%, not the plain-5m +1538%).

### 3.2 Common-window mode · `scripts/strategy_variants.py` and its report script
- Add `--common-window`: per instrument, `since = max(first valid bar over every table/column set under comparison)`,
  same `until`. Write to **new** files `iterations_<date>_common.csv`; never overwrite originals.
- Re-run the top candidates per batch plus S-55 `base`/`looser` in this mode (not all 102 strategies).
- The report prints both views and flags any ranking that changes.

**Commit 3. Done when:** the note and the common-window files exist and the sweep docs reference them.

---

## Phase 4 — Evidence for the one candidate (S-55)  [LOCAL DATA]

### 4.1 Risk-adjusted view · `strategy/docs/s55_nomination_review.md`
- Add `buyhold_sharpe_weekly` and `buyhold_max_drawdown_pct` to the sweep harness CSV schema (engine already emits
  them; keep the checker tolerant of older CSVs). Re-run **S-55 `base` and `looser` only**, in-sample windows, to a new
  `iterations_<date>_s55_risk.csv`.
- In the review doc, tabulate per instrument/window at 2 bps: strategy return vs buy-hold, `sharpe_weekly` minus
  buy-hold Sharpe, strategy max drawdown ÷ buy-hold max drawdown, exposure, trade count.
- State facts only. **Do not recommend or set `finalist`** (D10); the owner decides, and any change to
  `oos.pass_criteria` must be decided before nomination and recorded in `trial_log.md` (D6 of plan #3).

### 4.2 Reproduction check
- `run_matrix --strategy s55 --variant looser` on the in-sample windows must reproduce the `iterations` rows for
  S-55 `looser` (n_trades, total_return_pct, sharpe_weekly) exactly. If not, stop and report.

---

## Phase 5 — Replication on instruments never used for selection (conditional, D11)  [LOCAL DATA]

### 5.1 Pre-register, then run once
- List the instruments present in the feature parquet besides `EUR_USD`, `XAU_USD`, `BTC_USD`. If there are none,
  write that fact into the review doc and **skip this phase**.
- **Commit the instrument list and the exact config (S-55 `looser`, its `config_hash`) first**, in
  `strategy/docs/s55_replication_prereg.md`. Only then run it, **once**, in-sample windows only, with the same cost
  tiers. No parameter changes after seeing results.
- Record the result as one section in `trial_log.md` ("Replication on unseen instruments"), outside the table
  the X4 parser reads. Report per instrument: return vs buy-hold, Sharpe vs buy-hold Sharpe, drawdown ratio.
- This consumes **no holdout**. It is still data we look at once; treat it as a single pre-registered test.

---

## Out of scope (do NOT do)

- New strategies, new sweeps, new variants of any of S-01…S-102 (D9).
- Changing `oos.pass_criteria`, the committed windows, or the existing holdout window/ledger.
- Setting any registry row to `finalist`, or running any OOS (D10).
- Rewriting the engine beyond what is already there.

## Definition of done

- [ ] pytest, self-test and `check_results.py` green; ledger still `{"version":1,"consumptions":[]}`.
- [ ] Strategy freeze enforced by the checker; sweep docs corrected; S-55 wording corrected.
- [ ] Causality test covers every `strategy_*_lib.py`; first-bar wrap-around fixed in templates and libs.
- [ ] `config_hash` covers resolved rule parameters; `run_matrix --variant` works; a finalist without a valid pin is refused by both `run_matrix` and the checker.
- [ ] [LOCAL DATA] baseline note, common-window CSVs, S-55 risk review, and (if data exists) the pre-registered replication.
- [ ] Final message lists changed files, defaulted decisions, and any [LOCAL DATA] task not done.

# VS Code AI 执行清单 — Commit `84547d8`

> Repository: `ttrrei/moneta`  
> Review target: `84547d8f0a9623ddb2d48ea9e60d433b32a331ea`  
> 基准日期：2026-10-30（Australia/Sydney）  
> 目标：修复这次提交暴露出的研究流程和策略实现问题，不扩张策略数量，不消耗 OOS。

---

## 给 VS Code AI 的总指令

请在当前 Moneta 仓库中，按下面阶段逐项执行。先检查当前工作区、HEAD 和相关文件，再修改代码。**不要假定当前 HEAD 一定等于 review commit**；先确认分支和工作区状态，并将所有修改限制在本清单范围内。

### 必须遵守的约束

1. **禁止读取、运行或修改 OOS holdout。** 不得调用 OOS runner，不得修改 `config/strategies.yml` 中的 holdout 日期、`pass_criteria` 或 OOS gate，不得写入 `strategy/oos_ledger.json`。本次所有回测必须严格使用现有 in-sample 窗口（截止 `2025-07-31`）。
2. **不得覆盖任何现有研究 CSV。** 特别是 `strategy/results/iterations_2026-10-30.csv`、`iterations_2026-11-01.csv` 和本次新增的三个 CSV。需要重跑时使用全新的文件名。
3. 不要新增 S-103 及之后的策略；不要为了让某个策略通过而调整既定的 buy-and-hold、跨市场或交易频率门槛。
4. 不要擅自把所有策略的 `not_null_cols` 加上 `ema_24`。EMA gate 是可选改进项；未启用 gate 时，不应因为 EMA 缺失而改变基础策略的样本区间。
5. 不要把本清单之外的大规模重构、格式化或依赖升级混入提交。每个阶段完成后先运行相关测试，再继续下一阶段。
6. 对无法从仓库证据确认的历史事实（例如报告实际运行日期），明确标记为“无法验证”，不要猜测或伪造执行记录。

### 执行顺序

- [ ] Phase 0 — 确认仓库状态和改动边界
- [ ] Phase 1 — 修正未来日期报告的研究溯源信息
- [ ] Phase 2 — 修复 S-82 True Range 尺度问题
- [ ] Phase 3 — 修复 EMA Gate 遇到 NaN 时的 fail-open
- [ ] Phase 4 — 防止 sweep 覆盖历史结果，并修正 CLI/help
- [ ] Phase 5 — 澄清重叠窗口的研究含义
- [ ] Phase 6 — 修正文档语义和生成器注释
- [ ] Phase 7 — 回归测试、结果核验和交付摘要

---

## Phase 0 — 确认仓库状态和改动边界

- [ ] 执行 `git status --short`、`git branch --show-current`、`git rev-parse HEAD`。
- [ ] 确认当前 HEAD 是否为 `84547d8` 或其后继；若不是，先检查该 commit 是否仍在当前分支历史中。
- [ ] 保存当前工作区状态，不覆盖用户已有的未提交修改。
- [ ] 阅读并核对以下文件的当前版本：
  - `scripts/strategy_variants.py`
  - `strategy/strategy_trcollapse_lib.py`
  - `pipeline/indicators.py`
  - `scripts/_gen_batch5.py`、`scripts/_gen_batch6.py`、`scripts/_gen_batch7.py`
  - `strategy/strategy_*_lib.py` 中本批次 S-58 至 S-102 的 `ema_gate` 实现
  - `strategy/docs/strategy_sweep_2026-11-04.md` 至 `strategy_sweep_2026-11-06.md`
  - `strategy/trial_log.md`、`strategy/STRATEGY_REGISTRY.md`
- [ ] 在执行摘要中记录实际 HEAD、工作区是否干净，以及本次准备修改的文件列表。

**验收：** 没有覆盖用户已有修改；清楚知道实际代码版本；没有触碰 OOS。

---

## Phase 1 — 修正未来日期报告的研究溯源信息（P1）

### 背景

Review commit 的时间是 `2026-10-30 09:58:24 UTC`（悉尼时间 `2026-10-30 20:58:24`），但同一 commit 已包含标注为 2026-11-04、2026-11-05、2026-11-06 的 sweep 报告和 CSV。仅凭文件名和报告文字，不能证明这些实验实际在哪一天运行。

### 需要处理的文件

- `strategy/docs/strategy_sweep_2026-11-04.md`
- `strategy/docs/strategy_sweep_2026-11-05.md`
- `strategy/docs/strategy_sweep_2026-11-06.md`
- 对应三个 `strategy/results/iterations_*.csv`

### 执行要求

- [ ] 查找仓库中是否存在实际执行日志、命令记录、运行 metadata、CI artifact 或其他可验证的运行时间证据。
- [ ] 不要把 Git commit 时间、文件名日期或本机文件修改时间当成实验真实执行时间。
- [ ] 若能验证真实运行时间，在每份报告中增加 `Run provenance`，至少记录：
  - `run_started_at_utc`、`run_completed_at_utc`
  - 执行时的 git commit SHA
  - 数据文件版本或 fingerprint（至少记录文件路径、大小；若仓库已有 hash 工具则记录 hash）
  - 完整运行命令及 workers 数量
  - 策略范围、variant 数、instrument、window、cost tiers、总 cells、错误 cells
- [ ] 若无法验证实际运行日期，将报告状态改为 `unverified` 或 `precomputed evidence — execution time not verified`；不要再用肯定语气声称某日已完成运行。
- [ ] 如日期只是批次编号/计划日期，明确说明它不是实际执行日期。可以保留现有文件名作为 batch ID，但必须消除“未来日期已完成”的歧义。
- [ ] 不要重写或伪造三个 CSV 的执行时间；不要因为本阶段而重新跑全部 45 个策略。

**验收：** 报告能够区分“实验日期”“文件批次日期”和“无法验证”；所有历史记录诚实、可追溯。

---

## Phase 2 — 修复 S-82 True Range 尺度问题（P1）

### 当前问题

`pipeline/indicators.py` 中 `tr` 是 `talib.TRANGE(h, l, c)` 的原始价格单位。S-82 却用跨 EUR_USD、BTC_USD、XAU_USD 的固定绝对阈值（默认 `k_in=0.001`、`k_exit=0.002`），导致相同参数在不同资产上含义不同。原始 sweep 中 S-82 的交易频率也明显失衡：BTC 和 XAU 极少交易，EUR 交易很多。

### 建议实现

优先考虑增加归一化特征，例如：

`tr_atr_ratio = tr / atr_24`

或：

`tr_pct = tr / close`

先检查现有 feature 命名、指标 group、输出 parquet 和测试结构，选一个最符合本项目现有特征约定的实现；不要同时引入多个近似特征。若使用 `tr_atr_ratio`，对 `atr_24 <= 0`、NaN 和 Inf 做安全处理。

### 执行要求

- [ ] 在 `pipeline/indicators.py` 增加归一化 TR 特征，使用当前及之前已收盘 bar 的数据，不得使用未来数据。
- [ ] 为特征增加单元测试，覆盖正常值、零分母、NaN、Inf，以及跨不同价格尺度时的可比性。
- [ ] 修改 `strategy/strategy_trcollapse_lib.py`：S-82 使用归一化特征，不再用原始 `tr` 与跨市场固定绝对阈值比较。
- [ ] 将新参数定义为无量纲参数；默认值应根据指标数学含义设定，不要凭空宣称它已优化。保留参数可由 sweep variant 传入。
- [ ] 更新 `scripts/_gen_batch6.py` 中 S-82 对应 spec（S-82 当前属于 batch 6），以及相关 variant 配置文件/`scripts/strategy_variants.py` 中 S-82 的配置。
- [ ] 更新 S-82 的 CLI wrapper（如参数名、help text 或默认值发生变化）。
- [ ] 更新 `strategy/STRATEGY_REGISTRY.md`、`strategy/trial_log.md` 和对应 sweep 报告，说明原始 TR 版本存在尺度问题，新结果是一次修正后的独立实验。
- [ ] 新结果写入**新文件**，例如 `strategy/results/iterations_s82_trnorm_20261030.csv`；禁止覆盖 `iterations_2026-11-05.csv`。
- [ ] 仅运行 S-82 的 in-sample sweep：8 variants × 3 instruments × 2 windows × 3 costs = **144 cells**。命令应显式指定 `--strategies s82` 和新的 `--out` 路径。
- [ ] 重新核验 144 个组合全部唯一、无 error、无缺失数值；报告 0/2/5 bps 结果、每市场交易次数和 trades/year。
- [ ] 与旧 S-82 结果分开呈现，不得把新旧结果混合排名。

**验收：** S-82 使用归一化特征；三个市场上的阈值具有一致的数学尺度；新 CSV 144 行且组合完整；旧 CSV 保持原样；没有访问 OOS。

---

## Phase 3 — 修复 EMA Gate 遇到 NaN 时的 fail-open（P1/P2）

### 当前问题

目前常见写法是：只有 `gate_close` 和 `gate_ema` 都 finite，且 `close <= ema` 才阻止入场。若 EMA 或 close 是 NaN，条件不成立，代码会继续执行 entry，等于 EMA 不可用时反而放行。

### 执行要求

- [ ] 搜索本批次 S-58 至 S-102 的所有 `ema_gate` 实现，列出受影响文件；不要只修 S-66 或 S-82。
- [ ] 对 `state == 0` 且 `ema_gate == True` 的入场路径改成 fail-closed：
  - `gate_close` 或 `gate_ema` 不存在/不是 finite：不允许新开仓，返回当前 state。
  - 两者有效但 `close <= ema`：不允许新开仓。
  - 两者有效且 `close > ema`：允许继续执行策略自身 entry 条件。
- [ ] EMA gate 只限制**新入场**；已有仓位的 exit 必须继续正常工作，不能因 EMA 缺失而阻断退出。
- [ ] 不要无条件把 `ema_24` 加进 `not_null_cols`，否则未启用 EMA gate 的基础策略也会丢弃数据行并改变样本范围。
- [ ] 优先修正 generator/template 逻辑，确认 `scripts/_gen_batch3.py` 的共享模板和 `_gen_batch5.py`、`_gen_batch6.py`、`_gen_batch7.py` 的生成逻辑不会再次产生旧 bug。
- [ ] 对已有生成文件做一致性修复；不要只修模板而留下实际运行的策略库。
- [ ] 增加测试：
  1. gate 关闭时行为与原策略相同；
  2. gate 开启且 close/EMA 有效、close 大于 EMA，可以正常入场；
  3. gate 开启且 close 小于等于 EMA，不入场；
  4. gate 开启且 EMA 为 NaN，不入场；
  5. gate 开启且 close 为 NaN，不入场；
  6. 已经持仓时 EMA 为 NaN，策略仍可按自身 exit 条件退出。
- [ ] 检查 gate 相关测试是否真正调用各策略的 `desired_position`，而不是只测一个与实现脱节的 helper。

**验收：** 所有受影响策略和 generator 一致；EMA 缺失不会触发新入场；已有仓位仍能退出；未启用 gate 的样本区间不变。

---

## Phase 4 — 防止 sweep 覆盖历史结果，并修正 CLI/help（P1）

### 当前问题

`scripts/strategy_variants.py` 默认 `--out` 指向 `strategy/results/iterations_2026-10-30.csv`，写入时使用 `open("w")`。当前策略范围已扩大到 S-08 至 S-102，默认全量运行将生成 12,960 cells，并可能覆盖已有 1,080 行历史数据。

### 执行要求

- [ ] 在打开输出文件前检查目标路径是否已存在；存在时默认报错退出，不得覆盖。
- [ ] 增加显式 `--force` 参数，只有用户明确传入才允许覆盖；错误信息应提示使用新 `--out` 路径或 `--force`。
- [ ] 不要自动删除旧文件，也不要自动给旧文件改名。
- [ ] 将默认输出路径改为安全的新路径策略（例如要求用户显式提供 `--out`，或生成带运行时间/ID 的新文件名）。不得再默认指向已存在的历史结果文件。
- [ ] 验证 `--strategies` 中的未知策略 ID、`--variants` 中不存在的 variant、`--workers <= 0` 时能给出清晰的 argparse 错误，而不是 traceback 或静默生成空结果。
- [ ] 修正脚本顶部 docstring、`--variants` help、运行进度信息等过期描述。当前实际范围为 S-08..S-102，且策略 variant 数不再统一为 6。
- [ ] 运行成功后，打印实际策略数、variant 数和计划 cells；不要硬编码 `10 strategies x 6 variants`。
- [ ] 增加测试：
  1. 目标文件不存在时允许正常写入；
  2. 目标文件已存在且未传 `--force` 时拒绝写入，并确认原文件内容未变；
  3. 传 `--force` 时才覆盖；
  4. `--strategies s82` 的计划 cell 数是 144；
  5. 全量任务数与实际策略/variant 配置计算一致。
- [ ] 为本阶段测试使用临时目录，不要拿真实历史 CSV 做覆盖测试。

**验收：** 不带 `--force` 永远不会覆盖已有 CSV；CLI 描述与实际行为一致；现存研究结果保持原样。

---

## Phase 5 — 澄清 Full / Last 12m 的研究含义（P2）

### 当前问题

`full`（从历史起点到 2025-07-31）包含了 `last_12m`（2024-08-01 到 2025-07-31）。两个窗口是嵌套/重叠窗口，不是两份独立验证样本。

### 执行要求

- [ ] 保留现有窗口日期和历史 CSV，不要为了本阶段重跑全部 95 个策略。
- [ ] 检查所有报告中“both windows”“two windows”“validation”等措辞。把 `full` + `last_12m` 准确描述为“全样本表现 + 最近 12 个月子区间稳定性检查”，不能称为两个独立验证窗口。
- [ ] 若需要使用“独立 validation”的表述，必须先提出并记录一个非重叠的时间切分方案，再单独实施；不得直接把 `last_12m` 改日期后覆盖已有 CSV。
- [ ] 任何新的时间切分仍须严格早于现有 OOS 起点 `2025-08-01`；不得借此扩展或读取 holdout。
- [ ] 报告的跨窗口通过条件应保留原意，但明确它是嵌套窗口一致性门槛，不是独立样本上的重复验证。

**验收：** 文档不再把重叠窗口称为独立验证；历史数据及 OOS 边界没有改变。

---

## Phase 6 — 修正文档语义和生成器注释（P2/P3）

### 6.1 Williams %R 命名与规则描述

- [ ] 检查 S-74（`willr_60`）和 S-93（`willr_12`）的规则说明、registry 和 CLI help。
- [ ] 精确写明当前逻辑是 Williams %R 从阈值下方上穿后入场、跌破 exit 阈值离场；不要笼统写成传统 oversold rebound。
- [ ] 明确 S-74 默认入场阈值 `-50`、退出阈值 `-80`；S-93 默认入场阈值 `-60`、退出阈值 `-80`。
- [ ] 本阶段只校正文档和描述，除非另有独立证据，不要改动策略信号规则或重新挑选参数。

### 6.2 Volume Proxy 语义

- [ ] 检查数据源中 `volume` 字段的实际含义及 `pipeline/indicators.py` 的计算方式。
- [ ] 在 `strategy/STRATEGY_REGISTRY.md`、相关策略 docstring 和背景文档中明确 `vol_rel_24` 是输入数据 volume 相对其 24-bar 均值的比率。
- [ ] 对 FX/CFD 数据，若源数据为 tick volume，应明确称为 tick-volume/activity proxy，不得称为整个市场的真实成交量或集中成交量。
- [ ] 不要在没有数据源证据时自行断言所有 instrument 的 volume 都是 tick volume；按 instrument/source 说明，无法确认的标记为待核实。

### 6.3 清理 generator 和 CLI 过期描述

- [ ] 核对 `_gen_batch5.py`、`_gen_batch6.py`、`_gen_batch7.py` 的 batch 范围、注释与实际 S-ID 对应关系。
- [ ] 核对 `_gen_cli_batch5.py`、`_gen_cli_batch6.py`、`_gen_cli_batch7.py` 的 docstring 是否准确描述实际策略范围。
- [ ] 修正 `strategy_variants.py` 中“10 strategies x 6 variants”等硬编码文字。
- [ ] 不要删除仍被生成脚本、测试或研究复现使用的文件；对于 one-shot generator 是否保留，只能提出建议，不能在本次直接删除。

### 6.4 多指标共振策略的研究记录

- [ ] 在 S-97/S-98 的研究备注中记录 RSI、Stochastic、MFI 等振荡指标可能存在信息相关性；不要把三个/四个指标简单解释为三/四份独立信号。
- [ ] 暂不增加更多 oscillator stacking 策略。若未来要继续研究，先做跨市场、跨窗口的 feature correlation / incremental information 分析。

**验收：** 策略名称、规则说明、指标来源和 generator 描述准确一致；没有偷偷改变历史策略定义。

---

## Phase 7 — 回归测试、结果核验和交付摘要

### 测试要求

- [ ] 运行与修改范围相关的单元测试。
- [ ] 运行完整测试套件（按仓库当前约定，例如 `pytest -q`）。
- [ ] 运行仓库现有的结果检查器（先确认当前标准命令及参数，例如 `scripts/check_results.py`），确保没有引入新的 failure/warning。
- [ ] 检查所有生成的 Python 文件可 import，CLI `--help` 正常。
- [ ] 对 S-82 的新 CSV 核对 144 行、144 个唯一组合、0 error、0 缺失指标。
- [ ] 对 sweep overwrite tests 使用临时文件夹；确认历史 CSV 的 git diff 为空。
- [ ] 确认 `strategy/oos_ledger.json` 没有变化，OOS holdout 的配置没有变化。
- [ ] 运行 `git diff --check`，检查空白错误；检查 diff 中没有无关格式化或大规模重排。

### 最终交付摘要

请在完成后输出：

1. **完成情况**：按 Phase 0–7 标记完成/未完成/受阻。
2. **修改文件列表**：每个文件一行，说明具体改动。
3. **关键设计决定**：尤其说明 S-82 最终选用哪种归一化定义、单位和阈值含义。
4. **测试结果**：测试命令、通过/失败数量；不要只写“tests passed”。
5. **S-82 新 sweep**：新 CSV 文件名、行数、错误数、各市场交易频率摘要，以及是否仍不符合候选标准。
6. **历史证据处理**：三份未来日期报告最终标记为何种状态，哪些运行信息有证据、哪些无法验证。
7. **未完成事项**：明确列出，不要将未完成写成已完成。
8. **OOS 保护确认**：明确 `oos_ledger.json` 和 holdout 配置均未修改，且没有运行 OOS。

不要自动创建 OOS finalist，不要自动修改策略状态为 `tested`，不要为了让检查器变绿而降低既定标准。

---

## 建议的提交拆分

为方便 review，建议最多拆成以下 4 个独立提交；不要把 45 个策略重新生成并全部格式化：

1. `Fix S-82 normalized true-range signal` — 指标、S-82、对应测试和 144-cell 新结果。
2. `Make EMA gate fail closed on invalid data` — generator/template、受影响策略实现和测试。
3. `Protect sweep outputs from accidental overwrite` — harness 参数、测试和帮助文本。
4. `Clarify research provenance and window semantics` — 报告状态、registry/trial log、Williams %R 和 volume 语义文档。

如果某一项无法在当前证据下安全完成，保留代码不变，提交明确的问题说明和建议，不要猜测事实或绕过保护。