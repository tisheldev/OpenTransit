import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { Icon, LineBadge } from "../../components/ds";
import { Bdi } from "../../components/states";
import { useI18n } from "../../i18n/I18nProvider";
import type { MessageKey } from "../../i18n/messages";
import { formatClock } from "../../lib/time";
import type { LocationError } from "../../lib/geolocation";
import { requestLocate, usePublishScene, type MapScene } from "../../map/scene";
import {
  endActiveTrip,
  isExpired,
  updateActiveTrip,
  useActiveTrip,
  wasExpiredOnLoad,
  type ActiveTrip,
} from "../../nav/activeTrip";
import { engineCallPositions } from "../../nav/callPositions";
import type { NavEffect } from "../../nav/engine";
import { SIM_SPEEDS } from "../../nav/simulatedSource";
import { useTripPrefetch } from "../../nav/usePrefetch";
import { useNavigation, useWakeLock } from "../../nav/useNavigation";
import type { NavStep } from "../../nav/steps";
import { usePlan } from "../../plan/PlanProvider";
import type { Endpoint } from "../../plan/draft";
import { go, hrefFor } from "../../router";
import { SNAP_FRACTION, useSheet } from "../../shell/sheet";
import { Answer } from "./Answer";
import { badgeLabel, badgeMode, countdownText, isolate, rideLine, isSameStop, placeName, rowText, rideName, stepSummary, type EndLabels } from "./describe";
import { missedRide } from "./missed";
import { MissedPanel } from "./MissedPanel";
import { navScene } from "./navScene";
import { rideRemaining } from "./rideRows";
import "./navigate.css";

// Navigate — C05, as the approved boards 4–6 (user, 11 November 2026): the map is the
// interface and the panel at its foot gives one answer. Walking, the map follows the
// passenger and the panel says where to, how far, and whether the bus will be caught
// ("עליתי" when on board); on board it counts the stops to the exit and lists them
// ("ירדתי"); "לא הגיע?" offers the choices from where the passenger stands. A close
// button (end navigation) and the arrival time float over the map. Drag the sheet up for
// every step (the checklist) and the testing tools. The web client cannot follow location
// with the screen locked (design S6.5 is native-only), so it says "keep this page open".

/** One more recentre this long after the step starts following (the lazy map may not have been there). */
const LOCATE_SETTLE_MS = 2_000;
/** Room kept under the panel's actions when the sheet is sized to it. */
const PANEL_GAP_PX = 8;

const endpointLabel = (endpoint: Endpoint | null): string | null =>
  endpoint?.type === "place" ? endpoint.place.label : null;

/** Why location is off, in one short phrase (the banner adds "steps advance manually"). */
function locationReason(error: LocationError | null): MessageKey {
  if (typeof window !== "undefined" && window.isSecureContext === false) return "nav.loc.insecure";
  if (error === "unsupported") return "nav.loc.unsupported";
  return "nav.loc.denied";
}

function NoTrip() {
  const { t } = useI18n();
  useEffect(() => {
    if (wasExpiredOnLoad()) go({ name: "home" }, { replace: true });
  }, []);
  return (
    <div className="navigate navigate-none">
      <h1>{t("screen.navigate")}</h1>
      <p className="ot-banner nav-none">{t("nav.noTrip")}</p>
      <a className="ot-btn ot-btn--secondary ot-btn--block" href={hrefFor({ name: "home" })}>
        {t("screen.backHome")}
      </a>
    </div>
  );
}

/** A checklist row's mode: the line's badge for a ride, an icon for walking and arriving. */
function RowIcon({ step }: { step: NavStep }) {
  const { t } = useI18n();
  if (step.kind === "ride") return <LineBadge mode={badgeMode(step)} label={badgeLabel(step, t)} line={rideLine(step)} />;
  if (step.kind === "arrive") return <Icon name="pin" />;
  if (step.kind === "transfer_walk" && isSameStop(step)) return <Icon name="stop" />;
  return <Icon name="walk" />;
}

/** Publishes the map while mounted (Bus didn't come publishes its own instead). */
function NavMap({ scene }: { scene: MapScene }) {
  usePublishScene(scene);
  return null;
}

export function NavigateScreen() {
  const trip = useActiveTrip();
  if (!trip) return <NoTrip />;
  return <Navigating key={trip.startedAt} trip={trip} />;
}

