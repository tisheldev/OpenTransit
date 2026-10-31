import type { MessageKey } from "../../i18n/messages";
import { formatDuration } from "../../lib/format";
import { formatClock, type Lang } from "../../lib/time";
import type { NavPlace, NavStep } from "../../nav/steps";

// Text for steps (card, checklist, announcements). Pure; every fact comes from the step.

export type T = (key: MessageKey, values?: Record<string, string | number>) => string;

export interface EndLabels {
  origin: string | null;
  destination: string | null;
}

/** Coordinate ends are named "START"/"END" by the engine; the plan's labels are shown instead. */
export function placeName(place: NavPlace | null, labels: EndLabels, t: T): string {
  const name = place?.name.trim() ?? "";
  if (name === "START") return labels.origin || t("nav.origin");
  if (name === "END" || !name) return labels.destination || t("nav.destination");
  return name;
}

function modeLabel(mode: string, t: T): string {
  const m = mode.toLowerCase();
  if (m === "bus") return t("nav.mode.bus");
  if (m === "rail") return t("nav.mode.rail");
  if (m === "light_rail" || m === "tram" || m === "subway") return t("nav.mode.light_rail");
  return t("nav.mode.other");
}

/** "Bus 8" or, for rail (empty short name), "Train to Hof HaCarmel". Never an empty label. */
export function rideName(step: NavStep, t: T): string {
  const ride = step.ride;
  if (!ride) return "";
  if (ride.lineLabel) return `${modeLabel(ride.mode, t)} ${ride.lineLabel}`;
  return t("nav.ride.train", { to: ride.destinationName });
}

/** The headsign, for buses only (rail headsigns are train numbers). */
export function rideHeadsign(step: NavStep): string | null {
  const ride = step.ride;
  if (!ride?.lineLabel || !ride.headsign?.trim()) return null;
  return ride.headsign.trim();
}

export function stopsText(count: number, t: T): string {
  return t("nav.stopCount", { count });
}

export function stopsLeftText(count: number, t: T): string {
  return count === 1 ? t("nav.stopsLeftOne") : t("nav.stopsLeft", { count });
}

/** One line per step, for the checklist and announcements. */
export function stepSummary(step: NavStep, labels: EndLabels, t: T, lang: Lang): string {
  const duration = formatDuration(step.durationSeconds, lang);
  switch (step.kind) {
    case "walk_to_stop":
      return t("nav.summary.walkToStop", { stop: placeName(step.target, labels, t), duration });
    case "transfer_walk":
      return t("nav.summary.transfer", { duration });
    case "walk_to_destination":
      return t("nav.summary.walkToDestination", { place: placeName(step.target, labels, t), duration });
    case "ride": {
      const count = step.ride?.stopCount ?? null;
      return count === null
        ? t("nav.summary.rideNoStops", { ride: rideName(step, t), stop: step.target.name })
        : `${rideName(step, t)} · ${stopsText(count, t)}`;
    }
    case "arrive":
      return t("nav.summary.arrive", { time: formatClock(step.scheduledArrival, lang) });
  }
}

/** Countdown to a scheduled departure from the display clock. */
export function countdownText(departure: string, now: number, t: T, lang: Lang): string {
  const seconds = (Date.parse(departure) - now) / 1000;
  if (seconds < -60) return t("nav.countdownPast");
  if (seconds < 60) return t("nav.countdownNow");
  return t("nav.countdown", { duration: formatDuration(seconds, lang) });
}
