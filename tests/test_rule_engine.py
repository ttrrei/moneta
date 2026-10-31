"""Contract tests for the declarative rule layer.

What is locked here
-------------------
1. **The migration is exact.** The S-113..S-132 catalogue moved from Python
   literals to ``config/strategy_specs.yml``. A golden digest of the
   *signal* fields pins the result, so a stray edit to a migrated spec fails
   the build instead of silently changing a strategy.
2. **The vectorised path equals the per-bar path.** The vectorised
   evaluation in :mod:`strategy.rule_engine` is only allowed to exist if it
   reproduces the original per-bar state machine *bar for bar* — on random
   data, on data with missing values, and on every one of the twenty
   registered specs.
3. **The engine's positions fast path equals the rule path.** A pre-computed
   position array must produce byte-identical metrics, because that array is
   what makes a cost-tier sweep cheap.
4. **Causality survives vectorisation.** Perturbing the future cannot change
   a past decision.
"""

from __future__ import annotations

import hashlib
import json
import time

import numpy as np
import pytest

from strategy import rule_spec as rule_spec_mod
from strategy.engine import BarFrame, run_backtest
from strategy.rule_engine import (ReferenceRuleState, positions_from_spec,
                               positions_from_spec_events)
from strategy.rule_spec import RuleSpec, load_specs, signal_identity
from strategy.strategy_diverse_lib import RULES

SPECS_PATH = "config/strategy_specs.yml"

#: sha256 of the catalogue's signal fields, captured while the twenty rules
#: still lived in ``strategy/strategy_diverse_lib.py`` as Python literals.
#: Any drift in the YAML migration breaks this.
GOLDEN_CATALOGUE_DIGEST = (
    "6892a52c9864c85091ba1de73b4f8cf1fe24e9bfccc5c2347a3229439732796c"
)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _random_values(spec: RuleSpec, length: int, seed: int) -> dict[str, np.ndarray]:
    """Deterministic pseudo-random feature values for a spec."""
    rng = np.random.default_rng(seed)
    values: dict[str, np.ndarray] = {}
    for index, column in enumerate(spec.columns):
        series = rng.normal(0.0, 1.0, length)
        # Give every column its own scale so "above 20" style thresholds are
        # sometimes true and sometimes false — the interesting case.
        series = series * (5.0 + index * 3.0) + (index * 1.5)
        values[column] = series
    return values


def _catalogue_digest(specs: dict[str, RuleSpec]) -> str:
    payload = {spec.sid: signal_identity(spec) for spec in sorted(specs.values(),
                                                                  key=lambda s: s.sid)}
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=list)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# 1. the migration is exact
# ---------------------------------------------------------------------------

def test_catalogue_matches_the_golden_digest():
    """The YAML catalogue is byte-identical to the pre-migration literals."""
    assert _catalogue_digest(RULES) == GOLDEN_CATALOGUE_DIGEST


def test_catalogue_still_holds_exactly_the_pre_registered_batch():
    assert len(RULES) == 20
    assert {spec.sid for spec in RULES.values()} == {
        f"S-{number}" for number in range(113, 133)
    }


def test_every_spec_declares_its_hypothesis_axes():
    """A spec without a hypothesis, a role or a family cannot be iterated on."""
    for spec in RULES.values():
        assert spec.hypothesis, spec.sid
        assert spec.difference, spec.sid
        assert spec.expected_trades, spec.sid
        assert spec.family != "unspecified", spec.sid
        assert spec.role, spec.sid
        assert spec.side in ("long", "short", "both"), spec.sid


def test_signal_identity_ignores_annotation():
    """Re-labelling a spec must not change the identity of its OOS run."""
    spec = RULES["s113"]
    relabelled = spec.with_params(family="reversion", role="something else",
                                   rationale="a new note", mutation="seasonal_mask")
    assert signal_identity(spec) == signal_identity(relabelled)
    assert relabelled.family != spec.family
    assert relabelled.role != spec.role
    assert relabelled.mutation == "seasonal_mask"


