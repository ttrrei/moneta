# RSI-24 Mean-Reversion on 1h Bars — Backtest Report (S-02)

> **Purpose:** the deliberately *slower* variant of S-01 — the same RSI-24
> mean-reversion rule run on **1-hour** bars instead of 5m, to test whether a
> lower trade rate survives the cost model. Deliberately *not* a claim of alpha.
> **Date:** 2026-10-28 · **Code:** [strategy/code/strategy_rsi_1h.py](../code/strategy_rsi_1h.py) ·
> **Library:** [strategy/strategy_rsi_1h_lib.py](../strategy_rsi_1h_lib.py) ·
> **Data:** `data/ohlcv_1h_features/ohlcv_1h_features.parquet` ·
> **Registry ID:** S-02 — see [STRATEGY_REGISTRY.md](../STRATEGY_REGISTRY.md)
>
> **OOS caveat:** all numbers are the **capped** in-sample window
> (`until: 2025-07-31`, the day before the OOS holdout
> `oos.holdout_start = 2025-08-01` in `config/strategies.yml`). The full matrix
> (all 18 cells, 0/2/5 bps × 3 instruments × 2 windows) is at
> [results/S02/matrix.md](../results/S02/matrix.md).

---

## 1. The strategy

| Item | Choice |
|---|---|
| Indicator | **RSI-24** — pre-computed `rsi_24` in the 1h feature table (defined once in [pipeline/indicators.py](../../pipeline/indicators.py), no duplicated indicator code) |
| Entry (long) | previous closed bar's `rsi_24 < 30` → in at bar T+1 open |
| Exit (long) | previous closed bar's `rsi_24 > 55` → out at bar T+1 open |
| Position | Long-only, one position at a time, 1 unit, fully closed at data end |
| Cost | **2 bps one-way** baseline; standard matrix is 0 / 2 / 5 bps |
| Causality | signal on closed bar T, fill at bar T+1 open — **no lookahead** |
| Data | 2020-01 → 2025-07-31 (capped in-sample), ~5.5 years |
| Timeframe | **1h** (the distinguishing choice vs S-01, which is 5m) |

Why this strategy: S-01's honest diagnosis was *cost × frequency* — the rule
churns ~270 round-trips and the spread eats it. The cheapest way to test the
hypothesis "is it the frequency or the signal?" is to slow the signal down. A
1h bar is ~12× coarser than a 5m bar, so the same rule should trade ~12× less
often and pay ~12× less cost. If the edge were real it should survive; if it
wasn't, slowing it down will still not beat buy-hold.

## 2. Results (full window, 2020-01 → 2025-07-31)

| Instrument | Cost (bps) | Strategy | Buy & hold | Trades | Trades/yr | Sharpe (wk) | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|
| **EUR_USD** | 0 | −5.16% | +3.1% | 74 | 13.4 | −0.32 | 12.8% |
| **EUR_USD** | **2** | **−7.93%** | +3.1% | 74 | 13.4 | −0.51 | 13.6% |
| **EUR_USD** | 5 | −11.93% | +3.1% | 74 | 13.4 | −0.78 | 15.1% |
| **BTC_USD** | 0 | +20.9% | +1,288% | 79 | 14.3 | 0.26 | 54.8% |
| **BTC_USD** | **2** | **+17.1%** | +1,288% | 79 | 14.3 | 0.25 | 55.4% |
| **BTC_USD** | 5 | +11.7% | +1,288% | 79 | 14.3 | 0.22 | 56.3% |
| **XAU_USD** | 0 | +6.7% | +110% | 65 | 11.8 | 0.24 | 14.5% |
| **XAU_USD** | **2** | **+3.9%** | +110% | 65 | 11.8 | 0.15 | 15.1% |
| **XAU_USD** | 5 | −0.04% | +110% | 65 | 11.8 | 0.03 | 16.0% |

New metrics: **Sharpe (weekly)** resamples the per-bar equity to weekly closes
and annualises over 52 weeks — a coarser, less fragile Sharpe for a trade-based
strategy (see `strategy/metrics.py`). **Trades/yr** makes the opportunity
frequency explicit next to total return (the "am I trading too little?" check).

## 3. Verdict: **rejected — better than S-01, still structurally below buy-hold**

1. **The slowdown worked as intended and confirms the diagnosis.** 74–79
   trades / 5.5 years (≈13–14 trades/yr) vs S-01's ~270. Cost drag dropped
   accordingly — S-02 is *less negative* than S-01 on every instrument at
   every cost tier. This is exactly the cost/frequency relationship the S-01
   report predicted.
2. **But the edge itself was never there.** Even at 0 bps (free execution),
   the strategy **beats no instrument's buy-hold**: EUR −5.2% vs +3.1%,
   BTC +20.9% vs +1,288%, XAU +6.7% vs +110%. The 1h timeframe removed the
   *cost* objection but not the *signal* objection. A mean-reversion trigger
   of "RSI-24 < 30" on a 1h bar simply does not produce an edge that beats
   holding the asset.
3. **Opportunity frequency is healthy** (13–14 trades/yr, distributed across
   the window — not a single lucky trade). The rejection is on **quality**,
   not on "too few trades."

## 4. How it differs from S-01 (and why both lose)

| | S-01 (5m) | S-02 (1h) |
|---|---|---|
| Signal | RSI-24 < 30 | RSI-24 < 30 (same) |
| Timeframe | 5m | **1h** |
| Trades / 5.5y | ~270 | **74–79** |
| 0 bps (EUR) | negative | **−5.2%** |
| Diagnosis | cost × frequency | **signal quality (edge not present)** |

Same rule, one coarser clock: S-02 isolates the cost effect and shows that once
cost is removed, the rule still does not beat buy-hold. The binding
constraint was never the frequency alone.

## 5. What *would* make this worth another look

- **Short side**: S-02 is long-only; a symmetric long/short version would
  capture the downtrend legs it currently ignores (see S-04's attempt).
- **Higher timeframes**: if any edge exists, it is likely on a clock
  (days/weeks) far coarser than 1h — a different instrument class or
  a trend regime, not a slower version of the same trigger.

## 6. How to reproduce

```bash
# From the repo root (Python 3.12, .venv):
.venv/bin/python strategy/code/strategy_rsi_1h.py --instrument EUR_USD
.venv/bin/python strategy/code/strategy_rsi_1h.py --instrument BTC_USD --cost-bps 0
.venv/bin/python strategy/run_matrix.py s02
```

---

### Caveats
- One instrument at a time; results are per-instrument.
- 2 bps one-way is an assumption (no slippage / partial fills / liquidity).
- Capped at the in-sample boundary; the OOS holdout may be run **once**
  (see `config/strategies.yml` `oos` block).
- This is a **reference backtest of a standard rule**, included to isolate the
  cost/frequency vs signal-quality question — not a trading recommendation.
