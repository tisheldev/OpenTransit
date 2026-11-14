import type { Map as MapLibreMap } from "maplibre-gl";
import { useCallback, useEffect, useMemo, useRef, useState, useSyncExternalStore, type CSSProperties } from "react";
import { listStops, type StopMode } from "../../api/endpoints";
import { useI18n } from "../../i18n/I18nProvider";
import { basemapRole, type StyleLayerJson } from "../layers";
import type { LonLat, MapKnownStop, MapStopsLayer } from "../scene";
import { AreaStops, isStationMode, keeps, toAreaStop, type AreaStop, type Bounds } from "./area";
import {
  centredBox,
  CHOSEN_PX,
  dotBox,
  groupMarkers,
  groupSize,
  overlaps,
  placeTags,
  preferredTagSide,
  sideFromBearing,
  sideFromStreets,
  signBox,
  SIGN_PX,
  SQUARE_PX,
  STATION_PX,
  STREET_SEARCH_METRES,
  toLocalMetres,
  ZOOM_SIGNS,
  ZOOM_STOPS,
  zoomLevel,
  type Box,
  type PlacedTag,
  type PoleSide,
  type Px,
  type StopsLevel,
  type StreetLine,
  type TagRequest,
} from "./geometry";
import { Hit, Pole, SignFace, TagBadge, ZOOM_IN_PATH, type SignSide } from "./markers";
import { setSettledView } from "./view";
import "./stops.css";

// The stops layer over the map (stops and lines design, 12 November 2026). It asks for
// stops by area when the map settles (src/map/stops/area.ts, kept for the session), lays
// them out once per settle (three zoom levels, groups, poles, a couple of tags), and while
// the map moves only re-projects what it drew, so stops stay glued to the street. Drawn as
// HTML over the canvas so the marker matches the canvas to the pixel and taps reach real
// buttons; every fact on it is also in the sheet as text.

let source = new AreaStops((bbox, modes, paging, signal) =>
  listStops({ bbox, modes: modes as readonly StopMode[] | null }, paging, signal),
);

/** A fresh session cache (tests). */
export function resetAreaStopsForTests(list?: ConstructorParameters<typeof AreaStops>[0]): AreaStops {
  source = new AreaStops(list ?? ((bbox, modes, paging, signal) => listStops({ bbox, modes: modes as readonly StopMode[] | null }, paging, signal)));
  streetSides.clear();
  return source;
}

/** Below this zoom not even stations are asked for (the whole country fits in a few tiles anyway). */
const MIN_STATION_ZOOM = 7;
/** Tags return this long after the map stops (MarkerMotion: "a quarter-second after it stops"). */
const TAG_RETURN_MS = 250;
const ENTER_CLEAR_MS = 320;

const reducedMotion = () => typeof window.matchMedia === "function" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

/** The side found from the map's streets, per stop, with the zoom it was read at. */
const streetSides = new Map<string, { side: PoleSide | null; zoom: number }>();

interface View {
  zoom: number;
  bounds: Bounds;
  center: LonLat;
  width: number;
  height: number;
  /** The visible map: below the top band, above the sheet. */
  visible: Box;
}

function readView(map: MapLibreMap, topInset: number, bottomInset: number): View {
  const element = map.getContainer();
  const width = element.clientWidth;
  const height = element.clientHeight;
  const bottom = Math.max(topInset + 1, height - Math.min(bottomInset, Math.round(height * 0.75)));
  const corners = [
    [0, topInset],
    [width, topInset],
    [0, bottom],
    [width, bottom],
  ].map((point) => map.unproject(point as [number, number]));
  const lngs = corners.map((point) => point.lng);
  const lats = corners.map((point) => point.lat);
  const centre = map.unproject([width / 2, (topInset + bottom) / 2]);
  return {
    zoom: map.getZoom(),
    bounds: { west: Math.min(...lngs), east: Math.max(...lngs), south: Math.min(...lats), north: Math.max(...lats) },
    center: [centre.lng, centre.lat],
    width,
    height,
    visible: { left: 0, top: topInset, right: width, bottom },
  };
}

function grow(bounds: Bounds, by: number): Bounds {
  const dx = (bounds.east - bounds.west) * by;
  const dy = (bounds.north - bounds.south) * by;
  return { west: bounds.west - dx, east: bounds.east + dx, south: bounds.south - dy, north: bounds.north + dy };
}

/** The level the layer draws at, or null for none (a quiet layer below street zoom). */
function levelFor(layer: MapStopsLayer, zoom: number): StopsLevel | null {
  if (layer.mode === "quiet") return zoom >= ZOOM_SIGNS ? "signs" : null;
  return zoomLevel(zoom);
}

function roadLayerIds(map: MapLibreMap): string[] {
  return (map.getStyle()?.layers ?? [])
    .filter((layer) => layer.type === "line" && basemapRole(layer as unknown as StyleLayerJson) === "road")
    .map((layer) => layer.id);
}

