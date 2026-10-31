"""Regressions from the independent review; all market data is synthetic."""
from __future__ import annotations

import importlib
from itertools import product
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from strategy import run_matrix as rm
from strategy.schema import validate_cell_grid
from strategy.variants import STRATEGIES, VARIANTS, resolve


def test_every_declared_variant_resolves_and_defaults_are_explicit():
    cfg = rm._load_config()
    for sid, variants in VARIANTS.items():
        for name, overrides in variants:
            resolved = resolve(sid, name, cfg=cfg)
            assert resolved.timeframe == overrides.get("timeframe", rm._registered_timeframe(cfg, sid))
    base, looser = resolve("s55"), resolve("S-55", "looser")
    assert looser.rule_params == {"ema_gate": False, "k_in": 33.0, "k_exit": 27.0}
    assert rm.config_hash(base.timeframe, base.entry_guard, base.rule_params) != \
        rm.config_hash(looser.timeframe, looser.entry_guard, looser.rule_params)
    assert resolve("s113").rule_params["rule_spec"]["enter_long"]
    assert set(STRATEGIES) <= set(rm._STRATEGIES)
    with pytest.raises(ValueError, match="unknown variant"):
        resolve("s55", "made_up")
    with pytest.raises(ValueError, match="registered for timeframe"):
        resolve("s08", "1h", timeframe="5m")


@pytest.mark.parametrize("missing", ["oos_variant", "oos_config_hash"])
def test_unpinned_reservation_never_writes_ledger(tmp_path, monkeypatch, missing):
    pin = rm.config_hash("5m", False, {"k_in": 33.0})
    spec = {"timeframe": "5m", "oos_variant": "looser", "oos_config_hash": pin}
    del spec[missing]
    cfg = {"strategies": {"S-55": spec}, "oos": {
        "holdout_id": "test", "holdout_start": "2025-08-01",
        "holdout_end": "2026-10-22", "max_strategies_per_holdout": 1}}
    ledger = tmp_path / "ledger.json"
    ledger.write_text('{"version":1,"consumptions":[]}')
    before = ledger.read_bytes()
    monkeypatch.setattr(rm, "_load_config", lambda: cfg)
    monkeypatch.setattr(rm, "_oos_ledger_path", lambda: ledger)
    with pytest.raises(SystemExit, match="requires oos_variant"):
        rm._reserve_oos("s55", {}, {"variant": "looser", "config_hash": pin})
    assert ledger.read_bytes() == before


def test_wrong_variant_refused_even_with_matching_hash():
    cfg = {"strategies": {"S-55": {"oos_variant": "looser", "oos_config_hash": "a" * 64}}}
    with pytest.raises(SystemExit, match="pinned to OOS variant"):
        rm._check_config_pin(cfg, "s55", {"variant": "base", "config_hash": "a" * 64})


def test_named_variant_reaches_runner_and_never_overwrites_base(tmp_path, monkeypatch):
    calls = []
    def fake_run(**kw):
        calls.append(kw)
        return {"strategy_id": "S-55", "instrument": kw["instrument"], "n_trades": 1,
                "total_return_pct": 1, "buyhold_return_pct": 2}
    monkeypatch.setitem(rm._STRATEGIES, "s55", {"run": fake_run})
    monkeypatch.setattr(rm, "_data_fingerprint", lambda path, window: {"window": window})
    cells = rm.run_matrix("s55", ["EUR_USD"], ["full"], [2.0], None, None,
                          tmp_path, variant="looser")
    assert calls[0]["k_in"] == 33.0 and calls[0]["k_exit"] == 27.0
    assert cells[0]["rule_params"]["ema_gate"] is False
    assert cells[0]["data_fingerprint"]["window"] == "full"
    assert (tmp_path / "variants/looser/EUR_USD__full__c2.json").exists()
    import yaml
    manifest = yaml.safe_load((tmp_path / "variants/looser/manifest.yml").read_text())
    assert manifest["variant"] == "looser"
    assert manifest["rule_params"]["k_in"] == 33.0
    assert manifest["config_hash"] == cells[0]["config_hash"]
    assert not (tmp_path / "EUR_USD__full__c2.json").exists()


