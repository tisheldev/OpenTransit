import { describe, expect, it } from "vitest";
import type { Journey } from "../api/types";
import { earlierTime, laterTime, NO_ROUTE_STEP_MIN, whenFromOverride } from "./shift";

const j = (departure: string, arrival: string) =>
  ({ timing: { scheduledDeparture: departure, scheduledArrival: arrival } }) as Journey;

const shown = [
  j("2026-11-02T08:12:00+02:00", "2026-11-02T09:52:00+02:00"),
  j("2026-11-02T08:30:00+02:00", "2026-11-02T10:25:00+02:00"),
  j("2026-11-02T08:35:00+02:00", "2026-11-02T10:37:00+02:00"),
];

describe("Earlier / Later", () => {
  it("Later departs one minute after the latest shown departure", () => {
    expect(laterTime(shown)).toEqual({ departAt: "2026-11-02T08:36:00+02:00" });
  });

  it("Earlier arrives one minute before the earliest shown arrival", () => {
    expect(earlierTime(shown)).toEqual({ arriveBy: "2026-11-02T09:51:00+02:00" });
  });

  it("does not depend on the order shown", () => {
    const reversed = [...shown].reverse();
    expect(laterTime(reversed)).toEqual(laterTime(shown));
    expect(earlierTime(reversed)).toEqual(earlierTime(shown));
  });

  it("keeps an explicit Israel offset across the autumn change", () => {
    expect(laterTime([j("2026-10-25T01:59:00+03:00", "2026-10-25T03:00:00+02:00")])).toEqual({
      departAt: "2026-10-25T01:00:00+02:00",
    });
  });

  it("becomes the plan's time with the same instant, its explicit offset kept", () => {
    expect(whenFromOverride({ departAt: "2026-11-02T08:36:00+02:00" })).toEqual({
      mode: "depart_at",
      wall: "2026-11-02T08:36",
      offset: "+02:00",
    });
    expect(whenFromOverride({ arriveBy: "2026-10-01T09:51:00+03:00" })).toEqual({
      mode: "arrive_by",
      wall: "2026-10-01T09:51",
      offset: "+03:00",
    });
    // The repeated autumn hour stays the one shifted to, not re-asked.
    expect(whenFromOverride({ departAt: "2026-10-25T01:00:00+02:00" })).toEqual({
      mode: "depart_at",
      wall: "2026-10-25T01:00",
      offset: "+02:00",
    });
  });

  it("moves the asked time by a step when no route was found", () => {
    const asked = { departAt: "2026-11-02T08:00:00+02:00" } as never;
    expect(NO_ROUTE_STEP_MIN).toBe(60);
    expect(laterTime([], asked)).toEqual({ departAt: "2026-11-02T09:00:00+02:00" });
    expect(earlierTime([], asked)).toEqual({ arriveBy: "2026-11-02T07:00:00+02:00" });
    expect(laterTime([], null)).toBeNull();
  });
});
