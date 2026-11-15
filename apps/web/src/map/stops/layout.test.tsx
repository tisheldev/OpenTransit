import type { Map as MapLibreMap } from "maplibre-gl";
import { describe, expect, it } from "vitest";
import type { AreaStop } from "./area";
import { layoutStops } from "./StopsLayer";

// Neighbourhood zoom on real data was "way too bloated" (user, 15 November 2026): below
// street zoom only the featured stops (Home: the ones its sheet lists) are signs; the rest
// are small dots, or none when the passenger chose "only the listed stops".

const stop = (stopId: string, x: number, y: number): AreaStop => ({
  stopId,
  name: stopId,
  code: null,
  // One unit of longitude or latitude is a pixel on the fake map below.
  longitude: x,
  latitude: y,
  mode: "bus",
  bearingDegrees: null,
  parentStationId: null,
  locationType: 0,
});

const map = { project: ([x, y]: [number, number]) => ({ x, y }), getBearing: () => 0 } as unknown as MapLibreMap;
const view = { zoom: 14, bounds: { west: 0, east: 400, south: 0, north: 800 }, center: [200, 400] as [number, number], width: 400, height: 800, visible: { left: 0, top: 0, right: 400, bottom: 800 } };
const stops = [stop("listed", 100, 100), stop("near", 300, 100), stop("far", 100, 400), stop("chosen", 300, 400)];
const kinds = (layout: ReturnType<typeof layoutStops>) => Object.fromEntries(layout.items.map((item) => [item.kind === "group" ? item.key : item.id, item.kind]));

describe("the stops layer below street zoom", () => {
  it("draws featured stops and the chosen one as signs, every other stop as a dot", () => {
    const layout = layoutStops(map, view, "grouped", stops, [], "chosen", "rtl", new Set(["listed"]), true);
    expect(kinds(layout)).toEqual({ listed: "sign", near: "square", far: "square", chosen: "sign" });
    // A dot is the small muted one (6 px), not the old 12 px square.
    const dot = layout.items.find((item) => item.kind === "square")!;
    expect(dot.box.right - dot.box.left).toBe(6);
  });

  it("draws no other stops when the passenger chose only the listed ones", () => {
    const layout = layoutStops(map, view, "grouped", stops, [], "chosen", "rtl", new Set(["listed"]), false);
    expect(kinds(layout)).toEqual({ listed: "sign", chosen: "sign" });
  });

  it("leaves out a dot a sign would cover", () => {
    const under = stop("under", 102, 92);
    const layout = layoutStops(map, view, "grouped", [...stops, under], [], null, "rtl", new Set(["listed"]), true);
    expect(layout.items.some((item) => item.kind === "square" && item.id === "under")).toBe(false);
  });

  it("draws every stop as a sign from street zoom, featured or not", () => {
    const layout = layoutStops(map, { ...view, zoom: 16 }, "signs", stops, [], "chosen", "rtl", new Set(["listed"]), false);
    expect(Object.values(kinds(layout))).toEqual(["sign", "sign", "sign", "sign"]);
  });
});
