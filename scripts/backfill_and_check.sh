#!/usr/bin/env bash
# Backfill earlier history from config/history_map.yml, ingest it, then check the result.
#
#   scripts/backfill_and_check.sh                            # everything in the map
#   scripts/backfill_and_check.sh --only GBP_USD             # extra args go to extract_oanda
#   scripts/backfill_and_check.sh --dry-run                  # plan only (stops before ingesting)
#   scripts/backfill_and_check.sh --yes                      # skip the "press enter" prompt
#   scripts/backfill_and_check.sh --step load,sanity         # only a subset of the steps
#   scripts/backfill_and_check.sh --timeout 0                # no per-step timeout
#
# Steps: extract, load, aggregate, sanity, profile.
# Each step:
#   * is wrapped in coreutils `timeout` (default 3600s; `--timeout 0` disables),
#   * is guarded by a per-step flock (a second run of the same step cannot
#     trample the first while it is still running),
#   * tees to logs/backfill.log AND to logs/backfill/<step>.log,
#   * on failure the script exits non-zero (no "Done" banner) and lists the
#     step(s) that failed and their exit code, so a half-failed backfill is
#     never ingested silently.
#
# Run it inside tmux/screen: a full multi-year backfill takes hours.

# This script needs bash (associative arrays, read -ra, [[ ]]).
# Refuse to run under a POSIX shell with a clear error instead of half-failing.
if [ -z "${BASH_VERSION:-}" ]; then
  echo "This script requires bash; re-run as: bash scripts/backfill_and_check.sh $*" >&2
  exit 2
fi

set -Eeuo pipefail
cd "$(dirname "$0")/.."

# --- config / defaults ---------------------------------------------------------------
DRY_RUN=0
ASSUME_YES=0
TIMEOUT_SECS="${BACKFILL_STEP_TIMEOUT:-3600}"
STEP_OVERRIDE=""
PYTHON_BIN="${PYTHON:-}"
EXTRA_ARGS=()

usage() {
  sed -n '2,20p' "$0" | sed 's/^# \{0,1\}//'
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY_RUN=1; shift ;;
    --yes|-y) ASSUME_YES=1; shift ;;
    --timeout) shift; [[ $# -gt 0 ]] || { echo "--timeout needs a value (seconds, 0 disables)" >&2; exit 2; }; TIMEOUT_SECS="$1"; shift ;;
    --step) shift; [[ $# -gt 0 ]] || { echo "--step needs a value (e.g. extract,load)" >&2; exit 2; }; STEP_OVERRIDE="$1"; shift ;;
    --python) shift; [[ $# -gt 0 ]] || { echo "--python needs a value (e.g. python3)" >&2; exit 2; }; PYTHON_BIN="$1"; shift ;;
    --help|-h) usage; exit 0 ;;
    *) EXTRA_ARGS+=("$1"); shift ;;
  esac
done

# --- sanity checks --------------------------------------------------------------------
if ! [[ "$TIMEOUT_SECS" =~ ^([0-9]+)$ ]]; then
  echo "timeout must be a non-negative integer number of seconds (or 0 to disable)" >&2
  exit 2
fi

if [[ -z "$PYTHON_BIN" ]]; then
  if command -v python3 >/dev/null 2>&1; then PYTHON_BIN=python3
  elif command -v python >/dev/null 2>&1; then PYTHON_BIN=python
  else
    echo "no python interpreter found (looked for python3, python); pass --python <path>" >&2
    exit 2
  fi
fi

if ! command -v timeout >/dev/null 2>&1 && [[ "$TIMEOUT_SECS" != "0" ]]; then
  echo "coreutils 'timeout' not found; either install coreutils or pass --timeout 0" >&2
  exit 2
fi

LOG_ROOT="$(pwd)/logs/backfill"
mkdir -p "$LOG_ROOT" docs

# --- step registry --------------------------------------------------------------------
STEP_LIST=()
case "${STEP_OVERRIDE:-}" in
  "")
    if [[ $DRY_RUN == 1 ]]; then STEP_LIST=(extract)
    else STEP_LIST=(extract load aggregate sanity profile); fi
    ;;
  *)
    if [[ -z "$STEP_OVERRIDE" ]]; then echo "--step needs a value (e.g. extract,load)" >&2; exit 2; fi
    IFS=',' read -ra _requested <<<"$STEP_OVERRIDE"
    for s in "${_requested[@]}"; do
      case "$s" in
        extract|load|aggregate|sanity|profile) STEP_LIST+=("$s") ;;
        *) echo "unknown step '$s' (expected extract|load|aggregate|sanity|profile)" >&2; exit 2 ;;
      esac
    done
    ;;
