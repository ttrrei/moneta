# RSI Mean-Reversion Strategy — Backtest Report

> **Purpose:** first end-to-end proof that the new feature pipeline is usable for
> strategy backtesting. Deliberately the *simplest possible* strategy (one
> indicator, one rule), not a claim of alpha.
> **Date:** 2026-10-26 · **Code:** [strategy/code/strategy_rsi.py](../code/strategy_rsi.py) ·
> **Data:** `data/ohlcv_5m_features/ohlcv_5m_features.parquet` (built 2026-10-26) ·
> **Registry ID:** S-01 — see [STRATEGY_REGISTRY.md](../STRATEGY_REGISTRY.md)

> **Update (2026-10-27):** the strategy now runs through the shared
> [engine](../engine.py) and is exposed as a lib
> ([strategy_rsi_lib.py](../strategy_rsi_lib.py)) plus a thin CLI. The standard
> 3×2×3 evaluation is automated by [run_matrix.py](../run_matrix.py); the
> current matrix (all 18 cells, this exact baseline) is at
> [results/S01/matrix.md](../results/S01/matrix.md). A B6 entry-guard option
> (`--entry-guard`) blocks new entries on gap / near-market-close bars — this
> report's numbers are the **guard-off** baseline (944/1011/920 trades); the
> guard-on variant drops a few gap-bar entries (e.g. EUR 944→941, −21.58%→−21.25%).

---

## 1. The strategy (the simplest possible)

| Item | Choice |
|---|---|
| Indicator | **RSI-24** (`rsi_24`, Wilder RSI, TA-Lib) on 5m bars |
| Entry (long) | RSI_24(T) < **30** on a closed bar → buy at **bar T+1 open** |
| Exit (long) | RSI_24(T) > **55** on a closed bar → sell at **bar T+1 open** |
| Position | Long-only, one position at a time, 1 unit, fully closed at data end |
| Cost | **2 bps one-way** (typical OANDA CFD spread), applied at entry and exit |
| Causality | Signal on closed bar T, fill at next bar's open — **no lookahead** (spec §3.3) |
| Data | 2020-01 → 2026-10, ~500k 5m bars per instrument |

Why RSI-24: it is the most universally understood oscillator, it is already in
the feature table, and the 30/55 thresholds are the classic "oversold /
neutral" levels. It needs no parameters beyond the window we already fixed on
the CFD grid.

## 2. Results (full history, 2020-01 → 2026-10)

| Instrument | Trades | Win rate | **Strategy** | Buy & hold | Max DD | Avg trade | Exposure |
|---|---:|---:|---:|---:|---:|---:|---:|
| **EUR_USD** | 944 | 54.3% | **−21.6%** | +0.3% | 22.2% | −0.026% | 12.5% |
| **BTC_USD** | 1,011 | 63.2% | **−41.9%** | +1031% | 68.0% | −0.028% | 14.3% |
| **XAU_USD** | 920 | 62.2% | **−29.2%** | +159% | 37.1% | −0.035% | 12.8% |
| **NAS100_USD** | 1,075 | 62.5% | **−34.6%** | +230% | 50.1% | −0.035% | 14.1% |

**Verdict: the strategy loses money on every instrument tested**, roughly in
proportion to the transaction cost of its ~1,000 trades.

## 3. Why it loses — diagnosis

1. **Costs dominate.** At ~1,000 trades × 4 bps round-trip ≈ **40% of equity
   paid in spread** over the period. The average trade is only ±0.03%, i.e.
   the *edge per trade is smaller than the cost per trade*. No signal quality
   question: the trade frequency is structurally uneconomic for a CFD spread.
2. **A high win rate with negative expectancy.** 54–63% of trades win, but
   losers are larger than winners (classic mean-reversion distribution: many
   small recoveries, occasional deep continued moves). Win rate is the wrong
   headline; expectancy (avg trade) is negative.
3. **Long-only mean reversion in trending assets is one-sided.** In a strong
   downtrend, "RSI < 30" keeps buying a falling knife; there is no short side
   to harvest the same signal.
4. **5m timeframe amplifies everything.** 5-minute RSI crosses its thresholds
   constantly; the signal churns far faster than the spread it pays.

## 4. What this exercise *did* achieve

- ✅ **Pipeline validation.** The feature table was queried with DuckDB,
  filtered, and driven an event-loop backtest in **~1 second per instrument**.
  This is exactly the intended workflow (feature parquet → strategy code).
- ✅ **No-lookahead path proven.** Signal-at-T / fill-at-T+1-open is enforced
  in code, matching the spec's causality rule.
- ✅ **Honest baseline.** We now know the cost/frequency boundary: a viable
  strategy on this data needs either **far fewer trades** (slower signals) or
  **larger per-trade edges** (stronger conditional signals).

## 5. Concrete next steps (ranked)

1. **Slow the signal down.** Same RSI rule evaluated on **1h bars**
   (`ohlcv_1h_features` already exists) — ~1/12 the trade count, ~1/12 the cost.
   This single change is the cheapest way to test whether *any* edge survives.
2. **Add a regime filter.** Trade the RSI signal only when the trend agrees —
   e.g. require `close > ema_24` before going long. Uses existing columns,
   one extra condition.
3. **Use the squeeze feature.** Enter on `sqz_on_24 = 1` (BB inside Keltner —
   volatility compression) with direction from `close` vs `bb_mid_24`;
   squeeze releases are the natural 5m event and should be far less frequent
   than RSI threshold crosses.
4. **Cost sensitivity sweep.** Re-run the same strategy at 0 / 2 / 5 bps to
   quantify exactly how much edge would be required to break even — this turns
   "it lost" into a concrete required-edge number.
5. **Short side.** Symmetric short rules (RSI > 70 exit at 45) to test the
   signal in both directions before concluding it has no information.

## 6. How to reproduce

```bash
# From the repo root (Python 3.12, .venv):
.venv/bin/python strategy/code/strategy_rsi.py --instrument EUR_USD
.venv/bin/python strategy/code/strategy_rsi.py --instrument BTC_USD --since 2023-01-01
```

Outputs a JSON metrics block (n_trades, win rate, total return vs buy-hold,
max drawdown, avg trade, Sharpe, market exposure).

---

### Caveats
- One instrument at a time, no cross-sectional logic; results are per-instrument.
- 2 bps one-way is an assumption, not an account fill model (no slippage, no
  partial fills, no liquidity constraints).
- No out-of-sample split yet: all 2020→2026 is in-sample. Before any
  parameter tuning, hold out the last 12 months.
- This is a **reference backtest of the simplest possible rule**, included to
  prove the pipeline and set a cost baseline — not a trading recommendation.
