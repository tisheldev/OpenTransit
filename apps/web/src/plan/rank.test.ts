import { describe, expect, it } from "vitest";
import type { Journey } from "../api/types";
import { isWalkOnly, rankLabels } from "./rank";

const ride = { kind: "transit" } as Journey["legs"][number];
const walk = { kind: "walk" } as Journey["legs"][number];

const j = (durationMin: number, transfers: number, walkingMin: number, legs = [walk, ride, walk]): Journey =>
  ({
    id: `${durationMin}-${transfers}-${walkingMin}`,
    durationSeconds: durationMin * 60,
    transfers,
    walkingSeconds: walkingMin * 60,
    legs,
  }) as Journey;

describe("rankLabels", () => {
  it("labels the first journey recommended and keeps the API's order and count", () => {
    const journeys = [j(60, 2, 10), j(70, 2, 10), j(80, 2, 10)];
    const labels = rankLabels(journeys);
    expect(labels).toHaveLength(3);
    expect(labels[0]).toBe("recommended");
    expect(journeys.map((x) => x.id)).toEqual(["60-2-10", "70-2-10", "80-2-10"]);
  });

  it("gives fastest to a later option strictly shorter than every option", () => {
    expect(rankLabels([j(60, 2, 10), j(50, 2, 10), j(70, 2, 10)])).toEqual(["recommended", "fastest", null]);
  });

  it("never captions an option fastest when the first is as fast or faster", () => {
    expect(rankLabels([j(50, 2, 10), j(55, 2, 10), j(70, 2, 10)])).toEqual(["recommended", null, null]);
    expect(rankLabels([j(50, 2, 10), j(50, 2, 10)])).toEqual(["recommended", null]);
  });

  it("gives no transfers to a strictly unique zero, fewer transfers to a strictly lowest count", () => {
    expect(rankLabels([j(60, 2, 10), j(70, 0, 10), j(80, 1, 10)])).toEqual(["recommended", "noTransfers", null]);
    expect(rankLabels([j(60, 3, 10), j(70, 1, 10), j(80, 2, 10)])).toEqual(["recommended", "fewerTransfers", null]);
  });

  it("gives less walking to a strictly lowest walking time", () => {
    expect(rankLabels([j(60, 2, 10), j(70, 2, 15), j(80, 2, 4)])).toEqual(["recommended", null, "lessWalking"]);
  });

  it("gives ties none", () => {
    expect(rankLabels([j(60, 2, 10), j(55, 1, 5), j(55, 1, 5)])).toEqual(["recommended", null, null]);
  });

  it("gives one label per option, preferring fastest, and each label once", () => {
    // Option 2 is fastest, fewest transfers and least walking: it keeps "fastest" only.
    expect(rankLabels([j(60, 2, 10), j(40, 0, 2), j(80, 3, 12)])).toEqual(["recommended", "fastest", null]);
    // Option 3 is fastest; option 2 has fewest transfers.
    expect(rankLabels([j(60, 2, 10), j(70, 1, 12), j(50, 2, 11)])).toEqual(["recommended", "fewerTransfers", "fastest"]);
  });

  it("handles one and zero options", () => {
    expect(rankLabels([j(60, 2, 10)])).toEqual(["recommended"]);
    expect(rankLabels([])).toEqual([]);
  });

  it("does not give a walk-only option a transfer label", () => {
    const walkOnly = j(20, 0, 20, [walk]);
    expect(isWalkOnly(walkOnly)).toBe(true);
    expect(rankLabels([j(60, 2, 10), walkOnly])).toEqual(["recommended", "fastest"]);
    expect(rankLabels([j(60, 2, 10), j(50, 2, 30, [walk, ride]), { ...walkOnly, durationSeconds: 7200 }])).toEqual([
      "recommended",
      "fastest",
      null,
    ]);
  });
});
