import { useDeparturesFrom } from "../../api/queries";
import type { DeparturesPage } from "../../api/schemas";
import type { Leg } from "../../api/types";
import { useI18n } from "../../i18n/I18nProvider";
import { formatClock } from "../../lib/time";
import { useLineKeyFor } from "../line/data";
import { StrokeIcon } from "../line/icons";
import { openLine } from "../line/intent";
import "../line/stopline.css";

// A journey's ride opened in place (canvas board Journey, 6), 14 November 2026: the next
// departures of that line from the boarding stop, the one in the journey chosen; choosing
// another re-plans with it (RouteScreen), and a link to the whole line.

export type Departure = DeparturesPage["data"][number];

/** Times shown (board 6: three, the journey's own first). */
const CHIPS = 3;

export function RideDepartures({ leg, onChoose }: { leg: Leg; onChoose: (departure: Departure) => void }) {
  const { t, lang } = useI18n();
  const transit = leg.transit!;
  const stopId = leg.from.stopId ?? null;
  const departures = useDeparturesFrom(stopId, leg.timing.scheduledDeparture, { routeId: transit.routeId, horizonMinutes: 120, limit: 6 });
  const lineKey = useLineKeyFor(transit.routeId, transit.routeShortName || null);
  const key = lineKey.data ?? null;
  const label = transit.routeShortName || t("stop.train");
  // An API without the route filter answers every route: keep this one's, later than the ride.
  const later = (departures.data?.data ?? [])
    .filter((item) => (item.routeId === transit.routeId || item.routeId === null) && item.tripRef !== transit.engineTripId)
    .filter((item) => Date.parse(item.scheduledDeparture) > Date.parse(leg.timing.scheduledDeparture))
    .sort((a, b) => Date.parse(a.scheduledDeparture) - Date.parse(b.scheduledDeparture))
    .slice(0, CHIPS - 1);
  return (
    <div className="compare-ride-open">
      <div className="b-mu">{t("route.lineHere", { line: label })}</div>
      <div className="compare-ride-open__times" role="group" aria-label={t("stop.nextTimes", { line: label })}>
        <button type="button" className="sl-chip" aria-pressed={true}>
          {formatClock(leg.timing.scheduledDeparture, lang)}
        </button>
        {later.map((item) => (
          <button key={`${item.tripRef}|${item.scheduledDeparture}`} type="button" className="sl-chip" aria-pressed={false} onClick={() => onChoose(item)}>
            {formatClock(item.scheduledDeparture, lang)}
          </button>
        ))}
      </div>
      {key && (
        <button
          type="button"
          className="sl-link"
          onClick={() => openLine({ lineKey: key, stopId, routeId: transit.routeId, tripRef: transit.engineTripId })}
        >
          {t("route.allStopsOf", { line: label })}
          <StrokeIcon name="forward" />
        </button>
      )}
    </div>
  );
}
