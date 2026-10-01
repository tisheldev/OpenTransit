// Manual explorer for every public endpoint. It talks only to this origin, stores
// nothing, and renders API text with textContent only.
import { clockTime, dateLabel, departureInstant, duration, israelWallTime, tomorrowMorning } from "./time.mjs";
import { buildJourneyRequest, buildQuery, idKind } from "./explorer-request.mjs";

const $ = id => document.getElementById(id);
const panel = name => document.querySelector(`[data-panel="${name}"]`);
const field = (form, name) => form.elements.namedItem(name);
const TIMEOUT_MS = 30000;

let map, layer, pickTarget = null;
let current = { request: "", response: "" };
const history = [];

// ---------- DOM helpers ----------

function h(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (value == null || value === false) continue;
    if (key === "class") node.className = value;
    else if (key.startsWith("on")) node.addEventListener(key.slice(2), value);
    else node.setAttribute(key, value === true ? "" : value);
  }
  for (const child of children.flat()) {
    if (child == null || child === false) continue;
    node.append(child instanceof Node ? child : String(child));
  }
  return node;
}

const button = (label, onclick, cls = "mini") => h("button", { type: "button", class: cls, onclick }, label);
const bdi = text => h("bdi", { dir: "auto" }, text ?? "—");

// An identifier rendered as a button that opens the matching endpoint.
function idLink(id) {
  if (!id) return h("span", { class: "muted" }, "—");
  const kind = idKind(id);
  const open = {
    stop: () => openStop(id),
    route: () => openRoute(id),
    trip: () => openTrip(id),
  }[kind];
  return open ? h("button", { type: "button", class: "id", title: `Open ${kind}`, onclick: open }, id) : h("code", {}, id);
}

function kv(rows) {
  return h("dl", { class: "kv" }, rows.filter(([, v]) => v !== undefined).flatMap(([k, v]) => [
    h("dt", {}, k),
    h("dd", {}, v instanceof Node ? v : v == null || v === "" ? h("span", { class: "muted" }, "—") : bdi(String(v))),
  ]));
}

function banner(text, kind = "") {
  $("banner").textContent = text;
  $("banner").className = `banner ${kind}`;
}

function showResult(...nodes) {
  $("result").replaceChildren(...nodes.flat().filter(Boolean));
}

// ---------- Transport ----------

async function call(method, path, body) {
  const started = performance.now();
  const init = { method, headers: { Accept: "application/json" }, signal: AbortSignal.timeout(TIMEOUT_MS) };
  if (body !== undefined) {
    init.headers["Content-Type"] = "application/json";
    init.body = typeof body === "string" ? body : JSON.stringify(body);
  }
  const shown = readable(path);
  current.request = `${method} ${shown}` + (init.body ? `\n\n${pretty(init.body)}` : "");
  $("ex-request").textContent = current.request;
  $("ex-response").textContent = "Waiting…";
  $("exchange-line").textContent = "";
  banner(`${method} ${shown} …`, "busy");
  document.body.setAttribute("aria-busy", "true");
  let status = 0, json = null, text = "";
  try {
    const response = await fetch(path, init);
    status = response.status;
    text = await response.text();
    try { json = JSON.parse(text); } catch { json = null; }
  } catch (error) {
    text = error.name === "TimeoutError" ? `Timed out after ${TIMEOUT_MS / 1000} s.` : `Network error: ${error.message}. Is the API running?`;
  } finally {
    document.body.removeAttribute("aria-busy");
  }
  const ms = Math.round(performance.now() - started);
  current.response = json ? JSON.stringify(json, null, 2) : text;
  $("ex-response").textContent = current.response;
  $("exchange-line").textContent = `· ${status || "no response"} · ${ms} ms`;
  const entry = { method, path: shown, status, ms, request: current.request, response: current.response };
  history.unshift(entry);
  history.length = Math.min(history.length, 50);
  renderHistory();
  const ok = status >= 200 && status < 300;
  if (ok) banner(`${method} ${shown} → ${status} in ${ms} ms`, "ok");
  else if (json?.code) banner(`${json.code} (HTTP ${status}): ${json.detail || json.title}${json.requestId ? ` · request ${json.requestId}` : ""}`, "error");
  else banner(status ? `HTTP ${status}` : text, "error");
  return { ok, status, json };
}

// Display only: Hebrew queries and IDs are easier to read decoded.
function readable(path) {
  try { return decodeURIComponent(path); } catch { return path; }
}

function pretty(text) {
  try { return JSON.stringify(JSON.parse(text), null, 2); } catch { return text; }
}

function renderHistory() {
  $("history").replaceChildren(...history.map(entry => h("li", {},
    h("button", { type: "button", class: "link", onclick: () => {
      $("ex-request").textContent = current.request = entry.request;
      $("ex-response").textContent = current.response = entry.response;
      $("exchange-line").textContent = `· ${entry.status || "no response"} · ${entry.ms} ms (from history)`;
      $("exchange").open = true;
    } }, `${entry.status || "ERR"} ${entry.method} ${entry.path}`),
    h("span", { class: "muted" }, ` ${entry.ms} ms`))));
}

