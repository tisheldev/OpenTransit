#!/usr/bin/env node
// Rebuild the `recorded-*` fixtures from HTTP evidence already committed under
// services/api/results. Deterministic and offline: it reads files, never the network.
//
//   node scripts/extract-recorded-fixtures.mjs
//
// Each fixture keeps the exact response body (sanitised) and records which result file
// and case it came from, so a schema failure can be traced back to the evidence.

import { createHash } from "node:crypto";
import { readFileSync, writeFileSync } from "node:fs";
import { dirname, join, relative } from "node:path";
import { fileURLToPath } from "node:url";
import { sanitise, stableJson } from "./sanitise.mjs";

const here = dirname(fileURLToPath(import.meta.url));
const web = join(here, "..");
const repo = join(web, "..", "..");
const out = join(web, "src", "api", "fixtures");

const SOURCES = {
  m3m4: "services/api/results/m3-m4-functional-http-20260930-01.json",
  english: "services/api/results/m4-english-functional-http-20260930-03.json",
};

// fixture name -> [source, case id]
const PICKS = {
  "recorded-journey-routes": ["m3m4", "search-to-journey"],
  "recorded-journey-poi": ["m3m4", "poi-ref-to-journey"],
  "recorded-trip-overnight": ["m3m4", "real-stop-overnight-20261001-trip"],
  "recorded-trip-dst-fold-first": ["m3m4", "real-stop-fold-first-20261025-trip"],
  "recorded-departures-page-1": ["m3m4", "overnight-departures-page-1"],
  "recorded-departures-page-2": ["m3m4", "overnight-departures-page-2"],
  "recorded-departures-last-page": ["m3m4", "overnight-departures-page-7"],
  "recorded-stop": ["m3m4", "search-stop-resolves"],
  "recorded-places-stop-he": ["m3m4", "stop-search"],
  "recorded-places-poi-en": ["m3m4", "poi-search"],
  "recorded-places-address-he": ["m3m4", "address-category-request"],
  "recorded-places-stop-en": ["english", "english-stop-search"],
  "recorded-places-empty": ["english", "valid-empty-stop-search"],
  "recorded-problem-invalid-cursor": ["m3m4", "cursor-query-mismatch"],
  "recorded-problem-outside-window": ["m3m4", "outside-coverage"],
  "recorded-problem-trip-not-found": ["m3m4", "unknown-trip"],
  "recorded-problem-invalid-place-ref": ["m3m4", "invalid-place-ref"],
  "recorded-problem-not-ready": ["english", "readiness-observation"],
};

const loaded = {};
const manifest = {};
for (const [name, [source, caseId]] of Object.entries(PICKS)) {
  const path = SOURCES[source];
  loaded[path] ??= readFileSync(join(repo, path));
  const evidence = JSON.parse(loaded[path].toString("utf8"));
  const recorded = evidence.cases.find((item) => item.id === caseId);
  if (!recorded) throw new Error(`${path} has no case ${caseId}`);
  const fixture = {
    request: { method: recorded.method, path: recorded.path, params: recorded.params ?? null, body: recorded.body ?? null },
    status: recorded.httpStatus,
    body: sanitise(recorded.response),
  };
  writeFileSync(join(out, `${name}.json`), stableJson(fixture));
  manifest[name] = {
    provenance: "recorded",
    source: path,
    sourceSha256: createHash("sha256").update(loaded[path]).digest("hex"),
    case: caseId,
    generationId: evidence.generationId,
    recordedAt: evidence.recordedAt,
  };
}

const manifestPath = join(out, "manifest.json");
let existing;
try {
  existing = JSON.parse(readFileSync(manifestPath, "utf8"));
} catch {
  existing = {};
}
const merged = Object.fromEntries(
  Object.entries({ ...existing, ...manifest }).sort(([a], [b]) => a.localeCompare(b)),
);
writeFileSync(manifestPath, stableJson(merged));
console.log(`wrote ${Object.keys(manifest).length} recorded fixtures to ${relative(repo, out)}`);
