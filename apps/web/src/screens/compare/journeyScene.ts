import type { Journey } from "../../api/types";
import { emptyScene, type LonLat, type MapPin, type MapScene } from "../../map/scene";
import { isRail, lineLabel } from "../../plan/chartLayout";
import type { Endpoint } from "../../plan/draft";
import { placeName, trainDestination, type EndLabels } from "./labels";

// STAND-IN for S3's src/map/fromJourney.ts `journeyToScene`: the coordinator may swap this
// for the map slice's converter. The selected journey's legs (GeoJSON LineString is
// [lon, lat]; a null geometry draws no line), its two ends as pins, camera "fit".

const lonLat = (point: { latitude: number; longitude: number }): LonLat => [point.longitude, point.latitude];

function toLonLat(coordinates: number[][] | undefined): LonLat[] | null {
  if (!coordinates || coordinates.length < 2) return null;
  return coordinates.map((pair) => [pair[0]!, pair[1]!] as LonLat);
}

export function journeyScene(journey: Journey, ends: EndLabels): MapScene {
  const first = journey.legs[0];
  const last = journey.legs[journey.legs.length - 1];
  const pins: MapPin[] = [];
  if (first) pins.push({ id: "origin", role: "origin", position: lonLat(first.from), label: placeName(first.from.name, ends) });
  if (last) pins.push({ id: "destination", role: "destination", position: lonLat(last.to), label: placeName(last.to.name, ends) });
  journey.legs.forEach((leg, index) => {
    if (leg.kind === "transit" && index > 0) {
      pins.push({ id: `transfer-${index}`, role: "transfer", position: lonLat(leg.from), label: placeName(leg.from.name, ends) });
    }
  });
  return {
    route: journey.legs.map((leg) => ({
      kind: leg.kind,
      mode: leg.mode,
      coordinates: leg.geometry ? toLonLat(leg.geometry.coordinates) : null,
      from: lonLat(leg.from),
      to: lonLat(leg.to),
      label: leg.kind === "transit" ? (isRail(leg) ? trainDestination(leg, ends) : lineLabel(leg)) : null,
    })),
    pins,
    user: null,
    camera: "fit",
    pick: false,
  };
}

/** Before an answer: pins for the ends already known (my location has no position yet). */
export function draftScene(from: Endpoint, to: Endpoint | null, ends: EndLabels): MapScene {
  const pins: MapPin[] = [];
  if (from.type === "place") pins.push({ id: "origin", role: "origin", position: lonLat(from.place), label: ends.from });
  if (to?.type === "place") pins.push({ id: "destination", role: "destination", position: lonLat(to.place), label: ends.to });
  return pins.length === 0 ? emptyScene : { ...emptyScene, pins, camera: "fit" };
}
