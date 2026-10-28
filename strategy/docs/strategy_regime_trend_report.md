# Regime-Gated Slow-Trend Follower — Backtest Report (S-07)

> **Purpose:** the strategy the last six rejections specifically point at —
> a **slow** trend signal (120-bar SuperTrend) on a **coarse** clock (1h),
> gated by a **regime** measure (ADX-24 > 25), long **and** short. Deliberately
> *not* a claim of alpha.
> **Date:** 2026-10-29 · **Code:** [strategy/code/strategy_regime_trend.py](../code/strategy_regime_trend.py) ·
> **Library:** [strategy/strategy_regime_trend_lib.py](../strategy_regime_trend_lib.py) ·
> **Data:** `data/ohlcv_1h_features/ohlcv_1h_features.parquet` ·
> **Registry ID:** S-07 — see [STRATEGY_REGISTRY.md](../STRATEGY_REGISTRY.md)
>
> **OOS caveat:** all numbers are the **capped** in-sample window
> (`until: 2025-07-31`, the day before the OOS holdout
> `oos.holdout_start = 2025-08-01` in `config/strategies.yml`). The full matrix
> (all 18 cells, 0/2/5 bps × 3 instruments × 2 windows) is at
> [results/S07/matrix.md](../results/S07/matrix.md).

---

## 1. The strategy

| Item | Choice |
|---|---|
| Trend signal | **SuperTrend-120 / 2.0×ATR** — pre-computed `st_dir_120_2` (+1 up / −1 down) in the 1h feature table ([pipeline/indicators.py](../../pipeline/indicators.py)) |
| Regime gate | **ADX-24 > 25** — pre-computed `adx_24`; a flip is taken **only** while trending, else flat |
| Entry / re-direction | a SuperTrend-120 **flip** whose flip-bar has `adx_24 > 25` → in at bar T+1 open (long if up, short if down) |
| Exit | the **next** SuperTrend-120 flip (or a flip in a weak regime → flat) |
| Position | Long **and** short, one position at a time, 1 unit, fully closed at data end |
| Cost | **2 bps one-way** baseline; standard matrix is 0 / 2 / 5 bps |
| Causality | signal on closed bar T, fill at bar T+1 open — **no lookahead** |
| Data | 2020-01 → 2025-07-31 (capped in-sample), ~5.5 years, ~42k 1h bars/instrument |
| Timeframe | **1h** (chosen so the trade frequency lands in the low-frequency band) |

Why this strategy: the six rejections converge on a required shape — **low
frequency** (S-01/S-04/S-05 died on cost×frequency), **non-empty** (S-03's
filter was an empty intersection), and **cross-market** (S-06 was a single-
instrument fit). A slow trend on a coarse clock, taken only in a confirmed
trending regime, is the cleanest way to hit all three with a genuinely new
mechanism (no MACD, no RSI, no squeeze, no fast 24-bar trend). The frequency
was probed on real data **before** building: ~280 SuperTrend-120 flips/yr on
1h, ~70–105 after the ADX gate — deliberately below the ~1,900/yr that killed
S-04/S-05.

## 2. Results (full window, 2020-01 → 2025-07-31)

| Instrument | Cost (bps) | Strategy | Buy & hold | Trades | Trades/yr | Win % | Sharpe (wk) | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| **EUR_USD** | 0 | −5.07% | +3.1% | 374 | 67.8 | 36.6 | −0.24 | 12.0% |
| **EUR_USD** | **2** | **−18.26%** | +3.1% | 374 | 67.8 | 33.2 | −0.96 | 20.0% |
| **EUR_USD** | 5 | −34.69% | +3.1% | 374 | 67.8 | 28.6 | −1.91 | 35.8% |
| **BTC_USD** | 0 | +73.6% | +1,288% | 577 | 104.6 | 37.3 | 0.43 | 72.8% |
| **BTC_USD** | **2** | **+37.8%** | +1,288% | 577 | 104.6 | 36.4 | 0.33 | 75.4% |
| **BTC_USD** | 5 | −2.5% | +1,288% | 577 | 104.6 | 35.7 | 0.17 | 79.0% |
| **XAU_USD** | 0 | −16.2% | +110% | 396 | 71.8 | 35.6 | −0.36 | 32.2% |
| **XAU_USD** | **2** | **−28.4%** | +110% | 396 | 71.8 | 33.6 | −0.71 | 40.7% |
| **XAU_USD** | 5 | −43.6% | +110% | 396 | 71.8 | 31.3 | −1.21 | 51.6% |

