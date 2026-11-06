import type { ReactNode } from "react";
import { Icon, LineBadge, type IconName } from "../../components/ds";
import { Bdi } from "../../components/states";
import { useI18n } from "../../i18n/I18nProvider";
import { formatDistance, formatDuration } from "../../lib/format";
import type { Fix } from "../../lib/geolocation";
import { formatClock, type Lang } from "../../lib/time";
import type { NavState } from "../../nav/engine";
import { haversineMeters } from "../../nav/geo";
import type { NavStep } from "../../nav/steps";
import {
  badgeLabel,
  badgeMode,
  countdownMinutes,
  isolate,
  isRail,
  isSameStop,
  placeName,
  relativeText,
  rideHeadsign,
  rideName,
  ridePlatform,
  rideStops,
  rideStopsText,
  stopCodeFor,
  stopsText,
  thenText,
  trainName,
  transferWindowSeconds,
  walkTargetName,
  type EndLabels,
} from "./describe";

// The step card (design system: NavStep, hero variant; Navigate — C05, "Step kind" table):
// pinned, high contrast (the hero is light in the dark theme, for sunlight), the one thing
// to do now. Kicker, title and sub-line; a countdown to the time that matters; three facts;
// what comes next as a note. Times are scheduled (said once in the header). A platform is
// a fact only for rail, and shows "—" until the API gives one (API-C2): never a guess.

interface Props {
  steps: readonly NavStep[];
  state: NavState;
  fix: Fix | null;
  clock: number;
  labels: EndLabels;
  /** End trip (small, in the card header, away from the primary action); none on arrive. */
  onEnd: (() => void) | null;
}

type T = ReturnType<typeof useI18n>["t"];

interface Fact {
  key: string;
  label: string;
  value: ReactNode;
  /** A name (Hebrew in an English card too): the cell takes its direction, so a cut name keeps its start. */
  name?: boolean;
}

const hasLetters = (value: string) => /\p{L}/u.test(value);

/** A value the API does not give yet: a dash on screen, "not known" to a screen reader. */
function Unknown() {
  const { t } = useI18n();
  return (
    <>
      <span aria-hidden="true">—</span>
      <span className="visually-hidden">{t("nav.unknown")}</span>
    </>
  );
}

