# Strategy Trial Log

> **Purpose:** the cumulative record of *every* strategy attempt — tested,
> parked, **and rejected** — so the multiple-testing burden of "best of N" is
> always visible. This is the OOS discipline from `config/strategies.yml`
> (`trial_log.required_fields`). A `tested` result earned after many rejections
> is worth far less than one earned on the first try; this table makes that
> difference explicit and auditable.
>
> **Rules:**
> - Add a row for **every** Step 6 evaluation (Step 7 close-out), regardless of
>   outcome. Rejected outcomes are *mandatory* here (the registry's
>   "Rejected combinations" table stays; this log adds the *running count*).
> - `n_tried_before` = how many distinct strategies were attempted **before**
>   this one (0 for the first). It is the honest denominator for "best of N".
> - `window` ∈ `full` | `last_12m` | `oos`. The **`oos`** row is the single,
>   final out-of-sample check and may be written **at most once** per strategy
>   (`config/strategies.yml` → `oos.usage = finalist_only_once`).
> - If a strategy is re-opened with a *new hypothesis*, it gets a **new ID** and
>   a new row — never a retune of the same row (see `generated_strategy.md` §6).

| # | date | strategy_id | hypothesis (one line) | window | outcome | ret vs BH (primary) | n_tried_before |
|---|------|-------------|-----------------------|--------|---------|---------------------|----------------|
| 1 | 2026-10-28 | S-01 | 5m RSI-24 30/55 long-only mean reversion | full | **rejected** | full c2 −19.2% vs +2.3% (EUR_USD); −34.8% vs +1538% (BTC_USD); 777 trades — cost × frequency | 0 |
| 2 | 2026-10-28 | S-05 | 5m SuperTrend(24, 2.0) `st_dir_24_2` flip trend-following (long-only) | full | **rejected** | 10,402 trades (full); below buy-hold at every cost tier on all 3 instruments (full c2 EUR −99%/BTC −97%/XAU −98%) — cost × frequency | 1 |
| 3 | 2026-10-28 | S-06 | 5m EMA-spread 24/120 `ema_spread_24_120` trend follower (long-only) | full | **rejected** | full c0 +2402% vs BH +1538% (BTC only), below buy-hold at 2/5 bps (+903/+154%); loses on EUR at every tier — single-instrument, not cross-market | 2 |
| 4 | 2026-10-29 | S-02 | same RSI-24 30/55 rule on 1h bars (1/12 the cost of S-01) | full | **rejected** | 74–79 trades (full), below buy-hold at every cost tier (c0 EUR −5.2%/BTC +21%/XAU +6.7% all < buy-hold) — signal quality, not frequency | 3 |
| 5 | 2026-10-29 | S-03 | RSI-24 < 30 AND close > ema_24 (buy dips in an uptrend) | full | **rejected** | **0 trades** in all 18 cells: `rsi_24<30` and `close>ema_24` never co-occur on this data (verified intersection = 0 on all 3 instruments) — empty signal, not a bug | 4 |
| 6 | 2026-10-29 | S-04 | Bollinger squeeze-onset follower (long/short, enter on 0→1 onset, exit on 1→0) | full | **rejected** | ~10,500 trades (full), ~1,900/yr; below buy-hold at every cost tier incl. 0 bps (c0 EUR −7.8%/BTC −57.8%/XAU −20.9%) — cost × frequency, "low-frequency" premise false at 5m | 5 |
| 7 | 2026-10-29 | S-07 | Regime-gated slow trend: ST-120 flips taken only while ADX-24>25 (1h, long/short) | full | **rejected** | ~68–105/yr (low-freq ✓) but below buy-hold at every cost tier incl. 0 bps (c0 EUR −5.1%/BTC +73.6%/XAU −16.2% vs +3.1/+1288/+110); win 33–37% — signal quality, not frequency | 6 |

<!--
Append a new row for every attempt. Keep `n_tried_before` = (previous max #) so
the running count is always the true number of strategies tried so far.
Example next row:
| 2 | 2026-11-02 | S-02 | same RSI rule on 1h bars (1/12 the cost) | full | <outcome> | <ret vs BH> | 1 |
-->
