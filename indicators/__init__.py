"""moneta indicator library — custom indicators built outside TA-Lib.

Why this folder exists
----------------------
TA-Lib is a fixed third-party library: everything it ships, every strategy in
this repo can call. The indicators we *create ourselves* (Supertrend today;
more later) live here, each in its own module, so that:

* **the pipeline references them** — ``pipeline/indicators.py`` imports
  from this package instead of embedding the logic;
* **each indicator can be checked in isolation** — the modules are pure
  (NumPy in, NumPy out; no parquet, no DuckDB, no network, no talib
  dependency inside the module), so their unit tests run anywhere and do not
  need the feature tables.

Conventions for every module in here (see ``README.md``):
  * **Causal** — value at bar T uses only bars <= T.
  * **No synthetic data** — undefined values are NaN, never imputed.
  * **Free parameters are named by the caller**, never library defaults
    (``docs/indicators.md`` §4.1 B10/B11).
  * **Deterministic** — same input, same output.

Current contents:
  * ``supertrend`` — causal Supertrend line + direction (+1/-1)
  * ``psar``       — PSAR line (TA-Lib) + our direction convention
  * ``utils``      — ``param_tag``, ``validate_free_params``
"""

from __future__ import annotations

from indicators.psar import psar_direction, psar_line
from indicators.supertrend import supertrend
from indicators.utils import param_tag, validate_free_params

__all__ = [
    "psar_direction",
    "psar_line",
    "supertrend",
    "param_tag",
    "validate_free_params",
]
