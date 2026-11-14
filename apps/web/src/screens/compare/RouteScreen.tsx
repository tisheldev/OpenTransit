import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";
import type { Journey } from "../../api/types";
import { TestDataBanner } from "../../components/states";
import { useI18n } from "../../i18n/I18nProvider";
import { useTheme } from "../../lib/theme";
import { formatClock, israelWallTime } from "../../lib/time";
import { usePublishScene } from "../../map/scene";
import type { Endpoint, PlaceChoice } from "../../plan/draft";
import { hrefFor } from "../../router";
import { addFavourite, deleteSaved, useLocalState } from "../../shell/localStore";
import { Banner } from "./Banner";
import { OptionsSkeleton } from "./OptionRow";
import { draftScene, stepScene } from "./journeyScene";
import { daysBetween, israelDate, untilText, type EndLabels } from "./labels";
import { Duration, NextDay, Nums, TimeArrow } from "./text";
import type { Departure } from "./RideDepartures";
import { Timeline } from "./Timeline";
import { useCompare, useNow, useScrollPadding, type TripState } from "./useCompare";

// Compare, step 2: route details of the chosen option (board 3 Step, approved 11 November
// 2026; replaces C04). Opened by "פרטי המסלול" at #/route; Back returns to Choose. The
// header: departure ← arrival, the duration and how long until it leaves. The timeline
// (Timeline.tsx): tap a leg and the map zooms to it (fitTo); the stop where its ride is
// boarded is a large pin saying which way the bus goes (and which side of the road, once
// the API says). "כל המסלול" floats over the map and zooms back out. At the bottom: save
// the destination (a star) and "יוצאים לדרך", which starts navigation.

/** The saved favourite at the same place (5 decimals, as Compare's suggestions match). */
function useFavourite(place: PlaceChoice | null) {
  const local = useLocalState();
  if (!place) return null;
  const key = (lat: number, lon: number) => `${lat.toFixed(5)},${lon.toFixed(5)}`;
  const target = key(place.latitude, place.longitude);
  return local.favourites.find((saved) => key(saved.latitude, saved.longitude) === target) ?? null;
}

/** "כל המסלול" over the map (top inline end, below the shell's top band); inline without the shell. */
function WholeRouteButton({ onClick }: { onClick: () => void }) {
  const { t } = useI18n();
  const button = (
    <button type="button" className="b-tag b-float b-float--end compare-whole" onClick={onClick}>
      {t("route.all")}
    </button>
  );
  const shell = typeof document === "undefined" ? null : document.querySelector(".shell");
  return shell ? createPortal(button, shell) : button;
}

function Details({
  journey,
  ends,
  trips,
  fixture,
  onReplan,
}: {
  journey: Journey;
  ends: EndLabels;
  trips: Record<string, TripState>;
  fixture: boolean;
  onReplan: (legIndex: number, departure: Departure) => void;
}) {
  const { t, lang } = useI18n();
  const theme = useTheme();
  const now = useNow();
  // The first leg is on the map when the details open (board Step: the walk to the stop).
  const [focused, setFocused] = useState<number | null>(0);
  const headingRef = useRef<HTMLHeadingElement>(null);

  const scene = useMemo(() => stepScene(journey, ends, focused, { t, lang, theme }), [journey, ends, focused, t, lang, theme]);
  usePublishScene(scene);

  const { scheduledDeparture: leave, scheduledArrival: arrive } = journey.timing;
  const overnight = daysBetween(israelDate(leave), israelDate(arrive));
  const until = untilText(leave, now, lang, t);
  return (
    <>
      {focused !== null && (
        <WholeRouteButton
          onClick={() => {
            setFocused(null);
            headingRef.current?.focus({ preventScroll: true });
          }}
        />
      )}
      <div className="route-head">
        <h1 ref={headingRef} className="route-head__times" tabIndex={-1}>
          <span className="visually-hidden">
            {t("screen.route")}: {t("compare.departs", { time: formatClock(leave, lang) })}, {t("compare.arrives", { time: formatClock(arrive, lang) })}
          </span>
          <span className="route-head__figure" aria-hidden="true">
            <bdi className="num">{formatClock(leave, lang)}</bdi>
            <TimeArrow />
            <bdi className="num">{formatClock(arrive, lang)}</bdi>
            {overnight > 0 && <NextDay days={overnight} />}
          </span>
        </h1>
        <span className="b-mu route-head__duration">
          <Duration seconds={journey.durationSeconds} />
        </span>
        {until && (
          <span className="b-tag b-tag--strong route-head__until">
            <Nums text={until} />
          </span>
        )}
      </div>
      {fixture && <TestDataBanner />}
      <section className="route-details" aria-label={t("screen.route")}>
        <Timeline journey={journey} ends={ends} trips={trips} focused={focused} onFocus={setFocused} onReplan={onReplan} />
      </section>
    </>
  );
}

