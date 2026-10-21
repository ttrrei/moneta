#!/usr/bin/env bash
# Backfill earlier history from config/history_map.yml, ingest it, then check the result.
#
#   scripts/backfill_and_check.sh                  # everything in the map
#   scripts/backfill_and_check.sh --only GBP_USD   # extra arguments go to extract_oanda
#   scripts/backfill_and_check.sh --dry-run        # plan only (stops before ingesting)
#
# Stops at the first failing step, so a half-failed backfill is never ingested
# silently: fix the cause and re-run (finished months are skipped).
# Run it inside tmux/screen: a full multi-year backfill takes hours.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p logs docs

python -m pipeline.extract_oanda --map config/history_map.yml "$@" 2>&1 | tee -a logs/backfill.log

if [[ " $* " == *" --dry-run "* ]]; then
  echo "Dry run: nothing downloaded, nothing ingested."
  exit 0
fi

python -m pipeline.load_data
python -m pipeline.aggregate_ohlcv
python pipeline/sanity_check.py
python pipeline/profile_check.py --raw --out docs/profile_output.txt

echo
echo "Done. Read docs/profile_output.txt: the 'gaps' VERDICT, and the 'raw' MATCH / conflict lines."
