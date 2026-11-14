import { describe, expect, it } from "vitest";
import {
  compassOf,
  groupMarkers,
  MAX_TAGS,
  placeTags,
  preferredTagSide,
  sideFromBearing,
  sideFromStreets,
  signBox,
  snapDirection,
  tagBox,
  zoomLevel,
  ZOOM_SIGNS,
  ZOOM_STOPS,
  type Box,
  type GroupInput,
} from "./geometry";

describe("zoom levels", () => {
  it("stations only far out, grouped stops in between, every sign close up", () => {
    expect(zoomLevel(8)).toBe("stations");
    expect(zoomLevel(ZOOM_STOPS - 0.01)).toBe("stations");
    expect(zoomLevel(ZOOM_STOPS)).toBe("grouped");
    expect(zoomLevel(ZOOM_SIGNS - 0.01)).toBe("grouped");
    expect(zoomLevel(ZOOM_SIGNS)).toBe("signs");
    expect(zoomLevel(18)).toBe("signs");
  });

  it("Home's walking ring, framed on a phone (zoom 13.8 to 14.3), shows every stop as a sign (board 1)", () => {
    expect(zoomLevel(13.8)).toBe("signs");
    expect(zoomLevel(14.3)).toBe("signs");
  });
});

describe("pole side", () => {
  it("snaps to the nearest of up, down, left and right; an exact diagonal stands up or down", () => {
    expect(snapDirection(1, 0.2)).toBe("right");
    expect(snapDirection(-1, -0.9)).toBe("left");
    expect(snapDirection(0.3, -1)).toBe("up");
    expect(snapDirection(1, 1)).toBe("down");
    expect(snapDirection(0, 0)).toBeNull();
    expect(snapDirection(Number.NaN, 1)).toBeNull();
  });

  it("from the direction of travel: traffic keeps right, so the sign stands to the right of it", () => {
    // Northbound: the kerb is east of the road, the sign east of the kerb.
    expect(sideFromBearing(0)).toBe("right");
    expect(sideFromBearing(90)).toBe("down");
    expect(sideFromBearing(180)).toBe("left");
    expect(sideFromBearing(270)).toBe("up");
    // A diagonal street (board MarkerTuning): the pole still snaps straight.
    expect(sideFromBearing(70)).toBe("down");
    expect(sideFromBearing(250)).toBe("up");
    // A map rotated 90° clockwise turns the sign with it.
    expect(sideFromBearing(0, 90)).toBe("up");
  });

  it("without a direction there is no side: the sign is centred, never guessed", () => {
    expect(sideFromBearing(null)).toBeNull();
    expect(sideFromBearing(undefined)).toBeNull();
  });

  it("from the map's streets: away from the nearest street that runs along the direction of travel", () => {
    // An east-west street 8 m south of the stop: the sign stands north (up) of the kerb.
    const street = [
      { x: -50, y: -8 },
      { x: 50, y: -8 },
    ];
    expect(sideFromStreets([street], null)).toBe("up");
    // A north-south cross street 5 m west is nearer, but runs across a westbound stop's road.
    const cross = [
      { x: -5, y: -50 },
      { x: -5, y: 50 },
    ];
    expect(sideFromStreets([street, cross], 270)).toBe("up");
    // Without a direction the nearest street wins.
    expect(sideFromStreets([street, cross], null)).toBe("right");
  });

  it("from the map's streets: none when no street is near or the stop is on its centre line", () => {
    expect(sideFromStreets([], 90)).toBeNull();
    const far = [
      { x: -50, y: -60 },
      { x: 50, y: -60 },
    ];
    expect(sideFromStreets([far], null)).toBeNull();
    const through = [
      { x: -50, y: -0.5 },
      { x: 50, y: -0.5 },
    ];
    expect(sideFromStreets([through], null)).toBeNull();
  });
});

describe("marker boxes", () => {
  it("place the 20 px sign 12 px from its kerb on the pole's side (boards' .sg.d/.u/.l/.r)", () => {
    const kerb = { x: 100, y: 100 };
    expect(signBox(kerb, "up")).toEqual({ left: 90, right: 110, top: 68, bottom: 88 });
    expect(signBox(kerb, "down")).toEqual({ left: 90, right: 110, top: 112, bottom: 132 });
    expect(signBox(kerb, "left")).toEqual({ left: 68, right: 88, top: 90, bottom: 110 });
    expect(signBox(kerb, "right")).toEqual({ left: 112, right: 132, top: 90, bottom: 110 });
    expect(signBox(kerb, null)).toEqual({ left: 90, right: 110, top: 90, bottom: 110 });
    // The chosen sign is 28 px, its near edge still 12 px from the kerb (Main: .sg.on.d).
    expect(signBox(kerb, "up", 28)).toEqual({ left: 86, right: 114, top: 60, bottom: 88 });
  });
});

