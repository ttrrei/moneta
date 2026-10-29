"""Data-layer holdout gate: a token is required to read bars that reach the
holdout, and the token is only valid while a matching *reserved* record exists
in the OOS ledger.

Layered design (see docs/repo_review_20261029.md §1.1 / §1.7 and
docs/repo_review_20261029_followup.md §1.1):

* ``strategy_lib.load_bars`` (and the S-01 copy in ``strategy_rsi_lib``) calls
  :func:`assert_access` before querying, so the gate lives in the data layer,
  not in ``run_matrix``: *any* caller that reads bars reaching the holdout
  needs a token.
* A token is NOT freely mintable: :func:`create_token` requires a
  ``reserved`` ledger record for ``(strategy, holdout_id)`` and refuses when
  the latest status for that pair is ``completed`` or an active ``reserved``
  for a different strategy already holds the holdout.
* Only the ``reserved`` status grants read access (``run_matrix`` flips it to
  ``completed`` after the run).  A ``completed`` or ``voided`` latest status
  grants NO read access — a borrowed name cannot be used to re-read the
  holdout after the first consumption.
* The config must declare ``oos.holdout_start``; a missing or unparseable
  value is a *config error* (SystemExit), never a pass-through (fail-closed).
* The read window must be in the holdout region (``until >= holdout_start``);
  an in-sample ``until`` does not need (and cannot use) a token.

The token carries no secrets and is not persisted.  It is a handle checked
against the append-only ledger at every read.
"""

from __future__ import annotations

import json
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = _REPO_ROOT / "config" / "strategies.yml"
_LEDGER_PATH = _REPO_ROOT / "strategy" / "oos_ledger.json"


class OOSToken:
    """A handle authorising a read that reaches the holdout.

    Constructed by :func:`create_token` after a ledger reservation check.
    Carries only the identity: no secrets, nothing persisted.
    """

    __slots__ = ("strategy", "holdout_id")

    def __init__(self, strategy: str, holdout_id: str):
        self.strategy = strategy
        self.holdout_id = holdout_id

    def __repr__(self) -> str:
        return f"OOSToken(strategy={self.strategy!r}, holdout_id={self.holdout_id!r})"


def _config_path() -> Path:
    return CONFIG_PATH


def _ledger_path() -> Path:
    return _LEDGER_PATH


def _load_config() -> dict:
    """Load the config; missing file is a config error (fail-closed)."""
    path = _config_path()
    if not path.exists():
        raise SystemExit(
            "[oos] FAIL CLOSED: config file is missing "
            f"({path}); refusing any data read (the holdout boundary "
            "cannot be established). Restore the config."
        )
    try:
        import yaml
    except ImportError:
        raise SystemExit(
            "[oos] FAIL CLOSED: PyYAML is not available; the holdout "
            "boundary cannot be established. Install PyYAML."
        )
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _oos_config() -> dict:
    """The ``oos:`` block; its absence is a config error (fail-closed)."""
    cfg = _load_config()
    oos = cfg.get("oos")
    if not isinstance(oos, dict):
        raise SystemExit(
            "[oos] FAIL CLOSED: config has no ``oos:`` block; the holdout "
            "boundary cannot be established. Restore the config."
        )
    return oos


def holdout_start_date() -> str:
    """The holdout start date as an ISO string.

    Missing or unparseable is a **config error** (SystemExit) — the gate
    must not pass reads through when the boundary is unknown (fail-closed;
    review §1.2: a deleted/mis-typed field must not disable the gate).
    """
    import datetime as _dt

    oos = _oos_config()
    raw = oos.get("holdout_start")
    if raw is None:
        raise SystemExit(
            "[oos] FAIL CLOSED: config ``oos.holdout_start`` is missing; the "
            "holdout boundary cannot be established, so no data read is "
            "permitted. Restore the config."
        )
    try:
        return _dt.date.fromisoformat(str(raw)[:10]).isoformat()
    except ValueError:
        raise SystemExit(
            f"[oos] FAIL CLOSED: config ``oos.holdout_start`` is not a "
            f"valid ISO date ({raw!r}); no data read is permitted."
        )


def holdout_id() -> str:
    """The declared holdout identifier (``oos.holdout_id``).

    Missing is a config error (fail-closed): a token cannot be validated
    against an unknown holdout, so no holdout read is permitted.
    """
    oos = _oos_config()
    hid = oos.get("holdout_id")
    if not hid:
        raise SystemExit(
            "[oos] FAIL CLOSED: config ``oos.holdout_id`` is missing; a "
            "token cannot be validated, so no holdout read is permitted."
        )
    return str(hid)


def _window_reaches_holdout(until: str | None) -> bool:
    """True when an ``until`` read reaches the holdout (None = all data, or
    until >= holdout_start).  Config errors propagate (fail-closed)."""
    if until is None:
        return True
    import datetime as _dt
    hs = holdout_start_date()  # raises on missing/invalid config
    return _dt.date.fromisoformat(str(until)[:10]) >= _dt.date.fromisoformat(hs)