esac

# --- helpers --------------------------------------------------------------------------
FAILED_STEPS=()

run_step() {
  local name="$1"; shift
  local cmd=("$@")
  local step_log="$LOG_ROOT/${name}.log"
  local lock_dir
  lock_dir="$(pwd)/.cache/backfill"
  mkdir -p "$lock_dir"
  local lockfile="$lock_dir/${name}.lock"

  if [[ "$name" == "extract" && $DRY_RUN == 1 ]]; then
    echo "[backfill] DRY RUN: only the extract plan will be printed; nothing is downloaded or ingested."
  fi

  echo
  echo "=== step: $name ==="
  echo "    cmd:     ${cmd[*]}"
  echo "    log:     $step_log"
  echo "    timeout: $([[ "$TIMEOUT_SECS" == "0" ]] && echo 'disabled' || echo "${TIMEOUT_SECS}s")"

  # The step command is run inside an exclusive flock, so a concurrent second
  # run of the same step cannot trample this one. `timeout 0` is a no-op, so
  # the same wrapper handles both the timed and the untimed paths.  The
  # leading `if !` keeps set -e from aborting before we can record the failure.
  local rc=0
  BACKFILL_STEP_LOG="$step_log" timeout "$TIMEOUT_SECS" flock -x "$lockfile" bash -c '
      set -o pipefail   # so the pipeline reports the step''s code, not tee''s
      "$@" 2>&1 | tee -a "$BACKFILL_STEP_LOG" logs/backfill.log
    ' _ "${cmd[@]}" || rc=$?

  if [[ $rc -eq 0 ]]; then
    echo "=== step: $name: OK ==="
    return 0
  fi
  if [[ $rc -eq 124 ]]; then
    echo "=== step: $name: TIMEOUT after ${TIMEOUT_SECS}s (see $step_log) ===" >&2
  else
    echo "=== step: $name: FAILED with exit code $rc (see $step_log) ===" >&2
  fi
  FAILED_STEPS+=("$name(rc=$rc)")
  return 1
}

on_exit() {
  local rc=$?
  if [[ ${#FAILED_STEPS[@]} -gt 0 && $rc -ne 0 ]]; then
    echo
    echo "Backfill aborted. Failed step(s): ${FAILED_STEPS[*]}"
    echo "Inspect the logs: $LOG_ROOT/<step>.log and logs/backfill.log"
    echo "Fix the root cause and re-run with --step <name>,... to resume where it stopped."
  fi
}
trap on_exit EXIT

# --- steps ----------------------------------------------------------------------------
declare -A STEP_CMD=(
  [extract]="$PYTHON_BIN -m pipeline.extract_oanda --map config/history_map.yml ${EXTRA_ARGS[*]}"
  [load]="$PYTHON_BIN -m pipeline.load_data"
  [aggregate]="$PYTHON_BIN -m pipeline.aggregate_ohlcv"
  [sanity]="$PYTHON_BIN pipeline/sanity_check.py"
  [profile]="$PYTHON_BIN pipeline/profile_check.py --raw --out docs/profile_output.txt"
)

# --- confirm & go ---------------------------------------------------------------------
if [[ $ASSUME_YES != 1 ]]; then
  echo "This will run: ${STEP_LIST[*]}"
  read -r -p "Continue? [y/N] " answer
  case "$answer" in
    y|Y|yes|YES) ;;
    *) echo "Aborted."; exit 0 ;;
  esac
fi

set +e
for name in "${STEP_LIST[@]}"; do
  run_step "$name" ${STEP_CMD[$name]} || exit 1
done
set -e

echo
echo "Done. Read docs/profile_output.txt: the 'gaps' VERDICT, and the 'raw' MATCH / conflict lines."
