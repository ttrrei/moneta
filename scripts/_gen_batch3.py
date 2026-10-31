"""One-shot generator for the S-28..S-40 strategy libs (batch 3).

Each strategy shares the SAME skeleton: a stateful SignalRule + a loader +
run_* + run() + the standard __all__. Only the signal arrays, the entry/exit
condition, and the tunable params differ. The optional ``ema_gate`` (only
enter while prev close > prev ema_24) is available on every strategy as an
improvement-iteration knob.

Run:  venv/bin/python scripts/_gen_batch3.py
"""

from __future__ import annotations

import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]


HEADER = '''"""{sid} {title} (signal only).

Data loading, the timeframe guard, and the shared accounting/metrics live in
:mod:`strategy.strategy_lib` / :mod:`strategy.engine`; this file only declares
the signal and the run wrapper (same contract as S-05/S-06/S-07).

{doc}

The optional ``ema_gate`` (available on every batch-3 strategy as an
improvement-iteration knob) blocks a *fresh* entry while the previous closed
bar's close is at/below ``ema_24``; it never blocks an exit.

All timestamps are UTC.
"""

from __future__ import annotations

import numpy as np

from strategy import strategy_lib
from strategy.strategy_lib import (  # noqa: F401  (re-exported public API)
    FEATURES_1H_PARQUET,
    FEATURES_PARQUET,
    TIMEFRAME_PARQUET,
    TIMEFRAME_SECONDS,
    detect_bar_seconds,
    load_bars,
    make_bars,
    run_strategy,
)

COST_BPS = 2.0  # one-way transaction cost, basis points (same convention as S-01)


'''

BODY = '''class {cls}:
    """{clsdoc}"""

    def __init__(self, {sig}) -> None:
{initbody}
        self.ema_gate = ema_gate
        self.gate_ema = gate_ema
        self.gate_close = gate_close
        self.state = 0

    def desired_position(self, i: int) -> int:
        if i == 0:
            return 0
        j = i - 1
{condcheck}
        if self.state == 0 and not strategy_lib.entry_gate_allows(
                self.ema_gate, self.gate_close, self.gate_ema, j):
            return self.state
        if self.state == 0:
{entry}
        elif {exitc}:
            self.state = 0
        return self.state


def build_rule(df, ema_gate: bool = False{bparams}) -> "{cls}":
    return {cls}({bargs}, ema_gate=ema_gate,
                 gate_ema=df["ema_24"].to_numpy(np.float64),
                 gate_close=df["close"].to_numpy(np.float64){bpkwargs})


def load_{loadname}_bars(parquet: str, instrument: str, since: str | None = None,
                     until: str | None = None, oos_token: object | None = None):
    """Load the {loadcols} column(s) (plus base pricing) for one window.

    ``oos_token`` is required for any window that reaches the OOS holdout
    (the data-layer gate in :func:`strategy_lib.load_bars`); in-sample windows
    load with no token.
    """
    return strategy_lib.load_bars(
        parquet, instrument, feature_cols={featurecols!r},
        not_null_cols={notnullcols!r},
        since=since, until=until, oos_token=oos_token)


def run_{runname}(
    parquet: str,
    instrument: str,
    timeframe: str = "5m",
    since: str | None = None,
    until: str | None = None,
    cost_bps: float = COST_BPS,
    entry_guard: bool = False,
    ema_gate: bool = False,
{runparams}
    oos_token: object | None = None,
) -> dict:
    """Run the {sid} rule for one instrument / window / cost tier.

    Returns the full result dict (metadata + engine metrics + distribution).
    """
    df = load_{loadname}_bars(parquet, instrument, since, until, oos_token=oos_token)
    if len(df) < 1_000:
        raise SystemExit(f"Only {{len(df)}} bars loaded for {{instrument}} "
                         f"(window {{since or 'start'}}..{{until or 'latest'}}); not enough to backtest.")

    bars = make_bars(df, timeframe, entry_guard=entry_guard)
    meta = {{
        "strategy_id": "{sid}",
        "instrument": instrument,
        "timeframe": timeframe,
        "window_since": since,
        "window_until": until,
        "start": str(df["time"].iloc[0]),
        "end": str(df["time"].iloc[-1]),
        "cost_bps": cost_bps,
        "entry_guard": "off" if not entry_guard else "gap_bar|near_market_close",
        "ema_gate": ema_gate,
{metaparams}
    }}
    return run_strategy(build_rule(df, ema_gate=ema_gate{bpcall}), bars, cost_bps,
                        long_only=True, meta=meta)


def run(
    parquet: str,
    instrument: str,
    timeframe: str = "5m",
    since: str | None = None,
    until: str | None = None,
    cost_bps: float = COST_BPS,
    entry_guard: bool = False,
    ema_gate: bool = False,
{runparams}
    oos_token: object | None = None,
) -> dict:
    """Matrix-runner entry point (keyword-compatible with :func:`run_{runname}`)."""
    return run_{runname}(parquet, instrument, timeframe, since, until, cost_bps,
                      entry_guard, ema_gate, {runargs}oos_token=oos_token)


__all__ = [
    "{cls}",
    "build_rule",
    "load_{loadname}_bars",
    "run_{runname}",
    "run",
    "COST_BPS",
    "FEATURES_PARQUET",
    "FEATURES_1H_PARQUET",
    "TIMEFRAME_SECONDS",
    "TIMEFRAME_PARQUET",
    "load_bars",
    "make_bars",
    "detect_bar_seconds",
    "run_strategy",
]
'''


