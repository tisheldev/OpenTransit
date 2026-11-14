import { describe, expect, it } from "vitest";
import type { LineItem } from "../../api/lines";
import type { DeparturesPage, StopLines, StopsPage } from "../../api/schemas";
import { anchorIndex, directionsOf, headwayMinutes, lineDepartures, railAt, rideRows, stopRows, stopTimes, walkMinutes, type PatternStop } from "./lineModel";

// The Line screen's and Ride it's facts (boards 4 and 5), without React or the map.

const stop = (id: string, latitude: number, name = id): PatternStop => ({ stopId: id, name, latitude, longitude: 34.78, pickupType: 0, dropOffType: 0 });
const stops = Array.from({ length: 42 }, (_, i) => stop(`s${i}`, 32 + i / 1000));

const line: LineItem = {
  lineKey: "5:55008",
  shortName: "8",
  operatorId: "5",
  operatorName: "דן",
  mode: "bus",
  routeIds: ["r1", "r2"],
  directions: [
    { routeId: "r1", headsign: "תל אביב יפו_אוניברסיטת ת\"א", originName: "s0", destinationName: "s41" },
    { routeId: "r2", headsign: null, originName: "s41", destinationName: "מסוף הטייסים" },
  ],
  area: null,
};

const pattern = (routeId: string, list: PatternStop[], id = routeId) => ({
  patternId: id,
  routeId,
  directionId: null,
  headsign: null,
  servesStop: true,
  stopIndex: 0,
  stops: list,
});

describe("directionsOf", () => {
  it("takes each route's longest pattern, in the line's order, from patterns=all (each pattern names its route)", () => {
    const items = [
      {
        routeId: "r1",
        routeShortName: "8",
        operatorId: "5",
        operatorName: "דן",
        mode: "bus",
        routeType: 3,
        patterns: [pattern("r2", [...stops].reverse()), pattern("r1", stops.slice(0, 10), "short"), pattern("r1", stops), pattern("other", stops)],
      },
    ] as unknown as StopLines["data"];
    const directions = directionsOf(line, items);
    expect(directions.map((d) => [d.routeId, d.towards, d.origin, d.stops.length])).toEqual([
      ["r1", "אוניברסיטת ת\"א", "s0", 42],
      ["r2", "מסוף הטייסים", "s41", 42],
    ]);
  });
});

describe("anchorIndex", () => {
  it("opens at the stop nearest the passenger, else the stop asked for, else the first", () => {
    expect(anchorIndex(stops, { latitude: 32.0221, longitude: 34.78 })).toBe(22);
    expect(anchorIndex(stops, null, ["s7"])).toBe(7);
    expect(anchorIndex(stops, null, ["missing"])).toBe(0);
    // Far from the line (over 2 km): the stop asked for.
    expect(anchorIndex(stops, { latitude: 31.5, longitude: 34.78 }, ["s9"])).toBe(9);
  });
});

describe("stopRows", () => {
  it("folds the earlier stops, shows four after the anchor, folds the rest and ends at the terminus (board 4)", () => {
    expect(stopRows(42, 19, { earlier: false, later: false })).toEqual([
      { kind: "earlier", count: 19, from: 0, to: 18 },
      { kind: "stop", index: 19 },
      { kind: "stop", index: 20 },
      { kind: "stop", index: 21 },
      { kind: "stop", index: 22 },
      { kind: "stop", index: 23 },
      { kind: "more", count: 17, from: 24, to: 40 },
      { kind: "stop", index: 41 },
    ]);
  });
  it("opens a fold when asked; at the start nothing is folded before", () => {
    const rows = stopRows(42, 19, { earlier: true, later: true });
    expect(rows).toHaveLength(42);
    expect(rows.every((row) => row.kind === "stop")).toBe(true);
    expect(stopRows(6, 0, { earlier: false, later: false }).map((row) => row.kind)).toEqual(["stop", "stop", "stop", "stop", "stop", "stop"]);
    expect(stopRows(3, 2, { earlier: false, later: false })).toEqual([{ kind: "earlier", count: 2, from: 0, to: 1 }, { kind: "stop", index: 2 }]);
  });
});

