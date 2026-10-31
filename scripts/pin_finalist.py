"""Print a finalist nomination's resolved config and YAML pin; never write files."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from strategy.run_matrix import config_hash
from strategy.variants import resolve
from strategy.provenance import nomination_freeze


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("strategy")
    parser.add_argument("variant", nargs="?", default="base")
    args = parser.parse_args()
    try:
        resolved = resolve(args.strategy, args.variant)
        from strategy.run_matrix import _load_config
        from strategy.strategy_lib import TIMEFRAME_PARQUET
        root = Path(__file__).resolve().parents[1]
        frozen = nomination_freeze(root, _load_config(), root / TIMEFRAME_PARQUET[resolved.timeframe])
    except (KeyError, ValueError, OSError) as exc:
        parser.error(str(exc))
    print(json.dumps({"timeframe": resolved.timeframe, "entry_guard": resolved.entry_guard,
                      "rule_params": resolved.rule_params}, indent=2))
    print(f"oos_variant: {json.dumps(resolved.variant)}")
    print(f"oos_config_hash: {config_hash(resolved.timeframe, resolved.entry_guard, resolved.rule_params)}")
    import yaml
    print(yaml.safe_dump(frozen, sort_keys=True), end="")


if __name__ == "__main__":
    main()
