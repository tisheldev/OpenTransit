import { useEffect, useState } from "react";
import { locationSource } from "../../lib/geolocation";
import { useMapSelector } from "../../map/scene";
import { useLocationAvailability } from "../../shell/location";

// Where the passenger is, for Home's walking ring and a stop's distance (boards 1 and 7).
// Never asks: a fix is taken only when location permission is already granted, or comes
// from the passenger's own tap on Locate. Kept in memory for the screen, never stored.
// Without one the screens centre on the last place instead; nothing waits for it.

export interface PassengerFix {
  latitude: number;
  longitude: number;
  accuracyMeters: number | null;
}

export function usePassengerFix(): PassengerFix | null {
  const { availability } = useLocationAvailability();
  const located = useMapSelector((state) => state.located);
  const [granted, setGranted] = useState<PassengerFix | null>(null);
  const [tapped, setTapped] = useState<PassengerFix | null>(null);

  // Locate's one-off fix lives in the map state only until the next scene is published,
  // which this screen does at once: keep it here.
  if (located && (tapped?.longitude !== located.position[0] || tapped?.latitude !== located.position[1])) {
    setTapped({ longitude: located.position[0], latitude: located.position[1], accuracyMeters: located.accuracyMeters });
  }

  useEffect(() => {
    if (availability !== "available") return;
    let live = true;
    void locationSource()
      .current()
      .then((result) => {
        if (live && result.ok) {
          setGranted({ latitude: result.fix.latitude, longitude: result.fix.longitude, accuracyMeters: result.fix.accuracyMeters });
        }
      });
    return () => {
      live = false;
    };
  }, [availability]);

  return tapped ?? granted;
}
