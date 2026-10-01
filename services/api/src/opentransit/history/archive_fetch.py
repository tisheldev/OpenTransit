"""Verified, pinned copies of Hasadna's public Open Bus S3 archive (OB-01 inputs).

Bucket `openbus-stride-public` (eu-west-1) allows anonymous listing and reads. SIRI minutes are
small single-part objects whose ETag is the MD5 of the bytes, so every download is checked
against the listing before it is kept. Daily GTFS zips are multipart uploads (ETag is not an
MD5); only the members OB-01 needs are copied with HTTP range requests, and zipfile's CRC check
verifies each member against the archive's own central directory. Provenance records carry the
archive key, size, ETag and SHA-256 so a batch can pin exactly what it read.
"""

from __future__ import annotations

import hashlib
import io
import json
import re
import time
import xml.etree.ElementTree as ElementTree
import zipfile
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import httpx

from opentransit.core.time import JERUSALEM

BUCKET_URL = "https://openbus-stride-public.s3.eu-west-1.amazonaws.com"
SIRI_PREFIX = "stride-siri-requester"
GTFS_FEED = "israel-public-transportation.zip"
SCHEDULE_MEMBERS = ("calendar.txt", "routes.txt", "trips.txt", "stop_times.txt", "stops.txt")
SERVICE_DAY_HOURS = 30  # local 00:00 to 06:00 the next day covers after-midnight trips
_NS = "{http://s3.amazonaws.com/doc/2006-03-01/}"
_MD5 = re.compile(r"[0-9a-f]{32}")


class ArchiveIntegrityError(RuntimeError):
    """A downloaded object does not match the archive listing."""


@dataclass(frozen=True, slots=True)
class ArchiveObject:
    key: str
    size: int
    etag: str  # quotes stripped

    @property
    def md5(self) -> str | None:
        """The ETag is the bytes' MD5 only for single-part uploads."""
        return self.etag if _MD5.fullmatch(self.etag) else None


def parse_listing(document: str) -> tuple[list[ArchiveObject], str | None]:
    root = ElementTree.fromstring(document)
    objects = [
        ArchiveObject(
            item.findtext(f"{_NS}Key"),
            int(item.findtext(f"{_NS}Size")),
            item.findtext(f"{_NS}ETag").strip('"'),
        )
        for item in root.iter(f"{_NS}Contents")
    ]
    return objects, root.findtext(f"{_NS}NextContinuationToken")


def get(client: httpx.Client, url: str, **kwargs) -> httpx.Response:
    """GET with retries; S3 occasionally drops idle keep-alive connections."""
    for attempt in range(5):
        try:
            response = client.get(url, **kwargs)
            response.raise_for_status()
            return response
        except (httpx.TransportError, httpx.HTTPStatusError) as error:
            client_error = (
                isinstance(error, httpx.HTTPStatusError) and error.response.status_code < 500
            )
            if attempt == 4 or client_error:
                raise
            time.sleep(2**attempt)
    raise AssertionError("unreachable")


def list_prefix(client: httpx.Client, prefix: str) -> list[ArchiveObject]:
    objects: list[ArchiveObject] = []
    token = None
    while True:
        params = {"list-type": "2", "prefix": prefix}
        if token:
            params["continuation-token"] = token
        page, token = parse_listing(get(client, "/", params=params).text)
        objects.extend(page)
        if not token:
            return objects


def _record(obj: ArchiveObject, sha: str) -> dict:
    return {"key": obj.key, "size": obj.size, "md5": obj.md5, "sha256": sha}


def fetch_object(client: httpx.Client, obj: ArchiveObject, target: Path) -> dict:
    """Download `obj` to `target` unless an identical verified copy is already there."""
    if target.exists() and target.stat().st_size == obj.size:
        body = target.read_bytes()
        if obj.md5 is None or hashlib.md5(body).hexdigest() == obj.md5:
            return _record(obj, hashlib.sha256(body).hexdigest())
    body = get(client, "/" + obj.key).content
    if len(body) != obj.size:
        raise ArchiveIntegrityError(f"{obj.key}: {len(body)} bytes, listing says {obj.size}")
    if obj.md5 is not None and hashlib.md5(body).hexdigest() != obj.md5:
        raise ArchiveIntegrityError(f"{obj.key}: MD5 differs from the listing ETag")
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_name(target.name + ".partial")
    partial.write_bytes(body)
    partial.replace(target)
    return _record(obj, hashlib.sha256(body).hexdigest())


