import { apiFetch } from "./http";
import { encodePathRef } from "./pathRef";
import { failure, type Result } from "./result";
import {
  DeparturesPageSchema,
  JourneyResponseSchema,
  LineSchema,
  LinesPageSchema,
  NearbyDeparturesSchema,
  PatternsPageSchema,
  PlacesSchema,
  RouteSchema,
  RoutesPageSchema,
  StatusSchema,
  StopSchema,
  StopLinesSchema,
  StopsPageSchema,
  TripSchema,
  type DeparturesPage,
  type LineDetail,
  type LinesPage,
  type NearbyDepartures,
  type StopLines,
  type PatternsPage,
  type Places,
  type RouteDetail,
  type RoutesPage,
  type Status,
  type StopDetail,
  type StopsPage,
  type Trip,
} from "./schemas";
import type { JourneyRequest, JourneyResponse } from "./types";

// One function per public endpoint. Each returns a Result and never throws.

export type Lang = "he" | "en";
export type PlaceTypeName = "stop" | "station" | "poi" | "address";

interface Paging {
  limit?: number;
  cursor?: string | null;
}

function withRef<T>(ref: string, run: (segment: string) => Promise<Result<T>>): Promise<Result<T>> {
  const encoded = encodePathRef(ref);
  if (!encoded.ok) return Promise.resolve(failure({ kind: "unroutable_ref", ref, reason: encoded.reason }));
  return run(encoded.segment);
}

const latLon = (point: { latitude: number; longitude: number }) => `${point.latitude},${point.longitude}`;

export function getStatus(signal?: AbortSignal): Promise<Result<Status>> {
  return apiFetch({ path: "/v1/status", signal }, StatusSchema);
}

export interface PlaceSearch {
  q: string;
  lang: Lang;
  near?: { latitude: number; longitude: number } | null;
  types?: readonly PlaceTypeName[];
  limit?: number;
}

export function searchPlaces(search: PlaceSearch, signal?: AbortSignal): Promise<Result<Places>> {
  return apiFetch(
    {
      path: "/v1/places",
      query: {
        q: search.q,
        lang: search.lang,
        near: search.near ? latLon(search.near) : null,
        type: search.types,
        limit: search.limit,
      },
      signal,
    },
    PlacesSchema,
  );
}

export function planJourney(request: JourneyRequest, signal?: AbortSignal): Promise<Result<JourneyResponse>> {
  return apiFetch({ method: "POST", path: "/v1/journeys", body: request, signal }, JourneyResponseSchema);
}

/** `tripRef` is `leg.transit.engineTripId` or a departure's `tripRef`, unchanged. */
export function getTrip(tripRef: string, signal?: AbortSignal): Promise<Result<Trip>> {
  return withRef(tripRef, (segment) => apiFetch({ path: `/v1/trips/${segment}`, signal }, TripSchema));
}

export function getStop(stopId: string, signal?: AbortSignal): Promise<Result<StopDetail>> {
  return withRef(stopId, (segment) => apiFetch({ path: `/v1/stops/${segment}`, signal }, StopSchema));
}

export interface DepartureQuery extends Paging {
  from: string; // ISO instant with an explicit offset
  horizonMinutes?: number;
}

export function getStopDepartures(
  stopId: string,
  query: DepartureQuery,
  signal?: AbortSignal,
): Promise<Result<DeparturesPage>> {
  return withRef(stopId, (segment) =>
    apiFetch(
      {
        path: `/v1/stops/${segment}/departures`,
        query: { from: query.from, horizonMinutes: query.horizonMinutes, limit: query.limit, cursor: query.cursor },
        signal,
      },
      DeparturesPageSchema,
    ),
  );
}

export interface NearbyDeparturesQuery {
  near: { latitude: number; longitude: number };
  from: string; // ISO instant with an explicit offset
  radiusMeters?: number;
  stops?: number;
  perStop?: number;
  horizonMinutes?: number;
}