const metresPerPixel = (lat: number, zoom: number) => (40_075_016.686 * Math.cos((lat * Math.PI) / 180)) / (512 * 2 ** zoom);

/** Reads the streets drawn around each stop and keeps the side they give (sideFromStreets). */
function readStreetSides(map: MapLibreMap, stops: readonly AreaStop[], zoom: number): void {
  const layers = roadLayerIds(map);
  if (layers.length === 0 || !map.areTilesLoaded()) return;
  for (const stop of stops) {
    const known = streetSides.get(stop.stopId);
    if (known && known.zoom >= zoom - 0.5) continue;
    const at = map.project([stop.longitude, stop.latitude]);
    const radius = STREET_SEARCH_METRES / metresPerPixel(stop.latitude, zoom);
    const features = map.queryRenderedFeatures(
      [
        [at.x - radius, at.y - radius],
        [at.x + radius, at.y + radius],
      ],
      { layers },
    );
    const lines: StreetLine[] = [];
    for (const feature of features) {
      const geometry = feature.geometry;
      const parts = geometry.type === "LineString" ? [geometry.coordinates] : geometry.type === "MultiLineString" ? geometry.coordinates : [];
      for (const part of parts as number[][][]) lines.push(part.map((point) => toLocalMetres(stop, point)));
    }
    streetSides.set(stop.stopId, { side: sideFromStreets(lines, stop.bearingDegrees, map.getBearing()), zoom });
  }
}

/** The side a stop's pole points to: the map's streets, else the API's direction, else none. */
function sideOf(stop: AreaStop, mapBearing: number): PoleSide | null {
  return streetSides.get(stop.stopId)?.side ?? sideFromBearing(stop.bearingDegrees, mapBearing);
}

// ---------------------------------------------------------------------------------------
// Layout (once per settle)

type Item =
  | { kind: "sign"; key: string; id: string; anchor: LonLat; side: PoleSide | null; chosen: boolean; box: Box; dot: Box | null }
  | { kind: "square"; key: string; id: string; anchor: LonLat; box: Box }
  | { kind: "station"; key: string; id: string; anchor: LonLat; box: Box; label: { text: string; toward: "left" | "right" } | null }
  | { kind: "group"; key: string; ids: string[]; anchor: LonLat; lifted: boolean; legs: Px[]; box: Box };

interface Layout {
  level: StopsLevel | null;
  items: Item[];
  /** Screen points at layout time, for the split and merge animations. */
  at: Map<string, Px>;
}

const anchorOf = (stop: AreaStop): LonLat => [stop.longitude, stop.latitude];

function layoutStops(
  map: MapLibreMap,
  view: View,
  level: StopsLevel | null,
  stops: readonly AreaStop[],
  stations: readonly AreaStop[],
  chosenId: string | null,
  dir: "rtl" | "ltr",
): Layout {
  const items: Item[] = [];
  const at = new Map<string, Px>();
  if (level === null) return { level, items, at };
  const project = (anchor: LonLat): Px => {
    const point = map.project(anchor);
    return { x: point.x, y: point.y };
  };
  const bearing = map.getBearing();

  // Stations: the purple sign, centred (a station's side is never guessed), with its name.
  const stationBoxes: Box[] = [];
  for (const station of stations) {
    const p = project(anchorOf(station));
    const box = centredBox(p, STATION_PX);
    stationBoxes.push(box);
    at.set(`t:${station.stopId}`, p);
    items.push({ kind: "station", key: `t:${station.stopId}`, id: station.stopId, anchor: anchorOf(station), box, label: null });
  }

  if (level !== "stations") {
    const chosen = chosenId ? stops.find((stop) => stop.stopId === chosenId) : undefined;
    const others = stops.filter((stop) => stop !== chosen);
    const inputs = others.map((stop) => ({ id: stop.stopId, at: project(anchorOf(stop)), side: level === "signs" ? sideOf(stop, bearing) : null }));
    const byId = new Map(others.map((stop) => [stop.stopId, stop]));
    const grouping = groupMarkers(inputs, level);
    for (const single of grouping.singles) {
      const stop = byId.get(single.id)!;
      at.set(`s:${single.id}`, single.at);
      if (level === "grouped") {
        items.push({ kind: "square", key: `s:${single.id}`, id: single.id, anchor: anchorOf(stop), box: centredBox(single.at, SQUARE_PX) });
      } else {
        items.push({ kind: "sign", key: `s:${single.id}`, id: single.id, anchor: anchorOf(stop), side: single.side, chosen: false, box: signBox(single.at, single.side), dot: dotBox(single.at, single.side) });
      }
    }
    for (const group of grouping.groups) {
      const members = group.ids.map((id) => byId.get(id)!);
      const anchor: LonLat = [
        members.reduce((sum, stop) => sum + stop.longitude, 0) / members.length,
        members.reduce((sum, stop) => sum + stop.latitude, 0) / members.length,
      ];
      const lifted = level === "signs";
      const key = `g:${[...group.ids].sort().join(",")}`;
      at.set(key, group.at);
      // The anchor is the members' centre; a lifted count stands 18 px above it on their kerb dots.
      const centre = project(anchor);
      items.push({
        kind: "group",
        key,
        ids: group.ids,
        anchor,
        lifted,
        legs: lifted ? group.kerbs.map((kerb) => ({ x: kerb.x - centre.x, y: kerb.y - centre.y })) : [],
        box: centredBox(group.at, groupSize(group.ids.length)),
      });
    }
    if (chosen) {
      const p = project(anchorOf(chosen));
      const side = sideOf(chosen, bearing);
      at.set(`s:${chosen.stopId}`, p);
      items.push({ kind: "sign", key: `s:${chosen.stopId}`, id: chosen.stopId, anchor: anchorOf(chosen), side, chosen: true, box: signBox(p, side, CHOSEN_PX), dot: dotBox(p, side) });
    }
  }

  // Station names where they fit: toward the end of the reading direction, else the other side.
  const taken: Box[] = items.filter((item) => item.kind !== "station").map((item) => item.box);
  taken.push(...stationBoxes);
  for (const item of items) {
    if (item.kind !== "station") continue;
    const stop = stations.find((station) => station.stopId === item.id);
    const text = stop?.name?.trim();
    if (!text) continue;
    const width = text.length * 7 + 4;
    const p = at.get(item.key)!;
    const first = preferredTagSide(null, dir);
    for (const toward of [first, first === "left" ? "right" : "left"] as const) {
      const box: Box =
        toward === "left"
          ? { left: p.x - 15 - width, right: p.x - 15, top: p.y - 9, bottom: p.y + 9 }
          : { left: p.x + 15, right: p.x + 15 + width, top: p.y - 9, bottom: p.y + 9 };
      const inside = box.left >= view.visible.left && box.right <= view.visible.right;
      if (inside && !taken.some((other) => other !== item.box && overlaps(box, other))) {
        item.label = { text, toward };
        taken.push(box);
        break;
      }
    }
  }
  return { level, items, at };
}

