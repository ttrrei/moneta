"""Shared summary-CSV contract + OOS pass/fail logic (repo_review_20261029).

This module is **dependency-free** (stdlib only) so it can be imported by BOTH:

* :mod:`strategy.run_matrix`  — writes the CSV (Phase 3.2 / 3.3), and
* :mod:`:` scripts/check_results.py  — data-free verifier (Phase 2.4 X13).

Keeping the field list and the pass/fail formula in one place is what stops
the two from drifting apart (the S01/S05/S06 "old schema" bug of §3.3).
"""

from __future__ import annotations

from itertools import product
from math import isfinite

__all__ = [
    "SUMMARY_FIELDS",
    "OOS_FIELDS",
    "OOS_FIELDS_REQUIRED_FOR_PASS",
    "OOS_HEADER",
    "oos_row_is_oos",
    "oos_pass_fields",
    "compute_oos_fields",
    "is_oos_cells",
    "csv_fieldnames",
    "validate_cell_grid",
]


def validate_cell_grid(rows: list[dict], instruments, windows, cost_tiers,
                       group_fields: tuple[str, ...] = ()) -> None:
    """Reject missing, duplicate, unexpected, failed or non-numeric cells.

    Each group (e.g. strategy/variant) must contain the entire declared grid.
    This validation runs before report dictionaries can discard duplicates.
    """
    expected = set(product(instruments, windows, map(float, cost_tiers)))
    groups: dict[tuple, set] = {}
    if not rows or not expected:
        raise ValueError("empty result matrix")
    for row in rows:
        group = tuple(row.get(field) for field in group_fields)
        if any(value in (None, "") for value in group):
            raise ValueError(f"missing group identity: {group}")
        if str(row.get("error") or "").strip():
            raise ValueError(f"failed cell in {group}: {row['error']}")
        try:
            key = (row["instrument"], row["window"], float(row["cost_bps"]))
            for field in ("n_trades", "trades_per_year", "total_return_pct", "buyhold_return_pct"):
                if not isfinite(float(row[field])):
                    raise ValueError(field)
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"invalid result cell in {group}: {exc}") from exc
        seen = groups.setdefault(group, set())
        if key in seen:
            raise ValueError(f"duplicate cell in {group}: {key}")
        if key not in expected:
            raise ValueError(f"unexpected cell in {group}: {key}")
        seen.add(key)
    for group, seen in groups.items():
        if missing := expected - seen:
            raise ValueError(f"missing {len(missing)} cells in {group}: {sorted(missing)}")

# ---------------------------------------------------------------------------
# Field lists — the single source of truth for a committed summary.csv header.
# ---------------------------------------------------------------------------
#: The base (in-sample) summary.csv column set. A strategy's ``summary.csv``
#: header must equal exactly this (check §3.3).
SUMMARY_FIELDS: list[str] = [
    "strategy", "instrument", "window", "timeframe", "cost_bps", "entry_guard",
    "start", "end", "n_bars", "n_trades", "total_return_pct", "buyhold_return_pct",
    "buyhold_max_drawdown_pct",
    "max_drawdown_pct", "win_rate_pct", "avg_trade_return_pct", "sharpe",
    "sharpe_weekly", "buyhold_sharpe_weekly",
    "trades_per_year", "exposure_pct", "mean_net_position_pct",
    "span_years",
]

#: The extra columns an OOS (holdout) summary.csv carries on top of
#: :data:`SUMMARY_FIELDS` — the machine-computed pass/fail block (Phase 2.4).
OOS_FIELDS: list[str] = [
    "beat_bh_at_2bps",        # per-cell bool: ret > buy-hold at the 2 bps tier
    "instruments_beating",    # count of distinct instruments that beat BH at 2 bps
    "mean_net_position_pct",  # (already in SUMMARY_FIELDS; repeated for clarity)
    "pass",                   # overall holdout pass/fail for this strategy
]

#: The subset of OOS fields that must be PRESENT and consistent for an OOS
#: ``summary.csv`` to be a valid, machine-checked holdout result (X13).
OOS_FIELDS_REQUIRED_FOR_PASS = [
    "beat_bh_at_2bps",
    "instruments_beating",
    "pass",
]

#: The FULL header of an OOS ``summary.csv`` = base fields + the OOS pass/fail
#: block (Phase 2.4). ``pass`` is the overall per-strategy verdict, repeated on
#: every OOS row; the per-row ``beat_bh_at_2bps`` is the per-cell flag.
OOS_HEADER: list[str] = SUMMARY_FIELDS + [
    "beat_bh_at_2bps",
    "instruments_beating",
    "pass",
]


def is_oos_cells(cells: list[dict]) -> bool:
    """True if any cell in ``cells`` is an OOS-window cell."""
    return any((c.get("window") or "").strip().lower() == "oos" for c in cells)


def csv_fieldnames(is_oos: bool) -> list[str]:
    """The exact summary.csv header for an in-sample vs. an OOS run."""
    return OOS_HEADER if is_oos else list(SUMMARY_FIELDS)


# ---------------------------------------------------------------------------
# OOS pass/fail — the single definition used by run_matrix AND the checker.
# ---------------------------------------------------------------------------

