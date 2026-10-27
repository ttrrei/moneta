"""Technical indicator & feature engine (spec: docs/indicators.md, v2.0 Final).

Builds the two feature tables consumed by strategy search:

* ``data/ohlcv_5m_features/ohlcv_5m_features.parquet``
* ``data/ohlcv_1h_features/ohlcv_1h_features.parquet``

Design rules enforced here:

* TA-Lib (C) is the source of truth for every indicator it implements;
  ``pandas_ta_classic`` is used only for ER/Chop and as the parity oracle.
* Strict causality: features at bar T use data <= T only.  1h features are
  joined to 5m with an as-of join on ``close_time`` (no lookahead).
* CFD parameter grid: N in {6, 12, 24, 60, 120}; pairs (6,24)/(12,60)/(24,120).
* No synthetic gap filling: rolling windows operate on bar rows as-is; gaps
  are exposed to downstream models via explicit flag features.
* float64 throughout computation, float32 at write time.
"""

from __future__ import annotations

import abc
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import talib

import pandas_ta_classic as ptac

from indicators import (  # noqa: E402  (project's own indicator library)
    param_tag,
    psar_direction,
    psar_line,
    supertrend,
    validate_free_params,
)

# ---------------------------------------------------------------------------
# Parameter grid (spec section 4.1)
# ---------------------------------------------------------------------------

N_GRID = (6, 12, 24, 60, 120)
PAIRS = ((6, 24), (12, 60), (24, 120))
NORM_ATR_N = 24
BB_SIGMA = 2.0
KC_MULT = 2.0
FASTD_PERIOD = 6
# Free (non-window) parameters.  Only *time-window* parameters are restricted
# to the N grid above; these are NOT whitelisted.  Defaults below are named
# constants (never library defaults) and can be overridden per run
# (compute_instrument_features / build_features / CLI flags).
PSAR_PARAMS = ((0.02, 0.20), (0.01, 0.10))  # Wilder SAR (acceleration, maximum)
ST_MULTS = (2.0, 3.0)                       # Supertrend ATR multiplier(s)
EPS = 1e-12
WARMUP_DROP = 3 * max(N_GRID)  # 360 bars (spec section 5)

VALID_N = frozenset(N_GRID)
VALID_PAIRS = frozenset(PAIRS)


def validate_grid(n_grid: Iterable[int], pairs: Iterable[tuple[int, int]]) -> None:
    """Reject any window/pair outside the CFD whitelist (spec section 4.1)."""
    bad_n = [n for n in n_grid if n not in VALID_N]
    if bad_n:
        raise ValueError(f"Windows outside CFD grid {sorted(VALID_N)}: {bad_n}")
    bad_pairs = [p for p in pairs if p not in VALID_PAIRS]
    if bad_pairs:
        raise ValueError(f"Pairs outside whitelist {sorted(VALID_PAIRS)}: {bad_pairs}")


# ---------------------------------------------------------------------------
# Session reset anchors (spec section 4.2), expressed as (month, UTC hour)
# (month = 1..12 of the *first* month of the DST-active half-year).
# ---------------------------------------------------------------------------

DST_EU_START_MONTH = 3
DST_EU_END_MONTH = 10


def _eu_dst_active(month: int) -> bool:
    return DST_EU_START_MONTH <= month < DST_EU_END_MONTH


@dataclass(frozen=True)
class SessionAnchor:
    """Day-reset anchor for one instrument, in local market time."""

    local_hour: int
    local_minute: int
    utc_offset_winter: float  # hours, local = UTC + offset
    utc_offset_summer: float


SESSION_ANCHORS: dict[str, SessionAnchor] = {
    # FX & spot metals: 17:00 New York (EST -5 / EDT -4)
    **{
        i: SessionAnchor(17, 0, -5.0, -4.0)
        for i in (
            "EUR_USD", "GBP_USD", "USD_JPY", "USD_CAD", "USD_CHF", "NZD_USD",
            "AUD_USD", "XAU_USD", "XAG_USD",
        )
    },
    # US index CFDs: 09:30 New York (regular trading session open)
    **{
        i: SessionAnchor(9, 30, -5.0, -4.0)
        for i in ("US30_USD", "SPX500_USD", "NAS100_USD")
    },
    # European index CFDs: 08:00 CET/BST
    **{
        i: SessionAnchor(8, 0, 1.0, 2.0)
        for i in ("DE30_EUR", "UK100_GBP")
    },
    # Asia index CFDs: local exchange open
    "JP225_USD": SessionAnchor(9, 0, 9.0, 9.0),
    "HK33_HKD": SessionAnchor(9, 30, 8.0, 8.0),
    "CN50_USD": SessionAnchor(9, 30, 8.0, 8.0),
    # Commodities & crypto: UTC midnight
    **{
        i: SessionAnchor(0, 0, 0.0, 0.0)
        for i in ("WTICO_USD", "BCO_USD", "BTC_USD", "ETH_USD")
    },
}


