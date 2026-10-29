# Efficiency-Ratio Regime Follower — Backtest Report (S-22)

> **Purpose:** a *regime* follower (the structural opposite of S-04's
> per-episode churn): stay long only while the market is *efficient* —
> directional displacement dominates total movement (`er_24`, Kaufman
> efficiency ratio over 24 bars, 0..1) **and** close is above `ema_24`.
> Deliberately *not* a claim of alpha.
> **Date:** 2026-11-01 · **Code:** [strategy/code/strategy_er.py](../code/strategy_er.py) ·
> **Library:** [strategy/strategy_er_lib.py](../strategy_er_lib.py) ·
> **Data:** `data/ohlcv_5m_features/ohlcv_5m_features.parquet` ·
> **Registry ID:** S-22 — see [STRATEGY_REGISTRY.md](../STRATEGY_REGISTRY.md)
>
> **OOS caveat:** all numbers are the **capped** in-sample window
> (`until: 2025-07-31`, the day before the OOS holdout
> `oos.holdout_start = 2025-08-01` in `config/strategies.yml`). The committed
> matrix (`last_12m`, 3 cost tiers) is at [results/S22/matrix.md](../results/S22/matrix.md).

---

## 1. The strategy

| Item | Choice |
|---|---|
| Indicators | **Kaufman efficiency ratio** — pre-computed `er_24` (0..1) and `ema_24` in the 5m feature table ([pipeline/indicators.py](../../pipeline/indicators.py)) |
| Direction | long only |
| Entry | previous closed bar with `er_24 > k` (reference `k = 0.30`) **and** `close > ema_24` → in at bar T+1 open |
| Exit | either condition fails on the previous closed bar → out at the next open |
| Position | Long only, one position at a time, 1 unit, fully closed at data end |
| Cost | **2 bps one-way** baseline; matrix is 0 / 2 / 5 bps |
| Causality | signal on closed bar T, fill at bar T+1 open — **no lookahead** |
| Data | `last_12m` 2024-08-01 → 2025-07-31 (capped in-sample), 74,295 bars |
| Timeframe | **5m** (the sweep also evaluated 1h variants — §4) |

Why this strategy: an efficiency ratio near 1 means the market moved almost
purely in one direction (a regime worth staying in); near 0 means chop
(noise the trend followers in S-05/S-13 get churned by). The premise:
holding a position only while the market is *efficient* is low-frequency
enough to survive costs.

## 2. Results (committed matrix, `last_12m`, EUR_USD)

| Instrument | Cost (bps) | Strategy | Buy & hold | Trades | Win % | Sharpe (wk) | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|
| EUR_USD | 0 | −4.22% | +5.62% | 1,945 | 34.9% | −1.72 | 5.7% |
| EUR_USD | **2** | **−56.01%** | +5.62% | 1,945 | 11.7% | −21.07 | 56.1% |
| EUR_USD | 5 | −86.30% | +5.62% | 1,945 | 4.7% | −28.87 | 86.3% |

Every cell is in [results/S22/summary.csv](../results/S22/summary.csv) /
[matrix.md](../results/S22/matrix.md). Exposure is 12.57% (the position is
mostly flat — the regime rarely holds at 5m), and even that small exposure
loses to a flat buy-hold at every cost tier.

## 3. Verdict: **rejected — cost × frequency again; the regime does not hold at 5m**

1. **1,945 trades in one year (~1,952/yr).** Despite the regime gate, the
   strategy re-enters constantly: at 5m the efficiency ratio oscillates
   around the threshold far faster than a tradable regime. This is the same
   failure mode as S-04/S-05 (cost × frequency), only the churn happens at
   the gate's edge instead of on every signal.
2. **Below buy-hold at every cost tier, including 0 bps** (−4.22% vs +5.62%):
   even with free execution there is no edge, so the mechanism — not just the
   costs — fails.
3. **Max drawdown 56.1% at 2 bps** on 12.57% exposure: when the strategy is
   in, it is in the wrong direction more often than not (win rate 11.7% at
   2 bps).

## 4. The 6-variant sweep (2026-11-01 batch)

S-22 was evaluated with 6 `k` variants (0.20–0.50) across 5m/1h in
[results/iterations_2026-11-01.csv](../results/iterations_2026-11-01.csv).
Best variant was `1h` (mean edge vs buy-hold at 2 bps ≈ −224 across the 3
instruments; e.g. full window EUR_USD −32.58% vs +3.07%); **no variant beat
buy-hold on ≥ 2 of 3 instruments on both windows**, so S-22 fails
`oos.pass_criteria` and was never promoted to `finalist`. See the sweep
report: [strategy_sweep_2026-11-01.md](strategy_sweep_2026-11-01.md).

## 5. How the candidates compare

S-22 is the most *selective* strategy of batch 2 (long only while the regime
holds) and still fails on frequency, which confirms the batch-2 conclusion:
at these bar cadences the binding constraint is cost × entry frequency, not
the rule. See the registry for the full S-18…S-27 outcome table.
