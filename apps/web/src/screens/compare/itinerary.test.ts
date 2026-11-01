import { describe, expect, it } from "vitest";
import type { Journey, Leg } from "../../api/types";
import { derivedJourneyFixtures } from "./derivedFixtures";
import { buildItinerary, placesOf, sameStopTransfer } from "./itinerary";

const ends = { from: "דיזנגוף סנטר", to: "טכניון" };
const three = () => (derivedJourneyFixtures["derived-journey-three"]().body as { data: { journeys: Journey[] } }).data.journeys;
const walkOnly = () =>
  (derivedJourneyFixtures["derived-journey-walk-only"]().body as { data: { journeys: Journey[] } }).data.journeys[0]!;

const at = (hhmm: string) => `2026-11-02T${hhmm}:00+02:00`;
const leg = (kind: "walk" | "transit", from: string, to: string, dep: string, arr: string, extra: Partial<Leg> = {}): Leg =>
  ({
    kind,
    mode: kind === "walk" ? "walk" : "bus",
    from: { name: from, latitude: 32, longitude: 34.8, stopId: kind === "walk" ? null : `s:${from}` },
    to: { name: to, latitude: 32, longitude: 34.8, stopId: kind === "walk" ? null : `s:${to}` },
    timing: { scheduledDeparture: at(dep), scheduledArrival: at(arr) },
    durationSeconds: (Date.parse(at(arr)) - Date.parse(at(dep))) / 1000,
    distanceMeters: kind === "walk" ? 120 : null,
    transit: kind === "transit" ? { routeShortName: "26", headsign: "מזכרת בתיה", operatorName: "אגד", engineTripId: from } : null,
    ...extra,
  }) as Leg;
const journey = (legs: Leg[]) => ({ legs }) as Journey;

describe("buildItinerary", () => {
  it("lists places with their scheduled times between rides and walks, exit times included", () => {
    const items = buildItinerary(three()[0]!, ends);
    expect(items.map((item) => item.kind)).toEqual([
      "place", "ride", "place", "walk", "place", "ride", "place", "walk", "place", "ride", "place", "walk", "place",
    ]);
    const places = placesOf(items);
    expect(places.map((p) => [p.role, p.time.slice(11, 16), p.name])).toEqual([
      ["origin", "08:07", "דיזנגוף סנטר/דיזנגוף"],
      ["exit", "08:14", "ת. רכבת השלום"],
      ["board", "08:21", "השלום"],
      ["exit", "09:24", "חוף הכרמל"],
      ["board", "09:33", "ת. רכבת חוף הכרמל"],
      ["exit", "09:47", "טכניון/מעונות העמים"],
      // The engine's "END" is the passenger's own destination label.
      ["destination", "09:52", "טכניון"],
    ]);
    // Line continuity: what is drawn above and below each place.
    expect(places.map((p) => [p.above, p.below])).toEqual([
      [null, "bus"],
      ["bus", "walk"],
      ["walk", "rail"],
      ["rail", "walk"],
      ["walk", "bus"],
      ["bus", "walk"],
      ["walk", null],
    ]);
  });

  it("puts the wait before and after a transfer walk on the walk", () => {
    const walks = buildItinerary(three()[0]!, ends).filter((item) => item.kind === "walk");
    // Bus 8 arrives 08:14, the walk is 08:19–08:21, the train leaves 08:21: 5 min waiting.
    expect(walks[0]).toMatchObject({ seconds: 120, waitSeconds: 300, distanceMeters: 226, sameStop: false });
    // 09:24 → 09:26 walk, bus 1 at 09:33: 7 min.
    expect(walks[1]).toMatchObject({ seconds: 120, waitSeconds: 420 });
    expect(walks[2]).toMatchObject({ waitSeconds: 0 });
  });

  it("starts at the passenger's own label when the trip starts with a walk", () => {
    const places = placesOf(buildItinerary(three()[2]!, ends));
    expect(places[0]).toMatchObject({ role: "origin", name: "דיזנגוף סנטר" });
    expect(places.at(-1)).toMatchObject({ role: "destination", name: "טכניון" });
    expect(placesOf(buildItinerary(walkOnly(), ends)).map((p) => p.role)).toEqual(["origin", "destination"]);
  });

  it("reads a 0 m walk between stops of the same name as a change at the same stop", () => {
    const legs = [
      leg("transit", "A", "הרצל/צומת בילו", "18:22", "19:12"),
      leg("walk", "הרצל/צומת בילו", "הרצל/צומת בילו", "19:12", "19:14", { distanceMeters: 0 }),
      leg("transit", "הרצל/צומת בילו", "B", "19:18", "19:39"),
    ];
    expect(sameStopTransfer(legs[1]!)).toBe(true);
    expect(sameStopTransfer({ ...legs[1]!, distanceMeters: 228 })).toBe(false);
    const walk = buildItinerary(journey(legs), ends).find((item) => item.kind === "walk");
    expect(walk).toMatchObject({ sameStop: true, seconds: 120, waitSeconds: 240 });
  });

  it("waits at the stop between two rides with no walk, then boards", () => {
    const legs = [leg("transit", "A", "B", "08:00", "08:20"), leg("transit", "B", "C", "08:26", "08:50")];
    const items = buildItinerary(journey(legs), ends);
    expect(items.map((item) => item.kind)).toEqual(["place", "ride", "place", "wait", "place", "ride", "place"]);
    expect(items[3]).toEqual({ kind: "wait", seconds: 360 });
    expect(placesOf(items).map((p) => p.role)).toEqual(["origin", "exit", "board", "destination"]);
  });

  it("shows a platform only where the API gives one", () => {
    const legs = [leg("transit", "A", "B", "08:00", "08:20", { from: { name: "A", latitude: 32, longitude: 34.8, stopId: "s:A", stopCode: null, platformCode: "3" } as Leg["from"] })];
    expect(placesOf(buildItinerary(journey(legs), ends))[0]!.platform).toBe("3");
    expect(placesOf(buildItinerary(three()[0]!, ends)).every((p) => p.platform === null)).toBe(true);
  });
});
