import { describe, expect, it } from "vitest";
import { THEME_COLORS } from "../styles/tokens";
import {
  DESTINATION_ICON,
  MARKER_PIXEL_RATIO,
  OPENFREEMAP_STYLES,
  accuracyFeatures,
  basemapRole,
  chooseStyle,
  destinationMarker,
  isNameTextField,
  lineMode,
  mapPalette,
  nameExpression,
  offlineStyle,
  overlayLayers,
  pinFeatures,
  ringFeatures,
  routeFeatures,
  sceneBounds,
  themeBasemap,
  userFeatures,
  withOverlay,
  type StyleJson,
  type StyleLayerJson,
} from "./layers";
import { emptyScene, type MapRouteLeg } from "./scene";

const walk: MapRouteLeg = { kind: "walk", mode: "walk", coordinates: null, from: [34.8, 32.1], to: [34.81, 32.11], label: null };
const walkLine: MapRouteLeg = {
  ...walk,
  coordinates: [
    [34.8, 32.1],
    [34.81, 32.11],
  ],
};
const bus: MapRouteLeg = {
  kind: "transit",
  mode: "bus",
  coordinates: [
    [34.81, 32.11],
    [34.9, 32.2],
  ],
  from: [34.81, 32.11],
  to: [34.9, 32.2],
  label: "8",
  active: true,
};
const train: MapRouteLeg = {
  kind: "transit",
  mode: "rail",
  coordinates: [
    [34.9, 32.2],
    [35.0, 32.8],
  ],
  from: [34.9, 32.2],
  to: [35.0, 32.8],
  label: null,
};

const layer = (layers: StyleLayerJson[], id: string) => layers.find((l) => l.id === id)!;

describe("scene to GeoJSON", () => {
  it("draws lines only for legs with geometry, each with its mode's line", () => {
    const { features } = routeFeatures([walk, bus]);
    expect(features).toHaveLength(1);
    expect(features[0]!.properties).toEqual({
      kind: "transit",
      mode: "bus",
      line: "bus",
      active: true,
      dimmed: false,
      label: "8",
      travelled: false,
      quiet: false,
      opacity: 1,
      vehicle: "bus",
      colorDark: "",
      colorLight: "",
    });
    expect(routeFeatures([walkLine, { ...bus, active: false }, train]).features.map((f) => f.properties.line)).toEqual([
      "walk",
      "bus",
      "rail",
    ]);
  });

  it("carries the operator's line colour per theme and the vehicle (look of 11 November 2026)", () => {
    const egged = { ...bus, operatorId: "3", operatorName: "אגד" };
    const [eggedLine, trainLine] = routeFeatures([egged, { ...train, operatorId: "2", operatorName: "רכבת ישראל" }]).features;
    expect(eggedLine!.properties).toMatchObject({ vehicle: "bus", colorDark: "#00a073", colorLight: "#008761" });
    expect(trainLine!.properties).toMatchObject({ vehicle: "train", colorDark: "#158aff", colorLight: "#00458a" });
    const lightRail = routeFeatures([{ ...bus, mode: "light_rail", operatorId: "99" }]).features[0]!;
    expect(lightRail.properties).toMatchObject({ vehicle: "light-rail", colorDark: "#f64b58", colorLight: "#f42434" });
    // An operator the table does not know: no colour of its own, the mode token applies.
    expect(routeFeatures([{ ...bus, operatorId: "16", operatorName: "סופרבוס" }]).features[0]!.properties.colorDark).toBe("");
  });

  it("fades every other leg while one is the current step, and none otherwise", () => {
    const dimmed = (route: MapRouteLeg[]) => routeFeatures(route).features.map((f) => f.properties.dimmed);
    expect(dimmed([walkLine, bus, train])).toEqual([true, false, true]);
    expect(dimmed([walkLine, { ...bus, active: false }, train])).toEqual([false, false, false]);
  });

  it("classifies API modes: rail, light rail, tram and metro as rail; walking; everything else as bus", () => {
    expect(["rail", "RAIL", "light_rail", "tram", "subway", "metro", "train"].map(lineMode)).toEqual(Array(7).fill("rail"));
    expect(["bus", "BUS", "ferry", "coach", "", null].map(lineMode)).toEqual(Array(6).fill("bus"));
    expect(lineMode("walk")).toBe("walk");
  });

  it("makes points for pins and the user, and a ring for accuracy", () => {
    expect(pinFeatures([{ id: "o", role: "origin", position: [34.8, 32.1], label: "A" }]).features[0]!.properties.role).toBe(
      "origin",
    );
    expect(userFeatures(null).features).toEqual([]);
    const user = { position: [34.8, 32.1] as [number, number], accuracyMeters: 50 };
    expect(userFeatures(user).features).toHaveLength(1);
    const ring = accuracyFeatures(user).features[0]!.geometry.coordinates[0]!;
    expect(ring[0]).toEqual(ring.at(-1));
    // 50 m north is ~0.00045 degrees of latitude.
    const maxLat = Math.max(...ring.map((p) => p[1]));
    expect(maxLat - 32.1).toBeCloseTo(0.00045, 4);
    expect(accuracyFeatures({ ...user, accuracyMeters: null }).features).toEqual([]);
  });

  it("gives a stop or transfer its own ride's line, else the drawn ride boarding or ending there", () => {
    const pins = [
      { id: "t", role: "transfer" as const, position: [34.9, 32.2] as [number, number], label: "Rail", mode: "light_rail" },
      { id: "b", role: "stop" as const, position: [34.81, 32.11] as [number, number], label: "Board" },
      { id: "x", role: "stop" as const, position: [35.0, 32.8] as [number, number], label: "Exit" },
      { id: "n", role: "stop" as const, position: [30, 30] as [number, number], label: "Nowhere" },
    ];
    const lines = pinFeatures(pins, [walk, bus, train]).features.map((f) => f.properties.line);
    expect(lines).toEqual(["rail", "bus", "rail", "bus"]);
  });

  it("frames route ends, geometry and pins, including a time-only walk's ends", () => {
    expect(sceneBounds(emptyScene)).toBeNull();
    expect(sceneBounds({ ...emptyScene, route: [walk, bus] })).toEqual([
      [34.8, 32.1],
      [34.9, 32.2],
    ]);
  });
});

