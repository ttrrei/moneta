# Independent verification of the three legacy reviews — 2026-10-31

The reviews are useful starting points, but they are not a safe execution plan
without corrections. Their strongest recommendations concern reproducibility,
configuration binding, data reuse and research discipline. Several statistics
are stale, some purported bugs are already fixed, and some proposed research
rules do not follow from the evidence.

Reviewed against `936f7b9`, including all Markdown in `legacy/review1`,
`legacy/review2` and `legacy/review3`, and the Word document in review2. The
`AGENTS.md` inside review1 is a proposed root policy: its current filesystem
scope is that review folder. It has not been installed as project policy.
No proposed owner decisions were treated as decisions already made by you.

## Project model

Moneta/Nova is an offline strategy research system. OCI and OANDA extractors
produce raw minute candles; `pipeline/load_data.py` cleans and deduplicates
them into Parquet. `aggregate_ohlcv.py` builds 5m/1h bars. `indicators.py`
computes features per instrument, with TA-Lib and the custom `library/`
indicators. Its higher-timeframe context uses completed-bar as-of joins.
DuckDB supplies queries and a metadata/view catalog; Parquet holds the data.

Strategies consume features through the data-layer holdout guard. Their rules
decide the position for open `i` using information through close `i-1`.
`strategy/engine.py` owns fills, compounded equity, costs and metrics.
`run_matrix.py` evaluates registered configurations; the sweep helper evaluates
named variants. CSV/Markdown evidence, the registry and trial log are checked by
`scripts/check_results.py`. The holdout ledger controls the final one-shot
evaluation. This is not a portfolio engine or a live execution system.

Local in-sample queries confirmed **21 instruments in both feature tables**.
The feature builder already discovers instruments and accepts an instrument
filter. The three-instrument evaluation universe is a research choice, not a
pipeline limitation. No holdout prices or returns were inspected in this review.

## Recomputed evidence

Run `.venv/bin/python scripts/audit_research.py` to reproduce
[the machine-readable audit](research_audit_20261031.json). It uses committed
CSV and Markdown evidence, without opening market data.

| Item | Verified finding |
|---|---|
| Registry | 132 strategies; 130 rejected, two parked; no finalist |
| Sweep files | 15,480 stored rows; 14,400 distinct cells; 1,080 identical repeats |
| Named sweep configurations | 800, rather than the 720 in reviews 2/3 |
| Total named configurations represented | 827 including seven early baselines and twenty fixed rules; these are not independent hypotheses |
| Sweep groups at 2 bps | 1,600 strategy/variant/window groups; 4,800 instrument cells |
| Positive edge cells | 83; 17 have at most two trades |
| Cross-market wins in both overlapping windows | `s55/looser` and `s109/ema_gate`, before any extra floors |
| Fixed S-113..S-132 batch | Zero positive edge cells out of 120 at 2 bps |
| Date errors | 85 trial rows used future batch labels; not the 86 repeatedly claimed |
| Baseline checks | 493 pytest tests; 37 checker mutation cases; checker PASS with 22 warnings |

The reviewers' failure classifier assigns 1,274 groups to “no wins and more
than 54 trades/year”, 239 to other losses, 62 to one-instrument wins, 15 to
empty signals and ten to two-or-more-instrument wins. The first bucket is
**79.625%** of the current groups. A trade-frequency threshold alone does not
prove that transaction costs caused a loss: compare gross and net performance
to establish that. A one-instrument win is not necessarily a BTC win.

The quoted one-trade `s109/ema_gate` example is incorrect. The actual full-window
EUR/XAU cells have 17/20 trades and +4.03/+5.38 percentage points of edge;
their recent-window cells have three/two trades and +3.81/+2.02 points.
BTC loses to its benchmark in both windows. Low observation counts remain a
valid concern, but the review's example and explanation are not reliable.

## Recommendations and implementation decisions

