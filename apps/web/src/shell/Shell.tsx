import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent,
  type PointerEvent,
  type ReactNode,
} from "react";
import { useStatus } from "../api/queries";
import { useI18n } from "../i18n/I18nProvider";
import { locationSource } from "../lib/geolocation";
import { MapAttribution, MapHost } from "../map/MapHost";
import { getMapState, requestLocate, setBottomInset, showLocated, useMapSelector } from "../map/scene";
import { back, hrefFor, useRoute, type Route } from "../router";
import { Screen } from "../screens/screens";
import { Banners } from "./Banners";
import { useLocationAvailability } from "./location";
import { SheetContext, SNAP_FRACTION, defaultSnap, fullHeight, nearestSnap, stepSnap, type Snap } from "./sheet";

/** Where Back leads when there is no in-app history entry (a deep link or a reload). */
export function backFallback(route: Route): Route {
  return route.name === "navigate" ? { name: "compare" } : { name: "home" };
}

// The surface (design: Surface): the map full-bleed behind, one bottom sheet that holds
// every screen, and only two floating controls, Back and Locate. No tabs, no menus.
// The top band (banners, Back, the one-line map attribution) is never covered: the full
// sheet stops below it (--overlay-top-h).

function viewportHeight(): number {
  return window.visualViewport?.height ?? window.innerHeight;
}

/** True after the first paint, so Home renders from storage before any request. */
function useAfterFirstPaint(): boolean {
  const [painted, setPainted] = useState(false);
  useEffect(() => {
    const id = window.setTimeout(() => setPainted(true), 0);
    return () => window.clearTimeout(id);
  }, []);
  return painted;
}

function Sheet({
  snap,
  setSnap,
  topReserved,
  corner,
  locate,
  children,
}: {
  snap: Snap;
  setSnap: (snap: Snap) => void;
  /** Height of the top band the full sheet must not cover. */
  topReserved: number;
  /** An optional control in the handle row's inline-end corner (Home: Settings). */
  corner?: ReactNode;
  /** The Locate button, floating just above the sheet. */
  locate?: ReactNode;
  children: ReactNode;
}) {
  const { t } = useI18n();
  const sheetRef = useRef<HTMLElement>(null);
  const drag = useRef<{ startY: number; startHeight: number; moved: boolean } | null>(null);
  const suppressClick = useRef(false);
  const [dragHeight, setDragHeight] = useState<number | null>(null);

  // Report the covered height so the map keeps its content above the sheet.
  useLayoutEffect(() => {
    const element = sheetRef.current;
    if (!element) return;
    const report = () => setBottomInset(Math.round(element.getBoundingClientRect().height || SNAP_FRACTION[snap] * viewportHeight()));
    report();
    if (typeof ResizeObserver === "undefined") return;
    // Next frame: the map reacting inside this callback must not re-trigger observers.
    let frame = 0;
    const observer = new ResizeObserver(() => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(report);
    });
    observer.observe(element);
    return () => {
      cancelAnimationFrame(frame);
      observer.disconnect();
    };
  }, [snap]);

  const onPointerDown = (event: PointerEvent<HTMLButtonElement>) => {
    const element = sheetRef.current;
    if (!element || event.button !== 0) return;
    drag.current = { startY: event.clientY, startHeight: element.getBoundingClientRect().height, moved: false };
    event.currentTarget.setPointerCapture?.(event.pointerId);
  };
  const onPointerMove = (event: PointerEvent<HTMLButtonElement>) => {
    const state = drag.current;
    if (!state) return;
    const delta = state.startY - event.clientY;
    if (Math.abs(delta) > 6) state.moved = true;
    if (!state.moved) return;
    const max = fullHeight(viewportHeight(), topReserved);
    const min = 0.2 * viewportHeight();
    setDragHeight(Math.max(min, Math.min(max, state.startHeight + delta)));
  };
  const onPointerUp = (event: PointerEvent<HTMLButtonElement>) => {
    const state = drag.current;
    drag.current = null;
    if (!state?.moved) return;
    suppressClick.current = true;
    setDragHeight(null);
    setSnap(nearestSnap(state.startHeight + (state.startY - event.clientY), viewportHeight()));
  };
  const onClick = () => {
    if (suppressClick.current) {
      suppressClick.current = false;
      return;
    }
    setSnap(snap === "full" ? "peek" : stepSnap(snap, 1));
  };
  const onKeyDown = (event: KeyboardEvent<HTMLButtonElement>) => {
    if (event.key === "ArrowUp") setSnap(stepSnap(snap, 1));
    else if (event.key === "ArrowDown") setSnap(stepSnap(snap, -1));
    else return;
    event.preventDefault();
  };

  return (
    <section
      ref={sheetRef}
      className={`sheet sheet-${snap}${dragHeight === null ? "" : " sheet-dragging"}`}
      style={dragHeight === null ? undefined : { blockSize: `${dragHeight}px` }}
      aria-label={t("shell.sheet")}
      data-snap={snap}
    >
      {locate}
      <div className="sheet-handle-row">
        <button
          type="button"
          className="sheet-handle"
          aria-label={t("shell.sheet.size", { size: t(`shell.sheet.${snap}`) })}
          aria-keyshortcuts="ArrowUp ArrowDown"
          onPointerDown={onPointerDown}
          onPointerMove={onPointerMove}
          onPointerUp={onPointerUp}
          onPointerCancel={() => {
            drag.current = null;
            setDragHeight(null);
          }}
          onClick={onClick}
          onKeyDown={onKeyDown}
        >
          <span className="sheet-grip" aria-hidden="true" />
        </button>
        {corner && <div className="sheet-corner">{corner}</div>}
      </div>
      {children}
    </section>
  );
}

