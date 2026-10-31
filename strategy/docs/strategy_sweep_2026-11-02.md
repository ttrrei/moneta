# 8-Iteration Improvement Sweep — S-28 .. S-42 (2026-11-02)

> Date provenance: `2026-11-02` is a historical batch identifier. Its CSV was
> recorded by `804964d 2026-10-30T16:31:36+11:00`; the exact run time is unavailable. Full and
> last_12m overlap. Signal corrections and evidence limits are described in
> [the independent verification](../../docs/review_verification_20261031.md).

Fifteen more new strategies (S-28 .. S-42) were designed, unit-tested, and
then each was evaluated over **8 improvement iterations** on the shared
in-sample matrix. This is the third batch in the series; S-08 .. S-17 were
batch 1 ([strategy_sweep_2026-10-30.md](strategy_sweep_2026-10-30.md)) and
S-18 .. S-27 were batch 2 ([strategy_sweep_2026-11-01.md](strategy_sweep_2026-11-01.md)).

* **Scope:** S-28 .. S-42 (15 strategies) × 8 variants × 3 instruments
  (EUR_USD, BTC_USD, XAU_USD) × 2 windows (`full`, `last_12m`) × 3 cost tiers
  (0/2/5 bps) = **2,160 cells**, all run through the shared engine
  (`strategy/engine.py`).
* **Data:** in-sample only — `until ≤ 2025-07-31`. **No OOS holdout was
  touched** (the holdout is a one-shot gate reserved for the single finalist
  under `config/strategies.yml → oos.pass_criteria`).
* **Harness:** `scripts/strategy_variants.py` (parallel sweep →
  `strategy/results/iterations_2026-11-02.csv`).
* **Run:** 2,160 cells, 12 workers, ~1,232 s wall, 0 error cells.
* **Signal sources:** all 15 reuse whitelisted feature columns from
  `config/indicators.yml` — none introduces a new indicator. The 8
  improvement iterations per strategy are: base, tighter/stricter,
  looser/lower, `ema_gate`, `wide_exit`, `1h` (timeframe), `entry_guard`
  (5m), and a `combo` (or `1h_guard` for the parameterless Keltner /
  Donchian-mid rules).

## Results — ranked by mean edge vs buy-hold (2 bps, 3 instruments)

`edge = total_return − buyhold_return` (both in %), averaged over the 3
instruments for a variant. A negative edge is expected to be large on the
`full` window because BTC_USD buy-hold is +1,288 % over the full sample, so
the comparison is dominated by how much of that one-sided upside the long-only
rule missed. The decision-relevant figures are the **trade count**
(`trades_per_year`), the **BTC full-sample win** (the only place a long-only
rule can plausibly beat buy-hold), and whether any variant beat buy-hold on
**≥2 of 3 instruments on both windows** (the `oos.pass_criteria` bar).

