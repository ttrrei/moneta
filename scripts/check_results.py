#!/usr/bin/env python3
"""check_results.py — verify that committed strategy results are *legal*.

Why this exists
---------------
The repo's own Gate G5 says every number in a report must trace back to a
matrix JSON block, and Gate G7 says a strategy is only "done" when the
registry row, the trial-log row, the matrix artifacts and the report all
agree. Until now those four were only *checked by a human reading them*, and
the 2026-10-28 review found a case where they did not agree:

    strategy/results/S01/summary.csv   full     2020-01-03 -> 2026-10-24
    strategy/results/S05/summary.csv   full     2020-01-03 -> 2025-07-31

`config/strategies.yml` declares `oos.holdout_start: 2025-08-01` and caps
both in-sample windows with `until: 2025-07-31`. The S-01 artifacts run
straight through the holdout (and its `last_12m` window sits *entirely*
inside it), while S-05/S-06 — produced by the same runner, hours later — are
correctly capped. Nothing caught it, because nothing looked.

This script is the machine that looks. It is deliberately *data-free*: it
reads only the committed CSV/Markdown artifacts plus the config, so it runs
in CI, in a bare container, on any machine — no parquet, no DuckDB, no
network, no TA-Lib.

What it checks
--------------
**Windows & OOS discipline**
  W1  every in-sample window declares an ``until`` cap
  W2  every in-sample window ends before ``oos.holdout_start``
  W3  every result row's [start, end] lies inside its declared window
  W4  no in-sample row reaches into the OOS holdout
  W5  a strategy has at most one adjudicated ``oos`` trial-log row

**Cross-artifact consistency**
  X1  results dir name == strategy id in the CSV == config registry key
  X2  the strategy is registered in ``config/strategies.yml``
  X3  the strategy has a row in ``STRATEGY_REGISTRY.md``
  X4  the strategy has a row in ``trial_log.md``
  X5  registry status agrees with the trial-log outcome
  X6  the registry's Code / Report links resolve to real files
  X7  the thin CLI (``strategy/code/<stem>.py``) exists
  X8  the strategy report (``strategy/docs/<stem>_report.md``) exists
  X9  the registry "Last run" date matches the trial-log date
  X10 the CSV timeframe matches the config registry

**Stop conditions (generated_strategy.md §5), machine-enforced**
  S1  trade count > 300  -> the status must be rejected / parked
  S2  loses to buy-hold at every cost tier on every cell -> rejected / parked
  S3  no instrument beats buy-hold at 2 bps -> rejected / parked

**Freshness**
  F1  if the feature parquet is present and is *newer* than the summary.csv,
      the committed results predate the current data build (stale)

Usage
-----
    python scripts/check_results.py                # human-readable report
    python scripts/check_results.py --json         # machine-readable
    python scripts/check_results.py --strict       # warnings become failures
    python scripts/check_results.py --root /path/to/moneta

Exit codes: 0 = no failures (warnings may exist); 1 = at least one failure.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Minimal YAML reader
# ---------------------------------------------------------------------------
# The checker must run where PyYAML is not installed (bare CI containers, a
# pre-commit hook, an agent sandbox). PyYAML is used when available; the
# fallback below understands exactly the subset of YAML that
# `config/strategies.yml` uses: nested mappings, scalar values, block
# scalars (`>` / `|`) and lists of strings. It is NOT a general YAML parser.


def _strip_inline_comment(v: str) -> str:
    """Remove a trailing YAML comment.

    A ``#`` only starts a comment when it is preceded by whitespace, and a
    ``#`` inside a quoted scalar is *not* a comment. Getting this wrong
    silently turns ``until: "2025-07-31"   # day before holdout`` into an
    unparseable string, which would quietly disable the window checks — so
    the rule is implemented explicitly rather than with a naive split.
    """
    v = v.strip()
    if not v:
        return v
    if v[0] in ("'", '"'):
        quote = v[0]
        i = 1
        while i < len(v):
            if v[i] == quote:
                rest = v[i + 1:].lstrip()
                if not rest or rest.startswith("#"):
                    return v[:i + 1]
                break
            i += 1
        return v
    m = re.search(r"\s#", v)
    if m:
        return v[:m.start()].strip()
    return v


def _scalar(raw: str):
    """Coerce a YAML scalar token to a Python value."""
    v = _strip_inline_comment(raw)
    if not v:
        return None
    if len(v) >= 2 and v[0] == v[-1] and v[0] in ("'", '"'):
        return v[1:-1]
    low = v.lower()
    if low in ("null", "~", "none"):
        return None
    if low == "true":
        return True
    if low == "false":
        return False
    if re.fullmatch(r"-?\d+", v):
        return int(v)
    if re.fullmatch(r"-?\d*\.\d+", v):
        return float(v)
    return v


def _mini_yaml(text: str) -> dict:
    """Parse the nested-mapping subset of YAML used by config/strategies.yml."""
    root: dict = {}
    stack: list[tuple[int, object]] = [(-1, root)]
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        raw = lines[i]
        i += 1
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip())
        line = raw.strip()

        if line.startswith("- "):
            container = stack[-1][1]
            if isinstance(container, dict):
                container.setdefault("__list__", []).append(_scalar(line[2:]))
            continue

        if ":" not in line:
            continue
        key, _, rest = line.partition(":")
        key = key.strip()
        rest = rest.strip()

        while stack and indent <= stack[-1][0]:
            stack.pop()
        parent = stack[-1][1] if stack else root
        if not isinstance(parent, dict):
            continue

        if rest in (">", "|", ">-", "|-"):
            block: list[str] = []
            while i < len(lines):
                nxt = lines[i]
                if nxt.strip() and (len(nxt) - len(nxt.lstrip())) <= indent:
                    break
                block.append(nxt.strip())
                i += 1
            parent[key] = " ".join(block)
            continue

        if rest == "":
            child: dict = {}
            parent[key] = child
            stack.append((indent, child))
        else:
            parent[key] = _scalar(rest)

    def _promote(node):
        if isinstance(node, dict):
            if "__list__" in node and len(node) == 1:
                return node["__list__"]
            return {k: _promote(v) for k, v in node.items()}
        return node

    return _promote(root)


def load_config(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    try:
        import yaml  # type: ignore
        data = yaml.safe_load(text)
    except ImportError:
        data = _mini_yaml(text)
    if not isinstance(data, dict):
        raise SystemExit(f"{path} did not parse into a mapping")
    _validate_config(data, path)
    return data


def _validate_config(cfg: dict, path: Path) -> None:
    """Fail loudly if the config did not parse into the shape we depend on.

    A parse quirk must never *silently* disable a check: if ``windows.full.until``
    comes back as an unparseable string, the window checks would quietly pass
    everything. So the shape is asserted up front and the tool refuses to run
    rather than running with blind spots.
    """
    problems: list[str] = []

    windows = cfg.get("windows")
    if not isinstance(windows, dict) or not windows:
        problems.append("no `windows:` mapping")
    else:
        for name, spec in windows.items():
            if not isinstance(spec, dict):
                problems.append(f"windows.{name} is not a mapping")
                continue
            if name == "oos":
                continue
            until = spec.get("until")
            if until is None:
                problems.append(f"windows.{name}.until is missing (in-sample window must be capped)")
            elif as_date(until) is None:
                problems.append(f"windows.{name}.until = {until!r} is not a parseable date")
            since = spec.get("since")
            if since is not None and as_date(since) is None:
                problems.append(f"windows.{name}.since = {since!r} is not a parseable date")

    oos = cfg.get("oos")
    if not isinstance(oos, dict):
        problems.append("no `oos:` mapping")
    else:
        hs = oos.get("holdout_start")
        if hs is None:
            problems.append("oos.holdout_start is missing")
        elif as_date(hs) is None:
            problems.append(f"oos.holdout_start = {hs!r} is not a parseable date")

    if problems:
        raise SystemExit(
            f"{path} did not parse into the expected shape — refusing to run with "
            "blind spots:\n  - " + "\n  - ".join(problems))


# ---------------------------------------------------------------------------
# Findings
# ---------------------------------------------------------------------------

@dataclass
class Finding:
    level: str          # FAIL | WARN | OK
    code: str
    where: str
    message: str

    def as_dict(self) -> dict:
        return {"level": self.level, "code": self.code,
                "where": self.where, "message": self.message}


@dataclass
class Report:
    findings: list[Finding] = field(default_factory=list)

    def add(self, level: str, code: str, where: str, message: str) -> None:
        self.findings.append(Finding(level, code, where, message))

    def fail(self, code: str, where: str, message: str) -> None:
        self.add("FAIL", code, where, message)

    def warn(self, code: str, where: str, message: str) -> None:
        self.add("WARN", code, where, message)

    def note(self, code: str, where: str, message: str) -> None:
        self.add("OK", code, where, message)

    @property
    def failures(self) -> list[Finding]:
        return [f for f in self.findings if f.level == "FAIL"]

    @property
    def warnings(self) -> list[Finding]:
        return [f for f in self.findings if f.level == "WARN"]


def norm_id(s: str) -> str:
    """Canonical comparison key for a strategy id: S-01 / s01 / S01 -> S01."""
    return (s or "").strip().upper().replace("-", "").replace("_", "")


# ---------------------------------------------------------------------------
# Artifact parsers
# ---------------------------------------------------------------------------

BOLD = re.compile(r"\*\*(.+?)\*\*")


def strip_md(s: str) -> str:
    return BOLD.sub(r"\1", s).strip()


def parse_registry(path: Path) -> dict[str, dict]:
    """Parse the strategy table of STRATEGY_REGISTRY.md -> {id: {col: value}}."""
    rows: dict[str, dict] = {}
    if not path.exists():
        return rows
    header: list[str] | None = None
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s.startswith("|"):
            continue
        cells = [strip_md(c) for c in s.strip("|").split("|")]
        if not cells:
            continue
        first = cells[0]
        if header is None and first.lower() == "id":
            header = [c.lower() for c in cells]
            continue
        if header is None or not re.fullmatch(r"S-\d+", first):
            continue
        rec = {header[i]: cells[i] for i in range(min(len(header), len(cells)))}
        rows[first] = rec
    return rows


def parse_trial_log(path: Path) -> list[dict]:
    """Parse trial_log.md data rows (HTML-comment examples excluded)."""
    out: list[dict] = []
    if not path.exists():
        return out
    body = re.sub(r"<!--.*?-->", "", path.read_text(encoding="utf-8"), flags=re.DOTALL)
    for line in body.splitlines():
        s = line.strip()
        if not s.startswith("|"):
            continue
        cells = [strip_md(c) for c in s.strip("|").split("|")]
        if len(cells) < 8 or not cells[0].isdigit():
            continue
        out.append({
            "n": int(cells[0]),
            "date": cells[1],
            "strategy_id": cells[2],
            "hypothesis": cells[3],
            "window": cells[4],
            "outcome": cells[5],
            "result": cells[6],
            "n_tried_before": cells[7],
        })
    return out


def parse_dt(s: str) -> datetime | None:
    s = (s or "").strip()
    if not s:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S%z", "%Y-%m-%dT%H:%M:%S%z",
                "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        return None


def as_date(s) -> date | None:
    d = parse_dt(str(s or ""))
    return d.date() if d else None


def link_target(cell: str) -> str | None:
    """Extract the target of the first markdown link in a table cell."""
    m = re.search(r"\]\(([^)]+)\)", cell or "")
    return m.group(1) if m else None


def _f(row: dict, key: str) -> float | None:
    try:
        return float(row.get(key))
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# G5: numbers quoted in prose must exist in the matrix
# ---------------------------------------------------------------------------

#: A quoted result number is either written as a percentage (unambiguous) or is
#: an integer >= 100 (metric-sized). Smaller bare integers are prose counts
#: ("all 3 instruments"), cost tiers ("2 bps") or parameter pairs ("60/3") and
#: are deliberately not checked.
_MIN_BARE_INT = 100


def _extract_quoted_numbers(text: str) -> list[tuple[float, int, bool]]:
    """Pull result-shaped numbers out of a prose cell.

    Returns ``(value, decimals, is_percentage)`` triples. Non-result number
    shapes are stripped first: strategy ids, cost-tier references (``c2``),
    parameter pairs (``60/3``), dates, basis points and approximations
    (``~1,900``).
    """
    t = (text or "").replace("\u2212", "-")   # unicode minus -> ASCII
    t = re.sub(r"S-\d+", " ", t)             # strategy ids
    t = re.sub(r"\bc\d+\b", " ", t)          # cost-tier refs (c0, c2, c5)
    t = re.sub(r"\b\d{1,3}/\d{1,3}\b", " ", t)   # parameter pairs (60/3, 120/3)
    t = re.sub(r"\b\d{4}-\d{2}-\d{2}\b", " ", t)  # dates
    t = re.sub(r"\d+\s*bps", " ", t)         # cost tiers in bps
    t = re.sub(r"[~\u2248><]\s*[+-]?\d[\d,]*(?:\.\d+)?", " ", t)  # approximations

    out: list[tuple[float, int, bool]] = []
    for m in re.finditer(r"([+-]?\d[\d,]*(?:\.\d+)?)(\s*%)?", t):
        raw = m.group(1).replace(",", "")
        try:
            val = float(raw)
        except ValueError:
            continue
        dec = len(raw.split(".")[1]) if "." in raw else 0
        is_pct = bool(m.group(2))
        if not is_pct and abs(val) < _MIN_BARE_INT:
            continue
        out.append((val, dec, is_pct))
    return out


def _matches_known(value: float, decimals: int, known: list[float]) -> bool:
    """Does `known` contain a value that rounds to `value` at `decimals`?"""
    tol = 0.6 * (10 ** -decimals)
    return any(abs(v - value) <= tol for v in known)


def _known_values(rows: list[dict]) -> list[float]:
    vals: list[float] = []
    for r in rows:
        for k in r:
            f = _f(r, k)
            if f is not None:
                vals.append(f)
    return vals


# ---------------------------------------------------------------------------
# Window / OOS discipline
# ---------------------------------------------------------------------------

def check_windows(cfg: dict, rep: Report, where: str) -> None:
    """W1 / W2 — the config's own window discipline."""
    windows = cfg.get("windows") or {}
    oos = cfg.get("oos") or {}
    holdout_start = oos.get("holdout_start")
    if not holdout_start:
        rep.fail("W2", where, "config has no oos.holdout_start — OOS discipline is undefined")
        return
    hs = as_date(holdout_start)
    for name, spec in windows.items():
        if not isinstance(spec, dict) or name == "oos":
            continue
        until = spec.get("until")
        if until is None:
            rep.fail("W1", f"config windows.{name}",
                     "in-sample window has no `until` cap — it can run into the OOS holdout")
            continue
        u = as_date(until)
        if u and hs and u >= hs:
            rep.fail("W2", f"config windows.{name}",
                     f"until={until} is not before oos.holdout_start={holdout_start}")


