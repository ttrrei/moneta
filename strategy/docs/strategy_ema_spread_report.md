# EMA-Spread 24/120 Trend Follower — Backtest Report

> **Purpose:** a third reference strategy on the shared core
> ([strategy_lib.py](../strategy_lib.py)) to probe a second trend-following
> family (fast/slow EMA relationship, versus S-05's SuperTrend) and to stress
> the cross-market and cost-sensitivity gates. Deliberately *not* a claim of
> alpha.
> **Date:** 2026-10-28 · **Code:** [strategy/code/strategy_ema_spread.py](../code/strategy_ema_spread.py) ·
> **Library:** [strategy/strategy_ema_spread_lib.py](../strategy_ema_spread_lib.py) ·
> **Data:** `data/ohlcv_5m_features/ohlcv_5m_features.parquet` ·
> **Registry ID:** S-06 — see [STRATEGY_REGISTRY.md](../STRATEGY_REGISTRY.md)
>
> **OOS caveat:** all numbers are the **capped** in-sample window
> (`until: 2025-07-31`, the day before the OOS holdout
> `oos.holdout_start = 2025-08-01` in `config/strategies.yml`). The full matrix
> (all 18 cells, 0/2/5 bps × 3 instruments) is at
> [results/S06/matrix.md](../results/S06/matrix.md).

---

## 1. The strategy

| Item | Choice |
|---|---|
| Indicator | **EMA 24 vs EMA 120 spread** — `ema_24 − ema_120` (pre-computed `ema_spread_24_120` in the feature table) |
| Entry (long) | previous closed bar's spread is **positive** (EMA24 above EMA120) → in at bar T+1 open |
| Exit (long) | previous closed bar's spread is **≤ 0** → out at bar T+1 open |
| Position | Long-only, one position at a time, 1 unit, fully closed at data end |
| Cost | **2 bps one-way** baseline; standard matrix is 0 / 2 / 5 bps |
| Causality | signal on closed bar T, fill at bar T+1 open — **no lookahead** |
| Data | 2020-01 → 2025-07-31 (capped in-sample), ~416k 5m bars per instrument |
| Timeframe | **5m** (`ema_spread_24_120` is computed on 5m bars) |

Why this strategy: the fast/slow EMA relationship is the most common
momentum/trend filter; it exercises the same shared
[strategy_lib.py](../strategy_lib.py) execution core (`simulate_trades` /
`compute_metrics`) with a different signal source, so we learn whether the
S-05 result is a property of *trend followers in general* or of SuperTrend
specifically.

## 2. Results (full history, 2020-01 → 2025-07-31)

| Instrument | Cost (bps) | Strategy | Buy & hold | Trades | Max DD |
|---|---:|---:|---:|---:|---:|
| **EUR_USD** | 0 | −11.0% | +2.3% | 2,405 | 20.7% |
| **EUR_USD** | **2** | **−66.0%** | +2.3% | 2,405 | 66.2% |
| **EUR_USD** | 5 | −92.0% | +2.3% | 2,405 | 92.0% |
| **BTC_USD** | 0 | **+2,402%** | +1,538% | 2,286 | 45.7% |
| **BTC_USD** | **2** | **+903%** | +1,538% | 2,286 | 55.2% |
| **BTC_USD** | 5 | +154% | +1,538% | 2,286 | 68.5% |
| **XAU_USD** | 0 | +65.1% | +113% | 2,269 | 18.3% |
| **XAU_USD** | **2** | **−33.4%** | +113% | 2,269 | 51.9% |
| **XAU_USD** | 5 | −82.9% | +113% | 2,269 | 85.1% |

## 3. Verdict: **rejected — not a cross-market edge (single-instrument beta)**

This strategy **looks** like a winner on BTC — but the evidence does not
survive the standard gate of "above buy-hold at every cost tier on every
instrument":

1. **BTC is the only instrument where it ever edges buy-hold, and only at
   0 bps.** At the realistic 2 bps the BTC return (+903%) is **below**
   buy-hold (+1,538%); at 5 bps (+154%) it is far below. Edging buy-hold only
   when you assume *zero* transaction cost is not an edge — it is long-only
   beta on a strongly bullish BTC sample period.
2. **EUR_USD is below buy-hold at every cost tier** (−11% / −66% / −92% vs
   +2.3% buy-hold) — no edge in a non-trending instrument.
3. **XAU_USD is below buy-hold at every cost tier** (+65% / −33% / −83% vs
   +113% buy-hold).
4. **Cross-market gate fails.** The S-01/S-05 rejections were cost ×
   frequency; S-06 is different in kind — **its one bright spot (BTC, 0 bps
   only) does not generalise across instruments**, so it fails the cross-market
   requirement that a usable signal must be robust, not a sample artifact.

## 4. Why it matters (honest read)

- The 0 bps row is **not** a realistic execution assumption; it is a
  diagnostic to see the *raw* signal strength. Even at 0 bps, BTC's
  +2,402% is only *1.56×* buy-hold's +1,538% — a modest multiple, not a
  robust margin, on a single, bullish instrument.
- The cross-instrument spread (BTC strong, EUR/XAU weak) is the classic
  signature of **long-only exposure riding one trending market**, not of a
  reusable edge.

## 5. How it compares to S-01 / S-05

| | S-01 (RSI mean-rev) | S-05 (SuperTrend-24) | S-06 (EMA 24/120) |
|---|---|---|---|
| Family | mean-reversion | trend (ATR) | trend (EMA) |
| Trades (full) | 777 | 10,402 | 2,405 |
| Best case (any inst, any cost) | XAU c0 +18.1% | BTC c0 +59.2% | BTC c0 +2,402% |
| Above buy-hold cross-market? | **No** | **No** | **No** (BTC only, 0 bps only) |
| Diagnosis | cost × freq | cost × freq | single-instrument beta |

## 6. How to reproduce

```bash
# From the repo root (Python 3.12, .venv):
.venv/bin/python strategy/code/strategy_ema_spread.py --instrument EUR_USD
.venv/bin/python strategy/code/strategy_ema_spread.py --instrument BTC_USD --cost-bps 0
.venv/bin/python strategy/run_matrix.py S06
```

---

### Caveats
- One instrument at a time; results are per-instrument.
- 0 bps is a diagnostic, **not** a realistic execution assumption.
- Capped at the in-sample boundary; the OOS holdout may be run **once**
  (see `config/strategies.yml` `oos` block).
- This is a **reference backtest of a standard rule**, included to stress the
  cross-market gate and confirm the shared core generalises — not a trading
  recommendation.
