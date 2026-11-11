import { useMemo, useState } from "react";
import { useDeparturesFrom, usePlanExcluding } from "../../api/queries";
import type { Journey, Metadata } from "../../api/types";
import { Bdi } from "../../components/states";
import { useI18n } from "../../i18n/I18nProvider";
import { formatDuration } from "../../lib/format";
import type { Fix } from "../../lib/geolocation";
import { formatClock, toIsraelIso } from "../../lib/time";
import { usePublishScene } from "../../map/scene";
import { startActiveTrip, updateActiveTrip, type ActiveTrip } from "../../nav/activeTrip";
import type { NavStep } from "../../nav/steps";
import { useJourneys, useTrip } from "../../plan/queries";
import { badgeLabel, isRail, type EndLabels } from "./describe";
import { afterExitRequest, exitArrival, firstRide, swapRide, nextSameRoute, waitJourney, type Departure, waitRequest, walkBeforeRide, walkJourney, walkRequest } from "./missed";
import { missedScene } from "./navScene";

// Bus didn't come (board 6, 11 November 2026), opened from "לא הגיע?". The choices are
// drawn from where the passenger stands: wait here for the same line's next departure, or
// walk to another stop for a fresh plan's best option. Each card says when it leaves and
// when the passenger would arrive; choosing one switches the trip to it (a new active trip
// from that answer, as Start does). "הגיע, עליתי": the bus came after all.

interface Option {
  key: "walk" | "wait";
  journey: Journey | null;
  meta: Metadata | null;
  title: string;
  sub: string;
  departs: string;
  arrives: string | null;
  /** The time is the arrival at the exit stop (from the trip), not at the destination. */
  atExit?: boolean;
}

interface Props {
  trip: ActiveTrip;
  ride: NavStep;
  fix: Fix | null;
  clock: number;
  labels: EndLabels;
  onBoarded: () => void;
  onCancel: () => void;
}

/**
 * Switch the trip to a chosen answer: a new active trip from it, as Compare's Start does
 * (its trips are fetched at mount), keeping the destination's label. A new start time, so
 * Navigate starts over on the new plan.
 */
function switchTrip(trip: ActiveTrip, journey: Journey, meta: Metadata, labels: EndLabels): void {
  const started = Date.parse(trip.startedAt);
  startActiveTrip({ journey, meta, trips: {} }, new Date(Math.max(Date.now(), started + 1)));
  updateActiveTrip((current) => ({ ...current, labels: { origin: null, destination: labels.destination } }));
}

/** Board 6's map while the panel is open: the missed line, its next departure, the other stop. */
function MissedMap({ journey, ride, fix, next, other }: { journey: Journey; ride: NavStep; fix: Fix | null; next: Departure | null; other: Journey | null }) {
  const { t, lang } = useI18n();
  const scene = useMemo(() => {
    const leg = other ? firstRide(other) : null;
    return missedScene({
      journey,
      ride,
      fix,
      badge: badgeLabel(ride, t),
      waitText: next ? t("nav.missed.next", { time: formatClock(next.scheduledDeparture, lang) }) : null,
      walk:
        other && leg?.transit
          ? {
              journey: other,
              badge: leg.transit.routeShortName.trim() || t("nav.mode.rail"),
              departs: formatClock(leg.timing.scheduledDeparture, lang),
              walkText: t("nav.answer.walkFor", { duration: formatDuration(walkBeforeRide(other), lang) }),
            }
          : null,
    });
  }, [journey, ride, fix, next, other, t, lang]);
  usePublishScene(scene);
  return null;
}

