import type { SavedPlace } from "../storage/local";

// The plan draft (design: Domain model, PlaceChoice / When / PlanDraft). It lives in
// React state in PlanProvider and is mirrored into sessionStorage so a reload keeps the
// trip being planned; it is never written to localStorage.

export type PlaceKind = "stop" | "station" | "address" | "poi" | "pin" | "saved";

/** A chosen place. Coordinates and label are the truth; `stopId`/`placeRef` are hints. */
export interface PlaceChoice {
  label: string;
  locality: string | null;
  kind: PlaceKind;
  latitude: number;
  longitude: number;
  /** `mot:stop:…` when the place is a stop or station: sent as `{kind: "stop"}`. */
  stopId: string | null;
  /** A search `locationRef` of kind `place`, bound to `refGenerationId`. */
  placeRef: string | null;
  refGenerationId: string | null;
}

/** "My location" is resolved to a coordinate only when a request needs it. */
export type Endpoint = { type: "myLocation" } | { type: "place"; place: PlaceChoice };

/** `wall` is an Israel wall time `YYYY-MM-DDTHH:mm`; see lib/time departureInstant(). */
export type When =
  | { mode: "now" }
  | { mode: "depart_at" | "arrive_by"; wall: string; offset: "auto" | "+03:00" | "+02:00" };

export interface PlanDraft {
  /** Null when no start is chosen yet (e.g. location unavailable): the plan asks for one. */
  from: Endpoint | null;
  to: Endpoint | null;
  when: When;
}

export const initialDraft: PlanDraft = { from: { type: "myLocation" }, to: null, when: { mode: "now" } };

export function sameEndpoint(a: Endpoint | null, b: Endpoint | null): boolean {
  if (a === null || b === null) return a === b;
  if (a.type === "myLocation" || b.type === "myLocation") return a.type === b.type;
  return a.place.latitude === b.place.latitude && a.place.longitude === b.place.longitude;
}

/** Saved places and recents store coordinates, label and a ref hint (storage/local.ts). */
export function choiceFromSaved(saved: SavedPlace): PlaceChoice {
  return {
    label: saved.label,
    locality: null,
    kind: saved.stopId ? "stop" : "saved",
    latitude: saved.latitude,
    longitude: saved.longitude,
    stopId: saved.stopId,
    placeRef: saved.placeRefHint,
    refGenerationId: null,
  };
}

export function savedFromChoice(choice: PlaceChoice, id: string, now: Date = new Date()): SavedPlace {
  return {
    id,
    label: choice.locality ? `${choice.label}, ${choice.locality}` : choice.label,
    latitude: choice.latitude,
    longitude: choice.longitude,
    stopId: choice.stopId,
    placeRefHint: choice.placeRef,
    savedAt: now.toISOString(),
  };
}

/** Recents are deduplicated by coordinates (design: On-device storage). */
export function recentId(choice: PlaceChoice): string {
  return `${choice.latitude.toFixed(5)},${choice.longitude.toFixed(5)}`;
}
