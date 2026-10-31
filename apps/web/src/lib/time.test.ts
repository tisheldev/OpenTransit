import { describe, expect, it } from "vitest";
import { fixture } from "../api/fixtures";
import { TripSchema } from "../api/schemas";
import { formatDistance, formatDuration } from "./format";
import {
  departureInstant,
  formatClock,
  formatDate,
  israelOffset,
  israelWallTime,
  minutesUntil,
  shiftMinutes,
  toIsraelIso,
  tomorrowMorning,
} from "./time";

describe("test host", () => {
  it("runs under the zone vite.config.ts set (UTC unless OT_TEST_TZ is given)", () => {
    const expected = process.env.OT_TEST_TZ ?? "UTC";
    expect(Intl.DateTimeFormat().resolvedOptions().timeZone).toBe(expected === "UTC" ? "UTC" : expected);
    if (expected === "UTC") expect(new Date("2026-07-01T12:00:00Z").getTimezoneOffset()).toBe(0);
  });
});

// Ported from services/api/tests/playground.test.mjs, plus the client's additions.
describe("departureInstant()", () => {
  it("uses the date's offset, independent of host timezone", () => {
    expect(departureInstant("2026-10-01T08:00")).toEqual({ ok: true, instant: "2026-10-01T08:00:00+03:00" });
    expect(departureInstant("2026-10-26T08:00")).toEqual({ ok: true, instant: "2026-10-26T08:00:00+02:00" });
    expect(israelWallTime(new Date("2026-09-30T23:30:00Z"))).toBe("2026-10-01T02:30");
  });

  it("requires an explicit offset for the repeated autumn hour", () => {
    expect(departureInstant("2026-10-25T01:30")).toEqual({
      ok: false,
      reason: "ambiguous",
      candidates: ["+03:00", "+02:00"],
    });
    expect(departureInstant("2026-10-25T01:30", "+03:00")).toEqual({ ok: true, instant: "2026-10-25T01:30:00+03:00" });
    expect(departureInstant("2026-10-25T01:30", "+02:00")).toEqual({ ok: true, instant: "2026-10-25T01:30:00+02:00" });
  });

  it("rejects the missing spring hour and a wrong seasonal offset", () => {
    expect(departureInstant("2026-03-27T02:30")).toMatchObject({ ok: false, reason: "nonexistent" });
    expect(departureInstant("2026-10-01T08:00", "+02:00")).toMatchObject({ ok: false, reason: "offset_mismatch" });
  });

  it("rejects invalid calendar values and timestamps", () => {
    expect(departureInstant("2026-02-30T08:00")).toMatchObject({ ok: false, reason: "invalid" });
    expect(departureInstant("2026-10-01")).toMatchObject({ ok: false, reason: "invalid" });
    expect(departureInstant("2026-10-01T25:00")).toMatchObject({ ok: false, reason: "invalid" });
  });

  it("bases tomorrow on the Israel calendar across month and year boundaries", () => {
    expect(tomorrowMorning(new Date("2026-09-30T23:30:00Z"))).toBe("2026-10-02T08:00");
    expect(tomorrowMorning(new Date("2026-12-31T19:00:00Z"))).toBe("2027-01-01T08:00");
  });
});

describe("explicit offsets", () => {
  it("names Israel's offset on each side of both changes", () => {
    expect(israelOffset(new Date("2026-03-26T23:59:00Z"))).toBe("+02:00");
    expect(israelOffset(new Date("2026-03-27T00:00:00Z"))).toBe("+03:00");
    expect(israelOffset(new Date("2026-10-24T22:59:00Z"))).toBe("+03:00");
    expect(israelOffset(new Date("2026-10-24T23:00:00Z"))).toBe("+02:00");
  });

  it("writes an explicit now that names the same instant", () => {
    for (const utc of ["2026-10-24T22:30:00Z", "2026-10-24T23:30:00Z", "2026-07-01T09:15:42Z", "2027-01-01T00:00:00Z"]) {
      const iso = toIsraelIso(new Date(utc));
      expect(iso).toMatch(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2}$/);
      expect(Date.parse(iso)).toBe(Date.parse(utc));
    }
    // Both 01:30s of the autumn fold are distinct.
    expect(toIsraelIso(new Date("2026-10-24T22:30:00Z"))).toBe("2026-10-25T01:30:00+03:00");
    expect(toIsraelIso(new Date("2026-10-24T23:30:00Z"))).toBe("2026-10-25T01:30:00+02:00");
  });

  it("shifts across the autumn change by real minutes, not wall minutes", () => {
    expect(shiftMinutes("2026-10-25T01:30:00+03:00", 60)).toBe("2026-10-25T01:30:00+02:00");
    expect(shiftMinutes("2026-03-27T01:30:00+02:00", 60)).toBe("2026-03-27T03:30:00+03:00");
  });
});

describe("formatting", () => {
  it("shows a 24-hour Israel clock with Latin digits in both languages", () => {
    expect(formatClock("2026-09-30T20:50:00Z", "he")).toBe("23:50");
    expect(formatClock("2026-09-30T20:50:00Z", "en")).toBe("23:50");
    expect(formatClock("2026-10-24T22:30:00Z", "en")).toBe("01:30");
    expect(formatClock("2026-10-24T23:30:00Z", "en")).toBe("01:30");
  });

  it("shows the Israel date, not the host's", () => {
    expect(formatDate("2026-09-30T21:30:00Z", "en")).toBe("Thu 1 Oct");
    expect(formatDate("2026-09-30T21:30:00Z", "he")).toMatch(/1/);
  });

  it("formats the recorded DST-fold trip in order and in Israel time", () => {
    const trip = TripSchema.parse(fixture("recorded-trip-dst-fold-first").body).data;
    const times = trip.calls.map((call) => call.scheduledDeparture ?? call.scheduledArrival).filter((t) => t !== null);
    const instants = times.map((time) => Date.parse(time));
    expect(instants).toEqual([...instants].sort((a, b) => a - b));
    expect(trip.serviceDate).toBe("2026-10-25");
    // GTFS measures service times from noon minus 12 h. On the autumn change day that is
    // 23:00 the previous evening, so service time 00:00 is 01:00 on the wall clock. The
    // client shows the API's instants and never rebuilds a clock time from startTime.
    expect(trip.startTime).toBe("00:00");
    expect(times[0]).toBe("2026-10-24T22:00:00Z");
    expect(formatClock(times[0]!, "he")).toBe("01:00");
  });

  it("counts whole minutes until a departure", () => {
    const now = new Date("2026-10-01T05:00:00Z");
    expect(minutesUntil("2026-10-01T08:04:30+03:00", now)).toBe(5);
    expect(minutesUntil("2026-10-01T07:59:00+03:00", now)).toBe(-1);
  });

  it("formats durations with the design's units", () => {
    expect(formatDuration(0, "he")).toBe("0 דק׳");
    expect(formatDuration(61, "he")).toBe("2 דק׳");
    expect(formatDuration(3600, "he")).toBe("1 שע׳");
    expect(formatDuration(3900, "he")).toBe("1 שע׳ 5 דק׳");
    expect(formatDuration(3900, "en")).toBe("1 h 5 min");
  });

  it("formats distances and keeps unknown distances unknown", () => {
    expect(formatDistance(347, "he")).toBe("350 מ׳");
    expect(formatDistance(3, "en")).toBe("10 m");
    expect(formatDistance(1250, "he")).toBe("1.3 ק״מ");
    expect(formatDistance(12_400, "en")).toBe("12.4 km");
    expect(formatDistance(null, "he")).toBeNull();
  });
});
