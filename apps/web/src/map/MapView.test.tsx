import { act, render, screen, waitFor } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { I18nProvider } from "../i18n/I18nProvider";
import type { Lang } from "../i18n/messages";
import { resetTheme, setTheme } from "../lib/theme";
import { THEME_COLORS } from "../styles/tokens";
import { destinationMarker } from "./layers";
import { MapHost } from "./MapHost";
import MapView from "./MapView";
import {
  emptyScene,
  getMapState,
  requestLocate,
  resetMapState,
  setBottomInset,
  setMapScene,
  setSideInset,
  showLocated,
  type MapRouteLeg,
  type MapScene,
} from "./scene";

// jsdom has no WebGL: maplibre-gl is replaced by a recording fake. finishStyle() does what
// MapLibre does when a style arrives: run transformStyle(previous, next), replace the
// style's sources and layers with the result, and fire "style.load".
const fake = vi.hoisted(() => {
  type Handler = (event?: unknown) => void;
  type Layer = { id: string; type: string; layout?: Record<string, unknown>; paint?: Record<string, unknown> };
  type Style = { version: 8; glyphs?: string; sources: Record<string, { type: string; data?: unknown }>; layers: Layer[] };
  type Transform = (previous: Style | undefined, next: Style) => Style;
  const state = { failNext: false, instances: [] as FakeMap[] };
  class FakeSource {
    data: unknown;
    constructor(data: unknown) {
      this.data = data;
    }
    setData(data: unknown) {
      this.data = data;
    }
  }
  /** A stand-in for an OpenFreeMap style: glyphs, land, water, a road, and two labels. */
  const remoteStyle = (): Style => ({
    version: 8,
    glyphs: "https://tiles.openfreemap.org/fonts/{fontstack}/{range}.pbf",
    sources: { openmaptiles: { type: "vector" } },
    layers: [
      { id: "background", type: "background", paint: { "background-color": "#0c0c0c" } },
      { id: "water", type: "fill", "source-layer": "water", paint: { "fill-color": "#1b1b1d" } } as Layer,
      { id: "highway_minor", type: "line", "source-layer": "transportation", paint: { "line-color": "#181818" } } as Layer,
      { id: "place_city", type: "symbol", layout: { "text-field": "{name:latin}" } },
      { id: "housenumber", type: "symbol", layout: { "text-field": "{housenumber}" } },
    ],
  });
  class FakeMap {
    options: Record<string, unknown>;
    handlers: Record<string, Handler[]> = {};
    sources = new Map<string, FakeSource>();
    /** The loaded style's own layers (the basemap) and ours (ot-*). */
    styleLayers: Layer[] = [];
    layers: Layer[] = [];
    glyphs: string | undefined;
    images = new Map<string, { image: { width: number; data: Uint8ClampedArray }; options?: unknown }>();
    pendingStyle: { style: unknown; options?: { diff?: boolean; transformStyle?: Transform } } | null = null;
    styled = false;
    center = { lng: 34.78, lat: 32.08 };
    calls: { method: string; args: unknown[] }[] = [];
    touchZoomRotate = { disableRotation: () => {} };
    constructor(options: Record<string, unknown>) {
      if (state.failNext) {
        state.failNext = false;
        throw new Error("Failed to initialize WebGL");
      }
      this.options = options;
      state.instances.push(this);
    }
    on(event: string, handler: Handler) {
      (this.handlers[event] ??= []).push(handler);
      return this;
    }
    off(event: string, handler: Handler) {
      this.handlers[event] = (this.handlers[event] ?? []).filter((h) => h !== handler);
      return this;
    }
    fire(event: string) {
      for (const handler of this.handlers[event] ?? []) handler({});
    }
    setStyle(style: unknown, options?: { diff?: boolean; transformStyle?: Transform }) {
      this.calls.push({ method: "setStyle", args: [style, options] });
      this.pendingStyle = { style, options };
      return this;
    }
    /** The pending style arrives (a URL resolves to `fetched`, else the stand-in). */
    finishStyle(fetched?: Style) {
      const { style, options } = this.pendingStyle!;
      this.pendingStyle = null;
      const json = structuredClone(fetched ?? (typeof style === "string" ? remoteStyle() : (style as Style)));
      const previous = this.styled ? (structuredClone(this.getStyle()) as Style) : undefined;
      const next = options?.transformStyle ? options.transformStyle(previous, json) : json;
      const ours = (id: string) => id.startsWith("ot-");
      this.glyphs = next.glyphs;
      this.styleLayers = next.layers.filter((layer) => !ours(layer.id));
      this.layers = next.layers.filter((layer) => ours(layer.id));
      this.sources = new Map(
        Object.entries(next.sources)
          .filter(([id]) => ours(id))
          .map(([id, source]) => [id, new FakeSource(source.data)]),
      );
      this.styled = true;
      this.fire("style.load");
    }
    addSource(id: string, spec: { data: unknown }) {
      this.sources.set(id, new FakeSource(spec.data));
    }
    getSource(id: string) {
      return this.sources.get(id);
    }
    addLayer(layer: Layer) {
      this.layers.push(layer);
    }
    getLayer(id: string) {
      return [...this.styleLayers, ...this.layers].find((layer) => layer.id === id);
    }
    getStyle(): Style {
      const sources = Object.fromEntries([...this.sources].map(([id, source]) => [id, { type: "geojson", data: source.data }]));
      return { version: 8, glyphs: this.glyphs, sources, layers: [...this.styleLayers, ...this.layers] };
    }
    getLayoutProperty(id: string, name: string) {
      return this.getLayer(id)?.layout?.[name];
    }
    setLayoutProperty(id: string, name: string, value: unknown) {
      const layer = this.getLayer(id);
      if (layer) layer.layout = { ...layer.layout, [name]: value };
    }
    hasImage(id: string) {
      return this.images.has(id);
    }
    addImage(id: string, image: { width: number; data: Uint8ClampedArray }, options?: unknown) {
      this.calls.push({ method: "addImage", args: [id, image, options] });
      this.images.set(id, { image, options });
    }
    updateImage(id: string, image: { width: number; data: Uint8ClampedArray }) {
      this.calls.push({ method: "updateImage", args: [id, image] });
      this.images.set(id, { image, options: this.images.get(id)?.options });
    }
    getContainer() {
      return { clientHeight: 640, clientWidth: 360 };
    }
    getCenter() {
      return this.center;
    }
    /** The inverse of unproject (map tags are placed with it). */
    project([lng, lat]: [number, number]) {
      return { x: 180 + (lng - this.center.lng) / 0.001, y: 320 - (lat - this.center.lat) / 0.001 };
    }
    /** Pretend 1 px = 0.001 degree around the centre, y growing southwards. */
    unproject([x, y]: [number, number]) {
      return { lng: this.center.lng + (x - 180) * 0.001, lat: this.center.lat - (y - 320) * 0.001 };
    }
    getZoom() {
      return 12;
    }
    setPadding(...args: unknown[]) {
      this.calls.push({ method: "setPadding", args });
    }
    fitBounds(...args: unknown[]) {
      this.calls.push({ method: "fitBounds", args });
    }
    easeTo(...args: unknown[]) {
      this.calls.push({ method: "easeTo", args });
    }
    remove() {}
  }
  return { state, FakeMap, remoteStyle };
});

