# 8-Iteration Improvement Sweep — S-73 .. S-87 (2026-11-05)

Fifteen more new strategies (S-73 .. S-87) were designed, unit-tested, and
then each was evaluated over **8 improvement iterations** on the shared
in-sample matrix. This is the sixth batch in the series; S-08 .. S-17 were
batch 1 ([strategy_sweep_2026-10-30.md](strategy_sweep_2026-10-30.md)),
S-18 .. S-27 batch 2 ([strategy_sweep_2026-11-01.md](strategy_sweep_2026-11-01.md)),
S-28 .. S-42 batch 3 ([strategy_sweep_2026-11-02.md](strategy_sweep_2026-11-02.md)),
S-43 .. S-57 batch 4 ([strategy_sweep_2026-11-03.md](strategy_sweep_2026-11-03.md)),
and S-58 .. S-72 batch 5 ([strategy_sweep_2026-11-04.md](strategy_sweep_2026-11-04.md)).

* **Scope:** S-73 .. S-87 (15 strategies) × 8 variants × 3 instruments
  (EUR_USD, BTC_USD, XAU_USD) × 2 windows (`full`, `last_12m`) × 3 cost tiers
  (0/2/5 bps) = **2,160 cells**, all run through the shared engine
  (`strategy/engine.py`).
* **Data:** in-sample only — `until ≤ 2025-07-31`. **No OOS holdout was
  touched** (the holdout is a one-shot gate reserved for the single finalist
  under `config/strategies.yml → oos.pass_criteria`). `strategy/oos_ledger.json`
  remains `{"version":1,"consumptions":[]}`.
* **Harness:** `scripts/strategy_variants.py` (parallel sweep →
  `strategy/results/iterations_2026-11-05.csv`).
* **Run:** 2,160 cells, 12 workers, 0 error cells.
* **Signal sources:** all 15 use feature columns that no earlier strategy
  (S-01..S-72) traded as its primary signal. New families this batch:
  slow-window oscillators (`aroon_up_60` S-73, `willr_60` S-74, `cci_120`
  S-75, `stoch_k_60` S-76, `mfi_60` S-77), slow-window volatility/momentum
  (`atr_pct_120` S-78, `roc_120` S-79), **time-of-day regime** (`hour_sin`
  S-80, `dow_sin` S-81 — never used before), **true-range collapse** (`tr`
  S-82), **slow-PSAR direction** (`psar_dir_0p02_0p2` S-83 — the `_0p02_0p2`
  PSAR family was untested), **dual-SuperTrend 120/24** (S-84), **1h
  two-scale SuperTrend-120** (`h1_st_dir_120_3` S-85), dual time-of-day
  confluence (S-86), and slow-ROC + volume confluence (S-87).

## Results — ranked by mean edge vs buy-hold (2 bps, 3 instruments)

`edge = total_return − buyhold_return` (both in %), averaged over the 3
instruments for a variant across both windows. The decision-relevant figures
are the trade count (`trades_per_year`), whether any variant beat buy-hold on
**≥2 of 3 instruments on both windows** (the `oos.pass_criteria` bar), and the
trade-count ceiling (54/yr).

