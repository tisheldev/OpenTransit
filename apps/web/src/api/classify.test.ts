import { describe, expect, it } from "vitest";
import { classify, isRetryable, UI_STATES, type UiState } from "./classify";
import { fixtures } from "./fixtures";

// Every problem code the API can emit (services/api/src/opentransit/api/**) with the
// status it is sent with, plus the transport cases.
const TABLE: Array<[status: number | null, code: string | null, expected: UiState]> = [
  [null, null, "network"],
  [0, null, "network"],
  [404, "NOT_FOUND", "not_found"],
  [404, null, "not_found"],
  [413, "BODY_TOO_LARGE", "invalid_request"],
  [422, "OUTSIDE_SERVICE_WINDOW", "outside_window"],
  [422, "INVALID_PLACE_REF", "invalid_place_ref"],
  [422, "INVALID_CURSOR", "invalid_cursor"],
  [422, "INVALID_REQUEST", "invalid_request"],
  [422, null, "invalid_request"],
  [400, null, "invalid_request"],
  [429, "RATE_LIMITED", "rate_limited"],
  [503, "FEED_EXPIRED", "data_expired"],
  [503, "CATEGORY_UNAVAILABLE", "category_unavailable"],
  [503, "DATA_UNAVAILABLE", "temporarily_unavailable"],
  [503, "SERVER_OVERLOADED", "temporarily_unavailable"],
  [503, "ENGINE_UNAVAILABLE", "temporarily_unavailable"],
  [503, "ENGINE_INVALID_RESPONSE", "temporarily_unavailable"],
  [503, "NOT_READY", "temporarily_unavailable"],
  [503, null, "temporarily_unavailable"],
  [504, "ENGINE_TIMEOUT", "temporarily_unavailable"],
  [502, null, "temporarily_unavailable"],
  [500, null, "unexpected"],
  [418, null, "unexpected"],
];

describe("classify()", () => {
  it.each(TABLE)("status %s code %s -> %s", (status, code, expected) => {
    expect(classify(status, code)).toBe(expected);
  });

  it("reaches every UI state", () => {
    expect(new Set(TABLE.map(([, , state]) => state))).toEqual(new Set(UI_STATES));
  });

  it("agrees with every problem fixture", () => {
    const expected: Record<string, UiState> = {
      "recorded-problem-invalid-cursor": "invalid_cursor",
      "recorded-problem-outside-window": "outside_window",
      "recorded-problem-trip-not-found": "not_found",
      "recorded-problem-invalid-place-ref": "invalid_place_ref",
      "recorded-problem-not-ready": "temporarily_unavailable",
      "synthetic-problem-stop-not-found": "not_found",
      "synthetic-problem-invalid-request": "invalid_request",
      "synthetic-problem-rate-limited": "rate_limited",
      "synthetic-problem-feed-expired": "data_expired",
    };
    const problemFixtures = Object.keys(fixtures).filter((name) => name.includes("-problem-"));
    expect(problemFixtures.sort()).toEqual(Object.keys(expected).sort());
    for (const name of problemFixtures) {
      const { status, body } = fixtures[name]!;
      expect(classify(status, (body as { code: string }).code), name).toBe(expected[name]);
    }
  });

  it("marks only transient states as retryable", () => {
    expect(UI_STATES.filter(isRetryable)).toEqual(["rate_limited", "temporarily_unavailable", "network"]);
  });
});
