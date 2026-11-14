// The stops layer's pure geometry (stops and lines design, 12 November 2026; marker G and
// the boards MapFar, MapGroups, MapGroupOpen, MapClose, Main, MarkerTuning). No MapLibre
// import: screen points come in as pixels, street geometry as local metres, so every rule
// here unit-tests without a map.

/** A point on the screen in CSS pixels (x right, y down). */
export interface Px {
  x: number;
  y: number;
}

/** An axis-aligned box in CSS pixels. */
export interface Box {
  left: number;
  top: number;
  right: number;
  bottom: number;
}

// ---------------------------------------------------------------------------------------
// Zoom levels

/**
 * The three levels by zoom (design: "below about zoom 13, stations only; from about 13 to
 * 15, stops with grouping; from about 16, every stop on its own"). MapLibre zooms, where a
 * level is one less than the common 256-pixel web-map zoom at the same scale. The design
 * calls its thresholds suggestions (open question 9); these follow the boards:
 * - Signs from 13.5: board 1 draws Home's 5-minute-walk ring (800 m across) 236 px wide,
 *   about 3.4 m a pixel, which is MapLibre zoom 14.3, with every stop as its own sign; on
 *   a 360 × 640 phone with the sheet at half, the same ring frames at about 13.8.
 * - Stations only below 12.5: from there a phone-sized view holds about 35 km² of stops
 *   (several hundred in central Tel Aviv, 100 to a page), still within a settle's request
 *   budget; at 12 it would be half as many again.
 */
export const ZOOM_STOPS = 12.5;
export const ZOOM_SIGNS = 13.5;

export type StopsLevel = "stations" | "grouped" | "signs";

export function zoomLevel(zoom: number): StopsLevel {
  if (zoom >= ZOOM_SIGNS) return "signs";
  if (zoom >= ZOOM_STOPS) return "grouped";
  return "stations";
}

// ---------------------------------------------------------------------------------------
// Which way the pole points

/**
 * Where the sign stands from its kerb dot: the pole points straight up, down, left or
 * right, whichever is most directly away from the road (user, 12 November: "Keep
 * snapped"). Null: the side is unknown, so the sign is drawn centred on the stop with no
 * pole and no kerb dot (design: "The side is never guessed").
 */
export type PoleSide = "up" | "down" | "left" | "right";

/** Snaps a screen direction (dx right, dy down) to the nearest of the four; null for none. */
export function snapDirection(dx: number, dy: number): PoleSide | null {
  if (!Number.isFinite(dx) || !Number.isFinite(dy) || (Math.abs(dx) < 1e-9 && Math.abs(dy) < 1e-9)) return null;
  // On an exact diagonal the pole stands up or down (board MarkerTuning, "On a diagonal street").
  if (Math.abs(dx) > Math.abs(dy)) return dx > 0 ? "right" : "left";
  return dy < 0 ? "up" : "down";
}

/**
 * The side from the stop's rough direction of travel (API-C6 `bearingDegrees`, clockwise
 * from north). Traffic in Israel keeps right, so the kerb is on the right of the direction
 * of travel and "away from the road" is the bearing plus 90°. `mapBearing` is the map's
 * own rotation (the client's map is north-up, so 0).
 */
export function sideFromBearing(bearingDegrees: number | null | undefined, mapBearing = 0): PoleSide | null {
  if (bearingDegrees === null || bearingDegrees === undefined || !Number.isFinite(bearingDegrees)) return null;
  const away = ((bearingDegrees + 90 - mapBearing) * Math.PI) / 180;
  return snapDirection(Math.sin(away), -Math.cos(away));
}

/** A point in local metres around the stop (x east, y north). */
export interface Metres {
  x: number;
  y: number;
}

/** A street as a polyline in local metres around the stop. */
export type StreetLine = readonly Metres[];

