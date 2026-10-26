# Strategy Registry

> **Purpose:** single source of truth for every strategy in this project.
> Before starting a new strategy, check this registry so no strategy duplicates
> an existing indicator + timeframe + rule combination.
>
> **Rules of use:**
> 1. Every new strategy **must** get a row in the table below (update at creation, again after each major result change).
> 2. "Key indicators" lists the *decision-driving* features (not every column read).
> 3. Two strategies are considered **duplicates** if they share the same key indicators + timeframe + entry logic, regardless of parameter tweaks.
> 4. Status: `tested` (backtest run & reported) · `candidate` (designed, not yet run) · `rejected` (tested, failed, do not re-test without new hypothesis) · `parked` (deprioritized).

## Registry

| ID | Name | Timeframe | Key indicators | Entry logic (short) | Exit logic (short) | Side | Status | Code | Report | Last run | Result (ret vs BH) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| S-01 | RSI mean-reversion (base) | 5m | `rsi_24` | RSI_24 < 30 | RSI_24 > 55 | long | **rejected** | [code/strategy_rsi.py](../code/strategy_rsi.py) | [docs/strategy_rsi_report.md](strategy_rsi_report.md) | 2026-10-26 | −21.6% vs +0.3% (EUR_USD); −41.9% vs +1031% (BTC_USD) |
| S-02 | RSI mean-reversion (1h) | 1h | `rsi_24` | RSI_24 < 30 | RSI_24 > 55 | long | candidate | — | — | — | (planned: same rule, 1/12 the trade count & cost of S-01) |
| S-03 | RSI + trend filter | 5m | `rsi_24`, `ema_24` | RSI_24 < 30 AND close > ema_24 | RSI_24 > 55 | long | candidate | — | — | — | (planned: trade only with the trend) |
| S-04 | Squeeze release | 5m | `sqz_on_24`, `bb_mid_24` | sqz_on_24 = 1 + direction vs bb_mid_24 | RSI-style or time stop | long/short | candidate | — | — | — | (planned: volatility-compression event, far fewer trades) |

## Indicator usage map

Which key indicators are already *claimed* by tested/candidate strategies (helps spot overlap fast):

| Indicator | Used by |
|---|---|
| `rsi_24` | S-01, S-02, S-03 |
| `ema_24` | S-03 |
| `sqz_on_24` | S-04 |
| `bb_mid_24` | S-04 |

## Rejected combinations — do not re-test without a new hypothesis

| Combination | Why rejected |
|---|---|
| 5m RSI_24 30/55 long-only (S-01) | Cost × frequency: ~1,000 trades × 4 bps round-trip ≈ 40% of equity paid in spread; per-trade edge (±0.03%) smaller than per-trade cost. See [S-01 report](strategy_rsi_report.md) §3. |

## Conventions

- **ID scheme:** `S-NN`, never reuse a rejected ID; open a new one and reference the old in the row notes.
- **Result column:** latest full-history result for the *primary* instrument, plus buy-hold reference.
- **Cost assumption:** 2 bps one-way (OANDA CFD spread) unless the report states otherwise.
- **No-lookahead:** every strategy must signal on a closed bar and fill at the next bar's open (spec §3.3).
