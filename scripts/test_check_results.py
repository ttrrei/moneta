#!/usr/bin/env python3
"""Self-test for scripts/check_results.py.

A checker that never fires is worthless, and one that fires on everything is
noise. This script proves both directions:

  * it builds a *legal* mini-repo from the real one (S-05 + S-06 with their
    CLIs and reports, S-01 dropped because its committed results are the
    known OOS-contamination case), asserts the checker PASSES it, and
  * then breaks one thing at a time and asserts the expected check code
    fires each time.

Zero dependencies (no pytest, no yaml, no duckdb) so it can run anywhere,
including a bare CI container.

    python scripts/test_check_results.py
"""

from __future__ import annotations

import csv
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
CHECKER = HERE / "check_results.py"

#: The S-06 registry Result cell already uses the honest "above buy-hold at
#: 0 bps only" phrasing (not a "beats buy-hold" claim), so the fixture just
#: inherits it. Kept here as the exact substring the X11 mutation targets.
S06_RESULT_PREFIX = "not a cross-market edge: above buy-hold on BTC at **0 bps only**"


# ---------------------------------------------------------------------------
# fixture construction
# ---------------------------------------------------------------------------

def build_fixture(dest: Path) -> None:
    """A legal mini-repo: the repo minus S-01, plus S-05/S-06's missing files."""
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)

    shutil.copytree(REPO / "config", dest / "config")
    cfg_path = dest / "config" / "strategies.yml"
    cfg = cfg_path.read_text(encoding="utf-8")
    cfg = re.sub(r'(?m)^  S-01:\n    timeframe: "5m"\n', "", cfg)
    cfg_path.write_text(cfg, encoding="utf-8")

    s = dest / "strategy"
    (s / "docs").mkdir(parents=True)
    (s / "code").mkdir(parents=True)
    (s / "results").mkdir(parents=True)

    reg = (REPO / "strategy" / "STRATEGY_REGISTRY.md").read_text(encoding="utf-8")
    reg = "\n".join(ln for ln in reg.splitlines() if not ln.startswith("| S-01 |")) + "\n"
    reg = reg.replace("| `rsi_24` | S-01, S-02, S-03 |", "| `rsi_24` | S-02, S-03 |")
    (s / "STRATEGY_REGISTRY.md").write_text(reg, encoding="utf-8")

    tl = (REPO / "strategy" / "trial_log.md").read_text(encoding="utf-8")
    tl = "\n".join(ln for ln in tl.splitlines() if "| S-01 |" not in ln) + "\n"
    (s / "trial_log.md").write_text(tl, encoding="utf-8")

    for d in ("S05", "S06"):
        src = REPO / "strategy" / "results" / d
        if src.exists():
            shutil.copytree(src, s / "results" / d)

    # The sweep CSVs are the committed evidence for the strategies that have no
    # results directory (S-08 … S-27); C5 validates them and evaluates S1–S3
    # from the `full`-window rows, so the fixture must carry them too.
    for name in ("iterations_2026-10-30.csv", "iterations_2026-11-01.csv"):
        src = REPO / "strategy" / "results" / name
        if src.exists():
            shutil.copy(src, s / "results" / name)

    for f in ("strategy_supertrend_lib.py", "strategy_ema_spread_lib.py",
              "oos_ledger.json"):
        p = REPO / "strategy" / f
        if p.exists():
            shutil.copy(p, s / f)

    for name in ("strategy_supertrend", "strategy_ema_spread"):
        (s / "code" / f"{name}.py").write_text('"""stub CLI for the fixture."""\n',
                                                encoding="utf-8")
        (s / "docs" / f"{name}_report.md").write_text(f"# {name} report\n\nstub\n",
                                                      encoding="utf-8")


# ---------------------------------------------------------------------------
# harness
# ---------------------------------------------------------------------------

