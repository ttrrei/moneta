"""Profile checks for the 1-minute / 5-minute / 1-hour parquet tables.

``sanity_check.py`` answers "is anything broken?".  This script answers the
questions that need judgement before strategy discovery, and prints a verdict
line where the data allows one:

  gaps       Which gaps are routine (weekends, daily breaks), which are one-offs,
             and which one-offs look like LOST DATA (peer instruments kept trading)?
  sessions   When do sessions open/close in UTC?  Do they line up with 1h buckets?
             Is ``time`` the bar open or the bar close?
  partial    How many 5m/1h bars are partial, where (session edge vs mid-session),
             and how many bars survive at each n_bars threshold?
  lookahead  Naive vs safe 1h->5m join: shows the leak, verifies the safe join has none.
  spread     Bid/ask cost per instrument (the aggregated bars drop bid/ask).
  quality    Stale (identical-close) runs, flat/zero-volume bars, one-bar price
             spikes that immediately revert.
  raw        (--raw) Reconcile raw CSVs with the parquet and count conflicting
             duplicates.  Slow: scans every raw CSV once.

Run from the repo root::

    python pipeline/profile_check.py                  # all sections except raw
    python pipeline/profile_check.py --only gaps,partial
    python pipeline/profile_check.py --raw

For the strategy stage, ``safe_mtf_view`` builds a 5m table with the last
*closed* 1h bar attached (no look-ahead)::

    from pipeline.profile_check import safe_mtf_view
    safe_mtf_view(conn)            # creates view m5_with_h1
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import duckdb

ONE_MIN = Path("data/all_data/all_data.parquet")
M5 = Path("data/ohlcv_5m/ohlcv_5m.parquet")
H1 = Path("data/ohlcv_1h/ohlcv_1h.parquet")
RAW_GLOB = "data/raw_csv/**/*.csv"

# Instruments that trade on the same schedule.  Used to tell a closure (peers
# silent too) from lost data (peers kept trading).  Edit freely; instruments
# not listed here (HK33, JP225, CN50 ...) simply have no peers.
PEER_GROUPS = [
    ["AUD_USD", "EUR_USD", "GBP_USD", "NZD_USD", "USD_CAD", "USD_CHF", "USD_JPY"],
    ["BTC_USD", "ETH_USD"],
    ["XAU_USD", "XAG_USD"],
    ["BCO_USD", "WTICO_USD"],
    ["NAS100_USD", "SPX500_USD", "US30_USD"],
    ["DE30_EUR", "UK100_GBP"],
]
MIN_GAP_MIN = 60         # only gaps at least this long are analysed
ROUTINE_MIN_WEEKS = 6    # a gap recurring at the same weekly slot in >= N other weeks is routine
PEERS_ACTIVE_FRAC = 0.5  # one-off gap with >= this share of peers trading => likely lost data
SPIKE_SIGMA = 20         # 1-min return > N robust sigmas AND >= 70% reverted next minute


def _src(path: Path) -> str:
    return f"read_parquet('{path.as_posix()}')"


def _title(text: str) -> None:
    print(f"\n{'=' * 10} {text} {'=' * 10}")


def _show(rel) -> None:
    rel.show(max_rows=300, max_width=240)


# --------------------------------------------------------------------------- gaps
def gaps(conn) -> None:
    _title(f"gaps >= {MIN_GAP_MIN} min: routine vs one-off vs lost data (1-minute)")
    conn.execute(f"""
        CREATE OR REPLACE TEMP TABLE gaps AS
        SELECT instrument, prev AS gap_start, time AS gap_end, time - prev AS gap,
               date_trunc('week', prev) AS wk,
               dayofweek(prev) * 48 + (hour(prev) * 60 + minute(prev)) // 30 AS slot
        FROM (SELECT instrument, time,
                     lag(time) OVER (PARTITION BY instrument ORDER BY time) AS prev
              FROM one_min)
        WHERE time - prev >= INTERVAL {MIN_GAP_MIN} MINUTE""")
    # Routine = the same instrument has a gap at (about) the same weekly slot in other weeks.
    conn.execute("""
        CREATE OR REPLACE TEMP TABLE gap_class AS
        SELECT g.*, (SELECT count(DISTINCT h.wk) FROM gaps h
                     WHERE h.instrument = g.instrument AND h.wk <> g.wk
                       AND least(abs(h.slot - g.slot), 336 - abs(h.slot - g.slot)) <= 1) AS similar_weeks
        FROM gaps g""")
    present = {r[0] for r in conn.execute("SELECT DISTINCT instrument FROM one_min").fetchall()}
    conn.execute("CREATE OR REPLACE TEMP TABLE peers(instrument VARCHAR, peer VARCHAR)")
    pairs = [(a, b) for grp in PEER_GROUPS for a in grp for b in grp
             if a != b and a in present and b in present]
    conn.executemany("INSERT INTO peers VALUES (?, ?)", pairs)
    conn.execute("""CREATE OR REPLACE TEMP TABLE inst_range AS
                    SELECT instrument, min(time) AS first_t, max(time) AS last_t FROM one_min GROUP BY 1""")
    # For every one-off gap: how many peers (that have data covering the gap) have a bar inside it?
    conn.execute(f"""
        CREATE OR REPLACE TEMP TABLE gap_peers AS
        SELECT g.instrument, g.gap_start, g.gap_end, g.gap_end - g.gap_start AS gap,
               count(r.instrument) AS peers, count(*) FILTER (nxt.time < g.gap_end) AS peers_active
        FROM (SELECT * FROM gap_class WHERE similar_weeks < {ROUTINE_MIN_WEEKS}) g
        LEFT JOIN peers p ON p.instrument = g.instrument
        LEFT JOIN inst_range r ON r.instrument = p.peer AND r.first_t <= g.gap_start AND r.last_t >= g.gap_end
        ASOF LEFT JOIN one_min nxt ON nxt.instrument = r.instrument AND g.gap_start < nxt.time
        GROUP BY g.instrument, g.gap_start, g.gap_end""")
    _show(conn.sql(f"""
        SELECT c.instrument, count(*) AS gaps,
               count(*) FILTER (c.similar_weeks >= {ROUTINE_MIN_WEEKS}) AS routine,
               count(*) FILTER (c.similar_weeks < {ROUTINE_MIN_WEEKS}) AS one_off,
               count(*) FILTER (gp.peers > 0 AND gp.peers_active >= {PEERS_ACTIVE_FRAC} * gp.peers) AS likely_lost,
               max(c.gap) FILTER (c.similar_weeks < {ROUTINE_MIN_WEEKS}) AS longest_one_off
        FROM gap_class c LEFT JOIN gap_peers gp
          ON gp.instrument = c.instrument AND gp.gap_start = c.gap_start
        GROUP BY 1 ORDER BY 1"""))
    verdict = f"""
        CASE WHEN peers = 0 THEN 'no peers: holiday or lost? check manually'
             WHEN peers_active >= {PEERS_ACTIVE_FRAC} * peers THEN 'LIKELY LOST DATA (peers kept trading)'
             ELSE 'closure (peers silent too)' END"""
    print("\nLongest 3 one-off gaps per instrument:")
    _show(conn.sql(f"""
        SELECT instrument, gap_start::VARCHAR AS gap_start, gap_end::VARCHAR AS gap_end, gap,
               peers, peers_active, {verdict} AS verdict
        FROM (SELECT *, row_number() OVER (PARTITION BY instrument ORDER BY gap DESC) AS rn FROM gap_peers)
        WHERE rn <= 3 ORDER BY instrument, gap DESC"""))
    lost = conn.sql(f"""
        SELECT instrument, gap_start::VARCHAR AS gap_start, gap_end::VARCHAR AS gap_end, gap, peers, peers_active
        FROM gap_peers WHERE peers > 0 AND peers_active >= {PEERS_ACTIVE_FRAC} * peers
        ORDER BY gap DESC LIMIT 40""")
    rows = lost.fetchall()
    if rows:
        print(f"\nVERDICT: {len(rows)} one-off gap(s) look like lost data (peers kept trading) - re-pull these:")
        _show(lost)
    else:
        print("\nVERDICT: no one-off gap looks like lost data (every gap with peers coincided with peer silence).")


# ------------------------------------------------------------------------ sessions
def sessions(conn) -> None:
    _title("sessions: UTC open/close times and bar-time labelling")
    if conn.execute("SELECT count(*) FROM information_schema.tables WHERE table_name = 'gaps'").fetchone()[0] == 0:
        print("(run the 'gaps' section first)")
        return
    q = conn.sql("""
        SELECT instrument, count(*) AS breaks,
               mode(strftime(gap_end, '%H:%M')) AS common_open_utc,
               round(100.0 * count(*) FILTER (minute(gap_end) BETWEEN 10 AND 49) / count(*), 1) AS pct_open_off_hour,
               mode(strftime(gap_start, '%H:%M')) AS common_last_bar_utc,
               round(100.0 * count(*) FILTER (minute(gap_start) % 15 = 14) / count(*), 1) AS pct_last_bar_open_style
        FROM gaps GROUP BY 1 ORDER BY 1""")
    rows = q.fetchall()
    _show(q)
    off = [r[0] for r in rows if r[3] is not None and r[3] >= 30]
    if off:
        print(f"\nVERDICT: sessions of {', '.join(off)} often open mid-hour -> UTC 1h buckets split the "
              "first hour of those sessions (partial 1h bars). Consider anchoring 1h buckets per instrument.")
    else:
        print("\nVERDICT: session opens line up with hour boundaries; UTC 1h buckets are fine.")
    print("Labelling: pct_last_bar_open_style = share of sessions whose last bar is stamped one minute before a "
          "quarter hour (20:59, 08:29 ...).\nHigh => `time` is the bar OPEN time (a bar stamped 20:59 covers "
          "20:59-21:00). Near 0 with last bars at ':00'/':15' => `time` may be the bar close and the 1h->5m "
          "availability rule must change.")


# -------------------------------------------------------------------------- partial
def partial(conn) -> None:
    for name, path, step, full in (("5m", M5, "5 minutes", 5), ("1h", H1, "1 hour", 60)):
        _title(f"partial bars: {name} (full bar = {full} one-minute bars)")
        if not path.exists():
            print(f"missing: {path}")
            continue
        k80, k60 = -(-full * 4 // 5), -(-full * 3 // 5)
        edge = (f"(prev_t IS NULL OR time - prev_t > INTERVAL '{step}' "
                f"OR next_t IS NULL OR next_t - time > INTERVAL '{step}')")
        conn.execute(f"""
            CREATE OR REPLACE TEMP TABLE partial_{name} AS
            WITH b AS (SELECT instrument, time, n_bars,
                              lag(time) OVER w AS prev_t, lead(time) OVER w AS next_t
                       FROM {_src(path)} WINDOW w AS (PARTITION BY instrument ORDER BY time))
            SELECT instrument, count(*) AS bars,
                   count(*) FILTER (n_bars < {full}) AS partial,
                   count(*) FILTER (n_bars < {full} AND {edge}) AS at_session_edge,
                   count(*) FILTER (n_bars < {full} AND NOT {edge}) AS mid_session,
                   round(100.0 * count(*) FILTER (n_bars >= {full}) / count(*), 1) AS kept_ge_{full},
                   round(100.0 * count(*) FILTER (n_bars >= {k80}) / count(*), 1) AS kept_ge_{k80},
                   round(100.0 * count(*) FILTER (n_bars >= {k60}) / count(*), 1) AS kept_ge_{k60}
            FROM b GROUP BY 1 ORDER BY 1""")
        _show(conn.sql(f"SELECT * FROM partial_{name}"))
        mid = [r[0] for r in conn.execute(
            f"SELECT instrument FROM partial_{name} WHERE mid_session > at_session_edge AND partial > 0.02 * bars").fetchall()]
        edg = [r[0] for r in conn.execute(
            f"SELECT instrument FROM partial_{name} WHERE at_session_edge >= mid_session AND partial > 0.02 * bars").fetchall()]
        if mid:
            print(f"Mostly MID-SESSION partials (thin trading, minutes without ticks): {', '.join(mid)}")
        if edg:
            print(f"Mostly SESSION-EDGE partials (bucket alignment / session start-end): {', '.join(edg)}")
        print(f"Pick a rule per use: kept_ge_{full} = strict; kept_ge_{k80} / kept_ge_{k60} = tolerate thin minutes. "
              "Choose where kept% stops dropping sharply.")


# ------------------------------------------------------------------------ lookahead
def safe_mtf_view(conn, m5: Path = M5, h1: Path = H1, name: str = "m5_with_h1") -> str:
    """Create *name*: every 5m row plus the last CLOSED 1h bar (no look-ahead).

    ``time`` is the bar open, so a 1h bar stamped 10:00 closes (is usable) at
    11:00.  Extra columns: ``h1_time`` (bar open), ``h1_n_bars`` and
    ``h1_age_min`` (minutes since that 1h bar closed; > 60 means the previous
    hour is missing, i.e. the feature is stale).  Filter on those as needed.
    """
    conn.execute(f"""
        CREATE OR REPLACE VIEW {name} AS
        SELECT f.*, h.time AS h1_time, h.open AS h1_open, h.high AS h1_high, h.low AS h1_low,
               h.close AS h1_close, h.volume AS h1_volume, h.n_bars AS h1_n_bars,
               date_diff('minute', h.avail, f.time) AS h1_age_min
        FROM {_src(m5)} f
        ASOF LEFT JOIN (SELECT *, time + INTERVAL '1 hour' AS avail FROM {_src(h1)}) h
          ON f.instrument = h.instrument AND f.time >= h.avail""")
    return name


def lookahead(conn) -> None:
    _title("look-ahead: 1h features attached to 5m rows")
    if not (M5.exists() and H1.exists()):
        print("missing 5m/1h parquet")
        return
    view = safe_mtf_view(conn)
    naive_total, naive_leak = conn.execute(f"""
        WITH n AS (SELECT f.time AS t, h.time AS ht FROM {_src(M5)} f
                   ASOF LEFT JOIN {_src(H1)} h ON f.instrument = h.instrument AND f.time >= h.time)
        SELECT count(*), count(*) FILTER (ht + INTERVAL '1 hour' > t) FROM n""").fetchone()
    safe_leak = conn.execute(
        f"SELECT count(*) FROM {view} WHERE h1_time + INTERVAL '1 hour' > time").fetchone()[0]
    print(f"naive join (1h bar with start <= 5m start): {naive_leak:,} of {naive_total:,} rows "
          f"({100.0 * naive_leak / max(naive_total, 1):.1f}%) use a 1h bar that has not closed yet")
    print(f"safe join (1h bar with end <= 5m start):    {safe_leak:,} rows leak -> "
          f"{'PASS' if safe_leak == 0 else 'FAIL'}")
    print("\nStaleness of the attached 1h bar (use h1_age_min / h1_n_bars in the view to filter):")
    _show(conn.sql(f"""
        SELECT instrument, count(*) AS rows,
               round(100.0 * count(*) FILTER (h1_time IS NULL) / count(*), 2) AS pct_no_1h,
               round(100.0 * count(*) FILTER (h1_age_min > 60) / count(*), 2) AS pct_1h_older_than_60m,
               round(100.0 * count(*) FILTER (h1_n_bars < 60) / count(*), 2) AS pct_1h_partial
        FROM {view} GROUP BY 1 ORDER BY 1"""))
    print("\nUse `safe_mtf_view(conn)` in the strategy stage; never join 1h to 5m on time <= time.")


# --------------------------------------------------------------------------- spread
def spread(conn) -> None:
    _title("spread: bid/ask cost from the 1-minute table (bps of mid close)")
    cols = {r[0] for r in conn.execute("DESCRIBE SELECT * FROM one_min").fetchall()}
    if not {"bid_c", "ask_c", "mid_c"} <= cols:
        print("bid_c / ask_c / mid_c not present - skipped")
        return
    _show(conn.sql("""
        SELECT instrument, round(median(s), 2) AS median_bps, round(quantile_cont(s, 0.95), 2) AS p95_bps,
               round(max(s), 1) AS max_bps, count(*) FILTER (ask_c < bid_c) AS crossed,
               count(*) FILTER (ask_c = bid_c) AS zero_spread, count(*) FILTER (bid_c IS NULL OR ask_c IS NULL) AS null_quote
        FROM (SELECT instrument, bid_c, ask_c, (ask_c - bid_c) / mid_c * 10000 AS s FROM one_min)
        GROUP BY 1 ORDER BY 1"""))
    print("\nmedian_bps is a per-fill cost proxy for the backtest (mid-price backtests ignore it); "
          "p95_bps shows how bad thin periods get.\ncrossed > 0 (ask < bid) is a data error.")


# -------------------------------------------------------------------------- quality
def quality(conn) -> None:
    _title("quality: stale runs, flat bars, reverting spikes (1-minute)")
    _show(conn.sql("""
        WITH a AS (SELECT instrument, time, mid_c,
                          mid_c IS DISTINCT FROM lag(mid_c) OVER (PARTITION BY instrument ORDER BY time) AS chg
                   FROM one_min),
             b AS (SELECT instrument, time, sum(chg::INT) OVER (PARTITION BY instrument ORDER BY time) AS grp FROM a),
             r AS (SELECT instrument, grp, count(*) AS run, min(time) AS start FROM b GROUP BY 1, 2),
             lr AS (SELECT instrument, max(run) AS longest_identical_close_run, arg_max(start::VARCHAR, run) AS run_start
                    FROM r GROUP BY 1),
             f AS (SELECT instrument,
                          round(100.0 * count(*) FILTER (mid_o = mid_h AND mid_h = mid_l AND mid_l = mid_c) / count(*), 2) AS flat_bar_pct,
                          round(100.0 * count(*) FILTER (volume = 0) / count(*), 2) AS zero_volume_pct
                   FROM one_min GROUP BY 1)
        SELECT instrument, flat_bar_pct, zero_volume_pct, longest_identical_close_run, run_start
        FROM f JOIN lr USING (instrument) ORDER BY 1"""))
    conn.execute(f"""
        CREATE OR REPLACE TEMP TABLE spikes AS
        WITH r AS (SELECT instrument, time,
                          CASE WHEN time - lag(time) OVER w = INTERVAL 1 MINUTE
                               THEN ln(mid_c / lag(mid_c) OVER w) END AS r0
                   FROM one_min WHERE mid_c > 0 WINDOW w AS (PARTITION BY instrument ORDER BY time)),
             s AS (SELECT instrument, 1.4826 * median(abs(r0)) FILTER (abs(r0) > 0) AS sigma FROM r GROUP BY 1),
             x AS (SELECT r.instrument, time, r0, sigma,
                          lead(r0) OVER (PARTITION BY r.instrument ORDER BY time) AS r1
                   FROM r JOIN s USING (instrument))
        SELECT instrument, time, round(r0 * 10000, 1) AS jump_bps,
               round(100 * (1 - abs(r0 + r1) / abs(r0)), 0) AS reverted_pct
        FROM x WHERE sigma > 0 AND abs(r0) > {SPIKE_SIGMA} * sigma AND r1 IS NOT NULL
              AND sign(r0) <> sign(r1) AND abs(r0 + r1) < 0.3 * abs(r0)""")
    total = conn.execute("SELECT count(*) FROM spikes").fetchone()[0]
    if total == 0:
        print(f"\nVERDICT: no one-bar spike (> {SPIKE_SIGMA} sigma, >= 70% reverted next minute) found.")
        return
    print(f"\nVERDICT: {total} one-bar spike(s) that reverted - bad ticks or real flash moves; inspect the largest:")
    _show(conn.sql("SELECT instrument, count(*) AS spikes FROM spikes GROUP BY 1 ORDER BY 2 DESC"))
    _show(conn.sql("SELECT instrument, time::VARCHAR AS time, jump_bps, reverted_pct FROM spikes "
                   "ORDER BY abs(jump_bps) DESC LIMIT 15"))


# ----------------------------------------------------------------------------- raw
def raw(conn) -> None:
    _title("raw CSVs vs parquet (scans every CSV once; may take a minute)")
    n_files = len(list(Path(RAW_GLOB.split("**")[0]).rglob("*.csv")))
    if n_files == 0:
        print(f"no CSVs under {RAW_GLOB}")
        return
    row = conn.execute(f"""
        WITH k AS (SELECT instrument, time, count(*) AS copies,
                          count(*) FILTER (is_complete) AS complete_copies,
                          count(*) FILTER (NOT is_complete) AS incomplete_copies,
                          count(*) FILTER (is_complete IS NULL) AS null_copies,
                          count(DISTINCT (mid_o, mid_h, mid_l, mid_c, volume)) FILTER (is_complete) AS distinct_values
                   FROM read_csv('{RAW_GLOB}', header = TRUE, union_by_name = TRUE) GROUP BY 1, 2)
        SELECT sum(copies), count(*), count(*) FILTER (complete_copies > 0), sum(incomplete_copies), sum(null_copies),
               count(*) FILTER (distinct_values > 1), round(avg(copies), 2), max(copies)
        FROM k""").fetchone()
    raw_rows, keys, keys_ok, incomplete, nulls, conflicts, avg_copies, max_copies = row
    parquet_rows = conn.execute("SELECT count(*) FROM one_min").fetchone()[0]
    print(f"CSV files: {n_files} | raw rows: {raw_rows:,} | distinct (instrument, time): {keys:,}")
    print(f"copies per key: avg {avg_copies}, max {max_copies}")
    print(f"is_complete = false rows: {incomplete:,} | is_complete NULL rows: {nulls:,}")
    print(f"keys with >= 1 complete row: {keys_ok:,} | parquet rows: {parquet_rows:,} -> "
          f"{'MATCH (no silent row loss)' if keys_ok == parquet_rows else f'MISMATCH (delta {keys_ok - parquet_rows:,})'}")
    print(f"keys whose complete duplicates DISAGREE on OHLC/volume: {conflicts:,} -> "
          f"{'duplicates are harmless copies; the dedup tie-break does not matter' if conflicts == 0 else 'DEDUP CHOICE MATTERS: resolve these before trusting the data'}")


SECTIONS = {"gaps": gaps, "sessions": sessions, "partial": partial, "lookahead": lookahead,
            "spread": spread, "quality": quality, "raw": raw}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--only", help=f"comma-separated subset of: {','.join(SECTIONS)}")
    ap.add_argument("--raw", action="store_true", help="also run the (slow) raw CSV reconciliation")
    args = ap.parse_args()
    wanted = [s.strip() for s in args.only.split(",")] if args.only else [s for s in SECTIONS if s != "raw"]
    if args.raw and "raw" not in wanted:
        wanted.append("raw")
    unknown = [s for s in wanted if s not in SECTIONS]
    if unknown:
        ap.error(f"unknown section(s): {unknown}")
    if not ONE_MIN.exists():
        print(f"missing: {ONE_MIN}")
        return 1
    conn = duckdb.connect()
    conn.execute("SET TimeZone = 'UTC'")
    conn.execute(f"CREATE VIEW one_min AS SELECT * FROM {_src(ONE_MIN)}")
    if "sessions" in wanted and "gaps" not in wanted:
        wanted.insert(wanted.index("sessions"), "gaps")  # sessions reuses the gap table
    for name in wanted:
        SECTIONS[name](conn)
    return 0


if __name__ == "__main__":
    sys.exit(main())