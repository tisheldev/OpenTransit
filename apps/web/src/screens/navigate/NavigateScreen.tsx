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
import type { NavEffect } from "../../nav/engine";
import { SIM_SPEEDS } from "../../nav/simulatedSource";
import { useTripPrefetch } from "../../nav/usePrefetch";
import { useNavigation, useWakeLock } from "../../nav/useNavigation";
import type { NavStep } from "../../nav/steps";
import { usePlan } from "../../plan/PlanProvider";
import type { Endpoint } from "../../plan/draft";
import { go, hrefFor } from "../../router";
import { useSheet } from "../../shell/sheet";
import { badgeLabel, badgeMode, isolate, isSameStop, placeName, rowText, stepSummary, type EndLabels } from "./describe";
import { navScene } from "./navScene";
import { RideProgress } from "./RideProgress";
import { StepCard } from "./StepCard";
import "./navigate.css";

// Navigate — C05 (design: Screens 5). Reads the active trip only; the engine advances on
// location fixes, Next step or a checklist tap. The web client cannot follow location
// with the screen locked (design S6.5 is native-only), so it says "keep this page open".
//
// Layout at the half sheet (the shell's default for Navigate): the step card, with what
// comes next in it, above one primary action, and the map (your position, the active leg)
// above the sheet. Drag the sheet up for every step and the testing tools.

