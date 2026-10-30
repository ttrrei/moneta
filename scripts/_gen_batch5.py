"""One-shot generator for the S-58..S-72 signal libs (batch 5).

Reuses the SAME template, helpers, and ``build()`` as :mod:`_gen_batch3`
(the S-28..S-42 generator) via importlib; only the strategy specs and the
FILES map differ. Each strategy is a stateful SignalRule with a
``run``/``run_*`` surface, the optional ``ema_gate`` improvement knob, and
(whenever it makes sense) a ``k_in``/``k_exit`` hysteresis pair that the
8-variant sweep tunes.

All 15 use feature columns that no earlier strategy (S-01..S-57) traded as
the primary signal — new families: rate-of-change hysteresis, Stochastic
K/D-turn and K-mid-turn, Aroon-Down collapse, momentum sign-turn,
realized-volatility expansion + trend, Bollinger-upper / Donchian-upper
breakout, lower-wick rejection, volume-confirmed band breakout, 1h-ADX +
1h-SuperTrend alignment, dual-SuperTrend alignment, 1h-low-vol coil + trend,
Aroon + Stochastic confluence, and ROC + volume confluence.

Run:  venv/bin/python scripts/_gen_batch5.py
"""

from __future__ import annotations

import importlib.util
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]

# Reuse the batch-3 template + helpers + build() (no __main__ side effects).
_spec = importlib.util.spec_from_file_location("_g3", str(ROOT / "scripts" / "_gen_batch3.py"))
_g3 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_g3)
build = _g3.build
nancheck = _g3.nancheck
fresh_cross = _g3.fresh_cross

# Two-array previous-bar NaN guard (like S-44/S-45's jguard pattern).
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

# --- S-58 rate-of-change hysteresis -----------------------------------------
S.append(mk("S-58", "Rate-of-change hysteresis", "RocState",
  [("r", "roc_24")],
  ["roc_24"], ["roc_24"],
  nancheck("r"),
  fresh_cross("r", "self.r[j] > self.k_in", "prev <= self.k_in"),
  "self.r[j] < self.k_exit",
  "roc", params=[("k_in", 0.004), ("k_exit", 0.0)]))

# --- S-59 Stochastic K/D-turn (oversold rebound) -----------------------------
S.append(mk("S-59", "Stochastic K/D-turn rebound", "StochKdState",
  [("k", "stoch_k_24"), ("d", "stoch_d_24")],
  ["stoch_k_24", "stoch_d_24"], ["stoch_k_24", "stoch_d_24"],
  nancheck("k") + nancheck("d") + jguard("k", "d"),
  ("            prev_ok = (self.k[j-1] > self.d[j-1]) if j >= 1 else False\n"
   "            if self.k[j] > self.d[j] and self.k[j] < self.k_in and not prev_ok:\n"
   "                self.state = 1\n"),
  "self.k[j] > self.k_exit",
  "stochkd", params=[("k_in", 30.0), ("k_exit", 70.0)]))

# --- S-60 Aroon-Down collapse ------------------------------------------------
S.append(mk("S-60", "Aroon-Down collapse", "AroonDnState",
  [("ad", "aroon_down_24")],
  ["aroon_down_24"], ["aroon_down_24"],
  nancheck("ad"),
  fresh_cross("ad", "self.ad[j] < self.k_in", "prev >= self.k_in"),
  "self.ad[j] > self.k_exit",
  "aroondn", params=[("k_in", 30.0), ("k_exit", 70.0)]))

# --- S-61 momentum sign-turn -------------------------------------------------
S.append(mk("S-61", "Momentum sign-turn", "MomSignState",
  [("m", "mom_24")],
  ["mom_24"], ["mom_24"],
  nancheck("m"),
  fresh_cross("m", "self.m[j] > self.k_in", "prev <= self.k_in"),
  "self.m[j] < self.k_exit",
  "momsign", params=[("k_in", 0.5), ("k_exit", -0.5)]))

# --- S-62 realized-vol expansion + trend ------------------------------------
S.append(mk("S-62", "Realized-vol expansion + trend", "HvUpState",
  [("hv", "hv_24"), ("close_sig", "close"), ("ema_sig", "ema_24")],
  ["hv_24"], ["hv_24"],
  nancheck("hv") + nancheck("close_sig") + nancheck("ema_sig"),
  ("            prev = self.hv[j-1] if j >= 1 else np.nan\n"
   "            if self.hv[j] > self.k_in and self.close_sig[j] > self.ema_sig[j] and "
   "(not np.isfinite(prev) or prev <= self.k_in):\n"
   "                self.state = 1\n"),
  "self.hv[j] < self.k_exit",
  "hvup", params=[("k_in", 0.0025), ("k_exit", 0.0015)]))

