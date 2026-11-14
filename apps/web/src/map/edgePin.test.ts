import { describe, expect, it } from "vitest";
import { edgePin, spreadPins } from "./edgePin";

// The visible map: 360 wide, the top band 60 px, the sheet over everything below 400.
const RECT = { left: 8, top: 68, right: 352, bottom: 392 };

describe("a tag pinned where its path leaves the map", () => {
  it("sits where the path crosses the side it leaves by", () => {
    // From the stop up and out of the top.
    expect(edgePin([{ x: 180, y: 300 }, { x: 180, y: 0 }], RECT)).toEqual({ x: 180, y: 68, side: "top" });
    // Out of the left side, through a bend.
    const left = edgePin([{ x: 180, y: 300 }, { x: 180, y: 200 }, { x: -100, y: 200 }], RECT)!;
    expect(left).toEqual({ x: 8, y: 200, side: "left" });
    // Diagonally out through the right side before the bottom.
    const right = edgePin([{ x: 300, y: 300 }, { x: 400, y: 380 }], RECT)!;
    expect(right.side).toBe("right");
    expect(right.x).toBe(352);
    expect(right.y).toBeCloseTo(341.6, 1);
  });

  it("sits at the path's end when it never leaves the map", () => {
    expect(edgePin([{ x: 180, y: 300 }, { x: 200, y: 250 }], RECT)).toEqual({ x: 200, y: 250, side: null });
  });

  it("is hidden while the stop is out of view (panned away, or under the sheet)", () => {
    expect(edgePin([{ x: 180, y: 500 }, { x: 180, y: 100 }], RECT)).toBeNull();
    expect(edgePin([{ x: 180, y: 300 }], RECT)).toBeNull();
  });

  it("moves a later tag on the same side inward when it would cover an earlier one", () => {
    const [a, b, c] = spreadPins([
      { x: 180, y: 68, side: "top" },
      { x: 230, y: 68, side: "top" },
      { x: 8, y: 200, side: "left" },
    ]);
    expect(a).toEqual({ x: 180, y: 68, side: "top" });
    expect(b).toEqual({ x: 230, y: 104, side: "top" });
    expect(c).toEqual({ x: 8, y: 200, side: "left" });
    expect(spreadPins([null])).toEqual([null]);
  });
});