// Problem responses are shown in full; the exchange panel already has the raw body.
function problemView(json, status) {
  if (!json) return h("p", { class: "warn" }, `No JSON body (HTTP ${status}).`);
  return h("div", { class: "card problem" },
    h("h3", {}, `${json.code || "ERROR"} · HTTP ${status}`),
    kv([["Detail", json.detail], ["Title", json.title], ["Type", json.type], ["Request", json.requestId]]),
    json.errors?.length ? h("ul", {}, json.errors.map(e => h("li", {}, Object.entries(e).map(([k, v]) => `${k}: ${v}`).join(" · ")))) : null);
}

function metaView(meta, extra = {}) {
  if (!meta) return null;
  const warnings = meta.warnings ?? [];
  return h("div", { class: "meta" },
    meta.mode === "fixture" ? h("p", { class: "warn" }, "SYNTHETIC FIXTURE data — not a real route or stop.") : null,
    h("span", {}, `freshness ${meta.freshness}`),
    h("span", {}, `mode ${meta.mode}`),
    meta.coverage ? h("span", {}, `coverage ${dateLabel(meta.coverage.from)} – ${dateLabel(new Date(new Date(meta.coverage.until) - 1))}`) : null,
    h("span", { title: meta.generationId }, `generation ${String(meta.generationId).slice(0, 12)}…`),
    h("span", {}, `request ${meta.requestId}`),
    ...Object.entries(extra).map(([k, v]) => h("span", {}, `${k} ${v}`)),
    ...warnings.map(w => h("span", { class: "warn-chip" }, w)));
}

function pager(tab, nextCursor, rerun) {
  if (!nextCursor) return h("p", { class: "muted" }, "End of results.");
  return button("Next page →", () => rerun(nextCursor), "secondary");
}

// ---------- Map ----------

function initMap() {
  if (!globalThis.L) {
    $("map-hint").textContent = "Map library unavailable; results still render below.";
    return;
  }
  map = L.map("map", { scrollWheelZoom: true }).setView([32.08, 34.78], 12);
  L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap contributors</a>',
  }).addTo(map);
  layer = L.layerGroup().addTo(map);
  map.on("click", event => onMapClick(event.latlng.lat, event.latlng.lng));
  new ResizeObserver(() => map.invalidateSize()).observe($("map"));
  setHint();
}

function setHint() {
  const tab = document.body.dataset.tab;
  $("map-hint").textContent = pickTarget ? `Click the map to set ${pickTarget === "from" ? "origin A" : "destination B"}.`
    : tab === "stops" ? "Click the map to list stops near that point."
    : tab === "places" ? "Click the map to set the search bias point (near)."
    : "";
}

function onMapClick(lat, lon) {
  const point = `${lat.toFixed(6)},${lon.toFixed(6)}`;
  const tab = document.body.dataset.tab;
  if (pickTarget) {
    setEndpoint(pickTarget, { kind: "coordinate", latitude: lat, longitude: lon });
    pickTarget = null;
    setHint();
    return;
  }
  if (tab === "stops") {
    const form = panel("stops");
    field(form, "near").value = point;
    form.querySelector('[name="selector"][value="near"]').checked = true;
    syncVisibility(form);
    form.requestSubmit();
  } else if (tab === "places") {
    field(panel("places"), "near").value = point;
    banner(`near set to ${point}. Press Search.`);
  }
}

function clearMap() { layer?.clearLayers(); }

function plotPoints(items, popup, fit = true) {
  if (!map) return;
  const bounds = [];
  for (const item of items) {
    const lat = item.latitude ?? item.coordinates?.latitude, lon = item.longitude ?? item.coordinates?.longitude;
    if (lat == null || lon == null) continue;
    bounds.push([lat, lon]);
    L.circleMarker([lat, lon], { radius: 6, color: "#0d6e69", weight: 2, fillColor: "#3fb6ae", fillOpacity: .8 })
      .addTo(layer).bindPopup(() => popup(item));
  }
  if (fit && bounds.length) map.fitBounds(bounds, { padding: [40, 40], maxZoom: 16 });
}

function plotLine(geometry, color, dashed = false) {
  if (!map || !geometry?.coordinates?.length) return [];
  const latlngs = geometry.coordinates.map(([lon, lat]) => [lat, lon]);  // GeoJSON is lon,lat.
  L.polyline(latlngs, { color, weight: dashed ? 4 : 5, dashArray: dashed ? "6 7" : null }).addTo(layer);
  return latlngs;
}

function endpointMarker(lat, lon, letter) {
  if (!map || lat == null) return;
  L.marker([lat, lon], { icon: L.divIcon({ className: `pin pin-${letter}`, html: letter, iconSize: [26, 26], iconAnchor: [13, 13] }) }).addTo(layer);
}

// ---------- Tabs and forms ----------

