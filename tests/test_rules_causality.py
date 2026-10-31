"""Every strategy must decide bar i using only rows strictly before i."""
from __future__ import annotations

import importlib
import inspect
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from strategy.strategy_diverse_lib import DiverseRuleState, RULES
from strategy.strategy_rsi_lib import RsiState


class FeatureFrame(pd.DataFrame):
    """Deterministic synthetic columns requested by each rule's builder."""
    @property
    def _constructor(self):
        return FeatureFrame

    def __getitem__(self, key):
        if isinstance(key, str) and key not in self.columns:
            self[key] = np.random.default_rng(sum(map(ord, key))).normal(40, 60, len(self))
        return super().__getitem__(key)


LIBRARIES = sorted(path.stem for path in
                   (Path(__file__).resolve().parents[1] / "strategy").glob("strategy_*_lib.py")
                   if hasattr(importlib.import_module(f"strategy.{path.stem}"), "build_rule"))


@pytest.mark.parametrize("module_name", LIBRARIES)
def test_rule_prefix_invariant_under_future_perturbation(module_name):
    module = importlib.import_module(f"strategy.{module_name}")
    frame = FeatureFrame(index=range(50))
    for kwargs in ({}, {"ema_gate": True}) if "ema_gate" in inspect.signature(module.build_rule).parameters else ({},):
        rule = module.build_rule(frame, **kwargs)
        original = [rule.desired_position(i) for i in range(len(frame))]
        for cut in (1, 2, 10, 30):
            for replacement in (np.nan, 1000.0, -1000.0):
                changed = frame.copy()
                changed.iloc[cut:, :] = replacement
                other = module.build_rule(changed, **kwargs)
                assert original[:cut + 1] == [other.desired_position(i) for i in range(cut + 1)]


@pytest.mark.parametrize("sid", sorted(RULES))
def test_diverse_rule_prefix_invariant_with_finite_and_missing_future(sid):
    spec = RULES[sid]
    frame = FeatureFrame(index=range(50))
    arrays = {column: frame[column].to_numpy() for column in spec.columns}
    rule = DiverseRuleState(spec, arrays)
    original = [rule.desired_position(i) for i in range(50)]
    for cut in (1, 2, 10, 30):
        changed = {name: array.copy() for name, array in arrays.items()}
        for array in changed.values():
            array[cut:] = np.nan
        rule = DiverseRuleState(spec, changed)
        assert original[:cut + 1] == [rule.desired_position(i) for i in range(cut + 1)]


def test_rsi_prefix_invariant():
    values = np.array([10., 60., 20., 40., 70., 5.])
    rule = RsiState(values)
    original = [rule.desired_position(i) for i in range(len(values))]
    for cut in range(1, len(values)):
        changed = values.copy()
        changed[cut:] = 1000
        rule = RsiState(changed)
        assert original[:cut + 1] == [rule.desired_position(i) for i in range(cut + 1)]