def nancheck(name: str) -> str:
    return f"        if not np.isfinite(self.{name}[j]):\n            return self.state\n"


def fresh_cross(name: str, cond_cur: str, cond_prev: str) -> str:
    return (f"            prev = self.{name}[j - 1] if j >= 1 else np.nan\n"
            f"            if {cond_cur} and (not np.isfinite(prev) or {cond_prev}):\n"
            f"                self.state = 1\n")


def build(sid, title, doc, cls, clsdoc, arrays, featurecols, notnullcols,
          condcheck, entry, exitc, loadname, params) -> str:
    sig = [f"{a}: np.ndarray" for a, _ in arrays] + \
          [f"{p[0]}: float = {p[1]}" for p in params] + \
          ["ema_gate: bool = False", "gate_ema: np.ndarray | None = None",
           "gate_close: np.ndarray | None = None"]
    initbody = "\n".join(f"        self.{a} = {a}" for a, _ in arrays)
    if params:
        initbody += "\n" + "\n".join(f"        self.{p[0]} = {p[0]}" for p in params)
    bargs = ", ".join(f'df["{c}"].to_numpy(np.float64)' for _, c in arrays)
    runparams = "".join(f"    {p[0]}: float = {p[1]},\n" for p in params)
    metaparams = "".join(f'        "{p[0]}": {p[0]},\n' for p in params)
    # trailing comma+space so `...ema_gate, {runargs}oos_token=...` stays valid
    # whether or not there are params
    runargs = (", ".join(p[0] for p in params) + ", ") if params else ""
    bparams = (", " + ", ".join(f"{p[0]}: float = {p[1]}" for p in params)) if params else ""
    bpkwargs = (", " + ", ".join(f"{p[0]}={p[0]}" for p in params)) if params else ""
    bpcall = (", " + ", ".join(f"{p[0]}={p[0]}" for p in params)) if params else ""
    fc = list(featurecols)
    if "ema_24" not in fc:
        fc.append("ema_24")
    header = HEADER.format(sid=sid, title=title, doc=doc)
    body = BODY.format(
        cls=cls, clsdoc=clsdoc.replace("\n", "\n    "),
        sig=", ".join(sig), initbody=initbody,
        condcheck=condcheck, entry=entry, exitc=exitc,
        bparams=bparams, bargs=bargs, bpkwargs=bpkwargs,
        loadname=loadname, runname=loadname,
        loadcols=", ".join(fc), featurecols=fc, notnullcols=notnullcols,
        runparams=runparams, metaparams=metaparams, sid=sid,
        runargs=runargs, bpcall=bpcall)
    return header + body


