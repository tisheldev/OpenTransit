// Sanitised API responses. `recorded-*` come from committed real-API evidence
// (scripts/extract-recorded-fixtures.mjs) or a live recording (scripts/record-fixtures.mjs);
// `synthetic-*` come from the API's in-process test harness on a synthetic feed
// (scripts/synthetic_api_fixtures.py). manifest.json records each one's provenance.

export interface Fixture {
  request: { method: string; path: string; params: Record<string, unknown> | null; body: unknown };
  status: number;
  headers?: Record<string, string>;
  body: unknown;
}

export interface FixtureProvenance {
  provenance: "recorded" | "synthetic";
  source: string;
  sourceSha256: string;
  [key: string]: unknown;
}

const modules = import.meta.glob<Fixture>("./*.json", { eager: true, import: "default" });

export const fixtures: Record<string, Fixture> = Object.fromEntries(
  Object.entries(modules)
    .filter(([path]) => !path.endsWith("/manifest.json"))
    .map(([path, fixture]) => [path.replace(/^\.\/(.*)\.json$/, "$1"), fixture]),
);

export const fixtureManifest = (modules["./manifest.json"] ?? {}) as unknown as Record<string, FixtureProvenance>;

export function fixture(name: string): Fixture {
  const found = fixtures[name];
  if (!found) throw new Error(`No fixture named ${name}`);
  return found;
}
