/**
 * Encode an API identifier (trip ref, stop ID, route ID) as one URL path segment.
 *
 * `leg.transit.engineTripId` is used verbatim as `GET /v1/trips/{tripRef}`. Real IDs look
 * like `20260930_23:50_mot60day_584668860_300926`; `encodeURIComponent` turns `:` into
 * `%3A`, which the API decodes back. An ID containing `/` cannot be sent: the server
 * decodes `%2F` before routing, so it would reach another route or 404. `.` and `..`
 * would be normalised away by the URL parser. Those are refused here instead of sent.
 */
export type PathRefResult =
  | { ok: true; segment: string }
  | { ok: false; reason: "empty" | "contains_slash" | "dot_segment" | "too_long" };

export const MAX_REF_LENGTH = 768;

export function encodePathRef(ref: string): PathRefResult {
  if (ref.length === 0) return { ok: false, reason: "empty" };
  if (ref.length > MAX_REF_LENGTH) return { ok: false, reason: "too_long" };
  if (ref.includes("/") || ref.includes("\\")) return { ok: false, reason: "contains_slash" };
  if (ref === "." || ref === "..") return { ok: false, reason: "dot_segment" };
  return { ok: true, segment: encodeURIComponent(ref) };
}
