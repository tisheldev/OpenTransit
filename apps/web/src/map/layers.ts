import { THEME_COLORS, type ThemeName } from "../styles/tokens";
import type { LonLat, MapPin, MapRouteLeg, MapScene, MapUser } from "./scene";

// Pure scene → GeoJSON and style helpers (no MapLibre import), so they unit-test in jsdom.
// Colours come from the design system's tokens for the active theme (design: Map; the
// mock maps on the App page): land, roads and water from map-*, lines by mode, origin a
// circle, destination a square, stops and transfers hollow in their line's colour, and
// the passenger a brand puck with a halo.

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

/** How a line is drawn: bus in mode-bus, rail (train, light rail, tram, metro) in mode-rail, walking dotted. */
export type LineMode = "bus" | "rail" | "walk";

/** The colour group of an API leg mode ("bus", "rail", "light_rail", "walk", …); anything else rides as a bus. */
export function lineMode(mode: string | null | undefined): LineMode {
  const value = (mode ?? "").toLowerCase();
  if (/^(walk|foot)/.test(value)) return "walk";
  if (/rail|train|tram|subway|metro|monorail|funicular/.test(value)) return "rail";
  return "bus";
}

export interface RouteProps {
  kind: MapRouteLeg["kind"];
  mode: string;
  line: LineMode;
  active: boolean;
  /** Another leg is active (the current step): this one is drawn faded (design: Navigate). */
  dimmed: boolean;
  label: string;
}

/** One line per leg that has geometry; a time-only walk (coordinates null) adds nothing. */
export function routeFeatures(route: MapRouteLeg[]): FeatureCollection<LineString, RouteProps> {
  const anyActive = route.some((leg) => leg.active === true);
  const features: Feature<LineString, RouteProps>[] = [];
  for (const leg of route) {
    if (!leg.coordinates || leg.coordinates.length < 2) continue;
    const active = leg.active === true;
    features.push({
      type: "Feature",
      geometry: { type: "LineString", coordinates: leg.coordinates },
      properties: {
        kind: leg.kind,
        mode: leg.mode,
        line: leg.kind === "walk" ? "walk" : lineMode(leg.mode),
        active,
        dimmed: anyActive && !active,
        label: leg.label ?? "",
      },
    });
  }
  return { type: "FeatureCollection", features };
}

export interface PinProps {
  id: string;
  role: MapPin["role"];
  label: string;
  /** The line a stop or transfer belongs to, for its stroke. */
  line: LineMode;
}

const near = (a: LonLat, b: LonLat) => Math.abs(a[0] - b[0]) < 1e-6 && Math.abs(a[1] - b[1]) < 1e-6;

/** The pin's own mode, else the ride that boards (or else ends) there, else bus. */
function pinLine(pin: MapPin, route: MapRouteLeg[]): LineMode {
  if (pin.mode) return lineMode(pin.mode) === "walk" ? "bus" : lineMode(pin.mode);
  const rides = route.filter((leg) => leg.kind === "transit");
  const ride = rides.find((leg) => near(leg.from, pin.position)) ?? rides.find((leg) => near(leg.to, pin.position));
  return ride ? (lineMode(ride.mode) === "walk" ? "bus" : lineMode(ride.mode)) : "bus";
}

