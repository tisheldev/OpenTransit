"""Compare complete source identifiers without inferring realtime correctness."""

import hashlib
import json
import zipfile
from datetime import date
from pathlib import Path

from opentransit.build.prepare import rows, sha256


def compare_ids(previous: Path, candidate: Path, previous_date: date, candidate_date: date) -> dict:
    if candidate_date <= previous_date:
        raise ValueError("Candidate acquisition date must follow the previous date")
    counts = {}
    fields = {
        "stops": (
            "stop_name",
            "stop_code",
            "stop_lat",
            "stop_lon",
            "parent_station",
            "location_type",
        ),
        "routes": ("agency_id", "route_short_name", "route_long_name", "route_type"),
        "trips": ("route_id", "service_id", "trip_headsign", "direction_id", "shape_id"),
    }
    with zipfile.ZipFile(previous) as old, zipfile.ZipFile(candidate) as new:
        for table, column in (("stops", "stop_id"), ("routes", "route_id"), ("trips", "trip_id")):

            def values(archive, table=table, column=column):
                result = {}
                for row in rows(archive, table + ".txt"):
                    fingerprint = json.dumps([row.get(field, "") for field in fields[table]])
                    result[row[column]] = hashlib.sha256(fingerprint.encode()).digest()
                return result

            old_values, new_values = values(old), values(new)
            before, after = set(old_values), set(new_values)
            retained = len(before & after)
            changed = sorted(key for key in before & after if old_values[key] != new_values[key])
            counts[table] = {
                "previous": len(before),
                "candidate": len(after),
                "retained": retained,
                "added": len(after - before),
                "removed": len(before - after),
                "retainedFraction": retained / len(before) if before else None,
                "metadataChangedCount": len(changed),
                "metadataChangedSamples": changed[:20],
            }
    return {
        "previous": {"sha256": sha256(previous), "acquiredDate": previous_date.isoformat()},
        "candidate": {"sha256": sha256(candidate), "acquiredDate": candidate_date.isoformat()},
        "consecutiveDailyFeeds": (candidate_date - previous_date).days == 1,
        "acquisitionDatesVerified": False,
        "counts": counts,
        "scope": "Full source identifiers; supplied dates require provenance review. "
        "Overlap does not prove semantic stability or realtime matching.",
    }
