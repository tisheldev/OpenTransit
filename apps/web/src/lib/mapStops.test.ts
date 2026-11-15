import { describe, expect, it } from "vitest";
import { homeOtherStops } from "./mapStops";

describe("homeOtherStops", () => {
  it("draws only the listed stops by default (user, 15 November 2026)", () => {
    expect(homeOtherStops(undefined)).toBe("hidden");
    expect(homeOtherStops("")).toBe("hidden");
    expect(homeOtherStops("0")).toBe("hidden");
  });

  it("brings back the small dots with VITE_MAP_STOP_DOTS=1", () => {
    expect(homeOtherStops("1")).toBe("dots");
  });
});