S = []
S.append(dict(sid="S-28", title="Candle close-location turn follower",
  doc=("Base rule (long-only): enter long when the *previous closed bar's* "
       "``bar_clv`` (close location value, (close-low)-(high-close) over the "
       "bar range, -1..+1 — a no-window *candle-structure* feature no earlier "
       "strategy has used) up-crosses ``k_in``; exit when ``bar_clv`` falls "
       "below ``k_exit``. The rule trades bar-body conviction (close near the "
       "high of a *completed* bar), not any windowed indicator."),
  cls="CandleClvState",
  clsdoc=("Candle close-location turn follower, long-only.\n"
    "``desired_position(i)`` = the position to hold at the open of bar ``i``,\n"
    "decided from the *previous* closed bar ``i-1``:\n"
    "* enter long: prev ``bar_clv`` > ``k_in`` (fresh up-cross);\n"
    "* exit:       prev ``bar_clv`` < ``k_exit``."),
  arrays=[("clv", "bar_clv")],
  featurecols=["bar_clv"], notnullcols=["bar_clv"],
  condcheck=nancheck("clv"),
  entry=fresh_cross("clv", "self.clv[j] > self.k_in", "prev <= self.k_in"),
  exitc="self.clv[j] < self.k_exit",
  loadname="candle",
  params=[("k_in", 0.4), ("k_exit", 0.1)]))
S.append(dict(sid="S-29", title="Volume-contraction trend buyer",
  doc=("Base rule (long-only): enter long when the *previous closed bar's* "
       "``vol_rel_24`` (tick-volume vs its 24-bar mean — a *volume-contraction* "
       "role no earlier strategy used) is below ``vmin`` (activity drying up) "
       "**and** close is above ``ema_24`` (direction); exit when ``vol_rel_24`` "
       "rises back above ``vmax``. Distinct from S-27 (which enters on volume "
       "*expansion*): contraction is the pre-breakout hush."),
  cls="VolConvergeState",
  clsdoc=("Volume-contraction trend buyer, long-only.\n"
    "``desired_position(i)`` = the position to hold at the open of bar ``i``,\n"
    "decided from the *previous* closed bar ``i-1``:\n"
    "* enter long: prev ``vol_rel_24`` < ``vmin`` and prev ``close_sig`` > prev ``ema_sig``;\n"
    "* exit:       prev ``vol_rel_24`` > ``vmax``."),
  arrays=[("volr", "vol_rel_24"), ("close_sig", "close"), ("ema_sig", "ema_24")],
  featurecols=["vol_rel_24", "ema_24"], notnullcols=["vol_rel_24", "ema_24"],
  condcheck=nancheck("volr") + nancheck("close_sig") + nancheck("ema_sig"),
  entry="            if self.volr[j] < self.vmin and self.close_sig[j] > self.ema_sig[j]:\n                self.state = 1\n",
  exitc="self.volr[j] > self.vmax",
  loadname="volconverge",
  params=[("vmin", 1.0), ("vmax", 1.5)]))
S.append(dict(sid="S-30", title="ATR-band EMA-distance turn",
  doc=("Base rule (long-only): enter long when the *previous closed bar's* "
       "``ema_dist_24`` (close distance from ``ema_24``, ATR-normalised — the "
       "derived scale-free distance no earlier strategy used) up-crosses "
       "``k_in`` (a fresh turn, not a stale level); exit when it falls below "
       "``k_exit``. Distinct from S-24 (band level follower: hold whenever "
       "distance >= k) — S-30 trades the *turn* of the distance with "
       "hysteresis exits."),
  cls="AtrBandPctState",
  clsdoc=("ATR-band EMA-distance turn, long-only.\n"
    "``desired_position(i)`` = the position to hold at the open of bar ``i``,\n"
    "decided from the *previous* closed bar ``i-1``:\n"
    "* enter long: prev ``ema_dist_24`` > ``k_in`` (fresh up-cross);\n"
    "* exit:       prev ``ema_dist_24`` < ``k_exit``."),
  arrays=[("dist", "ema_dist_24")],
  featurecols=["ema_dist_24"], notnullcols=["ema_dist_24"],
  condcheck=nancheck("dist"),
  entry=fresh_cross("dist", "self.dist[j] > self.k_in", "prev <= self.k_in"),
  exitc="self.dist[j] < self.k_exit",
  loadname="atrbandpct",
  params=[("k_in", 1.0), ("k_exit", 0.0)]))
