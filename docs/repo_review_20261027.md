# Repository Review & Pitfall Analysis Report

This document summarizes the comprehensive review of the Moneta repository, identifying potential conflicts, architectural pitfalls, and consistency issues.

## 1. High-Level Architectural Assessment

The repository follows a structured pipeline for financial data processing and strategy backtesting:
- **`pipeline/`**: Handles data extraction (`extract_oanda.py`, `extract_oci.py`), processing (`aggregate_ohlcv.py`), and feature engineering (`indicators.py`).
- **`library/`**: Contains core indicator implementations (Supertrend, PSAR) and shared utilities.
- **`strategy/`**: Implements the backtesting engine (`engine.py`), specific strategy logic (`strategy_rsi_lib.py`), and execution matrices (`run_matrix.py`).
- **`config/`**: Centralizes parameters and whitelists (`indicators.yml`, `setting.yml`).

## 2. Key Findings & Potential Pitfalls

### A. Configuration vs. Implementation Consistency (The "Whitelist" Trap)
**Finding:** There is a strict "Hard Whitelist" for time-window parameters (e.g., `6, 12, 24, 60, 120`) enforced by `pipeline.indicators.validate_grid()`.
- **Pitfall:** The documentation (specifically legacy notes and `docs/indicators.md`) has had conflicting statements about whether *all* parameters are whitelisted or only *windows*.
- **Current Status:** The code correctly distinguishes between **Windows** (strictly whitelisted via `validate_grid`) and **Free Parameters** (sanity-checked via `validate_free_params`).
- **Risk:** Future developers might attempt to add non-window parameters (like Supertrend multipliers) to the window grid, which would lead to `ValueError` or logical errors.

### B. Data Integrity & Timeframe Mismatch (The "B1" Failure)
**Finding:** Loading a 1-hour rule on 5-minute data (or vice versa) could lead to silent failures or incorrect metrics.
- **Mitigation:** `strategy/strategy_rsi_lib.py` implements `detect_bar_seconds()`, which calculates the median bar interval and raises `SystemExit` if it deviates from the expected timeframe.
- **Pitfall:** This guard is currently implemented in the `strategy_rsi_lib` wrapper. If new strategies are added without calling `make_bars()` (or a similar guard), the "B1" timeframe mismatch risk returns.

### C. Market-Specific Logic (The "B6" Entry Guard)
**Finding:** The "B6 rule" prevents new entries on gap bars or near market close to avoid unrealistic fills.
- **Pitfall:** The guard is optional (`--entry-guard` in CLI). Inconsistent use of this guard across different backtests can lead to non-comparable results.
- **Recommendation:** Ensure the `S-01` baseline and all subsequent alpha versions explicitly document the state of the B6 guard.

### D. Dependency & Environment Management
**Finding:** The project relies on `duckdb` for high-performance parquet reads and `talib` for technical indicators.
- **Pitfall:** `TA-Lib` is a C-library wrapper and is notoriously difficult to install across different OS environments.
- **Recommendation:** Consider providing a Dockerfile or a detailed `environment.yml` to ensure consistent C-library versions across team members.

## 3. Technical Debt & Conflicts

- **Legacy Files:** The `legacy/` folder contains several review documents (`review2.md`, `review3.md`) and patches. While useful for history, there is a risk that outdated "rules" from these documents are mistaken for current requirements.
- **Config Shadowing:** `config/setting.example.yml` exists to prevent `setting.yml` (containing API tokens) from being committed. This is a good practice, but the `.gitignore` must be strictly maintained to prevent accidental token leaks.

## 4. Final Verdict

The repository is in a **highly stable and disciplined state**. The "Code as Truth" approach is evident in `pipeline/indicators.py`, and the safety guards (`validate_grid`, `detect_bar_seconds`) effectively mitigate the most common pitfalls in financial backtesting (lookahead bias and timeframe mismatch).

**Priority Actions:**
1. Standardize the B6 guard documentation.
2. Ensure all new strategy libraries implement the `detect_bar_seconds` check.
3. Move "Maintenance Rules" from `legacy/` reviews into a permanent `CONTRIBUTING.md` or `docs/MAINTENANCE.md`.
