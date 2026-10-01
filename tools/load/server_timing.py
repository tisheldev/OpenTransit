"""Offline join of k6 correlation records to existing sanitized API duration logs."""

import argparse
import json
import math
import re
from collections import defaultdict
from pathlib import Path

API_LINE = re.compile(
    r"request_id=([a-f0-9]{32}) route=(\S+) status=(\d{3}) duration_ms=([\d.]+)"
)
ROUTES = {
    "journeys": "/v1/journeys",
    "places": "/v1/places",
    "departures": "/v1/stops/{stop_id}/departures",
    "trips": "/v1/trips/{trip_ref}",
}


def distribution(values):
    if not values:
        return {"count": 0, "p50_ms": None, "p95_ms": None}
    values = sorted(values)

    def percentile(fraction):
        position = (len(values) - 1) * fraction
        lower, upper = math.floor(position), math.ceil(position)
        return round(values[lower] + (values[upper] - values[lower]) * (position - lower), 3)

    return {"count": len(values), "p50_ms": percentile(0.5), "p95_ms": percentile(0.95)}


def report(client_path, server_path):
    servers = {}
    for line in server_path.read_text(encoding="utf-8").splitlines():
        # Plain logs or one CloudWatch JSON message per line.
        if line.lstrip().startswith("{"):
            line = json.loads(line).get("message", "")
        match = API_LINE.search(line)
        if match:
            request_id, route, status, duration = match.groups()
            if request_id in servers:
                raise ValueError("Duplicate server request ID; export each line once")
            servers[request_id] = (route, int(status), float(duration))
    groups = defaultdict(lambda: {"client": [], "server": [], "residual": [], "unmatched": 0})
    seen = set()
    for line in client_path.read_text(encoding="utf-8").splitlines():
        if "OT_LOAD_TIMING " not in line:
            continue
        item = json.loads(line.split("OT_LOAD_TIMING ", 1)[1])
        endpoint, request_id = item["endpoint"], item["request_id"]
        if endpoint not in ROUTES:
            raise ValueError("Unknown endpoint in correlation record")
        client_ms = float(item["client_ms"])
        if not math.isfinite(client_ms) or client_ms < 0:
            raise ValueError("Invalid client duration")
        if request_id and request_id in seen:
            raise ValueError("Duplicate client request ID")
        seen.add(request_id)
        group = groups[endpoint]
        group["client"].append(client_ms)
        server = servers.get(request_id)
        if server is None:
            group["unmatched"] += 1
            continue
        route, status, server_ms = server
        if route != ROUTES[endpoint] or status != item["status"]:
            raise ValueError("Matched request has inconsistent route/status")
        group["server"].append(server_ms)
        group["residual"].append(client_ms - server_ms)
    if not groups:
        raise ValueError("No records; enable CORRELATE=1 and raw k6 logging")
    return {
        "boundary": "client=whole request; server=API middleware to response creation",
        "residualNote": (
            "Per-pair client minus server; includes network/TLS/body/measurement overhead, "
            "not pure network latency"
        ),
        "endpoints": {
            endpoint: {
                "client_round_trip": distribution(group["client"]),
                "server_duration": distribution(group["server"]),
                "paired_residual": distribution(group["residual"]),
                "unmatched_client_count": group["unmatched"],
            }
            for endpoint, group in sorted(groups.items())
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--client-log", type=Path, required=True)
    parser.add_argument("--server-log", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = report(args.client_log, args.server_log)
    with args.output.open("x", encoding="utf-8") as output:
        json.dump(result, output, indent=2)
        output.write("\n")


if __name__ == "__main__":
    main()
