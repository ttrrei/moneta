"""Vectorised evaluation of a :class:`~strategy.rule_spec.RuleSpec`.

Why this module exists
----------------------
The reference implementation of a spec's state machine
(:class:`ReferenceRuleState`) asks the rule "what is your position on bar
``i``?" once per bar, from Python. That is correct but it is the single
biggest cost in the repository:

* 5-minute data is ~100k bars per instrument per year;
* a full sweep is (strategies x variants x instruments x windows x cost tiers);
* every one of those cells re-ran a Python-level loop with a NumPy *scalar*
  comparison inside it.

At the scale of the current catalogue that is billions of interpreted
iterations, and it is why "one more iteration" felt expensive.

This module computes the **same** positions array with vectorised NumPy. The
trick that makes it exact (not an approximation) is a small observation about
the state machine: **the position can only change on a bar where at least one
of the four condition groups is satisfied.** Everywhere else the machine
either holds (non-finite input) or does nothing. So:

1. compute the four boolean masks (``enter_long`` / ``enter_short`` /
   ``exit_long`` / ``exit_short``) for *all* bars at once;
2. find the *event* bars — where any mask is true and the inputs are finite;
3. run the state machine over the (usually far shorter) event list;
4. expand the result back to every bar.

That is the "space for time" trade: a few boolean arrays of length ``n``
(~100 KB each at 5m scale) replace a per-bar Python call, and the *signal
array is materialised once* and can be reused across every cost tier instead
of being recomputed.

Equivalence
-----------
:class:`ReferenceRuleState` is kept in this module as the **oracle**: it is
the original per-bar implementation, unchanged. ``tests/test_rule_engine.py``
asserts that the vectorised path reproduces it bar for bar on both synthetic
and randomised inputs. If you change one, change the other and re-run that
test — the two are a matched pair.
"""

from __future__ import annotations

import numpy as np

from strategy.rule_spec import Condition, RuleSpec

#: The four condition groups of a spec, in the order the state machine reads
#: them.
_GROUPS = ("enter_long", "enter_short", "exit_long", "exit_short")


# ---------------------------------------------------------------------------
# Vectorised condition masks
# ---------------------------------------------------------------------------

def _shift(arr: np.ndarray) -> np.ndarray:
    """``arr`` shifted one bar to the right; position 0 becomes NaN.

    The NaN at index 0 is what makes every cross condition false on the
    first bar — the reference implementation returns ``False`` for ``j < 1``.
    """
    out = np.full_like(arr, np.nan, dtype=np.float64)
    if arr.size > 1:
        out[1:] = arr[:-1]
    return out


def condition_mask(values: dict[str, np.ndarray], condition: Condition) -> np.ndarray:
    """Evaluate one condition over every bar at once.

    Returns a boolean array of the same length as the input series. The
    semantics match :meth:`ReferenceRuleState._matches` exactly, including
    the "a non-finite value blocks the condition" rule and the "a cross needs
    a previous bar" rule.
    """
    left, op, right = condition
    a = values[left]
    finite_a = np.isfinite(a)
    if isinstance(right, str):
        b = values[right]
        finite_b = np.isfinite(b)
    else:
        b = float(right)
        finite_b = np.ones(a.shape, dtype=bool)

    if op in ("cross_up", "cross_down", "cross_above", "cross_below"):
        pa = _shift(a)
        finite_pa = np.isfinite(pa)
        if isinstance(right, str):
            pb = _shift(b)
            finite_pb = np.isfinite(pb)
        else:
            pb = b
            finite_pb = np.ones(a.shape, dtype=bool)
        if op == "cross_up":       # a[j] > b[j] and a[j-1] <= b[j]
            return finite_a & finite_b & finite_pa & (a > b) & (pa <= b)
        if op == "cross_down":     # a[j] < b[j] and a[j-1] >= b[j]
            return finite_a & finite_b & finite_pa & (a < b) & (pa >= b)
        if op == "cross_above":    # a[j] > b[j] and a[j-1] <= b[j-1]
            return finite_a & finite_b & finite_pa & finite_pb & (a > b) & (pa <= pb)
        # cross_below: a[j] < b[j] and a[j-1] >= b[j-1]
        return finite_a & finite_b & finite_pa & finite_pb & (a < b) & (pa >= pb)

    if op == "above":
        return finite_a & finite_b & (a > b)
    if op == "below":
        return finite_a & finite_b & (a < b)
    raise ValueError(f"Unknown strategy condition {op!r}")


