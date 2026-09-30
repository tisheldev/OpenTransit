import { clockTime, dateLabel, departureInstant, duration, israelWallTime, tomorrowMorning } from "./time.mjs";

const $ = id => document.getElementById(id);
const places = [
  ["dizengoff", "Dizengoff Center · Tel Aviv", 32.0757, 34.7748],
  ["technion", "Technion · Haifa", 32.7775, 35.0219],
  ["savidor", "Savidor Center station · Tel Aviv", 32.0838, 34.7983],
  ["navon", "Yitzhak Navon station · Jerusalem", 31.7878, 35.2026],
  ["hof", "Hof HaCarmel station · Haifa", 32.7934, 34.9577],
  ["beersheva", "Be'er Sheva Center station", 31.2436, 34.7987],
];
let map, endpointLayer, routeLayer, pickTarget = null, busy = false;
let requestText = "", responseText = "";
const railModes = new Set(["RAIL", "TRAIN", "TRAM", "SUBWAY", "METRO", "LIGHT_RAIL"]);
const isRail = leg => railModes.has(leg.mode.toUpperCase());

function textElement(tag, text, className = "") {
  const node = document.createElement(tag);
  node.textContent = text;
  node.className = className;
  return node;
}

function status(text, kind = "") {
  $("status").textContent = text;
  $("status").className = `status ${kind}`;
}

function point(which) {
  return { kind: "coordinate", latitude: Number($(`${which}-lat`).value), longitude: Number($(`${which}-lon`).value) };
}

function validPoint(p) {
  return Number.isFinite(p.latitude) && Number.isFinite(p.longitude)
    && p.latitude >= 29 && p.latitude <= 34 && p.longitude >= 34 && p.longitude <= 36;
}

function clearResults(message = "Inputs changed. Press Plan journey to update the route.") {
  $("journey").hidden = true;
  $("metadata").hidden = true;
  $("debug").hidden = true;
  routeLayer?.clearLayers();
  status(message);
}

function renderEndpoints(fit = false) {
  if (!map) return;
  endpointLayer.clearLayers();
  const bounds = [];
  for (const [which, letter] of [["from", "A"], ["to", "B"]]) {
    const p = point(which);
    if (!validPoint(p)) continue;
    const latlng = [p.latitude, p.longitude];
    bounds.push(latlng);
    L.marker(latlng, {
      icon: L.divIcon({ className: `point-label point-${which}`, html: letter, iconSize: [28, 28], iconAnchor: [14, 14] }),
      title: which === "from" ? "Origin" : "Destination",
    }).addTo(endpointLayer).bindPopup(textElement("span", `${letter}: ${p.latitude}, ${p.longitude}`));
  }
  if (fit && bounds.length) map.fitBounds(bounds, { padding: [50, 60], maxZoom: 14 });
}

function setPicker(which) {
  pickTarget = pickTarget === which ? null : which;
  for (const side of ["from", "to"]) $("pick-" + side).setAttribute("aria-pressed", String(pickTarget === side));
  $("map-hint").textContent = pickTarget
    ? `Click the map to set your ${pickTarget === "from" ? "origin (A)" : "destination (B)"}.`
    : "Choose points using the buttons on the left.";
  if (map) map.getContainer().style.cursor = pickTarget ? "crosshair" : "";
}

function initMap() {
  if (!globalThis.L) {
    $("map-hint").textContent = "Map unavailable. You can still plan using example places or coordinates.";
    $("pick-from").disabled = $("pick-to").disabled = true;
    return;
  }
  map = L.map("map", { scrollWheelZoom: false }).setView([32.35, 34.95], 9);
  const tiles = L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap contributors</a>',
  }).addTo(map);
  tiles.on("tileerror", () => { $("tile-warning").hidden = false; });
  tiles.on("tileload", () => { $("tile-warning").hidden = true; });
  endpointLayer = L.layerGroup().addTo(map);
  routeLayer = L.layerGroup().addTo(map);
  map.on("click", event => {
    if (!pickTarget || busy) return;
    const p = { latitude: event.latlng.lat, longitude: event.latlng.lng };
    if (!validPoint(p)) {
      status("Choose a point inside the supported coordinate range (latitude 29–34, longitude 34–36).", "error");
      return;
    }
    $(`${pickTarget}-lat`).value = p.latitude.toFixed(6);
    $(`${pickTarget}-lon`).value = p.longitude.toFixed(6);
    $(`${pickTarget}-preset`).value = "custom";
    const label = pickTarget === "from" ? "Origin" : "Destination";
    setPicker(pickTarget);
    clearResults(`${label} set. Press Plan journey to update the route.`);
    renderEndpoints();
  });
  new ResizeObserver(() => map.invalidateSize()).observe($("map"));
  renderEndpoints(true);
}

function selectPlace(which, id) {
  const place = places.find(p => p[0] === id);
  if (!place) return;
  $(`${which}-lat`).value = place[2];
  $(`${which}-lon`).value = place[3];
  $(`${which}-preset`).value = id;
}

