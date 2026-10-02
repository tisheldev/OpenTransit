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

// Raw requests may only reach this API. Resolving against the origin catches
// protocol-relative ("//host") and backslash ("/\host") paths that start with "/".
export function sameOriginTarget(path, origin) {
  let url;
  try { url = new URL(path, origin); } catch { url = null; }
  if (!url || url.origin !== origin) throw new Error("Raw requests go to this API only: enter a path such as /v1/status.");
  return url.pathname + url.search;
}

// The exact request line is what was sent; a decoded copy is added only for readability.
export function describeRequest(method, path) {
  let decoded = null;
  try { decoded = decodeURIComponent(path); } catch { /* malformed escapes: show the exact path only */ }
  return { exact: `${method} ${path}`, decoded: decoded !== null && decoded !== path ? decoded : null };
}

// Each call takes a ticket; only the newest ticket may render, so a slow earlier
// response cannot overwrite a newer one (for example after rapid map clicks).
export function latestOnly() {
  let latest = 0;
  return () => {
    const id = ++latest;
    return () => id === latest;
  };
}

// Labels for response meta. Fixture data must always be flagged as synthetic, and
// fields the response lacks (no generation loaded) are skipped, not shown as "undefined".
export function metaFacts(meta) {
  if (!meta) return null;
  const parts = [];
  if (meta.generationId == null) parts.push("no generation loaded");
  if (meta.freshness != null) parts.push(`freshness ${meta.freshness}`);
  if (meta.mode != null) parts.push(`mode ${meta.mode}`);
  const synthetic = meta.mode === "fixture";
  return { synthetic, caution: synthetic || meta.freshness !== "current", parts };
}

// Header pill: green only for a ready API serving current, real data.
export function pillState(httpStatus, body) {
  const d = body?.data;
  if (!d || typeof d.ready !== "boolean") return { tone: "bad", text: `API error (HTTP ${httpStatus})` };
  if (!d.ready) return { tone: "bad", text: `Not ready · data ${d.staticData} · routing ${d.routing}` };
  const facts = metaFacts(body.meta) ?? { synthetic: false, caution: true };
  const mode = facts.synthetic ? "SYNTHETIC fixture" : body.meta?.mode;
  return {
    tone: facts.caution ? "warn" : "ok",
    text: ["Ready", body.meta?.freshness, mode].filter(Boolean).join(" · "),
  };
}
