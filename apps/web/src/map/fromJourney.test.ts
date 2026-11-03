import { describe, expect, it } from "vitest";
import { fixture } from "../api/fixtures";
import type { Journey, JourneyResponse, Leg } from "../api/types";
import { journeyToScene, legLabel } from "./fromJourney";
import { routeFeatures } from "./layers";

function journeys(name: string): Journey[] {
  return (fixture(name).body as JourneyResponse).data.journeys;
}

const routes = journeys("recorded-journey-routes")[0]!;
const poi = journeys("recorded-journey-poi")[0]!;

describe("journeyToScene", () => {
  it("keeps every leg, in order, with [lon, lat] geometry", () => {
    const { route } = journeyToScene(routes);
    expect(route.map((leg) => `${leg.kind}:${leg.mode}`)).toEqual([
      "transit:bus",
      "walk:walk",
      "transit:rail",
      "walk:walk",
      "transit:bus",
      "walk:walk",
    ]);
    const first = route[0]!;
    // Israel: longitude ~34-36, latitude ~29-34.
    expect(first.coordinates![0]![0]).toBeGreaterThan(34);
    expect(first.coordinates![0]![1]).toBeGreaterThan(31);
    expect(first.from).toEqual([routes.legs[0]!.from.longitude, routes.legs[0]!.from.latitude]);
  });

  it("labels buses by line number; rail by no label (never by the exit stop), never an empty label", () => {
    const { route } = journeyToScene(routes);
    expect(route[0]!.label).toBe("8");
    expect(routes.legs[2]!.transit!.routeShortName).toBe("");
    expect(route[2]!.label).toBeNull();
    expect(route[4]!.label).toBe("1");
    for (const leg of route.filter((l) => l.kind === "walk")) expect(leg.label).toBeNull();
    for (const leg of route) expect(leg.label).not.toBe("");
  });

  it("marks only the active leg", () => {
    const { route } = journeyToScene(routes, { activeLeg: 2 });
    expect(route.map((leg) => leg.active)).toEqual([false, false, true, false, false, false]);
    expect(journeyToScene(routes).route.every((leg) => !leg.active)).toBe(true);
  });

  it("pins origin, boarding stops and transfers, and destination", () => {
    const { pins } = journeyToScene(routes, { destinationLabel: "Technion" });
    expect(pins[0]).toMatchObject({ role: "origin", label: routes.legs[0]!.from.name });
    // The journey starts at the first stop: no separate boarding pin there.
    expect(pins.filter((pin) => pin.role === "stop")).toHaveLength(0);
    expect(pins.filter((pin) => pin.role === "transfer").map((pin) => pin.label)).toEqual([
      routes.legs[2]!.from.name,
      routes.legs[4]!.from.name,
    ]);
    expect(pins.at(-1)).toMatchObject({ role: "destination", label: "Technion" });
  });

  it("never shows the engine's START/END names", () => {
    expect(poi.legs[0]!.from.name).toBe("START");
    const unnamed = journeyToScene(poi).pins;
    expect(unnamed[0]!.label).toBe("");
    expect(unnamed.at(-1)!.label).toBe("");
    expect(unnamed.find((pin) => pin.role === "stop")?.label).toBe(poi.legs[1]!.from.name);
    const named = journeyToScene(poi, { originLabel: "Rothschild 1", destinationLabel: "Technion" }).pins;
    expect(named[0]!.label).toBe("Rothschild 1");
    expect(named.at(-1)!.label).toBe("Technion");
  });

  it("draws no line for a time-only walk (geometry null)", () => {
    const legs: Leg[] = routes.legs.map((leg, index) =>
      index === 1 ? { ...leg, geometry: null, distanceMeters: null, geometryUnavailableReason: "TRANSFER_STREET_PATH_UNAVAILABLE" } : leg,
    );
    const { route } = journeyToScene({ ...routes, legs });
    expect(route[1]!.coordinates).toBeNull();
    // Its ends are still known (for framing), but it adds no line feature.
    expect(route[1]!.from).toEqual([legs[1]!.from.longitude, legs[1]!.from.latitude]);
    const lines = routeFeatures(route).features;
    expect(lines).toHaveLength(5);
    expect(lines.filter((f) => f.properties.kind === "walk")).toHaveLength(2);
  });

  it("handles an empty journey", () => {
    expect(journeyToScene({ ...routes, legs: [] })).toEqual({ route: [], pins: [] });
  });
});

describe("legLabel", () => {
  it("falls back to no label when a rail leg has nothing to show", () => {
    const rail = routes.legs[2]!;
    expect(legLabel({ ...rail, to: { ...rail.to, name: "END" } })).toBeNull();
    expect(legLabel(routes.legs[1]!)).toBeNull();
  });
});