for (const which of ["from", "to"]) {
  const select = $(`${which}-preset`);
  for (const [id, label] of [...places, ["custom", "Custom coordinates / map point"]]) {
    const option = textElement("option", label);
    option.value = id;
    select.append(option);
  }
  select.addEventListener("change", () => {
    selectPlace(which, select.value);
    clearResults();
    renderEndpoints(true);
  });
  for (const coordinate of ["lat", "lon"]) {
    $(`${which}-${coordinate}`).addEventListener("input", () => {
      select.value = "custom";
      clearResults();
      renderEndpoints();
    });
  }
  $("pick-" + which).addEventListener("click", () => setPicker(which));
}
selectPlace("from", "dizengoff");
selectPlace("to", "technion");
$("depart-at").value = tomorrowMorning();
initMap();

$("swap").addEventListener("click", () => {
  for (const suffix of ["preset", "lat", "lon"]) {
    const a = $("from-" + suffix), b = $("to-" + suffix);
    [a.value, b.value] = [b.value, a.value];
  }
  clearResults();
  renderEndpoints(true);
});
$("depart-now").addEventListener("click", () => {
  $("depart-at").value = israelWallTime();
  $("offset").value = "auto";
  clearResults();
});
for (const id of ["depart-at", "offset"]) $(id).addEventListener("input", () => clearResults());

function renderMetadata(meta) {
  const panel = $("metadata");
  panel.replaceChildren();
  panel.append(textElement("p", `Data: ${meta.mode === "fixture" ? "SYNTHETIC FIXTURE" : "real scheduled feed"} · Freshness: ${meta.freshness}`));
  if (meta.mode === "fixture") panel.append(textElement("p", "This response uses synthetic data, not a real route.", "warning"));
  for (const warning of meta.warnings) panel.append(textElement("p", `Warning: ${warning}`, "warning"));
  panel.append(textElement("p", `Service dates: ${dateLabel(meta.coverage.from)} to ${dateLabel(new Date(new Date(meta.coverage.until).getTime() - 1))} (Israel time).`));
  panel.append(textElement("p", `Built: ${dateLabel(meta.dataBuiltAt)} ${clockTime(meta.dataBuiltAt)} · Request: ${meta.requestId}`));
  panel.append(textElement("p", `Generation: ${meta.generationId}`));
  panel.hidden = false;
}

function drawJourney(journey) {
  if (!map) return;
  const points = [];
  for (const [index, leg] of journey.legs.entries()) {
    if (!leg.geometry) continue;
    // API GeoJSON uses longitude, latitude; Leaflet uses latitude, longitude.
    const latlngs = leg.geometry.coordinates.map(([lon, lat]) => [lat, lon]);
    points.push(...latlngs);
    const color = leg.kind === "walk" ? "#607681" : isRail(leg) ? "#8656b7" : "#3673ba";
    L.polyline(latlngs, { color, weight: leg.kind === "walk" ? 4 : 5, dashArray: leg.kind === "walk" ? "6 7" : null })
      .addTo(routeLayer).bindPopup(textElement("span", `${index + 1}. ${legTitle(leg)}`));
  }
  if (points.length) map.fitBounds(points, { padding: [45, 60], maxZoom: 16 });
}

function legTitle(leg) {
  if (leg.kind === "walk") return "Walk";
  const mode = isRail(leg) ? "Rail" : leg.mode.toLowerCase().replaceAll("_", " ");
  return `${mode[0].toUpperCase()}${mode.slice(1)} ${leg.transit?.routeShortName || ""}`.trim();
}

function locationName(location) {
  const which = location.name === "START" ? "from" : location.name === "END" ? "to" : null;
  if (!which) return location.name;
  const place = places.find(p => p[0] === $(`${which}-preset`).value);
  return place ? place[1] : which === "from" ? "Origin (A)" : "Destination (B)";
}

