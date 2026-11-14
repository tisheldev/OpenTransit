import type { Result } from "../../api/result";
import type { StopsPage } from "../../api/schemas";

// Stops by area for the stops layer (design: "stops by area are requested when the map
// settles and kept for the session"). The map is cut into fixed tiles; a settle asks only
// for tiles not yet held, merged into as few rectangles as the API's area limit allows,
// each read to its last page. Requests share one small budget so a settle never bursts
// past the API's limits (60 a minute with a burst of 20, shared by the whole client), and
// a 429 pauses them all for its Retry-After. Nothing here imports React or MapLibre.

export interface Bounds {
  west: number;
  south: number;
  east: number;
  north: number;
}

/** A stop as the layer draws it (a stop item from GET /v1/stops). */
export interface AreaStop {
  stopId: string;
  name: string | null;
  code: string | null;
  latitude: number;
  longitude: number;
  /** "rail", "light_rail", "bus", "other"; null when no line serves it; undefined from an API without API-C6. */
  mode: string | null | undefined;
  bearingDegrees: number | null | undefined;
  parentStationId: string | null;
  locationType: number | null;
}

export type AreaKind = "stops" | "stations";

/** Modes the station layer asks for (A1: these alone lift the area limit from 100 to 120,000 km², the whole country). */
export const STATION_MODES = ["rail", "light_rail"] as const;

export function isStationMode(mode: string | null | undefined): boolean {
  return mode === "rail" || mode === "light_rail";
}

interface KindConfig {
  /** Tile zoom of the cache. */
  tileZoom: number;
  /** The API's area limit for one request, with a margin. */
  maxKm2: number;
  /** Mode filter sent with the request (A1); none for every stop. */
  modes: readonly string[] | null;
}

export const KINDS: Record<AreaKind, KindConfig> = {
  // About 1 km² a tile at 32° N: a close-up view needs a handful, merged into one request.
  stops: { tileZoom: 15, maxKm2: 90, modes: null },
  // About 4,400 km² a tile: the whole of central Israel in one or two requests.
  stations: { tileZoom: 9, maxKm2: 100_000, modes: STATION_MODES },
};

/** One page is 100 stops; a rectangle stops after this many pages (a few thousand stops). */
export const PAGE_LIMIT = 100;
export const MAX_PAGES = 20;

// ---------------------------------------------------------------------------------------
// Tiles (Web Mercator, as the map's own)

export interface Tile {
  x: number;
  y: number;
}

const clampLat = (lat: number) => Math.max(-85, Math.min(85, lat));

export function tileOf(lon: number, lat: number, z: number): Tile {
  const n = 2 ** z;
  const rad = (clampLat(lat) * Math.PI) / 180;
  const x = Math.floor(((lon + 180) / 360) * n);
  const y = Math.floor(((1 - Math.log(Math.tan(rad) + 1 / Math.cos(rad)) / Math.PI) / 2) * n);
  return { x: Math.max(0, Math.min(n - 1, x)), y: Math.max(0, Math.min(n - 1, y)) };
}

export function tileBounds(x: number, y: number, z: number): Bounds {
  const n = 2 ** z;
  const lat = (row: number) => (Math.atan(Math.sinh(Math.PI * (1 - (2 * row) / n))) * 180) / Math.PI;
  return { west: (x / n) * 360 - 180, east: ((x + 1) / n) * 360 - 180, north: lat(y), south: lat(y + 1) };
}

export function areaKm2(bounds: Bounds): number {
  const mid = (((bounds.north + bounds.south) / 2) * Math.PI) / 180;
  return (bounds.east - bounds.west) * 111.32 * Math.cos(mid) * (bounds.north - bounds.south) * 110.57;
}

/** A rectangle of tiles, inclusive. */
export interface TileRect {
  x0: number;
  x1: number;
  y0: number;
  y1: number;
}

export function rectBounds(rect: TileRect, z: number): Bounds {
  const a = tileBounds(rect.x0, rect.y0, z);
  const b = tileBounds(rect.x1, rect.y1, z);
  return { west: a.west, north: a.north, east: b.east, south: b.south };
}