| # | Strategy | Rule (signal columns) | Best variant (mean edge) | Beat BH ≥2/3 (both windows) |
|---|----------|-----------------------|:---:|:---:|
| 1 | **S-81** | `dow_sin` (day-of-week) | `1h` **−11.9** | ✗ (BTC-only: BTC `last_12m` +15 to +29%; loses on EUR/XAU & BTC `full`) |
| 2 | S-75 | `cci_120` (slow CCI) | `1h` **−44.3** | ✗ (0/3) |
| 3 | S-74 | `willr_60` (slow %R) | `1h` **−115.9** | ✗ (0/3) |
| 4 | S-76 | `stoch_k_60` (slow stoch) | `1h` **−150.0** | ✗ (0/3) |
| 5 | S-79 | `roc_120` (slow ROC) | `1h` **−159.8** | ✗ (0/3) |
| 6 | S-83 | `psar_dir_0p02_0p2` | `1h` **−160.3** | ✗ (0/3) |
| 7 | S-86 | `hour_sin`+`dow_sin` | `looser` **−173.5** | ✗ (0/3) |
| 8 | S-84 | `st_dir_120_3`/`st_dir_24_3` | `1h_ema_guard` **−190.2** | ✗ (0/3) |
| 9 | S-78 | `atr_pct_120` | `1h` **−248.7** | ✗ (0/3) |
| 10 | S-80 | `hour_sin` (time-of-day) | `1h` **−249.3** | ✗ (0/3) |
| 11 | S-73 | `aroon_up_60` (slow aroon) | `1h` **−251.8** | ✗ (0/3) |
| 12 | S-77 | `mfi_60` (slow MFI) | `1h` **−255.2** | ✗ (0/3) |
| 13 | S-82 | `tr` (true-range collapse) | `1h` **−257.8** | ✗ (0/3) |
| 14 | S-87 | `roc_120`+`vol_rel_24` | `1h` **−261.1** | ✗ (0/3) |
| 15 | S-85 | `h1_st_dir_120_3`/`st_dir_24_3` | `ema_only` **−271.8** | ✗ (0/3) |

## The finding: all 15 rejected, one new near-miss (S-81, BTC-only)

**No strategy in S-73..S-87 clears the `oos.pass_criteria` in-sample bar.**
The closest is **S-81** (`dow_sin`, day-of-week regime), whose best variant
(`1h`, −11.9% mean edge) beats buy-hold on **BTC `last_12m` only** (+15.4%
`1h`, +29.0% `looser`) while *losing* on EUR and XAU in every window and on
BTC `full`. That is the same single-instrument artifact as round 2's S-45 —
the `≥2 of 3 instruments on both windows` bar exists precisely to exclude it.
Rejected, not parked.

### S-81 decomposition (the only cross-window-positive cell set)

| Instrument | Window | base | 1h | looser |
|-----------|--------|-----:|-----:|-------:|
| BTC_USD | full | −144.5% | −40.8% | −144.5% |
| BTC_USD | last_12m | **+27.7%** | **+15.4%** | **+29.0%** |
| EUR_USD | full | −17.7% | −20.5% | −17.7% |
| EUR_USD | last_12m | −2.0% | −4.4% | −1.3% |
| XAU_USD | full | −15.1% | −16.8% | −15.1% |
| XAU_USD | last_12m | −0.4% | −4.4% | +1.0% |

Only **1 of 6** instrument-window cells is positive (BTC `last_12m`), and
`full`-window BTC is deeply negative (−144%) — so the positive `last_12m`
BTC cell is a regime-overfit, not a repeatable edge. The other 14 strategies
are uniformly worse (best mean edge ≤ −44%), confirming the cost×frequency and
single-instrument signatures.

## Consistent pattern (reproduces batches 1–5)

1. **`1h` / low-frequency iterations dominate** the best-variant ranking for
   12 of 15 strategies — the sixth consecutive batch with this outcome.
2. **Slow-window (`_60`/`_120`) oscillators do not help.** S-73..S-79 (slow
   Aroon/%R/CCI/Stoch/MFI/ATR%/ROC) all lose ≥ −44% mean edge, matching the
   batches-1–4 finding that widening the window does not manufacture an edge
   on this data.
3. **Time-of-day features (S-80/S-81/S-86) are not an edge.** S-81's BTC-only
   `last_12m` positivity is a calendar-overfit; the dual confluence (S-86) and
   the `hour_sin` single (S-80) lose uniformly.
4. **Confluence does not compound** (S-84, S-86, S-87, S-85) — consistent
   with the previous five batches.

## Registry / trial-log action

All 15 are registered in `STRATEGY_REGISTRY.md` as **`rejected`**. All 15 are
rows 73–87 in `strategy/trial_log.md`; the Configuration tally is updated to
**87 strategies / 607 configurations / ≥10,926 cells**. No OOS consumption
occurred; `strategy/oos_ledger.json` remains
`{"version":1,"consumptions":[]}`. The S-55 `parked` finalist candidate from
round 2 remains the only strategy still awaiting the human-nominated one-shot
OOS gate.
