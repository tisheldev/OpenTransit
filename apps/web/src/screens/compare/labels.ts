import type { Trip } from "../../api/schemas";
import type { Journey, Leg } from "../../api/types";
import type { MessageKey } from "../../i18n/messages";
import { formatClock, israelWallTime, ZONE, type Lang } from "../../lib/time";
import { isRail, lineLabel } from "../../plan/chartLayout";
import type { Endpoint } from "../../plan/draft";
import { isWalkOnly } from "../../plan/rank";

// Text for the option rows and the route details (design: Compare and Route details;
// Language and layout rules: buses by number and headsign). Trains: the API's rail legs
// carry no line name and a train number as headsign, and the trip's terminus is not
// known (API-C1), so a train is named by its operator ("רכבת ישראל") and number and read
// from its boarding stop to its exit stop; never by the exit stop alone.

export type T = (key: MessageKey, values?: Record<string, string | number>) => string;

export interface EndLabels {
  from: string;
  to: string;
}

export function endpointLabel(endpoint: Endpoint | null, t: T): string {
  if (endpoint === null) return "";
  return endpoint.type === "myLocation" ? t("compare.myLocation") : endpoint.place.label;
}

/** The engine names coordinate ends "START" / "END"; show the passenger's own labels. */
export function placeName(name: string, ends: EndLabels): string {
  if (name === "START") return ends.from;
  if (name === "END") return ends.to;
  return name;
}

const isNumeric = (text: string) => /^\s*\d+\s*$/.test(text);

/** GTFS headsigns join city and place with "_" (e.g. "חיפה_מרכזית חוף הכרמל"). */
export function readableHeadsign(headsign: string): string {
  return headsign.replace(/_/g, " · ").trim();
}

/** A train's number: rail headsigns are train numbers ("156"). Null otherwise. */
export function trainNumber(leg: Leg): string | null {
  const headsign = leg.transit?.headsign?.trim() ?? "";
  return isRail(leg) && isNumeric(headsign) ? headsign : null;
}

/** A text headsign worth showing as a direction (never a train number). */
export function direction(leg: Leg): string | null {
  const headsign = leg.transit?.headsign?.trim() ?? "";
  return headsign === "" || isNumeric(headsign) ? null : readableHeadsign(headsign);
}

/**
 * The ride's name beside its badge (board Step): a bus by its headsign ("מסוף הטייסים"),
 * a train by its operator ("רכבת ישראל"), anything else by its operator or mode.
 */
export function rideName(leg: Leg, t: T): string {
  const toward = direction(leg);
  if (!isRail(leg) && toward) return toward;
  return leg.transit?.operatorName?.trim() || (isRail(leg) ? t("compare.train") : leg.mode);
}

/** The badge's short label on a row and on the map (board Choose): a bus by number, a train "רכבת". */
export function shortBadgeLabel(leg: Leg, t: T): string {
  if (isRail(leg)) return t("compare.train");
  return lineLabel(leg) ?? leg.transit?.operatorName ?? leg.mode;
}

/** The badge's label in the timeline: a train with its number ("רכבת 156") when known. */
export function badgeLabel(leg: Leg, t: T): string {
  if (!isRail(leg)) return shortBadgeLabel(leg, t);
  return [t("compare.train"), trainNumber(leg)].filter(Boolean).join(" ");
}

/**
 * Which side of the road a ride is boarded on, and which way it goes (board Step: "בצד
 * הזה · לכיוון סבידור"). The API's transit legs carry an optional `boarding` (API PR #35:
 * `bearingDegrees`, `stopSide` "right" | "left" | null, `towards`, `stopCount`, …). With a
 * side, the tag names the stop the passenger rides to, as the board does ("לכיוון <exit
 * stop>"); without one (older answers, a side the API could not work out) it says only
 * "לכיוון <headsign>". Read as optional data, so an answer without it still works.
 */
export interface Boarding {
  side: "right" | "left" | null;
  direction: string | null;
  bearing: number | null;
}

interface ApiBoarding {
  bearingDegrees?: unknown;
  stopSide?: unknown;
  stopCount?: unknown;
}

function apiBoarding(leg: Leg): ApiBoarding | null {
  const value = (leg as { boarding?: unknown }).boarding;
  return value && typeof value === "object" ? (value as ApiBoarding) : null;
}

export function boardingOf(leg: Leg): Boarding {
  const api = apiBoarding(leg);
  const side = api?.stopSide === "right" || api?.stopSide === "left" ? api.stopSide : null;
  const bearing = typeof api?.bearingDegrees === "number" ? api.bearingDegrees : null;
  const exit = leg.to.name.trim();
  return { side, direction: side && exit && exit !== "END" ? exit : direction(leg), bearing };
}

