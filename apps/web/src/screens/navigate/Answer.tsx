import type { ReactNode } from "react";
import { Icon, LineBadge, VehicleIcon } from "../../components/ds";
import { Bdi } from "../../components/states";
import { useI18n } from "../../i18n/I18nProvider";
import type { Fix } from "../../lib/geolocation";
import { vehicleOf } from "../../lib/lines";
import { formatClock } from "../../lib/time";
import type { CallPosition, NavState } from "../../nav/engine";
import type { NavStep, TripDetail } from "../../nav/steps";
import {
  arrivalCountdown,
  badgeLabel,
  badgeMode,
  isolate,
  isSameStop,
  makesIt,
  placeName,
  relativeText,
  rideHeadsign,
  rideLine,
  rideName,
  ridePlatform,
  stopCodeFor,
  stopsText,
  transferWindowSeconds,
  walkLeft,
  walkLeftText,
  walkTargetName,
  type EndLabels,
} from "./describe";
import { rideRemaining, type StopRow } from "./rideRows";
import { formatDuration } from "../../lib/format";

// The one answer (boards 4 and 5, 11 November 2026): the panel at the bottom of the map
// says what to do now and nothing else. Walking: where to, how far, and whether the bus
// will be caught by the timetable (said honestly when it will not). On board: how many
// stops until the exit, the stops themselves, what comes after, and "ירדתי". Times are
// scheduled ("לפי הלוח"). The full step list stays below, in the expanded sheet.

export interface AnswerActions {
  /** "עליתי": the ride begins. */
  onBoard: () => void;
  /** "ירדתי" / "הגעתי": the next step. */
  onNext: () => void;
  /** "לא הגיע?": opens Bus didn't come. Null when no ride is ahead. */
  onMissed: (() => void) | null;
  /** "סיום" on arrival. */
  onFinish: () => void;
}

interface Props extends AnswerActions {
  steps: readonly NavStep[];
  state: NavState;
  fix: Fix | null;
  clock: number;
  labels: EndLabels;
  trips: Readonly<Record<string, TripDetail>>;
  /** Known call positions (with names) for this ride step, when fetched. */
  callPositions?: readonly CallPosition[];
}

/** The board's check mark (the icon set has none). */
function Check() {
  return (
    <svg className="nav-check-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false">
      <path d="M5 12.5l4.5 4.5L19 7.5" />
    </svg>
  );
}

/** One short line under the answer: an icon, a bold word, and the scheduled time muted. */
function CheckLine({ icon, strong, muted, tone }: { icon: ReactNode; strong: string; muted: string | null; tone?: "late" }) {
  return (
    <p className={`nav-check${tone ? ` nav-check--${tone}` : ""}`}>
      {icon}
      <b>
        <Bdi>{strong}</Bdi>
      </b>
      {muted && (
        <span className="b-mu">
          <Bdi>{muted}</Bdi>
        </span>
      )}
    </p>
  );
}

function Actions({ children }: { children: ReactNode }) {
  return <div className="b-actions nav-actions">{children}</div>;
}

function MissedLink({ onMissed }: { onMissed: (() => void) | null }) {
  const { t } = useI18n();
  if (!onMissed) return null;
  return (
    <button type="button" className="b-link nav-missed-link" onClick={onMissed}>
      {t("nav.answer.missed")}
    </button>
  );
}

function Primary({ onClick, children, name }: { onClick: () => void; children: string; name: string }) {
  return (
    <button type="button" className={`b-btn nav-primary nav-primary--${name}`} onClick={onClick}>
      {children}
    </button>
  );
}

