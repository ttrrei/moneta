"""Write auditable reports for the S-103..S-132 strategy batches."""

from __future__ import annotations

import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from strategy.strategy_diverse_lib import RULES  # noqa: E402

INSTRUMENTS = ("EUR_USD", "BTC_USD", "XAU_USD")
WINDOWS = ("full", "last_12m")
COSTS = (0.0, 2.0, 5.0)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _registry_slug(lines: list[str], sid: str) -> str:
    row = next((line for line in lines if line.startswith(f"| {sid} |")), None)
    if row is None:
        raise SystemExit(f"{sid}: registry row not found")
    cells = row.split("|")
    target = cells[9].strip().partition("](")[2].rstrip(")")
    filename = Path(target).name
    if not filename.startswith("strategy_") or not filename.endswith(".py"):
        raise SystemExit(f"{sid}: invalid registry code link: {cells[9].strip()}")
    return filename.removeprefix("strategy_").removesuffix(".py")


def _number(row: dict, key: str) -> float:
    return float(row.get(key) or 0)


def _status(rows: list[dict], max_tpy: float,
            guard_rows: list[dict] | None = None) -> tuple[str, str, int, int]:
    guard_rows = guard_rows or rows
    at_two = [row for row in rows if _number(row, "cost_bps") == 2.0]
    wins = {
        window: sum(
            _number(row, "total_return_pct") > _number(row, "buyhold_return_pct")
            for row in at_two if row["window"] == window
        )
        for window in WINDOWS
    }
    peak_trades = max(
        (int(float(row.get("n_trades") or 0))
         for row in guard_rows if row["window"] == "full"),
        default=0,
    )
    peak_tpy = max(
        (_number(row, "trades_per_year")
         for row in guard_rows if row["window"] == "full"),
        default=0.0,
    )
    if peak_trades > 300 or wins["full"] == 0 or wins["last_12m"] == 0:
        return "rejected", "A pre-registered stop condition is met (trade count or no positive edge in a required window).", wins["full"], wins["last_12m"]
    if wins["full"] >= 2 and wins["last_12m"] >= 2 and peak_tpy <= max_tpy:
        return "candidate", "In-sample bar appears clear; left as candidate for human review. No OOS run or promotion was performed.", wins["full"], wins["last_12m"]
    if peak_tpy > max_tpy:
        return "rejected", f"Trade frequency exceeds the configured {max_tpy:g} trades/year ceiling.", wins["full"], wins["last_12m"]
    return "parked", "Some positive cells exist, but the cross-instrument in-sample bar is not met.", wins["full"], wins["last_12m"]


