import { useSyncExternalStore } from "react";

// Saved stops and lines (user, 14 November 2026: "Saved stops and lines on Home: YES",
// device-only). MINIMAL STAND-IN written by the stop/line builder so the Stop and Line
// screens' stars work; builder H owns the real module (same exports) and the two are
// reconciled at merge. A line is keyed by operator + MOT line code (`lineKey`), never by a
// route id, which can disappear and return between generations (M2.8).
//
// Stored under "opentransit:saved" in localStorage: the "opentransit:" prefix is what
// Settings' "clear all" removes (storage/local.ts clearAllLocalData).

export interface SavedStop {
  stopId: string;
  name: string;
  savedAt: string;
}

export interface SavedLine {
  lineKey: string;
  shortName: string;
  operatorId: string;
  operatorName: string;
  mode: string;
  headsign: string | null;
  savedAt: string;
}

interface Saved {
  version: 1;
  stops: SavedStop[];
  lines: SavedLine[];
}

const KEY = "opentransit:saved";
const MAX = 50;
const empty: Saved = { version: 1, stops: [], lines: [] };

function store(): Storage | null {
  try {
    return globalThis.localStorage ?? null;
  } catch {
    return null;
  }
}

const isString = (value: unknown): value is string => typeof value === "string";

function rawValue(): string | null {
  try {
    return store()?.getItem(KEY) ?? null;
  } catch {
    return null;
  }
}

function parse(raw: string | null): Saved {
  try {
    const parsed = JSON.parse(raw ?? "null") as Partial<Saved> | null;
    if (!parsed || parsed.version !== 1) return empty;
    const stops = (Array.isArray(parsed.stops) ? parsed.stops : []).filter((s) => isString(s?.stopId) && isString(s?.name) && isString(s?.savedAt));
    const lines = (Array.isArray(parsed.lines) ? parsed.lines : []).filter(
      (l) => isString(l?.lineKey) && isString(l?.shortName) && isString(l?.operatorId) && isString(l?.savedAt),
    );
    return { version: 1, stops: stops.slice(0, MAX), lines: lines.slice(0, MAX) };
  } catch {
    return empty;
  }
}

// The parsed value is kept while the stored text is unchanged (a stable snapshot for
// useSyncExternalStore); another tab's or a "clear all" change is read on the next look.
let snapshot: { raw: string | null; saved: Saved } | null = null;
let memoryOnly: Saved | null = null;
const listeners = new Set<() => void>();

function get(): Saved {
  if (memoryOnly) return memoryOnly;
  const raw = rawValue();
  if (!snapshot || snapshot.raw !== raw) snapshot = { raw, saved: parse(raw) };
  return snapshot.saved;
}

function write(next: Saved): void {
  const raw = JSON.stringify(next);
  try {
    store()?.setItem(KEY, raw);
    memoryOnly = null;
    snapshot = { raw, saved: next };
  } catch {
    memoryOnly = next; // quota or blocked storage: kept in memory for this page
  }
  for (const listener of listeners) listener();
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function useSavedStops(): SavedStop[] {
  return useSyncExternalStore(subscribe, () => get().stops, () => empty.stops);
}

export function useSavedLines(): SavedLine[] {
  return useSyncExternalStore(subscribe, () => get().lines, () => empty.lines);
}

export function isStopSaved(stopId: string): boolean {
  return get().stops.some((stop) => stop.stopId === stopId);
}

export function isLineSaved(lineKey: string): boolean {
  return get().lines.some((line) => line.lineKey === lineKey);
}

/** Save the stop, or remove it when it is already saved. */
export function toggleSavedStop(stop: SavedStop): void {
  const saved = get();
  const stops = isStopSaved(stop.stopId) ? saved.stops.filter((s) => s.stopId !== stop.stopId) : [stop, ...saved.stops].slice(0, MAX);
  write({ ...saved, stops });
}

/** Save the line, or remove it when it is already saved. */
export function toggleSavedLine(line: SavedLine): void {
  const saved = get();
  const lines = isLineSaved(line.lineKey) ? saved.lines.filter((l) => l.lineKey !== line.lineKey) : [line, ...saved.lines].slice(0, MAX);
  write({ ...saved, lines });
}
