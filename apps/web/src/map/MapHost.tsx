import { lazy, Suspense, useEffect, useState } from "react";
import { useI18n } from "../i18n/I18nProvider";
import "./map.css";

// The full-bleed layer the shell renders behind the sheet. It renders at once as an empty
// container plus the attribution; MapLibre (the MapView chunk) is imported only after the
// first frame and an idle moment, so it never delays Home becoming interactive.
//
// Placement hooks for the shell: .map-host is position:absolute; inset:0 (give its parent
// a positioning context). The attribution sits at the top of the map, below any header
// the shell overlays: set --map-attribution-top on .map-host (or an ancestor) to that
// header's height. The sheet never reaches the top, so the attribution stays visible.

function MapUnavailable() {
  const { t, dir } = useI18n();
  return (
    <p className="map-note" dir={dir}>
      {t("map.unavailable")}
    </p>
  );
}

const MapView = lazy(() =>
  import("./MapView").catch((error: unknown) => {
    console.warn("Map chunk failed to load", error);
    return { default: MapUnavailable };
  }),
);

/** Resolves after the next frame has been painted and the browser is idle (or 1 s passes). */
function afterFirstFrame(callback: () => void): () => void {
  let cancelled = false;
  let frame: number | undefined;
  let idle: number | undefined;
  let timer: ReturnType<typeof setTimeout> | undefined;
  const run = () => {
    if (!cancelled) callback();
  };
  const whenIdle = () => {
    if (typeof window.requestIdleCallback === "function") idle = window.requestIdleCallback(run, { timeout: 1000 });
    else timer = setTimeout(run, 50);
  };
  if (typeof window.requestAnimationFrame === "function") {
    // Two frames: the first callback runs before that frame paints.
    frame = window.requestAnimationFrame(() => {
      frame = window.requestAnimationFrame(whenIdle);
    });
  } else {
    timer = setTimeout(whenIdle, 0);
  }
  return () => {
    cancelled = true;
    if (frame !== undefined) window.cancelAnimationFrame?.(frame);
    if (idle !== undefined) window.cancelIdleCallback?.(idle);
    if (timer !== undefined) clearTimeout(timer);
  };
}

export function MapAttribution() {
  const { t, dir, lang } = useI18n();
  return (
    <p className="map-attribution" dir={dir} lang={lang} data-testid="map-attribution">
      <span>{t("map.attribution.osm")}</span>
      <span aria-hidden="true"> · </span>
      <span>{t("map.attribution.tiles")}</span>
      <span aria-hidden="true"> · </span>
      <span>{t("map.attribution.mot")}</span>
    </p>
  );
}

export function MapHost() {
  const [ready, setReady] = useState(false);
  useEffect(() => afterFirstFrame(() => setReady(true)), []);

  return (
    // The map is never mirrored: it stays left to right in Hebrew too.
    <div className="map-host" dir="ltr" data-testid="map-host" data-map-ready={ready ? "true" : "false"}>
      {ready && (
        <Suspense fallback={null}>
          <MapView />
        </Suspense>
      )}
      <MapAttribution />
    </div>
  );
}
