# Tests

This directory contains the **test suite for the `pipeline/` modules** only.

- Tests here cover the Bronze data pipeline's public functions in `pipeline/extract_oci.py` (OCI listing/download and idempotent skipping, safe path resolution, zip extraction to a flat CSV directory, unique target paths, YAML config loading, happy paths and degradation/edge cases such as missing files/empty inputs).
- **Not** intended for trading-strategy validation/backtesting — strategies, Alpha signals, and portfolio-level evaluation are out of scope for this folder and belong to separate evaluation tooling.
- Conventions:
  - Test files named `test_*.py`.
  - Prefer unit tests that do not require network access; mock OCI and filesystem where necessary.
  - Test directory name `tests/` is kept so pytest auto-discovers without extra config.
  - Run with: `pytest -q` (7 tests currently exercise `pipeline/extract_oci.py`).