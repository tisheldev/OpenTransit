import { describe, expect, it } from "vitest";
import type { Trip } from "../../api/schemas";
import type { LonLat } from "../../map/scene";
import { haversineMeters } from "../../nav/geo";
import {
  callPosition,
  callsAhead,
  directionMark,
  firstStretch,
  groupLines,
  lineOf,
  modeOfRouteType,
  routeAhead,
  shortHeadsign,
  type Departure,
} from "./lines";

const departure = (routeShortName: string, minutes: number, extra: Record<string, unknown> = {}): Departure => ({
  scheduledDeparture: new Date(Date.parse("2026-11-11T10:00:00Z") + minutes * 60_000).toISOString(),
  stopId: "mot:stop:1",
  routeId: `mot:route:${routeShortName}`,
  routeShortName,
  headsign: "תל אביב יפו_מסוף רדינג",
  platformCode: null,
  pickupType: 0,
  tripRef: `trip-${routeShortName}-${minutes}`,
  callSequence: 3,
  ...extra,
});

const route = (routeShortName: string, operatorId: string, routeType = 3) => ({
  routeId: `mot:route:${routeShortName}`,
  sourceId: routeShortName,
  operatorId,
  routeShortName,
  routeLongName: null,
  routeType,
  color: null,
  textColor: null,
});

const now = new Date("2026-11-11T10:00:00Z");

describe("the lines through a stop", () => {
  it("one row per line and direction, by its next departure; departures gone are dropped", () => {
    const lines = groupLines(
      [departure("5", 9), departure("61", 2), departure("5", 4), departure("61", 12, { headsign: "רמת אביב" }), departure("9", -3)],
      [],
      { trainLabel: "רכבת", now },
    );
    expect(lines.map((line) => [line.label, line.headsign, line.tripRef])).toEqual([
      ["61", "מסוף רדינג", "trip-61-2"],
      ["5", "מסוף רדינג", "trip-5-4"],
      ["61", "רמת אביב", "trip-61-12"],
    ]);
    expect(groupLines([departure("5", 1), departure("6", 2)], [], { trainLabel: "", now, max: 1 })).toHaveLength(1);
  });

  it("takes the operator and mode from the departure when the API sends them, else from the stop's routes", () => {
    expect(lineOf(departure("5", 1), [route("5", "5")], "רכבת")).toMatchObject({ mode: "BUS", operatorId: "5", operatorName: null });
    expect(lineOf(departure("5", 1, { operatorId: "3", operatorName: "אגד", mode: "BUS" }), [route("5", "5")], "רכבת")).toMatchObject({
      operatorId: "3",
      operatorName: "אגד",
    });
    // No route data at all: a neutral bus.
    expect(lineOf(departure("5", 1), [], "רכבת")).toMatchObject({ mode: "BUS", operatorId: null });
    // A train without a line number is badged with the train word, and its number is not a headsign.
    expect(lineOf(departure("", 1, { headsign: "156", routeId: "mot:route:r" }), [{ ...route("", "2", 2), routeId: "mot:route:r" }], "רכבת")).toMatchObject({
      mode: "RAIL",
      label: "רכבת",
      headsign: null,
    });
  });

  it("maps GTFS route types to modes", () => {
    expect([0, 1, 2, 3, 715, 900, 401, 109, null].map(modeOfRouteType)).toEqual([
      "TRAM",
      "SUBWAY",
      "RAIL",
      "BUS",
      "BUS",
      "TRAM",
      "SUBWAY",
      "RAIL",
      "BUS",
    ]);
  });

  it("names the place a line goes to without the GTFS city prefix", () => {
    expect(shortHeadsign("תל אביב יפו_מסוף רדינג")).toBe("מסוף רדינג");
    expect(shortHeadsign("נווה דן")).toBe("נווה דן");
    expect(shortHeadsign("156")).toBeNull();
    expect(shortHeadsign(null)).toBeNull();
  });
});

describe("a line's route out of the stop", () => {
  // A straight line north from the stop's south, then east.
  const shape: LonLat[] = [
    [34.78, 32.07],
    [34.78, 32.08],
    [34.79, 32.08],
  ];
  const stop = { latitude: 32.075, longitude: 34.7801 };

  it("starts where the stop meets the shape and follows it to the end", () => {
    const ahead = routeAhead({ type: "LineString", coordinates: shape }, stop)!;
    expect(ahead[0]![1]).toBeCloseTo(32.075, 5);
    expect(ahead.slice(1)).toEqual(shape.slice(1));
    expect(routeAhead(null, stop)).toBeNull();
    // A shape far from the stop is not this stop's pass.
    expect(routeAhead({ type: "LineString", coordinates: shape }, { latitude: 32.2, longitude: 34.9 })).toBeNull();
  });

  it("fans out its first stretch only", () => {
    const fan = firstStretch(routeAhead({ type: "LineString", coordinates: shape }, stop)!, 300);
    let length = 0;
    for (let i = 1; i < fan.length; i += 1) {
      length += haversineMeters({ latitude: fan[i - 1]![1], longitude: fan[i - 1]![0] }, { latitude: fan[i]![1], longitude: fan[i]![0] });
    }
    expect(length).toBeCloseTo(300, 0);
  });

  it("points its direction arrow the way the line goes", () => {
    expect(directionMark(shape)?.arrow).toBe("↑");
    expect(directionMark([...shape].reverse().slice(0, 2))?.arrow).toBe("←");
    expect(directionMark([[34.78, 32.07]])).toBeNull();
  });

  it("rings the stops after the stop's own call, with their own coordinates when the trip has them", () => {
    const calls = [1, 2, 3, 4, 5].map((callSequence) => ({
      callSequence,
      ordinal: callSequence - 1,
      stopId: `s${callSequence}`,
      scheduledArrival: null,
      scheduledDeparture: null,
      pickupType: 0,
      dropOffType: 0,
      ...(callSequence === 4 ? { latitude: 32.1, longitude: 34.8 } : {}),
    }));
    const trip = { calls } as unknown as Trip["data"];
    const ahead = callsAhead(trip, 2, 2);
    expect(ahead.map((call) => call.stopId)).toEqual(["s3", "s4"]);
    expect(ahead.map(callPosition)).toEqual([null, [34.8, 32.1]]);
  });
});
