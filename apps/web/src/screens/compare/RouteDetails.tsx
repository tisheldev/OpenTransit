import { Fragment, type CSSProperties, type ReactNode } from "react";
import type { Trip } from "../../api/schemas";
import type { Journey, Leg } from "../../api/types";
import { Icon, LineBadge } from "../../components/ds";
import { Bdi } from "../../components/states";
import { useI18n } from "../../i18n/I18nProvider";
import { formatDistance, formatDuration } from "../../lib/format";
import { operatorColour } from "../../lib/lines";
import { formatClock } from "../../lib/time";
import { isRail, type TransitMode } from "../../plan/chartLayout";
import { isWalkOnly, type RankLabel } from "../../plan/rank";
import { buildSteps, type Step } from "./itinerary";
import {
  chipLabel,
  daysBetween,
  israelDate,
  placeName,
  rankKey,
  rideSpeech,
  rideTitle,
  stopsRidden,
  trainNumber,
  transfersText,
  type EndLabels,
} from "./labels";
import { Duration, NextDay } from "./OptionsChart";

// Route details of the selected option (design: LegBar's route, `ot-route`, and StepList;
// C04; CU06, CU14): leave → arrive in a big figure with the rank, duration, transfers and
// walking, the first boarding, then the steps with their scheduled times: each ride with
// its line badge, direction, stop count (once the trip detail arrives, in the background,
// on the same line, so nothing moves) and its exit stop at its arrival time; each walk
// with its minutes and where it leads; waits; the arrival. Platforms are left out until
// the API provides them (API-C2). A failed trip detail leaves the count out and never
// blocks Start. Stop and trip screens are not built yet (S7), so nothing here links.

export type TripState = { status: "pending" } | { status: "error" } | { status: "ok"; trip: Trip["data"] };

/** A translated message with React nodes in its {placeholders} (times in <bdi>). */
function fill(template: string, nodes: Record<string, ReactNode>): ReactNode[] {
  return template.split(/(\{\w+\})/).map((part, index) => {
    const name = /^\{(\w+)\}$/.exec(part)?.[1];
    return <Fragment key={index}>{name !== undefined && name in nodes ? nodes[name] : part}</Fragment>;
  });
}

