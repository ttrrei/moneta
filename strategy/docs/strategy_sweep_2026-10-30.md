# 6-Iteration Improvement Sweep — S-08 .. S-17 (2026-10-30)

Ten new strategies (S-08 .. S-17) were designed, unit-tested, and then each
was evaluated over **6 improvement iterations** on the shared in-sample matrix.

* **Scope:** 10 strategies × 6 variants × 3 instruments (EUR_USD, BTC_USD,
  XAU_USD) × 2 windows (`full`, `last_12m`) × 3 cost tiers (0/2/5 bps) =
  **1,080 cells**, all run through the shared engine (`strategy/engine.py`).
* **Data:** in-sample only — `until ≤ 2025-07-31`. **No OOS holdout was
  touched** (the holdout is a one-shot gate reserved for the single finalist
  under `config/strategies.yml → oos.pass_criteria`).
* **Harness:** `scripts/strategy_variants.py` (parallel sweep →
  `strategy/results/iterations_2026-10-30.csv`).
* **Summary:** `scripts/strategy_variants_report.py`.
* **Run log:** `strategy/results/iterations_run.log` (916 s wall, 8 workers).

## The 6 iterations (variant set)

Every strategy gets the same six *flavours* of improvement, parameterised per
rule (each variant is a named, reproducible config in
`scripts/strategy_variants.py → VARIANTS`):

| # | Flavour | Meaning |
|---|---|---|
| 1 | `base` | The strategy's base rule, default parameters. |
| 2 | `ema_gate` / regime gate | Add an entry gate (close > `ema_24`, or ST/ADX gate for S-17). |
| 3 | `slower` / `atr_*` / `hysteresis` / `band_*` / `cooldown` / `lag` | Rule-specific threshold change (slower oscillator, wider/narrower band, hysteresis, ATR magnitude gate, cooldown, or slope lag). |
| 4 | `1h` | Re-run the identical rule on the 1h feature table (1/12 the bar count → fewer trades). |
| 5 | `entry_guard` | Enable the B6 rule (no new entries on gap / near-market-close bars). |
| 6 | second rule-specific variant | e.g. `hysteresis_strict`, `atr_loose`, `band_wide`, `both_gates`, `fast_lag`. |

## Results — ranked by mean edge vs buy-hold (2 bps, 3 instruments)

`edge = total_return − buyhold_return` (both in %). **All cells are in-sample.**
A negative edge is expected to be *large* on the `full` window because
BTC_USD buy-hold is +1,538% over 2020-01 → 2025-07, so the comparison is
dominated by that beta; the `last_12m` window (in the CSV) is the more
balanced read. **No single cell cleared the pre-committed bar** (beat buy-hold
on ≥ 2 of 3 instruments at 2 bps) — see `scripts/strategy_variants_report.py`
output for the per-instrument ledger.

| Strategy | Best variant (2 bps) | mean edge vs BH | mean trades/yr (full) | notes |
|---|---|---|---|---|
| S-08 CCI-24 dip-buying | `1h` | −261.95 | 8.4 | 28 trades (full) at 1h; 5m base = 208 trades |
| S-09 Williams %R-24 | `1h` | −267.98 | 132.1 | cooldown_24 reduces 5m trades 5,886→3,967 |
| S-10 Stochastic-24 | `1h` | −280.68 | 213.1 | base 5m = 8,983 trades (cost × frequency) |
| S-11 MACD-12/60 turn | `1h` | −170.73 | 64.1 | ATR filter keeps base ~2,642 trades |
| S-12 Dual-velocity | `1h` | −173.12 | 156.5 | lag 6→120 changes trades 7,469→6,509 |
| S-13 Slow PSAR | `1h` | −141.92 | 159.2 | ±1 direction col ⇒ threshold variants coincide |
| S-14 Donchian-24 | `1h` | −85.63 | 296.5 | **best edge of all 60 cells**; 13,224 → 956 trades |
| S-15 Aroon-24 | `1h` | −265.37 | 77.8 | 5m base = 2,766 trades |
| S-16 MFI-24 | `1h` | −254.15 | 7.0 | **fewest trades** (30 full / 12 ema_gate) |
| S-17 Slow RSI-60 (1h) | `slower` | −249.09 | 0.1 | 0–2 trades — near-empty signal |

### Consistent pattern

1. **The 1h variant is the best iteration for 9 of 10 strategies** (the only
   exception is S-17, which is 1h-native and whose best variant is `slower`).
   Slower bars → fewer trades → lower cost drag, exactly the mechanism that
   failed S-01/S-02/S-04/S-05 on the cost×frequency axis.
2. **Gating (EMA / ST / ADX / entry-guard) reduces trade count but does not
   create a cross-market edge** — the same signature as S-03 (empty gate) and
   S-07 (regime gate).
3. **No variant beat buy-hold on ≥ 2 of 3 instruments at 2 bps**, so none
   advances to `finalist` under `config/strategies.yml → oos.pass_criteria`.

### Registry / trial-log action

All ten remain `candidate` in [STRATEGY_REGISTRY.md](../STRATEGY_REGISTRY.md)
and are recorded as **rejected** in [trial_log.md](../trial_log.md) rows 8–17
(the sweep was a genuine multi-attempt search; the honest best-of-N outcome is
that the search did not find a cross-market 2-bps edge on these families).

## Reproduce

```
venv/bin/python scripts/strategy_variants.py --workers 8 --out strategy/results/iterations_2026-10-30.csv
venv/bin/python scripts/strategy_variants_report.py --csv strategy/results/iterations_2026-10-30.csv
```
