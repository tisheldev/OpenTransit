import { useSyncExternalStore } from "react";
import {
  isLocationPossible,
  watchLocationAvailability,
  type LocationAvailability,
  type LocationUnavailableReason,
} from "../lib/geolocation";

// One shared view of whether "my location" can work (lib/geolocation.ts), for the plan's
// default From, Search's "My location" row and the Locate button. It starts from the
// synchronous check (secure context + API) and follows the permission state after that.
// It never asks for a position.

export interface LocationState {
  availability: LocationAvailability;
  reason: LocationUnavailableReason | null;
}

let snapshot: LocationState | null = null;
let stop: (() => void) | null = null;
const listeners = new Set<() => void>();

function initial(): LocationState {
  // Optimistic until the permission state is read: "prompt" means "ask when used".
  return isLocationPossible()
    ? { availability: "prompt", reason: null }
    : { availability: "unavailable", reason: window.isSecureContext === false ? "insecure" : "unsupported" };
}

function get(): LocationState {
  if (snapshot === null) snapshot = initial();
  return snapshot;
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  if (stop === null) {
    stop = watchLocationAvailability((detail) => {
      const current = get();
      if (current.availability === detail.availability && current.reason === detail.reason) return;
      snapshot = detail;
      for (const notify of listeners) notify();
    });
  }
  return () => {
    listeners.delete(listener);
    if (listeners.size === 0) {
      stop?.();
      stop = null;
      snapshot = null; // re-read on the next subscriber (tests swap the location source)
    }
  };
}

export function useLocationAvailability(): LocationState {
  return useSyncExternalStore(subscribe, get, get);
}
