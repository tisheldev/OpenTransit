// Small, pure geodesy for the navigation engine (design: Navigation engine). Lines are
// GeoJSON order, `[longitude, latitude]`. Distances are metres on a spherical Earth,
// which is well within a metre per kilometre at Israeli latitudes (29°–33.5° N).

export interface LatLon {
  latitude: number;
  longitude: number;
}

/** GeoJSON position: `[longitude, latitude]` (extra members, such as altitude, ignored). */
export type Position = readonly number[];

export const EARTH_RADIUS_METERS = 6_371_008.8;

const toRadians = (degrees: number) => (degrees * Math.PI) / 180;
const toDegrees = (radians: number) => (radians * 180) / Math.PI;

/** Great-circle distance in metres. */
export function haversineMeters(a: LatLon, b: LatLon): number {
  const phi1 = toRadians(a.latitude);
  const phi2 = toRadians(b.latitude);
  const dPhi = phi2 - phi1;
  const dLambda = toRadians(b.longitude - a.longitude);
  const h = Math.sin(dPhi / 2) ** 2 + Math.cos(phi1) * Math.cos(phi2) * Math.sin(dLambda / 2) ** 2;
  return 2 * EARTH_RADIUS_METERS * Math.asin(Math.min(1, Math.sqrt(h)));
}

/** Initial bearing from `a` to `b`, degrees clockwise from north in [0, 360). */
export function bearingDegrees(a: LatLon, b: LatLon): number {
  const phi1 = toRadians(a.latitude);
  const phi2 = toRadians(b.latitude);
  const dLambda = toRadians(b.longitude - a.longitude);
  const y = Math.sin(dLambda) * Math.cos(phi2);
  const x = Math.cos(phi1) * Math.sin(phi2) - Math.sin(phi1) * Math.cos(phi2) * Math.cos(dLambda);
  return (toDegrees(Math.atan2(y, x)) + 360) % 360;
}

/** The point `meters` away from `origin` along `bearing` (degrees). */
export function destinationPoint(origin: LatLon, bearing: number, meters: number): LatLon {
  const delta = meters / EARTH_RADIUS_METERS;
  const theta = toRadians(bearing);
  const phi1 = toRadians(origin.latitude);
  const lambda1 = toRadians(origin.longitude);
  const phi2 = Math.asin(Math.sin(phi1) * Math.cos(delta) + Math.cos(phi1) * Math.sin(delta) * Math.cos(theta));
  const lambda2 =
    lambda1 + Math.atan2(Math.sin(theta) * Math.sin(delta) * Math.cos(phi1), Math.cos(delta) - Math.sin(phi1) * Math.sin(phi2));
  return { latitude: toDegrees(phi2), longitude: toDegrees(lambda2) };
}

export const fromPosition = (position: Position): LatLon => ({ latitude: position[1] ?? NaN, longitude: position[0] ?? NaN });

/** Total length of a line in metres (0 for fewer than two points). */
export function lineLengthMeters(line: readonly Position[]): number {
  let total = 0;
  for (let i = 1; i < line.length; i += 1) total += haversineMeters(fromPosition(line[i - 1]!), fromPosition(line[i]!));
  return total;
}

export interface Projection {
  /** Distance along the line from its first point to the projected point, metres. */
  alongMeters: number;
  /** Distance from the point to the line, metres. */
  distanceMeters: number;
  /** Index of the segment (from point `segment` to `segment + 1`) holding the projection. */
  segment: number;
}

export interface ProjectOptions {
  /**
   * Only segments ending beyond this distance along the line are considered, and the
   * result is never before it. Keeps a projection on the right pass of a looping route.
   */
  minAlongMeters?: number;
}

/**
 * Project a point onto a line: the closest point of the line, its distance along the
 * line and the point's distance from it. Each segment is flattened in a local
 * equirectangular frame (exact enough for segments of a few kilometres). Returns null
 * for an empty line; a one-point line projects onto that point.
 */
export function projectOntoLine(point: LatLon, line: readonly Position[], options: ProjectOptions = {}): Projection | null {
  if (line.length === 0) return null;
  if (line.length === 1) {
    return { alongMeters: 0, distanceMeters: haversineMeters(point, fromPosition(line[0]!)), segment: 0 };
  }
  const minAlong = options.minAlongMeters ?? -Infinity;
  let best: Projection | null = null;
  let start = 0;
  for (let i = 0; i < line.length - 1; i += 1) {
    const a = fromPosition(line[i]!);
    const b = fromPosition(line[i + 1]!);
    const length = haversineMeters(a, b);
    const end = start + length;
    if (end >= minAlong) {
      const kx = EARTH_RADIUS_METERS * Math.cos(toRadians((a.latitude + b.latitude) / 2));
      const ky = EARTH_RADIUS_METERS;
      const bx = toRadians(b.longitude - a.longitude) * kx;
      const by = toRadians(b.latitude - a.latitude) * ky;
      const px = toRadians(point.longitude - a.longitude) * kx;
      const py = toRadians(point.latitude - a.latitude) * ky;
      const squared = bx * bx + by * by;
      let t = squared > 0 ? (px * bx + py * by) / squared : 0;
      t = Math.max(0, Math.min(1, t));
      // Respect the lower bound inside the segment that straddles it.
      if (length > 0 && start + t * length < minAlong) t = Math.min(1, (minAlong - start) / length);
      const distance = Math.hypot(px - t * bx, py - t * by);
      // On a tie (a route doubling back on itself) the earlier pass wins.
      if (!best || distance < best.distanceMeters - 0.01) {
        best = { alongMeters: start + t * length, distanceMeters: distance, segment: i };
      }
    }
    start = end;
  }
  // Every segment ended before the bound: the line's end is the only admissible point.
  return best ?? { alongMeters: start, distanceMeters: haversineMeters(point, fromPosition(line[line.length - 1]!)), segment: line.length - 2 };
}

/** Distance in metres from a point to a line (Infinity for an empty line). */
export function distanceToLineMeters(point: LatLon, line: readonly Position[]): number {
  return projectOntoLine(point, line)?.distanceMeters ?? Infinity;
}

/** The point `meters` along a line (clamped to its ends). */
export function pointAlongLine(line: readonly Position[], meters: number): LatLon | null {
  if (line.length === 0) return null;
  let remaining = Math.max(0, meters);
  for (let i = 0; i < line.length - 1; i += 1) {
    const a = fromPosition(line[i]!);
    const b = fromPosition(line[i + 1]!);
    const length = haversineMeters(a, b);
    if (remaining <= length) {
      const t = length > 0 ? remaining / length : 0;
      return { latitude: a.latitude + (b.latitude - a.latitude) * t, longitude: a.longitude + (b.longitude - a.longitude) * t };
    }
    remaining -= length;
  }
  return fromPosition(line[line.length - 1]!);
}