function showTab(name) {
  document.body.dataset.tab = name;
  for (const b of document.querySelectorAll("[data-tab]")) b.setAttribute("aria-current", String(b.dataset.tab === name));
  for (const p of document.querySelectorAll("[data-panel]")) p.hidden = p.dataset.panel !== name;
  pickTarget = null;
  setHint();
}

// Elements with data-show="name=value" are visible only when that control has that value.
function syncVisibility(form) {
  for (const node of form.querySelectorAll("[data-show]")) {
    const [name, value] = node.dataset.show.split("=");
    const control = field(form, name);
    const actual = control instanceof RadioNodeList ? control.value : control?.value;
    node.hidden = actual !== value;
  }
}

function values(form) {
  const data = {};
  for (const element of form.elements) {
    if (!element.name || element.type === "button" || element.type === "submit") continue;
    if (element.type === "checkbox") {
      (data[element.name] ??= []);
      if (element.checked) data[element.name].push(element.value);
    } else if (element.type === "radio") {
      if (element.checked) data[element.name] = element.value;
    } else data[element.name] = element.value.trim();
  }
  return data;
}

function onSubmit(name, handler) {
  panel(name).addEventListener("submit", event => {
    event.preventDefault();
    handler(values(panel(name))).catch(error => banner(error.message, "error"));
  });
}

// ---------- Status ----------

async function runStatus(path = "/v1/status") {
  const { ok, status, json } = await call("GET", path);
  clearMap();
  if (!ok) return showResult(problemView(json, status));
  if (path !== "/v1/status") return showResult(h("div", { class: "card" }, kv(Object.entries(json))));
  const d = json.data;
  showResult(h("div", { class: "card" },
    h("h3", {}, d.ready ? "Ready" : "Not ready"),
    kv([["Static data", d.staticData], ["Routing", d.routing], ["Reference", d.reference],
      ["Realtime", d.realtime], ["Alerts", d.alerts],
      ["Last validated", d.lastValidatedAt ? `${dateLabel(d.lastValidatedAt)} ${clockTime(d.lastValidatedAt)}` : null]])),
    metaView(json.meta));
}

async function refreshPill() {
  const pill = $("status-pill");
  try {
    const response = await fetch("/v1/status", { signal: AbortSignal.timeout(8000) });
    const body = await response.json();
    const d = body.data;
    pill.textContent = d.ready ? `Ready · ${body.meta.freshness} · ${body.meta.mode}` : `Not ready · data ${d.staticData} · routing ${d.routing}`;
    pill.className = `status-pill ${d.ready ? "ok" : "bad"}`;
  } catch {
    pill.textContent = "API unreachable";
    pill.className = "status-pill bad";
  }
}

// ---------- Places ----------

async function runPlaces(v) {
  const path = "/v1/places?" + buildQuery({ q: v.q, lang: v.lang, near: v.near, limit: v.limit, type: v.type });
  const { ok, status, json } = await call("GET", path);
  clearMap();
  if (!ok) return showResult(problemView(json, status));
  const items = json.data;
  plotPoints(items, item => placePopup(item));
  showResult(
    h("div", { class: "meta" },
      h("span", {}, `matched: ${json.matchedTypes.join(", ") || "none"}`),
      json.unavailableTypes.length ? h("span", { class: "warn-chip" }, `unavailable: ${json.unavailableTypes.join(", ")}`) : null,
      json.partial ? h("span", { class: "warn-chip" }, "partial") : null,
      h("span", {}, json.rankingPolicy)),
    items.length ? h("ol", { class: "list" }, items.map(item => h("li", { class: "card" }, placeCard(item))))
      : h("p", { class: "muted" }, "No candidates."),
    metaView(json.meta));
}

function placeCard(item) {
  const ref = item.locationRef ?? {};
  return [
    h("div", { class: "card-head" },
      h("span", { class: `kind kind-${item.kind}` }, item.kind),
      h("strong", {}, bdi(item.displayName)),
      item.locality ? h("span", { class: "muted" }, bdi(item.locality)) : null,
      item.distance != null ? h("span", { class: "muted" }, `${Math.round(item.distance)} m`) : null),
    kv([
      ["Ref", ref.kind === "stop" ? idLink(ref.stopId) : h("code", { class: "wrap" }, ref.placeRef ?? "—")],
      ["Lang", item.languageUsed],
      ["Code", item.stopCode],
      ["Parent", item.parentId ? idLink(item.parentId) : undefined],
      ["Platforms", item.platformIds?.length ? h("span", {}, item.platformIds.map(idLink)) : undefined],
    ]),
    h("div", { class: "row" },
      button("→ From", () => useLocation("from", item)),
      button("→ To", () => useLocation("to", item)),
      ref.kind === "stop" ? button("Departures", () => openDepartures(ref.stopId)) : null,
      ref.kind === "stop" ? button("Routes here", () => openRoutesAtStop(ref.stopId)) : null),
  ];
}

