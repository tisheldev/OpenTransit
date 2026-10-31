import { Fragment } from "react";
import type { Trip } from "../../api/schemas";
import type { Journey, Leg } from "../../api/types";
import { Bdi } from "../../components/states";
import { useI18n } from "../../i18n/I18nProvider";
import { formatDistance, formatDuration } from "../../lib/format";
import { formatClock } from "../../lib/time";
import { isRail, type TransitMode } from "../../plan/chartLayout";
import { buildItinerary, type ItineraryItem } from "./itinerary";
import { chipLabel, rideSpeech, rideTitle, stopsRidden, trainNumber, type EndLabels } from "./labels";

// Route details of the selected option as an itinerary timeline (design: Route details —
// C04; CU06, CU14): scheduled times on the inline start, a line coloured by mode (solid
// for rides, dotted for walks), each ride's line chip and direction, boarding and exit
// times, its stop count once the trip detail arrives (in the background, on the same
// line, so nothing moves), transfer waits, and platforms only when known (API-C2). A
// failed trip detail leaves the count out and never blocks Start. Stop and trip screens
// are not built yet (S7), so nothing here links to them.

export type TripState = { status: "pending" } | { status: "error" } | { status: "ok"; trip: Trip["data"] };

const modeIcon: Record<TransitMode, string> = { bus: "🚌", rail: "🚆", tram: "🚊" };

function LineChip({ leg, mode }: { leg: Leg; mode: TransitMode }) {
  const label = chipLabel(leg);
  return (
    <span className={`line-chip line-chip-${mode}`}>
      <span className="line-chip-icon" aria-hidden="true">
        {modeIcon[mode]}
      </span>
      {label && <Bdi>{label}</Bdi>}
    </span>
  );
}

function Ride({ leg, mode, trip, ends }: { leg: Leg; mode: TransitMode; trip: TripState | undefined; ends: EndLabels }) {
  const { t, lang } = useI18n();
  const stops = trip?.status === "ok" ? stopsRidden(leg, trip.trip) : null;
  const meta: string[] = [];
  if (!isRail(leg) && leg.transit?.operatorName) meta.push(leg.transit.operatorName);
  if (stops !== null) meta.push(stops === 1 ? t("route.stops.one") : t("route.stops", { n: stops }));
  meta.push(formatDuration(leg.durationSeconds, lang));
  const number = trainNumber(leg);
  return (
    <>
      <span className="visually-hidden">{rideSpeech(leg, ends, t)}. </span>
      <span className="it-ride-title" aria-hidden="true">
        <LineChip leg={leg} mode={mode} />
        <span className="it-ride-name">{rideTitle(leg, t)}</span>
      </span>
      <span className="it-meta">
        {number && <span className="visually-hidden">{t("route.trainNumber", { number })}. </span>}
        {meta.map((part, index) => (
          <span key={index}>
            {index > 0 && " · "}
            <Bdi>{part}</Bdi>
          </span>
        ))}
        {trip?.status === "error" && <span className="it-note"> · {t("route.stopsUnavailable")}</span>}
      </span>
    </>
  );
}

function walkText(item: Extract<ItineraryItem, { kind: "walk" }>, t: ReturnType<typeof useI18n>["t"], lang: "he" | "en"): string[] {
  if (item.sameStop) {
    const total = item.seconds + item.waitSeconds;
    return [t("route.sameStop"), ...(total >= 60 ? [t("route.wait", { duration: formatDuration(total, lang) })] : [])];
  }
  const duration = formatDuration(item.seconds, lang);
  const distance = formatDistance(item.distanceMeters, lang);
  const parts = [distance ? t("route.walk", { duration, distance }) : t("route.walkTimeOnly", { duration })];
  if (item.waitSeconds >= 60) parts.push(t("route.wait", { duration: formatDuration(item.waitSeconds, lang) }));
  return parts;
}

export function RouteDetails({
  journey,
  ends,
  trips,
  day = null,
}: {
  journey: Journey;
  ends: EndLabels;
  trips: Record<string, TripState>;
  /** The trip's day when it is not the day asked (e.g. "שבת, 7.11"). */
  day?: string | null;
}) {
  const { t, lang } = useI18n();
  const items = buildItinerary(journey, ends);
  return (
    <section className="route-details" aria-labelledby="route-details-title">
      <h2 id="route-details-title" className="route-title">
        {t("screen.route")}
        {day && <span className="route-day"> · {day}</span>}
      </h2>
      <ol className="itinerary" aria-label={t("route.steps")}>
        {items.map((item, index) => {
          if (item.kind === "place") {
            return (
              <li
                key={index}
                className={`it it-place it-${item.role}`}
                data-above={item.above ?? undefined}
                data-below={item.below ?? undefined}
              >
                <span className="it-time">
                  <Bdi>{formatClock(item.time, lang)}</Bdi>
                </span>
                <span className="it-rail" aria-hidden="true">
                  <span className="it-dot" />
                </span>
                <span className="it-body">
                  <span className="visually-hidden">{t(`route.role.${item.role}`)}: </span>
                  <span className="it-name">{item.name}</span>
                  {item.platform && <span className="it-platform"> · {t("route.platform", { platform: item.platform })}</span>}
                </span>
              </li>
            );
          }
          if (item.kind === "ride") {
            return (
              <li key={index} className={`it it-ride it-mode-${item.mode}`}>
                <span className="it-time" />
                <span className="it-rail" aria-hidden="true" />
                <span className="it-body">
                  <Ride leg={item.leg} mode={item.mode} trip={item.leg.transit ? trips[item.leg.transit.engineTripId] : undefined} ends={ends} />
                </span>
              </li>
            );
          }
          const parts =
            item.kind === "walk" ? walkText(item, t, lang) : [t("route.wait", { duration: formatDuration(item.seconds, lang) })];
          return (
            <li key={index} className={`it it-${item.kind === "walk" && !item.sameStop ? "walk" : "wait"}`}>
              <span className="it-time" />
              <span className="it-rail" aria-hidden="true" />
              <span className="it-body it-meta">
                <span className="it-icon" aria-hidden="true">
                  {item.kind === "walk" && !item.sameStop ? "🚶" : "⏱"}
                </span>
                {parts.map((part, i) => (
                  <Fragment key={i}>
                    {i > 0 && " · "}
                    <span>{part}</span>
                  </Fragment>
                ))}
              </span>
            </li>
          );
        })}
      </ol>
    </section>
  );
}
