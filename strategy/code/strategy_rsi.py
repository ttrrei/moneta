"""Minimal RSI mean-reversion backtest (reference strategy, not an alpha claim).

Rules (all on 5m bars, one instrument at a time):
  * Enter long  at bar T+1 open  when RSI_24(T) <  30 and flat.
  * Exit long   at bar T+1 open  when RSI_24(T) >  55.
  * One position at a time, long only, position size = 1 unit.
  * One-way cost of 2 bps applied at entry and exit (typical OANDA CFD spread).

Execution model follows the indicator spec: a signal computed on a closed bar
T is traded at the next bar's open (no same-bar fill, no lookahead).

Run from the repo root::

    python strategy/code/strategy_rsi.py                     # EUR_USD, all history
    python strategy/code/strategy_rsi.py --instrument BTC_USD --since 2023-01-01
    python strategy/code/strategy_rsi.py --cost-bps 0        # cost sensitivity (0/2/5)
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, asdict
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

FEATURES_PARQUET = "data/ohlcv_5m_features/ohlcv_5m_features.parquet"
RSI_COL = "rsi_24"
COST_BPS = 2.0  # one-way transaction cost, basis points


@dataclass
class BacktestResult:
    instrument: str
    start: str
    end: str
    n_bars: int
    n_trades: int
    win_rate_pct: float
    total_return_pct: float
    buyhold_return_pct: float
    max_drawdown_pct: float
    avg_trade_return_pct: float
    sharpe: float
    exposure_pct: float


def load_bars(
    parquet: str, instrument: str, since: str | None = None
) -> pd.DataFrame:
    conn = duckdb.connect()
    try:
        where = [
            "instrument = ?",
            RSI_COL + " IS NOT NULL",
        ]
        params: list = [parquet, instrument]
        if since:
            where.append("time >= ?")
            params.append(since)
        sql = (
            "SELECT time, open, close, " + RSI_COL +
            " FROM read_parquet(?) WHERE " + " AND ".join(where) +
            " ORDER BY time"
        )
        return conn.execute(sql, params).fetch_df()
    finally:
        conn.close()


def run_backtest(df: pd.DataFrame, instrument: str, cost_bps: float = COST_BPS) -> BacktestResult:
    """Event-loop over bars; signal on bar T, fill at open of bar T+1."""
    o = df["open"].to_numpy(np.float64)
    c = df["close"].to_numpy(np.float64)
    rsi = df[RSI_COL].to_numpy(np.float64)
    n = len(df)

    cost = cost_bps / 10_000.0
    pos = 0.0
    entry_px = np.nan
    entry_cost_px = np.nan
    equity = np.empty(n)
    in_trade = np.zeros(n, dtype=bool)
    trades: list[float] = []
    n_trades = 0
    bars_in_market = 0

    for t in range(n):
        px_open = o[t]
        # 1) Execute the pending signal from bar t-1 at this bar's open.
        if t > 0 and np.isfinite(rsi[t - 1]):
            if pos == 0.0 and rsi[t - 1] < 30.0:
                pos = 1.0
                entry_px = px_open
                entry_cost_px = px_open * cost
            elif pos == 1.0 and rsi[t - 1] > 55.0:
                px_net = px_open - px_open * cost
                trades.append(px_net / (entry_px + entry_cost_px) - 1.0)
                pos = 0.0
                n_trades += 1
        # 2) Mark-to-market at this bar's close.
        if pos == 1.0:
            bars_in_market += 1
            equity[t] = (c[t] - entry_px - entry_cost_px) / (entry_px + entry_cost_px)
        else:
            equity[t] = np.nan
        in_trade[t] = pos == 1.0

    # Force-close an open position at the last close (counted as a trade).
    if pos == 1.0:
        px_net = c[-1] - c[-1] * cost
        trades.append(px_net / (entry_px + entry_cost_px) - 1.0)
        n_trades += 1
        equity[-1] = px_net / (entry_px + entry_cost_px) - 1.0

    # Account equity curve: compounded P&L of closed trades, times the
    # open-trade value (if any) at each bar.
    account = np.ones(n)
    base = 1.0
    trade_idx = 0
    closed_pnl = 1.0 + np.array(trades)
    for t in range(n):
        if in_trade[t]:
            account[t] = base * (1.0 + equity[t])
        else:
            if t > 0 and in_trade[t - 1] and trade_idx < len(trades):
                base *= closed_pnl[trade_idx]
                trade_idx += 1
            account[t] = base

    total_return = account[-1] - 1.0
    buyhold = c[-1] / o[0] - 1.0

    peak = np.maximum.accumulate(account)
    max_dd = float(np.max((peak - account) / peak))

    if trades:
        tr = np.array(trades)
        win_rate = float((tr > 0).mean() * 100)
        avg_trade = float(tr.mean() * 100)
        if tr.std(ddof=1) > 0:
            sharpe = float(tr.mean() / tr.std(ddof=1) * np.sqrt(len(tr) * 12))
        else:
            sharpe = 0.0
    else:
        win_rate = avg_trade = sharpe = 0.0

    return BacktestResult(
        instrument=instrument,
        start=str(df["time"].iloc[0]),
        end=str(df["time"].iloc[-1]),
        n_bars=int(n),
        n_trades=int(n_trades),
        win_rate_pct=round(win_rate, 2),
        total_return_pct=round(total_return * 100, 2),
        buyhold_return_pct=round(buyhold * 100, 2),
        max_drawdown_pct=round(max_dd * 100, 2),
        avg_trade_return_pct=round(avg_trade, 4),
        sharpe=round(sharpe, 2),
        exposure_pct=round(bars_in_market / n * 100, 2),
    )


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--instrument", default="EUR_USD")
    ap.add_argument("--since", default=None, help="ISO date, e.g. 2023-01-01")
    ap.add_argument("--parquet", default=FEATURES_PARQUET)
    ap.add_argument("--cost-bps", type=float, default=COST_BPS,
                    help="one-way transaction cost in basis points (default 2)")
    ap.add_argument("--json", default=None, help="also write results JSON to path")
    args = ap.parse_args()

    df = load_bars(args.parquet, args.instrument, args.since)
    if len(df) < 1_000:
        raise SystemExit(f"Only {len(df)} bars loaded; not enough to backtest.")
    result = run_backtest(df, args.instrument, cost_bps=args.cost_bps)
    print(json.dumps(asdict(result), indent=2))
    if args.json:
        Path(args.json).write_text(json.dumps(asdict(result), indent=2))


if __name__ == "__main__":
    main()
