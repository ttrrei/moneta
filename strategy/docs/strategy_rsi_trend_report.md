# RSI-24 in an Uptrend — Backtest Report (S-03)

> **Purpose:** a *filtered* mean-reversion entry — RSI-24 < 30 **and** price
> above its 24-EMA — to test whether buying only dips *within* an uptrend beats
> the unfiltered S-01/S-02 rule. Deliberately *not* a claim of alpha.
> **Date:** 2026-10-28 · **Code:** [strategy/code/strategy_rsi_trend.py](../code/strategy_rsi_trend.py) ·
> **Library:** [strategy/strategy_rsi_trend_lib.py](../strategy_rsi_trend_lib.py) ·
> **Data:** `data/ohlcv_5m_features/ohlcv_5m_features.parquet` ·
> **Registry ID:** S-03 — see [STRATEGY_REGISTRY.md](../STRATEGY_REGISTRY.md)
>
> **OOS caveat:** all numbers are the **capped** in-sample window
> (`until: 2025-07-31`, the day before the OOS holdout
> `oos.holdout_start = 2025-08-01` in `config/strategies.yml`). The full matrix
> (all 18 cells) is at [results/S03/matrix.md](../results/S03/matrix.md).

---

## 1. The strategy

| Item | Choice |
|---|---|
| Indicators | **RSI-24** and **EMA-24** — pre-computed `rsi_24`, `ema_24` in the 5m feature table ([pipeline/indicators.py](../../pipeline/indicators.py)) |
| Entry (long) | previous closed bar's `rsi_24 < 30` **AND** `close > ema_24` → in at bar T+1 open |
| Exit (long) | previous closed bar's `rsi_24 > 55` → out at bar T+1 open |
| Position | Long-only, one position at a time, 1 unit, fully closed at data end |
| Cost | **2 bps one-way** baseline; standard matrix is 0 / 2 / 5 bps |
| Causality | signal on closed bar T, fill at bar T+1 open — **no lookahead** |
| Data | 2020-01 → 2025-07-31 (capped in-sample), ~5.5 years, ~416k 5m bars/instrument |

Why this strategy: the natural improvement on a pure RSI trigger is to buy
dips only when the broader trend is up. If the S-01/S-02 weakness was "buying
dips during downtrends," gating on `close > ema_24` should remove the worst
entries and improve the hit rate.

## 2. Results (full window, 2020-01 → 2025-07-31)

| Instrument | Cost (bps) | Trades | Strategy | Buy & hold |
|---|---:|---:|---:|---:|
| **EUR_USD** | 0 / 2 / 5 | **0** | 0.0% | +2.3% |
| **BTC_USD** | 0 / 2 / 5 | **0** | 0.0% | +1,538% |
| **XAU_USD** | 0 / 2 / 5 | **0** | 0.0% | +113% |

**The strategy makes zero trades on every instrument, every window, every
cost tier.** The result of a 0-trade backtest is defined as 0.0% return
(flat the entire window), Sharpe 0, no drawdown, no exposure — see the
`n_trades == 0` guards in [strategy/engine.py](../engine.py).

## 3. Verdict: **rejected — the registered entry condition is empty on this data**

This is the important, honest finding, and it is **not a bug**:

- Verified directly on the full 5m feature table (all bars, not just the
  in-sample window), the intersection is **exactly 0** on every instrument:

  | Instrument | `rsi_24 < 30` | `close > ema_24` | **both** |
  |---|---:|---:|---:|
  | EUR_USD | 6,482 | 256,767 | **0** |
  | BTC_USD | 7,216 | 257,640 | **0** |
  | XAU_USD | 5,960 | 250,284 | **0** |

  Each predicate alone is common (thousands of bars), yet they never co-occur.
- RSI-24 below 30 (a 24-period oversold reading) and "price above the 24-EMA"
  cannot co-occur on this data — a 24-bar lookback that has pushed RSI under 30
  has, by construction, pushed price *below* its 24-EMA. The "uptrend filter"
  is therefore not a *filter* at all; it is a **negation** of the entry.
- The empty intersection on all three instruments shows this is a structural
  property of the two indicators at this period, not an instrument artifact.

The correct response to an empty signal set is to **report it and reject**, not
to quietly substitute a different rule. Doing the latter would be exactly the
data-snooping the registry is built to prevent.

## 4. What this tells us

| | S-01 (RSI only) | S-03 (RSI + trend) |
|---|---|---|
| Entry | RSI-24 < 30 | RSI-24 < 30 **and** close > EMA-24 |
| Trades / 5.5y | ~270 | **0** |
| Diagnosis | cost × frequency | **empty condition (indicators conflict)** |

Adding the "trend" filter did not sharpen the signal — it annihilated it. The
RSI-24/EMA-24 pair is too tightly coupled on a 24-bar window for the intended
"dip in an uptrend" to ever trigger. A dip-in-uptrend rule needs the
**oversold** and **trend** windows to be on different clocks (e.g. a fast RSI
against a slow trend line), not both on 24.

## 5. What *would* make this worth another look

- **Mismatched windows**: a short RSI (e.g. 7–14) against a long trend EMA
  (e.g. 100–200) is the standard "pullback in a trend" construction — the
  two clocks are independent enough for the intersection to be non-empty.
- But that would be a **new** registered strategy (new rule, new S-id, new
  trial-log row), not a re-tuning of S-03.

## 6. How to reproduce

```bash
# From the repo root (Python 3.12, .venv):
.venv/bin/python strategy/code/strategy_rsi_trend.py --instrument EUR_USD
.venv/bin/python strategy/run_matrix.py s03
# confirm the empty intersection directly:
.venv/bin/python - <<'PY'
import duckdb
c=duckdb.connect()
print(c.execute("SELECT count(*) FROM read_parquet('data/ohlcv_5m_features/ohlcv_5m_features.parquet') WHERE instrument='EUR_USD' AND rsi_24<30 AND close>ema_24").fetchone())
PY
```

---

### Caveats
- One instrument at a time; results are per-instrument.
- A 0-trade result is 0.0% by definition (flat all window), **not** a positive
  signal — it is a rejection.
- Capped at the in-sample boundary; the OOS holdout may be run **once**
  (see `config/strategies.yml` `oos` block).
- This is a **reference backtest of a standard rule**, included to document an
  empty-signal rejection honestly — not a trading recommendation.