# ---------------------------------------------------------------------------
# 2. the vectorised path equals the per-bar path
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("key", sorted(RULES))
def test_vectorised_matches_the_per_bar_oracle(key):
    spec = RULES[key]
    values = _random_values(spec, 400, seed=abs(hash(key)) % 10_000)
    reference = ReferenceRuleState(spec, values).positions()
    vectorised = positions_from_spec(spec, values)
    assert np.array_equal(reference, vectorised), key


@pytest.mark.parametrize("key", sorted(RULES))
def test_fast_path_matches_the_readable_event_walk(key):
    """The fast (list-indexed) path and the readable path must agree exactly."""
    spec = RULES[key]
    values = _random_values(spec, 400, seed=(abs(hash(key)) + 1) % 10_000)
    assert np.array_equal(positions_from_spec(spec, values),
                          positions_from_spec_events(spec, values)), key


@pytest.mark.parametrize("key", sorted(RULES))
def test_vectorised_matches_the_oracle_with_missing_values(key):
    """A NaN anywhere in the inputs must hold the position, not break it."""
    spec = RULES[key]
    values = _random_values(spec, 300, seed=(abs(hash(key)) + 7) % 10_000)
    rng = np.random.default_rng(99)
    for column in spec.columns:
        holes = rng.choice(len(values[column]), size=12, replace=False)
        values[column][holes] = np.nan
    reference = ReferenceRuleState(spec, values).positions()
    vectorised = positions_from_spec(spec, values)
    assert np.array_equal(reference, vectorised), key


def test_vectorised_matches_the_oracle_on_a_synthetic_cross():
    """The S-113 Aroon/ADX scenario from tests/test_strategy_diverse.py."""
    spec = RULES["s113"]
    values = {
        "aroon_up_24": np.array([10.0, 20.0, 20.0, 10.0, 20.0]),
        "aroon_down_24": np.array([20.0, 10.0, 10.0, 20.0, 10.0]),
        "adx_24": np.array([30.0, 30.0, 30.0, 30.0, 30.0]),
    }
    reference = ReferenceRuleState(spec, values).positions()
    assert np.array_equal(reference, positions_from_spec(spec, values))
    assert list(reference) == [0, 0, 1, 1, -1]


def test_vectorised_is_much_faster_than_the_per_bar_oracle():
    """The reason this module exists: the per-bar call is the hot loop."""
    spec = RULES["s117"]
    length = 40_000
    values = _random_values(spec, length, seed=5)

    start = time.perf_counter()
    ReferenceRuleState(spec, values).positions()
    reference_seconds = time.perf_counter() - start

    start = time.perf_counter()
    positions_from_spec(spec, values)
    vectorised_seconds = time.perf_counter() - start

    assert vectorised_seconds * 5 < reference_seconds, (
        f"vectorised path is not faster: {vectorised_seconds:.4f}s vs "
        f"{reference_seconds:.4f}s"
    )


# ---------------------------------------------------------------------------
# 3. causality survives vectorisation
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("key", sorted(RULES))
def test_vectorised_positions_are_causal(key):
    """A decision on bar i may not depend on anything after bar i."""
    spec = RULES[key]
    values = _random_values(spec, 120, seed=(abs(hash(key)) + 3) % 10_000)
    baseline = positions_from_spec(spec, values)
    for cut in (1, 5, 30, 90):
        changed = {name: array.copy() for name, array in values.items()}
        for array in changed.values():
            array[cut:] = 1000.0
        assert np.array_equal(baseline[:cut + 1], positions_from_spec(spec, changed)[:cut + 1]), (
            key, cut)


# ---------------------------------------------------------------------------
# 4. the engine's positions fast path equals the rule path
# ---------------------------------------------------------------------------

