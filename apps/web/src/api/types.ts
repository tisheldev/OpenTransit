// Journey and problem types come from the committed OpenAPI snapshot (openapi/openapi.json,
// regenerated with `npm run openapi:types`). Every other response is untyped in the API
// and is described by the zod schemas in ./schemas.ts.
import type { components, operations } from "./generated/openapi";

type Schemas = components["schemas"];

export type JourneyRequest = Schemas["JourneyRequest"];
export type JourneyResponse = Schemas["JourneyResponse"];
export type Journey = Schemas["Journey"];
export type Leg = Schemas["Leg"];
export type Transit = Schemas["Transit"];
export type Metadata = Schemas["Metadata"];
export type LocationInput = JourneyRequest["from"];

export type Problem =
  operations["plan_v1_journeys_post"]["responses"][422]["content"]["application/problem+json"];
