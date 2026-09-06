"""Download and change detection for the MOT feeds.

**There is no HTTP HEAD in this module and there must never be one.**

`HEAD https://gtfs.mot.gov.il/gtfsfiles/TripIdToDate.zip` answers
`200 Content-Length: 3382, Content-Type: text/html` against a 9.7 MB zip —
the edge appliance in front of the origin serves an HTML interstitial to
HEAD and the real bytes to GET. A size or ETag check built on HEAD therefore
reports "unchanged" forever. This is corpus check E01 and KDP-004.

Change detection is: full GET -> sha256 of the received bytes -> zip
structural validation -> compare against the sha256 already on disk. That is
the only signal this module trusts. `poc/gtfs/checks.py` contains the HEAD
probe used to *evidence* the discrepancy; it is a diagnostic and its result
never feeds a decision.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path

import requests

BASE = "https://gtfs.mot.gov.il/gtfsfiles/"

FEEDS: dict[str, dict] = {
    "Gtfs_10_days.zip": {
        "url": BASE + "Gtfs_10_days.zip",
        "role": "comparison",
        "description": "MOT 10-day GTFS — comparison only (ADR 0005)",
        "required_members": ["agency.txt", "routes.txt", "trips.txt", "stops.txt",
                             "stop_times.txt", "shapes.txt", "feed_info.txt"],
    },
    "israel-public-transportation.zip": {
        "url": BASE + "israel-public-transportation.zip",
        "role": "primary",
        "description": "MOT 60-day GTFS — primary input (ADR 0005)",
        "required_members": ["agency.txt", "routes.txt", "trips.txt", "stops.txt",
                             "stop_times.txt", "shapes.txt"],
    },
    "TripIdToDate.zip": {
        "url": BASE + "TripIdToDate.zip",
        "role": "companion",
        "description": "MOT trip-id to date mapping — required for realtime matching",
        "required_members": ["TripIdToDate.txt"],
    },
}

USER_AGENT = "OpenTransit-Israel-POC/0.1 (Phase 0 feasibility; contact: repository owner)"
CHUNK = 1 << 20


@dataclass
class FetchResult:
    name: str
    url: str
    status: str            # "new" | "changed" | "unchanged" | "failed"
    sha256: str | None
    size_bytes: int | None
    seconds: float
    http_status: int | None = None
    last_modified: str | None = None
    etag: str | None = None
    previous_sha256: str | None = None
    zip_valid: bool | None = None
    error: str | None = None

    def as_dict(self) -> dict:
        return asdict(self)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(CHUNK), b""):
            h.update(chunk)
    return h.hexdigest()


def fetch(name: str, data_dir: Path, timeout: int = 600,
          session: requests.Session | None = None) -> FetchResult:
    """GET one feed into data_dir, deciding new/changed/unchanged by content hash.

    Works from an empty directory: an absent local file is simply "new".
    The download lands in a `.part` file and is promoted only after the zip
    validates, so an interrupted refresh can never leave a half file that a
    later run mistakes for a good one.
    """
    from . import zipread  # local import keeps this module importable standalone

    spec = FEEDS[name]
    url = spec["url"]
    dest = data_dir / name
    part = data_dir / (name + ".part")
    data_dir.mkdir(parents=True, exist_ok=True)

    previous = sha256_file(dest) if dest.exists() else None
    t0 = time.monotonic()
    sess = session or requests.Session()

    try:
        # GET, always. Never HEAD — see the module docstring.
        with sess.get(url, stream=True, timeout=timeout,
                      headers={"User-Agent": USER_AGENT}) as resp:
            resp.raise_for_status()
            h = hashlib.sha256()
            size = 0
            with part.open("wb") as out:
                for chunk in resp.iter_content(CHUNK):
                    if not chunk:
                        continue
                    out.write(chunk)
                    h.update(chunk)
                    size += len(chunk)
            digest = h.hexdigest()
            http_status = resp.status_code
            last_mod = resp.headers.get("Last-Modified")
            etag = resp.headers.get("ETag")
    except Exception as e:  # noqa: BLE001 — a failed refresh is a recorded result
        part.unlink(missing_ok=True)
        return FetchResult(name, url, "failed", None, None,
                           time.monotonic() - t0, error=f"{type(e).__name__}: {e}")

    v = zipread.validate_zip(part, spec["required_members"])
    if not v["valid"]:
        part.unlink(missing_ok=True)
        return FetchResult(name, url, "failed", digest, size, time.monotonic() - t0,
                           http_status, last_mod, etag, previous, False,
                           error=f"zip validation failed, missing members: {v['missing']}")

    if previous == digest:
        # Byte-identical to what is already on disk. Keep the existing file.
        part.unlink(missing_ok=True)
        status = "unchanged"
    else:
        os.replace(part, dest)
        status = "new" if previous is None else "changed"

    return FetchResult(name, url, status, digest, size, time.monotonic() - t0,
                       http_status, last_mod, etag, previous, True)


def refresh(data_dir: Path, names: list[str] | None = None,
            timeout: int = 600) -> dict[str, FetchResult]:
    """Refresh every feed. This is the whole automatic-refresh path."""
    sess = requests.Session()
    out: dict[str, FetchResult] = {}
    for name in names or list(FEEDS):
        out[name] = fetch(name, data_dir, timeout=timeout, session=sess)
    return out


def write_manifest(data_dir: Path, results: dict[str, FetchResult] | None = None) -> Path:
    """Record the exact bytes a run worked from, in poc/manifest.py's shape."""
    import zipfile

    files: dict[str, dict] = {}
    for name, spec in FEEDS.items():
        p = data_dir / name
        if not p.exists():
            files[name] = {"present": False, "description": spec["description"]}
            continue
        st = p.stat()
        entry = {
            "present": True,
            "description": spec["description"],
            "source": spec["url"],
            "size_bytes": st.st_size,
            "sha256": sha256_file(p),
            "retrieved_utc": datetime.fromtimestamp(st.st_mtime, timezone.utc).isoformat(),
        }
        try:
            with zipfile.ZipFile(p) as z:
                entry["zip_valid"] = True
                entry["members"] = [{"name": i.filename, "size": i.file_size}
                                    for i in z.infolist()]
        except zipfile.BadZipFile as e:
            entry["zip_valid"] = False
            entry["members"] = [{"error": str(e)}]
        if results and name in results:
            entry["fetch"] = results[name].as_dict()
        files[name] = entry

    manifest = {
        "schema_version": 1,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "note": ("MOT rewrites these feeds nightly. Any result produced from this data "
                 "must cite the sha256 recorded here, not the filename."),
        "files": files,
    }
    out = data_dir / "manifest.json"
    out.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return out