| Recommendation | Assessment and action |
|---|---|
| Review1 S1.2/S1.3; review3 configuration binding | Confirmed. Moved named definitions into `strategy/variants.py`; both runners resolve effective defaults there. Matrix runner supports all existing IDs and `--variant`. OOS requires both `oos_variant` and a matching `oos_config_hash`, before fingerprinting, preflight or reservation. Hashes cover resolved defaults and the complete fixed RuleSpec where applicable. Added a read-only pin printer and checker X16. |
| RSI SQL-bound normalization | Confirmed. The dedicated RSI loader now queries the same normalized UTC instants that the guard checks. |
| First-bar wraparound | Confirmed in S-33/S-37/S-39, not the named S-71/S-89 examples, which were already guarded. Fixed the affected rules and generator. Added future-perturbation regression coverage across all strategy rules. |
| Review3 S-18 previous ATR mismatch | Confirmed. Previous VWAP distance now uses the previous bar's ATR. |
| Review3 missing-data gates | Confirmed. Enabled EMA gates now require finite price/EMA inputs through one shared helper; generated callers and templates use it. Optional S-17 ADX/Supertrend gates fail closed. S-08 no longer treats missing band position as zero. Exits remain available. |
| Review3 S-08 thresholds | Unusual, but explicitly encoded in both implementation and variants. Changing +100/-100 to conventional oscillator thresholds would change the research hypothesis. Kept the thresholds. |
| Review3 S-21 squeeze-release concern | It deliberately holds during compression, as documented in its rule. It is not a squeeze-release strategy. A different entry mechanism needs a separate hypothesis, not a silent repair. |
| Matrix completeness/report counts | Added shared grid validation before report generation: missing, duplicate, unexpected, errored and non-finite required values fail. Instrument wins are distinct instruments, with separate counts per overlapping window. |
| Date and rejection bookkeeping | Corrected future trial/registry dates using first-evidence commit dates, explicitly labeled as recorded-by bounds. Exact run times cannot be reconstructed from commit times. Preserved filenames as stable batch identifiers and annotated reports. Added 123 missing rejection records from existing reasons/links, with checker X17 to prevent another omission. |
| Runner provenance | New matrix runs write `manifest.yml`: resolved configuration/hash, bounds, cost tiers, data fingerprint, source commit/dirty flag, package versions and actual UTC timestamps. No historical manifests were invented. Dirty development runs remain possible and disclose their state. |
| Repeated Parquet reads | Added bounded, scoped, thread-local in-memory reuse for in-sample frames across cost tiers. File replacement invalidates entries, returned copies isolate consumers, the guard runs on every access, and holdout frames bypass the cache. Signal state is rebuilt for each cost run. |
| Failure visibility | Sweep failures remain in the CSV and now produce a nonzero exit. Selection must match declared variants; a new sweep requires an explicit output path. |
| CI correctness | `if: always()`, X5 and shared sweep-window resolution were already implemented. Preserved them. Added compilation of all Python entry points after finding thirteen generated CLIs with indentation errors; repaired those files and added help-path smoke coverage for every strategy CLI. |
| OOS output routing | Independently found that CLI summary output used the original directory while cells used the OOS directory. Both now use the same destination. Mixed/partial OOS matrices and incomplete OOS axes are refused before data access. |

`strategy/engine.py`, evaluation windows, pass thresholds, registered strategy
IDs/statuses, historical result CSV/JSON numbers and the real holdout ledger
were not changed. Non-base matrix runs write below `<ID>/variants/<name>` so
they do not overwrite base evidence. OOS summaries remain in `<ID>_oos`.

### Historical results affected by signal repairs

Preserving an old number does not make it a valid reproduction target after
repairing a lookahead defect. Review1's requirement that every number remain
identical cannot take priority over fixing causality.

For S-33/S-37/S-39, compared original and repaired rule decisions across 144
existing variant/instrument/window combinations, with local **in-sample** data.
Twenty combinations change early decisions: four S-33 combinations and sixteen
S-37 combinations. State converges by decision index nine at the latest.
The other 124 combinations are unchanged. All subsequent rule decisions agree
once state converges; this does not imply that compounded P&L agrees.
See [the comparison record](causality_impact_20261031.json).

S-18's ATR correction can affect decisions throughout a series. Missing-data
gate changes affect cases with absent/non-finite gate inputs. Historical
artifacts remain evidence of the original implementation, with explicit
caveats. Recompute affected performance into a separate versioned artifact
before treating those results as current-code evidence or nominating a finalist.
This review did not regenerate historical returns or open a new strategy search.

### Measured performance improvement

On this workspace, a profiled `s55/looser`, EUR_USD, `last_12m` evaluation at
0/2/5 bps took 1.6531 seconds without the scoped cache and 0.9884 seconds with
it. Time attributed to `load_bars` fell from 0.6446 to 0.2921 seconds. The
three output rows were identical. This is one profiled comparison, affected
by filesystem/import warmup; it is not a general speedup claim. Tests separately
prove that repeated identical reads share one DuckDB read, and that window
changes, file replacement and scope exit prevent stale reuse.

## Research proposals that need correction

1. **Do not inspect holdout buy-and-hold returns to choose a finalist or decide
   whether the holdout is informative.** Review3 follow-up Phase E would make
   selection depend on the protected outcome. Baseline-only inspection can
   contaminate the test just as strategy evaluation can. It was not executed.
2. **“Provably dead families” is unsupported.** Related variants on overlapping
   windows are correlated evidence. Family names assigned from the first
   alphabetic indicator also misclassify composites. Closing the specific
   unsuccessful search can be sensible; declaring trend, reversal or volume
   universally dead does not follow. No blanket family ban was installed.
3. **One fixed rule per strategy does not eliminate selection bias.** Selecting
   among twenty rules still creates a multiple-testing burden. Screening,
   regimes, horizons and exit variants all count as research choices.
4. **The proposed floors are policy choices, not statistical guarantees.** Ten
   trades, 20% exposure and five percentage points of edge may exclude useful
   low-exposure strategies, and fixed total-return floors vary with window
   length. Sharpe comparisons need care when the benchmark Sharpe is negative
   or its drawdown is zero. Keep historical criteria and register a justified
   new criterion before a new experiment; do not retroactively relabel evidence.
