"""The canonical strategy declaration language (``RuleSpec``).

Why this module exists
----------------------
The repository grew three different dialects for the *same* idea — "declare a
signal, let the shared engine account for it":

* **dialect A** — one hand-written 150-line module per strategy
  (``strategy/strategy_roc_lib.py``, ``strategy_mfi60_lib.py``, ...).
  ~113 of them, all the same skeleton with a different threshold.
* **dialect B** — the same skeleton with more knobs (``strategy_quadosc_lib``,
  ``strategy_triosc_lib``, ``strategy_multiscale_lib``, ...).
* **dialect C** — a *declarative* spec: a table of conditions, a hypothesis,
  an expected trade count and a "what makes this different" note. It was
  introduced at S-113 (``strategy/strategy_diverse_lib.py``) and is the only
  dialect that carries the research metadata a strategy actually needs.

Dialect C is the destination. It is also the only dialect in which a strategy
is **data**, so it can be compared, diffed, deduplicated and mutated
mechanically. This module promotes it from a private helper inside one file to
the repo-wide canonical form, and adds the three fields that turn a spec from
"a thing to run" into "a hypothesis to iterate on":

* ``family``   — which axis of the hypothesis space the strategy occupies
  (momentum / reversion / breakout / ...). This is what makes the *distribution*
  of candidates controllable instead of accidental.
* ``role``     — the regime the idea is *for* ("works when 1h ADX is low").
  A strategy without a role cannot be targeted at anything.
* ``parent`` / ``mutation`` / ``rationale`` — the lineage of an iteration:
  which parent it came from, which mutation operator produced it, and the
  diagnosis that motivated that operator. This is what makes iteration
  *targeted* and auditable instead of "try knob B again".

The condition vocabulary is deliberately tiny and closed
(:data:`CONDITION_OPS`). A closed vocabulary is what lets the evaluation be
**vectorised** (see :mod:`strategy.rule_engine`) and what lets two specs be
compared structurally (dedup) without executing them.

A spec carries *no* logic: it never touches data, never reads a clock and
never mutates. It is a frozen dataclass, so it is hashable and comparable.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Mapping, Sequence

import yaml

#: ``(left, op, right)`` — ``left`` is a feature column, ``op`` is one of
#: :data:`CONDITION_OPS`, ``right`` is either a number or another column name.
Condition = tuple[str, str, float | str]

#: The closed comparison vocabulary. Every op is causal by construction: it
#: compares bar ``j`` with bar ``j-1`` at most, never with a future bar.
#:
#: ``above`` / ``below``       level comparison (``a > b`` / ``a < b``)
#: ``cross_up``                ``a`` crosses *above* a constant ``b``
#:                              (``a[j] > b`` and ``a[j-1] <= b``)
#: ``cross_down``              ``a`` crosses *below* a constant ``b``
#: ``cross_above``             ``a`` crosses *above* the series ``b``
#:                              (``a[j] > b[j]`` and ``a[j-1] <= b[j-1]``)
#: ``cross_below``             ``a`` crosses *below* the series ``b``
CONDITION_OPS: tuple[str, ...] = (
    "above",
    "below",
    "cross_up",
    "cross_down",
    "cross_above",
    "cross_below",
)

#: Ops that compare against a *series* rather than a constant.
SERIES_OPS: frozenset[str] = frozenset({"cross_above", "cross_below"})

#: The hypothesis-space axes. A candidate declares its ``family`` so the
#: cohort allocator can keep the *distribution* of research balanced instead
#: of letting whichever indicator happened to be popular last week dominate.
FAMILIES: tuple[str, ...] = (
    "momentum",
    "reversion",
    "breakout",
    "volatility",
    "flow",
    "seasonal",
    "microstructure",
    "unspecified",
)

#: Holding-period scale of the hypothesis.
HORIZONS: tuple[str, ...] = ("fast", "intraday", "slow", "multi_day")

#: Which side of the book the hypothesis trades.
SIDES: tuple[str, ...] = ("long", "short", "both")

#: Default location of the spec catalogue.
DEFAULT_SPEC_PATH = Path("config/strategy_specs.yml")

#: The fields that define *what the strategy trades*. Everything else on a
#: spec (family, role, side, horizon, lineage) is annotation.
#:
#: This split matters: the OOS ``config_hash`` is built from the signal
#: fields only, so re-labelling a strategy (giving it a role, re-filing it
#: under a different family, recording its lineage) can never change the
#: identity of an already-pinned or already-adjudicated run.
SIGNAL_FIELDS: tuple[str, ...] = (
    "sid",
    "slug",
    "name",
    "timeframe",
    "columns",
    "hypothesis",
    "expected_trades",
    "difference",
    "enter_long",
    "enter_short",
    "exit_long",
    "exit_short",
)


@dataclass(frozen=True)
class RuleSpec:
    """One strategy hypothesis, declared as data.

    The four ``enter_*`` / ``exit_*`` tuples are the *only* signal definition.
    Each tuple is a conjunction: every condition in it must hold on the same
    closed bar. An empty tuple is "never" — so a long-only spec simply leaves
    ``enter_short`` / ``exit_short`` empty.

    Attributes
    ----------
    sid             : the strategy id (``"S-113"``).
    slug            : stable kebab-case name used in ids and file names.
    name            : human-readable name.
    timeframe       : ``"5m"`` or ``"1h"`` — the *only* timeframe the rule
                      is allowed to run on.
    columns         : every feature column the rule reads. Used both to load
                      the data and to decide when a bar is unusable (a bar
                      with a non-finite value in any of these columns holds
                      the position instead of trading).
    hypothesis      : the falsifiable claim ("X may persist when Y").
    expected_trades : the *prior* on opportunity frequency, e.g. ``"20-180"``.
    difference      : what distinguishes this from an already-tried idea —
                      the human-readable dedup rationale.
    family / role / side / horizon
                    : the axes of the hypothesis space (see the module
                      docstring). ``role`` is the regime the idea is *for*.
    parent / mutation / rationale
                    : iteration lineage. ``parent`` is the id this spec was
                      derived from, ``mutation`` names the operator that
                      produced it, ``rationale`` records the diagnosis that
                      justified applying that operator.
    """

    sid: str
    slug: str
    name: str
    timeframe: str
    columns: tuple[str, ...]
    hypothesis: str
    expected_trades: str
    difference: str
    enter_long: tuple[Condition, ...]
    enter_short: tuple[Condition, ...]
    exit_long: tuple[Condition, ...]
    exit_short: tuple[Condition, ...]
    family: str = "unspecified"
    role: str = ""
    side: str = "both"
    horizon: str = "intraday"
    parent: str | None = None
    mutation: str | None = None
    rationale: str = ""

    # -- convenience ------------------------------------------------------
    @property
    def key(self) -> str:
        """Canonical lookup key: ``"S-113"`` -> ``"s113"``."""
        return self.sid.lower().replace("-", "")

    @property
    def trades_long(self) -> bool:
        return bool(self.enter_long)

    @property
    def trades_short(self) -> bool:
        return bool(self.enter_short)

    def with_params(self, **changes: Any) -> "RuleSpec":
        """Return a copy with ``changes`` applied (frozen dataclass helper)."""
        return replace(self, **changes)

    def lineage(self) -> str:
        """One-line lineage description, e.g. ``"S-113 <- seasonal_mask"``."""
        if self.parent and self.mutation:
            return f"{self.sid} <- {self.parent} via {self.mutation}"
        return self.sid


# ---------------------------------------------------------------------------
# Parsing / validation
# ---------------------------------------------------------------------------

def _condition(raw: Any, where: str) -> Condition:
    """Parse one ``[left, op, right]`` triple into a :data:`Condition`."""
    if isinstance(raw, Mapping):
        left = raw.get("left")
        op = raw.get("op")
        right = raw.get("right")
    elif isinstance(raw, Sequence) and not isinstance(raw, (str, bytes)) and len(raw) == 3:
        left, op, right = raw
    else:
        raise ValueError(f"{where}: condition must be [left, op, right], got {raw!r}")
    if not isinstance(left, str) or not left:
        raise ValueError(f"{where}: condition left must be a column name, got {left!r}")
    if op not in CONDITION_OPS:
        raise ValueError(f"{where}: unknown condition op {op!r} "
                         f"(allowed: {', '.join(CONDITION_OPS)})")
    if isinstance(right, bool) or not isinstance(right, (int, float, str)):
        raise ValueError(f"{where}: condition right must be a number or a column "
                         f"name, got {right!r}")
    if isinstance(right, str) and op not in SERIES_OPS:
        raise ValueError(f"{where}: op {op!r} compares against a constant; a "
                         f"column name is only allowed for {sorted(SERIES_OPS)}")
    # Keep the number's own type (int stays int). The OOS ``config_hash`` is a
    # JSON digest, and ``20`` and ``20.0`` serialise differently — coercing
    # here would silently change the identity of every migrated strategy.
    return (left, str(op), right)


def _conditions(raw: Any, where: str) -> tuple[Condition, ...]:
    if raw is None:
        return ()
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
        raise ValueError(f"{where}: expected a list of conditions, got {raw!r}")
    return tuple(_condition(c, f"{where}[{i}]") for i, c in enumerate(raw))


def spec_from_dict(raw: Mapping[str, Any]) -> RuleSpec:
    """Build a :class:`RuleSpec` from its mapping form (as stored in YAML)."""
    for key in ("sid", "slug", "name", "timeframe", "columns"):
        if key not in raw:
            raise ValueError(f"spec is missing required key {key!r}: {raw!r}")
    columns = tuple(str(c) for c in raw["columns"])
    if not columns:
        raise ValueError(f"{raw.get('sid')}: a spec needs at least one column")

    spec = RuleSpec(
        sid=str(raw["sid"]),
        slug=str(raw["slug"]),
        name=str(raw["name"]),
        timeframe=str(raw["timeframe"]),
        columns=columns,
        hypothesis=str(raw.get("hypothesis", "")),
        expected_trades=str(raw.get("expected_trades", "")),
        difference=str(raw.get("difference", "")),
        enter_long=_conditions(raw.get("enter_long"), f"{raw['sid']}.enter_long"),
        enter_short=_conditions(raw.get("enter_short"), f"{raw['sid']}.enter_short"),
        exit_long=_conditions(raw.get("exit_long"), f"{raw['sid']}.exit_long"),
        exit_short=_conditions(raw.get("exit_short"), f"{raw['sid']}.exit_short"),
        family=str(raw.get("family", "unspecified")),
        role=str(raw.get("role", "")),
        side=str(raw.get("side", "both")),
        horizon=str(raw.get("horizon", "intraday")),
        parent=(str(raw["parent"]) if raw.get("parent") else None),
        mutation=(str(raw["mutation"]) if raw.get("mutation") else None),
        rationale=str(raw.get("rationale", "")),
    )
    _validate(spec)
    return spec


def _validate(spec: RuleSpec) -> None:
    """Fail fast on a spec that could not be evaluated causally."""
    if spec.timeframe not in ("5m", "1h"):
        raise ValueError(f"{spec.sid}: unknown timeframe {spec.timeframe!r}")
    if spec.family not in FAMILIES:
        raise ValueError(f"{spec.sid}: unknown family {spec.family!r} "
                         f"(allowed: {', '.join(FAMILIES)})")
    if spec.side not in SIDES:
        raise ValueError(f"{spec.sid}: unknown side {spec.side!r} "
                         f"(allowed: {', '.join(SIDES)})")
    if spec.horizon not in HORIZONS:
        raise ValueError(f"{spec.sid}: unknown horizon {spec.horizon!r} "
                         f"(allowed: {', '.join(HORIZONS)})")
    if not spec.enter_long and not spec.enter_short:
        raise ValueError(f"{spec.sid}: a spec must enter on at least one side")
    known = set(spec.columns)
    for side, conds in (("enter_long", spec.enter_long),
                        ("enter_short", spec.enter_short),
                        ("exit_long", spec.exit_long),
                        ("exit_short", spec.exit_short)):
        for left, op, right in conds:
            if left not in known:
                raise ValueError(f"{spec.sid}.{side}: condition reads column "
                                 f"{left!r} which is not in `columns`")
            if isinstance(right, str) and right not in known:
                raise ValueError(f"{spec.sid}.{side}: condition compares against "
                                 f"column {right!r} which is not in `columns`")


def load_specs(path: str | Path = DEFAULT_SPEC_PATH) -> dict[str, RuleSpec]:
    """Load the spec catalogue from a YAML file.

    Returns a mapping keyed by :attr:`RuleSpec.key` (``"s113"``). A missing
    file yields an empty mapping — callers decide whether that is an error.
    """
    p = Path(path)
    if not p.exists():
        return {}
    data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    raw_specs = data.get("strategies") or {}
    if not isinstance(raw_specs, Mapping):
        raise ValueError(f"{p}: `strategies:` must be a mapping of id -> spec")
    out: dict[str, RuleSpec] = {}
    for sid, raw in raw_specs.items():
        spec = spec_from_dict(raw)
        if spec.key in out:
            raise ValueError(f"{p}: duplicate strategy key {spec.key!r}")
        out[spec.key] = spec
    return out


def load_spec(path: str | Path, key: str) -> RuleSpec:
    """Load one spec by id (``"S-113"``, ``"s113"`` or ``"113"``)."""
    specs = load_specs(path)
    want = str(key).lower().replace("-", "")
    if want.startswith("s"):
        want = "s" + want[1:].lstrip("0").rjust(3, "0")
    else:
        want = "s" + want.zfill(3)
    try:
        return specs[want]
    except KeyError as exc:
        raise SystemExit(f"Unknown strategy {key!r} (not in {path})") from exc


def signal_identity(spec: RuleSpec) -> dict:
    """The signal-only projection of a spec.

    This is what an OOS ``config_hash`` must be built from: the fields that
    decide what is traded. Annotation (family / role / side / horizon /
    lineage) is deliberately excluded so that relabelling a strategy never
    invalidates a pinned or already-adjudicated run.
    """
    return {field: getattr(spec, field) for field in SIGNAL_FIELDS}


def spec_rows(specs: Mapping[str, RuleSpec]) -> list[str]:
    """A compact, stable text rendering of the catalogue (for reports)."""
    lines = ["| id | family | side | horizon | role | hypothesis |",
             "| --- | --- | --- | --- | --- | --- |"]
    for spec in sorted(specs.values(), key=lambda s: s.sid):
        lines.append(f"| {spec.sid} | {spec.family} | {spec.side} | {spec.horizon} "
                     f"| {spec.role or '-'} | {spec.hypothesis} |")
    return lines


__all__ = [
    "CONDITION_OPS",
    "Condition",
    "DEFAULT_SPEC_PATH",
    "FAMILIES",
    "HORIZONS",
    "RuleSpec",
    "SERIES_OPS",
    "SIGNAL_FIELDS",
    "SIDES",
    "load_spec",
    "load_specs",
    "signal_identity",
    "spec_from_dict",
    "spec_rows",
]
