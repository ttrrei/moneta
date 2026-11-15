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
