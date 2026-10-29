"""Automated backtest matrix runner (T1.1 — G5 traceability without copy-paste).

Runs a strategy over an instrument × window × cost-tier matrix and persists
every cell, so the report's tables can be *generated* from the JSON instead of
retyped (WORKFLOW.md Step 4/5, Gate G5 "every number traces to a JSON block").

The in-sample matrix for S-01 (WORKFLOW.md Step 4):
  3 instruments × 2 windows (full, last_12m) × 3 cost tiers (0/2/5 bps) = 18 cells.

Windows are read verbatim from ``config/strategies.yml`` (fixed anchors, B4) —
never recomputed at run time. Both in-sample windows are capped at
``until: 2025-07-31`` (the day before the OOS holdout), so no in-sample run can
tune on holdout data. ``oos`` is the single out-of-sample check and is gated by
the one-time lock (a strategy with an already-adjudicated ``oos`` row is
refused a second holdout run).

Output layout (default ``--out strategy/results``)::

    strategy/results/S-01/
        EUR_USD__full__c0.json
        EUR_USD__full__c2.json
        ...  (18 cells)
        matrix.md       # paste-ready markdown tables (per window)
        summary.csv     # one row per cell (flat, for analysis)

Run from the repo root::

    python strategy/run_matrix.py --strategy s01
    python strategy/run_matrix.py --strategy s01 --instruments EUR_USD BTC_USD --windows full
    python strategy/run_matrix.py --strategy s01 --trial-row        # + one trial_log row
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from datetime import date
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import strategy.registry as registry_mod  # noqa: E402  (shared gate parsing, §1.6)

CONFIG_PATH = _REPO_ROOT / "config" / "strategies.yml"
TRIAL_LOG = _REPO_ROOT / "strategy" / "trial_log.md"
INSTRUMENTS = ["EUR_USD", "BTC_USD", "XAU_USD"]
COST_TIERS = [0.0, 2.0, 5.0]

# Strategy registry for runners: strategy id -> (label, callable signature).
# Adding a strategy = add one entry here (the callable must take the same
# keyword arguments as run_rsi and return its result dict).
_STRATEGIES: dict[str, dict] = {}


def _register_s01() -> None:
    from strategy.strategy_rsi_lib import run_rsi

    _STRATEGIES["s01"] = {"label": "S-01 RSI-24 mean-reversion", "run": run_rsi}


def _register_s05() -> None:
    from strategy.strategy_supertrend_lib import run

    _STRATEGIES["s05"] = {"label": "S-05 SuperTrend-24 follower", "run": run}


def _register_s06() -> None:
    from strategy.strategy_ema_spread_lib import run

    _STRATEGIES["s06"] = {"label": "S-06 EMA-spread-24/120 follower", "run": run}


def _register_s02() -> None:
    from strategy.strategy_rsi_1h_lib import run

    _STRATEGIES["s02"] = {"label": "S-02 RSI-24 mean-reversion (1h)", "run": run}


def _register_s03() -> None:
    from strategy.strategy_rsi_trend_lib import run

    _STRATEGIES["s03"] = {"label": "S-03 RSI + trend filter", "run": run}


def _register_s04() -> None:
    from strategy.strategy_squeeze_lib import run

    _STRATEGIES["s04"] = {"label": "S-04 Squeeze-onset follower", "run": run}


def _register_s07() -> None:
    from strategy.strategy_regime_trend_lib import run

    _STRATEGIES["s07"] = {"label": "S-07 Regime-gated slow trend (ADX gate)", "run": run}


_register_s01()
_register_s05()
_register_s06()
_register_s02()
_register_s03()
_register_s04()
_register_s07()


def _load_config() -> dict:
    import yaml

    with open(CONFIG_PATH, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _window_bounds(cfg: dict, window: str) -> tuple[str | None, str | None]:
    """Resolve a window name to (since, until) from config (fixed anchors).

    The holdout window is named ``oos``; every other window must carry an
    ``until`` cap so in-sample runs can never tune on holdout data
    (repo_review_20261027 §1.1). An empty window (since > until) is a config
    error — the runner refuses to run it instead of returning zero bars.
    """
    try:
        spec = cfg["windows"][window]
    except KeyError as exc:
        raise SystemExit(f"Unknown window {window!r}; see windows: in config/strategies.yml") from exc
    since = spec.get("since")
    until = spec.get("until")
    if window != "oos" and until is None:
        raise SystemExit(
            f"Window {window!r} has no `until` cap in config/strategies.yml; "
            f"in-sample windows must stop before oos.holdout_start.")
    if since is not None and until is not None and str(since) >= str(until):
        raise SystemExit(
            f"Window {window!r} is empty (since {since} >= until {until}). "
            f"Re-anchor the window in config/strategies.yml before running it.")
    return (None if since is None else str(since),
            None if until is None else str(until))


def _registered_timeframe(cfg: dict, strategy: str) -> str | None:
    """The timeframe a strategy is registered on (config `strategies:` block).

    Config keys are canonical (e.g. ``S-01``); the runner may pass a lowercase
    id (``s01``), so compare case- and dash-insensitively.
    """
    wanted = strategy.upper().replace("-", "")
    for key, spec in (cfg.get("strategies") or {}).items():
        if key.upper().replace("-", "") == wanted:
            return spec.get("timeframe")
    return None


def _registered_id(cfg: dict, strategy: str) -> str | None:
    """Canonical strategy id from the config registry (e.g. ``s01`` → ``S-01``)."""
    wanted = strategy.upper().replace("-", "")
    for key in (cfg.get("strategies") or {}):
        if key.upper().replace("-", "") == wanted:
            return key
    return None


def _cell_name(instrument: str, window: str, cost: float) -> str:
    return f"{instrument}__{window}__c{cost:g}"


def _parquet_columns(parquet: str) -> set[str]:
    """The set of column names present in a parquet file (cheap: metadata only)."""
    import duckdb
    con = duckdb.connect()
    try:
        rows = con.execute(
            "SELECT column_name FROM (DESCRIBE SELECT * FROM read_parquet(?))",
            [str(parquet)]).fetchall()
    finally:
        con.close()
    return {r[0] for r in rows}


def _sha256_file(path: Path) -> str | None:
    """Hex sha256 of a file, or ``None`` if it does not exist."""
    if not path.exists():
        return None
    import hashlib
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _git_commit_of(path: Path) -> str | None:
    """The abbreviated git commit that last touched ``path`` (None if unavailable)."""
    import subprocess
    try:
        out = subprocess.run(
            ["git", "log", "-1", "--format=%h", "--", str(path)],
            cwd=_REPO_ROOT, capture_output=True, text=True, timeout=15)
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout.strip()
    except (subprocess.SubprocessError, OSError):
        pass
    return None


def _talib_version() -> str | None:
    """The installed TA-Lib version (so a feature-code change is visible)."""
    try:
        import talib  # lazy: keeps the import path clean when talib is absent
        return talib.__version__
    except Exception:  # noqa: BLE001 — audit field, never fatal
        return None


def _data_fingerprint(parquet: str) -> dict:
    """Audit identity of the OOS dataset (repo_review_20261029 §2.3).

    The fingerprint is an **audit field** — it is recorded in the ledger but is
    *not* part of the lock key (the lock is keyed on (strategy, holdout_id),
    §1.2). It exists so a future reviewer can see *exactly which data* a
    consumption saw, and so a genuinely different holdout is distinguishable.

    It hashes the OHLCV columns — ``instrument, time, open, high, low, close,
    volume`` (whichever exist) — over the holdout interval only, using DuckDB's
    64-bit ``hash()`` summed as an order-independent :class:`HUGEINT` (a
    rebuild that only reorders rows keeps the same hash). ``open`` and ``close``
    must both be present — if either is missing the fingerprint fails loudly
    (the engine fills at ``open[T+1]``, so ``open`` must be covered). Also
    recorded: row count, first/last bar, ``sha256(config/indicators.yml)``, the
    git commit of ``pipeline/indicators.py``, and the TA-Lib version.
    """
    import duckdb  # lazy: keeps the OOS-lock path importable without duckdb at module load
    p = Path(parquet)
    cfg = _load_config()
    oos_win = (cfg.get("windows") or {}).get("oos") or {}
    holdout_start = oos_win.get("since") or cfg["oos"].get("holdout_start")
    holdout_until = oos_win.get("until")

    cols = _parquet_columns(str(p))
    if "open" not in cols or "close" not in cols:
        missing = [c for c in ("open", "close") if c not in cols]
        raise SystemExit(
            f"OOS data fingerprint requires both `open` and `close` in {p}; "
            f"missing {missing}. Refusing to fingerprint (the engine fills at "
            f"`open[T+1]`, so `open` must be covered).")

    hashed_cols = ["instrument", "time", "open", "high", "low", "close", "volume"]
    hashed_cols = [c for c in hashed_cols if c in cols]
    row_hash = " || '#' || ".join(f"cast({c} as VARCHAR)" for c in hashed_cols)

    where = ["time >= ?"]
    params: list = [str(p), holdout_start]
    if holdout_until:
        where.append("time <= ?")
        params.append(holdout_until)
    where_sql = " AND ".join(where)

    con = duckdb.connect()
    try:
        n, tmin, tmax, h = con.execute(
            f"SELECT count(*) n, min(time) tmin, max(time) tmax, "
            f"sum(hash({row_hash}))::HUGEINT h "
            f"FROM read_parquet(?) WHERE {where_sql}",
            params).fetchone()
    finally:
        con.close()

    return {
        "path": str(p),
        "holdout_start": holdout_start,
        "holdout_until": holdout_until,
        "hashed_columns": hashed_cols,
        "rows": int(n),
        "tmin": str(tmin),
        "tmax": str(tmax),
        "content_hash": int(h),
        "indicators_sha256": _sha256_file(_REPO_ROOT / "config" / "indicators.yml"),
        "indicators_git_commit": _git_commit_of(_REPO_ROOT / "pipeline" / "indicators.py"),
        "talib_version": _talib_version(),
    }


# ---------------------------------------------------------------------------
# One-time OOS holdout consumption (repo_review_20261029 Phase 1).
#
# The holdout is a **fixed, closed window with an explicit id**
# (``oos.holdout_id``). Access is gated three ways, all *fail closed*:
#
#   1. **Finalist-only** (shared in :mod:`strategy.registry`): the strategy
#      must be registered in config, be ``finalist`` in the registry, and have
#      a real in-sample trial row. `rejected` / `parked` / `candidate` /
#      unregistered / `<TBD>` are all refused.
#   2. **Once per (strategy, holdout)**: the ledger is an *append-only*
#      ``consumptions`` list and the lock is keyed on ``(strategy, holdout_id)``
#      — **not** on data content. Rebuilt data, a new path, appended rows or a
#      restart cannot re-open it. Every record is walked (not just the latest),
#      so the old ``reserve(A) → reserve(B) → check(A)`` chain-walk bug is gone.
#   3. **Per-holdout strategy cap** (D1): once ``max_strategies_per_holdout``
#      distinct strategies have consumed a holdout, it is *spent* for everyone.
#
# The attempt is **reserved before the holdout is loaded**, so a crash mid-run
# still counts as consumed. The data fingerprint is recorded for audit only —
# it is not part of the lock key (repo_review_20261029 §1.2 / §2.3).
# ---------------------------------------------------------------------------

#: Registry file the OOS gate reads (separate from the config so the gate and
#: the results-checker both parse the same table via :mod:`strategy.registry`).
REGISTRY_PATH = Path(__file__).resolve().parent / "STRATEGY_REGISTRY.md"

#: Schema version of strategy/oos_ledger.json (bump + migrate if the shape
#: ever changes; the loader refuses any other version, fail closed).
OOS_LEDGER_VERSION = 1

#: The retired pre-2026-10-29 ledger path. If it still exists we refuse to run
#: rather than guess which ledger is authoritative (repo_review_20261029 §1.3).
_RETIRED_LEDGER = Path(__file__).resolve().parent / "results" / "oos_consumption.json"


def _oos_ledger_path() -> Path:
    return Path(__file__).resolve().parent / "oos_ledger.json"


def _oos_holdout_spec(cfg: dict) -> tuple[str, int, object, object]:
    """Resolve the holdout identity + cap from config, failing closed.

    Returns ``(holdout_id, max_strategies_per_holdout, holdout_start,
    holdout_end)``. A holdout without an id is a config error — the runner
    refuses to run it instead of guessing (there is no "default holdout").
    """
    oos = cfg.get("oos") or {}
    holdout_id = oos.get("holdout_id")
    if not holdout_id:
        raise SystemExit(
            "config/strategies.yml has no `oos.holdout_id` — the holdout has no "
            "identity, so OOS is undefined. Set it before running the holdout.")
    max_per = oos.get("max_strategies_per_holdout", 1)
    if not isinstance(max_per, int) or isinstance(max_per, bool) or max_per < 1:
        raise SystemExit(
            f"config/strategies.yml: `oos.max_strategies_per_holdout` must be a "
            f"positive integer, got {max_per!r}.")
    return holdout_id, max_per, oos.get("holdout_start"), oos.get("holdout_end")


def _load_oos_ledger() -> dict:
    """Load the consumption ledger, **failing closed** on any bad input.

    A missing, unreadable, invalid-JSON, wrong-version or wrong-shape ledger
    all raise :class:`SystemExit`. There is deliberately **no** `return {}`
    fallback: the moment a guard cannot read its input it must refuse to run,
    never default to "allowed" (repo_review_20261029 §1.4).
    """
    p = _oos_ledger_path()
    if not p.exists():
        raise SystemExit(
            f"OOS ledger missing: {p}. Refusing to run the holdout (fail closed). "
            f"Create it as {{\"version\": {OOS_LEDGER_VERSION}, \"consumptions\": []}}.")
    try:
        text = p.read_text(encoding="utf-8")
    except OSError as exc:
        raise SystemExit(f"OOS ledger unreadable ({p}): {exc}") from exc
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"OOS ledger is not valid JSON ({p}): {exc}") from exc
    if not isinstance(data, dict):
        raise SystemExit(f"OOS ledger must be a JSON object ({p}), got {type(data).__name__}.")
    if data.get("version") != OOS_LEDGER_VERSION:
        raise SystemExit(
            f"OOS ledger version mismatch ({p}): found {data.get('version')!r}, "
            f"expected {OOS_LEDGER_VERSION}. Refusing to run (fail closed).")
    if not isinstance(data.get("consumptions"), list):
        raise SystemExit(f"OOS ledger `consumptions` must be a list ({p}).")
    return data


def _save_oos_ledger(ledger: dict) -> None:
    p = _oos_ledger_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(ledger, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(p)  # atomic-ish: readers never see a torn file


def _reserve_oos(strategy: str, fingerprint: dict, manifest: dict) -> dict:
    """Append a consumption record **before** the holdout is loaded.

    Bound to ``(strategy, holdout_id)`` — rebuilt data, a new path, appended
    rows or a restart cannot re-open the holdout. The data ``fingerprint`` is
    recorded as an audit field only (not part of the lock key). Returns the
    appended record.
    """
    ledger = _load_oos_ledger()
    cfg = _load_config()
    holdout_id, _max, h_start, h_end = _oos_holdout_spec(cfg)
    rec = {
        "strategy": registry_mod.norm_id(strategy),
        "holdout_id": holdout_id,
        "holdout_start": h_start,
        "holdout_end": h_end,
        "reserved_at": date.today().isoformat(),
        "status": "reserved",
        "fingerprint": fingerprint,
        "manifest": manifest,
    }
    ledger["consumptions"].append(rec)
    _save_oos_ledger(ledger)
    return rec


def _complete_oos(strategy: str) -> None:
    """Mark this strategy's most recent `reserved` record for the holdout as
    `completed`. Pure bookkeeping — a `reserved` record already blocks re-runs,
    so a crash that never reaches here still counts as consumed."""
    ledger = _load_oos_ledger()
    cfg = _load_config()
    holdout_id, _max, _hs, _he = _oos_holdout_spec(cfg)
    sid = registry_mod.norm_id(strategy)
    for rec in reversed(ledger["consumptions"]):
        if (registry_mod.norm_id(rec.get("strategy", "")) == sid
                and rec.get("holdout_id") == holdout_id
                and rec.get("status") == "reserved"):
            rec["status"] = "completed"
            break
    _save_oos_ledger(ledger)


def _check_oos_once(strategy: str, fingerprint: dict | None = None,
                    manifest: dict | None = None) -> None:
    """Refuse a holdout run unless the strategy is a clean finalist and the
    holdout has not already been consumed (by anyone, for D1).

    All checks are *fail closed*: a missing/unreadable ledger, registry or
    trial log raises rather than defaulting to "allowed" (repo_review_20261029
    §1.4). ``fingerprint`` is accepted for compatibility but is audit-only —
    the lock is keyed on ``(strategy, holdout_id)``, so data content cannot
    re-open the holdout.
    """
    cfg = _load_config()
    holdout_id, max_per, _hs, _he = _oos_holdout_spec(cfg)

    # Retired ledger present → refuse (there is no safe "which wins" answer).
    if _RETIRED_LEDGER.exists():
        raise SystemExit(
            f"Retired OOS ledger found at {_RETIRED_LEDGER}. It predates the "
            f"one-time holdout lock and must be reviewed and removed (its "
            f"consumptions belong in {_oos_ledger_path()}) before running OOS.")

    # Load inputs — fail closed if any are unreadable / malformed.
    ledger = _load_oos_ledger()
    consumptions = ledger["consumptions"]
    registry = registry_mod.parse_registry(REGISTRY_PATH)
    trials = registry_mod.parse_trial_log(TRIAL_LOG)

    # (1) Finalist-only gate (shared registry/trial parsing, §1.6).
    ok, reason = registry_mod.oos_eligible(strategy, cfg, registry, trials)
    if not ok:
        raise SystemExit(
            f"Strategy {strategy.upper()} is not eligible to consume the OOS holdout: "
            f"{reason}. (Only a `finalist` with a real in-sample outcome may.)")

    # (2) Label lock: an adjudicated `oos` row already exists for this strategy.
    if registry_mod.adjudicated_oos_rows(trials, strategy):
        raise SystemExit(
            f"Strategy {strategy.upper()} already has an adjudicated `oos` row in "
            f"{TRIAL_LOG}. Re-running the holdout is prohibited — open a new "
            f"strategy ID or a new, unseen holdout window.")

    sid = registry_mod.norm_id(strategy)

    # (3) Walk **every** consumption record (§1.5), not just the latest: this
    #     strategy may consume a given holdout exactly once.
    for rec in consumptions:
        if (registry_mod.norm_id(rec.get("strategy", "")) == sid
                and rec.get("holdout_id") == holdout_id):
            raise SystemExit(
                f"Strategy {strategy.upper()} already consumed holdout {holdout_id} "
                f"(reserved {rec.get('reserved_at')}, status {rec.get('status')!r}). "
                f"Re-running the holdout is prohibited — use a new, unseen holdout "
                f"window under a new holdout id.")

    # (4) D1: the holdout is spent once `max_per` distinct strategies consumed it.
    distinct = {registry_mod.norm_id(rec.get("strategy", ""))
                for rec in consumptions if rec.get("holdout_id") == holdout_id}
    if sid not in distinct and len(distinct) >= max_per:
        plural = "y" if len(distinct) == 1 else "ies"
        raise SystemExit(
            f"Holdout {holdout_id} was already consumed by {len(distinct)} distinct "
            f"strateg{plural} (the cap is `oos.max_strategies_per_holdout` = {max_per}). "
            f"It is now spent — further research needs a new, unseen holdout window "
            f"under a new holdout id.")


def run_matrix(
    strategy: str,
    instruments: list[str],
    windows: list[str],
    cost_tiers: list[float],
    timeframe: str,
    entry_guard: bool,
    out_dir: Path,
    allow_partial: bool = False,
) -> list[dict]:
    """Run every cell, persist per-cell JSON, and return the result list.

    Any failed cell aborts the run with a non-zero exit unless
    ``allow_partial`` is set (repo_review_20261027 §1.10: a 1-of-18 success
    must not be summarised as a full matrix).
    """
    if strategy not in _STRATEGIES:
        raise SystemExit(f"Unknown strategy {strategy!r}; registered: {sorted(_STRATEGIES)}")
    run = _STRATEGIES[strategy]["run"]

    cfg = _load_config()

    # Timeframe binding (repo_review_20261027 §1.7): the strategy's registered
    # timeframe is authoritative; the CLI cannot silently run it on 5m.
    expected = _registered_timeframe(cfg, strategy)
    if expected is not None and expected != timeframe:
        raise SystemExit(
            f"Strategy {strategy.upper()} is registered for timeframe {expected} "
            f"(config/strategies.yml); refusing to run it on {timeframe}.")
    parquet = {
        "5m": "data/ohlcv_5m_features/ohlcv_5m_features.parquet",
        "1h": "data/ohlcv_1h_features/ohlcv_1h_features.parquet",
    }[timeframe]

    fingerprint = _data_fingerprint(parquet)

    is_oos = "oos" in windows
    if is_oos:
        manifest = {
            "strategy": strategy,
            "instruments": instruments,
            "windows": windows,
            "cost_tiers": cost_tiers,
            "timeframe": timeframe,
            "entry_guard": entry_guard,
        }
        # (1) Finalist gate + once-per-(strategy,holdout) lock + D1 cap:
        #     refuse unless a clean finalist and the holdout is unspent.
        # (2) Reserve the attempt BEFORE the holdout is loaded, so a crash
        #     mid-run still counts as consumed (a `reserved` record blocks re-runs).
        # (3) OOS output goes to its own directory so it can never overwrite
        #     the in-sample matrix.md / summary.csv.
        _check_oos_once(strategy, fingerprint, manifest)
        _reserve_oos(strategy, fingerprint, manifest)
        out_dir = out_dir.parent / (out_dir.name + "_oos")

    out_dir.mkdir(parents=True, exist_ok=True)
    cells: list[dict] = []
    failures: list[tuple[str, str]] = []

    for instrument in instruments:
        for window in windows:
            since, until = _window_bounds(cfg, window)
            for cost in cost_tiers:
                name = _cell_name(instrument, window, cost)
                print(f"[{len(cells) + 1 + len(failures)}/{len(instruments) * len(windows) * len(cost_tiers)}] "
                      f"{name} ... ", end="", flush=True)
                try:
                    result = run(
                        parquet=parquet,
                        instrument=instrument,
                        timeframe=timeframe,
                        since=since,
                        until=until,
                        cost_bps=cost,
                        entry_guard=entry_guard,
                    )
                    result["window"] = window
                    result["window_until"] = until
                    result["data_fingerprint"] = fingerprint
                    result["matrix"] = {
                        "strategy": strategy,
                        "instruments": instruments,
                        "windows": windows,
                        "cost_tiers": cost_tiers,
                        "timeframe": timeframe,
                        "entry_guard": entry_guard,
                    }
                    out_path = out_dir / f"{name}.json"
                    out_path.write_text(json.dumps(result, indent=2))
                    print(f"ok  ({result['n_trades']} trades, "
                          f"{result['total_return_pct']}% vs BH {result['buyhold_return_pct']}%)")
                    cells.append(result)
                except SystemExit as exc:
                    print(f"FAIL ({exc})")
                    failures.append((name, str(exc)))
                    if not allow_partial:
                        raise
                except Exception as exc:  # noqa: BLE001 — one cell must not kill the matrix
                    print(f"ERROR ({exc!r})")
                    failures.append((name, repr(exc)))
                    if not allow_partial:
                        raise

    if failures:
        print(f"\n{len(failures)} cell(s) failed: " +
              "; ".join(f"{n}: {e}" for n, e in failures))
    if not cells:
        raise SystemExit("No cells completed; nothing to summarise.")

    # Book the holdout consumption as `completed` only when the run produced a
    # full matrix with no failed cells. A failed cell raises (unless
    # --allow-partial) *before* this, leaving the record `reserved` — which
    # still blocks re-runs, so a crash or partial run never re-opens the holdout.
    if is_oos and not failures:
        _complete_oos(strategy)

    return cells


def _fmt(v: float) -> str:
    return f"{v:+.2f}%"


def write_markdown(cells: list[dict], path: Path) -> None:
    """Paste-ready markdown tables, one per window (WORKFLOW Step 5 report input)."""
    m = cells[0]["matrix"]
    lines = [
        f"## {m['strategy'].upper()} — matrix results (generated, do not retype)",
        "",
        f"Windows: {', '.join(m['windows'])} · Cost tiers: {m['cost_tiers']} bps "
        f"one-way · Timeframe: {m['timeframe']} · Entry guard: "
        f"{'on (gap/near-close)' if m['entry_guard'] else 'off'}",
        "",
        "Values copied from the per-cell JSON (Gate G5). Buy-hold is the "
        "cost-free reference for the identical window.",
    ]
    for window in m["windows"]:
        lines += [
            "",
            f"### Window: `{window}`",
            "",
            "| Instrument | Cost (bps) | Ret % | Buy-hold % | Trades | Win % | MaxDD % | Sharpe | Sharpe (weekly) | Trades/yr | Exposure % |",
            "|---|---|---|---|---|---|---|---|---|---|---|",
        ]
        for c in cells:
            if c["window"] != window:
                continue
            lines.append(
                f"| {c['instrument']} | {c['cost_bps']:g} | {_fmt(c['total_return_pct'])} "
                f"| {_fmt(c['buyhold_return_pct'])} | {c['n_trades']} "
                f"| {c['win_rate_pct']:.1f} | {c['max_drawdown_pct']:.1f} "
                f"| {c['sharpe']:+.2f} | {c.get('sharpe_weekly', 0.0):+.2f} "
                f"| {c.get('trades_per_year', 0.0):.1f} | {c['exposure_pct']:.0f} |"
            )
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def write_csv(cells: list[dict], path: Path) -> None:
    fieldnames = [
        "strategy", "instrument", "window", "timeframe", "cost_bps", "entry_guard",
        "start", "end", "n_bars", "n_trades", "total_return_pct", "buyhold_return_pct",
        "max_drawdown_pct", "win_rate_pct", "avg_trade_return_pct", "sharpe",
        "sharpe_weekly", "trades_per_year", "exposure_pct", "span_years",
    ]
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        for c in cells:
            row = dict(c)
            row["strategy"] = c["matrix"]["strategy"]
            w.writerow(row)


def _trial_log_rows() -> list[list[str]]:
    """All real trial_log.md data rows (HTML-comment examples excluded)."""
    if not TRIAL_LOG.exists():
        return []
    body = re.sub(r"<!--.*?-->", "", TRIAL_LOG.read_text(), flags=re.DOTALL)
    rows: list[list[str]] = []
    for line in body.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) >= 8 and cells[0].isdigit():
            rows.append(cells)
    return rows


def _next_trial_log_number() -> int:
    """Highest real row number in trial_log.md, +1."""
    rows = _trial_log_rows()
    return max(int(r[0]) for r in rows) + 1 if rows else 1


def _n_tried_before(rows: list[list[str]], strategy: str) -> int:
    """Distinct strategies attempted *before* this row (repo_review_20261027
    §2.1: the old `row_number - 1` was wrong whenever a strategy had more
    than one row)."""
    wanted = strategy.upper().replace("-", "")
    tried: set[str] = set()
    for r in rows:
        sid = r[2].upper().replace("-", "")
        if sid != wanted:
            tried.add(sid)
    return len(tried)


def write_trial_row(
    cells: list[dict],
    strategy: str,
    window: str,
    hypothesis: str,
    outcome: str = "<TBD>",
    cfg: dict | None = None,
) -> str:
    """Append one row to strategy/trial_log.md (T0 OOS discipline).

    The strategy ID is written *as registered* (e.g. ``S-01``), not upper-cased
    (repo_review_20261027 §2.1). ``outcome`` defaults to ``<TBD>`` when the
    run is recorded before the Gate 6/7 decision; pass the final outcome
    (``tested`` / ``parked`` / ``rejected``) when adjudicating.
    """
    # Primary reference cell: EUR_USD @ 2 bps in the requested window (else first cell).
    primary = next((c for c in cells
                    if c["instrument"] == "EUR_USD" and c["cost_bps"] == 2.0
                    and c["window"] == window), None)
    if primary is None:
        primary = cells[0]
        print(f"NOTE: no EUR_USD@2bps/{window} cell; using {primary['instrument']} "
              f"@ {primary['cost_bps']:g} bps / {primary['window']} for the trial row.")
    rows = _trial_log_rows()
    number = _next_trial_log_number()
    tried_before = _n_tried_before(rows, strategy)
    # Canonical strategy id (repo_review_20261027 §2.1): the old
    # ``strategy.upper()`` wrote ``S01`` while the registry/trial_log canon is
    # ``S-01``. Resolve the registered form when known.
    sid = _registered_id(cfg, strategy) if cfg is not None else strategy.upper()
    if sid is None:
        sid = strategy.upper()
    ret = (f"{primary['total_return_pct']:+.1f}% vs {primary['buyhold_return_pct']:+.1f}% "
           f"({primary['instrument']})")
    line = (f"| {number} | {date.today().isoformat()} | {sid} "
            f"| {hypothesis} | {window} | {outcome} | {ret} | {tried_before} |")
    with open(TRIAL_LOG, "a", encoding="utf-8") as fh:
        fh.write("\n" + line)
    return line


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--strategy", default="s01", choices=sorted(_STRATEGIES),
                    help="strategy id (registry in this file)")
    ap.add_argument("--instruments", nargs="+", default=INSTRUMENTS)
    ap.add_argument("--windows", nargs="+", default=["full", "last_12m"])
    ap.add_argument("--cost-tiers", nargs="+", type=float, default=COST_TIERS)
    ap.add_argument("--timeframe", default="5m", choices=["5m", "1h"])
    ap.add_argument("--out", default=None,
                    help="output dir for per-cell JSON + matrix.md + summary.csv "
                         "(default: strategy/results/<strategy>)")
    ap.add_argument("--entry-guard", action="store_true",
                    help="enable the B6 entry guard (no new entries on gap / near-close bars). "
                         "Off by default to match the documented S-01 baseline.")
    ap.add_argument("--trial-row", action="store_true",
                    help="append one row to strategy/trial_log.md after the run")
    ap.add_argument("--hypothesis", default="", help="one-line hypothesis for the trial row")
    ap.add_argument("--outcome", default="<TBD>",
                    help="trial row outcome: tested | parked | rejected (default <TBD> "
                         "= run recorded, Gate 6/7 decision still open)")
    ap.add_argument("--allow-partial", action="store_true",
                    help="summarise even when some cells fail (default: any failure "
                         "aborts with a non-zero exit code)")
    args = ap.parse_args()

    out_dir = Path(args.out) if args.out else (
        _REPO_ROOT / "strategy" / "results" / args.strategy.upper())
    cells = run_matrix(
        strategy=args.strategy,
        instruments=args.instruments,
        windows=args.windows,
        cost_tiers=args.cost_tiers,
        timeframe=args.timeframe,
        entry_guard=args.entry_guard,
        out_dir=out_dir,
        allow_partial=args.allow_partial,
    )
    md_path = out_dir / "matrix.md"
    csv_path = out_dir / "summary.csv"
    write_markdown(cells, md_path)
    write_csv(cells, csv_path)

    print(f"\n{len(cells)} cells → {out_dir}/  ({out_dir.name}.json per cell, matrix.md, summary.csv)")
    if args.trial_row:
        hypothesis = args.hypothesis or f"matrix run of {_STRATEGIES[args.strategy]['label']}"
        cfg = _load_config()
        line = write_trial_row(cells, args.strategy, args.windows[0], hypothesis,
                               outcome=args.outcome, cfg=cfg)
        print(f"Trial log row appended:\n{line}")


if __name__ == "__main__":
    main()
