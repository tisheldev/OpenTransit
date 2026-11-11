import { Fragment, type ReactNode } from "react";
import type { Journey } from "../../api/types";
import { LineBadge } from "../../components/ds";
import { useI18n } from "../../i18n/I18nProvider";
import { formatDistance, formatDuration } from "../../lib/format";
import { formatClock } from "../../lib/time";
import { isRail } from "../../plan/chartLayout";
import { isWalkOnly } from "../../plan/rank";
import { daysBetween, firstWalkSeconds, israelDate, optionSpeech, shortBadgeLabel } from "./labels";
import { Duration, LegChevron, NextDay, Nums, TimeArrow } from "./text";

// One option (board Choose, `b-op`; also the wide panel's rows): departure ← arrival in
// the big figure with how long until it leaves (strong on the chosen row, muted on the
// others), then the walk to the first stop, the line badges between small chevrons, and
// the total duration at the inline end. The whole row is one button read as one sentence.

export function OptionRow({
  journey,
  index,
  chosen,
  until,
  dayOf,
  onChoose,
}: {
  journey: Journey;
  index: number;
  chosen: boolean;
  /** "בעוד 4 דק׳", the day it leaves, or null once it has left. */
  until: string | null;
  /** The day of an instant when it is not the day asked, else null. */
  dayOf: (instant: string) => string | null;
  onChoose: (index: number) => void;
}) {
  const { t, lang } = useI18n();
  const { scheduledDeparture: leave, scheduledArrival: arrive } = journey.timing;
  const overnight = daysBetween(israelDate(leave), israelDate(arrive));
  const walkOnly = isWalkOnly(journey);
  const walk = firstWalkSeconds(journey);
  const rides = journey.legs.filter((leg) => leg.kind === "transit");
  const distance = walkOnly ? formatDistance(journey.walkingDistanceMeters ?? null, lang) : null;

  const parts: ReactNode[] = [];
  if (walkOnly) {
    parts.push(
      <span key="walk">
        {t("compare.walkOnly")}
        {distance && (
          <>
            {" · "}
            <Nums text={distance} />
          </>
        )}
      </span>,
    );
  } else if (walk >= 60) {
    parts.push(
      <span key="walk">
        <Nums text={t("compare.walkFirst", { duration: formatDuration(walk, lang) })} />
      </span>,
    );
  }
  rides.forEach((leg, i) => {
    parts.push(
      <LineBadge
        key={`ride-${i}`}
        mode={isRail(leg) ? "rail" : "bus"}
        label={shortBadgeLabel(leg, t)}
        line={{ mode: leg.mode, operatorId: leg.transit?.operatorId, operatorName: leg.transit?.operatorName }}
      />,
    );
  });

  return (
    <button
      type="button"
      className={`b-op${chosen ? " b-op--on" : ""}`}
      aria-pressed={chosen}
      onClick={() => onChoose(index)}
    >
      {/* Its name is this sentence; the drawn rows below say the same and are hidden from it. */}
      <span className="visually-hidden">{optionSpeech(journey, index, t, lang, { dayOf, until })}</span>
      <span className="b-op__l1" aria-hidden="true">
        <span className="b-op__time">
          <bdi className="num">{formatClock(leave, lang)}</bdi>
          <TimeArrow />
          <bdi className="num">{formatClock(arrive, lang)}</bdi>
          {overnight > 0 && <NextDay days={overnight} />}
        </span>
        {until && (chosen ? <span className="b-tag b-tag--strong"><Nums text={until} /></span> : <span className="b-mu"><Nums text={until} /></span>)}
      </span>
      <span className="b-op__l2" aria-hidden="true">
        {parts.map((part, i) => (
          <Fragment key={i}>
            {i > 0 && <LegChevron />}
            {part}
          </Fragment>
        ))}
        <span className="b-op__dur">
          <Duration seconds={journey.durationSeconds} />
        </span>
      </span>
    </button>
  );
}

/** Loading: the space for three option rows is reserved so nothing jumps. */
export function OptionsSkeleton() {
  const { t } = useI18n();
  return (
    <div className="options-skeleton" role="status" aria-live="polite" aria-busy="true">
      <span className="visually-hidden">{t("compare.loading")}</span>
      <div className="compare-options" aria-hidden="true">
        {[0, 1, 2].map((index) => (
          <div key={index} className="b-op option-placeholder">
            <span className="b-op__l1">
              <span className="ot-skel compare-skel-times" />
            </span>
            <span className="b-op__l2">
              <span className="ot-skel compare-skel-legs" style={{ inlineSize: `${60 - index * 10}%` }} />
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