/**
 * Stops ridden on a leg: the API's `boarding.stopCount`, else its intermediate stops plus
 * the exit, else the trip detail's calls (stopsRidden). Null when none is known.
 */
export function stopCountOf(leg: Leg, trip: Trip["data"] | undefined): number | null {
  const count = apiBoarding(leg)?.stopCount;
  if (typeof count === "number" && count > 0) return count;
  const between = (leg as { intermediateStops?: unknown }).intermediateStops;
  if (Array.isArray(between)) return between.length + 1;
  return stopsRidden(leg, trip);
}

/** The boarding stop's map tag: "בצד הזה · לכיוון X", "לכיוון X", or null with nothing known. */
export function boardingTag(boarding: Boarding, t: T): string | null {
  const toward = boarding.direction ? t("route.toward", { headsign: boarding.direction }) : null;
  if (boarding.side && toward) return `${t("route.thisSide")} · ${toward}`;
  return toward ?? (boarding.side ? t("route.thisSide") : null);
}

/** One sentence for a ride (screen readers): "רכבת ישראל 156 מהשלום לחוף הכרמל". */
export function rideSpeech(leg: Leg, ends: EndLabels, t: T): string {
  const from = placeName(leg.from.name, ends);
  const to = placeName(leg.to.name, ends);
  if (isRail(leg)) {
    const number = trainNumber(leg);
    const name = leg.transit?.operatorName?.trim() || t("compare.train");
    return t("route.trainSpeech", { train: number ? `${name} ${number}` : name, from, to });
  }
  const line = lineLabel(leg);
  const name = line ? t("route.bus", { line }) : (leg.transit?.operatorName ?? leg.mode);
  const toward = direction(leg);
  return [name, toward ? t("route.toward", { headsign: toward }) : null, t("route.fromTo", { from, to })]
    .filter(Boolean)
    .join(" ");
}

/** Platform only when the API knows it (API-C2); never guessed. */
export function platformOf(leg: Leg): string | null {
  const code = (leg.from as { platformCode?: unknown }).platformCode;
  return typeof code === "string" && code.trim() !== "" ? code.trim() : null;
}

/**
 * Stops ridden on a leg, from the trip detail: the exit call's ordinal minus the boarding
 * call's. Null when either call cannot be matched (never estimated).
 */
export function stopsRidden(leg: Leg, trip: Trip["data"] | undefined): number | null {
  if (!trip || !leg.from.stopId || !leg.to.stopId) return null;
  const departure = Date.parse(leg.timing.scheduledDeparture);
  const arrival = Date.parse(leg.timing.scheduledArrival);
  const boardings = trip.calls.filter((call) => call.stopId === leg.from.stopId);
  const board =
    boardings.find((call) => call.scheduledDeparture !== null && Date.parse(call.scheduledDeparture) === departure) ??
    (boardings.length === 1 ? boardings[0] : undefined);
  if (!board) return null;
  const exits = trip.calls.filter((call) => call.stopId === leg.to.stopId && call.ordinal > board.ordinal);
  const exit =
    exits.find((call) => call.scheduledArrival !== null && Date.parse(call.scheduledArrival) === arrival) ?? exits[0];
  return exit ? exit.ordinal - board.ordinal : null;
}

export function minutesText(seconds: number, t: T): string {
  const minutes = Math.max(0, Math.ceil(seconds / 60));
  return minutes === 1 ? t("compare.minutes.one") : t("compare.minutes", { n: minutes });
}

export function transfersText(count: number, t: T): string {
  if (count === 0) return t("compare.transfers.0");
  if (count === 1) return t("compare.transfers.1");
  return t("compare.transfers.n", { n: count });
}

// --- days ---------------------------------------------------------------------------

/** The Israel calendar date of an instant, `YYYY-MM-DD`. */
export const israelDate = (instant: string | Date): string =>
  israelWallTime(typeof instant === "string" ? new Date(instant) : instant).slice(0, 10);

/** Whole days from one Israel date (`YYYY-MM-DD`) to another. */
export function daysBetween(from: string, to: string): number {
  return Math.round((Date.parse(`${to}T12:00:00Z`) - Date.parse(`${from}T12:00:00Z`)) / 86_400_000);
}

