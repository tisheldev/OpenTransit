import type { Journey } from "../../api/types";
import type { Fix } from "../../lib/geolocation";
import { journeyToScene } from "../../map/fromJourney";
import type { LonLat, MapPin, MapScene } from "../../map/scene";
import type { NavStep } from "../../nav/steps";
import type { EndLabels } from "./describe";

// What Navigate's map draws (design: Navigate — C05, "map: you + leg"): the current
// step's leg, its ends, and the passenger. On a long journey the whole route would be
// framed far too wide for the step at hand; the checklist carries the overview. The
// arrive step shows the whole journey.

const same = (a: LonLat, b: LonLat) => Math.abs(a[0] - b[0]) < 1e-6 && Math.abs(a[1] - b[1]) < 1e-6;

export type NavCamera = MapScene["camera"];

export function navScene(
  journey: Journey,
  step: NavStep,
  labels: EndLabels,
  fix: Fix | null,
  camera: NavCamera,
): MapScene {
  const base = journeyToScene(journey, {
    activeLeg: step.legIndex,
    originLabel: labels.origin,
    destinationLabel: labels.destination,
  });
  const user = fix ? { position: [fix.longitude, fix.latitude] as LonLat, accuracyMeters: fix.accuracyMeters } : null;
  const leg = step.legIndex === null ? undefined : base.route[step.legIndex];
  if (!leg) return { ...base, user, camera, pick: false };

  const pins: MapPin[] = base.pins.filter((pin) => same(pin.position, leg.from) || same(pin.position, leg.to));
  // Where to get off has no pin of its own when the next step walks elsewhere.
  if (step.kind === "ride" && !pins.some((pin) => same(pin.position, leg.to))) {
    pins.push({ id: `exit-${step.legIndex}`, role: "stop", position: leg.to, label: step.target.name });
  }
  return { route: [leg], pins, user, camera, pick: false };
}
