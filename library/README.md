# `library/` — custom indicator library

The project's **own** indicator implementations, kept separate from
`pipeline/indicators.py` (the feature engine) so they can be referenced by
the pipeline *and* checked in isolation.

## Why a separate folder

* **TA-Lib is fixed third-party code.** Everything it ships is available to
  every strategy. Our *custom* indicators (things TA-Lib lacks, like
  Supertrend) deserve their own home with their own tests.
* **Isolation = easier correctness checks.** Each module is pure NumPy
  (in: OHLC arrays; out: arrays). No parquet, no DuckDB, no pandas, no
  network. Their tests run in < 1 s on any machine — no need to build the
  10 GB feature tables to verify the math of a single indicator.
* **Single source of truth.** The pipeline imports from here; it does not
  re-implement. Changing an indicator means changing one file plus its tests.

## Current contents

| Module | What it provides | Notes |
|---|---|---|
| `supertrend.py` | `supertrend(h, l, c, atr, mult)` → (line, direction) | Causal, path-dependent. TA-Lib has no Supertrend, so this is our own. |
| `psar.py` | `psar_line(h, l, accel, max)` + `psar_direction(c, sar)` | SAR line via `talib.SAR`; the direction convention + parameter rules are ours. |
| `utils.py` | `param_tag` (0.02 → `0p02` column tag), `validate_free_params` | Shared by the modules and the pipeline. |
| `market_structure.py` | `confirmed_structure`, `frozen_events` | Confirmed swings and frozen range/retest events; experimental additive stage, [definitions](../docs/indicator_research_P1_spec.md). |

## Conventions (apply to every module here)

1. **Causal** — bar `T` uses only bars `≤ T`. Path-dependent recursions are
   still causal; the pipeline drops `WARMUP_DROP` leading rows to *reduce*
   start-point dependence — a fixed warmup does **not** guarantee the state
   has converged (see `supertrend.py` and `docs/indicators.md` §8 Gate 2).
2. **No synthetic data** — undefined values are `NaN`, never imputed.
3. **Free parameters are explicit** — multipliers / accelerations are named
   by the caller, never library defaults (B10/B11 in `docs/indicators.md` §4.1).
4. **Deterministic** — same input, same output; no clock, no randomness.

## Adding a new indicator (checklist)

1. New module `library/<name>.py` implementing the above conventions.
2. Pure-NumPy unit tests in `tests/test_indicators.py` (or a dedicated
   `tests/test_<name>.py`): prefix-invariance, bounds, degenerate input,
   and (if a reference exists, e.g. pandas-ta-classic) a parity smoke test.
3. Export from `library/__init__.py`.
4. Feature-engine integration in `pipeline/indicators.py` (column names +
   `param_tag`), then the **four-file sync**:
   `config/indicators.yml` → `docs/indicators.md` →
   `strategy/STRATEGY_BACKGROUND.md` → `docs/README.md`/BRD/SAD literals
   (recompute column counts).
5. Rebuild the feature parquets and re-run the S-01 matrix as a regression
   check (must still reproduce 944/1011/920 trades).

The P1 research stage uses `pipeline/research_features.py` and its own explicit
`config/indicator_research.yml`; it does not rebuild or add columns to default
Gold. Its definitions, tests and measured decisions are recorded in the
[research report](../docs/indicator_research_20261031_report.md). Promotion into
the default feature engine would require the integration/sync steps above.
