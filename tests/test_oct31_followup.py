"""Window semantics, nomination integrity and measured cost attribution."""
from __future__ import annotations

import importlib
import subprocess
from copy import deepcopy
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

from strategy import provenance, schema
from strategy import run_matrix as rm


@pytest.fixture
def boundary_file(tmp_path):
    path = tmp_path / "boundaries.parquet"
    pd.DataFrame({"time": pd.to_datetime(["2025-07-31 00:00", "2025-07-31 12:00",
                                         "2025-07-31 23:55", "2025-08-01 00:00"], utc=True),
                  "instrument": "EUR_USD", "open": 1., "close": 1., "rsi_24": 50.,
                  "is_gap_bar": 0, "is_near_market_close": 0}).to_parquet(path)
    return path


@pytest.mark.parametrize("name", ["strategy.strategy_lib", "strategy.strategy_rsi_lib"])
def test_date_until_includes_entire_day_but_exact_timestamp_is_unchanged(boundary_file, name):
    module = importlib.import_module(name)
    kw = {"feature_cols": ["rsi_24"], "not_null_cols": ["rsi_24"]} if name.endswith(".strategy_lib") else {}
    def load(until):
        return module.load_bars(str(boundary_file), "EUR_USD", since="2025-07-31", until=until, **kw)
    assert len(load("2025-07-31")) == 3
    assert len(load("2025-07-31T00:00:00+00:00")) == 1
    assert len(load("2025-07-31T17:00:00+05:00")) == 2
    with pytest.raises(SystemExit):
        load("2025-08-01")


def test_fingerprint_and_loader_agree_at_final_day(boundary_file):
    fingerprint = rm._data_fingerprint(str(boundary_file), "full")
    assert fingerprint["rows"] == 3
    assert fingerprint["tmax"].startswith("2025-07-31 23:55")
    from strategy.oos_token import query_until, normalize_bound
    assert normalize_bound("2025-07-31") == "2025-07-31T00:00:00+00:00"
    assert query_until("2025-07-31") == ("2025-08-01T00:00:00+00:00", True)
    assert query_until("2026-10-23") == ("2026-10-23T00:00:00+00:00", True)
    assert rm._window_bounds({"windows": {"day": {"since": "2025-07-31", "until": "2025-07-31"}}},
                             "day") == ("2025-07-31", "2025-07-31")


def test_s01_uses_shared_cache_and_boundary_operators_are_distinct(boundary_file, monkeypatch):
    import duckdb
    from strategy.strategy_lib import cache_bars
    from strategy.strategy_rsi_lib import load_bars
    calls = []
    connect = duckdb.connect
    def counted(*args, **kwargs):
        calls.append(1)
        return connect(*args, **kwargs)
    monkeypatch.setattr(duckdb, "connect", counted)
    with cache_bars():
        assert len(load_bars(str(boundary_file), "EUR_USD", until="2025-07-31")) == 3
        assert len(load_bars(str(boundary_file), "EUR_USD", until="2025-07-31")) == 3
        assert len(calls) == 1
        # Same resolved midnight, different operator: July 30 excludes the
        # first row; an explicit July 31 midnight includes it.
        assert len(load_bars(str(boundary_file), "EUR_USD", until="2025-07-30")) == 0
        assert len(load_bars(str(boundary_file), "EUR_USD", until="2025-07-31T00:00:00Z")) == 1
        assert len(calls) == 3


