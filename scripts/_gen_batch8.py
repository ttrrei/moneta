"""One-shot generator for the S-103..S-112 signal libs (batch 8).

Reuses the SAME template, helpers, and ``build()`` as :mod:`_gen_batch3`
(via importlib); only the strategy specs and the FILES map differ. Each
strategy is a stateful SignalRule with a ``run``/``run_*`` surface, the
optional ``ema_gate`` improvement knob, and a ``k_in``/``k_exit`` hysteresis
pair that the 8-variant sweep tunes.

All 10 use feature columns / families that no earlier strategy (S-01..S-102)
traded as the primary signal — new families this batch:
  slow Choppiness (`chop_120` S-103),
  slow Chaikin Money Flow (`cmf_60` S-104),
  60-bar HV (`hv_60` S-105),
  slow Stochastic-D (`stoch_d_60` S-106),
  slow Bollinger squeeze (`sqz_on_120` S-107),
  ultra-fast RSI (`rsi_6` S-108),
  slow ADX (`adx_60` S-109),
  slow absolute ATR (`atr_120` S-110),
  ultra-fast Williams-%R (`willr_6` S-111),
  slow Efficiency Ratio (`er_60` S-112).

Run:  venv/bin/python scripts/_gen_batch8.py
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

def mk(sid, title, cls, arrs, feat, nn, cond, entry, exitc, load, params=None, doc="", clsdoc=""):
    return dict(sid=sid, title=title, doc=doc, cls=cls, clsdoc=clsdoc, arrays=arrs,
                featurecols=feat, notnullcols=nn, condcheck=cond, entry=entry,
                exitc=exitc, loadname=load, params=params or [])

S = []

# --- S-103 slow Choppiness (low = trending) ----------------------------------
S.append(mk("S-103", "Slow Choppiness (low = trend)", "Chop120State",
  [("c", "chop_120")],
  ["chop_120"], ["chop_120"],
  nancheck("c"),
  fresh_cross("c", "self.c[j] < self.k_in", "prev >= self.k_in"),
  "self.c[j] > self.k_exit",
  "chop120", params=[("k_in", 40.0), ("k_exit", 60.0)]))

# --- S-104 slow Chaikin Money Flow (accumulation) -----------------------------
S.append(mk("S-104", "Slow CMF accumulation", "Cmf60State",
  [("m", "cmf_60")],
  ["cmf_60"], ["cmf_60"],
  nancheck("m"),
  fresh_cross("m", "self.m[j] > self.k_in", "prev <= self.k_in"),
  "self.m[j] < self.k_exit",
  "cmf60", params=[("k_in", 0.05), ("k_exit", 0.0)]))

# --- S-105 60-bar HV low-vol regime -------------------------------------------
S.append(mk("S-105", "60-bar HV low-vol regime", "Hv60State",
  [("h", "hv_60")],
  ["hv_60"], ["hv_60"],
  nancheck("h"),
  fresh_cross("h", "self.h[j] < self.k_in", "prev >= self.k_in"),
  "self.h[j] > self.k_exit",
  "hv60", params=[("k_in", 0.0005), ("k_exit", 0.001)]))

# --- S-106 slow Stochastic-D turn ----------------------------------------------
S.append(mk("S-106", "Slow Stochastic-D turn", "StochD60State",
  [("d", "stoch_d_60")],
  ["stoch_d_60"], ["stoch_d_60"],
  nancheck("d"),
  fresh_cross("d", "self.d[j] > self.k_in", "prev <= self.k_in"),
  "self.d[j] < self.k_exit",
  "stochd60", params=[("k_in", 55.0), ("k_exit", 40.0)]))

# --- S-107 slow Bollinger squeeze (flag rule) -----------------------------------
S.append(mk("S-107", "Slow Bollinger squeeze", "Sqz120State",
  [("s", "sqz_on_120")],
  ["sqz_on_120"], ["sqz_on_120"],
  nancheck("s"),
  ("            prev = self.s[j-1] if j >= 1 else np.nan\n"
   "            if self.s[j] > 0 and (not np.isfinite(prev) or prev <= 0):\n"
   "                self.state = 1\n"),
  "self.s[j] <= 0",
  "sqz120"))

# --- S-108 ultra-fast RSI-6 rebound ---------------------------------------------
S.append(mk("S-108", "Ultra-fast RSI-6 rebound", "Rsi6State",
  [("r", "rsi_6")],
  ["rsi_6"], ["rsi_6"],
  nancheck("r"),
  fresh_cross("r", "self.r[j] > self.k_in", "prev <= self.k_in"),
  "self.r[j] < self.k_exit",
  "rsi6", params=[("k_in", 55.0), ("k_exit", 40.0)]))

# --- S-109 slow ADX (low = range regime) -----------------------------------------
S.append(mk("S-109", "Slow ADX range regime", "Adx60State",
  [("a", "adx_60")],
  ["adx_60"], ["adx_60"],
  nancheck("a"),
  fresh_cross("a", "self.a[j] < self.k_in", "prev >= self.k_in"),
  "self.a[j] > self.k_exit",
  "adx60", params=[("k_in", 20.0), ("k_exit", 35.0)]))

# --- S-110 slow Stochastic-K (120-bar) -------------------------------------------
S.append(mk("S-110", "Slow Stochastic-K (120-bar)", "StochK120State",
  [("k", "stoch_k_120")],
  ["stoch_k_120"], ["stoch_k_120"],
  nancheck("k"),
  fresh_cross("k", "self.k[j] > self.k_in", "prev <= self.k_in"),
  "self.k[j] < self.k_exit",
  "stochk120", params=[("k_in", 55.0), ("k_exit", 40.0)]))

# --- S-111 ultra-fast Williams-%R rebound -----------------------------------------
S.append(mk("S-111", "Ultra-fast Williams-%R rebound", "Willr6State",
  [("w", "willr_6")],
  ["willr_6"], ["willr_6"],
  nancheck("w"),
  ("            prev = self.w[j-1] if j >= 1 else np.nan\n"
   "            if self.w[j] > self.k_in and (not np.isfinite(prev) or prev <= self.k_in):\n"
   "                self.state = 1\n"),
  "self.w[j] < self.k_exit",
  "willr6", params=[("k_in", -60.0), ("k_exit", -80.0)]))

# --- S-112 slow Efficiency Ratio (trending) ----------------------------------------
S.append(mk("S-112", "Slow Efficiency-Ratio trend", "Er60State",
  [("e", "er_60")],
  ["er_60"], ["er_60"],
  nancheck("e"),
  fresh_cross("e", "self.e[j] > self.k_in", "prev <= self.k_in"),
  "self.e[j] < self.k_exit",
  "er60", params=[("k_in", 0.3), ("k_exit", 0.15)]))


FILES = {
  "S-103": "strategy/strategy_chop120_lib.py",
  "S-104": "strategy/strategy_cmf60_lib.py",
  "S-105": "strategy/strategy_hv60_lib.py",
  "S-106": "strategy/strategy_stochd60_lib.py",
  "S-107": "strategy/strategy_sqz120_lib.py",
  "S-108": "strategy/strategy_rsi6_lib.py",
  "S-109": "strategy/strategy_adx60_lib.py",
  "S-110": "strategy/strategy_stochk120_lib.py",
  "S-111": "strategy/strategy_willr6_lib.py",
  "S-112": "strategy/strategy_er60_lib.py",
}


def main() -> None:
    assert len(S) == 10, f"expected 10 strategies, got {len(S)}"
    seen = [s["sid"] for s in S]
    assert len(set(seen)) == 10, f"duplicate sids: {seen}"
    for s in S:
        assert s["sid"] in FILES, f"missing FILES entry for {s['sid']}"
        out = ROOT / FILES[s["sid"]]
        out.write_text(build(**s))
        print("wrote", out.name, s["sid"])


if __name__ == "__main__":
    main()
