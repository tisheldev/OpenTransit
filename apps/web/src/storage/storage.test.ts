import { describe, expect, it } from "vitest";
import { z } from "zod";
import {
  clearAllLocalData,
  defaultLocalState,
  loadLocalState,
  MAX_RECENTS,
  saveLocalState,
  STORAGE_KEY,
  updateLocalState,
  withRecent,
  type LocalState,
  type SavedPlace,
} from "./local";
import { readSession, removeSession, writeSession } from "./session";

const place = (id: string): SavedPlace => ({
  id,
  label: `Place ${id}`,
  latitude: 32.0757,
  longitude: 34.7748,
  stopId: null,
  placeRefHint: null,
  savedAt: "2026-10-31T10:00:00+02:00",
});

describe("loadLocalState()", () => {
  it("starts empty with Hebrew", () => {
    expect(loadLocalState()).toEqual({ state: defaultLocalState(), source: "empty", writable: true });
    expect(defaultLocalState().settings.lang).toBe("he");
  });

  it("reads back what it saved", () => {
    const state: LocalState = { ...defaultLocalState(), settings: { lang: "en" }, home: place("home") };
    expect(saveLocalState(state)).toBe(true);
    expect(loadLocalState()).toEqual({ state, source: "stored", writable: true });
  });

  it("resets corrupt or invalid data instead of crashing", () => {
    for (const raw of ["{not json", "[]", "null", '{"version":1,"settings":{"lang":"fr"}}', '{"version":0}']) {
      localStorage.setItem(STORAGE_KEY, raw);
      expect(loadLocalState()).toMatchObject({ state: defaultLocalState(), source: "reset", writable: true });
    }
  });

  it("does not overwrite data written by a newer version", () => {
    const newer = JSON.stringify({ version: 99, somethingNew: true });
    localStorage.setItem(STORAGE_KEY, newer);
    expect(loadLocalState()).toMatchObject({ source: "newer", writable: false });
    updateLocalState((state) => ({ ...state, settings: { lang: "en" } }));
    expect(localStorage.getItem(STORAGE_KEY)).toBe(newer);
  });

  it("works in memory when storage is blocked", () => {
    const blocked = {
      getItem: () => {
        throw new DOMException("denied", "SecurityError");
      },
    } as unknown as Storage;
    expect(loadLocalState({ store: blocked })).toMatchObject({ source: "unavailable", writable: false });
    expect(loadLocalState({ store: null })).toMatchObject({ source: "unavailable" });
  });
});

describe("migration", () => {
  // Version 1 is the first shipped shape, so the runner is exercised with a test schema
  // two versions ahead: v1 -> v2 lifts settings.lang to `language`; v2 -> v3 moves it
  // back under settings and adds `pinned`.
  const V3 = z.object({
    version: z.literal(3),
    settings: z.object({ lang: z.enum(["he", "en"]) }),
    home: z.unknown().nullable(),
    work: z.unknown().nullable(),
    favourites: z.array(z.unknown()),
    recents: z.array(z.unknown()),
    pinned: z.array(z.string()),
  });
  const migrations = {
    1: ({ settings, ...rest }: Record<string, unknown>) => ({ ...rest, language: (settings as { lang: string }).lang }),
    2: ({ language, ...rest }: Record<string, unknown>) => ({ ...rest, settings: { lang: language }, pinned: [] }),
  };

  it("upgrades step by step, validates and writes the result back", () => {
    saveLocalState({ ...defaultLocalState(), settings: { lang: "en" }, recents: [place("a")] });
    const result = loadLocalState({ migrations, version: 3, schema: V3 as unknown as z.ZodType<LocalState> });
    expect(result.source).toBe("migrated");
    expect(result.state).toMatchObject({ version: 3, settings: { lang: "en" }, pinned: [] });
    expect(JSON.parse(localStorage.getItem(STORAGE_KEY)!).version).toBe(3);
  });

  it("resets when a migration step is missing", () => {
    saveLocalState(defaultLocalState());
    const result = loadLocalState({ migrations: { 2: migrations[2] }, version: 3, schema: V3 as unknown as z.ZodType<LocalState> });
    expect(result.source).toBe("reset");
  });
});

describe("recents and saved places", () => {
  it("keeps at most 10 recents, newest first, without duplicates", () => {
    let state = defaultLocalState();
    for (let index = 0; index < 15; index += 1) state = withRecent(state, place(String(index)));
    state = withRecent(state, place("12"));
    expect(state.recents).toHaveLength(MAX_RECENTS);
    expect(state.recents.map((item) => item.id).slice(0, 3)).toEqual(["12", "14", "13"]);
    expect(saveLocalState(state)).toBe(true);
  });

  it("refuses a place outside Israel's bounds rather than storing it", () => {
    expect(() => saveLocalState({ ...defaultLocalState(), home: { ...place("x"), latitude: 51.5 } })).toThrow();
  });
});

describe("clearAllLocalData()", () => {
  it("removes our local and session keys and nothing else", () => {
    saveLocalState({ ...defaultLocalState(), home: place("home") });
    writeSession("journeys", { id: 1 });
    writeSession("activeTrip", { id: 2 });
    localStorage.setItem("someone-else", "keep");
    sessionStorage.setItem("other", "keep");
    clearAllLocalData();
    expect(localStorage.getItem(STORAGE_KEY)).toBeNull();
    const anything = (value: unknown): value is unknown => value !== undefined;
    expect(readSession("journeys", anything)).toBeNull();
    expect(readSession("activeTrip", anything)).toBeNull();
    expect(localStorage.getItem("someone-else")).toBe("keep");
    expect(sessionStorage.getItem("other")).toBe("keep");
    expect(loadLocalState().source).toBe("empty");
  });
});

describe("session storage", () => {
  it("validates what it reads and removes on request", () => {
    const isTrip = (value: unknown): value is { id: number } =>
      typeof value === "object" && value !== null && typeof (value as { id: unknown }).id === "number";
    writeSession("activeTrip", { id: 7 });
    expect(readSession("activeTrip", isTrip)).toEqual({ id: 7 });
    writeSession("activeTrip", { id: "seven" });
    expect(readSession("activeTrip", isTrip)).toBeNull();
    removeSession("activeTrip");
    expect(sessionStorage.length).toBe(0);
  });
});