// ---------------------------------------------------------------------------------------
// Rendering

interface Enter {
  kind: "grow" | "split" | "group-in" | "choosing";
  dx?: number;
  dy?: number;
}

interface Ghost {
  key: string;
  item: Item;
  kind: "merge" | "group-out";
  dx: number;
  dy: number;
}

function transformAt(map: MapLibreMap, anchor: LonLat, lift = 0): string {
  const point = map.project(anchor);
  return `translate(${Math.round(point.x)}px, ${Math.round(point.y - lift)}px)`;
}

const sideClass = (side: PoleSide | null): SignSide => side ?? "centre";

export function StopsLayer({
  map,
  layer,
  topInset,
  bottomInset,
}: {
  map: MapLibreMap;
  layer: MapStopsLayer;
  topInset: number;
  bottomInset: number;
}) {
  const { t, dir } = useI18n();
  const [view, setView] = useState<View>(() => readView(map, topInset, bottomInset));
  const [moving, setMoving] = useState(false);
  const [streetTick, setStreetTick] = useState(0);
  const elements = useRef(new Map<string, { element: HTMLElement; anchor: LonLat; lift: number; inside: boolean }>());
  const insets = useRef({ topInset, bottomInset });
  useEffect(() => {
    insets.current = { topInset, bottomInset };
  }, [topInset, bottomInset]);

  // The view is read when the map settles (and when the sheet changes what is visible).
  useEffect(() => {
    let timer: ReturnType<typeof setTimeout> | undefined;
    const onStart = () => {
      if (timer) clearTimeout(timer);
      setMoving(true);
    };
    const onEnd = () => {
      setView(readView(map, insets.current.topInset, insets.current.bottomInset));
      if (timer) clearTimeout(timer);
      timer = setTimeout(() => setMoving(false), TAG_RETURN_MS);
    };
    const onIdle = () => setStreetTick((n) => n + 1);
    map.on("movestart", onStart);
    map.on("moveend", onEnd);
    map.on("idle", onIdle);
    map.on("resize", onEnd);
    return () => {
      if (timer) clearTimeout(timer);
      map.off("movestart", onStart);
      map.off("moveend", onEnd);
      map.off("idle", onIdle);
      map.off("resize", onEnd);
    };
  }, [map]);
  // A sheet that moves changes what is visible: read the view again (during render, not in an effect).
  const insetKey = `${topInset}:${bottomInset}`;
  const [readFor, setReadFor] = useState(insetKey);
  if (readFor !== insetKey) {
    setReadFor(insetKey);
    setView(readView(map, topInset, bottomInset));
  }
  useEffect(() => {
    setSettledView({ center: view.center, zoom: view.zoom, bounds: view.bounds });
  }, [view]);
  useEffect(() => () => setSettledView(null), []);

  const level = levelFor(layer, view.zoom);

  // Ask for what the settled view lacks (a little beyond it, so a short pan finds stops waiting).
  useEffect(() => {
    const ahead = grow(view.bounds, 0.15);
    if (view.zoom >= MIN_STATION_ZOOM && (layer.mode === "full" || level !== null)) source.want("stations", ahead);
    if (level === "grouped" || level === "signs") source.want("stops", ahead);
  }, [view, level, layer.mode]);

  const version = useSyncExternalStore(source.subscribe, source.getVersion, source.getVersion);
  const drawn = useMemo(() => grow(view.bounds, 0.3), [view]);
  const { stops, stations } = useMemo(() => {
    void version;
    const byId = new Map<string, AreaStop>();
    for (const stop of source.stopsIn("stops", drawn)) byId.set(stop.stopId, stop);
    for (const known of layer.known ?? []) {
      const stop = knownAsArea(known);
      if (byId.has(stop.stopId) || isStationMode(stop.mode) || !keeps("stops", stop)) continue;
      const inside = stop.longitude >= drawn.west && stop.longitude <= drawn.east && stop.latitude >= drawn.south && stop.latitude <= drawn.north;
      if (inside) byId.set(stop.stopId, stop);
    }
    return { stops: [...byId.values()], stations: source.stopsIn("stations", drawn) };
  }, [version, drawn, layer.known]);

  // Street sides need the drawn streets: read them once the tiles are in (each idle).
  useMemo(() => {
    void streetTick;
    if (level === "signs") readStreetSides(map, stops, view.zoom);
  }, [map, stops, level, view.zoom, streetTick]);

  const chosenId = layer.chosenStopId ?? null;
  const layout = useMemo(() => {
    void streetTick;
    return layoutStops(map, view, level, stops, stations, chosenId, dir);
  }, [map, view, level, stops, stations, chosenId, dir, streetTick]);

  const stopById = useMemo(() => new Map([...stops, ...stations].map((stop) => [stop.stopId, stop])), [stops, stations]);

  // --- tags: measured, then placed (the chosen stop's first) --------------------------------
  const full = layer.mode === "full";
  const candidates = useMemo(() => {
    if (!full || layout.level !== "signs" || !layer.next) return [];
    const signs = layout.items.filter((item): item is Extract<Item, { kind: "sign" }> => item.kind === "sign" && !!layer.next?.[item.id]);
    const centre = { x: view.width / 2, y: (view.visible.top + view.visible.bottom) / 2 };
    return signs
      .filter((item) => item.box.right > view.visible.left && item.box.left < view.visible.right && item.box.bottom > view.visible.top && item.box.top < view.visible.bottom)
      .sort((a, b) => Number(b.chosen) - Number(a.chosen) || dist(a.box, centre) - dist(b.box, centre))
      .slice(0, 6);
  }, [full, layout, layer.next, view]);
  // Each tag is measured off screen (its hidden twin's ref) before it is placed.
  const [widths, setWidths] = useState<Record<string, number>>({});
  const measured = useCallback(
    (id: string) => (element: HTMLElement | null) => {
      if (!element) return;
      const width = element.offsetWidth;
      setWidths((old) => (old[id] === width ? old : { ...old, [id]: width }));
    },
    [],
  );
  const tags = useMemo<PlacedTag[]>(() => {
    const requests: TagRequest[] = [];
    for (const item of candidates) {
      const next = layer.next?.[item.id];
      const width = next ? widths[widthKey(item.id, item.chosen, next)] : undefined;
      if (!width) continue;
      requests.push({ id: item.id, sign: item.box, side: item.side, width });
    }
    const obstacles = layout.items.flatMap((item) => {
      const boxes = [{ id: item.kind === "group" ? item.key : item.id, box: item.box }];
      if (item.kind === "sign" && item.dot) boxes.push({ id: item.id, box: item.dot });
      return boxes;
    });
    const visible = { left: view.visible.left + 4, right: view.visible.right - 4, top: view.visible.top + 4, bottom: view.visible.bottom - 4 };
    return placeTags(requests, obstacles, visible, dir);
  }, [candidates, widths, layout, view, dir, layer.next]);

  // --- enter and leave animations (MarkerMotion) -------------------------------------------
  // Worked out when a new layout arrives (during render, from the one before it).
  const [shown, setShown] = useState<{ layout: Layout | null; chosen: string | null }>({ layout: null, chosen: null });
  const [enter, setEnter] = useState<Record<string, Enter>>({});
  const [ghosts, setGhosts] = useState<Ghost[]>([]);
  if (shown.layout !== layout || shown.chosen !== chosenId) {
    const diff = diffLayouts(map, shown.layout, layout, shown.chosen, chosenId);
    setShown({ layout, chosen: chosenId });
    setEnter(diff.enters);
    setGhosts(diff.leaving);
  }
  useEffect(() => {
    if (Object.keys(enter).length === 0 && ghosts.length === 0) return;
    const timer = setTimeout(() => {
      setEnter({});
      setGhosts([]);
    }, ENTER_CLEAR_MS);
    return () => clearTimeout(timer);
  }, [enter, ghosts]);

  // --- following the map: re-project every frame while it moves ------------------------------
  useEffect(() => {
    let frame = 0;
    const reposition = () => {
      frame = 0;
      const { topInset: top, bottomInset: bottom } = insets.current;
      const element = map.getContainer();
      const height = element.clientHeight;
      const width = element.clientWidth;
      const visibleBottom = height - Math.min(bottom, Math.round(height * 0.75));
      for (const entry of elements.current.values()) {
        const point = map.project(entry.anchor);
        entry.element.style.transform = `translate(${Math.round(point.x)}px, ${Math.round(point.y - entry.lift)}px)`;
        // A stop coming into view grows out of its kerb dot (at most 180 ms).
        const inside = point.x >= -8 && point.x <= width + 8 && point.y >= top - 8 && point.y <= visibleBottom + 8;
        if (inside && !entry.inside) growIn(entry.element.firstElementChild as HTMLElement | null);
        entry.inside = inside;
      }
    };
    const schedule = () => {
      if (!frame) frame = requestAnimationFrame(reposition);
    };
    map.on("move", schedule);
    return () => {
      if (frame) cancelAnimationFrame(frame);
      map.off("move", schedule);
    };
  }, [map]);

  const register = useCallback(
    (key: string, anchor: LonLat, lift: number) => (element: HTMLElement | null) => {
      if (!element) {
        elements.current.delete(key);
        return;
      }
      const point = map.project(anchor);
      const { topInset: top, bottomInset: bottom } = insets.current;
      const container = map.getContainer();
      const visibleBottom = container.clientHeight - Math.min(bottom, Math.round(container.clientHeight * 0.75));
      const inside = point.x >= -8 && point.x <= container.clientWidth + 8 && point.y >= top - 8 && point.y <= visibleBottom + 8;
      elements.current.set(key, { element, anchor, lift, inside });
    },
    [map],
  );

  // --- taps ---------------------------------------------------------------------------------
  const select = layer.mode === "full" ? layer.onSelectStop : undefined;
  const onOpenGroup = layer.onOpenGroup;
  const openGroup = useCallback(
    (ids: string[]) => {
      const members = ids.map((id) => stopById.get(id)).filter((stop): stop is AreaStop => !!stop);
      if (members.length === 0) return;
      const west = Math.min(...members.map((stop) => stop.longitude));
      const east = Math.max(...members.map((stop) => stop.longitude));
      const south = Math.min(...members.map((stop) => stop.latitude));
      const north = Math.max(...members.map((stop) => stop.latitude));
      const { topInset: top, bottomInset: bottom } = insets.current;
      const container = map.getContainer();
      const covered = Math.min(bottom, Math.round(container.clientHeight * 0.75));
      let camera: { center?: unknown; zoom?: number } | undefined;
      try {
        camera = map.cameraForBounds(
          [
            [west, south],
            [east, north],
          ],
          { padding: { top: top + 64, bottom: covered + 48, left: 56, right: 56 }, maxZoom: 18 },
        );
      } catch {
        camera = undefined;
      }
      // Far enough in that the group opens into its stops (street zoom at least).
      const zoom = Math.min(18, Math.max(camera?.zoom ?? 0, map.getZoom() + 1, ZOOM_SIGNS + 1));
      map.easeTo({
        center: [(west + east) / 2, (south + north) / 2],
        zoom,
        offset: [0, (top - covered) / 2],
        duration: reducedMotion() ? 0 : 400,
      });
      onOpenGroup?.(members.map((stop) => ({ stopId: stop.stopId, name: stop.name, latitude: stop.latitude, longitude: stop.longitude, mode: stop.mode, bearingDegrees: stop.bearingDegrees })));
    },
    [map, stopById, onOpenGroup],
  );

  const nameOf = (id: string) => stopById.get(id)?.name?.trim() || t("stops.unnamed");
  const signLabel = (id: string) => {
    const next = layer.next?.[id];
    return next ? t("stops.sign.next", { stop: nameOf(id), line: next.line.label, minutes: next.minutes }) : t("stops.sign", { stop: nameOf(id) });
  };

  const placedById = new Map(tags.map((tag) => [tag.id, tag]));
  const ring = useMemo(() => openRing(map, layer.openGroup ?? null, stopById, view), [map, layer.openGroup, stopById, view]);

  const renderItem = (item: Item, ghost?: Ghost) => {
    const key = ghost ? ghost.key : item.key;
    const enterState = ghost ? undefined : enter[item.key];
    const bodyClass = ["ot-stop__body"];
    const style: CSSProperties = {};
    if (ghost) {
      bodyClass.push(ghost.kind === "merge" ? "ot-stop__body--merge" : "ot-stop__body--group-out");
      Object.assign(style, { "--to-x": `${ghost.dx}px`, "--to-y": `${ghost.dy}px` });
    } else if (enterState?.kind === "grow") bodyClass.push("ot-stop__body--grow");
    else if (enterState?.kind === "split") {
      bodyClass.push("ot-stop__body--split");
      Object.assign(style, { "--from-x": `${enterState.dx ?? 0}px`, "--from-y": `${enterState.dy ?? 0}px` });
    } else if (enterState?.kind === "group-in") bodyClass.push("ot-stop__body--group-in");
    const tap = ghost ? undefined : select;

    if (item.kind === "sign") {
      const side = sideClass(item.side);
      const tag = ghost ? undefined : placedById.get(item.id);
      const next = layer.next?.[item.id];
      const choosing = enterState?.kind === "choosing";
      const outer = ["ot-stop", `ot-stop--${side}`, item.chosen ? "ot-stop--chosen ot-stop--top" : "", choosing ? "ot-stop--choosing" : ""].filter(Boolean).join(" ");
      return (
        <div key={key} ref={ghost ? undefined : register(key, item.anchor, 0)} className={outer} style={{ transform: transformAt(map, item.anchor) }} data-stop-id={item.id}>
          <div className={bodyClass.join(" ")} style={style}>
            <Pole side={side} />
            {tag && next && (
              <button
                type="button"
                className={`ot-stop-tag ot-stop-tag--${tag.toward}${item.chosen ? " ot-stop-tag--chosen" : ""}`}
                style={{ insetInlineStart: `${tag.box.left - (layout.at.get(item.key)?.x ?? 0)}px`, insetBlockStart: `${tag.box.top - (layout.at.get(item.key)?.y ?? 0)}px` }}
                onClick={tap ? () => tap(item.id) : undefined}
                tabIndex={tap ? undefined : -1}
              >
                <TagBadge line={next.line} />
                <span dir={dir}>{next.text}</span>
              </button>
            )}
            {choosing && (
              <span className="ot-stop-hit ot-stop-was" aria-hidden="true" style={chosenWasStyle(side)}>
                <SignFace kind="stop" />
              </span>
            )}
            <Hit className="ot-stop-hit--sign" label={signLabel(item.id)} onSelect={tap ? () => tap(item.id) : undefined}>
              <SignFace kind="stop" chosen={item.chosen} />
            </Hit>
            {choosing && !reducedMotion() && <span className="ot-stop-ripple" style={rippleStyle(side)} aria-hidden="true" />}
          </div>
        </div>
      );
    }
    if (item.kind === "square") {
      return (
        <div key={key} ref={ghost ? undefined : register(key, item.anchor, 0)} className="ot-stop ot-stop--centre" style={{ transform: transformAt(map, item.anchor) }} data-stop-id={item.id}>
          <div className={bodyClass.join(" ")} style={style}>
            <Hit className="ot-stop-hit--square" label={signLabel(item.id)} onSelect={tap ? () => tap(item.id) : undefined}>
              <span className="ot-stop-square" aria-hidden="true" />
            </Hit>
          </div>
        </div>
      );
    }
    if (item.kind === "station") {
      return (
        <div key={key} ref={ghost ? undefined : register(key, item.anchor, 0)} className="ot-stop ot-stop--centre ot-stop--station" style={{ transform: transformAt(map, item.anchor) }} data-stop-id={item.id}>
          <div className={bodyClass.join(" ")} style={style}>
            {item.label && (
              <span className={`ot-stop-label ot-stop-label--${item.label.toward}`} dir={dir} aria-hidden="true">
                {item.label.text}
              </span>
            )}
            <Hit className="ot-stop-hit--station" label={t("stops.sign", { stop: nameOf(item.id) })} onSelect={tap ? () => tap(item.id) : undefined}>
              <SignFace kind="station" />
            </Hit>
          </div>
        </div>
      );
    }
    const lift = item.lifted ? 18 : 0;
    const large = item.ids.length >= 5;
    const size = large ? 36 : 30;
    return (
      <div key={key} ref={ghost ? undefined : register(key, item.anchor, lift)} className="ot-stop ot-stop--centre ot-stop--group" style={{ transform: transformAt(map, item.anchor, lift) }}>
        <div className={bodyClass.join(" ")} style={style}>
          {item.legs.length > 0 && <GroupLegs legs={item.legs} lift={lift} radius={size / 2} />}
          <Hit
            className="ot-stop-hit--group"
            label={t("stops.group", { count: item.ids.length })}
            onSelect={!ghost && layer.mode === "full" ? () => openGroup(item.ids) : undefined}
          >
            <span className={`ot-stop-group${large ? " ot-stop-group--large" : ""}`} aria-hidden="true">
              <bdi className="num">{item.ids.length}</bdi>
            </span>
          </Hit>
        </div>
      </div>
    );
  };

  const className = ["ot-stops", moving ? "ot-stops--moving" : "", layer.mode === "quiet" ? "ot-stops--quiet" : ""].filter(Boolean).join(" ");
  // Order: groups and squares, signs, stations, the chosen stop last (on top).
  const ordered = [...layout.items].sort((a, b) => rank(a) - rank(b));
  return (
    <div className={className} data-testid="stops-layer" data-level={layout.level ?? "off"} aria-hidden={layer.mode === "quiet" || undefined}>
      {ring && (
        <div key={`ring-${ring.anchor.join(",")}`} ref={register("ring", ring.anchor, 0)} className="ot-stop" style={{ transform: transformAt(map, ring.anchor) }}>
          <svg
            className="ot-stop-ring"
            width={ring.r * 2 + 4}
            height={ring.r * 2 + 4}
            style={{ insetInlineStart: -ring.r - 2, insetBlockStart: -ring.r - 2 }}
            aria-hidden="true"
          >
            <circle cx={ring.r + 2} cy={ring.r + 2} r={ring.r} />
          </svg>
        </div>
      )}
      {ghosts.map((ghost) => renderItem(ghost.item, ghost))}
      {ordered.map((item) => renderItem(item))}
      {/* Tags are measured before they are placed. */}
      <div aria-hidden="true">
        {candidates.map((item) => {
          const next = layer.next?.[item.id];
          if (!next) return null;
          return (
            <span
              key={`measure-${item.id}`}
              ref={measured(widthKey(item.id, item.chosen, next))}
              className={`ot-stop-tag ot-stop-tag--measure${item.chosen ? " ot-stop-tag--chosen" : ""}`}
              style={{ insetInlineStart: 0, insetBlockStart: 0 }}
            >
              <TagBadge line={next.line} />
              <span dir={dir}>{next.text}</span>
            </span>
          );
        })}
      </div>
      {layer.mode === "full" && layout.level === "stations" && (
        <p className="ot-stops-hint" style={{ top: `${topInset + 8}px` }} dir={dir}>
          <svg viewBox="0 0 20 20" aria-hidden="true">
            <circle cx="9" cy="9" r="6" />
            <path d={ZOOM_IN_PATH} />
          </svg>
          {t("stops.hint")}
        </p>
      )}
    </div>
  );
}

