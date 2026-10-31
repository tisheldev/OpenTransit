import type { Journey, Leg } from "../api/types";
import { formatClock, type Lang } from "../lib/time";

// The comparison chart (design: Compare, "Chart"): every journey is a bar on one shared
// time axis from the earliest departure to the latest arrival. Positions are fractions of
// the axis measured from its inline start, so CSS `inset-inline-start` puts the earliest
// time on the right in Hebrew and on the left in English without mirroring the data.

export const RESERVED_ROWS = 3;
/** Below this share of the axis a segment is drawn without its text label. */
export const MIN_LABEL_FRACTION = 0.1;

export type SegmentKind = "walk" | "transit" | "wait";

export interface ChartSegment {
  kind: SegmentKind;
  /** Fraction of the axis from its inline start (earliest time). */
  start: number;
  width: number;
  /** Line number for a bus or light rail; "rail" for a train (drawn as a train icon). */
  label: string | null;
  rail: boolean;
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

export function layoutChart(journeys: readonly Journey[], lang: Lang): ChartLayout | null {
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
      segments,
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