/** Board 1: the stops around a point, each with the earliest departure of each line. */
export function getNearbyDepartures(query: NearbyDeparturesQuery, signal?: AbortSignal): Promise<Result<NearbyDepartures>> {
  return apiFetch(
    {
      path: "/v1/departures/nearby",
      query: {
        near: latLon(query.near),
        from: query.from,
        radius: query.radiusMeters,
        stops: query.stops,
        perStop: query.perStop,
        horizonMinutes: query.horizonMinutes,
      },
      signal,
    },
    NearbyDeparturesSchema,
  );
}

/** Board 7: every line through a stop with the patterns serving it (their stops in order). */
export function getStopLines(stopId: string, signal?: AbortSignal): Promise<Result<StopLines>> {
  return withRef(stopId, (segment) =>
    apiFetch({ path: `/v1/stops/${segment}/lines`, query: { patterns: "serving", limit: 50 }, signal }, StopLinesSchema),
  );
}

/** A stop item's mode (API-C6); the `mode` filter of GET /v1/stops takes a list of these (A1). */
export type StopMode = "rail" | "light_rail" | "bus" | "other";

export type StopArea =
  | { near: { latitude: number; longitude: number }; radiusMeters?: number }
  | {
      bbox: { west: number; south: number; east: number; north: number };
      /** A1: only these modes. Rail and light rail alone lift the area limit from 100 to 120,000 km². */
      modes?: readonly StopMode[] | null;
    };

export function listStops(area: StopArea, paging: Paging = {}, signal?: AbortSignal): Promise<Result<StopsPage>> {
  const query =
    "near" in area
      ? { near: latLon(area.near), radius: area.radiusMeters }
      : {
          bbox: `${area.bbox.west},${area.bbox.south},${area.bbox.east},${area.bbox.north}`,
          mode: area.modes && area.modes.length > 0 ? area.modes.join(",") : null,
        };
  return apiFetch({ path: "/v1/stops", query: { ...query, ...paging }, signal }, StopsPageSchema);
}

export interface RouteFilter extends Paging {
  stopId?: string;
  operatorId?: string;
  routeShortName?: string;
}

export function listRoutes(filter: RouteFilter, signal?: AbortSignal): Promise<Result<RoutesPage>> {
  return apiFetch({ path: "/v1/routes", query: { ...filter }, signal }, RoutesPageSchema);
}

export function getRoute(routeId: string, signal?: AbortSignal): Promise<Result<RouteDetail>> {
  return withRef(routeId, (segment) => apiFetch({ path: `/v1/routes/${segment}`, signal }, RouteSchema));
}

export function getRoutePatterns(
  routeId: string,
  paging: Paging = {},
  signal?: AbortSignal,
): Promise<Result<PatternsPage>> {
  return withRef(routeId, (segment) =>
    apiFetch({ path: `/v1/routes/${segment}/patterns`, query: { ...paging }, signal }, PatternsPageSchema),
  );
}

export interface LineSearch extends Paging {
  /** One character or more (user, 14 November 2026: a one-character query searches). */
  q: string;
  /** The passenger's position: ranks lines with a nearby stop first and adds `nearestStop`. */
  near?: { latitude: number; longitude: number } | null;
}

/** Contract A2: lines whose number starts with `q` (exact first), one item per operator + line code. */
export function searchLines(search: LineSearch, signal?: AbortSignal): Promise<Result<LinesPage>> {
  return apiFetch(
    {
      path: "/v1/lines",
      query: {
        q: search.q,
        lat: search.near ? search.near.latitude : null,
        lon: search.near ? search.near.longitude : null,
        limit: search.limit,
        cursor: search.cursor,
      },
      signal,
    },
    LinesPageSchema,
  );
}

/** Contract A2: one line by its key (operator + MOT line code). */
export function getLine(
  lineKey: string,
  near: { latitude: number; longitude: number } | null = null,
  signal?: AbortSignal,
): Promise<Result<LineDetail>> {
  return withRef(lineKey, (segment) =>
    apiFetch(
      { path: `/v1/lines/${segment}`, query: { lat: near?.latitude ?? null, lon: near?.longitude ?? null }, signal },
      LineSchema,
    ),
  );
}
