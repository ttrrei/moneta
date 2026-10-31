# Versioned replay of repaired legacy strategies

Existing S-18/S-33/S-37/S-39 configurations were replayed on local development
data, at the existing 0/2/5-bps tiers and three-instrument/two-window grid.
No new hypothesis, holdout evaluation or status change is included.

| Strategy | Recomputed cells | Positive benchmark edges at 2 bps, before → after | Largest absolute return delta across cost tiers, percentage points |
|---|---:|---:|---:|
| S-18 | 108 | 1 → 1 | 558.49 |
| S-33 | 144 | 0 → 0 | 1.04 |
| S-37 | 144 | 0 → 0 | 31.50 |
| S-39 | 144 | 0 → 0 | 0.28 |

All **180 original 2-bps cells** were first reproduced exactly using the rules
at `936f7b9` and the old midnight upper bound. The repaired replay produces
**540 cells** and **1,579 added/removed trade records at 2 bps**. Deltas combine
signal repairs with the full-final-day window correction. All cells change at
least one metric, including benchmark return or annualized frequency; this does
not mean every cell changes its trade sequence.

The four strategies still have no configuration beating the benchmark on two
instruments in both overlapping windows. Their historical rejected statuses
remain unchanged. The windows overlap and do not constitute independent
validation. The large S-18 differences make the original ATR-index result
unsuitable as evidence for the repaired implementation.

- [comparison.csv](comparison.csv): original and repaired metrics, differences,
  exact endpoints and legacy reproduction checks for every cost cell.
- [trade_changes.csv](trade_changes.csv): removed/added trades at 2 bps, including
  direction, entry/exit timestamps and prices. An altered exit is represented
  by removal of the old trade and addition of the new trade.
- [manifest.yml](manifest.yml): actual run interval, source revision and dirty
  flag, executed implementation digests, source CSV digests and scope.
- [input_provenance.yml](input_provenance.yml): opaque feature-file hashes
  explicitly recorded after the replay, plus the development gate-input audit.

Gate-input checks use only `time < 2025-08-01T00:00:00Z`. Price/EMA/ADX/Supertrend
inputs are finite on both timeframes for the evaluation instruments. BTC has
twelve null `bb_pctb_24` values on each timeframe; the S-08 loader's existing
`IS NOT NULL` condition already excludes them. Additional gate-only historical
replays are therefore unnecessary for this data snapshot.

To reproduce into a fresh directory from the repository root:

```bash
.venv/bin/python scripts/recompute_repairs.py --out /tmp/moneta-repair-replay
```

The script refuses an existing destination, unknown strategy grids, conflicting
source cells and legacy reproduction mismatches. Rule decisions are evaluated
once per configuration and replayed immutably across cost tiers; shared engine
accounting is unchanged. No original result artifact is overwritten.
