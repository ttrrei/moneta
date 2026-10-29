"""Data-layer OOS holdout gate (the capability ``run_matrix`` mints after a
successful reservation).

Why this exists (follow-up review of repo_review_20261029)
-----------------------------------------------------------
The one-time OOS gate used to live *only* in ``run_matrix.py``. That left the
data layer wide open: ``strategy_lib.load_bars(until=None)`` (the default) reads
**all** history, so a new script or an AI session could call it directly, tune
on the holdout, and never touch the ledger.

This module closes that hole at the point where the bars are actually read:

* :func:`assert_access` — called by :func:`strategy.strategy_lib.load_bars`
  before any parquet is read. It refuses a window that reaches the holdout
  (``until`` is unset, i.e. "read everything", **or** ``until`` is on/after
  ``oos.holdout_start``) unless the caller holds a valid :class:`OOSToken`.
* :class:`OOSToken` — a small capability object. :func:`create_token` is only
  called by ``run_matrix`` *after* the ledger reservation has been appended, so
  the token is always backed by a real, committed ``reserved``/``completed``
  record.

Verification is deliberately tied to the ledger, so **fabricating a token object
does not open the holdout**: the token must reference the current ``holdout_id``
and there must be a matching ledger consumption record for the strategy. Every
check here *fails closed* — an unreadable config, a wrong-version ledger, or a
token with no backing reservation all raise :class:`SystemExit`.

This module is stdlib-only (json, datetime, pathlib) so it imports cleanly in a
bare CI container; ``yaml`` is imported lazily only when the config is read.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path


class OOSToken:
    """A capability proving the caller is an authorized holdout run.

    Only :func:`create_token` should construct one (``run_matrix`` does so after
    ``_reserve_oos``). It carries the ``strategy`` and ``holdout_id`` it is
    valid for; :func:`assert_access` re-checks both against the config and the
    ledger before it lets holdout data be read.
    """

    __slots__ = ("strategy", "holdout_id")

    def __init__(self, strategy: str, holdout_id: str) -> None:
        self.strategy = strategy
        self.holdout_id = holdout_id

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"OOSToken(strategy={self.strategy!r}, holdout_id={self.holdout_id!r})"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _config_path() -> Path:
    return _repo_root() / "config" / "strategies.yml"


def _ledger_path() -> Path:
    return Path(__file__).resolve().parent / "oos_ledger.json"


def _norm_id(s: str) -> str:
    return (s or "").strip().upper().replace("-", "").replace("_", "")


def _load_config() -> dict:
    import yaml  # lazy: keep the module importable without PyYAML in CI
    with open(_config_path(), encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def _holdout_id() -> str | None:
    oos = _load_config().get("oos") or {}
    hid = oos.get("holdout_id")
    return str(hid) if hid else None


def holdout_start_date() -> date | None:
    """The holdout start (single source: config ``oos.holdout_start``) as a date.

    ``None`` when it is absent / unparseable — in which case there is no
    holdout to protect and :func:`assert_access` is a no-op.
    """
    oos = _load_config().get("oos") or {}
    hs = oos.get("holdout_start")
    if not hs:
        return None
    try:
        return date.fromisoformat(str(hs)[:10])
    except (ValueError, TypeError):
        return None


def _window_reaches_holdout(until: str | None) -> bool:
    """True when a ``load_bars`` window would include holdout bars.

    A window reaches the holdout when ``until`` is unset (reads to the latest
    bar) or its date is on/after the holdout start.
    """
    hs = holdout_start_date()
    if hs is None:
        return False
    if until is None:
        return True
    try:
        d = date.fromisoformat(str(until)[:10])
    except (ValueError, TypeError):
        # An unparseable `until` that is *claiming* to bound the window must not
        # silently be treated as "before the holdout".
        return True
    return d >= hs


def ledger_has_consumption(strategy: str, holdout_id: str) -> bool:
    """True when the committed ledger has a reservation for (strategy, holdout_id).

    Fail closed on a missing / wrong-version / corrupt ledger: a token with no
    backing reservation must not open the holdout.
    """
    p = _ledger_path()
    if not p.exists():
        return False
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    if not isinstance(data, dict) or data.get("version") != _LEDGER_VERSION:
        return False
    cons = data.get("consumptions")
    if not isinstance(cons, list):
        return False
    want_s = _norm_id(strategy)
    for rec in cons:
        if not isinstance(rec, dict):
            continue
        if (_norm_id(rec.get("strategy", "")) == want_s
                and rec.get("holdout_id") == holdout_id
                and rec.get("status") in ("reserved", "completed", "voided")):
            return True
    return False


#: Schema version of strategy/oos_ledger.json (kept in lockstep with
#: ``run_matrix.OOS_LEDGER_VERSION`` so the two agree on what a valid ledger is).
_LEDGER_VERSION = 1


def create_token(strategy: str, holdout_id: str) -> OOSToken:
    """Mint an :class:`OOSToken`. ``run_matrix`` calls this only *after*
    ``_reserve_oos`` has appended a committed record, so every real token is
    backed by the ledger."""
    return OOSToken(strategy=strategy, holdout_id=holdout_id)


def assert_access(until: str | None, token: OOSToken | None) -> None:
    """Fail closed if a ``load_bars`` window reaches the holdout without a
    valid token (the data-layer gate, see module docstring).

    An in-sample window (``until`` strictly before the holdout) is always
    allowed and needs no token. A window that reaches the holdout requires a
    token that (a) references the current ``holdout_id`` and (b) has a matching
    ledger reservation for the strategy — otherwise :class:`SystemExit`.
    """
    if not _window_reaches_holdout(until):
        return

    if token is None:
        hs = holdout_start_date()
        raise SystemExit(
            "Refusing to load a window that reaches the OOS holdout "
            f"(holdout_start={hs}): the request (until={until!r}) would include "
            "holdout data, but no OOS token was supplied. Only a reserved "
            "run_matrix OOS holdout run may read the holdout. (The gate now "
            "lives in the data layer, not just run_matrix.)")

    hid = _holdout_id()
    if not hid or not getattr(token, "holdout_id", None):
        raise SystemExit("OOS token present but no holdout id resolvable; "
                         "refusing to load the holdout (fail closed).")
    if token.holdout_id != hid:
        raise SystemExit(
            f"OOS token references holdout {token.holdout_id!r} but the current "
            f"holdout is {hid!r}; refusing to load (fail closed).")
    strat = getattr(token, "strategy", "")
    if not ledger_has_consumption(strat, hid):
        raise SystemExit(
            "OOS token does not correspond to a ledger reservation for "
            f"({strat!r}, {hid!r}); refusing to load the holdout (fail closed). "
            "A fabricated token cannot open the holdout.")


__all__ = [
    "OOSToken",
    "create_token",
    "assert_access",
    "holdout_start_date",
    "ledger_has_consumption",
]
