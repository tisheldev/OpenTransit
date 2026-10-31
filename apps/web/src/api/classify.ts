/**
 * Every way a request can fail, as the interface shows it (design: Cross-cutting rules,
 * Error codes). "No route", "no departures" and "no matches" are successes with empty
 * results, so they never appear here.
 */
export const UI_STATES = [
  "outside_window", // 422 OUTSIDE_SERVICE_WINDOW: show the coverage dates
  "invalid_place_ref", // 422 INVALID_PLACE_REF: retry once with the saved coordinate
  "invalid_cursor", // 422 INVALID_CURSOR: restart the list
  "invalid_request", // other 400/413/422: a client bug, not the passenger's fault
  "not_found", // 404: "no longer in the timetable"
  "rate_limited", // 429: honour Retry-After
  "data_expired", // 503 FEED_EXPIRED: the timetable needs a fresh build
  "category_unavailable", // 503 CATEGORY_UNAVAILABLE: shown inline in search
  "temporarily_unavailable", // other 503/504: "temporarily unavailable", with retry
  "network", // no HTTP response: "can't reach OpenTransit"
  "unexpected", // anything else, including a response that fails its schema
] as const;

export type UiState = (typeof UI_STATES)[number];

/** Map an HTTP status (null when no response arrived) and problem code to a UI state. */
export function classify(status: number | null, code?: string | null): UiState {
  if (status === null || status === 0) return "network";
  switch (status) {
    case 404:
      return "not_found";
    case 429:
      return "rate_limited";
    case 400:
    case 413:
      return "invalid_request";
    case 422:
      if (code === "OUTSIDE_SERVICE_WINDOW") return "outside_window";
      if (code === "INVALID_PLACE_REF") return "invalid_place_ref";
      if (code === "INVALID_CURSOR") return "invalid_cursor";
      return "invalid_request";
    case 503:
      if (code === "FEED_EXPIRED") return "data_expired";
      if (code === "CATEGORY_UNAVAILABLE") return "category_unavailable";
      return "temporarily_unavailable";
    case 502:
    case 504:
      return "temporarily_unavailable";
    default:
      return "unexpected";
  }
}

/** States where trying the same request again later can succeed. */
export function isRetryable(state: UiState): boolean {
  return state === "temporarily_unavailable" || state === "network" || state === "rate_limited";
}