# --- S-63 Bollinger-upper breakout -------------------------------------------
S.append(mk("S-63", "Bollinger-upper breakout", "BbUpperState",
  [("close_sig", "close"), ("up", "bb_upper_24")],
  ["bb_upper_24"], ["bb_upper_24"],
  nancheck("close_sig") + nancheck("up") + jguard("close_sig", "up"),
  ("            prev_ok = (self.close_sig[j-1] > self.up[j-1]) if j >= 1 else False\n"
   "            if self.close_sig[j] > self.up[j] and not prev_ok:\n"
   "                self.state = 1\n"),
  "self.close_sig[j] < self.up[j]",
  "bbupper"))

# --- S-64 Donchian-upper breakout -------------------------------------------
S.append(mk("S-64", "Donchian-upper breakout", "DcUpperState",
  [("close_sig", "close"), ("up", "dc_upper_24"), ("mid", "bb_mid_24")],
  ["dc_upper_24", "bb_mid_24"], ["dc_upper_24", "bb_mid_24"],
  nancheck("close_sig") + nancheck("up") + nancheck("mid") + jguard("close_sig", "up"),
  ("            prev_ok = (self.close_sig[j-1] > self.up[j-1]) if j >= 1 else False\n"
   "            if self.close_sig[j] > self.up[j] and not prev_ok:\n"
   "                self.state = 1\n"),
  "self.close_sig[j] < self.mid[j]",
  "dcupper"))

# --- S-65 lower-wick rejection -----------------------------------------------
S.append(mk("S-65", "Lower-wick rejection", "LowWickState",
  [("lw", "bar_lower_wick_ratio")],
  ["bar_lower_wick_ratio"], ["bar_lower_wick_ratio"],
  nancheck("lw"),
  fresh_cross("lw", "self.lw[j] > self.k_in", "prev <= self.k_in"),
  "self.lw[j] < self.k_exit",
  "lowwick", params=[("k_in", 0.5), ("k_exit", 0.15)]))

# --- S-66 volume-confirmed band breakout ------------------------------------
S.append(mk("S-66", "Volume-confirmed band breakout", "VolBbState",
  [("close_sig", "close"), ("up", "bb_upper_24"), ("volr", "vol_rel_24")],
  ["bb_upper_24", "vol_rel_24"], ["bb_upper_24", "vol_rel_24"],
  nancheck("close_sig") + nancheck("up") + nancheck("volr") + jguard("close_sig", "up"),
  ("            prev_ok = (self.close_sig[j-1] > self.up[j-1]) if j >= 1 else False\n"
   "            if self.close_sig[j] > self.up[j] and self.volr[j] > self.vmin and not prev_ok:\n"
   "                self.state = 1\n"),
  "self.close_sig[j] < self.up[j]",
  "volbb", params=[("vmin", 1.0)]))

# --- S-67 1h-ADX + 1h-SuperTrend alignment -----------------------------------
S.append(mk("S-67", "1h ADX + 1h SuperTrend alignment", "H1AdxStState",
  [("a", "h1_adx_24"), ("st1", "h1_st_dir_24_3")],
  ["h1_adx_24", "h1_st_dir_24_3"], ["h1_adx_24", "h1_st_dir_24_3"],
  nancheck("a") + nancheck("st1") + jguard("a", "st1"),
  ("            prev_ok = (self.a[j-1] > self.k_in and self.st1[j-1] > 0) if j >= 1 else False\n"
   "            if self.a[j] > self.k_in and self.st1[j] > 0 and not prev_ok:\n"
   "                self.state = 1\n"),
  "(self.a[j] < self.k_exit) or (self.st1[j] <= 0)",
  "h1adxst", params=[("k_in", 25.0), ("k_exit", 20.0)]))

# --- S-68 dual-SuperTrend alignment ------------------------------------------
S.append(mk("S-68", "Dual-SuperTrend alignment", "DualStState",
  [("st24", "st_dir_24_3"), ("st120", "st_dir_120_2")],
  ["st_dir_24_3", "st_dir_120_2"], ["st_dir_24_3", "st_dir_120_2"],
  nancheck("st24") + nancheck("st120") + jguard("st24", "st120"),
  ("            prev_ok = (self.st24[j-1] > 0 and self.st120[j-1] > 0) if j >= 1 else False\n"
   "            if self.st24[j] > 0 and self.st120[j] > 0 and not prev_ok:\n"
   "                self.state = 1\n"),
  "(self.st24[j] <= 0) or (self.st120[j] <= 0)",
  "dualst"))

