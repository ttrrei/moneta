"""Generate fixed-ID wrappers and align registry links for S-113..S-132."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from strategy.strategy_diverse_lib import RULES  # noqa: E402


def main() -> None:
    registry_path = ROOT / "strategy" / "STRATEGY_REGISTRY.md"
    registry_text = registry_path.read_text(encoding="utf-8")
    for key, spec in RULES.items():
        lib_name = f"strategy_{spec.slug}_lib"
        cli_name = f"strategy_{spec.slug}"
        lib = f'''"""Fixed-ID adapter for {spec.sid}: {spec.name}."""

from strategy.strategy_diverse_lib import run_rule


def run(parquet: str, instrument: str, timeframe: str = "{spec.timeframe}",
        since: str | None = None, until: str | None = None,
        cost_bps: float = 2.0, entry_guard: bool = False,
        oos_token: object | None = None) -> dict:
    return run_rule(
        parquet=parquet, instrument=instrument, timeframe=timeframe,
        since=since, until=until, cost_bps=cost_bps,
        entry_guard=entry_guard, oos_token=oos_token, strategy_id="{key}")


__all__ = ["run"]
'''
        cli = f'''"""Thin CLI for {spec.sid}: {spec.name}."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = str(Path(__file__).resolve().parents[2])
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from strategy.strategy_diverse_lib import cli_main


if __name__ == "__main__":
    cli_main("{key}")
'''
        (ROOT / "strategy" / f"{lib_name}.py").write_text(lib, encoding="utf-8")
        (ROOT / "strategy" / "code" / f"{cli_name}.py").write_text(cli, encoding="utf-8")
        for line in registry_text.splitlines():
            if line.startswith(f"| {spec.sid} |"):
                updated = line.replace(
                    "[code/strategy_diverse.py](code/strategy_diverse.py)",
                    f"[code/{cli_name}.py](code/{cli_name}.py)")
                updated = updated.replace(
                    f"[docs/strategy_batch_20261030_{key}_report.md](docs/strategy_batch_20261030_{key}_report.md)",
                    f"[docs/{cli_name}_report.md](docs/{cli_name}_report.md)")
                registry_text = registry_text.replace(line, updated, 1)
                break
        print(spec.sid, lib_name, cli_name)
    registry_path.write_text(registry_text, encoding="utf-8")


if __name__ == "__main__":
    main()
