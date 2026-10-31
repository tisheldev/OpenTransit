import { useSyncExternalStore } from "react";
import type { Trip } from "../api/schemas";
import type { Journey, Metadata } from "../api/types";
import { readSession, removeSession, writeSession } from "../storage/session";

// The active trip (design: ActiveTrip, Restore after the app is killed). In the web test
// client it lives in sessionStorage: it survives a reload, never a closed tab, and holds
// no device position. CONTRACT: S6 extends NavProgress and the engine wiring but keeps
// these exports and their meaning.

export const ACTIVE_TRIP_VERSION = 1;
/** A trip ends by itself two hours after its scheduled arrival. */
export const EXPIRY_AFTER_ARRIVAL_MS = 2 * 3600_000;

export interface NavProgress {
  stepIndex: number;
  /** Set by S6 (phase, stopsLeft, cue, locationMode, lastFixAt); never a position. */
  [key: string]: unknown;
}

export interface ActiveTrip {
  version: typeof ACTIVE_TRIP_VERSION;
  journey: Journey;
  meta: Metadata;
  /** Trip details already fetched for this journey's transit legs, by engineTripId. */
  trips: Record<string, Trip["data"]>;
  startedAt: string;
  nav: NavProgress;
}

function isActiveTrip(value: unknown): value is ActiveTrip {
  if (!value || typeof value !== "object") return false;
  const trip = value as Partial<ActiveTrip>;
  return (
    trip.version === ACTIVE_TRIP_VERSION &&
    typeof trip.journey === "object" &&
    trip.journey !== null &&
    Array.isArray(trip.journey.legs) &&
    typeof trip.nav?.stepIndex === "number"
  );
}

export function isExpired(trip: ActiveTrip, now: number = Date.now()): boolean {
  const arrival = Date.parse(trip.journey.timing.scheduledArrival);
  return !Number.isFinite(arrival) || now > arrival + EXPIRY_AFTER_ARRIVAL_MS;
}

let cached: ActiveTrip | null | undefined;
const listeners = new Set<() => void>();

function notify(): void {
  for (const listener of listeners) listener();
}

/** Read the stored trip; an expired or unreadable one is cleared. */
export function loadActiveTrip(now: number = Date.now()): ActiveTrip | null {
  const stored = readSession("activeTrip", isActiveTrip);
  if (stored && isExpired(stored, now)) {
    removeSession("activeTrip");
    return null;
  }
  return stored;
}

export function getActiveTrip(): ActiveTrip | null {
  if (cached === undefined) cached = loadActiveTrip();
  return cached;
}

/** Start a trip (replacing any other). */
export function startActiveTrip(input: { journey: Journey; meta: Metadata; trips: ActiveTrip["trips"] }, now = new Date()): ActiveTrip {
  const trip: ActiveTrip = { version: ACTIVE_TRIP_VERSION, ...input, startedAt: now.toISOString(), nav: { stepIndex: 0 } };
  cached = trip;
  writeSession("activeTrip", trip);
  notify();
  return trip;
}

export function updateActiveTrip(change: (trip: ActiveTrip) => ActiveTrip): void {
  const current = getActiveTrip();
  if (!current) return;
  cached = change(current);
  writeSession("activeTrip", cached);
  notify();
}

/** Finish or End trip: cleared from storage. */
export function endActiveTrip(): void {
  cached = null;
  removeSession("activeTrip");
  notify();
}

/** Forget the in-memory copy (tests; clear all local data). */
export function resetActiveTripCache(): void {
  cached = undefined;
  notify();
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function useActiveTrip(): ActiveTrip | null {
  return useSyncExternalStore(subscribe, getActiveTrip, getActiveTrip);
}

/** The same journey (same legs, trips and times), regardless of response identity. */
export function sameJourney(a: Journey, b: Journey): boolean {
  if (a.legs.length !== b.legs.length) return false;
  return a.legs.every((leg, index) => {
    const other = b.legs[index]!;
    return (
      leg.kind === other.kind &&
      leg.timing.scheduledDeparture === other.timing.scheduledDeparture &&
      leg.timing.scheduledArrival === other.timing.scheduledArrival &&
      (leg.transit?.engineTripId ?? null) === (other.transit?.engineTripId ?? null)
    );
  });
}
