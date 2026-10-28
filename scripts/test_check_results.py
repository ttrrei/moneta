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

    for f in ("strategy_supertrend_lib.py", "strategy_ema_spread_lib.py"):
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

def run_checker(root: Path) -> tuple[set[str], int, str]:
    out = subprocess.run([sys.executable, str(CHECKER), "--root", str(root), "--json"],
                         capture_output=True, text=True)
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

CASES = [
    ("baseline: a legal repo must PASS", set(), 0, None, lambda w: None),

    ("window cap did not apply -> W3 + W4", {"W3", "W4"}, 1, None,
     lambda w: edit_csv(w / "strategy/results/S05/summary.csv",
                        lambda r: {**r, "end": "2026-10-24 07:55:00+11:00"}
                        if r["window"] == "full" else r)),

    ("timeframe != config registry -> X10", {"X10"}, 1, None,
     lambda w: edit_csv(w / "strategy/results/S05/summary.csv",
                        lambda r: {**r, "timeframe": "1h"})),

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

    ("config strategy missing from the registry -> X3", {"X3"}, 1, None,
     lambda w: replace_in(w / "config/strategies.yml",
                          '  S-05:\n    timeframe: "5m"',
                          '  S-05:\n    timeframe: "5m"\n  S-09:\n    timeframe: "5m"')),

    ("trial_log row missing -> X4", {"X4"}, 1, None,
     lambda w: (w / "strategy/trial_log.md").write_text(
         "\n".join(ln for ln in (w / "strategy/trial_log.md").read_text(
             encoding="utf-8").splitlines() if "| S-05 |" not in ln) + "\n",
         encoding="utf-8")),

    ("registry Report link points nowhere -> X6", {"X6"}, 1, None,
     lambda w: replace_in(w / "strategy/STRATEGY_REGISTRY.md",
                          "(docs/strategy_supertrend_report.md)", "(docs/nope_report.md)")),
]


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="check-results-selftest-"))
    template = tmp / "template"
    work = tmp / "work"
    passed = failed = 0
    try:
        for name, expect_codes, expect_exit, expect_output, mutate in CASES:
            build_fixture(template)
            if work.exists():
                shutil.rmtree(work)
            shutil.copytree(template, work)
            mutate(work)
            got, code, raw = run_checker(work)
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
