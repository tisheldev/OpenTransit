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
  /** The ride's operator, for its line colour (look of 11 November 2026). */
  operatorId?: string | null;
  operatorName?: string | null;
  /**
   * How the leg is drawn (boards, 11 November 2026): "normal" in its colour with a pale
   * outline; "faded" thinner at .6 in its own colour (an option not chosen, a line not
   * picked); "travelled" in grey (the part of a ride already behind the passenger).
   */
  tone?: "normal" | "faded" | "travelled" | "quiet";
  /**
   * "quiet" (stops-and-lines boards Stop and Ride, 14 November 2026): the lines not chosen
   * at a stop, 5 px in their own colour at `quietOpacity` (Stop .45, Ride .4) with no edge.
   */
  quietOpacity?: number;
}

/** A line badge on a map tag (the operator picks its colour, the mode its vehicle icon). */
export interface MapTagLine {
  mode: string;
  label: string;
  operatorId?: string | null;
  operatorName?: string | null;
}

/**
 * A label pinned to a place on the map (boards: a stop's next departure, an option's
 * arrival time, a destination name, "יורדים כאן"). "strong" is ink on the page colour
 * (the one that matters), "plain" an outlined tag, "faded" a muted one for options not
 * chosen. With onSelect it is a button (tap a faded option to choose it).
 */
export interface MapTag {
  id: string;
  position: LonLat;
  kind: "strong" | "plain" | "faded";
  text?: string;
  line?: MapTagLine;
  /** A CSS colour for the outline (a faded option's own line colour). */
  accent?: string;
  /** Spoken name when the visible text alone is not enough. */
  ariaLabel?: string;
  onSelect?: () => void;
  /** Where the tag sits relative to its point: above it (default) or centred on it. */
  anchor?: "above" | "center" | "below";
  /**
   * Drawn as a bare glyph centred on the point instead of a tag (stops-and-lines boards:
   * the chosen line's direction chevron, turned to its bearing in degrees from north).
   */
  glyph?: { kind: "chevron"; bearing: number };
}

/** A stop drawn as a large round pin with a stop sign (boards: Home, Stop, Bus didn't come). */
export interface MapStopPin {
  id: string;
  position: LonLat;
  /** The stop the panel is about: ink filled; others are outlined. */
  selected?: boolean;
  ariaLabel: string;
  onSelect?: () => void;
  /**
   * "sign": the stops-and-lines marker G (a sign on a pole, its kerb dot on the point;
   * src/map/stops/markers.tsx, the stops layer's own) instead of the round pin. `rail`
   * draws a station's sign. The pole points away from the road as the stops layer knows
   * it (the map's streets, the stop's direction from stops by area), else from
   * `bearingDegrees` (the stop item's, API-C6); with neither, the sign is centred.
   */
  look?: "sign";
  rail?: boolean;
  bearingDegrees?: number | null;
}

/** A stop the screen already knows (Home's nearby answer), drawn before the area request answers. */
export interface MapKnownStop {
  stopId: string;
  name: string | null;
  latitude: number;
  longitude: number;
  /** API-C6; undefined from an API without it. */
  mode?: string | null;
  bearingDegrees?: number | null;
}

/** A stop's next line, for the flag tag on its sign (Home: from its one nearby-departures answer). */
export interface MapStopNext {
  line: MapTagLine;
  /** Whole minutes until it leaves (0: now). */
  minutes: number;
  /** What the tag says after the badge: "4 דק׳", "עכשיו". */
  text: string;
}

/**
 * The stops layer (stops and lines design, 12 November 2026: marker G at three zoom levels,
 * groups, next-line tags). Absent: no stops layer and no request for it (Navigate, Search,
 * Settings). "full": every level, tags, tappable (Home). "quiet": only when zoomed in close,
 * drawn quieter, never tappable, no tags, so it never competes with a route (Choose and
 * Route details).
 */
export interface MapStopsLayer {
  mode: "full" | "quiet";
  /** The stop the panel is about: drawn bright and larger, its tag pale. */
  chosenStopId?: string | null;
  /** Next lines by stop id, for the tags (a couple at most show, the chosen stop's first). */
  next?: Readonly<Record<string, MapStopNext>>;
  known?: readonly MapKnownStop[];
  /** A sign or tag tapped (a full layer without it draws stops that cannot be tapped). */
  onSelectStop?: (stopId: string) => void;
  /** A group tapped: the map has zoomed in on it; the screen may list its stops (board 9). */
  onOpenGroup?: (stops: MapKnownStop[]) => void;
  /** The stops of the group opened (board 9): ringed on the map. */
  openGroup?: readonly string[] | null;
}

/** A dashed circle around a place: Home's 5-minute walk around the passenger. */
export interface MapRing {
  center: LonLat;
  radiusMeters: number;
}

export interface MapPin {
  id: string;
  role: "origin" | "destination" | "stop" | "transfer";
  position: LonLat;
  label: string;
  /**
   * Stops and transfers: the API mode of the ride boarded there, for the ring's colour.
   * Optional: without it the map uses the drawn ride that boards or ends at the pin.
   */
  mode?: string;
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
  /** Labels pinned to places (boards); drawn over the map as buttons or text. */
  tags?: MapTag[];
  /** Large stop pins (boards: Home's nearby stops, a tapped stop, Bus didn't come). */
  stopPins?: MapStopPin[];
  /** A dashed walking ring (Home). */
  ring?: MapRing | null;
  /**
   * Optional: a "fit" camera frames only these points (a tapped step's leg, the stretch
   * before the exit stop) instead of the whole scene; null or empty frames everything.
   */
  fitTo?: LonLat[] | null;
  /**
   * Optional: a "fit" camera frames once per key. A screen that republishes its scene as
   * times tick (Home's next departures) passes a key that changes only when what it shows
   * changes, so the passenger's own panning is not undone every minute.
   */
  cameraKey?: string;
  /** Controls float over the top of the map (close, "כל המסלול"): fitting keeps clear of them. */
  topControls?: boolean;
  /** The stops layer; absent, none is drawn or requested. */
  stops?: MapStopsLayer | null;
}

/** Choose and Route details: the stops layer only zoomed in close, quieter (design, "During a journey"). */
export const QUIET_STOPS: MapStopsLayer = { mode: "quiet" };

export const emptyScene: MapScene = { route: [], pins: [], user: null, camera: "keep", pick: false };

interface MapState {
  scene: MapScene;
  /** Pixels at the bottom covered by the sheet, so fitting keeps content visible. */
  bottomInset: number;
  /**
   * Pixels covered at the map's left and right edges (physical sides: the map is never
   * mirrored) by a panel beside it: the wide-screen layout (board 8). Zero on a phone.
   */
  sideInset: { left: number; right: number };
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

const NO_SIDE_INSET = { left: 0, right: 0 };
const initialState: MapState = {
  scene: emptyScene,
  bottomInset: 0,
  sideInset: NO_SIDE_INSET,
  center: null,
  locateRequest: 0,
  located: null,
};
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

export function setSideInset(left: number, right: number): void {
  if (left !== state.sideInset.left || right !== state.sideInset.right) {
    update({ sideInset: left === 0 && right === 0 ? NO_SIDE_INSET : { left, right } });
  }
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
