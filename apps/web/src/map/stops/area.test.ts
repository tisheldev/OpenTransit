import { afterEach, describe, expect, it, vi } from "vitest";
import type { Result } from "../../api/result";
import type { StopsPage } from "../../api/schemas";
import { AreaStops, areaKm2, keeps, KINDS, mergeTiles, rectBounds, tileBounds, tileOf, tilesIn, toAreaStop, type Bounds, type ListStops } from "./area";

const META = {} as StopsPage["meta"];

function item(stopId: string, latitude: number, longitude: number, extra: Record<string, unknown> = {}): StopsPage["data"][number] {
  return {
    stopId,
    sourceId: stopId,
    code: null,
    name: stopId,
    description: null,
    latitude,
    longitude,
    locationType: 0,
    parentStationId: null,
    wheelchairBoarding: null,
    platformCode: null,
    mode: "bus",
    bearingDegrees: 90,
    bearingSource: "next_stop",
    ...extra,
  };
}

const page = (data: StopsPage["data"], nextCursor: string | null = null): Result<StopsPage> => ({
  ok: true,
  status: 200,
  value: { data, page: { nextCursor }, meta: META },
});

/** Dizengoff Center, about a kilometre either way. */
const VIEW: Bounds = { west: 34.768, south: 32.07, east: 34.782, north: 32.081 };

afterEach(() => {
  vi.useRealTimers();
});

describe("tiles", () => {
  it("round-trip a point through its tile", () => {
    const tile = tileOf(34.7748, 32.0757, 15);
    const bounds = tileBounds(tile.x, tile.y, 15);
    expect(34.7748).toBeGreaterThanOrEqual(bounds.west);
    expect(34.7748).toBeLessThan(bounds.east);
    expect(32.0757).toBeGreaterThanOrEqual(bounds.south);
    expect(32.0757).toBeLessThan(bounds.north);
    // About 1 km² at 32° N.
    expect(areaKm2(bounds)).toBeGreaterThan(0.9);
    expect(areaKm2(bounds)).toBeLessThan(1.2);
  });

  it("merge the wanted tiles into rectangles: rows of runs, stacked when they match", () => {
    const range = { x0: 0, x1: 3, y0: 0, y1: 2 };
    // Everything but the tile at (1, 1).
    const rects = mergeTiles(range, (x, y) => !(x === 1 && y === 1), 15, 1000);
    const covered = new Set<string>();
    for (const rect of rects) for (let x = rect.x0; x <= rect.x1; x += 1) for (let y = rect.y0; y <= rect.y1; y += 1) covered.add(`${x}/${y}`);
    expect(covered.size).toBe(11);
    expect(covered.has("1/1")).toBe(false);
    expect(rects.length).toBeLessThanOrEqual(4);
  });

  it("keep each rectangle within the API's area limit", () => {
    const range = tilesIn({ west: 34.6, south: 31.95, east: 34.95, north: 32.2 }, 15);
    const rects = mergeTiles(range, () => true, 15, KINDS.stops.maxKm2);
    expect(rects.length).toBeGreaterThan(1);
    for (const rect of rects) expect(areaKm2(rectBounds(rect, 15))).toBeLessThanOrEqual(KINDS.stops.maxKm2);
  });
});

describe("what each layer keeps", () => {
  it("bus stops leave stations (and parent stations) to the station layer; a stop no line serves is dropped", () => {
    expect(keeps("stops", toAreaStop(item("b", 32, 34)))).toBe(true);
    expect(keeps("stops", toAreaStop(item("r", 32, 34, { mode: "rail" })))).toBe(false);
    expect(keeps("stops", toAreaStop(item("p", 32, 34, { mode: null, locationType: 1 })))).toBe(false);
    expect(keeps("stops", toAreaStop(item("n", 32, 34, { mode: null })))).toBe(false);
    expect(keeps("stations", toAreaStop(item("l", 32, 34, { mode: "light_rail" })))).toBe(true);
  });

  it("an API without modes: every stop is drawn as a bus stop", () => {
    const old = item("old", 32, 34);
    delete (old as Record<string, unknown>).mode;
    delete (old as Record<string, unknown>).bearingDegrees;
    const stop = toAreaStop(old);
    expect(stop.mode).toBeUndefined();
    expect(stop.bearingDegrees).toBeUndefined();
    expect(keeps("stops", stop)).toBe(true);
  });
});

