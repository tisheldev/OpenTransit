import { useEffect, useMemo, useRef, useState } from "react";
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
import { rowText, stepSummary, type EndLabels } from "./describe";
import { navScene } from "./navScene";
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
    <div className="navigate">
      <h1>{t("screen.navigate")}</h1>
      <p>{t("nav.noTrip")}</p>
      <a className="button block" href={hrefFor({ name: "home" })}>
        {t("screen.backHome")}
      </a>
    </div>
  );
}

export function NavigateScreen() {
  const trip = useActiveTrip();
  if (!trip) return <NoTrip />;
  return <Navigating key={trip.startedAt} trip={trip} />;
}

function Navigating({ trip }: { trip: ActiveTrip }) {
  const { t, lang } = useI18n();
  const { draft } = usePlan();
  const { snap, setSnap } = useSheet();
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

  // Camera: the current leg until a fix arrives. On foot (and waiting at the stop) the
  // map recentres on the passenger at street level (the map's Locate: zoom 15 or closer),
  // at most twice a second so each move finishes; on board it follows at the zoom the
  // passenger chose, so zooming out to see the ride stays possible. Simulated playback
  // runs 30–600 times faster than a vehicle, which a smooth follow cannot keep up with,
  // so it recentres in steps on board too.
  const streetLevel = !!fix && (nav.simulated || step.kind !== "ride" || state.phase === "waiting");
  const { origin, destination } = labels;
  const scene = useMemo<MapScene>(
    () => navScene(trip.journey, step, { origin, destination }, fix, !fix ? "fit" : streetLevel ? "keep" : "follow"),
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

  return (
    <div className={`navigate navigate-${snap}`}>
      <h1 className="visually-hidden">{t("screen.navigate")}</h1>
      <div className="navigate-top" ref={topRef}>
        {manual && (
          <p className="nav-banner" role="status">
            {t(locationReason(nav.locationError))} · {t("nav.manual")}
          </p>
        )}
        {!manual && state.locationLost && (
          <p className="nav-banner" role="status">
            {t("nav.lost")} · {t("nav.manual")}
          </p>
        )}
        {nav.simulated && (
          <p className="nav-banner nav-banner-sim" role="note">
            <span aria-hidden="true">◌ </span>
            {t("nav.sim.on", { time: formatClock(new Date(nav.clock), lang), n: nav.simSpeed })}
          </p>
        )}
        <StepCard steps={steps} state={state} fix={fix} clock={nav.clock} labels={labels} onEnd={last ? null : leave} />
      </div>

      <section className="nav-checklist" aria-labelledby="nav-checklist-title">
        <h2 id="nav-checklist-title" className="section-title">
          {t("nav.checklist")}
        </h2>
        <ol className="checklist">
          {steps.map((item) => {
            const status = item.index < state.stepIndex ? "done" : item.index === state.stepIndex ? "current" : "pending";
            const row = rowText(item, labels, t, lang, steps[item.index + 1]);
            return (
              <li key={item.index}>
                <button
                  type="button"
                  className={`checklist-row checklist-${status}`}
                  aria-current={status === "current" ? "step" : undefined}
                  aria-label={`${t(`nav.row.${status}`)}: ${row.time} ${row.main}${row.sub ? `, ${row.sub}` : ""}`}
                  onClick={() => nav.jump(item.index)}
                >
                  <span className="checklist-time tabular" aria-hidden="true">
                    {row.time}
                  </span>
                  <span className={`checklist-mark checklist-mark-${status}`} aria-hidden="true">
                    {status === "done" ? "✓" : status === "current" ? "●" : ""}
                  </span>
                  <span className="checklist-body" aria-hidden="true">
                    <bdi className="checklist-main">{row.main}</bdi>
                    {row.sub && <bdi className="checklist-sub">{row.sub}</bdi>}
                  </span>
                </button>
              </li>
            );
          })}
        </ol>
        <p className="muted small nav-keep-open">{t("nav.keepOpen")}</p>
      </section>

      <section className="nav-testing" aria-labelledby="nav-testing-title">
        <h2 id="nav-testing-title" className="section-title">
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

      <div className="navigate-actions">
        <button type="button" className="button button-primary nav-next" onClick={last ? leave : nav.next}>
          {last ? t("nav.finish") : t("nav.next")}
        </button>
      </div>

      <div className="visually-hidden" aria-live="polite" aria-atomic="true">
        {announcement.text && <p key={announcement.n}>{announcement.text}</p>}
      </div>
    </div>
  );
}