def test_unpinned_oos_refused_before_any_data_read(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("must refuse before reading any data")
    monkeypatch.setattr(rm, "_data_fingerprint", forbidden)
    with pytest.raises(SystemExit, match="requires oos_variant"):
        rm.run_matrix("s55", rm.INSTRUMENTS, ["oos"], rm.COST_TIERS,
                      None, None, tmp_path, variant="looser")


def test_oos_summary_and_cells_share_output_directory(tmp_path, monkeypatch):
    # Exercise CLI output routing with a fake run; no ledger or data access.
    expected = rm.result_directory(tmp_path / "S55", ["oos"])
    def fake_matrix(**kwargs):
        expected.mkdir()
        return []
    written = []
    monkeypatch.setattr(rm, "run_matrix", fake_matrix)
    monkeypatch.setattr(rm, "write_csv", lambda rows, path: written.append(path))
    monkeypatch.setattr(rm, "write_markdown", lambda rows, path: written.append(path))
    monkeypatch.setattr("sys.argv", ["run_matrix", "--strategy", "s55", "--variant", "looser",
                                    "--windows", "oos", "--out", str(tmp_path / "S55")])
    rm.main()
    assert {path.parent for path in written} == {expected}


@pytest.mark.parametrize("loader", ["strategy.strategy_lib", "strategy.strategy_rsi_lib"])
def test_both_loaders_use_the_gated_utc_bound(tmp_path, loader):
    frame = pd.DataFrame({"time": pd.date_range("2025-07-01", periods=4, freq="D"),
                          "instrument": "EUR_USD", "open": 1., "close": 1.,
                          "is_gap_bar": 0, "is_near_market_close": 0, "rsi_24": 50.})
    path = tmp_path / "bars.parquet"
    frame.to_parquet(path)
    kwargs = {"feature_cols": ["rsi_24"]} if loader.endswith(".strategy_lib") else {}
    result = importlib.import_module(loader).load_bars(
        str(path), "EUR_USD", since="2025-07-01T05:00:00+05:00",
        until="2025-07-02T05:00:00+05:00", **kwargs)
    assert len(result) == 2


def _grid():
    return [{"strategy": "s55", "variant": "base", "instrument": inst, "window": win,
             "cost_bps": cost, "n_trades": 10, "trades_per_year": 2,
             "total_return_pct": 1, "buyhold_return_pct": 2, "error": ""}
            for inst, win, cost in product(["A", "B"], ["full", "last_12m"], [0, 2, 5])]


@pytest.mark.parametrize("mutation, message", [
    (lambda rs: rs.pop(), "missing"),
    (lambda rs: rs.append(dict(rs[0])), "duplicate"),
    (lambda rs: rs[0].update(error="failed"), "failed cell"),
    (lambda rs: rs[0].update(total_return_pct="NaN"), "invalid result"),
    (lambda rs: rs[0].update(instrument="C"), "unexpected"),
])
def test_report_grid_rejects_invalid_evidence(mutation, message):
    rows = _grid()
    validate = lambda: validate_cell_grid(rows, ["A", "B"], ["full", "last_12m"],
                                         [0, 2, 5], ("strategy", "variant"))
    validate()
    mutation(rows)
    with pytest.raises(ValueError, match=message):
        validate()


def test_report_wins_count_instruments_once_across_overlapping_windows():
    from scripts.strategy_variants_report import aggregate
    rows = _grid()
    for row in rows:
        row.update(edge_vs_bh_pct=1, win_rate_pct=50)
    result = aggregate(rows, 2)["s55", "base"]
    assert result["win_instr"] == 2
    assert result["win_instr_by_window"] == {"full": 2, "last_12m": 2}


def test_finalist_pin_checker():
    from scripts.check_results import Report, check_finalist_pins
    reg = {"S-55": {"status": "finalist"}}
    rep = Report()
    check_finalist_pins({"strategies": {"S-55": {}}}, reg, rep)
    assert [finding.code for finding in rep.failures] == ["X16"]
    rep = Report()
    check_finalist_pins({"strategies": {"S-55": {
        "oos_variant": "looser", "oos_config_hash": "a" * 64}}}, reg, rep)
    assert not rep.failures


@pytest.mark.parametrize("close,ema", [(None, None), ([2.], [np.nan]),
                                      ([np.nan], [1.]), ([2.], [np.inf]), ([1.], [2.])])
def test_enabled_entry_gate_fails_closed(close, ema):
    from strategy.strategy_lib import entry_gate_allows
    assert not entry_gate_allows(True, close, ema, 0)
    assert entry_gate_allows(False, close, ema, 0)


def test_missing_gate_inputs_block_entries_but_allow_exit():
    from strategy.strategy_h1rsi_lib import H1RsiState
    rule = H1RsiState(np.array([60., 40.]), ema_gate=True,
                      gate_close=np.array([2., 2.]), gate_ema=np.array([np.nan, np.nan]))
    assert rule.desired_position(1) == 0
    rule.state = 1
    assert rule.desired_position(2) == 0


def test_vwap_cross_uses_previous_bars_atr():
    from strategy.strategy_vwap_stretch_lib import VwapStretchState
    # Previous normalized distance is .10; current is .50. Dividing the old
    # distance by the new ATR would incorrectly turn .10 into 1 and miss entry.
    rule = VwapStretchState(np.array([1., .5]), np.array([10., 1.]),
                            np.array([10., 10.]), np.array([5., 5.]), k=.25)
    assert rule.desired_position(1) == 0
    assert rule.desired_position(2) == 1


def test_cci_requires_band_position_and_rsi_gates_require_finite_context():
    from strategy.strategy_cci_reversion_lib import CciReversionState
    from strategy.strategy_rsi_slow_lib import RsiSlowState
    rule = CciReversionState(np.array([0.]), np.array([np.nan]), np.array([2.]), np.array([1.]))
    assert rule.desired_position(1) == 0
    for gate in ("st_gate", "adx_gate"):
        rule = RsiSlowState(np.array([0.]), np.array([np.nan]), np.array([np.nan]), **{gate: True})
        assert rule.desired_position(1) == 0


def test_in_sample_cache_reuses_reads_and_invalidates_replaced_file(tmp_path, monkeypatch):
    import duckdb
    from strategy.strategy_lib import cache_bars, load_bars
    frame = pd.DataFrame({"time": pd.date_range("2025-07-01", periods=4, freq="D"),
                          "instrument": "EUR_USD", "open": 1., "close": 1.,
                          "is_gap_bar": 0, "is_near_market_close": 0})
    path = tmp_path / "bars.parquet"
    frame.to_parquet(path)
    connect = duckdb.connect
    calls = []
    def counted_connect(*args, **kwargs):
        calls.append(1)
        return connect(*args, **kwargs)
    monkeypatch.setattr(duckdb, "connect", counted_connect)
    def load(until="2025-07-04"):
        return load_bars(str(path), "EUR_USD", [], until=until)
    with cache_bars():
        first = load()
        first.loc[0, "close"] = 9
        assert load().loc[0, "close"] == 1
        assert len(calls) == 1
        load("2025-07-03")
        assert len(calls) == 2
        frame["close"] = 2.
        replacement = tmp_path / "replacement.parquet"
        frame.to_parquet(replacement)
        replacement.replace(path)
        assert load().loc[0, "close"] == 2
        assert len(calls) == 3
        with pytest.raises(SystemExit):
            load("2025-08-01")
        assert len(calls) == 3  # The gate runs even with a populated cache.
    load()
    assert len(calls) == 4


def test_in_sample_fingerprint_does_not_depend_on_holdout_prices(tmp_path):
    frame = pd.DataFrame({"instrument": "EUR_USD", "open": [1., 2.], "close": [1., 2.],
                          "time": pd.to_datetime(["2025-07-01", "2025-08-02"], utc=True)})
    path = tmp_path / "bars.parquet"
    frame.to_parquet(path)
    before = rm._data_fingerprint(str(path), "full")
    frame.loc[1, "close"] = 99.
    frame.to_parquet(path)
    after = rm._data_fingerprint(str(path), "full")
    assert before["rows"] == after["rows"] == 1
    assert before["content_hash"] == after["content_hash"]


def test_all_strategy_clis_parse_without_reading_market_data(monkeypatch):
    import runpy
    root = Path(__file__).resolve().parents[1]
    monkeypatch.setattr("sys.argv", ["strategy", "--help"])
    for path in sorted((root / "strategy/code").glob("strategy_*.py")):
        with pytest.raises(SystemExit) as exc:
            runpy.run_path(str(path), run_name="__main__")
        assert exc.value.code == 0, path
