import { describe, expect, it } from "vitest";
import { buildSteps } from "../../nav/steps";
import { recordedJourneys, recordedTrips } from "../../nav/testdata";
import { navScene } from "./navScene";

const labels = { origin: "Dizengoff Center", destination: "Technion" };

describe("navScene: you + the current leg", () => {
  const journey = recordedJourneys[2]!;
  const steps = buildSteps(journey, recordedTrips);

  it("a walk: only that leg, its end pin, and no stale user", () => {
    const scene = navScene(journey, steps[0]!, labels, null, "fit");
    expect(scene.route).toHaveLength(1);
    expect(scene.route[0]).toMatchObject({ kind: "walk", active: true });
    expect(scene.pins.map((pin) => pin.role)).toEqual(["origin", "stop"]);
    expect(scene.user).toBeNull();
    expect(scene.camera).toBe("fit");
    expect(scene.pick).toBe(false);
  });

  it("a ride: its line, the boarding pin, and an exit pin when none is there", () => {
    const scene = navScene(journey, steps[7]!, labels, null, "fit");
    expect(scene.route).toEqual([expect.objectContaining({ kind: "transit", label: "4", active: true })]);
    const exit = scene.pins.find((pin) => pin.id === "exit-7");
    expect(exit).toMatchObject({ role: "stop", label: "גרנד קניון/שמחה גולן" });
  });

  it("the passenger's fix is drawn with the camera asked for", () => {
    const fix = { latitude: 32.07, longitude: 34.78, accuracyMeters: 12, at: 0 };
    const scene = navScene(journey, steps[0]!, labels, fix, "keep");
    expect(scene.user).toEqual({ position: [34.78, 32.07], accuracyMeters: 12 });
    expect(scene.camera).toBe("keep");
  });

  it("arrive: the whole journey", () => {
    const scene = navScene(journey, steps.at(-1)!, labels, null, "fit");
    expect(scene.route).toHaveLength(journey.legs.length);
    expect(scene.pins.at(-1)).toMatchObject({ role: "destination", label: "Technion" });
  });
});