/** Metres per degree, near enough for a few dozen metres around one stop. */
export function toLocalMetres(origin: { longitude: number; latitude: number }, lonLat: readonly [number, number] | readonly number[]): Metres {
  const lat0 = (origin.latitude * Math.PI) / 180;
  return {
    x: ((lonLat[0]! - origin.longitude) * Math.PI * 6_371_008.8 * Math.cos(lat0)) / 180,
    y: ((lonLat[1]! - origin.latitude) * Math.PI * 6_371_008.8) / 180,
  };
}

/** Streets farther than this from the stop are some other road. */
export const STREET_SEARCH_METRES = 35;
/** Closer than this to the street's centre line, the side cannot be told from it. */
export const STREET_MIN_OFFSET_METRES = 1.5;
/** A street within this angle of the direction of travel is the stop's own road. */
const ALONG_DEGREES = 40;

function nearestOnSegment(a: Metres, b: Metres): { point: Metres; distance: number } {
  const dx = b.x - a.x;
  const dy = b.y - a.y;
  const length = dx * dx + dy * dy;
  const t = length > 0 ? Math.max(0, Math.min(1, -(a.x * dx + a.y * dy) / length)) : 0;
  const point = { x: a.x + dx * t, y: a.y + dy * t };
  return { point, distance: Math.hypot(point.x, point.y) };
}

function angleBetweenLines(dx: number, dy: number, bearingDegrees: number): number {
  // Compass angle of the segment (clockwise from north), folded so a street runs both ways.
  const segment = (Math.atan2(dx, dy) * 180) / Math.PI;
  const diff = Math.abs((((segment - bearingDegrees) % 180) + 180) % 180);
  return Math.min(diff, 180 - diff);
}

/**
 * The side from the map's own streets around the stop (user, 12 November: the client
 * points the pole at the nearest street on the map; the API's direction stays as the
 * fallback). The stop is at the origin; "away from the road" is from the nearest point of
 * its road to the stop. With a direction of travel, only streets running roughly along it
 * count, so a junction's cross street does not turn the pole. Null when no street is near
 * enough or the stop sits on the centre line (then the caller falls back to the bearing).
 */
export function sideFromStreets(
  streets: readonly StreetLine[],
  bearingDegrees: number | null | undefined,
  mapBearing = 0,
): PoleSide | null {
  let best: { point: Metres; distance: number } | null = null;
  const hasBearing = bearingDegrees !== null && bearingDegrees !== undefined && Number.isFinite(bearingDegrees);
  for (const line of streets) {
    for (let i = 1; i < line.length; i += 1) {
      const a = line[i - 1]!;
      const b = line[i]!;
      if (hasBearing && angleBetweenLines(b.x - a.x, b.y - a.y, bearingDegrees!) > ALONG_DEGREES) continue;
      const found = nearestOnSegment(a, b);
      if (found.distance <= STREET_SEARCH_METRES && (!best || found.distance < best.distance)) best = found;
    }
  }
  if (!best || best.distance < STREET_MIN_OFFSET_METRES) return null;
  // From the road to the stop: its compass angle, then on screen (y down) under the map's rotation.
  const compass = Math.atan2(-best.point.x, -best.point.y) - (mapBearing * Math.PI) / 180;
  return snapDirection(Math.sin(compass), -Math.cos(compass));
}

// ---------------------------------------------------------------------------------------
// Marker boxes (marker G as drawn: boards Main, MapGroupOpen, MapClose)

/** A stop sign: 20 px, corner 5; chosen: 28 px, corner 8 (with a 3 px outline). */
export const SIGN_PX = 20;
export const CHOSEN_PX = 28;
/** From the kerb point to the sign's near edge: the 10 px pole and the 6 px dot around +1 px. */
export const SIGN_GAP_PX = 12;
export const POLE_PX = 10;
export const DOT_PX = 6;
/** Neighbourhood zoom: a 12 px square, no pole, no icon (board 8). */
export const SQUARE_PX = 12;
/** A train or light-rail station: the same sign, 22 px, centred (boards 7 and 8). */
export const STATION_PX = 22;
/** A group: a pale circle 30 px, 36 px for five or more (board 8). */
export const GROUP_PX = 30;
export const GROUP_LARGE_PX = 36;
export const GROUP_LARGE_FROM = 5;
/** Space kept between two markers so they never touch. */
export const MARKER_GAP_PX = 2;

