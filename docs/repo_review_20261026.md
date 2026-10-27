# Moneta Legacy Review — Consolidated (2026-10-27)

> Consolidates `legacy/review1.md` (EN, broad scope), `legacy/review2.md` (ZH, v1+v2),
> `legacy/review3.md` (ZH, incl. tested PSAR/SuperTrend patch), `legacy/review4.md` (ZH, loop + indicators).
> Key claims re-verified against the repo on 2026-10-27 (sharpe formula, 5m-default parquet,
> zero `psar`/`supertrend` hits outside `.venv`, no indicator tests, no `scripts/verify_indicator_parity.py`).

---

## 1. Points all four reviews agree on

| # | Finding | Review(s) | Verified |
|---|---------|-----------|----------|
| A1 | **Workflow loop exists and works once** — WORKFLOW.md steps 0–7 + gates, registry dedup, S-01 ran end-to-end | 1, 2, 3, 4 | ✅ |
| A2 | **PSAR and SuperTrend are absent** from the feature library | 1, 2, 3, 4 | ✅ (grep: 0 hits in project code) |
| A3 | **The `6/12/24/60/120` grid is a *window (bar-count) whitelist only*** — non-window parameters (PSAR accel/max, SuperTrend multiplier, BB sigma, KC mult) must be free, named constants, never library defaults | 1, 2, 3, 4 | ✅ (`validate_grid()` only checks `n_grid`/`pairs`) |
| A4 | **No indicator tests / six quality gates unimplemented** — `tests/` covers only extract/aggregate; `scripts/verify_indicator_parity.py` promised in `docs/indicators.md` §8 does not exist | 1, 2, 3, 4 | ✅ |
| A5 | **`sharpe` in `strategy_rsi.py:145` is wrong** — `tr.mean()/tr.std(ddof=1) * sqrt(len(tr) * 12)`; sharpe grows ∝ √n_trades, so it is not comparable across strategies or windows | 2, 3 | ✅ (confirmed in source) |
| A6 | **No shared backtest engine** — each strategy re-implements ~100+ lines of accounting (long-only), and metric definitions drift | 1, 2, 3 | ✅ |
| A7 | **No true out-of-sample discipline** — "last 12 months" is computed at run time (in-sample), rejected trials seed the next hypothesis (data snooping), no attempt count logged | 1, 2, 3, 4 | ✅ |
| A8 | **18-cell matrix run + report copy-paste is fully manual** — G5 demands traceability but `--json` is never used in the documented command | 1, 2, 3 | ✅ |
| A9 | **Root `README.md` is badly outdated** (claims single commit, untracked files, unimplemented pipeline) | 2, 3 | ✅ |
| A10 | **Environment lock-in** — `data/` parquets and `.venv` are gitignored; the loop cannot run in CI/cloud/other machines | 2, 3, 4 | ✅ |

### Disagreements resolved

- **review4 vs review1 vs review3 on extra indicators**: review4 recommends KST → TRIX → Vortex → PVO;
  review3 argues most oscillators are collinear with the existing momentum family and prefers
  session high/low, ATR-normalized regression slope + R², and rolling bb_width quantile;
  review1 lists KAMA, CMO, McGinley Dynamic as P2/P3.
  **Consensus position**: *do not bulk-add oscillators*. The project has 226 features and no
  multiple-testing control — adding collinear columns increases the data-mining surface.
  Take only genuinely new dimensions (trend state, session structure, slope/quality) after the
  baseline is trustworthy.
- **review3 vs review2 on column counts**: both derive the new-count formula differently
  (review3: 1h 234→270, 5m 259→305 with default params; review2: 234→258, 259→289 with a
  narrower "package A"). Not a contradiction — different parameter sets chosen. The rule is:
  recompute and sync **four files** (`pipeline/indicators.py`, `config/indicators.yml`,
  `docs/indicators.md`, `strategy/STRATEGY_BACKGROUND.md` + `docs/README.md` literals) on every change.

---

## 2. Ranked action list (consolidated, deduplicated)

Priority order is by **risk reduction per unit of effort**. Anything in T0 blocks or
corrupts everything that comes after it.

### T0 — Do before running more strategies or adding indicators (days)

