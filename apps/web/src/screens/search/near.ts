import { useEffect, useState } from "react";
import { locationSource } from "../../lib/geolocation";

// `near` for place search only when location permission is already granted (design:
// Where to, "near only when location is already granted"). Without the Permissions API
// we never ask: search must not trigger a prompt.

export async function grantedPosition(): Promise<{ latitude: number; longitude: number } | null> {
  const permissions = globalThis.navigator?.permissions;
  if (!permissions?.query) return null;
  try {
    const status = await permissions.query({ name: "geolocation" as PermissionName });
    if (status.state !== "granted") return null;
  } catch {
    return null;
  }
  const result = await locationSource().current();
  return result.ok ? { latitude: result.fix.latitude, longitude: result.fix.longitude } : null;
}

export function useNearIfGranted(): { latitude: number; longitude: number } | null {
  const [near, setNear] = useState<{ latitude: number; longitude: number } | null>(null);
  useEffect(() => {
    let live = true;
    void grantedPosition().then((position) => {
      if (live) setNear(position);
    });
    return () => {
      live = false;
    };
  }, []);
  return near;
}