/**
 * Locate: recentre on the scene's own position (Navigate), or take one fix on this tap
 * and show it (Home, choose on map). Busy while the fix is pending; a failure says so.
 */
function LocateButton() {
  const { t } = useI18n();
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    if (!failed) return;
    const id = window.setTimeout(() => setFailed(false), 4000);
    return () => window.clearTimeout(id);
  }, [failed]);

  const locate = async () => {
    if (getMapState().scene.user) {
      requestLocate();
      return;
    }
    if (busy) return;
    setBusy(true);
    setFailed(false);
    const result = await locationSource().current();
    setBusy(false);
    if (result.ok) {
      showLocated({ position: [result.fix.longitude, result.fix.latitude], accuracyMeters: result.fix.accuracyMeters });
    } else {
      setFailed(true);
    }
  };

  return (
    <div className="sheet-locate">
      {failed && (
        <p className="locate-note" role="status">
          {t("shell.locate.failed")}
        </p>
      )}
      <button
        type="button"
        className="icon-button floating"
        aria-label={t("nav.locate")}
        aria-busy={busy || undefined}
        onClick={() => void locate()}
      >
        {busy ? <span className="spinner" aria-hidden="true" /> : <span aria-hidden="true">◎</span>}
      </button>
    </div>
  );
}

/** Focus the new screen: its autofocus field if it has one, else its heading. */
function focusScreen(main: HTMLElement | null): void {
  if (!main) return;
  const target = main.querySelector<HTMLElement>("[data-autofocus]") ?? main.querySelector<HTMLElement>("h1");
  if (!target) {
    main.focus({ preventScroll: true });
    return;
  }
  if (target.tagName === "H1" && !target.hasAttribute("tabindex")) target.setAttribute("tabindex", "-1");
  target.focus({ preventScroll: true });
}