5. **Dollar neutrality does not imply beta neutrality.** Different asset
   volatilities, currencies and financing matter. Three single-instrument
   backtests cannot be added together and called a funded portfolio. Review2's
   claim that cross-sectional work needs only a benchmark change is incorrect.
6. **Position sizing is not a one-line UNIT_SIZE change.** That constant
   cancels from the legacy return calculation. Fractional holdings need explicit
   capital, rebalance, financing and turnover accounting. The legacy short
   convention is reciprocal: a price fall from 100 to 50 returns +100% before
   costs, whereas a fixed entry-notional short returns +50%. A new conventional
   portfolio core cannot silently claim exact equivalence to that convention.
7. **21:00 UTC does not always equal 17:00 New York.** It becomes 22:00 UTC
   during New York standard time. Choose a fixed UTC boundary or a local-market
   boundary explicitly and test DST. Do not describe them as identical.
8. **Slow-trend sample requirements must fit the data.** Five or six years do
   not supply 100 independent 250-day holdings. More instruments do not create
   independence automatically. A random-entry control also needs causal
   event/side matching and realistic market-session constraints.
9. **Statistical test requirements need precise definitions.** A single noise
   fixture cannot guarantee its realized false-discovery fraction is below q;
   FDR is an expectation over repetitions. Bootstrap nulls/block lengths,
   dependence assumptions, minimum samples and the full tested family must be
   specified before implementing Holm/BH gates. In YAML registration examples,
   quote `"on"`/`"off"`: PyYAML otherwise interprets them as booleans.
10. **Review2's precedence table contradicts itself.** It says higher numbers
    win while putting code last and also says prose should override code.
    Intent, current implementation and measurements must be distinguished.
    Adopted configuration defines the contract; implementation proves current
    behavior; proposed review prose is not an owner decision.

## Feasible next stages

| Stage | Deliverable and dependency | Decision |
|---|---|---|
| Reproduction repair | Versioned reruns of affected historical configurations; compare with preserved originals; fix stale report interpretations | Next engineering task; no new search or holdout needed |
| Experiment contract | One machine-readable preregistration source, explicit feature/parameter/horizon grids, trial accounting and commit-before-run enforcement | Sound; agree on the contract first. Date strings alone do not prove preregistration. Preserve legacy replay access. |
| Data isolation | Publish separate development/holdout tables atomically, maintaining feature warmup/context and loader/catalog compatibility | Feasible migration, not a file move. Raw source data still exists, so a split is defense in depth, not an access-control boundary. |
| Slow bars and costs | DST-aware daily/weekly bars, quality/staleness inventory and sourced instrument costs including financing | Feasible; build on the existing 21-instrument pipeline. Do not guess the missing cost inputs. |
| Screening/validation | Small preregistered feature study with next-open targets, chronological non-overlapping validation, overlap-aware statistics and full search accounting | Useful next research infrastructure; feature selection itself must remain inside development data |
| Weighted portfolio core | Separate conventional accounting contract, cost/financing model, realistic calendars, tests against hand-calculated cases | Required for volatility targeting, cross-sectional portfolios and path-dependent exits; retain the current engine as a historical reference |
| New directions | Choose one small registered slow-trend, structure, exit-control or relative-value experiment once its prerequisites exist | Plausible hypotheses, not proven edges. No new strategy batch was run here. |
| Large cleanup/acceleration | Spec migration, persistent signal cache, Numba, process pools, legacy removal, broad lint/type/coverage rollout | Benchmark and prove equivalence first; adding dependencies or deleting reference code now is unnecessary |

Review1 is the most complete dependency plan, but it combines several major
projects and contains the accounting/calendar/statistics issues above.
Review2 is right to prioritize research discipline, but its counts, family
inferences and “small engine change” assessment are unreliable.
Review3's gradual migration, feature research and matched benchmarking are
useful; its old follow-up checklist targets a superseded 102-strategy tree and
its holdout-inspection phase should be rejected.

## Validation and preserved state

Validation includes the full pytest suite, the dependency-free checker mutation
suite, the committed-results checker, compilation of pipeline/library/strategy/
script/test entry points, CLI help smoke tests, and the bounded in-sample
comparisons described above. Existing saturation/freshness warnings remain
visible; their checks were not weakened. Final local verification: **652 tests
passed, 38/38 checker mutation cases passed, and the results checker passed
with zero failures and 22 existing warnings**. All Python entry points compiled.
A real in-sample `s55/looser` EUR_USD recent-window matrix reproduced the
committed metrics at all three cost tiers and wrote the expected manifest.
Remote CI was not run in this session.

The ledger remains byte-identical, SHA-256
`3148000cf7f66bc564211610f3423571c484e6eae979963577a3ba6a48236cd6`.
No holdout strategy, holdout benchmark inspection, finalist promotion, new
research batch, commit or push was performed. The pre-existing deletion of
`legacy/README.md` is left as found.