S.append(dict(sid="S-31", title="Supertrend-distance follower",
  doc=("Base rule (long-only): hold long while the *previous closed bar's* "
       "``st_dist_24_2`` (close distance from the SuperTrend line, ATR-"
       "normalised and side-signed — a derived column no earlier strategy "
       "used) stays above ``th_in``; exit when it falls below ``th_exit``. "
       "Distinct from S-05/S-20 (which follow the SuperTrend *direction*): "
       "S-31 trades the signed *distance to the stop line*."),
  cls="StDistTrendState",
  clsdoc=("Supertrend-distance follower, long-only.\n"
    "``desired_position(i)`` = the position to hold at the open of bar ``i``,\n"
    "decided from the *previous* closed bar ``i-1``:\n"
    "* hold long: prev ``st_dist_24_2`` > ``th_in``;\n"
    "* exit:      prev ``st_dist_24_2`` < ``th_exit`` (hysteresis)."),
  arrays=[("st", "st_dist_24_2")],
  featurecols=["st_dist_24_2"], notnullcols=["st_dist_24_2"],
  condcheck=nancheck("st"),
  entry="            if self.st[j] > self.th_in:\n                self.state = 1\n",
  exitc="self.st[j] < self.th_exit",
  loadname="stdist",
  params=[("th_in", 0.5), ("th_exit", -0.5)]))
S.append(dict(sid="S-32", title="PSAR-distance follower",
  doc=("Base rule (long-only): hold long while the *previous closed bar's* "
       "``psar_dist_0p01_0p1`` (close distance from the slow Wilder SAR, "
       "ATR-normalised and side-signed — a derived column no earlier strategy "
       "used) stays above ``th_in``; exit when it falls below ``th_exit``. "
       "Distinct from S-13 (PSAR *direction* follower): S-32 uses the signed "
       "*distance*, so a shallow drift through the line is not an immediate "
       "exit while price is still clearly on one side."),
  cls="PsarDistState",
  clsdoc=("PSAR-distance follower, long-only.\n"
    "``desired_position(i)`` = the position to hold at the open of bar ``i``,\n"
    "decided from the *previous* closed bar ``i-1``:\n"
    "* hold long: prev ``psar_dist_0p01_0p1`` > ``th_in``;\n"
    "* exit:      prev ``psar_dist_0p01_0p1`` < ``th_exit`` (hysteresis)."),
  arrays=[("pd", "psar_dist_0p01_0p1")],
  featurecols=["psar_dist_0p01_0p1"], notnullcols=["psar_dist_0p01_0p1"],
  condcheck=nancheck("pd"),
  entry="            if self.pd[j] > self.th_in:\n                self.state = 1\n",
  exitc="self.pd[j] < self.th_exit",
  loadname="psardist",
  params=[("th_in", 0.5), ("th_exit", -0.5)]))
