import { describe, expect, it } from "vitest";
import { fixture } from "../api/fixtures";
import type { JourneyResponse } from "../api/types";
import { buildSteps } from "./steps";
import { recordedJourneys, recordedTrips } from "./testdata";

const fixtureJourneys = ["recorded-journey-routes", "recorded-journey-poi"].flatMap(
  (name) => (fixture(name).body as JourneyResponse).data.journeys,
);
const all = [...fixtureJourneys, ...recordedJourneys];

describe("buildSteps", () => {
  it.each(all.map((journey) => [journey.id, journey] as const))("maps legs one-to-one, then arrive (%s)", (_id, journey) => {
    const steps = buildSteps(journey, recordedTrips);
    expect(steps).toHaveLength(journey.legs.length + 1);
    steps.forEach((step, index) => expect(step.index).toBe(index));
    expect(steps.at(-1)!.kind).toBe("arrive");
    expect(steps.at(-1)!.legIndex).toBeNull();
    expect(steps.at(-1)!.scheduledArrival).toBe(journey.timing.scheduledArrival);
    journey.legs.forEach((leg, index) => {
      const step = steps[index]!;
      expect(step.legIndex).toBe(index);
      expect(step.kind === "ride").toBe(leg.kind === "transit");
      expect(step.target.name).toBe(leg.to.name);
      expect(step.distanceMeters).toBe(leg.distanceMeters);
      if (step.ride) expect(step.ride.tripRef).toBe(leg.transit!.engineTripId);
    });
  });

  it("names walk kinds by position", () => {
    const kinds = buildSteps(recordedJourneys[2]!).map((step) => step.kind);
    expect(kinds).toEqual([
      "walk_to_stop",
      "ride",
      "transfer_walk",
      "ride",
      "transfer_walk",
      "ride",
      "transfer_walk",
      "ride",
      "transfer_walk",
      "ride",
      "walk_to_destination",
      "arrive",
    ]);
  });

  it("starts with the ride when the origin is the stop", () => {
    const steps = buildSteps(recordedJourneys[0]!);
    expect(steps.map((step) => step.kind)).toEqual(["ride", "transfer_walk", "ride", "transfer_walk", "ride", "walk_to_destination", "arrive"]);
    expect(steps[0]!.from!.stopId).toBe("mot:stop:13561");
  });

  it("keeps a time-only transfer walk without inventing a distance", () => {
    const steps = buildSteps(recordedJourneys[1]!, recordedTrips);
    const walk = steps[3]!;
    expect(walk.kind).toBe("transfer_walk");
    expect(walk.distanceMeters).toBeNull();
    expect(walk.hasGeometry).toBe(false);
    expect(walk.durationSeconds).toBe(240);
    expect(walk.scheduledDeparture).toBe("2026-11-02T09:52:00+02:00");
    expect(walk.target.stopId).toBe("mot:stop:2410");
  });

  it("matches boarding and exit calls and counts stops", () => {
    const steps = buildSteps(recordedJourneys[0]!, recordedTrips);
    expect(steps[0]!.ride).toMatchObject({ lineLabel: "8", boardOrdinal: 17, exitOrdinal: 21, stopCount: 4, mode: "bus" });
    expect(steps[4]!.ride).toMatchObject({ lineLabel: "1", boardOrdinal: 1, exitOrdinal: 10, stopCount: 9 });
  });

  it("labels a train by destination, not an empty line name", () => {
    const rail = buildSteps(recordedJourneys[0]!, recordedTrips)[2]!.ride!;
    expect(rail.mode).toBe("rail");
    expect(rail.lineLabel).toBeNull();
    expect(rail.routeShortName).toBe("");
    expect(rail.headsign).toBe("156");
    expect(rail.destinationName).toBe("חוף הכרמל");
    expect(rail.operatorName).not.toBe("");
    expect(rail.stopCount).toBe(5);
  });

  it("carries a platform only when the leg has one (API-C2), never guessed", () => {
    const journey = recordedJourneys[0]!;
    expect(buildSteps(journey, recordedTrips).flatMap((step) => (step.ride ? [step.ride.platform] : []))).toEqual([null, null, null]);
    const withPlatform = structuredClone(journey);
    Object.assign(withPlatform.legs[2]!.from, { platformCode: " 3 " });
    Object.assign(withPlatform.legs[0]!.from, { platformCode: "" });
    const steps = buildSteps(withPlatform, recordedTrips);
    expect(steps[2]!.ride!.platform).toBe("3");
    expect(steps[0]!.ride!.platform).toBeNull();
  });

  it("leaves ride ordinals null without trip detail and breaks nothing else", () => {
    const steps = buildSteps(recordedJourneys[0]!, {});
    expect(steps[0]!.ride).toMatchObject({ boardOrdinal: null, exitOrdinal: null, stopCount: null, lineLabel: "8" });
    // A trip that does not contain the leg's stops also gives nulls.
    const other = buildSteps(recordedJourneys[0]!, { [recordedJourneys[0]!.legs[0]!.transit!.engineTripId]: recordedTrips[recordedJourneys[0]!.legs[2]!.transit!.engineTripId]! });
    expect(other[0]!.ride!.stopCount).toBeNull();
  });

  it("matches an exit at the same stop by time on a loop (exit after board)", () => {
    const journey = recordedJourneys[0]!;
    const tripRef = journey.legs[0]!.transit!.engineTripId;
    const trip = recordedTrips[tripRef]!;
    const steps = buildSteps(journey, { [tripRef]: { ...trip, calls: [...trip.calls].reverse() } });
    expect(steps[0]!.ride!.stopCount).toBe(4);
  });
});