/** The sign's box around its kerb point for a side (null: centred, no pole). */
export function signBox(kerb: Px, side: PoleSide | null, size = SIGN_PX): Box {
  const half = size / 2;
  const far = SIGN_GAP_PX + size;
  switch (side) {
    case "up":
      return { left: kerb.x - half, right: kerb.x + half, top: kerb.y - far, bottom: kerb.y - SIGN_GAP_PX };
    case "down":
      return { left: kerb.x - half, right: kerb.x + half, top: kerb.y + SIGN_GAP_PX, bottom: kerb.y + far };
    case "left":
      return { left: kerb.x - far, right: kerb.x - SIGN_GAP_PX, top: kerb.y - half, bottom: kerb.y + half };
    case "right":
      return { left: kerb.x + SIGN_GAP_PX, right: kerb.x + far, top: kerb.y - half, bottom: kerb.y + half };
    default:
      return { left: kerb.x - half, right: kerb.x + half, top: kerb.y - half, bottom: kerb.y + half };
  }
}

/** The kerb dot's box (none without a side). */
export function dotBox(kerb: Px, side: PoleSide | null): Box | null {
  if (!side) return null;
  // Centred on the kerb point: "the kerb dot stays exactly on the kerb" (the boards draw it within a pixel of it).
  return centredBox(kerb, DOT_PX);
}

export function centredBox(at: Px, size: number): Box {
  return { left: at.x - size / 2, right: at.x + size / 2, top: at.y - size / 2, bottom: at.y + size / 2 };
}

export function overlaps(a: Box, b: Box, gap = 0): boolean {
  return a.left < b.right + gap && b.left < a.right + gap && a.top < b.bottom + gap && b.top < a.bottom + gap;
}

export function groupSize(count: number): number {
  return count >= GROUP_LARGE_FROM ? GROUP_LARGE_PX : GROUP_PX;
}

// ---------------------------------------------------------------------------------------
// Grouping

/** One stop as the grouping sees it: its kerb point and, at sign zoom, its side. */
export interface GroupInput {
  id: string;
  at: Px;
  side: PoleSide | null;
}

export interface MarkerGroup {
  /** Member ids, in input order. */
  ids: string[];
  /** Where the count stands: the members' centroid (above their kerb dots at sign zoom). */
  at: Px;
  /** The members' own kerb points (sign zoom: the count stands on both kerb dots). */
  kerbs: Px[];
}

export interface Grouping {
  singles: GroupInput[];
  groups: MarkerGroup[];
}

/** How far above its members' kerb dots a sign-zoom group's count stands (board MarkerTuning). */
export const GROUP_LIFT_PX = 18;

interface Footprint {
  box: Box;
  /** A kerb dot: two dots may meet (stops facing each other across a street). */
  dot: boolean;
}

function footprints(item: GroupInput, level: "grouped" | "signs"): Footprint[] {
  if (level === "grouped") return [{ box: centredBox(item.at, SQUARE_PX), dot: false }];
  const boxes: Footprint[] = [{ box: signBox(item.at, item.side), dot: false }];
  const dot = dotBox(item.at, item.side);
  if (dot) boxes.push({ box: dot, dot: true });
  return boxes;
}

function centroid(points: readonly Px[]): Px {
  const sum = points.reduce((acc, point) => ({ x: acc.x + point.x, y: acc.y + point.y }), { x: 0, y: 0 });
  return { x: sum.x / points.length, y: sum.y / points.length };
}