S.append(dict(sid="S-33", title="Keltner upper-band breakout",
  doc=("Base rule (long-only): enter long when the *previous closed bar's* "
       "close up-crosses ``kc_upper_24`` (Keltner band = ema_24 +/- 2*atr_24, "
       "the only band family no earlier strategy used — S-04/S-21 use "
       "Bollinger squeeze, S-08 uses Bollinger %B); exit when close falls "
       "back to/through ``kc_mid_24``."),
  cls="KcBreakState",
  clsdoc=("Keltner upper-band breakout, long-only.\n"
    "``desired_position(i)`` = the position to hold at the open of bar ``i``,\n"
    "decided from the *previous* closed bar ``i-1``:\n"
    "* enter long: prev close_sig > prev ``kc_upper_24`` (fresh up-cross);\n"
    "* exit:       prev close_sig <= prev ``kc_mid_24``."),
  arrays=[("close_sig", "close"), ("upper", "kc_upper_24"), ("mid", "kc_mid_24")],
  featurecols=["kc_upper_24", "kc_mid_24"], notnullcols=["kc_upper_24", "kc_mid_24"],
  condcheck=(nancheck("close_sig") + nancheck("upper") + nancheck("mid") +
    "        if j >= 1:\n"
    "            if not (np.isfinite(self.close_sig[j-1]) and np.isfinite(self.upper[j-1])):\n"
    "                return self.state\n"),
  entry="            if j >= 1 and self.close_sig[j] > self.upper[j] and self.close_sig[j-1] <= self.upper[j-1]:\n                self.state = 1\n",
  exitc="self.close_sig[j] <= self.mid[j]",
  loadname="kcbreak",
  params=[]))
S.append(dict(sid="S-34", title="Bollinger %B dip turn",
  doc=("Base rule (long-only): enter long when the *previous closed bar's* "
       "``bb_pctb_24`` (close position within the Bollinger band, ~0 at the "
       "lower band — S-08 only used %B as a *gate*) down-crosses ``k_in``; "
       "exit when ``bb_pctb_24`` rises back to/above ``k_exit``. Distinct "
       "from S-08 (CCI oscillator): S-34 trades the %B level itself as the "
       "oscillator."),
  cls="BbPctbTurnState",
  clsdoc=("Bollinger %B dip turn, long-only.\n"
    "``desired_position(i)`` = the position to hold at the open of bar ``i``,\n"
    "decided from the *previous* closed bar ``i-1``:\n"
    "* enter long: prev ``bb_pctb_24`` < ``k_in`` (fresh down-cross);\n"
    "* exit:       prev ``bb_pctb_24`` >= ``k_exit``."),
  arrays=[("pctb", "bb_pctb_24")],
  featurecols=["bb_pctb_24"], notnullcols=["bb_pctb_24"],
  condcheck=nancheck("pctb"),
  entry=fresh_cross("pctb", "self.pctb[j] < self.k_in", "prev >= self.k_in"),
  exitc="self.pctb[j] >= self.k_exit",
  loadname="bbpctb",
  params=[("k_in", 0.2), ("k_exit", 0.5)]))
S.append(dict(sid="S-35", title="Bollinger-width compression dip",
  doc=("Base rule (long-only): enter long when the *previous closed bar's* "
       "``bb_width_24`` (normalised Bollinger band width — the squeeze "
       "*magnitude*, which S-04/S-21 only read as the on/off flag ``sqz_on``) "
       "down-crosses ``low`` (volatility compressing) **and** the close is "
       "within its band (``bb_pctb_24`` > 0); exit when the width expands "
       "back above ``high``."),
  cls="BbWidthTurnState",
  clsdoc=("Bollinger-width compression dip, long-only.\n"
    "``desired_position(i)`` = the position to hold at the open of bar ``i``,\n"
    "decided from the *previous* closed bar ``i-1``:\n"
    "* enter long: prev ``bb_width_24`` < ``low`` (fresh) and prev ``bb_pctb_24`` > 0;\n"
    "* exit:       prev ``bb_width_24`` > ``high``."),
  arrays=[("width", "bb_width_24"), ("pctb", "bb_pctb_24")],
  featurecols=["bb_width_24", "bb_pctb_24"], notnullcols=["bb_width_24", "bb_pctb_24"],
  condcheck=nancheck("width") + nancheck("pctb"),
  entry=fresh_cross("width", "self.width[j] < self.low and self.pctb[j] > 0", "prev >= self.low"),
  exitc="self.width[j] > self.high",
  loadname="bbwidth",
  params=[("low", 0.03), ("high", 0.10)]))
