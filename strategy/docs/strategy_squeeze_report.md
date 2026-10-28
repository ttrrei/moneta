# Squeeze-Onset Follower — Backtest Report (S-04)

> **Purpose:** a *volatility-compression* strategy (the structural opposite of
> S-01's mean-reversion): trade a Bollinger-band squeeze **onset** — enter when
> the bands squeeze inside the Keltner channel (0→1), hold the direction, exit
> when it relaxes (1→0). Deliberately *not* a claim of alpha.
> **Date:** 2026-10-28 · **Code:** [strategy/code/strategy_squeeze.py](../code/strategy_squeeze.py) ·
> **Library:** [strategy/strategy_squeeze_lib.py](../strategy_squeeze_lib.py) ·
> **Data:** `data/ohlcv_5m_features/ohlcv_5m_features.parquet` ·
> **Registry ID:** S-04 — see [STRATEGY_REGISTRY.md](../STRATEGY_REGISTRY.md)
>
> **OOS caveat:** all numbers are the **capped** in-sample window
> (`until: 2025-07-31`, the day before the OOS holdout
> `oos.holdout_start = 2025-08-01` in `config/strategies.yml`). The full matrix
> (all 18 cells) is at [results/S04/matrix.md](../results/S04/matrix.md).

---

## 1. The strategy

| Item | Choice |
|---|---|
| Indicators | **Bollinger-band squeeze** — pre-computed `sqz_on_24` (0/1), `bb_mid_24` in the 5m feature table ([pipeline/indicators.py](../../pipeline/indicators.py)) |
| Direction | on the onset bar, long if `close > bb_mid_24`, else short; held through the episode |
| Entry | the **squeeze-onset bar** (0→1 transition) → in at bar T+1 open, once per episode |
| Exit | the **squeeze-off bar** (1→0 transition) → out at bar T+1 open |
| Position | Long **and** short, one position at a time, 1 unit, fully closed at data end |
| Cost | **2 bps one-way** baseline; standard matrix is 0 / 2 / 5 bps |
| Causality | signal on closed bar T, fill at bar T+1 open — **no lookahead** |
| Data | 2020-01 → 2025-07-31 (capped in-sample), ~5.5 years |
| Timeframe | **5m** |

Why this strategy: a Bollinger squeeze is the textbook *volatility-compression
event* — the bands narrow inside the Keltner channel and then relax. The
premise was that at 5m it would be a low-frequency setup (a handful of
episodes a day), so the cost model should not dominate. The trade is taken at
the **onset** of the compression (0→1) and held until it relaxes (1→0). The
premise — that it is rare — is exactly what this test checks.

## 2. Results (full window, 2020-01 → 2025-07-31)

| Instrument | Cost (bps) | Strategy | Buy & hold | Trades | Trades/yr | Sharpe (wk) | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|
| **EUR_USD** | 0 | −7.8% | +2.3% | 10,586 | 1,899 | −15.4 | 98.7% |
| **EUR_USD** | **2** | **−98.7%** | +2.3% | 10,586 | 1,899 | −15.6 | 98.7% |
| **BTC_USD** | 0 | −57.8% | +1,538% | 10,508 | 1,885 | −2.0 | 99.5% |
| **BTC_USD** | **2** | **−99.4%** | +1,538% | 10,508 | 1,885 | −2.1 | 99.4% |
| **XAU_USD** | 0 | −20.9% | +113% | 10,065 | 1,806 | −8.0 | 98.6% |
| **XAU_USD** | **2** | **−98.6%** | +113% | 10,065 | 1,806 | −7.5 | 98.6% |

New metrics: **Sharpe (weekly)** (weekly-resampled equity, see `strategy/metrics.py`)
and **Trades/yr** (the opportunity-frequency check) both make the failure
mechanism visible at a glance: ~1,900 trades/year is not a low-frequency setup.

## 3. Verdict: **rejected — cost × frequency; the "low-frequency" premise is false at 5m**

1. **The strategy trades ~10,500 times in 5.5 years (≈1,900/yr).** A
   24-bar Bollinger squeeze on 5m bars resolves *constantly* — it is not a
   rare event, it is the norm. The whole cost story is the same failure mode
   as S-05 (SuperTrend): ~10k round-trips × 4 bps round-trip ≈ the entire
   equity, before any edge.
2. **Even at 0 bps (free execution) it loses on every instrument** — EUR
   −7.8%, BTC −57.8%, XAU −20.9%. So the problem is not *only* cost: the
   direction chosen (close vs band mid at the onset bar) has no predictive
   edge either. Both the signal and the frequency are wrong.
3. **Max drawdown ~99%** at 2 bps — the position is re-churned so fast that
   adverse fills compound.

## 4. A note on the rule's implementation (honesty about churn)

A naive per-bar reading of "long if close > mid, short if close < mid while
squeezed" re-fires *every bar* and churns to ~19,307 trades. The registered
rule therefore fires **once per squeeze episode** (on the onset bar) and
holds the chosen direction until the squeeze turns off. This is the intended
"trade the episode" semantics — but it still yields ~10.5k episodes, which
confirms the premise failure is real and not an artifact of re-entry churn.

## 5. How the candidates compare (all rejected, different reasons)

| | S-02 (RSI 1h) | S-03 (RSI+trend) | S-04 (squeeze) |
|---|---|---|---|
| Family | mean-reversion | filtered mean-rev | volatility-compression |
| Trades / 5.5y | 74–79 | **0** | **~10,500** |
| 0 bps (EUR) | −5.2% | 0.0% (no trades) | −7.8% |
| Diagnosis | **signal quality** | **empty condition** | **cost × frequency** |

Three different logic families, three different failure modes — none of them
"the backtest broke." That spread of *diagnoses* is the useful output: the
rig is now able to distinguish a weak signal from an empty signal from a
churn-and-bleed signal, which is exactly what prevents overfitting by
wishful-tuning.

## 6. What *would* make this worth another look

- **Coarser timeframe**: the same squeeze-onset rule on 1h bars would fire
  ~12× less often. But the 1h feature table would need the `sqz_on`/`bb_mid`
  columns computed (currently 5m only) — a small additive pipeline change, and
  it would be a **new** registered strategy, not a re-tuning of S-04.
- **Long-only** to match the market's upward drift on BTC — but the 0 bps
  long+short already loses, so a directional slice is unlikely to save it.

## 7. How to reproduce

```bash
# From the repo root (Python 3.12, .venv):
.venv/bin/python strategy/code/strategy_squeeze.py --instrument EUR_USD
.venv/bin/python strategy/code/strategy_squeeze.py --instrument BTC_USD --cost-bps 0
.venv/bin/python strategy/run_matrix.py s04
```

---

### Caveats
- One instrument at a time; results are per-instrument.
- 2 bps one-way is an assumption (no slippage / partial fills / liquidity).
- Capped at the in-sample boundary; the OOS holdout may be run **once**
  (see `config/strategies.yml` `oos` block).
- This is a **reference backtest of a standard rule**, included to document a
  cost/frequency rejection honestly — not a trading recommendation.
