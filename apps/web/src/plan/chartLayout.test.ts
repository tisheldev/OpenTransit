import { describe, expect, it } from "vitest";
import type { Journey, Leg } from "../api/types";
import { derivedJourneyFixtures } from "../screens/compare/derivedFixtures";
import { isRail, layoutChart, lineLabel, MIN_LABEL_FRACTION, physicalLeft } from "./chartLayout";

const three = () => (derivedJourneyFixtures["derived-journey-three"]().body as { data: { journeys: Journey[] } }).data.journeys;

const leg = (kind: "walk" | "transit", from: string, to: string, extra: Partial<Leg> = {}): Leg =>
  ({
    kind,
    mode: kind === "walk" ? "walk" : "bus",
    timing: { scheduledDeparture: `2026-11-02T${from}:00+02:00`, scheduledArrival: `2026-11-02T${to}:00+02:00` },
    transit: kind === "transit" ? { routeShortName: "8" } : null,
    ...extra,
  }) as Leg;

const journey = (legs: Leg[]): Journey =>
  ({
    id: legs.map((l) => l.timing.scheduledDeparture).join(),
    timing: { scheduledDeparture: legs[0]!.timing.scheduledDeparture, scheduledArrival: legs.at(-1)!.timing.scheduledArrival },
    durationSeconds: (Date.parse(legs.at(-1)!.timing.scheduledArrival) - Date.parse(legs[0]!.timing.scheduledDeparture)) / 1000,
    transfers: 0,
    legs,
  }) as Journey;

describe("layoutChart", () => {
  it("puts every option on one axis from the earliest departure to the latest arrival", () => {
    const journeys = three();
    const layout = layoutChart(journeys, "he")!;
    expect(layout.axisStart).toBe(new Date("2026-10-01T08:07:00+03:00").toISOString());
    expect(layout.axisEnd).toBe(new Date("2026-10-01T10:32:00+03:00").toISOString());
    expect(layout.rows.map((row) => row.journeyId)).toEqual(journeys.map((j) => j.id));
    expect(layout.rows[0]!.segments[0]!.start).toBe(0);
    const lastRow = layout.rows[2]!;
    const lastSegment = lastRow.segments.at(-1)!;
    expect(lastSegment.start + lastSegment.width).toBeCloseTo(1);
  });

  it("lays out one, two or three rows (rows collapse)", () => {
    const journeys = three();
    for (const count of [1, 2, 3]) expect(layoutChart(journeys.slice(0, count), "en")!.rows).toHaveLength(count);
    expect(layoutChart([], "en")).toBeNull();
  });

  it("marks walk, transit and wait segments; rail is a train, never an empty line label", () => {
    const row = layoutChart(three(), "he")!.rows[0]!;
    expect(row.segments.map((s) => s.kind)).toEqual(["transit", "wait", "walk", "transit", "walk", "wait", "transit", "walk"]);
    const rail = row.segments.find((s) => s.rail)!;
    expect(rail.label).toBe("rail");
    expect(row.segments[0]!.label).toBe("8");
    expect(row.segments.filter((s) => s.kind !== "transit").every((s) => s.label === null)).toBe(true);
  });

  it("shows a waiting gap between legs and hides labels too narrow to read", () => {
    const layout = layoutChart([journey([leg("walk", "08:00", "08:05"), leg("transit", "08:10", "09:00")])], "en")!;
    const [walkSeg, wait, ride] = layout.rows[0]!.segments;
    expect(wait!.kind).toBe("wait");
    expect(wait!.start).toBeCloseTo(walkSeg!.width);
    expect(wait!.width).toBeCloseTo(5 / 60);
    expect(ride!.showLabel).toBe(true);
    const narrow = layoutChart(
      [journey([leg("transit", "08:00", "08:02")]), journey([leg("walk", "08:00", "09:00")])],
      "en",
    )!.rows[0]!.segments[0]!;
    expect(narrow.width).toBeLessThan(MIN_LABEL_FRACTION);
    expect(narrow.showLabel).toBe(false);
  });

  it("names lines by their number and detects trains", () => {
    const rail = leg("transit", "08:00", "09:00", { mode: "rail", transit: { routeShortName: "" } as Leg["transit"] });
    expect(isRail(rail)).toBe(true);
    expect(lineLabel(rail)).toBeNull();
    expect(lineLabel(leg("transit", "08:00", "09:00"))).toBe("8");
  });

  it("puts the earliest time on the right in Hebrew and on the left in English", () => {
    const row = layoutChart(three(), "he")!.rows[0]!;
    const first = row.segments[0]!;
    const last = row.segments.at(-1)!;
    expect(physicalLeft(first.start, first.width, "ltr")).toBeLessThan(physicalLeft(last.start, last.width, "ltr"));
    expect(physicalLeft(first.start, first.width, "rtl")).toBeGreaterThan(physicalLeft(last.start, last.width, "rtl"));
    expect(physicalLeft(0, 0.25, "rtl")).toBeCloseTo(0.75);
  });

  it("labels round ticks in Israel time inside the axis", () => {
    const layout = layoutChart(three(), "en")!;
    expect(layout.ticks.map((tick) => tick.label)).toEqual(["09:00", "10:00"]);
    expect(layout.ticks.every((tick) => tick.fraction > 0 && tick.fraction < 1)).toBe(true);
  });
});
