import spec from "../../openapi/openapi.json";

// The mocks answer like the API for a query parameter out of the API's own bounds (the
// committed OpenAPI snapshot's minimum, maximum and maxLength): 422 INVALID_REQUEST. Found
// on 14 November 2026 when Home asked nearby departures for perStop=6 (the API's maximum is
// 5): the fixtures answered, the real API refused and Home showed an error.

interface ParameterSchema {
  type?: string;
  minimum?: number;
  maximum?: number;
  exclusiveMinimum?: number;
  exclusiveMaximum?: number;
  maxLength?: number;
  anyOf?: ParameterSchema[];
}
interface Parameter {
  name: string;
  in: string;
  schema?: ParameterSchema;
}
type Operation = { parameters?: Parameter[] };

const paths = (spec as unknown as { paths: Record<string, Record<string, Operation>> }).paths;

/** Each GET path as a pattern (`{stopId}` matches one segment) with its query parameters. */
const routes = Object.entries(paths)
  .filter(([, item]) => item.get)
  .map(([path, item]) => ({
    pattern: new RegExp(`^${path.replace(/[.*+?^$()|[\]\\]/g, "\\$&").replace(/\\?\{[^}]+\\?\}/g, "[^/]+")}$`),
    query: (item.get!.parameters ?? []).filter((parameter) => parameter.in === "query"),
  }));

function bounds(schema: ParameterSchema | undefined): ParameterSchema | null {
  if (!schema) return null;
  if (schema.anyOf) return schema.anyOf.find((option) => option.type && option.type !== "null") ?? null;
  return schema;
}

/** The first query parameter outside the API's bounds, or null when the request is within them. */
export function outsideSpec(url: URL): string | null {
  const route = routes.find((candidate) => candidate.pattern.test(url.pathname.replace(/^.*?(\/v1\/)/, "$1")));
  if (!route) return null;
  for (const parameter of route.query) {
    const raw = url.searchParams.get(parameter.name);
    const schema = bounds(parameter.schema);
    if (raw === null || !schema) continue;
    if (schema.maxLength !== undefined && raw.length > schema.maxLength) return parameter.name;
    if (schema.type === "integer" || schema.type === "number") {
      const value = Number(raw);
      if (!Number.isFinite(value)) return parameter.name;
      if (schema.type === "integer" && !Number.isInteger(value)) return parameter.name;
      if (schema.minimum !== undefined && value < schema.minimum) return parameter.name;
      if (schema.maximum !== undefined && value > schema.maximum) return parameter.name;
      if (schema.exclusiveMinimum !== undefined && value <= schema.exclusiveMinimum) return parameter.name;
      if (schema.exclusiveMaximum !== undefined && value >= schema.exclusiveMaximum) return parameter.name;
    }
  }
  return null;
}