/** Which markers enter (grow, split from a count, a count forming, a stop being chosen) and which leave. */
function diffLayouts(
  map: MapLibreMap,
  before: Layout | null,
  layout: Layout,
  was: string | null,
  chosenId: string | null,
): { enters: Record<string, Enter>; leaving: Ghost[] } {
  const project = (anchor: LonLat): Px => {
    const p = map.project(anchor);
    return { x: p.x, y: p.y };
  };
  const enters: Record<string, Enter> = {};
  const leaving: Ghost[] = [];
  const beforeKeys = new Map((before?.items ?? []).map((item) => [item.key, item]));
  const nowKeys = new Set(layout.items.map((item) => item.key));
  const groupOf = new Map<string, Extract<Item, { kind: "group" }>>();
  for (const item of before?.items ?? []) if (item.kind === "group") for (const id of item.ids) groupOf.set(id, item);
  for (const item of layout.items) {
    if (beforeKeys.has(item.key)) {
      if (item.kind === "sign" && item.chosen && was !== chosenId && before) enters[item.key] = { kind: "choosing" };
      continue;
    }
    if (item.kind === "group") {
      enters[item.key] = { kind: "group-in" };
      // Its members slide into it from their own kerbs.
      const centre = project(item.anchor);
      for (const id of item.ids) {
        const single = beforeKeys.get(`s:${id}`);
        if (single && !nowKeys.has(single.key)) {
          const from = project(single.anchor);
          leaving.push({ key: `ghost:${single.key}`, item: single, kind: "merge", dx: centre.x - from.x, dy: centre.y - (item.lifted ? 18 : 0) - from.y });
        }
      }
      continue;
    }
    const from = groupOf.get(item.id);
    if (from && (item.kind === "sign" || item.kind === "square")) {
      const p = project(from.anchor);
      const own = project(item.anchor);
      enters[item.key] = { kind: "split", dx: p.x - own.x, dy: p.y - (from.lifted ? 18 : 0) - own.y };
    } else {
      enters[item.key] = { kind: "grow" };
    }
  }
  for (const item of before?.items ?? []) {
    if (item.kind === "group" && !nowKeys.has(item.key) && item.ids.some((id) => nowKeys.has(`s:${id}`))) {
      leaving.push({ key: `ghost:${item.key}`, item, kind: "group-out", dx: 0, dy: 0 });
    }
  }
  return { enters, leaving };
}

