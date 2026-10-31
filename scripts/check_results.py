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
  X11 the registry's buy-hold claim agrees with the matrix (no false "beats BH")
  X12 the trial-log row's stated timeframe matches the config registry
  X14 a registered strategy has no committed evidence (no results dir and no
      sweep-CSV row), or a sweep CSV has no rows / is missing columns / has
      failed cells (review follow-up #3 §C5)
  X15 registry saturation: the same (base indicator, timeframe) family already
      holds too many strategies — WARN at >= 4 members, FAIL at >= 8
      (review follow-up #3 §B.3). A strategy "belongs" to a family if any of
      its backticked key indicators reduce to that base name (window suffix
      stripped: willr_60 -> willr, macd_hist_6_24 -> macd_hist).

**Stop conditions (generated_strategy.md §5), machine-enforced**
  S1  trade count > 300  -> the status must be rejected / parked
  S2  loses to buy-hold at every cost tier on every cell -> rejected / parked
  S3  no instrument beats buy-hold at 2 bps -> rejected / parked

**Freshness**
  F1  if the feature parquet is present and is *newer* than the summary.csv,
      the committed results predate the current data build (stale)

**OOS holdout ledger (append-only + cross-consistency, follow-up review)**
  L0  ``windows.oos.until`` equals ``oos.holdout_end`` + 1 day (single source
      of truth for the holdout's end; the loader is inclusive of ``until``, so
      the last fully-closed day is ``holdout_end``)
  L1  the committed ``oos_ledger.json`` is a **superset** of the base ledger
      (``--base-ledger``) — a holdout record may never be *removed*; the ledger
      must only ever grow (CI: pass the base branch's ledger)
  L2  the ledger and ``trial_log.md`` agree: every adjudicated ``oos`` trial
      row has a ledger consumption record, and every ``completed`` ledger
      record has an adjudicated ``oos`` trial row

Usage
-----
    python scripts/check_results.py                # human-readable report
    python scripts/check_results.py --json         # machine-readable
    python scripts/check_results.py --strict       # warnings become failures
    python scripts/check_results.py --root /path/to/moneta
    python scripts/check_results.py --base-ledger /path/to/base/oos_ledger.json

Exit codes: 0 = no failures (warnings may exist); 1 = at least one failure.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path

# ---------------------------------------------------------------------------
# Shared contract (strategy/schema.py) — the summary.csv field list and the
# OOS pass/fail formula, so the checker and the runner cannot drift apart
# (repo_review_20261029 §2.4 X13 / §3.2 / §3.3). schema.py is stdlib-only, so
# importing it keeps this script data-free.
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
import strategy.schema as schema  # noqa: E402

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
    is_oos: bool = False            # a distinct `<ID>_oos` holdout directory


def collect_results(results_dir: Path, cfg: dict, rep: Report, root: Path) -> StrategyResults | None:
    """Read one results directory and check it against the configured windows."""
    csv_path = results_dir / "summary.csv"
    rel = str(csv_path.relative_to(root))
    if not csv_path.exists():
        rep.warn("F1", str(results_dir.relative_to(root)),
                 "no summary.csv in this results directory (per-cell JSON only)")
        return None

    with open(csv_path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)
    if not rows:
        rep.fail("F1", rel, "summary.csv has no data rows")
        return None

    # Whether this directory is an OOS holdout matrix (a distinct `<ID>_oos`
    # dir, see the X1 identity check) — the X13 check re-computes pass/fail for
    # it.
    is_oos = results_dir.name.lower().endswith("_oos")

    # ---- H1 (§3.3): the committed header must equal the shared field list --
    # The single source is strategy/schema.py; the runner (write_csv) writes
    # exactly this. This is the check that would have caught S01/S05/S06 being
    # committed on the old schema (missing sharpe_weekly / trades_per_year /
    # mean_net_position_pct) — CI never caught it because there was no rule.
    expected = schema.OOS_HEADER if is_oos else schema.SUMMARY_FIELDS
    if fieldnames != expected:
        missing = [f for f in expected if f not in fieldnames]
        extra = [f for f in fieldnames if f not in expected]
        parts = []
        if missing:
            parts.append(f"missing {missing}")
        if extra:
            parts.append(f"unexpected {extra}")
        rep.fail("H1", rel,
                 f"summary.csv header must equal the shared field list from "
                 f"strategy/schema.py ({' and '.join(parts) or 'column order differs'}); "
                 f"regenerate with run_matrix.py so the committed schema is current")

    windows = cfg.get("windows") or {}
    oos = cfg.get("oos") or {}
    holdout_start = as_date(oos.get("holdout_start") or "")
    registered = cfg.get("strategies") or {}

    # ---- identity ---------------------------------------------------------
    raw_ids = {r.get("strategy", "").strip() for r in rows if (r.get("strategy") or "").strip()}
    norm_ids = {norm_id(i) for i in raw_ids}
    dir_id = results_dir.name
    # An OOS holdout matrix is written to a distinct ``<ID>_oos`` directory so
    # it can never overwrite the in-sample results (run_matrix). A valid OOS
    # dir must still pass X1 (its name == the strategy id, modulo the suffix);
    # a mislabelled one must fail.
    is_oos_dir = dir_id.lower().endswith("_oos")
    dir_base = dir_id[:-4] if is_oos_dir else dir_id
    if len(norm_ids) != 1:
        rep.fail("X1", rel,
                 f"summary.csv mixes strategy ids {sorted(raw_ids)} — one directory, one strategy")
        return None
    if norm_id(dir_base) != next(iter(norm_ids)):
        rep.fail("X1", rel,
                 f"results dir {dir_id!r} does not match strategy id {sorted(raw_ids)[0]!r}"
                 + ("" if not is_oos_dir else " (an OOS dir must be `<ID>_oos` for that id)"))

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
        is_oos=is_oos,
        csv_mtime=csv_path.stat().st_mtime, csv_path=csv_path,
    )


def dir_name_of(p: Path) -> str:
    return p.name


# ---------------------------------------------------------------------------
# Sweep-CSV evidence (review follow-up #3 §C5)
# ---------------------------------------------------------------------------
# S-08 … S-27 (except the one with a committed results directory) have their
# evidence only in the sweep CSVs (`strategy/results/iterations_*.csv`), so the
# per-strategy results-directory checks (S1–S3 / X1 …) never evaluate them.
# This reads those CSVs and (a) verifies their schema and that no cell failed,
# (b) verifies every registered strategy that has NO results directory has at
# least one committed row, and (c) evaluates S1–S3 from the `full`-window rows.
#
#: Required columns in a sweep CSV (the columns this checker needs to verify).
SWEEP_REQUIRED = [
    "strategy", "variant", "instrument", "window", "cost_bps",
    "n_trades", "total_return_pct", "buyhold_return_pct", "error",
]


def load_sweep_csvs(results_root: Path) -> list[tuple[Path, list[dict]]]:
    """The committed `iterations_*.csv` sweep files as (path, rows) pairs."""
    out: list[tuple[Path, list[dict]]] = []
    if not results_root.exists():
        return out
    for p in sorted(results_root.glob("iterations_*.csv")):
        with open(p, newline="", encoding="utf-8") as fh:
            out.append((p, list(csv.DictReader(fh))))
    return out


def check_sweep_evidence(root: Path, cfg: dict, registry: dict,
                         results: list[StrategyResults], rep: Report) -> None:
    """C5 — validate the sweep CSVs and evaluate S1–S3 for strategies that have
    no results directory (see module docstring above).

    New check codes:
      X14 a registered strategy has NO committed evidence at all (no
          `strategy/results/<ID>/` and no row in any sweep CSV) — a sweep-era
          strategy cannot be `rejected`/`finalist` without committed evidence.
    """
    results_root = root / "strategy" / "results"
    sweeps = load_sweep_csvs(results_root)

    # Which strategies have a committed results directory (they are covered by
    # collect_results / the X checks); the rest must be covered by the sweeps.
    with_dir = {norm_id(next(iter(r.ids))) for r in results if r.ids}

    # ---- (a) schema + no failures + (b) every dir-less registered strategy
    #         has committed rows ---------------------------------------------
    by_sid: dict[str, list[dict]] = {}
    for path, rows in sweeps:
        if not rows:
            rep.fail("X14", str(path.relative_to(root)),
                     "sweep CSV has no data rows — a sweep that produced no "
                     "committed cells is not evidence")
            continue
        missing = [c for c in SWEEP_REQUIRED if c not in rows[0]]
        if missing:
            rep.fail("X14", str(path.relative_to(root)),
                     f"sweep CSV is missing required column(s) {missing}")
            continue
        errs = [r for r in rows if (r.get("error") or "").strip()]
        if errs:
            ex = errs[0]
            rep.fail("X14", str(path.relative_to(root)),
                     f"{len(errs)} sweep cell(s) recorded an error "
                     f"(e.g. {ex.get('strategy')}/{ex.get('variant')}: "
                     f"{(ex.get('error') or '')[:60]!r}) — the sweep did not "
                     f"complete cleanly and is not valid evidence")
        for r in rows:
            sid = norm_id(r.get("strategy", ""))
            if sid:
                by_sid.setdefault(sid, []).append(r)

    def _num(sid: str) -> int:
        m = re.search(r"(\d+)$", (sid or ""))
        return int(m.group(1)) if m else 0

    registered = list((cfg.get("strategies") or {}).keys())
    reg_by_norm = {norm_id(k): k for k in registered}
    for k in registered:
        key = norm_id(k)
        if key in with_dir:
            continue  # covered by its results directory
        # The sweep CSVs are evidence for the *sweep era* (S-08 and up). The
        # earlier hand-run strategies (S-01 … S-07) have their own results
        # directories and are covered by the per-directory checks above.
        if _num(key) < 8:
            continue
        if key not in by_sid:
            rep.fail("X14", f"registry {k}",
                     f"{k} is registered (sweep era, S-08+) but has no committed "
                     f"evidence: no strategy/results/{k.upper()}/ directory and no "
                     f"row in any strategy/results/iterations_*.csv sweep — a "
                     f"status (rejected/finalist) requires committed evidence")

    # ---- (c) S1–S3 from the `full`-window rows of each dir-less strategy ----
    status_of = {norm_id(k): ((v.get("status") or "").strip().lower().replace("*", ""))
                 for k, v in registry.items()}
    for key, k in sorted(reg_by_norm.items()):
        if key in with_dir or key not in by_sid:
            continue
        status = status_of.get(key, "")
        terminal = status in {"rejected", "parked"}
        # `full`-window rows only (the primary window; the plan's evidence basis)
        full_rows = [r for r in by_sid[key]
                     if (r.get("window") or "").strip().lower() == "full"]
        if not full_rows:
            rep.fail("X14", f"registry {k}",
                     f"{k} has sweep rows but none in the `full` window — "
                     f"S1–S3 cannot be evaluated from the committed evidence")
            continue
        try:
            max_trades = max(int(float(r.get("n_trades") or 0)) for r in full_rows)
        except ValueError:
            continue
        rets = [(float(r.get("total_return_pct")) if r.get("total_return_pct") not in (None, "") else None,
                 float(r.get("buyhold_return_pct")) if r.get("buyhold_return_pct") not in (None, "") else None)
                for r in full_rows]
        loses_everywhere = all(
            tr is not None and bh is not None and tr <= bh for tr, bh in rets)
        beating = set()
        for r in full_rows:
            if abs(float(r.get("cost_bps") or 0) - 2.0) < 1e-9:
                tr = r.get("total_return_pct")
                bh = r.get("buyhold_return_pct")
                if tr not in (None, "") and bh not in (None, "") and float(tr) > float(bh):
                    beating.add(r.get("instrument"))
        canon = reg_by_norm[key]

        def _emit(code: str, ok: bool, msg_ok: str, msg_fail: str) -> None:
            if ok:
                if terminal:
                    rep.note(code, f"registry {canon}", msg_ok)
                else:
                    rep.fail(code, f"registry {canon}", msg_fail)

        if max_trades > 300:
            _emit("S1", True,
                  f"max trade count {max_trades} > 300 (sweep full window) and the "
                  f"status is {status!r} — the §5 stop condition is correctly reflected",
                  f"max trade count {max_trades} exceeds the 300-trade budget (sweep "
                  f"`full` window) but the status is {status!r} — it must be rejected "
                  "or parked")
        if loses_everywhere:
            _emit("S2", True,
                  "loses to buy-hold in every `full`-window sweep cell and the status "
                  f"is {status!r} — the §5 stop condition is correctly reflected",
                  "loses to buy-hold in every `full`-window sweep cell (every cost "
                  f"tier, every instrument) but the status is {status!r} — it must "
                  "be rejected or parked")
        if not beating:
            _emit("S3", True,
                  "no instrument beats buy-hold at 2 bps in the `full`-window sweep "
                  f"and the status is {status!r} — the §5 stop condition is "
                  "correctly reflected",
                  "no instrument beats buy-hold at 2 bps in the `full`-window sweep "
                  f"(generated_strategy.md §5) but the status is {status!r} — it "
                  "must be rejected or parked")


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

        # The registry status is needed by several checks below (X13, X5, ...).
        status = (reg.get("status") or "").strip().lower().replace("*", "")

        # ---- X13: the OOS pass/fail must be present and self-consistent ---
        # (repo_review_20261029 §2.4). An OOS directory (a distinct `<ID>_oos`)
        # carries a machine pass/fail block. The checker re-computes that
        # verdict from the committed OOS cells using the SAME shared logic as
        # the runner (strategy/schema.py, driven by
        # `config/strategies.yml → oos.pass_criteria`) and requires it to match
        # the committed `pass`/`instruments_beating` columns.
        if res.is_oos:
            crit = ((cfg.get("oos") or {}).get("pass_criteria") or {})
            min_instr = crit.get("min_instruments_beating_bh_at_2bps", 2)
            max_tpy = crit.get("max_trades_per_year", 54)
            try:
                min_instr = int(min_instr); max_tpy = float(max_tpy)
            except (TypeError, ValueError):
                rep.fail("X13", f"registry {canon_id}",
                         "config `oos.pass_criteria` is missing a numeric "
                         "min_instruments_beating_bh_at_2bps / max_trades_per_year")
            computed = schema.oos_pass_fields(
                res.rows, min_instruments=min_instr, max_trades_per_year=max_tpy)

            def _bool(v):
                s = str(v).strip().lower()
                if s in ("true", "1", "yes"): return True
                if s in ("false", "0", "no"): return False
                return None

            def _num(v):
                try: return float(v)
                except (TypeError, ValueError): return None

            # (a) the OOS pass/fail columns must actually be present.
            need = schema.OOS_FIELDS_REQUIRED_FOR_PASS
            oos_rows = [r for r in res.rows if (r.get("window") or "").strip().lower() == "oos"]
            if oos_rows:
                for f in need:
                    if all((r.get(f) in (None, "")) for r in oos_rows):
                        rep.fail("X13", f"registry {canon_id}",
                                 f"the OOS `summary.csv` is missing the required "
                                 f"pass/fail column {f!r} (Phase 2.4)")
                # (b) the committed `pass` must equal the recomputed verdict.
                committed_passes = {_bool(r.get("pass")) for r in oos_rows}
                if len(committed_passes) > 1:
                    rep.fail("X13", f"registry {canon_id}",
                             f"the committed OOS `pass` is not consistent across rows "
                             f"({sorted(committed_passes)})")
                else:
                    cp = next(iter(committed_passes))
                    if cp is None:
                        rep.fail("X13", f"registry {canon_id}",
                                 "the committed OOS `pass` is blank — a machine verdict "
                                 "is required (Phase 2.4)")
                    elif cp != computed["pass"]:
                        rep.fail("X13", f"registry {canon_id}",
                                 f"the committed OOS `pass`={cp} disagrees with the "
                                 f"recomputed verdict {computed['pass']} "
                                 f"(beats on {computed['instruments_beating']} instrument(s), "
                                 f"need >= {min_instr}; trades/yr "
                                 f"{computed['max_trades_per_year_seen']} vs ceiling {max_tpy:g})")
                # (c) the committed `instruments_beating` must equal the
                #     recomputed count.
                committed_ib = {_num(r.get("instruments_beating")) for r in oos_rows}
                if len(committed_ib) > 1 or (committed_ib and
                                             next(iter(committed_ib)) != computed["instruments_beating"]):
                    rep.fail("X13", f"registry {canon_id}",
                             f"the committed OOS `instruments_beating` {sorted(committed_ib)} "
                             f"disagrees with the recomputed count "
                             f"{computed['instruments_beating']}")
                # (d) a trade-ceiling breach must not be hidden behind `pass=True`.
                if computed["trade_ceiling_breached"]:
                    rep.fail("X13", f"registry {canon_id}",
                             f"an OOS cell exceeds the trade ceiling "
                             f"({computed['max_trades_per_year_seen']} > {max_tpy:g} trades/yr) "
                             f"but the holdout must stay inside the ceiling")
            else:
                rep.fail("X13", f"registry {canon_id}",
                         "an OOS directory was declared but its `summary.csv` has no "
                         "window == 'oos' rows")
            # (e) the registry status must agree with the verdict: a passing
            #     holdout => `tested`; a failing one => `rejected`.
            if status == "tested" and computed["pass"] is False:
                rep.fail("X13", f"registry {canon_id}",
                         f"registry status is `tested` but the OOS verdict is FAIL "
                         f"(beats {computed['instruments_beating']}/{min_instr}, "
                         f"trade-ceiling breached={computed['trade_ceiling_breached']}) — "
                         f"only a passing holdout may be `tested`")
            if status == "rejected" and computed["pass"] is True:
                rep.warn("X13", f"registry {canon_id}",
                         f"the OOS verdict is PASS but the status is `rejected` — "
                         f"review whether it should be `tested`")
            # An OOS directory is only checked for identity (X1/X2/X3/X10) and
            # the holdout pass/fail (X13) above. The in-sample matrix value
            # checks (X5/X11/S1-S3/G5) apply to the strategy's in-sample `<ID>`
            # directory, not to the holdout result — stop here.
            continue

        # ---- X5: status vs outcome (two-sided) --------------------------
        # Existing (terminal-status) direction: the registry status must be one
        # of the trial-log outcomes. New (review follow-up #3 B.1) direction:
        # a *non-terminal* registry status (`candidate` / `finalist`) must not
        # sit on top of a terminal verdict in the trial log (`rejected` /
        # `parked` / `tested`) — that is "the row says adjudicated but the
        # registry still says not-run / OOS-pending", the exact hole 20 rows
        # sat in at e6350d5. `finalist` may carry a `tested` outcome (the OOS
        # just passed and the registry update is pending — transient, not a
        # contradiction).
        if status and trows:
            def _norm(s: str) -> str:
                return s.lower().replace(" ", "").replace("-", "")
            norm_out = {_norm(t["outcome"]) for t in trows}
            norm_status = _norm(status)
            terminal = {"rejected", "parked", "tested"}
            if norm_status in terminal:
                if norm_status not in norm_out:
                    rep.fail("X5", f"registry {canon_id}",
                             f"registry status {status!r} disagrees with the trial-log outcome(s) "
                             f"{sorted({t['outcome'] for t in trows})}")
            elif norm_status in {"candidate", "finalist"}:
                allowed = {"tested"} if norm_status == "finalist" else set()
                bad = (norm_out & terminal) - allowed
                if bad:
                    rep.fail("X5", f"registry {canon_id}",
                             f"registry status {status!r} is non-terminal but the trial log "
                             f"records a terminal verdict {sorted(bad)} — the row is "
                             f"adjudicated but the registry still says "
                             f"{'OOS pending' if norm_status == 'finalist' else 'not run'}")

        # ---- X12: trial-log timeframe agrees with the config -------------
        # The trial-log `hypothesis` column is free text, but when a row names
        # a bar timeframe (e.g. "5m RSI-24 ...") that claim must agree with the
        # strategy's registered timeframe in config/strategies.yml. This is the
        # check that would have caught the S-05/S-06 "1h" mislabel (their
        # registry + config + CSV are 5m).
        cfg_tf = ((cfg.get("strategies") or {}).get(canon_id) or {}).get("timeframe")
        if cfg_tf and trows:
            for t in trows:
                hyp = t["hypothesis"] or ""
                tokens = set(re.findall(r"\b\d+(?:m|h|d|w)\b", hyp))
                if tokens and cfg_tf not in tokens:
                    rep.fail("X12", f"trial_log {canon_id}",
                             f"trial-log row {t['n']} names timeframe(s) "
                             f"{sorted(tokens)} but {canon_id} is registered "
                             f"as {cfg_tf!r} in config/strategies.yml")
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

        # ---- F (finalist gate): a `finalist` row must actually beat the
        # in-sample bar — otherwise it could not be promoted to the holdout.
        # §1.6: the bar (from `config/strategies.yml → oos.pass_criteria`) is
        # no §5 stop condition AND total_return > buy-hold at 2 bps on
        # >= 2 of 3 instruments on BOTH `full` and `last_12m`.
        if status == "finalist":
            min_beat = 2  # >= 2 of 3 instruments (see pass_criteria)
            required_windows = ("full", "last_12m")
            per_win_instruments: dict[str, set[str]] = {}
            for c in res.cells:
                if (c.cost_bps == 2.0 and c.total_return_pct is not None
                        and c.buyhold_return_pct is not None
                        and c.total_return_pct > c.buyhold_return_pct):
                    per_win_instruments.setdefault(c.window, set()).add(c.instrument)
            weak = [w for w in required_windows
                    if len(per_win_instruments.get(w, set())) < min_beat]
            # The `> 300 trades` stop condition is not implied by the beat bar.
            trade_stop = res.max_trades > 300
            if weak or trade_stop:
                parts = []
                if weak:
                    parts.append("does not beat buy-hold at 2 bps on "
                                 f">= {min_beat} of 3 instruments on "
                                 f"{', '.join(required_windows)} — weak on {weak}")
                if trade_stop:
                    parts.append(f"max trade count {res.max_trades} > 300 (a §5 stop condition)")
                rep.fail("F", f"registry {canon_id}",
                         f"status is `finalist` but the in-sample results { ' and '.join(parts) } "
                         f"— a finalist must beat the in-sample bar "
                         f"(see `config/strategies.yml → oos.pass_criteria`)")
            else:
                rep.note("F", f"registry {canon_id}",
                         "status is `finalist` and the in-sample results satisfy the bar "
                         "(beats buy-hold at 2 bps on >= 2 of 3 instruments on full and last_12m, "
                         "max trade count <= 300)")

    # ---- X2 (other direction): config registry -> registry table --------
    for k in (cfg.get("strategies") or {}):
        if norm_id(k) not in reg_by_norm:
            rep.fail("X3", f"config strategies.{k}",
                     f"{k} is in config/strategies.yml but has no STRATEGY_REGISTRY.md row")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# OOS holdout ledger — append-only + cross-consistency (follow-up review)
# ---------------------------------------------------------------------------

def _ledger_path(root: Path) -> Path:
    return root / "strategy" / "oos_ledger.json"


def _ledger_records(p: Path) -> list[dict] | None:
    """The ledger's ``consumptions`` list, or ``None`` when the file is absent,
    not JSON, or not a list. (``None`` = "cannot verify", distinct from `[]`.)"""
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    cons = data.get("consumptions")
    return cons if isinstance(cons, list) else None


def _rec_key(rec: dict) -> tuple | None:
    """A comparable identity for a ledger consumption record.

    ``status`` is deliberately **not** part of the identity (follow-up review
    §1.3 / §3.4): a legal ``reserved → voided`` transition keeps the same
    (strategy, holdout_id, window) identity, so the append-only diff must not
    treat the status change as a "record removal". The permitted status
    transitions are enforced separately in L1 (a terminal ``completed`` or
    ``voided`` record can never be re-opened).
    """
    if not isinstance(rec, dict):
        return None
    return (norm_id(rec.get("strategy", "")),
            str(rec.get("holdout_id", "")),
            str(rec.get("holdout_start", "")),
            str(rec.get("holdout_end", "")))


def _norm_id_of(s: str) -> str:
    return norm_id(s)


def check_oos_end_field(cfg: dict, rep: Report, where: str) -> None:
    """L0 — the holdout end has a single source of truth.

    ``windows.oos.until`` must equal ``oos.holdout_end`` + 1 day. The loader
    (``strategy/strategy_lib.py::load_bars``) applies the holdout bound as a
    **half-open** interval ``time < until`` (a date-only bound is read at UTC
    midnight), so ``until = holdout_end + 1 day`` means "include every bar of
    ``holdout_end`` and exclude the 00:00 bar of ``until``" — the last
    fully-closed holdout day is ``holdout_end`` and ``until`` is the first day
    after it. Two hand-edited fields previously diverged (and the config
    comment was wrong about which bars were included); this check makes them
    agree or fails.
    """
    oos = cfg.get("oos") or {}
    windows = cfg.get("windows") or {}
    oos_win = windows.get("oos")
    holdout_end = as_date(oos.get("holdout_end"))
    if holdout_end is None:
        rep.fail("L0", where, "config has no parseable `oos.holdout_end` — "
                              "the holdout end is undefined")
        return
    if not isinstance(oos_win, dict):
        rep.fail("L0", where, "config has no `windows.oos` mapping — the "
                              "holdout window is undefined")
        return
    until = as_date(oos_win.get("until"))
    if until is None:
        rep.fail("L0", "config windows.oos", "windows.oos has no parseable `until`")
        return
    expected = holdout_end + timedelta(days=1)
    if until != expected:
        rep.fail("L0", "config windows.oos",
                 f"windows.oos.until={until} does not equal oos.holdout_end"
                 f"+1d ({holdout_end}+1d = {expected}). Set until to the day "
                 f"after the last fully-closed holdout day so the two fields "
                 f"cannot drift apart.")


def check_oos_ledger(root: Path, trials: list[dict], rep: Report,
                     base_ledger: Path | None = None) -> None:
    """L1 / L2 — the OOS ledger is append-only and agrees with trial_log.

    L1 (append-only): the committed ledger's records must be a *superset* of
       the base ledger's (``--base-ledger``). A holdout record may never be
       removed; the ledger only grows. Without ``--base-ledger`` there is no
       baseline to diff against, so L1 is skipped (still verified by CI, which
       always passes the base branch's ledger).

    L2 (cross-consistency): adjudicated OOS trial rows and ``completed`` ledger
       records must agree — every adjudicated ``oos`` trial row has a ledger
       consumption record, and every ``completed`` ledger record has an
       adjudicated ``oos`` trial row.
    """
    ledger_p = _ledger_path(root)
    if not ledger_p.exists():
        rep.fail("L1", "strategy/oos_ledger.json",
                 "OOS ledger is missing — a ledger reset is an append-only "
                 "violation; restore it (or pass the base ledger to --base-ledger)")
        return
    recs = _ledger_records(ledger_p)
    if recs is None:
        rep.fail("L1", "strategy/oos_ledger.json",
                 "OOS ledger is not a valid JSON object with a `consumptions` "
                 "list — refusing to verify append-only (fail closed)")
        return

    # ---- L1: superset of the base ledger (append-only) ---------------------
    if base_ledger is not None:
        if not base_ledger.exists():
            rep.fail("L1", str(base_ledger),
                     f"--base-ledger {base_ledger} does not exist — cannot "
                     f"verify the ledger is append-only")
            return
        base_recs = _ledger_records(base_ledger)
        if base_recs is None:
            rep.fail("L1", str(base_ledger),
                     f"base ledger {base_ledger} is not valid JSON with a "
                     f"`consumptions` list — cannot verify append-only (fail closed)")
            return
        # Index current records by identity (status NOT in the key, so a
        # reserved -> voided status change is not a "removal").
        cur_by_key: dict[tuple, list[dict]] = {}
        for r in recs:
            k = _rec_key(r)
            if k is not None:
                cur_by_key.setdefault(k, []).append(r)
        for br in base_recs:
            k = _rec_key(br)
            if k is None:
                continue
            matches = cur_by_key.get(k, [])
            if not matches:
                rep.fail("L1", "strategy/oos_ledger.json",
                         f"append-only violation: the base ledger's record "
                         f"({k[0]!r}, {k[1]!r}, {k[2]}..{k[3]}) is missing "
                         f"from the committed ledger. A holdout consumption may "
                         f"not be removed.")
                continue
            base_status = br.get("status")
            cur_statuses = {m.get("status") for m in matches}
            if base_status == "completed":
                # Terminal: once completed it stays completed (no re-open).
                if "completed" not in cur_statuses:
                    rep.fail("L1", "strategy/oos_ledger.json",
                             f"append-only violation: record "
                             f"({k[0]!r}, {k[1]!r}) was `completed` in the base "
                             f"ledger but no `completed` record remains "
                             f"(current statuses {sorted(str(s) for s in cur_statuses)}). "
                             f"A completed holdout is terminal.")
            elif base_status == "voided":
                # Terminal void: stays voided. Re-opening to reserved/completed
                # (re-running a holdout that was voided) is prohibited.
                if "voided" not in cur_statuses:
                    rep.fail("L1", "strategy/oos_ledger.json",
                             f"append-only violation: record "
                             f"({k[0]!r}, {k[1]!r}) was `voided` in the base "
                             f"ledger but no `voided` record remains "
                             f"(current statuses {sorted(str(s) for s in cur_statuses)}). "
                             f"A voided reservation is terminal — re-running a "
                             f"voided holdout is prohibited.")
            # reserved -> reserved | completed | voided are all legal (the
            # record was consumed or later invalidated by the human flow).

    # ---- L1b: a `voided` record must carry a written reason ---------------
    # (follow-up review §1.3: "看到结果再 void 重跑" is a backdoor — a void is
    #  only valid with a written, auditable reason AND no OOS output for the
    #  strategy; enforced whether or not a baseline ledger was supplied.)
    for r in recs:
        if isinstance(r, dict) and r.get("status") == "voided":
            reason = str(r.get("reason") or "").strip()
            if not reason:
                rep.fail("L1", "strategy/oos_ledger.json",
                         f"voided ledger record ({r.get('strategy')!r}, "
                         f"{r.get('holdout_id')!r}) has no `reason`. A void "
                         f"is only valid with a written reason documenting "
                         f"the infrastructure failure and that no holdout "
                         f"result was read.")
            # L1c: a void is only valid when NO OOS output exists for the
            # strategy — voiding a reservation that produced a result and
            # re-running is a backdoor. Review follow-up #3 §B2: count ANY
            # committed file in the OOS directory (``strategy/results/**/
            # *.json`` is git-ignored, so a clean CI checkout may hold only a
            # ``summary.csv`` / ``matrix.md`` — those are the committed
            # evidence), and treat an adjudicated `oos` trial-log row as OOS
            # output (the result was adjudicated, i.e. read).
            sid = norm_id(r.get("strategy", ""))
            out_dir = root / "strategy" / "results" / f"{sid}_oos"
            n_out = 0
            if out_dir.exists():
                n_out = sum(1 for f in out_dir.rglob("*") if f.is_file())
            has_oos_row = any(
                _norm_id_of(t["strategy_id"]) == sid
                and (t["window"] or "").strip().lower() == "oos"
                and (t["outcome"] or "").strip().lower() not in ("<tbd>", "", "tbd")
                for t in trials)
            if n_out > 0 or has_oos_row:
                detail = []
                if n_out > 0:
                    detail.append(f"{n_out} file(s) under {out_dir.relative_to(root)}/")
                if has_oos_row:
                    detail.append("an adjudicated `oos` trial-log row")
                rep.fail("L1", "strategy/oos_ledger.json",
                         f"voided ledger record ({r.get('strategy')!r}, "
                         f"{r.get('holdout_id')!r}) has OOS output ({' + '.join(detail)}). "
                         "A void is only valid when the reservation produced NO "
                         "result — voiding a result that was already read is a "
                         "backdoor.")

    # ---- L2: ledger <-> trial_log agree -----------------------------------
    def _oos_trials_for(sid_norm: str) -> list[dict]:
        return [t for t in trials
                if _norm_id_of(t["strategy_id"]) == sid_norm
                and (t["window"] or "").strip().lower() == "oos"
                and (t["outcome"] or "").strip().lower() not in ("<tbd>", "", "tbd")]

    # (a) every adjudicated OOS trial row must have a ledger record.
    for t in trials:
        if (t["window"] or "").strip().lower() != "oos":
            continue
        if (t["outcome"] or "").strip().lower() in ("<tbd>", "", "tbd"):
            continue  # not adjudicated yet — no ledger record required
        sid = _norm_id_of(t["strategy_id"])
        matched = [r for r in recs
                   if isinstance(r, dict)
                   and _norm_id_of(r.get("strategy", "")) == sid
                   and r.get("status") in ("reserved", "completed")]
        if not matched:
            rep.fail("L2", f"trial_log {t['strategy_id']}",
                     f"adjudicated `oos` trial row (strategy {t['strategy_id']}, "
                     f"outcome {t['outcome']!r}) has no matching OOS ledger "
                     f"consumption — the holdout was used without a reservation.")

    # (b) every `completed` ledger record must have an adjudicated OOS trial row.
    for r in recs:
        if not isinstance(r, dict) or r.get("status") != "completed":
            continue
        sid = _norm_id_of(r.get("strategy", ""))
        if not _oos_trials_for(sid):
            rep.fail("L2", "strategy/oos_ledger.json",
                     f"ledger record for strategy {sid!r} is `completed` but "
                     f"trial_log.md has no adjudicated `oos` row for it — a "
                     f"holdout result must be recorded before it is completed.")


def run(root: Path, base_ledger: Path | None = None) -> Report:
    rep = Report()
    cfg_path = root / "config" / "strategies.yml"
    if not cfg_path.exists():
        raise SystemExit(f"config not found: {cfg_path}")
    cfg = load_config(cfg_path)

    registry = parse_registry(root / "strategy" / "STRATEGY_REGISTRY.md")
    trials = parse_trial_log(root / "strategy" / "trial_log.md")

    check_windows(cfg, rep, "config/strategies.yml")

    # OOS holdout ledger — append-only (L1) + cross-consistency (L2) and the
    # single-source end-date (L0) (follow-up review).
    check_oos_end_field(cfg, rep, "config/strategies.yml")
    check_oos_ledger(root, trials, rep, base_ledger)

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

    # C5: the sweep CSVs are the committed evidence for the strategies that
    # have no results directory (S-08 … S-27 except the one with results/).
    check_sweep_evidence(root, cfg, registry, results, rep)

    # B.3: registry saturation guard (X15).
    check_saturation(registry, rep)
    check_finalist_pins(cfg, registry, rep)
    check_rejection_records(root, registry, rep)

    return rep


def check_finalist_pins(cfg: dict, registry: dict, rep: Report) -> None:
    """X16: every finalist must nominate a variant and a SHA-256 config pin."""
    configured = {_norm_id_of(k): v for k, v in (cfg.get("strategies") or {}).items()}
    for sid, row in registry.items():
        if (row.get("status") or "").lower() != "finalist":
            continue
        spec = configured.get(_norm_id_of(sid)) or {}
        variant, pin = spec.get("oos_variant"), spec.get("oos_config_hash")
        if not isinstance(variant, str) or not variant.strip() or not isinstance(pin, str) \
                or re.fullmatch(r"[0-9a-f]{64}", pin) is None:
            rep.fail("X16", f"registry {sid}",
                     "finalist requires oos_variant and a valid oos_config_hash in config/strategies.yml")


def check_rejection_records(root: Path, registry: dict, rep: Report) -> None:
    """X17: rejected ideas stay visible in the no-repeat table."""
    text = (root / "strategy/STRATEGY_REGISTRY.md").read_text(encoding="utf-8")
    section = text.partition("## Rejected combinations")[2].partition("\n## ")[0]
    recorded = set(re.findall(r"\((S-\d+)\)", section))
    for sid, row in registry.items():
        if row.get("status") == "rejected" and sid not in recorded:
            rep.fail("X17", f"registry {sid}",
                     "rejected strategy missing from the Rejected combinations table")


def _base_indicator(ind: str) -> str:
    """Strip trailing window numeric suffixes: willr_60 -> willr,
    macd_hist_6_24 -> macd_hist, st_dir_24_3 -> st_dir. Non-trailing suffixes
    are kept (stoch_d, ema_spread, vol_ratio stay intact)."""
    parts = ind.split("_")
    while parts and parts[-1].isdigit():
        parts = parts[:-1]
    return "_".join(parts) if parts else ind


def check_saturation(registry: dict, rep: Report) -> None:
    """X15 (review follow-up #3 §B.3): enforce the registry's own duplicate
    rule. Group strategy rows by (base indicator family, timeframe); a
    strategy belongs to a family if any of its backticked key indicators
    reduces to that base name. >= 4 members -> WARN, >= 8 -> FAIL.

    Baseline produces 6 warnings (ema 5m, st_dir 5m, atr 5m, mfi 5m, roc 5m,
    aroon_down 5m) and 0 failures, so the build stays green (D2). The guard
    exists so the *next* session that adds another variant of a saturated
    family trips it.
    """
    # family -> set of strategy ids
    fam: dict[tuple[str, str], set[str]] = {}
    for sid, rec in registry.items():
        row = (rec.get("key indicators") or "").strip()
        inds = re.findall(r"`([A-Za-z0-9_]+)`", row)
        tf = (rec.get("timeframe") or "").strip()
        for ind in set(inds):
            base = _base_indicator(ind)
            if not base:
                continue
            fam.setdefault((base, tf), set()).add(sid)

    for (base, tf), sids in sorted(fam.items()):
        n = len(sids)
        if n >= 8:
            rep.fail("X15", f"registry {base} {tf}",
                     f"registry saturated for this family — {n} strategies share "
                     f"({base!r}, {tf!r}) — STOP and report per WORKFLOW.md Step 1 "
                     f"(saturation guard)")
        elif n >= 4:
            rep.warn("X15", f"registry {base} {tf}",
                     f"the ({base!r}, {tf!r}) family already has {n} strategies; "
                     f"the next variant needs a different indicator family — see "
                     f"WORKFLOW.md Step 1 (registry saturation)")


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
    ap.add_argument("--base-ledger", default=None,
                    help="path to the base branch's oos_ledger.json (CI): the "
                         "committed ledger must be a superset of it (append-only)")
    args = ap.parse_args()

    root = Path(args.root).resolve() if args.root else Path(__file__).resolve().parents[1]
    base_ledger = Path(args.base_ledger).resolve() if args.base_ledger else None
    rep = run(root, base_ledger)

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
