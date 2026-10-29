"""Golden-value tests for the shared backtest engine (:mod:`strategy.engine`).

These lock the *metric definitions* (SAD §7.2 / engine ``METRIC_FORMULAS``) so
they can no longer drift between strategies. They are pure (no data, no network,
no talib) and run in any environment / CI.

Key regression covered here: the old reference ``sharpe`` was
``mean(tr)/std(tr) * sqrt(n_trades * 12)`` — a number that *grows with the
number of trades*. These tests pin the corrected, annualised-by-trading-rate
Sharpe and prove it is independent of sample length at a fixed rate (same edge,
same trades/yr, longer sample → same Sharpe).

.. note::
   "Rate-based" does NOT mean "comparable across strategies": because the
   metric scales with trades/year, two strategies with the same per-trade edge
   but different trade counts get different Sharpes (the higher-frequency one
   scores higher). ``test_sharpe_depends_on_trades_per_year`` therefore pins
   that frequency-dependent behaviour as a *known property*, not a bug — and
   the metric must not be used to rank strategies against each other.
"""

from __future__ import annotations

import json

import numpy as np
import pytest

from strategy.engine import (
    BarFrame,
    FlatRule,
    annualised_sharpe,
    run_backtest,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _bars(open_, close, bar_seconds: int = 300) -> BarFrame:
    o = np.asarray(open_, dtype=np.float64)
    c = np.asarray(close, dtype=np.float64)
    return BarFrame(open=o, close=c, time=None, bar_seconds=bar_seconds)


def _always_long() -> object:
    """A rule that is long from the very first bar's open to the last bar."""
    class _Long:
        def desired_position(self, i: int) -> int:
            return 1
    return _Long()


def _always_short() -> object:
    class _Short:
        def desired_position(self, i: int) -> int:
            return -1
    return _Short()


def _tug_of_war() -> object:
    """Flip between long and short every bar: a fully-known, deterministic
    round-trip sequence with no overlap. Used for exact-value checks."""
    class _Flip:
        def desired_position(self, i: int) -> int:
            return 1 if (i % 2 == 0) else -1
    return _Flip()


# ---------------------------------------------------------------------------
# annualised_sharpe — the B2 regression, stated directly
# ---------------------------------------------------------------------------

def test_sharpe_is_invariant_to_sample_length():
    """The *same* per-trade edge at the *same* trading rate (trades/year), over
    a longer sample, gives (approximately) the *same* annualised Sharpe — it
    depends on the rate, not the total count. This is the B2 fix made concrete.

    Tolerance is loose (the *sample* std with ddof=1 has finite-sample noise as
    n grows) but tight enough that the OLD formula — which scales by
    ``sqrt(n_trades)`` and therefore differs by ``sqrt(n_b/n_a)`` — fails it.
    """
    edge = np.array([0.001, -0.0008, 0.0012, -0.0005, 0.0009, -0.0003])
    a = list(edge) * 20                 # 120 trades / 5 yr  = 24 trades/yr
    b = list(edge) * 40                 # 240 trades / 10 yr = 24 trades/yr
    span_a, span_b = 5.0, 10.0
    assert len(a) / span_a == pytest.approx(len(b) / span_b, rel=1e-12)

    new_a = annualised_sharpe(a, span_a)
    new_b = annualised_sharpe(b, span_b)
    # Approximately invariant to sample length (same rate, same edge).
    assert new_a == pytest.approx(new_b, rel=0.05)

    # The OLD (B2) formula is NOT approximately invariant: it scales by sqrt(n),
    # so the longer sample's value is sqrt(n_b/n_a) = sqrt(2) times larger.
    old = lambda xs: float(np.mean(xs) / np.std(xs, ddof=1) * np.sqrt(len(xs) * 12))
    assert old(a) == pytest.approx(old(b) / np.sqrt(2), rel=0.05)


def test_sharpe_depends_on_trades_per_year():
    """Same number of trades, but a longer span (fewer trades/year) → lower
    annualised Sharpe. Confirms the scaling is by the *rate*, not the count."""
    edge = [0.001, -0.0008, 0.0012, -0.0005, 0.0009, -0.0003]
    s_dense = annualised_sharpe(edge, span_years=1.0)   # 6 trades/yr
    s_sparse = annualised_sharpe(edge, span_years=4.0)  # 1.5 trades/yr
    assert s_dense == pytest.approx(s_sparse * 2.0, rel=1e-9)  # sqrt(4/1) = 2


def test_sharpe_zero_when_under_two_trades_or_zero_std():
    assert annualised_sharpe([0.001], 1.0) == 0.0
    assert annualised_sharpe([], 1.0) == 0.0
    assert annualised_sharpe([0.0, 0.0], 1.0) == 0.0  # std == 0


# ---------------------------------------------------------------------------
# Deterministic accounting — exact values on a known price path
# ---------------------------------------------------------------------------

def test_flat_rule_produces_no_trades_and_zero_return():
    bars = _bars(open_=[100.0, 101.0, 102.0], close=[101.0, 102.0, 103.0])
    res = run_backtest(bars, FlatRule(), cost_bps=0.0)
    assert res.n_trades == 0
    assert res.raw_total_return_pct == 0.0
    assert res.raw_sharpe == 0.0
    assert res.raw_max_drawdown_pct == 0.0


def test_single_long_round_trip_exact_value():
    """Enter long at bar 0 open (100), exit long at bar 2 open (102) → one
    round-trip with return (102*(1-c))/(100*(1+c)) - 1 exactly.

    At cost 0 that is 2.0%; at cost 2 bps it is (102/100)/(1+0.0002)^2 - 1.
    """
    open_ = [100.0, 101.0, 102.0]
    close = [101.0, 102.0, 103.0]

    class _EnterExit:
        # long at bar0 and bar1 open; flat at bar2 open (exit).
        def desired_position(self, i: int) -> int:
            return 1 if i < 2 else 0

    # cost = 0
    res0 = run_backtest(_bars(open_, close), _EnterExit(), cost_bps=0.0)
    assert res0.n_trades == 1
    assert res0.raw_total_return_pct == pytest.approx(2.0, rel=1e-12)
    assert res0.raw_avg_trade_return_pct == pytest.approx(2.0, rel=1e-12)
    assert res0.raw_buyhold_return_pct == pytest.approx((103.0 / 100.0 - 1.0) * 100, rel=1e-12)

    # cost = 2 bps (one-way)
    c = 2.0 / 10_000.0
    expected = 102.0 * (1 - c) / (100.0 * (1 + c)) - 1.0
    res2 = run_backtest(_bars(open_, close), _EnterExit(), cost_bps=2.0)
    assert res2.n_trades == 1
    assert res2.raw_total_return_pct == pytest.approx(expected * 100, rel=1e-12)


def test_short_side_symmetry():
    """A short entered at 100 (bar0 open) and exited at 98 (bar2 open) earns
    ``entry/exit - 1`` = 100/98 - 1 at cost 0 — the mirror image of the long
    case, in the opposite direction."""
    open_ = [100.0, 99.0, 98.0]
    close = [99.0, 98.0, 97.0]

    class _Short:
        def desired_position(self, i: int) -> int:
            return -1 if i < 2 else 0

    res = run_backtest(_bars(open_, close), _Short(), cost_bps=0.0)
    assert res.n_trades == 1
    assert res.trades[0].direction == -1
    assert res.raw_total_return_pct == pytest.approx((100.0 / 98.0 - 1.0) * 100, rel=1e-12)


def test_short_cost_direction():
    """With non-zero cost the short return must be *lower* than the cost-free
    one (sell at px_entry*(1-cost), buy back at px_exit*(1+cost)). The pre-fix
    formula px_entry*(1+cost)/(px_exit*(1-cost)) - 1 inverted this: higher
    cost gave a HIGHER short return (legacy review 1.2)."""
    open_ = [100.0, 99.0, 98.0]
    close = [99.0, 98.0, 97.0]

    class _Short:
        def desired_position(self, i: int) -> int:
            return -1 if i < 2 else 0

    c = 2.0 / 10_000.0
    expected = 100.0 * (1 - c) / (98.0 * (1 + c)) - 1.0
    res = run_backtest(_bars(open_, close), _Short(), cost_bps=2.0)
    assert res.raw_total_return_pct == pytest.approx(expected * 100, rel=1e-12)
    # Cost must reduce, not increase, the short profit (100 -> 98 is a win).
    res0 = run_backtest(_bars(open_, close), _Short(), cost_bps=0.0)
    assert res.raw_total_return_pct < res0.raw_total_return_pct


def test_long_only_clamps_shorts():
    bars = _bars([100.0, 99.0, 98.0], [99.0, 98.0, 97.0])
    # _always_short wants to be short every bar; long_only must clamp to flat.
    res = run_backtest(bars, _always_short(), cost_bps=0.0, long_only=True)
    assert res.n_trades == 0
    assert res.raw_total_return_pct == 0.0


# ---------------------------------------------------------------------------
# mean_net_position_pct (repo_review_20261029 §2.2) — the time-weighted
# *signed* mean position. Report-only (a sanity check next to buy-hold's
# +100% exposure); must NOT change any pre-existing metric.
# ---------------------------------------------------------------------------

def _rule(positions: list[int]) -> object:
    """A rule whose desired position is a fixed per-bar list (length n)."""
    class _R:
        def desired_position(self, i: int) -> int:
            return int(positions[i])
    return _R()


def test_mean_net_position_long_only():
    """Long every bar → signed mean is +100% (full, one-sided long)."""
    bars = _bars([100.0, 101.0, 102.0], [101.0, 102.0, 105.0])
    res = run_backtest(bars, _always_long(), cost_bps=0.0)
    assert res.raw_mean_net_position_pct == pytest.approx(100.0, rel=1e-12)
    # Full long → exposure (fraction non-zero) is also 100%.
    assert res.raw_exposure_pct == pytest.approx(100.0, rel=1e-12)


def test_mean_net_position_short_only():
    """Short every bar → signed mean is -100% (the SIGN is what exposure
    cannot see)."""
    bars = _bars([100.0, 99.0, 98.0], [99.0, 98.0, 97.0])
    res = run_backtest(bars, _always_short(), cost_bps=0.0)
    assert res.raw_mean_net_position_pct == pytest.approx(-100.0, rel=1e-12)
    # Exposure is still 100% (all bars non-zero) — the two differ by sign.
    assert res.raw_exposure_pct == pytest.approx(100.0, rel=1e-12)


def test_mean_net_position_flat():
    """Never in the market → signed mean is 0 and exposure is 0."""
    bars = _bars([100.0, 101.0, 102.0], [101.0, 102.0, 103.0])
    res = run_backtest(bars, _rule([0, 0, 0]), cost_bps=0.0)
    assert res.raw_mean_net_position_pct == pytest.approx(0.0, abs=1e-12)
    assert res.raw_exposure_pct == pytest.approx(0.0, abs=1e-12)
    assert res.n_trades == 0


def test_mean_net_position_mixed_differs_from_exposure():
    """Long 2 bars, short 1 bar: signed mean = (1+1-1)/3 = +33.33%, while
    exposure (all bars non-zero) is 100%. Proves mean_net_position_pct is
    NOT redundant with exposure_pct (review §2.2)."""
    bars = _bars([100.0, 101.0, 102.0], [101.0, 102.0, 103.0])
    res = run_backtest(bars, _rule([1, 1, -1]), cost_bps=0.0)
    assert res.raw_mean_net_position_pct == pytest.approx(100.0 / 3.0, rel=1e-12)
    assert res.raw_exposure_pct == pytest.approx(100.0, rel=1e-12)
    assert res.mean_net_position_pct != res.exposure_pct


def test_mean_net_position_added_changes_no_existing_metric():
    """§2.2 'additive only': the new field must not perturb any pre-existing
    metric. A fixed known case pins the legacy values."""
    open_ = [100.0, 101.0, 102.0]
    close = [101.0, 102.0, 105.0]
    res = run_backtest(_bars(open_, close), _always_long(), cost_bps=0.0)
    # entry@100 (bar0 open), force-closed at close[2]=105 → +5%
    assert res.raw_total_return_pct == pytest.approx(5.0, rel=1e-12)
    assert res.raw_exposure_pct == pytest.approx(100.0, rel=1e-12)
    assert res.n_trades == 1
    assert res.n_bars == 3
    # The new field is present and correct, independent of the above.
    assert res.raw_mean_net_position_pct == pytest.approx(100.0, rel=1e-12)
    # And it is exported by to_dict (CSV/JSON contract).
    assert "mean_net_position_pct" in res.to_dict()


def test_force_close_at_last_bar_books_the_open_trade():
    """If we are still long at the end, the open position must be force-closed
    and counted as a trade (no unbooked return)."""
    open_ = [100.0, 101.0, 102.0]
    close = [101.0, 102.0, 105.0]  # rally to the end
    res = run_backtest(_bars(open_, close), _always_long(), cost_bps=0.0)
    assert res.n_trades == 1  # the single open position, force-closed at bar 2 close
    # entry at 100 (bar0 open), exit at 105 (bar2 close): +5%
    assert res.raw_total_return_pct == pytest.approx(5.0, rel=1e-12)
    assert res.raw_exposure_pct == pytest.approx(100.0, rel=1e-12)


def test_signal_on_closed_bar_fills_at_next_open():
    """A rule that decides from bar ``i-1``'s close is filled at bar ``i``'s
    open. The rule is long at the open of bar 1 (entry at open[1]=101) and
    stays long; the single open position is force-closed at the last close
    (close[2]=103). It must NOT enter at bar 0 (no prior close to signal from).

    So the one trade is: entry 101, exit 103 → 103*(1-c)/(101*(1+c)) - 1.
    """
    open_ = [100.0, 101.0, 102.0]
    close = [101.0, 102.0, 103.0]

    class _EnterBar1:
        def desired_position(self, i: int) -> int:
            return 1 if i >= 1 else 0  # flat at bar0, long from bar1 onward

    c = 2.0 / 10_000.0
    expected = 103.0 * (1 - c) / (101.0 * (1 + c)) - 1.0  # enter@101 (bar1 open), exit@103 (last close)
    res = run_backtest(_bars(open_, close), _EnterBar1(), cost_bps=2.0)
    assert res.n_trades == 1
    assert res.trades[0].entry_price == pytest.approx(101.0)  # filled at bar1 open, NOT bar0
    assert res.trades[0].exit_price == pytest.approx(103.0)   # force-closed at last close
    assert res.raw_total_return_pct == pytest.approx(expected * 100, rel=1e-12)


def test_metrics_dict_is_json_serialisable():
    import json
    res = run_backtest(_bars([100.0, 101.0], [101.0, 102.0]),
                       _always_long(), cost_bps=2.0)
    d = res.to_dict()
    s = json.dumps(d)  # must not raise
    for key in ("n_trades", "total_return_pct", "buyhold_return_pct", "max_drawdown_pct",
                "win_rate_pct", "avg_trade_return_pct", "sharpe", "exposure_pct"):
        assert key in d
    assert "trades" not in d  # ledger is intentionally excluded from the JSON block


def test_needs_at_least_two_bars():
    with pytest.raises(ValueError):
        run_backtest(_bars([100.0], [101.0]), _always_long())


# ---------------------------------------------------------------------------
# run_matrix — pure helpers (no data / network)
# ---------------------------------------------------------------------------

def test_run_matrix_cell_names_are_stable():
    from strategy.run_matrix import _cell_name

    # Naming scheme used for per-cell JSON files; must not collide across the
    # standard matrix (3 instruments x 2 windows x 3 cost tiers = 18 cells).
    names = {
        _cell_name(inst, win, cost)
        for inst in ("EUR_USD", "BTC_USD", "XAU_USD")
        for win in ("full", "last_12m", "oos")
        for cost in (0.0, 2.0, 5.0)
    }
    assert len(names) == 27
    assert _cell_name("EUR_USD", "full", 2.0) == "EUR_USD__full__c2"
    assert _cell_name("EUR_USD", "last_12m", 0.0) == "EUR_USD__last_12m__c0"
    assert _cell_name("EUR_USD", "oos", 5.0) == "EUR_USD__oos__c5"


def test_run_matrix_window_bounds():
    """In-sample windows must be capped by `until`; the `oos` window is the
    only one allowed without one; empty windows (since >= until) are a config
    error, not a silent empty run (repo_review_20261027 §1.1)."""
    from strategy.run_matrix import _window_bounds

    cfg = {"windows": {
        "full": {"since": None, "until": "2025-07-31"},
        "last_12m": {"since": "2024-08-01", "until": "2025-07-31"},
        "oos": {"since": "2025-08-01", "until": None},
        "uncapped": {"since": "2024-01-01"},
        "empty": {"since": "2025-10-27", "until": "2025-07-31"},
    }}
    assert _window_bounds(cfg, "full") == (None, "2025-07-31")
    assert _window_bounds(cfg, "last_12m") == ("2024-08-01", "2025-07-31")
    assert _window_bounds(cfg, "oos") == ("2025-08-01", None)
    with pytest.raises(SystemExit):
        _window_bounds(cfg, "uncapped")
    with pytest.raises(SystemExit):
        _window_bounds(cfg, "empty")
    with pytest.raises(SystemExit):
        _window_bounds(cfg, "nope")


# ---------------------------------------------------------------------------
# OOS one-time holdout gate (repo_review_20261029 Phase 1, §1.7)
# ---------------------------------------------------------------------------
# Every test here uses tmp_path + monkeypatch and touches NO real ledger,
# registry, trial_log, or parquet — the holdout must stay unconsumed.
# ---------------------------------------------------------------------------

def _finalize_fixture(tmp_path, monkeypatch, strategy="s01", status="finalist",
                      in_sample_outcome="tested"):
    """Point the gate at a scratch ledger/registry/trial_log and make
    ``strategy`` eligible (registered in config, ``status`` in the registry,
    one real in-sample trial row). Returns the tmp paths for later mutation."""
    import strategy.run_matrix as rm

    cfg_path = tmp_path / "strategies.yml"
    cfg_path.write_text(
        "windows:\n  full: {since: null, until: '2025-07-31'}\n"
        "  last_12m: {since: '2024-08-01', until: '2025-07-31'}\n"
        "  oos: {since: '2025-08-01', until: '2026-10-23'}\n"
        "oos:\n  holdout_id: 'oos1'\n  holdout_start: '2025-08-01'\n"
        "  holdout_end: '2026-10-22'\n  max_strategies_per_holdout: 1\n"
        "strategies:\n  S-01: {timeframe: '5m'}\n  S-02: {timeframe: '1h'}\n")
    registry = tmp_path / "STRATEGY_REGISTRY.md"
    registry.write_text(
        "# Registry\n| ID | Name | Timeframe | Status |\n"
        "|---|---|---|---|\n"
        f"| S-01 | A | 5m | **{status}** |\n"
        f"| S-02 | B | 1h | **{status}** |\n")
    trial = tmp_path / "trial_log.md"
    trial.write_text(
        "| # | date | strategy_id | hypothesis | window | outcome | ret | n |\n"
        "|---|---|---|---|---|---|---|---|\n"
        f"| 1 | 2026-10-26 | S-01 | hyp | full | **{in_sample_outcome}** | x | 0 |\n"
        f"| 2 | 2026-10-26 | S-02 | hyp | full | **{in_sample_outcome}** | x | 1 |\n")
    ledger = tmp_path / "oos_ledger.json"
    ledger.write_text('{"version": 1, "consumptions": []}')

    monkeypatch.setattr(rm, "CONFIG_PATH", cfg_path)
    monkeypatch.setattr(rm, "REGISTRY_PATH", registry)
    monkeypatch.setattr(rm, "TRIAL_LOG", trial)
    monkeypatch.setattr(rm, "_oos_ledger_path", lambda: ledger)
    monkeypatch.setattr(rm, "_RETIRED_LEDGER", tmp_path / "absent_retired.json")
    return {"cfg": cfg_path, "registry": registry, "trial": trial, "ledger": ledger}


def test_oos_gate_finalist_with_empty_ledger_is_allowed(tmp_path, monkeypatch):
    """A clean finalist with a real in-sample row and an empty ledger may run."""
    import strategy.run_matrix as rm
    _finalize_fixture(tmp_path, monkeypatch)
    rm._check_oos_once("s01")  # must not raise


@pytest.mark.parametrize("status", ["rejected", "parked", "candidate", "tested"])
def test_oos_gate_refuses_non_finalist_status(tmp_path, monkeypatch, status):
    """Only `finalist` may consume the holdout — every other status is refused."""
    import strategy.run_matrix as rm
    _finalize_fixture(tmp_path, monkeypatch, status=status)
    with pytest.raises(SystemExit, match="not eligible"):
        rm._check_oos_once("s01")


def test_oos_gate_refuses_unregistered_strategy(tmp_path, monkeypatch):
    """A strategy absent from config/strategies.yml cannot consume the holdout."""
    import strategy.run_matrix as rm
    _finalize_fixture(tmp_path, monkeypatch)
    # s03 is not in the fixture config's strategies: block
    with pytest.raises(SystemExit, match="not registered"):
        rm._check_oos_once("s03")


def test_oos_gate_refuses_tbd_in_sample(tmp_path, monkeypatch):
    """A `<TBD>` in-sample outcome is not a real evaluation -> refused."""
    import strategy.run_matrix as rm
    _finalize_fixture(tmp_path, monkeypatch, in_sample_outcome="<TBD>")
    with pytest.raises(SystemExit, match="no in-sample trial row"):
        rm._check_oos_once("s01")


def test_oos_gate_refuses_when_ledger_missing(tmp_path, monkeypatch):
    """A missing ledger is a fail-closed refusal, not an empty-ledger allow."""
    import strategy.run_matrix as rm
    _finalize_fixture(tmp_path, monkeypatch)
    import strategy.run_matrix as rm2
    (tmp_path / "oos_ledger.json").unlink()
    with pytest.raises(SystemExit, match="OOS ledger missing"):
        rm2._check_oos_once("s01")


def test_oos_gate_refuses_corrupt_ledger(tmp_path, monkeypatch):
    """Invalid JSON in the ledger is a fail-closed refusal."""
    import strategy.run_matrix as rm
    p = _finalize_fixture(tmp_path, monkeypatch)
    p["ledger"].write_text("{ this is not json ]")
    with pytest.raises(SystemExit, match="not valid JSON"):
        rm._check_oos_once("s01")


def test_oos_gate_refuses_wrong_ledger_version(tmp_path, monkeypatch):
    """A wrong schema version is a fail-closed refusal."""
    import strategy.run_matrix as rm
    p = _finalize_fixture(tmp_path, monkeypatch)
    p["ledger"].write_text('{"version": 999, "consumptions": []}')
    with pytest.raises(SystemExit, match="version mismatch"):
        rm._check_oos_once("s01")


def test_oos_gate_refuses_missing_registry(tmp_path, monkeypatch):
    """A missing registry file means the status cannot be verified -> refused."""
    import strategy.run_matrix as rm
    p = _finalize_fixture(tmp_path, monkeypatch)
    p["registry"].unlink()
    with pytest.raises(SystemExit, match="not eligible"):
        rm._check_oos_once("s01")


def test_oos_gate_refuses_missing_trial_log(tmp_path, monkeypatch):
    """A missing trial log means no in-sample outcome -> refused."""
    import strategy.run_matrix as rm
    p = _finalize_fixture(tmp_path, monkeypatch)
    p["trial"].unlink()
    with pytest.raises(SystemExit, match="not eligible"):
        rm._check_oos_once("s01")


def test_oos_gate_refuses_retired_ledger_present(tmp_path, monkeypatch):
    """A leftover retired ledger must stop the run (no 'which wins' guess)."""
    import strategy.run_matrix as rm
    p = _finalize_fixture(tmp_path, monkeypatch)
    retired = tmp_path / "retired.json"
    retired.write_text('{"old": "ledger"}')
    monkeypatch.setattr(rm, "_RETIRED_LEDGER", retired)
    with pytest.raises(SystemExit, match="Retired OOS ledger"):
        rm._check_oos_once("s01")


def test_oos_gate_refuses_after_any_consumption_walk_all_records(tmp_path, monkeypatch):
    """Walking the WHOLE ledger: once s01 consumed the holdout, s01 is refused
    — even with 3+ records (no chain-walk 'check the wrong record' bug)."""
    import strategy.run_matrix as rm
    _finalize_fixture(tmp_path, monkeypatch)
    rm._check_oos_once("s01")          # first run: allowed
    rm._reserve_oos("s01", {"content_hash": 1}, {"n": 1})
    with pytest.raises(SystemExit, match="already consumed holdout oos1"):
        rm._check_oos_once("s01")
    # Append more records (e.g. a new-holdout reservation) and s01 is STILL
    # refused for oos1 — every record is checked, not just the latest.
    rm._reserve_oos("s02", {"content_hash": 2}, {"n": 2})
    rm._reserve_oos("s02", {"content_hash": 3}, {"n": 3})
    with pytest.raises(SystemExit, match="already consumed holdout oos1"):
        rm._check_oos_once("s01")


def test_oos_gate_data_rebuild_does_not_reopen(tmp_path, monkeypatch):
    """The lock is (strategy, holdout) — a rebuilt dataset / new path / appended
    rows must NOT re-open a consumed holdout."""
    import strategy.run_matrix as rm
    _finalize_fixture(tmp_path, monkeypatch)
    rm._check_oos_once("s01", {"content_hash": 111}, {})
    rm._reserve_oos("s01", {"content_hash": 111}, {})
    # Same strategy + holdout, but the data was rebuilt to a new path/hash:
    # the lock is keyed on the holdout, not the data, so it is STILL refused.
    rebuilt = {"content_hash": 999, "path": "rebuilt.parquet"}
    with pytest.raises(SystemExit, match="already consumed holdout oos1"):
        rm._check_oos_once("s01", rebuilt, {})


def test_oos_gate_d1_cap_refuses_second_strategy(tmp_path, monkeypatch):
    """D1 (max_strategies_per_holdout=1): once s01 consumed the holdout, a
    different strategy (s02) is refused even though s02 itself has not run."""
    import strategy.run_matrix as rm
    _finalize_fixture(tmp_path, monkeypatch)
    rm._check_oos_once("s01")
    rm._reserve_oos("s01", {"content_hash": 1}, {})
    with pytest.raises(SystemExit, match="spent"):
        rm._check_oos_once("s02")


def test_oos_gate_crash_after_reserve_still_refuses(tmp_path, monkeypatch):
    """Reserve-then-crash (record left `reserved`) still blocks a re-run — a
    crashed attempt counts as consumed."""
    import strategy.run_matrix as rm
    _finalize_fixture(tmp_path, monkeypatch)
    rm._check_oos_once("s01")
    rm._reserve_oos("s01", {"content_hash": 1}, {})  # no _complete_oos -> stays reserved
    ledger = rm._load_oos_ledger()
    assert ledger["consumptions"][0]["status"] == "reserved"
    with pytest.raises(SystemExit, match="already consumed holdout oos1"):
        rm._check_oos_once("s01")


def test_oos_gate_complete_marks_completed(tmp_path, monkeypatch):
    """_complete_oos flips the latest `reserved` record to `completed`."""
    import strategy.run_matrix as rm
    _finalize_fixture(tmp_path, monkeypatch)
    rm._reserve_oos("s01", {"content_hash": 1}, {})
    rm._complete_oos("s01")
    ledger = rm._load_oos_ledger()
    assert ledger["consumptions"][0]["status"] == "completed"


def test_oos_window_until_includes_last_closed_day(tmp_path):
    """§1.1 boundary: `until` uses `time <= until@UTC-midnight`, so the config
    `oos.until = 2026-10-23` includes ALL bars of the last fully-closed day
    (2026-10-22) and EXCLUDES any bar on/after 2026-10-23 00:00 UTC."""
    import strategy.run_matrix as rm
    # The committed config pins the holdout's fixed, closed end date.
    cfg = rm._load_config()
    assert cfg["windows"]["oos"]["until"] == "2026-10-23"
    assert cfg["oos"]["holdout_end"] == "2026-10-22"
    # _window_bounds returns the raw (since, until) the loader applies as
    # `time >= since` and `time <= until` (date-only, read at UTC midnight).
    since, until = rm._window_bounds(cfg, "oos")
    assert since == "2025-08-01"
    assert until == "2026-10-23"


def test_oos_fingerprint_covers_open_and_is_order_independent(tmp_path, monkeypatch):
    """§2.3: the fingerprint must (a) fail if `open`/`close` is missing, and
    (b) be order-independent (sum of 64-bit per-row hashes)."""
    import duckdb
    import strategy.run_matrix as rm
    from strategy.run_matrix import _parquet_columns

    p = tmp_path / "f.parquet"
    con = duckdb.connect()
    # 6 bars on 2026-10-22 (inside the holdout window 2025-08-01..2026-10-23),
    # `open` values 10..15, `time` is a proper TIMESTAMP (real-data type).
    sql = ("COPY (SELECT 'EUR_USD' AS instrument, "
           "make_timestamp(2026,10,22, 12+i, 0, 0) AS \"time\", "
           "(10+i)::DOUBLE AS open, (10+i)::DOUBLE AS high, "
           "(10+i)::DOUBLE AS low, (20+i)::DOUBLE AS close, "
           "(1+i)::DOUBLE AS volume FROM range(6) r(i)) TO ? (FORMAT PARQUET)")
    con.execute(sql, [str(p)])
    con.close()

    base = rm._data_fingerprint(str(p))
    assert "open" in base["hashed_columns"] and "close" in base["hashed_columns"]

    # (a) fail loudly when `open` is missing.
    monkeypatch.setattr(rm, "_parquet_columns", lambda q: {"time", "close", "volume"})
    with pytest.raises(SystemExit, match="both `open` and `close`"):
        rm._data_fingerprint(str(p))
    monkeypatch.undo()

    # (b) order-independence: reordering the rows must NOT change the hash.
    p2 = tmp_path / "f_reordered.parquet"
    con = duckdb.connect()
    con.execute(
        "COPY (SELECT * FROM (SELECT 'EUR_USD' AS instrument, "
        "make_timestamp(2026,10,22, 12+i, 0, 0) AS \"time\", "
        "(10+i)::DOUBLE AS open, (10+i)::DOUBLE AS high, "
        "(10+i)::DOUBLE AS low, (20+i)::DOUBLE AS close, "
        "(1+i)::DOUBLE AS volume FROM range(6) r(i)) ORDER BY \"time\" DESC) "
        "TO ? (FORMAT PARQUET)", [str(p2)])
    con.close()
    base2 = rm._data_fingerprint(str(p2))
    assert base2["content_hash"] == base["content_hash"], "reordering changed the hash"


def test_oos_fingerprint_open_change_changes_hash(tmp_path):
    """§2.3: changing ONLY `open` must change the fingerprint (open is covered,
    which the old close-only hash missed)."""
    import duckdb
    import strategy.run_matrix as rm

    def _write(path, open_offset):
        con = duckdb.connect()
        con.execute(
            "COPY (SELECT 'EUR_USD' AS instrument, "
            "make_timestamp(2026,10,22, 12+i, 0, 0) AS \"time\", "
            f"({open_offset}+i)::DOUBLE AS open, (10+i)::DOUBLE AS high, "
            "(10+i)::DOUBLE AS low, (20+i)::DOUBLE AS close, "
            "(1+i)::DOUBLE AS volume FROM range(6) r(i)) TO ? (FORMAT PARQUET)",
            [str(path)])
        con.close()

    a = tmp_path / "a.parquet"
    b = tmp_path / "b.parquet"
    _write(a, 10)
    _write(b, 999)  # different `open`, everything else identical
    fa = rm._data_fingerprint(str(a))
    fb = rm._data_fingerprint(str(b))
    assert fa["content_hash"] != fb["content_hash"], "changing open must change the hash"


def test_run_matrix_n_tried_before_counts_distinct_strategies():
    """`n_tried_before` counts *distinct other* strategies, so repeated rows of
    the same strategy do not inflate the 'best of N' denominator
    (repo_review_20261027 §2.1)."""
    import strategy.run_matrix as rm

    rows = [
        ["1", "d", "S-01", "h", "full", "rejected", "r", "0"],
        ["2", "d", "S-01", "h", "full", "rejected", "r", "0"],
        ["3", "d", "S-02", "h", "full", "parked", "r", "1"],
    ]
    # Trying S-01: the only *other* strategy on record is S-02 → 1
    # (two S-01 rows must not double-count).
    assert rm._n_tried_before(rows, "s01") == 1
    # Trying S-02: the only *other* strategy is S-01 → 1 (not 2).
    assert rm._n_tried_before(rows, "s02") == 1
    assert rm._n_tried_before([], "s01") == 0
    # Case/dash-insensitive: "s01" must match the "S-01" rows and be excluded.
    assert rm._n_tried_before(rows, "S-01") == 1


def test_run_matrix_trial_row_uses_canonical_id(tmp_path, monkeypatch):
    """The trial row must use the *registered* id (``S-01``), not the upper-cased
    runner id (``S01``) — the old ``strategy.upper()`` broke the registry canon
    (repo_review_20261027 §2.1)."""
    import strategy.run_matrix as rm

    log = tmp_path / "trial_log.md"
    log.write_text(
        "| # | date | strategy_id | hypothesis | window | outcome | ret | n |\n"
        "|---|------|-------------|------------|--------|---------|-----|---|\n")
    monkeypatch.setattr(rm, "TRIAL_LOG", log)
    cfg = {"strategies": {"S-01": {"timeframe": "5m"}}}
    cells = [{"instrument": "EUR_USD", "cost_bps": 2.0, "window": "full",
              "total_return_pct": -21.6, "buyhold_return_pct": 0.3}]
    rm.write_trial_row(cells, "s01", "full", "hyp", cfg=cfg)
    line = log.read_text().splitlines()[-1]
    assert "S-01" in line
    assert "S01" not in line
    # n_tried_before should be 0 (no other strategies on record).
    assert "| 0 |" in line


# ---------------------------------------------------------------------------
# B6 entry guard — no *new* entries on flagged bars (gap / near market close)
# ---------------------------------------------------------------------------

def _bars_with_mask(open_, close, no_entry) -> BarFrame:
    o = np.asarray(open_, dtype=np.float64)
    c = np.asarray(close, dtype=np.float64)
    return BarFrame(open=o, close=c, time=None, bar_seconds=300,
                    no_entry_mask=np.asarray(no_entry, dtype=bool))


def test_entry_guard_blocks_new_entry_from_flat():
    """Bar 1 is flagged no-entry. A rule going long at bar 1 (decided from
    bar 0's close) must NOT enter at bar 1's open; the engine stays flat and
    re-attempts at bar 2.

    Rule: long from bar 1 onward. Without the guard: entry at open[1]=101,
    force-closed at close[2]=103. With the guard on bar 1: entry at
    open[2]=102, force-closed at close[2]=103 → +1% at cost 0.
    """
    open_ = [100.0, 101.0, 102.0]
    close = [101.0, 102.0, 103.0]

    class _EnterBar1:
        def desired_position(self, i: int) -> int:
            return 1 if i >= 1 else 0

    res_no_guard = run_backtest(_bars(open_, close), _EnterBar1(), cost_bps=0.0)
    assert res_no_guard.n_trades == 1
    assert res_no_guard.trades[0].entry_price == pytest.approx(101.0)

    res_guarded = run_backtest(
        _bars_with_mask(open_, close, no_entry=[False, True, False]),
        _EnterBar1(), cost_bps=0.0)
    assert res_guarded.n_trades == 1
    assert res_guarded.trades[0].entry_price == pytest.approx(102.0)  # deferred to bar 2
    # entry 102 (bar2 open), exit 103 (bar2 close, force-closed): +103/102 - 1
    assert res_guarded.raw_total_return_pct == pytest.approx((103.0 / 102.0 - 1.0) * 100, rel=1e-12)


def test_entry_guard_does_not_block_exits_or_flips():
    """The no-entry mask must only block fresh entries *from flat*. Closing an
    open position at a flagged bar's open is still allowed: long from bar 0,
    exit at bar 2 open (flagged). The trade must still close at 102."""
    open_ = [100.0, 101.0, 102.0]
    close = [101.0, 102.0, 103.0]

    class _EnterExit:
        def desired_position(self, i: int) -> int:
            return 1 if i < 2 else 0

    res = run_backtest(
        _bars_with_mask(open_, close, no_entry=[False, False, True]),
        _EnterExit(), cost_bps=0.0)
    assert res.n_trades == 1
    assert res.trades[0].entry_price == pytest.approx(100.0)
    assert res.trades[0].exit_price == pytest.approx(102.0)  # exit on flagged bar OK
    assert res.raw_total_return_pct == pytest.approx(2.0, rel=1e-12)


def test_rule_called_exactly_once_per_bar():
    """``desired_position`` must be evaluated exactly n times — the pre-fix
    clamp called it a second time whenever the answer was >= 0, silently
    breaking any rule with side effects (legacy review 1.6)."""
    n = 5
    bars = _bars([100.0] * n, [100.0] * n)

    class _Counting:
        calls = 0

        def desired_position(self, i: int) -> int:
            _Counting.calls += 1
            return 1 if i % 2 == 0 else 0

    run_backtest(bars, _Counting(), cost_bps=0.0)
    assert _Counting.calls == n
    # Same guarantee with long_only clamping (the old double-call path).
    _Counting.calls = 0
    run_backtest(bars, _Counting(), cost_bps=0.0, long_only=True)
    assert _Counting.calls == n


def test_span_years_fallback_uses_bar_seconds():
    """With no timestamps, the annualisation span must come from the frame's
    bar_seconds, not a hard-coded 300s (legacy review 1.8: a 1h bar with
    time=None inflated Sharpe ~3.5x)."""
    n = 24 * 365  # one calendar year of 1h bars (engine year = 365.25 d)
    bars = BarFrame(open=np.full(n, 100.0), close=np.full(n, 101.0),
                    time=None, bar_seconds=3600)
    res = run_backtest(bars, _always_long(), cost_bps=0.0)
    assert res.span_years == pytest.approx(365.0 / 365.25, rel=1e-9)
    # And the same bar count at 5m cadence must give a 12x smaller span.
    bars5 = BarFrame(open=np.full(n, 100.0), close=np.full(n, 101.0),
                     time=None, bar_seconds=300)
    res5 = run_backtest(bars5, _always_long(), cost_bps=0.0)
    assert res5.span_years == pytest.approx(res.span_years / 12.0, rel=1e-9)



    with pytest.raises(ValueError):
        run_backtest(
            _bars_with_mask([100.0, 101.0], [101.0, 102.0], no_entry=[True, False, True]),
            _always_long())


# ---------------------------------------------------------------------------
# Data-layer OOS holdout gate (follow-up review: the gate must live in
# load_bars, not only in run_matrix). Every test here uses tmp_path +
# monkeypatch against a scratch config/ledger and touches NO real ledger or
# parquet — the holdout must stay unconsumed.
# ---------------------------------------------------------------------------

def _oos_env(tmp_path, monkeypatch, holdout_start="2025-08-01",
             holdout_id="oos1", ledger_consumptions=None):
    """Point strategy.oos_token at a scratch config + ledger. Returns the paths
    for later mutation."""
    import strategy.oos_token as ot
    cfg = tmp_path / "strategies.yml"
    cfg.write_text(
        "oos:\n"
        f"  holdout_id: '{holdout_id}'\n"
        f"  holdout_start: '{holdout_start}'\n"
        "  holdout_end: '2026-10-22'\n"
        "windows:\n  oos: {since: '2025-08-01', until: '2026-10-23'}\n")
    ledger = tmp_path / "oos_ledger.json"
    ledger.write_text(
        json.dumps({"version": 1,
                    "consumptions": ledger_consumptions or []}) + "\n",
        encoding="utf-8")
    monkeypatch.setattr(ot, "_config_path", lambda: cfg)
    monkeypatch.setattr(ot, "_ledger_path", lambda: ledger)
    return {"cfg": cfg, "ledger": ledger}


def _tiny_parquet(tmp_path) -> str:
    """A minimal feature parquet (base cols + rsi_24) for load_bars to read."""
    import pandas as pd
    p = tmp_path / "mini.parquet"
    times = [f"2025-07-{d:02d} 00:00:00" for d in range(1, 5)]
    df = pd.DataFrame({
        "instrument": ["EUR_USD"] * 4,
        "time": pd.to_datetime(times),
        "open": [1.0, 1.1, 1.2, 1.3],
        "close": [1.05, 1.15, 1.25, 1.35],
        "is_gap_bar": [0, 0, 0, 0],
        "is_near_market_close": [0, 0, 0, 0],
        "rsi_24": [50.0, 40.0, 30.0, 60.0],
    })
    df.to_parquet(p)
    return str(p)


def test_load_bars_until_none_without_token_refuses(tmp_path, monkeypatch):
    """THE review test: a direct load_bars(until=None) must raise (holdout gate
    now lives in the data layer). Uses a real parquet so the only thing that
    can raise is assert_access, not the SQL read."""
    import strategy.oos_token as ot
    import strategy.strategy_lib as sl
    _oos_env(tmp_path, monkeypatch)
    pq = _tiny_parquet(tmp_path)
    # until=None means "read everything" -> reaches the holdout -> must refuse.
    with pytest.raises(SystemExit, match="holdout"):
        sl.load_bars(pq, "EUR_USD", feature_cols=["rsi_24"],
                     not_null_cols=["rsi_24"], until=None)


def test_load_bars_in_sample_until_reads_without_token(tmp_path, monkeypatch):
    """An in-sample window (until strictly before holdout_start) loads via the
    real load_bars with no token — proving the gate is selective, not blanket."""
    import strategy.strategy_lib as sl
    _oos_env(tmp_path, monkeypatch)
    pq = _tiny_parquet(tmp_path)
    df = sl.load_bars(pq, "EUR_USD", feature_cols=["rsi_24"],
                      not_null_cols=["rsi_24"], until="2025-07-31")
    assert len(df) == 4  # all 4 bars are <= 2025-07-31


def test_load_bars_in_sample_until_without_token_is_allowed(tmp_path, monkeypatch):
    """An in-sample window (until strictly before holdout_start) loads freely."""
    import strategy.oos_token as ot
    _oos_env(tmp_path, monkeypatch)
    ot.assert_access("2025-07-31", None)  # must not raise (strictly before holdout)


def test_load_bars_until_at_or_after_holdout_needs_token(tmp_path, monkeypatch):
    """until == holdout_start (or later) is a holdout window and needs a token."""
    import strategy.oos_token as ot
    _oos_env(tmp_path, monkeypatch)
    with pytest.raises(SystemExit):
        ot.assert_access("2025-08-01", None)      # == holdout_start
    with pytest.raises(SystemExit):
        ot.assert_access("2026-10-23", None)      # inside the holdout


def test_oos_token_backed_by_ledger_allows_holdout(tmp_path, monkeypatch):
    """A token minted after a real ledger reservation opens the holdout."""
    import strategy.oos_token as ot
    _oos_env(tmp_path, monkeypatch, ledger_consumptions=[
        {"strategy": "s01", "holdout_id": "oos1",
         "holdout_start": "2025-08-01", "holdout_end": "2026-10-22",
         "reserved_at": "2026-10-29", "status": "reserved"}])
    tok = ot.create_token("s01", "oos1")
    ot.assert_access("2026-10-23", tok)  # must not raise


def test_fabricated_token_without_ledger_record_refuses(tmp_path, monkeypatch):
    """A token object with no backing ledger record cannot open the holdout."""
    import strategy.oos_token as ot
    _oos_env(tmp_path, monkeypatch)  # empty ledger
    tok = ot.create_token("s01", "oos1")
    with pytest.raises(SystemExit, match="ledger"):
        ot.assert_access("2026-10-23", tok)


def test_oos_token_wrong_holdout_id_refuses(tmp_path, monkeypatch):
    """A token for a different holdout id does not match the current one."""
    import strategy.oos_token as ot
    _oos_env(tmp_path, monkeypatch, holdout_id="oos1")
    tok = ot.create_token("s01", "oos2")
    with pytest.raises(SystemExit, match="holdout"):
        ot.assert_access("2026-10-23", tok)


# ---------------------------------------------------------------------------
# Holdout-window identity lock (follow-up review, must-fix): renaming the id or
# shifting the window must not reset the lock for every strategy.
# ---------------------------------------------------------------------------

def _window_fixture(tmp_path, monkeypatch, holdout_id, h_start, h_end,
                    consumptions):
    """Scratch config + ledger for the window-identity lock."""
    import strategy.run_matrix as rm
    cfg_path = tmp_path / "strategies.yml"
    cfg_path.write_text(
        "oos:\n"
        f"  holdout_id: '{holdout_id}'\n"
        f"  holdout_start: '{h_start}'\n"
        f"  holdout_end: '{h_end}'\n"
        "  max_strategies_per_holdout: 1\n"
        "windows:\n  oos: {since: '2025-08-01', until: '2026-10-23'}\n"
        "strategies:\n  S-01: {timeframe: '5m'}\n")
    ledger = tmp_path / "oos_ledger.json"
    ledger.write_text(json.dumps({"version": 1, "consumptions": consumptions}),
                      encoding="utf-8")
    monkeypatch.setattr(rm, "CONFIG_PATH", cfg_path)
    monkeypatch.setattr(rm, "_oos_ledger_path", lambda: ledger)
    return {"cfg": cfg_path, "ledger": ledger}


def test_window_lock_same_id_same_dates_is_ok(tmp_path, monkeypatch):
    import strategy.run_matrix as rm
    _window_fixture(tmp_path, monkeypatch, "oos1", "2025-08-01", "2026-10-22",
                    [{"strategy": "s01", "holdout_id": "oos1",
                      "holdout_start": "2025-08-01", "holdout_end": "2026-10-22",
                      "status": "reserved"}])
    rm._check_holdout_window(rm._load_config())  # must not raise


def test_window_lock_same_id_changed_dates_refuses(tmp_path, monkeypatch):
    """Renaming the dates under an existing id must be refused."""
    import strategy.run_matrix as rm
    _window_fixture(tmp_path, monkeypatch, "oos1", "2025-09-01", "2026-10-22",
                    [{"strategy": "s01", "holdout_id": "oos1",
                      "holdout_start": "2025-08-01", "holdout_end": "2026-10-22",
                      "status": "reserved"}])
    with pytest.raises(SystemExit, match="already in the ledger"):
        rm._check_holdout_window(rm._load_config())


def test_window_lock_new_id_overlapping_window_refuses(tmp_path, monkeypatch):
    """A new id with an overlapping (earlier/equal) start must be refused."""
    import strategy.run_matrix as rm
    _window_fixture(tmp_path, monkeypatch, "oos2", "2025-09-01", "2026-11-01",
                    [{"strategy": "s01", "holdout_id": "oos1",
                      "holdout_start": "2025-08-01", "holdout_end": "2026-10-22",
                      "status": "completed"}])
    with pytest.raises(SystemExit, match="strictly later"):
        rm._check_holdout_window(rm._load_config())


def test_window_lock_new_id_strictly_later_is_ok(tmp_path, monkeypatch):
    import strategy.run_matrix as rm
    _window_fixture(tmp_path, monkeypatch, "oos2", "2026-10-23", "2027-10-22",
                    [{"strategy": "s01", "holdout_id": "oos1",
                      "holdout_start": "2025-08-01", "holdout_end": "2026-10-22",
                      "status": "completed"}])
    rm._check_holdout_window(rm._load_config())  # must not raise


# ---------------------------------------------------------------------------
# Void flow (follow-up review): a `voided` reservation does NOT consume the
# holdout — it must not block a later, corrected re-run, and it must not be
# counted as a D1-cap consumption.
# ---------------------------------------------------------------------------

def test_voided_reservation_does_not_block_re_run(tmp_path, monkeypatch):
    """A `voided` record for the strategy does not trigger the once-per-lock."""
    import strategy.run_matrix as rm
    _window_fixture(tmp_path, monkeypatch, "oos1", "2025-08-01", "2026-10-22",
                    [{"strategy": "s01", "holdout_id": "oos1",
                      "holdout_start": "2025-08-01", "holdout_end": "2026-10-22",
                      "status": "voided"}])
    # _check_holdout_window only cares about real (non-voided) consumptions,
    # so the same-id path sees no live record and does not pin the dates.
    rm._check_holdout_window(rm._load_config())  # must not raise


def test_voided_does_not_count_toward_d1_cap(tmp_path, monkeypatch):
    """A voided record for strategy A must not spend the D1=1 cap for B."""
    import strategy.run_matrix as rm
    cfg_path = tmp_path / "strategies.yml"
    cfg_path.write_text(
        "oos:\n  holdout_id: 'oos1'\n  holdout_start: '2025-08-01'\n"
        "  holdout_end: '2026-10-22'\n  max_strategies_per_holdout: 1\n"
        "windows:\n  oos: {since: '2025-08-01', until: '2026-10-23'}\n"
        "strategies:\n  S-01: {timeframe: '5m'}\n  S-02: {timeframe: '1h'}\n")
    ledger = tmp_path / "oos_ledger.json"
    ledger.write_text(json.dumps({"version": 1, "consumptions": [
        {"strategy": "s01", "holdout_id": "oos1",
         "holdout_start": "2025-08-01", "holdout_end": "2026-10-22",
         "status": "voided"}]}), encoding="utf-8")
    registry = tmp_path / "STRATEGY_REGISTRY.md"
    registry.write_text(
        "# Registry\n| ID | Name | Timeframe | Status |\n|---|---|---|---|\n"
        "| S-02 | B | 1h | **finalist** |\n")
    trial = tmp_path / "trial_log.md"
    trial.write_text(
        "| # | date | strategy_id | hypothesis | window | outcome | ret | n |\n"
        "|---|---|---|---|---|---|---|---|\n"
        "| 1 | 2026-10-29 | S-02 | hyp | full | **tested** | x | 0 |\n")
    monkeypatch.setattr(rm, "CONFIG_PATH", cfg_path)
    monkeypatch.setattr(rm, "REGISTRY_PATH", registry)
    monkeypatch.setattr(rm, "TRIAL_LOG", trial)
    monkeypatch.setattr(rm, "_oos_ledger_path", lambda: ledger)
    monkeypatch.setattr(rm, "_RETIRED_LEDGER", tmp_path / "absent.json")
    # S-02 is eligible and the only live consumption is voided -> allowed.
    rm._check_oos_once("s02")  # must not raise
