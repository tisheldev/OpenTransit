"""One-command scheduled demo: Dizengoff Center to Technion against a running API.

The command only calls ``POST /v1/journeys`` and prints what the response says. It never
fabricates realtime state: capabilities and timing labels are shown exactly as returned.
"""

import sys
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import httpx

ISRAEL = ZoneInfo("Asia/Jerusalem")
DEFAULT_API_URL = "http://127.0.0.1:8000"
# Same coordinates as services/api/examples/journey.json (approximate station/campus points).
DIZENGOFF_CENTER = {"kind": "coordinate", "latitude": 32.0757, "longitude": 34.7748}
TECHNION = {"kind": "coordinate", "latitude": 32.7775, "longitude": 35.0219}

EXIT_OK = 0
EXIT_NO_ROUTE = 1
EXIT_ERROR = 2


def default_depart_at(now: datetime | None = None) -> str:
    """Tomorrow 08:00 Israel time with its explicit UTC offset (never ambiguous at 08:00)."""
    local = (now or datetime.now(UTC)).astimezone(ISRAEL) + timedelta(days=1)
    return local.replace(hour=8, minute=0, second=0, microsecond=0).isoformat()


def build_request(depart_at: str, results: int, lang: str) -> dict:
    return {
        "from": DIZENGOFF_CENTER,
        "to": TECHNION,
        "departAt": depart_at,
        "results": results,
        "lang": lang,
    }


def _clock(value: str) -> str:
    return datetime.fromisoformat(value).astimezone(ISRAEL).strftime("%H:%M")


def _span(seconds: int) -> str:
    hours, minutes = divmod(round(seconds / 60), 60)
    return f"{hours}h{minutes:02d}m" if hours else f"{minutes}m"


def _leg_line(leg: dict) -> str:
    timing = leg["timing"]
    label = timing.get("timingState", "unknown")
    span = f"{_clock(timing['scheduledDeparture'])}-{_clock(timing['scheduledArrival'])}"
    route = ""
    if leg.get("transit"):
        transit = leg["transit"]
        route = (
            f" line {transit['routeShortName']} to {transit['headsign'] or '?'}"
            f" ({transit['operatorName']}, service date {transit['serviceDate']})"
        )
    places = f"{leg['from']['name']} -> {leg['to']['name']}"
    extra = ""
    if timing.get("expectedDeparture") or timing.get("expectedArrival"):
        extra = f" expected {timing.get('expectedDeparture')}/{timing.get('expectedArrival')}"
    return f"    {span}  {leg['mode']:<10} {places}{route}  [{label}{extra}]"


def format_summary(request_body: dict, response: dict, api_url: str) -> str:
    data, meta = response["data"], response["meta"]
    capabilities = meta.get("capabilities") or {}
    lines = [
        "OpenTransit scheduled journey demo (Dizengoff Center -> Technion)",
        f"  API:        {api_url}",
        f"  Requested:  departAt {request_body['departAt']} (Israel time)",
        f"  Generation: {meta['generationId']} ({meta['mode']} data, "
        f"freshness {meta['freshness']})",
        f"  Coverage:   {meta['coverage']['from']} .. {meta['coverage']['until']}",
        "  Times:      scheduled timetable only; predicted times and delays are not provided",
        f"  Realtime:   {capabilities.get('realtime', 'unavailable')}",
        f"  Alerts:     {capabilities.get('alerts', 'unavailable')}"
        f" (alerts list: {data.get('alerts')!r})",
        f"  Outcome:    {data['outcome']} ({len(data['journeys'])} journey(s))",
    ]
    for number, journey in enumerate(data["journeys"], start=1):
        timing = journey["timing"]
        lines.append("")
        lines.append(
            f"  Journey {number}: depart {_clock(timing['scheduledDeparture'])} "
            f"arrive {_clock(timing['scheduledArrival'])} "
            f"({_span(journey['durationSeconds'])}, {journey['transfers']} transfer(s), "
            f"walking {_span(journey['walkingSeconds'])} / "
            f"{journey['walkingDistanceMeters']:.0f} m)  [{timing.get('timingState', 'unknown')}]"
        )
        lines.extend(_leg_line(leg) for leg in journey["legs"])
    constraints = meta.get("appliedConstraints") or {}
    if constraints:
        shown = ", ".join(f"{key}={value}" for key, value in constraints.items())
        lines += ["", f"  Constraints: {shown}"]
    if meta.get("warnings"):
        lines.append("  Warnings:    " + ", ".join(meta["warnings"]))
    return "\n".join(lines)


def run_demo(
    api_url: str = DEFAULT_API_URL,
    depart_at: str | None = None,
    *,
    results: int = 3,
    lang: str = "en",
    client: httpx.Client | None = None,
    out=None,
    err=None,
) -> int:
    """Return 0 for routes, 1 for a successful empty search, 2 for any error."""
    out, err = out or sys.stdout, err or sys.stderr
    try:
        depart_at = depart_at or default_depart_at()
        if datetime.fromisoformat(depart_at).tzinfo is None:
            raise ValueError("--depart-at needs an explicit offset such as +03:00")
    except ValueError as exc:
        print(f"error: {exc}", file=err)
        return EXIT_ERROR
    body = build_request(depart_at, results, lang)
    owned = client is None
    client = client or httpx.Client(timeout=10.0)
    try:
        response = client.post(api_url.rstrip("/") + "/v1/journeys", json=body)
    except httpx.HTTPError as exc:
        print(f"error: cannot reach the API at {api_url} ({type(exc).__name__})", file=err)
        return EXIT_ERROR
    finally:
        if owned:
            client.close()
    try:
        payload = response.json()
    except ValueError:
        payload = None
    if response.status_code != 200:
        if isinstance(payload, dict) and "code" in payload:
            print(
                f"error: HTTP {response.status_code} {payload['code']}: {payload.get('detail', '')}"
                f" (requestId {payload.get('requestId', 'unknown')})",
                file=err,
            )
        else:
            print(f"error: HTTP {response.status_code} without a problem document", file=err)
        return EXIT_ERROR
    try:
        text = format_summary(body, payload, api_url)
    except KeyError, TypeError, ValueError, AttributeError:
        print("error: the API returned an unrecognised journey response", file=err)
        return EXIT_ERROR
    print(text, file=out)
    if payload["data"]["outcome"] != "routes_found" or not payload["data"]["journeys"]:
        print("\nno route found for this departure time", file=err)
        return EXIT_NO_ROUTE
    return EXIT_OK