function placePopup(item) {
  return h("div", {}, h("strong", {}, bdi(item.displayName)), h("div", { class: "row" },
    button("→ From", () => useLocation("from", item)), button("→ To", () => useLocation("to", item))));
}

function useLocation(which, item) {
  const ref = item.locationRef;
  if (ref?.kind === "stop") setEndpoint(which, { kind: "stop", stopId: ref.stopId }, item.displayName);
  else if (ref?.kind === "place") setEndpoint(which, { kind: "place", placeRef: ref.placeRef }, item.displayName);
  else if (item.coordinates) setEndpoint(which, { kind: "coordinate", ...item.coordinates }, item.displayName);
}

// ---------- Stops ----------

async function runStops(v, cursor) {
  const params = v.selector === "bbox"
    ? { bbox: v.bbox, limit: v.limit, cursor }
    : { near: v.near, radius: v.radius, limit: v.limit, cursor };
  const { ok, status, json } = await call("GET", "/v1/stops?" + buildQuery(params));
  clearMap();
  if (!ok) return showResult(problemView(json, status));
  plotPoints(json.data, stop => h("div", {}, h("strong", {}, bdi(stop.name)), h("div", {}, idLink(stop.stopId))));
  if (v.selector !== "bbox" && map) {
    const [lat, lon] = v.near.split(",").map(Number);
    L.circle([lat, lon], { radius: Number(v.radius) || 500, color: "#8a9aa0", weight: 1, fill: false }).addTo(layer);
  }
  showResult(
    h("ol", { class: "list" }, json.data.map(stop => h("li", { class: "card" }, stopCard(stop)))),
    pager("stops", json.page?.nextCursor, next => runStops(v, next)),
    metaView(json.meta));
}

function stopCard(stop) {
  return [
    h("div", { class: "card-head" },
      h("strong", {}, bdi(stop.name)),
      stop.code ? h("span", { class: "muted" }, `code ${stop.code}`) : null,
      stop.distanceMeters != null ? h("span", { class: "muted" }, `${Math.round(stop.distanceMeters)} m`) : null),
    kv([["ID", idLink(stop.stopId)], ["Type", locationType(stop.locationType)], ["Platform", stop.platformCode ?? undefined],
      ["Parent", stop.parentStationId ? idLink(stop.parentStationId) : undefined]]),
    stopActions(stop.stopId, stop),
  ];
}

function stopActions(stopId, stop) {
  return h("div", { class: "row" },
    button("Departures", () => openDepartures(stopId)),
    button("Routes here", () => openRoutesAtStop(stopId)),
    button("→ From", () => setEndpoint("from", { kind: "stop", stopId }, stop?.name)),
    button("→ To", () => setEndpoint("to", { kind: "stop", stopId }, stop?.name)));
}

const locationType = t => ({ 0: "stop / platform", 1: "station", 2: "entrance", 3: "generic node", 4: "boarding area" })[t] ?? t;

async function runStop(stopId) {
  const { ok, status, json } = await call("GET", `/v1/stops/${encodeURIComponent(stopId)}`);
  clearMap();
  if (!ok) return showResult(problemView(json, status));
  const s = json.data;
  plotPoints([s, ...(s.children ?? [])], stop => h("div", {}, bdi(stop.name), h("div", {}, idLink(stop.stopId))));
  showResult(
    h("div", { class: "card" },
      h("h3", {}, bdi(s.name)),
      kv([["ID", idLink(s.stopId)], ["Source ID", s.sourceId], ["Code", s.code], ["Description", s.description],
        ["Type", locationType(s.locationType)], ["Platform", s.platformCode], ["Wheelchair", s.wheelchairBoarding],
        ["Coordinates", `${s.latitude}, ${s.longitude}`], ["Parent", s.parent ? idLink(s.parent.stopId) : null],
        ["Translations", s.translations ? h("span", {}, Object.entries(s.translations).map(([lang, text]) => h("span", { class: "tag" }, `${lang}: `, bdi(text)))) : null]]),
      stopActions(s.stopId, s)),
    s.children?.length ? h("div", { class: "card" }, h("h3", {}, `Children (${s.children.length})`),
      h("ul", { class: "plain" }, s.children.map(c => h("li", {}, idLink(c.stopId), " ", bdi(c.name), c.platformCode ? ` · platform ${c.platformCode}` : "")))) : null,
    h("div", { class: "card" }, h("h3", {}, `Routes serving this stop (${s.routes?.length ?? 0})`), routeTable(s.routes ?? [])),
    metaView(json.meta));
}

// ---------- Departures ----------

