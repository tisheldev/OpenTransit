import type { Journey, Leg } from "../api/types";
import type { LonLat, MapPin, MapRouteLeg } from "./scene";

// Pure conversion from an API journey to what the map draws. No MapLibre here.

export interface JourneySceneOptions {
  /** Index into journey.legs of the highlighted leg (the current step); none if omitted. */
  activeLeg?: number | null;
  /** Labels for the two ends. The engine names coordinate ends "START"/"END"; pass the draft labels. */
  originLabel?: string | null;
  destinationLabel?: string | null;
}

export interface JourneyScene {
  route: MapRouteLeg[];
  pins: MapPin[];
}

/** Names the engine gives coordinate (non-stop) ends; never shown to the passenger. */
const ENGINE_PLACEHOLDER_NAMES = new Set(["START", "END"]);

function lonLat(location: { longitude: number; latitude: number }): LonLat {
  return [location.longitude, location.latitude];
}

function displayName(name: string, override: string | null | undefined): string {
  if (override) return override;
  return ENGINE_PLACEHOLDER_NAMES.has(name) ? "" : name;
}

/**
 * Line label: the route short name ("8", "142"). Rail legs carry an empty short name and a
 * train number as headsign, so they are labelled by the stop the passenger rides to; an empty
 * label is never drawn.
 */
export function legLabel(leg: Leg): string | null {
  if (leg.kind !== "transit" || !leg.transit) return null;
  const short = leg.transit.routeShortName.trim();
  if (short) return short;
  const to = leg.to.name.trim();
  return to && !ENGINE_PLACEHOLDER_NAMES.has(to) ? to : null;
}

function legCoordinates(leg: Leg): LonLat[] | null {
  const coords = leg.geometry?.coordinates;
  if (!coords || coords.length < 2) return null;
  const line: LonLat[] = [];
  for (const point of coords) {
    const [lon, lat] = point;
    if (typeof lon === "number" && typeof lat === "number") line.push([lon, lat]);
  }
  return line.length >= 2 ? line : null;
}

function samePosition(a: LonLat, b: LonLat): boolean {
  return Math.abs(a[0] - b[0]) < 1e-6 && Math.abs(a[1] - b[1]) < 1e-6;
}

export function journeyToScene(journey: Journey, options: JourneySceneOptions = {}): JourneyScene {
  const legs = journey.legs;
  const route: MapRouteLeg[] = legs.map((leg, index) => ({
    kind: leg.kind,
    mode: leg.mode,
    // A time-only walk (geometry null) draws no line: we never invent a straight one.
    coordinates: legCoordinates(leg),
    from: lonLat(leg.from),
    to: lonLat(leg.to),
    label: legLabel(leg),
    active: options.activeLeg === index,
  }));

  const pins: MapPin[] = [];
  const first = legs[0];
  const last = legs[legs.length - 1];
  if (!first || !last) return { route, pins };

  const origin = lonLat(first.from);
  const destination = lonLat(last.to);
  pins.push({ id: "origin", role: "origin", position: origin, label: displayName(first.from.name, options.originLabel) });

  let rides = 0;
  legs.forEach((leg, index) => {
    if (leg.kind !== "transit") return;
    const position = lonLat(leg.from);
    rides += 1;
    if (samePosition(position, origin)) return;
    pins.push({
      id: `board-${index}`,
      role: rides === 1 ? "stop" : "transfer",
      position,
      label: leg.from.name,
    });
  });

  pins.push({
    id: "destination",
    role: "destination",
    position: destination,
    label: displayName(last.to.name, options.destinationLabel),
  });
  return { route, pins };
}
