# Verification of `repo_review_20261030_followup.md`

This file records, per claim, whether the review's fix list is **correct**
(→ I fixed it) or **incorrect** (→ I document the discrepancy here). Verification
was done against the committed tree at `84547d8` (clean working tree, i.e. the
review's assumed 102-strategy baseline) and the live GitHub Actions history.

**Method note.** Several of the review's "baseline" facts were re-checked by
stashing *only* the uncommitted WIP (S-103…S-112: config rows, libs, CLIs, tests,
`iterations_2026-11-07.csv`) and running the three gate commands with the review's
proposed fixes applied. With the WIP stashed the tree is exactly the review's
assumed state; with it present the checker reports 26 pre-existing failures on
S-103…S-112 (X1/S1/S2/S3/X3), unrelated to this review.

## Baseline facts (review §0) — all confirmed

| Fact (review §0) | Verified value |
|---|---|
| `check_results.py` → 0 failure, 0 warning, 220 note, PASS | ✅ exact (clean baseline, before my B.3 change) |
| `test_check_results.py` → 35/35 | ✅ exact |
| `pytest tests/ -q` → green | ✅ 455 passed |
| `oos_ledger.json` → `{"version": 1, "consumptions": []}` | ✅ exact |
| 102 registry rows | ✅ 102 |
| 101 rejected + 1 parked (S-55), 0 finalist/tested | ✅ exact |
| 720 distinct `(strategy, variant)` sweep pairs | ✅ exact |
| S-55 margins (BTC full +1536.2/64 tr; XAU last_12m +0.57%/4 tr; EUR negative both windows) | ✅ exact |

## Correct claims — fixed

| Claim | Verdict | Fix applied |
|---|---|---|
| **A.1** results-check step lacks `if: always()`; CI at `e6350d5` shows the self-test failing and step 5 never running | ✅ Correct — `.github/workflows/ci.yml` had no `if: always()`; Actions run 40951793306 (e6350d5) = `failure`, job log shows `30/32 mutation cases passed` then the results step skipped | Added `if: always()` + comment to the results-check step |
| **A.2** step label says "32 mutation cases" but the suite has 35 | ✅ Correct — label said 32, self-test reports 35 | Dropped the count from the label (it would drift again) |
| **B.1** X5 is one-directional: `candidate`/`finalist` + a terminal trial-log outcome (`rejected`/`parked`/`tested`) passes silently | ✅ Correct — `check_results.py` only fired X5 for `{rejected, parked, tested}` | X5 made two-sided (terminal-status direction kept; new non-terminal-status direction added; `finalist`+`tested` allowed as transient) |
| **B.2** add the two mutation cases | ✅ Correct | Added both (`candidate`+`rejected`, `parked`+`rejected`); self-test now **37/37** |
| **B.3** saturation unenforced, `X15` is the next free code, add a WARN/FAIL guard | ✅ Correct in logic — highest code in use is `X14`; the guard is sound | Added `check_saturation` (X15): WARN ≥4, FAIL ≥8 per `(base indicator, timeframe)` family |
| **C.1** 86 trial-log rows are dated in the future | ✅ Correct — `grep -c` = 86 | *Not executed — see "Deferred" below (collides with the WIP / needs C.2 rename + registry `Last run` rewrite)* |
| **C.2** dated artifacts are really from 2026-10-30 (git commit times prove it) | ✅ Correct — `e6350d5`/`804964d`/`84547d8` all committed 2026-10-30, yet artifacts are named 11-01…11-06 | *Not executed — rename blast radius (≈352 refs) + owner decision D1* |
| **C.3** "Rejected combinations" table has 7 rows, missing the 101 rejected | ✅ Correct — table has exactly 7 data rows (S-01…S-07) | *Not executed — needs the C.2 rename for correct doc links* |
| **D.1** sweep harness hardcodes `WINDOWS`/`INSTRUMENTS`/`COST_TIERS` and a `sid != "s17"` special case | ✅ Correct — confirmed at the cited lines | Import `INSTRUMENTS`/`COST_TIERS`/`_load_config`/`_window_bounds` from `run_matrix`; derive the timeframe from config; removed the `s17` special case |
| **D.2** add a "sweep-only, not canonical" note | ✅ Correct | Added the header note |
| **E** S-55 is effectively 98%-long buy-and-hold, edge almost entirely BTC | ✅ Correct — margins reproduced exactly | *Not executed — read-only holdout analysis, owner decision D4* |

## One discrepancy (review §B.3 / D2) — documented, not silently "fixed"

The review's D2 table states:

> **WARN at ≥ 4, FAIL at ≥ 8.** At baseline the max group is 5, so this produces
> **6 warnings and 0 failures.**

The review body lists exactly six saturated families (`ema`, `st_dir`, `atr`,
`mfi`, `roc`, `aroon_down`, all `5m`). That list is *incomplete*, not wrong:
applying the review's own stated grouping rule ("a strategy belongs to a family
if its backticked key indicators reduce to that base name", `willr_60→willr`,
`macd_hist_6_24→macd_hist`) over the 102-row baseline yields **12 families ≥ 4,
max size 7**:

