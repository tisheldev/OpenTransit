import {
  Map as MapLibreMap,
  setWorkerUrl,
  type GeoJSONSource,
  type LayerSpecification,
  type StyleSpecification,
} from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import workerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?url";
import { useEffect, useRef, useState, type CSSProperties } from "react";
import { useI18n } from "../i18n/I18nProvider";
import { useTheme, type ThemeName } from "../lib/theme";
import {
  DEFAULT_CENTER,
  DEFAULT_ZOOM,
  DESTINATION_ICON,
  MARKER_PIXEL_RATIO,
  OVERLAY_SOURCES,
  accuracyFeatures,
  chooseStyle,
  destinationMarker,
  isNameTextField,
  nameExpression,
  overlayLayers,
  pinFeatures,
  ringFeatures,
  routeFeatures,
  sceneBounds,
  themeBasemap,
  userFeatures,
  withOverlay,
  type StyleJson,
} from "./layers";
import { MapOverlay } from "./MapOverlay";
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

/** Fit padding around the route; the sheet height is added to the bottom. */
const FIT_PADDING = { top: 64, bottom: 24, left: 32, right: 32 };

function prefersReducedMotion(): boolean {
  return typeof window.matchMedia === "function" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

/**
 * Loads the base style for a theme, recoloured to the theme's map tokens and labelled in
 * the page language before it is first drawn. `diff`: a theme switch, applied as a style
 * diff that carries our sources (the drawn scene) and layers (in the new colours) over, so
 * nothing is redrawn from scratch and the camera stays where it is.
 */
function loadStyle(map: MapLibreMap, theme: ThemeName, lang: () => "he" | "en", diff: boolean, applied: (theme: ThemeName) => void): void {
  const style = chooseStyle(import.meta.env.MODE, import.meta.env.VITE_MAP_STYLE, theme);
  map.setStyle(style as string | StyleSpecification, {
    diff,
    transformStyle: (previous, next) => {
      applied(theme);
      const themed = themeBasemap(next as unknown as StyleJson, theme, lang());
      return withOverlay(previous as unknown as StyleJson | undefined, themed, theme) as unknown as StyleSpecification;
    },
  });
}

/** The destination square for a theme (replaced in place on a theme switch). */
function setDestinationIcon(map: MapLibreMap, theme: ThemeName): void {
  const image = destinationMarker(theme);
  if (map.hasImage(DESTINATION_ICON)) map.updateImage(DESTINATION_ICON, image);
  else map.addImage(DESTINATION_ICON, image, { pixelRatio: MARKER_PIXEL_RATIO });
}

/** Adds whatever of ours the loaded style lacks: everything after the first load, nothing after a switch. */
function installOverlay(map: MapLibreMap, theme: ThemeName): void {
  if (!map.hasImage(DESTINATION_ICON)) setDestinationIcon(map, theme);
  const empty = { type: "FeatureCollection" as const, features: [] };
  for (const id of OVERLAY_SOURCES) if (!map.getSource(id)) map.addSource(id, { type: "geojson", data: empty });
  // Line labels need glyphs; the offline style has none, so it draws lines only.
  for (const layer of overlayLayers(theme, { labels: !!map.getStyle()?.glyphs })) {
    if (!map.getLayer(layer.id)) map.addLayer(layer as unknown as LayerSpecification);
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
  const set = (id: (typeof OVERLAY_SOURCES)[number], data: unknown) =>
    (map.getSource(id) as GeoJSONSource | undefined)?.setData(data as never);
  const user = scene.user ?? located;
  set("ot-route", routeFeatures(scene.route));
  set("ot-ring", ringFeatures(scene.ring));
  set("ot-pins", pinFeatures(scene.pins, scene.route));
  set("ot-user", userFeatures(user));
  set("ot-accuracy", accuracyFeatures(user));
}

/** The sheet's height over the map, clamped so a tall sheet still leaves a quarter visible. */
function coveredHeight(map: MapLibreMap, inset: number): number {
  const height = map.getContainer().clientHeight;
  return height > 0 ? Math.min(inset, Math.round(height * 0.75)) : 0;
}

type Side = { left: number; right: number };

/** Reports the centre of the visible map (above the sheet, beside a side panel), where the pick pin points. */
function reportCenter(map: MapLibreMap, inset: number, side: Side): void {
  const element = map.getContainer();
  const covered = coveredHeight(map, inset);
  const sideways = side.left > 0 || side.right > 0;
  const { lng, lat } =
    covered > 0 || sideways
      ? map.unproject([(side.left + element.clientWidth - side.right) / 2, (element.clientHeight - covered) / 2])
      : map.getCenter();
  setMapCenter([lng, lat]);
}

export default function MapView() {
  const { lang, t } = useI18n();
  const theme = useTheme();
  const { scene, bottomInset, sideInset, locateRequest, located } = useMapState();
  const container = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [failed, setFailed] = useState(false);
  const pickRef = useRef(scene.pick);
  const insetRef = useRef(0);
  const sideRef = useRef<Side>({ left: 0, right: 0 });
  // What a style (re)load needs when it lands: the current scene, fix, language and theme.
  const sceneRef = useRef(scene);
  const langRef = useRef(lang);
  const themeRef = useRef(theme);
  // After Locate on a scene without a user, the camera stays on that fix until the next scene.
  const locatedRef = useRef(located);
  /** The theme last asked for, and the theme of the style actually loaded. */
  const requestedTheme = useRef<ThemeName | null>(null);
  const styledTheme = useRef<ThemeName | null>(null);
  useEffect(() => {
    pickRef.current = scene.pick;
    sceneRef.current = scene;
  }, [scene]);
  useEffect(() => {
    langRef.current = lang;
  }, [lang]);
  useEffect(() => {
    themeRef.current = theme;
  }, [theme]);
  useEffect(() => {
    locatedRef.current = located;
  }, [located]);

  // Create the map once. Missing WebGL throws here (a short note replaces the map); a
  // failing style or tile only fires "error" and leaves the map area blank. Neither
  // breaks the rest of the app.
  useEffect(() => {
    if (!container.current) return;
    let map: MapLibreMap;
    try {
      map = new MapLibreMap({
        container: container.current,
        // The style is set below, recoloured for the theme before its first frame.
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
    // Every style load (the first, and a theme switch): add what is missing of ours and
    // draw the current scene into it.
    map.on("style.load", () => {
      installOverlay(map, styledTheme.current ?? themeRef.current);
      applyLabelLanguage(map, langRef.current);
      drawScene(map, sceneRef.current, locatedRef.current);
    });
    map.on("load", () => {
      setLoaded(true);
      if (pickRef.current) reportCenter(map, insetRef.current, sideRef.current);
    });
    map.on("moveend", () => {
      if (pickRef.current) reportCenter(map, insetRef.current, sideRef.current);
    });
    map.on("error", (event) => console.warn("Map error", event.error));
    requestedTheme.current = themeRef.current;
    loadStyle(map, themeRef.current, () => langRef.current, false, (applied) => (styledTheme.current = applied));
    return () => {
      mapRef.current = null;
      setLoaded(false);
      map.remove();
    };
  }, []);

  // A theme chosen in Settings restyles the loaded map in place: the scene, the camera and
  // the sheet inset are untouched.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !loaded || theme === requestedTheme.current) return;
    requestedTheme.current = theme;
    setDestinationIcon(map, theme);
    loadStyle(map, theme, () => langRef.current, true, (applied) => (styledTheme.current = applied));
  }, [theme, loaded]);

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
  // a band of that height at the top of the canvas undrawn (seen in Chromium). Note that
  // headless Chromium on its default GPU backend also leaves a band the height of whatever
  // covers the bottom of the canvas undrawn in screenshots, with no padding at all; with
  // --use-angle=swiftshader the whole canvas draws. That one is a screenshot artefact.
  const inset = Math.max(0, bottomInset);
  useEffect(() => {
    insetRef.current = inset;
  }, [inset]);
  useEffect(() => {
    sideRef.current = sideInset;
  }, [sideInset]);
  /** Horizontal offset that centres content in the part of the map beside a side panel. */
  const sideOffset = (sideInset.left - sideInset.right) / 2;
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
            padding: {
              ...FIT_PADDING,
              bottom: FIT_PADDING.bottom + bottom,
              left: FIT_PADDING.left + sideInset.left,
              right: FIT_PADDING.right + sideInset.right,
            },
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
          map.easeTo({ center: focus.center, zoom: focus.zoom, offset: [sideOffset, -bottom / 2], duration: fresh ? duration : 0 });
        }
      }
    } else if (scene.camera === "follow" && scene.user) {
      map.easeTo({ center: scene.user.position, offset: [sideOffset, -bottom / 2], duration });
    }
  }, [scene, inset, sideOffset, sideInset, loaded]);

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
      offset: [(sideRef.current.left - sideRef.current.right) / 2, -coveredHeight(map, insetRef.current) / 2],
      duration: prefersReducedMotion() ? 0 : 400,
    });
  }, [locateRequest, target, loaded]);

  // Entering pick mode (or the sheet moving) reports the visible centre straight away.
  useEffect(() => {
    const map = mapRef.current;
    if (map && loaded && scene.pick) reportCenter(map, inset, sideInset);
  }, [scene.pick, inset, sideInset, loaded]);


  return (
    <div className="map-view" data-testid="map-view">
      <div ref={container} className="map-canvas" data-testid="map-canvas" />
      {loaded && mapRef.current && (
        <MapOverlay map={mapRef.current} tags={scene.tags ?? []} stopPins={scene.stopPins ?? []} dir={lang === "he" ? "rtl" : "ltr"} />
      )}
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
