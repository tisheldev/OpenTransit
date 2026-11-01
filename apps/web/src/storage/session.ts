import { SESSION_PREFIX } from "./local";

// sessionStorage for journey results and the active trip (design: Navigate, Privacy).
// It ends with the tab; nothing here is written to localStorage.

export type SessionKey = "journeys" | "activeTrip" | "plan";

function store(): Storage | null {
  try {
    return globalThis.sessionStorage ?? null;
  } catch {
    return null;
  }
}

export function readSession<T>(key: SessionKey, isValid: (value: unknown) => value is T): T | null {
  try {
    const raw = store()?.getItem(SESSION_PREFIX + key);
    if (raw === null || raw === undefined) return null;
    const value: unknown = JSON.parse(raw);
    return isValid(value) ? value : null;
  } catch {
    return null;
  }
}

export function writeSession(key: SessionKey, value: unknown): boolean {
  try {
    store()?.setItem(SESSION_PREFIX + key, JSON.stringify(value));
    return store() !== null;
  } catch {
    return false;
  }
}

export function removeSession(key: SessionKey): void {
  try {
    store()?.removeItem(SESSION_PREFIX + key);
  } catch {
    // nothing stored
  }
}
