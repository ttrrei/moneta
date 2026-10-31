"""Freeze implementation/configuration and opaque data bytes before nomination.

No market rows are decoded here. A nomination metadata commit may follow the
implementation commit, provided it changes none of the frozen implementation
or evaluation settings. Only new nomination fields are excluded from hashing.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from copy import deepcopy
from pathlib import Path

FREEZE_FIELDS = ("oos_code_commit", "oos_code_hash", "oos_dirty", "oos_data_fingerprint")
NOMINATION_FIELDS = (*FREEZE_FIELDS, "oos_variant", "oos_config_hash")


def freeze_shape_error(spec: dict) -> str | None:
    if not isinstance(spec.get("oos_code_commit"), str) or not re.fullmatch(
            r"[0-9a-f]{40}", spec["oos_code_commit"]):
        return "oos_code_commit must be a full Git SHA"
    if not isinstance(spec.get("oos_code_hash"), str) or not re.fullmatch(
            r"[0-9a-f]{64}", spec["oos_code_hash"]):
        return "oos_code_hash must freeze the implementation and evaluation settings"
    if spec.get("oos_dirty") is not False:
        return "oos_dirty must be false"
    data = spec.get("oos_data_fingerprint")
    if not isinstance(data, dict) or not isinstance(data.get("sha256"), str) \
            or re.fullmatch(r"[0-9a-f]{64}", data["sha256"]) is None \
            or type(data.get("size_bytes")) is not int or data["size_bytes"] <= 0:
        return "oos_data_fingerprint requires a SHA-256 and positive size_bytes"
    return None


def git_state(root: Path) -> dict:
    try:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root,
                                         text=True, stderr=subprocess.DEVNULL).strip()
        dirty = bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=root, text=True))
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ValueError("Git provenance unavailable; refusing nomination/OOS") from exc
    return {"git_commit": commit, "dirty": dirty}


def code_fingerprint(root: Path, cfg: dict) -> str:
    files = subprocess.check_output(
        ["git", "ls-files", "-z", "strategy", "pipeline", "library", "config/indicators.yml"],
        cwd=root).decode().split("\0")
    hashes = {name: hashlib.sha256((root / name).read_bytes()).hexdigest()
              for name in files if name and (name.endswith(".py") or name == "config/indicators.yml")}
    evaluation = deepcopy(cfg)
    for spec in (evaluation.get("strategies") or {}).values():
        for field in NOMINATION_FIELDS:
            spec.pop(field, None)
    payload = {"files": hashes, "evaluation_config": evaluation}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"),
                                     default=str).encode()).hexdigest()


def file_fingerprint(path: Path) -> dict:
    """Hash opaque bytes in bounded memory; detect a file changing mid-read."""
    before = path.stat()
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(4 * 1024 * 1024), b""):
            digest.update(block)
    after = path.stat()
    fields = ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns")
    if any(getattr(before, field) != getattr(after, field) for field in fields):
        raise ValueError("data changed while computing nomination fingerprint")
    return {"sha256": digest.hexdigest(), "size_bytes": after.st_size}


def nomination_freeze(root: Path, cfg: dict, parquet: Path) -> dict:
    source = git_state(root)
    if source["dirty"]:
        raise ValueError("OOS nomination requires a clean working tree; commit reviewed changes first")
    return {"oos_code_commit": source["git_commit"], "oos_code_hash": code_fingerprint(root, cfg),
            "oos_dirty": False, "oos_data_fingerprint": file_fingerprint(parquet)}


def verify_freeze(root: Path, cfg: dict, spec: dict, parquet: Path) -> dict:
    if problem := freeze_shape_error(spec):
        raise ValueError(problem)
    current = git_state(root)
    if current["dirty"]:
        raise ValueError("OOS requires a clean working tree; no reservation was made")
    ancestor = subprocess.run(["git", "merge-base", "--is-ancestor", spec["oos_code_commit"], "HEAD"],
                              cwd=root, capture_output=True)
    if ancestor.returncode:
        raise ValueError("pinned implementation commit is not an ancestor of HEAD")
    if code_fingerprint(root, cfg) != spec["oos_code_hash"]:
        raise ValueError("implementation or evaluation settings changed since nomination")
    data = file_fingerprint(parquet)
    if data != spec["oos_data_fingerprint"]:
        raise ValueError("feature data changed since nomination")
    return {field: spec[field] for field in FREEZE_FIELDS}
