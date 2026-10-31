import { act, render, screen, waitFor } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { I18nProvider } from "../i18n/I18nProvider";
import type { Lang } from "../i18n/messages";
import { MapHost } from "./MapHost";
import MapView from "./MapView";
import {
  emptyScene,
  getMapState,
  requestLocate,
  resetMapState,
  setBottomInset,
  setMapScene,
  showLocated,
  type MapRouteLeg,
  type MapScene,
} from "./scene";

// jsdom has no WebGL: maplibre-gl is replaced by a recording fake.
const fake = vi.hoisted(() => {
  type Handler = (event?: unknown) => void;
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
  class FakeMap {
    options: Record<string, unknown>;
    handlers: Record<string, Handler[]> = {};
    sources = new Map<string, FakeSource>();
    layers: { id: string; type: string }[] = [];
    styleLayers = [
      { id: "place_city", type: "symbol", textField: "{name:latin}" as unknown },
      { id: "housenumber", type: "symbol", textField: "{housenumber}" as unknown },
    ];
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
    fire(event: string) {
      for (const handler of this.handlers[event] ?? []) handler({});
    }
    addSource(id: string, spec: { data: unknown }) {
      this.sources.set(id, new FakeSource(spec.data));
    }
    getSource(id: string) {
      return this.sources.get(id);
    }
    addLayer(layer: { id: string; type: string }) {
      this.layers.push(layer);
    }
    getStyle() {
      return { layers: this.styleLayers, glyphs: undefined };
    }
    getLayoutProperty(id: string) {
      return this.styleLayers.find((layer) => layer.id === id)?.textField;
    }
    setLayoutProperty(id: string, _name: string, value: unknown) {
      const layer = this.styleLayers.find((l) => l.id === id);
      if (layer) layer.textField = value;
    }
    getContainer() {
      return { clientHeight: 640, clientWidth: 360 };
    }
    getCenter() {
      return this.center;
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
  return { state, FakeMap };
});

vi.mock("maplibre-gl", () => {
  return { Map: fake.FakeMap, setWorkerUrl: () => {} };
});

type FakeMap = InstanceType<typeof fake.FakeMap>;

function renderWith(ui: ReactNode, lang: Lang = "he") {
  return render(<I18nProvider initialLang={lang}>{ui}</I18nProvider>);
}

async function loadedMap(): Promise<FakeMap> {
  await waitFor(() => expect(fake.state.instances.length).toBeGreaterThan(0));
  const map = fake.state.instances.at(-1)!;
  act(() => map.fire("load"));
  return map;
}

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
afterEach(() => resetMapState());

describe("MapView", () => {
  it("creates an offline map with no MapLibre attribution control and adds the scene layers", async () => {
    renderWith(<MapView />);
    const map = await loadedMap();
    expect(typeof map.options.style).toBe("object");
    expect(map.options.attributionControl).toBe(false);
    expect(map.layers.map((layer) => layer.id)).toEqual([
      "ot-accuracy",
      "ot-route-casing",
      "ot-route-walk",
      "ot-route-transit",
      "ot-pins",
      "ot-user",
    ]);
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
    const map = await loadedMap();
    expect(JSON.stringify(map.styleLayers[0]!.textField)).toContain("name:en");
    expect(map.styleLayers[1]!.textField).toBe("{housenumber}");
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
    expect(text).toHaveTextContent("Ministry of Transport");
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