async function runDepartures(v, cursor) {
  const from = departureInstant(v.from, v.offset);
  const path = `/v1/stops/${encodeURIComponent(v.stopId)}/departures?` +
    buildQuery({ from, horizonMinutes: v.horizonMinutes, limit: v.limit, cursor });
  const { ok, status, json } = await call("GET", path);
  clearMap();
  if (!ok) return showResult(problemView(json, status));
  showResult(
    json.data.length ? h("table", { class: "table" },
      h("thead", {}, h("tr", {}, ["Time", "Line", "Headsign", "Platform", "Stop", "Trip"].map(t => h("th", {}, t)))),
      h("tbody", {}, json.data.map(d => h("tr", {},
        h("td", {}, h("time", { datetime: d.scheduledDeparture }, clockTime(d.scheduledDeparture)), h("div", { class: "muted small" }, dateLabel(d.scheduledDeparture))),
        h("td", {}, h("button", { type: "button", class: "id", onclick: () => openRoute(d.routeId), title: d.routeId }, d.routeShortName || d.routeId)),
        h("td", {}, bdi(d.headsign)),
        h("td", {}, d.platformCode ?? ""),
        h("td", {}, idLink(d.stopId)),
        h("td", {}, button("Trip", () => openTrip(d.tripRef)))))))
      : h("p", { class: "muted" }, "No departures in this window."),
    pager("departures", json.page?.nextCursor, next => runDepartures(v, next)),
    metaView(json.meta));
}

// ---------- Routes ----------

const routeType = t => ({ 0: "light rail", 1: "metro", 2: "rail", 3: "bus", 715: "on-demand" })[t] ?? t;

function routeTable(routes) {
  if (!routes.length) return h("p", { class: "muted" }, "None.");
  return h("table", { class: "table" },
    h("thead", {}, h("tr", {}, ["Line", "Name", "Type", "Operator", "ID"].map(t => h("th", {}, t)))),
    h("tbody", {}, routes.map(r => h("tr", {},
      h("td", {}, h("strong", {}, r.routeShortName ?? "")),
      h("td", {}, bdi(r.routeLongName)),
      h("td", {}, routeType(r.routeType)),
      h("td", {}, h("button", { type: "button", class: "id", onclick: () => openRoutesByOperator(r.operatorId) }, r.operatorId ?? "")),
      h("td", {}, idLink(r.routeId))))));
}

async function runRoutes(v, cursor) {
  const path = "/v1/routes?" + buildQuery({ routeShortName: v.routeShortName, operatorId: v.operatorId, stopId: v.stopId, limit: v.limit, cursor });
  const { ok, status, json } = await call("GET", path);
  clearMap();
  if (!ok) return showResult(problemView(json, status));
  showResult(routeTable(json.data), pager("routes", json.page?.nextCursor, next => runRoutes(v, next)), metaView(json.meta));
}

async function runRoute(routeId) {
  const { ok, status, json } = await call("GET", `/v1/routes/${encodeURIComponent(routeId)}`);
  clearMap();
  if (!ok) return showResult(problemView(json, status));
  const r = json.data;
  showResult(
    h("div", { class: "card" },
      h("h3", {}, `Line ${r.routeShortName ?? ""} `, bdi(r.routeLongName)),
      kv([["ID", idLink(r.routeId)], ["Source ID", r.sourceId], ["Type", routeType(r.routeType)], ["Description", r.description],
        ["Operator", r.agency ? h("span", {}, bdi(r.agency.name), " · ", h("button", { type: "button", class: "id", onclick: () => openRoutesByOperator(r.operatorId) }, r.operatorId)) : r.operatorId],
        ["Colour", r.color ? h("span", { class: "swatch", style: `background:#${/^[0-9a-f]{6}$/i.test(r.color) ? r.color : "ccc"}` }, r.color) : null],
        ["Translations", r.translations ? h("span", {}, Object.entries(r.translations).map(([lang, text]) => h("span", { class: "tag" }, `${lang}: `, bdi(text)))) : null]]),
      h("div", { class: "row" }, button("All patterns with stops", () => runPatterns(r.routeId)))),
    h("div", { class: "card" },
      h("h3", {}, `Patterns (${r.patterns_count ?? r.patterns?.length ?? 0}${r.patterns_truncated ? ", truncated" : ""})`),
      h("ul", { class: "plain" }, (r.patterns ?? []).map(p => h("li", {}, h("code", {}, p.patternId), ` · direction ${p.directionId ?? "—"} · `, bdi(p.headsign))))),
    metaView(json.meta));
}

async function runPatterns(routeId, cursor) {
  const query = buildQuery({ cursor });
  const { ok, status, json } = await call("GET", `/v1/routes/${encodeURIComponent(routeId)}/patterns${query ? `?${query}` : ""}`);
  clearMap();
  if (!ok) return showResult(problemView(json, status));
  showResult(
    json.data.map(p => h("details", { class: "card" },
      h("summary", {}, h("code", {}, p.patternId), ` · direction ${p.directionId ?? "—"} · `, bdi(p.headsign), ` · ${p.stops?.length ?? 0} stops`),
      h("ol", { class: "plain stops" }, (p.stops ?? []).map(s => h("li", {}, `${s.sequence}. `, idLink(s.stopId),
        s.pickupType ? h("span", { class: "muted" }, ` pickup ${s.pickupType}`) : null,
        s.dropOffType ? h("span", { class: "muted" }, ` drop-off ${s.dropOffType}`) : null))))),
    pager("patterns", json.page?.nextCursor, next => runPatterns(routeId, next)),
    metaView(json.meta));
}