class RangeFile(io.RawIOBase):
    """Read-only, seekable view of an archive object through HTTP range requests."""

    def __init__(self, client: httpx.Client, key: str, size: int, block: int):
        self.client, self.url, self.size, self.block_size = client, "/" + key, size, block
        self.position = 0
        self.blocks: dict[int, bytes] = {}
        self.requests = 0

    def readable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return True

    def tell(self) -> int:
        return self.position

    def seek(self, offset: int, whence: int = io.SEEK_SET) -> int:
        base = {io.SEEK_SET: 0, io.SEEK_CUR: self.position, io.SEEK_END: self.size}[whence]
        self.position = max(0, base + offset)
        return self.position

    def _block(self, index: int) -> bytes:
        if index not in self.blocks:
            start = index * self.block_size
            end = min(self.size, start + self.block_size) - 1
            response = get(self.client, self.url, headers={"Range": f"bytes={start}-{end}"})
            if len(self.blocks) >= 4:
                self.blocks.pop(next(iter(self.blocks)))
            self.blocks[index] = response.content
            self.requests += 1
        return self.blocks[index]

    def read(self, n: int = -1) -> bytes:
        if n is None or n < 0:
            n = self.size - self.position
        n = min(n, self.size - self.position)
        parts = []
        while n > 0:
            index, offset = divmod(self.position, self.block_size)
            chunk = self._block(index)[offset : offset + n]
            parts.append(chunk)
            self.position += len(chunk)
            n -= len(chunk)
        return b"".join(parts)

    def readinto(self, buffer) -> int:
        data = self.read(len(buffer))
        buffer[: len(data)] = data
        return len(data)


def extract_members(
    client: httpx.Client,
    obj: ArchiveObject,
    members: tuple[str, ...],
    target: Path,
    *,
    block: int = 4 << 20,
) -> dict:
    """Copy `members` of a remote zip into a local zip; return (and cache) provenance."""
    meta_path = target.with_name(target.name + ".json")
    if target.exists() and meta_path.exists():
        cached = json.loads(meta_path.read_text(encoding="utf-8"))
        if (cached["key"], cached["size"], cached["etag"]) == (obj.key, obj.size, obj.etag):
            return cached
    remote = RangeFile(client, obj.key, obj.size, block)
    meta = {"key": obj.key, "size": obj.size, "etag": obj.etag, "members": {}}
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_name(target.name + ".partial")
    with (
        zipfile.ZipFile(remote) as archive,
        zipfile.ZipFile(partial, "w", zipfile.ZIP_DEFLATED, compresslevel=1) as out,
    ):
        for name in members:
            digest = hashlib.sha256()
            with archive.open(name) as reader, out.open(name, "w") as writer:
                for chunk in iter(lambda reader=reader: reader.read(1 << 20), b""):
                    digest.update(chunk)  # zipfile raises on a CRC mismatch at EOF
                    writer.write(chunk)
            info = archive.getinfo(name)
            meta["members"][name] = {
                "sha256": digest.hexdigest(),
                "bytes": info.file_size,
                "crc32": info.CRC,
            }
    meta["rangeRequests"] = remote.requests
    partial.replace(target)
    meta_path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    return meta


def siri_window(day: date) -> tuple[datetime, datetime]:
    """UTC range of archive minutes for one service day (local midnight plus 30 hours)."""
    start = datetime.combine(day, datetime.min.time(), JERUSALEM).astimezone(UTC)
    return start, start + timedelta(hours=SERVICE_DAY_HOURS)


def manifest_digest(records: list[dict]) -> str:
    """SHA-256 over sorted `key<TAB>size<TAB>sha256` lines: one pin for many objects."""
    digest = hashlib.sha256()
    for record in sorted(records, key=lambda item: item["key"]):
        digest.update(f"{record['key']}\t{record['size']}\t{record['sha256']}\n".encode())
    return digest.hexdigest()
