"""One-shot generator for the S-73..S-87 signal libs (batch 6).

Reuses the SAME template, helpers, and ``build()`` as :mod:`_gen_batch3`
(via importlib); only the strategy specs and the FILES map differ. Each
strategy is a stateful SignalRule with a ``run``/``run_*`` surface, the
optional ``ema_gate`` improvement knob, and a ``k_in``/``k_exit`` hysteresis
pair that the 8-variant sweep tunes.

All 15 use feature columns that no earlier strategy (S-01..S-72) traded as
the primary signal — new families this batch: slow-window oscillators
(`aroon_up_60` S-73, `willr_60` S-74, `cci_120` S-75, `stoch_k_60` S-76,
`mfi_60` S-77), slow-window momentum (`roc_120` S-79), time-of-day regime
(`hour_sin` S-80, `dow_sin` S-81), true-range collapse (S-82), slow-PSAR
direction (S-83), dual-SuperTrend 120/24 alignment (S-84), 1h two-scale
SuperTrend (S-85), and slow-ROC + volume confluence (S-87).

Run:  venv/bin/python scripts/_gen_batch6.py
"""

from __future__ import annotations

import importlib.util
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]

_spec = importlib.util.spec_from_file_location("_g3", str(ROOT / "scripts" / "_gen_batch3.py"))
_g3 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_g3)
build = _g3.build
nancheck = _g3.nancheck
fresh_cross = _g3.fresh_cross

JGUARD = ("        if j >= 1:\n"
          "            if not (np.isfinite(self.{a}[j-1]) and np.isfinite(self.{b}[j-1])):\n"
          "                return self.state\n")

def jguard(a: str, b: str) -> str:
    return JGUARD.format(a=a, b=b)

def mk(sid, title, cls, arrs, feat, nn, cond, entry, exitc, load, params=None, doc="", clsdoc=""):
    return dict(sid=sid, title=title, doc=doc, cls=cls, clsdoc=clsdoc, arrays=arrs,
                featurecols=feat, notnullcols=nn, condcheck=cond, entry=entry,
                exitc=exitc, loadname=load, params=params or [])

S = []

# --- S-73 slow Aroon-Up trend follower --------------------------------------
S.append(mk("S-73", "Slow Aroon-Up trend", "AroonUp60State",
  [("au", "aroon_up_60")],
  ["aroon_up_60"], ["aroon_up_60"],
  nancheck("au"),
  fresh_cross("au", "self.au[j] > self.k_in", "prev <= self.k_in"),
  "self.au[j] < self.k_exit",
  "aroonup60", params=[("k_in", 70.0), ("k_exit", 40.0)]))

# --- S-74 slow Williams %R rebound buyer ------------------------------------
S.append(mk("S-74", "Slow Williams-%R rebound", "Willr60State",
  [("w", "willr_60")],
  ["willr_60"], ["willr_60"],
  nancheck("w"),
  ("            prev = self.w[j-1] if j >= 1 else np.nan\n"
   "            if self.w[j] > self.k_in and (not np.isfinite(prev) or prev <= self.k_in):\n"
   "                self.state = 1\n"),
  "self.w[j] < self.k_exit",
  "willr60", params=[("k_in", -50.0), ("k_exit", -80.0)]))

# --- S-75 slow CCI momentum follower ----------------------------------------
S.append(mk("S-75", "Slow CCI momentum", "Cci120State",
  [("c", "cci_120")],
  ["cci_120"], ["cci_120"],
  nancheck("c"),
  fresh_cross("c", "self.c[j] > self.k_in", "prev <= self.k_in"),
  "self.c[j] < self.k_exit",
  "cci120", params=[("k_in", 100.0), ("k_exit", 50.0)]))

# --- S-76 slow Stochastic-K turn ---------------------------------------------
S.append(mk("S-76", "Slow Stochastic-K turn", "StochK60State",
  [("k", "stoch_k_60")],
  ["stoch_k_60"], ["stoch_k_60"],
  nancheck("k"),
  fresh_cross("k", "self.k[j] > self.k_in", "prev <= self.k_in"),
  "self.k[j] < self.k_exit",
  "stochk60", params=[("k_in", 80.0), ("k_exit", 50.0)]))