export function Shell({ fixtureMode }: { fixtureMode: boolean }) {
  const { t } = useI18n();
  const route = useRoute();
  const painted = useAfterFirstPaint();
  const status = useStatus({ enabled: painted });
  const location = useLocationAvailability();
  const picking = useMapSelector((state) => state.scene.pick);
  const mainRef = useRef<HTMLElement>(null);
  const shellRef = useRef<HTMLDivElement>(null);
  const topRef = useRef<HTMLDivElement>(null);
  const [topReserved, setTopReserved] = useState(0);
  const routeKey = JSON.stringify(route);

  // Each route opens at its own snap; a screen may change it afterwards (pick on map).
  const [snapState, setSnapState] = useState<{ key: string; snap: Snap }>(() => ({ key: routeKey, snap: defaultSnap(route.name) }));
  let snap = snapState.snap;
  if (snapState.key !== routeKey) {
    snap = defaultSnap(route.name);
    setSnapState({ key: routeKey, snap });
  }
  // Stable per route: a screen's effect that sets a snap runs once, then the handle rules.
  const setSnap = useCallback((next: Snap) => setSnapState({ key: routeKey, snap: next }), [routeKey]);
  const sheet = useMemo(() => ({ snap, setSnap }), [snap, setSnap]);

  // The top band's height: the full sheet stops below it (shell.css --overlay-top-h).
  useLayoutEffect(() => {
    const top = topRef.current;
    const shell = shellRef.current;
    if (!top || !shell) return;
    const report = () => {
      const height = Math.round(top.getBoundingClientRect().height);
      shell.style.setProperty("--overlay-top-h", `${height}px`);
      setTopReserved(height);
    };
    report();
    if (typeof ResizeObserver === "undefined") return;
    // Resizing the sheet from inside this callback would re-trigger the sheet's own
    // observer in the same frame ("ResizeObserver loop"); apply it on the next frame.
    let frame = 0;
    const observer = new ResizeObserver(() => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(report);
    });
    observer.observe(top);
    return () => {
      cancelAnimationFrame(frame);
      observer.disconnect();
    };
  }, []);

  // Every screen opens at its top, whatever the previous one was scrolled to.
  useLayoutEffect(() => {
    if (mainRef.current) mainRef.current.scrollTop = 0;
  }, [routeKey]);

  // Move focus to the new screen on navigation (not on first load, unless it asks).
  const first = useRef(true);
  useEffect(() => {
    if (first.current) {
      first.current = false;
      const autofocus = mainRef.current?.querySelector<HTMLElement>("[data-autofocus]");
      autofocus?.focus({ preventScroll: true });
      return;
    }
    focusScreen(mainRef.current);
  }, [routeKey]);

  // Locate only where a position helps (Home, Navigate, choosing on the map), only when
  // location can work at all, and never over a full sheet (no map left to show).
  const locateHelps = route.name === "home" || route.name === "navigate" || picking;
  const showLocate = locateHelps && snap !== "full" && location.availability !== "unavailable";

  return (
    <SheetContext.Provider value={sheet}>
      <div className="shell" ref={shellRef}>
        <a
          className="skip-link"
          href="#main"
          onClick={(event) => {
            event.preventDefault();
            focusScreen(mainRef.current);
          }}
        >
          {t("app.skipToContent")}
        </a>
        <div className="map-layer">
          <MapHost attribution={false} />
        </div>
        <div className="overlay-top" ref={topRef}>
          <Banners fixtureMode={fixtureMode} status={status} />
          <div className="top-row">
            {route.name !== "home" && (
              <button type="button" className="icon-button floating back-button" aria-label={t("nav.back")} onClick={() => back(backFallback(route))}>
                <span className="mirror" aria-hidden="true">
                  →
                </span>
              </button>
            )}
            <MapAttribution inline />
          </div>
        </div>
        <Sheet
          snap={snap}
          setSnap={setSnap}
          topReserved={topReserved}
          locate={showLocate ? <LocateButton /> : undefined}
          corner={
            route.name === "home" ? (
              <a className="icon-button quiet settings-link" href={hrefFor({ name: "settings" })} aria-label={t("screen.settings")}>
                <span aria-hidden="true">⚙</span>
              </a>
            ) : undefined
          }
        >
          <main id="main" ref={mainRef} className="sheet-content" tabIndex={-1}>
            <Screen route={route} />
          </main>
        </Sheet>
      </div>
    </SheetContext.Provider>
  );
}
