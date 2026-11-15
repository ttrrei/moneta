# 04 — Strategy Master Plan (总纲)

> Baseline commit `936f7b9`. This is the **contract** for all new research. Every direction file
> (`05_*`, `06_*`, `07_*`, and the stubs below) inherits §3 (success), §4 (stage gates), §5 (budgets)
> and §6 (registration). Read `AGENTS.md` first. This file has two audiences: the owner (decisions in §9)
> and the AI executors (rules and formats).

## 1. Where we are and why we change direction

At `936f7b9`: **132 strategies, 827 configurations, ≥ 14,886 evaluated cells**; none is a finalist; two are
`parked` (S-55, S-103). What the sweeps (`strategy/results/iterations_*.csv`) show:

- **Cost wall.** Across the 105 strategies in the sweep CSVs, the median config trades ~721 times per year and its
  median gross return per trade is 0.16–0.9 bps by family (`full` window, 0 bps), against a round-trip cost of
  roughly 4 bps (assuming 2 bps is per side — to be verified in `02_*` E1). Only the low-frequency families
  (calendar, multi-timeframe, volatility regime) show a per-trade edge above cost, and those figures include the
  BTC bull trend.
- **One instrument carries the results.** At 2 bps, 44% of `BTC_USD` cells are net-positive versus 23% for
  `XAU_USD` and 7% for `EUR_USD`. A bare "net return > 0" is satisfied mostly by market beta.
- **One kind of idea.** Almost every strategy is a threshold rule on 1–2 OHLCV-derived indicators of a single
  instrument on 5m/1h bars. They are highly correlated; the *effective* number of independent tries is far smaller
  than 827. The shortfall is diversity of hypotheses, not volume.
- **The yardstick was tied to the long-only, buy-and-hold framing** (BTC +1538% in the sample), which cannot be
  met by any strategy that is not almost always long BTC.

Decision (owner): **success = positive absolute return net of costs, not compared with buy-and-hold**
(long/short and market-neutral strategies are in scope). §3 adds guardrails so "positive" cannot come from beta
or from luck.

## 2. Taxonomy — directions by source of edge

Classify by the **hypothesis**, not by the indicator. The conventional-indicator search is closed.

| ID | Direction | Hypothesis | Registration | Needs |
|---|---|---|---|---|
| L-0 | Conventional indicators (RSI, MACD, bands, …) on 5m/1h | none distinct | **Closed** (S-01 … S-132, frozen) | — |
| D-A | Slow trend + volatility targeting | Time-series momentum is a documented risk premium; risk-scaled long/short positions at daily horizons trade rarely, so the cost wall does not apply | `05_*` (this pass) | 03: D2 |
| D-B | Exit design and payoff asymmetry | Entries carry little edge; **exits** (trailing stops, time stops, targets, long/short asymmetry) shape the payoff. Tested against a random-entry control so an "edge" is not just beta | `06_*` (this pass) | 03: D2, D3; 02: E1 exits |
| D-C | Cross-sectional (many instruments) | Relative strength / reversal across instruments, dollar-neutral, is independent of market direction and gains statistical power from many instruments | `07_*` (this pass) | 03: D0, D1, D2, D4, D5, (D7) |
| D-D | Structure features | Prior-period extremes, session ranges, opening range, confirmed swing levels carry information the oscillators do not | **Stub** — register after the screening layer (02 E6) shows which features survive G1 | 03: D3 |
| D-E | Generated indicators / ML | Combinations of many weak signals in a purged, walk-forward model | **Stub** — last; needs purged cross-validation infrastructure and a strict trial budget | 02, 03 |

Stubs are listed so the idea is not lost; **they cannot be executed** until a registration file exists (§6).

## 3. Success criteria (default thresholds — owner may edit in §9 **before the first registration commit**)

**Primary (owner):** net absolute return > 0 after costs, on the direction's evaluation unit:
the equal-risk portfolio of the registered universe for D-A and D-B; the dollar-neutral portfolio for D-C.
No comparison with buy-and-hold.

**Guardrails (all must hold for a config to count as a success):**

| # | Guardrail | Default |
|---|---|---|
| S-1 | **Significance** — net-return p-value from a stationary block bootstrap, Holm-corrected across **all** the direction's registered configs | family-wise α = 0.10 |
| S-2 | **Market beta** — beta of daily net returns to the equal-weight daily return of the same universe's buy-and-hold basket (diagnostic, not a comparison); alpha t-stat > 0 | \|β\| ≤ 0.30 |
| S-3 | **Concentration** — no single instrument contributes more than a share of total net PnL (universes with ≥ 3 instruments) | ≤ 60% |
| S-4 | **Subperiods** — calendar years in the in-sample window | net positive in ≥ 60% of years; worst year ≥ −2 × realised annual vol |
| S-5 | **Cost stress** | net return still > 0 at 2× the base cost |
| S-6 | **Parameter stability** — grid neighbours (±1 step per parameter) of the chosen config | ≥ 70% of neighbours net positive |
| S-7 | **Activity** — enough independent observations (non-overlapping holding periods or rebalances) | ≥ 100 per config |
| S-8 | **Economic relevance** — net `sharpe_weekly` | ≥ 0.4 |

**OOS adjudication (G5):** net return > 0 at the base cost **and** at 2× the base cost, and S-2 holds on the
holdout. No significance test is imposed on the ~1.2-year holdout (too little power); it is a sanity gate, not proof.
The criteria are written into `config/strategies.yml` (`oos.success_criteria_by_direction`, see `01_*` S2.2)
and frozen at the first registration commit; the criteria hash is recorded in `trial_log.md`.