# --- S-77 slow MFI accumulation follower -------------------------------------
S.append(mk("S-77", "Slow MFI accumulation", "Mfi60State",
  [("m", "mfi_60")],
  ["mfi_60"], ["mfi_60"],
  nancheck("m"),
  fresh_cross("m", "self.m[j] > self.k_in", "prev <= self.k_in"),
  "self.m[j] < self.k_exit",
  "mfi60", params=[("k_in", 80.0), ("k_exit", 55.0)]))

# --- S-78 slow ATR-% expansion regime ----------------------------------------
S.append(mk("S-78", "Slow ATR-% expansion", "AtrPct120State",
  [("ap", "atr_pct_120"), ("close_sig", "close"), ("ema_sig", "ema_24")],
  ["atr_pct_120"], ["atr_pct_120"],
  nancheck("ap") + nancheck("close_sig") + nancheck("ema_sig"),
  ("            prev = self.ap[j-1] if j >= 1 else np.nan\n"
   "            if self.ap[j] > self.k_in and self.close_sig[j] > self.ema_sig[j] and "
   "(not np.isfinite(prev) or prev <= self.k_in):\n"
   "                self.state = 1\n"),
  "(self.ap[j] < self.k_exit) or (self.close_sig[j] <= self.ema_sig[j])",
  "atrpct120", params=[("k_in", 0.006), ("k_exit", 0.003)]))

# --- S-79 slow ROC momentum --------------------------------------------------
S.append(mk("S-79", "Slow ROC momentum", "Roc120State",
  [("r", "roc_120")],
  ["roc_120"], ["roc_120"],
  nancheck("r"),
  fresh_cross("r", "self.r[j] > self.k_in", "prev <= self.k_in"),
  "self.r[j] < self.k_exit",
  "roc120", params=[("k_in", 0.02), ("k_exit", 0.0)]))

# --- S-80 time-of-day (hour_sin) regime --------------------------------------
S.append(mk("S-80", "Time-of-day (hour_sin) regime", "HourSinState",
  [("h", "hour_sin")],
  ["hour_sin"], ["hour_sin"],
  nancheck("h"),
  fresh_cross("h", "self.h[j] > self.k_in", "prev <= self.k_in"),
  "self.h[j] < self.k_exit",
  "hoursin", params=[("k_in", 0.5), ("k_exit", -0.5)]))

# --- S-81 day-of-week (dow_sin) regime ----------------------------------------
S.append(mk("S-81", "Day-of-week (dow_sin) regime", "DowSinState",
  [("d", "dow_sin")],
  ["dow_sin"], ["dow_sin"],
  nancheck("d"),
  fresh_cross("d", "self.d[j] > self.k_in", "prev <= self.k_in"),
  "self.d[j] < self.k_exit",
  "dowsin", params=[("k_in", 0.5), ("k_exit", -0.5)]))

# --- S-82 true-range collapse ------------------------------------------------
S.append(mk("S-82", "True-range collapse", "TrState",
  [("tr_", "tr")],
  ["tr"], ["tr"],
  nancheck("tr_"),
  ("            prev = self.tr_[j-1] if j >= 1 else np.nan\n"
   "            if self.tr_[j] < self.k_in and (not np.isfinite(prev) or prev >= self.k_in):\n"
   "                self.state = 1\n"),
  "self.tr_[j] > self.k_exit",
  "trcollapse", params=[("k_in", 0.001), ("k_exit", 0.002)]))

# --- S-83 slow-PSAR direction follower ----------------------------------------
S.append(mk("S-83", "Slow-PSAR direction follower", "Psar002State",
  [("p", "psar_dir_0p02_0p2")],
  ["psar_dir_0p02_0p2"], ["psar_dir_0p02_0p2"],
  nancheck("p"),
  ("            prev = self.p[j-1] if j >= 1 else np.nan\n"
   "            if self.p[j] > 0 and (not np.isfinite(prev) or prev <= 0):\n"
   "                self.state = 1\n"),
  "self.p[j] <= 0",
  "psar002"))