def session_anchor(instrument: str) -> SessionAnchor:
    try:
        return SESSION_ANCHORS[instrument]
    except KeyError:
        raise KeyError(
            f"No session anchor configured for {instrument!r}; add it to SESSION_ANCHORS"
        ) from None


def _reset_utc_hour(anchor: SessionAnchor, month: int) -> float:
    offset = anchor.utc_offset_summer if _eu_dst_active(month) else anchor.utc_offset_winter
    return (anchor.local_hour + anchor.local_minute / 60.0 - offset) % 24.0


def session_reset_index(ts: pd.Series, anchor: SessionAnchor) -> np.ndarray:
    """For each bar (UTC) return the id of its session: the index of the most
    recent reset instant <= the bar timestamp (spec section 4.2 dynamic VWAP).
    """
    times = ts.dt.tz_convert("UTC").to_numpy(dtype="datetime64[ns]")
    ns = times.astype("int64")  # epoch ns, UTC
    months = ts.dt.month.to_numpy()
    # One reset per day; the UTC hour of the reset depends on the DST month.
    # We compute, for each bar, the reset instant of *its* day; sessions are
    # contiguous in time so grouping by that instant is sufficient even when
    # the UTC hour of the anchor shifts across DST dates (a bar is always
    # compared against resets on-or-before itself).
    DAY_NS = 86_400 * 1_000_000_000
    day_ns = (ns // DAY_NS) * DAY_NS
    hour = np.vectorize(lambda m: _reset_utc_hour(anchor, int(m)))(months)
    reset_ns = day_ns + (hour * 3600.0).astype(np.int64) * 1_000_000_000
    # A bar before its own day's reset belongs to the previous day's session.
    prev_day_reset = reset_ns - DAY_NS
    group = np.where(ns >= reset_ns, reset_ns, prev_day_reset)
    # Compress the (strictly increasing) reset instants to small integer ids.
    _, ids = np.unique(group, return_inverse=True)
    return ids


def vwap_within_session(
    tp: np.ndarray, volume: np.ndarray, session: np.ndarray
) -> np.ndarray:
    """Session-anchored VWAP: cumsum(tp*vol)/cumsum(vol) within each session."""
    pv = tp * volume
    df = pd.DataFrame({"s": session, "pv": pv, "v": volume})
    g = df.groupby("s", sort=False)
    cum_pv = g["pv"].cumsum().to_numpy()
    cum_v = g["v"].cumsum().to_numpy()
    with np.errstate(divide="ignore", invalid="ignore"):
        out = np.where(cum_v > 0, cum_pv / np.where(cum_v == 0, 1.0, cum_v), np.nan)
    return out


# ---------------------------------------------------------------------------
# Gap / market-state flags (spec section 3.2)
# ---------------------------------------------------------------------------


def is_gap_bar_series(times: pd.Series, interval_seconds: int) -> np.ndarray:
    """1 where the gap since the previous bar's *close* exceeds one period."""
    t = times.dt.tz_convert("UTC").to_numpy(dtype="datetime64[ns]").astype("int64")
    gap_ns = np.empty(len(t), dtype=np.int64)
    if len(t) > 1:
        gap_ns[1:] = t[1:] - (t[:-1] + interval_seconds * 1_000_000_000)
    else:
        gap_ns[:] = 0
    return (gap_ns > 0).astype(np.int8)


def is_partial_series(n_bars: np.ndarray, interval_seconds: int) -> np.ndarray:
    expected = interval_seconds // 60  # 5m -> 5 one-minute bars, 1h -> 60
    return (np.asarray(n_bars) < expected).astype(np.int8)


def is_near_market_close_series(times: pd.Series, anchor: SessionAnchor) -> np.ndarray:
    """1 during the 2 hours before the instrument's session anchor on Fridays."""
    # Friday = weekday 4; window [anchor-2h, anchor) in local time.
    dt = times.dt
    weekday = dt.weekday.to_numpy()
    # Local time of each bar using both offsets; a bar is "near close" if it
    # falls inside the 2h window under either DST state.
    def in_window(offset: float) -> np.ndarray:
        local_h = (times.dt.hour.to_numpy() + times.dt.minute.to_numpy() / 60.0
                   + times.dt.second.to_numpy() / 3600.0 + offset) % 24.0
        start = (anchor.local_hour - 2.0) % 24.0
        end = anchor.local_hour % 24.0
        if start < end:
            inside = (local_h >= start) & (local_h < end)
        else:
            inside = (local_h >= start) | (local_h < end)
        return inside

    w = (in_window(anchor.utc_offset_winter) | in_window(anchor.utc_offset_summer))
    return (w & (weekday == 4)).astype(np.int8)


# ---------------------------------------------------------------------------
# Feature groups (spec section 6-7)
# ---------------------------------------------------------------------------


class BaseFeatureGroup(abc.ABC):
    """Uniform interface every feature family must implement (spec 6.1)."""

    @abc.abstractmethod
    def compute(
        self,
        o: np.ndarray, h: np.ndarray, l: np.ndarray, c: np.ndarray,
        v: np.ndarray, n_grid: tuple[int, ...], pairs: tuple[tuple[int, int], ...],
        aux: dict | None = None,
    ) -> dict[str, np.ndarray]:
        """Return {column name: float64 1-D array} aligned to the input rows."""

    @property
    @abc.abstractmethod
    def required_columns(self) -> list[str]:
        ...


class TrendGroup(BaseFeatureGroup):
    required_columns = ["high", "low", "close"]

    def compute(self, o, h, l, c, v, n_grid, pairs, aux=None):
        out: dict[str, np.ndarray] = {}
        for n in n_grid:
            out[f"sma_{n}"] = talib.SMA(c, timeperiod=n)
            out[f"ema_{n}"] = talib.EMA(c, timeperiod=n)
            adx = talib.ADX(h, l, c, timeperiod=n)
            out[f"adx_{n}"] = adx
            out[f"plus_di_{n}"] = talib.PLUS_DI(h, l, c, timeperiod=n)
            out[f"minus_di_{n}"] = talib.MINUS_DI(h, l, c, timeperiod=n)
            up, down = talib.AROON(h, l, timeperiod=n)
            out[f"aroon_up_{n}"] = up
            out[f"aroon_down_{n}"] = down
            hi_n = talib.MAX(h, timeperiod=n)
            lo_n = talib.MIN(l, timeperiod=n)
            out[f"dc_upper_{n}"] = hi_n
            out[f"dc_lower_{n}"] = lo_n
            out[f"dc_mid_{n}"] = (hi_n + lo_n) / 2.0
        for f, s in pairs:
            macd, signal, hist = talib.MACD(c, fastperiod=f, slowperiod=s, signalperiod=f)
            out[f"macd_{f}_{s}"] = macd
            out[f"macd_signal_{f}_{s}"] = signal
            out[f"macd_hist_{f}_{s}"] = hist
        # Parabolic SAR (free params, no window) and Supertrend (length = N from
        # the grid, multiplier free).  Column names carry the free parameters.
        # Implemented in the `indicators/` library; tested in isolation there.
        cfg = aux or {}
        for accel, mx in cfg.get("psar_params", PSAR_PARAMS):
            tag = f"{param_tag(accel)}_{param_tag(mx)}"
            sar = psar_line(h, l, accel=accel, maximum=mx)
            out[f"psar_{tag}"] = sar
            out[f"psar_dir_{tag}"] = psar_direction(c, sar)
        for n in n_grid:
            atr_n = talib.ATR(h, l, c, timeperiod=n)
            for mult in cfg.get("st_mults", ST_MULTS):
                st, st_dir = supertrend(h, l, c, atr_n, mult)
                out[f"st_{n}_{param_tag(mult)}"] = st
                out[f"st_dir_{n}_{param_tag(mult)}"] = st_dir
        return out


class MomentumGroup(BaseFeatureGroup):
    required_columns = ["high", "low", "close"]

    def compute(self, o, h, l, c, v, n_grid, pairs, aux=None):
        out: dict[str, np.ndarray] = {}
        for n in n_grid:
            out[f"rsi_{n}"] = talib.RSI(c, timeperiod=n)
            out[f"roc_{n}"] = talib.ROC(c, timeperiod=n)
            out[f"mom_{n}"] = talib.MOM(c, timeperiod=n)
            # STOCHF returns (fastk, fastd); fastd = SMA(%K, 6, simple) per spec 7.2.
            stoch_k, stoch_d = talib.STOCHF(
                h, l, c, fastk_period=n, fastd_period=FASTD_PERIOD, fastd_matype=0
            )
            out[f"stoch_k_{n}"] = stoch_k
            out[f"stoch_d_{n}"] = stoch_d
            out[f"cci_{n}"] = talib.CCI(h, l, c, timeperiod=n)
            out[f"willr_{n}"] = talib.WILLR(h, l, c, timeperiod=n)
        return out


class VolatilityGroup(BaseFeatureGroup):
    required_columns = ["high", "low", "close"]

    def compute(self, o, h, l, c, v, n_grid, pairs, aux=None):
        out: dict[str, np.ndarray] = {}
        out["tr"] = talib.TRANGE(h, l, c)
        log_ret = np.empty_like(c)
        log_ret[0] = np.nan
        log_ret[1:] = np.log(c[1:] / c[:-1])
        for n in n_grid:
            atr = talib.ATR(h, l, c, timeperiod=n)
            out[f"atr_{n}"] = atr
            mid, upper, lower = talib.BBANDS(
                c, timeperiod=n, nbdevup=BB_SIGMA, nbdevdn=BB_SIGMA, matype=0
            )
            out[f"bb_mid_{n}"] = mid
            out[f"bb_upper_{n}"] = upper
            out[f"bb_lower_{n}"] = lower
            out[f"bb_width_{n}"] = (upper - lower) / mid
            span = upper - lower
            out[f"bb_pctb_{n}"] = (c - lower) / np.where(span == 0, np.nan, span)
            kc_mid = talib.EMA(c, timeperiod=n)
            out[f"kc_mid_{n}"] = kc_mid
            out[f"kc_upper_{n}"] = kc_mid + KC_MULT * atr
            out[f"kc_lower_{n}"] = kc_mid - KC_MULT * atr
            out[f"sqz_on_{n}"] = (
                (lower > out[f"kc_lower_{n}"]) & (upper < out[f"kc_upper_{n}"])
            ).astype(np.float64)
            out[f"hv_{n}"] = talib.STDDEV(log_ret, timeperiod=n)
        return out


class RegimeGroup(BaseFeatureGroup):
    required_columns = ["high", "low", "close"]

    def compute(self, o, h, l, c, v, n_grid, pairs, aux=None):
        s = pd.Series
        out: dict[str, np.ndarray] = {}
        for n in n_grid:
            out[f"er_{n}"] = np.asarray(ptac.er(s(c), length=n), dtype=np.float64)
            out[f"chop_{n}"] = np.asarray(
                ptac.chop(s(h), s(l), s(c), length=n), dtype=np.float64
            )
        return out


class CandleStructureGroup(BaseFeatureGroup):
    required_columns = ["open", "high", "low", "close"]

    def compute(self, o, h, l, c, v, n_grid, pairs, aux=None):
        rng = np.maximum(h - l, EPS)
        return {
            "bar_body_ratio": np.abs(c - o) / rng,
            "bar_upper_wick_ratio": (h - np.maximum(o, c)) / rng,
            "bar_lower_wick_ratio": (np.minimum(o, c) - l) / rng,
            "bar_clv": ((c - l) - (h - c)) / rng,
        }


class VolumeProxyGroup(BaseFeatureGroup):
    required_columns = ["high", "low", "close", "volume"]

    def compute(self, o, h, l, c, v, n_grid, pairs, aux=None):
        aux = aux or {}
        out: dict[str, np.ndarray] = {}
        for n in n_grid:
            vol_sma = talib.SMA(v, timeperiod=n)
            out[f"vol_sma_{n}"] = vol_sma
            out[f"vol_rel_{n}"] = v / np.where(vol_sma == 0, np.nan, vol_sma)
            out[f"mfi_{n}"] = talib.MFI(h, l, c, v, timeperiod=n)
            cmf = ptac.cmf(pd.Series(h), pd.Series(l), pd.Series(c), pd.Series(v), length=n)
            out[f"cmf_{n}"] = np.asarray(cmf, dtype=np.float64)
        if "vwap" in aux:
            out["vwap"] = aux["vwap"]
        return out


class DerivedFeatureGroup(BaseFeatureGroup):
    required_columns = ["open", "high", "low", "close"]

    def compute(self, o, h, l, c, v, n_grid, pairs, aux=None):
        aux = aux or {}
        out: dict[str, np.ndarray] = {}
        atr_norm = aux.get("atr_norm")
        for n in n_grid:
            atr = aux.get(f"atr_{n}")
            if atr is not None:
                out[f"atr_pct_{n}"] = atr / c
            ema = aux.get(f"ema_{n}")
            if ema is not None and atr_norm is not None:
                out[f"ema_dist_{n}"] = (c - ema) / np.where(atr_norm == 0, np.nan, atr_norm)
        for f, s in pairs:
            ema_f, ema_s = aux.get(f"ema_{f}"), aux.get(f"ema_{s}")
            if ema_f is not None and ema_s is not None and atr_norm is not None:
                out[f"ema_spread_{f}_{s}"] = (ema_f - ema_s) / np.where(
                    atr_norm == 0, np.nan, atr_norm
                )
            macd_hist = aux.get(f"macd_hist_{f}_{s}")
            if macd_hist is not None and atr_norm is not None:
                out[f"macd_hist_atr_{f}_{s}"] = macd_hist / np.where(
                    atr_norm == 0, np.nan, atr_norm
                )
            atr_f, atr_s = aux.get(f"atr_{f}"), aux.get(f"atr_{s}")
            if atr_f is not None and atr_s is not None:
                out[f"vol_ratio_{f}_{s}"] = atr_f / np.where(atr_s == 0, np.nan, atr_s)
        # Donchian position and shifted high/low distance (lookahead-safe).
        for n in n_grid:
            dc_up, dc_lo = aux.get(f"dc_upper_{n}"), aux.get(f"dc_lower_{n}")
            if dc_up is not None and dc_lo is not None:
                span = dc_up - dc_lo
                out[f"dc_pos_{n}"] = (c - dc_lo) / np.where(span <= 0, np.nan, span)
            prev_hi = np.full_like(c, np.nan)
            prev_lo = np.full_like(c, np.nan)
            if len(c) > 1:
                prev_hi[1:] = talib.MAX(h, timeperiod=n)[:-1]
                prev_lo[1:] = talib.MIN(l, timeperiod=n)[:-1]
            if atr_norm is not None:
                out[f"dist_high_{n}"] = (prev_hi - c) / np.where(atr_norm == 0, np.nan, atr_norm)
                out[f"dist_low_{n}"] = (c - prev_lo) / np.where(atr_norm == 0, np.nan, atr_norm)
        # Signed ATR-normalised distance to the trailing-stop lines (sign = side).
        if atr_norm is not None:
            safe = np.where(atr_norm == 0, np.nan, atr_norm)
            for accel, mx in aux.get("psar_params", PSAR_PARAMS):
                tag = f"{param_tag(accel)}_{param_tag(mx)}"
                if aux.get(f"psar_{tag}") is not None:
                    out[f"psar_dist_{tag}"] = (c - aux[f"psar_{tag}"]) / safe
            for n in n_grid:
                for mult in aux.get("st_mults", ST_MULTS):
                    key = f"st_{n}_{param_tag(mult)}"
                    if aux.get(key) is not None:
                        out[f"st_dist_{n}_{param_tag(mult)}"] = (c - aux[key]) / safe
        if "hour_sin" in aux:
            out["hour_sin"] = aux["hour_sin"]
            out["hour_cos"] = aux["hour_cos"]
            out["dow_sin"] = aux["dow_sin"]
            out["dow_cos"] = aux["dow_cos"]
        return out


GROUPS = (
    TrendGroup,
    MomentumGroup,
    VolatilityGroup,
    RegimeGroup,
    CandleStructureGroup,
    VolumeProxyGroup,
    DerivedFeatureGroup,
)


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

OHLCV_COLS = ("instrument", "time", "open", "high", "low", "close", "volume", "n_bars")


def _instrument_arrays(df: pd.DataFrame) -> tuple[np.ndarray, ...]:
    return (
        df["open"].to_numpy(np.float64),
        df["high"].to_numpy(np.float64),
        df["low"].to_numpy(np.float64),
        df["close"].to_numpy(np.float64),
        df["volume"].to_numpy(np.float64),
    )


def compute_instrument_features(
    df: pd.DataFrame,
    interval_seconds: int,
    n_grid: tuple[int, ...] = N_GRID,
    pairs: tuple[tuple[int, int], ...] = PAIRS,
    psar_params: tuple[tuple[float, float], ...] = PSAR_PARAMS,
    st_mults: tuple[float, ...] = ST_MULTS,
) -> pd.DataFrame:
    """Compute the full spec feature matrix for one instrument's bars (sorted).

    ``n_grid`` / ``pairs`` are whitelisted (time-window parameters).
    ``psar_params`` / ``st_mults`` are free parameters and are only
    sanity-checked (not whitelisted) — see the `indicators/` library.

    ``df`` must contain OHLCV_COLS with a UTC ``time`` column.  Returns a
    DataFrame of the same length (warm-up rows are NaN, dropped by the caller).
    """
    validate_grid(n_grid, pairs)
    validate_free_params(psar_params, st_mults)
    df = df.reset_index(drop=True)
    o, h, l, c, v = _instrument_arrays(df)
    instrument = df["instrument"].iloc[0]
    anchor = session_anchor(instrument)
    times = df["time"]

    # Shared auxiliaries.
    session = session_reset_index(times, anchor)
    tp = (h + l + c) / 3.0
    vwap = vwap_within_session(tp, v, session)
    atr24 = talib.ATR(h, l, c, timeperiod=NORM_ATR_N)

    aux: dict = {"vwap": vwap, "atr_norm": atr24,
                 "psar_params": tuple(psar_params), "st_mults": tuple(st_mults)}
    out: dict[str, np.ndarray] = {}
    for group_cls in GROUPS[:5]:  # trend..candle: self-contained
        out.update(group_cls().compute(o, h, l, c, v, n_grid, pairs, aux))
    # Feed computed intermediates to volume/derived groups.
    aux.update(out)
    out.update(VolumeProxyGroup().compute(o, h, l, c, v, n_grid, pairs, aux))
    hour = times.dt.hour.to_numpy() + times.dt.minute.to_numpy() / 60.0
    aux.update(
        hour_sin=np.sin(2 * math.pi * hour / 24.0),
        hour_cos=np.cos(2 * math.pi * hour / 24.0),
        dow_sin=np.sin(2 * math.pi * times.dt.dayofweek.to_numpy() / 7.0),
        dow_cos=np.cos(2 * math.pi * times.dt.dayofweek.to_numpy() / 7.0),
    )
    out.update(DerivedFeatureGroup().compute(o, h, l, c, v, n_grid, pairs, aux))

    # Gap / market-state flags.
    out["is_gap_bar"] = is_gap_bar_series(times, interval_seconds)
    out["is_partial"] = is_partial_series(df["n_bars"].to_numpy(np.int64), interval_seconds)
    out["is_near_market_close"] = is_near_market_close_series(times, anchor)

    return pd.DataFrame(out, index=df.index)


# 1h background features projected onto the 5m signal layer (spec 3.3).
H1_PROJECTION_TEMPLATES = (
    "ema_dist_{n}", "adx_{n}", "rsi_{n}", "er_{n}", "atr_pct_{n}",
)


def _h1_feature_columns(
    n_grid: tuple[int, ...] = N_GRID, st_mults: tuple[float, ...] = ST_MULTS
) -> list[str]:
    cols: list[str] = []
    for n in n_grid:
        cols += [tmpl.format(n=n) for tmpl in H1_PROJECTION_TEMPLATES]
        cols += [f"st_dir_{n}_{param_tag(m)}" for m in st_mults]  # 1h Supertrend direction
    return cols


def asof_join_h1_features(
    m: pd.DataFrame, h: pd.DataFrame, interval_5m_seconds: int, interval_1h_seconds: int,
    st_mults: tuple[float, ...] = ST_MULTS,
) -> pd.DataFrame:
    """As-of join: 1h row is visible only once its close_time <= the 5m bar's
    close_time (spec 3.3).  Strict, no lookahead.
    """
    m = m.reset_index(drop=True)
    h_close = h["time"].dt.tz_convert("UTC").to_numpy(dtype="datetime64[ns]").astype("int64")
    h_close = h_close + interval_1h_seconds * 1_000_000_000
    m_close = m["time"].dt.tz_convert("UTC").to_numpy(dtype="datetime64[ns]").astype("int64")
    m_close = m_close + interval_5m_seconds * 1_000_000_000
    # Searchsorted on h_close (sorted): position of first h_close > m_close,
    # so idx = pos - 1 is the last 1h bar with close_time <= m_close.
    pos = np.searchsorted(h_close, m_close, side="right")
    valid = pos > 0
    idx = np.full(len(m), -1, dtype=np.int64)
    idx[valid] = pos[valid] - 1

    base_cols = _h1_feature_columns(st_mults=st_mults)
    for col in base_cols:
        src = h[col].to_numpy()
        out = np.full(len(m), np.nan, dtype=np.float64)
        out[valid] = src[idx[valid]]
        m[f"h1_{col}"] = out
    return m


def _read_instrument(
    src: str, instrument: str
) -> pd.DataFrame:
    import duckdb

    conn = duckdb.connect()
    try:
        df = conn.execute(
            "SELECT * FROM read_parquet(?) WHERE instrument = ? ORDER BY time",
            [src, instrument],
        ).fetch_df()
    finally:
        conn.close()
    return df


def _parquet_schema(df: pd.DataFrame) -> pa.Schema:
    """Arrow schema for a feature frame.

    The 8 OHLCV columns keep their source types; explicit flags become int8;
    everything else (all computed features, incl. ``h1_*``) is float32
    (spec section 2: float32 at write time).
    """
    fields = []
    for name in df.columns:
        if name == "instrument":
            fields.append(pa.field(name, pa.string()))
        elif name == "time":
            fields.append(pa.field(name, pa.timestamp("us", tz="UTC")))
        elif name in ("n_bars",):
            fields.append(pa.field(name, pa.int64()))
        elif name in OHLCV_COLS:
            fields.append(pa.field(name, pa.float64()))
        elif name in _FLAG_COLS:
            fields.append(pa.field(name, pa.int8()))
        else:
            fields.append(pa.field(name, pa.float32()))
    return pa.schema(fields)


_FLAG_COLS = ("is_gap_bar", "is_partial", "is_near_market_close")


class _ParquetSink:
    """Append-only Parquet writer that finalises atomically (tmp + rename)."""

    def __init__(self, target: Path, schema: pa.Schema) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        self._tmp = target.with_name(target.stem + ".tmp.parquet")
        self._sink = pa.OSFile(str(self._tmp), "wb")
        self._writer = pq.ParquetWriter(self._sink, schema)
        self._schema = schema
        self.rows = 0

    def write(self, frame: pd.DataFrame) -> None:
        table = pa.table({name: frame[name] for name in self._schema.names},
                         schema=self._schema)
        self._writer.write_table(table, row_group_size=131_072)
        self.rows += table.num_rows

    def finish(self, target: Path) -> int:
        self._writer.close()
        self._sink.close()
        self._tmp.replace(target)
        return self.rows

    def abort(self) -> None:
        try:
            self._writer.close()
        finally:
            self._sink.close()
            if self._tmp.exists():
                self._tmp.unlink()


def _build_one_instrument(
    src5: str,
    src1: str,
    inst: str,
    psar_params: tuple[tuple[float, float], ...] = PSAR_PARAMS,
    st_mults: tuple[float, ...] = ST_MULTS,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Compute the 1h and 5m feature frames for one instrument (warm-up dropped).

    Returns ``(frame_5m, frame_1h)``; both carry the 8 OHLCV columns plus
    computed features (float64).  The 5m frame includes the as-of ``h1_*``
    background columns.
    """
    # ---- 1h features -----------------------------------------------------
    h = _read_instrument(src1, inst)
    if len(h) < WARMUP_DROP + 1:
        raise ValueError(f"{inst}: not enough 1h bars ({len(h)})")
    h_feats = compute_instrument_features(h, 3600, psar_params=psar_params, st_mults=st_mults)
    h_frame = pd.concat([h[list(OHLCV_COLS)], h_feats], axis=1).iloc[WARMUP_DROP:].reset_index(drop=True)

    # ---- 5m features + as-of 1h join -------------------------------------
    m = _read_instrument(src5, inst)
    if len(m) < WARMUP_DROP + 1:
        raise ValueError(f"{inst}: not enough 5m bars ({len(m)})")
    m_feats = compute_instrument_features(m, 300, psar_params=psar_params, st_mults=st_mults)
    m_frame = pd.concat([m[list(OHLCV_COLS)], m_feats], axis=1)
    m_frame = asof_join_h1_features(m_frame, h_frame, 300, 3600, st_mults=st_mults)
    m_frame = m_frame.iloc[WARMUP_DROP:].reset_index(drop=True)
    return m_frame, h_frame


def build_features(
    source_5m: str | Path = "data/ohlcv_5m/ohlcv_5m.parquet",
    source_1h: str | Path = "data/ohlcv_1h/ohlcv_1h.parquet",
    out_5m: str | Path = "data/ohlcv_5m_features/ohlcv_5m_features.parquet",
    out_1h: str | Path = "data/ohlcv_1h_features/ohlcv_1h_features.parquet",
    instruments: list[str] | None = None,
    psar_params: tuple[tuple[float, float], ...] = PSAR_PARAMS,
    st_mults: tuple[float, ...] = ST_MULTS,
) -> dict[str, int]:
    """Regenerate both feature tables, streaming per instrument to disk.

    Computation is float64; written Parquet is float32 (spec section 2).
    Warm-up rows (first WARMUP_DROP bars per instrument) are dropped.  Only one
    instrument's worth of data is held in memory at a time.
    """
    import duckdb

    src5, src1 = str(source_5m), str(source_1h)
    conn = duckdb.connect()
    try:
        insts = sorted(
            r[0] for r in conn.execute(
                "SELECT DISTINCT instrument FROM read_parquet(?) ORDER BY 1", [src5]
            ).fetchall()
        )
    finally:
        conn.close()
    if instruments is not None:
        insts = [i for i in insts if i in set(instruments)]
    if not insts:
        raise ValueError("No instruments selected")

    # Probe the first instrument once to lock both Parquet schemas.
    probe_5m, probe_1h = _build_one_instrument(src5, src1, insts[0], psar_params, st_mults)
    sink_5m = _ParquetSink(Path(out_5m), _parquet_schema(probe_5m))
    sink_1h = _ParquetSink(Path(out_1h), _parquet_schema(probe_1h))
    print(f"{insts[0]}: 5m {len(probe_5m)} rows ({probe_5m.shape[1]} cols) | "
          f"1h {len(probe_1h)} rows ({probe_1h.shape[1]} cols)")
    try:
        sink_5m.write(probe_5m)
        sink_1h.write(probe_1h)
        for inst in insts[1:]:
            m_frame, h_frame = _build_one_instrument(src5, src1, inst, psar_params, st_mults)
            sink_5m.write(m_frame)
            sink_1h.write(h_frame)
            print(f"{inst}: 5m {len(m_frame)} rows | 1h {len(h_frame)} rows")
    except BaseException:
        sink_5m.abort()
        sink_1h.abort()
        raise
    rows_5m = sink_5m.finish(Path(out_5m))
    rows_1h = sink_1h.finish(Path(out_1h))
    print(f"Wrote {out_5m} ({rows_5m} rows, {len(sink_5m._schema.names)} cols)")
    print(f"Wrote {out_1h} ({rows_1h} rows, {len(sink_1h._schema.names)} cols)")
    return {"5m": rows_5m, "1h": rows_1h}


def _parse_psar(spec: str) -> tuple[tuple[float, float], ...]:
    """Parse 'accel:max,accel:max' → ((a1, m1), (a2, m2), ...)."""
    params = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        a_s, m_s = part.split(":")
        params.append((float(a_s), float(m_s)))
    if not params:
        raise ValueError(f"--psar {spec!r} parsed to no parameter sets")
    return tuple(params)


def main(argv: list[str] | None = None) -> None:
    import argparse

    ap = argparse.ArgumentParser(description="Rebuild the 5m/1h feature tables.")
    ap.add_argument("--psar", default=None,
                    help="free PSAR params 'accel:max,accel:max' (default %s)" % (
                        ",".join(f"{a}:{m}" for a, m in PSAR_PARAMS)))
    ap.add_argument("--st-mult", default=None,
                    help="free Supertrend ATR multipliers 'm1,m2' (default %s)" % (
                        ",".join(str(m) for m in ST_MULTS)))
    args = ap.parse_args(argv)
    kwargs: dict = {}
    if args.psar:
        kwargs["psar_params"] = _parse_psar(args.psar)
    if args.st_mult:
        kwargs["st_mults"] = tuple(float(x) for x in args.st_mult.split(",") if x)
    build_features(**kwargs)


if __name__ == "__main__":
    main()
