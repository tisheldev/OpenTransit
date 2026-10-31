import {
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
import { MapHost } from "../map/MapHost";
import { requestLocate, setBottomInset } from "../map/scene";
import { back, useRoute } from "../router";
import { Screen } from "../screens/screens";
import { Banners } from "./Banners";
import { SheetContext, SNAP_FRACTION, defaultSnap, nearestSnap, stepSnap, type Snap } from "./sheet";

// The surface (design: Surface): the map full-bleed behind, one bottom sheet that holds
// every screen, and only two floating controls, Back and Locate. No tabs, no menus.

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

function Sheet({ snap, setSnap, children }: { snap: Snap; setSnap: (snap: Snap) => void; children: ReactNode }) {
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
    const observer = new ResizeObserver(report);
    observer.observe(element);
    return () => observer.disconnect();
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
    const max = SNAP_FRACTION.full * viewportHeight();
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
      <button
        type="button"
        className="icon-button floating sheet-locate"
        aria-label={t("nav.locate")}
        onClick={() => requestLocate()}
      >
        <span aria-hidden="true">◎</span>
      </button>
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
      </div>
      {children}
    </section>
  );
}

/** Focus the new screen: its autofocus field if it has one, else its heading. */
function focusScreen(main: HTMLElement | null): void {
  if (!main) return;
  const target = main.querySelector<HTMLElement>("[data-autofocus]") ?? main.querySelector<HTMLElement>("h1");
  if (!target) {
    main.focus();
    return;
  }
  if (target.tagName === "H1" && !target.hasAttribute("tabindex")) target.setAttribute("tabindex", "-1");
  target.focus();
}

export function Shell({ fixtureMode }: { fixtureMode: boolean }) {
  const { t } = useI18n();
  const route = useRoute();
  const painted = useAfterFirstPaint();
  const status = useStatus({ enabled: painted });
  const mainRef = useRef<HTMLElement>(null);
  const shellRef = useRef<HTMLDivElement>(null);
  const topRef = useRef<HTMLDivElement>(null);
  const routeKey = JSON.stringify(route);

  // Each route opens at its own snap; a screen may change it afterwards (pick on map).
  const [snapState, setSnapState] = useState<{ key: string; snap: Snap }>(() => ({ key: routeKey, snap: defaultSnap(route.name) }));
  let snap = snapState.snap;
  if (snapState.key !== routeKey) {
    snap = defaultSnap(route.name);
    setSnapState({ key: routeKey, snap });
  }
  const sheet = useMemo(
    () => ({ snap, setSnap: (next: Snap) => setSnapState({ key: routeKey, snap: next }) }),
    [snap, routeKey],
  );

  // The map attribution sits just below whatever floats at the top (banners, Back),
  // so neither those nor the sheet ever cover it (map.css --map-attribution-top).
  useLayoutEffect(() => {
    const top = topRef.current;
    const shell = shellRef.current;
    if (!top || !shell) return;
    const report = () => shell.style.setProperty("--map-attribution-top", `${Math.round(top.getBoundingClientRect().height)}px`);
    report();
    if (typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(report);
    observer.observe(top);
    return () => observer.disconnect();
  }, []);

  // Move focus to the new screen on navigation (not on first load, unless it asks).
  const first = useRef(true);
  useEffect(() => {
    if (first.current) {
      first.current = false;
      const autofocus = mainRef.current?.querySelector<HTMLElement>("[data-autofocus]");
      autofocus?.focus();
      return;
    }
    focusScreen(mainRef.current);
  }, [routeKey]);

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
          <MapHost />
        </div>
        <div className="overlay-top" ref={topRef}>
          <Banners fixtureMode={fixtureMode} status={status} />
          {route.name !== "home" && (
            <button type="button" className="icon-button floating back-button" aria-label={t("nav.back")} onClick={() => back()}>
              <span className="mirror" aria-hidden="true">
                →
              </span>
            </button>
          )}
        </div>
        <Sheet snap={snap} setSnap={sheet.setSnap}>
          <main id="main" ref={mainRef} className="sheet-content" tabIndex={-1}>
            <Screen route={route} />
          </main>
        </Sheet>
      </div>
    </SheetContext.Provider>
  );
}
