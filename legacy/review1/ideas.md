# ideas.md — parking lot (cannot be executed from here)

> Place at `docs/plan/ideas.md`. Anything written here is **not registered and must not be run**. An idea becomes
> executable only when it is added to a direction file (new file or a `version` bump) in a commit **before** any run
> that uses it (`04_*` §6). Mid-run inspiration goes here, not into code.

## Rules

- One entry per idea, append-only. Do not delete entries; change `status` instead.
- An entry needs: id, one-line hypothesis, why it might differ from what has been tried, data it needs, and status
  (`parked` / `promoted to <file> v<n>` / `rejected (reason)`).
- Ideas are not trials. Nothing here counts toward budgets until it is registered and run.

## Entries

| id | Hypothesis | Why different | Needs | Status |
|---|---|---|---|---|
| I-01 | Structure features (prior-day/week extremes, session ranges, opening range, confirmed swing levels) carry information the oscillators do not | Distinct information source; stub direction D-D | `03_*` D3; screening layer G1 must show survivors first | parked → direction D-D (stub in `04_*` §2) |
| I-02 | Generated / combined indicators in a purged walk-forward model (many weak signals ensembled) | Combines weak signals instead of hunting one strong rule; stub direction D-E | purged CV infrastructure; strict trial budget | parked → direction D-E (stub in `04_*` §2) |
| I-03 | Session / hour-of-day seasonality in FX and metals (London/NY open effects) | The legacy calendar family had the highest per-trade gross edge (but includes BTC trend) | `03_*` D3 session definitions; instrument cost model | parked |
| I-04 | Carry / rollover differentials for FX (financing-rate based) | A different premium from price patterns | financing/swap data (`03_*` D7) | parked |
| I-05 | Volatility-regime switching: scale risk with a volatility forecast rather than a signal | Pure risk-management layer; can be bolted onto any direction | daily vol features (`03_*` D2) | parked |
| I-06 | Cross-sectional carry + momentum composite across the D-C universe | Combines two independent premia | `03_*` D7 financing data; D-C results | parked (after D-C G2) |
| I-07 | Regime-conditional exits (different exit design in high vs low volatility) | Extension of D-B, only if D-B shows exits matter | D-B results | parked (after D-B G3) |

## How to promote an idea

1. Write or bump a direction file with a full registration block (explicit grid, `max_configs`, kill criterion).
2. The owner reviews and commits it; the checker (R2/R3) enforces the order.
3. Only then does an AI session run it via `scripts/run_direction.py`.