function renderJourney(journey) {
  const start = journey.timing.scheduledDeparture, end = journey.timing.scheduledArrival;
  $("time-range").textContent = `${clockTime(start)} → ${clockTime(end)}`;
  $("journey-date").textContent = dateLabel(start) === dateLabel(end)
    ? `${dateLabel(start)} · Israel time`
    : `${dateLabel(start)} → ${dateLabel(end)} · Israel time`;
  $("summary").replaceChildren(...[
    duration(journey.durationSeconds),
    `${journey.transfers} transfer${journey.transfers === 1 ? "" : "s"}`,
    `${duration(journey.walkingSeconds)} walking · ${(journey.walkingDistanceMeters / 1000).toFixed(1)} km`,
  ].map(text => textElement("span", text)));
  $("legs").replaceChildren();
  let previousArrival = null;
  for (const leg of journey.legs) {
    const node = $("leg-template").content.firstElementChild.cloneNode(true);
    if (leg.kind === "transit") node.classList.add("transit");
    if (isRail(leg)) node.classList.add("rail");
    node.querySelector(".leg-icon").textContent = leg.kind === "walk" ? "WALK" : isRail(leg) ? "RAIL" : "BUS";
    node.querySelector("h3").textContent = legTitle(leg);
    node.querySelector(".leg-duration").textContent = duration(leg.durationSeconds);
    node.querySelector(".leg-direction").textContent = leg.transit
      ? [leg.transit.operatorName, leg.transit.headsign ? `toward ${leg.transit.headsign}` : ""].filter(Boolean).join(" · ")
      : leg.distanceMeters == null ? "Walking connection" : `${Math.round(leg.distanceMeters)} m on foot`;
    for (const [selector, instant] of [[".departure", leg.timing.scheduledDeparture], [".arrival", leg.timing.scheduledArrival]]) {
      const time = node.querySelector(selector);
      time.textContent = `${clockTime(instant)}${dateLabel(instant) !== dateLabel(start) ? ` · ${dateLabel(instant)}` : ""}`;
      time.dateTime = instant;
    }
    node.querySelector(".from-name").textContent = locationName(leg.from);
    node.querySelector(".to-name").textContent = locationName(leg.to);
    const notes = [];
    if (previousArrival) {
      const wait = (new Date(leg.timing.scheduledDeparture) - new Date(previousArrival)) / 1000;
      if (wait > 0) notes.push(`${duration(wait)} wait before this leg`);
    }
    if (!leg.geometry) notes.push(`Map geometry unavailable: ${leg.geometryUnavailableReason || "not provided"}`);
    if (leg.transit) notes.push(`Service date ${leg.transit.serviceDate}`);
    node.querySelector(".leg-note").textContent = notes.join(" · ");
    node.querySelector(".leg-note").hidden = !notes.length;
    previousArrival = leg.timing.scheduledArrival;
    $("legs").append(node);
  }
  $("journey").hidden = false;
  drawJourney(journey);
}

$("planner").addEventListener("submit", async event => {
  event.preventDefault();
  if (busy) return;
  clearResults("Planning your scheduled journey…");
  let request;
  try {
    request = { from: point("from"), to: point("to"), departAt: departureInstant($("depart-at").value, $("offset").value) };
    if (!validPoint(request.from) || !validPoint(request.to)) throw new Error("Check both sets of coordinates.");
  } catch (error) {
    status(error.message, "error");
    return;
  }
  if (pickTarget) setPicker(pickTarget);
  busy = true;
  $("inputs").disabled = true;
  $("submit").textContent = "Planning…";
  $("journey").setAttribute("aria-busy", "true");
  requestText = JSON.stringify(request, null, 2);
  $("request-json").textContent = requestText;
  $("response-json").textContent = "Waiting for response…";
  $("debug").hidden = false;
  $("copy-status").textContent = "";
  responseText = "";
  try {
    const response = await fetch("/v1/journeys", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(request), signal: AbortSignal.timeout(10000),
    });
    const raw = await response.text();
    responseText = raw;
    let body;
    try { body = JSON.parse(raw); } catch { throw new Error(`API returned an unreadable response (HTTP ${response.status}).`); }
    responseText = JSON.stringify(body, null, 2);
    if (!response.ok) {
      const advice = {
        OUTSIDE_SERVICE_WINDOW: "Choose a departure inside the current graph's service dates (see the development runbook).",
        FEED_EXPIRED: "The local graph needs a fresh build; see the development runbook.",
        DATA_UNAVAILABLE: "Start the API with a verified generation; see the development runbook.",
        INVALID_REQUEST: "Check the coordinates and departure time.",
        ENGINE_UNAVAILABLE: "Check that the local MOTIS container is running.",
        ENGINE_TIMEOUT: "Try again; the routing engine did not respond in time.",
      };
      status(`${body.code || "REQUEST_FAILED"} (HTTP ${response.status}): ${body.detail || body.title || "Planning failed."} ${advice[body.code] || ""}${body.requestId ? ` Request: ${body.requestId}` : ""}`, "error");
      return;
    }
    renderMetadata(body.meta);
    if (body.data.outcome === "no_route") {
      status("No scheduled route found. Try different locations or another departure time.");
      return;
    }
    if (!body.data.journeys.length) throw new Error("API response contained no itinerary.");
    renderJourney(body.data.journeys[0]);
    status(body.meta.mode === "fixture" ? "Synthetic test itinerary received." : "Scheduled journey found. Check the legs and transfer times below.", "success");
  } catch (error) {
    $("journey").hidden = true;
    routeLayer?.clearLayers();
    status(error.name === "TimeoutError" ? "The request timed out. Check the local API and try again."
      : error instanceof TypeError ? "Cannot reach the local API. Check that it is running, then try again."
      : error.message, "error");
    if (!responseText) responseText = "No response received.";
  } finally {
    $("response-json").textContent = responseText;
    $("inputs").disabled = false;
    $("submit").textContent = "Plan journey →";
    $("journey").setAttribute("aria-busy", "false");
    busy = false;
  }
});

for (const kind of ["request", "response"]) {
  $("copy-" + kind).addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(kind === "request" ? requestText : responseText);
      $("copy-status").textContent = `${kind === "request" ? "Request" : "Response"} copied.`;
    } catch {
      $("copy-status").textContent = "Clipboard unavailable. Select and copy the JSON below.";
    }
  });
}