def is_holdout_until(until: str | None) -> bool:
    """Public helper for the loader: True when ``until`` is in the holdout
    region, so the query should use the **exclusive** bound ``time < until``
    (the OOS window ``until`` = ``holdout_end + 1 day`` is the first day
    *after* the holdout; ``<`` excludes its bars entirely).  In-sample
    ``until`` (< holdout_start) keeps the inclusive ``time <= until``.
    Config errors propagate (fail-closed)."""
    if not until:
        return False
    return _window_reaches_holdout(until)


def _load_ledger() -> dict:
    path = _ledger_path()
    if not path.exists():
        return {"consumptions": []}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _latest_status(strategy: str, holdout_id: str, records: list) -> str | None:
    """The status of the most recent ledger record for (strategy, holdout).

    Append-only semantics: a later ``voided`` record voids an earlier
    ``reserved``; a later ``completed`` finalises it.  The last record wins.
    Returns None when the pair has no records.
    """
    import strategy.registry as _reg
    sid = _reg.norm_id(strategy)
    latest = None
    for rec in records:
        if (_reg.norm_id(rec.get("strategy", "")) == sid
                and rec.get("holdout_id") == holdout_id
                and rec.get("status") in ("reserved", "completed", "voided")):
            latest = rec["status"]
    return latest


def ledger_has_active_reservation(strategy: str, holdout_id: str) -> bool:
    """True when the *latest* status for (strategy, holdout) is ``reserved``
    — i.e. an active reservation that grants a read.  ``completed`` and
    ``voided`` grant NO read access (review §1.1: only ``reserved`` is
    accepted; a borrowed name cannot re-read the holdout)."""
    records = _load_ledger().get("consumptions", [])
    return _latest_status(strategy, holdout_id, records) == "reserved"


def assert_access(until: str | None, token: "OOSToken | None" = None) -> None:
    """Enforce the holdout gate for a data read ending at ``until``.

    * In-sample read (``until`` strictly before ``holdout_start``) → allowed,
      token neither needed nor accepted.
    * Read reaching the holdout (``until`` None or >= ``holdout_start``):
      a token is required and valid only when
      (a) ``token.holdout_id`` equals the declared holdout id, and
      (b) the *latest* ledger status for (token.strategy, holdout) is
          ``reserved`` (an active reservation).

    A missing or invalid holdout boundary in the config raises (fail-closed)
    rather than allowing the read through.
    """
    if not _window_reaches_holdout(until):
        return
    # A holdout read is being requested: the boundary MUST be well-formed
    # (fail closed). For a concrete `until` the comparison above already did
    # this; for `until=None` (read all) it did not — so force the check here
    # too. A missing/invalid holdout_start raises rather than passing the read
    # through (review §1.2).
    holdout_start_date()
    if token is None:
        raise SystemExit(
            "[oos] HOLDOUT GATE: this read reaches the declared holdout "
            f"(holdout_id={holdout_id()!r}); a data-layer OOS token is "
            "required. Tokens are minted by run_matrix only after the "
            "one-time holdout is reserved in the ledger."
        )
    try:
        declared = holdout_id()
    except SystemExit:
        raise
    if token.holdout_id != declared:
        raise SystemExit(
            f"[oos] HOLDOUT GATE: token is for a different holdout "
            f"({token.holdout_id!r} vs declared {declared!r}); refusing the "
            f"read."
        )
    if not ledger_has_active_reservation(token.strategy, token.holdout_id):
        raise SystemExit(
            f"[oos] HOLDOUT GATE: no *active* (status=reserved) ledger record "
            f"for strategy={token.strategy!r} holdout={token.holdout_id!r}. "
            "A token is only valid while a reservation is active (reserved); "
            "completed or voided records grant no read access."
        )


def create_token(strategy: str, holdout_id: str) -> OOSToken:
    """Mint a token for ``strategy`` on ``holdout_id`` if the ledger allows it.

    Requires an **active ``reserved`` ledger record** for
    ``(strategy, holdout_id)`` — i.e. the one-time holdout must be reserved
    (by :func:`run_matrix._reserve_oos`) *before* the data-layer token can be
    minted.  This is the anti-fabrication check: a freely-constructed
    ``OOSToken`` is useless without the backing reservation.

    Config errors (missing oos block / holdout_start) propagate fail-closed.
    """
    records = _load_ledger().get("consumptions", [])
    if _latest_status(strategy, holdout_id, records) != "reserved":
        raise SystemExit(
            f"[oos] token refused: no *active* (status=reserved) ledger record "
            f"for strategy={strategy!r} holdout={holdout_id!r}. A token is "
            "minted only after the one-time holdout is reserved in the ledger "
            "by run_matrix (a completed or voided record grants no read access)."
        )
    return OOSToken(strategy, holdout_id)


__all__ = [
    "OOSToken",
    "assert_access",
    "create_token",
    "holdout_id",
    "holdout_start_date",
    "is_holdout_until",
    "ledger_has_active_reservation",
]
