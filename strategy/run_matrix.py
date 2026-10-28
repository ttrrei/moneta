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


_register_s01()


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


def _check_oos_once(strategy: str) -> None:
    """One-time OOS lock (repo_review_20261027 §1.1 step 3): if the trial log
    already records an `oos` window row for this strategy, re-running the
    holdout would be re-tuning on the OOS span — refuse.

    A row with outcome `<TBD>` does not count: that is the run *in progress*
    (this lock exists to stop a second run, which implies the first was
    already adjudicated).
    """
    if not TRIAL_LOG.exists():
        return
    body = re.sub(r"<!--.*?-->", "", TRIAL_LOG.read_text(), flags=re.DOTALL)
    wanted = strategy.upper().replace("-", "")
    for line in body.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 6 or not cells[0].isdigit():
            continue
        if (cells[2].replace("-", "") == wanted and cells[4] == "oos"
                and cells[5] != "<TBD>"):
            raise SystemExit(
                f"Strategy {strategy.upper()} already has an adjudicated `oos` row "
                f"in strategy/trial_log.md ({line.strip()}). Re-running the holdout "
                f"is prohibited — open a new strategy ID instead.")


def _cell_name(instrument: str, window: str, cost: float) -> str:
    return f"{instrument}__{window}__c{cost:g}"


def _data_fingerprint(parquet: str) -> dict:
    """Identity of the input data for a cell (repo_review_20261027 §2.2):
    path + mtime + row count, so a rerun after a data rebuild can be told
    apart from a rerun on identical data."""
    p = Path(parquet)
    st = p.stat()
    import duckdb
    conn = duckdb.connect()
    try:
        n = conn.execute("SELECT count(*) FROM read_parquet(?)", [str(p)]).fetchone()[0]
    finally:
        conn.close()
    return {"path": str(p), "mtime": st.st_mtime, "rows": int(n)}


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
    if "oos" in windows:
        _check_oos_once(strategy)

    parquet = {
        "5m": "data/ohlcv_5m_features/ohlcv_5m_features.parquet",
        "1h": "data/ohlcv_1h_features/ohlcv_1h_features.parquet",
    }[timeframe]

    out_dir.mkdir(parents=True, exist_ok=True)
    cells: list[dict] = []
    failures: list[tuple[str, str]] = []
    fingerprint = _data_fingerprint(parquet)

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
            "| Instrument | Cost (bps) | Ret % | Buy-hold % | Trades | Win % | MaxDD % | Sharpe | Exposure % |",
            "|---|---|---|---|---|---|---|---|---|",
        ]
        for c in cells:
            if c["window"] != window:
                continue
            lines.append(
                f"| {c['instrument']} | {c['cost_bps']:g} | {_fmt(c['total_return_pct'])} "
                f"| {_fmt(c['buyhold_return_pct'])} | {c['n_trades']} "
                f"| {c['win_rate_pct']:.1f} | {c['max_drawdown_pct']:.1f} "
                f"| {c['sharpe']:+.2f} | {c['exposure_pct']:.0f} |"
            )
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def write_csv(cells: list[dict], path: Path) -> None:
    fieldnames = [
        "strategy", "instrument", "window", "timeframe", "cost_bps", "entry_guard",
        "start", "end", "n_bars", "n_trades", "total_return_pct", "buyhold_return_pct",
        "max_drawdown_pct", "win_rate_pct", "avg_trade_return_pct", "sharpe",
        "exposure_pct", "span_years",
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