vi.mock("maplibre-gl", () => {
  return { Map: fake.FakeMap, setWorkerUrl: () => {} };
});

type FakeMap = InstanceType<typeof fake.FakeMap>;

function renderWith(ui: ReactNode, lang: Lang = "he") {
  return render(<I18nProvider initialLang={lang}>{ui}</I18nProvider>);
}

/** The map once its first style has arrived (`fetched` stands in for a remote style) and it has loaded. */
async function loadedMap(fetched?: ReturnType<typeof fake.remoteStyle>): Promise<FakeMap> {
  await waitFor(() => expect(fake.state.instances.length).toBeGreaterThan(0));
  const map = fake.state.instances.at(-1)!;
  act(() => {
    map.finishStyle(fetched);
    map.fire("load");
  });
  return map;
}

const paintOf = (map: FakeMap, id: string) => map.getLayer(id)!.paint!;
const backgroundOf = (map: FakeMap) => paintOf(map, "background")["background-color"];
const styleCalls = (map: FakeMap) => map.calls.filter((call) => call.method === "setStyle");
const cameraCalls = (map: FakeMap) => map.calls.filter((call) => call.method === "fitBounds" || call.method === "easeTo");

function lines(map: FakeMap) {
  return (map.getSource("ot-route")!.data as { features: { properties: { kind: string } }[] }).features;
}

const bus: MapRouteLeg = {
  kind: "transit",
  mode: "bus",
  coordinates: [
    [34.78, 32.07],
    [34.8, 32.09],
  ],
  from: [34.78, 32.07],
  to: [34.8, 32.09],
  label: "8",
};
const timeOnlyWalk: MapRouteLeg = { kind: "walk", mode: "walk", coordinates: null, from: [34.8, 32.09], to: [34.81, 32.1], label: null };

