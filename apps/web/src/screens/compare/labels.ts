import type { Trip } from "../../api/schemas";
import type { Journey, Leg } from "../../api/types";
import type { MessageKey } from "../../i18n/messages";
import { formatDuration } from "../../lib/format";
import { formatClock, type Lang } from "../../lib/time";
import { isRail, lineLabel } from "../../plan/chartLayout";
import type { Endpoint } from "../../plan/draft";
import { isWalkOnly, type RankLabel } from "../../plan/rank";

// Text for the chart and the route details (design: Compare and Route details; Language
// and layout rules: trains by destination, buses by number and headsign).

type T = (key: MessageKey, values?: Record<string, string | number>) => string;

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

/** A train's destination: a text headsign, otherwise where the leg ends (rail headsigns are train numbers). */
export function trainDestination(leg: Leg, ends: EndLabels): string {
  const headsign = leg.transit?.headsign?.trim() ?? "";
  if (headsign !== "" && !isNumeric(headsign)) return readableHeadsign(headsign);
  return placeName(leg.to.name, ends);
}

export function transitTitle(leg: Leg, ends: EndLabels, t: T): string {
  if (isRail(leg)) return t("route.trainTo", { destination: trainDestination(leg, ends) });
  const line = lineLabel(leg);
  const headsign = leg.transit?.headsign?.trim();
  const name = line ? t("route.bus", { line }) : (leg.transit?.operatorName ?? leg.mode);
  return headsign ? `${name} ${t("route.toward", { headsign: readableHeadsign(headsign) })}` : name;
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

/** Screen-reader text for one option, e.g. "אפשרות 1, מומלץ, 47 דקות, יציאה 08:41, החלפה אחת". */
export function optionSpeech(journey: Journey, index: number, rank: RankLabel | null, t: T, lang: Lang): string {
  const parts = [t("compare.option", { n: index + 1 })];
  if (rank) parts.push(t(rankKey[rank]));
  if (isWalkOnly(journey)) parts.push(t("compare.walkOnly"));
  parts.push(minutesText(journey.durationSeconds, t));
  parts.push(t("compare.departs", { time: formatClock(journey.timing.scheduledDeparture, lang) }));
  if (!isWalkOnly(journey)) parts.push(transfersText(journey.transfers, t));
  return parts.join(", ");
}

export function durationText(seconds: number, lang: Lang): string {
  return formatDuration(seconds, lang);
}