/**
 * Stops whose markers would touch on screen merge into one count (design: "merge stops
 * whose markers would touch on screen"; signs never touch). A sign touches another when
 * its sign overlaps the other's sign or kerb dot (two dots may meet: stops across a
 * street). The circles that result are checked again, so a count never covers a stop.
 * At sign zoom the count stands above its members' kerb dots, which stay drawn.
 */
export function groupMarkers(items: readonly GroupInput[], level: "grouped" | "signs", gap = MARKER_GAP_PX): Grouping {
  type Cluster = { members: GroupInput[]; boxes: Footprint[] };
  const asCluster = (members: GroupInput[]): Cluster => {
    if (members.length === 1) return { members, boxes: footprints(members[0]!, level) };
    const kerbs = members.map((member) => member.at);
    const centre = centroid(kerbs);
    const at = level === "signs" ? { x: centre.x, y: centre.y - GROUP_LIFT_PX } : centre;
    return { members, boxes: [{ box: centredBox(at, groupSize(members.length)), dot: false }] };
  };
  const touches = (a: Cluster, b: Cluster) => {
    for (const x of a.boxes) {
      for (const y of b.boxes) {
        // Two kerb dots may meet; anything else touching merges.
        if (!(x.dot && y.dot) && overlaps(x.box, y.box, gap)) return true;
      }
    }
    return false;
  };

  let clusters = items.map((item) => asCluster([item]));
  for (let pass = 0; pass < 8; pass += 1) {
    // Union-find over the pairs that touch.
    const parent = clusters.map((_, index) => index);
    const find = (i: number): number => (parent[i] === i ? i : (parent[i] = find(parent[i]!)));
    let merged = false;
    // Bucket by a coarse grid so a crowded view stays fast.
    const cell = 48;
    const buckets = new Map<string, number[]>();
    clusters.forEach((cluster, index) => {
      const box = cluster.boxes
        .map((footprint) => footprint.box)
        .reduce((acc, b) => ({ left: Math.min(acc.left, b.left), top: Math.min(acc.top, b.top), right: Math.max(acc.right, b.right), bottom: Math.max(acc.bottom, b.bottom) }));
      for (let gx = Math.floor((box.left - gap) / cell); gx <= Math.floor((box.right + gap) / cell); gx += 1) {
        for (let gy = Math.floor((box.top - gap) / cell); gy <= Math.floor((box.bottom + gap) / cell); gy += 1) {
          const key = `${gx}:${gy}`;
          const list = buckets.get(key);
          if (list) list.push(index);
          else buckets.set(key, [index]);
        }
      }
    });
    const seen = new Set<string>();
    for (const list of buckets.values()) {
      for (let i = 0; i < list.length; i += 1) {
        for (let j = i + 1; j < list.length; j += 1) {
          const a = list[i]!;
          const b = list[j]!;
          const key = a < b ? `${a}|${b}` : `${b}|${a}`;
          if (seen.has(key)) continue;
          seen.add(key);
          if (find(a) !== find(b) && touches(clusters[a]!, clusters[b]!)) {
            parent[find(a)] = find(b);
            merged = true;
          }
        }
      }
    }
    if (!merged) break;
    const byRoot = new Map<number, GroupInput[]>();
    clusters.forEach((cluster, index) => {
      const root = find(index);
      const list = byRoot.get(root) ?? [];
      list.push(...cluster.members);
      byRoot.set(root, list);
    });
    clusters = [...byRoot.values()].map((members) => asCluster(members));
  }

  const order = new Map(items.map((item, index) => [item.id, index]));
  const singles: GroupInput[] = [];
  const groups: MarkerGroup[] = [];
  for (const cluster of clusters) {
    if (cluster.members.length === 1) {
      singles.push(cluster.members[0]!);
      continue;
    }
    const members = [...cluster.members].sort((a, b) => order.get(a.id)! - order.get(b.id)!);
    const kerbs = members.map((member) => member.at);
    const centre = centroid(kerbs);
    groups.push({
      ids: members.map((member) => member.id),
      at: level === "signs" ? { x: centre.x, y: centre.y - GROUP_LIFT_PX } : centre,
      kerbs,
    });
  }
  singles.sort((a, b) => order.get(a.id)! - order.get(b.id)!);
  groups.sort((a, b) => order.get(a.ids[0]!)! - order.get(b.ids[0]!)!);
  return { singles, groups };
}

