import type { ReactNode } from "react";
import { Bdi } from "../../components/states";
import { useI18n } from "../../i18n/I18nProvider";
import { formatDistance, formatDuration } from "../../lib/format";
import type { Fix } from "../../lib/geolocation";
import { formatClock } from "../../lib/time";
import type { NavState } from "../../nav/engine";
import { haversineMeters } from "../../nav/geo";
import type { NavStep } from "../../nav/steps";
import { countdownText, placeName, rideHeadsign, rideName, stepSummary, stopsLeftText, type EndLabels } from "./describe";

// The step card (design: Navigate — C05, "Step kind" table): pinned, high contrast.
// Times are scheduled and say so; a platform is never guessed (API-C1 pending).

interface Props {
  steps: readonly NavStep[];
  state: NavState;
  fix: Fix | null;
  clock: number;
  labels: EndLabels;
}

function NextVehicle({ ride, clock }: { ride: NavStep; clock: number }) {
  const { t, lang } = useI18n();
  const headsign = rideHeadsign(ride);
  return (
    <>
      <p className="step-line step-strong">
        <Bdi>{rideName(ride, t)}</Bdi>
        {headsign && (
          <>
            {" "}
            <Bdi>{t("nav.ride.headsign", { headsign })}</Bdi>
          </>
        )}
      </p>
      <p className="step-line">
        <Bdi>{t("nav.departsAt", { time: formatClock(ride.scheduledDeparture, lang) })}</Bdi> ·{" "}
        <Bdi>{countdownText(ride.scheduledDeparture, clock, t, lang)}</Bdi> · {t("nav.platformUnknown")}
      </p>
    </>
  );
}

function WalkDistance({ step, fix }: { step: NavStep; fix: Fix | null }) {
  const { t, lang } = useI18n();
  if (fix && Number.isFinite(step.target.latitude)) {
    const left = formatDistance(haversineMeters(fix, step.target), lang);
    if (left) return <p className="step-line"><Bdi>{t("nav.distanceLeft", { distance: left })}</Bdi></p>;
  }
  const distance = formatDistance(step.distanceMeters, lang);
  if (distance) return <p className="step-line"><Bdi>{t("nav.walkDistance", { distance })}</Bdi></p>;
  return (
    <p className="step-line">
      <Bdi>{t("nav.walkTimeOnly", { duration: formatDuration(step.durationSeconds, lang) })}</Bdi>
    </p>
  );
}

export function StepCard({ steps, state, fix, clock, labels }: Props) {
  const { t, lang } = useI18n();
  const step = steps[state.stepIndex]!;
  const following = steps[step.index + 1];
  const cue = step.kind === "ride" ? state.cue : "none";
  const n = step.index + 1;

  let title: string;
  let body: ReactNode;
  switch (step.kind) {
    case "walk_to_stop":
    case "transfer_walk":
      title = t(step.kind === "walk_to_stop" ? "nav.step.walkToStop" : "nav.step.transferWalk", {
        stop: placeName(step.target, labels, t),
      });
      body = (
        <>
          <WalkDistance step={step} fix={fix} />
          {following?.kind === "ride" && <NextVehicle ride={following} clock={clock} />}
        </>
      );
      break;
    case "walk_to_destination":
      title = t("nav.step.walkToDestination", { place: placeName(step.target, labels, t) });
      body = (
        <>
          <WalkDistance step={step} fix={fix} />
          <p className="step-line">
            <Bdi>{t("nav.arriveAt", { time: formatClock(step.scheduledArrival, lang) })}</Bdi>
          </p>
        </>
      );
      break;
    case "ride": {
      const headsign = rideHeadsign(step);
      title = rideName(step, t);
      const left = state.stopsLeft ?? step.ride?.stopCount ?? null;
      body = (
        <>
          {headsign && (
            <p className="step-line">
              <Bdi>{t("nav.ride.headsign", { headsign })}</Bdi>
            </p>
          )}
          <p className="step-line step-strong">{left === null ? t("nav.stopsUnknown") : stopsLeftText(left, t)}</p>
          <p className="step-line">
            <Bdi>
              {t("nav.exitAt", { stop: step.target.name, time: formatClock(step.scheduledArrival, lang) })}
            </Bdi>
          </p>
          {state.phase === "waiting" && (
            <p className="step-line">
              <Bdi>{t("nav.departsAt", { time: formatClock(step.scheduledDeparture, lang) })}</Bdi> ·{" "}
              <Bdi>{countdownText(step.scheduledDeparture, clock, t, lang)}</Bdi> · {t("nav.platformUnknown")}
            </p>
          )}
          {following && (
            <p className="step-line muted-on-card">
              <Bdi>{t("nav.then", { next: stepSummary(following, labels, t, lang) })}</Bdi>
            </p>
          )}
        </>
      );
      break;
    }
    case "arrive":
      title = t("nav.step.arrive", { place: placeName(step.target, labels, t) });
      body = (
        <p className="step-line">
          <Bdi>{t("nav.arriveAt", { time: formatClock(step.scheduledArrival, lang) })}</Bdi>
        </p>
      );
      break;
  }

  return (
    <section className={`step-card${cue === "none" ? "" : ` step-card-cue step-card-${cue}`}`} aria-labelledby="step-card-title" data-step-kind={step.kind}>
      {cue !== "none" && (
        <p className="step-cue">
          <span aria-hidden="true">{cue === "next_stop" ? "⬇ " : "⚠ "}</span>
          {t(cue === "next_stop" ? "nav.cueNext" : "nav.cueTwo")}
        </p>
      )}
      <p className="step-of">{t("nav.stepOf", { n, total: steps.length })}</p>
      <h2 id="step-card-title" className="step-title">
        <Bdi>{title}</Bdi>
      </h2>
      {body}
    </section>
  );
}