export function RouteScreen() {
  const { t } = useI18n();
  const compare = useCompare();
  const { plan, ends, answer, chosen, trips, refreshing, start, resume, built, planned, journeys, list, choose } = compare;
  const rootRef = useRef<HTMLDivElement>(null);
  useScrollPadding(rootRef);

  // Board 6: another departure of a ride's line was chosen. Re-plan by time rather than by
  // pinning the trip: `pinnedTrip` answers one walk and one ride, which would drop the rest
  // of a journey with a transfer or a final walk, and `excludeTripRefs` alone cannot say
  // which later trip to take. So the journey now leaves when the passenger must leave to
  // reach that departure (its departure less the time from the journey's start to the
  // boarding stop): the earlier trips can no longer be caught. The option that rides the
  // chosen trip is then selected when the engine returns one; otherwise its own best.
  const wanted = useRef<{ tripRef: string; asked: unknown } | null>(null);
  const replan = (legIndex: number, departure: Departure) => {
    if (!chosen) return;
    const leg = chosen.legs[legIndex];
    if (!leg) return;
    const lead = Date.parse(leg.timing.scheduledDeparture) - Date.parse(chosen.timing.scheduledDeparture);
    const leave = new Date(Date.parse(departure.scheduledDeparture) - Math.max(0, lead));
    wanted.current = { tripRef: departure.tripRef, asked: answer?.sent ?? null };
    plan.setWhen({ mode: "depart_at", wall: israelWallTime(leave), offset: "auto" });
  };
  useEffect(() => {
    const want = wanted.current;
    // The new answer only (not the one on screen when the departure was chosen).
    if (!want || !answer || refreshing || answer.sent === want.asked) return;
    wanted.current = null;
    const index = list.findIndex((journey) => journey.legs.some((leg) => leg.transit?.engineTripId === want.tripRef));
    if (index > 0) choose(index);
  }, [answer, refreshing, list, choose]);

  // Without an answer (a deep link still loading, or nothing found) the map shows the ends.
  const fallbackScene = useMemo(() => draftScene(plan.draft.from, plan.draft.to, ends), [plan.draft.from, plan.draft.to, ends]);

  let body: ReactNode;
  if (answer && chosen) {
    body = (
      <Details
        key={`${plan.selected}-${chosen.id}`}
        journey={chosen}
        ends={ends}
        trips={trips}
        fixture={answer.response.meta.mode === "fixture"}
        onReplan={replan}
      />
    );
  } else if (built.isPending || (planned && journeys.isPending)) {
    body = (
      <>
        <h1 className="visually-hidden" tabIndex={-1}>
          {t("screen.route")}
        </h1>
        <OptionsSkeleton />
      </>
    );
  } else {
    body = (
      <>
        <h1 className="visually-hidden" tabIndex={-1}>
          {t("screen.route")}
        </h1>
        <Banner icon="info" title={t("compare.noRoute")} role="status" />
        <a className="ot-btn ot-btn--secondary" href={hrefFor({ name: "compare" })}>
          {t("screen.compare")}
        </a>
      </>
    );
  }

  return (
    <div className="compare route" ref={rootRef}>
      {!(answer && chosen) && <FallbackScene scene={fallbackScene} />}
      {body}
      {answer && chosen && <RouteActions destination={plan.draft.to} refreshing={refreshing} resume={resume} onStart={start} />}
    </div>
  );
}

/**
 * Board 3's bottom row: save the destination (the client has no saved trips) and start.
 * Also under the chosen option on a wide screen, where its steps open in place (board 8).
 */
export function RouteActions({
  destination: to,
  refreshing,
  resume,
  onStart,
}: {
  destination: Endpoint | null;
  refreshing: boolean;
  resume: boolean;
  onStart: () => void;
}) {
  const { t } = useI18n();
  const destination = to?.type === "place" ? to.place : null;
  const favourite = useFavourite(destination);
  const toggleFavourite = () => {
    if (!destination) return;
    if (favourite) deleteSaved(favourite.id);
    else addFavourite(destination, destination.label);
  };
  return (
    <div className="compare-start">
      <button
        type="button"
        className="b-btn b-btn--icon"
        aria-label={t("route.save")}
        aria-pressed={favourite !== null}
        disabled={!destination}
        onClick={toggleFavourite}
      >
        <svg width="20" height="20" viewBox="0 0 24 24" fill={favourite ? "currentColor" : "none"} stroke="currentColor" strokeWidth="1.9" strokeLinejoin="round" aria-hidden="true" focusable="false">
          <path d="M12 3.5l2.6 5.4 5.9.8-4.3 4.1 1.1 5.8L12 16.8l-5.3 2.8 1.1-5.8-4.3-4.1 5.9-.8z" />
        </svg>
      </button>
      <button type="button" className="b-btn b-btn--main compare-start__main" disabled={refreshing} onClick={onStart}>
        {resume ? t("compare.resume") : t("compare.start")}
      </button>
    </div>
  );
}

function FallbackScene({ scene }: { scene: ReturnType<typeof draftScene> }) {
  usePublishScene(scene);
  return null;
}
