import type { Journey, Leg } from "../api/types";
import type { Fix } from "../lib/geolocation";
import { destinationPoint, fromPosition, lineLengthMeters, pointAlongLine, type LatLon, type Position } from "./geo";

// SIMULATED positions (test data only): a passenger following a journey's schedule.
// Walks move along the leg geometry at walking pace, then wait at the stop; rides move
// along the leg geometry from the scheduled departure to the scheduled arrival. A walk
// without geometry (time-only transfer) is a straight line between its ends — invented
// for simulation, never shown as a real path.

export interface SimulateOptions {
  /** Schedule time between fixes. Default 5000 ms. */
  intervalMs?: number;
  /** Random horizontal error, metres (uniform in a disc). Default 0. */
  jitterMeters?: number;
  /** Reported accuracy on every fix. Default 10 m (null allowed). */
  accuracyMeters?: number | null;
  /** Seed for the jitter. Default 1. */
  seed?: number;
  /** Start this long before the first departure. Default 60 000 ms. */
  leadMs?: number;
  /** Keep emitting at the destination for this long after arrival. Default 60 000 ms. */
  trailMs?: number;
  /** Walking speed, m/s. Default 1.3. */
  walkSpeedMps?: number;
  /** No fixes in this window (offsets from the simulation start), e.g. a tunnel. */
  gap?: { afterMs: number; durationMs: number };
  /** Playback speed-up: `offsetMs` is compressed by this factor. Default 1. */
  speedUp?: number;
}

export interface SimulatedFix extends Fix {
  /** Always true: labels the fix as simulated. */
  simulated: true;
  /** When to play this fix, ms after playback starts (schedule offset ÷ speed-up). */
  offsetMs: number;
}

interface Piece {
  t0: number;
  t1: number;
  line: readonly Position[];
  length: number;
  /** Travel the line at constant speed from `t0` for `moveMs`, then stand at its end. */
  moveMs: number;
}

const legLine = (leg: Leg): readonly Position[] => {
  const coords = leg.geometry?.coordinates;
  if (coords && coords.length >= 2) return coords;
  return [
    [leg.from.longitude, leg.from.latitude],
    [leg.to.longitude, leg.to.latitude],
  ];
};

/** Deterministic PRNG (mulberry32). */
function random(seed: number): () => number {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function positionAt(pieces: readonly Piece[], t: number, start: LatLon): LatLon {
  let last: LatLon = start;
  for (const piece of pieces) {
    if (t < piece.t0) return last;
    const end = fromPosition(piece.line[piece.line.length - 1]!);
    if (t <= piece.t1) {
      const fraction = piece.moveMs > 0 ? Math.min(1, (t - piece.t0) / piece.moveMs) : 1;
      return pointAlongLine(piece.line, fraction * piece.length) ?? end;
    }
    last = end;
  }
  return last;
}

/** Simulated fixes for a journey, in schedule time (`at` follows the timetable). */
export function simulateJourney(journey: Journey, options: SimulateOptions = {}): SimulatedFix[] {
  const interval = options.intervalMs ?? 5_000;
  const jitter = options.jitterMeters ?? 0;
  const accuracy = options.accuracyMeters === undefined ? 10 : options.accuracyMeters;
  const walkSpeed = options.walkSpeedMps ?? 1.3;
  const speedUp = options.speedUp ?? 1;
  const first = journey.legs[0];
  if (!first || !(interval > 0) || !(speedUp > 0)) return [];

  const pieces: Piece[] = journey.legs.map((leg) => {
    const line = legLine(leg);
    const length = lineLengthMeters(line);
    const t0 = Date.parse(leg.timing.scheduledDeparture);
    const t1 = Date.parse(leg.timing.scheduledArrival);
    const scheduled = Math.max(0, t1 - t0);
    // Rides use the whole scheduled time; walks go at walking pace (faster if late).
    const moveMs = leg.kind === "transit" ? scheduled : Math.min(scheduled, (length / walkSpeed) * 1000);
    return { t0, t1, line, length, moveMs };
  });

  const start = Date.parse(first.timing.scheduledDeparture) - (options.leadMs ?? 60_000);
  const end = Date.parse(journey.timing.scheduledArrival) + (options.trailMs ?? 60_000);
  const origin: LatLon = { latitude: first.from.latitude, longitude: first.from.longitude };
  const next = random(options.seed ?? 1);
  const fixes: SimulatedFix[] = [];
  for (let t = start; t <= end; t += interval) {
    const offset = t - start;
    if (options.gap && offset >= options.gap.afterMs && offset < options.gap.afterMs + options.gap.durationMs) continue;
    let here = positionAt(pieces, t, origin);
    if (jitter > 0) here = destinationPoint(here, next() * 360, Math.sqrt(next()) * jitter);
    fixes.push({ latitude: here.latitude, longitude: here.longitude, accuracyMeters: accuracy, at: t, simulated: true, offsetMs: offset / speedUp });
  }
  return fixes;
}
