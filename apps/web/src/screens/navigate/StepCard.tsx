import type { ReactNode } from "react";
import { Bdi } from "../../components/states";
import { useI18n } from "../../i18n/I18nProvider";
import { formatDistance, formatDuration } from "../../lib/format";
import type { Fix } from "../../lib/geolocation";
import { formatClock, type Lang } from "../../lib/time";
import type { NavState } from "../../nav/engine";
import { haversineMeters } from "../../nav/geo";
import type { NavStep } from "../../nav/steps";
import {
  isSameStop,
  placeName,
  relativeText,
  rideHeadsign,
  rideName,
  ridePlatform,
  rideStopsText,
  stopCodeFor,
  thenText,
  transferWindowSeconds,
  walkTargetName,
  type EndLabels,
} from "./describe";

// The step card (design: Navigate — C05, "Step kind" table): pinned, high contrast, the
// one thing to do now and the time that matters for it. Times are scheduled (said once in
// the header); a platform is shown only for rail and only when the API gives one.

interface Props {
  steps: readonly NavStep[];
  state: NavState;
  fix: Fix | null;
  clock: number;
  labels: EndLabels;
  /** End trip (small, in the card header, away from the primary action); none on arrive. */
  onEnd: (() => void) | null;
}

/** "Bus 249" with its headsign in a lighter run, so a long headsign does not shout. */
function RideTitle({ ride, headsign: show = true }: { ride: NavStep; headsign?: boolean }) {
  const { t } = useI18n();
  const headsign = show ? rideHeadsign(ride) : null;
  return (
    <>
      <Bdi>{rideName(ride, t)}</Bdi>
      {headsign && (
        <>
          {" "}
          <span className="step-toward">
            <Bdi>{t("nav.ride.headsign", { headsign })}</Bdi>
          </span>
        </>
      )}
    </>
  );
}

/** The departure that matters while walking or waiting: time, countdown, platform (rail, known). */
function Departure({ ride, clock }: { ride: NavStep; clock: number }) {
  const { t, lang } = useI18n();
  const platform = ridePlatform(ride);
  return (
    <p className="step-line step-when">
      <Bdi>{t("nav.departs", { time: formatClock(ride.scheduledDeparture, lang) })}</Bdi>
      {" · "}
      <strong className="step-countdown">
        <Bdi>{relativeText(ride.scheduledDeparture, clock, t, lang, "departure")}</Bdi>
      </strong>
      {platform && (
        <>
          {" · "}
          <Bdi>{t("nav.platform", { platform })}</Bdi>
        </>
      )}
    </p>
  );
}

/** The vehicle to catch after a walk: line and direction (rail: where to get off), departure. */
function NextVehicle({ ride, clock }: { ride: NavStep; clock: number }) {
  const { t } = useI18n();
  // No headsign (trains: a train number): say where to get off, which gives the direction.
  const noDirection = !rideHeadsign(ride);
  return (
    <div className="step-vehicle">
      <p className="step-line step-strong">
        <RideTitle ride={ride} />
        {noDirection && (
          <>
            {" · "}
            <Bdi>{t("nav.exit", { stop: ride.target.name })}</Bdi>
          </>
        )}
      </p>
      <Departure ride={ride} clock={clock} />
    </div>
  );
}

function walkLine(step: NavStep, fix: Fix | null, extra: Array<string | null>, t: ReturnType<typeof useI18n>["t"], lang: Lang): string {
  let first: string;
  const left = fix && Number.isFinite(step.target.latitude) ? formatDistance(haversineMeters(fix, step.target), lang) : null;
  const distance = formatDistance(step.distanceMeters, lang);
  const duration = formatDuration(step.durationSeconds, lang);
  if (left) first = t("nav.distanceLeft", { distance: left });
  else if (distance) first = t("nav.walk", { distance, duration });
  else first = t("nav.walkTimeOnly", { duration });
  return [first, ...extra.filter((part): part is string => !!part)].join(" · ");
}

