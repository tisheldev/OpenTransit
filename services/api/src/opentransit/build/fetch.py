"""Immutable acquisition of the schedule generation's source files.

Successful checks are recorded as append-only events. Source bytes live under
their SHA-256, so a changed feed never overwrites evidence used by a prior
generation. Archives are inspected in place and are never extracted.
"""

from __future__ import annotations

import hashlib
import json
import os
import stat
import urllib.error
import urllib.request
import uuid
import zipfile
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path, PurePosixPath

CHUNK_SIZE = 1 << 20
USER_AGENT = "OpenTransit-schedule-builder/0.1"
GTFS_URL = "https://gtfs.mot.gov.il/gtfsfiles/israel-public-transportation.zip"
MAPPING_URL = "https://gtfs.mot.gov.il/gtfsfiles/TripIdToDate.zip"
OSM_URL = "https://download.geofabrik.de/asia/israel-and-palestine-latest.osm.pbf"


@dataclass(frozen=True)
class SourceSpec:
    name: str
    url: str
    required_members: tuple[str, ...] = ()
    cadence: timedelta = timedelta(0)


DEFAULT_SOURCES: dict[str, SourceSpec] = {
    "gtfs": SourceSpec(
        "israel-public-transportation.zip",
        GTFS_URL,
        ("agency.txt", "routes.txt", "trips.txt", "stops.txt", "stop_times.txt", "shapes.txt"),
    ),
    "trip_id_to_date": SourceSpec("TripIdToDate.zip", MAPPING_URL, ("TripIdToDate.txt",)),
    "osm": SourceSpec("israel-and-palestine-latest.osm.pbf", OSM_URL, cadence=timedelta(days=7)),
}


@dataclass(frozen=True)
class FetchResult:
    key: str
    name: str
    status: str
    path: Path | None
    sha256: str | None
    size_bytes: int | None
    acquired_at: str | None
    checked_at: str
    http_status: int | None = None
    last_modified: str | None = None
    error: str | None = None

    def as_dict(self) -> dict:
        return {
            "key": self.key,
            "name": self.name,
            "status": self.status,
            "path": str(self.path) if self.path else None,
            "sha256": self.sha256,
            "sizeBytes": self.size_bytes,
            "acquiredAt": self.acquired_at,
            "checkedAt": self.checked_at,
            "httpStatus": self.http_status,
            "lastModified": self.last_modified,
            "error": self.error,
        }


@dataclass(frozen=True)
class FetchReport:
    inputs_root: Path
    results: Mapping[str, FetchResult]

    @property
    def successful(self) -> bool:
        return all(
            item.status in {"new", "changed", "unchanged", "skipped"}
            for item in self.results.values()
        )


