import { useEffect, useMemo, useState } from "react";
import { useI18n } from "../../i18n/I18nProvider";
import { formatClock } from "../../lib/time";
import { journeyToScene } from "../../map/fromJourney";
import { usePublishScene, type MapScene } from "../../map/scene";
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
import { stepSummary, type EndLabels } from "./describe";
import { StepCard } from "./StepCard";
import "./navigate.css";

// Navigate — C05 (design: Screens 5). Reads the active trip only; the engine advances on
// location fixes, Next step or a checklist tap. The web client cannot follow location
// with the screen locked (design S6.5 is native-only), so it says "keep this page open".

/**
 * The sheet snap Navigate opens at: full. At 360 × 640 a half sheet cannot hold a long
 * step card (rail names, two banners) above the pinned actions; the passenger can drag
 * the sheet down to see more map.
 */
export const NAVIGATE_SNAP = "full" as const;

const endpointLabel = (endpoint: Endpoint | null): string | null =>
  endpoint?.type === "place" ? endpoint.place.label : null;

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
  const { setSnap } = useSheet();
  const [announcement, setAnnouncement] = useState<{ text: string; n: number }>({ text: "", n: 0 });

  useEffect(() => setSnap(NAVIGATE_SNAP), [setSnap]);

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
        parts.push(t("nav.announce.step", { n: effect.stepIndex + 1, total: steps.length, summary: stepSummary(changed, labels, t, lang) }));
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

  const scene = useMemo<MapScene>(() => {
    const base = journeyToScene(trip.journey, {
      activeLeg: step.legIndex,
      originLabel: labels.origin,
      destinationLabel: labels.destination,
    });
    return {
      ...base,
      user: fix ? { position: [fix.longitude, fix.latitude], accuracyMeters: fix.accuracyMeters } : null,
      camera: fix ? "follow" : "fit",
      pick: false,
    };
  }, [trip.journey, step.legIndex, labels.origin, labels.destination, fix]);
  usePublishScene(scene);

  const manual = state.locationMode === "manual" && !nav.simulated;

  return (
    <div className="navigate">
      <h1 className="visually-hidden">{t("screen.navigate")}</h1>
      <div className="navigate-top">
        {manual && (
          <p className="nav-banner" role="status">
            {t("nav.manual")}
          </p>
        )}
        {!manual && state.locationLost && (
          <p className="nav-banner" role="status">
            {t("nav.lost")} · {t("nav.manual")}
          </p>
        )}
        {nav.simulated && (
          <p className="nav-banner nav-banner-sim" role="note">
            {t("nav.sim.on", { time: formatClock(new Date(nav.clock), lang) })}
          </p>
        )}
        <StepCard steps={steps} state={state} fix={fix} clock={nav.clock} labels={labels} />
      </div>

      <section className="nav-checklist" aria-labelledby="nav-checklist-title">
        <h2 id="nav-checklist-title" className="section-title">
          {t("nav.checklist")}
        </h2>
        <ol className="checklist">
          {steps.map((item) => {
            const status = item.index < state.stepIndex ? "done" : item.index === state.stepIndex ? "current" : "pending";
            const summary = stepSummary(item, labels, t, lang);
            return (
              <li key={item.index}>
                <button
                  type="button"
                  className={`checklist-row checklist-${status}`}
                  aria-current={status === "current" ? "step" : undefined}
                  aria-label={`${t(`nav.row.${status}`)}: ${summary}`}
                  onClick={() => nav.jump(item.index)}
                >
                  <span className="checklist-mark" aria-hidden="true">
                    {status === "done" ? "✓" : status === "current" ? "●" : "○"}
                  </span>
                  <bdi className="checklist-text">{summary}</bdi>
                </button>
              </li>
            );
          })}
        </ol>
      </section>

      <section className="nav-testing" aria-labelledby="nav-testing-title">
        <h2 id="nav-testing-title" className="section-title">
          {t("nav.testing")}
        </h2>
        <label className="nav-sim-toggle">
          <input type="checkbox" checked={nav.simulated} onChange={(event) => nav.setSimulated(event.target.checked)} />
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
        <p className="muted small">{t("nav.keepOpen")}</p>
      </section>

      <div className="navigate-actions">
        <button type="button" className="button nav-end" onClick={leave}>
          {t("nav.end")}
        </button>
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
