import type { Journey, Leg } from "../api/types";
import { formatClock, type Lang } from "../lib/time";

// The comparison chart (design: Compare, "Chart"): every journey is a bar on one shared
// time axis from the earliest departure to the latest arrival. Positions are fractions of
// the axis measured from its inline start, so CSS `inset-inline-start` puts the earliest
// time on the right in Hebrew and on the left in English without mirroring the data.
//
// Legibility: a ride shorter than MIN_TRANSIT_FRACTION of the axis is widened to it so its
// line number can be read; the room comes out of the same row's walks and waits first,
// and only when those cannot give enough does the row grow past its own times (it never
// leaves the axis). Every number stays the API's; only the drawing is adjusted.

export const RESERVED_ROWS = 3;
/** A ride is drawn at least this wide (about 26 px on a 360 px phone), with its label. */
export const MIN_TRANSIT_FRACTION = 0.085;
/** A walk or a wait keeps at least this much of the axis when room is taken from it. */
export const MIN_GAP_FRACTION = 0.012;
/** Below this share of the axis a segment is drawn without its text label. */
export const MIN_LABEL_FRACTION = MIN_TRANSIT_FRACTION;

export type SegmentKind = "walk" | "transit" | "wait";
export type TransitMode = "bus" | "rail" | "tram";

export interface ChartSegment {
  kind: SegmentKind;
  /** Fraction of the axis from its inline start (earliest time), after widening. */
  start: number;
  width: number;
  /** Line number for a bus or light rail; "rail" for a train (drawn as a train icon). */
  label: string | null;
  rail: boolean;
  /** Ride mode (colour and icon); null for walks and waits. */
  mode: TransitMode | null;
  showLabel: boolean;
  legIndex: number | null;
}

export interface ChartRow {
  index: number;
  journeyId: string;
  departure: string;
  arrival: string;
  durationSeconds: number;
  transfers: number;
  segments: ChartSegment[];
}

export interface ChartTick {
  at: string;
  fraction: number;
  label: string;
}

export interface ChartLayout {
  axisStart: string;
  axisEnd: string;
  rows: ChartRow[];
  ticks: ChartTick[];
}

export function isRail(leg: Leg): boolean {
  return /^(rail|train|heavy_rail)$/i.test(leg.mode);
}

/** The ride's mode for colour and icon: train, light rail / tram / metro, otherwise bus. */
export function transitMode(leg: Leg): TransitMode {
  if (isRail(leg)) return "rail";
  if (/tram|light|subway|metro|cable/i.test(leg.mode)) return "tram";
  return "bus";
}

/** A transit leg's short label: its line number, or null for a train (never an empty label). */
export function lineLabel(leg: Leg): string | null {
  const name = leg.transit?.routeShortName.trim() ?? "";
  return name === "" ? null : name;
}

const ms = (iso: string) => Date.parse(iso);

const TICK_STEPS_MIN = [10, 15, 20, 30, 60, 120, 180];

function ticksFor(start: number, end: number, lang: Lang, maxTicks = 4): ChartTick[] {
  const span = end - start;
  if (span <= 0) return [];
  const step = (TICK_STEPS_MIN.find((minutes) => span / (minutes * 60_000) <= maxTicks) ?? 240) * 60_000;
  const ticks: ChartTick[] = [];
  // Israel's offset is a whole number of hours, so UTC multiples of the step fall on
  // round Israel wall times too.
  for (let at = Math.ceil(start / step) * step; at <= end; at += step) {
    const iso = new Date(at).toISOString();
    ticks.push({ at: iso, fraction: (at - start) / span, label: formatClock(iso, lang) });
  }
  return ticks;
}

/**
 * Widen short rides to `minTransit`. The room comes, in order, from the row's walks and
 * waits (down to `MIN_GAP_FRACTION` each), then from its longer rides (never below the
 * minimum), so the row keeps its own departure and arrival on the axis; only a row of
 * nothing but short rides grows (towards the axis end, then back). Order and adjacency
 * are kept; the row stays inside [0, 1].
 */
