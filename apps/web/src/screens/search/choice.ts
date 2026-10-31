import type { Meta, PlaceCandidate } from "../../api/schemas";
import type { LonLat } from "../../map/scene";
import type { PlaceChoice } from "../../plan/draft";

// From a search result (or a map pin) to the PlaceChoice the plan and storage hold
// (design: Domain model). Coordinates and label are always kept; a stop carries its
// stopId, a geocoded place its locationRef bound to the answer's generation.

/**
 * Stop localities arrive as the timetable's description, e.g.
 * "רחוב: דיזנגוף 50 עיר: תל אביב יפו רציף:  קומה: ". Show "street, city" instead.
 */
export function readableLocality(locality: string | null): string | null {
  if (locality === null) return null;
  const match = /רחוב:\s*(.*?)\s*עיר:\s*(.*?)\s*(?:רציף:|$)/.exec(locality);
  if (!match) return locality.trim() || null;
  const parts = [match[1], match[2]].map((part) => part?.trim() ?? "").filter(Boolean);
  return parts.length ? parts.join(", ") : null;
}

export function choiceFromCandidate(candidate: PlaceCandidate, meta: Meta): PlaceChoice {
  const base = {
    label: candidate.displayName,
    locality: readableLocality(candidate.locality),
    latitude: candidate.coordinates.latitude,
    longitude: candidate.coordinates.longitude,
  };
  if (candidate.kind === "stop" || candidate.kind === "station") {
    return { ...base, kind: candidate.kind, stopId: candidate.locationRef.stopId, placeRef: null, refGenerationId: null };
  }
  return {
    ...base,
    kind: candidate.kind,
    stopId: null,
    placeRef: String((candidate.locationRef as { placeRef: unknown }).placeRef),
    refGenerationId: meta.generationId,
  };
}

export function formatCoordinates(latitude: number, longitude: number): string {
  return `${latitude.toFixed(5)}, ${longitude.toFixed(5)}`;
}

/** "Choose on map": the map centre becomes a coordinate end, labelled as a pin. */
export function choiceFromPin(center: LonLat, label: string): PlaceChoice {
  const [longitude, latitude] = center;
  return {
    label,
    locality: formatCoordinates(latitude, longitude),
    kind: "pin",
    latitude,
    longitude,
    stopId: null,
    placeRef: null,
    refGenerationId: null,
  };
}

/** `addressLevel: "street"` marks an address resolved only to the street (CU02). */
export function isStreetLevel(candidate: PlaceCandidate): boolean {
  return candidate.kind === "address" && (candidate as { addressLevel?: unknown }).addressLevel === "street";
}

export function candidateKey(candidate: PlaceCandidate, index: number): string {
  return candidate.kind === "stop" || candidate.kind === "station"
    ? `${candidate.id}:${index}`
    : `${String(candidate.placeRef).slice(-24)}:${index}`;
}