describe("rideRows", () => {
  it("from the board stop to the exit, one greyed stop after it, the rest folded (board 5)", () => {
    expect(rideRows(42, 19, 23)).toEqual([
      { kind: "stop", index: 19, role: "board" },
      { kind: "stop", index: 20, role: "between" },
      { kind: "stop", index: 21, role: "between" },
      { kind: "stop", index: 22, role: "between" },
      { kind: "stop", index: 23, role: "alight" },
      { kind: "stop", index: 24, role: "after" },
      { kind: "more", count: 17 },
    ]);
    expect(rideRows(42, 19, 23, true).filter((row) => row.kind === "stop")).toHaveLength(23);
    expect(rideRows(5, 1, null).map((row) => (row.kind === "stop" ? row.role : row.kind))).toEqual(["board", "between", "between", "between"]);
  });
});

const departure = (minutes: number, tripRef = `t${minutes}`, routeId = "r1"): DeparturesPage["data"][number] => ({
  scheduledDeparture: new Date(Date.UTC(2026, 10, 14, 16, minutes)).toISOString(),
  stopId: "s19",
  routeId,
  routeShortName: "8",
  headsign: null,
  platformCode: null,
  pickupType: 0,
  tripRef,
  callSequence: 20,
});

describe("departures and headway", () => {
  it("keeps the direction's departures from now on, soonest first, once each", () => {
    const now = new Date(Date.UTC(2026, 10, 14, 16, 5));
    const list = lineDepartures([departure(30), departure(2), departure(18), departure(18), departure(9, "x", "r2")], "r1", now);
    expect(list.map((item) => item.tripRef)).toEqual(["t18", "t30"]);
  });
  it("is the median gap in minutes; unknown with fewer than three departures", () => {
    expect(headwayMinutes([departure(0), departure(12), departure(24), departure(40)])).toBe(12);
    expect(headwayMinutes([departure(0), departure(12)])).toBeNull();
  });
});

describe("stopTimes", () => {
  it("matches the trip's calls to the pattern by stop, in order", () => {
    const trip = {
      calls: [
        { callSequence: 1, stopId: "s0", scheduledArrival: null, scheduledDeparture: "2026-11-14T16:00:00Z" },
        { callSequence: 2, stopId: "s2", scheduledArrival: "2026-11-14T16:03:00Z", scheduledDeparture: "2026-11-14T16:03:00Z" },
        { callSequence: 3, stopId: "s3", scheduledArrival: "2026-11-14T16:05:00Z", scheduledDeparture: null },
      ],
    } as never;
    expect(stopTimes(stops.slice(0, 4), trip)).toEqual(["2026-11-14T16:00:00Z", null, "2026-11-14T16:03:00Z", "2026-11-14T16:05:00Z"]);
    expect(stopTimes(stops.slice(0, 2), null)).toEqual([null, null]);
  });
});

describe("railAt", () => {
  it("marks the stops within 200 m of a train or light-rail station", () => {
    const station = (id: string, latitude: number, mode: string) => ({ stopId: id, latitude, longitude: 34.78, mode }) as unknown as StopsPage["data"][number];
    const found = railAt(stops.slice(0, 5), [station("a", 32.0011, "rail"), station("b", 32.004, "light_rail"), station("c", 32.0, "bus")]);
    expect([...found.entries()]).toEqual([
      ["s0", "rail"],
      ["s1", "rail"],
      ["s2", "rail"],
      ["s3", "light_rail"],
      ["s4", "light_rail"],
    ]);
  });
});

it("walks about 75 m a minute, at least one", () => {
  expect(walkMinutes(120)).toBe(2);
  expect(walkMinutes(10)).toBe(1);
});