// ---------- Trip ----------

async function runTrip(tripRef) {
  const { ok, status, json } = await call("GET", `/v1/trips/${encodeURIComponent(tripRef)}`);
  clearMap();
  if (!ok) return showResult(problemView(json, status));
  const t = json.data;
  const line = plotLine(t.shape, "#3673ba");
  if (line.length) map.fitBounds(line, { padding: [30, 30] });
  showResult(
    h("div", { class: "card" },
      h("h3", {}, `Line ${t.routeShortName} → `, bdi(t.headsign)),
      kv([["Trip ref", h("code", { class: "wrap" }, t.tripRef)], ["Source trip", t.sourceTripId], ["Service date", t.serviceDate],
        ["Start time", t.startTime], ["Route", idLink(t.routeId)], ["Timing", t.timingState], ["Alerts", t.alerts],
        ["Shape", t.shape ? `${t.shape.coordinates.length} points` : "unavailable"]])),
    h("table", { class: "table" },
      h("thead", {}, h("tr", {}, ["#", "Stop", "Arrive", "Depart", "Pickup", "Drop-off"].map(x => h("th", {}, x)))),
      h("tbody", {}, t.calls.map(c => h("tr", {},
        h("td", {}, c.callSequence), h("td", {}, idLink(c.stopId)),
        h("td", {}, c.scheduledArrival ? clockTime(c.scheduledArrival) : "—"),
        h("td", {}, c.scheduledDeparture ? clockTime(c.scheduledDeparture) : "—"),
        h("td", {}, c.pickupType), h("td", {}, c.dropOffType))))),
    metaView(json.meta));
}

// ---------- Journeys ----------

function setEndpoint(which, location, label) {
  const form = panel("journeys");
  field(form, `${which}Kind`).value = location.kind;
  if (location.kind === "coordinate") {
    field(form, `${which}Lat`).value = Number(location.latitude).toFixed(6);
    field(form, `${which}Lon`).value = Number(location.longitude).toFixed(6);
  } else if (location.kind === "stop") field(form, `${which}Stop`).value = location.stopId;
  else field(form, `${which}Place`).value = location.placeRef;
  field(form, `${which}Label`).value = label ?? "";
  syncVisibility(form);
  banner(`${which === "from" ? "Origin A" : "Destination B"} set (${location.kind}${label ? `: ${label}` : ""}). Open Journeys to plan.`, "ok");
}

async function runJourneys(v) {
  const body = buildJourneyRequest(v, departureInstant);
  const { ok, status, json } = await call("POST", "/v1/journeys", body);
  clearMap();
  if (!ok) return showResult(problemView(json, status));
  const meta = json.meta;
  const constraints = h("details", { class: "card" }, h("summary", {}, "Applied constraints and ranking"),
    kv([["Ranking policy", meta.rankingPolicy], ...Object.entries(meta.appliedConstraints ?? {}).map(([k, val]) => [k, typeof val === "object" ? JSON.stringify(val) : val])]));
  if (json.data.outcome === "no_route") {
    return showResult(h("p", { class: "card warn" }, "Outcome no_route: no scheduled journey for these inputs."), constraints, metaView(meta));
  }
  const cards = json.data.journeys.map((journey, index) => journeyCard(journey, index, v));
  showResult(h("p", { class: "muted" }, `${json.data.journeys.length} alternative(s). Click one to draw it.`), cards, constraints, metaView(meta));
  drawJourney(json.data.journeys[0]);
  cards[0]?.classList.add("selected");
}

function journeyCard(journey, index, v) {
  const t = journey.timing;
  const card = h("article", { class: "card journey", tabindex: "0" },
    h("div", { class: "card-head" },
      h("strong", {}, `${index + 1}. ${clockTime(t.scheduledDeparture)} → ${clockTime(t.scheduledArrival)}`),
      h("span", { class: "muted" }, dateLabel(t.scheduledDeparture)),
      h("span", { class: "tag" }, duration(journey.durationSeconds)),
      h("span", { class: "tag" }, `${journey.transfers} transfer${journey.transfers === 1 ? "" : "s"}`),
      h("span", { class: "tag" }, `walk ${duration(journey.walkingSeconds)} · ${journey.walkingDistanceMeters == null ? "distance unknown" : `${Math.round(journey.walkingDistanceMeters)} m`}`),
      h("span", { class: "tag scheduled" }, t.timingState)),
    h("ol", { class: "legs" }, journey.legs.map(leg => legItem(leg, v))));
  const select = () => {
    for (const other of document.querySelectorAll(".journey.selected")) other.classList.remove("selected");
    card.classList.add("selected");
    clearMap();
    drawJourney(journey);
  };
  card.addEventListener("click", event => { if (!event.target.closest("button")) select(); });
  card.addEventListener("keydown", event => { if (event.key === "Enter") select(); });
  return card;
}

