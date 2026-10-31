# 8-Iteration Improvement Sweep — S-88 .. S-102 (2026-11-06)

> Date provenance: `2026-11-06` is a historical batch identifier. Its CSV was
> recorded by `84547d8 2026-10-30T20:58:24+11:00`; the exact run time is unavailable. Full and
> last_12m overlap. Signal corrections and evidence limits are described in
> [the independent verification](../../docs/review_verification_20261031.md).

Fifteen more new strategies (S-88 .. S-102) were designed, unit-tested, and
then each was evaluated over **8 improvement iterations** on the shared
in-sample matrix. This is the seventh batch in the series; S-08 .. S-17 were
batch 1 ([strategy_sweep_2026-10-30.md](strategy_sweep_2026-10-30.md)),
S-18 .. S-27 batch 2 ([strategy_sweep_2026-11-01.md](strategy_sweep_2026-11-01.md)),
S-28 .. S-42 batch 3 ([strategy_sweep_2026-11-02.md](strategy_sweep_2026-11-02.md)),
S-43 .. S-57 batch 4 ([strategy_sweep_2026-11-03.md](strategy_sweep_2026-11-03.md)),
S-58 .. S-72 batch 5 ([strategy_sweep_2026-11-04.md](strategy_sweep_2026-11-04.md)),
and S-73 .. S-87 batch 6 ([strategy_sweep_2026-11-05.md](strategy_sweep_2026-11-05.md)).

* **Scope:** S-88 .. S-102 (15 strategies) × 8 variants × 3 instruments
  (EUR_USD, BTC_USD, XAU_USD) × 2 windows (`full`, `last_12m`) × 3 cost tiers
  (0/2/5 bps) = **2,160 cells**, all run through the shared engine
  (`strategy/engine.py`).
* **Data:** in-sample only — `until ≤ 2025-07-31`. **No OOS holdout was
  touched** (the holdout is a one-shot gate reserved for the single finalist
  under `config/strategies.yml → oos.pass_criteria`). `strategy/oos_ledger.json`
  remains `{"version":1,"consumptions":[]}`.
* **Harness:** `scripts/strategy_variants.py` (parallel sweep →
  `strategy/results/iterations_2026-11-06.csv`).
* **Run:** 2,160 cells, 12 workers, 0 error cells (the featurecols audit —
  the S-64 lesson — was applied up front before generation).
* **Signal sources:** all 15 use feature columns that no earlier strategy
  (S-01..S-87) traded as its primary signal. New families this batch:
  **fast (6/12-bar) oscillators** (`rsi_12` S-88, `aroon_up_12`/`aroon_down_12`
  spread S-89, `macd_hist_6_24` S-90, `stoch_d_12` S-91, `mfi_12` S-92,
  `willr_12` S-93, `er_12` S-94), **slow volatility regimes** (`hv_120` S-95,
  `bb_width_60` squeeze-release S-96), **multi-oscillator confluence**
  (S-97 triple: `rsi_12`+`stoch_k_12`+`mfi_12`; S-98 quad: `rsi_12`+`willr_12`+
  `stoch_d_12`+`mfi_12`), **fast-ROC + volume-ratio breakout**
  (`roc_6`+`vol_ratio_6_24` S-99), **fast MACD signal cross**
  (`macd_6_24`/`macd_signal_6_24` S-100), **slow-ROC-120 + EMA-120
  confluence** (`roc_120`+`ema_120` S-101), and **slow Donchian-position
  regime** (`dc_pos_12` S-102).

## Results — ranked by mean edge vs buy-hold (2 bps, 3 instruments)

`edge = total_return − buyhold_return` (both in %), averaged over the 3
instruments for a variant across both windows. The decision-relevant figures
are the trade count (`trades_per_year`), whether any variant beat buy-hold on
**≥2 of 3 instruments on both windows** (the `oos.pass_criteria` bar), and the
trade-count ceiling.

| # | Strategy | Rule (signal columns) | Best variant (mean edge) | Beat BH ≥2/3 (both windows) |
|---|----------|-----------------------|:---:|:---:|
| 1 | **S-96** | `bb_width_60` (squeeze release) | `combo` **+30.5** | ✗ (BTC-only: BTC `full` +342%; XAU `full` −129%, EUR `full` −4.8%; `1h` 3/3 wins are 1–25-trade artifacts) |
| 2 | **S-88** | `rsi_12` (fast RSI) | `1h` **+15.7** | ✗ (BTC-only: BTC `full` +256%; loses on EUR/XAU & BTC `last_12m`) |
| 3 | S-93 | `willr_12` (fast %R) | `1h` **−20.5** | ✗ (BTC-only: BTC `full` +88%; loses on EUR/XAU) |
| 4 | S-95 | `hv_120` (low-vol regime) | `looser` **−44.4** | ✗ (XAU-only: XAU `full` +34%/+23%; BTC `full` −1506% on same variant) |
| 5 | S-91 | `stoch_d_12` (fast stoch-D) | `1h` **−35.9** | ✗ (0/3) |
| 6 | S-92 | `mfi_12` (fast MFI) | `1h` **−169.1** | ✗ (0/3) |
| 7 | S-100 | `macd_6_24`/`macd_signal_6_24` | `1h` **−169.2** | ✗ (0/3) |
| 8 | S-102 | `dc_pos_12` (Donchian position) | `1h` **−129.3** | ✗ (0/3) |
| 9 | S-101 | `roc_120`+`ema_120` | `1h` **−138.1** | ✗ (0/3) |
| 10 | S-99 | `roc_6`+`vol_ratio_6_24` | `1h` **−248.1** | ✗ (0/3) |
| 11 | S-94 | `er_12` (efficiency ratio) | `1h` **−256.1** | ✗ (0/3) |
| 12 | S-89 | `aroon_up_12`−`aroon_down_12` | `1h` **−261.2** | ✗ (0/3) |
| 13 | S-97 | `rsi_12`+`stoch_k_12`+`mfi_12` | `1h` **−215.7** | ✗ (0/3) |
| 14 | S-98 | `rsi_12`+`willr_12`+`stoch_d_12`+`mfi_12` | `1h` **−204.9** | ✗ (0/3) |
| 15 | S-90 | `macd_hist_6_24` (fast MACD) | `1h_ema_guard` **−223.3** | ✗ (0/3) |

