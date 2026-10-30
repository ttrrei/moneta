"""6-iteration improvement harness for S-08 .. S-27.

For each of the new strategies, evaluate 6 improvement *iterations* (variants)
over the in-sample matrix: 3 instruments (EUR_USD / BTC_USD / XAU_USD) x 2
windows (full, last_12m) x 3 cost tiers (0 / 2 / 5 bps) = 18 cells.

All variants run on **in-sample data only** (``until <= 2025-07-31``) — no
OOS holdout is touched (the holdout is a one-shot gate reserved for the single
finalist under ``config/strategies.yml → oos.pass_criteria``).

Each row of the CSV records one cell:
  strategy, variant, instrument, window, cost_bps,
  n_trades, trades_per_year, total_return_pct, buyhold_return_pct,
  win_rate_pct, sharpe_weekly, max_drawdown_pct, exposure_pct.

Run from the repo root::

    venv/bin/python scripts/strategy_variants.py --workers 6
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

INSTRUMENTS = ["EUR_USD", "BTC_USD", "XAU_USD"]
COST_TIERS = [0.0, 2.0, 5.0]
WINDOWS = {
    "full": {"since": None, "until": "2025-07-31"},
    "last_12m": {"since": "2024-08-01", "until": "2025-07-31"},
}
PARQUET_5M = "data/ohlcv_5m_features/ohlcv_5m_features.parquet"
PARQUET_1H = "data/ohlcv_1h_features/ohlcv_1h_features.parquet"

STRATEGIES = {
    "s08": "strategy_cci_reversion_lib",
    "s09": "strategy_willr_lib",
    "s10": "strategy_stoch_lib",
    "s11": "strategy_macd_lib",
    "s12": "strategy_dual_velocity_lib",
    "s13": "strategy_psar_lib",
    "s14": "strategy_donchian_lib",
    "s15": "strategy_aroon_lib",
    "s16": "strategy_mfi_lib",
    "s17": "strategy_rsi_slow_lib",
    # batch 2
    "s18": "strategy_vwap_stretch_lib",
    "s19": "strategy_cmf_lib",
    "s20": "strategy_multiscale_lib",
    "s21": "strategy_squeeze_slow_lib",
    "s22": "strategy_er_lib",
    "s23": "strategy_macd_slow_lib",
    "s24": "strategy_atr_band_lib",
    "s25": "strategy_chop_lib",
    "s26": "strategy_spread_lib",
    "s27": "strategy_volmom_lib",
    # batch 3 (S-28 .. S-40) — 15 new strategies, 8 improvement iterations each
    "s28": "strategy_candle_lib",
    "s29": "strategy_volconverge_lib",
    "s30": "strategy_atrbandpct_lib",
    "s31": "strategy_stdist_lib",
    "s32": "strategy_psardist_lib",
    "s33": "strategy_kcbreak_lib",
    "s34": "strategy_bb_pctb_lib",
    "s35": "strategy_bb_width_lib",
    "s36": "strategy_dcpos_lib",
    "s37": "strategy_dcmid_lib",
    "s38": "strategy_distlow_lib",
    "s39": "strategy_dcwidth_lib",
    "s40": "strategy_stdist_hyst_lib",
    "s41": "strategy_hvconverge_lib",
    "s42": "strategy_barbody_lib",
    "s43": "strategy_dispread_lib",
    "s44": "strategy_dualsma_lib",
    "s45": "strategy_macdsig_lib",
    "s46": "strategy_atrpct_lib",
    "s47": "strategy_disthigh_lib",
    "s48": "strategy_volratio_lib",
    "s49": "strategy_kclower_lib",
    "s50": "strategy_bbmid_lib",
    "s51": "strategy_upwick_lib",
    "s52": "strategy_clv_lib",
    "s53": "strategy_macdhist6_lib",
    "s54": "strategy_h1adx_lib",
    "s55": "strategy_h1rsi_lib",
    "s56": "strategy_h1er_lib",
    "s57": "strategy_h1edist_lib",
    "s58": "strategy_roc_lib",
    "s59": "strategy_stochkd_lib",
    "s60": "strategy_aroondn_lib",
    "s61": "strategy_momsign_lib",
    "s62": "strategy_hvup_lib",
    "s63": "strategy_bbupper_lib",
    "s64": "strategy_dcupper_lib",
    "s65": "strategy_lowwick_lib",
    "s66": "strategy_volbb_lib",
    "s67": "strategy_h1adxst_lib",
    "s68": "strategy_dualst_lib",
    "s69": "strategy_stok_lib",
    "s70": "strategy_h1vol_lib",
    "s71": "strategy_aroondnstoch_lib",
    "s72": "strategy_rocvol_lib",
    "s73": "strategy_aroonup60_lib",
    "s74": "strategy_willr60_lib",
    "s75": "strategy_cci120_lib",
    "s76": "strategy_stochk60_lib",
    "s77": "strategy_mfi60_lib",
    "s78": "strategy_atrpct120_lib",
    "s79": "strategy_roc120_lib",
    "s80": "strategy_hoursin_lib",
    "s81": "strategy_dowsin_lib",
    "s82": "strategy_trcollapse_lib",
    "s83": "strategy_psar002_lib",
    "s84": "strategy_stdual120_lib",
    "s85": "strategy_h1st120_lib",
    "s86": "strategy_timeconf_lib",
    "s87": "strategy_roc120vol_lib",
    "s88": "strategy_rsi12_lib",
    "s89": "strategy_aroon12spread_lib",
    "s90": "strategy_macdh624_lib",
    "s91": "strategy_stochd12_lib",
    "s92": "strategy_mfi12_lib",
    "s93": "strategy_willr12_lib",
    "s94": "strategy_er12_lib",
    "s95": "strategy_hv120_lib",
    "s96": "strategy_bbw60_lib",
    "s97": "strategy_triosc_lib",
    "s98": "strategy_quadosc_lib",
    "s99": "strategy_roc6volr_lib",
    "s100": "strategy_macdcross624_lib",
    "s101": "strategy_roc120ema120_lib",
    "s102": "strategy_dcpos12_lib",
}

#: Per-strategy list of (variant_name, kwargs) — the 6 improvement iterations.
VARIANTS: dict[str, list[tuple[str, dict]]] = {
    "s08": [
        ("base", {}),
        ("ema_gate", {"ema_gate": True}),
        ("slower", {"enter_below": 150.0, "exit_above": 250.0}),
        ("1h", {"timeframe": "1h"}),
        ("entry_guard", {"entry_guard": True}),
        ("band_wide", {"enter_below": 200.0, "exit_above": 300.0}),
    ],
    "s09": [
        ("base", {}),
        ("ema_gate", {"ema_gate": True}),
        ("slower", {"enter_below": -85.0, "exit_above": -30.0}),
        ("1h", {"timeframe": "1h"}),
        ("entry_guard", {"entry_guard": True}),
        ("cooldown_24", {"cooldown": 24}),
    ],
    "s10": [
        ("base", {}),
        ("ema_gate", {"ema_gate": True}),
        ("slower", {"k_below": 20.0}),
        ("1h", {"timeframe": "1h"}),
        ("entry_guard", {"entry_guard": True}),
        ("band_wide", {"k_below": 40.0}),
    ],
    "s11": [
        ("base", {}),
        ("ema_gate", {"ema_gate": True}),
        ("atr_strict", {"atr_min": 0.15}),
        ("1h", {"timeframe": "1h"}),
        ("entry_guard", {"entry_guard": True}),
        ("atr_loose", {"atr_min": 0.02}),
    ],
    "s12": [
        ("base", {}),
        ("ema_gate", {"ema_gate": True}),
        ("slower_lag", {"slope_lag": 120}),
        ("1h", {"timeframe": "1h"}),
        ("entry_guard", {"entry_guard": True}),
        ("fast_lag", {"slope_lag": 6}),
    ],
    "s13": [
        ("base", {}),
        ("hysteresis", {"up_th": 0.9}),
        ("hysteresis_strict", {"up_th": 0.95}),
        ("1h", {"timeframe": "1h"}),
        ("entry_guard", {"entry_guard": True}),
        ("near_flat", {"up_th": 0.2}),
    ],
    "s14": [
        ("base", {}),
        ("hysteresis", {"th": 0.5}),
        ("hysteresis_strict", {"th": 0.8}),
        ("1h", {"timeframe": "1h"}),
        ("entry_guard", {"entry_guard": True}),
        ("band_tight", {"th": 0.2}),
    ],
    "s15": [
        ("base", {}),
        ("ema_gate", {"ema_gate": True}),
        ("slower", {"up_at": 85.0, "up_exit": 85.0, "down_below": 20.0}),
        ("1h", {"timeframe": "1h"}),
        ("entry_guard", {"entry_guard": True}),
        ("band_wide", {"up_at": 50.0, "up_exit": 50.0, "down_below": 50.0}),
    ],
    "s16": [
        ("base", {}),
        ("ema_gate", {"ema_gate": True}),
        ("slower", {"enter_below": 10.0, "exit_above": 60.0}),
        ("1h", {"timeframe": "1h"}),
        ("entry_guard", {"entry_guard": True}),
        ("band_wide", {"enter_below": 30.0, "exit_above": 70.0}),
    ],
    "s17": [
        ("base", {}),
        ("st_gate", {"st_gate": True}),
        ("adx_gate", {"adx_gate": True, "adx_at": 20.0}),
        ("both_gates", {"st_gate": True, "adx_gate": True, "adx_at": 20.0}),
        ("slower", {"enter_below": 20.0, "exit_above": 45.0}),
        ("entry_guard", {"entry_guard": True}),
    ],
    # ---- batch 2 (S-18 .. S-27) ----
    "s18": [
        ("base", {}),
        ("ema_gate", {"ema_gate": True}),
        ("looser", {"k": 0.5, "k_exit": 0.0}),
        ("tight_exit", {"k": 0.25, "k_exit": 0.1}),
        ("1h", {"timeframe": "1h"}),
        ("entry_guard", {"entry_guard": True}),
    ],
    "s19": [
        ("base", {}),
        ("ema_gate", {"ema_gate": True}),
        ("looser", {"k": 0.10}),
        ("tighter", {"k": 0.02}),
        ("1h", {"timeframe": "1h"}),
        ("entry_guard", {"entry_guard": True}),
    ],
    "s20": [
        ("base", {}),
        ("gate_120_3", {"gate_cols": ("st_dir_120_3",)}),
        ("dual_gate", {"gate_cols": ("st_dir_120_2", "st_dir_120_3")}),
        ("h1_align", {"gate_cols": ("st_dir_120_2", "h1_st_dir_120_3")}),
        ("1h", {"timeframe": "1h"}),
        ("entry_guard", {"entry_guard": True}),
    ],
    "s21": [
        ("base", {}),
        ("ema_gate", {"ema_gate": True}),
        ("onset_only", {"onset_only": True}),
        ("onset_ema", {"onset_only": True, "ema_gate": True}),
        ("1h", {"timeframe": "1h"}),
        ("entry_guard", {"entry_guard": True}),
    ],
    "s22": [
        ("base", {}),
        ("lower_k", {"k": 0.20}),
        ("higher_k", {"k": 0.40}),
        ("1h", {"timeframe": "1h"}),
        ("entry_guard", {"entry_guard": True}),
        ("slower", {"k": 0.50}),
    ],
    "s23": [
        ("base", {}),
        ("pos_th", {"th": 0.1, "th_exit": 0.0}),
        ("hysteresis", {"th": 0.0, "th_exit": -0.1}),
        ("1h", {"timeframe": "1h"}),
        ("entry_guard", {"entry_guard": True}),
        ("tight", {"th": 0.2, "th_exit": 0.0}),
    ],
    "s24": [
        ("base", {}),
        ("wider", {"k": 1.5, "k_exit": 0.75}),
        ("narrower", {"k": 0.5, "k_exit": 0.25}),
        ("1h", {"timeframe": "1h"}),
        ("entry_guard", {"entry_guard": True}),
        ("slower_exit", {"k": 1.0, "k_exit": 0.25}),
    ],
    "s25": [
        ("base", {}),
        ("chop_higher", {"chop_at": 65.0}),
        ("chop_lower", {"chop_at": 55.0}),
        ("wider_stretch", {"k": 1.5}),
        ("1h", {"timeframe": "1h"}),
        ("entry_guard", {"entry_guard": True}),
    ],
    "s26": [
        ("base", {}),
        ("wider", {"th": 1.0, "th_exit": 0.0}),
        ("narrower", {"th": 0.25, "th_exit": 0.0}),
        ("hysteresis", {"th": 0.5, "th_exit": 0.2}),
        ("1h", {"timeframe": "1h"}),
        ("entry_guard", {"entry_guard": True}),
    ],
    "s27": [
        ("base", {}),
        ("vol_stronger", {"vmin": 1.5}),
        ("vol_looser", {"vmin": 0.8}),
        ("1h", {"timeframe": "1h"}),
        ("entry_guard", {"entry_guard": True}),
        ("vol_2x", {"vmin": 2.0}),
    ],
    # ---- batch 3 (S-28 .. S-40), 8 improvement iterations each ----
    "s28": [
        ("base", {}),
        ("stricter", {"k_in": 0.6, "k_exit": 0.2}),
        ("looser", {"k_in": 0.2, "k_exit": 0.0}),
        ("ema_gate", {"ema_gate": True}),
        ("wide_exit", {"k_in": 0.4, "k_exit": -0.2}),
        ("1h", {"timeframe": "1h"}),
        ("entry_guard", {"entry_guard": True}),
        ("combo", {"k_in": 0.6, "k_exit": 0.2, "ema_gate": True}),
    ],
    "s29": [
        ("base", {}),
        ("tighter", {"vmin": 0.8, "vmax": 1.2}),
        ("looser", {"vmin": 1.3, "vmax": 2.0}),
        ("ema_gate", {"ema_gate": True}),
        ("wide_exit", {"vmin": 1.0, "vmax": 2.5}),
        ("1h", {"timeframe": "1h"}),
        ("entry_guard", {"entry_guard": True}),
        ("combo", {"vmin": 0.8, "vmax": 1.2, "ema_gate": True}),
    ],
    "s30": [
        ("base", {}),
        ("higher", {"k_in": 1.5, "k_exit": 0.5}),
        ("lower", {"k_in": 0.5, "k_exit": -0.5}),
        ("ema_gate", {"ema_gate": True}),
        ("wide_exit", {"k_in": 1.0, "k_exit": -0.5}),
        ("1h", {"timeframe": "1h"}),
        ("entry_guard", {"entry_guard": True}),
        ("combo", {"k_in": 1.5, "k_exit": 0.5, "ema_gate": True}),
    ],
    "s31": [
        ("base", {}),
        ("higher", {"th_in": 1.0, "th_exit": 0.0}),
        ("lower", {"th_in": 0.25, "th_exit": -1.0}),
        ("ema_gate", {"ema_gate": True}),
        ("wide_exit", {"th_in": 0.5, "th_exit": -2.0}),
        ("1h", {"timeframe": "1h"}),
        ("entry_guard", {"entry_guard": True}),
        ("combo", {"th_in": 1.0, "th_exit": 0.0, "ema_gate": True}),
    ],
    "s32": [
        ("base", {}),
        ("higher", {"th_in": 1.0, "th_exit": 0.0}),
        ("lower", {"th_in": 0.25, "th_exit": -1.0}),
        ("ema_gate", {"ema_gate": True}),
        ("wide_exit", {"th_in": 0.5, "th_exit": -2.0}),
        ("1h", {"timeframe": "1h"}),
        ("entry_guard", {"entry_guard": True}),
        ("combo", {"th_in": 1.0, "th_exit": 0.0, "ema_gate": True}),
    ],
    "s33": [
        ("base", {}),
        ("ema_gate", {"ema_gate": True}),
        ("entry_guard", {"entry_guard": True}),
        ("1h", {"timeframe": "1h"}),
        ("ema_guard", {"ema_gate": True, "entry_guard": True}),
        ("1h_ema", {"timeframe": "1h", "ema_gate": True}),
        ("1h_guard", {"timeframe": "1h", "entry_guard": True}),
        ("1h_ema_guard", {"timeframe": "1h", "ema_gate": True, "entry_guard": True}),
    ],
    "s34": [
        ("base", {}),
        ("deeper", {"k_in": 0.1, "k_exit": 0.6}),
        ("shallow", {"k_in": 0.35, "k_exit": 0.4}),
        ("ema_gate", {"ema_gate": True}),
        ("wide_exit", {"k_in": 0.2, "k_exit": 0.8}),
        ("1h", {"timeframe": "1h"}),
        ("entry_guard", {"entry_guard": True}),
        ("combo", {"k_in": 0.1, "k_exit": 0.6, "ema_gate": True}),
    ],
    "s35": [
        ("base", {}),
        ("tighter", {"low": 0.02, "high": 0.06}),
        ("looser", {"low": 0.05, "high": 0.15}),
        ("ema_gate", {"ema_gate": True}),
        ("wide_exit", {"low": 0.03, "high": 0.20}),
        ("1h", {"timeframe": "1h"}),
        ("entry_guard", {"entry_guard": True}),
        ("combo", {"low": 0.02, "high": 0.06, "ema_gate": True}),
    ],
    "s36": [
        ("base", {}),
        ("higher", {"k_in": 0.9, "k_exit": 0.5}),
        ("lower", {"k_in": 0.7, "k_exit": 0.3}),
        ("ema_gate", {"ema_gate": True}),
        ("wide_exit", {"k_in": 0.8, "k_exit": 0.2}),
        ("1h", {"timeframe": "1h"}),
        ("entry_guard", {"entry_guard": True}),
        ("combo", {"k_in": 0.9, "k_exit": 0.5, "ema_gate": True}),
    ],
    "s37": [
        ("base", {}),
        ("ema_gate", {"ema_gate": True}),
        ("entry_guard", {"entry_guard": True}),
        ("1h", {"timeframe": "1h"}),
        ("ema_guard", {"ema_gate": True, "entry_guard": True}),
        ("1h_ema", {"timeframe": "1h", "ema_gate": True}),
        ("1h_guard", {"timeframe": "1h", "entry_guard": True}),
        ("1h_ema_guard", {"timeframe": "1h", "ema_gate": True, "entry_guard": True}),
    ],
    "s38": [
        ("base", {}),
        ("higher", {"k_in": 1.5, "k_exit": 0.4}),
        ("lower", {"k_in": 0.5, "k_exit": 0.1}),
        ("ema_gate", {"ema_gate": True}),
        ("wide_exit", {"k_in": 1.0, "k_exit": -0.5}),
        ("1h", {"timeframe": "1h"}),
        ("entry_guard", {"entry_guard": True}),
        ("combo", {"k_in": 1.5, "k_exit": 0.4, "ema_gate": True}),
    ],
    "s39": [
        ("base", {}),
        ("tighter", {"w_in": 1.5, "w_exit": 3.0}),
        ("looser", {"w_in": 3.0, "w_exit": 6.0}),
        ("ema_gate", {"ema_gate": True}),
        ("wide_exit", {"w_in": 2.0, "w_exit": 8.0}),
        ("1h", {"timeframe": "1h"}),
        ("entry_guard", {"entry_guard": True}),
        ("combo", {"w_in": 1.5, "w_exit": 3.0, "ema_gate": True}),
    ],
    "s40": [
        ("base", {}),
        ("higher_in", {"th_in": 1.5, "th_exit": 0.4}),
        ("lower_in", {"th_in": 0.5, "th_exit": 0.1}),
        ("ema_gate", {"ema_gate": True}),
        ("wide_exit", {"th_in": 1.0, "th_exit": -0.5}),
        ("1h", {"timeframe": "1h"}),
        ("entry_guard", {"entry_guard": True}),
        ("combo", {"th_in": 1.5, "th_exit": 0.4, "ema_gate": True}),
    ],
    "s41": [
        ("base", {}),
        ("tighter", {"k_in": 0.0002, "k_exit": 0.0004}),
        ("looser", {"k_in": 0.0005, "k_exit": 0.0010}),
        ("ema_gate", {"ema_gate": True}),
        ("wide_exit", {"k_in": 0.0003, "k_exit": 0.0020}),
        ("1h", {"timeframe": "1h"}),
        ("entry_guard", {"entry_guard": True}),
        ("combo", {"k_in": 0.0002, "k_exit": 0.0004, "ema_gate": True}),
    ],
    "s42": [
        ("base", {}),
        ("stronger", {"k_in": 0.7, "k_exit": 0.4}),
        ("weaker", {"k_in": 0.4, "k_exit": 0.2}),
        ("ema_gate", {"ema_gate": True}),
        ("wide_exit", {"k_in": 0.6, "k_exit": 0.1}),
        ("1h", {"timeframe": "1h"}),
        ("entry_guard", {"entry_guard": True}),
        ("combo", {"k_in": 0.7, "k_exit": 0.4, "ema_gate": True}),
    ],
    "s43": [
        ("base", {}),
        ("stronger", {"k_in": 4.5,"k_exit": 1.5}),
        ("looser", {"k_in": 1.8,"k_exit": 0.6}),
        ("ema_gate", {"ema_gate": True}),
        ("wide_exit", {"k_in": 3.0,"k_exit": 0.6}),
        ("1h", {"timeframe": "1h"}),
        ("entry_guard", {"entry_guard": True}),
        ("combo", {"k_in": 4.5,"k_exit": 1.5,"ema_gate": True}),
    ],
    "s44": [
        ("base", {}),
        ("ema_gate", {"ema_gate": True}),
        ("entry_guard", {"entry_guard": True}),
        ("1h", {"timeframe": "1h"}),
        ("ema_guard", {"ema_gate": True,"entry_guard": True}),
        ("1h_ema", {"timeframe": "1h","ema_gate": True}),
        ("1h_guard", {"timeframe": "1h","entry_guard": True}),
        ("1h_ema_guard", {"timeframe": "1h","ema_gate": True,"entry_guard": True}),
    ],
    "s45": [
        ("base", {}),
        ("ema_gate", {"ema_gate": True}),
        ("entry_guard", {"entry_guard": True}),
        ("1h", {"timeframe": "1h"}),
        ("ema_guard", {"ema_gate": True,"entry_guard": True}),
        ("1h_ema", {"timeframe": "1h","ema_gate": True}),
        ("1h_guard", {"timeframe": "1h","entry_guard": True}),
        ("1h_ema_guard", {"timeframe": "1h","ema_gate": True,"entry_guard": True}),
    ],
    "s46": [
        ("base", {}),
        ("stronger", {"k_in": 0.0015,"k_exit": 0.00315}),
        ("looser", {"k_in": 0.00375,"k_exit": 0.00675}),
        ("ema_gate", {"ema_gate": True}),
        ("wide_exit", {"k_in": 0.0025,"k_exit": 0.0081}),
        ("1h", {"timeframe": "1h"}),
        ("entry_guard", {"entry_guard": True}),
        ("combo", {"k_in": 0.0015,"k_exit": 0.00315,"ema_gate": True}),
    ],
    "s47": [
        ("base", {}),
        ("stronger", {"k_in": 2.25,"k_exit": 0.75}),
        ("looser", {"k_in": 0.9,"k_exit": 0.3}),
        ("ema_gate", {"ema_gate": True}),
        ("wide_exit", {"k_in": 1.5,"k_exit": 0.3}),
        ("1h", {"timeframe": "1h"}),
        ("entry_guard", {"entry_guard": True}),
        ("combo", {"k_in": 2.25,"k_exit": 0.75,"ema_gate": True}),
    ],
    "s48": [
        ("base", {}),
        ("stronger", {"k_in": 1.58,"k_exit": 1.27}),
        ("looser", {"k_in": 0.63,"k_exit": 0.51}),
        ("ema_gate", {"ema_gate": True}),
        ("wide_exit", {"k_in": 1.05,"k_exit": 0.51}),
        ("1h", {"timeframe": "1h"}),
        ("entry_guard", {"entry_guard": True}),
        ("combo", {"k_in": 1.58,"k_exit": 1.27,"ema_gate": True}),
    ],
    "s49": [
        ("base", {}),
        ("ema_gate", {"ema_gate": True}),
        ("entry_guard", {"entry_guard": True}),
        ("1h", {"timeframe": "1h"}),
        ("ema_guard", {"ema_gate": True,"entry_guard": True}),
        ("1h_ema", {"timeframe": "1h","ema_gate": True}),
        ("1h_guard", {"timeframe": "1h","entry_guard": True}),
        ("1h_ema_guard", {"timeframe": "1h","ema_gate": True,"entry_guard": True}),
    ],
    "s50": [
        ("base", {}),
        ("ema_gate", {"ema_gate": True}),
        ("entry_guard", {"entry_guard": True}),
        ("1h", {"timeframe": "1h"}),
        ("ema_guard", {"ema_gate": True,"entry_guard": True}),
        ("1h_ema", {"timeframe": "1h","ema_gate": True}),
        ("1h_guard", {"timeframe": "1h","entry_guard": True}),
        ("1h_ema_guard", {"timeframe": "1h","ema_gate": True,"entry_guard": True}),
    ],
    "s51": [
        ("base", {}),
        ("stronger", {"k_in": 0.09,"k_exit": 0.32}),
        ("looser", {"k_in": 0.22,"k_exit": 0.68}),
        ("ema_gate", {"ema_gate": True}),
        ("wide_exit", {"k_in": 0.15,"k_exit": 0.81}),
        ("1h", {"timeframe": "1h"}),
        ("entry_guard", {"entry_guard": True}),
        ("combo", {"k_in": 0.09,"k_exit": 0.32,"ema_gate": True}),
    ],
    "s52": [
        ("base", {}),
        ("stronger", {"k_in": 0.45,"k_exit": -0.15}),
        ("looser", {"k_in": 0.18,"k_exit": -0.06}),
        ("ema_gate", {"ema_gate": True}),
        ("wide_exit", {"k_in": 0.3,"k_exit": -0.06}),
        ("1h", {"timeframe": "1h"}),
        ("entry_guard", {"entry_guard": True}),
        ("combo", {"k_in": 0.45,"k_exit": -0.15,"ema_gate": True}),
    ],
    "s53": [
        ("base", {}),
        ("stronger", {"k_in": 0.5,"k_exit": -0.075}),
        ("looser", {"k_in": -0.2,"k_exit": -0.03}),
        ("ema_gate", {"ema_gate": True}),
        ("wide_exit", {"k_in": 0.0,"k_exit": -0.03}),
        ("1h", {"timeframe": "1h"}),
        ("entry_guard", {"entry_guard": True}),
        ("combo", {"k_in": 0.5,"k_exit": -0.075,"ema_gate": True}),
    ],
    "s54": [
        ("base", {}),
        ("stronger", {"k_in": 37.5,"k_exit": 30.0}),
        ("looser", {"k_in": 15.0,"k_exit": 12.0}),
        ("ema_gate", {"ema_gate": True}),
        ("wide_exit", {"k_in": 25.0,"k_exit": 12.0}),
        ("entry_guard", {"entry_guard": True}),
        ("entry_ema", {"entry_guard": True,"ema_gate": True}),
        ("combo", {"k_in": 37.5,"k_exit": 30.0,"ema_gate": True}),
    ],
    "s55": [
        ("base", {}),
        ("stronger", {"k_in": 82.5,"k_exit": 67.5}),
        ("looser", {"k_in": 33.0,"k_exit": 27.0}),
        ("ema_gate", {"ema_gate": True}),
        ("wide_exit", {"k_in": 55.0,"k_exit": 27.0}),
        ("entry_guard", {"entry_guard": True}),
        ("entry_ema", {"entry_guard": True,"ema_gate": True}),
        ("combo", {"k_in": 82.5,"k_exit": 67.5,"ema_gate": True}),
    ],
    "s56": [
        ("base", {}),
        ("stronger", {"k_in": 0.52,"k_exit": 0.3}),
        ("looser", {"k_in": 0.21,"k_exit": 0.12}),
        ("ema_gate", {"ema_gate": True}),
        ("wide_exit", {"k_in": 0.35,"k_exit": 0.12}),
        ("entry_guard", {"entry_guard": True}),
        ("entry_ema", {"entry_guard": True,"ema_gate": True}),
        ("combo", {"k_in": 0.52,"k_exit": 0.3,"ema_gate": True}),
    ],
    "s57": [
        ("base", {}),
        ("stronger", {"k_in": 3.0,"k_exit": 1.5}),
        ("looser", {"k_in": 1.2,"k_exit": 0.6}),
        ("ema_gate", {"ema_gate": True}),
        ("wide_exit", {"k_in": 2.0,"k_exit": 0.6}),
        ("entry_guard", {"entry_guard": True}),
        ("entry_ema", {"entry_guard": True,"ema_gate": True}),
        ("combo", {"k_in": 3.0,"k_exit": 1.5,"ema_gate": True}),
    ],
    "s58": [
        ("base", {}),
        ("stronger", {"k_in": 0.008,"k_exit": 0.001}),
        ("looser", {"k_in": 0.002,"k_exit": 0.0}),
        ("ema_gate", {"ema_gate": True}),
        ("wide_exit", {"k_in": 0.004,"k_exit": -0.001}),
        ("1h", {"timeframe": "1h"}),
        ("entry_guard", {"entry_guard": True}),
        ("combo", {"k_in": 0.008,"k_exit": 0.001,"ema_gate": True}),
    ],
    "s59": [
        ("base", {}),
        ("stronger", {"k_in": 20.0,"k_exit": 50.0}),
        ("looser", {"k_in": 40.0,"k_exit": 80.0}),
        ("ema_gate", {"ema_gate": True}),
        ("wide_exit", {"k_in": 30.0,"k_exit": 90.0}),
        ("1h", {"timeframe": "1h"}),
        ("entry_guard", {"entry_guard": True}),
        ("combo", {"k_in": 20.0,"k_exit": 50.0,"ema_gate": True}),
    ],
    "s60": [
        ("base", {}),
        ("stronger", {"k_in": 20.0,"k_exit": 80.0}),
        ("looser", {"k_in": 40.0,"k_exit": 60.0}),
        ("ema_gate", {"ema_gate": True}),
        ("wide_exit", {"k_in": 30.0,"k_exit": 90.0}),
        ("1h", {"timeframe": "1h"}),
        ("entry_guard", {"entry_guard": True}),
        ("combo", {"k_in": 20.0,"k_exit": 80.0,"ema_gate": True}),
    ],
    "s61": [
        ("base", {}),
        ("stronger", {"k_in": 1.0,"k_exit": -0.25}),
        ("looser", {"k_in": 0.25,"k_exit": -0.75}),
        ("ema_gate", {"ema_gate": True}),
        ("wide_exit", {"k_in": 0.5,"k_exit": -1.0}),
        ("1h", {"timeframe": "1h"}),
        ("entry_guard", {"entry_guard": True}),
        ("combo", {"k_in": 1.0,"k_exit": -0.25,"ema_gate": True}),
    ],
    "s62": [
        ("base", {}),
        ("stronger", {"k_in": 0.004,"k_exit": 0.002}),
        ("looser", {"k_in": 0.0015,"k_exit": 0.0008}),
        ("ema_gate", {"ema_gate": True}),
        ("wide_exit", {"k_in": 0.0025,"k_exit": 0.0005}),
        ("1h", {"timeframe": "1h"}),
        ("entry_guard", {"entry_guard": True}),
        ("combo", {"k_in": 0.004,"k_exit": 0.002,"ema_gate": True}),
    ],
    "s63": [
        ("base", {}),
        ("ema_gate", {"ema_gate": True}),
        ("entry_guard", {"entry_guard": True}),
        ("1h", {"timeframe": "1h"}),
        ("ema_guard", {"ema_gate": True,"entry_guard": True}),
        ("1h_ema", {"timeframe": "1h","ema_gate": True}),
        ("1h_guard", {"timeframe": "1h","entry_guard": True}),
        ("1h_ema_guard", {"timeframe": "1h","ema_gate": True,"entry_guard": True}),
    ],
    "s64": [
        ("base", {}),
        ("ema_gate", {"ema_gate": True}),
        ("entry_guard", {"entry_guard": True}),
        ("1h", {"timeframe": "1h"}),
        ("ema_guard", {"ema_gate": True,"entry_guard": True}),
        ("1h_ema", {"timeframe": "1h","ema_gate": True}),
        ("1h_guard", {"timeframe": "1h","entry_guard": True}),
        ("1h_ema_guard", {"timeframe": "1h","ema_gate": True,"entry_guard": True}),
    ],
    "s65": [
        ("base", {}),
        ("stronger", {"k_in": 0.35,"k_exit": 0.1}),
        ("looser", {"k_in": 0.7,"k_exit": 0.25}),
        ("ema_gate", {"ema_gate": True}),
        ("wide_exit", {"k_in": 0.5,"k_exit": 0.05}),
        ("1h", {"timeframe": "1h"}),
        ("entry_guard", {"entry_guard": True}),
        ("combo", {"k_in": 0.35,"k_exit": 0.1,"ema_gate": True}),
    ],
    "s66": [
        ("base", {}),
        ("stronger", {"vmin": 1.5}),
        ("looser", {"vmin": 0.8}),
        ("ema_gate", {"ema_gate": True}),
        ("wide_exit", {"vmin": 1.2}),
        ("1h", {"timeframe": "1h"}),
        ("entry_guard", {"entry_guard": True}),
        ("combo", {"vmin": 1.5,"ema_gate": True}),
    ],
    "s67": [
        ("base", {}),
        ("stronger", {"k_in": 30.0,"k_exit": 25.0}),
        ("looser", {"k_in": 20.0,"k_exit": 15.0}),
        ("ema_gate", {"ema_gate": True}),
        ("wide_exit", {"k_in": 25.0,"k_exit": 18.0}),
        ("entry_guard", {"entry_guard": True}),
        ("entry_ema", {"entry_guard": True,"ema_gate": True}),
        ("combo", {"k_in": 30.0,"k_exit": 25.0,"ema_gate": True}),
    ],
    "s68": [
        ("base", {}),
        ("ema_gate", {"ema_gate": True}),
        ("entry_guard", {"entry_guard": True}),
        ("1h", {"timeframe": "1h"}),
        ("ema_guard", {"ema_gate": True,"entry_guard": True}),
        ("1h_ema", {"timeframe": "1h","ema_gate": True}),
        ("1h_guard", {"timeframe": "1h","entry_guard": True}),
        ("1h_ema_guard", {"timeframe": "1h","ema_gate": True,"entry_guard": True}),
    ],
    "s69": [
        ("base", {}),
        ("stronger", {"k_in": 60.0,"k_exit": 45.0}),
        ("looser", {"k_in": 45.0,"k_exit": 35.0}),
        ("ema_gate", {"ema_gate": True}),
        ("wide_exit", {"k_in": 50.0,"k_exit": 30.0}),
        ("1h", {"timeframe": "1h"}),
        ("entry_guard", {"entry_guard": True}),
        ("combo", {"k_in": 60.0,"k_exit": 45.0,"ema_gate": True}),
    ],
    "s70": [
        ("base", {}),
        ("stronger", {"k_in": 0.005,"k_exit": 0.01}),
        ("looser", {"k_in": 0.012,"k_exit": 0.025}),
        ("ema_gate", {"ema_gate": True}),
        ("wide_exit", {"k_in": 0.008,"k_exit": 0.03}),
        ("entry_guard", {"entry_guard": True}),
        ("entry_ema", {"entry_guard": True,"ema_gate": True}),
        ("combo", {"k_in": 0.005,"k_exit": 0.01,"ema_gate": True}),
    ],
    "s71": [
        ("base", {}),
        ("stronger", {"k_in": 20.0,"k_exit": 80.0}),
        ("looser", {"k_in": 40.0,"k_exit": 60.0}),
        ("ema_gate", {"ema_gate": True}),
        ("wide_exit", {"k_in": 30.0,"k_exit": 90.0}),
        ("1h", {"timeframe": "1h"}),
        ("entry_guard", {"entry_guard": True}),
        ("combo", {"k_in": 20.0,"k_exit": 80.0,"ema_gate": True}),
    ],
    "s72": [
        ("base", {}),
        ("stronger", {"k_in": 0.008,"k_exit": 0.001}),
        ("looser", {"k_in": 0.002,"k_exit": 0.0}),
        ("ema_gate", {"ema_gate": True}),
        ("wide_exit", {"k_in": 0.004,"k_exit": -0.001}),
        ("1h", {"timeframe": "1h"}),
        ("entry_guard", {"entry_guard": True}),
        ("combo", {"k_in": 0.008,"k_exit": 0.001,"ema_gate": True}),
    ],
    "s73": [
        ("base", {}),
        ("stronger", {"k_in": 80.0,"k_exit": 50.0}),
        ("looser", {"k_in": 60.0,"k_exit": 30.0}),
        ("ema_gate", {"ema_gate": True}),
        ("wide_exit", {"k_in": 70.0,"k_exit": 20.0}),
        ("1h", {"timeframe": "1h"}),
        ("entry_guard", {"entry_guard": True}),
        ("combo", {"k_in": 80.0,"k_exit": 50.0,"ema_gate": True}),
    ],
    "s74": [
        ("base", {}),
        ("stronger", {"k_in": -30.0,"k_exit": -60.0}),
        ("looser", {"k_in": -60.0,"k_exit": -90.0}),
        ("ema_gate", {"ema_gate": True}),
        ("wide_exit", {"k_in": -50.0,"k_exit": -95.0}),
        ("1h", {"timeframe": "1h"}),
        ("entry_guard", {"entry_guard": True}),
        ("combo", {"k_in": -30.0,"k_exit": -60.0,"ema_gate": True}),
    ],
    "s75": [
        ("base", {}),
        ("stronger", {"k_in": 150.0,"k_exit": 75.0}),
        ("looser", {"k_in": 75.0,"k_exit": 25.0}),
        ("ema_gate", {"ema_gate": True}),
        ("wide_exit", {"k_in": 100.0,"k_exit": 0.0}),
        ("1h", {"timeframe": "1h"}),
        ("entry_guard", {"entry_guard": True}),
        ("combo", {"k_in": 150.0,"k_exit": 75.0,"ema_gate": True}),
    ],
    "s76": [
        ("base", {}),
        ("stronger", {"k_in": 85.0,"k_exit": 60.0}),
        ("looser", {"k_in": 75.0,"k_exit": 45.0}),
        ("ema_gate", {"ema_gate": True}),
        ("wide_exit", {"k_in": 80.0,"k_exit": 35.0}),
        ("1h", {"timeframe": "1h"}),
        ("entry_guard", {"entry_guard": True}),
        ("combo", {"k_in": 85.0,"k_exit": 60.0,"ema_gate": True}),
    ],
    "s77": [
        ("base", {}),
        ("stronger", {"k_in": 85.0,"k_exit": 60.0}),
        ("looser", {"k_in": 75.0,"k_exit": 50.0}),
        ("ema_gate", {"ema_gate": True}),
        ("wide_exit", {"k_in": 80.0,"k_exit": 45.0}),
        ("1h", {"timeframe": "1h"}),
        ("entry_guard", {"entry_guard": True}),
        ("combo", {"k_in": 85.0,"k_exit": 60.0,"ema_gate": True}),
    ],
    "s78": [
        ("base", {}),
        ("stronger", {"k_in": 0.008,"k_exit": 0.004}),
        ("looser", {"k_in": 0.004,"k_exit": 0.002}),
        ("ema_gate", {"ema_gate": True}),
        ("wide_exit", {"k_in": 0.006,"k_exit": 0.0015}),
        ("1h", {"timeframe": "1h"}),
        ("entry_guard", {"entry_guard": True}),
        ("combo", {"k_in": 0.008,"k_exit": 0.004,"ema_gate": True}),
    ],
    "s79": [
        ("base", {}),
        ("stronger", {"k_in": 0.04,"k_exit": 0.01}),
        ("looser", {"k_in": 0.01,"k_exit": 0.0}),
        ("ema_gate", {"ema_gate": True}),
        ("wide_exit", {"k_in": 0.02,"k_exit": -0.01}),
        ("1h", {"timeframe": "1h"}),
        ("entry_guard", {"entry_guard": True}),
        ("combo", {"k_in": 0.04,"k_exit": 0.01,"ema_gate": True}),
    ],
    "s80": [
        ("base", {}),
        ("stronger", {"k_in": 0.7,"k_exit": -0.3}),
        ("looser", {"k_in": 0.3,"k_exit": -0.7}),
        ("ema_gate", {"ema_gate": True}),
        ("wide_exit", {"k_in": 0.5,"k_exit": -0.9}),
        ("1h", {"timeframe": "1h"}),
        ("entry_guard", {"entry_guard": True}),
        ("combo", {"k_in": 0.7,"k_exit": -0.3,"ema_gate": True}),
    ],
    "s81": [
        ("base", {}),
        ("stronger", {"k_in": 0.7,"k_exit": -0.3}),
        ("looser", {"k_in": 0.3,"k_exit": -0.7}),
        ("ema_gate", {"ema_gate": True}),
        ("wide_exit", {"k_in": 0.5,"k_exit": -0.9}),
        ("1h", {"timeframe": "1h"}),
        ("entry_guard", {"entry_guard": True}),
        ("combo", {"k_in": 0.7,"k_exit": -0.3,"ema_gate": True}),
    ],
    "s82": [
        ("base", {}),
        ("stronger", {"k_in": 0.0005,"k_exit": 0.001}),
        ("looser", {"k_in": 0.002,"k_exit": 0.004}),
        ("ema_gate", {"ema_gate": True}),
        ("wide_exit", {"k_in": 0.001,"k_exit": 0.003}),
        ("1h", {"timeframe": "1h"}),
        ("entry_guard", {"entry_guard": True}),
        ("combo", {"k_in": 0.0005,"k_exit": 0.001,"ema_gate": True}),
    ],
    "s83": [
        ("base", {}),
        ("ema_gate", {"ema_gate": True}),
        ("entry_guard", {"entry_guard": True}),
        ("1h", {"timeframe": "1h"}),
        ("ema_guard", {"ema_gate": True,"entry_guard": True}),
        ("1h_ema", {"timeframe": "1h","ema_gate": True}),
        ("1h_guard", {"timeframe": "1h","entry_guard": True}),
        ("1h_ema_guard", {"timeframe": "1h","ema_gate": True,"entry_guard": True}),
    ],
    "s84": [
        ("base", {}),
        ("ema_gate", {"ema_gate": True}),
        ("entry_guard", {"entry_guard": True}),
        ("1h", {"timeframe": "1h"}),
        ("ema_guard", {"ema_gate": True,"entry_guard": True}),
        ("1h_ema", {"timeframe": "1h","ema_gate": True}),
        ("1h_guard", {"timeframe": "1h","entry_guard": True}),
        ("1h_ema_guard", {"timeframe": "1h","ema_gate": True,"entry_guard": True}),
    ],
    "s85": [
        ("base", {}),
        ("ema_gate", {"ema_gate": True}),
        ("entry_guard", {"entry_guard": True}),
        ("ema_guard", {"ema_gate": True,"entry_guard": True}),
        ("entry_ema", {"entry_guard": True,"ema_gate": True}),
        ("combo", {"ema_gate": True,"entry_guard": True}),
        ("ema_only", {"ema_gate": True}),
        ("guard_only", {"entry_guard": True}),
    ],
    "s86": [
        ("base", {}),
        ("stronger", {"k_in": 0.7,"k_exit": -0.3}),
        ("looser", {"k_in": 0.3,"k_exit": -0.7}),
        ("ema_gate", {"ema_gate": True}),
        ("wide_exit", {"k_in": 0.5,"k_exit": -0.9}),
        ("1h", {"timeframe": "1h"}),
        ("entry_guard", {"entry_guard": True}),
        ("combo", {"k_in": 0.7,"k_exit": -0.3,"ema_gate": True}),
    ],
    "s87": [
        ("base", {}),
        ("stronger", {"k_in": 0.04,"k_exit": 0.01}),
        ("looser", {"k_in": 0.01,"k_exit": 0.0}),
        ("ema_gate", {"ema_gate": True}),
        ("wide_exit", {"k_in": 0.02,"k_exit": -0.01}),
        ("1h", {"timeframe": "1h"}),
        ("entry_guard", {"entry_guard": True}),
        ("combo", {"k_in": 0.04,"k_exit": 0.01,"ema_gate": True}),
    ],
    "s88": [
        ("base", {}),
        ("stronger", {"k_in": 65.0,"k_exit": 50.0}),
        ("looser", {"k_in": 45.0,"k_exit": 30.0}),
        ("ema_gate", {"ema_gate": True}),
        ("wide_exit", {"k_in": 55.0,"k_exit": 25.0}),
        ("1h", {"timeframe": "1h"}),
        ("entry_guard", {"entry_guard": True}),
        ("combo", {"k_in": 65.0,"k_exit": 50.0,"ema_gate": True}),
    ],
    "s89": [
        ("base", {}),
        ("stronger", {"k_in": 50.0,"k_exit": 20.0}),
        ("looser", {"k_in": 15.0,"k_exit": 0.0}),
        ("ema_gate", {"ema_gate": True}),
        ("wide_exit", {"k_in": 30.0,"k_exit": 0.0}),
        ("1h", {"timeframe": "1h"}),
        ("entry_guard", {"entry_guard": True}),
        ("combo", {"k_in": 50.0,"k_exit": 20.0,"ema_gate": True}),
    ],
    "s90": [
        ("base", {}),
        ("ema_gate", {"ema_gate": True}),
        ("entry_guard", {"entry_guard": True}),
        ("1h", {"timeframe": "1h"}),
        ("ema_guard", {"ema_gate": True,"entry_guard": True}),
        ("1h_ema", {"timeframe": "1h","ema_gate": True}),
        ("1h_guard", {"timeframe": "1h","entry_guard": True}),
        ("1h_ema_guard", {"timeframe": "1h","ema_gate": True,"entry_guard": True}),
    ],
    "s91": [
        ("base", {}),
        ("stronger", {"k_in": 65.0,"k_exit": 50.0}),
        ("looser", {"k_in": 45.0,"k_exit": 30.0}),
        ("ema_gate", {"ema_gate": True}),
        ("wide_exit", {"k_in": 55.0,"k_exit": 25.0}),
        ("1h", {"timeframe": "1h"}),
        ("entry_guard", {"entry_guard": True}),
        ("combo", {"k_in": 65.0,"k_exit": 50.0,"ema_gate": True}),
    ],
    "s92": [
        ("base", {}),
        ("stronger", {"k_in": 70.0,"k_exit": 55.0}),
        ("looser", {"k_in": 50.0,"k_exit": 35.0}),
        ("ema_gate", {"ema_gate": True}),
        ("wide_exit", {"k_in": 60.0,"k_exit": 30.0}),
        ("1h", {"timeframe": "1h"}),
        ("entry_guard", {"entry_guard": True}),
        ("combo", {"k_in": 70.0,"k_exit": 55.0,"ema_gate": True}),
    ],
    "s93": [
        ("base", {}),
        ("stronger", {"k_in": -40.0,"k_exit": -60.0}),
        ("looser", {"k_in": -70.0,"k_exit": -90.0}),
        ("ema_gate", {"ema_gate": True}),
        ("wide_exit", {"k_in": -50.0,"k_exit": -95.0}),
        ("1h", {"timeframe": "1h"}),
        ("entry_guard", {"entry_guard": True}),
        ("combo", {"k_in": -40.0,"k_exit": -60.0,"ema_gate": True}),
    ],
    "s94": [
        ("base", {}),
        ("stronger", {"k_in": 0.5,"k_exit": 0.3}),
        ("looser", {"k_in": 0.3,"k_exit": 0.15}),
        ("ema_gate", {"ema_gate": True}),
        ("wide_exit", {"k_in": 0.4,"k_exit": 0.1}),
        ("1h", {"timeframe": "1h"}),
        ("entry_guard", {"entry_guard": True}),
        ("combo", {"k_in": 0.5,"k_exit": 0.3,"ema_gate": True}),
    ],
    "s95": [
        ("base", {}),
        ("stronger", {"k_in": 0.0005,"k_exit": 0.001}),
        ("looser", {"k_in": 0.002,"k_exit": 0.005}),
        ("ema_gate", {"ema_gate": True}),
        ("wide_exit", {"k_in": 0.001,"k_exit": 0.004}),
        ("1h", {"timeframe": "1h"}),
        ("entry_guard", {"entry_guard": True}),
        ("combo", {"k_in": 0.0005,"k_exit": 0.001,"ema_gate": True}),
    ],
    "s96": [
        ("base", {}),
        ("stronger", {"k_in": 0.006,"k_exit": 0.002}),
        ("looser", {"k_in": 0.003,"k_exit": 0.001}),
        ("ema_gate", {"ema_gate": True}),
        ("wide_exit", {"k_in": 0.005,"k_exit": 0.001}),
        ("1h", {"timeframe": "1h"}),
        ("entry_guard", {"entry_guard": True}),
        ("combo", {"k_in": 0.006,"k_exit": 0.002,"ema_gate": True}),
    ],
    "s97": [
        ("base", {}),
        ("stronger", {"r_in": 65.0,"k_in": 65.0,"m_in": 65.0}),
        ("looser", {"r_in": 45.0,"k_in": 45.0,"m_in": 45.0}),
        ("ema_gate", {"ema_gate": True}),
        ("wide_exit", {"r_exit": 40.0,"k_exit": 40.0,"m_exit": 40.0}),
        ("1h", {"timeframe": "1h"}),
        ("entry_guard", {"entry_guard": True}),
        ("combo", {"r_in": 65.0,"k_in": 65.0,"m_in": 65.0,"ema_gate": True}),
    ],
    "s98": [
        ("base", {}),
        ("stronger", {"r_in": 65.0,"w_in": -40.0,"d_in": 65.0,"m_in": 65.0}),
        ("looser", {"r_in": 45.0,"w_in": -70.0,"d_in": 45.0,"m_in": 45.0}),
        ("ema_gate", {"ema_gate": True}),
        ("wide_exit", {"r_exit": 40.0,"w_exit": -90.0,"d_exit": 40.0,"m_exit": 40.0}),
        ("1h", {"timeframe": "1h"}),
        ("entry_guard", {"entry_guard": True}),
        ("combo", {"r_in": 65.0,"w_in": -40.0,"d_in": 65.0,"m_in": 65.0,"ema_gate": True}),
    ],
    "s99": [
        ("base", {}),
        ("stronger", {"k_in": 0.01,"k_exit": 0.005}),
        ("looser", {"k_in": 0.002,"k_exit": 0.0}),
        ("ema_gate", {"ema_gate": True}),
        ("wide_exit", {"k_in": 0.005,"k_exit": -0.005}),
        ("1h", {"timeframe": "1h"}),
        ("entry_guard", {"entry_guard": True}),
        ("combo", {"k_in": 0.01,"k_exit": 0.005,"ema_gate": True}),
    ],
    "s100": [
        ("base", {}),
        ("ema_gate", {"ema_gate": True}),
        ("entry_guard", {"entry_guard": True}),
        ("1h", {"timeframe": "1h"}),
        ("ema_guard", {"ema_gate": True,"entry_guard": True}),
        ("1h_ema", {"timeframe": "1h","ema_gate": True}),
        ("1h_guard", {"timeframe": "1h","entry_guard": True}),
        ("1h_ema_guard", {"timeframe": "1h","ema_gate": True,"entry_guard": True}),
    ],
    "s101": [
        ("base", {}),
        ("stronger", {"k_in": 0.04,"k_exit": 0.01}),
        ("looser", {"k_in": 0.01,"k_exit": 0.0}),
        ("ema_gate", {"ema_gate": True}),
        ("wide_exit", {"k_in": 0.02,"k_exit": -0.01}),
        ("1h", {"timeframe": "1h"}),
        ("entry_guard", {"entry_guard": True}),
        ("combo", {"k_in": 0.04,"k_exit": 0.01,"ema_gate": True}),
    ],
    "s102": [
        ("base", {}),
        ("stronger", {"k_in": 0.8,"k_exit": 0.5}),
        ("looser", {"k_in": 0.6,"k_exit": 0.3}),
        ("ema_gate", {"ema_gate": True}),
        ("wide_exit", {"k_in": 0.7,"k_exit": 0.25}),
        ("1h", {"timeframe": "1h"}),
        ("entry_guard", {"entry_guard": True}),
        ("combo", {"k_in": 0.8,"k_exit": 0.5,"ema_gate": True}),
    ],
}

FIELDS = [
    "strategy", "variant", "instrument", "window", "cost_bps",
    "n_trades", "trades_per_year",
    "total_return_pct", "buyhold_return_pct", "edge_vs_bh_pct",
    "win_rate_pct", "sharpe_weekly", "max_drawdown_pct", "exposure_pct",
    "error",
]


def _run_one(sid: str, variant: str, kw: dict, instrument: str,
             window: str, wcfg: dict, cost: float) -> dict:
    import importlib
    lib = importlib.import_module(f"strategy.{STRATEGIES[sid]}")
    tf = kw.get("timeframe", "5m" if sid != "s17" else "1h")
    parquet = PARQUET_1H if tf == "1h" else PARQUET_5M
    try:
        res = lib.run(
            parquet=parquet,
            instrument=instrument,
            timeframe=tf,
            since=wcfg["since"],
            until=wcfg["until"],
            cost_bps=cost,
            entry_guard=kw.get("entry_guard", False),
            **{k: v for k, v in kw.items()
               if k not in ("timeframe", "entry_guard")},
        )
        edge = res["total_return_pct"] - res["buyhold_return_pct"]
        return {
            "strategy": sid, "variant": variant, "instrument": instrument,
            "window": window, "cost_bps": cost,
            "n_trades": res["n_trades"],
            "trades_per_year": res["trades_per_year"],
            "total_return_pct": res["total_return_pct"],
            "buyhold_return_pct": res["buyhold_return_pct"],
            "edge_vs_bh_pct": round(edge, 2),
            "win_rate_pct": res["win_rate_pct"],
            "sharpe_weekly": res["sharpe_weekly"],
            "max_drawdown_pct": res["max_drawdown_pct"],
            "exposure_pct": res["exposure_pct"],
            "error": "",
        }
    except SystemExit as e:
        return {f: ("" if isinstance(f, str) else 0) for f in FIELDS} | {
            "strategy": sid, "variant": variant, "instrument": instrument,
            "window": window, "cost_bps": cost,
            "error": f"SystemExit: {e}",
        }
    except Exception as e:  # pragma: no cover - surfaced in the CSV
        return {f: ("" if isinstance(f, str) else 0) for f in FIELDS} | {
            "strategy": sid, "variant": variant, "instrument": instrument,
            "window": window, "cost_bps": cost,
            "error": f"{type(e).__name__}: {e}",
        }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--out", default="strategy/results/iterations_2026-10-30.csv")
    ap.add_argument("--strategies", default=None,
                    help="comma-separated subset (e.g. s08,s09)")
    ap.add_argument("--variants", default=None,
                    help="comma-separated variant names to run (default: all 6)")
    args = ap.parse_args()

    sids = args.strategies.split(",") if args.strategies else list(STRATEGIES)
    varnames = args.variants.split(",") if args.variants else None

    tasks = []
    for sid in sids:
        for variant, kw in VARIANTS[sid]:
            if varnames and variant not in varnames:
                continue
            for instrument in INSTRUMENTS:
                for window, wcfg in WINDOWS.items():
                    for cost in COST_TIERS:
                        tasks.append((sid, variant, kw, instrument, window,
                                     wcfg, cost))

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"Running {len(tasks)} cells with {args.workers} workers "
          f"(10 strategies x 6 variants x 3 instruments x 2 windows x 3 costs)...",
          file=sys.stderr)
    t0 = time.time()

    rows: list[dict] = []
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(_run_one, *t): t for t in tasks}
        done = 0
        for fut in as_completed(futs):
            rows.append(fut.result())
            done += 1
            if done % 100 == 0 or done == len(futs):
                print(f"  {done}/{len(futs)} done "
                      f"({time.time() - t0:.1f}s)", file=sys.stderr)
    rows.sort(key=lambda r: (r["strategy"], r["variant"], r["instrument"],
                             r["window"], r["cost_bps"]))

    with out_path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in FIELDS})
    print(f"Wrote {len(rows)} rows -> {out_path}", file=sys.stderr)

    # Console summary: best variant per strategy at 2 bps (edge vs buy-hold,
    # averaged over the 3 instruments, both windows combined).
    _print_summary(rows)


def _print_summary(rows: list[dict]) -> None:
    from collections import defaultdict
    agg: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for r in rows:
        if r["cost_bps"] != 2.0 or r.get("error"):
            continue
        agg[(r["strategy"], r["variant"])].append(r)

    print("\n=== Best variant per strategy (2 bps, mean edge vs buy-hold across 3 instruments) ===")
    print(f"{'sid':<6} {'variant':<22} {'mean_edge':>10} {'n_trades':>9} {'tpy':>7}")
    by_sid: dict[str, list[tuple[str, float, float, float]]] = defaultdict(list)
    for (sid, variant), cells in agg.items():
        mean_edge = sum(c["edge_vs_bh_pct"] for c in cells) / len(cells)
        mean_trades = sum(c["n_trades"] for c in cells) / len(cells)
        mean_tpy = sum(c["trades_per_year"] for c in cells) / len(cells)
        by_sid[sid].append((variant, mean_edge, mean_trades, mean_tpy))
    for sid in sorted(by_sid):
        ranked = sorted(by_sid[sid], key=lambda x: -x[1])
        for i, (v, me, mt, mtpy) in enumerate(ranked, 1):
            print(f"{sid:<6} {v:<22} {me:>+10.2f} {mt:>9.0f} {mtpy:>7.1f}")
        print()


if __name__ == "__main__":
    main()