beforeEach(() => {
  resetMapState();
  fake.state.instances.length = 0;
  fake.state.failNext = false;
});
afterEach(() => {
  resetMapState();
  localStorage.clear();
  resetTheme();
});

describe("MapView", () => {
  it("creates an offline map with no MapLibre attribution control and adds the scene layers", async () => {
    renderWith(<MapView />);
    const map = await loadedMap();
    const [style, options] = styleCalls(map)[0]!.args as [unknown, { diff: boolean }];
    expect(typeof style).toBe("object");
    expect(options.diff).toBe(false);
    expect(map.options.attributionControl).toBe(false);
    expect(map.layers.map((layer) => layer.id)).toEqual([
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
  });

  it("is dark by default: land, lines and the destination square in the dark tokens", async () => {
    renderWith(<MapView />);
    const map = await loadedMap();
    const dark = THEME_COLORS.dark;
    expect(backgroundOf(map)).toBe(dark["map-land"]);
    expect(JSON.stringify(paintOf(map, "ot-route-transit")["line-color"])).toContain(dark["mode-bus"]);
    expect(paintOf(map, "ot-user")["circle-color"]).toBe(dark.brand);
    const icon = map.images.get("ot-destination")!;
    expect(icon.options).toEqual({ pixelRatio: 2 });
    expect(Array.from(icon.image.data)).toEqual(Array.from(destinationMarker("dark").data));
  });

  it("starts light when light is the stored choice, recolouring the real basemap before it is drawn", async () => {
    setTheme("light");
    vi.stubEnv("VITE_MAP_STYLE", "https://tiles.openfreemap.org/styles/positron");
    try {
      renderWith(<MapView />);
      const map = await loadedMap(fake.remoteStyle());
      const light = THEME_COLORS.light;
      expect(styleCalls(map)[0]!.args[0]).toBe("https://tiles.openfreemap.org/styles/positron");
      expect(backgroundOf(map)).toBe(light["map-land"]);
      expect(paintOf(map, "water")["fill-color"]).toBe(light["map-water"]);
      expect(paintOf(map, "highway_minor")["line-color"]).toBe(light["map-road"]);
      // With glyphs, lines carry their number in the line's colour.
      expect(map.getLayer("ot-route-label")).toBeDefined();
      expect(paintOf(map, "ot-route-label")["text-halo-color"]).toBe(light.surface);
    } finally {
      vi.unstubAllEnvs();
    }
  });

  it("a theme switch restyles the map in place: the scene, camera and sheet inset are kept", async () => {
    renderWith(<MapView />);
    const map = await loadedMap();
    act(() => setBottomInset(224));
    const scene: MapScene = {
      ...emptyScene,
      route: [bus],
      pins: [{ id: "destination", role: "destination", position: [34.8, 32.09], label: "B" }],
      user: { position: [34.79, 32.08], accuracyMeters: 30 },
      camera: "fit",
    };
    act(() => setMapScene(scene));
    const camera = cameraCalls(map).length;
    const drawn = map.getSource("ot-route")!.data;
    expect(lines(map)).toHaveLength(1);

    act(() => setTheme("light"));
    const [, options] = styleCalls(map).at(-1)!.args as [unknown, { diff: boolean }];
    expect(styleCalls(map)).toHaveLength(2);
    expect(options.diff).toBe(true);
    // The destination square is replaced in place in the new colours.
    expect(map.calls.filter((c) => c.method === "updateImage")).toHaveLength(1);
    expect(Array.from(map.images.get("ot-destination")!.image.data)).toEqual(Array.from(destinationMarker("light").data));
    act(() => map.finishStyle());

    const light = THEME_COLORS.light;
    expect(backgroundOf(map)).toBe(light["map-land"]);
    expect(JSON.stringify(paintOf(map, "ot-route-transit")["line-color"])).toContain(light["mode-bus"]);
    expect(JSON.stringify(paintOf(map, "ot-route-casing")["line-color"])).toContain(light["map-casing"]);
    expect(paintOf(map, "ot-user")["circle-color"]).toBe(light.brand);
    // Scene: still drawn, the same features; camera: not moved; inset: unchanged.
    expect(map.getSource("ot-route")!.data).toEqual(drawn);
    expect((map.getSource("ot-pins")!.data as { features: unknown[] }).features).toHaveLength(1);
    expect((map.getSource("ot-user")!.data as { features: unknown[] }).features).toHaveLength(1);
    expect(cameraCalls(map)).toHaveLength(camera);
    expect(getMapState().bottomInset).toBe(224);
    // Our layers are not duplicated.
    expect(map.layers.map((layer) => layer.id).filter((id) => id === "ot-route-transit")).toHaveLength(1);

    // And back to dark.
    act(() => setTheme("dark"));
    act(() => map.finishStyle());
    expect(backgroundOf(map)).toBe(THEME_COLORS.dark["map-land"]);
    expect(cameraCalls(map)).toHaveLength(camera);
    expect(lines(map)).toHaveLength(1);
  });

  it("a theme chosen before the map has loaded is applied once it loads", async () => {
    renderWith(<MapView />);
    await waitFor(() => expect(fake.state.instances.length).toBeGreaterThan(0));
    const map = fake.state.instances.at(-1)!;
    act(() => setTheme("light"));
    expect(styleCalls(map)).toHaveLength(1);
    act(() => {
      map.finishStyle();
      map.fire("load");
    });
    expect(styleCalls(map)).toHaveLength(2);
    act(() => map.finishStyle());
    expect(backgroundOf(map)).toBe(THEME_COLORS.light["map-land"]);
  });

  it("updates sources when the scene changes, and a null-geometry walk adds no line", async () => {
    renderWith(<MapView />);
    const map = await loadedMap();
    expect(lines(map)).toEqual([]);
    const scene: MapScene = {
      ...emptyScene,
      route: [bus, timeOnlyWalk],
      pins: [{ id: "destination", role: "destination", position: [34.81, 32.1], label: "B" }],
      user: { position: [34.79, 32.08], accuracyMeters: 30 },
      camera: "fit",
    };
    act(() => setMapScene(scene));
    expect(lines(map)).toHaveLength(1);
    expect(lines(map)[0]!.properties.kind).toBe("transit");
    expect((map.getSource("ot-pins")!.data as { features: unknown[] }).features).toHaveLength(1);
    expect((map.getSource("ot-user")!.data as { features: unknown[] }).features).toHaveLength(1);
    expect((map.getSource("ot-accuracy")!.data as { features: unknown[] }).features).toHaveLength(1);
    // fit frames the route and pins, including the time-only walk's end.
    const fit = map.calls.filter((call) => call.method === "fitBounds").at(-1)!;
    expect(fit.args[0]).toEqual([
      [34.78, 32.07],
      [34.81, 32.1],
    ]);
  });

  it("draws tags and stop pins over the map at their points; the tappable ones are buttons (boards)", async () => {
    renderWith(<MapView />);
    const map = await loadedMap();
    const chose = vi.fn();
    const picked = vi.fn();
    act(() =>
      setMapScene({
        ...emptyScene,
        camera: "keep",
        tags: [
          { id: "arrive", position: [34.79, 32.08], kind: "faded", text: "18:41", ariaLabel: "האפשרות שמגיעה ב־18:41", onSelect: chose },
          { id: "dest", position: [34.8, 32.09], kind: "strong", text: "מרכז הרצליה" },
          { id: "next", position: [34.78, 32.07], kind: "plain", text: "2 דק׳", line: { mode: "bus", label: "5", operatorId: "5" } },
        ],
        stopPins: [{ id: "s1", position: [34.78, 32.07], ariaLabel: "דיזנגוף / המלך ג׳ורג׳", selected: true, onSelect: picked }],
        ring: { center: [34.78, 32.07], radiusMeters: 400 },
      }),
    );
    expect((map.getSource("ot-ring")!.data as { features: unknown[] }).features).toHaveLength(1);
    const option = screen.getByRole("button", { name: "האפשרות שמגיעה ב־18:41" });
    option.click();
    expect(chose).toHaveBeenCalledTimes(1);
    const stop = screen.getByRole("button", { name: "דיזנגוף / המלך ג׳ורג׳" });
    expect(stop).toHaveAttribute("aria-pressed", "true");
    stop.click();
    expect(picked).toHaveBeenCalledTimes(1);
    // A tag without an action is text, not a button; a line badge carries its operator's colour.
    expect(screen.getByText("מרכז הרצליה").closest("button")).toBeNull();
    const badge = screen.getByTestId("map-overlay").querySelector<HTMLElement>(".ot-line")!;
    expect(badge.style.getPropertyValue("--line-bg")).toBe("#1565c0");
    act(() => setMapScene(emptyScene));
    expect(screen.queryByTestId("map-overlay")).toBeNull();
  });

  it("on a wide screen frames the scene beside the side panel (board 8), and a phone layout clears it", async () => {
    renderWith(<MapView />);
    const map = await loadedMap();
    act(() => setSideInset(0, 400));
    act(() => setMapScene({ ...emptyScene, route: [bus], camera: "fit" }));
    const fit = map.calls.filter((call) => call.method === "fitBounds").at(-1)!;
    expect((fit.args[1] as { padding: Record<string, number> }).padding).toMatchObject({ left: 32, right: 432, bottom: 24 });
    act(() => setSideInset(0, 0));
    expect(getMapState().sideInset).toEqual({ left: 0, right: 0 });
  });

  it("keeps the sheet's height (clamped) out of fitting, and follows / recentres on the user above it", async () => {
    renderWith(<MapView />);
    const map = await loadedMap();
    const pin = { id: "o", role: "origin" as const, position: [34.8, 32.1] as [number, number], label: "A" };
    act(() => setBottomInset(224));
    act(() => setMapScene({ ...emptyScene, pins: [pin], camera: "fit" }));
    const fit = () => map.calls.filter((c) => c.method === "fitBounds").at(-1)!.args[1];
    // A single point frames at street level (15), not the closest zoom.
    expect(fit()).toMatchObject({ padding: { top: 64, bottom: 224 + 24, left: 32, right: 32 }, maxZoom: 15 });
    act(() => setBottomInset(5000));
    expect(fit()).toMatchObject({ padding: { bottom: 480 + 24 } });
    // No persistent map padding (it left part of the canvas undrawn in MapLibre 6.14).
    expect(map.calls.some((c) => c.method === "setPadding")).toBe(false);
    act(() => setBottomInset(224));

    const user = { position: [34.79, 32.08] as [number, number], accuracyMeters: null };
    act(() => setMapScene({ ...emptyScene, user, camera: "follow" }));
    expect(map.calls.filter((c) => c.method === "easeTo").at(-1)!.args[0]).toMatchObject({
      center: user.position,
      offset: [0, -112],
    });

    act(() => setMapScene({ ...emptyScene, user, camera: "keep" }));
    const before = map.calls.length;
    act(() => requestLocate());
    expect(map.calls.length).toBe(before + 1);
    expect(map.calls.at(-1)).toMatchObject({ method: "easeTo", args: [{ center: user.position, zoom: 15, offset: [0, -112] }] });

    // keep: a new scene leaves the camera alone.
    act(() => setMapScene({ ...emptyScene, pins: [pin], camera: "keep" }));
    expect(map.calls.length).toBe(before + 1);
  });

  it("with nothing to frame, a fit scene goes to its focus (or the default view) above the sheet, once", async () => {
    renderWith(<MapView />);
    const map = await loadedMap();
    act(() => setBottomInset(224));
    const focus = { center: [34.7749, 32.0753] as [number, number], zoom: 13 };
    act(() => setMapScene({ ...emptyScene, camera: "fit", focus }));
    expect(map.calls.filter((c) => c.method === "easeTo").at(-1)!.args[0]).toMatchObject({
      center: focus.center,
      zoom: 13,
      offset: [0, -112],
    });
    act(() => setMapScene({ ...emptyScene, camera: "fit" }));
    expect(map.calls.filter((c) => c.method === "easeTo").at(-1)!.args[0]).toMatchObject({ center: [34.7818, 32.0853], zoom: 11 });
    // Long after the scene arrived, a resize no longer moves the camera (the passenger may have panned).
    const now = Date.now();
    vi.spyOn(Date, "now").mockReturnValue(now + 5000);
    const before = map.calls.length;
    act(() => setBottomInset(300));
    expect(map.calls.length).toBe(before);
  });

  it("draws a one-off located fix where the scene has no user, recentres on it, and drops it with the next scene", async () => {
    renderWith(<MapView />);
    const map = await loadedMap();
    act(() => setMapScene({ ...emptyScene, camera: "keep" }));
    act(() => showLocated({ position: [34.7749, 32.0753], accuracyMeters: 20 }));
    expect((map.getSource("ot-user")!.data as { features: unknown[] }).features).toHaveLength(1);
    expect(map.calls.at(-1)).toMatchObject({ method: "easeTo", args: [{ center: [34.7749, 32.0753], zoom: 15 }] });
    act(() => setMapScene({ ...emptyScene, camera: "keep" }));
    expect((map.getSource("ot-user")!.data as { features: unknown[] }).features).toHaveLength(0);
  });

  it("reports the visible centre (above the sheet) in pick mode", async () => {
    setBottomInset(240);
    setMapScene({ ...emptyScene, pick: true });
    renderWith(<MapView />);
    await loadedMap();
    // Visible area is 400 px high: its centre is y=200, 120 px above the canvas centre.
    const [lng, lat] = getMapState().center!;
    expect(lng).toBeCloseTo(34.78, 6);
    expect(lat).toBeCloseTo(32.08 + 0.12, 6);
  });

  it("reports the centre in pick mode on load and after every move, and shows the centre pin", async () => {
    setMapScene({ ...emptyScene, pick: true });
    renderWith(<MapView />);
    const map = await loadedMap();
    expect(getMapState().center).toEqual([34.78, 32.08]);
    expect(screen.getByRole("img", { name: "המיקום שנבחר נמצא במרכז המפה" })).toBeInTheDocument();
    map.center = { lng: 35.0, lat: 32.8 };
    act(() => map.fire("moveend"));
    expect(getMapState().center).toEqual([35.0, 32.8]);

    act(() => setMapScene(emptyScene));
    map.center = { lng: 34.5, lat: 31.5 };
    act(() => map.fire("moveend"));
    expect(getMapState().center).toEqual([35.0, 32.8]);
    expect(screen.queryByTestId("map-pick-pin")).toBeNull();
  });

  it("switches basemap name labels with the language, leaving other labels alone", async () => {
    renderWith(<MapView />, "en");
    const map = await loadedMap(fake.remoteStyle());
    expect(JSON.stringify(map.getLayoutProperty("place_city", "text-field"))).toContain("name:en");
    expect(map.getLayoutProperty("housenumber", "text-field")).toBe("{housenumber}");
  });

  it("shows a short note instead of breaking when WebGL is missing", async () => {
    fake.state.failNext = true;
    vi.spyOn(console, "warn").mockImplementation(() => {});
    renderWith(<MapView />);
    expect(await screen.findByText("המפה אינה זמינה כרגע")).toBeInTheDocument();
  });
});

describe("MapHost", () => {
  it("renders at once, left to right, with attribution, before the map chunk loads", async () => {
    let frame: FrameRequestCallback | null = null;
    vi.spyOn(window, "requestAnimationFrame").mockImplementation((callback) => {
      frame = callback;
      return 1;
    });
    renderWith(<MapHost />);
    const host = screen.getByTestId("map-host");
    expect(host).toHaveAttribute("dir", "ltr");
    expect(host).toHaveAttribute("data-map-ready", "false");
    expect(screen.queryByTestId("map-view")).toBeNull();
    expect(screen.getByTestId("map-attribution")).toHaveTextContent("© OpenStreetMap");
    // Frames run: the chunk is imported and the map is created.
    vi.mocked(window.requestAnimationFrame).mockImplementation((callback) => {
      setTimeout(() => callback(0), 0);
      return 2;
    });
    act(() => (frame as FrameRequestCallback | null)?.(0));
    expect(await screen.findByTestId("map-view")).toBeInTheDocument();
    expect(host).toHaveAttribute("data-map-ready", "true");
  });

  it("shows the attribution in the current language", () => {
    renderWith(<MapHost />, "en");
    const text = screen.getByTestId("map-attribution");
    expect(text).toHaveAttribute("dir", "ltr");
    expect(text).toHaveTextContent("© OpenStreetMap");
    expect(text).toHaveTextContent("OpenFreeMap");
    expect(text).toHaveTextContent("Israel MoT");
  });

  it("attribution in Hebrew names the Ministry of Transport", () => {
    renderWith(<MapHost />, "he");
    const text = screen.getByTestId("map-attribution");
    expect(text).toHaveAttribute("dir", "rtl");
    expect(text).toHaveTextContent("משרד התחבורה");
    expect(text).toHaveTextContent("OpenFreeMap");
  });

  it("does not import MapLibre statically (only the lazy MapView does)", () => {
    for (const file of ["MapHost.tsx", "scene.ts", "fromJourney.ts", "layers.ts"]) {
      const source = readFileSync(resolve("src/map", file), "utf8");
      expect(source, file).not.toMatch(/from\s+["']maplibre-gl/);
    }
    const host = readFileSync(resolve("src/map/MapHost.tsx"), "utf8");
    expect(host).toMatch(/lazy\(\(\) =>\s*import\("\.\/MapView"\)/);
  });
});
