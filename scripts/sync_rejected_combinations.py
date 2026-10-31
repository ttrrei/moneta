"""Append missing rejected strategies to the registry's no-repeat table.

Reasons and links come from the existing registry/trial log; no results or
statuses are inferred or changed. Existing rows are preserved.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from strategy.registry import parse_registry, parse_trial_log


def sync(root: Path) -> int:
    path = root / "strategy/STRATEGY_REGISTRY.md"
    text = path.read_text(encoding="utf-8")
    start = text.index("## Rejected combinations")
    end = text.index("\n## ", start + 1)
    section = text[start:end]
    present = set(re.findall(r"\(S-(\d+)\)", section))
    trials = {row["strategy_id"]: row for row in parse_trial_log(root / "strategy/trial_log.md")}
    additions = []
    for sid, row in parse_registry(path).items():
        if row.get("status") != "rejected" or sid[2:] in present:
            continue
        trial = trials.get(sid)
        if trial is None:
            raise ValueError(f"{sid}: no trial-log reason")
        combination = f"{row['timeframe']} {row['key indicators']}; {row['entry logic (short)']} ({sid})"
        reason = f"{trial['result']}. Evidence: {row['report']}"
        additions.append(f"| {combination} | {reason} |")
    if additions:
        text = text[:end].rstrip() + "\n" + "\n".join(additions) + "\n" + text[end:]
        path.write_text(text, encoding="utf-8")
    return len(additions)


if __name__ == "__main__":
    print(f"Added {sync(Path(__file__).resolve().parents[1])} missing rejection records")