export function tilesIn(bounds: Bounds, z: number): TileRect {
  const a = tileOf(bounds.west, bounds.north, z);
  const b = tileOf(bounds.east, bounds.south, z);
  return { x0: Math.min(a.x, b.x), x1: Math.max(a.x, b.x), y0: Math.min(a.y, b.y), y1: Math.max(a.y, b.y) };
}

const tileKey = (x: number, y: number) => `${x}/${y}`;

/**
 * The tiles in `range` that `wanted` says to fetch, as rectangles: runs along each row,
 * stacked where consecutive rows have the same run, then halved until each is within
 * `maxKm2`. Every wanted tile is in exactly one rectangle and no other tile is.
 */
export function mergeTiles(range: TileRect, wanted: (x: number, y: number) => boolean, z: number, maxKm2: number): TileRect[] {
  const open: TileRect[] = [];
  const done: TileRect[] = [];
  for (let y = range.y0; y <= range.y1; y += 1) {
    const runs: TileRect[] = [];
    let start: number | null = null;
    for (let x = range.x0; x <= range.x1 + 1; x += 1) {
      const want = x <= range.x1 && wanted(x, y);
      if (want && start === null) start = x;
      if (!want && start !== null) {
        runs.push({ x0: start, x1: x - 1, y0: y, y1: y });
        start = null;
      }
    }
    // Extend a rectangle from the row above with exactly the same run; close the others.
    const next: TileRect[] = [];
    for (const run of runs) {
      const above = open.findIndex((rect) => rect.x0 === run.x0 && rect.x1 === run.x1 && rect.y1 === y - 1);
      if (above >= 0) {
        const [rect] = open.splice(above, 1);
        next.push({ ...rect!, y1: y });
      } else {
        next.push(run);
      }
    }
    done.push(...open);
    open.splice(0, open.length, ...next);
  }
  done.push(...open);
  const split = (rect: TileRect): TileRect[] => {
    if (areaKm2(rectBounds(rect, z)) <= maxKm2 || (rect.x0 === rect.x1 && rect.y0 === rect.y1)) return [rect];
    const wide = rect.x1 - rect.x0 >= rect.y1 - rect.y0;
    if (wide) {
      const mid = Math.floor((rect.x0 + rect.x1) / 2);
      return [...split({ ...rect, x1: mid }), ...split({ ...rect, x0: mid + 1 })];
    }
    const mid = Math.floor((rect.y0 + rect.y1) / 2);
    return [...split({ ...rect, y1: mid }), ...split({ ...rect, y0: mid + 1 })];
  };
  return done.flatMap(split);
}

// ---------------------------------------------------------------------------------------
// The session cache and its request budget

export type ListStops = (
  bbox: Bounds,
  modes: readonly string[] | null,
  paging: { limit: number; cursor: string | null },
  signal?: AbortSignal,
) => Promise<Result<StopsPage>>;

type Item = StopsPage["data"][number];

export function toAreaStop(item: Item): AreaStop {
  const extra = item as Record<string, unknown>;
  const bearing = extra.bearingDegrees;
  return {
    stopId: item.stopId,
    name: item.name,
    code: item.code,
    latitude: item.latitude,
    longitude: item.longitude,
    mode: "mode" in extra ? (typeof extra.mode === "string" ? extra.mode : null) : undefined,
    bearingDegrees: typeof bearing === "number" ? bearing : bearing === null ? null : undefined,
    parentStationId: item.parentStationId,
    locationType: item.locationType,
  };
}

/**
 * What a kind keeps: bus stops leave stations to the station layer (which folds platforms
 * into their station, A1); a stop no line serves (mode null) has nothing to board. A stop
 * from an API without modes (undefined) is drawn as a bus stop.
 */
export function keeps(kind: AreaKind, stop: AreaStop): boolean {
  if (kind === "stations") return isStationMode(stop.mode);
  if (stop.locationType === 1) return false;
  return stop.mode === undefined || (stop.mode !== null && !isStationMode(stop.mode));
}

interface Job {
  kind: AreaKind;
  rect: TileRect;
  cursor: string | null;
  pages: number;
  found: AreaStop[];
  started: boolean;
}

export interface Budget {
  /** Requests that may start at once. */
  capacity: number;
  /** One more request every this many milliseconds. */
  refillMs: number;
}