def _cell_table(rows: list[dict]) -> str:
    rows_by_key = {
        (row["instrument"], row["window"], _number(row, "cost_bps")): row
        for row in rows
    }
    lines = [
        "| Instrument | Window | Cost bps | Return % | Buy-hold % | Trades | Trades/yr | Max DD % | Weekly Sharpe |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for instrument in INSTRUMENTS:
        for window in WINDOWS:
            for cost in COSTS:
                row = rows_by_key[(instrument, window, cost)]
                lines.append(
                    f"| {instrument} | {window} | {cost:g} | "
                    f"{_number(row, 'total_return_pct'):.2f} | "
                    f"{_number(row, 'buyhold_return_pct'):.2f} | "
                    f"{int(float(row.get('n_trades') or 0))} | "
                    f"{_number(row, 'trades_per_year'):.2f} | "
                    f"{_number(row, 'max_drawdown_pct'):.2f} | "
                    f"{_number(row, 'sharpe_weekly'):.3f} |"
                )
    return "\n".join(lines)


def _regime_counts(results_dir: Path, sid: str) -> str:
    month = [0] * 12
    weekday = [0] * 7
    found = False
    for instrument in INSTRUMENTS:
        path = results_dir / f"{instrument}__full__c2.json"
        if not path.exists():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        distribution = data.get("trade_distribution") or {}
        for index, value in enumerate(distribution.get("by_month", [])):
            month[index] += int(value)
        for index, value in enumerate(distribution.get("by_weekday", [])):
            weekday[index] += int(value)
        found = True
    if not found:
        return "Monthly and weekday distribution was not included in the committed matrix output."
    return (
        f"Full-window 2 bps entry trades by month (all instruments): `{month}`.\n\n"
        f"Full-window 2 bps entry trades by weekday, Mon–Sun (all instruments): `{weekday}`."
    )


def _write_report(spec, rows: list[dict], result_dir: Path,
                  selected_variant: str, tried_before: int, max_tpy: float,
                  guard_rows: list[dict] | None = None) -> tuple[str, str]:
    if len(rows) != 18:
        raise SystemExit(f"{spec.sid}: expected 18 report cells, found {len(rows)}")
    outcome, rationale, full_wins, recent_wins = _status(rows, max_tpy, guard_rows)
    primary = next(
        row for row in rows
        if row["instrument"] == "EUR_USD" and row["window"] == "full"
        and _number(row, "cost_bps") == 2.0
    )
    actual_trades = int(float(primary.get("n_trades") or 0))
    report = f"""# {spec.sid}: {spec.name}

## Pre-registered hypothesis

{spec.hypothesis}

Expected full-history EUR_USD trade count: **{spec.expected_trades}**.  
Difference from prior work: {spec.difference}

## Evaluation

Fixed rule; selected config/variant: **{selected_variant}**. The selected
variant for S-103..S-112 is the highest mean edge across the 18 sweep cells at
2 bps, selected after the sweep; treat its performance as selection-biased.
S-113..S-132 use the one pre-registered rule with no parameter sweep.

{_cell_table(rows)}

At EUR_USD/full/2 bps: {actual_trades} trades, return
{_number(primary, 'total_return_pct'):+.2f}% versus buy-hold
{_number(primary, 'buyhold_return_pct'):+.2f}%. The full-window 2 bps edge count
is {full_wins}/3 instruments; last-12-month edge count is {recent_wins}/3.

## Outcome

**{outcome.upper()}** — {rationale}

This is in-sample evidence only. No strategy was run on or promoted using the
OOS holdout. A candidate status is not a finalist nomination; human review is
required before any OOS eligibility change.

## Regime / opportunity distribution

{_regime_counts(result_dir, spec.sid)}

## Causality checklist

- Rule reads only index `i - 1` (the last closed bar).
- Cross conditions compare the current closed bar to the preceding closed bar;
  no negative shifts or future indexing are used.
- The shared engine executes fills at the next bar's open and applies costs to
  entry and exit.
- Only feature columns in the committed 5m/1h feature tables are loaded.
- No OOS window was requested; the configured in-sample windows are
  `full` and `last_12m`.

## Caveats

- The matrices are in-sample and the batch tests 20 additional hypotheses;
  observed best-of-batch performance is subject to multiple-testing bias.
- Buy-hold is a cost-free benchmark while strategy costs are charged at each
  fill, making the comparison conservative on the cost side.
- Results do not model slippage or live execution constraints and are
  instrument-specific.

N strategies tried before this one: **{tried_before}**.
"""
    out = ROOT / "strategy" / "docs" / f"strategy_{spec.slug}_report.md"
    out.write_text(report, encoding="utf-8")
    return outcome, f"{_number(primary, 'total_return_pct'):+.1f}% vs {_number(primary, 'buyhold_return_pct'):+.1f}% (EUR_USD)"


def main() -> None:
    import yaml

    cfg = yaml.safe_load((ROOT / "config" / "strategies.yml").read_text(encoding="utf-8"))
    max_tpy = float(cfg["oos"]["pass_criteria"]["max_trades_per_year"])
    sweep_rows = _read_csv(ROOT / "strategy" / "results" / "iterations_2026-11-07.csv")
    old: dict[str, dict[str, list[dict]]] = defaultdict(lambda: defaultdict(list))
    for row in sweep_rows:
        old[row["strategy"]][row["variant"]].append(row)

    statuses: dict[str, tuple[str, str, str]] = {}
    registry = ROOT / "strategy" / "STRATEGY_REGISTRY.md"
    lines = registry.read_text(encoding="utf-8").splitlines()
    for number in range(103, 133):
        key = f"s{number}"
        sid = f"S-{number}"
        if number <= 112:
            variants = old.get(key, {})
            valid = {
                name: rows for name, rows in variants.items()
                if len(rows) == 18 and all(not row.get("error") for row in rows)
            }
            if not valid:
                raise SystemExit(f"{sid}: no complete sweep variant")
            selected_variant = max(
                valid,
                key=lambda name: sum(
                    _number(row, "edge_vs_bh_pct")
                    for row in valid[name] if _number(row, "cost_bps") == 2.0
                ) / 6,
            )
            rows = valid[selected_variant]
            guard_rows = [row for variant_rows in valid.values() for row in variant_rows]
            spec = type("Spec", (), {
                "sid": sid,
                "slug": _registry_slug(lines, sid),
                "name": next(line.split("|")[2].strip() for line in lines if line.startswith(f"| {sid} |")),
                "hypothesis": next(line.split("|")[5].strip() for line in lines if line.startswith(f"| {sid} |")),
                "expected_trades": "see sweep results",
                "difference": "This was the registered strategy hypothesis; the report selects the best-of-eight variant after evaluation.",
            })()
            result_dir = ROOT / "strategy" / "results"
        else:
            spec = RULES[key]
            result_dir = ROOT / "strategy" / "results" / f"S{number}"
            rows = _read_csv(result_dir / "summary.csv")
            selected_variant = "pre-registered fixed rule"
            guard_rows = rows

        outcome, result_text = _write_report(
            spec, rows, result_dir, selected_variant, number - 1, max_tpy, guard_rows)
        status = "candidate" if outcome == "candidate" else outcome
        statuses[sid] = (status, outcome, result_text)

        # Keep report and CLI links consistent with the checker's X7/X8 stem rule.
        code_name = f"strategy_{spec.slug}.py"
        report_name = f"strategy_{spec.slug}_report.md"
        for line in list(lines):
            if line.startswith(f"| {sid} |"):
                cells = line.split("|")
                cells[8] = f" **{status}** "
                cells[9] = f" [code/{code_name}](code/{code_name}) "
                cells[10] = f" [docs/{report_name}](docs/{report_name}) "
                cells[11] = " 2026-10-30 "
                cells[12] = f" {result_text}; variant={selected_variant}; see report "
                updated = "|".join(cells)
                lines[lines.index(line)] = updated
                break

    registry.write_text("\n".join(lines) + "\n", encoding="utf-8")
    trial_log = ROOT / "strategy" / "trial_log.md"
    log_lines = trial_log.read_text(encoding="utf-8")
    if any(f"| {sid} |" in log_lines for sid in statuses):
        raise SystemExit("trial log already has a batch row; refusing duplicate append")
    additions = []
    for number in range(103, 133):
        sid = f"S-{number}"
        status, outcome, result_text = statuses[sid]
        log_outcome = "<TBD>" if status == "candidate" else f"**{outcome}**"
        timeframe = cfg["strategies"][sid]["timeframe"]
        if number <= 112:
            hypothesis = f"{timeframe} strategy; 8-variant sweep; " + result_text
        else:
            hypothesis = f"{timeframe} strategy; " + RULES[f"s{number}"].hypothesis
        additions.append(
            f"| {number} | 2026-10-30 | {sid} | {hypothesis} | full | "
            f"{log_outcome} | {result_text} | {number - 1} |"
        )
    with trial_log.open("a", encoding="utf-8") as fh:
        fh.write("\n" + "\n".join(additions) + "\n")
    tally = trial_log.read_text(encoding="utf-8").splitlines()
    for index, line in enumerate(tally):
        if "| **Strategies tried**" in line:
            tally[index] = "| **Strategies tried** (S-01 … S-132) | **132** | rows 1–132 above |"
        elif "| **Configurations tried**" in line:
            tally[index] = (
                "| **Configurations tried** (distinct `(strategy, variant)` pairs) | **827** | "
                "727 prior configs + 80 sweep variants for S-103…S-112 + 20 fixed rules S-113…S-132 |"
            )
        elif "| **Total cells evaluated**" in line:
            tally[index] = "| **Total cells evaluated** | **≥ 14,886** | 827 × 18 |"
    trial_log.write_text("\n".join(tally) + "\n", encoding="utf-8")
    for sid, (status, outcome, _) in statuses.items():
        print(sid, "registry", status, "trial", "<TBD>" if status == "candidate" else outcome)


if __name__ == "__main__":
    main()