def _bars(length: int = 500, seed: int = 3) -> BarFrame:
    rng = np.random.default_rng(seed)
    base = 100.0 + np.cumsum(rng.normal(0.0, 0.2, length))
    open_ = np.concatenate(([base[0]], base[:-1]))
    return BarFrame(open=open_, close=base, time=None, bar_seconds=300)


def test_engine_positions_path_matches_the_rule_path():
    spec = RULES["s113"]
    length = 500
    values = _random_values(spec, length, seed=11)
    bars = _bars(length)

    rule = ReferenceRuleState(spec, values)
    from_rule = run_backtest(bars, rule, cost_bps=2.0, long_only=False)
    from_positions = run_backtest(bars, None, cost_bps=2.0, long_only=False,
                                   positions=positions_from_spec(spec, values))
    assert from_rule.to_dict() == from_positions.to_dict()


def test_engine_rejects_a_mismatched_positions_array():
    bars = _bars(50)
    with pytest.raises(ValueError):
        run_backtest(bars, None, positions=np.zeros(10, dtype=np.int8))


def test_engine_requires_a_rule_or_positions():
    bars = _bars(50)
    with pytest.raises(ValueError):
        run_backtest(bars, None)


def test_long_only_clamp_applies_to_the_positions_path():
    spec = RULES["s113"]
    length = 500
    values = _random_values(spec, length, seed=13)
    bars = _bars(length)
    positions = positions_from_spec(spec, values)
    assert positions.min() == -1, "this fixture is expected to produce shorts"
    clamped = run_backtest(bars, None, cost_bps=2.0, long_only=True, positions=positions)
    reference = run_backtest(bars, ReferenceRuleState(spec, values), cost_bps=2.0,
                             long_only=True)
    assert clamped.to_dict() == reference.to_dict()


# ---------------------------------------------------------------------------
# 5. the spec loader rejects malformed specs
# ---------------------------------------------------------------------------

def test_loader_rejects_an_unknown_operator(tmp_path):
    path = tmp_path / "bad.yml"
    path.write_text(
        "strategies:\n"
        "  S-900:\n"
        "    sid: S-900\n"
        "    slug: bad\n"
        "    name: Bad\n"
        "    timeframe: 5m\n"
        "    columns: [x]\n"
        "    enter_long:\n"
        "      - [x, sideways, 1]\n",
        encoding="utf-8")
    with pytest.raises(ValueError, match="unknown condition op"):
        load_specs(path)


def test_loader_rejects_a_condition_on_an_undeclared_column(tmp_path):
    path = tmp_path / "bad.yml"
    path.write_text(
        "strategies:\n"
        "  S-900:\n"
        "    sid: S-900\n"
        "    slug: bad\n"
        "    name: Bad\n"
        "    timeframe: 5m\n"
        "    columns: [x]\n"
        "    enter_long:\n"
        "      - [y, above, 1]\n",
        encoding="utf-8")
    with pytest.raises(ValueError, match="not in `columns`"):
        load_specs(path)


def test_loader_rejects_a_spec_that_never_enters(tmp_path):
    path = tmp_path / "bad.yml"
    path.write_text(
        "strategies:\n"
        "  S-900:\n"
        "    sid: S-900\n"
        "    slug: bad\n"
        "    name: Bad\n"
        "    timeframe: 5m\n"
        "    columns: [x]\n",
        encoding="utf-8")
    with pytest.raises(ValueError, match="must enter on at least one side"):
        load_specs(path)


def test_missing_catalogue_is_an_empty_mapping_not_a_crash(tmp_path):
    assert load_specs(tmp_path / "nope.yml") == {}


def test_condition_vocabulary_is_closed():
    """The closed vocabulary is what makes vectorisation and dedup possible."""
    assert set(rule_spec_mod.CONDITION_OPS) == {
        "above", "below", "cross_up", "cross_down", "cross_above", "cross_below"
    }