New metrics: **Sharpe (weekly)** (weekly-resampled equity, `strategy/metrics.py`)
and **Trades/yr** (the opportunity-frequency check). Both confirm the design
goal — **the frequency is right** (68–105 trades/yr, well below the churn that
killed S-04/S-05).

## 3. Verdict: **rejected — low-frequency achieved, but no edge at 0 bps**

1. **The frequency target was hit.** 374–577 trades over ~5.5 years
   (68–105/yr). This is *not* a cost×frequency failure in the S-05 sense — the
   rule trades far less often. If the strategy merely had a *weak* edge that
   cost eroded, we would see it *win* at 0 bps and lose at 5 bps. That is
   **not** what happens.
2. **It does not even win at 0 bps.** On 2 of 3 instruments (EUR −5.1%,
   XAU −16.2%) the strategy is *below* buy-hold with **free execution**; on BTC
   it is +73.6% vs buy-hold +1,288% — positive, but an order of magnitude
   short. So the signal itself has no exploitable edge over simply holding.
3. **Win rate is 33–37%** — below a coin flip at every instrument and cost
   tier. A trend-follower should, if the trend signal were real, win more
   often than it loses (few, larger winners). Getting *fewer* winners than
   losers means the "trend" flips are not predicting the subsequent move; they
   are roughly as likely to be tops as bottoms.
4. **Diagnosis = signal quality**, the same root cause as S-02. The regime gate
   did its job (frequency + a plausible "only trade trends" shape), but a
   SuperTrend-120 flip is not, on its own, a directional edge on any of these
   three instruments in this period.

## 4. How S-07 differs from the trend family it joins

| | S-05 (ST-24, 5m) | S-07 (ST-120 + ADX, 1h) |
|---|---|---|
| Signal speed | 10,402 trades | **374–577 trades** |
| Gate | none | **ADX-24 > 25** |
| 0 bps (EUR) | −32.7% | **−5.1%** |
| Win % | ~50 | **33–37** |
| Diagnosis | cost × frequency | **signal quality** |

S-07 is the "fixed" version of S-05 (right frequency, sensible gate) and it
still loses — which is the stronger, more useful finding: *frequency and
regime alone do not create an edge; the underlying trend signal on these
instruments does not have one.*

## 5. What this tells us (and what would need to be true)

- The rig has now isolated **three** distinct failure modes across 7
  strategies — cost×frequency (S-01/04/05), empty signal (S-03), and signal
  quality (S-02/07) — plus single-instrument (S-06). That spread is the
  point: it is what prevents the false comfort of "my rejected strategy just
  had the wrong frequency."
- For S-07 *specifically* to be worth another look, a **new hypothesis** would
  need to supply a genuinely directional edge (e.g. a filter that selects
  *which* trends, not just *when* there is a trend) — that is a new S-id,
  not a retune.

## 6. How to reproduce

```bash
# From the repo root (Python 3.12, .venv):
.venv/bin/python strategy/code/strategy_regime_trend.py --instrument EUR_USD
.venv/bin/python strategy/code/strategy_regime_trend.py --instrument BTC_USD --cost-bps 0
.venv/bin/python strategy/run_matrix.py s07
```

---

### Caveats
- One instrument at a time; results are per-instrument.
- 2 bps one-way is an assumption (no slippage / partial fills / liquidity).
- Capped at the in-sample boundary; the OOS holdout may be run **once**
  (see `config/strategies.yml` `oos` block) and is now data-bound
  (re-running the holdout on the same parquet is refused by `run_matrix`).
- This is a **reference backtest of a standard rule**, included to test the
  specific hypothesis "slow trend + regime gate on 1h" — not a trading
  recommendation.
