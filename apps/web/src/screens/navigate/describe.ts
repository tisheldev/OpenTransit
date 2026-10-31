import type { MessageKey } from "../../i18n/messages";
import { formatDuration } from "../../lib/format";
import { formatClock, ZONE, type Lang } from "../../lib/time";
import type { NavState } from "../../nav/engine";
import type { NavPlace, NavStep } from "../../nav/steps";

// Text for steps (card, checklist, announcements). Pure; every fact comes from the step
// or the engine state. Times are scheduled (the card says so once, in its header).

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

/**
 * In an English (LTR) line a Hebrew name followed by a number pulls the number into its
 * right-to-left run ("Walk to הטכניון · 4 min" shows as "4 · הטכניון min"): isolate it
 * (FSI … PDI). Hebrew lines are right-to-left already and need nothing.
 */
export function isolate(name: string, lang: Lang): string {
  return lang === "en" ? `⁨${name}⁩` : name;
}

function modeLabel(mode: string, t: T): string {
  const m = mode.toLowerCase();
  if (m === "bus") return t("nav.mode.bus");
  if (m === "rail") return t("nav.mode.rail");
  if (m === "light_rail" || m === "tram" || m === "subway") return t("nav.mode.light_rail");
  return t("nav.mode.other");
}

const isNumeric = (value: string) => /^\d+$/.test(value);
const isRail = (step: NavStep) => step.ride?.mode.toLowerCase() === "rail";

/** GTFS headsigns separate city and place with "_" ("כפר סבא_תחנה מרכזית"). */
export function readableHeadsign(headsign: string): string {
  return headsign.replace(/\s*_\s*/g, " · ").trim();
}

/**
 * "Bus 249"; a train (empty short name, numeric headsign = train number) is "Train 156",
 * never named after where the passenger gets off (that reads as its destination).
 */
export function rideName(step: NavStep, t: T): string {
  const ride = step.ride;
  if (!ride) return "";
  const mode = modeLabel(ride.mode, t);
  if (ride.lineLabel) return `${mode} ${ride.lineLabel}`;
  const headsign = ride.headsign?.trim() ?? "";
  return isNumeric(headsign) ? `${mode} ${headsign}` : mode;
}

/** "towards Kfar Saba · Central Station" when the headsign is a place (not a train number). */
export function rideHeadsign(step: NavStep): string | null {
  const headsign = step.ride?.headsign?.trim() ?? "";
  if (!headsign || isNumeric(headsign)) return null;
  return readableHeadsign(headsign);
}

/** A platform only for rail and only when the API gives one (API-C2 pending: never today). */
export function ridePlatform(step: NavStep): string | null {
  return isRail(step) ? (step.ride?.platform ?? null) : null;
}

/** The stop a walk leads to; a station when a train follows ("HaShalom" alone reads as a street). */
export function walkTargetName(step: NavStep, following: NavStep | undefined, labels: EndLabels, t: T): string {
  const name = placeName(step.target, labels, t);
  return following && isRail(following) && step.kind !== "walk_to_destination" ? t("nav.station", { stop: name }) : name;
}

/** Bus stop code for finding the right pole; not shown for stations (rail). */
export function stopCodeFor(target: NavPlace, nextRide: NavStep | undefined): string | null {
  if (nextRide && isRail(nextRide)) return null;
  const code = target.stopCode?.trim();
  return code ? code : null;
}

/** A transfer that stays at the same stop: same stop ID, or a zero-length walk in the journey. */
export function isSameStop(step: NavStep): boolean {
  if (step.from?.stopId && step.from.stopId === step.target.stopId) return true;
  return step.distanceMeters !== null && step.distanceMeters < 1;
}

export function stopsText(count: number, t: T): string {
  return count === 1 ? t("nav.stopCountOne") : t("nav.stopCount", { count });
}

export function stopsLeftText(count: number, t: T): string {
  return count === 1 ? t("nav.stopsLeftOne") : t("nav.stopsLeft", { count });
}

/**
 * Stops on the current ride. "N stops left" only once the engine has measured progress
 * (a passed call lowered stopsLeft); before that "N stops to your exit", which does not
 * pretend to count down. Null without trip detail (the count is hidden, never guessed).
 */
export function rideStopsText(step: NavStep, state: NavState, t: T): string | null {
  const count = step.ride?.stopCount ?? null;
  if (count === null) return null;
  const onThisRide = state.stepIndex === step.index;
  const left = onThisRide ? state.stopsLeft : null;
  if (left !== null && left < count) return stopsLeftText(left, t);
  return count === 1 ? t("nav.stopsToExitOne") : t("nav.stopsToExit", { count });
}

/** Scheduled time to change between two rides: next departure − previous arrival. */
export function transferWindowSeconds(steps: readonly NavStep[], index: number): number | null {
  const step = steps[index];
  const before = steps[index - 1];
  const after = steps[index + 1];
  if (step?.kind !== "transfer_walk" || before?.kind !== "ride" || after?.kind !== "ride") return null;
  const seconds = (Date.parse(after.scheduledDeparture) - Date.parse(before.scheduledArrival)) / 1000;
  return Number.isFinite(seconds) ? Math.max(0, seconds) : null;
}

