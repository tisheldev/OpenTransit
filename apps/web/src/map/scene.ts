import { useEffect, useSyncExternalStore } from "react";

// What the map draws (design: Surface, "the map draws whatever the sheet is about").
// Screens publish a scene; the map (src/map/MapView.tsx, lazy) subscribes. Nothing here
// imports MapLibre, so screens and tests never pull the map chunk.

export type LonLat = [longitude: number, latitude: number];

export interface MapRouteLeg {
  kind: "walk" | "transit";
  /** API leg mode (`WALK`, `BUS`, `RAIL`, …). */
  mode: string;
  /** Leg geometry; null for a time-only walk, which draws no line (design: S3.2). */
  coordinates: LonLat[] | null;
  from: LonLat;
  to: LonLat;
  /** Line number or train destination, shown beside the line. */
  label: string | null;
  /** Highlighted leg (the current step while navigating). */
  active?: boolean;
}

export interface MapPin {
  id: string;
  role: "origin" | "destination" | "stop" | "transfer";
  position: LonLat;
  label: string;
}

export interface MapUser {
  position: LonLat;
  accuracyMeters: number | null;
}

/** A place to centre on at a zoom (Home's last place, the pick-on-map start). */
export interface MapFocus {
  center: LonLat;
  zoom: number;
}

export interface MapScene {
  route: MapRouteLeg[];
  pins: MapPin[];
  user: MapUser | null;
  /**
   * fit: frame route and pins (with nothing to frame, go to `focus` or the default view);
   * follow: keep the user centred; keep: leave the camera.
   */
  camera: "fit" | "follow" | "keep";
  /** "Choose on map": a centre pin is shown and the centre is reported via setMapCenter. */
  pick: boolean;
  /** Optional: where a "fit" camera goes when there are no route or pins to frame. */
  focus?: MapFocus | null;
}

export const emptyScene: MapScene = { route: [], pins: [], user: null, camera: "keep", pick: false };

interface MapState {
  scene: MapScene;
  /** Pixels at the bottom covered by the sheet, so fitting keeps content visible. */
  bottomInset: number;
  /** Latest map centre (pick mode); null until the map reports one. */
  center: LonLat | null;
  /** Bumped by requestLocate(); the map recentres on the user when it changes. */
  locateRequest: number;
  /**
   * A one-off fix from the Locate button on a screen whose scene has no user (Home, pick
   * on map). Memory only, never stored; dropped when the next scene is published.
   */
  located: MapUser | null;
}

const initialState: MapState = { scene: emptyScene, bottomInset: 0, center: null, locateRequest: 0, located: null };
let state: MapState = initialState;
const listeners = new Set<() => void>();

function update(change: Partial<MapState>): void {
  state = { ...state, ...change };
  for (const listener of listeners) listener();
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function getMapState(): MapState {
  return state;
}

export function setMapScene(scene: MapScene): void {
  update({ scene, located: null });
}

export function setBottomInset(px: number): void {
  if (px !== state.bottomInset) update({ bottomInset: px });
}

export function setMapCenter(center: LonLat): void {
  update({ center });
}

export function requestLocate(): void {
  update({ locateRequest: state.locateRequest + 1 });
}

/** Show a one-off fix (Locate on a scene without a user) and recentre on it. */
export function showLocated(user: MapUser): void {
  update({ located: user, locateRequest: state.locateRequest + 1 });
}

export function useMapState(): MapState {
  return useSyncExternalStore(subscribe, getMapState, getMapState);
}

/** One derived value (return a primitive): re-renders only when it changes. */
export function useMapSelector<T>(select: (state: MapState) => T): T {
  const read = () => select(state);
  return useSyncExternalStore(subscribe, read, read);
}

/**
 * Publish a scene while the calling screen is mounted. Pass a memoised scene (useMemo);
 * the previous scene is cleared on unmount so a screen never leaves stale drawings.
 */
export function usePublishScene(scene: MapScene): void {
  useEffect(() => {
    setMapScene(scene);
    return () => {
      if (getMapState().scene === scene) setMapScene(emptyScene);
    };
  }, [scene]);
}

/** Reset between tests. */
export function resetMapState(): void {
  state = initialState;
  for (const listener of listeners) listener();
}
