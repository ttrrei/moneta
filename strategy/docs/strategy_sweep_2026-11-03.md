# 8-Iteration Improvement Sweep — S-43 .. S-57 (2026-11-03)

Fifteen more new strategies (S-43 .. S-57) were designed, unit-tested, and
then each was evaluated over **8 improvement iterations** on the shared
in-sample matrix. This is the fourth batch in the series; S-08 .. S-17 were
batch 1 ([strategy_sweep_2026-10-30.md](strategy_sweep_2026-10-30.md)),
S-18 .. S-27 batch 2 ([strategy_sweep_2026-11-01.md](strategy_sweep_2026-11-01.md)),
and S-28 .. S-42 batch 3 ([strategy_sweep_2026-11-02.md](strategy_sweep_2026-11-02.md)).

* **Scope:** S-43 .. S-57 (15 strategies) × 8 variants × 3 instruments
  (EUR_USD, BTC_USD, XAU_USD) × 2 windows (`full`, `last_12m`) × 3 cost tiers
  (0/2/5 bps) = **2,160 cells**, all run through the shared engine
  (`strategy/engine.py`).
* **Data:** in-sample only — `until ≤ 2025-07-31`. **No OOS holdout was
  touched** (the holdout is a one-shot gate reserved for the single finalist
  under `config/strategies.yml → oos.pass_criteria`). `strategy/oos_ledger.json`
  remains `{"version":1,"consumptions":[]}`.
* **Harness:** `scripts/strategy_variants.py` (parallel sweep →
  `strategy/results/iterations_2026-11-03.csv`).
* **Run:** 2,160 cells, 12 workers, 0 error cells.
* **Signal sources:** all 15 use feature columns that no earlier strategy
  (S-01..S-42) traded as its primary signal. New families this batch:
  Directional-Index spread (S-43), dual-SMA (S-44), MACD signal-line (S-45),
  ATR-% regime (S-46), ATR-distance-to-prior-high (S-47), fast/slow ATR ratio
  (S-48), Keltner lower-band (S-49), Bollinger midline (S-50), candle
  upper-wick (S-51), close-location/CLV (S-52), fast ATR-normalised MACD
  histogram (S-53), and the **5m-only `h1_*` two-scale block** (S-54..S-57),
  which reads the prior 1h ADX / RSI / efficiency-ratio / EMA-distance.

## Results — ranked by mean edge vs buy-hold (2 bps, 3 instruments)

`edge = total_return − buyhold_return` (both in %), averaged over the 3
instruments for a variant. The decision-relevant figures are the trade count
(`trades_per_year`), whether any variant beat buy-hold on **≥2 of 3
instruments on both windows** (the `oos.pass_criteria` bar), and the
trade-count ceiling (54/yr).

| # | Strategy | Rule (signal columns) | Best variant (mean edge) | Best-variant trades/yr | Beat BH ≥2/3 (both windows) |
|---|----------|-----------------------|:---:|---:|:---:|
| 1 | **S-55** | `h1_rsi_24` (1h RSI momentum) | `looser` **+43.4** | ~10 | **✓ `looser`: BTC & XAU, `full` + `last_12m`** |
| 2 | **S-45** | `macd_12_60`/`macd_signal_12_60` | `1h_guard` **+147.5** | ~182 | ✗ (BTC-only; XAU −71.5) |
| 3 | S-46 | `atr_pct_24` (ATR-% low-vol) | `looser` −26.9 | ~5 | ✗ |
| 4 | S-57 | `h1_ema_dist_24` (1h EMA-distance) | `entry_guard` −31.3 | ~141 | ✗ (1/3 full) |
| 5 | S-48 | `vol_ratio_12_60` | `wide_exit` −68.8 | ~89 | ✗ |
| 6 | S-54 | `h1_adx_24` (1h ADX regime) | `entry_ema` −112.6 | ~20 | ✗ |
| 7 | S-44 | `close`/`sma_24`/`sma_60` | `1h_ema` −157.4 | ~90 | ✗ |
| 8 | S-50 | `close`/`bb_mid_24`/`bb_lower_24` | `1h_ema_guard` −163.9 | ~63 | ✗ |
| 9 | S-43 | `plus_di_24`−`minus_di_24` | `1h` −175.2 | ~97 | ✗ |
| 10 | S-53 | `macd_hist_atr_6_24` | `1h` −177.6 | ~313 | ✗ |
| 11 | S-56 | `h1_er_24` (1h ER regime) | `looser` −178.1 | ~247 | ✗ |
| 12 | S-47 | `dist_high_24` | `1h` −246.7 | ~163 | ✗ |
| 13 | S-49 | `close`/`kc_lower_24`/`kc_mid_24` | `1h_ema` −255.3 | ~2 | ✗ |
| 14 | S-51 | `bar_upper_wick_ratio` | `1h` −290.8 | ~784 | ✗ |
| 15 | S-52 | `bar_clv` | `1h` −322.8 | ~1,294 | ✗ |