describe("the session cache", () => {
  it("asks once per area, reads every page, and answers later settles from memory", async () => {
    const calls: Array<{ bbox: Bounds; modes: readonly string[] | null; cursor: string | null }> = [];
    const list: ListStops = async (bbox, modes, paging) => {
      calls.push({ bbox, modes, cursor: paging.cursor });
      return paging.cursor === null ? page([item("a", 32.075, 34.775)], "next") : page([item("b", 32.076, 34.776)]);
    };
    const source = new AreaStops(list);
    source.want("stops", VIEW);
    await vi.waitFor(() => expect(source.busy).toBe(false));
    expect(calls.map((call) => call.cursor)).toEqual([null, "next"]);
    expect(calls[0]!.modes).toBeNull();
    expect(source.stopsIn("stops", VIEW).map((stop) => stop.stopId).sort()).toEqual(["a", "b"]);
    // The same view again, and a smaller one inside it: nothing more is asked.
    source.want("stops", VIEW);
    source.want("stops", { west: 34.772, south: 32.074, east: 34.778, north: 32.078 });
    await vi.waitFor(() => expect(source.busy).toBe(false));
    expect(calls).toHaveLength(2);
  });

  it("stations ask with the rail modes over a large area (A1), and fold platforms into their station", async () => {
    const modes: Array<readonly string[] | null> = [];
    const list: ListStops = async (_bbox, asked) => {
      modes.push(asked);
      return page([
        item("station", 32.08, 34.79, { mode: "rail", locationType: 1 }),
        item("platform", 32.0801, 34.7901, { mode: "rail", parentStationId: "station" }),
      ]);
    };
    const source = new AreaStops(list);
    const country: Bounds = { west: 34.2, south: 29.5, east: 35.9, north: 33.3 };
    source.want("stations", country);
    await vi.waitFor(() => expect(source.busy).toBe(false));
    expect(modes.every((asked) => asked?.join(",") === "rail,light_rail")).toBe(true);
    expect(source.stopsIn("stations", country).map((stop) => stop.stopId)).toEqual(["station"]);
  });

  it("spends at most its budget at once, then one request every refill", async () => {
    vi.useFakeTimers();
    let now = 0;
    let started = 0;
    const list: ListStops = async () => {
      started += 1;
      return page([]);
    };
    const source = new AreaStops(list, { capacity: 2, refillMs: 1000 }, () => now);
    // Three separate areas far apart: three rectangles.
    source.want("stops", { west: 34.7, south: 32.0, east: 34.705, north: 32.004 });
    source.want("stops", { west: 34.8, south: 32.0, east: 34.805, north: 32.004 });
    source.want("stops", { west: 34.9, south: 32.0, east: 34.905, north: 32.004 });
    await vi.advanceTimersByTimeAsync(0);
    const first = started;
    expect(first).toBeLessThanOrEqual(2);
    now = 1000;
    await vi.advanceTimersByTimeAsync(1000);
    expect(started).toBeGreaterThan(first);
  });

  it("a 429 pauses every request for its Retry-After, then asks the same page again", async () => {
    vi.useFakeTimers();
    let now = 0;
    let calls = 0;
    const list: ListStops = async () => {
      calls += 1;
      if (calls === 1) {
        return { ok: false, state: "rate_limited", error: { kind: "problem", status: 429, retryAfterSeconds: 5, problem: {} as never } };
      }
      return page([item("a", 32.075, 34.775)]);
    };
    const source = new AreaStops(list, { capacity: 10, refillMs: 100 }, () => now);
    source.want("stops", { west: 34.774, south: 32.0745, east: 34.776, north: 32.0755 });
    await vi.advanceTimersByTimeAsync(0);
    expect(calls).toBe(1);
    now = 4000;
    await vi.advanceTimersByTimeAsync(4000);
    expect(calls).toBe(1);
    now = 5100;
    await vi.advanceTimersByTimeAsync(1200);
    expect(calls).toBe(2);
    expect(source.stopsIn("stops", VIEW).map((stop) => stop.stopId)).toEqual(["a"]);
  });
});