| # | Strategy | Rule (signal columns) | Best variant (mean edge) | 5m trades/yr | BTC full win | Beat BH ≥2/3 (both windows) |
|---|----------|-----------------------|:---:|---:|:---:|:---:|
| 1 | **S-36** | `dc_position` vs prior-13 (Donchian position) | `1h` **+48.3** | 1,128 | +415.8 (630 tr) | ✗ (1/3 full, 0/3 last-12m) |
| 2 | **S-35** | `bb_width` vs prior-13 (Bollinger width) | `1h` **+33.5** | 13.9 | +189.6 (18 tr) | ✗ (2/3 full, 1/3 last-12m) |
| 3 | S-29 | `ema_std_ratio_20`/`close`/`ema` (vol-convergence) | `1h` −19.0 | 2,622 | +115.7 (29 tr) | ✗ (1/3 full, 0/3 last-12m) |
| 4 | S-37 | `donchian_mid_cross` (flag) | `1h_guard` −78.1 | 2,921 | −74.7 (63 tr) | ✗ |
| 5 | S-42 | `bar_body_ratio` vs prior-13 (bar-body momentum) | `1h` −220.7 | 9,875 | +146.5 (68 tr) | ✗ |
| 6 | S-28 | `close` vs `ema`, `hlc3` (candle-close momentum) | `1h` −323.4 | 12,899 | +38.0 (44 tr) | ✗ |
| 7 | S-33 | `keltner_close_breakout` (flag) | `1h` −210.5 | 728 | +107.6 (166 tr) | ✗ |
| 8 | S-38 | `dist_low_20` vs prior-13 | `1h` −157.9 | 1,556 | +130.3 (136 tr) | ✗ |
| 9 | S-40 | `ema_std_ratio_20` hysteresis band | `1h` −85.5 | 1,518 | +24.1 (118 tr) | ✗ |
| 10 | S-34 | `bb_pctb` vs prior-13 (Bollinger %B) | `1h` −275.7 | 1,777 | +53.1 (487 tr) | ✗ |
| 11 | S-32 | `parabolic_sar_distance` vs prior-13 | `1h` −144.9 | 1,574 | +35.0 (100 tr) | ✗ |
| 12 | S-31 | `ema_std_ratio_20` vs prior-13 | `1h` −95.0 | 1,361 | +59.3 (248 tr) | ✗ |
| 13 | S-30 | `atr_range_position_pct` vs prior-13 | `1h` −127.3 | 1,390 | +42.8 (203 tr) | ✗ |
| 14 | S-41 | `hv_24` vs prior-13 (realized-vol contraction) | `1h` −247.7 | 5.6 | — | ✗ |
| 15 | S-39 | `dc_width` vs prior-13 (Donchian width) | `1h` −247.7 | 0.9 | — | ✗ |

**Verdict: no strategy met the in-sample promotion bar.** The single
pass-criterion (`oos.pass_criteria`) requires a configuration to beat
buy-and-hold on **≥2 of 3 instruments** on **both** the `full` and
`last_12m` windows at 2 bps. No variant of S-28 .. S-42 satisfies that.

## Why the two "winners" do not pass (decomposition)

* **S-35 `1h` (Bollinger width, mean edge +33.5):** the best variant on a
  *3-instrument* mean, and it beat buy-hold on **2 of 3** instruments on the
  `full` window (BTC +189.6 on 18 trades; XAU +0.16 on 1 trade) — but it
  **failed the `last_12m` window on 2 of 3** (only EUR +0.2 on 1 trade). It
  is also near-flat: 1.4 trades/yr on the 5m base, 18 trades over the whole
  BTC full sample. This is the same single-instrument, low-frequency
  signature as the prior S-06/S-18 rejects, not a cross-market edge.
* **S-36 `1h` (Donchian position, mean edge +48.3):** the best single cell
  in the batch (BTC full +415.8 on 630 trades) but it beat buy-hold on **only
  1 of 3** instruments (`full`) and **0 of 3** (`last_12m`). A BTC-only
  result is exactly what the 3-instrument bar is designed to exclude — a
  long-only rule riding the +1,288 % BTC trend, not a robust signal.

Both are therefore **rejected**, not promoted to finalist. The rest of the
batch lost to cost × frequency (5m variants 73–12,899 trades/yr) or were
near-flat (S-39, S-41 with <6 trades/yr).

## Consistent pattern across the batch (reproduces batch 1 and 2)

1. **5m = cost × frequency.** Every 5m variant with >100 trades/yr lost
   large, dominated by the 2–5 bps round-trip cost.
2. **1h is the best iteration for 13 of 15** (all but S-39/S-41, which were
   too sparse even on 1h) — the same finding as both prior batches.
3. **No cross-market, low-frequency long-only edge on ≥2/3 instruments.**
   The only positive cells are BTC-only, matching the historical S-06/S-18
   signature. This is now the third consecutive batch with this outcome.

## Registry / trial-log action

All 15 are registered in `STRATEGY_REGISTRY.md` (status `rejected`) and in
`strategy/trial_log.md` (rows 28–42). The trial-log Configuration tally is
updated to **247 configurations / ≥4,446 cells**. No OOS consumption
occurred; `strategy/oos_ledger.json` remains `{"version":1,"consumptions":[]}`.
