"""M1 preparation into a new directory/volume. No destructive rerun behavior."""

import argparse
import csv
import hashlib
import io
import json
import shutil
import subprocess
import time
import urllib.request
import uuid
import zipfile
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ENGINE_DIGEST = "sha256:6055f51eec43eeed28524037ca0161b96efe9cd05728eaa9ac04c20c2826d330"
IMAGE = f"ghcr.io/motis-project/motis@{ENGINE_DIGEST}"
BASE = "https://gtfs.mot.gov.il/gtfsfiles/"
OSM_URL = "https://download.geofabrik.de/asia/israel-and-palestine-latest.osm.pbf"
FILES = {
    "israel-public-transportation.zip": BASE + "israel-public-transportation.zip",
    "TripIdToDate.zip": BASE + "TripIdToDate.zip",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def save(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def download(url: str, path: Path) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": "OpenTransit-local-preview/0.1"})
    partial = path.with_suffix(path.suffix + ".part")
    print(f"Downloading {path.name}", flush=True)
    # Full GET is intentional: MOT HEAD responses have misleading HTML metadata.
    with urllib.request.urlopen(request, timeout=120) as response, partial.open("xb") as output:
        shutil.copyfileobj(response, output, 1 << 20)
        modified = response.headers.get("Last-Modified")
    if path.suffix == ".zip":
        with zipfile.ZipFile(partial) as archive:
            if archive.testzip() is not None:
                raise ValueError("Archive CRC validation failed")
    partial.rename(path)
    return {
        "url": url,
        "sha256": sha256(path),
        "bytes": path.stat().st_size,
        "acquiredAt": datetime.now(UTC).isoformat(),
        "lastModified": modified,
    }


def rows(archive: zipfile.ZipFile, member: str):
    with (
        archive.open(member) as raw,
        io.TextIOWrapper(raw, encoding="utf-8-sig", newline="") as text,
    ):
        yield from csv.DictReader(text)


def inspect_inputs(feed: Path, mapping: Path, today: date) -> dict:
    """Static coverage and join-key preflight; never a realtime matching verdict."""
    active_services, trip_ids = set(), set()
    with zipfile.ZipFile(feed) as archive:
        required = {
            "agency.txt",
            "routes.txt",
            "stops.txt",
            "trips.txt",
            "stop_times.txt",
            "shapes.txt",
            "calendar.txt",
        }
        if not required.issubset(archive.namelist()):
            raise ValueError("Required GTFS members missing")
        for row in rows(archive, "trips.txt"):
            active_services.add(row["service_id"])
            trip_ids.add(row["trip_id"])
        service_days = {}
        weekdays = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
        for row in rows(archive, "calendar.txt"):
            if row["service_id"] not in active_services:
                continue
            start = datetime.strptime(row["start_date"], "%Y%m%d").date()
            end = datetime.strptime(row["end_date"], "%Y%m%d").date()
            if end < start or (end - start).days > 400:
                raise ValueError("Invalid service calendar")
            days = {
                start + timedelta(days=i)
                for i in range((end - start).days + 1)
                if row[weekdays[(start + timedelta(days=i)).weekday()]] == "1"
            }
            service_days[row["service_id"]] = days
        if "calendar_dates.txt" in archive.namelist():
            for row in rows(archive, "calendar_dates.txt"):
                if row["service_id"] not in active_services:
                    continue
                day = datetime.strptime(row["date"], "%Y%m%d").date()
                days = service_days.setdefault(row["service_id"], set())
                if row["exception_type"] == "1":
                    days.add(day)
                elif row["exception_type"] == "2":
                    days.discard(day)
                else:
                    raise ValueError("Invalid calendar exception")
        days = set().union(*service_days.values()) if service_days else set()
    if not trip_ids or not days or not min(days) <= today <= max(days):
        raise ValueError("Feed service coverage does not include today")
    mapping_keys, mapping_start, mapping_end = set(), None, None
    with zipfile.ZipFile(mapping) as archive:
        for row in rows(archive, "TripIdToDate.txt"):
            mapping_keys.add(row["TripId"])
            start = datetime.strptime(row["FromDate"].split(" ")[0], "%d/%m/%Y").date()
            end = datetime.strptime(row["ToDate"].split(" ")[0], "%d/%m/%Y").date()
            mapping_start = min(start, mapping_start) if mapping_start else start
            mapping_end = max(end, mapping_end) if mapping_end else end
    keys = {key.split("_", 1)[0] for key in trip_ids}
    unmatched = keys - mapping_keys
    if unmatched or mapping_start is None or mapping_end is None:
        raise ValueError("Feed/mapping join-key preflight failed")
    if mapping_end < min(days) or mapping_start > max(days):
        raise ValueError("Feed/mapping service windows are disjoint")
    until_day = min(today + timedelta(days=31), max(days) + timedelta(days=1))
    local = ZoneInfo("Asia/Jerusalem")
    return {
        "feedServiceDates": [min(days).isoformat(), max(days).isoformat()],
        "coverage": {
            "from": datetime.combine(today, datetime.min.time(), local).isoformat(),
            "until": datetime.combine(until_day, datetime.min.time(), local).isoformat(),
        },
        "importDays": (until_day - today).days,
        "tripCount": len(trip_ids),
        "distinctJoinKeys": len(keys),
        "unmatchedJoinKeys": len(unmatched),
        "pairingScope": "static join-key and date-window preflight; not realtime proof",
    }


def prepare(output: Path, osm_path: Path | None = None) -> None:
    output = output.resolve()
    # Existence is a hard refusal, including failed builds. Use a new name to retry.
    output.mkdir(parents=True, exist_ok=False)
    inputs = output / "inputs"
    inputs.mkdir()
    manifest_path = output / "manifest.json"
    today = datetime.now(ZoneInfo("Asia/Jerusalem")).date()
    suffix = f"{today:%Y%m%d}-{uuid.uuid4().hex[:8]}"
    volume = f"opentransit-m1-{suffix}"
    manifest = {
        "schemaVersion": 1,
        "state": "preparing",
        "engineDigest": ENGINE_DIGEST,
        "graphVolume": volume,
        "inputs": {},
        "mode": "real",
    }
    save(manifest_path, manifest)
    for name, url in FILES.items():
        manifest["inputs"][name] = download(url, inputs / name)
        save(manifest_path, manifest)
    osm_name = "israel-and-palestine-latest.osm.pbf"
    if osm_path:
        shutil.copyfile(osm_path.resolve(), inputs / osm_name)
        manifest["inputs"][osm_name] = {
            "sha256": sha256(inputs / osm_name),
            "bytes": (inputs / osm_name).stat().st_size,
            "reusedLocalPath": str(osm_path.resolve()),
            "acquiredAt": None,
            "note": "Existing OSM snapshot copied explicitly; not a fresh OSM download",
        }
    else:
        manifest["inputs"][osm_name] = download(OSM_URL, inputs / osm_name)
    preflight = inspect_inputs(
        inputs / "israel-public-transportation.zip", inputs / "TripIdToDate.zip", today
    )
    manifest["preflight"] = preflight
    manifest["coverage"] = preflight["coverage"]
    manifest["validatedAt"] = datetime.now(UTC).isoformat()
    config = output / "config.yml"
    config.write_text(
        f"""osm: /input/{osm_name}
timetable:
  first_day: {today.isoformat()}
  num_days: {preflight["importDays"]}
  with_shapes: true
  railviz: true
  adjust_footpaths: true
  merge_dupes_intra_src: false
  merge_dupes_inter_src: false
  datasets:
    mot60day:
      path: /input/israel-public-transportation.zip
      extend_calendar: false
street_routing: true
geocoding: false
reverse_geocoding: false
""",
        encoding="utf-8",
    )
    manifest["configSha256"] = sha256(config)
    identity = {
        "inputs": {k: v["sha256"] for k, v in manifest["inputs"].items()},
        "config": manifest["configSha256"],
        "engine": ENGINE_DIGEST,
        "schema": 1,
    }
    manifest["generationId"] = hashlib.sha256(
        json.dumps(identity, sort_keys=True).encode()
    ).hexdigest()
    manifest["state"] = "building"
    manifest["build"] = {"memoryCapBytes": 6 * 1024**3, "startedAt": datetime.now(UTC).isoformat()}
    save(manifest_path, manifest)
    # Random unique volume; never inspect/remove/reset a PoC volume.
    subprocess.run(["docker", "volume", "create", volume], check=True)
    command = [
        "docker",
        "run",
        "--name",
        f"{volume}-builder",
        "--memory",
        "6g",
        "--mount",
        f"type=volume,src={volume},dst=/data",
        "--mount",
        f"type=bind,src={inputs},dst=/input,readonly",
        "--mount",
        f"type=bind,src={config},dst=/config.yml,readonly",
        IMAGE,
        "/motis",
        "import",
        "-c",
        "/config.yml",
        "-d",
        "/data",
    ]
    print(f"Building {volume}; full log: {output / 'import.log'}", flush=True)
    started = time.perf_counter()
    with (output / "import.log").open("w", encoding="utf-8") as log:
        result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, check=False)
    manifest["build"].update(
        seconds=round(time.perf_counter() - started, 2),
        exitCode=result.returncode,
        finishedAt=datetime.now(UTC).isoformat(),
    )
    manifest["state"] = "ready" if result.returncode == 0 else "failed"
    manifest["builtAt"] = datetime.now(UTC).isoformat()
    save(manifest_path, manifest)
    if result.returncode:
        raise RuntimeError(f"MOTIS import failed; inspect {output / 'import.log'}")
    env = f"OPENTRANSIT_GENERATION_DIR={output.as_posix()}\nOPENTRANSIT_GRAPH_VOLUME={volume}\n"
    (output / "compose.env").write_text(env, encoding="utf-8")
    print(
        f"Prepared {manifest_path}. Start Compose with --env-file {output / 'compose.env'}",
        flush=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["prepare-m1"])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--osm-path", type=Path, help="Explicitly reuse a local OSM snapshot")
    args = parser.parse_args()
    prepare(args.output, args.osm_path)


if __name__ == "__main__":
    main()
