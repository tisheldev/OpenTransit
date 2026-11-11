import { describe, expect, it } from "vitest";
import { pointAlongLine } from "../../nav/geo";
import { buildSteps } from "../../nav/steps";
import { callPositionsFor, recordedJourneys, recordedTrips } from "../../nav/testdata";
import { derivedWalkJourney } from "../../mocks/navigateMissed";
import { missedScene, navScene, type NavSceneInput } from "./navScene";

const labels = { origin: "Dizengoff Center", destination: "Technion" };
const words = { badge: "249", countdown: "4 דק׳", exitHere: "יורדים כאן" };

describe("navScene (boards 4–5)", () => {
  const journey = recordedJourneys[2]!;
  const steps = buildSteps(journey, recordedTrips);
  const input = (index: number, extra: Partial<NavSceneInput> = {}): NavSceneInput => ({
    journey,
    steps,
    step: steps[index]!,
    waiting: false,
    labels,
    fix: null,
    words,
    ...extra,
  });

  it("walking without a fix: the walk and the ride ahead, the stop as a large pin with its tag, framed", () => {
    const scene = navScene(input(0));
    expect(scene.route.map((leg) => [leg.kind, leg.tone])).toEqual([
      ["walk", "normal"],
      ["transit", "normal"],
    ]);
    expect(scene.stopPins).toEqual([expect.objectContaining({ id: "board", selected: true, ariaLabel: "דיזנגוף סנטר/טשרניחובסקי" })]);
    expect(scene.tags).toEqual([expect.objectContaining({ kind: "strong", text: "4 דק׳", line: expect.objectContaining({ label: "249", mode: "bus" }) })]);
    expect(scene.camera).toBe("fit");
    expect(scene.fitTo).toHaveLength(2);
    expect(scene.user).toBeNull();
    // Nothing is "active": every leg keeps its own tone (no dimming by another).
    expect(scene.route.some((leg) => leg.active)).toBe(false);
  });

  it("walking with a fix: the map follows, the part walked is dimmer", () => {
    const line = journey.legs[0]!.geometry!.coordinates;
    const middle = pointAlongLine(line, 80)!;
    const scene = navScene(input(0, { fix: { ...middle, accuracyMeters: 8, at: 0 } }));
    expect(scene.camera).toBe("follow");
    expect(scene.fitTo).toBeNull();
    expect(scene.route.map((leg) => [leg.kind, leg.tone])).toEqual([
      ["walk", "faded"],
      ["walk", "normal"],
      ["transit", "normal"],
    ]);
    expect(scene.user?.position).toEqual([middle.longitude, middle.latitude]);
  });

  it("on board: the travelled part grey, the next leg drawn, rings on the stops, 'יורדים כאן' at the exit, framed on what is left", () => {
    const steps0 = buildSteps(recordedJourneys[0]!, recordedTrips);
    const positions = callPositionsFor(steps0, "two_before_exit")[2]!;
    const line = recordedJourneys[0]!.legs[2]!.geometry!.coordinates;
    const halfway = pointAlongLine(line, 30_000)!;
    const scene = navScene({
      journey: recordedJourneys[0]!,
      steps: steps0,
      step: steps0[2]!,
      waiting: false,
      labels,
      fix: { ...halfway, accuracyMeters: 10, at: 0 },
      callPositions: positions,
      words,
    });
    expect(scene.route.map((leg) => [leg.mode.toLowerCase(), leg.tone])).toEqual([
      ["rail", "travelled"],
      ["rail", "normal"],
      ["walk", "normal"],
      ["bus", "normal"],
    ]);
    expect(scene.tags).toEqual([expect.objectContaining({ id: "exit", kind: "strong", text: "יורדים כאן" })]);
    expect(scene.pins.filter((pin) => pin.id.startsWith("call-"))).toHaveLength(positions.length);
    expect(scene.pins.find((pin) => pin.id === "exit")).toMatchObject({ role: "stop", label: "חוף הכרמל" });
    expect(scene.camera).toBe("fit");
    // The frame is what is left (to the exit) and the passenger, not the boarding stop.
    const boarding = [steps0[2]!.from!.longitude, steps0[2]!.from!.latitude];
    expect(scene.fitTo).not.toContainEqual(boarding);
    expect(scene.fitTo).toContainEqual([halfway.longitude, halfway.latitude]);
  });

  it("a ride waiting at its stop is drawn as board 4 (the stop pin and its countdown)", () => {
    const steps0 = buildSteps(recordedJourneys[0]!, recordedTrips);
    const scene = navScene({ journey: recordedJourneys[0]!, steps: steps0, step: steps0[0]!, waiting: true, labels, fix: null, words: { ...words, badge: "8" } });
    expect(scene.stopPins?.[0]).toMatchObject({ id: "board", selected: true });
    expect(scene.tags?.[0]).toMatchObject({ kind: "strong", line: expect.objectContaining({ label: "8" }) });
  });

  it("arrive: the whole journey", () => {
    const scene = navScene(input(steps.length - 1));
    expect(scene.route).toHaveLength(journey.legs.length);
    expect(scene.pins.at(-1)).toMatchObject({ role: "destination", label: "Technion" });
  });
});

describe("missedScene (board 6)", () => {
  const journey = recordedJourneys[2]!;
  const steps = buildSteps(journey, recordedTrips);
  const ride = steps[1]!;

  it("the missed line faded with its next departure; the other stop selected with its own; the walk to it labelled", () => {
    const other = derivedWalkJourney();
    const scene = missedScene({
      journey,
      ride,
      fix: null,
      badge: "249",
      waitText: "הבא 08:58",
      walk: { journey: other, badge: "8", departs: "08:45", walkText: "3 דק׳ הליכה" },
    });
    expect(scene.route[0]).toMatchObject({ kind: "transit", tone: "faded" });
    expect(scene.route.slice(1).map((leg) => [leg.kind, leg.tone])).toEqual([
      ["walk", "normal"],
      ["transit", "normal"],
    ]);
    expect(scene.stopPins?.map((pin) => [pin.id, pin.selected ?? false])).toEqual([
      ["missed", false],
      ["other", true],
    ]);
    expect(scene.tags?.map((tag) => [tag.id, tag.kind, tag.text])).toEqual([
      ["missed", "faded", "הבא 08:58"],
      ["other", "strong", "08:45"],
      ["walk", "faded", "3 דק׳ הליכה"],
    ]);
    expect(scene.camera).toBe("fit");
  });

  it("without another stop: the missed line and its stop only", () => {
    const scene = missedScene({ journey, ride, fix: null, badge: "249", waitText: null, walk: null });
    expect(scene.route).toHaveLength(1);
    expect(scene.stopPins).toHaveLength(1);
    expect(scene.tags?.[0]?.text).toBeUndefined();
  });
});
