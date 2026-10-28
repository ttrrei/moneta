# SuperTrend-24 Direction Follower — Backtest Report

> **Purpose:** a second, structurally different reference strategy
> (trend-following, versus S-01's mean-reversion) to probe the rig further and
> exercise the shared core
> ([strategy_lib.py](../strategy_lib.py)) end-to-end. Deliberately *not* a
> claim of alpha.
> **Date:** 2026-10-28 · **Code:** [strategy/code/strategy_supertrend.py](../code/strategy_supertrend.py) ·
> **Library:** [strategy/strategy_supertrend_lib.py](../strategy_supertrend_lib.py) ·
> **Data:** `data/ohlcv_5m_features/ohlcv_5m_features.parquet` ·
> **Registry ID:** S-05 — see [STRATEGY_REGISTRY.md](../STRATEGY_REGISTRY.md)
>
> **OOS caveat:** all numbers are the **capped** in-sample window
> (`until: 2025-07-31`, the day before the OOS holdout
> `oos.holdout_start = 2025-08-01` in `config/strategies.yml`). The full matrix
> (all 18 cells, 0/2/5 bps × 3 instruments) is at
> [results/S05/matrix.md](../results/S05/matrix.md).

---

## 1. The strategy

| Item | Choice |
|---|---|
| Indicator | **SuperTrend 24 / 2.0×ATR** direction — pre-computed column `st_dir_24_2` in the feature table (defined once in [pipeline/indicators.py](../../pipeline/indicators.py), no duplicated indicator code) |
| Entry (long) | previous closed bar's `st_dir_24_2` is **up** (+1) → in at bar T+1 open |
| Exit (long) | previous closed bar's `st_dir_24_2` is **down** (−1) → out at bar T+1 open |
| Position | Long-only, one position at a time, 1 unit, fully closed at data end |
| Cost | **2 bps one-way** baseline; standard matrix is 0 / 2 / 5 bps |
| Causality | signal on closed bar T, fill at bar T+1 open — **no lookahead** |
| Data | 2020-01 → 2025-07-31 (capped in-sample), ~416k 5m bars per instrument |
| Timeframe | **5m** (the feature table is 5m-based; `st_dir_24_2` is a 24-bar indicator on 5m bars) |

Why this strategy: it is the simplest *trend follower* — the natural opposite
of S-01's mean-reversion — and it uses an indicator already present in the
feature table, so it reuses the shared [strategy_lib.py](../strategy_lib.py)
execution core (`simulate_trades` / `compute_metrics`) with zero new engine
code.

## 2. Results (full history, 2020-01 → 2025-07-31)

| Instrument | Cost (bps) | Strategy | Buy & hold | Trades | Max DD |
|---|---:|---:|---:|---:|---:|
| **EUR_USD** | 0 | −32.7% | +2.3% | 10,402 | 35.2% |
| **EUR_USD** | **2** | **−98.95%** | +2.3% | 10,402 | 99.0% |
| **EUR_USD** | 5 | −100.0% | +2.3% | 10,402 | 100.0% |
| **BTC_USD** | 0 | +59.2% | +1,538% | 9,713 | 60.5% |
| **BTC_USD** | **2** | **−96.7%** | +1,538% | 9,713 | 97.3% |
| **BTC_USD** | 5 | −100.0% | +1,538% | 9,713 | 100.0% |
| **XAU_USD** | 0 | −16.8% | +113% | 9,628 | 45.9% |
| **XAU_USD** | **2** | **−98.2%** | +113% | 9,628 | 98.3% |
| **XAU_USD** | 5 | −100.0% | +113% | 9,628 | 100.0% |

## 3. Verdict: **rejected — cost × frequency (structurally uneconomic)**

1. **~10,400 round-trip trades.** A 24-bar SuperTrend on 5m bars flips
   direction every ~24–50 bars — that is **10,402 trades** over the 5.6-year
   window. At 2 bps one-way (4 bps round-trip) the strategy pays
   ~**40% of equity in spread** before any edge. The average trade is
   ±0.004%, i.e. the edge per trade is orders of magnitude below the cost.
2. **Below buy-hold at every cost tier on every instrument.** Even at 0 bps
   (free execution, unrealistic), the strategy **edges no instrument above
   buy-hold** — BTC's +59% is far below buy-hold's +1,538%.
3. **The signal is too fast for a CFD spread.** This is the same structural
   cost problem as S-01 (777 trades) but **13× worse** on frequency.

## 4. How it differs from S-01 (and why both lose)

| | S-01 (RSI mean-rev) | S-05 (SuperTrend-24 follower) |
|---|---|---|
| Signal speed | 777 trades | **10,402 trades** |
| Logic | contrarian | trend |
| 0 bps best (BTC) | −9.7% | +59.2% |
| 2 bps (BTC) | −34.8% | −96.7% |
| Diagnosis | cost × frequency | **cost × frequency (worse)** |

Two different logic families, both structurally uneconomic on 5m bars with a
CFD spread. The common root is **signal frequency relative to cost**, not
signal quality — confirming the cost/frequency boundary the S-01 report
predicted.

## 5. What *would* make this worth another look

- **1h bars** (`ohlcv_1h_features` already exists): the same rule on 1h bars
  would trade ~1/12 as often (~900 trades), ~1/12 the cost. This is the single
  cheapest next test — but note the 1h feature table would need the same
  `st_dir` column computed (currently the 5m table has it).
- **Higher-timeframe indicator**: SuperTrend on 1h bars would need a new
  pre-computed column (`st_dir` on the 1h table) — a small, additive pipeline
  change, not engine work.
- **Long + short symmetric**: capture downtrend moves too.

## 6. How to reproduce

```bash
# From the repo root (Python 3.12, .venv):
.venv/bin/python strategy/code/strategy_supertrend.py --instrument EUR_USD
.venv/bin/python strategy/code/strategy_supertrend.py --instrument BTC_USD --cost-bps 0
.venv/bin/python strategy/run_matrix.py S05
```

---

### Caveats
- One instrument at a time; results are per-instrument.
- 2 bps one-way is an assumption (no slippage / partial fills / liquidity).
- Capped at the in-sample boundary; the OOS holdout may be run **once**
  (see `config/strategies.yml` `oos` block).
- This is a **reference backtest of a standard rule**, included to prove the
  shared core generalises and to set a cost/frequency baseline — not a trading
  recommendation.
