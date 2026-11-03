import { describe, expect, it } from "vitest";
import type { JourneyRequest, JourneyResponse } from "../api/types";
import { keepForSameEnds, type JourneyAnswer } from "./queries";

const request = (extra: Partial<JourneyRequest> = {}): JourneyRequest =>
  ({
    from: { kind: "stop", stopId: "mot:stop:13583" },
    to: { kind: "coordinate", latitude: 32.7767, longitude: 35.0231 },
    departAt: "2026-11-02T08:00:00+02:00",
    results: 3,
    lang: "he",
    ...extra,
  }) as JourneyRequest;
const answer: JourneyAnswer = { response: {} as JourneyResponse, sent: request() };

describe("keepForSameEnds", () => {
  it("keeps the previous answer while only the time changes", () => {
    expect(keepForSameEnds(answer, { request: request({ departAt: "2026-11-02T08:36:00+02:00" }) })).toBe(answer);
    expect(keepForSameEnds(answer, { request: request({ departAt: undefined, arriveBy: "2026-11-02T09:51:00+02:00" }) })).toBe(answer);
  });

  it("never keeps it for other ends, another language, or nothing", () => {
    expect(keepForSameEnds(answer, { request: request({ from: { kind: "stop", stopId: "mot:stop:37358" } }) })).toBeUndefined();
    expect(keepForSameEnds(answer, { request: request({ to: answer.sent.from }) })).toBeUndefined();
    expect(keepForSameEnds(answer, { request: request({ lang: "en" }) })).toBeUndefined();
    expect(keepForSameEnds(undefined, { request: request() })).toBeUndefined();
    expect(keepForSameEnds(answer, null)).toBeUndefined();
  });
});
