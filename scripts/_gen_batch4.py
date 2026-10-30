"""One-shot generator for the S-43..S-57 signal libs (batch 4).

Reuses the SAME template, helpers, and ``build()`` as :mod:`_gen_batch3`
(the S-28..S-42 generator); only the strategy specs and the FILES map differ.
Each strategy is a stateful SignalRule with a ``run``/``run_*`` surface, the
optional ``ema_gate`` improvement knob, and (for most) a ``k_in``/``k_exit``
hysteresis pair that the 8-variant sweep tunes.

All 15 use feature columns that no earlier strategy (S-01..S-42) traded as the
primary signal — new families: Directional-Index spread, dual-SMA /
MACD-signal trend, ATR-% regime, ATR-normalised distance-to-prior-high,
fast/slow ATR ratio, Keltner lower-band / Bollinger-midline bounce, candle
wick / close-location structure, fast MACD histogram, and the 5m-only 1h
context block (``h1_*`` two-scale regimes).

Run:  venv/bin/python scripts/_gen_batch4.py
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

# Helper for strategies whose entry/exit read a *previous* bar (j-1).
JGUARD = ("        if j >= 1:\n"
          "            if not (np.isfinite(self.{a}[j-1]) and np.isfinite(self.{b}[j-1])):\n"
          "                return self.state\n")


def jguard(*names: str) -> str:
    return JGUARD.format(a=names[0], b=names[1] if len(names) > 1 else names[0])


def mk(sid, title, cls, arrs, feat, nn, cond, entry, exitc, load, params=None, doc="", clsdoc=""):
    return dict(sid=sid, title=title, doc=doc, cls=cls, clsdoc=clsdoc, arrays=arrs,
                featurecols=feat, notnullcols=nn, condcheck=cond, entry=entry,
                exitc=exitc, loadname=load, params=params or [])


S = []

# --- S-43 Directional-Index spread turn -------------------------------------
S.append(mk("S-43", "Directional-Index spread turn", "DiSpreadState",
  [("pdi", "plus_di_24"), ("mdi", "minus_di_24")],
  ["plus_di_24", "minus_di_24"], ["plus_di_24", "minus_di_24"],
  nancheck("pdi") + nancheck("mdi") + jguard("pdi", "mdi"),
  ("            prev_spread = (self.pdi[j-1] - self.mdi[j-1]) if j >= 1 else np.nan\n"
   "            if (self.pdi[j] - self.mdi[j]) > self.k_in and "
   "(not np.isfinite(prev_spread) or (self.pdi[j-1] - self.mdi[j-1]) <= self.k_in):\n"
   "                self.state = 1\n"),
  "(self.pdi[j] - self.mdi[j]) < -self.k_exit",
  "dispread", params=[("k_in", 3.0), ("k_exit", 1.0)]))

# --- S-44 dual-SMA trend follower -------------------------------------------
S.append(mk("S-44", "Dual-SMA trend follower", "DualSmaState",
  [("close_sig", "close"), ("fast", "sma_24"), ("slow", "sma_60")],
  ["sma_24", "sma_60"], ["sma_24", "sma_60"],
  nancheck("close_sig") + nancheck("fast") + nancheck("slow") + jguard("fast", "slow"),
  ("            prev_ok = (self.close_sig[j-1] > self.fast[j-1] and self.fast[j-1] > self.slow[j-1]) if j >= 1 else False\n"
   "            if self.close_sig[j] > self.fast[j] and self.fast[j] > self.slow[j] and not prev_ok:\n"
   "                self.state = 1\n"),
  "self.close_sig[j] < self.slow[j]",
  "dualsma"))

# --- S-45 MACD / signal-line cross ------------------------------------------
S.append(mk("S-45", "MACD signal-line cross", "MacdSigState",
  [("macd", "macd_12_60"), ("sig", "macd_signal_12_60")],
  ["macd_12_60", "macd_signal_12_60"], ["macd_12_60", "macd_signal_12_60"],
  nancheck("macd") + nancheck("sig") + jguard("macd", "sig"),
  ("            prev_ok = (self.macd[j-1] > self.sig[j-1]) if j >= 1 else False\n"
   "            if self.macd[j] > self.sig[j] and not prev_ok:\n"
   "                self.state = 1\n"),
  "self.macd[j] < self.sig[j]",
  "macdsig"))

# --- S-46 ATR-% low-volatility trend ----------------------------------------
S.append(mk("S-46", "ATR-% low-volatility trend", "AtrPctState",
  [("apct", "atr_pct_24"), ("close_sig", "close"), ("ema_sig", "ema_24")],
  ["atr_pct_24"], ["atr_pct_24"],
  nancheck("apct") + nancheck("close_sig") + nancheck("ema_sig"),
  ("            prev = self.apct[j-1] if j >= 1 else np.nan\n"
   "            if self.apct[j] < self.k_in and self.close_sig[j] > self.ema_sig[j] and "
   "(not np.isfinite(prev) or prev >= self.k_in):\n"
   "                self.state = 1\n"),
  "self.apct[j] > self.k_exit",
  "atrpct", params=[("k_in", 0.0025), ("k_exit", 0.0045)]))

# --- S-47 ATR-distance-to-prior-high "room to run" ---------------------------
S.append(mk("S-47", "Distance-to-prior-high room", "DistHighState",
  [("dh", "dist_high_24")],
  ["dist_high_24"], ["dist_high_24"],
  nancheck("dh"),
  ("            prev = self.dh[j-1] if j >= 1 else np.nan\n"
   "            if self.dh[j] > self.k_in and (not np.isfinite(prev) or prev <= self.k_in):\n"
   "                self.state = 1\n"),
  "self.dh[j] < self.k_exit",
  "disthigh", params=[("k_in", 1.5), ("k_exit", 0.5)]))

# --- S-48 fast/slow ATR ratio expansion -------------------------------------
S.append(mk("S-48", "ATR vol-ratio expansion", "VolRatioState",
  [("vr", "vol_ratio_12_60")],
  ["vol_ratio_12_60"], ["vol_ratio_12_60"],
  nancheck("vr"),
  ("            prev = self.vr[j-1] if j >= 1 else np.nan\n"
   "            if self.vr[j] > self.k_in and (not np.isfinite(prev) or prev <= self.k_in):\n"
   "                self.state = 1\n"),
  "self.vr[j] < self.k_exit",
  "volratio", params=[("k_in", 1.05), ("k_exit", 0.85)]))

# --- S-49 Keltner lower-band bounce -----------------------------------------
S.append(mk("S-49", "Keltner lower-band bounce", "KcLowerState",
  [("close_sig", "close"), ("lo", "kc_lower_24"), ("mid", "kc_mid_24")],
  ["kc_lower_24", "kc_mid_24"], ["kc_lower_24", "kc_mid_24"],
  nancheck("close_sig") + nancheck("lo") + nancheck("mid") + jguard("close_sig", "lo"),
  ("            prev_ok = (self.close_sig[j-1] > self.lo[j-1]) if j >= 1 else False\n"
   "            if self.close_sig[j] > self.lo[j] and not prev_ok:\n"
   "                self.state = 1\n"),
  "self.close_sig[j] < self.mid[j]",
  "kclower"))

# --- S-50 Bollinger midline pullback ----------------------------------------
S.append(mk("S-50", "Bollinger midline pullback", "BbMidState",
  [("close_sig", "close"), ("mid", "bb_mid_24"), ("lo", "bb_lower_24")],
  ["bb_mid_24", "bb_lower_24"], ["bb_mid_24", "bb_lower_24"],
  nancheck("close_sig") + nancheck("mid") + nancheck("lo") + jguard("close_sig", "mid"),
  ("            prev_ok = (self.close_sig[j-1] > self.mid[j-1]) if j >= 1 else False\n"
   "            if self.close_sig[j] > self.mid[j] and self.close_sig[j] > self.lo[j] and not prev_ok:\n"
   "                self.state = 1\n"),
  "self.close_sig[j] < self.lo[j]",
  "bbmid"))

# --- S-51 low upper-wick strong close ---------------------------------------
S.append(mk("S-51", "Low upper-wick strong close", "UpWickState",
  [("uw", "bar_upper_wick_ratio")],
  ["bar_upper_wick_ratio"], ["bar_upper_wick_ratio"],
  nancheck("uw"),
  ("            prev = self.uw[j-1] if j >= 1 else np.nan\n"
   "            if self.uw[j] < self.k_in and (not np.isfinite(prev) or prev >= self.k_in):\n"
   "                self.state = 1\n"),
  "self.uw[j] > self.k_exit",
  "upwick", params=[("k_in", 0.15), ("k_exit", 0.45)]))

# --- S-52 close-location (CLV) turn -----------------------------------------
S.append(mk("S-52", "Close-location (CLV) turn", "ClvState",
  [("clv", "bar_clv")],
  ["bar_clv"], ["bar_clv"],
  nancheck("clv"),
  ("            prev = self.clv[j-1] if j >= 1 else np.nan\n"
   "            if self.clv[j] > self.k_in and (not np.isfinite(prev) or prev <= self.k_in):\n"
   "                self.state = 1\n"),
  "self.clv[j] < self.k_exit",
  "clv", params=[("k_in", 0.3), ("k_exit", -0.1)]))

# --- S-53 fast MACD histogram turn ------------------------------------------
S.append(mk("S-53", "Fast MACD histogram turn", "MacdHist6State",
  [("h", "macd_hist_atr_6_24")],
  ["macd_hist_atr_6_24"], ["macd_hist_atr_6_24"],
  nancheck("h"),
  ("            prev = self.h[j-1] if j >= 1 else np.nan\n"
   "            if self.h[j] > self.k_in and (not np.isfinite(prev) or prev <= self.k_in):\n"
   "                self.state = 1\n"),
  "self.h[j] < self.k_exit",
  "macdhist6", params=[("k_in", 0.0), ("k_exit", -0.05)]))

# --- S-54 1h ADX trend regime (two-scale) -----------------------------------
S.append(mk("S-54", "1h ADX trend regime", "H1AdxState",
  [("a", "h1_adx_24"), ("close_sig", "close"), ("ema_sig", "ema_24")],
  ["h1_adx_24"], ["h1_adx_24"],
  nancheck("a") + nancheck("close_sig") + nancheck("ema_sig"),
  ("            prev = self.a[j-1] if j >= 1 else np.nan\n"
   "            if self.a[j] > self.k_in and self.close_sig[j] > self.ema_sig[j] and "
   "(not np.isfinite(prev) or prev <= self.k_in):\n"
   "                self.state = 1\n"),
  "self.a[j] < self.k_exit",
  "h1adx", params=[("k_in", 25.0), ("k_exit", 20.0)]))

# --- S-55 1h RSI momentum (two-scale) ---------------------------------------
S.append(mk("S-55", "1h RSI momentum", "H1RsiState",
  [("r", "h1_rsi_24")],
  ["h1_rsi_24"], ["h1_rsi_24"],
  nancheck("r"),
  ("            prev = self.r[j-1] if j >= 1 else np.nan\n"
   "            if self.r[j] > self.k_in and (not np.isfinite(prev) or prev <= self.k_in):\n"
   "                self.state = 1\n"),
  "self.r[j] < self.k_exit",
  "h1rsi", params=[("k_in", 55.0), ("k_exit", 45.0)]))

# --- S-56 1h efficiency-ratio regime (two-scale) ----------------------------
S.append(mk("S-56", "1h efficiency-ratio regime", "H1ErState",
  [("e", "h1_er_24")],
  ["h1_er_24"], ["h1_er_24"],
  nancheck("e"),
  ("            prev = self.e[j-1] if j >= 1 else np.nan\n"
   "            if self.e[j] > self.k_in and (not np.isfinite(prev) or prev <= self.k_in):\n"
   "                self.state = 1\n"),
  "self.e[j] < self.k_exit",
  "h1er", params=[("k_in", 0.35), ("k_exit", 0.2)]))

# --- S-57 1h EMA-distance pullback (two-scale) ------------------------------
S.append(mk("S-57", "1h EMA-distance pullback", "H1EdistState",
  [("ed", "h1_ema_dist_24")],
  ["h1_ema_dist_24"], ["h1_ema_dist_24"],
  nancheck("ed"),
  ("            prev = self.ed[j-1] if j >= 1 else np.nan\n"
   "            in_band = self.ed[j] > 0 and self.ed[j] < self.k_in\n"
   "            prev_in = (0 < self.ed[j-1] < self.k_in) if j >= 1 else False\n"
   "            if in_band and not prev_in:\n"
   "                self.state = 1\n"),
  "self.ed[j] < -self.k_exit",
  "h1edist", params=[("k_in", 2.0), ("k_exit", 1.0)]))


FILES = {
  "S-43": "strategy/strategy_dispread_lib.py",
  "S-44": "strategy/strategy_dualsma_lib.py",
  "S-45": "strategy/strategy_macdsig_lib.py",
  "S-46": "strategy/strategy_atrpct_lib.py",
  "S-47": "strategy/strategy_disthigh_lib.py",
  "S-48": "strategy/strategy_volratio_lib.py",
  "S-49": "strategy/strategy_kclower_lib.py",
  "S-50": "strategy/strategy_bbmid_lib.py",
  "S-51": "strategy/strategy_upwick_lib.py",
  "S-52": "strategy/strategy_clv_lib.py",
  "S-53": "strategy/strategy_macdhist6_lib.py",
  "S-54": "strategy/strategy_h1adx_lib.py",
  "S-55": "strategy/strategy_h1rsi_lib.py",
  "S-56": "strategy/strategy_h1er_lib.py",
  "S-57": "strategy/strategy_h1edist_lib.py",
}


def main() -> None:
    for s in S:
        out = ROOT / FILES[s["sid"]]
        out.write_text(build(**s))
        print("wrote", out.name, s["sid"])


if __name__ == "__main__":
    main()
