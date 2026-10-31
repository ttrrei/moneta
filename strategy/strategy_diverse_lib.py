"""Compatibility façade for the pre-registered S-113..S-132 rule batch.

What changed
------------
The twenty rules used to live here as **Python literals** — a 150-line
``RuleSpec`` dataclass plus a hand-maintained list of twenty entries. That
made the catalogue impossible to diff, impossible to extend mechanically, and
impossible to reason about as a *distribution*.

They now live where data belongs: ``config/strategy_specs.yml``. This module
is the thin façade that keeps every existing import working:

* :data:`RULES` — the catalogue, keyed ``"s113"`` ... ``"s132"``;
* :class:`RuleSpec` — the canonical dataclass (:mod:`strategy.rule_spec`);
* :class:`DiverseRuleState` — the per-bar reference oracle
  (:class:`strategy.rule_engine.ReferenceRuleState`), kept as the equivalence
  anchor for ``tests/test_rule_engine.py``;
* :func:`run_rule` / :func:`cli_main` — the same entry points as before.

The evaluation itself moved to the shared, vectorised path
(:func:`strategy.strategy_spec_runner.run_spec`): the signal is computed
**once** per (strategy, instrument, window) and the engine accounts for that
same position array at every cost tier.

Everything else in the repository — the 20 thin ``strategy_*_lib.py``
adapters, the 20 CLIs under ``strategy/code/``, ``strategy/run_matrix.py``,
``strategy/variants.py`` and ``scripts/`` — keeps working unchanged.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from strategy.rule_engine import ReferenceRuleState as DiverseRuleState
from strategy.rule_spec import RuleSpec, load_specs
from strategy.strategy_spec_runner import SPEC_PATH, run_spec

#: The catalogue, keyed by the canonical id (``"s113"`` ... ``"s132"``).
RULES: dict[str, RuleSpec] = load_specs(SPEC_PATH)

if not RULES:  # pragma: no cover - a missing catalogue is a repo-integrity bug
    raise SystemExit(
        f"config/strategy_specs.yml is missing or empty — the S-113..S-132 "
        f"catalogue cannot be loaded (looked in {Path(SPEC_PATH)})")


def run_rule(parquet: str | None, instrument: str, timeframe: str | None = None,
             since: str | None = None, until: str | None = None,
             cost_bps: float = 2.0, entry_guard: bool = False,
             oos_token: object | None = None, strategy_id: str = "s113") -> dict:
    """Evaluate one of the pre-registered rules on one instrument / window.

    Same contract as before: the spec's own timeframe is enforced, the bars
    are loaded behind the OOS holdout gate, and the result carries the
    standard metadata + engine metrics + trade distribution.
    """
    key = strategy_id.lower().replace("-", "")
    try:
        spec = RULES[key]
    except KeyError as exc:
        raise SystemExit(f"Unknown diverse strategy {strategy_id!r}") from exc
    return run_spec(
        spec, instrument, parquet=parquet, timeframe=timeframe, since=since,
        until=until, cost_bps=cost_bps, entry_guard=entry_guard,
        oos_token=oos_token, long_only=False)


def cli_main(strategy_id: str) -> None:
    """The shared CLI body for the S-113..S-132 wrappers."""
    spec = RULES[strategy_id.lower().replace("-", "")]
    parser = argparse.ArgumentParser(description=f"{spec.sid} {spec.name}")
    parser.add_argument("--instrument", default="EUR_USD")
    parser.add_argument("--timeframe", default=spec.timeframe, choices=("5m", "1h"))
    parser.add_argument("--since")
    parser.add_argument("--until")
    parser.add_argument("--parquet")
    parser.add_argument("--cost-bps", type=float, default=2.0)
    parser.add_argument("--json")
    parser.add_argument("--entry-guard", action="store_true")
    args = parser.parse_args()
    result = run_rule(
        args.parquet, args.instrument, args.timeframe, args.since, args.until,
        args.cost_bps, args.entry_guard, strategy_id=strategy_id)
    if args.json:
        print(json.dumps(result, indent=2, default=str))
    else:
        for key in ("strategy_id", "instrument", "timeframe", "n_trades",
                    "total_return_pct", "buyhold_return_pct", "sharpe_weekly",
                    "max_drawdown_pct", "trades_per_year"):
            if key in result:
                print(f"{key:22} {result[key]}")


__all__ = ["DiverseRuleState", "RULES", "RuleSpec", "cli_main", "run_rule"]