function legItem(leg, v) {
  const name = (loc, which) => loc.name === "START" ? v.fromLabel || "Origin (A)" : loc.name === "END" ? v.toLabel || "Destination (B)" : loc.name;
  const tr = leg.transit;
  return h("li", { class: `leg leg-${leg.kind}` },
    h("div", { class: "leg-head" },
      h("span", { class: `kind kind-${leg.kind}` }, leg.kind === "walk" ? "walk" : leg.mode.toLowerCase()),
      tr ? h("strong", {}, `Line ${tr.routeShortName}`) : h("strong", {}, "Walk"),
      tr?.headsign ? h("span", {}, "→ ", bdi(tr.headsign)) : null,
      h("span", { class: "muted" }, `${clockTime(leg.timing.scheduledDeparture)}–${clockTime(leg.timing.scheduledArrival)} · ${duration(leg.durationSeconds)}`),
      leg.distanceMeters != null ? h("span", { class: "muted" }, `${Math.round(leg.distanceMeters)} m`) : null),
    h("div", { class: "small" }, bdi(name(leg.from)), leg.from.stopId ? [" ", idLink(leg.from.stopId)] : null,
      " → ", bdi(name(leg.to)), leg.to.stopId ? [" ", idLink(leg.to.stopId)] : null),
    tr ? h("div", { class: "small" }, bdi(tr.operatorName), " · ", idLink(tr.routeId), ` · service ${tr.serviceDate} ${tr.startTime} · `,
      button("Trip", () => openTrip(tr.engineTripId))) : null,
    !leg.geometry ? h("div", { class: "small warn" }, `No geometry: ${leg.geometryUnavailableReason ?? "not provided"}`) : null);
}

function drawJourney(journey) {
  if (!map) return;
  const points = [];
  for (const leg of journey.legs) {
    const rail = ["RAIL", "TRAIN", "TRAM", "SUBWAY", "METRO", "LIGHT_RAIL"].includes(leg.mode.toUpperCase());
    points.push(...plotLine(leg.geometry, leg.kind === "walk" ? "#607681" : rail ? "#8656b7" : "#3673ba", leg.kind === "walk"));
  }
  const first = journey.legs[0]?.from, last = journey.legs.at(-1)?.to;
  endpointMarker(first?.latitude, first?.longitude, "A");
  endpointMarker(last?.latitude, last?.longitude, "B");
  if (points.length) map.fitBounds(points, { padding: [40, 40], maxZoom: 16 });
}

// ---------- Raw ----------

const examples = [
  ["Status", "GET", "/v1/status"],
  ["OpenAPI schema", "GET", "/openapi.json"],
  ["Place search, English, stations only", "GET", "/v1/places?q=Savidor&lang=en&type=station"],
  ["Invalid: places q too short (422)", "GET", "/v1/places?q=a"],
  ["Invalid: stops with both near and bbox (422)", "GET", "/v1/stops?near=32.07,34.77&bbox=34.7,32,34.8,32.1"],
  ["Invalid: unknown stop (404)", "GET", "/v1/stops/mot:stop:does-not-exist"],
  ["Invalid: departures without offset (422)", "GET", "/v1/stops/mot:stop:1/departures?from=2026-10-02T08:00:00"],
  ["Invalid: bad trip reference (422)", "GET", "/v1/trips/not-a-trip"],
  ["Journey (arrive-by, rail only)", "POST", "/v1/journeys", () => ({
    from: { kind: "coordinate", latitude: 32.0838, longitude: 34.7983 },
    to: { kind: "coordinate", latitude: 32.7934, longitude: 34.9577 },
    arriveBy: departureInstant(tomorrowMorning().replace("08:00", "10:00")), modes: ["rail"], results: 2 })],
  ["Invalid: journey with both departAt and arriveBy (422)", "POST", "/v1/journeys", () => ({
    from: { kind: "coordinate", latitude: 32.0757, longitude: 34.7748 },
    to: { kind: "coordinate", latitude: 32.7775, longitude: 35.0219 },
    departAt: departureInstant(tomorrowMorning()), arriveBy: departureInstant(tomorrowMorning()) })],
  ["Invalid: journey coordinate outside Israel (422)", "POST", "/v1/journeys", () => ({
    from: { kind: "coordinate", latitude: 40, longitude: 34.7748 },
    to: { kind: "coordinate", latitude: 32.7775, longitude: 35.0219 }, departAt: departureInstant(tomorrowMorning()) })],
  ["Invalid: stale place reference (422)", "POST", "/v1/journeys", () => ({
    from: { kind: "place", placeRef: "bogus" },
    to: { kind: "coordinate", latitude: 32.7775, longitude: 35.0219 }, departAt: departureInstant(tomorrowMorning()) })],
];

async function runRaw(v) {
  if (!v.path.startsWith("/")) throw new Error("Path must start with / (same-origin only).");
  let body;
  if (v.method === "POST") {
    body = v.body || "{}";
    try { JSON.parse(body); } catch { banner("Body is not valid JSON; sending it anyway to see the server's answer.", "error"); }
  }
  const { ok, status, json } = await call(v.method, v.path, body);
  clearMap();
  showResult(ok ? h("p", { class: "muted" }, "See the raw response below.") : problemView(json, status));
}