export function widenRow(segments: ChartSegment[], minTransit = MIN_TRANSIT_FRACTION): ChartSegment[] {
  if (segments.length === 0) return segments;
  const rowStart = segments[0]!.start;
  const widths = segments.map((s) => (s.kind === "transit" ? Math.max(s.width, minTransit) : s.width));
  let extra = widths.reduce((sum, w, i) => sum + (w - segments[i]!.width), 0);
  const takeFrom = (floor: (index: number) => number | null) => {
    if (extra <= 0) return;
    const give = widths.map((w, i) => {
      const min = floor(i);
      return min === null ? 0 : Math.max(0, w - min);
    });
    const available = give.reduce((sum, g) => sum + g, 0);
    const take = Math.min(extra, available);
    if (take <= 0) return;
    give.forEach((g, i) => (widths[i] = widths[i]! - (g * take) / available));
    extra -= take;
  };
  takeFrom((i) => (segments[i]!.kind === "transit" ? null : Math.min(widths[i]!, MIN_GAP_FRACTION)));
  takeFrom((i) => (segments[i]!.kind === "transit" ? minTransit : null));
  const total = widths.reduce((sum, w) => sum + w, 0);
  // Grow towards the axis end first; slide back only when the end is reached.
  const start = Math.max(0, Math.min(rowStart, 1 - total));
  let cursor = start;
  return segments.map((segment, i) => {
    const width = Math.min(widths[i]!, 1);
    const placed = { ...segment, start: cursor, width };
    cursor += width;
    return { ...placed, showLabel: placed.label !== null && width >= MIN_LABEL_FRACTION - 1e-9 };
  });
}

export function layoutChart(journeys: readonly Journey[], lang: Lang, minTransit = MIN_TRANSIT_FRACTION): ChartLayout | null {
  if (journeys.length === 0) return null;
  const start = Math.min(...journeys.map((j) => ms(j.timing.scheduledDeparture)));
  const end = Math.max(...journeys.map((j) => ms(j.timing.scheduledArrival)));
  const span = Math.max(end - start, 60_000);
  const fraction = (at: number) => Math.min(1, Math.max(0, (at - start) / span));

  const rows = journeys.map((journey, index): ChartRow => {
    const segments: ChartSegment[] = [];
    let cursor: number | null = null;
    journey.legs.forEach((leg, legIndex) => {
      const legStart = ms(leg.timing.scheduledDeparture);
      const legEnd = ms(leg.timing.scheduledArrival);
      if (cursor !== null && legStart > cursor) {
        segments.push({
          kind: "wait",
          start: fraction(cursor),
          width: fraction(legStart) - fraction(cursor),
          label: null,
          rail: false,
          mode: null,
          showLabel: false,
          legIndex: null,
        });
      }
      const width = fraction(legEnd) - fraction(legStart);
      const rail = leg.kind === "transit" && isRail(leg);
      const label = leg.kind === "transit" ? (rail ? "rail" : lineLabel(leg)) : null;
      segments.push({
        kind: leg.kind,
        start: fraction(legStart),
        width,
        label,
        rail,
        mode: leg.kind === "transit" ? transitMode(leg) : null,
        showLabel: label !== null && width >= MIN_LABEL_FRACTION,
        legIndex,
      });
      cursor = Math.max(cursor ?? legEnd, legEnd);
    });
    return {
      index,
      journeyId: journey.id,
      departure: journey.timing.scheduledDeparture,
      arrival: journey.timing.scheduledArrival,
      durationSeconds: journey.durationSeconds,
      transfers: journey.transfers,
      segments: minTransit > 0 ? widenRow(segments, minTransit) : segments,
    };
  });

  return {
    axisStart: new Date(start).toISOString(),
    axisEnd: new Date(start + span).toISOString(),
    rows,
    ticks: ticksFor(start, start + span, lang),
  };
}

/**
 * Where a fraction measured from the inline start lands from the physical left edge:
 * the earliest time is on the left in English and on the right in Hebrew.
 */
export function physicalLeft(start: number, width: number, dir: "rtl" | "ltr"): number {
  return dir === "ltr" ? start : 1 - start - width;
}
