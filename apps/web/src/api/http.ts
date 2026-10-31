import type { z } from "zod";
import { failure, parseRetryAfter, type Result } from "./result";
import { ProblemSchema } from "./schemas";

export type Query = Record<string, string | number | readonly string[] | null | undefined>;

export interface ApiRequest {
  method?: "GET" | "POST";
  path: string; // already encoded, starting with /v1/
  query?: Query;
  body?: unknown;
  signal?: AbortSignal;
}

export function buildUrl(path: string, query?: Query): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query ?? {})) {
    if (value === null || value === undefined) continue;
    if (Array.isArray(value)) for (const item of value) params.append(key, item);
    else params.append(key, String(value));
  }
  const search = params.toString();
  // Absolute against this page's origin: the API is same-origin (no CORS), and Node's
  // fetch under test cannot resolve a bare path.
  const url = new URL(path, globalThis.location?.origin ?? "http://localhost");
  url.search = search;
  return url.href;
}

function issuesOf(error: z.ZodError): string[] {
  return error.issues.slice(0, 10).map((issue) => `${issue.path.join(".") || "(root)"}: ${issue.message}`);
}

/**
 * One request to the same-origin API. Never throws: every outcome is a Result whose
 * failure carries the UI state from classify(). Success bodies are validated.
 */
export async function apiFetch<S extends z.ZodType>(
  request: ApiRequest,
  schema: S,
): Promise<Result<z.infer<S>>> {
  let response: Response;
  try {
    response = await fetch(buildUrl(request.path, request.query), {
      method: request.method ?? "GET",
      headers: {
        Accept: "application/json, application/problem+json",
        ...(request.body === undefined ? {} : { "Content-Type": "application/json" }),
      },
      body: request.body === undefined ? undefined : JSON.stringify(request.body),
      signal: request.signal,
      credentials: "same-origin",
      cache: "no-store",
    });
  } catch (error) {
    if (request.signal?.aborted || (error instanceof DOMException && error.name === "AbortError")) {
      return failure({ kind: "aborted" });
    }
    return failure({ kind: "network" });
  }

  let body: unknown;
  try {
    body = await response.json();
  } catch {
    body = undefined;
  }

  if (!response.ok) {
    const problem = ProblemSchema.safeParse(body);
    if (problem.success) {
      return failure({
        kind: "problem",
        status: response.status,
        problem: problem.data,
        retryAfterSeconds: parseRetryAfter(response.headers.get("Retry-After")),
      });
    }
    return failure({ kind: "http", status: response.status });
  }

  const parsed = schema.safeParse(body);
  if (!parsed.success) {
    return failure({ kind: "invalid_response", status: response.status, issues: issuesOf(parsed.error) });
  }
  return { ok: true, value: parsed.data, status: response.status };
}