/** Beyond this a countdown says the day instead ("in 34 h 43 min" helps nobody). */
const COUNTDOWN_MAX_SECONDS = 12 * 3600;

const dayFormat = {
  he: new Intl.DateTimeFormat("he-IL", { timeZone: ZONE, weekday: "short", day: "numeric", month: "numeric", numberingSystem: "latn" }),
  en: new Intl.DateTimeFormat("en-GB", { timeZone: ZONE, weekday: "short", day: "numeric", month: "short" }),
} as const;

/** Relative to the display clock: "in 12 min", "now", "3 min ago"; far ahead, the day. */
export function relativeText(at: string, now: number, t: T, lang: Lang, kind: "departure" | "arrival"): string {
  const seconds = (Date.parse(at) - now) / 1000;
  if (seconds >= COUNTDOWN_MAX_SECONDS) return t("nav.onDay", { day: dayFormat[lang].format(new Date(at)) });
  if (seconds >= 60) return t("nav.in", { duration: formatDuration(seconds, lang) });
  if (seconds > -60) return kind === "departure" ? t("nav.departingNow") : t("nav.now");
  return t("nav.ago", { duration: formatDuration(-seconds, lang) });
}

/** One line per step, for announcements and the card's "then" line. */
export function stepSummary(step: NavStep, labels: EndLabels, t: T, lang: Lang, following?: NavStep): string {
  const duration = formatDuration(step.durationSeconds, lang);
  switch (step.kind) {
    case "walk_to_stop":
      return t("nav.summary.walkToStop", { stop: isolate(walkTargetName(step, following, labels, t), lang), duration });
    case "transfer_walk":
      return isSameStop(step) ? t("nav.summary.transferSameStop") : t("nav.summary.transfer", { duration });
    case "walk_to_destination":
      return t("nav.summary.walkToDestination", { place: isolate(placeName(step.target, labels, t), lang), duration });
    case "ride":
      return t("nav.summary.ride", { ride: rideName(step, t), stop: step.target.name });
    case "arrive":
      return t("nav.summary.arrive", { time: formatClock(step.scheduledArrival, lang) });
  }
}

export interface RowText {
  /** Scheduled start of the step (arrival time for "arrive"). */
  time: string;
  main: string;
  sub: string | null;
}

/** A checklist row: its time, what to do, and for rides where to get off. */
export function rowText(step: NavStep, labels: EndLabels, t: T, lang: Lang, following?: NavStep): RowText {
  const time = formatClock(step.kind === "arrive" ? step.scheduledArrival : step.scheduledDeparture, lang);
  const duration = formatDuration(step.durationSeconds, lang);
  switch (step.kind) {
    case "walk_to_stop":
      return { time, main: t("nav.summary.walkToStop", { stop: isolate(walkTargetName(step, following, labels, t), lang), duration }), sub: null };
    case "transfer_walk":
      return { time, main: isSameStop(step) ? t("nav.summary.transferSameStop") : t("nav.summary.transfer", { duration }), sub: null };
    case "walk_to_destination":
      return { time, main: t("nav.summary.walkToDestination", { place: isolate(placeName(step.target, labels, t), lang), duration }), sub: null };
    case "ride": {
      const count = step.ride?.stopCount ?? null;
      const name = rideName(step, t);
      return {
        time,
        main: count === null ? name : `${name} · ${stopsText(count, t)}`,
        sub: t("nav.exitAt", { stop: isolate(step.target.name, lang), time: formatClock(step.scheduledArrival, lang) }),
      };
    }
    case "arrive":
      return { time, main: t("nav.row.arrive", { place: placeName(step.target, labels, t) }), sub: null };
  }
}

/** What follows the current step, for the ride card ("Then: change, 3 min · Bus 825 08:51"). */
export function thenText(steps: readonly NavStep[], index: number, labels: EndLabels, t: T, lang: Lang): string | null {
  const following = steps[index + 1];
  if (!following) return null;
  if (following.kind === "transfer_walk") {
    const ride = steps[following.index + 1];
    if (ride?.kind !== "ride") return t("nav.then", { next: stepSummary(following, labels, t, lang) });
    const window = transferWindowSeconds(steps, following.index);
    const parts = [t("nav.then.change", { ride: rideName(ride, t), time: formatClock(ride.scheduledDeparture, lang) })];
    if (isSameStop(following)) parts.push(t("nav.then.sameStop"));
    if (window !== null) parts.push(t("nav.transferWindow", { duration: formatDuration(window, lang) }));
    return t("nav.then", { next: parts.join(" · ") });
  }
  if (following.kind === "ride") {
    return t("nav.then", { next: t("nav.then.change", { ride: rideName(following, t), time: formatClock(following.scheduledDeparture, lang) }) });
  }
  if (following.kind === "arrive") {
    return t("nav.then", { next: t("nav.arrival", { time: formatClock(following.scheduledArrival, lang) }) });
  }
  return t("nav.then", { next: stepSummary(following, labels, t, lang) });
}