/** Ten at once, then one every three seconds: at most 30 a minute for stops, well inside the shared 60. */
export const DEFAULT_BUDGET: Budget = { capacity: 10, refillMs: 3000 };

export class AreaStops {
  private readonly tiles: Record<AreaKind, Map<string, AreaStop[]>> = { stops: new Map(), stations: new Map() };
  /** Tiles a queued or running job covers. */
  private readonly pending: Record<AreaKind, Set<string>> = { stops: new Set(), stations: new Set() };
  /** Tiles whose request failed, with when they may be asked again. */
  private readonly cooling: Record<AreaKind, Map<string, number>> = { stops: new Map(), stations: new Map() };
  private queue: Job[] = [];
  private running = 0;
  private tokens: number;
  private refilledAt: number;
  private pausedUntil = 0;
  private timer: ReturnType<typeof setTimeout> | null = null;
  private version = 0;
  private readonly listeners = new Set<() => void>();
  /** Requests started, for tests and the request-limit check. */
  requests = 0;

  constructor(
    private readonly list: ListStops,
    private readonly budget: Budget = DEFAULT_BUDGET,
    private readonly now: () => number = () => Date.now(),
  ) {
    this.tokens = budget.capacity;
    this.refilledAt = now();
  }

  subscribe = (listener: () => void): (() => void) => {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  };

  getVersion = (): number => this.version;

  private changed(): void {
    this.version += 1;
    for (const listener of this.listeners) listener();
  }

  /**
   * The map settled on `bounds`: queue what is missing there (nearest the centre first),
   * and drop queued work for places the passenger has left. Running requests finish.
   */
  want(kind: AreaKind, bounds: Bounds): void {
    const config = KINDS[kind];
    const z = config.tileZoom;
    const range = tilesIn(bounds, z);
    const at = this.now();
    // Queued (not started) jobs of this kind outside the new view are dropped.
    this.queue = this.queue.filter((job) => {
      if (job.kind !== kind || job.started) return true;
      const inView = job.rect.x1 >= range.x0 && job.rect.x0 <= range.x1 && job.rect.y1 >= range.y0 && job.rect.y0 <= range.y1;
      if (!inView) this.forEachTile(job.rect, (key) => this.pending[kind].delete(key));
      return inView;
    });
    const held = this.tiles[kind];
    const rects = mergeTiles(
      range,
      (x, y) => {
        const key = tileKey(x, y);
        return !held.has(key) && !this.pending[kind].has(key) && (this.cooling[kind].get(key) ?? 0) <= at;
      },
      z,
      config.maxKm2,
    );
    const cx = (range.x0 + range.x1) / 2;
    const cy = (range.y0 + range.y1) / 2;
    rects.sort((a, b) => Math.hypot((a.x0 + a.x1) / 2 - cx, (a.y0 + a.y1) / 2 - cy) - Math.hypot((b.x0 + b.x1) / 2 - cx, (b.y0 + b.y1) / 2 - cy));
    for (const rect of rects) {
      this.forEachTile(rect, (key) => this.pending[kind].add(key));
      this.queue.push({ kind, rect, cursor: null, pages: 0, found: [], started: false });
    }
    this.pump();
  }

  /** Every stop of a kind held for `bounds` (whole tiles, and the pages read so far of running jobs). */
  stopsIn(kind: AreaKind, bounds: Bounds): AreaStop[] {
    const z = KINDS[kind].tileZoom;
    const range = tilesIn(bounds, z);
    const out = new Map<string, AreaStop>();
    const inside = (stop: AreaStop) =>
      stop.longitude >= bounds.west && stop.longitude <= bounds.east && stop.latitude >= bounds.south && stop.latitude <= bounds.north;
    for (let x = range.x0; x <= range.x1; x += 1) {
      for (let y = range.y0; y <= range.y1; y += 1) {
        for (const stop of this.tiles[kind].get(tileKey(x, y)) ?? []) if (inside(stop)) out.set(stop.stopId, stop);
      }
    }
    for (const job of this.queue) if (job.kind === kind) for (const stop of job.found) if (inside(stop)) out.set(stop.stopId, stop);
    return foldPlatforms([...out.values()]);
  }

