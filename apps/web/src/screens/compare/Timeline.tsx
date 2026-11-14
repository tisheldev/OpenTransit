import { Fragment, useState, type CSSProperties, type ReactNode } from "react";
import { StrokeIcon } from "../line/icons";
import { openStop } from "../stop/intent";
import { RideDepartures, type Departure } from "./RideDepartures";
import type { Journey, Leg } from "../../api/types";
import { LineBadge } from "../../components/ds";
import { useI18n } from "../../i18n/I18nProvider";
import { formatDistance, formatDuration } from "../../lib/format";
import { operatorColour } from "../../lib/lines";
import { useTheme } from "../../lib/theme";
import { formatClock } from "../../lib/time";
import type { ThemeName } from "../../styles/tokens";
import { isRail } from "../../plan/chartLayout";
import { buildItinerary, type ItineraryItem } from "./itinerary";
import { badgeLabel, boardingOf, daysBetween, israelDate, rideName, rideSpeech, stopCountOf, type EndLabels } from "./labels";
import { NextDay, Nums } from "./text";
import type { TripState } from "./useCompare";

// The chosen option's timeline (board Step, `b-tl`; also the wide panel, opened in place).
// Stop rows: the scheduled time, a dot (filled at the start, a square at the arrival) and
// the stop, with its platform when the API gives one. Between them, one row per leg: a
// walk as ink dots with its minutes and metres, a ride as a bar in its line's colour with
// the badge, the headsign and the stops ridden (once the trip detail arrives). With
// `onFocus` each leg row is a button that shows that leg on the map; the leg on the map
// is marked "מוצג במפה".

type Place = Extract<ItineraryItem, { kind: "place" }>;

function StopTime({ instant, startDate }: { instant: string; startDate: string }) {
  const { t, lang } = useI18n();
  const days = daysBetween(startDate, israelDate(instant));
  return (
    <time className="b-tl__time" dateTime={instant}>
      <bdi className="num">{formatClock(instant, lang)}</bdi>
      {days > 0 && (
        <>
          <span className="visually-hidden"> ({t("compare.nextDay")})</span>
          <span aria-hidden="true">
            <NextDay days={days} />
          </span>
        </>
      )}
    </time>
  );
}

function StopRow({ place, startDate }: { place: Place; startDate: string }) {
  const { t } = useI18n();
  const dot = place.role === "origin" ? "b-dot b-dot--filled" : place.role === "destination" ? "b-dot b-dot--end" : "b-dot";
  return (
    <div className={`b-tl compare-tl-stop compare-tl-stop--${place.role}`}>
      <StopTime instant={place.time} startDate={startDate} />
      <span className={dot} aria-hidden="true" />
      <span className="b-tl__stop compare-place">
        {/* Board 6: a stop's name opens the stop. */}
        {place.stopId ? (
          <button type="button" className="compare-stop-link" onClick={() => openStop(place.stopId!)}>
            <bdi>{place.name}</bdi>
          </button>
        ) : (
          <bdi>{place.name}</bdi>
        )}
        {place.platform && (
          <span className="b-mu compare-platform">
            {" · "}
            <Nums text={t("route.platform", { platform: place.platform })} />
          </span>
        )}
      </span>
    </div>
  );
}

/** The line's colour on the map for the current theme, else the mode token. */
function barColour(leg: Leg, theme: ThemeName): string {
  const colour = operatorColour({ mode: leg.mode, operatorId: leg.transit?.operatorId, operatorName: leg.transit?.operatorName });
  return colour?.line[theme] ?? (isRail(leg) ? "var(--mode-rail)" : "var(--mode-bus)");
}

function LegRow({
  legIndex,
  marker,
  focused,
  onFocus,
  expanded,
  style,
  children,
}: {
  legIndex: number;
  marker: ReactNode;
  focused: boolean;
  onFocus?: (legIndex: number) => void;
  /** A ride that opens in place (board 6): whether it is open. */
  expanded?: boolean;
  style?: CSSProperties;
  children: ReactNode;
}) {
  const { t } = useI18n();
  const body = (
    <>
      <span />
      {marker}
      <span className="b-tl__leg">
        {children}
        {focused && <span className="b-mu">{t("route.shown")}</span>}
        {expanded !== undefined && <StrokeIcon name={expanded ? "up" : "down"} className="compare-ride-chevron" />}
      </span>
    </>
  );
  if (!onFocus) {
    return (
      <div className="b-tl compare-tl-leg" style={style}>
        {body}
      </div>
    );
  }
  return (
    <button
      type="button"
      className={`b-tl compare-tl-leg${focused ? " b-tl--on" : ""}`}
      style={style}
      aria-pressed={focused}
      aria-expanded={expanded}
      onClick={() => onFocus(legIndex)}
    >
      {body}
    </button>
  );
}