def run_checker(root: Path, base_ledger: Path | None = None
                ) -> tuple[set[str], int, str]:
    cmd = [sys.executable, str(CHECKER), "--root", str(root), "--json"]
    if base_ledger is not None:
        cmd += ["--base-ledger", str(base_ledger)]
    out = subprocess.run(cmd, capture_output=True, text=True)
    raw = out.stdout + out.stderr
    try:
        data = json.loads(out.stdout)
    except json.JSONDecodeError:
        return {"ERROR"}, out.returncode, raw
    return ({f["code"] for f in data["findings"] if f["level"] == "FAIL"},
            out.returncode, raw)


def edit_csv(path: Path, fn) -> None:
    if not path.exists():
        return
    with open(path, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    if not rows:
        return
    fields = list(rows[0].keys())
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(fn(r) for r in rows)


def replace_in(path: Path, old: str, new: str) -> None:
    if path.exists():
        path.write_text(path.read_text(encoding="utf-8").replace(old, new),
                        encoding="utf-8")


S05_ROW = ("| S-05 | SuperTrend-24 direction follower | 5m | `st_dir_24_2` | "
           "st_dir_24_2 up | st_dir_24_2 down | long | **rejected** |")

#: A synthetic OOS strategy used by the X13 mutation cases. It is registered
#: (config + registry + trial log) but has NO in-sample results directory, so
#: only its `<ID>_oos` directory is present — exactly what Phase 2.4 commits.
#: The id must NOT collide with a real registry row (S-01 … S-27): the real
#: registry row would shadow the synthetic one and the X13 verdict check would
#: be skipped.
OOS_SID = "S-99"


def write_oos_dir(work: Path, status: str = "tested",
                  beats: int = 2, tpy: float = 40,
                  committed_pass: bool = True, committed_ib: int = 2) -> None:
    """Write a self-consistent OOS holdout matrix for the synthetic S-09.

    `beats` is how many instruments actually beat buy-hold at 2 bps (0..3);
    the rest lose. All cells use a trade-rate of `tpy`/year. The committed
    `pass`/`instruments_beating` columns are `committed_pass`/`committed_ib`,
    so a caller can set them to disagree with the recompute to trigger X13.
    """
    if str(REPO) not in sys.path:
        sys.path.insert(0, str(REPO))
    import strategy.schema as _s
    insts = ["EUR_USD", "BTC_USD", "XAU_USD"]
    dir_ = work / "strategy" / "results" / f"{OOS_SID}_oos"
    dir_.mkdir(parents=True, exist_ok=True)
    # register the synthetic strategy in config + registry + trial log
    cfgp = work / "config" / "strategies.yml"
    cfg = cfgp.read_text(encoding="utf-8")
    if f"  {OOS_SID}:" not in cfg:
        cfg = cfg.replace("  S-05:\n", f"  {OOS_SID}:\n    timeframe: \"5m\"\n  S-05:\n", 1)
        cfgp.write_text(cfg, encoding="utf-8")
    regp = work / "strategy" / "STRATEGY_REGISTRY.md"
    reg = regp.read_text(encoding="utf-8")
    if f"| {OOS_SID} |" not in reg:
        row = (f"| {OOS_SID} | synthetic OOS | 5m | `x` | a | b | long | **{status}** "
               f"| [code/strategy_syn.py](code/strategy_syn.py) "
               f"| [docs/strategy_syn_report.md](docs/strategy_syn_report.md) "
               f"| 2026-10-26 | n/a |")
        reg = reg.replace("## Indicator usage map", row + "\n\n## Indicator usage map", 1)
        regp.write_text(reg, encoding="utf-8")
    tlp = work / "strategy" / "trial_log.md"
    tl = tlp.read_text(encoding="utf-8")
    if f"| {OOS_SID} |" not in tl:
        tl += (f"\n| 1 | 2026-10-26 | {OOS_SID} | synthetic | oos | **{status}** "
               f"| n/a | 0 |\n")
        tlp.write_text(tl, encoding="utf-8")
    # thin CLI + report so X6/X7/X8 (in-sample) are satisfied if ever hit
    (work / "strategy" / "code" / "strategy_syn.py").write_text("stub\n", encoding="utf-8")
    (work / "strategy" / "docs" / "strategy_syn_report.md").write_text("# stub\n", encoding="utf-8")

    # L2: an adjudicated OOS trial row must have a ledger consumption record.
    # A legal holdout run reserved before loading — so add a `reserved` record
    # for the synthetic strategy (this satisfies L2 and keeps these cases
    # testing X13's pass/fail logic, not L2).
    lp = work / "strategy" / "oos_ledger.json"
    try:
        ld = json.loads(lp.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        ld = {"version": 1, "consumptions": []}
    ld.setdefault("consumptions", [])
    if not any(isinstance(r, dict) and str(r.get("strategy", "")).upper() == OOS_SID
               and r.get("holdout_id") == "oos1" for r in ld["consumptions"]):
        ld["consumptions"].append({
            "strategy": OOS_SID.lower().replace("-", ""), "holdout_id": "oos1",
            "holdout_start": "2025-08-01", "holdout_end": "2026-10-22",
            "reserved_at": "2026-10-26", "status": "reserved"})
    lp.write_text(json.dumps(ld, indent=2) + "\n", encoding="utf-8")

    fields = _s.OOS_HEADER
    with open(dir_ / "summary.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for idx, inst in enumerate(insts):
            beat_this = idx < beats
            for cost in (0.0, 2.0, 5.0):
                # ret > buyhold only at the 2 bps tier for the `beats` insts
                if cost == 2.0:
                    tr, bh = (10.0, 5.0) if beat_this else (-5.0, 10.0)
                else:
                    tr, bh = (0.0, 5.0) if beat_this else (0.0, 5.0)
                w.writerow({
                    "strategy": OOS_SID.lower().replace("-", ""),
                    "instrument": inst, "window": "oos", "timeframe": "5m",
                    "cost_bps": cost, "entry_guard": "off",
                    "start": "2025-08-01 00:00:00+00:00",
                    "end": "2026-10-22 00:00:00+00:00",
                    "n_bars": 100, "n_trades": 10,
                    "total_return_pct": tr, "buyhold_return_pct": bh,
                    "max_drawdown_pct": 10, "win_rate_pct": 50,
                    "avg_trade_return_pct": 0, "sharpe": 1, "sharpe_weekly": 1,
                    "trades_per_year": tpy, "exposure_pct": 50,
                    "mean_net_position_pct": 50, "span_years": 1.224,
                    "beat_bh_at_2bps": beat_this and cost == 2.0,
                    "instruments_beating": committed_ib,
                    "pass": committed_pass,
                })


def _drop_column(path: Path, col: str) -> None:
    """Rewrite a committed summary.csv without `col` (header + all rows)."""
    if not path.exists():
        return
    with open(path, newline="", encoding="utf-8") as fh:
        rd = csv.DictReader(fh)
        fields = [f for f in (rd.fieldnames or []) if f != col]
        rows = list(rd)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)


def _ledger_json(records: list[dict]) -> str:
    """A one-record ledger file body."""
    return '{"version": 1, "consumptions": ' + json.dumps(records) + "}\n"


def _one_rec(strategy: str, status: str, reason: str | None = None) -> dict:
    rec = {"strategy": strategy, "holdout_id": "oos1",
           "holdout_start": "2025-08-01", "holdout_end": "2026-10-22",
           "status": status}
    if reason is not None:
        rec["reason"] = reason
    return rec


def _set_ledgers(w: Path, cur_status: str, cur_reason: str | None,
                 base_status: str, base_reason: str | None = None) -> None:
    """Write the committed ledger (cur_status) and the base ledger
    (base_status) for the S-05/oos1 record — used by the L1 void-flow cases."""
    (w / "strategy/oos_ledger.json").write_text(
        _ledger_json([_one_rec("S05", cur_status, cur_reason)]), encoding="utf-8")
    (w / "base_oos_ledger.json").write_text(
        _ledger_json([_one_rec("S05", base_status, base_reason)]), encoding="utf-8")


def _c5_flip_candidate(w: Path) -> None:
    """C5 S2 mutation: S-10 has NO results directory, so its S1–S3 evidence
    comes from the sweep CSVs. It loses to buy-hold in every `full`-window
    cell, so flipping its registry status to a non-terminal one (candidate)
    must be flagged by S2 — proving the checker reaches a dir-less strategy
    through the CSV."""
    reg = w / "strategy/STRATEGY_REGISTRY.md"
    t = reg.read_text(encoding="utf-8")
    line = next((l for l in t.splitlines() if l.startswith("| S-10 |")), None)
    if line is not None:
        t = t.replace(line, line.replace("**rejected**", "**candidate**"), 1)
        reg.write_text(t, encoding="utf-8")


def _void_with_output(w: Path) -> None:
    """A voided S-05 reservation (with a reason) AND an OOS output file —
    the "void a result that was read" backdoor (must be L1)."""
    (w / "strategy/oos_ledger.json").write_text(
        _ledger_json([_one_rec("S05", "voided", "crash after reserve")]),
        encoding="utf-8")
    out = w / "strategy" / "results" / "S05_oos"
    out.mkdir(parents=True, exist_ok=True)
    (out / "EUR_USD__oos__c2.json").write_text("{}\n", encoding="utf-8")


CASES = [
    ("baseline: a legal repo must PASS", set(), 0, None, lambda w: None),

    ("window cap did not apply -> W3 + W4", {"W3", "W4"}, 1, None,
     lambda w: edit_csv(w / "strategy/results/S05/summary.csv",
                        lambda r: {**r, "end": "2026-10-24 07:55:00+11:00"}
                        if r["window"] == "full" else r)),

    ("timeframe != config registry -> X10", {"X10"}, 1, None,
     lambda w: edit_csv(w / "strategy/results/S05/summary.csv",
                        lambda r: {**r, "timeframe": "1h"})),

    ("trial_log names a timeframe the config disagrees with -> X12", {"X12"}, 1, None,
     lambda w: replace_in(w / "strategy/trial_log.md",
                          "5m SuperTrend(24, 2.0)", "1h SuperTrend(24, 2.0)")),

    ("registry quotes a number absent from the matrix -> G5", {"G5"}, 1, None,
     lambda w: replace_in(w / "strategy/STRATEGY_REGISTRY.md", "+2402%", "+9999%")),

    ("missing strategy report -> X8", {"X8"}, 1, None,
     lambda w: (w / "strategy/docs/strategy_supertrend_report.md").unlink()),

    ("missing thin CLI -> X7", {"X7"}, 1, None,
     lambda w: (
         replace_in(w / "strategy/STRATEGY_REGISTRY.md",
                    "[code/strategy_supertrend.py](code/strategy_supertrend.py)",
                    "[strategy_supertrend_lib.py](strategy_supertrend_lib.py)"),
         (w / "strategy/code/strategy_supertrend.py").unlink())),

    ("two adjudicated oos rows -> W5", {"W5"}, 1, None,
     lambda w: (w / "strategy/trial_log.md").write_text(
         (w / "strategy/trial_log.md").read_text(encoding="utf-8")
         + "\n| 4 | 2026-10-28 | S-05 | first holdout run | oos | **rejected** | x | 3 |\n"
           "| 5 | 2026-10-28 | S-05 | second holdout run | oos | **rejected** | x | 3 |\n",
         encoding="utf-8")),

    ("registry status != trial-log outcome -> X5", {"X5"}, 1, None,
     lambda w: replace_in(w / "strategy/STRATEGY_REGISTRY.md", S05_ROW,
                          S05_ROW.replace("**rejected**", "**tested**"))),

    # §1.6 (check F): a `finalist` must actually beat the in-sample bar.
    # S-05 beats 0 of 3 instruments at 2 bps (and has 10402 trades), so making
    # it a `finalist` must be flagged as not satisfying the promotion bar.
    ("finalist row fails the in-sample bar -> F", {"F"}, 1, None,
     lambda w: replace_in(w / "strategy/STRATEGY_REGISTRY.md", S05_ROW,
                          S05_ROW.replace("**rejected**", "**finalist**"))),

    ("stop condition met but status is not rejected -> S1", {"S1"}, 1, None,
     lambda w: replace_in(w / "strategy/STRATEGY_REGISTRY.md", S05_ROW,
                          S05_ROW.replace("**rejected**", "**tested**"))),

    ("registry claims a buy-hold win the matrix contradicts -> X11", {"X11"}, 1, None,
     lambda w: replace_in(w / "strategy/STRATEGY_REGISTRY.md",
                          S06_RESULT_PREFIX,
                          "beats buy-hold on BTC across all 3 cost tiers")),

    ("results dir name != strategy id -> X1", {"X1"}, 1, None,
     lambda w: (w / "strategy/results/S05").rename(w / "strategy/results/S99")),

    ("in-sample window without an until cap -> refuse to run", {"ERROR"}, 1,
     "windows.full.until is missing",
     lambda w: replace_in(w / "config/strategies.yml",
                          'until: "2025-07-31"        # day before oos.holdout_start',
                          "until: null")),

    # S-99 cannot exist in the registry (real ids are S-01 … S-27).
    ("config strategy missing from the registry -> X3", {"X3"}, 1, None,
     lambda w: replace_in(w / "config/strategies.yml",
                          '  S-05:\n    timeframe: "5m"',
                          '  S-05:\n    timeframe: "5m"\n  S-99:\n    timeframe: "5m"')),

    ("trial_log row missing -> X4", {"X4"}, 1, None,
     lambda w: (w / "strategy/trial_log.md").write_text(
         "\n".join(ln for ln in (w / "strategy/trial_log.md").read_text(
             encoding="utf-8").splitlines() if "| S-05 |" not in ln) + "\n",
         encoding="utf-8")),

    ("registry Report link points nowhere -> X6", {"X6"}, 1, None,
     lambda w: replace_in(w / "strategy/STRATEGY_REGISTRY.md",
                          "(docs/strategy_supertrend_report.md)", "(docs/nope_report.md)")),

    # ---- X13: machine pass/fail for an OOS holdout matrix (Phase 2.4) ----
    # A VALID OOS directory (a distinct `<ID>_oos`) must pass the checker.
    ("OOS dir passes with a consistent pass verdict -> ok", set(), 0, None,
     lambda w: write_oos_dir(w, status="tested", beats=2, tpy=40,
                             committed_pass=True, committed_ib=2)),
    # committed pass=True but only 1 instrument actually beats -> inconsistent
    ("OOS pass inconsistent with the matrix -> X13", {"X13"}, 1, None,
     lambda w: write_oos_dir(w, status="tested", beats=1, tpy=40,
                             committed_pass=True, committed_ib=1)),
    # trade ceiling breached (60/yr > 54/yr) -> must fail
    ("OOS trade-ceiling breach -> X13", {"X13"}, 1, None,
     lambda w: write_oos_dir(w, status="rejected", beats=2, tpy=60,
                             committed_pass=False, committed_ib=2)),
    # status `tested` but the OOS verdict fails (only 1 beats) -> must fail
    ("OOS `tested` status on a failing holdout -> X13", {"X13"}, 1, None,
     lambda w: write_oos_dir(w, status="tested", beats=1, tpy=40,
                             committed_pass=False, committed_ib=1)),
    # a mislabelled OOS dir (name != the strategy id) -> X1
    ("OOS dir name != strategy id -> X1", {"X1"}, 1, None,
     lambda w: (write_oos_dir(w, status="tested", beats=2, tpy=40,
                              committed_pass=True, committed_ib=2),
                (w / "strategy" / "results" / f"{OOS_SID}_oos")
                .rename(w / "strategy" / "results" / "S77_oos"))),

    # ---- H1 (§3.3): committed header must equal the shared field list -----
    # A summary.csv missing a required column (sharpe_weekly / ...) -> the
    # header no longer matches strategy/schema.py -> H1.
    ("committed summary.csv missing a shared column -> H1", {"H1"}, 1, None,
     lambda w: _drop_column(w / "strategy" / "results" / "S05" / "summary.csv",
                            "sharpe_weekly")),

    # ---- L0: the holdout end has a single source of truth ----------------
    # windows.oos.until must be oos.holdout_end + 1 day; if someone edits the
    # two fields apart the checker must fail (not silently let them drift).
    ("holdout end fields disagree -> L0", {"L0"}, 1, None,
     lambda w: replace_in(w / "config/strategies.yml",
                          'until: "2026-10-23"', 'until: "2026-10-31"')),

    # ---- L1: the ledger is append-only ------------------------------------
    # The committed ledger is a superset of the base ledger (a record may never
    # be removed). A base record missing from the current ledger -> L1.
    ("ledger record removed vs base -> L1", {"L1"}, 1, None,
     lambda w: (
         (w / "strategy/oos_ledger.json").write_text(
             '{"version": 1, "consumptions": []}\n', encoding="utf-8"),
         (w / "base_oos_ledger.json").write_text(
             '{"version": 1, "consumptions": ['
             '{"strategy": "S05", "holdout_id": "oos1", '
             '"holdout_start": "2025-08-01", "holdout_end": "2026-10-22", '
             '"status": "reserved"}]}\n', encoding="utf-8")),
     lambda w: w / "base_oos_ledger.json"),
    # The base ledger holds one consumption; the committed ledger keeps it
    # plus one more -> a valid superset -> must PASS (append-only satisfied).
    ("ledger is a superset of the base -> ok", set(), 0, None,
     lambda w: (
         (w / "strategy/oos_ledger.json").write_text(
             '{"version": 1, "consumptions": ['
             '{"strategy": "S05", "holdout_id": "oos1", '
             '"holdout_start": "2025-08-01", "holdout_end": "2026-10-22", '
             '"status": "reserved"},'
             '{"strategy": "S06", "holdout_id": "oos1", '
             '"holdout_start": "2025-08-01", "holdout_end": "2026-10-22", '
             '"status": "reserved"}]}\n', encoding="utf-8"),
         (w / "base_oos_ledger.json").write_text(
             '{"version": 1, "consumptions": ['
             '{"strategy": "S05", "holdout_id": "oos1", '
             '"holdout_start": "2025-08-01", "holdout_end": "2026-10-22", '
             '"status": "reserved"}]}\n', encoding="utf-8")),
     lambda w: w / "base_oos_ledger.json"),
    # ---- L1 void-flow (follow-up review §1.3 / §3.4) -----------------------
    # reserved -> voided keeps the same identity; the status change is NOT a
    # record removal (status is not in the identity key).
    ("reserved -> voided with a reason is append-only-safe -> ok", set(), 0, None,
     lambda w: _set_ledgers(w, "voided", "crash after reserve, no result read", "reserved"),
     lambda w: w / "base_oos_ledger.json"),
    # ---- C5: the sweep CSVs are evidence for strategies with no results dir --
    # S-09 has no results directory, so S1–S3 are evaluated from its sweep-CSV
    # `full`-window rows. It loses to buy-hold in every `full` cell, so flipping
    # its status to a non-terminal one (candidate) must be flagged by S2 —
    # proving the checker can reach a dir-less strategy through the CSV.
    ("sweep strategy loses everywhere but status is not rejected -> S2", {"S2"}, 1, None,
     _c5_flip_candidate),
    # Registered (config) but has NO committed evidence: no results dir and no
    # sweep-CSV row -> X14 (new code, §C5).
    ("registered strategy with no committed evidence -> X14", {"X14"}, 1, None,
     lambda w: replace_in(w / "config/strategies.yml",
                          '  S-05:\n    timeframe: "5m"',
                          '  S-05:\n    timeframe: "5m"\n  S-98:\n    timeframe: "5m"')),
    # §B2: the OOS dir's committed evidence is summary.csv / matrix.md (the
    # per-cell JSON files are git-ignored). A voided record with a committed
    # summary.csv in the OOS dir must still be caught.
    ("voided record with committed summary.csv OOS output -> L1", {"L1"}, 1, None,
     lambda w: (write_oos_dir(w, status="rejected", beats=0, tpy=40,
                              committed_pass=False, committed_ib=0),
                (w / "strategy/oos_ledger.json").write_text(
                    _ledger_json([_one_rec(OOS_SID, "voided",
                                           "crash after reserve, no result read")]),
                    encoding="utf-8"))),
    # A voided record must carry a written reason (L1b).
    ("voided record without a reason -> L1", {"L1"}, 1, None,
     lambda w: (w / "strategy/oos_ledger.json").write_text(
         _ledger_json([_one_rec("S05", "voided")]), encoding="utf-8")),
    # A void is only valid when no OOS output exists for the strategy (L1c).
    ("voided record with OOS output files -> L1", {"L1"}, 1, None,
     lambda w: _void_with_output(w)),
    # A completed record must stay completed (terminal — no re-open to reserved).
    ("completed record re-opened to reserved -> L1", {"L1"}, 1, None,
     lambda w: _set_ledgers(w, "reserved", None, "completed"),
     lambda w: w / "base_oos_ledger.json"),

    # ---- L2: ledger <-> trial_log cross-consistency -----------------------
    # An adjudicated `oos` trial row must have a ledger consumption record;
    # with an empty ledger it does not -> L2.
    ("adjudicated oos trial row without a ledger record -> L2", {"L2"}, 1, None,
     lambda w: (w / "strategy/trial_log.md").write_text(
         (w / "strategy/trial_log.md").read_text(encoding="utf-8")
         + "\n| 9 | 2026-10-28 | S-05 | single holdout run | oos | **rejected** | x | 3 |\n",
         encoding="utf-8")),
    # The reverse direction: a `completed` ledger record must have an
    # adjudicated `oos` trial row. With the ledger saying S-05 `completed` but
    # no oos trial row, that is L2. (L1 is not in scope — no --base-ledger.)
    ("completed ledger record without an oos trial row -> L2", {"L2"}, 1, None,
     lambda w: (w / "strategy/oos_ledger.json").write_text(
         '{"version": 1, "consumptions": [{"strategy": "S05", '
         '"holdout_id": "oos1", "holdout_start": "2025-08-01", '
         '"holdout_end": "2026-10-22", "status": "completed"}]}\n',
         encoding="utf-8")),
]


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="check-results-selftest-"))
    template = tmp / "template"
    work = tmp / "work"
    passed = failed = 0
    try:
        for case in CASES:
            name, expect_codes, expect_exit, expect_output, mutate = case[:5]
            base_ledger_fn = case[5] if len(case) > 5 else None  # work -> Path | None
            build_fixture(template)
            if work.exists():
                shutil.rmtree(work)
            shutil.copytree(template, work)
            mutate(work)
            base_ledger = base_ledger_fn(work) if base_ledger_fn else None
            got, code, raw = run_checker(work, base_ledger)
            if expect_codes == set():
                ok = (got == set()) and (code == expect_exit)
            else:
                ok = expect_codes <= got and (code == expect_exit)
            if ok and expect_output:
                ok = expect_output in raw
            print(("PASS " if ok else "FAIL ") + name)
            if not ok:
                print(f"        expected {sorted(expect_codes)} + exit {expect_exit}"
                      + (f" + {expect_output!r}" if expect_output else ""))
                print(f"        got      {sorted(got)} + exit {code}")
                for line in raw.splitlines()[:14]:
                    print(f"        | {line}")
                failed += 1
            else:
                passed += 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print()
    print(f"{passed}/{len(CASES)} mutation cases passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
