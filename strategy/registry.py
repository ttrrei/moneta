"""Shared strategy-registry / trial-log parsing (one place, two consumers).

Why this exists (repo_review_20261029 §1.6)
-------------------------------------------
Two programs need to read ``STRATEGY_REGISTRY.md`` and ``trial_log.md`` and
agree on what they mean:

* :mod:`strategy.run_matrix` — the *OOS gate* (finalist-only holdout access),
  and
* :mod:`scripts.check_results` — the committed-results consistency checker.

Keeping the table/row parsing here is what prevents the two from drifting
(§1.6: "reuse the existing registry/trial-log parsing ... do not duplicate the
regexes"). Both import this module instead of each carrying a copy of the
``|``-splitting and ``**bold**``-stripping logic.

This module is deliberately **pure**: no DuckDB, no TA-Lib, no parquet, no
network — it reads two Markdown files and a config dict. That is what lets
``scripts/check_results.py`` import it in a bare CI container where none of the
data stack is installed.
"""

from __future__ import annotations

import re
from pathlib import Path

#: ``**bold**`` → ``bold`` (the registry/trial tables use bold for statuses).
BOLD = re.compile(r"\*\*(.+?)\*\*")

#: The registry-status vocabulary (repo_review_20261029 §1.6):
#:   candidate  — designed, not yet run
#:   finalist   — passed the in-sample bar, OOS pending (may consume the holdout)
#:   tested     — reached only by passing the single OOS evaluation
#:   parked     — deprioritised
#:   rejected   — failed; do not re-test without a new hypothesis
STATUSES = ("candidate", "finalist", "tested", "parked", "rejected")

#: Windows that count as *in-sample* (a real in-sample evaluation happened).
IN_SAMPLE_WINDOWS = ("full", "last_12m")


def strip_md(s: str) -> str:
    """``**bold**`` → ``bold`` and trim whitespace."""
    return BOLD.sub(r"\1", (s or "")).strip()


def norm_id(s: str) -> str:
    """Canonical comparison key for a strategy id: S-01 / s01 / S01 -> S01."""
    return (s or "").strip().upper().replace("-", "").replace("_", "")


def parse_registry(path: Path | str) -> dict[str, dict]:
    """Parse the strategy table of STRATEGY_REGISTRY.md -> ``{id: {col: value}}``.

    Keys are the *lower-cased header* names (e.g. ``"status"``, ``"result (ret vs bh)"``).
    Rows are the ``S-NN`` table rows; the header / separator rows are skipped.
    An absent file yields an empty dict (callers decide whether that is a failure).
    """
    p = Path(path)
    rows: dict[str, dict] = {}
    if not p.exists():
        return rows
    header: list[str] | None = None
    for line in p.read_text(encoding="utf-8").splitlines():
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


def registry_status(path: Path | str, strategy: str) -> str | None:
    """The registry ``Status`` of ``strategy`` (lower-cased, bold stripped),
    or ``None`` when the strategy has no registry row."""
    rec = parse_registry(path).get(strategy) or None
    if rec is None:
        # Tolerate a runner-style id (``s01``) against a canonical row (``S-01``).
        for k, v in parse_registry(path).items():
            if norm_id(k) == norm_id(strategy):
                rec = v
                break
    if not rec:
        return None
    return (rec.get("status") or "").strip().lower().replace("*", "")


def parse_trial_log(path: Path | str) -> list[dict]:
    """Parse trial_log.md data rows (HTML-comment examples excluded)."""
    p = Path(path)
    out: list[dict] = []
    if not p.exists():
        return out
    body = re.sub(r"<!--.*?-->", "", p.read_text(encoding="utf-8"), flags=re.DOTALL)
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


def _trials_for(trials: list[dict], strategy: str) -> list[dict]:
    want = norm_id(strategy)
    return [t for t in trials if norm_id(t["strategy_id"]) == want]


def has_in_sample_outcome(trials: list[dict], strategy: str) -> bool:
    """True when the strategy has at least one *in-sample* trial row with a
    real outcome (i.e. not ``<TBD>``). That is the evidence it "passed the
    in-sample bar" before it is allowed to consume the holdout (§1.6)."""
    for t in _trials_for(trials, strategy):
        if (t["window"] or "").strip().lower() in IN_SAMPLE_WINDOWS \
                and (t["outcome"] or "").strip().lower() not in ("<tbd>", "", "tbd"):
            return True
    return False


def oos_eligible(strategy: str, cfg: dict,
                 registry: dict[str, dict], trials: list[dict]) -> tuple[bool, str]:
    """Decide whether ``strategy`` is *eligible* to consume the OOS holdout.

    Returns ``(ok, reason)``. This is the *label/pipeline* side of the gate
    (repo_review_20261029 §1.6): the ledger side (a strategy may consume a
    holdout once; D1 cap) is enforced separately by :mod:`strategy.run_matrix`,
    because it needs the committed ledger file. All of the following must hold:

      * the strategy is registered in ``config/strategies.yml``;
      * the registry ``Status`` is exactly ``finalist``;
      * the trial log has a real in-sample outcome (not ``<TBD>``).

    Anything else — ``rejected`` / ``parked`` / ``candidate`` / unregistered /
    ``<TBD>`` — is refused (fail closed: an unparseable/absent registry or
    trial log makes the strategy ineligible, never assumed eligible).
    """
    want = norm_id(strategy)

    registered = cfg.get("strategies") or {}
    if not any(norm_id(k) == want for k in registered):
        return False, f"not registered in config/strategies.yml (strategies:)"

    row = next((v for k, v in registry.items() if norm_id(k) == want), None)
    if row is None:
        return False, "no row in STRATEGY_REGISTRY.md"
    status = (row.get("status") or "").strip().lower().replace("*", "")
    if status != "finalist":
        return False, f"registry status is {status!r}, not 'finalist' " \
                      f"(only a finalist may consume the holdout)"

    if not has_in_sample_outcome(trials, strategy):
        return False, "no in-sample trial row with a real outcome " \
                      "(need a `full`/`last_12m` row that is not `<TBD>`)"

    return True, "eligible (finalist with a real in-sample outcome)"


def adjudicated_oos_rows(trials: list[dict], strategy: str) -> list[dict]:
    """The strategy's *adjudicated* OOS rows (window == ``oos``, outcome != <TBD>).

    This is the existing *label lock* (an adjudicated OOS row blocks a second
    holdout run) — kept here so both the runner and the checker share it."""
    want = norm_id(strategy)
    return [t for t in trials
            if norm_id(t["strategy_id"]) == want
            and (t["window"] or "").strip().lower() == "oos"
            and (t["outcome"] or "").strip().lower() not in ("<tbd>", "", "tbd")]


__all__ = [
    "BOLD",
    "STATUSES",
    "IN_SAMPLE_WINDOWS",
    "strip_md",
    "norm_id",
    "parse_registry",
    "registry_status",
    "parse_trial_log",
    "has_in_sample_outcome",
    "oos_eligible",
    "adjudicated_oos_rows",
]
