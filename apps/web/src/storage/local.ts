import { z } from "zod";

// Versioned localStorage for settings, saved places and at most 10 recents (design:
// Privacy). No location history, journey results or account data live here. Saved
// places keep coordinates and a label; a placeRef is only a hint because it is bound
// to one generation (INVALID_PLACE_REF after a refresh).

export const STORAGE_KEY = "opentransit";
export const SESSION_PREFIX = "opentransit:";
export const STORAGE_VERSION = 1;
export const MAX_RECENTS = 10;

const SavedPlaceSchema = z.object({
  id: z.string().min(1),
  label: z.string().min(1).max(200),
  latitude: z.number().min(29).max(34),
  longitude: z.number().min(34).max(36),
  stopId: z.string().nullable().default(null),
  placeRefHint: z.string().nullable().default(null),
  savedAt: z.string(),
});

const LocalStateSchema = z.object({
  version: z.literal(STORAGE_VERSION),
  settings: z.object({ lang: z.enum(["he", "en"]) }),
  home: SavedPlaceSchema.nullable(),
  work: SavedPlaceSchema.nullable(),
  favourites: z.array(SavedPlaceSchema).max(50),
  recents: z.array(SavedPlaceSchema).max(MAX_RECENTS),
});

export type SavedPlace = z.infer<typeof SavedPlaceSchema>;
export type LocalState = z.infer<typeof LocalStateSchema>;

export function defaultLocalState(): LocalState {
  return { version: STORAGE_VERSION, settings: { lang: "he" }, home: null, work: null, favourites: [], recents: [] };
}

/** migrations[n] upgrades a stored version-n object to version n+1. */
export type Migrations = Record<number, (stored: Record<string, unknown>) => Record<string, unknown>>;

/** Version 1 is the first released shape, so there is nothing to migrate from yet. */
export const MIGRATIONS: Migrations = {};

export interface LoadResult {
  state: LocalState;
  /** Where the state came from; `newer` means a later app version wrote it. */
  source: "empty" | "stored" | "migrated" | "reset" | "newer" | "unavailable";
  /** False when writing back would destroy data this version cannot read. */
  writable: boolean;
}

function storage(): Storage | null {
  try {
    return globalThis.localStorage ?? null;
  } catch {
    return null; // blocked storage (privacy mode, sandboxed frame)
  }
}

export function loadLocalState(
  options: { store?: Storage | null; migrations?: Migrations; version?: number; schema?: z.ZodType<LocalState> } = {},
): LoadResult {
  const store = options.store === undefined ? storage() : options.store;
  const migrations = options.migrations ?? MIGRATIONS;
  const current = options.version ?? STORAGE_VERSION;
  const schema = options.schema ?? LocalStateSchema;
  if (!store) return { state: defaultLocalState(), source: "unavailable", writable: false };

  let raw: string | null;
  try {
    raw = store.getItem(STORAGE_KEY);
  } catch {
    return { state: defaultLocalState(), source: "unavailable", writable: false };
  }
  if (raw === null) return { state: defaultLocalState(), source: "empty", writable: true };

  let stored: Record<string, unknown>;
  try {
    const parsed: unknown = JSON.parse(raw);
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) throw new Error("not an object");
    stored = parsed as Record<string, unknown>;
  } catch {
    return { state: defaultLocalState(), source: "reset", writable: true };
  }

  let version = typeof stored.version === "number" ? stored.version : NaN;
  if (!Number.isInteger(version) || version < 1) return { state: defaultLocalState(), source: "reset", writable: true };
  if (version > current) return { state: defaultLocalState(), source: "newer", writable: false };

  let migrated = false;
  while (version < current) {
    const step = migrations[version];
    if (!step) return { state: defaultLocalState(), source: "reset", writable: true };
    stored = { ...step(stored), version: version + 1 };
    version += 1;
    migrated = true;
  }

  const valid = schema.safeParse(stored);
  if (!valid.success) return { state: defaultLocalState(), source: "reset", writable: true };
  if (migrated) writeRaw(valid.data, store);
  return { state: valid.data, source: migrated ? "migrated" : "stored", writable: true };
}

function writeRaw(state: unknown, store: Storage | null): boolean {
  if (!store) return false;
  try {
    store.setItem(STORAGE_KEY, JSON.stringify(state));
    return true;
  } catch {
    return false; // quota or blocked storage: keep working in memory
  }
}

export function saveLocalState(state: LocalState, store: Storage | null = storage()): boolean {
  return writeRaw(LocalStateSchema.parse(state), store);
}

/** Read, change and write back, unless a newer app version owns the stored data. */
export function updateLocalState(change: (state: LocalState) => LocalState, store: Storage | null = storage()): LocalState {
  const loaded = loadLocalState({ store });
  const next = change(loaded.state);
  if (loaded.writable) saveLocalState(next, store);
  return next;
}

/** Add a place to recents: newest first, deduplicated by id, capped at MAX_RECENTS. */
export function withRecent(state: LocalState, place: SavedPlace): LocalState {
  const recents = [place, ...state.recents.filter((item) => item.id !== place.id)].slice(0, MAX_RECENTS);
  return { ...state, recents };
}

/**
 * Remove everything this app stored on the device: settings, saved places, recents and
 * session data (journeys, active trip). Other sites' and other apps' keys are untouched.
 */
export function clearAllLocalData(
  local: Storage | null = storage(),
  session: Storage | null = (() => {
    try {
      return globalThis.sessionStorage ?? null;
    } catch {
      return null;
    }
  })(),
): void {
  for (const store of [local, session]) {
    if (!store) continue;
    try {
      const keys = Array.from({ length: store.length }, (_, index) => store.key(index)).filter(
        (key): key is string => key !== null && (key === STORAGE_KEY || key.startsWith(SESSION_PREFIX)),
      );
      for (const key of keys) store.removeItem(key);
    } catch {
      // blocked storage holds nothing of ours
    }
  }
}
