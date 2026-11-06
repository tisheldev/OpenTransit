import { useI18n } from "../../i18n/I18nProvider";
import { formatClock } from "../../lib/time";
import type { NavState } from "../../nav/engine";
import type { NavStep } from "../../nav/steps";
import { badgeMode, rideStopsText } from "./describe";

// Ride progress (design system: RideProgress) under the current ride in the checklist,
// from real data only. The design lists every stop by name; the trip detail has no
// intermediate stop names (API-C1, not approved) and positions only for the two calls
// before each exit, so the stops between are one row with their count ("8 stops to your
// exit", "2 stops left" once passed calls are measured). Boarding and exit stops, with
// their scheduled times, come from the journey; the exit is called out.

export function RideProgress({ step, state }: { step: NavStep; state: NavState }) {
  const { t, lang } = useI18n();
  if (step.kind !== "ride" || !step.from) return null;
  const onBoard = state.stepIndex === step.index && state.phase !== "waiting";
  const count = step.ride?.stopCount ?? null;
  const between = count !== null && count > 1 ? rideStopsText(step, state, t) : null;
  return (
    <ol className={`ot-ride nav-ride${badgeMode(step) === "rail" ? " nav-ride-rail" : ""}`} aria-label={t("nav.ride.progress")}>
      <li className={`ot-ride__stop ${onBoard ? "ot-ride__stop--done" : "ot-ride__stop--here"}`}>
        <span className="ot-ride__dot" aria-hidden="true" />
        <bdi className="nav-ride-name">{step.from.name}</bdi>
        <time>
          <bdi className="num">{formatClock(step.scheduledDeparture, lang)}</bdi>
        </time>
      </li>
      {between && (
        <li className={`ot-ride__stop${onBoard ? " ot-ride__stop--here" : ""}`}>
          <span className="ot-ride__dot" aria-hidden="true" />
          <bdi className="nav-ride-name">{between}</bdi>
        </li>
      )}
      <li className="ot-ride__stop ot-ride__stop--exit">
        <span className="ot-ride__dot" aria-hidden="true" />
        <bdi className="nav-ride-name">{`${step.target.name} · ${t("nav.fact.exit")}`}</bdi>
        <time>
          <bdi className="num">{formatClock(step.scheduledArrival, lang)}</bdi>
        </time>
      </li>
    </ol>
  );
}