/** "Bus 249" with its headsign in a lighter run, so a long headsign does not shout. */
function RideTitle({ ride }: { ride: NavStep }) {
  const { t } = useI18n();
  const headsign = rideHeadsign(ride);
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

/** The vehicle's fact: a bus or light-rail line as its badge; a train by where it goes or its number. */
function vehicleFact(ride: NavStep, t: T): Fact {
  if (isRail(ride)) {
    const name = trainName(ride);
    if (name && hasLetters(name)) return { key: "train", label: t("nav.fact.train"), value: name, name: true };
    return { key: "train", label: t("nav.fact.train"), value: name ? <Bdi>{name}</Bdi> : <Unknown /> };
  }
  return { key: "line", label: t("nav.fact.line"), value: <LineBadge mode={badgeMode(ride)} label={badgeLabel(ride, t)} /> };
}

/** Before boarding R. Bus: line · departs · get off. Train: train · platform · departs. */
function boardingFacts(ride: NavStep, t: T, lang: Lang): Fact[] {
  const departs = <Bdi>{formatClock(ride.scheduledDeparture, lang)}</Bdi>;
  if (isRail(ride)) {
    const platform = ridePlatform(ride);
    return [
      vehicleFact(ride, t),
      { key: "platform", label: t("nav.fact.platform"), value: platform ? <Bdi>{platform}</Bdi> : <Unknown /> },
      { key: "departs", label: t("nav.fact.departsTrain"), value: departs },
    ];
  }
  return [
    vehicleFact(ride, t),
    { key: "departs", label: t("nav.fact.departs"), value: departs },
    { key: "exit", label: t("nav.fact.exit"), value: ride.target.name, name: true },
  ];
}

/** On board (the title names the line): when to get off, and the stops (to the exit, or left once measured). */
function rideFacts(step: NavStep, state: NavState, t: T, lang: Lang): Fact[] {
  const facts: Fact[] = [{ key: "exit", label: t("nav.fact.exit"), value: <Bdi>{formatClock(step.scheduledArrival, lang)}</Bdi> }];
  const stops = rideStops(step, state);
  if (stops) {
    facts.push({
      key: "stops",
      label: t(stops.measured ? "nav.fact.stopsLeft" : "nav.fact.stopsToExit"),
      value: <Bdi>{stopsText(stops.count, t)}</Bdi>,
    });
  }
  return facts;
}

function Facts({ facts, named }: { facts: Fact[]; named: boolean }) {
  if (facts.length === 0) return null;
  return (
    <dl className={`ot-nav__facts step-facts${named ? " step-facts-named" : ""}`}>
      {facts.map((fact) => (
        <div key={fact.key} className={`ot-fact step-fact-${fact.key}`}>
          <dt className="ot-fact__k">{fact.label}</dt>
          <dd className="ot-fact__v" dir={fact.name ? "auto" : undefined}>
            {fact.value}
          </dd>
        </div>
      ))}
    </dl>
  );
}

/**
 * The countdown figure (hero-accent): minutes to the time that matters, from one minute
 * to an hour ahead; otherwise its words ("leaving now", "4 min ago", a day). A screen
 * reader hears what the figure means: "Departs 08:38 · in 8 min".
 */
function Countdown({ at, clock, kind, lead }: { at: string; clock: number; kind: "departure" | "arrival"; lead: string }) {
  const { t, lang } = useI18n();
  const relative = relativeText(at, clock, t, lang, kind);
  const minutes = countdownMinutes(at, clock);
  return (
    <p className="ot-nav__count step-count">
      <span className="visually-hidden">{`${lead} · ${relative}`}</span>
      <span aria-hidden="true">
        {minutes === null ? (
          <b className="step-count-words">
            <bdi>{relative}</bdi>
          </b>
        ) : (
          <>
            <b>
              <bdi className="num">{minutes}</bdi>
            </b>
            <span>{t("nav.count.min")}</span>
          </>
        )}
      </span>
    </p>
  );
}

function Note({ icon, className, children }: { icon: IconName; className?: string; children: string }) {
  return (
    <p className={`ot-nav__note${className ? ` ${className}` : ""}`}>
      <Icon name={icon} size="sm" />
      <span>
        <Bdi>{children}</Bdi>
      </span>
    </p>
  );
}

function walkLine(step: NavStep, fix: Fix | null, extra: Array<string | null>, t: T, lang: Lang): string {
  let first: string;
  const left = fix && Number.isFinite(step.target.latitude) ? formatDistance(haversineMeters(fix, step.target), lang) : null;
  const distance = formatDistance(step.distanceMeters, lang);
  const duration = formatDuration(step.durationSeconds, lang);
  if (left) first = t("nav.distanceLeft", { distance: left });
  else if (distance) first = t("nav.walk", { distance, duration });
  else first = t("nav.walkTimeOnly", { duration });
  return [first, ...extra.filter((part): part is string => !!part)].join(" · ");
}

/** The vehicle to catch after a walk: line and direction (rail: where to get off). */
function vehicleLine(ride: NavStep, t: T): string {
  const headsign = rideHeadsign(ride);
  const name = rideName(ride, t);
  // No headsign (trains: a train number): say where to get off, which gives the direction.
  return headsign ? `${name} ${t("nav.ride.headsign", { headsign })}` : `${name} · ${t("nav.exit", { stop: ride.target.name })}`;
}

interface Content {
  title: ReactNode;
  sub: ReactNode;
  count: ReactNode;
  facts: Fact[];
  /** The last fact is a stop name: the other two take their own width, the name the rest. */
  named: boolean;
  notes: ReactNode;
}

export function StepCard({ steps, state, fix, clock, labels, onEnd }: Props) {
  const { t, lang } = useI18n();
  const step = steps[state.stepIndex]!;
  const following = steps[step.index + 1];
  const cue = step.kind === "ride" ? state.cue : "none";
  const n = step.index + 1;

  let content: Content;
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
      let title: string;
      let sub: string;
      if (step.kind === "transfer_walk" && isSameStop(step)) {
        title = t("nav.step.transferSameStop");
        sub = [isolate(stop, lang), codeText, windowText].filter(Boolean).join(" · ");
      } else {
        title = waiting ? t("nav.step.waitAt", { stop }) : t(step.kind === "walk_to_stop" ? "nav.step.walkToStop" : "nav.step.transferWalk", { stop });
        sub = waiting ? [codeText, windowText].filter(Boolean).join(" · ") || stop : walkLine(step, fix, [codeText, windowText], t, lang);
      }
      content = {
        title,
        sub: <Bdi>{sub}</Bdi>,
        count: ride && (
          <Countdown at={ride.scheduledDeparture} clock={clock} kind="departure" lead={t("nav.departs", { time: formatClock(ride.scheduledDeparture, lang) })} />
        ),
        facts: ride ? boardingFacts(ride, t, lang) : [],
        named: !!ride && !isRail(ride),
        notes: ride && (
          <Note icon={badgeMode(ride) === "rail" ? "train" : "bus"} className="step-vehicle">
            {vehicleLine(ride, t)}
          </Note>
        ),
      };
      break;
    }
    case "walk_to_destination":
      content = {
        title: t("nav.step.walkToDestination", { place: placeName(step.target, labels, t) }),
        sub: <Bdi>{walkLine(step, fix, [t("nav.arrival", { time: formatClock(step.scheduledArrival, lang) })], t, lang)}</Bdi>,
        count: (
          <Countdown at={step.scheduledArrival} clock={clock} kind="arrival" lead={t("nav.arrival", { time: formatClock(step.scheduledArrival, lang) })} />
        ),
        facts: [],
        named: false,
        notes: null,
      };
      break;
    case "ride": {
      const then = thenText(steps, step.index, labels, t, lang);
      const thenNote = then && (
        <Note icon="info" className="step-then">
          {then}
        </Note>
      );
      // During a cue the passenger is on board: the cue is the title and the exit follows.
      const title =
        cue === "none" ? (
          <RideTitle ride={step} />
        ) : (
          <>
            <Icon name={cue === "next_stop" ? "stop" : "alert"} size="lg" className="step-cue-icon" />
            {t(cue === "next_stop" ? "nav.cueNext" : "nav.cueTwo")}
          </>
        );
      if (state.phase === "waiting") {
        // At the boarding stop: where to board and when it leaves come first.
        const code = step.from ? stopCodeFor(step.from, step) : null;
        const stops = rideStopsText(step, state, t);
        const exitTime = formatClock(step.scheduledArrival, lang);
        // A bus's facts name the exit stop already; a train's do not (its platform is there).
        const exit = isRail(step) ? t("nav.exitAt", { stop: isolate(step.target.name, lang), time: exitTime }) : `${t("nav.fact.exit")} ${exitTime}`;
        content = {
          title,
          sub: step.from && <Bdi>{[t("nav.board", { stop: isolate(step.from.name, lang) }), code ? t("nav.stopCode", { code }) : null].filter(Boolean).join(" · ")}</Bdi>,
          count: <Countdown at={step.scheduledDeparture} clock={clock} kind="departure" lead={t("nav.departs", { time: formatClock(step.scheduledDeparture, lang) })} />,
          facts: boardingFacts(step, t, lang),
          named: !isRail(step),
          notes: (
            <>
              <Note icon="stop" className="step-exit">
                {[exit, stops].filter(Boolean).join(" · ")}
              </Note>
              {thenNote}
            </>
          ),
        };
      } else {
        const time = formatClock(step.scheduledArrival, lang);
        content = {
          title,
          sub: (
            <span className="step-lead">
              <Bdi>{t("nav.exit", { stop: step.target.name })}</Bdi>
            </span>
          ),
          count: <Countdown at={step.scheduledArrival} clock={clock} kind="arrival" lead={`${t("nav.fact.exit")} ${time}`} />,
          facts: rideFacts(step, state, t, lang),
          named: false,
          notes: thenNote,
        };
      }
      break;
    }
    case "arrive":
      content = {
        title: t("nav.step.arrive", { place: placeName(step.target, labels, t) }),
        sub: <Bdi>{t("nav.arrival", { time: formatClock(step.scheduledArrival, lang) })}</Bdi>,
        count: null,
        facts: [],
        named: false,
        notes: null,
      };
      break;
  }

  return (
    <section
      className={`ot-nav ot-nav--hero step-card${cue === "none" ? "" : ` step-card-cue step-card-${cue}`}`}
      aria-labelledby="step-card-title"
      data-step-kind={step.kind}
    >
      <div className="ot-nav__kicker step-head">
        <span className="step-kicker">{t("nav.kicker")}</span>
        <span className="step-of">
          {t("nav.stepOf", { n, total: steps.length })} · {t("nav.scheduled")}
        </span>
        {onEnd && (
          <button type="button" className="step-end" onClick={onEnd}>
            {t("nav.end")}
          </button>
        )}
      </div>
      {/* The countdown floats at the inline end (first, so the title and sub-line flow
          around it and take the full width below it rather than wrap in a narrow column). */}
      <div className="ot-nav__main step-main">
        {content.count}
        <div className="ot-nav__what">
          <h2 id="step-card-title" className={`ot-nav__title step-title${cue === "none" ? "" : " step-cue"}`}>
            {content.title}
          </h2>
          {content.sub && <p className="ot-nav__sub step-sub">{content.sub}</p>}
        </div>
      </div>
      <Facts facts={content.facts} named={content.named} />
      {content.notes}
    </section>
  );
}
