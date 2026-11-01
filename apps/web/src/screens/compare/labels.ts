import type { Trip } from "../../api/schemas";
import type { Journey, Leg } from "../../api/types";
import type { MessageKey } from "../../i18n/messages";
import { formatDuration } from "../../lib/format";
import { formatClock, israelWallTime, ZONE, type Lang } from "../../lib/time";
import { isRail, lineLabel } from "../../plan/chartLayout";
import type { Endpoint } from "../../plan/draft";
import { isWalkOnly, type RankLabel } from "../../plan/rank";

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

/** What the line chip says: the line number, or for a train its number (or nothing). */
export function chipLabel(leg: Leg): string | null {
  return isRail(leg) ? trainNumber(leg) : lineLabel(leg);
}

/**
 * The ride's title beside its chip: a bus by its headsign ("לכיוון מסוף הטייסים"), a
 * train by its operator ("רכבת ישראל"), anything else by its operator or mode.
 */
export function rideTitle(leg: Leg, t: T): string {
  const toward = direction(leg);
  if (!isRail(leg) && toward) return t("route.toward", { headsign: toward });
  return leg.transit?.operatorName?.trim() || (isRail(leg) ? t("compare.train") : leg.mode);
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

export const rankKey: Record<RankLabel, MessageKey> = {
  recommended: "rank.recommended",
  fastest: "rank.fastest",
  noTransfers: "rank.noTransfers",
  fewerTransfers: "rank.fewerTransfers",
  lessWalking: "rank.lessWalking",
};

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

/** Screen-reader text for one option, e.g. "אפשרות 1, מומלץ, 47 דקות, יציאה 08:41, הגעה 09:28, החלפה אחת". */
export function optionSpeech(
  journey: Journey,
  index: number,
  rank: RankLabel | null,
  t: T,
  lang: Lang,
  dayOf: (instant: string) => string | null = () => null,
): string {
  const parts = [t("compare.option", { n: index + 1 })];
  if (rank) parts.push(t(rankKey[rank]));
  if (isWalkOnly(journey)) parts.push(t("compare.walkOnly"));
  parts.push(minutesText(journey.durationSeconds, t));
  const at = (instant: string) => [dayOf(instant), formatClock(instant, lang)].filter(Boolean).join(" ");
  parts.push(t("compare.departs", { time: at(journey.timing.scheduledDeparture) }));
  parts.push(t("compare.arrives", { time: at(journey.timing.scheduledArrival) }));
  if (!isWalkOnly(journey)) parts.push(transfersText(journey.transfers, t));
  return parts.join(", ");
}

export function durationText(seconds: number, lang: Lang): string {
  return formatDuration(seconds, lang);
}
