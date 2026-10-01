"""Supplementary M2.8 evidence: source-ID stability across Hasadna's public daily GTFS archive.

Open Bus (Hasadna) archives each day's MOT GTFS at
`openbus-stride-public/gtfs_archive/YYYY/MM/DD/israel-public-transportation.zip`. This tool reads
only `stops.txt`, `routes.txt` and `trips.txt` from each archived zip with HTTP range requests,
caches them as small local zips, and compares day-over-day pairs plus longer lags with the same
`compare_ids` used for the genuine consecutive-daily M2.8 check. It adds field-level detail
(stop names, codes and coordinates; route numbers and agencies) and IDs that disappear and
come back.

This is historical, third-party-archived evidence. It does not replace the M2.8 requirement of
two genuinely consecutive daily feeds acquired by our own `fetch` with retained hashes; ID
overlap never proves realtime matching.

    uv run --project services/api --locked python services/api/tools/archive_id_stability.py
        --start 2026-07-01 --end 2026-10-01 --lags 7,30,90,365
        --verify-local .runtime/sources/snapshots/<stamp>/israel-public-transportation.zip
        --output services/api/results/m2-id-stability-archive-20261001-01.json

(from the repository root). Refuses to overwrite --output. Exit 0: report written; 2: error.
"""

from __future__ import annotations

import argparse
import functools
import hashlib
import io
import json
import math
import re
import statistics
import sys
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import httpx

from opentransit.build.identity import compare_ids
from opentransit.build.prepare import rows, sha256

BUCKET = "https://openbus-stride-public.s3.eu-west-1.amazonaws.com"
FEED = "israel-public-transportation.zip"
MEMBERS = ("stops.txt", "routes.txt", "trips.txt")
BLOCK = 4 << 20
MOVED_METERS = 100


def get(client: httpx.Client, url: str, **kwargs) -> httpx.Response:
    """GET with a few retries; S3 occasionally drops idle keep-alive connections."""
    for attempt in range(4):
        try:
            response = client.get(url, **kwargs)
            response.raise_for_status()
            return response
        except (httpx.TransportError, httpx.HTTPStatusError) as error:
            if attempt == 3 or (
                isinstance(error, httpx.HTTPStatusError) and error.response.status_code < 500
            ):
                raise
            time.sleep(2**attempt)
    raise AssertionError("unreachable")


class RangeFile(io.RawIOBase):
    """Read-only, seekable view of an HTTP object using Range requests and a small block cache."""

    def __init__(self, client: httpx.Client, url: str, size: int):
        self.client, self.url, self.size, self.position = client, url, size, 0
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

    def block(self, index: int) -> bytes:
        if index not in self.blocks:
            start = index * BLOCK
            end = min(self.size, start + BLOCK) - 1
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
            index, offset = divmod(self.position, BLOCK)
            chunk = self.block(index)[offset : offset + n]
            parts.append(chunk)
            self.position += len(chunk)
            n -= len(chunk)
        return b"".join(parts)

    def readinto(self, buffer) -> int:
        data = self.read(len(buffer))
        buffer[: len(data)] = data
        return len(data)


def listing(client: httpx.Client, day: date) -> dict | None:
    prefix = f"gtfs_archive/{day:%Y/%m/%d}/{FEED}"
    response = get(client, BUCKET + "/", params={"list-type": "2", "prefix": prefix})
    match = re.search(
        r"<Key>([^<]+)</Key><LastModified>([^<]+)</LastModified><ETag>([^<]+)</ETag>.*?<Size>(\d+)</Size>",
        response.text,
    )
    if not match:
        return None
    key, modified, etag, size = match.groups()
    return {
        "key": key,
        "lastModified": modified,
        "etag": etag.replace("&quot;", ""),
        "size": int(size),
    }


def extract(client: httpx.Client, day: date, cache: Path) -> tuple[Path, dict] | None:
    """Copy the three members into a cached local zip; return it with archive provenance."""
    target, meta_path = cache / f"{day:%Y-%m-%d}.zip", cache / f"{day:%Y-%m-%d}.json"
    if target.exists() and meta_path.exists():
        return target, json.loads(meta_path.read_text(encoding="utf-8"))
    source = listing(client, day)
    if source is None:
        return None
    remote = RangeFile(client, f"{BUCKET}/{source['key']}", source["size"])
    members = {}
    partial = target.with_suffix(".partial")
    with (
        zipfile.ZipFile(remote) as archive,
        zipfile.ZipFile(partial, "w", zipfile.ZIP_DEFLATED) as out,
    ):
        for name in MEMBERS:
            digest = hashlib.sha256()
            with archive.open(name) as reader, out.open(name, "w") as writer:
                for chunk in iter(lambda reader=reader: reader.read(1 << 20), b""):
                    digest.update(chunk)
                    writer.write(chunk)
            info = archive.getinfo(name)
            members[name] = {
                "sha256": digest.hexdigest(),
                "bytes": info.file_size,
                "crc32": info.CRC,
            }
    source["members"] = members
    source["rangeRequests"] = remote.requests
    partial.replace(target)
    meta_path.write_text(json.dumps(source, indent=2) + "\n", encoding="utf-8")
    return target, source