S.append(dict(sid="S-36", title="Donchian-position turn",
  doc=("Base rule (long-only): enter long when the *previous closed bar's* "
       "``dc_pos_24`` (close position within the 24-bar Donchian channel, 0-1 "
       "— the channel *level*, which S-14 does not read) up-crosses ``k_in``; "
       "exit when ``dc_pos_24`` falls below ``k_exit``. Distinct from S-14 "
       "(close vs channel midline): S-36 trades the absolute position inside "
       "the channel with hysteresis."),
  cls="DcPosState",
  clsdoc=("Donchian-position turn, long-only.\n"
    "``desired_position(i)`` = the position to hold at the open of bar ``i``,\n"
    "decided from the *previous* closed bar ``i-1``:\n"
    "* enter long: prev ``dc_pos_24`` > ``k_in`` (fresh up-cross);\n"
    "* exit:       prev ``dc_pos_24`` < ``k_exit``."),
  arrays=[("pos", "dc_pos_24")],
  featurecols=["dc_pos_24"], notnullcols=["dc_pos_24"],
  condcheck=nancheck("pos"),
  entry=fresh_cross("pos", "self.pos[j] > self.k_in", "prev <= self.k_in"),
  exitc="self.pos[j] < self.k_exit",
  loadname="dcpos",
  params=[("k_in", 0.8), ("k_exit", 0.4)]))
S.append(dict(sid="S-37", title="Donchian midline fresh-cross",
  doc=("Base rule (long-only): enter long on the *fresh* up-cross of "
       "``dc_mid_24`` (close vs the Donchian midline — the same reference "
       "line S-14 uses, but S-14 *holds* through all time above the line "
       "while S-37 only re-enters on a new cross, so its trade frequency and "
       "holding periods differ); exit when close falls back to/below "
       "``dc_mid_24``."),
  cls="DcMidState",
  clsdoc=("Donchian midline fresh-cross, long-only.\n"
    "``desired_position(i)`` = the position to hold at the open of bar ``i``,\n"
    "decided from the *previous* closed bar ``i-1``:\n"
    "* enter long: prev close_sig > prev ``dc_mid_24`` and the bar before had close_sig <= mid;\n"
    "* exit:       prev close_sig <= prev ``dc_mid_24``."),
  arrays=[("close_sig", "close"), ("mid", "dc_mid_24")],
  featurecols=["dc_mid_24"], notnullcols=["dc_mid_24"],
  condcheck=(nancheck("close_sig") + nancheck("mid") +
    "        if j >= 1:\n"
    "            if not (np.isfinite(self.close_sig[j-1]) and np.isfinite(self.mid[j-1])):\n"
    "                return self.state\n"),
  entry="            if j >= 1 and self.close_sig[j] > self.mid[j] and self.close_sig[j-1] <= self.mid[j-1]:\n                self.state = 1\n",
  exitc="self.close_sig[j] <= self.mid[j]",
  loadname="dcmid",
  params=[]))
S.append(dict(sid="S-38", title="Distance-from-low turn",
  doc=("Base rule (long-only): enter long when the *previous closed bar's* "
       "``dist_low_24`` (ATR-normalised distance above the *previous* 24-bar "
       "low — a derived, lookahead-safe feature no earlier strategy used) "
       "up-crosses ``k_in`` (price lifting off its recent low); exit when it "
       "falls below ``k_exit`` (drift back toward the low). Distinct from "
       "S-14/S-24: the reference line is the recent *low*, and only the turn "
       "is traded."),
  cls="DistLowState",
  clsdoc=("Distance-from-low turn, long-only.\n"
    "``desired_position(i)`` = the position to hold at the open of bar ``i``,\n"
    "decided from the *previous* closed bar ``i-1``:\n"
    "* enter long: prev ``dist_low_24`` > ``k_in`` (fresh up-cross);\n"
    "* exit:       prev ``dist_low_24`` < ``k_exit``."),
  arrays=[("dl", "dist_low_24")],
  featurecols=["dist_low_24"], notnullcols=["dist_low_24"],
  condcheck=nancheck("dl"),
  entry=fresh_cross("dl", "self.dl[j] > self.k_in", "prev <= self.k_in"),
  exitc="self.dl[j] < self.k_exit",
  loadname="distlow",
  params=[("k_in", 1.0), ("k_exit", 0.2)]))
