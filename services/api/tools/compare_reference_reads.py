"""Compare the served reference reads with an earlier implementation on a real generation.

API-PERF package A evidence: stop/route detail, the slim stop lookup and routes?stopId
must return byte-identical JSON to the previous SQL paths. Read-only: the reference is
opened ``mode=ro&immutable=1`` and verified by its manifest digest (no integrity check).

    git show <rev>:services/api/src/opentransit/reference.py > /tmp/old_reference.py
    uv run --project services/api python services/api/tools/compare_reference_reads.py
        <generation dir> /tmp/old_reference.py <output.json>    # (one command line)

Timings are single-threaded, uncached (the store's LRU is bypassed) and native; they are
not HTTP or container latencies.
"""

import importlib.util
import json
import random
import statistics
import sys
import time
import tracemalloc
from pathlib import Path

from opentransit import reference as new_module
from opentransit.reference import ReferenceStore, _TranslationIndex

generation = Path(sys.argv[1])
spec = importlib.util.spec_from_file_location("old_reference", sys.argv[2])
old_module = importlib.util.module_from_spec(spec)
sys.modules["old_reference"] = old_module
spec.loader.exec_module(old_module)

manifest = json.loads((generation / "manifest.json").read_text(encoding="utf-8"))
reference_sha = manifest["artifacts"]["reference"]["sha256"]
started = time.perf_counter()
store = ReferenceStore(generation / "reference.sqlite", integrity_attested_sha256=reference_sha)
open_seconds = time.perf_counter() - started

old = object.__new__(old_module.ReferenceStore)
old.path = store.path
old._uri = store._uri
old.metadata = store.metadata
old.has_localities = store.has_localities


def dumps(value):
    return json.dumps(value, ensure_ascii=False)  # key order matters too


def timed(call, *args):
    began = time.perf_counter()
    result = call(*args)
    return result, (time.perf_counter() - began) * 1000


with store._connect() as connection:
    stops = [
        tuple(row)
        for row in connection.execute(
            "SELECT stop_id, source_id, parent_station FROM stops ORDER BY stop_id"
        )
    ]
    route_ids = [
        row[0] for row in connection.execute("SELECT route_id FROM routes ORDER BY route_id")
    ]
    parent_example = connection.execute(
        "SELECT parent_station FROM stops WHERE parent_station IS NOT NULL LIMIT 1"
    ).fetchone()[0]
traced = []
with store._connect() as connection:
    pass
connection.set_trace_callback(traced.append)
store._routes(parent_example, None, None, 20, None)
connection.set_trace_callback(None)
routes_sql = next(statement for statement in traced if "route_stops" in statement)
plan = [tuple(row) for row in connection.execute("EXPLAIN QUERY PLAN " + routes_sql)]

# Index memory, measured on a separate build of the same structures.
tracemalloc.start()
with store._connect() as connection:
    connection.row_factory = None
    indexes = [_TranslationIndex(connection, *pair) for pair in new_module.SERVED_TRANSLATIONS]
    translation_bytes = tracemalloc.get_traced_memory()[0]
    refs = ReferenceStore._load_stop_refs(connection)
    total_bytes = tracemalloc.get_traced_memory()[0]
tracemalloc.stop()
del indexes, refs

mismatches = {"stop": [], "stop_by_source": [], "stop_ref": [], "route": [], "routes_by_stop": []}
timings = {
    "stop_old": [],
    "stop_new": [],
    "route_old": [],
    "route_new": [],
    "routes_stop_old": [],
    "routes_stop_new": [],
}
parents = {parent for _, _, parent in stops if parent}
rng = random.Random(20261015)

# Old stop()/route() each scan the whole translations table (~0.5 s), so the old/new
# comparison covers every parent station plus a random sample; the slim lookup is
# compared with the new detail for every stop (and the sample ties that to the old one).
compared_stops = sorted(parents) + rng.sample([s[0] for s in stops if s[0] not in parents], 800)
by_id = {s[0]: s for s in stops}
for stop_id in compared_stops:
    source_id = by_id[stop_id][1]
    new, new_ms = timed(store._stop, stop_id)
    expected, old_ms = timed(old.stop, stop_id)
    timings["stop_old"].append(old_ms)
    timings["stop_new"].append(new_ms)
    if dumps(new) != dumps(expected):
        mismatches["stop"].append(stop_id)
    if dumps(store._stop(source_id)) != dumps(expected):
        mismatches["stop_by_source"].append(source_id)
for stop_id, source_id, _ in stops:
    detail = store._stop(stop_id)
    want = {
        "stop_id": detail["stop_id"],
        "source_id": detail["source_id"],
        "platform_code": detail["platform_code"],
        "children": [
            {
                "stop_id": c["stop_id"],
                "source_id": c["source_id"],
                "platform_code": c["platform_code"],
            }
            for c in detail["children"]
        ],
    }
    if store.stop_ref(stop_id) != want or store.stop_ref(source_id) != want:
        mismatches["stop_ref"].append(stop_id)

compared_routes = rng.sample(route_ids, 400)
for route_id in compared_routes:
    new, new_ms = timed(store._route, route_id, 20)
    expected, old_ms = timed(old.route, route_id)
    timings["route_old"].append(old_ms)
    timings["route_new"].append(new_ms)
    if dumps(new) != dumps(expected):
        mismatches["route"].append(route_id)

# routes?stopId: every parent station plus a sample of other stops, each page walked.
sample = sorted(parents) + rng.sample([s[0] for s in stops if s[0] not in parents], 1000)
pages_compared = 0
for stop_id in sample:
    cursor_new = cursor_old = None
    while True:
        new, new_ms = timed(store._routes, stop_id, None, None, 20, cursor_new)
        expected, old_ms = timed(old.routes, stop_id, None, None, 20, cursor_old)
        timings["routes_stop_old"].append(old_ms)
        timings["routes_stop_new"].append(new_ms)
        pages_compared += 1
        if dumps(new) != dumps(expected):
            mismatches["routes_by_stop"].append(stop_id)
            break
        if not new["next_cursor"]:
            break
        cursor_new, cursor_old = new["next_cursor"], expected["next_cursor"]


def summary(values):
    ordered = sorted(values)
    return {
        "n": len(values),
        "medianMs": round(statistics.median(ordered), 3),
        "p95Ms": round(ordered[int(0.95 * (len(ordered) - 1))], 3),
        "maxMs": round(ordered[-1], 3),
    }


report = {
    "openSecondsWithAttestedDigest": round(open_seconds, 1),
    "routesStopQueryPlan": [row[3] for row in plan],
    "inMemoryIndexBytes": {
        "translations": translation_bytes,
        "translationsPlusStopRefs": total_bytes,
    },
    "compared": {
        "stopsOldVsNew": len(compared_stops),
        "stopsBySourceIdOldVsNew": len(compared_stops),
        "stopRefsVsNewDetail": len(stops) * 2,
        "routesOldVsNew": len(compared_routes),
        "routesTotal": len(route_ids),
        "stopsTotal": len(stops),
        "routesByStopSelectors": len(sample),
        "routesByStopParentStations": len(parents),
        "routesByStopPages": pages_compared,
    },
    "mismatches": {key: len(value) for key, value in mismatches.items()},
    "mismatchExamples": {key: value[:10] for key, value in mismatches.items() if value},
    "timingsUncachedSingleThread": {key: summary(value) for key, value in timings.items()},
}
Path(sys.argv[3]).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
print(json.dumps(report, indent=2))
