import { z } from "zod";
import type { JourneyResponse, Problem } from "./types";

// Objects are loose: the API may add fields (M7 adds response models and departure
// operator/mode), and an addition must not break the client. Fields the client reads
// are required with their exact nullability, so a removal or type change fails loudly.

/** ISO instant with an explicit `Z` or ±HH:MM offset, as every API time is. */
export const instant = z
  .string()
  .regex(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$/)
  .refine((value) => Number.isFinite(Date.parse(value)), "not a valid instant");

const serviceDate = z.string().regex(/^\d{4}-\d{2}-\d{2}$/);
const notEnabled = z.literal("not_enabled");

export const ProblemSchema = z.looseObject({
  type: z.string(),
  title: z.string(),
  status: z.number().int(),
  code: z.string(),
  detail: z.string(),
  requestId: z.string(),
  errors: z.array(z.record(z.string(), z.string())).nullish(),
});

export const MetaSchema = z.looseObject({
  requestId: z.string(),
  generationId: z.string(),
  generatedAt: instant,
  dataBuiltAt: instant,
  mode: z.enum(["real", "fixture"]),
  coverage: z.looseObject({ from: instant, until: instant }),
  freshness: z.string(),
  capabilities: z.looseObject({ realtime: notEnabled, alerts: notEnabled }),
  attribution: z.array(z.string()),
  rankingPolicy: z.string(),
  appliedConstraints: z.record(z.string(), z.unknown()),
  warnings: z.array(z.string()),
});

const PageSchema = z.looseObject({ nextCursor: z.string().nullable() });
const LineString = z.looseObject({
  type: z.literal("LineString"),
  coordinates: z.array(z.array(z.number())),
});
const LatLon = z.looseObject({ latitude: z.number(), longitude: z.number() });

// --- /v1/status -------------------------------------------------------------

export const StatusSchema = z.looseObject({
  data: z.looseObject({
    ready: z.boolean(),
    staticData: z.enum(["available", "expired", "unavailable"]),
    routing: z.enum(["available", "unverified", "unavailable", "unchecked"]),
    reference: z.enum(["available", "unavailable"]),
    realtime: notEnabled,
    alerts: notEnabled,
    lastValidatedAt: instant.optional(),
  }),
  // Without a generation the API returns only requestId, generatedAt and a null id.
  meta: z.union([
    MetaSchema,
    z.looseObject({ requestId: z.string(), generatedAt: instant, generationId: z.null() }),
  ]),
});

// --- /v1/places ---------------------------------------------------------------

export const PlaceType = z.enum(["stop", "station", "poi", "address"]);

const StopLocationRef = z.looseObject({ kind: z.literal("stop"), stopId: z.string() });
const PlaceLocationRef = z.looseObject({ kind: z.literal("place"), placeRef: z.string() });

const StopCandidate = z.looseObject({
  kind: z.enum(["stop", "station"]),
  id: z.string(),
  displayName: z.string(),
  languageUsed: z.string(),
  locality: z.string().nullable(),
  coordinates: LatLon,
  stopCode: z.string().nullable(),
  parentId: z.string().nullable(),
  platformIds: z.array(z.string()),
  locationRef: StopLocationRef,
});

const GeocodedCandidate = z.looseObject({
  kind: z.enum(["poi", "address"]),
  name: z.string(),
  displayName: z.string(),
  languageUsed: z.string(),
  locality: z.string().nullable(),
  coordinates: LatLon,
  placeRef: z.string(),
  locationRef: PlaceLocationRef,
});

export const PlaceCandidateSchema = z.discriminatedUnion("kind", [StopCandidate, GeocodedCandidate]);

export const PlacesSchema = z.looseObject({
  data: z.array(PlaceCandidateSchema),
  meta: MetaSchema,
  matchedTypes: z.array(PlaceType),
  unavailableTypes: z.array(PlaceType),
  partial: z.boolean(),
  rankingPolicy: z.string(),
});

// --- stops and routes ---------------------------------------------------------

const StopItem = z.looseObject({
  stopId: z.string(),
  sourceId: z.string(),
  code: z.string().nullable(),
  name: z.string().nullable(),
  description: z.string().nullable(),
  latitude: z.number(),
  longitude: z.number(),
  locationType: z.number().int().nullable(),
  parentStationId: z.string().nullable(),
  wheelchairBoarding: z.number().int().nullable(),
  platformCode: z.string().nullable(),
});

const RouteItem = z.looseObject({
  routeId: z.string(),
  sourceId: z.string(),
  operatorId: z.string().nullable(),
  routeShortName: z.string().nullable(),
  routeLongName: z.string().nullable(),
  routeType: z.number().int(),
  color: z.string().nullable(),
  textColor: z.string().nullable(),
});

export const StopsPageSchema = z.looseObject({
  data: z.array(StopItem.extend({ distanceMeters: z.number().optional() })),
  page: PageSchema,
  meta: MetaSchema,
});

export const StopSchema = z.looseObject({
  data: StopItem.extend({
    translations: z.record(z.string(), z.string()),
    children: z.array(StopItem),
    routes: z.array(RouteItem),
    parent: StopItem.nullable().optional(),
  }),
  meta: MetaSchema,
});

export const RoutesPageSchema = z.looseObject({
  data: z.array(RouteItem),
  page: PageSchema,
  meta: MetaSchema,
});