S.append(dict(sid="S-39", title="Donchian-width compression dip",
  doc=("Base rule (long-only): enter long when the *previous closed bar's* "
       "Donchian channel width (``dc_upper_24`` - ``dc_lower_24``) "
       "down-crosses ``w_in * atr_24`` (the 24-bar range contracting — "
       "channel compression, which no earlier strategy read); exit when the "
       "width expands back above ``w_exit * atr_24``. Distinct from S-04/S-21 "
       "(Bollinger-squeeze onset): the compression measure is the ATR-"
       "normalised Donchian range."),
  cls="DcWidthState",
  clsdoc=("Donchian-width compression dip, long-only.\n"
    "``desired_position(i)`` = the position to hold at the open of bar ``i``,\n"
    "decided from the *previous* closed bar ``i-1``:\n"
    "* enter long: prev width < w_in * prev atr (fresh compression);\n"
    "* exit:       prev width > w_exit * prev atr."),
  arrays=[("upper", "dc_upper_24"), ("lower", "dc_lower_24"), ("atr", "atr_24")],
  featurecols=["dc_upper_24", "dc_lower_24", "atr_24"],
  notnullcols=["dc_upper_24", "dc_lower_24", "atr_24"],
  condcheck=(nancheck("upper") + nancheck("lower") + nancheck("atr") +
    "        if not (self.atr[j] > 0):\n            return self.state\n"
    "        if j >= 1:\n"
    "            if not (np.isfinite(self.upper[j-1]) and np.isfinite(self.lower[j-1]) and np.isfinite(self.atr[j-1]) and self.atr[j-1] > 0):\n"
    "                return self.state\n"),
  entry=("            if j >= 1 and (self.upper[j] - self.lower[j]) < self.w_in * self.atr[j] and "
         "(self.upper[j-1] - self.lower[j-1]) >= self.w_in * self.atr[j-1]:\n"
         "                self.state = 1\n"),
  exitc="(self.upper[j] - self.lower[j]) > self.w_exit * self.atr[j]",
  loadname="dcwidth",
  params=[("w_in", 2.0), ("w_exit", 4.0)]))
S.append(dict(sid="S-40", title="SuperTrend side + distance hysteresis",
  doc=("Base rule (long-only): hold long while the *previous closed bar's* "
       "SuperTrend is up (``st_dir_24_2``) **and** the signed distance to "
       "the line (``st_dist_24_2``) stays above ``th_exit``; entry requires "
       "the distance to rise above ``th_in`` while the side is up (hysteresis "
       "between entry and exit). Distinct from S-05 (raw direction follower, "
       "exits the moment the line flips) and S-31 (distance only): the "
       "combination of side AND distance hysteresis is the new rule."),
  cls="StDistHystState",
  clsdoc=("SuperTrend side + distance hysteresis, long-only.\n"
    "``desired_position(i)`` = the position to hold at the open of bar ``i``,\n"
    "decided from the *previous* closed bar ``i-1``:\n"
    "* enter long: side up, prev ``st_dist_24_2`` > ``th_in`` (fresh side-up or dist-up);\n"
    "* exit:       side down or prev ``st_dist_24_2`` < ``th_exit``."),
  arrays=[("side", "st_dir_24_2"), ("dist", "st_dist_24_2")],
  featurecols=["st_dir_24_2", "st_dist_24_2"], notnullcols=["st_dir_24_2", "st_dist_24_2"],
  condcheck=(nancheck("side") + nancheck("dist") +
    "        if j >= 1:\n"
    "            if not (np.isfinite(self.side[j-1]) and np.isfinite(self.dist[j-1])):\n"
    "                return self.state\n"),
  entry=("            if (self.side[j] > 0 and self.dist[j] > self.th_in and "
         "(self.side[j-1] <= 0 or self.dist[j-1] <= self.th_in)):\n"
         "                self.state = 1\n"),
  exitc="self.side[j] <= 0 or self.dist[j] < self.th_exit",
  loadname="stdisthyst",
  params=[("th_in", 1.0), ("th_exit", 0.2)]))

