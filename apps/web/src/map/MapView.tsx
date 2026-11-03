import { Map as MapLibreMap, setWorkerUrl, type GeoJSONSource, type StyleSpecification } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import workerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?url";
import { useEffect, useRef, useState, type CSSProperties } from "react";
import { useI18n } from "../i18n/I18nProvider";
import {
  COLORS,
  DEFAULT_CENTER,
  DEFAULT_ZOOM,
  accuracyFeatures,
  chooseStyle,
  isNameTextField,
  nameExpression,
  pinFeatures,
  routeFeatures,
  sceneBounds,
  userFeatures,
} from "./layers";
import { setMapCenter, useMapState, type MapScene, type MapUser } from "./scene";

// The lazy map chunk: everything that imports MapLibre lives here (MapHost loads it after
// the first frame). The map is never mirrored; MapHost gives this container dir="ltr".
//
// No RTL text plugin is loaded: MapLibre 6 shapes and reorders right-to-left text itself
// (setRTLTextPlugin is deprecated), and the mapbox-gl-rtl-text plugin is evaluated with
// eval() and instantiates WebAssembly in the worker, which the client CSP (script-src
// 'self', no 'unsafe-eval'/'wasm-unsafe-eval') forbids.

// The worker is a separate module file next to the hashed assets (same origin, no CDN).
setWorkerUrl(workerUrl);

const SOURCES = ["ot-accuracy", "ot-route", "ot-pins", "ot-user"] as const;
/** Fit padding around the route; the sheet height is added to the bottom. */
const FIT_PADDING = { top: 64, bottom: 24, left: 32, right: 32 };