  /** One held stop by id (any kind), or undefined. */
  find(stopId: string): AreaStop | undefined {
    for (const kind of ["stops", "stations"] as const) {
      for (const stops of this.tiles[kind].values()) {
        const found = stops.find((stop) => stop.stopId === stopId);
        if (found) return found;
      }
    }
    return undefined;
  }

  /** True while anything is queued or running. */
  get busy(): boolean {
    return this.queue.length > 0;
  }

  private forEachTile(rect: TileRect, run: (key: string) => void): void {
    for (let x = rect.x0; x <= rect.x1; x += 1) for (let y = rect.y0; y <= rect.y1; y += 1) run(tileKey(x, y));
  }

  private refill(): void {
    const at = this.now();
    const earned = Math.floor((at - this.refilledAt) / this.budget.refillMs);
    if (earned > 0) {
      this.tokens = Math.min(this.budget.capacity, this.tokens + earned);
      this.refilledAt += earned * this.budget.refillMs;
    }
    if (this.tokens >= this.budget.capacity) this.refilledAt = at;
  }

  private schedule(ms: number): void {
    if (this.timer) return;
    this.timer = setTimeout(() => {
      this.timer = null;
      this.pump();
    }, Math.max(0, ms));
  }

  private pump(): void {
    this.refill();
    const at = this.now();
    if (at < this.pausedUntil) {
      this.schedule(this.pausedUntil - at);
      return;
    }
    // Two at a time: pages of one rectangle follow each other anyway.
    while (this.running < 2) {
      const job = this.queue.find((item) => !item.started || (item.started && item.cursor !== null && !this.isRunning(item)));
      if (!job) return;
      if (this.tokens < 1) {
        this.schedule(this.budget.refillMs - (at - this.refilledAt));
        return;
      }
      this.tokens -= 1;
      void this.run(job);
    }
  }

  private readonly active = new Set<Job>();
  private isRunning(job: Job): boolean {
    return this.active.has(job);
  }

  private async run(job: Job): Promise<void> {
    job.started = true;
    this.active.add(job);
    this.running += 1;
    this.requests += 1;
    const config = KINDS[job.kind];
    const result = await this.list(rectBounds(job.rect, config.tileZoom), config.modes, { limit: PAGE_LIMIT, cursor: job.cursor }).catch(() => null);
    this.running -= 1;
    this.active.delete(job);
    if (result && result.ok) {
      job.pages += 1;
      for (const item of result.value.data) {
        const stop = toAreaStop(item);
        if (keeps(job.kind, stop)) job.found.push(stop);
      }
      job.cursor = result.value.page.nextCursor;
      if (job.cursor === null || job.pages >= MAX_PAGES) this.finish(job);
      this.changed();
    } else if (result && !result.ok && result.error.kind === "problem" && result.error.status === 429) {
      // Rate limited: everything waits, then this page is asked again.
      this.pausedUntil = this.now() + (result.error.retryAfterSeconds ?? 30) * 1000;
      job.started = job.pages > 0;
    } else {
      // Failed (an API without the mode filter refuses a large area, a network drop): leave
      // these tiles for a minute rather than ask again on every settle.
      this.queue = this.queue.filter((item) => item !== job);
      const until = this.now() + 60_000;
      this.forEachTile(job.rect, (key) => {
        this.pending[job.kind].delete(key);
        this.cooling[job.kind].set(key, until);
      });
      if (job.found.length > 0) this.finish(job);
      this.changed();
    }
    this.pump();
  }

  private finish(job: Job): void {
    this.queue = this.queue.filter((item) => item !== job);
    const z = KINDS[job.kind].tileZoom;
    const byTile = new Map<string, AreaStop[]>();
    this.forEachTile(job.rect, (key) => byTile.set(key, []));
    for (const stop of job.found) {
      const tile = tileOf(stop.longitude, stop.latitude, z);
      byTile.get(tileKey(tile.x, tile.y))?.push(stop);
    }
    for (const [key, stops] of byTile) {
      this.tiles[job.kind].set(key, stops);
      this.pending[job.kind].delete(key);
    }
  }
}

/** Platforms fold into their station when both are held (the API already folds with a station filter). */
export function foldPlatforms(stops: AreaStop[]): AreaStop[] {
  const ids = new Set(stops.map((stop) => stop.stopId));
  return stops.filter((stop) => !(stop.parentStationId && ids.has(stop.parentStationId)));
}
