# 8-Iteration Improvement Sweep — S-58 .. S-72 (2026-11-04)

> Date provenance: `2026-11-04` is a historical batch identifier. Its CSV was
> recorded by `84547d8 2026-10-30T20:58:24+11:00`; the exact run time is unavailable. Full and
> last_12m overlap. Signal corrections and evidence limits are described in
> [the independent verification](../../docs/review_verification_20261031.md).

Fifteen more new strategies (S-58 .. S-72) were designed, unit-tested, and
then each was evaluated over **8 improvement iterations** on the shared
in-sample matrix. This is the fifth batch in the series; S-08 .. S-17 were
batch 1 ([strategy_sweep_2026-10-30.md](strategy_sweep_2026-10-30.md)),
S-18 .. S-27 batch 2 ([strategy_sweep_2026-11-01.md](strategy_sweep_2026-11-01.md)),
S-28 .. S-42 batch 3 ([strategy_sweep_2026-11-02.md](strategy_sweep_2026-11-02.md)),
and S-43 .. S-57 batch 4 ([strategy_sweep_2026-11-03.md](strategy_sweep_2026-11-03.md)).

* **Scope:** S-58 .. S-72 (15 strategies) × 8 variants × 3 instruments
  (EUR_USD, BTC_USD, XAU_USD) × 2 windows (`full`, `last_12m`) × 3 cost tiers
  (0/2/5 bps) = **2,160 cells**, all run through the shared engine
  (`strategy/engine.py`).
* **Data:** in-sample only — `until ≤ 2025-07-31`. **No OOS holdout was
  touched** (the holdout is a one-shot gate reserved for the single finalist
  under `config/strategies.yml → oos.pass_criteria`). `strategy/oos_ledger.json`
  remains `{"version":1,"consumptions":[]}`.
* **Harness:** `scripts/strategy_variants.py` (parallel sweep →
  `strategy/results/iterations_2026-11-04.csv`).
* **Run:** 2,160 cells, 12 workers, 0 error cells.
* **Signal sources:** all 15 use feature columns that no earlier strategy
  (S-01..S-57) traded as its primary signal. New families this batch:
  rate-of-change hysteresis (S-58), Stochastic K/D-turn and K-mid-turn
  (S-59, S-69), Aroon-Down collapse (S-60), momentum sign-turn (S-61),
  realized-volatility expansion + trend (S-62), Bollinger-upper / Donchian-upper
  breakout (S-63, S-64), lower-wick rejection (S-65), volume-confirmed band
  breakout (S-66), 1h-ADX + 1h-SuperTrend alignment (S-67), dual-SuperTrend
  alignment (S-68), 1h-low-vol coil + trend (S-70), Aroon + Stochastic
  confluence (S-71), and ROC + volume confluence (S-72).

## Results — ranked by mean edge vs buy-hold (2 bps, 3 instruments)

`edge = total_return − buyhold_return` (both in %), averaged over the 3
instruments for a variant across both windows. The decision-relevant figures
are the trade count (`trades_per_year`), whether any variant beat buy-hold on
**≥2 of 3 instruments on both windows** (the `oos.pass_criteria` bar), and the
trade-count ceiling (54/yr).