export const RouteSchema = z.looseObject({
  data: RouteItem.extend({
    translations: z.record(z.string(), z.string()),
    agency: z.looseObject({ operatorId: z.string(), name: z.string().nullable() }).nullable(),
    patterns: z.array(
      z.looseObject({ patternId: z.string(), directionId: z.string().nullable(), headsign: z.string().nullable() }),
    ),
    patterns_count: z.number().int(),
    patterns_truncated: z.boolean(),
  }),
  meta: MetaSchema,
});

export const PatternsPageSchema = z.looseObject({
  data: z.array(
    z.looseObject({
      patternId: z.string(),
      routeId: z.string(),
      directionId: z.string().nullable(),
      headsign: z.string().nullable(),
      stops: z.array(
        z.looseObject({
          sequence: z.number().int(),
          stopId: z.string(),
          pickupType: z.number().int().nullable(),
          dropOffType: z.number().int().nullable(),
        }),
      ),
    }),
  ),
  page: PageSchema,
  meta: MetaSchema,
});

// --- timetable ----------------------------------------------------------------

export const TripSchema = z.looseObject({
  data: z.looseObject({
    tripRef: z.string(),
    sourceTripId: z.string(),
    serviceDate,
    startTime: z.string(),
    routeId: z.string().nullable(),
    routeShortName: z.string(),
    headsign: z.string().nullable(),
    shape: LineString.nullable(),
    calls: z.array(
      z.looseObject({
        callSequence: z.number().int(),
        ordinal: z.number().int(),
        stopId: z.string(),
        scheduledArrival: instant.nullable(),
        scheduledDeparture: instant.nullable(),
        pickupType: z.number().int().nullable(),
        dropOffType: z.number().int().nullable(),
      }),
    ),
    timingState: z.literal("scheduled"),
    expectedArrival: z.null(),
    expectedDeparture: z.null(),
    delaySeconds: z.null(),
    // The trip says "not_enabled" where journeys say null; capability decisions read
    // meta.capabilities and /v1/status only (design: Constraints from the current API).
    alerts: z.unknown(),
  }),
  meta: MetaSchema,
});

export const DeparturesPageSchema = z.looseObject({
  data: z.array(
    z.looseObject({
      scheduledDeparture: instant,
      stopId: z.string(),
      routeId: z.string().nullable(),
      routeShortName: z.string(),
      headsign: z.string().nullable(),
      platformCode: z.string().nullable(),
      pickupType: z.number().int().nullable(),
      tripRef: z.string(),
      callSequence: z.number().int(),
    }),
  ),
  page: PageSchema,
  meta: MetaSchema,
});

// --- journeys (typed by OpenAPI; validated here too) --------------------------

const Timing = z.looseObject({
  scheduledDeparture: instant,
  scheduledArrival: instant,
  timingState: z.literal("scheduled"),
  expectedDeparture: z.null(),
  expectedArrival: z.null(),
  delaySeconds: z.null(),
  observedAt: z.null(),
});

const JourneyLocation = z.looseObject({
  name: z.string(),
  latitude: z.number(),
  longitude: z.number(),
  stopId: z.string().nullable(),
  stopCode: z.string().nullable(),
});

const LegSchema = z.looseObject({
  kind: z.enum(["walk", "transit"]),
  mode: z.string(),
  from: JourneyLocation,
  to: JourneyLocation,
  timing: Timing,
  durationSeconds: z.number().int(),
  distanceMeters: z.number().nullable(),
  geometry: LineString.nullable(),
  geometryUnavailableReason: z.string().nullable(),
  transit: z
    .looseObject({
      operatorId: z.string(),
      operatorName: z.string(),
      routeId: z.string(),
      routeShortName: z.string(),
      headsign: z.string().nullable(),
      engineTripId: z.string(),
      sourceTripId: z.string(),
      serviceDate,
      startTime: z.string(),
    })
    .nullable(),
});

export const JourneyResponseSchema = z.looseObject({
  data: z.looseObject({
    outcome: z.enum(["routes_found", "no_route"]),
    journeys: z.array(
      z.looseObject({
        id: z.string(),
        timing: Timing,
        durationSeconds: z.number().int(),
        walkingSeconds: z.number().int(),
        walkingDistanceMeters: z.number().nullable(),
        transfers: z.number().int(),
        legs: z.array(LegSchema),
      }),
    ),
    alerts: z.null().optional(),
  }),
  meta: MetaSchema,
});

// Compile-time guard: what zod accepts must satisfy the OpenAPI-generated types.
type Satisfies<T extends U, U> = T;
export type _JourneyMatchesOpenApi = Satisfies<z.infer<typeof JourneyResponseSchema>, JourneyResponse>;
export type _ProblemMatchesOpenApi = Satisfies<z.infer<typeof ProblemSchema>, Problem>;

export type Status = z.infer<typeof StatusSchema>;
export type Places = z.infer<typeof PlacesSchema>;
export type PlaceCandidate = z.infer<typeof PlaceCandidateSchema>;
export type StopsPage = z.infer<typeof StopsPageSchema>;
export type StopDetail = z.infer<typeof StopSchema>;
export type RoutesPage = z.infer<typeof RoutesPageSchema>;
export type RouteDetail = z.infer<typeof RouteSchema>;
export type PatternsPage = z.infer<typeof PatternsPageSchema>;
export type Trip = z.infer<typeof TripSchema>;
export type DeparturesPage = z.infer<typeof DeparturesPageSchema>;
export type Meta = z.infer<typeof MetaSchema>;