function Navigating({ trip }: { trip: ActiveTrip }) {
  const { t, lang } = useI18n();
  const { draft } = usePlan();
  const { snap, setSnap, fitHalf } = useSheet();
  const [announcement, setAnnouncement] = useState<{ text: string; n: number }>({ text: "", n: 0 });
  const announce = (text: string) => setAnnouncement((a) => ({ text, n: a.n + 1 }));
  /** The step "לא הגיע?" was opened on; it closes by itself when the step changes. */
  const [missedAt, setMissedAt] = useState<number | null>(null);

  // The plan's end labels at Start: coordinate ends are "START"/"END" in the journey.
  const labels: EndLabels = trip.labels ?? { origin: endpointLabel(draft.from), destination: endpointLabel(draft.to) };
  useEffect(() => {
    if (trip.labels) return;
    updateActiveTrip((t) => (t.startedAt === trip.startedAt && !t.labels ? { ...t, labels } : t));
  });

  useTripPrefetch(trip.startedAt);

  const onEffects = (effects: NavEffect[], steps: readonly NavStep[]) => {
    const parts: string[] = [];
    let cue = false;
    for (const effect of effects) {
      if (effect.type === "step_changed") {
        const changed = steps[effect.stepIndex]!;
        parts.push(t("nav.announce.step", { n: effect.stepIndex + 1, total: steps.length, summary: stepSummary(changed, labels, t, lang, steps[effect.stepIndex + 1]) }));
      } else if (effect.type === "cue") {
        cue = true;
        parts.push(t(effect.cue === "next_stop" ? "nav.cueNext" : "nav.cueTwo"));
      }
    }
    if (parts.length > 0) announce(parts.join(". "));
    if (cue && typeof navigator !== "undefined" && typeof navigator.vibrate === "function") navigator.vibrate([200, 100, 200]);
  };
  const nav = useNavigation(trip, onEffects);
  const { steps, state, fix } = nav;
  const step = steps[state.stepIndex]!;
  const last = step.kind === "arrive";
  const missed = missedRide(steps, state.stepIndex, state.phase);
  const showMissed = missedAt === state.stepIndex && missed !== null;

  useWakeLock(state.phase !== "arrived");

  const leave = () => {
    nav.stop();
    endActiveTrip();
    go({ name: "home" }, { replace: true });
  };
  const board = () => {
    // Waiting at the stop, boarding keeps the step: say so (a new step announces itself).
    if (step.kind === "ride" && state.phase === "waiting") announce(t("nav.announce.boarded", { ride: rideName(step, t) }));
    setMissedAt(null);
    nav.board();
  };

  // Expiry while open (two hours after the scheduled arrival): cleared, back Home.
  useEffect(() => {
    const check = () => {
      if (isExpired(trip)) {
        endActiveTrip();
        go({ name: "home" }, { replace: true });
      }
    };
    check();
    const id = setInterval(check, 60_000);
    return () => clearInterval(id);
  }, [trip]);

  // The map (boards 4–6). Countdown and stop words change at most once a minute, so the
  // scene (and a fitted camera) does not move with every clock tick.
  const callPositions = useMemo(() => engineCallPositions(trip.callPositions), [trip.callPositions]);
  const ridePositions = callPositions[step.index];
  const riding = step.kind === "ride" && state.phase !== "waiting";
  const passed = riding ? rideRemaining(step, state, step.ride ? trip.trips[step.ride.tripRef] : undefined, ridePositions, nav.clock).passed : null;
  const boarding = step.kind === "ride" ? step : steps[step.index + 1]?.kind === "ride" ? steps[step.index + 1]! : null;
  const countdown = boarding ? countdownText(boarding.scheduledDeparture, nav.clock, t, lang, "departure") : null;
  const badge = boarding ? badgeLabel(boarding, t) : "";
  const exitHere = t("nav.answer.exitHere");
  const waiting = state.phase === "waiting";
  const scene = useMemo<MapScene>(
    () =>
      navScene({
        journey: trip.journey,
        steps,
        step,
        waiting,
        labels,
        fix,
        callPositions: ridePositions,
        passedOrdinal: passed,
        words: { badge, countdown, exitHere },
      }),
    // labels: its two strings, not the object (rebuilt on every render)
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [trip.journey, steps, step, waiting, labels.origin, labels.destination, fix, ridePositions, passed, badge, countdown, exitHere],
  );

  // Walking (and waiting at the stop) the map follows the passenger at street level: one
  // recentre (the map's Locate: zoom 15 or closer) when following starts, once more after
  // the lazy map has had time to load; the scene's "follow" camera keeps them centred.
  const following = !!fix && !riding && !last && !showMissed;
  useEffect(() => {
    if (!following) return;
    requestLocate();
    const id = setTimeout(requestLocate, LOCATE_SETTLE_MS);
    return () => clearTimeout(id);
  }, [following, state.stepIndex]);

  // The sheet holds one answer (the boards' collapsed panel): sized to the panel when the
  // view changes, at the peek when it fits there, else the half grown to fit (fitHalf),
  // never beyond the full sheet. The passenger's own drag rules until the view changes.
  const rootRef = useRef<HTMLDivElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const view = `${state.stepIndex}|${riding ? "ride" : waiting ? "wait" : "walk"}|${showMissed ? "missed" : ""}`;
  const seenView = useRef<string | null>(null);
  useLayoutEffect(() => {
    const root = rootRef.current;
    const panel = panelRef.current;
    if (!root || !panel) return;
    const sheet = root.closest(".sheet");
    const scroller = root.closest(".sheet-content");
    const needed = () => {
      if (!sheet || !scroller) return 0;
      return panel.getBoundingClientRect().bottom - sheet.getBoundingClientRect().top + scroller.scrollTop + PANEL_GAP_PX;
    };
    const peekPx = () => SNAP_FRACTION.peek * (root.closest(".shell")?.getBoundingClientRect().height || window.innerHeight);
    const changed = seenView.current !== view;
    seenView.current = view;
    if (changed && scroller) scroller.scrollTop = 0;
    const report = (choose: boolean) => {
      // No layout (jsdom, a hidden page): nothing to size; the shell's snap stays.
      if (panel.getBoundingClientRect().height <= 0) return fitHalf(null);
      const px = needed();
      if (choose && snap !== "full") {
        const want = px <= peekPx() ? "peek" : "half";
        if (want !== snap) setSnap(want);
      } else if (snap === "peek" && px > peekPx()) {
        // Fonts or a banner made the panel taller than the peek: the half, sized to it.
        setSnap("half");
      }
      fitHalf(snap === "half" ? px : null);
    };
    report(changed);
    if (typeof ResizeObserver === "undefined") return () => fitHalf(null);
    const observer = new ResizeObserver(() => report(false));
    observer.observe(panel);
    return () => {
      observer.disconnect();
      fitHalf(null);
    };
  }, [view, snap, setSnap, fitHalf]);

  const manual = state.locationMode === "manual" && !nav.simulated;
  // The checklist's head (design: navigation sheet header): where to, and when.
  const arrival = steps[steps.length - 1]!;
  const arrivalPlace = placeName(arrival.target, labels, t);
  const arrivalTime = formatClock(arrival.scheduledArrival, lang);

  return (
    <div className={`navigate navigate-${snap}`} ref={rootRef}>
      {/* Over the map (boards 4–5): end navigation at the inline start, the arrival time at the end. */}
      {snap !== "full" && (
        <div className="nav-floats">
          {!last && (
            <button type="button" className="b-close nav-float nav-float--start" aria-label={t("nav.end")} onClick={leave}>
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true" focusable="false">
                <path d="M6 6l12 12M18 6L6 18" />
              </svg>
            </button>
          )}
          <span className="b-tag nav-float nav-float--end">
            <Bdi>{t("nav.answer.arriving", { time: arrivalTime })}</Bdi>
          </span>
        </div>
      )}

      <div className="nav-panel" ref={panelRef}>
        {manual && (
          <p className="ot-banner ot-banner--warning ot-banner--compact nav-banner" role="status">
            <Icon name="alert" />
            <span className="ot-banner__body">
              {t(locationReason(nav.locationError))} · {t("nav.manual")}
            </span>
          </p>
        )}
        {!manual && state.locationLost && (
          <p className="ot-banner ot-banner--warning ot-banner--compact nav-banner" role="status">
            <Icon name="locate" />
            <span className="ot-banner__body">
              {t("nav.lost")} · {t("nav.manual")}
            </span>
          </p>
        )}
        {nav.simulated && (
          <p className="ot-banner ot-banner--warning ot-banner--compact nav-banner nav-banner-sim" role="note">
            <Icon name="info" />
            <span className="ot-banner__body">
              <Bdi>{t("nav.sim.on", { time: formatClock(new Date(nav.clock), lang), n: nav.simSpeed })}</Bdi>
            </span>
          </p>
        )}
        {showMissed && missed ? (
          <MissedPanel trip={trip} ride={missed} fix={fix} clock={nav.clock} labels={labels} onBoarded={board} onCancel={() => setMissedAt(null)} />
        ) : (
          <Answer
            steps={steps}
            state={state}
            fix={fix}
            clock={nav.clock}
            labels={labels}
            trips={trip.trips}
            callPositions={ridePositions}
            onBoard={board}
            onNext={nav.next}
            onMissed={missed ? () => setMissedAt(state.stepIndex) : null}
            onFinish={leave}
          />
        )}
      </div>
      {!showMissed && <NavMap scene={scene} />}

      <section className="nav-checklist" aria-labelledby="nav-checklist-title">
        <div className="ot-navhead nav-checklist-head">
          <div>
            <h2 id="nav-checklist-title" className="nav-section-title">
              {t("nav.checklist")}
            </h2>
            <span>
              <Bdi>{t("nav.toward", { place: isolate(arrivalPlace, lang), time: arrivalTime })}</Bdi>
            </span>
          </div>
        </div>
        <ol className="ot-steps checklist" aria-labelledby="nav-checklist-title">
          {steps.map((item) => {
            const status = item.index < state.stepIndex ? "done" : item.index === state.stepIndex ? "current" : "pending";
            const row = rowText(item, labels, t, lang, steps[item.index + 1]);
            const itemClass = status === "done" ? " ot-steps__item--done" : status === "current" ? " ot-steps__item--now" : "";
            return (
              <li key={item.index} className={`ot-steps__item${itemClass}`}>
                <button
                  type="button"
                  className={`ot-steps__row checklist-row checklist-${status}`}
                  aria-current={status === "current" ? "step" : undefined}
                  onClick={() => nav.jump(item.index)}
                >
                  {/* The name is the visible text with the state in front (not colour alone). */}
                  <span className="visually-hidden">{`${t(`nav.row.${status}`)}:`}</span>{" "}
                  <time className="checklist-time">{row.time}</time>{" "}
                  <span className="ot-steps__icon" aria-hidden="true">
                    <RowIcon step={item} />
                  </span>
                  <span className="ot-steps__text checklist-body">
                    <bdi className="checklist-main">{row.main}</bdi>
                    {row.sub && (
                      <>
                        <span className="visually-hidden">,</span>{" "}
                        <small className="checklist-sub">
                          <bdi>{row.sub}</bdi>
                        </small>
                      </>
                    )}
                  </span>
                  <span className={`checklist-mark checklist-mark-${status}`} aria-hidden="true">
                    {status === "done" ? "✓" : status === "current" ? "●" : ""}
                  </span>
                </button>
              </li>
            );
          })}
        </ol>
        <p className="ot-banner ot-banner--compact nav-keep-open">
          <Icon name="info" />
          <span className="ot-banner__body">{t("nav.keepOpen")}</span>
        </p>
        {snap === "full" && !last && (
          <button type="button" className="b-btn nav-end-full" onClick={leave}>
            {t("nav.end")}
          </button>
        )}
      </section>

      <section className="nav-testing" aria-labelledby="nav-testing-title">
        <h2 id="nav-testing-title" className="nav-section-title">
          {t("nav.testing")}
        </h2>
        <label className="nav-sim-toggle">
          <input
            type="checkbox"
            checked={nav.simulated}
            onChange={(event) => {
              const on = event.target.checked;
              nav.setSimulated(on);
              // Show the map: the simulated dot moving along the route is the point.
              if (on) setSnap("half");
            }}
          />
          {t("nav.sim.toggle")}
        </label>
        <label className="nav-sim-speed">
          {t("nav.sim.speed")}{" "}
          <select value={nav.simSpeed} onChange={(event) => nav.setSimSpeed(Number(event.target.value))}>
            {SIM_SPEEDS.map((speed) => (
              <option key={speed} value={speed}>
                {t("nav.sim.speedValue", { n: speed })}
              </option>
            ))}
          </select>
        </label>
      </section>

      <div className="visually-hidden" aria-live="polite" aria-atomic="true">
        {announcement.text && <p key={announcement.n}>{announcement.text}</p>}
      </div>
    </div>
  );
}