| # | Action | Why it is #1 class | Source |
|---|--------|--------------------|--------|
| **0.1** | **Fix the silent 1h-on-5m failure mode (review2 B1)**: `strategy_rsi.py` defaults `--parquet` to the 5m table and WORKFLOW.md Step 4 never passes `--parquet`, so a 1h strategy (e.g. pre-registered S-02) runs on 5m bars with *no error at any gate*. Add `--timeframe {5m,1h}` + `bar_seconds` assertion, and/or make each strategy doc pin its parquet path. Also extend G0 to check both parquet files. | **Highest-severity finding in all four reviews.** Produces plausible-but-wrong numbers that pass every gate and get written into the registry — the single biggest threat to trust in the loop. | review2 B1/B5 |
| **0.2** | **Fix `sharpe` and lock metric definitions** (`strategy_rsi.py:145` → annualize from `n_trades / n_years` or switch to daily-equity Sharpe); define total_return / max_dd / sharpe / exposure once in SAD §7.2 with exact formulas. | All cross-strategy comparison is downstream of this; currently sharpe is monotonic in trade count. | review2 B2, review3 §3.2, review1 §6.3 |
| **0.3** | **Extract a shared backtest engine** (`strategy/engine.py` or `strategy/lib/engine.py`): long+short, costs per instrument, trade ledger, end-of-data closure, fixed metric formulas; strategy files emit only target-position sequences. Add golden-value tests (`tests/test_metrics.py`) on constructed price paths. | Stops metric drift (A6), removes per-strategy re-implementation of accounting (which AI re-checks only via its own self-review, G3), and is a prerequisite for the automated matrix runner. S-01's RSI numbers must reproduce as a regression baseline. | review1 §6.3, review2 §2.2②, review3 §3.3 |
| **0.4** | **Write `tests/test_indicators.py` on synthetic OHLCV** (no real data needed, runs in CI): prefix-invariance/causality (truncate to row k, recompute, first k rows must match), range invariants (RSI∈[0,100], bb_lower≤bb_upper, direction∈{±1,0}), degenerate input (flat/zero-range bars → no Inf/NaN), as-of join order. This is the "six gates" promised in `docs/indicators.md` §8, currently 0% implemented. | Before touching a 690-line, 259-column, untested feature engine, changes "fail silently as semantically wrong columns" (review2 ⑥). Every later step depends on trusting the feature table. | review2 B7, review3 §3.2, review4 §1.2, review1 §5 |
| **0.5** | **Add OOS discipline**: reserve a fixed holdout window (e.g. 2025-07 → 2026-10) used *only* for finalists; pin the "last 12 months" window to a fixed anchor date (review2 B4, also cross-run comparability); add a trial log (`strategy/trial_log.md`) recording every attempt incl. rejections, and a "N strategies tried before this one" line in every report. | The stated goal is *repeated* loop runs — without this, batch iteration mathematically guarantees overfit selection (BRD's own #1 risk). Cheap (doc + config) and blocks the biggest scientific failure mode. | review2 ⑤/B4, review3 §3.2, review4 §5.3 |

### T1 — Make the loop actually repeatable (a week or two)

| # | Action | Why | Source |
|---|--------|-----|--------|
| **1.1** | **`strategy/run_matrix.py`**: run the 3-instrument × 2-window × 3-cost matrix automatically; persist each cell to `strategy/results/<id>/<inst>__<win>__<cost>.json` and emit a paste-ready markdown table + `summary.csv`. G5 traceability becomes automatic instead of "human discipline". | The main friction point in "can I run this loop over and over" (review2 ①); also creates the data needed for cross-strategy questions. | review2 ①/③, review3 §3.3 |
| **1.2** | **Parameter-governance doc fixes (B10/B11)**: rewrite `docs/indicators.md` §4.1 to the A/B split (window vs non-window); require all non-window params as explicit named constants in a `config/indicators.yml` `constants:` block (never rely on library defaults → silent drift on version bumps). ~30 min of doc work that prevents the exact mistake of forcing `PSAR_ACCEL=0.02` into the grid. | All four reviews flagged the ambiguity; review2 v2 elevated it to a rule. | review2 B10/B11/§3.0, review4 §4 |
| **1.3** | **Small fixes (B3, B6, B9)**: report path → `strategy/docs/...` unambiguously in both WORKFLOW.md and generated_strategy.md; add strategy-layer rule for `is_gap_bar` / `is_partial` / `is_near_market_close` (no new entries on gap bars by default); state explicitly that buy-hold baseline is cost-free while strategy is cost-bearing. | 10-minute doc fixes; B3 causes misfiled reports, B6 forces every new strategy to re-decide gap handling. | review2 B3/B6/B9 |
| **1.4** | **Refresh root `README.md` "Current Status"** to match reality (40 commits, tracked pipeline, 30 tests, implemented extract/aggregate/indicators). | First thing any AI collaborator reads; currently actively misleading. | review2 §1.1, review3 §3.2 |
| **1.5** | **Reproduce S-01 from a clean environment** (sanity_check + run RSI matrix once) and audit equity/trade-ledger/cost math against the shared engine (0.3). Confirms the baseline the whole loop is measured against. | review1 Phase 1; cheap insurance before scaling. | review1 §7 |

### T2 — Expand the feature library (after T0+T1)

| # | Action | Why / notes | Source |
|---|--------|-------------|--------|
| **2.1** | **Implement PSAR (`psar`, `psar_dir`, `psar_dist/atr`) and SuperTrend (`st_{n}_{k}`, `st_dir`, `st_dist`, plus `h1_*` 1h-state projected into the 5m table)** using the A/B parameter rule: SuperTrend ATR `n` from the grid (lib default 10 must be overridden), multiplier free but named; PSAR accel/max free but named; SuperTrend `offset` must be explicit 0. Use `talib.SAR` (exists) + a causal recursive SuperTrend (TA-Lib has none); validate with prefix-invariance and parity vs `pandas_ta_classic`. | **Unanimous #1 requested feature across all four reviews** — adds the "trailing-stop / trend-state reversal" dimension the current MA/EMA trend family lacks. review3 already has a tested patch (`moneta_psar_supertrend.patch`) as a starting point — but note it and review2 disagree on column naming/counts, so reconcile with the 4-file sync rule first. | all four |
| **2.2** | **A small set of genuinely new-dimension features only** (pick at most 2–3, each with its own test): previous-session high/low/open-range (reuses `session_reset_index`, causal, sparse); ATR-normalized linear-regression slope + R² (trend quality); rolling (windowed, never full-history) bb_width quantile (squeeze *strength*). | Fills real information gaps without collinear oscillators. | review3 §2, review1 §3.3 |
| **2.3** | **Explicitly *not* adding** (consolidated rejection list): KST, TRIX, PVO, Vortex, CMO, Ultimate Oscillator, McGinley Dynamic (collinear with existing momentum/trend families); Ichimoku (chikou span = look-ahead), Zigzag/Fractals (repaint); raw OBV/PV (non-stationary, cross-instrument incomparable); z-score (≡ `bb_pctb`). | Prevents parameter/column explosion with no new information while multiple-testing control is still absent. | review4 §3.1, review3 §2, review2 §3.1 |

### T3 — Reproducibility & automation (optional, when scaling)

| # | Action | Source |
|---|--------|--------|
| **3.1** | Commit a small fixture parquet (e.g. EUR_USD, ~20k 5m bars, a few MB) so smoke backtests + the indicator test suite can run in CI / cloud / any machine; unblocks AI-assisted runs off the primary laptop. | review2 ④, review4 §1.2 |
| **3.2** | GitHub Actions: `pytest` (incl. new indicator + metric tests) + registry structure check (`check_registry.py`: table column counts, usage map, duplicate detection → machine-enforced G2). | review2 §5 B7 / step 13 |
| **3.3** | Fix `generated_strategy.md` §5 ambiguity ("at 0/2/5 bps" — all tiers or any tier?) and the S-03 trade-count budget (300-trade cap likely violated by a filtered 5m RSI). | review3 §3.2 |
| **3.4** | Consider walk-forward validation once 5–10 strategies have a clean OOS record. | review2 ⑤, review1 §6.4 |

---

## 3. What is MOST important (bottom line)

**Do not add indicators or run more strategies until T0 is done.**

The single most important action is **0.1** — the 1h-strategy-runs-on-5m-data silent
failure mode. It is the only finding that produces *wrong numbers that pass every quality
gate*, and it is one step away from being triggered (S-02 is a pre-registered 1h strategy).
It is also the cheapest fix.

Immediately after: **the shared engine + correct sharpe (0.2/0.3)** — because "can I run
this loop over and over?" (your core question) is currently answered *yes, but not
reliably*: manual 18× copy-paste, per-strategy accounting, non-comparable metrics.
T0 turns the loop from "runs once" into "runs *reliably and comparably*"; T1 makes it
repeatable with low friction; only then does T2 (PSAR/SuperTrend + a few new-dimension
features) add value instead of more data-mining surface.

**Suggested commit order:** 0.1 → 0.2 → 0.5 → 0.3 → 0.4 → 1.x (docs are a 30-minute batch)
→ 2.1 → 2.2.

## 4. Verification caveats (shared by the reviewers)

- review1/2/3 could not run on real data (`data/` gitignored); review3's PSAR/SuperTrend
  patch was verified on synthetic data only (53 pytest cases, prefix-invariance + pandas-ta
  parity 99.8–99.99%).
- All "column count" projections (258/270/289/305) are parameter-set-dependent — recompute
  at implementation time and sync the four files.
- review2 could not confirm `talib.SAR` / `pandas_ta_classic.supertrend` signatures in a
  sandbox; `inspect.signature` in `.venv` before relying on exact parameter names.
