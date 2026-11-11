import { describe, expect, it } from "vitest";
import { initialNavState, type NavState } from "../../nav/engine";
import { buildSteps } from "../../nav/steps";
import { callPositionsFor, recordedJourneys, recordedTrips } from "../../nav/testdata";
import { rideRemaining } from "./rideRows";

// Journey 2's first ride: bus 249, 8 stops from דיזנגוף סנטר/טשרניחובסקי (08:38) to
// ת. רכבת תל אביב - סבידור/דרך נמיר (08:48).
const steps = buildSteps(recordedJourneys[2]!, recordedTrips);
const ride = steps[1]!;
const trip = recordedTrips[ride.ride!.tripRef]!;
const riding = (stopsLeft: number | null): NavState => ({ ...initialNavState(steps, 0), stepIndex: 1, phase: "riding", stopsLeft });
const named = callPositionsFor(steps, "two_before_exit")[1]!.map((call, i) => ({ ...call, name: `תחנה ${i + 1}` }));
const at = (hhmm: string) => Date.parse(`2026-11-02T${hhmm}:00+02:00`);

describe("rideRemaining (board 5)", () => {
  it("before departure: every stop left, from the boarding stop; the panel stays short (middle stops as one count)", () => {
    const left = rideRemaining(ride, riding(8), trip, named, at("08:30"));
    expect(left).toMatchObject({ left: 8, measured: false, passed: ride.ride!.boardOrdinal });
    // Seven stops between: only the next one and the one before the exit could be named;
    // the next one has no name here, so it joins the count.
    expect(left.rows.map((row) => [row.kind, row.name, row.count ?? null])).toEqual([
      ["here", "דיזנגוף סנטר/טשרניחובסקי", null],
      ["between", null, 6],
      ["stop", "תחנה 2", null],
      ["exit", "ת. רכבת תל אביב - סבידור/דרך נמיר", null],
    ]);
    expect(Date.parse(left.rows.at(-1)!.time!)).toBe(Date.parse(ride.scheduledArrival));
  });

  it("by the timetable the count goes down with the clock (said as such)", () => {
    const left = rideRemaining(ride, riding(8), trip, named, at("08:47"));
    expect(left.measured).toBe(false);
    expect(left.left).toBeLessThan(8);
    expect(left.rows[0]!.kind).toBe("here");
  });

  it("measured from fixes once the engine passed calls; a named 'here' row", () => {
    const left = rideRemaining(ride, riding(2), trip, named, at("08:30"));
    expect(left).toMatchObject({ left: 2, measured: true });
    expect(left.rows.map((row) => [row.kind, row.name])).toEqual([
      ["here", "תחנה 1"],
      ["stop", "תחנה 2"],
      ["exit", "ת. רכבת תל אביב - סבידור/דרך נמיר"],
    ]);
  });

  it("an unnamed place is 'you are here', never a made-up name", () => {
    const left = rideRemaining(ride, riding(5), trip, named, at("08:30"));
    expect(left.rows[0]).toMatchObject({ kind: "here", name: null });
  });

  it("without trip detail but with the journey's intermediate stops (API PR #35): every stop by name, by the timetable", () => {
    const noDetail = structuredClone(buildSteps(recordedJourneys[2]!, {})[1]!);
    // Shaped as the API's leg.intermediateStops: names and times made up for the test.
    noDetail.ride!.intermediateStops = ["א", "ב", "ג"].map((name, i) => ({
      name: `תחנה ${name}`,
      stopId: `test:${i}`,
      latitude: 32.08,
      longitude: 34.78,
      scheduledArrival: `2026-11-02T08:4${i}:00+02:00`,
      scheduledDeparture: `2026-11-02T08:4${i}:00+02:00`,
    }));
    const left = rideRemaining(noDetail, riding(null), undefined, undefined, at("08:41"));
    expect(left).toMatchObject({ left: 2, measured: false, passed: null });
    expect(left.rows.map((row) => [row.kind, row.name])).toEqual([
      ["here", "תחנה ב"],
      ["stop", "תחנה ג"],
      ["exit", "ת. רכבת תל אביב - סבידור/דרך נמיר"],
    ]);
  });

  it("trip calls with names (API PR #35): the next stop and the one before the exit by name, the rest counted", () => {
    const withNames = structuredClone(trip);
    for (const call of withNames.calls) Object.assign(call, { name: `קריאה ${call.ordinal}` });
    const board = ride.ride!.boardOrdinal!;
    const exit = ride.ride!.exitOrdinal!;
    const left = rideRemaining(ride, riding(8), withNames, undefined, at("08:30"));
    expect(left.rows.map((row) => [row.kind, row.name, row.count ?? null])).toEqual([
      ["here", "דיזנגוף סנטר/טשרניחובסקי", null],
      ["stop", `קריאה ${board + 1}`, null],
      ["between", null, 5],
      ["stop", `קריאה ${exit - 1}`, null],
      ["exit", "ת. רכבת תל אביב - סבידור/דרך נמיר", null],
    ]);
    // Two stops to go: all named.
    expect(rideRemaining(ride, riding(3), withNames, undefined, at("08:30")).rows.map((row) => row.kind)).toEqual(["here", "stop", "stop", "exit"]);
  });

  it("without trip detail: the two stops the journey names, no count", () => {
    const noDetail = buildSteps(recordedJourneys[2]!, {})[1]!;
    const left = rideRemaining(noDetail, riding(null), undefined, undefined, at("08:40"));
    expect(left).toMatchObject({ left: null, passed: null });
    expect(left.rows.map((row) => row.kind)).toEqual(["stop", "exit"]);
  });
});