## The finding: all 15 rejected; S-96's apparent 3/3 win is a 1–25-trade artifact

**No strategy in S-88..S-102 clears the `oos.pass_criteria` in-sample bar.**
The closest is **S-96** (`bb_width_60` squeeze release), whose `1h` variant
appears to beat buy-hold on **all 3 instruments on the `full` window** — but
the edge is **0.2–3.9% with 1–25 trades** (BTC: 1 trade +3.7%; XAU: 1 trade
+0.2%; EUR: 25 trades +3.9%), and **on `last_12m` all three instruments are
flat or negative** (−0.1% to +0.1%). That is a 1-bar coincidence on BTC/XAU,
not an edge. S-96's `combo` variant looks larger (+30.5% mean edge) but only
because BTC `full` is +342% on 188 trades while XAU `full` is **−129%** on
304 trades — the other 5 instrument-window cells are all negative. Rejected,
not parked.

**S-88** (`rsi_12` fast RSI, `1h` +15.7% mean edge) shows the same single-
instrument signature: BTC `full` +256% on 567 trades, but EUR `full` −23.5%,
XAU `full` −50.8%, and **BTC `last_12m` −61.3%** — the `≥2 of 3 instruments
on both windows` bar exists precisely to exclude this. Same for S-93 (`1h`
−20.5%, BTC `full` +88% only) and S-95 (`looser` −44.4%, XAU `full` +34%
only, BTC `full` **−1506%** on the same variant).

### S-96 decomposition (the only apparent 3/3-win cell set)

| Instrument | Window | combo | 1h | looser |
|-----------|--------|-----:|-----:|-------:|
| BTC_USD | full | +341.7% (188 trades) | +3.7% (1 trade) | +34.4% (18 trades) |
| BTC_USD | last_12m | +17.6% (29 trades) | −0.1% (1 trade) | −4.0% (8 trades) |
| EUR_USD | full | −4.8% (64 trades) | +3.9% (25 trades) | −5.9% (85 trades) |
| EUR_USD | last_12m | −4.7% (12 trades) | +0.1% (5 trades) | −1.3% (8 trades) |
| XAU_USD | full | −129.3% (304 trades) | +0.2% (1 trade) | −25.5% (36 trades) |
| XAU_USD | last_12m | −37.5% (52 trades) | −0.1% (1 trade) | −19.1% (8 trades) |

Only **3 of 6** instrument-window cells are positive on `1h` (all ≤ +3.9%,
1–25 trades), and **2 of 6** on `combo` (BTC only, the other 4 all negative).
No variant wins on **≥2 of 3 instruments on both windows simultaneously** —
the S-81 (round 4) and S-45 (round 2) exclusion rule applies again. The other
13 strategies are uniformly worse (best mean edge ≤ −36%), reproducing the
cost×frequency and single-instrument signatures from batches 1–6.

## Consistent pattern (reproduces batches 1–6)

1. **`1h` / low-frequency iterations dominate** the best-variant ranking for
   11 of 15 strategies — the seventh consecutive batch with this outcome.
   (S-95 `looser` and S-96 `combo` are the two exceptions, both on the
   5m timeframe but both single-instrument artifacts.)
2. **Fast (6/12-bar) oscillators do not manufacture an edge** (S-88..S-94).
   Every one of the 7 fast-oscillator strategies loses ≥ −21% mean edge; the
   4 that show any single-instrument positivity (S-88/S-93) are BTC-`full`-
   only artifacts with `last_12m` losses.
3. **Multi-oscillator confluence does not compound** (S-97 triple, S-98 quad).
   Stacking 3 or 4 oscillator confirmations does not produce an edge — it
   simply narrows the trade set, and the resulting trades still lose to
   buy-and-hold at 2 bps.
4. **Slow volatility regimes (`hv_120`, `bb_width_60`) do not work** (S-95,
   S-96). S-96's apparent 3/3 win on `1h` is a 1–25-trade artifact; S-95's
   XAU-only +34% on `full` is matched by a BTC-only **−1506%** loss on the
   same variant.
5. **MACD-based rules (S-90 hist, S-100 cross) remain dominated** by
   buy-and-hold at every cost tier, consistent with S-11/S-45/S-53 from
   earlier batches.

## Registry / trial-log action

All 15 are registered in `STRATEGY_REGISTRY.md` as **`rejected`**. All 15 are
rows 88–102 in `strategy/trial_log.md`; the Configuration tally is updated to
**102 strategies / 727 configurations / ≥13,086 cells**. No OOS consumption
occurred; `strategy/oos_ledger.json` remains
`{"version":1,"consumptions":[]}`. The S-55 `parked` finalist candidate from
round 2 remains the only strategy still awaiting the human-nominated one-shot
OOS gate.