# ---------------------------------------------------------------------------
# Per-results-directory checks
# ---------------------------------------------------------------------------

@dataclass
class Cell:
    window: str
    instrument: str
    cost_bps: float | None
    total_return_pct: float | None
    buyhold_return_pct: float | None
    n_trades: int
    start: str
    end: str


@dataclass
class StrategyResults:
    dir_name: str
    ids: set[str]
    rows: list[dict]
    cells: list[Cell]
    max_trades: int
    # stop-condition evidence
    loses_everywhere: bool          # S2
    instruments_beating_bh: set[str]  # S3
    windows_beating_bh: set[str]      # S3
    csv_mtime: float
    csv_path: Path


def collect_results(results_dir: Path, cfg: dict, rep: Report, root: Path) -> StrategyResults | None:
    """Read one results directory and check it against the configured windows."""
    csv_path = results_dir / "summary.csv"
    rel = str(csv_path.relative_to(root))
    if not csv_path.exists():
        rep.warn("F1", str(results_dir.relative_to(root)),
                 "no summary.csv in this results directory (per-cell JSON only)")
        return None

    with open(csv_path, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    if not rows:
        rep.fail("F1", rel, "summary.csv has no data rows")
        return None

    windows = cfg.get("windows") or {}
    oos = cfg.get("oos") or {}
    holdout_start = as_date(oos.get("holdout_start") or "")
    registered = cfg.get("strategies") or {}

    # ---- identity ---------------------------------------------------------
    raw_ids = {r.get("strategy", "").strip() for r in rows if (r.get("strategy") or "").strip()}
    norm_ids = {norm_id(i) for i in raw_ids}
    dir_id = results_dir.name
    if len(norm_ids) != 1:
        rep.fail("X1", rel,
                 f"summary.csv mixes strategy ids {sorted(raw_ids)} — one directory, one strategy")
        return None
    if norm_id(dir_id) != next(iter(norm_ids)):
        rep.fail("X1", rel,
                 f"results dir {dir_id!r} does not match strategy id {sorted(raw_ids)[0]!r}")

    # ---- X2: registered in config/strategies.yml -------------------------
    reg_key = None
    for k in registered:
        if norm_id(k) == next(iter(norm_ids)):
            reg_key = k
            break
    if reg_key is None:
        rep.fail("X2", rel,
                 f"{sorted(raw_ids)[0]} has results but is not registered in config/strategies.yml")

    # ---- X10: timeframe agrees with the config ---------------------------
    reg_tf = (registered.get(reg_key) or {}).get("timeframe") if reg_key else None
    csv_tf = {r.get("timeframe") for r in rows if r.get("timeframe")}
    if reg_tf and csv_tf and csv_tf != {reg_tf}:
        rep.fail("X10", rel,
                 f"timeframe in results {sorted(csv_tf)} != config registry {reg_tf!r}")

    # ---- per-row window checks (aggregated per window) -------------------
    issues: dict[tuple[str, str], list[str]] = {}
    seen: dict[tuple[str, str], tuple] = {}
    cells: list[Cell] = []
    max_trades = 0

    def issue(code: str, window: str, msg: str) -> None:
        issues.setdefault((code, window), []).append(msg)

    for r in rows:
        window = (r.get("window") or "").strip()
        inst = (r.get("instrument") or "").strip()
        cost = _f(r, "cost_bps")
        spec = windows.get(window)
        if spec is None:
            issue("W3", window or "?", f"{inst}@{cost}bps: window {window!r} is not declared "
                                       f"in config/strategies.yml")
            continue
        if not isinstance(spec, dict):
            continue
        since = spec.get("since")
        until = spec.get("until")
        start = parse_dt(r.get("start", ""))
        end = parse_dt(r.get("end", ""))
        if start is None or end is None:
            issue("W3", window, f"{inst}@{cost}bps: cannot parse start/end "
                                f"({r.get('start')!r} -> {r.get('end')!r})")
            continue
        if end < start:
            issue("W3", window, f"{inst}@{cost}bps: end {end.isoformat()} is before "
                                f"start {start.isoformat()}")

        if since:
            sd = as_date(since)
            if sd and start.date() < sd:
                issue("W3", window,
                      f"{inst}@{cost}bps: start {start.date()} is before the window's "
                      f"since={sd} — the window filter did not apply")
        if until:
            ud = as_date(until)
            if ud and end.date() > ud:
                over = (end.date() - ud).days
                issue("W3", window,
                      f"{inst}@{cost}bps: end {end.date()} is past the window's "
                      f"until={ud} (+{over}d) — the window cap did not apply")
        elif window != "oos":
            issue("W1", window, f"{inst}@{cost}bps: window {window!r} has no until cap "
                                f"but is not `oos`")

        if window != "oos" and holdout_start and end.date() >= holdout_start:
            issue("W4", window,
                  f"{inst}@{cost}bps: end {end.date()} reaches into the OOS holdout "
                  f"(holdout_start={holdout_start}) — this run has seen OOS data")

        k = (window, inst)
        span = (r.get("start"), r.get("end"), r.get("n_bars"))
        if k in seen:
            if seen[k] != span:
                issue("X1", window,
                      f"{inst}: same window/instrument has inconsistent spans across "
                      f"cost tiers: {seen[k]} vs {span}")
        else:
            seen[k] = span

        n_trades = int(_f(r, "n_trades") or 0)
        max_trades = max(max_trades, n_trades)
        cells.append(Cell(
            window=window, instrument=inst, cost_bps=cost,
            total_return_pct=_f(r, "total_return_pct"),
            buyhold_return_pct=_f(r, "buyhold_return_pct"),
            n_trades=n_trades,
            start=r.get("start", ""), end=r.get("end", ""),
        ))

    for (code, window), msgs in sorted(issues.items()):
        head = msgs[0]
        extra = "" if len(msgs) == 1 else f"  (+{len(msgs) - 1} more cell(s) with the same problem)"
        rep.fail(code, f"{rel} [{window}]", head + extra)

    # ---- stop-condition evidence ----------------------------------------
    loses_everywhere = bool(cells) and all(
        c.total_return_pct is not None and c.buyhold_return_pct is not None
        and c.total_return_pct <= c.buyhold_return_pct for c in cells)
    inst_beating: set[str] = set()
    win_beating: set[str] = set()
    for c in cells:
        if (c.cost_bps == 2.0 and c.total_return_pct is not None
                and c.buyhold_return_pct is not None
                and c.total_return_pct > c.buyhold_return_pct):
            inst_beating.add(c.instrument)
            win_beating.add(c.window)

    return StrategyResults(
        dir_name=dir_name_of(results_dir), ids=raw_ids, rows=rows, cells=cells,
        max_trades=max_trades, loses_everywhere=loses_everywhere,
        instruments_beating_bh=inst_beating, windows_beating_bh=win_beating,
        csv_mtime=csv_path.stat().st_mtime, csv_path=csv_path,
    )


def dir_name_of(p: Path) -> str:
    return p.name


def check_freshness(res: StrategyResults, root: Path, rep: Report) -> None:
    """F1 — the committed results must not predate the current data build."""
    rel = str(res.csv_path.relative_to(root))
    for tf, fname in (("5m", "ohlcv_5m_features"), ("1h", "ohlcv_1h_features")):
        parquet = root / "data" / fname / f"{fname}.parquet"
        if parquet.exists() and parquet.stat().st_mtime > res.csv_mtime:
            rep.warn("F1", rel,
                     f"the {tf} feature parquet is newer than these results — the committed "
                     "numbers predate the current data build (stale)")


# ---------------------------------------------------------------------------
# Cross-artifact checks
# ---------------------------------------------------------------------------

def check_cross_artifacts(root: Path, cfg: dict, registry: dict, trials: list[dict],
                          results: list[StrategyResults], rep: Report) -> None:
    """X3-X9 and S1-S3 — registry / trial log / report / CLI consistency."""
    strategies_dir = root / "strategy"
    reg_by_norm = {norm_id(k): (k, v) for k, v in registry.items()}
    trials_by_norm: dict[str, list[dict]] = {}
    for t in trials:
        trials_by_norm.setdefault(norm_id(t["strategy_id"]), []).append(t)

    for res in results:
        key = norm_id(next(iter(res.ids)))
        sid = next(iter(res.ids))

        # ---- X3: registry row -------------------------------------------
        if key not in reg_by_norm:
            rep.fail("X3", f"registry {sid}",
                     f"{sid} has results but no row in STRATEGY_REGISTRY.md")
            continue
        canon_id, reg = reg_by_norm[key]

        # ---- X4: trial log row ------------------------------------------
        trows = trials_by_norm.get(key, [])
        if not trows:
            rep.fail("X4", f"trial_log {sid}",
                     f"{sid} has results but no row in strategy/trial_log.md")

        # ---- X5: status vs outcome --------------------------------------
        status = (reg.get("status") or "").strip().lower().replace("*", "")
        if status and trows:
            norm_out = {t["outcome"].lower().replace(" ", "").replace("-", "")
                        for t in trows}
            norm_status = status.replace(" ", "").replace("-", "")
            if norm_status in {"rejected", "parked", "tested"} and norm_status not in norm_out:
                rep.fail("X5", f"registry {canon_id}",
                         f"registry status {status!r} disagrees with the trial-log outcome(s) "
                         f"{sorted({t['outcome'] for t in trows})}")

        # ---- W5: at most one adjudicated OOS row ------------------------
        adjudicated = [t for t in trows if t["window"] == "oos" and t["outcome"] != "<TBD>"]
        if len(adjudicated) > 1:
            rep.fail("W5", f"trial_log {canon_id}",
                     f"{canon_id} has {len(adjudicated)} adjudicated `oos` rows — the holdout "
                     "may be evaluated exactly once per strategy")

        # ---- X9: "Last run" date vs the trial-log date -------------------
        last_run = (reg.get("last run") or "").strip()
        if last_run and trows:
            tdates = {t["date"] for t in trows}
            if last_run not in tdates:
                rep.warn("X9", f"registry {canon_id}",
                         f"registry 'Last run' = {last_run!r} matches no trial-log date "
                         f"({sorted(tdates)})")

        # ---- X6 / X7 / X8: code link, thin CLI, report -------------------
        target = link_target(reg.get("code") or "")
        if not target:
            rep.fail("X6", f"registry {canon_id}",
                     "registry row has no Code link — a strategy with results must link its code")
        else:
            if not (strategies_dir / target).exists():
                rep.fail("X6", f"registry {canon_id}",
                         f"Code link {target!r} does not exist")
            else:
                stem = Path(target).stem
                if stem.endswith("_lib"):
                    stem = stem[:-4]
                if not (strategies_dir / "code" / f"{stem}.py").exists():
                    rep.fail("X7", f"registry {canon_id}",
                             f"no thin CLI at strategy/code/{stem}.py "
                             "(WORKFLOW Step 3 requires one)")
                if not (strategies_dir / "docs" / f"{stem}_report.md").exists():
                    rep.fail("X8", f"registry {canon_id}",
                             f"no strategy report at strategy/docs/{stem}_report.md "
                             "(WORKFLOW Step 5 / Gate G7)")

        rtarget = link_target(reg.get("report") or "")
        if rtarget:
            if not (strategies_dir / rtarget).exists():
                rep.fail("X6", f"registry {canon_id}",
                         f"Report link {rtarget!r} does not exist")
            elif rtarget.startswith("results"):
                rep.warn("X8", f"registry {canon_id}",
                         f"the Report column points at {rtarget!r} — a matrix is data, "
                         "not a report (WORKFLOW Step 5)")

        # ---- G5: every number quoted in the Result cell must exist ------
        result_cell = reg.get("result (ret vs bh)") or reg.get("result") or ""
        known = _known_values(res.rows)
        for value, dec, is_pct in _extract_quoted_numbers(result_cell):
            if _matches_known(value, dec, known):
                continue
            if is_pct:
                rep.fail("G5", f"registry {canon_id}",
                         f"the Result cell quotes {value:+g} (or {value:g}%) which does not "
                         "appear in strategy/results — every number must trace to a matrix cell")
            else:
                rep.warn("G5", f"registry {canon_id}",
                         f"the Result cell quotes {value:g} which does not appear in "
                         "strategy/results — check it traces to a matrix cell")

        # ---- the "beats buy-hold" claim must agree with the matrix -------
        cell_text = result_cell
        negative_claim = re.search(r"never\s+beat|not\s+beat|no\s+\w+\s+beats?\s+buy", cell_text, re.I)
        if re.search(r"\bbeat", cell_text, re.I) and not negative_claim:
            at2 = [c for c in res.cells if c.cost_bps == 2.0]
            beat2 = [c for c in at2
                     if c.total_return_pct is not None and c.buyhold_return_pct is not None
                     and c.total_return_pct > c.buyhold_return_pct]
            beat_any = [c for c in res.cells
                        if c.total_return_pct is not None and c.buyhold_return_pct is not None
                        and c.total_return_pct > c.buyhold_return_pct]
            if at2 and not beat2:
                above = ", ".join(
                    f"{c.instrument}/{c.window}/c{c.cost_bps:g}" for c in beat_any) or "none"
                rep.fail("X11", f"registry {canon_id}",
                         "the Result cell claims the strategy beats buy-hold, but at the "
                         f"reference cost tier (2 bps) it is above buy-hold in 0 of "
                         f"{len(at2)} cells (0/{len({c.instrument for c in at2})} instruments, "
                         f"0/{len({c.window for c in at2})} windows); the only cell(s) above "
                         f"buy-hold at any tier: {above}")
            elif beat2:
                rep.warn("X11", f"registry {canon_id}",
                         f"the Result cell claims a buy-hold win; at 2 bps the strategy is "
                         f"above buy-hold in {len(beat2)} of {len(at2)} cells "
                         f"({len({c.instrument for c in beat2})}/"
                         f"{len({c.instrument for c in at2})} instruments, "
                         f"{len({c.window for c in beat2})}/"
                         f"{len({c.window for c in at2})} windows)")

        # ---- S1 / S2 / S3: stop conditions vs the recorded status -------
        terminal = status in {"rejected", "parked"}
        if res.max_trades > 300:
            if terminal:
                rep.note("S1", f"registry {canon_id}",
                         f"max trade count {res.max_trades} > 300 and the status is {status!r} "
                         "— the §5 stop condition is correctly reflected")
            else:
                rep.fail("S1", f"registry {canon_id}",
                         f"max trade count {res.max_trades} exceeds the 300-trade budget "
                         f"(generated_strategy.md §5) but the status is {status!r} — it must be "
                         "rejected or parked")
        if res.loses_everywhere:
            if terminal:
                rep.note("S2", f"registry {canon_id}",
                         "loses to buy-hold in every cell and the status is "
                         f"{status!r} — the §5 stop condition is correctly reflected")
            else:
                rep.fail("S2", f"registry {canon_id}",
                         "loses to buy-hold in every cell (every cost tier, every instrument, "
                         f"every window) but the status is {status!r} — it must be rejected "
                         "or parked")
        if res.cells and not res.instruments_beating_bh:
            if terminal:
                rep.note("S3", f"registry {canon_id}",
                         f"no instrument beats buy-hold at 2 bps and the status is {status!r} "
                         "— the §5 stop condition is correctly reflected")
            else:
                rep.fail("S3", f"registry {canon_id}",
                         "no instrument beats buy-hold at 2 bps (generated_strategy.md §5: "
                         f"'edge appears on < 1 of 3 instruments') but the status is {status!r} "
                         "— it must be rejected or parked")

    # ---- X2 (other direction): config registry -> registry table --------
    for k in (cfg.get("strategies") or {}):
        if norm_id(k) not in reg_by_norm:
            rep.fail("X3", f"config strategies.{k}",
                     f"{k} is in config/strategies.yml but has no STRATEGY_REGISTRY.md row")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def run(root: Path) -> Report:
    rep = Report()
    cfg_path = root / "config" / "strategies.yml"
    if not cfg_path.exists():
        raise SystemExit(f"config not found: {cfg_path}")
    cfg = load_config(cfg_path)

    registry = parse_registry(root / "strategy" / "STRATEGY_REGISTRY.md")
    trials = parse_trial_log(root / "strategy" / "trial_log.md")

    check_windows(cfg, rep, "config/strategies.yml")

    results: list[StrategyResults] = []
    results_root = root / "strategy" / "results"
    if results_root.exists():
        for results_dir in sorted(p for p in results_root.glob("*") if p.is_dir()):
            res = collect_results(results_dir, cfg, rep, root)
            if res is not None:
                results.append(res)
                check_freshness(res, root, rep)
    else:
        rep.warn("F1", "strategy/results", "no results directory — nothing to check")

    check_cross_artifacts(root, cfg, registry, trials, results, rep)
    return rep


def print_human(rep: Report, strict: bool) -> None:
    order = {"FAIL": 0, "WARN": 1, "OK": 2}
    for f in sorted(rep.findings, key=lambda x: (order.get(x.level, 3), x.code, x.where)):
        if f.level == "OK":
            continue
        print(f"[{f.level}] {f.code:<4} {f.where}")
        print(f"        {f.message}")
    print()
    for f in sorted((x for x in rep.findings if x.level == "OK"), key=lambda x: (x.code, x.where)):
        print(f"[ OK ] {f.code:<4} {f.where}")
        print(f"        {f.message}")
    print()
    n_ok = sum(1 for f in rep.findings if f.level == "OK")
    print(f"{len(rep.failures)} failure(s), {len(rep.warnings)} warning(s), {n_ok} note(s)")
    if rep.failures:
        print("RESULT: FAIL — the committed results are not legal.")
    elif strict and rep.warnings:
        print("RESULT: FAIL (--strict: warnings treated as failures).")
    else:
        print("RESULT: PASS — committed results are consistent with the config.")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=None,
                    help="repo root (default: the parent of this script's directory)")
    ap.add_argument("--json", action="store_true", help="emit JSON instead of a text report")
    ap.add_argument("--strict", action="store_true", help="treat warnings as failures")
    args = ap.parse_args()

    root = Path(args.root).resolve() if args.root else Path(__file__).resolve().parents[1]
    rep = run(root)

    if args.json:
        print(json.dumps({
            "root": str(root),
            "failures": len(rep.failures),
            "warnings": len(rep.warnings),
            "findings": [f.as_dict() for f in rep.findings],
        }, indent=2, default=str))
    else:
        print_human(rep, args.strict)

    if rep.failures:
        return 1
    if args.strict and rep.warnings:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