describe("grouping", () => {
  const at = (id: string, x: number, y: number, side: GroupInput["side"] = null): GroupInput => ({ id, at: { x, y }, side });

  it("neighbourhood zoom: squares that would touch merge into one count; others stay apart", () => {
    const { singles, groups } = groupMarkers([at("a", 100, 100), at("b", 108, 104), at("c", 300, 300)], "grouped");
    expect(singles.map((item) => item.id)).toEqual(["c"]);
    expect(groups).toHaveLength(1);
    expect(groups[0]!.ids).toEqual(["a", "b"]);
    expect(groups[0]!.at).toEqual({ x: 104, y: 102 });
  });

  it("a count is checked again: the circle it makes swallows a square it would cover", () => {
    // a and b touch; their 30 px circle at (100, 100) then covers c, 16 px away.
    const { singles, groups } = groupMarkers([at("a", 94, 100), at("b", 106, 100), at("c", 100, 116)], "grouped");
    expect(singles).toHaveLength(0);
    expect(groups[0]!.ids).toEqual(["a", "b", "c"]);
  });

  it("street zoom: stops facing each other across a street keep their own signs (only the dots meet)", () => {
    // Kerb dots 4 px apart, signs pointing away from each other.
    const { singles, groups } = groupMarkers([at("north", 100, 98, "up"), at("south", 100, 102, "down")], "signs");
    expect(groups).toHaveLength(0);
    expect(singles.map((item) => item.id)).toEqual(["north", "south"]);
  });

  it("street zoom: two signs that would still touch share one count standing above their kerb dots", () => {
    const { singles, groups } = groupMarkers([at("a", 100, 100, "up"), at("b", 110, 100, "up")], "signs");
    expect(singles).toHaveLength(0);
    expect(groups[0]).toMatchObject({ ids: ["a", "b"], at: { x: 105, y: 82 } });
    expect(groups[0]!.kerbs).toEqual([
      { x: 100, y: 100 },
      { x: 110, y: 100 },
    ]);
  });

  it("a sign never covers another stop's kerb dot", () => {
    // b's dot is under a's sign (a's sign spans y 68–88 above its kerb at y 100).
    const { groups } = groupMarkers([at("a", 100, 100, "up"), at("b", 100, 80, "left")], "signs");
    expect(groups).toHaveLength(1);
  });
});

describe("next-line tags", () => {
  const visible: Box = { left: 0, top: 0, right: 390, bottom: 400 };
  const sign = signBox({ x: 200, y: 200 }, "up");

  it("run away from the road; with the road above or below, toward the reading end", () => {
    expect(preferredTagSide("left", "rtl")).toBe("left");
    expect(preferredTagSide("right", "rtl")).toBe("right");
    expect(preferredTagSide("up", "rtl")).toBe("left");
    expect(preferredTagSide("down", "ltr")).toBe("right");
    expect(preferredTagSide(null, "rtl")).toBe("left");
  });

  it("hang from the sign at its height, tucked 5 px behind it (boards Main and MapClose)", () => {
    expect(tagBox(sign, 80, "left")).toEqual({ left: 115, right: 195, top: sign.top, bottom: sign.bottom });
    expect(tagBox(sign, 80, "right")).toEqual({ left: 205, right: 285, top: sign.top, bottom: sign.bottom });
  });

  it("flip to the other side rather than cover a stop, and are left out when neither side is free", () => {
    const blockLeft = { id: "other", box: { left: 130, right: 150, top: 170, bottom: 190 } };
    expect(placeTags([{ id: "a", sign, side: "up", width: 80 }], [blockLeft], visible, "rtl")).toEqual([
      { id: "a", box: tagBox(sign, 80, "right"), toward: "right" },
    ]);
    const blockRight = { id: "third", box: { left: 250, right: 270, top: 170, bottom: 190 } };
    expect(placeTags([{ id: "a", sign, side: "up", width: 80 }], [blockLeft, blockRight], visible, "rtl")).toEqual([]);
  });

  it("never leave the visible map (the sheet's edge included)", () => {
    const nearEdge = signBox({ x: 30, y: 200 }, "up");
    expect(placeTags([{ id: "a", sign: nearEdge, side: "up", width: 80 }], [], visible, "rtl")).toEqual([
      { id: "a", box: tagBox(nearEdge, 80, "right"), toward: "right" },
    ]);
    const underSheet = signBox({ x: 200, y: 410 }, "down");
    expect(placeTags([{ id: "a", sign: underSheet, side: "down", width: 80 }], [], visible, "rtl")).toEqual([]);
  });

  it("show on a couple of stops at most, the first asked (the chosen stop's) first, and never on each other", () => {
    const signs = [0, 1, 2].map((i) => signBox({ x: 200, y: 100 + i * 100 }, "up"));
    const placed = placeTags(
      signs.map((box, i) => ({ id: `s${i}`, sign: box, side: "up" as const, width: 60 })),
      [],
      visible,
      "rtl",
    );
    expect(placed.map((tag) => tag.id)).toEqual(["s0", "s1"]);
    expect(placed).toHaveLength(MAX_TAGS);
    // Two signs side by side: the second tag cannot take the first one's place.
    const left = signBox({ x: 150, y: 200 }, "up");
    const right = signBox({ x: 200, y: 200 }, "up");
    const both = placeTags(
      [
        { id: "a", sign: right, side: "left", width: 40 },
        { id: "b", sign: left, side: "right", width: 40 },
      ],
      [],
      visible,
      "rtl",
    );
    expect(both.map((tag) => [tag.id, tag.toward])).toEqual([
      ["a", "left"],
      ["b", "left"],
    ]);
  });
});

describe("direction words", () => {
  it("name the direction of travel in four words (board 9)", () => {
    expect(compassOf(10)).toBe("north");
    expect(compassOf(350)).toBe("north");
    expect(compassOf(90)).toBe("east");
    expect(compassOf(181)).toBe("south");
    expect(compassOf(260)).toBe("west");
    expect(compassOf(null)).toBeNull();
  });
});