# --- S-69 Stochastic-K mid-turn + trend --------------------------------------
S.append(mk("S-69", "Stochastic-K mid-turn + trend", "StochKState",
  [("k", "stoch_k_24"), ("close_sig", "close"), ("ema_sig", "ema_24")],
  ["stoch_k_24"], ["stoch_k_24"],
  nancheck("k") + nancheck("close_sig") + nancheck("ema_sig"),
  fresh_cross("k", "self.k[j] > self.k_in", "prev <= self.k_in"),
  "self.k[j] < self.k_exit",
  "stok", params=[("k_in", 50.0), ("k_exit", 40.0)]))

# --- S-70 1h-low-vol coil + trend --------------------------------------------
S.append(mk("S-70", "1h low-vol coil + trend", "H1VolState",
  [("apct", "h1_atr_pct_24"), ("close_sig", "close"), ("ema_sig", "ema_24")],
  ["h1_atr_pct_24"], ["h1_atr_pct_24"],
  nancheck("apct") + nancheck("close_sig") + nancheck("ema_sig"),
  ("            prev = self.apct[j-1] if j >= 1 else np.nan\n"
   "            if self.apct[j] < self.k_in and self.close_sig[j] > self.ema_sig[j] and "
   "(not np.isfinite(prev) or prev >= self.k_in):\n"
   "                self.state = 1\n"),
  "(self.apct[j] > self.k_exit) or (self.close_sig[j] <= self.ema_sig[j])",
  "h1vol", params=[("k_in", 0.008), ("k_exit", 0.015)]))

# --- S-71 Aroon-Down + Stochastic confluence ---------------------------------
S.append(mk("S-71", "Aroon-Down + Stochastic confluence", "AroonStochState",
  [("ad", "aroon_down_24"), ("k", "stoch_k_24"), ("close_sig", "close"), ("ema_sig", "ema_24")],
  ["aroon_down_24", "stoch_k_24"], ["aroon_down_24", "stoch_k_24"],
  nancheck("ad") + nancheck("k") + nancheck("close_sig") + nancheck("ema_sig") + jguard("ad", "k"),
  ("            prev_ok = (self.ad[j-1] < self.k_in and self.k[j-1] > self.d_in and self.close_sig[j-1] > self.ema_sig[j-1]) if j >= 1 else False\n"
   "            if self.ad[j] < self.k_in and self.k[j] > self.d_in and self.close_sig[j] > self.ema_sig[j] and not prev_ok:\n"
   "                self.state = 1\n"),
  "(self.ad[j] > self.k_exit) or (self.k[j] < self.d_exit)",
  "aroonstoch", params=[("k_in", 30.0), ("k_exit", 70.0), ("d_in", 25.0), ("d_exit", 15.0)]))

# --- S-72 ROC + volume confluence --------------------------------------------
S.append(mk("S-72", "ROC + volume confluence", "RocVolState",
  [("r", "roc_24"), ("volr", "vol_rel_24")],
  ["roc_24", "vol_rel_24"], ["roc_24", "vol_rel_24"],
  nancheck("r") + nancheck("volr"),
  ("            prev = self.r[j-1] if j >= 1 else np.nan\n"
   "            if self.r[j] > self.k_in and self.volr[j] > self.vmin and "
   "(not np.isfinite(prev) or prev <= self.k_in):\n"
   "                self.state = 1\n"),
  "(self.r[j] < self.k_exit) or (self.volr[j] < self.vexit)",
  "rocvol", params=[("k_in", 0.004), ("k_exit", 0.0), ("vmin", 1.0), ("vexit", 0.8)]))


FILES = {
  "S-58": "strategy/strategy_roc_lib.py",
  "S-59": "strategy/strategy_stochkd_lib.py",
  "S-60": "strategy/strategy_aroondn_lib.py",
  "S-61": "strategy/strategy_momsign_lib.py",
  "S-62": "strategy/strategy_hvup_lib.py",
  "S-63": "strategy/strategy_bbupper_lib.py",
  "S-64": "strategy/strategy_dcupper_lib.py",
  "S-65": "strategy/strategy_lowwick_lib.py",
  "S-66": "strategy/strategy_volbb_lib.py",
  "S-67": "strategy/strategy_h1adxst_lib.py",
  "S-68": "strategy/strategy_dualst_lib.py",
  "S-69": "strategy/strategy_stok_lib.py",
  "S-70": "strategy/strategy_h1vol_lib.py",
  "S-71": "strategy/strategy_aroondnstoch_lib.py",
  "S-72": "strategy/strategy_rocvol_lib.py",
}


def main() -> None:
    for s in S:
        out = ROOT / FILES[s["sid"]]
        out.write_text(build(**s))
        print("wrote", out.name, s["sid"])


if __name__ == "__main__":
    main()