| # | Strategy | Rule (signal columns) | Best variant (mean edge) | Beat BH ≥2/3 (both windows) |
|---|----------|-----------------------|:---:|:---:|
| 1 | S-69 | `stoch_k_24` (Stochastic-K mid-turn) | `1h` **−48.7** | ✗ (0/3) |
| 2 | S-61 | `mom_24` (momentum sign-turn) | `1h` **−82.9** | ✗ (0/3) |
| 3 | S-58 | `roc_24` (rate-of-change) | `1h` **−87.4** | ✗ (0/3) |
| 4 | S-63 | `close`/`bb_upper_24` | `1h` **−126.1** | ✗ (0/3) |
| 5 | S-62 | `hv_24` (realized-vol + trend) | `1h` **−137.9** | ✗ (near-miss EUR `full` −1.5%, 1 trade) |
| 6 | S-68 | `st_dir_24_3`/`st_dir_120_2` | `1h_ema` **−192.0** | ✗ (0/3) |
| 7 | S-67 | `h1_adx_24`/`h1_st_dir_24_3` | `looser` **−226.1** | ✗ (best cell EUR `last_12m` −0.14%) |
| 8 | S-59 | `stoch_k_24`/`stoch_d_24` | `1h` **−235.7** | ✗ (0/3) |
| 9 | S-66 | `close`/`bb_upper_24`/`vol_rel_24` | `1h` **−239.9** | ✗ (0/3) |
| 10 | S-70 | `h1_atr_pct_24` (1h low-vol coil) | `base` **−247.0** | ✗ (0/3) |
| 11 | S-60 | `aroon_down_24` | `1h` **−252.3** | ✗ (0/3) |
| 12 | S-64 | `close`/`dc_upper_24`/`bb_mid_24` | `1h_ema_guard` **−253.9** | ✗ (0/3) |
| 13 | S-72 | `roc_24`/`vol_rel_24` | `1h` **−266.9** | ✗ (0/3) |
| 14 | S-71 | `aroon_down_24`/`stoch_k_24` | `1h` **−273.4** | ✗ (0/3) |
| 15 | S-65 | `bar_lower_wick_ratio` | `1h` **−305.8** | ✗ (0/3) |

## The finding: all 15 rejected, none clears the in-sample bar

Unlike the previous batch (which produced the S-55 `parked` finalist
candidate), **no strategy in S-58..S-72 clears the `oos.pass_criteria`
in-sample bar**. The strongest result is S-67 (`1h ADX + 1h SuperTrend
alignment`), whose single best cell is EUR_USD `last_12m` at **−0.14%** edge
(27 trades, 27 tpy) — i.e. the strategy *loses* to buy-hold by a rounding
error on one instrument in one window, and loses more clearly everywhere else.
No variant of any strategy beats buy-hold on ≥2 of 3 instruments in even a
single window, let alone both windows.

### The closest near-misses (all still losses)

| Strategy | Cell | Instrument | Window | Edge vs BH | Trades | Note |
|----------|------|-----------|--------|-----------:|-------:|------|
| S-67 | `entry_guard` | EUR_USD | last_12m | **−0.14%** | 27 | closest to zero; still a loss |
| S-62 | `wide_exit` | EUR_USD | full | −1.51% | 1 | 1 trade over full span; not a signal |
| S-69 | `1h` | XAU_USD | last_12m | −23.9% | ~130 | best window for the best strategy |

The pattern is unambiguous across the batch: at 2 bps, **every** strategy
variant on **every** instrument loses to buy-and-hold. There is no configuration
in this batch that even reaches break-even.

## Consistent pattern (reproduces batches 1–4)

1. **5m = cost × frequency** for the high-turnover variants: S-58/S-63/S-65
   base variants run 3,000–10,000+ trades/year and lose >370% — the recurring
   cost×frequency signature.
2. **`1h` / low-frequency iterations dominate** the best-variant ranking for
   11 of 15 strategies (all single-signal hysteresis rules) — the fifth
   consecutive batch with this outcome, confirming the 5m grid is systematically
   cost-dominated.
3. **Confluence / multi-indicator rules (S-66, S-67, S-71, S-72) do not
   compound.** They trade less (17–530 tpy) but lose more per trade than the
   single-signal rules, consistent with the batches-1–4 finding that stacking
   indicators on this data does not produce a cross-market edge.
4. **Two-scale `h1_*` rules (S-67, S-70) are low-frequency but still lose.**
   S-67 (1h ADX + 1h SuperTrend, ~17–53 tpy) is the closest to the S-55
   finalist profile in this batch — low-frequency, cross-window, near-neutral
   on EUR — but it does not beat buy-hold anywhere, so it is rejected rather
   than parked.

## Registry / trial-log action

All 15 are registered in `STRATEGY_REGISTRY.md` as **`rejected`**. All 15 are
rows 58–72 in `strategy/trial_log.md`; the Configuration tally is updated to
**72 strategies / 487 configurations / ≥8,766 cells**. No OOS consumption
occurred; `strategy/oos_ledger.json` remains
`{"version":1,"consumptions":[]}`. The S-55 `parked` finalist candidate from
the previous batch is the only strategy still awaiting the human-nominated
one-shot OOS gate.
