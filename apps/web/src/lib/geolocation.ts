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

function toError(error: GeolocationPositionError): LocationError {
  if (error.code === error.PERMISSION_DENIED) return "denied";
  if (error.code === error.TIMEOUT) return "timeout";
  return "unavailable";
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

/** Replace the source (simulation, tests). Returns a function that restores the previous one. */
export function setLocationSource(next: LocationSource): () => void {
  const previous = source;
  source = next;
  return () => {
    source = previous;
  };
}