S.append(dict(sid="S-41", title="Realized-volatility contraction",
  doc=("Base rule (long-only): hold long while the *previous closed bar's* "
       "``hv_24`` (rolling std of log returns — *realized volatility*, a "
       "different compression proxy from the band-width measures S-04/S-21/S-35 "
       "use) stays below ``k_in`` (the market compressing); exit when it rises "
       "back above ``k_exit``. Distinct from S-35 (Bollinger band width) and "
       "S-04/S-21 (Bollinger/Keltner squeeze flag): the signal is the return-"
       "distribution dispersion, not a band."),
  cls="HvConvergeState",
  clsdoc=("Realized-volatility contraction, long-only.\n"
    "``desired_position(i)`` = the position to hold at the open of bar ``i``,\n"
    "decided from the *previous* closed bar ``i-1``:\n"
    "* hold long: prev ``hv_24`` < ``k_in``;\n"
    "* exit:      prev ``hv_24`` > ``k_exit`` (hysteresis)."),
  arrays=[("hv", "hv_24")],
  featurecols=["hv_24"], notnullcols=["hv_24"],
  condcheck=nancheck("hv"),
  entry="            if self.hv[j] < self.k_in:\n                self.state = 1\n",
  exitc="self.hv[j] > self.k_exit",
  loadname="hvconverge",
  params=[("k_in", 0.0003), ("k_exit", 0.0006)]))
S.append(dict(sid="S-42", title="Bar-body momentum turn",
  doc=("Base rule (long-only): enter long when the *previous closed bar's* "
       "``bar_body_ratio`` (body / range, 0..1 — a no-window *candle "
       "structure* feature; high values are close-driven, near-unidirectional "
       "bars, a feature no earlier strategy used) up-crosses ``k_in`` (a "
       "fresh strong body, not a stale one); exit when it falls below "
       "``k_exit``. Distinct from S-28 (which trades the close *location* "
       "``bar_clv``): S-42 trades bar-body *size* (conviction), not position."),
  cls="BarBodyState",
  clsdoc=("Bar-body momentum turn, long-only.\n"
    "``desired_position(i)`` = the position to hold at the open of bar ``i``,\n"
    "decided from the *previous* closed bar ``i-1``:\n"
    "* enter long: prev ``bar_body_ratio`` > ``k_in`` (fresh up-cross);\n"
    "* exit:       prev ``bar_body_ratio`` < ``k_exit``."),
  arrays=[("body", "bar_body_ratio")],
  featurecols=["bar_body_ratio"], notnullcols=["bar_body_ratio"],
  condcheck=nancheck("body"),
  entry=fresh_cross("body", "self.body[j] > self.k_in", "prev <= self.k_in"),
  exitc="self.body[j] < self.k_exit",
  loadname="barbody",
  params=[("k_in", 0.6), ("k_exit", 0.3)]))

FILES = {
  "S-28": "strategy/strategy_candle_lib.py",
  "S-29": "strategy/strategy_volconverge_lib.py",
  "S-30": "strategy/strategy_atrbandpct_lib.py",
  "S-31": "strategy/strategy_stdist_lib.py",
  "S-32": "strategy/strategy_psardist_lib.py",
  "S-33": "strategy/strategy_kcbreak_lib.py",
  "S-34": "strategy/strategy_bb_pctb_lib.py",
  "S-35": "strategy/strategy_bb_width_lib.py",
  "S-36": "strategy/strategy_dcpos_lib.py",
  "S-37": "strategy/strategy_dcmid_lib.py",
  "S-38": "strategy/strategy_distlow_lib.py",
  "S-39": "strategy/strategy_dcwidth_lib.py",
  "S-40": "strategy/strategy_stdist_hyst_lib.py",
  "S-41": "strategy/strategy_hvconverge_lib.py",
  "S-42": "strategy/strategy_barbody_lib.py",
}


def main() -> None:
    for s in S:
        out = ROOT / FILES[s["sid"]]
        out.write_text(build(**s))
        print("wrote", out.name, s["sid"])


if __name__ == "__main__":
    main()
