// Pure request builders for the API explorer, kept DOM-free so Node can test them.

const TRIP_REF = /^\d{8}_\d{2}:\d{2}(?::\d{2})?_mot60day_.+$/;

// Which endpoint opens an identifier: public stop/route IDs or a dated trip reference.
export function idKind(id) {
  if (typeof id !== "string") return null;
  if (id.startsWith("mot:stop:")) return "stop";
  if (id.startsWith("mot:route:")) return "route";
  if (TRIP_REF.test(id)) return "trip";
  return null;
}

// Blank values are omitted so the server's defaults apply; arrays repeat the key.
export function buildQuery(params) {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (Array.isArray(value)) for (const item of value) search.append(key, item);
    else if (value != null && String(value).trim() !== "") search.append(key, String(value).trim());
  }
  return search.toString();
}

function location(v, which) {
  const kind = v[`${which}Kind`];
  if (kind === "coordinate") {
    return { kind, latitude: Number(v[`${which}Lat`]), longitude: Number(v[`${which}Lon`]) };
  }
  if (kind === "stop") return { kind, stopId: v[`${which}Stop`] };
  if (kind === "place") return { kind, placeRef: v[`${which}Place`] };
  throw new Error(`Unknown ${which} kind: ${kind}`);
}

// Form values -> POST /v1/journeys body. Out-of-range values are sent as typed on
// purpose, so the explorer can show the API's own validation response.
export function buildJourneyRequest(v, toInstant) {
  const body = { from: location(v, "from"), to: location(v, "to") };
  body[v.anchor === "arriveBy" ? "arriveBy" : "departAt"] = toInstant(v.time, v.offset);
  if (v.modes) body.modes = v.modes;
  for (const name of ["results", "maxAccessWalkMinutes", "maxEgressWalkMinutes", "maxDirectWalkMinutes"]) {
    if (v[name] !== undefined && v[name] !== "") body[name] = Number(v[name]);
  }
  if (v.lang) body.lang = v.lang;
  return body;
}