const shortDay: Record<Lang, Intl.DateTimeFormatOptions> = {
  he: { weekday: "short", day: "numeric", month: "numeric" },
  en: { weekday: "short", day: "numeric", month: "short" },
};

/** A short weekday and date in Israel: "יום ב׳, 2.11" / "Mon 2 Nov". */
export function formatShortDay(instant: string | Date, lang: Lang): string {
  return new Intl.DateTimeFormat(lang === "he" ? "he-IL" : "en-GB", { timeZone: ZONE, numberingSystem: "latn", ...shortDay[lang] }).format(
    typeof instant === "string" ? new Date(instant) : instant,
  );
}

/** "היום" / "מחר" / a short day, relative to the Israel date `today`. */
export function relativeDay(date: string, today: string, lang: Lang, t: T): string {
  const days = daysBetween(today, date);
  if (days === 0) return t("compare.when.today");
  if (days === 1) return t("compare.when.tomorrow");
  return formatShortDay(`${date}T12:00:00Z`, lang);
}

/**
 * One option row as one sentence (screen readers; board Choose): "אפשרות 1, 105 דקות,
 * יציאה 08:07, הגעה 09:52, 2 החלפות, קווים: 61, רכבת, בעוד 4 דק׳". Every fact the row and
 * the map show for it, in words.
 */
export function optionSpeech(
  journey: Journey,
  index: number,
  t: T,
  lang: Lang,
  {
    dayOf = () => null,
    until = null,
  }: { dayOf?: (instant: string) => string | null; until?: string | null } = {},
): string {
  const parts = [t("compare.option", { n: index + 1 })];
  const walkOnly = isWalkOnly(journey);
  if (walkOnly) parts.push(t("compare.walkOnly"));
  parts.push(minutesText(journey.durationSeconds, t));
  const at = (instant: string) => [dayOf(instant), formatClock(instant, lang)].filter(Boolean).join(" ");
  parts.push(t("compare.departs", { time: at(journey.timing.scheduledDeparture) }));
  parts.push(t("compare.arrives", { time: at(journey.timing.scheduledArrival) }));
  if (!walkOnly) {
    parts.push(transfersText(journey.transfers, t));
    const lines = journey.legs.filter((leg) => leg.kind === "transit").map((leg) => shortBadgeLabel(leg, t));
    if (lines.length > 0) parts.push(t("compare.lines", { lines: lines.join(", ") }));
  }
  if (until) parts.push(until);
  return parts.join(", ");
}

/** The walk before the first ride (board Choose: "הליכה 3 דק׳"), in seconds; 0 when none. */
export function firstWalkSeconds(journey: Journey): number {
  const first = journey.legs[0];
  return first?.kind === "walk" && journey.legs.some((leg) => leg.kind === "transit") ? first.durationSeconds : 0;
}

/**
 * How long until an option leaves (board Choose: "בעוד 4 דק׳"), from the scheduled
 * departure and the device clock: minutes under an hour, then h:mm; on another Israel
 * day, the day ("מחר", "יום ה׳, 1.10"); "עכשיו" in its last half minute; null once it has left.
 */
export function untilText(departure: string, now: Date, lang: Lang, t: T): string | null {
  const day = israelDate(departure);
  const today = israelDate(now);
  if (day !== today) return relativeDay(day, today, lang, t);
  const seconds = (Date.parse(departure) - now.getTime()) / 1000;
  if (seconds < 0) return null;
  const minutes = Math.round(seconds / 60);
  if (minutes < 1) return t("compare.in.now");
  if (minutes < 60) return t("compare.in.min", { n: minutes });
  return t("compare.in.h", { n: `${Math.floor(minutes / 60)}:${String(minutes % 60).padStart(2, "0")}` });
}

/**
 * The design's compact duration (LegBar): "1:45" with the unit שע׳ from an hour on, else
 * whole minutes with דק׳. Rounded up to whole minutes, like formatDuration.
 */
export function compactDuration(seconds: number): { value: string; unit: "h" | "min" } {
  const minutes = Math.max(0, Math.ceil(seconds / 60));
  if (minutes < 60) return { value: String(minutes), unit: "min" };
  return { value: `${Math.floor(minutes / 60)}:${String(minutes % 60).padStart(2, "0")}`, unit: "h" };
}

/** The first sentence of a message, for a banner's bold opening phrase, and the rest. */
export function splitFirstSentence(message: string): { first: string; rest: string } {
  const match = /^(.+?[.!?])\s+(\S[\s\S]*)$/.exec(message);
  return match ? { first: match[1]!, rest: match[2]! } : { first: message, rest: "" };
}
