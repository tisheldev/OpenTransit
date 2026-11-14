import type { LineItem, PlaceCandidate } from "../../api/schemas";
import { haversineMeters, type LatLon } from "../../nav/geo";

// Search's one list (board 2; user, 12 November 2026: "I'm not sure if I want the stops to
// show up before places always"): places, stops and lines in one order by best match. The
// order is the client design's suggestion: how well the text matches first, then the
// distance from the passenger; with a number typed, lines with exactly that number lead
// (user, 14 November 2026: "exact number matches rank first"). Within a tie the API's own
// order stands. Pure, so it unit-tests without the screen.

/** Lines shown before "N more lines" (as drawn: four). */
export const LINES_SHOWN = 4;

export type MixedItem =
  | { kind: "line"; key: string; line: LineItem; rank: number; distance: number | null; order: number }
  | { kind: "place"; key: string; candidate: PlaceCandidate; rank: number; distance: number | null; order: number };

export type ListItem = MixedItem | { kind: "more"; key: "more"; count: number; atLeast: boolean };

const normal = (text: string) => text.normalize("NFC").trim().toLocaleLowerCase();

/** A query that names a line: it starts with a digit ("8", "82", "1א"). */
export const isLineQuery = (q: string) => /^\d/.test(q.trim());

/**
 * How well a name matches what was typed: 0 the whole name, 1 its start, 2 the start of a
 * word in it, 3 anywhere in it, 4 not literally (the API matched it some other way:
 * spelling, the other language, an alias).
 */
export function matchRank(text: string, typed: string): number {
  const name = normal(text);
  const q = normal(typed);
  if (q === "") return 4;
  if (name === q) return 0;
  if (name.startsWith(q)) return 1;
  if (name.split(/[\s/,()\-־–]+/).some((word) => word.startsWith(q))) return 2;
  return name.includes(q) ? 3 : 4;
}

/** A place's name for matching: a stop's display name is "street/cross street". */
const placeName = (candidate: PlaceCandidate) => candidate.displayName;

function placeDistance(candidate: PlaceCandidate, near: LatLon | null): number | null {
  if (near) return haversineMeters(near, candidate.coordinates);
  const sent = (candidate as Record<string, unknown>).distance;
  return typeof sent === "number" && Number.isFinite(sent) ? sent : null;
}

const placeKey = (candidate: PlaceCandidate, index: number) =>
  candidate.kind === "stop" || candidate.kind === "station"
    ? `place:${candidate.id}:${index}`
    : `place:${String(candidate.placeRef).slice(-24)}:${index}`;

/** Places and lines in one order. Either list may be empty. */
export function mixResults(input: {
  typed: string;
  places: readonly PlaceCandidate[];
  lines: readonly LineItem[];
  near: LatLon | null;
}): MixedItem[] {
  const numeric = isLineQuery(input.typed);
  const q = normal(input.typed);
  const items: MixedItem[] = [
    ...input.lines.map((line, index): MixedItem => {
      const exact = normal(line.shortName) === q;
      return {
        kind: "line",
        key: `line:${line.lineKey}`,
        line,
        // An exact number outranks any name; a longer number that starts with it is a prefix match.
        rank: exact && numeric ? -1 : matchRank(line.shortName, input.typed),
        distance: line.nearestStop?.distanceM ?? null,
        order: index,
      };
    }),
    ...input.places.map(
      (candidate, index): MixedItem => ({
        kind: "place",
        key: placeKey(candidate, index),
        candidate,
        rank: matchRank(placeName(candidate), input.typed),
        distance: placeDistance(candidate, input.near),
        order: index,
      }),
    ),
  ];
  return items.sort((a, b) => {
    if (a.rank !== b.rank) return a.rank - b.rank;
    if (a.distance !== b.distance) {
      if (a.distance === null) return 1;
      if (b.distance === null) return -1;
      return a.distance - b.distance;
    }
    // Same match, same (or no) distance: a typed number favours lines; else the API's order.
    if (a.kind !== b.kind) return (a.kind === "line" ? -1 : 1) * (numeric ? 1 : -1);
    return a.order - b.order;
  });
}

/**
 * The list as shown: the first LINES_SHOWN lines in their places, then one "N more lines"
 * row right after the last of them, unless the passenger opened it. `atLeast` says the
 * API holds more than it returned (a further page).
 */
export function withMoreRow(items: readonly MixedItem[], expanded: boolean, morePages: boolean): ListItem[] {
  const lines = items.filter((item) => item.kind === "line").length;
  if (expanded || lines <= LINES_SHOWN) return [...items];
  const out: ListItem[] = [];
  let seen = 0;
  for (const item of items) {
    if (item.kind === "line") {
      seen += 1;
      if (seen > LINES_SHOWN) continue;
    }
    out.push(item);
    if (item.kind === "line" && seen === LINES_SHOWN) out.push({ kind: "more", key: "more", count: lines - LINES_SHOWN, atLeast: morePages });
  }
  return out;
}
