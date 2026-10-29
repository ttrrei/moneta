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


def test_run_matrix_oos_once_lock(tmp_path, monkeypatch):
    """A strategy that already has an adjudicated `oos` row in the trial log
    must be refused a second holdout run (repo_review_20261027 §1.1 step 3)."""
    import strategy.run_matrix as rm

    log = tmp_path / "trial_log.md"
    log.write_text(
        "| # | date | strategy_id | hypothesis | window | outcome | ret | n |\n"
        "|---|------|-------------|------------|--------|---------|-----|---|\n"
        "| 1 | 2026-10-26 | S-01 | hyp | full | rejected | x | 0 |\n"
        "| 2 | 2026-10-27 | S-01 | hyp | oos | tested | y | 1 |\n")
    monkeypatch.setattr(rm, "TRIAL_LOG", log)
    with pytest.raises(SystemExit, match="already has an adjudicated"):
        rm._check_oos_once("s01")
    # A `<TBD>` row (run in progress, not yet adjudicated) must not lock.
    log.write_text(
        "| # | date | strategy_id | hypothesis | window | outcome | ret | n |\n"
        "|---|------|-------------|------------|--------|---------|-----|---|\n"
        "| 1 | 2026-10-26 | S-01 | hyp | oos | <TBD> | y | 1 |\n")
    rm._check_oos_once("s01")  # must not raise


def test_oos_data_bound_lock(tmp_path, monkeypatch):
    """Data-bound OOS lock (review 2026-10-28 item 6): once a strategy has
    consumed a specific dataset, it cannot be re-consumed on that same data —
    even before any trial-log row exists — but a *new* dataset is allowed."""
    import strategy.run_matrix as rm

    # Point the ledger and trial log at a scratch location (no real repo writes).
    monkeypatch.setattr(rm, "TRIAL_LOG", tmp_path / "trial_log.md")  # absent -> label lock off
    monkeypatch.setattr(rm, "_oos_ledger_path", lambda: tmp_path / "oos.json")

    # Content-bound fingerprints (review 2026-10-28: bind to data, not file
    # metadata). Identical content -> same lock key; different content -> different.
    fp_a = {"path": "a.parquet", "holdout_start": "2025-08-01", "rows": 1000,
            "tmin": "2025-08-01 00:00:00+00:00", "tmax": "2026-10-24 00:00:00+00:00",
            "content_hash": 11111}
    fp_b = {"path": "b.parquet", "holdout_start": "2025-08-01", "rows": 2000,
            "tmin": "2025-08-01 00:00:00+00:00", "tmax": "2026-11-01 00:00:00+00:00",
            "content_hash": 22222}
    # Same data as A, but rebuilt to a NEW path (fresh file, fresh mtime) — this
    # is the exact case the review flagged: the lock must survive a rebuild, so
    # the content-bound key is identical to fp_a and a re-run is refused.
    fp_a_rebuilt = {"path": "a_rebuilt.parquet", "holdout_start": "2025-08-01",
                    "rows": 1000, "tmin": "2025-08-01 00:00:00+00:00",
                    "tmax": "2026-10-24 00:00:00+00:00", "content_hash": 11111}

    # First run on dataset A: allowed, then reserved.
    rm._check_oos_once("s01", fp_a, {})
    rm._reserve_oos("s01", fp_a, {})

    # Second run on the SAME dataset A is refused (data-bound).
    with pytest.raises(SystemExit, match="already consumed this exact OOS dataset"):
        rm._check_oos_once("s01", fp_a, {})

    # A rebuild of the SAME data to a new path is STILL refused — the lock is
    # bound to content, not to the file. (The core of the review fix.)
    with pytest.raises(SystemExit, match="already consumed this exact OOS dataset"):
        rm._check_oos_once("s01", fp_a_rebuilt, {})

    # A genuinely different dataset B (different holdout bars) is still allowed.
    rm._check_oos_once("s01", fp_b, {})

    # Case/dash-insensitive: "S-01" and "s01" are the same strategy.
    with pytest.raises(SystemExit, match="already consumed this exact OOS dataset"):
        rm._check_oos_once("S-01", fp_a, {})


