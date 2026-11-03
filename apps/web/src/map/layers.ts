import type { LonLat, MapPin, MapRouteLeg, MapScene, MapUser } from "./scene";

// Pure scene → GeoJSON and style helpers (no MapLibre import), so they unit-test in jsdom.

export interface Feature<G, P> {
  type: "Feature";
  geometry: G;
  properties: P;
}
export interface FeatureCollection<G, P> {
  type: "FeatureCollection";
  features: Feature<G, P>[];
}
type LineString = { type: "LineString"; coordinates: LonLat[] };
type Point = { type: "Point"; coordinates: LonLat };
type Polygon = { type: "Polygon"; coordinates: LonLat[][] };

export interface RouteProps {
  kind: MapRouteLeg["kind"];
  mode: string;
  active: boolean;
  label: string;
}

/** One line per leg that has geometry; a time-only walk (coordinates null) adds nothing. */
export function routeFeatures(route: MapRouteLeg[]): FeatureCollection<LineString, RouteProps> {
  const features: Feature<LineString, RouteProps>[] = [];
  for (const leg of route) {
    if (!leg.coordinates || leg.coordinates.length < 2) continue;
    features.push({
      type: "Feature",
      geometry: { type: "LineString", coordinates: leg.coordinates },
      properties: { kind: leg.kind, mode: leg.mode, active: leg.active === true, label: leg.label ?? "" },
    });
  }
  return { type: "FeatureCollection", features };
}

export function pinFeatures(pins: MapPin[]): FeatureCollection<Point, { id: string; role: MapPin["role"]; label: string }> {
  return {
    type: "FeatureCollection",
    features: pins.map((pin) => ({
      type: "Feature",
      geometry: { type: "Point", coordinates: pin.position },
      properties: { id: pin.id, role: pin.role, label: pin.label },
    })),
  };
}

export function userFeatures(user: MapUser | null): FeatureCollection<Point, Record<string, never>> {
  return {
    type: "FeatureCollection",
    features: user ? [{ type: "Feature", geometry: { type: "Point", coordinates: user.position }, properties: {} }] : [],
  };
}

const EARTH_RADIUS_M = 6_371_008.8;

/** Accuracy circle as a polygon (metres are not a pixel radius, so a circle layer will not do). */
export function accuracyFeatures(user: MapUser | null, steps = 48): FeatureCollection<Polygon, Record<string, never>> {
  if (!user || !user.accuracyMeters || user.accuracyMeters <= 0) return { type: "FeatureCollection", features: [] };
  const [lon, lat] = user.position;
  const latRad = (lat * Math.PI) / 180;
  const dLat = (user.accuracyMeters / EARTH_RADIUS_M) * (180 / Math.PI);
  const dLon = dLat / Math.max(Math.cos(latRad), 1e-6);
  const ring: LonLat[] = [];
  for (let i = 0; i <= steps; i += 1) {
    const angle = (i / steps) * 2 * Math.PI;
    ring.push([lon + dLon * Math.cos(angle), lat + dLat * Math.sin(angle)]);
  }
  return { type: "FeatureCollection", features: [{ type: "Feature", geometry: { type: "Polygon", coordinates: [ring] }, properties: {} }] };
}

/** [[west, south], [east, north]] of everything a "fit" camera should frame; null if nothing. */
export function sceneBounds(scene: MapScene): [LonLat, LonLat] | null {
  let west = Infinity;
  let south = Infinity;
  let east = -Infinity;
  let north = -Infinity;
  const add = ([lon, lat]: LonLat) => {
    west = Math.min(west, lon);
    east = Math.max(east, lon);
    south = Math.min(south, lat);
    north = Math.max(north, lat);
  };
  for (const leg of scene.route) {
    add(leg.from);
    add(leg.to);
    for (const point of leg.coordinates ?? []) add(point);
  }
  for (const pin of scene.pins) add(pin.position);
  if (!Number.isFinite(west)) return null;
  return [
    [west, south],
    [east, north],
  ];
}

/** Tel Aviv area: the default view when nothing is drawn. */
export const DEFAULT_CENTER: LonLat = [34.7818, 32.0853];
export const DEFAULT_ZOOM = 11;

export const OPENFREEMAP_STYLE = "https://tiles.openfreemap.org/styles/liberty";

/**
 * Offline style for fixture mode and tests: a background only, so no request leaves the
 * origin and no glyphs are needed (route labels are skipped without a glyph source).
 */
export const OFFLINE_STYLE = {
  version: 8 as const,
  name: "OpenTransit offline",
  sources: {},
  layers: [{ id: "background", type: "background" as const, paint: { "background-color": "#e6ecee" } }],
};

/** Which style to load: VITE_MAP_STYLE overrides; fixtures and tests stay offline. */
export function chooseStyle(mode: string, override: string | undefined): string | typeof OFFLINE_STYLE {
  if (override) return override === "offline" ? OFFLINE_STYLE : override;
  if (mode === "fixtures" || mode === "test") return OFFLINE_STYLE;
  return OPENFREEMAP_STYLE;
}

/** Label language: Hebrew names in Hebrew, Latin/English in English, then the local name. */
export function nameExpression(lang: "he" | "en"): unknown[] {
  return lang === "he"
    ? ["coalesce", ["get", "name:he"], ["get", "name"]]
    : ["coalesce", ["get", "name:en"], ["get", "name:latin"], ["get", "name"]];
}

/** True for a text-field that shows a feature name (not a house number or a road ref). */
export function isNameTextField(field: unknown): boolean {
  if (field == null) return false;
  const text = typeof field === "string" ? field : JSON.stringify(field);
  return /\bname(:[a-z]+|_[a-z]+)?\b/.test(text);
}

export const COLORS = {
  walk: "#54717a",
  transit: "#137c78",
  active: "#0b4f4c",
  origin: "#137c78",
  destination: "#bf5647",
  stop: "#ffffff",
  transfer: "#ffffff",
  user: "#1f6feb",
  halo: "#ffffff",
};