// ---------------------------------------------------------------------------------------
// Next-line tags

/** The tag's near edge tucks this far behind its sign (boards Main and MapClose). */
export const TAG_TUCK_PX = 5;
/** At most this many tags at once, the chosen stop's first (design; Home limited them to two). */
export const MAX_TAGS = 2;
/** A tag may graze another marker by this much (anti-aliased edges), never cover it. */
export const TAG_GRAZE_PX = 2;

export interface TagRequest {
  id: string;
  /** The sign it hangs from. */
  sign: Box;
  side: PoleSide | null;
  /** Measured tag width; its height is the sign's. */
  width: number;
}

export interface PlacedTag {
  id: string;
  box: Box;
  /** Which side of its sign the tag runs to. */
  toward: "left" | "right";
}

/**
 * The side a tag prefers: away from the road; where the road is above or below the sign
 * (or unknown), toward the end of the reading direction (left in Hebrew).
 */
export function preferredTagSide(side: PoleSide | null, dir: "rtl" | "ltr"): "left" | "right" {
  if (side === "left" || side === "right") return side;
  return dir === "rtl" ? "left" : "right";
}

export function tagBox(sign: Box, width: number, toward: "left" | "right"): Box {
  const top = sign.top;
  const bottom = sign.bottom;
  return toward === "left"
    ? { left: sign.left + TAG_TUCK_PX - width, right: sign.left + TAG_TUCK_PX, top, bottom }
    : { left: sign.right - TAG_TUCK_PX, right: sign.right - TAG_TUCK_PX + width, top, bottom };
}

/**
 * Places tags in priority order (the chosen stop's first). A tag never covers another stop
 * or another tag and never leaves the visible map: it flips to the other side of its sign,
 * or is not shown (design, board MarkerTuning "At a crowded junction").
 */
export function placeTags(
  requests: readonly TagRequest[],
  obstacles: readonly { id: string; box: Box }[],
  visible: Box,
  dir: "rtl" | "ltr",
  max = MAX_TAGS,
): PlacedTag[] {
  const placed: PlacedTag[] = [];
  for (const request of requests) {
    if (placed.length >= max) break;
    const first = preferredTagSide(request.side, dir);
    const sides: ("left" | "right")[] = [first, first === "left" ? "right" : "left"];
    for (const toward of sides) {
      const box = tagBox(request.sign, request.width, toward);
      const inside = box.left >= visible.left && box.right <= visible.right && box.top >= visible.top && box.bottom <= visible.bottom;
      if (!inside) continue;
      const blocked =
        obstacles.some((other) => other.id !== request.id && overlaps(box, other.box, -TAG_GRAZE_PX)) || placed.some((other) => overlaps(box, other.box, 2));
      if (blocked) continue;
      placed.push({ id: request.id, box, toward });
      break;
    }
  }
  return placed;
}

// ---------------------------------------------------------------------------------------
// Direction words for a group's list (board 9: "לכיוון דרום")

export type Compass = "north" | "east" | "south" | "west";

/** The direction of travel in four words; null without a bearing. */
export function compassOf(bearingDegrees: number | null | undefined): Compass | null {
  if (bearingDegrees === null || bearingDegrees === undefined || !Number.isFinite(bearingDegrees)) return null;
  const value = ((bearingDegrees % 360) + 360) % 360;
  if (value >= 315 || value < 45) return "north";
  if (value < 135) return "east";
  if (value < 225) return "south";
  return "west";
}