export function pinFeatures(pins: MapPin[], route: MapRouteLeg[] = []): FeatureCollection<Point, PinProps> {
  return {
    type: "FeatureCollection",
    features: pins.map((pin) => ({
      type: "Feature",
      geometry: { type: "Point", coordinates: pin.position },
      properties: { id: pin.id, role: pin.role, label: pin.label, line: pinLine(pin, route) },
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

// ---------------------------------------------------------------------------------------
// Colours per theme

export interface MapPalette {
  land: string;
  road: string;
  water: string;
  /** Basemap label text (ink-muted; its halo is land). */
  label: string;
  surface: string;
  bus: string;
  rail: string;
  walk: string;
  origin: string;
  destination: string;
  brand: string;
}

/** The map's colours for a theme, resolved from the design tokens (MapLibre takes no CSS variables). */
export function mapPalette(theme: ThemeName): MapPalette {
  const c = THEME_COLORS[theme];
  return {
    land: c["map-land"],
    road: c["map-road"],
    water: c["map-water"],
    label: c["ink-muted"],
    surface: c.surface,
    bus: c["mode-bus"],
    rail: c["mode-rail"],
    walk: c["mode-walk"],
    origin: c.origin,
    destination: c.destination,
    brand: c.brand,
  };
}

// ---------------------------------------------------------------------------------------
// Basemap styles

/**
 * OpenFreeMap base styles: "dark" (neutral greys) under the dark theme and "positron"
 * (pale, minimal) under the light one; both are then recoloured to the theme's map-land,
 * map-water and map-road (themeBasemap). Both share one sprite and glyph set, so a theme
 * switch can be applied as a style diff.
 */
export const OPENFREEMAP_STYLES: Record<ThemeName, string> = {
  dark: "https://tiles.openfreemap.org/styles/dark",
  light: "https://tiles.openfreemap.org/styles/positron",
};

/** Minimal style JSON shapes this module reads and writes (no MapLibre types here). */
export interface StyleLayerJson {
  id: string;
  type: string;
  source?: string;
  "source-layer"?: string;
  filter?: unknown;
  layout?: Record<string, unknown>;
  paint?: Record<string, unknown>;
  [key: string]: unknown;
}
export interface StyleJson {
  version: 8;
  name?: string;
  sources: Record<string, unknown>;
  layers: StyleLayerJson[];
  glyphs?: string;
  [key: string]: unknown;
}

/**
 * Offline style for fixture mode and tests: the theme's land colour only, so no request
 * leaves the origin and no glyphs are needed (route labels are skipped without glyphs).
 */
export function offlineStyle(theme: ThemeName): StyleJson {
  return {
    version: 8,
    name: "OpenTransit offline",
    sources: {},
    layers: [{ id: "background", type: "background", paint: { "background-color": mapPalette(theme).land } }],
  };
}

/** Which style to load: VITE_MAP_STYLE overrides ("offline" or a URL); fixtures and tests stay offline. */
export function chooseStyle(mode: string, override: string | undefined, theme: ThemeName): string | StyleJson {
  if (override) return override === "offline" ? offlineStyle(theme) : override;
  if (mode === "fixtures" || mode === "test") return offlineStyle(theme);
  return OPENFREEMAP_STYLES[theme];
}

/** What a basemap layer stands for in the design's map: land, water, a road, or none (left as styled). */
export function basemapRole(layer: StyleLayerJson): "land" | "water" | "road" | null {
  if (layer.type === "background") return "land";
  const sourceLayer = layer["source-layer"];
  if (sourceLayer === "water" && layer.type === "fill") return "water";
  if (sourceLayer === "waterway" && layer.type === "line") return "water";
  if (sourceLayer === "transportation" && (layer.type === "line" || layer.type === "fill")) {
    if (/rail|aeroway|ferry|aerialway|cable/i.test(layer.id)) return null;
    // Piers are land; casings take the land colour so roads read as plain strokes (the mock maps).
    if (/pier|casing/i.test(layer.id)) return "land";
    return "road";
  }
  return null;
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

const isOverlayId = (id: string) => id.startsWith("ot-");

/**
 * The base style in the theme's colours and the page language: background, water and road
 * layers take map-land, map-water and map-road; label text takes ink-muted on a land halo
 * (the dark base style's grey labels are about 2:1 on map-land); name labels follow the
 * language. Other layers (parks, buildings, rail, boundaries) keep the base style's own
 * colours. Returns a new style; the input is not changed.
 */
export function themeBasemap(style: StyleJson, theme: ThemeName, lang: "he" | "en"): StyleJson {
  const palette = mapPalette(theme);
  const colour = { land: palette.land, water: palette.water, road: palette.road };
  const layers = style.layers.map((layer) => {
    if (isOverlayId(layer.id)) return layer;
    let next = layer;
    const role = basemapRole(layer);
    if (role && (layer.type === "background" || layer.type === "fill" || layer.type === "line")) {
      const paint: Record<string, unknown> = { ...(layer.paint ?? {}), [`${layer.type}-color`]: colour[role] };
      delete paint[`${layer.type}-pattern`];
      if (layer.type === "fill" && "fill-outline-color" in paint) paint["fill-outline-color"] = colour[role];
      next = { ...next, paint };
    }
    if (layer.type === "symbol" && layer.layout?.["text-field"] != null) {
      next = { ...next, paint: { ...(next.paint ?? {}), "text-color": palette.label, "text-halo-color": palette.land } };
      if (isNameTextField(layer.layout["text-field"])) {
        next = { ...next, layout: { ...(next.layout ?? {}), "text-field": nameExpression(lang) } };
      }
    }
    return next;
  });
  return { ...style, layers };
}

// ---------------------------------------------------------------------------------------
// Our own layers

export const OVERLAY_SOURCES = ["ot-accuracy", "ot-route", "ot-pins", "ot-user"] as const;
export type OverlaySource = (typeof OVERLAY_SOURCES)[number];

/** The destination square's image id (a symbol: MapLibre circles cannot be square). */
export const DESTINATION_ICON = "ot-destination";
/** Image pixels per CSS pixel for generated markers (sharp on 2x screens, fine on 1x). */
export const MARKER_PIXEL_RATIO = 2;

/** Faded legs while another is the current step (design: the next ride at .55). */
const DIMMED_OPACITY = 0.55;
const dimmable = ["case", ["get", "dimmed"], DIMMED_OPACITY, 1];

/**
 * Our layers, bottom to top, in the theme's colours. Sizes follow the mock maps: lines
 * 5 px, walking 3 px dotted (SVG dasharray 2 6, round caps), origin and destination about
 * 20 px with a surface edge, stops a 2.5 px ring in their line's colour, the puck 8 px
 * with a 24 px brand halo. MapLibre draws a circle's stroke outside its radius, so each
 * radius is the SVG radius less half its stroke. Line labels need glyphs (`labels`).
 */
export function overlayLayers(theme: ThemeName, { labels }: { labels: boolean }): StyleLayerJson[] {
  const p = mapPalette(theme);
  const byLine = ["match", ["get", "line"], "rail", p.rail, "walk", p.walk, p.bus];
  const layers: StyleLayerJson[] = [
    {
      id: "ot-accuracy",
      type: "fill",
      source: "ot-accuracy",
      paint: { "fill-color": p.brand, "fill-opacity": 0.12, "fill-outline-color": p.brand },
    },
    {
      // A land-coloured edge, so a line stays legible over roads and labels on real tiles.
      id: "ot-route-casing",
      type: "line",
      source: "ot-route",
      filter: ["==", ["get", "kind"], "transit"],
      layout: { "line-cap": "round", "line-join": "round" },
      paint: { "line-color": p.land, "line-width": 8, "line-opacity": dimmable },
    },
    {
      id: "ot-route-walk",
      type: "line",
      source: "ot-route",
      filter: ["==", ["get", "kind"], "walk"],
      layout: { "line-cap": "round", "line-join": "round" },
      // Dash lengths are in line widths: 2 and 6 px at 3 px wide.
      paint: { "line-color": p.walk, "line-width": 3, "line-dasharray": [2 / 3, 2], "line-opacity": dimmable },
    },
    {
      id: "ot-route-transit",
      type: "line",
      source: "ot-route",
      filter: ["==", ["get", "kind"], "transit"],
      layout: { "line-cap": "round", "line-join": "round" },
      paint: { "line-color": byLine, "line-width": 5, "line-opacity": dimmable },
    },
    {
      id: "ot-pins",
      type: "circle",
      source: "ot-pins",
      filter: ["!=", ["get", "role"], "destination"],
      paint: {
        "circle-radius": ["match", ["get", "role"], "origin", 8, 4],
        "circle-color": ["match", ["get", "role"], "origin", p.origin, p.surface],
        "circle-stroke-color": ["match", ["get", "role"], "origin", p.surface, byLine],
        "circle-stroke-width": 2.5,
      },
    },
    {
      id: "ot-destination",
      type: "symbol",
      source: "ot-pins",
      filter: ["==", ["get", "role"], "destination"],
      layout: { "icon-image": DESTINATION_ICON, "icon-allow-overlap": true, "icon-ignore-placement": true },
    },
    {
      id: "ot-user-halo",
      type: "circle",
      source: "ot-user",
      paint: { "circle-radius": 24, "circle-color": p.brand, "circle-opacity": 0.18 },
    },
    {
      id: "ot-user",
      type: "circle",
      source: "ot-user",
      paint: { "circle-radius": 6.5, "circle-color": p.brand, "circle-stroke-color": p.surface, "circle-stroke-width": 3 },
    },
  ];
  if (labels) {
    layers.push({
      id: "ot-route-label",
      type: "symbol",
      source: "ot-route",
      filter: ["all", ["==", ["get", "kind"], "transit"], ["!=", ["get", "label"], ""]],
      layout: {
        "symbol-placement": "line",
        "text-field": ["get", "label"],
        "text-font": ["Noto Sans Bold"],
        "text-size": 13,
      },
      paint: { "text-color": byLine, "text-halo-color": p.surface, "text-halo-width": 2 },
    });
  }
  return layers;
}

/**
 * The next style with our sources and layers carried over from the previous one (a theme
 * switch): the drawn scene keeps its data, and the layers take the new theme's colours.
 * With nothing of ours in `previous` (the first load), `next` is returned as is.
 */
export function withOverlay(previous: StyleJson | undefined, next: StyleJson, theme: ThemeName): StyleJson {
  const kept = Object.entries(previous?.sources ?? {}).filter(([id]) => isOverlayId(id));
  if (kept.length === 0) return next;
  return {
    ...next,
    sources: { ...next.sources, ...Object.fromEntries(kept) },
    layers: [...next.layers.filter((layer) => !isOverlayId(layer.id)), ...overlayLayers(theme, { labels: !!next.glyphs })],
  };
}

// ---------------------------------------------------------------------------------------
// The destination square

export interface MarkerImage {
  width: number;
  height: number;
  data: Uint8ClampedArray;
}

function rgb(hex: string): [number, number, number] {
  const value = hex.replace("#", "");
  return [0, 2, 4].map((at) => parseInt(value.slice(at, at + 2), 16)) as [number, number, number];
}

/** Signed distance from a point to a rounded square centred at c (negative inside). */
function roundedSquareDistance(x: number, y: number, c: number, half: number, radius: number): number {
  const qx = Math.abs(x - c) - (half - radius);
  const qy = Math.abs(y - c) - (half - radius);
  const outside = Math.hypot(Math.max(qx, 0), Math.max(qy, 0));
  return outside + Math.min(Math.max(qx, qy), 0) - radius;
}

/**
 * The destination marker (design: the destination is a square, as in Trip fields): a
 * rounded square in `destination` with a surface edge, anti-aliased, as RGBA pixels at
 * MARKER_PIXEL_RATIO. `size` and `stroke` are CSS pixels.
 */
export function destinationMarker(theme: ThemeName, size = 19, stroke = 2.5, radius = 4.5): MarkerImage {
  const p = mapPalette(theme);
  const scale = MARKER_PIXEL_RATIO;
  const side = Math.ceil(size * scale) + 2; // a pixel of room for the anti-aliased edge
  const centre = side / 2;
  const half = (size * scale) / 2;
  const [fr, fg, fb] = rgb(p.destination);
  const [sr, sg, sb] = rgb(p.surface);
  const data = new Uint8ClampedArray(side * side * 4);
  for (let y = 0; y < side; y += 1) {
    for (let x = 0; x < side; x += 1) {
      const px = x + 0.5;
      const py = y + 0.5;
      const outer = Math.min(Math.max(0.5 - roundedSquareDistance(px, py, centre, half, radius * scale), 0), 1);
      const innerHalf = half - stroke * scale;
      const innerRadius = Math.max(radius - stroke, 0.5) * scale;
      const inner = Math.min(Math.max(0.5 - roundedSquareDistance(px, py, centre, innerHalf, innerRadius), 0), 1);
      const at = (y * side + x) * 4;
      data[at] = Math.round(sr + (fr - sr) * inner);
      data[at + 1] = Math.round(sg + (fg - sg) * inner);
      data[at + 2] = Math.round(sb + (fb - sb) * inner);
      data[at + 3] = Math.round(255 * outer);
    }
  }
  return { width: side, height: side, data };
}
