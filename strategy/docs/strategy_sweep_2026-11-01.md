# 6-Iteration Improvement Sweep — S-18 .. S-27 (2026-11-01)

> Date provenance: `2026-11-01` is a historical batch identifier. Its CSV was
> recorded by `e6350d5 2026-10-30T07:44:56+11:00`; the exact run time is unavailable. Full and
> last_12m overlap. Signal corrections and evidence limits are described in
> [the independent verification](../../docs/review_verification_20261031.md).

Ten more new strategies (S-18 .. S-27) were designed, unit-tested, and then each
was evaluated over **6 improvement iterations** on the shared in-sample matrix.
This is the second batch in the same session; S-08 .. S-17 were the first
(see [strategy_sweep_2026-10-30.md](strategy_sweep_2026-10-30.md)).

* **Scope:** the full registry (20 strategies) × 6 variants × 3 instruments
  (EUR_USD, BTC_USD, XAU_USD) × 2 windows (`full`, `last_12m`) × 3 cost tiers
  (0/2/5 bps) = **2,160 cells**, all run through the shared engine
  (`strategy/engine.py`). S-18 .. S-27 contribute the last 1,080.
* **Data:** in-sample only — `until ≤ 2025-07-31`. **No OOS holdout was
  touched** (the holdout is a one-shot gate reserved for the single finalist
  under `config/strategies.yml → oos.pass_criteria`).
* **Harness:** `scripts/strategy_variants.py` (parallel sweep →
  `strategy/results/iterations_2026-11-01.csv`).
* **Run:** 2,160 cells, 8 workers, ~1,854 s wall.

## What changed versus batch 1

The batch-1 conclusion was unambiguous: on 5m data every candidate lost to
cost × frequency, and the 1h bar was the single best iteration for 9 of 10
strategies. Batch 2 was deliberately designed to *escape* that trap by
targeting **lower-frequency, regime-conditioned** rules:

* **Regime followers** (long only while a slow regime holds, not on every
  cross): S-22 efficiency-ratio, S-23 slow ATR-normalised MACD, S-21 slow
  60-bar squeeze, S-25 chop-regime reversion, S-26 EMA-spread follower.
* **Multi-scale / HTF alignment:** S-20 gates a short-timeframe SuperTrend flip
  on a longer SuperTrend (and, in one variant, on the 1h-native direction
  `h1_st_dir_120_3`), the "two scales of the same family" idea.
* **Volume-confirmed momentum:** S-27 (momentum × relative volume), S-19
  (CMF-24 accumulation), S-18 (VWAP-stretch reversion).
* **Breakout with hysteresis:** S-24 ATR-band.

## Results — ranked by mean edge vs buy-hold (2 bps, 3 instruments)

`edge = total_return − buyhold_return` (both in %). All cells in-sample. A
negative edge is expected to be *large* on the `full` window because BTC_USD
buy-hold is +1,288 % over the full sample, so the comparison is dominated by
that beta; the `last_12m` window is the more balanced read.

| Strategy | Best variant (2 bps) | mean edge vs BH | mean tpy | beats BH (full / last12m) |
|---|---|---|---|---|
| S-18 VWAP-stretch reversion | `1h` | **+23.73** | 441.3 | 1 / 3 · 0 / 3 |
| S-19 CMF-24 accumulation | `1h` | −120.63 | 139.9 | 0 / 3 · 0 / 3 |
| S-23 Slow ATR-normalised MACD | `1h` | −129.82 | 88.0 | 0 / 3 · 0 / 3 |
| S-24 ATR-band breakout | `1h` | −138.44 | 183.0 | 0 / 3 · 0 / 3 |
| S-20 Multi-scale SuperTrend | `1h` | −162.36 | 126.7 | 0 / 3 · 0 / 3 |
| S-26 EMA-12/60-spread | `1h` | −169.72 | 48.5 | 0 / 3 · 0 / 3 |
| S-22 Efficiency-ratio regime | `1h` | −223.92 | 172.8 | 0 / 3 · 0 / 3 |
| S-27 Volume-confirmed momentum | `1h` | −230.24 | 195.1 | 0 / 3 · 0 / 3 |
| S-21 Slow squeeze (60-bar) | `1h` | −252.68 | 15.5 | 0 / 3 · 0 / 3 |
| S-25 Chop-regime reversion | `1h` | −253.65 | 19.5 | 0 / 3 · 0 / 3 |

### S-18 `1h` — the only positive mean edge, and why it does **not** pass

S-18's 1h VWAP-stretch variant is the single best cell in the entire
2,160-cell sweep (+23.73 mean edge at 2 bps). The decomposition is
unambiguous, though:

| Instrument | full | last_12m |
|---|---|---|
| BTC_USD | **edge +458.98** (1,747 % vs BH 1,288 %) | edge −52.44 |
| EUR_USD | edge −70.38 | edge −20.58 |
| XAU_USD | edge −146.13 | edge −27.09 |

It is **above buy-hold on exactly 1 of 3 instruments in `full`** (BTC only)
and **0 of 3 in `last_12m`** — a single-instrument, long-only beta exposure on
a bullish BTC sample. This is the exact S-06 signature (BTC-only, 0 bps) and
**fails** `oos.pass_criteria` (beat buy-hold on ≥ 2 of 3 instruments on both
`full` and `last_12m`). It is therefore logged as rejected, not promoted to
`finalist`.

### Consistent pattern (batch 2)

1. **The 1h variant is again the best iteration for all 10 strategies** — the
   cost × frequency mechanism that killed batch 1's 5m variants is the binding
   constraint; halving bar cadence is the only knob that moves the needle.
2. **The regime / multi-scale / chop conditioning was designed to be selective
   but was not selective enough to be profitable:** the fewest-trade
   variants (S-21 1h ≈ 15/yr, S-25 1h ≈ 19/yr) are also the most negative,
   because a low-frequency long-only rule in a market that trends *down* on
   EUR/XAU simply sits in the drawdown.
3. **No variant beat buy-hold on ≥ 2 of 3 instruments at 2 bps**, so none
   advances to `finalist`.

### Registry / trial-log action

All ten remain `candidate` in [STRATEGY_REGISTRY.md](../STRATEGY_REGISTRY.md)
and are recorded as **rejected** in [trial_log.md](../trial_log.md) rows
18–27. No strategy consumes the OOS holdout.
