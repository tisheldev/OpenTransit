import { lazy, Suspense, useEffect, useState } from "react";
import { useI18n } from "../i18n/I18nProvider";
import "./map.css";

// The full-bleed layer the shell renders behind the sheet. It renders at once as an empty
// container plus the attribution; MapLibre (the MapView chunk) is imported only after the
// first frame and an idle moment, so it never delays Home becoming interactive.
//
// Placement hooks for the shell: .map-host is position:absolute; inset:0 (give its parent
// a positioning context). On its own (the e2e harness) the attribution floats at the top
// of the map, below --map-attribution-top. The shell renders <MapHost attribution={false}/>
// and places <MapAttribution inline/> in its top row beside Back, a band the sheet never
// covers (the full snap stops below it).

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

/**
 * The map credits as one compact, semi-opaque line (full credits are in Settings).
 * `inline`: placed by its container (the shell's top row) instead of floating on the map.
 */
export function MapAttribution({ inline = false }: { inline?: boolean }) {
  const { t, dir, lang } = useI18n();
  return (
    <p className={inline ? "map-attribution map-attribution-inline" : "map-attribution"} dir={dir} lang={lang} data-testid="map-attribution">
      {/* Each credit is isolated, so Latin names keep their order inside a Hebrew line. */}
      <bdi>{t("map.attribution.osm")}</bdi>
      <span aria-hidden="true"> · </span>
      <bdi>{t("map.attribution.tiles")}</bdi>
      <span aria-hidden="true"> · </span>
      <bdi>{t("map.attribution.mot")}</bdi>
    </p>
  );
}

/** `attribution={false}` when the host page shows <MapAttribution inline /> itself (the shell). */
export function MapHost({ attribution = true }: { attribution?: boolean }) {
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
      {attribution && <MapAttribution />}
    </div>
  );
}