def _group_mask(values: dict[str, np.ndarray], conditions: tuple[Condition, ...]) -> np.ndarray:
    """AND of every condition in a group; an empty group is never satisfied."""
    if not conditions:
        return np.zeros(len(next(iter(values.values()))), dtype=bool)
    mask = condition_mask(values, conditions[0])
    for condition in conditions[1:]:
        mask &= condition_mask(values, condition)
    return mask


def spec_masks(spec: RuleSpec, values: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    """The four condition-group masks plus the "usable bar" mask."""
    usable = np.ones(len(values[spec.columns[0]]), dtype=bool)
    for column in spec.columns:
        usable &= np.isfinite(values[column])
    masks = {"usable": usable}
    for group in _GROUPS:
        masks[group] = _group_mask(values, getattr(spec, group))
    return masks


# ---------------------------------------------------------------------------
# The state machine
# ---------------------------------------------------------------------------

def positions_from_spec(spec: RuleSpec, values: dict[str, np.ndarray]) -> np.ndarray:
    """The desired position for every bar, computed vectorised.

    Returns an ``int8`` array of length ``n`` where element ``i`` is the
    position intended at the **open of bar ``i``**, derived from the *closed*
    bar ``i-1``. That is exactly the array
    :func:`strategy.engine.run_backtest` would have built by calling
    ``rule.desired_position(i)`` for every ``i`` — and it is the array the
    engine can reuse across cost tiers without recomputing anything.

    How it stays exact *and* fast
    -----------------------------
    Two observations do all the work:

    1. **A position can only change on a bar where a condition group
       fires.** Everywhere else the machine either holds (a non-finite
       input) or does nothing. So the four group masks are computed for
       *all* bars at once, and only the bars where at least one group fires
       need to be visited individually.
    2. **The loop should touch Python objects, not NumPy scalars.** A NumPy
       scalar index costs ~0.5 us; a Python list element costs ~0.03 us.
       Converting the event masks to lists once turns the inner loop into
       plain Python and is worth roughly a factor of two on top of the
       vectorisation.

    The result is identical to the per-bar oracle — bar for bar — which
    ``tests/test_rule_engine.py`` asserts on random data, on data with
    missing values, and on every registered spec.

    :func:`positions_from_spec_events` is the same algorithm written with
    NumPy scalar indexing. It is kept as an independent cross-check: the
    test suite asserts that the two agree, so neither can drift silently.
    """
    n = len(values[spec.columns[0]])
    masks = spec_masks(spec, values)
    usable = masks["usable"]
    enter_long = masks["enter_long"]
    enter_short = masks["enter_short"]
    exit_long = masks["exit_long"]
    exit_short = masks["exit_short"]

    # Bars where *any* group fires — the only bars a transition can happen on.
    events = np.flatnonzero(usable & (enter_long | enter_short | exit_long | exit_short))
    if events.size == 0:
        return np.zeros(n, dtype=np.int8)

    el = enter_long[events].tolist()
    es = enter_short[events].tolist()
    xl = exit_long[events].tolist()
    xs = exit_short[events].tolist()

    state = np.zeros(n, dtype=np.int8)
    position = 0
    previous = -1
    for index, bar in enumerate(events.tolist()):
        if previous >= 0 and bar > previous + 1:
            state[previous + 1:bar] = position
        if position == 0:
            if el[index]:
                position = 1
            elif es[index]:
                position = -1
        elif position > 0:
            if xl[index]:
                position = -1 if es[index] else 0
        else:
            if xs[index]:
                position = 1 if el[index] else 0
        state[bar] = position
        previous = bar
    if previous >= 0 and previous + 1 < n:
        state[previous + 1:] = position

    # desired[i] is the state after processing closed bar i-1.
    desired = np.zeros(n, dtype=np.int8)
    if n > 1:
        desired[1:] = state[:-1]
    return desired


def positions_from_spec_events(spec: RuleSpec, values: dict[str, np.ndarray]) -> np.ndarray:
    """A deliberately simple, event-by-event evaluation of a spec.

    This is the *readable* implementation of :func:`positions_from_spec`: it
    walks every event bar and applies the state machine directly. It is kept
    because it is much easier to audit than the chain walk, and the test
    suite asserts that the two agree bar for bar.
    """
    n = len(values[spec.columns[0]])
    masks = spec_masks(spec, values)
    usable = masks["usable"]
    enter_long = masks["enter_long"]
    enter_short = masks["enter_short"]
    exit_long = masks["exit_long"]
    exit_short = masks["exit_short"]

    events = np.flatnonzero(usable & (enter_long | enter_short | exit_long | exit_short))

    state = np.zeros(n, dtype=np.int8)
    position = 0
    previous = -1
    for j in events:
        if previous >= 0:
            state[previous + 1:j] = position
        if position == 0:
            if enter_long[j]:
                position = 1
            elif enter_short[j]:
                position = -1
        elif position > 0:
            if exit_long[j]:
                position = -1 if enter_short[j] else 0
        else:
            if exit_short[j]:
                position = 1 if enter_long[j] else 0
        state[j] = position
        previous = j
    if previous >= 0:
        state[previous + 1:] = position

    desired = np.zeros(n, dtype=np.int8)
    if n > 1:
        desired[1:] = state[:-1]
    return desired


# ---------------------------------------------------------------------------
# The reference oracle (per-bar, unchanged)
# ---------------------------------------------------------------------------

class ReferenceRuleState:
    """The original per-bar state machine — kept as the equivalence oracle.

    This is the implementation the vectorised path replaced at the call site.
    It is **not** dead code: ``tests/test_rule_engine.py`` drives it and
    :func:`positions_from_spec` against each other, so the two can never
    drift apart silently.
    """

    def __init__(self, spec: RuleSpec, values: dict[str, np.ndarray]) -> None:
        self.spec = spec
        self.values = values
        self.position = 0

    def _matches(self, condition: Condition, j: int) -> bool:
        left, op, right = condition
        a = self.values[left][j]
        if not np.isfinite(a):
            return False
        if isinstance(right, str):
            b = self.values[right][j]
            if not np.isfinite(b):
                return False
        else:
            b = float(right)
        if op in {"cross_up", "cross_down", "cross_above", "cross_below"}:
            if j < 1:
                return False
            pa = self.values[left][j - 1]
            if not np.isfinite(pa):
                return False
            if isinstance(right, str):
                pb = self.values[right][j - 1]
                if not np.isfinite(pb):
                    return False
            else:
                pb = float(right)
            if op == "cross_up":
                return a > b and pa <= b
            if op == "cross_down":
                return a < b and pa >= b
            if op == "cross_above":
                return a > b and pa <= pb
            return a < b and pa >= pb
        if op == "above":
            return a > b
        if op == "below":
            return a < b
        raise ValueError(f"Unknown strategy condition {op!r}")

    def _all(self, conditions: tuple[Condition, ...], j: int) -> bool:
        return all(self._matches(condition, j) for condition in conditions)

    def desired_position(self, i: int) -> int:
        if i <= 0:
            return 0
        j = i - 1
        if any(not np.isfinite(self.values[col][j]) for col in self.spec.columns):
            return self.position
        if self.position == 0:
            if self._all(self.spec.enter_long, j):
                self.position = 1
            elif self._all(self.spec.enter_short, j):
                self.position = -1
        elif self.position > 0 and self._all(self.spec.exit_long, j):
            self.position = -1 if self._all(self.spec.enter_short, j) else 0
        elif self.position < 0 and self._all(self.spec.exit_short, j):
            self.position = 1 if self._all(self.spec.enter_long, j) else 0
        return self.position

    def positions(self) -> np.ndarray:
        """The full desired-position array, computed bar by bar."""
        n = len(self.values[self.spec.columns[0]])
        return np.array([self.desired_position(i) for i in range(n)], dtype=np.int8)


__all__ = [
    "ReferenceRuleState",
    "condition_mask",
    "positions_from_spec",
    "positions_from_spec_events",
    "spec_masks",
]
