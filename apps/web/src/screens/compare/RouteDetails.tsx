import type { ReactNode } from "react";
import type { Trip } from "../../api/schemas";
import type { Journey, Leg } from "../../api/types";
import { useI18n } from "../../i18n/I18nProvider";
import { formatDistance, formatDuration } from "../../lib/format";
import { formatClock } from "../../lib/time";
import { isRail } from "../../plan/chartLayout";
import { hrefFor } from "../../router";
import { placeName, platformOf, stopsRidden, transfersText, transitTitle, type EndLabels } from "./labels";

// Route details of the selected option (design: Route details — C04; CU06, CU14). Walks
// show minutes and metres, or minutes only when the distance is unknown. Rides show the
// line or train, operator, departure, platform only when known (API-C2), and the stop
// count and exit from the trip detail when it has arrived; a failed trip detail leaves the
// count out and never blocks Start. Waits between legs are shown.

/** First-strong isolate: keeps a time or number whole inside right-to-left text. */
const isolate = (text: string) => `⁨${text}⁩`;

export type TripState = { status: "pending" } | { status: "error" } | { status: "ok"; trip: Trip["data"] };

function modeIcon(leg: Leg): string {
  if (leg.kind === "walk") return "🚶";
  if (isRail(leg)) return "🚆";
  if (/tram|light/i.test(leg.mode)) return "🚊";
  return "🚌";
}

function WalkRow({ leg, ends }: { leg: Leg; ends: EndLabels }) {
  const { t, lang } = useI18n();
  const duration = formatDuration(leg.durationSeconds, lang);
  const distance = formatDistance(leg.distanceMeters, lang);
  return (
    <li className="leg leg-walk">
      <span className="leg-icon" aria-hidden="true">
        {modeIcon(leg)}
      </span>
      <span className="leg-body">
        <span className="leg-title">
          {distance ? t("route.walk", { duration, distance }) : t("route.walkTimeOnly", { duration })}{" "}
          {t("route.walkTo", { place: placeName(leg.to.name, ends) })}
        </span>
      </span>
    </li>
  );
}

function TransitRow({ leg, ends, trip }: { leg: Leg; ends: EndLabels; trip: TripState | undefined }) {
  const { t, lang } = useI18n();
  const transit = leg.transit!;
  const platform = platformOf(leg);
  const stops = trip?.status === "ok" ? stopsRidden(leg, trip.trip) : null;
  const from = placeName(leg.from.name, ends);
  const to = placeName(leg.to.name, ends);
  const time = formatClock(leg.timing.scheduledDeparture, lang);
  return (
    <li className="leg leg-transit">
      <span className="leg-icon" aria-hidden="true">
        {modeIcon(leg)}
      </span>
      <span className="leg-body">
        <a className="leg-title" href={hrefFor({ name: "trip", tripRef: transit.engineTripId })}>
          {transitTitle(leg, ends, t)}
        </a>
        <span className="leg-meta">
          {transit.operatorName} · {t("route.departs", { time: isolate(time), stop: "" })}
          {leg.from.stopId ? (
            <a href={hrefFor({ name: "stop", stopId: leg.from.stopId })}>{from}</a>
          ) : (
            from
          )}
          {platform && <> · {t("route.platform", { platform })}</>}
        </span>
        <span className="leg-meta">
          {stops !== null && <>{stops === 1 ? t("route.stops.one") : t("route.stops", { n: stops })} · </>}
          {t("route.exit", { stop: to })}
          {trip?.status === "error" && <span className="leg-note"> · {t("route.stopsUnavailable")}</span>}
        </span>
      </span>
    </li>
  );
}

function WaitRow({ seconds }: { seconds: number }) {
  const { t, lang } = useI18n();
  return (
    <li className="leg leg-wait">
      <span className="leg-icon" aria-hidden="true">
        ⏱
      </span>
      <span className="leg-body leg-meta">{t("route.wait", { duration: formatDuration(seconds, lang) })}</span>
    </li>
  );
}

export function RouteDetails({
  journey,
  ends,
  trips,
}: {
  journey: Journey;
  ends: EndLabels;
  trips: Record<string, TripState>;
}) {
  const { t, lang } = useI18n();
  const rows: ReactNode[] = [];
  journey.legs.forEach((leg, index) => {
    const previous = journey.legs[index - 1];
    if (previous && leg.kind === "transit") {
      const wait = (Date.parse(leg.timing.scheduledDeparture) - Date.parse(previous.timing.scheduledArrival)) / 1000;
      if (wait >= 60) rows.push(<WaitRow key={`wait-${index}`} seconds={wait} />);
    }
    rows.push(
      leg.kind === "walk" ? (
        <WalkRow key={index} leg={leg} ends={ends} />
      ) : (
        <TransitRow key={index} leg={leg} ends={ends} trip={leg.transit ? trips[leg.transit.engineTripId] : undefined} />
      ),
    );
  });
  const summary = t("route.summary", {
    departure: isolate(formatClock(journey.timing.scheduledDeparture, lang)),
    arrival: isolate(formatClock(journey.timing.scheduledArrival, lang)),
    duration: isolate(formatDuration(journey.durationSeconds, lang)),
  });
  return (
    <section className="route-details" aria-labelledby="route-details-title">
      <h2 id="route-details-title" className="route-summary">
        <span className="visually-hidden">{t("screen.route")}: </span>
        {summary}
      </h2>
      <p className="route-facts">
        {journey.legs.some((leg) => leg.kind === "transit") && <>{transfersText(journey.transfers, t)} · </>}
        {t("route.walking", { duration: formatDuration(journey.walkingSeconds, lang) })}
      </p>
      <ol className="legs">{rows}</ol>
    </section>
  );
}