The legacy rule (beat buy-and-hold on ≥ 2 of 3 instruments, 54 trades/year) stays only for L-0.

## 4. Stage gates (every config of every direction passes through these in order)

| Gate | What | Who/what enforces |
|---|---|---|
| G0 | **Registration** committed (§6) before any result | checker R2/R3, `run_direction.py` |
| G1 | **Screening** (`02_*` E6): FDR q ≤ 0.10 and gross-edge ÷ round-trip-cost ≥ 2. *Gating* for feature-selection directions (D-D, D-E); *diagnostic only* for directions whose signals are fixed by the registration (D-A, D-B, D-C) | screening layer |
| G2 | **In-sample evaluation** of every registered config on the `full` window; primary criterion + S-1 + S-7 | `run_direction.py` + checker |
| G3 | **Robustness**: S-2, S-3, S-4, S-5, S-6, S-8 on the survivors | checker |
| G4 | **Finalist pin**: a human sets status `finalist`, `oos_variant`, `oos_config_hash` | `01_*` S1.3 |
| G5 | **OOS once**: owner-started, single process, one-shot ledger | `run_matrix`, ledger |

A direction is **closed** if after G2 no registered config meets the primary criterion and S-1. Re-opening needs a
new `version` with a new hypothesis; its configs count toward the direction's and the global budget.

## 5. Budgets and multiple-testing accounting

- Each direction file fixes `max_configs` (an explicit, enumerated grid). `max_configs` equals the grid size.
- Global budget for new work: `research.global_config_budget` in `config/strategies.yml` (default **200**).
  Past work is already counted separately (827 legacy configurations).
- `trial_log.md` records, per row: `direction`, `config_id`, `n_configs_direction_before`, `n_configs_global_before`.
- Holm correction (S-1) uses the direction's `max_configs`, not the number you happened to look at.
- The holdout is a single shared resource (`01_*` H1): at most **one** finalist across all directions consumes `oos1`.
  Later finalists wait for `oos2` (a new, non-overlapping, later window after 2026-10-22, accruing with new data).

## 6. Registration protocol

1. A direction file contains a **registration block** — a fenced `yaml` block under the heading `## Registration` —
   with these keys: `direction_id`, `version`, `title`, `status`, `hypothesis`, `universe`, `data_requires`,
   `signals`, `grid`, `excluded_combos`, `max_configs`, `sizing`, `costs`, `windows`, `kill`.
2. `grid` is an explicit parameter→values map; the cross product minus `excluded_combos` is enumerated by
   `scripts/run_direction.py`; `max_configs` must equal that count. `windows` may contain only `full` and `last_12m`.
3. The **owner reviews and commits** the file. Only then may anything run (checker R2). The `status` field is
   informational; git history is the authority.
4. After the first result commit, the file is immutable except via a dedicated commit that bumps `version`
   (checker R3). A new version's configs count toward the budgets.
5. Ideas arising mid-way go to `ideas.md`. They become executable only by being added to a new direction file or a
   new version of an existing one, in a commit **before** any run that uses them.
6. `scripts/run_direction.py` refuses uncommitted registration files and any config outside the enumerated grid.

## 7. Cost and metrics rules for all directions

- Costs: use the instrument-specific model in `config/costs.yml` once the owner has filled it in (`03_*` D7).
  Until then run the uniform `0 / 2 / 5 bps` tiers and label every report "uniform-cost".
- Positions are decided at the close of bar `t` and applied at the open of `t+1`. No same-bar information.
- Reported metrics (all from the shared core `strategy/core/sim.py`): net return, `sharpe_weekly`, max drawdown,
  annual turnover, mean net position, beta to the universe basket, PnL share by instrument, calendar-year returns.
- Horizons are in bars of the direction's own timeframe; daily bars use the `03_*` Q1 boundary.

## 8. Order of work and dependencies

1. `01_*` S1–S2 (freeze, pins, holdout split, criteria hook) → 2. `02_*` E0–E6 → 3. `03_*` D0–D8 →
4. **Owner finalises §9 and commits this file** → 5. owner commits each direction registration → 6. run G2/G3.
`05_*` can start once `03_*` D2 and `02_*` E1 exist; `06_*` additionally needs D3 and the exit state machine;
`07_*` needs D0, D1, D4, D5 (and preferably D7).

## 9. Owner decisions (defaults apply unless edited before the first registration commit)

| # | Decision | Default |
|---|---|---|
| M1 | Success guardrail thresholds (§3) | as listed |
| M2 | `research.global_config_budget` | 200 |
| M3 | Which finalist uses `oos1` | the direction with the strongest G3 evidence at nomination time; owner decides |
| M4 | Instrument-specific costs | owner supplies `config/costs.yml` before D-C is evaluated |
| M5 | Stubs D-D and D-E | register only after G1 evidence (D-D) and after purged-CV infra exists (D-E) |

## 10. Definition of done for this plan

- [ ] `01_*`, `02_*`, `03_*` completed per their own checklists.
- [ ] §9 reviewed; this file committed; criteria written to config and hashed in `trial_log.md`.
- [ ] Each direction registered by a separate owner commit **before** its first run.
- [ ] Checker rules R1–R7 active (R7 = global budget) with mutation tests.
