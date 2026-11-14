import { describe, expect, it } from "vitest";
import { derivedNearbyDepartures } from "../../mocks/stopFixtures";
import type { NearbyDepartures } from "../../api/schemas";
import type { NearStopDepartures } from "./homeStops";
import { lineIdentity, nearLines, walkMinutes } from "./nearLines";
import { savedLineDepartures, savedLineNext } from "./savedDepartures";

// "Near you" (board 1): each line once, at the stop where it leaves first, with the walk.

const FROM = "2026-11-14T10:00:00+02:00";
const now = new Date(Date.parse(FROM));
const centre = { latitude: 32.0753, longitude: 34.7749 };

function entries(): NearStopDepartures[] {
  const body = derivedNearbyDepartures(FROM).body as NearbyDepartures;
  return body.data.map((entry) => ({ stop: entry.stop, departures: entry.departures, routes: [] }));
}

describe("nearLines()", () => {
  it("lists each line once, where it leaves first, earliest first, naming the stop and the walk", () => {
    const rows = nearLines(entries(), centre, { trainLabel: "רכבת", now, max: 20 });
    const labels = rows.map((row) => row.line.label);
    expect(new Set(labels).size).toBe(labels.length);
    // Line 8 runs from 13583 (9 min, to the university) and 13561 (5 min, to Pilots' terminal).
    const eight = rows.find((row) => row.line.label === "8")!;
    expect([eight.stop.stopId, eight.line.headsign, eight.walkMinutes]).toEqual(["mot:stop:13561", "מסוף הטייסים", 2]);
    const times = rows.map((row) => Date.parse(row.line.next));
    expect([...times].sort((a, b) => a - b)).toEqual(times);
    expect(rows[0]!.stopName).toBe("דיזנגוף סנטר/דיזנגוף");
  });

  it("keeps six rows by default and drops departures already gone", () => {
    expect(nearLines(entries(), centre, { trainLabel: "רכבת", now })).toHaveLength(6);
    const later = new Date(now.getTime() + 6 * 60_000);
    expect(nearLines(entries(), centre, { trainLabel: "רכבת", now: later, max: 20 }).every((row) => Date.parse(row.line.next) >= later.getTime() - 30_000)).toBe(true);
  });

  it("takes the walk from the API's distance, else a straight line from the centre", () => {
    const withoutDistance = entries().map((entry) => ({ ...entry, stop: { ...entry.stop, distanceMeters: undefined } as typeof entry.stop }));
    const far = { latitude: 32.0753, longitude: 34.7712 };
    const eight = nearLines(withoutDistance, far, { trainLabel: "רכבת", now, max: 20 }).find((row) => row.line.label === "8")!;
    expect(eight.walkMinutes).toBe(5);
  });

  it("names a walk in whole minutes at 80 m a minute, at least one", () => {
    expect([walkMinutes(0), walkMinutes(80), walkMinutes(81), walkMinutes(400)]).toEqual([1, 1, 2, 5]);
    expect(lineIdentity({ operatorId: "5", operatorName: "דן", mode: "BUS", label: "8" })).not.toBe(
      lineIdentity({ operatorId: "3", operatorName: "אגד", mode: "BUS", label: "8" }),
    );
  });
});

describe("a saved line's next departure", () => {
  const departures = entries()[1]!.departures!;
  const saved = {
    lineKey: "5:10008",
    shortName: "8",
    operatorId: "5",
    operatorName: "דן",
    mode: "bus",
    destinationName: "מסוף הטייסים",
    originName: null,
    routeIdHint: null,
    area: null,
    stopId: "mot:stop:13561",
    stopName: "דיזנגוף סנטר",
    savedAt: FROM,
  };

  it("matches the number, the operator and the direction saved", () => {
    expect(savedLineDepartures(saved, departures).map((item) => item.headsign)).toEqual(["מסוף הטייסים"]);
    expect(savedLineNext(saved, { departures, routes: [] }, now, "רכבת")?.label).toBe("8");
    expect(savedLineDepartures({ ...saved, operatorId: "3" }, departures)).toEqual([]);
    expect(savedLineDepartures({ ...saved, destinationName: "אוניברסיטת ת\"א" }, departures)).toEqual([]);
    expect(savedLineNext(saved, undefined, now, "רכבת")).toBeNull();
  });
});