/** A step's scheduled time, with "+1" when it falls on a later day than the trip starts. */
function StepTime({ instant, startDate }: { instant: string | null; startDate: string }) {
  const { t, lang } = useI18n();
  if (instant === null) return <span className="compare-step-notime" />;
  const days = daysBetween(startDate, israelDate(instant));
  return (
    <time dateTime={instant}>
      <Bdi>{formatClock(instant, lang)}</Bdi>
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

/** The line as the design's badge: bus by number; train "רכבת 156"; light rail in rail colour. */
function badgeOf(leg: Leg, mode: TransitMode, train: string): { mode: "bus" | "rail"; label: string } {
  if (mode === "bus") return { mode: "bus", label: chipLabel(leg) ?? "" };
  if (isRail(leg)) return { mode: "rail", label: [train, trainNumber(leg)].filter(Boolean).join(" ") };
  return { mode: "rail", label: chipLabel(leg) ?? train };
}

/** The leg's mode and operator, for the badge's vehicle icon and colour. */
function rideLine(leg: Leg) {
  return { mode: leg.mode, operatorId: leg.transit?.operatorId, operatorName: leg.transit?.operatorName };
}

/** A boarding stop's ring in the line's operator colour (light map shade, readable in both themes). */
function stopDotStyle(leg: Leg): CSSProperties | undefined {
  const colour = operatorColour(rideLine(leg));
  return colour ? { borderColor: colour.badge.bg } : undefined;
}

function RideStep({
  step,
  trip,
  ends,
  startDate,
}: {
  step: Extract<Step, { kind: "ride" }>;
  trip: TripState | undefined;
  ends: EndLabels;
  startDate: string;
}) {
  const { t, lang } = useI18n();
  const { leg } = step;
  const stops = trip?.status === "ok" ? stopsRidden(leg, trip.trip) : null;
  const meta: string[] = [];
  if (!isRail(leg) && leg.transit?.operatorName) meta.push(leg.transit.operatorName);
  if (stops !== null) meta.push(stops === 1 ? t("route.stops.one") : t("route.stops", { n: stops }));
  meta.push(formatDuration(leg.durationSeconds, lang));
  const number = trainNumber(leg);
  const badge = badgeOf(leg, step.mode, t("compare.train"));
  return (
    <li className="ot-steps__item compare-step compare-step--ride">
      <div className="ot-steps__row">
        <StepTime instant={step.time} startDate={startDate} />
        <span className="ot-steps__icon" aria-hidden="true">
          <LineBadge mode={badge.mode} label={badge.label} line={rideLine(leg)} />
        </span>
        <span className="ot-steps__text">
          <span className="visually-hidden">{rideSpeech(leg, ends, t)}. </span>
          <span className="compare-ride-name" aria-hidden="true">
            {rideTitle(leg, t)}
          </span>
          <small>
            {number && <span className="visually-hidden">{t("route.trainNumber", { number })}. </span>}
            {meta.map((part, index) => (
              <Fragment key={index}>
                {index > 0 && " · "}
                <Bdi>{part}</Bdi>
              </Fragment>
            ))}
            {trip?.status === "error" && <span className="compare-step-note"> · {t("route.stopsUnavailable")}</span>}
          </small>
        </span>
      </div>
      {step.exit && (
        <div className="ot-steps__row compare-exit">
          <StepTime instant={step.exit.time} startDate={startDate} />
          <span className="ot-steps__icon" aria-hidden="true">
            <span className={`compare-stopdot compare-stopdot--${badge.mode}`} style={stopDotStyle(leg)} />
          </span>
          <span className="ot-steps__text compare-place">
            {t("route.role.exit")} · <bdi>{step.exit.name}</bdi>
          </span>
        </div>
      )}
    </li>
  );
}

function WalkStep({ step, startDate }: { step: Extract<Step, { kind: "walk" }>; startDate: string }) {
  const { t, lang } = useI18n();
  const duration = formatDuration(step.seconds, lang);
  const distance = formatDistance(step.distanceMeters, lang);
  const total = step.seconds + step.waitSeconds;
  const main = step.sameStop
    ? t("route.sameStop")
    : distance
      ? t("route.walk", { duration, distance })
      : t("route.walkTimeOnly", { duration });
  // A change at the same stop is all waiting; a walk keeps its own minutes.
  const wait = step.sameStop ? (total >= 60 ? total : 0) : step.waitSeconds >= 60 ? step.waitSeconds : 0;
  const sub = [
    !step.sameStop && step.to ? t("route.walkTo", { place: step.to }) : null,
    wait > 0 ? t("route.wait", { duration: formatDuration(wait, lang) }) : null,
  ].filter((part): part is string => part !== null);
  return (
    <li className="ot-steps__item compare-step compare-step--walk">
      <div className="ot-steps__row">
        <StepTime instant={step.time} startDate={startDate} />
        <span className="ot-steps__icon" aria-hidden="true">
          <Icon name={step.sameStop ? "clock" : "walk"} />
        </span>
        <span className="ot-steps__text">
          <span>{main}</span>
          {sub.length > 0 && (
            <small>
              {sub.map((part, index) => (
                <Fragment key={index}>
                  {index > 0 && " · "}
                  <span>{part}</span>
                </Fragment>
              ))}
            </small>
          )}
        </span>
      </div>
    </li>
  );
}

export function RouteDetails({
  journey,
  ends,
  trips,
  day = null,
  rank = null,
}: {
  journey: Journey;
  ends: EndLabels;
  trips: Record<string, TripState>;
  /** The trip's day when it is not the day asked (e.g. "שבת, 7.11"). */
  day?: string | null;
  rank?: RankLabel | null;
}) {
  const { t, lang } = useI18n();
  const steps = buildSteps(journey, ends);
  const { scheduledDeparture: leave, scheduledArrival: arrive } = journey.timing;
  const startDate = israelDate(leave);
  const overnight = daysBetween(startDate, israelDate(arrive));
  const walkOnly = isWalkOnly(journey);
  const firstRide = journey.legs.find((leg) => leg.kind === "transit");
  const distance = walkOnly ? formatDistance(journey.walkingDistanceMeters ?? null, lang) : null;
  return (
    <section className="ot-route route-details" aria-labelledby="route-details-title">
      <h2 id="route-details-title" className="visually-hidden">
        {t("screen.route")}
        {day && ` · ${day}`}
      </h2>
      <div className="ot-route__top">
        <p className="ot-route__big">
          <span className="visually-hidden">
            {t("compare.departs", { time: formatClock(leave, lang) })}, {t("compare.arrives", { time: formatClock(arrive, lang) })}
          </span>
          <span aria-hidden="true">
            <Bdi>{formatClock(leave, lang)}</Bdi> <span className="compare-flip">←</span> <Bdi>{formatClock(arrive, lang)}</Bdi>
            {overnight > 0 && <NextDay days={overnight} />}
          </span>
        </p>
        {rank && <span className="ot-kicker compare-kicker">{t(rankKey[rank])}</span>}
      </div>
      <p className="ot-route__meta">
        {day && (
          <span className="compare-day" aria-hidden="true">
            {day}
          </span>
        )}
        <span>
          <Duration seconds={journey.durationSeconds} />
        </span>
        {walkOnly ? (
          distance && (
            <>
              <span aria-hidden="true">·</span>
              <Bdi>{distance}</Bdi>
            </>
          )
        ) : (
          <>
            <span aria-hidden="true">·</span>
            <span>{transfersText(journey.transfers, t)}</span>
            {journey.walkingSeconds >= 60 && (
              <>
                <span aria-hidden="true">·</span>
                <span className="compare-meta-walk">
                  <Icon name="walk" size="sm" />
                  {t("compare.walking", { duration: formatDuration(journey.walkingSeconds, lang) })}
                </span>
              </>
            )}
          </>
        )}
      </p>
      {firstRide && (
        <p className="ot-route__board">
          {fill(t("route.boardAt"), {
            time: <Bdi>{formatClock(firstRide.timing.scheduledDeparture, lang)}</Bdi>,
            stop: <bdi>{placeName(firstRide.from.name, ends)}</bdi>,
          })}
        </p>
      )}
      <ol className="ot-steps" aria-label={t("route.steps")}>
        {steps.map((step, index) => {
          if (step.kind === "ride") {
            return (
              <RideStep
                key={index}
                step={step}
                trip={step.leg.transit ? trips[step.leg.transit.engineTripId] : undefined}
                ends={ends}
                startDate={startDate}
              />
            );
          }
          if (step.kind === "walk") return <WalkStep key={index} step={step} startDate={startDate} />;
          if (step.kind === "wait") {
            return (
              <li key={index} className="ot-steps__item compare-step compare-step--wait">
                <div className="ot-steps__row">
                  <StepTime instant={null} startDate={startDate} />
                  <span className="ot-steps__icon" aria-hidden="true">
                    <Icon name="clock" />
                  </span>
                  <span className="ot-steps__text">
                    <span>{t("route.wait", { duration: formatDuration(step.seconds, lang) })}</span>
                  </span>
                </div>
              </li>
            );
          }
          return (
            <li key={index} className={`ot-steps__item compare-step compare-step--${step.role}`}>
              <div className="ot-steps__row">
                <StepTime instant={step.time} startDate={startDate} />
                <span className="ot-steps__icon" aria-hidden="true">
                  {step.role === "destination" ? <Icon name="pin" /> : <span className="compare-stopdot" />}
                </span>
                <span className="ot-steps__text compare-place">
                  {t(`route.role.${step.role}`)} · <bdi>{step.name}</bdi>
                </span>
              </div>
            </li>
          );
        })}
      </ol>
    </section>
  );
}