export function Timeline({
  journey,
  ends,
  trips,
  focused = null,
  onFocus,
  onReplan,
}: {
  journey: Journey;
  ends: EndLabels;
  trips: Record<string, TripState>;
  /** The leg shown on the map (index into journey.legs), or null for the whole route. */
  focused?: number | null;
  onFocus?: (legIndex: number) => void;
  /**
   * Board 6: with it, a ride's row opens in place to that line's next departures from its
   * boarding stop; choosing one calls this to re-plan with it.
   */
  onReplan?: (legIndex: number, departure: Departure) => void;
}) {
  const { t, lang } = useI18n();
  const theme = useTheme();
  const [openLeg, setOpenLeg] = useState<number | null>(null);
  const items = buildItinerary(journey, ends);
  const startDate = israelDate(journey.timing.scheduledDeparture);
  return (
    <div className="compare-timeline" role="group" aria-label={t("route.steps")}>
      {items.map((item, index) => {
        if (item.kind === "place") return <StopRow key={index} place={item} startDate={startDate} />;
        if (item.kind === "wait") {
          return (
            <div key={index} className="b-tl compare-tl-wait">
              <span />
              <span />
              <span className="b-mu">
                <Nums text={t("route.wait", { duration: formatDuration(item.seconds, lang) })} />
              </span>
            </div>
          );
        }
        if (item.kind === "walk") {
          const duration = formatDuration(item.seconds, lang);
          const distance = formatDistance(item.distanceMeters, lang);
          const main = item.sameStop
            ? t("route.sameStop")
            : distance
              ? t("route.walk", { duration, distance })
              : t("route.walkTimeOnly", { duration });
          const wait = item.waitSeconds >= 60 ? t("route.wait", { duration: formatDuration(item.waitSeconds, lang) }) : null;
          return (
            <LegRow
              key={index}
              legIndex={item.legIndex}
              marker={<span className="b-dots" aria-hidden="true" />}
              focused={focused === item.legIndex}
              onFocus={onFocus}
            >
              <span className="compare-walk">
                <Nums text={main} />
              </span>
              {wait && (
                <span className="b-mu compare-wait">
                  <Nums text={wait} />
                </span>
              )}
            </LegRow>
          );
        }
        const leg = item.leg;
        const trip = leg.transit ? trips[leg.transit.engineTripId] : undefined;
        // The API counts them on the leg; older answers fall back to the trip detail.
        const stops = stopCountOf(leg, trip?.status === "ok" ? trip.trip : undefined);
        const boarding = boardingOf(leg);
        // The side of the road is drawn by the map's stop pin; here it is said in words.
        const side = boarding.side ? t(boarding.side === "right" ? "route.side.right" : "route.side.left") : null;
        const opens = onReplan !== undefined && onFocus !== undefined && leg.transit != null && leg.from.stopId != null;
        const open = opens && openLeg === item.legIndex;
        const row = (
          <LegRow
            key={index}
            legIndex={item.legIndex}
            marker={<span className="b-bar" aria-hidden="true" />}
            focused={focused === item.legIndex}
            onFocus={
              opens
                ? (legIndex) => {
                    setOpenLeg(open ? null : legIndex);
                    onFocus(legIndex);
                  }
                : onFocus
            }
            expanded={opens ? open : undefined}
            style={{ "--bar": barColour(leg, theme) } as CSSProperties}
          >
            <span className="visually-hidden">
              {rideSpeech(leg, ends, t)}
              {side && `, ${side}`}.{" "}
            </span>
            <LineBadge
              mode={isRail(leg) ? "rail" : "bus"}
              label={badgeLabel(leg, t)}
              line={{ mode: leg.mode, operatorId: leg.transit?.operatorId, operatorName: leg.transit?.operatorName }}
            />
            <span className="compare-ride-name" aria-hidden="true">
              {rideName(leg, t)}
            </span>
            {stops !== null && (
              <span className="b-mu compare-stops">
                <Nums text={stops === 1 ? t("route.stops.one") : t("route.stops", { n: stops })} />
              </span>
            )}
            {stops === null && trip?.status === "error" && <span className="b-mu compare-stops">{t("route.stopsUnavailable")}</span>}
          </LegRow>
        );
        // Always in a fragment, so opening the row does not remount it (focus stays on it).
        return (
          <Fragment key={index}>
            {row}
            {open && (
              <div className="b-tl compare-tl-open" style={{ "--bar": barColour(leg, theme) } as CSSProperties}>
                <span />
                <span className="b-bar" aria-hidden="true" />
                <RideDepartures leg={leg} onChoose={(departure) => onReplan!(item.legIndex, departure)} />
              </div>
            )}
          </Fragment>
        );
      })}
    </div>
  );
}
