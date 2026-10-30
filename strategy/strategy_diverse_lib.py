"""Causal rule implementations for pre-registered S-113..S-132."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import TypeAlias

import numpy as np

from strategy import strategy_lib
from strategy.strategy_lib import TIMEFRAME_PARQUET, make_bars, run_strategy

Condition: TypeAlias = tuple[str, str, float | str]


@dataclass(frozen=True)
class RuleSpec:
    sid: str
    slug: str
    name: str
    timeframe: str
    columns: tuple[str, ...]
    hypothesis: str
    expected_trades: str
    difference: str
    enter_long: tuple[Condition, ...]
    enter_short: tuple[Condition, ...]
    exit_long: tuple[Condition, ...]
    exit_short: tuple[Condition, ...]


def _c(left: str, op: str, right: float | str) -> Condition:
    return (left, op, right)


_specs = [
    RuleSpec("S-113", "aroon_adx_1h", "1h Aroon direction with ADX regime", "1h",
        ("aroon_up_24", "aroon_down_24", "adx_24"),
        "Aroon direction changes may persist longer when 1h ADX confirms a directional regime.",
        "20–180", "1h Aroon cross plus ADX confirmation; not a single-indicator Aroon flip.",
        (_c("aroon_up_24", "cross_above", "aroon_down_24"), _c("adx_24", "above", 20)),
        (_c("aroon_up_24", "cross_below", "aroon_down_24"), _c("adx_24", "above", 20)),
        (_c("aroon_up_24", "cross_below", "aroon_down_24"),),
        (_c("aroon_up_24", "cross_above", "aroon_down_24"),)),
    RuleSpec("S-114", "htf_ema_pullback", "Higher-timeframe trend pullback", "5m",
        ("ema_dist_24", "h1_ema_dist_24"),
        "A 5m pullback recovery aligned with closed 1h direction may avoid counter-trend entries.",
        "20–220", "Pullback recovery in ATR-normalized EMA distance with a closed 1h context gate.",
        (_c("ema_dist_24", "cross_up", -0.5), _c("h1_ema_dist_24", "above", 0)),
        (_c("ema_dist_24", "cross_down", 0.5), _c("h1_ema_dist_24", "below", 0)),
        (_c("ema_dist_24", "cross_down", 0),), (_c("ema_dist_24", "cross_up", 0),)),
    RuleSpec("S-115", "htf_channel_break", "Higher-timeframe-gated channel break", "5m",
        ("dist_high_24", "dist_low_24", "h1_adx_24", "dc_pos_24"),
        "A break of the prior 24-bar extreme may persist when closed 1h ADX confirms trend strength.",
        "10–160", "Prior-extreme break plus 1h regime confirmation; distinct from raw channel followers.",
        (_c("dist_high_24", "cross_up", 0), _c("h1_adx_24", "above", 20)),
        (_c("dist_low_24", "cross_down", 0), _c("h1_adx_24", "above", 20)),
        (_c("dc_pos_24", "cross_down", 0.5),), (_c("dc_pos_24", "cross_up", 0.5),)),
    RuleSpec("S-116", "squeeze_clv_htf", "Squeeze release with close-location direction", "5m",
        ("sqz_on_24", "bar_clv", "h1_ema_dist_24"),
        "Compression release with close-location aligned with 1h direction may filter weak breakouts.",
        "10–160", "Squeeze release requires close-location and 1h trend alignment.",
        (_c("sqz_on_24", "cross_down", 0.5), _c("bar_clv", "above", 0.6), _c("h1_ema_dist_24", "above", 0)),
        (_c("sqz_on_24", "cross_down", 0.5), _c("bar_clv", "below", -0.6), _c("h1_ema_dist_24", "below", 0)),
        (_c("sqz_on_24", "above", 0.5),), (_c("sqz_on_24", "above", 0.5),)),
    RuleSpec("S-117", "vwap_range_reclaim", "Low-trend VWAP reclaim", "5m",
        ("close", "vwap", "h1_adx_24"),
        "In weak 1h trend regimes, a VWAP reclaim may capture intraday mean reversion.",
        "30–240", "VWAP crossing only under low 1h ADX; not a VWAP-stretch threshold retune.",
        (_c("close", "cross_above", "vwap"), _c("h1_adx_24", "below", 20)),
        (_c("close", "cross_below", "vwap"), _c("h1_adx_24", "below", 20)),
        (_c("close", "cross_below", "vwap"),), (_c("close", "cross_above", "vwap"),)),
    RuleSpec("S-118", "bb_chop_reversion", "Band re-entry in a choppy regime", "5m",
        ("bb_pctb_24", "chop_24", "h1_adx_24"),
        "Band re-entry may mean-revert when both local and 1h regimes are non-trending.",
        "20–180", "Bollinger %B re-entry requires local choppiness and weak 1h ADX.",
        (_c("bb_pctb_24", "cross_up", 0.05), _c("chop_24", "above", 55), _c("h1_adx_24", "below", 20)),
        (_c("bb_pctb_24", "cross_down", 0.95), _c("chop_24", "above", 55), _c("h1_adx_24", "below", 20)),
        (_c("bb_pctb_24", "cross_up", 0.5),), (_c("bb_pctb_24", "cross_down", 0.5),)),
    RuleSpec("S-119", "channel_position_continuation", "Channel-position continuation", "5m",
        ("dist_high_60", "dist_low_60", "h1_ema_dist_24"),
        "A break of the prior 60-bar extreme may continue when the closed 1h context agrees.",
        "10–140", "60-bar prior-extreme breakout with explicit 1h direction and bilateral entries.",
        (_c("dist_high_60", "cross_up", 0), _c("h1_ema_dist_24", "above", 0)),
        (_c("dist_low_60", "cross_down", 0), _c("h1_ema_dist_24", "below", 0)),
        (_c("dist_high_60", "cross_down", 0),), (_c("dist_low_60", "cross_up", 0),)),
    RuleSpec("S-120", "dmi_regime_cross", "Directional-movement cross with ADX filter", "5m",
        ("plus_di_60", "minus_di_60", "adx_60"),
        "A slow directional-movement cross may reduce false starts when 60-bar ADX is established.",
        "10–160", "DI cross paired with a slow ADX regime gate.",
        (_c("plus_di_60", "cross_above", "minus_di_60"), _c("adx_60", "above", 20)),
        (_c("plus_di_60", "cross_below", "minus_di_60"), _c("adx_60", "above", 20)),
        (_c("plus_di_60", "cross_below", "minus_di_60"),),
        (_c("plus_di_60", "cross_above", "minus_di_60"),)),
    RuleSpec("S-121", "macd_er_1h", "1h MACD momentum in efficient regimes", "1h",
        ("macd_hist_atr_12_60", "er_24"),
        "A normalized 1h MACD zero-cross may persist when the path is directionally efficient.",
        "10–140", "1h normalized MACD cross confirmed by efficiency ratio.",
        (_c("macd_hist_atr_12_60", "cross_up", 0), _c("er_24", "above", 0.25)),
        (_c("macd_hist_atr_12_60", "cross_down", 0), _c("er_24", "above", 0.25)),
        (_c("macd_hist_atr_12_60", "cross_down", 0),),
        (_c("macd_hist_atr_12_60", "cross_up", 0),)),
    RuleSpec("S-122", "psar_htf_alignment", "PSAR reversal aligned with 1h trend", "5m",
        ("psar_dir_0p01_0p1", "h1_st_dir_24_3"),
        "A slow PSAR reversal may be more selective when the closed 1h SuperTrend agrees.",
        "15–160", "Slow-PSAR direction flip gated by independent 1h SuperTrend context.",
        (_c("psar_dir_0p01_0p1", "cross_up", 0), _c("h1_st_dir_24_3", "above", 0)),
        (_c("psar_dir_0p01_0p1", "cross_down", 0), _c("h1_st_dir_24_3", "below", 0)),
        (_c("psar_dir_0p01_0p1", "cross_down", 0),),
        (_c("psar_dir_0p01_0p1", "cross_up", 0),)),
    RuleSpec("S-123", "wick_band_reversal", "Wick rejection at Bollinger extremes", "5m",
        ("bar_lower_wick_ratio", "bar_upper_wick_ratio", "bar_clv", "bb_pctb_60"),
        "Extreme band location plus rejection wick and close location may identify failed extensions.",
        "10–120", "Candlestick rejection pattern plus 60-bar band location.",
        (_c("bar_lower_wick_ratio", "above", 0.6), _c("bar_clv", "above", 0.5), _c("bb_pctb_60", "below", 0.1)),
        (_c("bar_upper_wick_ratio", "above", 0.6), _c("bar_clv", "below", -0.5), _c("bb_pctb_60", "above", 0.9)),
        (_c("bb_pctb_60", "cross_up", 0.5),), (_c("bb_pctb_60", "cross_down", 0.5),)),
    RuleSpec("S-124", "squeeze_volume_break", "Squeeze release with activity-confirmed break", "5m",
        ("sqz_on_60", "dist_high_60", "dist_low_60", "vol_rel_60", "dc_pos_60"),
        "A 60-bar squeeze release with activity and an extreme break may avoid low-energy false breaks.",
        "5–100", "Compression release, tick-activity proxy, and prior-channel break.",
        (_c("sqz_on_60", "cross_down", 0.5), _c("dist_high_60", "cross_up", 0), _c("vol_rel_60", "above", 1.2)),
        (_c("sqz_on_60", "cross_down", 0.5), _c("dist_low_60", "cross_down", 0), _c("vol_rel_60", "above", 1.2)),
        (_c("dc_pos_60", "cross_down", 0.5),), (_c("dc_pos_60", "cross_up", 0.5),)),
    RuleSpec("S-125", "ema_dist_htf", "ATR-normalized EMA trend with 1h SuperTrend", "5m",
        ("ema_dist_60", "h1_st_dir_120_3"),
        "A sustained normalized EMA-distance transition may carry when the slower 1h SuperTrend agrees.",
        "10–130", "Slow EMA-distance transition plus higher-timeframe SuperTrend.",
        (_c("ema_dist_60", "cross_up", 0), _c("h1_st_dir_120_3", "above", 0)),
        (_c("ema_dist_60", "cross_down", 0), _c("h1_st_dir_120_3", "below", 0)),
        (_c("ema_dist_60", "cross_down", 0),), (_c("ema_dist_60", "cross_up", 0),)),
    RuleSpec("S-126", "atr_expansion_break", "ATR expansion plus prior-extreme breakout", "5m",
        ("atr_pct_24", "atr_pct_60", "dist_high_24", "dist_low_24", "dc_pos_24"),
        "Local volatility expansion relative to its slower baseline may confirm a channel break.",
        "5–120", "Relative volatility expansion and prior-extreme break, distinct from fixed ATR bands.",
        (_c("atr_pct_24", "cross_above", "atr_pct_60"), _c("dist_high_24", "cross_up", 0)),
        (_c("atr_pct_24", "cross_above", "atr_pct_60"), _c("dist_low_24", "cross_down", 0)),
        (_c("dc_pos_24", "cross_down", 0.5),), (_c("dc_pos_24", "cross_up", 0.5),)),
    RuleSpec("S-127", "cmf_htf_flow", "Money-flow zero-cross with 1h trend alignment", "5m",
        ("cmf_12", "h1_ema_dist_24"),
        "A shorter money-flow regime change may be useful only when closed 1h price trend agrees.",
        "10–150", "CMF crossing with independent higher-timeframe trend gate.",
        (_c("cmf_12", "cross_up", 0), _c("h1_ema_dist_24", "above", 0)),
        (_c("cmf_12", "cross_down", 0), _c("h1_ema_dist_24", "below", 0)),
        (_c("cmf_12", "cross_down", 0),), (_c("cmf_12", "cross_up", 0),)),
    RuleSpec("S-128", "vwap_trend_reclaim", "VWAP reclaim in strong 1h trend", "5m",
        ("close", "vwap", "h1_adx_24", "h1_ema_dist_24"),
        "A session VWAP reclaim may be trend resumption when the closed 1h regime is strong and aligned.",
        "10–120", "Session VWAP crossing with strong-ADX and 1h direction.",
        (_c("close", "cross_above", "vwap"), _c("h1_adx_24", "above", 25), _c("h1_ema_dist_24", "above", 0)),
        (_c("close", "cross_below", "vwap"), _c("h1_adx_24", "above", 25), _c("h1_ema_dist_24", "below", 0)),
        (_c("close", "cross_below", "vwap"),), (_c("close", "cross_above", "vwap"),)),
    RuleSpec("S-129", "htf_channel_break_120", "1h SuperTrend with 5m 120-bar breakout", "5m",
        ("h1_st_dir_24_3", "dist_high_120", "dist_low_120", "dc_pos_120"),
        "A long-window 5m extreme break may persist when the closed 1h SuperTrend agrees.",
        "10–120", "120-bar prior-extreme breakout gated by 1h SuperTrend; distinct from the 24-bar ADX-gated break.",
        (_c("dist_high_120", "cross_up", 0), _c("h1_st_dir_24_3", "above", 0)),
        (_c("dist_low_120", "cross_down", 0), _c("h1_st_dir_24_3", "below", 0)),
        (_c("dc_pos_120", "cross_down", 0.5),),
        (_c("dc_pos_120", "cross_up", 0.5),)),
    RuleSpec("S-130", "channel_efficiency_1h", "1h channel-position break in efficient trend", "1h",
        ("dc_pos_60", "er_60"),
        "A sustained 1h channel-position break may be more reliable when path efficiency is high.",
        "5–100", "60-bar channel position and efficiency ratio on 1h bars.",
        (_c("dc_pos_60", "cross_up", 0.8), _c("er_60", "above", 0.3)),
        (_c("dc_pos_60", "cross_down", 0.2), _c("er_60", "above", 0.3)),
        (_c("dc_pos_60", "cross_down", 0.5),), (_c("dc_pos_60", "cross_up", 0.5),)),
    RuleSpec("S-131", "clv_activity_impulse", "Close-location impulse with tick-activity confirmation", "5m",
        ("bar_clv", "vol_rel_6", "h1_adx_24"),
        "Directional close-location with elevated tick activity may indicate an impulse in an established regime.",
        "10–160", "Candle close-location and tick-activity proxy with independent 1h regime gate.",
        (_c("bar_clv", "cross_up", 0.7), _c("vol_rel_6", "above", 1.2), _c("h1_adx_24", "above", 20)),
        (_c("bar_clv", "cross_down", -0.7), _c("vol_rel_6", "above", 1.2), _c("h1_adx_24", "above", 20)),
        (_c("bar_clv", "cross_down", 0),), (_c("bar_clv", "cross_up", 0),)),
    RuleSpec("S-132", "bandwidth_expansion_htf", "Band-width expansion aligned with 1h trend", "5m",
        ("bb_width_12", "bb_width_60", "h1_ema_dist_24", "dc_pos_24"),
        "Short-window volatility expansion may signal a phase change when price location and 1h trend agree.",
        "10–150", "Relative bandwidth expansion, channel location, and independent 1h direction.",
        (_c("bb_width_12", "cross_above", "bb_width_60"), _c("dc_pos_24", "above", 0.6), _c("h1_ema_dist_24", "above", 0)),
        (_c("bb_width_12", "cross_above", "bb_width_60"), _c("dc_pos_24", "below", 0.4), _c("h1_ema_dist_24", "below", 0)),
        (_c("dc_pos_24", "cross_down", 0.5),), (_c("dc_pos_24", "cross_up", 0.5),)),
]
RULES = {f"s{int(spec.sid[2:]):03d}": spec for spec in _specs}


def _matches(values: dict[str, np.ndarray], condition: Condition, j: int) -> bool:
    left, op, right = condition
    a = values[left][j]
    if not np.isfinite(a):
        return False
    if isinstance(right, str):
        b = values[right][j]
        if not np.isfinite(b):
            return False
    else:
        b = float(right)
    if op in {"cross_up", "cross_down", "cross_above", "cross_below"}:
        if j < 1:
            return False
        pa = values[left][j - 1]
        if not np.isfinite(pa):
            return False
        if isinstance(right, str):
            pb = values[right][j - 1]
            if not np.isfinite(pb):
                return False
        else:
            pb = float(right)
        if op == "cross_up":
            return a > b and pa <= b
        if op == "cross_down":
            return a < b and pa >= b
        if op == "cross_above":
            return a > b and pa <= pb
        return a < b and pa >= pb
    if op == "above":
        return a > b
    if op == "below":
        return a < b
    raise ValueError(f"Unknown strategy condition {op!r}")


class DiverseRuleState:
    """Two-sided state machine whose inputs are only closed bars."""

    def __init__(self, spec: RuleSpec, values: dict[str, np.ndarray]) -> None:
        self.spec = spec
        self.values = values
        self.position = 0

    def _all(self, conditions: tuple[Condition, ...], j: int) -> bool:
        return all(_matches(self.values, condition, j) for condition in conditions)

    def desired_position(self, i: int) -> int:
        if i <= 0:
            return 0
        j = i - 1
        if any(not np.isfinite(self.values[col][j]) for col in self.spec.columns):
            return self.position
        if self.position == 0:
            if self._all(self.spec.enter_long, j):
                self.position = 1
            elif self._all(self.spec.enter_short, j):
                self.position = -1
        elif self.position > 0 and self._all(self.spec.exit_long, j):
            self.position = -1 if self._all(self.spec.enter_short, j) else 0
        elif self.position < 0 and self._all(self.spec.exit_short, j):
            self.position = 1 if self._all(self.spec.enter_long, j) else 0
        return self.position


def run_rule(parquet: str | None, instrument: str, timeframe: str | None = None,
             since: str | None = None, until: str | None = None,
             cost_bps: float = 2.0, entry_guard: bool = False,
             oos_token: object | None = None, strategy_id: str = "s113") -> dict:
    key = strategy_id.lower().replace("-", "")
    try:
        spec = RULES[key]
    except KeyError as exc:
        raise SystemExit(f"Unknown diverse strategy {strategy_id!r}") from exc
    tf = timeframe or spec.timeframe
    if tf != spec.timeframe:
        raise SystemExit(f"{spec.sid} is registered for {spec.timeframe}, not {tf}")
    path = parquet or TIMEFRAME_PARQUET[tf]
    df = strategy_lib.load_bars(
        path, instrument, feature_cols=spec.columns, not_null_cols=spec.columns,
        since=since, until=until, oos_token=oos_token)
    if len(df) < 1_000:
        raise SystemExit(f"Only {len(df)} bars loaded for {instrument}; need at least 1,000.")
    bars = make_bars(df, tf, entry_guard=entry_guard)
    values = {col: df[col].to_numpy(dtype=np.float64) for col in spec.columns}
    rule = DiverseRuleState(spec, values)
    meta = {
        "strategy_id": spec.sid, "name": spec.name, "instrument": instrument,
        "timeframe": tf, "window_since": since, "window_until": until,
        "start": str(df["time"].iloc[0]), "end": str(df["time"].iloc[-1]),
        "cost_bps": cost_bps,
        "entry_guard": "off" if not entry_guard else "gap_bar|near_market_close",
    }
    return run_strategy(rule, bars, cost_bps, long_only=False, meta=meta)


def cli_main(strategy_id: str) -> None:
    spec = RULES[strategy_id.lower().replace("-", "")]
    parser = argparse.ArgumentParser(description=f"{spec.sid} {spec.name}")
    parser.add_argument("--instrument", default="EUR_USD")
    parser.add_argument("--timeframe", default=spec.timeframe, choices=("5m", "1h"))
    parser.add_argument("--since")
    parser.add_argument("--until")
    parser.add_argument("--parquet")
    parser.add_argument("--cost-bps", type=float, default=2.0)
    parser.add_argument("--json")
    parser.add_argument("--entry-guard", action="store_true")
    args = parser.parse_args()
    result = run_rule(
        args.parquet, args.instrument, args.timeframe, args.since, args.until,
        args.cost_bps, args.entry_guard, strategy_id=strategy_id)
    payload = {key: value for key, value in result.items() if key != "trades"}
    if args.json:
        Path(args.json).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))


__all__ = ["RULES", "RuleSpec", "DiverseRuleState", "run_rule", "cli_main"]
