import { classify, type UiState } from "./classify";
import type { Problem } from "./types";

export type ApiError =
  | { kind: "problem"; status: number; problem: Problem; retryAfterSeconds: number | null }
  | { kind: "http"; status: number } // an error status without a problem body
  | { kind: "invalid_response"; status: number; issues: string[] }
  | { kind: "network" }
  | { kind: "aborted" }
  | { kind: "unroutable_ref"; ref: string; reason: string };

export type Result<T> =
  | { ok: true; value: T; status: number }
  | { ok: false; error: ApiError; state: UiState };

export function stateOf(error: ApiError): UiState {
  switch (error.kind) {
    case "problem":
      return classify(error.status, error.problem.code);
    case "http":
      return classify(error.status);
    case "network":
    case "aborted":
      return "network";
    case "invalid_response":
    case "unroutable_ref":
      return "unexpected";
  }
}

export function failure<T>(error: ApiError): Result<T> {
  return { ok: false, error, state: stateOf(error) };
}

/** Thrown by query functions so TanStack Query sees a failure with its UI state attached. */
export class ApiFailure extends Error {
  readonly error: ApiError;
  readonly state: UiState;
  constructor(error: ApiError, state: UiState) {
    super(`OpenTransit API: ${state}`);
    this.name = "ApiFailure";
    this.error = error;
    this.state = state;
  }
}

export function unwrap<T>(result: Result<T>): T {
  if (result.ok) return result.value;
  throw new ApiFailure(result.error, result.state);
}

/** Retry-After is delta-seconds or an HTTP date; anything else is ignored. */
export function parseRetryAfter(header: string | null, now = Date.now()): number | null {
  if (header === null || header.trim() === "") return null;
  const trimmed = header.trim();
  if (/^\d+$/.test(trimmed)) return Number(trimmed);
  const at = Date.parse(trimmed);
  if (!Number.isFinite(at)) return null;
  return Math.max(0, Math.ceil((at - now) / 1000));
}