## The finding: S-55 `looser` clears the in-sample promotion bar

This is the first configuration across **all four batches (S-01 … S-57)** to
satisfy the `oos.pass_criteria` cross-market bar in-sample. `S-55` (1h RSI
momentum, `h1_rsi_24`) with the `looser` iteration (k_in=33, k_exit=27) at
2 bps:

| Instrument | Window | Strategy | Buy-hold | Edge | Trades | tpy |
|-----------|--------|---------:|---------:|-----:|-------:|----:|
| BTC_USD | full | +1,536.2% | +1,289.5% | **+246.7%** | 64 | 11.6 |
| BTC_USD | last_12m | +94.9% | +82.4% | **+12.6%** | 11 | 11.0 |
| EUR_USD | full | −1.4% | +3.1% | −4.5% | 60 | 10.9 |
| EUR_USD | last_12m | +4.2% | +5.6% | −1.4% | 12 | 12.0 |
| XAU_USD | full | +116.9% | +110.6% | **+6.3%** | 50 | 9.1 |
| XAU_USD | last_12m | +35.0% | +34.4% | **+0.6%** | 4 | 4.0 |

* **Cross-market:** beats buy-hold on **BTC and XAU — 2 of 3 instruments**
  (the `min_instruments_beating_bh_at_2bps: 2` bar), on **both** the `full`
  and `last_12m` windows. EUR is the one loss (−4.5% / −1.4% edge).
* **Frequency guard:** 4–12 trades over each window, ~9–12 trades/year — far
  below the 54/yr ceiling. Not a cost×frequency artifact.
* **Exposure:** ~98% net long, just below buy-hold's 100% (the
  same-exposure sanity check passes).
* **Mean edge is modest** (+0.6% to +246.7%) and EUR is negative — the win is
  carried by BTC (full-sample +246.7%) and a small XAU edge. This is a
  *lower-confidence, cross-market* pass, not a large-margin one; the honest
  caveat is that two of the six wins are small (XAU +0.6% last-12m, +6.3%
  full).

### Why S-55 is `parked`, not promoted

Two things keep it from an automatic promotion:

1. **The machine-enforced S1 gate.** The batch's *baseline* `base` variant
   (k_in=55, k_exit=45) runs 360 trades over the `full` window (EUR_USD),
   which exceeds the 300-trade budget. `check_results.py` therefore requires a **terminal**
   status (`rejected` or `parked`) for the strategy row — it cannot be
   promoted while a same-strategy baseline violates the ceiling.
2. **The bar is an in-sample bar.** `oos.pass_criteria` is applied to the
   single, unadjusted OOS holdout, run **once** for a human-nominated
   finalist (`oos.usage = finalist_only_once`). S-55 has only cleared the
   in-sample proxy; it has not (and must not, yet) been evaluated on the
   holdout.

The correct action per `WORKFLOW.md` is therefore to hold S-55 as **`parked`**
— the top in-sample candidate — and present it to a human for the one-shot
OOS nomination. **The OOS holdout was NOT consumed** in this batch; the ledger
stays empty.

## Why S-45 does not pass (decomposition)

`S-45` `1h_guard` (MACD signal-line cross) has the best mean edge (+147.5%)
but it is the familiar **BTC-only** signature: it beat buy-hold on BTC
(`full` +1,068% on 182 tpy) but *lost* on XAU (−71.5%) and EUR. That is the
exact single-instrument artifact the `≥2 of 3` bar exists to exclude (see the
S-06 note in the config). Rejected.

## Consistent pattern (reproduces batches 1–3)

1. **5m = cost × frequency** for the high-turnover variants (S-51/S-52 at
   7,837 / 12,944 tpy lost >290%).
2. **`1h` / low-frequency iterations dominate** the best-variant ranking for
   most strategies — the fourth consecutive batch with this outcome.
3. **Cross-market, low-frequency long-only edges are rare.** The `h1_*`
   two-scale family produced the only genuine in-sample pass (S-55) and the
   near-miss (S-57, 1/3 full). The candle-structure and oscillator families
   (S-43, S-51, S-52, S-53) all lost to cost × frequency.

## Registry / trial-log action

All 15 are registered in `STRATEGY_REGISTRY.md`. **S-55 is `parked`** (in-sample
finalist candidate, awaiting the one-shot OOS nomination); the other 14 are
`rejected`. All 15 are rows 43–57 in `strategy/trial_log.md`; the
Configuration tally is updated to **367 configurations / ≥6,606 cells**. No
OOS consumption occurred; `strategy/oos_ledger.json` remains
`{"version":1,"consumptions":[]}`.