// ---------- Cross-navigation ----------

function openStop(stopId) {
  showTab("stops");
  field(panel("stops"), "stopId").value = stopId;
  runStop(stopId);
}

function openDepartures(stopId) {
  showTab("departures");
  const form = panel("departures");
  field(form, "stopId").value = stopId;
  if (!field(form, "from").value) field(form, "from").value = israelWallTime();
  form.requestSubmit();
}

function openRoutesAtStop(stopId) {
  showTab("routes");
  const form = panel("routes");
  for (const name of ["routeShortName", "operatorId"]) field(form, name).value = "";
  field(form, "stopId").value = stopId;
  form.requestSubmit();
}

function openRoutesByOperator(operatorId) {
  showTab("routes");
  const form = panel("routes");
  for (const name of ["routeShortName", "stopId"]) field(form, name).value = "";
  field(form, "operatorId").value = operatorId;
  form.requestSubmit();
}

function openRoute(routeId) {
  showTab("routes");
  field(panel("routes"), "routeId").value = routeId;
  runRoute(routeId);
}

function openTrip(tripRef) {
  showTab("trip");
  field(panel("trip"), "tripRef").value = tripRef;
  runTrip(tripRef);
}

// ---------- Wiring ----------

function wire() {
  for (const b of document.querySelectorAll("[data-tab]")) b.addEventListener("click", () => showTab(b.dataset.tab));
  for (const form of document.querySelectorAll("[data-panel]")) {
    form.addEventListener("change", () => syncVisibility(form));
    syncVisibility(form);
  }
  onSubmit("status", () => runStatus());
  for (const b of document.querySelectorAll("[data-run]")) b.addEventListener("click", () => runStatus(b.dataset.run));
  onSubmit("places", runPlaces);
  onSubmit("stops", v => runStops(v));
  onSubmit("departures", v => runDepartures(v));
  onSubmit("routes", v => runRoutes(v));
  onSubmit("trip", v => runTrip(v.tripRef));
  onSubmit("journeys", runJourneys);
  onSubmit("raw", runRaw);

  const guard = fn => () => fn().catch(error => banner(error.message, "error"));
  $("stop-detail").addEventListener("click", guard(async () => {
    const id = field(panel("stops"), "stopId").value.trim();
    if (!id) throw new Error("Enter a stop ID, or click one in a result.");
    return runStop(id);
  }));
  const routeId = () => {
    const id = field(panel("routes"), "routeId").value.trim();
    if (!id) throw new Error("Enter a route ID, or click one in a result.");
    return id;
  };
  $("route-detail").addEventListener("click", guard(async () => runRoute(routeId())));
  $("route-patterns").addEventListener("click", guard(async () => runPatterns(routeId())));
  $("bbox-from-map").addEventListener("click", () => {
    if (!map) return;
    const b = map.getBounds();
    field(panel("stops"), "bbox").value = [b.getWest(), b.getSouth(), b.getEast(), b.getNorth()].map(n => n.toFixed(5)).join(",");
  });

  for (const b of document.querySelectorAll("[data-now]")) {
    b.addEventListener("click", () => { field(b.closest("form"), b.dataset.now).value = israelWallTime(); });
  }
  field(panel("departures"), "from").value = israelWallTime();
  field(panel("journeys"), "time").value = tomorrowMorning();

  for (const b of document.querySelectorAll("[data-pick]")) {
    b.addEventListener("click", () => { pickTarget = b.dataset.pick; setHint(); });
  }
  $("swap").addEventListener("click", () => {
    const form = panel("journeys");
    for (const suffix of ["Kind", "Lat", "Lon", "Stop", "Place", "Label"]) {
      const a = field(form, "from" + suffix), b = field(form, "to" + suffix);
      [a.value, b.value] = [b.value, a.value];
    }
    syncVisibility(form);
  });

  const select = $("raw-examples");
  select.append(h("option", { value: "" }, "Choose an example…"), ...examples.map(([label], i) => h("option", { value: String(i) }, label)));
  select.addEventListener("change", () => {
    const example = examples[Number(select.value)];
    if (!example) return;
    const form = panel("raw");
    field(form, "method").value = example[1];
    field(form, "path").value = example[2];
    field(form, "body").value = example[3] ? JSON.stringify(example[3](), null, 2) : "";
  });

  for (const b of document.querySelectorAll("[data-copy]")) {
    b.addEventListener("click", async () => {
      try { await navigator.clipboard.writeText(current[b.dataset.copy]); banner(`${b.dataset.copy} copied.`, "ok"); }
      catch { banner("Clipboard unavailable; select the text instead.", "error"); }
    });
  }
  $("status-pill").addEventListener("click", () => { refreshPill(); showTab("status"); runStatus(); });
}

wire();
showTab("status");
initMap();
refreshPill();
