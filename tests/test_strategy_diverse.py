"""Contract tests for the pre-registered S-113..S-132 rule batch."""

from __future__ import annotations

import importlib
import numpy as np

from strategy.strategy_diverse_lib import DiverseRuleState, RULES


def _values(spec, length=8):
    return {name: np.ones(length, dtype=float) for name in spec.columns}


def test_batch_contains_twenty_distinct_registered_rules():
    assert len(RULES) == 20
    assert {spec.sid for spec in RULES.values()} == {
        f"S-{number}" for number in range(113, 133)
    }


def test_all_rule_conditions_use_declared_columns_and_supported_operators():
    supported = {
        "above", "below", "cross_up", "cross_down", "cross_above", "cross_below"
    }
    for spec in RULES.values():
        for condition in (
            *spec.enter_long, *spec.enter_short,
            *spec.exit_long, *spec.exit_short,
        ):
            left, operator, right = condition
            assert operator in supported, (spec.sid, condition)
            assert left in spec.columns, (spec.sid, left)
            if isinstance(right, str):
                assert right in spec.columns, (spec.sid, right)


def test_each_strategy_has_a_fixed_id_matrix_runner():
    for key, spec in RULES.items():
        module = importlib.import_module(f"strategy.strategy_{spec.slug}_lib")
        assert callable(module.run), (key, spec.slug)


def test_every_rule_is_flat_without_a_previous_bar():
    for spec in RULES.values():
        state = DiverseRuleState(spec, _values(spec))
        assert state.desired_position(0) == 0


def test_rule_decisions_are_causal_through_the_requested_bar():
    for spec in RULES.values():
        baseline = _values(spec, 12)
        changed = {key: value.copy() for key, value in baseline.items()}
        for value in changed.values():
            value[6:] = np.nan

        original_state = DiverseRuleState(spec, baseline)
        changed_state = DiverseRuleState(spec, changed)
        for index in range(7):
            assert original_state.desired_position(index) == changed_state.desired_position(index), (
                spec.sid, index
            )


def test_rule_state_remains_unchanged_on_missing_required_feature():
    for spec in RULES.values():
        values = _values(spec, 4)
        values[spec.columns[0]][1] = np.nan
        state = DiverseRuleState(spec, values)
        assert state.desired_position(2) == 0


def test_aroon_adx_rule_enters_and_exits_on_closed_bar_crosses():
    spec = RULES["s113"]
    values = {
        "aroon_up_24": np.array([10.0, 20.0, 20.0, 10.0, 20.0]),
        "aroon_down_24": np.array([20.0, 10.0, 10.0, 20.0, 10.0]),
        "adx_24": np.array([30.0, 30.0, 30.0, 30.0, 30.0]),
    }
    state = DiverseRuleState(spec, values)
    assert state.desired_position(1) == 0
    assert state.desired_position(2) == 1
    assert state.desired_position(3) == 1
    assert state.desired_position(4) == -1
    assert state.desired_position(5) == 1


def test_aroon_adx_rule_can_enter_and_exit_short():
    spec = RULES["s113"]
    values = {
        "aroon_up_24": np.array([20.0, 10.0, 10.0, 20.0, 10.0]),
        "aroon_down_24": np.array([10.0, 20.0, 20.0, 10.0, 20.0]),
        "adx_24": np.array([30.0, 30.0, 30.0, 30.0, 30.0]),
    }
    state = DiverseRuleState(spec, values)
    assert state.desired_position(2) == -1
    assert state.desired_position(3) == -1
    assert state.desired_position(4) == 1
    assert state.desired_position(5) == -1
