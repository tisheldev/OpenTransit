import { z } from "zod";
import { apiFetch } from "./http";
import { encodePathRef } from "./pathRef";
import { failure, type Result } from "./result";
import { JourneyResponseSchema, MetaSchema } from "./schemas";
import type { JourneyRequest, JourneyResponse } from "./types";

// Lines and "Ride it" (stops-and-lines contracts A2 and A3, 14 November 2026). Additive
// API surface the client mocks with MSW until the API ships it:
// - A2 `GET /v1/lines/{lineKey}` (one line) and `GET /v1/lines?q=` (line search; the Line
//   screen only uses it to find the line a route belongs to: route items carry no line code).
// - A3 `POST /v1/journeys` with `pinnedTrip`: one journey, a walk to the board stop and one
//   ride on that trip to the alight stop.
// Objects are loose, as in schemas.ts: fields the client reads are required.

const PageSchema = z.looseObject({ nextCursor: z.string().nullable() });

export const LineDirectionSchema = z.looseObject({
  routeId: z.string(),
  headsign: z.string().nullable(),
  originName: z.string().nullable(),
  destinationName: z.string().nullable(),
});

export const LineItemSchema = z.looseObject({
  lineKey: z.string(),
  shortName: z.string(),
  operatorId: z.string(),
  operatorName: z.string().nullable(),
  mode: z.string(),
  routeIds: z.array(z.string()),
  directions: z.array(LineDirectionSchema),
  area: z.string().nullable(),
  nearestStop: z.looseObject({ stopId: z.string(), name: z.string().nullable(), distanceM: z.number() }).nullish(),
});

export const LineSchema = z.looseObject({ data: LineItemSchema, meta: MetaSchema });
export const LinesPageSchema = z.looseObject({ data: z.array(LineItemSchema), page: PageSchema, meta: MetaSchema });

export type LineItem = z.infer<typeof LineItemSchema>;
export type LineDirection = z.infer<typeof LineDirectionSchema>;
export type LineAnswer = z.infer<typeof LineSchema>;
export type LinesPage = z.infer<typeof LinesPageSchema>;

type Near = { latitude: number; longitude: number } | null | undefined;

/** One line by its key; with a position, its stop nearest the passenger (within 2 km). */
export function getLine(lineKey: string, near?: Near, signal?: AbortSignal): Promise<Result<LineAnswer>> {
  const encoded = encodePathRef(lineKey);
  if (!encoded.ok) return Promise.resolve(failure({ kind: "unroutable_ref", ref: lineKey, reason: encoded.reason }));
  return apiFetch(
    { path: `/v1/lines/${encoded.segment}`, query: { lat: near?.latitude, lon: near?.longitude }, signal },
    LineSchema,
  );
}

/** Line search by number (prefix; exact matches first). */
export function searchLines(q: string, near?: Near, limit = 20, signal?: AbortSignal): Promise<Result<LinesPage>> {
  return apiFetch(
    { path: "/v1/lines", query: { q, lat: near?.latitude, lon: near?.longitude, limit }, signal },
    LinesPageSchema,
  );
}

/**
 * The line a route belongs to (a stop's line, a journey's ride): search its number and keep
 * the line whose routes include it. Null when the API lists no such line.
 */
export async function lineKeyForRoute(routeId: string, shortName: string, signal?: AbortSignal): Promise<Result<string | null>> {
  const found = await searchLines(shortName.trim(), null, 50, signal);
  if (!found.ok) return found;
  return { ...found, value: found.value.data.find((line) => line.routeIds.includes(routeId))?.lineKey ?? null };
}

/** A3: the trip to ride, where to board it and where to get off. */
export interface PinnedTrip {
  tripRef: string;
  boardStopId: string;
  alightStopId: string;
}

export type PinnedJourneyRequest = JourneyRequest & { pinnedTrip: PinnedTrip };

/** The warning a pinned journey carries when the walk cannot make the departure. */
export const PINNED_TRIP_MISSED_BY_WALK = "PINNED_TRIP_MISSED_BY_WALK";

export function planPinnedJourney(request: PinnedJourneyRequest, signal?: AbortSignal): Promise<Result<JourneyResponse>> {
  return apiFetch({ method: "POST", path: "/v1/journeys", body: request, signal }, JourneyResponseSchema);
}
