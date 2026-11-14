import { changeLocal, currentLocalState, useLocalState } from "../shell/localStore";
import {
  MAX_SAVED_ITEMS,
  SavedLineSchema,
  SavedStopSchema,
  type LocalState,
  type SavedLine,
  type SavedLineInput,
  type SavedStop,
  type SavedStopInput,
} from "./local";

// Saved stops and lines (user, 14 November 2026: "yes" to board 1's saved stops and lines).
// Device-only, beside the saved places in storage/local.ts (version 2). Home shows them
// as cards with their next departure; the Stop and Line screens' star buttons toggle them.
// A stop is keyed by its stop id; a line by operator + MOT line code (`lineKey`, API
// contract A2), never by route id. Every write goes through the reactive store, so every
// screen holding a hook re-renders at once.

export type { SavedLine, SavedStop } from "./local";

/** What the Stop screen passes to save a stop; `savedAt` defaults to now. */
export type SaveStopInput = Omit<SavedStopInput, "savedAt"> & { savedAt?: string };
/** What the Line screen passes to save a line; `savedAt` defaults to now. */
export type SaveLineInput = Omit<SavedLineInput, "savedAt"> & { savedAt?: string };

const stamped = <T extends { savedAt?: string }>(input: T, now: Date): T & { savedAt: string } => ({
  ...input,
  savedAt: input.savedAt ?? now.toISOString(),
});

export const isStopSaved = (state: Pick<LocalState, "savedStops">, stopId: string): boolean =>
  state.savedStops.some((item) => item.stopId === stopId);

export const isLineSaved = (state: Pick<LocalState, "savedLines">, lineKey: string): boolean =>
  state.savedLines.some((item) => item.lineKey === lineKey);

/** Saved stops, in the order they were saved. */
export function useSavedStops(): SavedStop[] {
  return useLocalState().savedStops;
}

/** Saved lines, in the order they were saved. */
export function useSavedLines(): SavedLine[] {
  return useLocalState().savedLines;
}

/** For a star button: is this stop saved? */
export function useIsStopSaved(stopId: string | null): boolean {
  const state = useLocalState();
  return stopId !== null && isStopSaved(state, stopId);
}

/** For a star button: is this line saved? */
export function useIsLineSaved(lineKey: string | null): boolean {
  const state = useLocalState();
  return lineKey !== null && isLineSaved(state, lineKey);
}

/**
 * Save a stop (or refresh its stored fields if already saved, keeping its place in the
 * order). False when it cannot be stored: invalid fields (outside Israel), the 50-item cap,
 * or storage owned by a newer app version.
 */
export function saveStop(input: SaveStopInput, now: Date = new Date()): boolean {
  const parsed = SavedStopSchema.safeParse(stamped(input, now));
  if (!parsed.success) return false;
  const stop = parsed.data;
  let added = false;
  const ok = changeLocal((state) => {
    if (isStopSaved(state, stop.stopId)) {
      return { ...state, savedStops: state.savedStops.map((item) => (item.stopId === stop.stopId ? { ...stop, savedAt: item.savedAt } : item)) };
    }
    if (state.savedStops.length >= MAX_SAVED_ITEMS) return state;
    added = true;
    return { ...state, savedStops: [...state.savedStops, stop] };
  });
  return ok && (added || isStopSavedNow(stop.stopId));
}

export function removeSavedStop(stopId: string): boolean {
  return changeLocal((state) => ({ ...state, savedStops: state.savedStops.filter((item) => item.stopId !== stopId) }));
}

/** The Stop screen's star: save or unsave. Returns whether the stop is saved afterwards. */
export function toggleSavedStop(input: SaveStopInput, now: Date = new Date()): boolean {
  if (isStopSavedNow(input.stopId)) {
    removeSavedStop(input.stopId);
    return isStopSavedNow(input.stopId);
  }
  return saveStop(input, now);
}

/** Save a line (or refresh its stored fields: direction, stop). See saveStop for false. */
export function saveLine(input: SaveLineInput, now: Date = new Date()): boolean {
  const parsed = SavedLineSchema.safeParse(stamped(input, now));
  if (!parsed.success) return false;
  const line = parsed.data;
  let added = false;
  const ok = changeLocal((state) => {
    if (isLineSaved(state, line.lineKey)) {
      return { ...state, savedLines: state.savedLines.map((item) => (item.lineKey === line.lineKey ? { ...line, savedAt: item.savedAt } : item)) };
    }
    if (state.savedLines.length >= MAX_SAVED_ITEMS) return state;
    added = true;
    return { ...state, savedLines: [...state.savedLines, line] };
  });
  return ok && (added || isLineSavedNow(line.lineKey));
}

export function removeSavedLine(lineKey: string): boolean {
  return changeLocal((state) => ({ ...state, savedLines: state.savedLines.filter((item) => item.lineKey !== lineKey) }));
}

/** The Line screen's star: save or unsave. Returns whether the line is saved afterwards. */
export function toggleSavedLine(input: SaveLineInput, now: Date = new Date()): boolean {
  if (isLineSavedNow(input.lineKey)) {
    removeSavedLine(input.lineKey);
    return isLineSavedNow(input.lineKey);
  }
  return saveLine(input, now);
}

// The current store, outside React (the toggles run in event handlers).
const isStopSavedNow = (stopId: string) => isStopSaved(currentLocalState(), stopId);
const isLineSavedNow = (lineKey: string) => isLineSaved(currentLocalState(), lineKey);