function rank(item: Item): number {
  if (item.kind === "sign" && item.chosen) return 4;
  if (item.kind === "station") return 3;
  if (item.kind === "sign") return 2;
  return 1;
}

function dist(box: Box, point: Px): number {
  return Math.hypot((box.left + box.right) / 2 - point.x, (box.top + box.bottom) / 2 - point.y);
}

/** A tag's width depends on its stop, whether it is the chosen one's, and what it says. */
function widthKey(id: string, chosen: boolean, next: { text: string; line: { label: string } }): string {
  return `${id}|${chosen ? 1 : 0}|${next.line.label}|${next.text}`;
}

function knownAsArea(stop: MapKnownStop): AreaStop {
  return {
    stopId: stop.stopId,
    name: stop.name,
    code: null,
    latitude: stop.latitude,
    longitude: stop.longitude,
    mode: stop.mode,
    bearingDegrees: stop.bearingDegrees,
    parentStationId: null,
    locationType: 0,
  };
}

/** Where the old (small) sign sits while the chosen one grows over it: the normal sign's place. */
function chosenWasStyle(side: SignSide): CSSProperties {
  switch (side) {
    case "up":
      return { insetInlineStart: -22, insetBlockStart: -44, transformOrigin: "22px 44px" };
    case "down":
      return { insetInlineStart: -22, insetBlockStart: 0, transformOrigin: "22px 0" };
    case "left":
      return { insetInlineStart: -44, insetBlockStart: -22, transformOrigin: "44px 22px" };
    case "right":
      return { insetInlineStart: 0, insetBlockStart: -22, transformOrigin: "0 22px" };
    default:
      return { insetInlineStart: -22, insetBlockStart: -22, transformOrigin: "22px 22px" };
  }
}