class FetchError(RuntimeError):
    """A source could not be safely acquired or validated."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _utc(value: datetime | None = None) -> datetime:
    current = value or datetime.now(UTC)
    if current.tzinfo is None or current.utcoffset() is None:
        raise ValueError("fetch timestamps must include a timezone")
    return current.astimezone(UTC)


def _events(root: Path, key: str) -> list[dict]:
    found = []
    if not root.exists():
        return found
    for path in root.glob("*/events/*.json"):
        try:
            event = json.loads(path.read_text(encoding="utf-8"))
        except OSError, json.JSONDecodeError:
            continue
        if event.get("key") == key and event.get("status") in {"new", "changed", "unchanged"}:
            found.append(event)
    return sorted(found, key=lambda e: e.get("checkedAt", ""))


def _verified_path(event: dict | None) -> Path | None:
    if not event or not event.get("path") or not event.get("sha256"):
        return None
    path = Path(event["path"])
    try:
        if path.is_file() and sha256_file(path) == event["sha256"]:
            return path
    except OSError:
        pass
    return None


def _validate_zip(path: Path, required: tuple[str, ...]) -> None:
    with zipfile.ZipFile(path) as archive:
        infos = archive.infolist()
        names = [info.filename for info in infos]
        if len(names) != len(set(names)):
            raise FetchError("archive contains duplicate member names")
        missing = set(required) - set(names)
        if missing:
            raise FetchError(f"archive is missing required members: {sorted(missing)}")
        for info in infos:
            member = PurePosixPath(info.filename)
            if member.is_absolute() or ".." in member.parts or "\\" in info.filename:
                raise FetchError(f"unsafe archive member path: {info.filename!r}")
            if stat.S_ISLNK(info.external_attr >> 16):
                raise FetchError(f"archive symlink is unsupported: {info.filename}")
            if info.flag_bits & 0x1:
                raise FetchError(f"encrypted archive member is unsupported: {info.filename}")
            if info.file_size > 0 and info.compress_size == 0:
                raise FetchError(f"invalid compressed size for {info.filename}")
            if info.file_size > max(256 * 1024 * 1024, info.compress_size * 500):
                raise FetchError(f"suspicious compression ratio for {info.filename}")
            # Small metadata CRCs are checked here. Large GTFS members are
            # verified while validation streams their contents to EOF.
            if info.file_size <= 64 * 1024 * 1024:
                with archive.open(info) as member_stream:
                    while member_stream.read(CHUNK_SIZE):
                        pass


def _download(
    spec: SourceSpec, destination: Path, timeout: float
) -> tuple[str, int, int | None, str | None]:
    request = urllib.request.Request(spec.url, headers={"User-Agent": USER_AGENT})
    digest = hashlib.sha256()
    size = 0
    with (
        urllib.request.urlopen(request, timeout=timeout) as response,
        destination.open("xb") as output,
    ):
        while chunk := response.read(CHUNK_SIZE):
            output.write(chunk)
            digest.update(chunk)
            size += len(chunk)
        output.flush()
        os.fsync(output.fileno())
        return (
            digest.hexdigest(),
            size,
            getattr(response, "status", None),
            response.headers.get("Last-Modified"),
        )


def _write_event(day_dir: Path, result: FetchResult) -> None:
    events = day_dir / "events"
    events.mkdir(parents=True, exist_ok=True)
    stamp = result.checked_at.replace(":", "").replace("-", "")
    path = events / f"{stamp}-{uuid.uuid4().hex}.json"
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(result.as_dict(), indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


WINDOWS_MAX_PATH = 259  # MAX_PATH (260) includes the terminating NUL
_EVENT_NAME_LENGTH = len("20260930T000000+0000-") + 32 + len(".json")


def _windows_long_paths_enabled() -> bool:
    try:
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\FileSystem"
        ) as key:
            return bool(winreg.QueryValueEx(key, "LongPathsEnabled")[0])
    except ImportError, OSError:
        return False


def _check_path_budget(day_dir: Path, sources: Mapping[str, SourceSpec]) -> None:
    """Fail clearly instead of mid-run when Windows would hit MAX_PATH.

    Evidence paths embed a 64-character digest (and a UUID on collisions), so
    a deep ``--output`` directory otherwise surfaces as an opaque
    FileNotFoundError and an unwritable failure event. Linux/Fargate has no
    such limit.
    """
    if os.name != "nt" or _windows_long_paths_enabled():
        return
    longest = len(str(day_dir / "events")) + 1 + _EVENT_NAME_LENGTH
    for key, spec in sources.items():
        objects = len(str(day_dir / "objects" / key)) + 1 + 64 + 1 + 32 + 1 + len(spec.name)
        staging = len(str(day_dir / ".staging")) + 1 + len(key) + 1 + 32 + len(".part")
        longest = max(longest, objects, staging)
    if longest > WINDOWS_MAX_PATH:
        raise FetchError(
            f"output directory is too deep for Windows MAX_PATH ({longest} > "
            f"{WINDOWS_MAX_PATH} characters for the longest evidence path); use a shorter "
            "--output path or enable Windows long paths (LongPathsEnabled)"
        )


def fetch_sources(
    inputs_root: Path,
    sources: Mapping[str, SourceSpec] = DEFAULT_SOURCES,
    *,
    timeout: float = 120,
    now: datetime | None = None,
    force_osm: bool = False,
) -> FetchReport:
    """GET and content-hash the configured sources into immutable evidence.

    GTFS and TripIdToDate always use full GETs; HEAD metadata is not a change
    signal. OSM is checked at most weekly unless ``force_osm`` is requested.
    A failed fetch never promotes partial bytes or overwrites earlier input.
    """
    root = Path(inputs_root).resolve()
    checked = _utc(now)
    day_dir = root / checked.date().isoformat()
    _check_path_budget(day_dir, sources)
    result: dict[str, FetchResult] = {}
    for key, spec in sources.items():
        previous = _events(root, key)
        prior = previous[-1] if previous else None
        prior_path = _verified_path(prior)
        if spec.cadence > timedelta(0) and prior and prior_path and not force_osm:
            checked_prior = datetime.fromisoformat(prior["checkedAt"])
            if checked - checked_prior < spec.cadence:
                result[key] = FetchResult(
                    key,
                    spec.name,
                    "skipped",
                    prior_path,
                    prior["sha256"],
                    prior["sizeBytes"],
                    prior.get("acquiredAt"),
                    prior["checkedAt"],
                )
                continue

        day_dir.mkdir(parents=True, exist_ok=True)
        staging_dir = day_dir / ".staging"
        staging_dir.mkdir(exist_ok=True)
        partial = staging_dir / f"{key}-{uuid.uuid4().hex}.part"
        try:
            digest, size, http_status, last_modified = _download(spec, partial, timeout)
            if spec.required_members:
                _validate_zip(partial, spec.required_members)
            unchanged_path = prior_path if prior and prior.get("sha256") == digest else None
            data_path = unchanged_path or (day_dir / "objects" / key / f"{digest}-{spec.name}")
            data_path.parent.mkdir(parents=True, exist_ok=True)
            if unchanged_path is not None:
                partial.unlink()
            elif data_path.exists() and sha256_file(data_path) == digest:
                partial.unlink()
            elif data_path.exists():
                data_path = data_path.with_name(f"{digest}-{uuid.uuid4().hex}-{spec.name}")
                os.replace(partial, data_path)
            else:
                os.replace(partial, data_path)
            status = (
                "new"
                if prior is None
                else ("unchanged" if prior.get("sha256") == digest else "changed")
            )
            acquired_at = prior.get("acquiredAt") if status == "unchanged" else checked.isoformat()
            item = FetchResult(
                key,
                spec.name,
                status,
                data_path,
                digest,
                size,
                acquired_at,
                checked.isoformat(),
                http_status,
                last_modified,
            )
        except (OSError, ValueError, zipfile.BadZipFile, urllib.error.URLError, FetchError) as exc:
            partial.unlink(missing_ok=True)
            item = FetchResult(
                key,
                spec.name,
                "failed",
                None,
                None,
                None,
                None,
                checked.isoformat(),
                error=f"{type(exc).__name__}: {exc}",
            )
        result[key] = item
        _write_event(day_dir, item)
    return FetchReport(root, result)