export function MissedPanel({ trip, ride, fix, clock, labels, onBoarded, onCancel }: Props) {
  const { t, lang } = useI18n();
  // The question is asked once, when the panel opens: the requests do not move with the clock.
  const [askedAt] = useState(() => clock);
  const [askedFix] = useState(() => fix);
  const stopId = ride.from?.stopId ?? null;
  const from = useMemo(() => toIsraelIso(new Date(Math.max(askedAt, Date.parse(ride.scheduledDeparture)))), [askedAt, ride.scheduledDeparture]);

  // Wait here: the API filters by route when it can (PR #35); nextSameRoute filters anyway.
  const departures = useDeparturesFrom(stopId, from, { routeId: ride.ride?.routeId ?? null });
  const next = useMemo(() => (departures.data ? nextSameRoute(departures.data.data, ride) : null), [departures.data, ride]);
  const waitPlan = useMemo(() => (next ? waitRequest(trip.journey, next, lang) : null), [next, trip.journey, lang]);
  const waitAnswer = useJourneys(waitPlan ? { request: waitPlan } : null);
  // Without a plan that boards it: its arrival at the exit stop from the trip itself, then
  // a plan from the exit at that time; the ride swapped to it, followed by that plan.
  const waitFound = useMemo(
    () => (next && waitAnswer.data ? waitJourney(waitAnswer.data.response.data.journeys, ride, next) : null),
    [next, waitAnswer.data, ride],
  );
  const nextTrip = useTrip(next && waitAnswer.isSuccess && !waitFound ? next.tripRef : null);
  const exitAt = useMemo(() => (next && nextTrip.data ? exitArrival(nextTrip.data.data, next, ride) : null), [next, nextTrip.data, ride]);
  const restPlan = useMemo(() => (exitAt ? afterExitRequest(trip.journey, ride, exitAt, lang) : null), [exitAt, trip.journey, ride, lang]);
  const restAnswer = useJourneys(restPlan ? { request: restPlan } : null);
  const swapped = useMemo(() => {
    if (!next || !nextTrip.data || !exitAt) return null;
    const rest = restAnswer.data ? ([...restAnswer.data.response.data.journeys].sort((a, b) => Date.parse(a.timing.scheduledArrival) - Date.parse(b.timing.scheduledArrival))[0] ?? null) : null;
    return swapRide(trip.journey, ride, next, nextTrip.data.data, exitAt, rest);
  }, [next, nextTrip.data, exitAt, restAnswer.data, trip.journey, ride]);
  // Walk elsewhere: a fresh plan without the bus that did not come (excludeTripRefs, PR #35).
  const walkPlan = useMemo(() => walkRequest(trip.journey, ride, askedFix, askedAt, lang), [trip.journey, ride, askedFix, askedAt, lang]);
  const excluded = useMemo(() => (ride.ride ? [ride.ride.tripRef] : []), [ride.ride]);
  const walkAnswer = usePlanExcluding(walkPlan, excluded);

  // The line in a sentence: "61"; a train without a number is said by its mode.
  const line = badgeLabel(ride, t);
  const options: Option[] = [];
  const walkFound = useMemo(() => (walkAnswer.data ? walkJourney(walkAnswer.data.data.journeys, ride) : null), [walkAnswer.data, ride]);
  const walkLeg = walkFound ? firstRide(walkFound) : null;
  if (walkFound && walkLeg?.transit) {
    const other = walkLeg.transit.routeShortName.trim() || t(walkLeg.mode.toLowerCase() === "rail" ? "nav.mode.rail" : "nav.mode.other");
    options.push({
      key: "walk",
      journey: walkFound,
      meta: walkAnswer.data!.meta,
      title: t("nav.missed.walk", { line: other }),
      sub: t("nav.missed.walkSub", { duration: formatDuration(walkBeforeRide(walkFound), lang), time: formatClock(walkLeg.timing.scheduledDeparture, lang) }),
      departs: formatClock(walkLeg.timing.scheduledDeparture, lang),
      arrives: formatClock(walkFound.timing.scheduledArrival, lang),
    });
  }
  if (next) {
    const found = waitFound ?? swapped;
    const meta = waitFound ? waitAnswer.data!.response.meta : swapped ? (restAnswer.data?.response.meta ?? waitAnswer.data?.response.meta ?? null) : null;
    options.push({
      key: "wait",
      journey: found,
      meta,
      title: t("nav.missed.wait", { line }),
      sub: t("nav.missed.next", { time: formatClock(next.scheduledDeparture, lang) }),
      departs: formatClock(next.scheduledDeparture, lang),
      arrives: found ? formatClock(found.timing.scheduledArrival, lang) : exitAt ? formatClock(exitAt, lang) : null,
      atExit: !found && exitAt !== null,
    });
  }
  const arrivals = options.flatMap((option) => (option.journey ? [Date.parse(option.journey.timing.scheduledArrival)] : []));
  const earliest = arrivals.length > 0 ? Math.min(...arrivals) : null;

  const pending = departures.isPending || walkAnswer.isPending || (waitPlan !== null && waitAnswer.isPending);
  const failed = departures.isError && walkAnswer.isError;

  const choose = (option: Option) => {
    if (option.journey && option.meta) switchTrip(trip, option.journey, option.meta, labels);
  };

  const titleText = isRail(ride) && !ride.ride?.lineLabel ? t("nav.missed.titleTrain") : t("nav.missed.title", { line });
  return (
    <>
      <MissedMap journey={trip.journey} ride={ride} fix={fix} next={next} other={walkFound} />
      <section className="nav-missed" aria-labelledby="nav-answer-title" data-answer="missed">
        <h1 id="nav-answer-title" className="b-answer__title">
          <Bdi>{titleText}</Bdi>
        </h1>
        <span className="b-mu">
          <Bdi>{t("nav.answer.bySchedule", { time: formatClock(ride.scheduledDeparture, lang) })}</Bdi>
        </span>
        <div className="nav-choices">
          {options.map((option) => {
            const on = option.journey !== null && earliest !== null && Date.parse(option.journey.timing.scheduledArrival) === earliest;
            return (
              <button
                key={option.key}
                type="button"
                className={`b-choice nav-choice nav-choice--${option.key}${on ? " b-choice--on" : ""}`}
                disabled={!option.journey}
                onClick={() => choose(option)}
              >
                <span className="b-choice__title nav-choice-title">
                  <Bdi>{option.title}</Bdi>
                </span>
                <span className="b-mu">
                  <Bdi>{option.sub}</Bdi>
                </span>
                <span className="b-choice__arrive">
                  {t(option.atExit ? "nav.missed.exitArrive" : "nav.missed.arrive")}
                  {option.arrives ? (
                    <b>
                      <bdi className="num">{option.arrives}</bdi>
                    </b>
                  ) : (
                    <b>
                      <span aria-hidden="true">—</span>
                      <span className="visually-hidden">{t("nav.unknown")}</span>
                    </b>
                  )}
                </span>
                {on && options.length > 1 && <span className="visually-hidden">{`, ${t("nav.missed.earliest")}`}</span>}
              </button>
            );
          })}
          {pending && options.length === 0 && (
            <p className="b-mu nav-missed-note" role="status">
              {t("nav.missed.loading")}
            </p>
          )}
          {/* Nothing to offer: "none" only when both questions were answered; otherwise say what could not be checked. */}
          {!pending && options.length === 0 && (failed || !(departures.isError || walkAnswer.isError)) && (
            <p className="nav-missed-note" role="status">
              {t(failed ? "nav.missed.failed" : "nav.missed.none")}
            </p>
          )}
          {/* One question failed: say which is missing, never imply there is none. */}
          {!pending && !failed && departures.isError && (
            <p className="b-mu nav-missed-note" role="status">
              <Bdi>{t("nav.missed.waitFailed", { line })}</Bdi>
            </p>
          )}
          {!pending && !failed && walkAnswer.isError && (
            <p className="b-mu nav-missed-note" role="status">
              {t("nav.missed.walkFailed")}
            </p>
          )}
          {!pending && (departures.isError || walkAnswer.isError) && (
            <button
              type="button"
              className="b-link nav-missed-retry"
              onClick={() => {
                if (departures.isError) void departures.refetch();
                if (walkAnswer.isError) void walkAnswer.refetch();
              }}
            >
              {t("state.retry")}
            </button>
          )}
        </div>
      </section>
      <div className="b-actions nav-actions nav-actions--missed">
        <button type="button" className="b-link" onClick={onCancel}>
          {t("nav.missed.cancel")}
        </button>
        <button type="button" className="b-btn nav-primary nav-primary--came" onClick={onBoarded}>
          {t("nav.missed.came")}
        </button>
      </div>
    </>
  );
}