```
7 ema 5m · 7 roc 5m · 6 st_dir 5m · 6 stoch_k 5m · 6 close 5m · 5 rsi 5m ·
5 atr 5m · 5 mfi 5m · 5 vol_rel 5m · 4 willr 5m · 4 stoch_d 5m · 4 aroon_down 5m
```

The six the review names are all present; it additionally misses `close`,
`stoch_k`, `rsi`, `vol_rel`, `stoch_d`, `willr`. **Conclusion:** the guard's
logic and the FAIL threshold are correct; only the *predicted baseline warning
count* (6, max 5) is understated. My implementation follows the stated rule and
reports **12 X15 warnings, 0 failures** — the build still stays green, which is
the property D2 actually cares about.

## Deferred (not executed) — and why

These review items are **correct in substance** but I did not execute them,
because each either collides with the uncommitted WIP or is an owner sign-off
gate the review itself marks as "stop and ask":

- **C.1 / C.2 / C.3** — the trial-log date fix, the dated-artifact rename, and
  the "Rejected combinations" table all interact with each other (the table's
  links point at the renamed sweep docs) and with the WIP's 10 new strategies.
  C.3 in particular needs the C.2 rename to keep its links valid. These also
  rest on the review's "the registry is at 102 / do not add strategies" premise,
  which the working tree (S-103…S-112 staged) has already moved past.
- **E** — the one-shot holdout analysis. The review forbids *me* promoting S-55
  or changing `oos.pass_criteria`; that is the owner's call after seeing the
  numbers.
- **Plan #4 phases 1–5** (freeze, variant registry, pin, baseline re-run,
  OOS) — larger structural changes; the review's own D9/D10 say nomination and
  freeze are human decisions.

## Files changed by this verification pass

- `.github/workflows/ci.yml` — A.1 (`if: always()`) + A.2 (label)
- `scripts/check_results.py` — B.1 (two-sided X5), B.3 (X15 saturation guard + docstring)
- `scripts/test_check_results.py` — B.2 (two new mutation cases)
- `scripts/strategy_variants.py` — D.1 (config-sourced windows/instruments/costs/timeframe,
  `s17` special case removed) + D.2 (header note)

Verification (clean baseline, WIP stashed): `check_results.py` → **0 failures,
12 warnings (X15), 220 notes, PASS**; `test_check_results.py` → **37/37**;
`pytest tests/ -q` → **455 passed**; `strategy_variants.py` re-run of one
cell-set is **byte-identical** to the committed CSV (18/18 cells).

## Decision defaulted

- **X15 baseline count** (D2): I kept the review's WARN ≥4 / FAIL ≥8 thresholds
  and reported the true count (12 warnings, max 7) rather than the review's
  stated 6/max-5. No FAIL is triggered, so the build stays green — the outcome
  D2 wanted.