/** Walking to a ride's stop, waiting at it, or changing at the same stop: board 4. */
function ToStop({ step, ride, steps, state, fix, clock, labels, onBoard, onMissed }: Props & { step: NavStep; ride: NavStep }) {
  const { t, lang } = useI18n();
  const departure = formatClock(ride.scheduledDeparture, lang);
  const schedule = t("nav.answer.bySchedule", { time: departure });
  const code = stopCodeFor(ride.from!, ride);
  const codeText = code ? t("nav.stopCode", { code }) : null;
  const vehicle = `${rideName(ride, t)}${rideHeadsign(ride) ? ` ${t("nav.ride.headsign", { headsign: rideHeadsign(ride)! })}` : ""}`;
  const relative = relativeText(ride.scheduledDeparture, clock, t, lang, "departure");
  const sameStop = step.kind === "transfer_walk" && isSameStop(step);
  const waiting = step.kind === "ride" || sameStop || state.phase === "waiting";

  let kicker: string;
  let sub: string;
  let check: ReactNode;
  if (waiting) {
    const window = sameStop ? transferWindowSeconds(steps, step.index) : null;
    kicker = sameStop ? t("nav.step.transferSameStop") : t("nav.answer.waitAt");
    sub = [vehicle, codeText, window === null ? null : t("nav.transferWindow", { duration: formatDuration(window, lang) })].filter(Boolean).join(" · ");
    check = <CheckLine icon={<VehicleIcon vehicle={vehicleOf(ride.ride?.mode ?? "bus")} className="nav-check-icon" />} strong={relative} muted={schedule} />;
  } else {
    const left = walkLeft(step, fix);
    kicker = t("nav.answer.walkTo");
    sub = [walkLeftText(left, t, lang), codeText].filter(Boolean).join(" · ");
    const ok = makesIt(left.seconds, ride, clock);
    check = ok ? (
      <CheckLine icon={<Check />} strong={t("nav.answer.makeIt")} muted={schedule} />
    ) : (
      <CheckLine icon={<Icon name="alert" size="sm" className="nav-check-icon" />} strong={t("nav.answer.tight")} muted={schedule} tone="late" />
    );
  }
  // At the stop the stop is named as the journey names it; walking to a train, as a station.
  const stop = waiting ? ride.from!.name : walkTargetName(step, ride, labels, t);
  return (
    <>
      <section className="b-answer nav-answer" aria-labelledby="nav-answer-title" data-answer={waiting ? "waiting" : "walking"}>
        <span className="b-mu nav-kicker">{kicker}</span>
        <h1 id="nav-answer-title" className="b-answer__title">
          <Bdi>{stop}</Bdi>
        </h1>
        <span className="nav-sub">
          <Bdi>{sub}</Bdi>
        </span>
        {/* The map tag's line and countdown, for whoever does not see the map. */}
        {!waiting && <span className="visually-hidden">{`${vehicle} · ${t("nav.departs", { time: departure })} · ${relative}`}</span>}
        {check}
      </section>
      <Actions>
        <MissedLink onMissed={onMissed} />
        <Primary name="board" onClick={onBoard}>
          {t("nav.answer.boarded")}
        </Primary>
      </Actions>
    </>
  );
}

function StopRowView({ row }: { row: StopRow }) {
  const { t, lang } = useI18n();
  const time = row.time ? formatClock(row.time, lang) : "";
  const dot = row.kind === "here" ? "b-dot b-dot--here" : row.kind === "exit" ? "b-dot b-dot--end" : row.kind === "between" ? "nav-dot-small" : "b-dot";
  return (
    <li className={`b-sr nav-sr nav-sr--${row.kind}${row.kind === "exit" ? " b-sr--exit" : ""}`}>
      <span className="nav-sr-time">{time && <bdi className="num">{time}</bdi>}</span>
      <span className="nav-sr-mark" aria-hidden="true">
        <span className={dot} />
      </span>
      <span className="nav-sr-name">
        {row.kind === "here" && row.name && <span className="visually-hidden">{`${t("nav.answer.here")}: `}</span>}
        {row.kind === "between" ? (
          <span className="b-mu">
            <Bdi>{stopsText(row.count ?? 0, t)}</Bdi>
          </span>
        ) : row.name ? (
          <bdi>{row.name}</bdi>
        ) : (
          <span className="b-mu">{t("nav.answer.here")}</span>
        )}
        {row.kind === "exit" && <span className="b-mu nav-sr-exit">{t("nav.answer.exitMark")}</span>}
      </span>
    </li>
  );
}

/** "אחר כך": the next ride (line, where it goes, platform when known, departure), or the walk. */
function After({ steps, step, labels }: { steps: readonly NavStep[]; step: NavStep; labels: EndLabels }) {
  const { t, lang } = useI18n();
  const following = steps[step.index + 1];
  if (!following) return null;
  const ride = following.kind === "ride" ? following : steps[following.index + 1]?.kind === "ride" && following.kind === "transfer_walk" ? steps[following.index + 1]! : null;
  let body: ReactNode;
  if (ride) {
    const platform = ridePlatform(ride);
    const where = rideHeadsign(ride) ?? ride.target.name;
    body = (
      <>
        <LineBadge mode={badgeMode(ride)} label={badgeLabel(ride, t)} line={rideLine(ride)} />
        <span className="nav-after-text">
          <Bdi>{[where, platform ? t("nav.platform", { platform }) : null].filter(Boolean).join(" · ")}</Bdi>
        </span>
        <bdi className="num nav-after-time">{formatClock(ride.scheduledDeparture, lang)}</bdi>
      </>
    );
  } else {
    const last = steps[steps.length - 1]!;
    body = (
      <>
        <Icon name="walk" size="sm" />
        <span className="nav-after-text">
          <Bdi>{t("nav.answer.afterWalk", { place: isolate(placeName(last.target, labels, t), lang) })}</Bdi>
        </span>
        <bdi className="num nav-after-time">{formatClock(last.scheduledArrival, lang)}</bdi>
      </>
    );
  }
  return (
    <p className="nav-after">
      <span className="b-mu">{t("nav.answer.after")}</span>
      {body}
    </p>
  );
}