export function StepCard({ steps, state, fix, clock, labels, onEnd }: Props) {
  const { t, lang } = useI18n();
  const step = steps[state.stepIndex]!;
  const following = steps[step.index + 1];
  const cue = step.kind === "ride" ? state.cue : "none";
  const n = step.index + 1;

  let title: ReactNode;
  let body: ReactNode;
  switch (step.kind) {
    case "walk_to_stop":
    case "transfer_walk": {
      const ride = following?.kind === "ride" ? following : undefined;
      const code = stopCodeFor(step.target, ride);
      const window = transferWindowSeconds(steps, step.index);
      const windowText = window === null ? null : t("nav.transferWindow", { duration: formatDuration(window, lang) });
      const codeText = code ? t("nav.stopCode", { code }) : null;
      const stop = walkTargetName(step, ride, labels, t);
      const waiting = state.phase === "waiting";
      if (step.kind === "transfer_walk" && isSameStop(step)) {
        title = t("nav.step.transferSameStop");
        body = (
          <p className="step-line">
            <Bdi>{[stop, codeText, windowText].filter(Boolean).join(" · ")}</Bdi>
          </p>
        );
      } else {
        title = waiting ? t("nav.step.waitAt", { stop }) : t(step.kind === "walk_to_stop" ? "nav.step.walkToStop" : "nav.step.transferWalk", { stop });
        body = (
          <p className="step-line">
            <Bdi>{waiting ? [codeText, windowText].filter(Boolean).join(" · ") || stop : walkLine(step, fix, [codeText, windowText], t, lang)}</Bdi>
          </p>
        );
      }
      body = (
        <>
          {body}
          {ride && <NextVehicle ride={ride} clock={clock} />}
        </>
      );
      break;
    }
    case "walk_to_destination":
      title = t("nav.step.walkToDestination", { place: placeName(step.target, labels, t) });
      body = (
        <>
          <p className="step-line">
            <Bdi>{walkLine(step, fix, [], t, lang)}</Bdi>
          </p>
          <p className="step-line step-when">
            <Bdi>{t("nav.arrival", { time: formatClock(step.scheduledArrival, lang) })}</Bdi>
            {" · "}
            <strong className="step-countdown">
              <Bdi>{relativeText(step.scheduledArrival, clock, t, lang, "arrival")}</Bdi>
            </strong>
          </p>
        </>
      );
      break;
    case "ride": {
      // During a cue the passenger is on board: the direction gives way to the exit.
      title = <RideTitle ride={step} headsign={cue === "none"} />;
      const stops = rideStopsText(step, state, t);
      const then = thenText(steps, step.index, labels, t, lang);
      const code = step.from ? stopCodeFor(step.from, step) : null;
      const exit = (
        <>
          <p className="step-line step-lead">
            <Bdi>{t("nav.exit", { stop: step.target.name })}</Bdi>
          </p>
          <p className="step-line step-when">
            <Bdi>{formatClock(step.scheduledArrival, lang)}</Bdi>
            {" · "}
            <strong className="step-countdown">
              <Bdi>{relativeText(step.scheduledArrival, clock, t, lang, "arrival")}</Bdi>
            </strong>
            {stops && (
              <>
                {" · "}
                <Bdi>{stops}</Bdi>
              </>
            )}
          </p>
        </>
      );
      body =
        state.phase === "waiting" ? (
          // At the boarding stop: where to board and when it leaves come first.
          <>
            {step.from && (
              <p className="step-line">
                <Bdi>{[t("nav.board", { stop: step.from.name }), code ? t("nav.stopCode", { code }) : null].filter(Boolean).join(" · ")}</Bdi>
              </p>
            )}
            <Departure ride={step} clock={clock} />
            <p className="step-line">
              <Bdi>{[t("nav.exitAt", { stop: step.target.name, time: formatClock(step.scheduledArrival, lang) }), stops].filter(Boolean).join(" · ")}</Bdi>
            </p>
          </>
        ) : (
          exit
        );
      body = (
        <>
          {body}
          {then && (
            <p className="step-line step-then">
              <Bdi>{then}</Bdi>
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
          <Bdi>{t("nav.arrival", { time: formatClock(step.scheduledArrival, lang) })}</Bdi>
        </p>
      );
      break;
  }

  return (
    <section
      className={`step-card${cue === "none" ? "" : ` step-card-cue step-card-${cue}`}`}
      aria-labelledby="step-card-title"
      data-step-kind={step.kind}
    >
      <div className="step-head">
        <p className="step-of">
          {t("nav.stepOf", { n, total: steps.length })} · {t("nav.scheduled")}
        </p>
        {onEnd && (
          <button type="button" className="step-end" onClick={onEnd}>
            {t("nav.end")}
          </button>
        )}
      </div>
      {cue !== "none" && (
        <p className="step-cue">
          <span aria-hidden="true">{cue === "next_stop" ? "⬇ " : "⚠ "}</span>
          {t(cue === "next_stop" ? "nav.cueNext" : "nav.cueTwo")}
        </p>
      )}
      <h2 id="step-card-title" className="step-title">
        {title}
      </h2>
      {body}
    </section>
  );
}
