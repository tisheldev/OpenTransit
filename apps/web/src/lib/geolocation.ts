// Device location behind one replaceable source (design: Privacy: location only after a
// tap, never stored). S6 swaps in a simulated source for tests and demos.

export interface Fix {
  latitude: number;
  longitude: number;
  accuracyMeters: number | null;
  /** Epoch milliseconds when the fix was taken. */
  at: number;
}

export type LocationError = "denied" | "unavailable" | "timeout" | "unsupported";

export interface LocationSource {
  /** One fix, for "my location" in a plan. */
  current(): Promise<{ ok: true; fix: Fix } | { ok: false; error: LocationError }>;
  /** Continuous fixes while navigating; returns a stop function. */
  watch(onFix: (fix: Fix) => void, onError: (error: LocationError) => void): () => void;
}

/**
 * A refusal seen in this page (the prompt dismissed or blocked). Browsers often keep the
 * permission at "prompt" after a dismissal, so the Permissions API alone would still say
 * "ask"; until a reload, location then counts as unavailable.
 */
let deniedInPage = false;
const deniedListeners = new Set<() => void>();

function toError(error: GeolocationPositionError): LocationError {
  if (error.code === error.PERMISSION_DENIED) {
    if (!deniedInPage) {
      deniedInPage = true;
      for (const listener of deniedListeners) listener();
    }
    return "denied";
  }
  if (error.code === error.TIMEOUT) return "timeout";
  return "unavailable";
}

/** Forget a refusal seen in this page (tests). */
export function resetLocationDenial(): void {
  deniedInPage = false;
}

const toFix = (position: GeolocationPosition): Fix => ({
  latitude: position.coords.latitude,
  longitude: position.coords.longitude,
  accuracyMeters: Number.isFinite(position.coords.accuracy) ? position.coords.accuracy : null,
  at: position.timestamp,
});

export const browserLocation: LocationSource = {
  current() {
    const geo = globalThis.navigator?.geolocation;
    if (!geo) return Promise.resolve({ ok: false, error: "unsupported" });
    return new Promise((resolve) => {
      geo.getCurrentPosition(
        (position) => resolve({ ok: true, fix: toFix(position) }),
        (error) => resolve({ ok: false, error: toError(error) }),
        { enableHighAccuracy: true, timeout: 15_000, maximumAge: 30_000 },
      );
    });
  },
  watch(onFix, onError) {
    const geo = globalThis.navigator?.geolocation;
    if (!geo) {
      onError("unsupported");
      return () => {};
    }
    const id = geo.watchPosition(
      (position) => onFix(toFix(position)),
      (error) => onError(toError(error)),
      { enableHighAccuracy: true, maximumAge: 5_000 },
    );
    return () => geo.clearWatch(id);
  },
};

let source: LocationSource = browserLocation;

export function locationSource(): LocationSource {
  return source;
}

// Whether "my location" can work at all, decided before it is used (design: Home, the
// plan's From). Browsers only offer geolocation in a secure context (https or localhost):
// a phone on a plain-http preview never gets a position, whatever the passenger answers.

export type LocationAvailability = "available" | "prompt" | "unavailable";
/** Why location is unavailable, for a one-line reason next to "My location". */
export type LocationUnavailableReason = "insecure" | "unsupported" | "denied";

function browserReason(): LocationUnavailableReason | null {
  if (typeof window === "undefined") return "unsupported";
  if (window.isSecureContext === false) return "insecure";
  if (!globalThis.navigator?.geolocation) return "unsupported";
  return null;
}

/**
 * Synchronous: a secure context with the Geolocation API. True does not mean permission
 * was given. A replaced source (simulation, tests) is always possible.
 */
export function isLocationPossible(): boolean {
  return source !== browserLocation || browserReason() === null;
}

async function geolocationPermission(): Promise<PermissionStatus | null> {
  const permissions = globalThis.navigator?.permissions;
  if (!permissions?.query) return null;
  try {
    return await permissions.query({ name: "geolocation" as PermissionName });
  } catch {
    return null;
  }
}

/** Availability with its reason (null unless unavailable). Never prompts. */
export async function locationAvailabilityDetail(): Promise<{
  availability: LocationAvailability;
  reason: LocationUnavailableReason | null;
}> {
  if (source !== browserLocation) return { availability: "available", reason: null };
  const reason = browserReason();
  if (reason) return { availability: "unavailable", reason };
  const state = (await geolocationPermission())?.state ?? null;
  if (state === "granted") {
    deniedInPage = false; // allowed later in the browser's settings
    return { availability: "available", reason: null };
  }
  if (state === "denied" || deniedInPage) return { availability: "unavailable", reason: "denied" };
  return { availability: "prompt", reason: null };
}

/** Insecure context, no API, or permission denied → unavailable. Never prompts. */
export async function locationAvailability(): Promise<LocationAvailability> {
  return (await locationAvailabilityDetail()).availability;
}

/**
 * Calls `listener` with the current availability and again whenever the permission
 * changes (a denial in the browser's prompt, or a change in its settings). Returns an
 * unsubscribe function.
 */
export function watchLocationAvailability(
  listener: (detail: { availability: LocationAvailability; reason: LocationUnavailableReason | null }) => void,
): () => void {
  let live = true;
  let status: PermissionStatus | null = null;
  const onChange = () => {
    void locationAvailabilityDetail().then((detail) => {
      if (live) listener(detail);
    });
  };
  onChange();
  deniedListeners.add(onChange);
  if (source === browserLocation && browserReason() === null) {
    void geolocationPermission().then((found) => {
      if (!live || !found) return;
      status = found;
      status.addEventListener?.("change", onChange);
    });
  }
  return () => {
    live = false;
    deniedListeners.delete(onChange);
    status?.removeEventListener?.("change", onChange);
  };
}

/** Replace the source (simulation, tests). Returns a function that restores the previous one. */
export function setLocationSource(next: LocationSource): () => void {
  const previous = source;
  source = next;
  return () => {
    source = previous;
  };
}