def test_oos_reserve_is_idempotent_for_same_data(tmp_path, monkeypatch):
    """Reserving twice on the same data keeps a single ledger entry (no growth)."""
    import strategy.run_matrix as rm

    monkeypatch.setattr(rm, "TRIAL_LOG", tmp_path / "trial_log.md")
    monkeypatch.setattr(rm, "_oos_ledger_path", lambda: tmp_path / "oos.json")

    fp = {"path": "x.parquet", "holdout_start": "2025-08-01", "rows": 5,
          "tmin": "2025-08-01 00:00:00+00:00", "tmax": "2025-08-02 00:00:00+00:00",
          "content_hash": 777}
    rm._reserve_oos("s02", fp, {"k": 1})
    rm._reserve_oos("s02", fp, {"k": 2})  # supersede, not append
    ledger = rm._load_oos_ledger()
    assert list(ledger.keys()) == ["S02"]
    assert ledger["S02"]["manifest"] == {"k": 2}


def test_run_matrix_oos_wiring_end_to_end(tmp_path, monkeypatch):
    """E2E wiring of the `--windows oos` path (review 2026-10-28: run the OOS
    flow end-to-end so the first *real* survivor isn't its first live test).

    Drives the real ``run_matrix`` with a stub strategy on a scratch dataset.
    Proves the three things that only unit tests had covered in isolation:
      1. an OOS run reserves the attempt in the ledger BEFORE any cell runs;
      2. OOS output goes to a SEPARATE ``<name>_oos`` dir (never overwrites the
         in-sample matrix);
      3. a second ``--windows oos`` run on the same data is refused by the
         data-bound lock (the ledger the first run wrote).
    Uses a stub strategy + a stub fingerprint so it touches no real parquet,
    ledger, or trial_log — no evidence pollution.
    """
    import strategy.run_matrix as rm

    # Isolate every persistent side effect.
    monkeypatch.setattr(rm, "TRIAL_LOG", tmp_path / "trial_log.md")  # absent -> label lock off
    monkeypatch.setattr(rm, "_oos_ledger_path", lambda: tmp_path / "oos.json")
    fp = {"path": "scratch.parquet", "holdout_start": "2025-08-01", "rows": 3,
          "tmin": "2025-08-01 00:00:00+00:00", "tmax": "2025-08-03 00:00:00+00:00",
          "content_hash": 424242}
    monkeypatch.setattr(rm, "_data_fingerprint", lambda parquet: fp)

    # Stub the strategy's per-cell run: returns a minimal result dict and never
    # touches real data.
    calls = []

    def stub_run(parquet, instrument, timeframe, since, until, cost_bps, entry_guard):
        calls.append((instrument, since, until, cost_bps))
        return {
            "instrument": instrument, "cost_bps": cost_bps, "start": "2025-08-01 00:00:00",
            "end": "2025-08-03 00:00:00", "n_bars": 10, "n_trades": 2,
            "total_return_pct": 1.0, "buyhold_return_pct": 0.5,
            "max_drawdown_pct": 1.0, "win_rate_pct": 50.0,
            "avg_trade_return_pct": 0.5, "sharpe": 0.1, "sharpe_weekly": 0.1,
            "trades_per_year": 0.1, "exposure_pct": 50.0, "span_years": 0.01,
        }

    rm._STRATEGIES["stub"] = {"label": "stub", "run": stub_run}
    monkeypatch.setitem(rm._STRATEGIES, "stub", {"label": "stub", "run": stub_run})

    out_dir = tmp_path / "results" / "stub"
    # (1) First OOS run succeeds and writes to a SEPARATE _oos dir.
    cells = rm.run_matrix("stub", ["EUR_USD"], ["oos"], [2.0], "5m", False, out_dir)
    assert cells, "the OOS run produced no cells"
    assert (tmp_path / "results" / "stub_oos").exists(), "OOS output must go to a separate dir"
    assert not (out_dir / "EUR_USD__oos__c2.json").exists(), "in-sample dir must stay untouched"

    # (2) The attempt was reserved in the ledger BEFORE the holdout was loaded.
    ledger = rm._load_oos_ledger()
    assert "STUB" in ledger and ledger["STUB"]["fingerprint_key"] == rm._fingerprint_key(fp)

    # (3) A second `--windows oos` run on the SAME data is now refused by the
    #     data-bound lock (the ledger written by run 1).
    with pytest.raises(SystemExit, match="already consumed this exact OOS dataset"):
        rm.run_matrix("stub", ["EUR_USD"], ["oos"], [2.0], "5m", False,
                      tmp_path / "results" / "stub2")


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