# --- S-84 dual SuperTrend 120/24 alignment ------------------------------------
S.append(mk("S-84", "Dual SuperTrend 120/24 alignment", "StDual120State",
  [("st120", "st_dir_120_3"), ("st24", "st_dir_24_3")],
  ["st_dir_120_3", "st_dir_24_3"], ["st_dir_120_3", "st_dir_24_3"],
  nancheck("st120") + nancheck("st24") + jguard("st120", "st24"),
  ("            prev_ok = (self.st120[j-1] > 0 and self.st24[j-1] > 0) if j >= 1 else False\n"
   "            if self.st120[j] > 0 and self.st24[j] > 0 and not prev_ok:\n"
   "                self.state = 1\n"),
  "(self.st120[j] <= 0) or (self.st24[j] <= 0)",
  "stdual120"))

# --- S-85 1h SuperTrend 120 (two-scale) ---------------------------------------
S.append(mk("S-85", "1h SuperTrend-120 two-scale", "H1St120State",
  [("h1st", "h1_st_dir_120_3"), ("st24", "st_dir_24_3")],
  ["h1_st_dir_120_3", "st_dir_24_3"], ["h1_st_dir_120_3", "st_dir_24_3"],
  nancheck("h1st") + nancheck("st24") + jguard("h1st", "st24"),
  ("            prev_ok = (self.h1st[j-1] > 0 and self.st24[j-1] > 0) if j >= 1 else False\n"
   "            if self.h1st[j] > 0 and self.st24[j] > 0 and not prev_ok:\n"
   "                self.state = 1\n"),
  "(self.h1st[j] <= 0) or (self.st24[j] <= 0)",
  "h1st120"))

# --- S-86 dual time-of-day (hour + dow) confluence -----------------------------
S.append(mk("S-86", "Dual time-of-day confluence", "TimeConfluenceState",
  [("h", "hour_sin"), ("d", "dow_sin")],
  ["hour_sin", "dow_sin"], ["hour_sin", "dow_sin"],
  nancheck("h") + nancheck("d"),
  ("            prev_ok = (self.h[j-1] > self.k_in and self.d[j-1] > self.d_in) if j >= 1 else False\n"
   "            if self.h[j] > self.k_in and self.d[j] > self.d_in and not prev_ok:\n"
   "                self.state = 1\n"),
  "(self.h[j] < self.k_exit) or (self.d[j] < self.d_exit)",
  "timeconf", params=[("k_in", 0.5), ("k_exit", -0.5), ("d_in", 0.0), ("d_exit", -0.5)]))

# --- S-87 slow-ROC + volume confluence -----------------------------------------
S.append(mk("S-87", "Slow-ROC + volume confluence", "Roc120VolState",
  [("r", "roc_120"), ("vr", "vol_rel_24")],
  ["roc_120", "vol_rel_24"], ["roc_120", "vol_rel_24"],
  nancheck("r") + nancheck("vr"),
  ("            prev = self.r[j-1] if j >= 1 else np.nan\n"
   "            if self.r[j] > self.k_in and self.vr[j] > self.vmin and "
   "(not np.isfinite(prev) or prev <= self.k_in):\n"
   "                self.state = 1\n"),
  "(self.r[j] < self.k_exit) or (self.vr[j] < self.vexit)",
  "roc120vol", params=[("k_in", 0.02), ("k_exit", 0.0), ("vmin", 1.0), ("vexit", 0.8)]))


FILES = {
  "S-73": "strategy/strategy_aroonup60_lib.py",
  "S-74": "strategy/strategy_willr60_lib.py",
  "S-75": "strategy/strategy_cci120_lib.py",
  "S-76": "strategy/strategy_stochk60_lib.py",
  "S-77": "strategy/strategy_mfi60_lib.py",
  "S-78": "strategy/strategy_atrpct120_lib.py",
  "S-79": "strategy/strategy_roc120_lib.py",
  "S-80": "strategy/strategy_hoursin_lib.py",
  "S-81": "strategy/strategy_dowsin_lib.py",
  "S-82": "strategy/strategy_trcollapse_lib.py",
  "S-83": "strategy/strategy_psar002_lib.py",
  "S-84": "strategy/strategy_stdual120_lib.py",
  "S-85": "strategy/strategy_h1st120_lib.py",
  "S-86": "strategy/strategy_timeconf_lib.py",
  "S-87": "strategy/strategy_roc120vol_lib.py",
}


def main() -> None:
    for s in S:
        out = ROOT / FILES[s["sid"]]
        out.write_text(build(**s))
        print("wrote", out.name, s["sid"])


if __name__ == "__main__":
    main()