@pytest.fixture
def frozen_repo(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    def git(*args):
        return subprocess.check_output(["git", *args], cwd=root, text=True, stderr=subprocess.DEVNULL).strip()
    git("init", "-q")
    (root / "strategy").mkdir()
    (root / "strategy/engine.py").write_text("value = 1\n")
    (root / "config").mkdir()
    cfg = {"strategies": {"S-01": {"timeframe": "5m"}},
           "windows": {"full": {"since": None, "until": "2025-07-31"}}}
    (root / "config/strategies.yml").write_text(yaml.safe_dump(cfg))
    (root / ".gitignore").write_text("data/\n")
    def commit():
        git("add", ".")
        git("-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "-qm", "fixture")
    commit()
    (root / "data").mkdir()
    data = root / "data/bars.parquet"
    data.write_bytes(b"opaque synthetic fixture data")
    freeze = provenance.nomination_freeze(root, cfg, data)
    cfg["strategies"]["S-01"].update(freeze)
    (root / "config/strategies.yml").write_text(yaml.safe_dump(cfg))
    commit()  # Metadata may be committed after the frozen implementation.
    return root, cfg, data, commit


def test_nomination_metadata_commit_does_not_invalidate_implementation(frozen_repo):
    root, cfg, data, _ = frozen_repo
    assert provenance.verify_freeze(root, cfg, cfg["strategies"]["S-01"], data)["oos_dirty"] is False


@pytest.mark.parametrize("mutation", ["code", "data", "settings", "dirty"])
def test_same_parameters_cannot_hide_a_changed_implementation_or_data(frozen_repo, mutation):
    root, cfg, data, commit = frozen_repo
    if mutation in ("code", "dirty"):
        (root / "strategy/engine.py").write_text("value = 2\n")
        if mutation == "code":
            commit()
    elif mutation == "data":
        data.write_bytes(b"changed ignored data")
    else:
        cfg["windows"]["full"]["until"] = "2025-07-30"
    with pytest.raises(ValueError, match="changed|clean working tree"):
        provenance.verify_freeze(root, cfg, cfg["strategies"]["S-01"], data)


def test_dirty_nomination_does_not_read_data(frozen_repo, monkeypatch):
    root, cfg, data, _ = frozen_repo
    (root / "uncommitted.txt").write_text("unreviewed")
    monkeypatch.setattr(provenance, "file_fingerprint", lambda path: pytest.fail("data must not be read"))
    with pytest.raises(ValueError, match="clean working tree"):
        provenance.nomination_freeze(root, cfg, data)


def test_matrix_refuses_missing_implementation_freeze_before_read_or_reserve(tmp_path, monkeypatch):
    from strategy.variants import resolve
    cfg = deepcopy(rm._load_config())
    resolved = resolve("s55", "looser", cfg=cfg)
    cfg["strategies"]["S-55"].update(
        oos_variant="looser",
        oos_config_hash=rm.config_hash(resolved.timeframe, resolved.entry_guard, resolved.rule_params))
    monkeypatch.setattr(rm, "_load_config", lambda: cfg)
    # Isolate freeze validation from the independently tested status gate.
    monkeypatch.setattr(rm, "_check_oos_once", lambda *args: None)
    monkeypatch.setattr(rm, "_data_fingerprint", lambda *args: pytest.fail("data must not be read"))
    monkeypatch.setattr(rm, "_reserve_oos", lambda *args: pytest.fail("ledger must not be written"))
    with pytest.raises(SystemExit, match="oos_code_commit"):
        rm.run_matrix("s55", rm.INSTRUMENTS, ["oos"], rm.COST_TIERS,
                      None, None, tmp_path, variant="looser")


def _oos_rows():
    return [{"instrument": instrument, "window": "oos", "cost_bps": cost,
             "total_return_pct": 10., "buyhold_return_pct": 5., "n_trades": 10,
             "trades_per_year": 20., "mean_net_position_pct": 20.}
            for instrument in schema.OOS_INSTRUMENTS for cost in schema.OOS_COST_TIERS]


@pytest.mark.parametrize("mutation", ["missing_rate", "nan", "inf", "missing_cell", "duplicate"])
def test_oos_adjudication_fails_closed_on_bad_data(mutation):
    rows = _oos_rows()
    assert schema.oos_pass_fields(rows)["pass"]
    if mutation == "missing_rate":
        del rows[0]["trades_per_year"]
    elif mutation in ("nan", "inf"):
        rows[0]["trades_per_year"] = float(mutation)
    elif mutation == "missing_cell":
        rows.pop()
    else:
        rows.append(dict(rows[0]))
    verdict = schema.oos_pass_fields(rows)
    assert verdict["invalid_data"] and not verdict["pass"]


def test_cost_attribution_distinguishes_positive_gross_from_positive_net():
    from scripts.audit_research import cost_diagnostics
    rows = [{"strategy": "s01", "variant": "base", "instrument": "EUR_USD", "window": "full",
             "cost_bps": cost, "total_return_pct": ret, "buyhold_return_pct": 5., "n_trades": 10}
            for cost, ret in [(0., 2.), (2., -1.)]]
    summary, cells = cost_diagnostics(rows)
    assert summary["positive_gross_bucket_net_outcomes"] == {"no_positive_net_return": 1}
    assert cells[0]["cost_erased_positive_return"]
    assert not cells[0]["cost_erased_benchmark_edge"]


def test_recorded_decisions_equal_fresh_rule_at_every_cost():
    from scripts.recompute_repairs import PositionReplay
    from strategy.strategy_vwap_stretch_lib import VwapStretchState
    from strategy.engine import BarFrame, run_backtest
    args = [np.array([1., .5, -.2, 1., 2., -.1]), np.array([10., 1., 1., 1., 1., 1.]),
            np.ones(6) * 10, np.ones(6) * 5]
    bars = BarFrame(open=np.arange(6) + 10., close=np.arange(6) + 11.)
    decisions = PositionReplay(VwapStretchState(*args), 6)
    for cost in (0., 2., 5.):
        assert run_backtest(bars, decisions, cost).to_dict() == run_backtest(bars, VwapStretchState(*args), cost).to_dict()
