import type { JourneyRequest, LocationInput } from "../api/types";
import { locationSource, type Fix, type LocationError } from "../lib/geolocation";
import { departureInstant, toIsraelIso, type Lang } from "../lib/time";
import type { Endpoint, PlaceChoice, PlanDraft } from "./draft";

// Journey input (design: Domain model, "Journey input"). A stop is sent as {kind: stop};
// my location, map pins and searched places as coordinates. "Now" is always an explicit
// Israel timestamp with an offset.
//
// Searched places are sent as their coordinate, never as `placeRef`: the S1 real check on
// generation oct31a (31 Oct 2026) found a placeRef and its returned coordinate route
// identically 8/8 (4 places, both directions). Per the design that settles it: the client
// sends coordinates always and the INVALID_PLACE_REF retry path is deleted.

export const JOURNEY_RESULTS = 3;

/** An explicit time that replaces the draft's (Earlier / Later, plan/shift.ts). */
export type TimeOverride = { departAt: string } | { arriveBy: string };

export interface PlannedRequest {
  request: JourneyRequest;
}

export type TimeProblem = "nonexistent" | "ambiguous" | "invalid" | "offset_mismatch";

export type BuildResult =
  | ({ ok: true } & PlannedRequest)
  | { ok: false; reason: "missing_destination" }
  | { ok: false; reason: "missing_origin" }
  | { ok: false; reason: "location"; error: LocationError }
  | { ok: false; reason: "time"; problem: TimeProblem; candidates: string[] };

export interface BuildContext {
  /** Resolved "my location": a fix, an error, or null when the draft does not use it. */
  myLocation: Fix | LocationError | null;
  now: Date;
  lang: Lang;
  override?: TimeOverride | null;
}

const coordinate = (point: { latitude: number; longitude: number }): LocationInput => ({
  kind: "coordinate",
  latitude: point.latitude,
  longitude: point.longitude,
});

function placeInput(place: PlaceChoice): LocationInput {
  return place.stopId ? { kind: "stop", stopId: place.stopId } : coordinate(place);
}

/** Does this draft need a device fix? Only then is the location source asked. */
export function needsMyLocation(draft: PlanDraft): boolean {
  return draft.from?.type === "myLocation" || draft.to?.type === "myLocation";
}

type EndResult = { ok: true; input: LocationInput } | { ok: false; error: LocationError };

function endpointInput(endpoint: Endpoint, context: BuildContext): EndResult {
  if (endpoint.type === "myLocation") {
    const fix = context.myLocation;
    if (fix === null) return { ok: false, error: "unavailable" };
    if (typeof fix === "string") return { ok: false, error: fix };
    return { ok: true, input: coordinate(fix) };
  }
  return { ok: true, input: placeInput(endpoint.place) };
}

/** Build the journey request exactly per the design's input rule. Pure: no clock, no device. */
export function buildJourneyRequest(draft: PlanDraft, context: BuildContext): BuildResult {
  if (draft.to === null) return { ok: false, reason: "missing_destination" };
  if (draft.from === null) return { ok: false, reason: "missing_origin" };
  const from = endpointInput(draft.from, context);
  if (!from.ok) return { ok: false, reason: "location", error: from.error };
  const to = endpointInput(draft.to, context);
  if (!to.ok) return { ok: false, reason: "location", error: to.error };

  let time: TimeOverride;
  if (context.override) {
    time = context.override;
  } else if (draft.when.mode === "now") {
    time = { departAt: toIsraelIso(context.now) };
  } else {
    const instant = departureInstant(draft.when.wall, draft.when.offset);
    if (!instant.ok) return { ok: false, reason: "time", problem: instant.reason, candidates: instant.candidates };
    time = draft.when.mode === "depart_at" ? { departAt: instant.instant } : { arriveBy: instant.instant };
  }

  const request: JourneyRequest = { from: from.input, to: to.input, ...time, results: JOURNEY_RESULTS, lang: context.lang };
  return { ok: true, request };
}

/**
 * Resolve "my location" through the location source at request time (never earlier),
 * then build. Used by the Compare screen's request query.
 */
export async function resolveJourneyRequest(
  draft: PlanDraft,
  context: Omit<BuildContext, "myLocation" | "now"> & { now?: Date },
): Promise<BuildResult> {
  if (draft.to === null) return { ok: false, reason: "missing_destination" };
  if (draft.from === null) return { ok: false, reason: "missing_origin" };
  let myLocation: BuildContext["myLocation"] = null;
  if (needsMyLocation(draft)) {
    const result = await locationSource().current();
    myLocation = result.ok ? result.fix : result.error;
  }
  return buildJourneyRequest(draft, { ...context, myLocation, now: context.now ?? new Date() });
}

/** The instant a request asks about (for no-route Earlier / Later). */
export function requestInstant(request: JourneyRequest): { mode: "departAt" | "arriveBy"; instant: string } | null {
  if (request.departAt) return { mode: "departAt", instant: request.departAt };
  if (request.arriveBy) return { mode: "arriveBy", instant: request.arriveBy };
  return null;
}
