import { emptyScene, type LonLat, type MapPin, type MapScene } from "../../map/scene";
import type { Endpoint } from "../../plan/draft";
import type { EndLabels } from "./labels";

// Compare's scene before an answer; with an answer it uses src/map/fromJourney.ts.

const lonLat = (point: { latitude: number; longitude: number }): LonLat => [point.longitude, point.latitude];

/** Before an answer: pins for the ends already known (my location has no position yet). */
export function draftScene(from: Endpoint | null, to: Endpoint | null, ends: EndLabels): MapScene {
  const pins: MapPin[] = [];
  if (from?.type === "place") pins.push({ id: "origin", role: "origin", position: lonLat(from.place), label: ends.from });
  if (to?.type === "place") pins.push({ id: "destination", role: "destination", position: lonLat(to.place), label: ends.to });
  return pins.length === 0 ? emptyScene : { ...emptyScene, pins, camera: "fit" };
}