/** On board: board 5. */
function OnBoard({ step, steps, state, clock, labels, trips, callPositions, onNext }: Props & { step: NavStep }) {
  const { t, lang } = useI18n();
  const remaining = rideRemaining(step, state, step.ride ? trips[step.ride.tripRef] : undefined, callPositions, clock);
  const cue = state.stepIndex === step.index ? state.cue : "none";
  const headsign = rideHeadsign(step);
  let figure: ReactNode;
  if (remaining.left !== null) {
    figure = <Bdi>{stopsText(remaining.left, t)}</Bdi>;
  } else {
    figure = <Bdi>{arrivalCountdown(step.scheduledArrival, clock, t, lang)}</Bdi>;
  }
  const byTimetable = !remaining.measured;
  return (
    <>
      <section className={`b-answer nav-answer nav-answer--ride${cue === "none" ? "" : " nav-answer--cue"}`} aria-labelledby="nav-answer-title" data-answer="riding" data-cue={cue}>
        <div className="nav-ride-line">
          <LineBadge mode={badgeMode(step)} label={badgeLabel(step, t)} line={rideLine(step)} />
          <Bdi>{headsign ?? t("nav.exit", { stop: step.target.name })}</Bdi>
        </div>
        <h1 id="nav-answer-title" className="nav-ride-title">
          <span className={`nav-kicker${cue === "none" ? " b-mu" : " nav-kicker--cue"}`}>
            {cue !== "none" && <Icon name={cue === "next_stop" ? "stop" : "alert"} size="sm" />}
            {cue === "none" ? t("nav.answer.exitIn") : t(cue === "next_stop" ? "nav.cueNext" : "nav.cueTwo")}
          </span>{" "}
          <span className="b-answer__figure">{figure}</span>
        </h1>
        {byTimetable && <span className="b-mu nav-by-timetable">{t("nav.answer.byTimetable")}</span>}
        <ol className="nav-stops" aria-label={t("nav.answer.stops")} data-mode={badgeMode(step)}>
          {remaining.rows.map((row) => (
            <StopRowView key={row.key} row={row} />
          ))}
        </ol>
        <After steps={steps} step={step} labels={labels} />
      </section>
      <Actions>
        <Primary name="alight" onClick={onNext}>
          {t("nav.answer.alighted")}
        </Primary>
      </Actions>
    </>
  );
}

/** Walking to the destination. */
function ToDestination({ step, fix, labels, onNext }: Props & { step: NavStep }) {
  const { t, lang } = useI18n();
  const left = walkLeft(step, fix);
  return (
    <>
      <section className="b-answer nav-answer" aria-labelledby="nav-answer-title" data-answer="destination">
        <span className="b-mu nav-kicker">{t("nav.answer.walkTo")}</span>
        <h1 id="nav-answer-title" className="b-answer__title">
          <Bdi>{placeName(step.target, labels, t)}</Bdi>
        </h1>
        <span className="nav-sub">
          <Bdi>{walkLeftText(left, t, lang)}</Bdi>
        </span>
        <CheckLine icon={<Icon name="pin" size="sm" className="nav-check-icon" />} strong={t("nav.answer.arriving", { time: formatClock(step.scheduledArrival, lang) })} muted={t("nav.answer.byTimetable")} />
      </section>
      <Actions>
        <Primary name="arrived" onClick={onNext}>
          {t("nav.answer.there")}
        </Primary>
      </Actions>
    </>
  );
}

function Arrived({ step, labels, onFinish }: Props & { step: NavStep }) {
  const { t, lang } = useI18n();
  return (
    <>
      <section className="b-answer nav-answer" aria-labelledby="nav-answer-title" data-answer="arrived">
        <span className="b-mu nav-kicker">{t("nav.answer.arrived")}</span>
        <h1 id="nav-answer-title" className="b-answer__title">
          <Bdi>{placeName(step.target, labels, t)}</Bdi>
        </h1>
        <span className="nav-sub">
          <Bdi>{t("nav.arrival", { time: formatClock(step.scheduledArrival, lang) })}</Bdi>
        </span>
      </section>
      <Actions>
        <Primary name="finish" onClick={onFinish}>
          {t("nav.finish")}
        </Primary>
      </Actions>
    </>
  );
}

export function Answer(props: Props) {
  const step = props.steps[props.state.stepIndex]!;
  switch (step.kind) {
    case "walk_to_stop":
    case "transfer_walk": {
      const ride = props.steps[step.index + 1];
      if (ride?.kind === "ride" && ride.from) return <ToStop {...props} step={step} ride={ride} />;
      return <ToDestination {...props} step={step} />;
    }
    case "ride":
      if (props.state.phase === "waiting" && step.from) return <ToStop {...props} step={step} ride={step} />;
      return <OnBoard {...props} step={step} />;
    case "walk_to_destination":
      return <ToDestination {...props} step={step} />;
    case "arrive":
      return <Arrived {...props} step={step} />;
  }
}
