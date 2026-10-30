"""Fixed-ID adapter for S-132: Band-width expansion aligned with 1h trend."""

from strategy.strategy_diverse_lib import run_rule


def run(parquet: str, instrument: str, timeframe: str = "5m",
        since: str | None = None, until: str | None = None,
        cost_bps: float = 2.0, entry_guard: bool = False,
        oos_token: object | None = None) -> dict:
    return run_rule(
        parquet=parquet, instrument=instrument, timeframe=timeframe,
        since=since, until=until, cost_bps=cost_bps,
        entry_guard=entry_guard, oos_token=oos_token, strategy_id="s132")


__all__ = ["run"]
