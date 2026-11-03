import { useSyncExternalStore } from "react";
import { choiceFromSaved, recentId, savedFromChoice, type PlaceChoice } from "../plan/draft";
import {
  SESSION_PREFIX,
  loadLocalState,
  updateLocalState,
  withRecent,
  type LocalState,
  type SavedPlace,
} from "../storage/local";

// A reactive view of storage/local.ts for Home, Search and Settings: read synchronously
// before the first frame (design: Home, "storage only"), written through on change.

let snapshot: LocalState | null = null;
const listeners = new Set<() => void>();

function get(): LocalState {
  if (snapshot === null) snapshot = loadLocalState().state;
  return snapshot;
}

function notify(): void {
  for (const listener of listeners) listener();
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function useLocalState(): LocalState {
  return useSyncExternalStore(subscribe, get, get);
}

/** Apply a change and persist it. False when the result is invalid (e.g. outside Israel). */
export function changeLocal(change: (state: LocalState) => LocalState): boolean {
  try {
    snapshot = updateLocalState(change);
  } catch {
    return false;
  }
  notify();
  return true;
}

/** Re-read storage (after "clear all", and between tests). */
export function reloadLocalState(): void {
  snapshot = null;
  notify();
}

export type SavedSlot = "home" | "work";

/** Within the bounds storage accepts (storage/local.ts SavedPlaceSchema). */
export function storable(choice: PlaceChoice): boolean {
  return choice.latitude >= 29 && choice.latitude <= 34 && choice.longitude >= 34 && choice.longitude <= 36;
}

export function addRecent(choice: PlaceChoice): boolean {
  if (!storable(choice)) return false;
  return changeLocal((state) => withRecent(state, savedFromChoice(choice, recentId(choice))));
}

// The last start the passenger chose, so a plan can start from it when "my location"
// cannot work (plain-http preview, denied permission). Only a pointer to one of the
// recents is kept (its id), never a device position; "clear all" removes it with the
// other "opentransit:" keys, and it is forgotten once that recent is pushed out.
const LAST_ORIGIN_KEY = `${SESSION_PREFIX}lastOrigin`;

function localStore(): Storage | null {
  try {
    return globalThis.localStorage ?? null;
  } catch {
    return null;
  }
}

/** Record a chosen From place (it is added to recents too). */
export function rememberOrigin(choice: PlaceChoice): void {
  if (!addRecent(choice)) return;
  try {
    localStore()?.setItem(LAST_ORIGIN_KEY, recentId(choice));
  } catch {
    // storage full or blocked: nothing to remember
  }
}

/** The most recent From place, if it is still among the recents. */
export function lastOrigin(): PlaceChoice | null {
  let id: string | null = null;
  try {
    id = localStore()?.getItem(LAST_ORIGIN_KEY) ?? null;
  } catch {
    return null;
  }
  if (id === null) return null;
  const recent = get().recents.find((item) => item.id === id);
  return recent ? choiceFromSaved(recent) : null;
}

export function saveSlot(slot: SavedSlot, choice: PlaceChoice, label?: string): boolean {
  if (!storable(choice)) return false;
  const saved = savedFromChoice(choice, slot);
  return changeLocal((state) => ({ ...state, [slot]: label ? { ...saved, label } : saved }));
}

export function addFavourite(choice: PlaceChoice, label: string, now: Date = new Date()): boolean {
  if (!storable(choice)) return false;
  const saved: SavedPlace = { ...savedFromChoice(choice, `fav-${now.getTime().toString(36)}-${Math.random().toString(36).slice(2, 6)}`, now), label };
  return changeLocal((state) => ({ ...state, favourites: [...state.favourites, saved].slice(0, 50) }));
}

/** Rename Home, Work or a favourite (by id). */
export function renameSaved(id: string, label: string): boolean {
  const trimmed = label.trim().slice(0, 200);
  if (!trimmed) return false;
  return changeLocal((state) => ({
    ...state,
    home: state.home?.id === id ? { ...state.home, label: trimmed } : state.home,
    work: state.work?.id === id ? { ...state.work, label: trimmed } : state.work,
    favourites: state.favourites.map((item) => (item.id === id ? { ...item, label: trimmed } : item)),
  }));
}

export function deleteSaved(id: string): boolean {
  return changeLocal((state) => ({
    ...state,
    home: state.home?.id === id ? null : state.home,
    work: state.work?.id === id ? null : state.work,
    favourites: state.favourites.filter((item) => item.id !== id),
  }));
}
