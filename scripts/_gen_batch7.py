"""One-shot generator for the S-88..S-102 signal libs (batch 7).

Reuses the SAME template, helpers, and ``build()`` as :mod:`_gen_batch3`
(via importlib); only the strategy specs and the FILES map differ. Each
strategy is a stateful SignalRule with a ``run``/``run_*`` surface, the
optional ``ema_gate`` improvement knob, and a ``k_in``/``k_exit`` hysteresis
pair that the 8-variant sweep tunes.

All 15 use feature columns / families that no earlier strategy (S-01..S-87)
traded as the primary signal — new families this batch: fast (6/12-bar)
oscillators (rsi_12 S-88, aroon_12 spread S-89, macd_hist_6_24 S-90,
stoch_d_12 S-91, mfi_12 S-92, willr_12 S-93, er_12 S-94), slow volatility
regimes (hv_120 S-95, bb_width_60 S-96), multi-oscillator confluence
(rs12+sk12+mfi12 S-97, rsi12+willr12+stochd12+mfi12 S-98), fast ROC +
vol-ratio breakout (S-99), fast MACD signal cross (S-100), slow-ROC-120 +
EMA-120 confluence (S-101), and slow Donchian-position-12 regime (S-102).

Run:  venv/bin/python scripts/_gen_batch7.py
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

# --- S-88 fast RSI-12 rebound ------------------------------------------------
S.append(mk("S-88", "Fast RSI-12 rebound", "Rsi12State",
  [("r", "rsi_12")],
  ["rsi_12"], ["rsi_12"],
  nancheck("r"),
  fresh_cross("r", "self.r[j] > self.k_in", "prev <= self.k_in"),
  "self.r[j] < self.k_exit",
  "rsi12", params=[("k_in", 55.0), ("k_exit", 40.0)]))

# --- S-89 Aroon-12 spread (up - down) -----------------------------------------
S.append(mk("S-89", "Aroon-12 spread", "Aroon12SpreadState",
  [("au", "aroon_up_12"), ("ad", "aroon_down_12")],
  ["aroon_up_12", "aroon_down_12"], ["aroon_up_12", "aroon_down_12"],
  nancheck("au") + nancheck("ad") + jguard("au", "ad"),
  ("            prev_spread = self.au[j-1] - self.ad[j-1] if j >= 1 else np.nan\n"
   "            spread = self.au[j] - self.ad[j]\n"
   "            if spread > self.k_in and (not np.isfinite(prev_spread) or prev_spread <= self.k_in):\n"
   "                self.state = 1\n"),
  "(self.au[j] - self.ad[j]) < self.k_exit",
  "aroon12spread", params=[("k_in", 30.0), ("k_exit", 5.0)]))

# --- S-90 fast MACD histogram (6/24) ------------------------------------------
S.append(mk("S-90", "Fast MACD hist (6/24)", "MacdHist624State",
  [("h", "macd_hist_6_24"), ("close_sig", "close"), ("ema_sig", "ema_24")],
  ["macd_hist_6_24"], ["macd_hist_6_24"],
  nancheck("h") + nancheck("close_sig") + nancheck("ema_sig"),
  fresh_cross("h", "self.h[j] > 0.0 and self.close_sig[j] > self.ema_sig[j]", "prev <= 0.0"),
  "self.h[j] < 0.0",
  "macdh624"))

# --- S-91 fast Stochastic-D turn ----------------------------------------------
S.append(mk("S-91", "Fast Stochastic-D turn", "StochD12State",
  [("d", "stoch_d_12")],
  ["stoch_d_12"], ["stoch_d_12"],
  nancheck("d"),
  fresh_cross("d", "self.d[j] > self.k_in", "prev <= self.k_in"),
  "self.d[j] < self.k_exit",
  "stochd12", params=[("k_in", 55.0), ("k_exit", 40.0)]))

# --- S-92 fast MFI-12 accumulation --------------------------------------------
S.append(mk("S-92", "Fast MFI-12 accumulation", "Mfi12State",
  [("m", "mfi_12")],
  ["mfi_12"], ["mfi_12"],
  nancheck("m"),
  fresh_cross("m", "self.m[j] > self.k_in", "prev <= self.k_in"),
  "self.m[j] < self.k_exit",
  "mfi12", params=[("k_in", 60.0), ("k_exit", 45.0)]))

# --- S-93 fast Williams-%R rebound ---------------------------------------------
S.append(mk("S-93", "Fast Williams-%R rebound", "Willr12State",
  [("w", "willr_12")],
  ["willr_12"], ["willr_12"],
  nancheck("w"),
  ("            prev = self.w[j-1] if j >= 1 else np.nan\n"
   "            if self.w[j] > self.k_in and (not np.isfinite(prev) or prev <= self.k_in):\n"
   "                self.state = 1\n"),
  "self.w[j] < self.k_exit",
  "willr12", params=[("k_in", -60.0), ("k_exit", -80.0)]))

# --- S-94 fast Efficiency-Ratio regime ------------------------------------------
S.append(mk("S-94", "Fast Efficiency-Ratio regime", "Er12State",
  [("e", "er_12")],
  ["er_12"], ["er_12"],
  nancheck("e"),
  fresh_cross("e", "self.e[j] > self.k_in", "prev <= self.k_in"),
  "self.e[j] < self.k_exit",
  "er12", params=[("k_in", 0.4), ("k_exit", 0.2)]))

# --- S-95 slow-HV-120 low-vol regime -------------------------------------------
S.append(mk("S-95", "Slow-HV-120 low-vol regime", "Hv120State",
  [("hv", "hv_120")],
  ["hv_120"], ["hv_120"],
  nancheck("hv"),
  fresh_cross("hv", "self.hv[j] < self.k_in", "prev >= self.k_in"),
  "self.hv[j] > self.k_exit",
  "hv120", params=[("k_in", 0.001), ("k_exit", 0.003)]))

# --- S-96 Bollinger-Width-60 squeeze-then-release --------------------------------
# Entry when width crosses ABOVE k_in (squeeze ending -> expansion starting).
# Exit when width re-collapses below k_exit (squeeze re-forming).
S.append(mk("S-96", "BB-Width-60 squeeze-then-release", "BbW60State",
  [("w", "bb_width_60")],
  ["bb_width_60"], ["bb_width_60"],
  nancheck("w"),
  fresh_cross("w", "self.w[j] > self.k_in", "prev <= self.k_in"),
  "self.w[j] < self.k_exit",
  "bbw60", params=[("k_in", 0.004), ("k_exit", 0.0015)]))

# --- S-97 triple-oscillator confluence (rsi12+stochk12+mfi12) ---------------------
S.append(mk("S-97", "Triple-oscillator confluence", "TriOscState",
  [("r", "rsi_12"), ("k", "stoch_k_12"), ("m", "mfi_12")],
  ["rsi_12", "stoch_k_12", "mfi_12"], ["rsi_12", "stoch_k_12", "mfi_12"],
  nancheck("r") + nancheck("k") + nancheck("m"),
  ("            prev_ok = (self.r[j-1] > self.r_in and self.k[j-1] > self.k_in and self.m[j-1] > self.m_in) if j >= 1 else False\n"
   "            if self.r[j] > self.r_in and self.k[j] > self.k_in and self.m[j] > self.m_in and not prev_ok:\n"
   "                self.state = 1\n"),
  "(self.r[j] < self.r_exit) or (self.k[j] < self.k_exit) or (self.m[j] < self.m_exit)",
  "triosc",
  params=[("r_in", 55.0), ("r_exit", 45.0),
          ("k_in", 55.0), ("k_exit", 45.0),
          ("m_in", 55.0), ("m_exit", 45.0)]))

# --- S-98 quad-oscillator confluence (rsi12+willr12+stochd12+mfi12) ----------------
S.append(mk("S-98", "Quad-oscillator confluence", "QuadOscState",
  [("r", "rsi_12"), ("w", "willr_12"), ("d", "stoch_d_12"), ("m", "mfi_12")],
  ["rsi_12", "willr_12", "stoch_d_12", "mfi_12"],
  ["rsi_12", "willr_12", "stoch_d_12", "mfi_12"],
  nancheck("r") + nancheck("w") + nancheck("d") + nancheck("m"),
  ("            prev_ok = (self.r[j-1] > self.r_in and self.w[j-1] > self.w_in and self.d[j-1] > self.d_in and self.m[j-1] > self.m_in) if j >= 1 else False\n"
   "            if self.r[j] > self.r_in and self.w[j] > self.w_in and self.d[j] > self.d_in and self.m[j] > self.m_in and not prev_ok:\n"
   "                self.state = 1\n"),
  ("(self.r[j] < self.r_exit) or (self.w[j] < self.w_exit) or "
   "(self.d[j] < self.d_exit) or (self.m[j] < self.m_exit)"),
  "quadosc",
  params=[("r_in", 55.0), ("r_exit", 45.0),
          ("w_in", -60.0), ("w_exit", -80.0),
          ("d_in", 55.0), ("d_exit", 45.0),
          ("m_in", 55.0), ("m_exit", 45.0)]))

# --- S-99 fast ROC breakout + volume-ratio confluence ------------------------------
S.append(mk("S-99", "Fast-ROC + vol-ratio breakout", "Roc6VolrState",
  [("r", "roc_6"), ("vr", "vol_ratio_6_24"), ("close_sig", "close"), ("ema_sig", "ema_24")],
  ["roc_6", "vol_ratio_6_24"], ["roc_6", "vol_ratio_6_24"],
  nancheck("r") + nancheck("vr") + nancheck("close_sig") + nancheck("ema_sig"),
  ("            prev = self.r[j-1] if j >= 1 else np.nan\n"
   "            if self.r[j] > self.k_in and self.vr[j] > self.vmin and self.close_sig[j] > self.ema_sig[j] and "
   "(not np.isfinite(prev) or prev <= self.k_in):\n"
   "                self.state = 1\n"),
  "(self.r[j] < self.k_exit) or (self.vr[j] < self.vexit) or (self.close_sig[j] <= self.ema_sig[j])",
  "roc6volr",
  params=[("k_in", 0.005), ("k_exit", 0.0), ("vmin", 1.0), ("vexit", 0.8)]))

# --- S-100 fast MACD signal cross (6/24) ---------------------------------------------
S.append(mk("S-100", "Fast MACD signal cross (6/24)", "MacdCross624State",
  [("m", "macd_6_24"), ("s", "macd_signal_6_24")],
  ["macd_6_24", "macd_signal_6_24"], ["macd_6_24", "macd_signal_6_24"],
  nancheck("m") + nancheck("s") + jguard("m", "s"),
  ("            prev_ok = (self.m[j-1] > self.s[j-1]) if j >= 1 else False\n"
   "            if self.m[j] > self.s[j] and not prev_ok:\n"
   "                self.state = 1\n"),
  "self.m[j] <= self.s[j]",
  "macdcross624"))

# --- S-101 slow-ROC-120 + close>EMA-120 confluence ------------------------------------
# Entry when 120-bar ROC turns positive AND price is above its 120-bar EMA
# (slow trend confirmation). Exit when either the ROC flips negative or price
# falls back below the 120-bar EMA.
S.append(mk("S-101", "Slow-ROC-120 + EMA-120 confluence", "Roc120Ema120State",
  [("r", "roc_120"), ("close_sig", "close"), ("ema120", "ema_120")],
  ["roc_120", "ema_120"], ["roc_120", "ema_120"],
  nancheck("r") + nancheck("close_sig") + nancheck("ema120"),
  ("            prev = self.r[j-1] if j >= 1 else np.nan\n"
   "            if self.r[j] > self.k_in and self.close_sig[j] > self.ema120[j] and "
   "(not np.isfinite(prev) or prev <= self.k_in):\n"
   "                self.state = 1\n"),
  "(self.r[j] < self.k_exit) or (self.close_sig[j] <= self.ema120[j])",
  "roc120ema120",
  params=[("k_in", 0.02), ("k_exit", 0.0)]))

# --- S-102 slow Donchian-Pos-12 regime ----------------------------------------------
S.append(mk("S-102", "Slow Donchian-Pos-12 regime", "DcPos12State",
  [("p", "dc_pos_12")],
  ["dc_pos_12"], ["dc_pos_12"],
  nancheck("p"),
  fresh_cross("p", "self.p[j] > self.k_in", "prev <= self.k_in"),
  "self.p[j] < self.k_exit",
  "dcpos12", params=[("k_in", 0.7), ("k_exit", 0.4)]))


FILES = {
  "S-88":  "strategy/strategy_rsi12_lib.py",
  "S-89":  "strategy/strategy_aroon12spread_lib.py",
  "S-90":  "strategy/strategy_macdh624_lib.py",
  "S-91":  "strategy/strategy_stochd12_lib.py",
  "S-92":  "strategy/strategy_mfi12_lib.py",
  "S-93":  "strategy/strategy_willr12_lib.py",
  "S-94":  "strategy/strategy_er12_lib.py",
  "S-95":  "strategy/strategy_hv120_lib.py",
  "S-96":  "strategy/strategy_bbw60_lib.py",
  "S-97":  "strategy/strategy_triosc_lib.py",
  "S-98":  "strategy/strategy_quadosc_lib.py",
  "S-99":  "strategy/strategy_roc6volr_lib.py",
  "S-100": "strategy/strategy_macdcross624_lib.py",
  "S-101": "strategy/strategy_roc120ema120_lib.py",
  "S-102": "strategy/strategy_dcpos12_lib.py",
}


def main() -> None:
    assert len(S) == 15, f"expected 15 strategies, got {len(S)}"
    seen = [s["sid"] for s in S]
    assert len(set(seen)) == 15, f"duplicate sids: {seen}"
    for s in S:
        assert s["sid"] in FILES, f"missing FILES entry for {s['sid']}"
        out = ROOT / FILES[s["sid"]]
        out.write_text(build(**s))
        print("wrote", out.name, s["sid"])


if __name__ == "__main__":
    main()