describe("our layers in the theme's colours", () => {
  it.each(["dark", "light"] as const)("%s: lines by mode, ends, stops and the puck from the tokens", (theme) => {
    const c = THEME_COLORS[theme];
    const layers = overlayLayers(theme, { labels: false });
    expect(layers.map((l) => l.id)).toEqual([
      "ot-accuracy",
      "ot-ring",
      "ot-route-casing",
      "ot-route-walk",
      "ot-route-transit",
      "ot-route-train",
      "ot-pins",
      "ot-destination",
      "ot-user-halo",
      "ot-user",
    ]);
    // Rides 7.5 px (5 px faded) in the operator's colour for this theme, else the mode token.
    const own = theme === "dark" ? "colorDark" : "colorLight";
    const transit = layer(layers, "ot-route-transit").paint!;
    const faint = ["any", ["get", "dimmed"], ["==", ["get", "travelled"], true]];
    expect(transit["line-width"]).toEqual(["case", faint, 5, 7.5]);
    // A travelled stretch is grey (boards: On board); otherwise the operator's colour, else the mode's.
    expect(transit["line-color"]).toEqual([
      "case",
      ["==", ["get", "travelled"], true],
      c["border-strong"],
      [
        "case",
        ["!=", ["coalesce", ["get", own], ""], ""],
        ["get", own],
        ["match", ["get", "line"], "rail", c["mode-rail"], "walk", c.ink, c["mode-bus"]],
      ],
    ]);
    expect(transit["line-dasharray"]).toBeUndefined();
    // The pale outline (a land-coloured edge on a faded leg) and the train's dashed centre.
    expect(layer(layers, "ot-route-casing").paint).toEqual({
      "line-color": ["case", faint, c["map-land"], c["map-casing"]],
      "line-width": ["case", faint, 7, 11.5],
    });
    // Home's walking ring: thin, dashed, muted ink.
    expect(layer(layers, "ot-ring").paint).toEqual({ "line-color": c["ink-muted"], "line-width": 1.5, "line-dasharray": [2, 4] });
    const trainCentre = layer(layers, "ot-route-train");
    expect(trainCentre.filter).toEqual([
      "all",
      ["==", ["get", "kind"], "transit"],
      ["==", ["get", "vehicle"], "train"],
      ["!", ["get", "dimmed"]],
      ["!=", ["get", "travelled"], true],
    ]);
    expect(trainCentre.paint).toMatchObject({ "line-color": c["map-casing"], "line-width": 3.6 });
    // Walking: round ink dots.
    const walkPaint = layer(layers, "ot-route-walk").paint!;
    expect(walkPaint).toMatchObject({ "line-color": c.ink, "line-width": 4.5 });
    expect(walkPaint["line-dasharray"]).toEqual([0.02, 2]);
    expect(layer(layers, "ot-route-walk").layout).toMatchObject({ "line-cap": "round" });
    // Origin: an ink dot with a surface edge; stops: ringed in ink on surface.
    const pins = layer(layers, "ot-pins").paint!;
    expect(pins["circle-color"]).toEqual(["match", ["get", "role"], "origin", c.origin, c.surface]);
    expect(pins["circle-stroke-color"]).toEqual(["match", ["get", "role"], "origin", c.surface, c.ink]);
    expect(layer(layers, "ot-pins").filter).toEqual(["!=", ["get", "role"], "destination"]);
    // Destination: the square image, only for the destination pin.
    expect(layer(layers, "ot-destination")).toMatchObject({
      type: "symbol",
      filter: ["==", ["get", "role"], "destination"],
      layout: { "icon-image": DESTINATION_ICON, "icon-allow-overlap": true },
    });
    // The puck: brand with a surface edge over a brand halo.
    expect(layer(layers, "ot-user").paint).toMatchObject({ "circle-color": c.brand, "circle-stroke-color": c.surface });
    expect(layer(layers, "ot-user-halo").paint).toMatchObject({ "circle-color": c.brand, "circle-opacity": 0.18, "circle-radius": 24 });
    expect(layer(layers, "ot-accuracy").paint!["fill-color"]).toBe(c.brand);
    // No hard-coded colour anywhere: every colour is one of this theme's tokens.
    const tokens = new Set(Object.values(c));
    const colours = JSON.stringify(layers).match(/#[0-9a-f]{6}\b/gi) ?? [];
    expect(colours.length).toBeGreaterThan(0);
    for (const colour of colours) expect(tokens, colour).toContain(colour);
  });

  it("fades the other legs to .6, and labels lines only when the style has glyphs", () => {
    const layers = overlayLayers("dark", { labels: true });
    for (const id of ["ot-route-walk", "ot-route-transit"]) {
      expect(layer(layers, id).paint!["line-opacity"]).toEqual(["case", ["==", ["get", "quiet"], true], ["get", "opacity"], ["get", "dimmed"], 0.6, 1]);
    }
    expect(layer(layers, "ot-route-label").paint).toMatchObject({ "text-halo-color": THEME_COLORS.dark.surface });
    expect(overlayLayers("dark", { labels: false }).some((l) => l.id === "ot-route-label")).toBe(false);
  });

  it("draws a quiet line (boards Stop and Ride) 5 px at its own opacity, with no edge", () => {
    const [stop] = routeFeatures([{ ...bus, active: false, tone: "quiet" }]).features;
    expect(stop!.properties).toMatchObject({ quiet: true, opacity: 0.45, dimmed: true });
    const [ride] = routeFeatures([{ ...bus, active: false, tone: "quiet", quietOpacity: 0.4 }]).features;
    expect(ride!.properties.opacity).toBe(0.4);
    const layers = overlayLayers("dark", { labels: false });
    expect(layer(layers, "ot-route-casing").filter).toEqual(["all", ["==", ["get", "kind"], "transit"], ["!=", ["get", "quiet"], true]]);
  });

  it("the two themes differ where their tokens differ", () => {
    expect(mapPalette("dark")).not.toEqual(mapPalette("light"));
    // The printed-map palette read from the approved boards (client design, visual direction).
    expect(mapPalette("light")).toMatchObject({ land: "#f2f2ee", road: "#e2e1db", water: "#cfe0ea", park: "#dbe6d3", casing: "#ffffff" });
    expect(mapPalette("dark")).toMatchObject({ land: "#242321", road: "#2f2d2a", water: "#1c2b33", park: "#262d22", casing: "#f4f1ea" });
  });

  it("draws the destination as a rounded square in destination with a surface edge", () => {
    for (const theme of ["dark", "light"] as const) {
      const image = destinationMarker(theme);
      expect(image.width).toBe(image.height);
      expect(image.width).toBe(Math.ceil(19 * MARKER_PIXEL_RATIO) + 2);
      expect(image.data).toHaveLength(image.width * image.height * 4);
      const pixel = (x: number, y: number) => Array.from(image.data.slice((y * image.width + x) * 4, (y * image.width + x) * 4 + 4));
      const hex = (p: number[]) => `#${p.slice(0, 3).map((v) => v.toString(16).padStart(2, "0")).join("")}`;
      const mid = Math.floor(image.width / 2);
      expect(hex(pixel(mid, mid))).toBe(THEME_COLORS[theme].destination);
      expect(pixel(mid, mid)[3]).toBe(255);
      // The edge (2.5 px at 2x: 5 image px) is surface.
      expect(hex(pixel(mid, 3))).toBe(THEME_COLORS[theme].surface);
      expect(pixel(mid, 3)[3]).toBe(255);
      // Outside, and the rounded corner, are transparent.
      expect(pixel(0, 0)[3]).toBe(0);
      expect(pixel(2, 2)[3]).toBe(0);
    }
  });
});

const base: StyleJson = {
  version: 8,
  sources: { openmaptiles: { type: "vector", url: "https://tiles.openfreemap.org/planet" } },
  glyphs: "https://tiles.openfreemap.org/fonts/{fontstack}/{range}.pbf",
  layers: [
    { id: "background", type: "background", paint: { "background-color": "rgb(12,12,12)" } },
    { id: "water", type: "fill", source: "openmaptiles", "source-layer": "water", paint: { "fill-color": "rgb(27,27,29)" } },
    { id: "waterway", type: "line", source: "openmaptiles", "source-layer": "waterway", paint: { "line-color": "#123" } },
    { id: "landuse_park", type: "fill", source: "openmaptiles", "source-layer": "landuse", paint: { "fill-color": "rgb(32,32,32)" } },
    { id: "road_pier", type: "line", source: "openmaptiles", "source-layer": "transportation", paint: { "line-color": "#000" } },
    { id: "highway_major_casing", type: "line", source: "openmaptiles", "source-layer": "transportation", paint: { "line-color": "#333" } },
    { id: "highway_major_inner", type: "line", source: "openmaptiles", "source-layer": "transportation", paint: { "line-color": "#111" } },
    {
      id: "highway_motorway_inner",
      type: "line",
      source: "openmaptiles",
      "source-layer": "transportation",
      paint: { "line-color": ["interpolate", ["linear"], ["zoom"], 5.8, "#ddd", 6, "#000"] },
    },
    { id: "railway_transit", type: "line", source: "openmaptiles", "source-layer": "transportation", paint: { "line-color": "#232323" } },
    {
      id: "place_city",
      type: "symbol",
      source: "openmaptiles",
      "source-layer": "place",
      layout: { "text-field": ["case", ["has", "name:nonlatin"], ["get", "name:latin"], ["get", "name"]] },
      paint: { "text-color": "#656565" },
    },
    { id: "highway_ref", type: "symbol", source: "openmaptiles", "source-layer": "transportation_name", layout: { "text-field": ["get", "ref"] } },
    { id: "building", type: "fill", source: "openmaptiles", "source-layer": "building", paint: { "fill-color": "#444" } },
    { id: "poi_r1", type: "symbol", source: "openmaptiles", "source-layer": "poi", layout: { "text-field": ["get", "name"] } },
  ],
};

describe("basemap styles", () => {
  it("dark uses OpenFreeMap dark, light uses positron; fixtures, tests and 'offline' stay offline", () => {
    expect(chooseStyle("production", undefined, "dark")).toBe("https://tiles.openfreemap.org/styles/dark");
    expect(chooseStyle("development", undefined, "light")).toBe("https://tiles.openfreemap.org/styles/positron");
    expect(OPENFREEMAP_STYLES).toEqual({
      dark: "https://tiles.openfreemap.org/styles/dark",
      light: "https://tiles.openfreemap.org/styles/positron",
    });
    expect(chooseStyle("fixtures", undefined, "dark")).toEqual(offlineStyle("dark"));
    expect(chooseStyle("test", undefined, "light")).toEqual(offlineStyle("light"));
    expect(chooseStyle("production", "offline", "light")).toEqual(offlineStyle("light"));
    expect(chooseStyle("fixtures", "/my-style.json", "dark")).toBe("/my-style.json");
    expect(JSON.stringify(offlineStyle("dark"))).not.toMatch(/https?:/);
  });

  it("the offline style is the theme's land colour", () => {
    expect(offlineStyle("dark").layers).toEqual([{ id: "background", type: "background", paint: { "background-color": "#242321" } }]);
    expect(offlineStyle("light").layers[0]!.paint!["background-color"]).toBe(THEME_COLORS.light["map-land"]);
  });

  it("knows land, water, parks and roads in an OpenMapTiles style; leaves rail and labels alone", () => {
    const roles = Object.fromEntries(base.layers.map((l) => [l.id, basemapRole(l)]));
    expect(roles).toEqual({
      background: "land",
      water: "water",
      waterway: "water",
      landuse_park: "park",
      road_pier: "land",
      highway_major_casing: "land",
      highway_major_inner: "road",
      highway_motorway_inner: "road",
      railway_transit: null,
      place_city: null,
      highway_ref: null,
      building: "land",
      poi_r1: null,
    });
  });

  it.each(["dark", "light"] as const)("%s: recolours background, water, roads and labels to the map tokens", (theme) => {
    const c = THEME_COLORS[theme];
    const before = JSON.stringify(base);
    const themed = themeBasemap(base, theme, "he");
    expect(JSON.stringify(base)).toBe(before); // the input is not changed
    const paint = (id: string) => layer(themed.layers, id).paint!;
    expect(paint("background")["background-color"]).toBe(c["map-land"]);
    expect(paint("water")["fill-color"]).toBe(c["map-water"]);
    expect(paint("waterway")["line-color"]).toBe(c["map-water"]);
    expect(paint("highway_major_inner")["line-color"]).toBe(c["map-road"]);
    expect(paint("highway_motorway_inner")["line-color"]).toBe(c["map-road"]);
    expect(paint("highway_major_casing")["line-color"]).toBe(c["map-land"]);
    expect(paint("road_pier")["line-color"]).toBe(c["map-land"]);
    // Labels read on land in either theme: ink-muted on a land halo.
    expect(paint("place_city")).toEqual({ "text-color": c["ink-muted"], "text-halo-color": c["map-land"] });
    expect(paint("highway_ref")).toEqual({ "text-color": c["ink-muted"], "text-halo-color": c["map-land"] });
    // Parks in map-park; buildings melt into the land; points of interest are hidden (few labels).
    expect(paint("landuse_park")).toEqual({ "fill-color": c["map-park"] });
    expect(paint("building")).toEqual({ "fill-color": c["map-land"] });
    expect(layer(themed.layers, "poi_r1").layout).toMatchObject({ visibility: "none" });
    // Everything else keeps the base style's own paint.
    expect(paint("railway_transit")).toEqual({ "line-color": "#232323" });
    expect(themed.sources).toEqual(base.sources);
    expect(themed.glyphs).toBe(base.glyphs);
  });

  it("labels names in the page language and leaves refs alone", () => {
    const he = themeBasemap(base, "dark", "he");
    expect(layer(he.layers, "place_city").layout!["text-field"]).toEqual(nameExpression("he"));
    expect(layer(he.layers, "highway_ref").layout!["text-field"]).toEqual(["get", "ref"]);
    const en = themeBasemap(base, "light", "en");
    expect(layer(en.layers, "place_city").layout!["text-field"]).toEqual(nameExpression("en"));
  });

  it("a theme switch carries our sources (the drawn scene) over and redraws our layers in the new colours", () => {
    const data = { type: "FeatureCollection", features: [{ type: "Feature", geometry: null, properties: { kind: "transit" } }] };
    const previous: StyleJson = {
      ...themeBasemap(base, "dark", "he"),
      sources: { ...base.sources, "ot-route": { type: "geojson", data } },
      layers: [...themeBasemap(base, "dark", "he").layers, ...overlayLayers("dark", { labels: true })],
    };
    const next = themeBasemap(base, "light", "he");
    const merged = withOverlay(previous, next, "light");
    expect(merged.sources["ot-route"]).toEqual({ type: "geojson", data });
    expect(merged.sources.openmaptiles).toEqual(base.sources.openmaptiles);
    expect(merged.layers.slice(0, next.layers.length)).toEqual(next.layers);
    expect(merged.layers.slice(next.layers.length)).toEqual(overlayLayers("light", { labels: true }));
    // The first load has nothing of ours to carry.
    expect(withOverlay(undefined, next, "light")).toBe(next);
    expect(withOverlay(base, next, "light")).toBe(next);
  });
});

describe("labels", () => {
  it("prefers Hebrew names in Hebrew and Latin names in English", () => {
    expect(nameExpression("he")).toEqual(["coalesce", ["get", "name:he"], ["get", "name"]]);
    expect(JSON.stringify(nameExpression("en"))).toContain("name:en");
    expect(JSON.stringify(nameExpression("en"))).toContain("name:latin");
  });

  it("rewrites only name labels", () => {
    expect(isNameTextField("{name}")).toBe(true);
    expect(isNameTextField(["coalesce", ["get", "name_en"], ["get", "name"]])).toBe(true);
    expect(isNameTextField("{housenumber}")).toBe(false);
    expect(isNameTextField(["get", "ref"])).toBe(false);
    expect(isNameTextField(undefined)).toBe(false);
  });
});

describe("board additions (11 November 2026)", () => {
  it("draws options not chosen faded and a travelled stretch grey", () => {
    const [faded, travelled, normal] = routeFeatures([
      { ...bus, active: false, tone: "faded" },
      { ...bus, active: false, tone: "travelled" },
      { ...bus, active: false },
    ]).features;
    expect(faded!.properties).toMatchObject({ dimmed: true, travelled: false });
    expect(travelled!.properties).toMatchObject({ dimmed: false, travelled: true });
    expect(normal!.properties).toMatchObject({ dimmed: false, travelled: false });
  });

  it("makes a closed ring of the given radius and frames it", () => {
    const ring = { center: [34.78, 32.08] as [number, number], radiusMeters: 400 };
    const line = ringFeatures(ring).features[0]!.geometry.coordinates;
    expect(line[0]).toEqual(line.at(-1));
    // 400 m north is ~0.0036 degrees of latitude.
    expect(Math.max(...line.map((p) => p[1])) - 32.08).toBeCloseTo(0.0036, 3);
    expect(ringFeatures(null).features).toEqual([]);
    const bounds = sceneBounds({ ...emptyScene, ring })!;
    expect(bounds[1][1] - bounds[0][1]).toBeCloseTo(0.0072, 3);
  });

  it("fitTo frames only the given points (a tapped step), else everything including tags and stop pins", () => {
    const scene = {
      ...emptyScene,
      route: [bus, train],
      tags: [{ id: "t", position: [35.5, 33] as [number, number], kind: "plain" as const, text: "x" }],
    };
    expect(sceneBounds(scene)![1]).toEqual([35.5, 33]);
    expect(sceneBounds({ ...scene, fitTo: bus.coordinates })).toEqual([
      [34.81, 32.11],
      [34.9, 32.2],
    ]);
    expect(sceneBounds({ ...emptyScene, stopPins: [{ id: "s", position: [34.7, 32], ariaLabel: "s" }] })).toEqual([
      [34.7, 32],
      [34.7, 32],
    ]);
  });
});