def _f(x):
    """Best-effort float parse; None on blank / unparseable."""
    try:
        if x is None:
            return None
        if isinstance(x, str) and x.strip() == "":
            return None
        return float(x)
    except (TypeError, ValueError):
        return None


def _b(x):
    """Best-effort bool parse of a CSV cell ('true'/'1'/'yes' -> True)."""
    if isinstance(x, bool):
        return x
    if x is None:
        return None
    s = str(x).strip().lower()
    if s in ("true", "1", "yes", "t", "y"):
        return True
    if s in ("false", "0", "no", "f", "n"):
        return False
    return None


def oos_row_is_oos(row: dict) -> bool:
    """True if this summary row belongs to the OOS holdout window."""
    return (row.get("window") or "").strip().lower() == "oos"


def compute_oos_fields(cells: list[dict], min_instruments: int = 2,
                       max_trades_per_year: float = 54.0) -> dict:
    """Attach the OOS pass/fail fields to each OOS cell IN PLACE (run_matrix).

    ``cells`` are the run_matrix result dicts (already carrying the in-sample
    metric keys). For every OOS-window cell it sets:

    * ``beat_bh_at_2bps`` — bool, True iff this cell is at the 2 bps tier and
      its ``total_return_pct`` exceeds ``buyhold_return_pct``;
    * ``instruments_beating`` — the strategy-level count of distinct
      instruments beating buy-hold at 2 bps;
    * ``pass`` — the strategy-level verdict (beats on >= ``min_instruments``
      AND no ``trades_per_year`` cell breaches ``max_trades_per_year``).

    Returns the strategy-level verdict dict (for the caller to log / persist).
    Non-OOS cells are left untouched.
    """
    verdict = oos_pass_fields(cells, min_instruments=min_instruments,
                              max_trades_per_year=max_trades_per_year)
    for c in cells:
        if not oos_row_is_oos(c):
            continue
        cost = _f(c.get("cost_bps"))
        tr = _f(c.get("total_return_pct"))
        bh = _f(c.get("buyhold_return_pct"))
        c["beat_bh_at_2bps"] = bool(cost is not None and abs(cost - 2.0) < 1e-9
                                    and tr is not None and bh is not None and tr > bh)
        c["instruments_beating"] = verdict["instruments_beating"]
        c["pass"] = verdict["pass"]
    return verdict


def oos_pass_fields(rows: list[dict], min_instruments: int = 2,
                    max_trades_per_year: float = 54.0) -> dict:
    """Recompute the machine pass/fail for a set of committed OOS ``rows``.

    ``rows`` must be the ``window == 'oos'`` rows of one strategy's
    summary.csv (all instruments, all cost tiers). The pass rule (from
    ``config/strategies.yml → oos.pass_criteria``) is:

    * ``instruments_beating`` >= ``min_instruments``  (default 2 of 3), where an
      instrument "beats" if at the 2 bps tier its ``total_return_pct`` is above
      ``buyhold_return_pct``; AND
    * the trade ceiling is not breached: the strategy's max
      ``trades_per_year`` (a cell) must be <= ``max_trades_per_year``.

    Returns a dict of the OOS pass/fail fields plus the pieces a caller wants
    to assert against. No external data is needed — the committed numbers in
    the rows are the only input (that is the whole point of the X13 check).
    """
    oos = [r for r in rows if oos_row_is_oos(r)]
    if not oos:
        return {
            "instruments_beating": 0,
            "beat_bh_at_2bps": 0,
            "max_trades_per_year_seen": 0.0,
            "trade_ceiling_breached": False,
            "pass": False,
            "mean_net_position_pct": 0.0,
        }

    beat_instruments: set[str] = set()
    beat_cells = 0
    tpy_max = 0.0
    pos = []
    for r in oos:
        inst = (r.get("instrument") or "").strip()
        cost = _f(r.get("cost_bps"))
        tr = _f(r.get("total_return_pct"))
        bh = _f(r.get("buyhold_return_pct"))
        tpy = _f(r.get("trades_per_year"))
        mnp = _f(r.get("mean_net_position_pct"))
        if mnp is not None:
            pos.append(mnp)
        if tpy is not None and tpy > tpy_max:
            tpy_max = tpy
        # "beats buy-hold at 2 bps" for this instrument.
        if cost is not None and abs(cost - 2.0) < 1e-9 and tr is not None \
                and bh is not None and tr > bh and inst:
            beat_instruments.add(inst)
            beat_cells += 1

    instruments_beating = len(beat_instruments)
    trade_ceiling_breached = tpy_max > max_trades_per_year + 1e-9
    passes = (instruments_beating >= min_instruments
              and not trade_ceiling_breached)

    return {
        "instruments_beating": instruments_beating,
        "beat_bh_at_2bps": beat_cells,
        "max_trades_per_year_seen": round(tpy_max, 2),
        "trade_ceiling_breached": trade_ceiling_breached,
        "pass": passes,
        "mean_net_position_pct": round(sum(pos) / len(pos), 2) if pos else 0.0,
    }
