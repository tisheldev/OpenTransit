import { describe, expect, it } from "vitest";
import type { z } from "zod";
import { fixtureManifest, fixtures } from "./fixtures";
import {
  DeparturesPageSchema,
  JourneyResponseSchema,
  PatternsPageSchema,
  PlacesSchema,
  ProblemSchema,
  RouteSchema,
  RoutesPageSchema,
  StatusSchema,
  StopSchema,
  StopsPageSchema,
  TripSchema,
} from "./schemas";

// Matches scripts/sanitise.mjs.
const SANITISED_REQUEST_ID = "0".repeat(32);

/** The schema each fixture's body must satisfy, chosen by its request. */
function schemaFor(name: string): z.ZodType {
  const { request, status } = fixtures[name]!;
  if (status >= 400) return ProblemSchema;
  const path = request.path;
  if (path === "/v1/status") return StatusSchema;
  if (path === "/v1/places") return PlacesSchema;
  if (path === "/v1/journeys") return JourneyResponseSchema;
  if (path.startsWith("/v1/trips/")) return TripSchema;
  if (path.endsWith("/departures")) return DeparturesPageSchema;
  if (path === "/v1/stops") return StopsPageSchema;
  if (path.startsWith("/v1/stops/")) return StopSchema;
  if (path.endsWith("/patterns")) return PatternsPageSchema;
  if (path === "/v1/routes") return RoutesPageSchema;
  if (path.startsWith("/v1/routes/")) return RouteSchema;
  throw new Error(`no schema for ${name} (${path})`);
}

const names = Object.keys(fixtures).sort();

describe("fixtures", () => {
  it("cover every public endpoint", () => {
    const schemas = new Set(names.map(schemaFor));
    for (const schema of [
      StatusSchema,
      PlacesSchema,
      JourneyResponseSchema,
      TripSchema,
      DeparturesPageSchema,
      StopsPageSchema,
      StopSchema,
      RoutesPageSchema,
      RouteSchema,
      PatternsPageSchema,
      ProblemSchema,
    ]) {
      expect(schemas.has(schema)).toBe(true);
    }
  });

  it.each(names)("%s passes its schema", (name) => {
    const result = schemaFor(name).safeParse(fixtures[name]!.body);
    expect(result.success ? [] : result.error.issues).toEqual([]);
  });

  it.each(names)("%s is sanitised and has provenance", (name) => {
    const text = JSON.stringify(fixtures[name]!.body);
    for (const match of text.matchAll(/"requestId":"([^"]*)"/g)) expect(match[1]).toBe(SANITISED_REQUEST_ID);
    expect(text).not.toMatch(/127\.0\.0\.1|localhost|[A-Z]:\\\\|\/home\//);
    const entry = fixtureManifest[name];
    expect(entry?.provenance).toMatch(/^(recorded|synthetic)$/);
    expect(name.startsWith(`${entry?.provenance}-`)).toBe(true);
    expect(entry?.sourceSha256).toMatch(/^[0-9a-f]{64}$/);
  });

  it("rejects a response that changes a field the client reads", () => {
    const body = structuredClone(fixtures["recorded-journey-routes"]!.body) as {
      data: { journeys: Array<{ durationSeconds: unknown }> };
    };
    body.data.journeys[0]!.durationSeconds = "12 minutes";
    expect(JourneyResponseSchema.safeParse(body).success).toBe(false);
  });

  it("tolerates fields the API adds later", () => {
    const body = structuredClone(fixtures["recorded-departures-page-1"]!.body) as {
      data: Array<Record<string, unknown>>;
    };
    body.data[0]!.operatorName = "added in M7";
    expect(DeparturesPageSchema.safeParse(body).success).toBe(true);
  });
});