/** The ripple around the chosen sign's centre. */
function rippleStyle(side: SignSide): CSSProperties {
  const half = SIGN_PX / 2 + 4 + 12;
  switch (side) {
    case "up":
      return { insetInlineStart: 0, insetBlockStart: -half };
    case "down":
      return { insetInlineStart: 0, insetBlockStart: half };
    case "left":
      return { insetInlineStart: -half, insetBlockStart: 0 };
    case "right":
      return { insetInlineStart: half, insetBlockStart: 0 };
    default:
      return { insetInlineStart: 0, insetBlockStart: 0 };
  }
}

/** A lifted group's legs: from each member's kerb dot a short pole toward the count (MarkerTuning). */
function GroupLegs({ legs, lift, radius }: { legs: Px[]; lift: number; radius: number }) {
  const pad = 60;
  return (
    <svg className="ot-stop-legs" width={pad * 2} height={pad * 2} style={{ insetInlineStart: -pad, insetBlockStart: -pad }} aria-hidden="true">
      {legs.map((leg, index) => {
        // From the count's centre (0, 0 here; the anchor is lifted) to the kerb at leg + lift.
        const kx = leg.x;
        const ky = leg.y + lift;
        const length = Math.hypot(kx, ky);
        const start = length > 0 ? Math.min(1, (radius + 1) / length) : 1;
        return (
          <g key={index}>
            {length > radius + 2 && <line x1={pad + kx * start} y1={pad + ky * start} x2={pad + kx} y2={pad + ky} />}
            <circle cx={pad + kx} cy={pad + ky} r={3} />
          </g>
        );
      })}
    </svg>
  );
}

