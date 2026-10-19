"""OCI Object Storage → DuckDB raw data ingestion pipeline.

This module downloads raw market-data archives from an Oracle Cloud
Infrastructure (OCI) Pre-Authenticated Request (PAR) URL, unarchives them,
and collects every CSV into a single flat directory so downstream steps
(Cleaning → Aggregation → Feature engineering) can consume one consistent
input location.

Configuration is read from ``config/setting.yml`` (``oci.par_url``).
"""

from __future__ import annotations

import shutil
import zipfile
from pathlib import Path
from urllib.parse import urljoin

import requests
import yaml
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

DEFAULT_ZIPS_DIR = Path("data/raw_zips")
DEFAULT_CSV_DIR = Path("data/raw_csv")
DEFAULT_CONFIG_PATH = Path("config/setting.yml")


def ensure_dir(dir_path: str | Path) -> Path:
    """Create *dir_path* (and parents) if needed and return it as ``Path``."""
    path = Path(dir_path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _build_session() -> requests.Session:
    """HTTP session with retry/backoff for transient OCI failures."""
    retry = Retry(
        total=5,
        connect=5,
        read=5,
        backoff_factor=0.5,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET"}),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry, pool_connections=4, pool_maxsize=4)
    session = requests.Session()
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def _safe_relative_path(name: str, root: Path) -> Path | None:
    """Resolve *name* under *root* without allowing path traversal.

    Traversal is judged on path *components*, so a legitimate file name that
    merely contains ``..`` as a substring (for example ``EUR..USD.csv``) is
    still accepted.
    """
    cleaned = name.strip()
    if not cleaned or cleaned.startswith("/") or cleaned.startswith("\\"):
        return None

    # Normalise separators and reject empty / dot / dot-dot *components*.
    parts = [part for part in cleaned.replace("\\", "/").split("/")]
    if any(part in ("", ".", "..") for part in parts):
        return None
    if any(":" in part for part in parts):
        return None

    root_resolved = Path(root).resolve()
    candidate = root_resolved
    for part in parts:
        candidate = candidate / part
    resolved = candidate.resolve()

    # Stay strictly inside *root*.
    if resolved == root_resolved:
        return None
    try:
        resolved.relative_to(root_resolved)
    except ValueError:
        return None
    return resolved


def _list_oci_objects(
    session: requests.Session, base_url: str, page_size: int = 1000
) -> list[dict]:
    """List all objects under an OCI PAR prefix, handling pagination."""
    objects: list[dict] = []
    start: str | None = None
    seen_starts: set[str] = set()

    while True:
        params: dict[str, str | int] = {
            "fields": "name,size,md5,timeModified",
            "limit": page_size,
        }
        if start:
            params["start"] = start

        try:
            response = session.get(base_url, params=params, timeout=60)
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise RuntimeError(
                f"Failed to list objects from OCI PAR URL ({base_url}): {exc}"
            ) from exc

        batch = payload.get("objects", [])
        objects.extend(
            obj for obj in batch if isinstance(obj, dict) and obj.get("name")
        )

        next_start = payload.get("nextStartWith")
        if not next_start or next_start in seen_starts:
            break
        seen_starts.add(next_start)
        start = str(next_start)

    return objects


def sync_oci_par(
    par_url: str,
    target_dir: str | Path = DEFAULT_ZIPS_DIR,
    *,
    session: requests.Session | None = None,
) -> list[Path]:
    """Download every object under *par_url* into *target_dir*.

    Returns the list of downloaded file paths. Objects already present with
    the same byte size are skipped to make re-runs idempotent.
    """
    save_dir = ensure_dir(target_dir)
    downloaded: list[Path] = []
    failures: list[str] = []
    close_session = session is None
    session = session or _build_session()

    base_url = par_url if par_url.endswith("/") else f"{par_url}/"

    try:
        objects = _list_oci_objects(session, base_url)
    except Exception:
        if close_session:
            session.close()
        raise

    if not objects:
        print("No objects found under the specified OCI PAR prefix.")
        return downloaded

    for obj in objects:
        object_name = str(obj.get("name", "")).strip()
        if not object_name or object_name.endswith("/"):
            continue

        local_path = _safe_relative_path(object_name, save_dir)
        if local_path is None:
            print(f"Skipping unsafe object name: {object_name!r}")
            continue

        obj_url = urljoin(base_url, object_name)
        remote_size = obj.get("size")
        if (
            local_path.exists()
            and remote_size is not None
            and local_path.stat().st_size == int(remote_size)
        ):
            print(f"Already downloaded, skipping: {object_name}")
            downloaded.append(local_path)
            continue

        local_path.parent.mkdir(parents=True, exist_ok=True)
        print(f"Downloading: {object_name} -> {local_path}")
        try:
            response = session.get(obj_url, stream=True, timeout=300)
            response.raise_for_status()
            with open(local_path, "wb") as handle:
                for chunk in response.iter_content(chunk_size=64 * 1024):
                    if chunk:
                        handle.write(chunk)
            downloaded.append(local_path)
        except requests.RequestException as exc:
            print(f"ERROR downloading {object_name}: {exc}")
            failures.append(object_name)

    if close_session:
        session.close()

    if failures:
        raise RuntimeError(
            f"Failed to download {len(failures)} object(s): {failures!r}"
        )

    print(f"Successfully downloaded {len(downloaded)} objects to {save_dir.resolve()}")
    return downloaded


def _unique_target_path(target_dir: Path, preferred_name: str) -> Path:
    """Return a non-colliding path under *target_dir* for *preferred_name*."""
    candidate = target_dir / preferred_name
    if not candidate.exists():
        return candidate
    stem = Path(preferred_name).stem
    suffix = Path(preferred_name).suffix
    counter = 1
    while True:
        candidate = target_dir / f"{stem}_{counter}{suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


def extract_all_zips_to_csv(
    zips_dir: str | Path = DEFAULT_ZIPS_DIR,
    csv_dir: str | Path = DEFAULT_CSV_DIR,
    *,
    clean_target: bool = True,
) -> list[Path]:
    """Extract every CSV from every zip under *zips_dir* into flat *csv_dir*.

    Archives may be nested in arbitrary sub-directories; all CSV files end up
    in the single *csv_dir* directory. Name collisions are resolved by
    appending a numeric suffix.

    When *clean_target* is True (the default) the destination directory is
    wiped first so that re-running extraction never leaves stale ``_N.csv``
    copies behind; the caller then owns full provenance of the output files.
    """
    source_dir = ensure_dir(zips_dir)
    target_dir = ensure_dir(csv_dir)
    if clean_target:
        for existing in target_dir.iterdir():
            if existing.is_file():
                existing.unlink()
            elif existing.is_dir():
                shutil.rmtree(existing)
    extracted: list[Path] = []

    zip_files = sorted(source_dir.rglob("*.zip"))
    if not zip_files:
        print(f"No zip files found in {source_dir.resolve()}")
        return extracted

    for zip_path in zip_files:
        print(f"Processing archive: {zip_path.relative_to(source_dir)}")
        try:
            with zipfile.ZipFile(zip_path, "r") as archive:
                bad = archive.testzip()
                if bad is not None:
                    print(f"Corrupt member {bad!r} in {zip_path}; skipping archive.")
                    continue

                for info in archive.infolist():
                    if info.is_dir():
                        continue
                    member = info.filename
                    if not member.lower().endswith(".csv"):
                        continue

                    preferred = Path(member).name
                    if not preferred or preferred.startswith("."):
                        continue

                    destination = _unique_target_path(target_dir, preferred)
                    with archive.open(info) as src, open(destination, "wb") as dst:
                        shutil.copyfileobj(src, dst, length=64 * 1024)
                    extracted.append(destination)
        except (zipfile.BadZipFile, OSError, RuntimeError) as exc:
            print(f"Error extracting {zip_path}: {exc}")

    print(
        f"Successfully extracted {len(extracted)} CSV files into {target_dir.resolve()}"
    )
    return extracted


def sync_oci_and_extract(
    par_url: str,
    zips_dir: str | Path = DEFAULT_ZIPS_DIR,
    csv_dir: str | Path = DEFAULT_CSV_DIR,
) -> tuple[list[Path], list[Path]]:
    """Download from OCI, then unarchive and collect all CSVs in *csv_dir*."""
    downloaded = sync_oci_par(par_url, zips_dir)
    extracted = extract_all_zips_to_csv(zips_dir, csv_dir)
    return downloaded, extracted


def load_config(config_path: str | Path = DEFAULT_CONFIG_PATH) -> dict:
    """Load YAML configuration from *config_path*."""
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Configuration file not found at: {path.resolve()}")
    with open(path, "r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def main() -> None:
    config = load_config()
    oci_config = config.get("oci", {}) or {}
    par_url = oci_config.get("par_url")
    if not par_url:
        raise ValueError(
            "OCI PAR URL ('par_url') not found under 'oci' section "
            f"in {DEFAULT_CONFIG_PATH}"
        )

    print(f"Using OCI PAR URL: {par_url}")
    downloaded, extracted = sync_oci_and_extract(par_url)
    print(
        f"Downloaded {len(downloaded)} objects; extracted {len(extracted)} CSV files."
    )


if __name__ == "__main__":
    main()
