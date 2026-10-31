import { apiFetch } from "./http";
import { encodePathRef } from "./pathRef";
import { failure, type Result } from "./result";
import {
  DeparturesPageSchema,
  JourneyResponseSchema,
  PatternsPageSchema,
  PlacesSchema,
  RouteSchema,
  RoutesPageSchema,
  StatusSchema,
  StopSchema,
  StopsPageSchema,
  TripSchema,
  type DeparturesPage,
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

export type StopArea =
  | { near: { latitude: number; longitude: number }; radiusMeters?: number }
  | { bbox: { west: number; south: number; east: number; north: number } };

export function listStops(area: StopArea, paging: Paging = {}, signal?: AbortSignal): Promise<Result<StopsPage>> {
  const query =
    "near" in area
      ? { near: latLon(area.near), radius: area.radiusMeters }
      : { bbox: `${area.bbox.west},${area.bbox.south},${area.bbox.east},${area.bbox.north}` };
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