function prefersReducedMotion(): boolean {
  return typeof window.matchMedia === "function" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

function installLayers(map: MapLibreMap): void {
  const empty = { type: "FeatureCollection" as const, features: [] };
  for (const id of SOURCES) if (!map.getSource(id)) map.addSource(id, { type: "geojson", data: empty });

  map.addLayer({
    id: "ot-accuracy",
    type: "fill",
    source: "ot-accuracy",
    paint: { "fill-color": COLORS.user, "fill-opacity": 0.15, "fill-outline-color": COLORS.user },
  });
  map.addLayer({
    id: "ot-route-casing",
    type: "line",
    source: "ot-route",
    filter: ["==", ["get", "kind"], "transit"],
    layout: { "line-cap": "round", "line-join": "round" },
    paint: { "line-color": COLORS.halo, "line-width": ["case", ["get", "active"], 11, 8] },
  });
  map.addLayer({
    id: "ot-route-walk",
    type: "line",
    source: "ot-route",
    filter: ["==", ["get", "kind"], "walk"],
    layout: { "line-cap": "round", "line-join": "round" },
    paint: {
      "line-color": ["case", ["get", "active"], COLORS.active, COLORS.walk],
      "line-width": ["case", ["get", "active"], 5, 3],
      "line-dasharray": [1, 2],
    },
  });
  map.addLayer({
    id: "ot-route-transit",
    type: "line",
    source: "ot-route",
    filter: ["==", ["get", "kind"], "transit"],
    layout: { "line-cap": "round", "line-join": "round" },
    paint: {
      "line-color": ["case", ["get", "active"], COLORS.active, COLORS.transit],
      "line-width": ["case", ["get", "active"], 7, 5],
    },
  });
  map.addLayer({
    id: "ot-pins",
    type: "circle",
    source: "ot-pins",
    paint: {
      "circle-radius": ["match", ["get", "role"], "origin", 7, "destination", 8, 5],
      "circle-color": [
        "match",
        ["get", "role"],
        "origin",
        COLORS.origin,
        "destination",
        COLORS.destination,
        COLORS.stop,
      ],
      "circle-stroke-color": ["match", ["get", "role"], "origin", COLORS.halo, "destination", COLORS.halo, COLORS.transit],
      "circle-stroke-width": 3,
    },
  });
  map.addLayer({
    id: "ot-user",
    type: "circle",
    source: "ot-user",
    paint: { "circle-radius": 7, "circle-color": COLORS.user, "circle-stroke-color": COLORS.halo, "circle-stroke-width": 3 },
  });

  // Line labels need glyphs; the offline style has none, so it draws lines only.
  if (map.getStyle()?.glyphs) {
    map.addLayer({
      id: "ot-route-label",
      type: "symbol",
      source: "ot-route",
      filter: ["all", ["==", ["get", "kind"], "transit"], ["!=", ["get", "label"], ""]],
      layout: {
        "symbol-placement": "line",
        "text-field": ["get", "label"],
        "text-font": ["Noto Sans Bold"],
        "text-size": 13,
      },
      paint: { "text-color": COLORS.active, "text-halo-color": COLORS.halo, "text-halo-width": 2 },
    });
  }
}

/** Basemap labels: Hebrew names in Hebrew, English/Latin in English (where the style has them). */
function applyLabelLanguage(map: MapLibreMap, lang: "he" | "en"): void {
  for (const layer of map.getStyle()?.layers ?? []) {
    if (layer.type !== "symbol" || layer.id.startsWith("ot-")) continue;
    if (!isNameTextField(map.getLayoutProperty(layer.id, "text-field"))) continue;
    map.setLayoutProperty(layer.id, "text-field", nameExpression(lang) as never);
  }
}

function drawScene(map: MapLibreMap, scene: MapScene, located: MapUser | null): void {
  const set = (id: (typeof SOURCES)[number], data: unknown) =>
    (map.getSource(id) as GeoJSONSource | undefined)?.setData(data as never);
  const user = scene.user ?? located;
  set("ot-route", routeFeatures(scene.route));
  set("ot-pins", pinFeatures(scene.pins));
  set("ot-user", userFeatures(user));
  set("ot-accuracy", accuracyFeatures(user));
}

/** The sheet's height over the map, clamped so a tall sheet still leaves a quarter visible. */
function coveredHeight(map: MapLibreMap, inset: number): number {
  const height = map.getContainer().clientHeight;
  return height > 0 ? Math.min(inset, Math.round(height * 0.75)) : 0;
}

/** Reports the centre of the visible map (above the sheet), where the pick pin points. */
function reportCenter(map: MapLibreMap, inset: number): void {
  const element = map.getContainer();
  const covered = coveredHeight(map, inset);
  const { lng, lat } =
    covered > 0 ? map.unproject([element.clientWidth / 2, (element.clientHeight - covered) / 2]) : map.getCenter();
  setMapCenter([lng, lat]);
}

export default function MapView() {
  const { lang, t } = useI18n();
  const { scene, bottomInset, locateRequest, located } = useMapState();
  const container = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [failed, setFailed] = useState(false);
  const pickRef = useRef(scene.pick);
  const insetRef = useRef(0);
  useEffect(() => {
    pickRef.current = scene.pick;
  }, [scene.pick]);

  // Create the map once. Missing WebGL throws here (a short note replaces the map); a
  // failing style or tile only fires "error" and leaves the map area blank. Neither
  // breaks the rest of the app.
  useEffect(() => {
    if (!container.current) return;
    let map: MapLibreMap;
    try {
      map = new MapLibreMap({
        container: container.current,
        style: chooseStyle(import.meta.env.MODE, import.meta.env.VITE_MAP_STYLE) as string | StyleSpecification,
        center: DEFAULT_CENTER,
        zoom: DEFAULT_ZOOM,
        // Our own attribution stays visible above the sheet (MapHost); MapLibre's collapses.
        attributionControl: false,
        dragRotate: false,
        pitchWithRotate: false,
      });
    } catch (error) {
      console.warn("Map unavailable", error);
      void Promise.resolve().then(() => setFailed(true));
      return;
    }
    mapRef.current = map;
    map.touchZoomRotate.disableRotation();
    map.on("load", () => {
      installLayers(map);
      setLoaded(true);
      if (pickRef.current) reportCenter(map, insetRef.current);
    });
    map.on("moveend", () => {
      if (pickRef.current) reportCenter(map, insetRef.current);
    });
    map.on("error", (event) => console.warn("Map error", event.error));
    return () => {
      mapRef.current = null;
      setLoaded(false);
      map.remove();
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (map && loaded) applyLabelLanguage(map, lang);
  }, [lang, loaded]);

  useEffect(() => {
    const map = mapRef.current;
    if (map && loaded) drawScene(map, scene, located);
  }, [scene, located, loaded]);

  // The sheet covers the bottom, so fitting, following and the pick centre all use the
  // visible area above it. This is done per camera move (fit padding, centre offset)
  // rather than with map.setPadding: in MapLibre 6.14 a persistent bottom padding left
  // a band of that height at the top of the canvas undrawn (seen in Chromium).
  const inset = Math.max(0, bottomInset);
  useEffect(() => {
    insetRef.current = inset;
  }, [inset]);
  // After Locate on a scene without a user, the camera stays on that fix until the next scene.
  const locatedRef = useRef(located);
  useEffect(() => {
    locatedRef.current = located;
  }, [located]);
  const focusedScene = useRef<{ scene: MapScene | null; at: number }>({ scene: null, at: 0 });

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !loaded) return;
    const duration = prefersReducedMotion() ? 0 : 400;
    const bottom = coveredHeight(map, inset);
    if (scene.camera === "fit") {
      const bounds = sceneBounds(scene);
      if (bounds) {
        // One point (a single pin) frames at street level rather than the closest zoom.
        const point = bounds[0][0] === bounds[1][0] && bounds[0][1] === bounds[1][1];
        try {
          map.fitBounds(bounds, {
            padding: { ...FIT_PADDING, bottom: FIT_PADDING.bottom + bottom },
            maxZoom: point ? 15 : 16,
            duration,
          });
        } catch (error) {
          console.warn("Map fit failed", error);
        }
      } else if (!locatedRef.current) {
        // Nothing to frame (Home, pick on map): the scene's focus or the default view,
        // centred in the part of the map the sheet leaves visible. Applied when the scene
        // arrives and while the sheet settles into its new snap, then left alone, so a
        // later resize (or the browser's bar) never undoes the passenger's own panning.
        const fresh = focusedScene.current.scene !== scene;
        if (fresh) focusedScene.current = { scene, at: Date.now() };
        if (fresh || Date.now() - focusedScene.current.at < 800) {
          const focus = scene.focus ?? { center: DEFAULT_CENTER, zoom: DEFAULT_ZOOM };
          map.easeTo({ center: focus.center, zoom: focus.zoom, offset: [0, -bottom / 2], duration: fresh ? duration : 0 });
        }
      }
    } else if (scene.camera === "follow" && scene.user) {
      map.easeTo({ center: scene.user.position, offset: [0, -bottom / 2], duration });
    }
  }, [scene, inset, loaded]);

  // requestLocate(): recentre on the user (the scene's, or a one-off fix from Locate). The
  // initial value is not a request.
  const seenLocate = useRef(locateRequest);
  const target = scene.user ?? located;
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !loaded || locateRequest === seenLocate.current) return;
    seenLocate.current = locateRequest;
    if (!target) return;
    map.easeTo({
      center: target.position,
      zoom: Math.max(map.getZoom(), 15),
      offset: [0, -coveredHeight(map, insetRef.current) / 2],
      duration: prefersReducedMotion() ? 0 : 400,
    });
  }, [locateRequest, target, loaded]);

  // Entering pick mode (or the sheet moving) reports the visible centre straight away.
  useEffect(() => {
    const map = mapRef.current;
    if (map && loaded && scene.pick) reportCenter(map, inset);
  }, [scene.pick, inset, loaded]);


  return (
    <div className="map-view" data-testid="map-view">
      <div ref={container} className="map-canvas" data-testid="map-canvas" />
      {scene.pick && (
        <div
          className="map-pick-pin"
          role="img"
          aria-label={t("map.pickPin")}
          data-testid="map-pick-pin"
          style={{ "--map-inset": `${inset}px` } as CSSProperties}
        />
      )}
      {failed && (
        <p className="map-note" dir={lang === "he" ? "rtl" : "ltr"}>
          {t("map.unavailable")}
        </p>
      )}
    </div>
  );
}