def meters(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lon1, lat2, lon2 = map(math.radians, (*a, *b))
    h = (
        math.sin((lat2 - lat1) / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    )
    return 2 * 6_371_000 * math.asin(math.sqrt(h))


def tables(path: Path) -> dict:
    with zipfile.ZipFile(path) as archive:
        stops = {r["stop_id"]: r for r in rows(archive, "stops.txt")}
        routes = {r["route_id"]: r for r in rows(archive, "routes.txt")}
    return {"stops": stops, "routes": routes}


def semantic(old: dict, new: dict) -> dict:
    """Field-level changes on retained stop and route IDs (possible ID reuse for another thing)."""
    stops = {
        "nameChanged": [],
        "codeChanged": [],
        f"movedOver{MOVED_METERS}m": [],
        "parentChanged": [],
    }
    for key in old["stops"].keys() & new["stops"].keys():
        a, b = old["stops"][key], new["stops"][key]
        if a.get("stop_name") != b.get("stop_name"):
            stops["nameChanged"].append(key)
        if a.get("stop_code") != b.get("stop_code"):
            stops["codeChanged"].append(key)
        if a.get("parent_station", "") != b.get("parent_station", ""):
            stops["parentChanged"].append(key)
        try:
            moved = meters(
                (float(a["stop_lat"]), float(a["stop_lon"])),
                (float(b["stop_lat"]), float(b["stop_lon"])),
            )
        except KeyError, ValueError:
            moved = 0.0
        if moved > MOVED_METERS:
            stops[f"movedOver{MOVED_METERS}m"].append(key)
    routes = {"shortNameChanged": [], "agencyChanged": [], "longNameChanged": [], "typeChanged": []}
    fields = {
        "shortNameChanged": "route_short_name",
        "agencyChanged": "agency_id",
        "longNameChanged": "route_long_name",
        "typeChanged": "route_type",
    }
    for key in old["routes"].keys() & new["routes"].keys():
        a, b = old["routes"][key], new["routes"][key]
        for label, field in fields.items():
            if a.get(field) != b.get(field):
                routes[label].append(key)

    def shape(groups: dict) -> dict:
        return {
            label: {"count": len(ids), "samples": sorted(ids)[:10]} for label, ids in groups.items()
        }

    return {"stops": shape(stops), "routes": shape(routes)}


def compare(pair: tuple[date, date], extracted: dict, load) -> dict:
    (previous, candidate) = pair
    (old_zip, old_meta), (new_zip, new_meta) = extracted[previous], extracted[candidate]
    report = compare_ids(old_zip, new_zip, previous, candidate)
    for side, meta, path in (("previous", old_meta, old_zip), ("candidate", new_meta, new_zip)):
        report[side] = {
            "archiveDate": report[side]["acquiredDate"],
            "archiveKey": meta["key"],
            "archiveLastModified": meta["lastModified"],
            "archiveSize": meta["size"],
            "archiveEtag": meta["etag"],
            "memberSha256": {name: member["sha256"] for name, member in meta["members"].items()},
            "extractSha256": sha256(path),
        }
    report.pop("acquisitionDatesVerified")
    report["consecutiveArchiveDays"] = report.pop("consecutiveDailyFeeds")
    report["lagDays"] = (candidate - previous).days
    report["semantic"] = semantic(load(previous), load(candidate))
    report.pop("scope")
    return report


def flicker(days: list[date], load) -> dict:
    """IDs that vanish from the archive on some day and later reappear inside the window."""
    result = {}
    state = {table: {"gone": {}, "returned": {}, "previous": None} for table in ("stops", "routes")}
    for day in days:
        tables_today = load(day)
        for table, track in state.items():
            current = set(tables_today[table])
            if track["previous"] is not None:
                for key in track["previous"] - current:
                    track["gone"].setdefault(key, day)
                for key in current & track["gone"].keys():
                    track["returned"][key] = track["returned"].get(key, 0) + 1
                    track["gone"].pop(key)
            track["previous"] = current
    for table, track in state.items():
        result[table] = {
            "removedAndReturned": len(track["returned"]),
            "removedNotReturned": len(track["gone"]),
            "returnedSamples": sorted(track["returned"])[:10],
        }
    return result


def summarize(pairs: list[dict]) -> dict:
    summary = {}
    for table in ("stops", "routes", "trips"):
        fractions = [p["counts"][table]["retainedFraction"] for p in pairs]
        summary[table] = {
            "pairs": len(pairs),
            "retainedFractionMin": min(fractions),
            "retainedFractionMedian": statistics.median(fractions),
            "pairsWithRemovals": sum(1 for p in pairs if p["counts"][table]["removed"]),
            "removedTotal": sum(p["counts"][table]["removed"] for p in pairs),
            "addedTotal": sum(p["counts"][table]["added"] for p in pairs),
            "metadataChangedTotal": sum(p["counts"][table]["metadataChangedCount"] for p in pairs),
        }
    for table, labels in (
        ("stops", ("nameChanged", "codeChanged", f"movedOver{MOVED_METERS}m", "parentChanged")),
        ("routes", ("shortNameChanged", "agencyChanged", "longNameChanged", "typeChanged")),
    ):
        summary[table]["semanticTotals"] = {
            label: sum(p["semantic"][table][label]["count"] for p in pairs) for label in labels
        }
    return summary


def local_cross_check(client: httpx.Client, local: Path, day: date) -> dict:
    """Hash the full archived object for `day` and compare with a feed we fetched ourselves."""
    source = listing(client, day)
    if source is None:
        return {"archiveDate": day.isoformat(), "archived": False}
    digest = hashlib.sha256()
    with client.stream("GET", f"{BUCKET}/{source['key']}") as response:
        response.raise_for_status()
        for chunk in response.iter_bytes(1 << 20):
            digest.update(chunk)
    ours = sha256(local)
    return {
        "archiveDate": day.isoformat(),
        "archiveKey": source["key"],
        "archiveLastModified": source["lastModified"],
        "archiveSha256": digest.hexdigest(),
        "localPath": local.as_posix(),
        "localSha256": ours,
        "identical": digest.hexdigest() == ours,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--start", type=date.fromisoformat, required=True)
    parser.add_argument("--end", type=date.fromisoformat, required=True)
    parser.add_argument(
        "--lags", default="7,30,90,365", help="Comma-separated lags in days back from --end"
    )
    parser.add_argument(
        "--cache-dir", type=Path, default=Path(".runtime/open-bus-archive/gtfs-members")
    )
    parser.add_argument(
        "--verify-local",
        type=Path,
        help="Our own fetched feed for --end, hashed against the archive",
    )
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        print(f"refusing to overwrite {args.output}", file=sys.stderr)
        return 2
    if args.end <= args.start:
        print("--end must follow --start", file=sys.stderr)
        return 2
    args.cache_dir.mkdir(parents=True, exist_ok=True)
    lags = sorted({int(x) for x in args.lags.split(",") if x.strip()})
    window = [args.start + timedelta(days=i) for i in range((args.end - args.start).days + 1)]
    lag_days = [args.end - timedelta(days=lag) for lag in lags]
    wanted = sorted(set(window) | set(lag_days))

    with httpx.Client(timeout=120, follow_redirects=False) as client:
        with ThreadPoolExecutor(args.workers) as pool:
            found = dict(
                zip(
                    wanted,
                    pool.map(lambda d: extract(client, d, args.cache_dir), wanted),
                    strict=True,
                )
            )
        extracted = {day: value for day, value in found.items() if value is not None}
        missing = [day.isoformat() for day, value in found.items() if value is None]
        load = functools.lru_cache(maxsize=4)(lambda day: tables(extracted[day][0]))
        present = [day for day in window if day in extracted]
        daily = [
            compare((a, b), extracted, load)
            for a, b in zip(present, present[1:], strict=False)
            if (b - a).days == 1
        ]
        lagged = [
            compare((day, args.end), extracted, load)
            for day in lag_days
            if day in extracted and args.end in extracted
        ]
        cross = (
            local_cross_check(client, args.verify_local, args.end) if args.verify_local else None
        )

    report = {
        "tool": "services/api/tools/archive_id_stability.py",
        "generatedAt": datetime.now(UTC).isoformat(timespec="seconds"),
        "source": f"{BUCKET}/gtfs_archive/ (Hasadna Open Bus public archive; "
        "third-party copy of MOT GTFS)",
        "members": list(MEMBERS),
        "window": {
            "start": args.start.isoformat(),
            "end": args.end.isoformat(),
            "days": len(window),
        },
        "missingArchiveDays": missing,
        "dailySummary": summarize(daily) if daily else None,
        "flicker": flicker(present, load),
        "lagPairs": lagged,
        "localCrossCheck": cross,
        "dailyPairs": daily,
        "scope": (
            "Supplementary historical evidence from a third-party archive. Archive dates are "
            "Hasadna's download dates, not our acquisitions; this does not satisfy the M2.8 "
            "requirement of two genuinely consecutive daily feeds fetched by OpenTransit. ID "
            "overlap does not prove semantic stability or realtime matching."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(
        json.dumps({"dailySummary": report["dailySummary"], "flicker": report["flicker"]}, indent=2)
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