/** The open group's dashed ring (board 9): around its stops' centre, sized at the settled view. */
function openRing(map: MapLibreMap, ids: readonly string[] | null, stops: Map<string, AreaStop>, view: View): { anchor: LonLat; r: number } | null {
  void view;
  if (!ids || ids.length === 0) return null;
  const members = ids.map((id) => stops.get(id)).filter((stop): stop is AreaStop => !!stop);
  if (members.length === 0) return null;
  const anchor: LonLat = [
    members.reduce((sum, stop) => sum + stop.longitude, 0) / members.length,
    members.reduce((sum, stop) => sum + stop.latitude, 0) / members.length,
  ];
  const centre = map.project(anchor);
  const r = Math.max(...members.map((stop) => {
    const p = map.project([stop.longitude, stop.latitude]);
    return Math.hypot(p.x - centre.x, p.y - centre.y);
  })) + 44;
  return { anchor, r: Math.min(r, 400) };
}

/** Grows a marker out of its kerb dot as it comes into view while the map moves. */
function growIn(body: HTMLElement | null): void {
  if (!body || typeof body.animate !== "function") return;
  const keyframes = reducedMotion()
    ? [{ opacity: 0 }, { opacity: 1 }]
    : [
        { opacity: 0, transform: "scale(0.3)", offset: 0 },
        { opacity: 1, transform: "scale(1.12)", offset: 0.625 },
        { opacity: 1, transform: "scale(1)", offset: 1 },
      ];
  body.animate(keyframes, { duration: 180, easing: "ease-out" });
}

export { toAreaStop, ZOOM_STOPS };