/** Street-level recentring at most this often (real time), so each camera move finishes. */
const LOCATE_EVERY_MS = 500;
/** One more recentre this long after the last fix (the lazy map may not have been there). */
const LOCATE_SETTLE_MS = 2_000;

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
  if (step.kind === "ride") return <LineBadge mode={badgeMode(step)} label={badgeLabel(step, t)} />;
  if (step.kind === "arrive") return <Icon name="pin" />;
  if (step.kind === "transfer_walk" && isSameStop(step)) return <Icon name="stop" />;
  return <Icon name="walk" />;
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
  const topRef = useRef<HTMLDivElement>(null);

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
    if (parts.length > 0) setAnnouncement((a) => ({ text: parts.join(". "), n: a.n + 1 }));
    if (cue && typeof navigator !== "undefined" && typeof navigator.vibrate === "function") navigator.vibrate([200, 100, 200]);
  };
  const nav = useNavigation(trip, onEffects);
  const { steps, state, fix } = nav;
  const step = steps[state.stepIndex]!;
  const last = step.kind === "arrive";

  useWakeLock(state.phase !== "arrived");

  const leave = () => {
    nav.stop();
    endActiveTrip();
    go({ name: "home" }, { replace: true });
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

  // A new step (a checklist tap, Next, or the engine) or a smaller sheet brings the card
  // (and the banners above it: "simulated" must stay in view) back into view when the
  // passenger had scrolled down to the checklist or the tools.
  const seen = useRef({ stepIndex: state.stepIndex, snap });
  useEffect(() => {
    if (seen.current.stepIndex === state.stepIndex && seen.current.snap === snap) return;
    seen.current = { stepIndex: state.stepIndex, snap };
    const top = topRef.current;
    if (top && typeof top.scrollIntoView === "function") top.scrollIntoView({ block: "nearest" });
  }, [state.stepIndex, snap]);

  // The card (pinned at the full sheet) and the bottom action cover the checklist's
  // edges; their heights become scroll margins so a focused or scrolled-to row is never
  // hidden beneath them (keyboard focus, scrollIntoView). At the half sheet the card must
  // also clear the pinned Next step whatever the fonts or the text (a long stop name, a
  // countdown in hours): the sheet is asked for the height from its top to the card's
  // end plus the action (fitHalf), so it grows rather than hide the card's last lines.
  const rootRef = useRef<HTMLDivElement>(null);
  const actionsRef = useRef<HTMLDivElement>(null);
  useLayoutEffect(() => {
    const root = rootRef.current;
    if (!root) return;
    const report = () => {
      const top = topRef.current;
      const pinned = getComputedStyle(top ?? root).position === "sticky";
      const actions = actionsRef.current?.getBoundingClientRect().height ?? 0;
      root.style.setProperty("--nav-cover-top", `${pinned ? Math.round(top?.getBoundingClientRect().height ?? 0) : 0}px`);
      root.style.setProperty("--nav-cover-bottom", `${Math.round(actions)}px`);
      const sheet = root.closest(".sheet");
      const scroller = root.closest(".sheet-content");
      if (snap !== "half" || !top || !sheet || !scroller) return fitHalf(null);
      const needed = top.getBoundingClientRect().bottom - sheet.getBoundingClientRect().top + scroller.scrollTop + actions;
      fitHalf(needed > 0 ? needed : null);
    };
    report();
    if (typeof ResizeObserver === "undefined") return () => fitHalf(null);
    const observer = new ResizeObserver(report);
    if (topRef.current) observer.observe(topRef.current);
    if (actionsRef.current) observer.observe(actionsRef.current);
    return () => {
      observer.disconnect();
      fitHalf(null);
    };
  }, [snap, fitHalf]);

  // Camera: the current leg is framed, and on board it stays framed while the dot moves
  // along it toward the exit (how far is my stop?). On foot, and waiting at the stop, the
  // map recentres on the passenger at street level (the map's Locate: zoom 15 or closer),
  // at most twice a second so each move finishes, also at simulated speed-ups.
  const streetLevel = !!fix && (step.kind !== "ride" || state.phase === "waiting");
  const { origin, destination } = labels;
  const scene = useMemo<MapScene>(
    () => navScene(trip.journey, step, { origin, destination }, fix, streetLevel ? "keep" : "fit"),
    [trip.journey, step, origin, destination, fix, streetLevel],
  );
  usePublishScene(scene);
  const lastLocate = useRef(-Infinity);
  useEffect(() => {
    if (!streetLevel) return;
    const locate = () => {
      lastLocate.current = performance.now();
      requestLocate();
    };
    if (performance.now() - lastLocate.current >= LOCATE_EVERY_MS) locate();
    // The map loads lazily and ignores a request made before it mounted, and a passenger
    // standing still gets few fixes: recentre once more after the map has had time to load.
    const id = setTimeout(locate, LOCATE_SETTLE_MS);
    return () => clearTimeout(id);
  }, [scene, streetLevel]);

  const manual = state.locationMode === "manual" && !nav.simulated;
  // The checklist's head (design: navigation sheet header): where to, and when.
  const arrival = steps[steps.length - 1]!;
  const arrivalPlace = placeName(arrival.target, labels, t);

  return (
    <div className={`navigate navigate-${snap}`} ref={rootRef}>
      <h1 className="visually-hidden">{t("screen.navigate")}</h1>
      <div className="navigate-top" ref={topRef}>
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
        <StepCard steps={steps} state={state} fix={fix} clock={nav.clock} labels={labels} onEnd={last ? null : leave} />
      </div>

      <section className="nav-checklist" aria-labelledby="nav-checklist-title">
        <div className="ot-navhead nav-checklist-head">
          <div>
            <h2 id="nav-checklist-title" className="nav-section-title">
              {t("nav.checklist")}
            </h2>
            <span>
              <Bdi>{t("nav.toward", { place: isolate(arrivalPlace, lang), time: formatClock(arrival.scheduledArrival, lang) })}</Bdi>
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
                {status === "current" && item.kind === "ride" && <RideProgress step={item} state={state} />}
              </li>
            );
          })}
        </ol>
        <p className="ot-banner ot-banner--compact nav-keep-open">
          <Icon name="info" />
          <span className="ot-banner__body">{t("nav.keepOpen")}</span>
        </p>
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

      <div className="navigate-actions" ref={actionsRef}>
        <button type="button" className="ot-btn ot-btn--primary ot-btn--block nav-next" onClick={last ? leave : nav.next}>
          {last ? t("nav.finish") : t("nav.next")}
        </button>
      </div>

      <div className="visually-hidden" aria-live="polite" aria-atomic="true">
        {announcement.text && <p key={announcement.n}>{announcement.text}</p>}
      </div>
    </div>
  );
}
