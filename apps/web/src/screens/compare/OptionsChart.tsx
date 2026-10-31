import { useMemo } from "react";
import type { Journey } from "../../api/types";
import { Bdi } from "../../components/states";
import { useI18n } from "../../i18n/I18nProvider";
import { formatDistance, formatDuration } from "../../lib/format";
import { formatClock } from "../../lib/time";
import { layoutChart, RESERVED_ROWS, type ChartSegment } from "../../plan/chartLayout";
import { isWalkOnly, rankLabels } from "../../plan/rank";
import { daysBetween, formatShortDay, israelDate, optionSpeech, rankKey, transfersText } from "./labels";

// The options (design: Compare, "Chart"; CU04, CU14; user's variant B). One row per
// journey in the API's order. Each row leads with its departure and arrival times, then
// a bar on the shared time axis (earliest on the inline start), then duration, transfers
// and walking. Rank labels are text pills. Selecting a row never sends a request. The
// list is read as one sentence per option; the drawing is hidden from it.

/** "+1" after a time on the next day (its own left-to-right run, so the sign stays in front). */
export function NextDay({ days }: { days: number }) {
  return (
    <sup className="option-plus">
      <bdi dir="ltr">{`+${days}`}</bdi>
    </sup>
  );
}

/** A train has no line number: its bar says "רכבת" (an emoji is unreadable on the dark bar). */
function Segment({ segment, trainLabel }: { segment: ChartSegment; trainLabel: string }) {
  const label = segment.rail ? trainLabel : segment.label;
  return (
    <span
      className={`bar-seg bar-seg-${segment.kind}${segment.mode ? ` bar-seg-${segment.mode}` : ""}`}
      style={{ insetInlineStart: `${segment.start * 100}%`, inlineSize: `${Math.max(segment.width * 100, 0.6)}%` }}
    >
      {segment.showLabel && label && <Bdi>{label}</Bdi>}
    </span>
  );
}

export function OptionsChart({
  journeys,
  selected,
  onSelect,
  askedDate,
}: {
  journeys: readonly Journey[];
  selected: number;
  onSelect: (index: number) => void;
  /** The Israel date the request asked about (`YYYY-MM-DD`): other days are named. */
  askedDate: string;
}) {
  const { t, lang } = useI18n();
  const layout = useMemo(() => layoutChart(journeys, lang), [journeys, lang]);
  const ranks = useMemo(() => rankLabels(journeys), [journeys]);
  if (!layout) return null;
  // A time on another day than the one asked carries its day (e.g. Friday night → Saturday).
  const dayOf = (instant: string): string | null => (israelDate(instant) === askedDate ? null : formatShortDay(instant, lang));
  return (
    <ol className="options" aria-label={t("compare.options")}>
      {layout.rows.map((row) => {
        const journey = journeys[row.index]!;
        const rank = ranks[row.index] ?? null;
        const isSelected = row.index === selected;
        const walkOnly = isWalkOnly(journey);
        const departureDay = israelDate(row.departure);
        const otherDay = departureDay !== askedDate;
        const overnight = daysBetween(departureDay, israelDate(row.arrival));
        const meta = [formatDuration(row.durationSeconds, lang)];
        if (walkOnly) {
          const distance = formatDistance(journey.walkingDistanceMeters ?? null, lang);
          if (distance) meta.push(distance);
        } else {
          meta.push(transfersText(journey.transfers, t));
          if (journey.walkingSeconds >= 60) meta.push(t("compare.walking", { duration: formatDuration(journey.walkingSeconds, lang) }));
        }
        return (
          <li key={`${row.index}-${row.journeyId}`}>
            <button type="button" className="option" aria-pressed={isSelected} onClick={() => onSelect(row.index)}>
              <span className="visually-hidden">{optionSpeech(journey, row.index, rank, t, lang, dayOf)}</span>
              <span className="option-head" aria-hidden="true">
                <span className="option-times">
                  {otherDay && <span className="option-day">{dayOf(row.departure)}</span>}
                  <Bdi>{formatClock(row.departure, lang)}</Bdi>
                  <span className="option-dash">–</span>
                  <Bdi>{formatClock(row.arrival, lang)}</Bdi>
                  {overnight > 0 && <NextDay days={overnight} />}
                </span>
                {rank && <span className="pill">{t(rankKey[rank])}</span>}
                {walkOnly && <span className="pill pill-quiet">{t("compare.walkOnly")}</span>}
              </span>
              <span className="option-bar" aria-hidden="true">
                {row.segments.map((segment, index) => (
                  <Segment key={index} segment={segment} trainLabel={t("compare.train")} />
                ))}
              </span>
              <span className="option-meta" aria-hidden="true">
                {meta.map((part, index) => (
                  <span key={index}>
                    {index > 0 && " · "}
                    <Bdi>{part}</Bdi>
                  </span>
                ))}
              </span>
            </button>
          </li>
        );
      })}
    </ol>
  );
}

/** Loading: the options' space for three rows is reserved so nothing jumps (design). */
export function OptionsSkeleton() {
  const { t } = useI18n();
  return (
    <div className="options-skeleton" role="status" aria-live="polite" aria-busy="true">
      <span className="visually-hidden">{t("compare.loading")}</span>
      <ol className="options" aria-hidden="true">
        {Array.from({ length: RESERVED_ROWS }, (_, index) => (
          <li key={index} className="option option-placeholder">
            <span className="option-head">
              <span className="skeleton skeleton-times" />
            </span>
            <span className="option-bar">
              <span className="skeleton skeleton-bar" style={{ insetInlineStart: `${index * 8}%`, inlineSize: `${70 - index * 10}%` }} />
            </span>
            <span className="option-meta">
              <span className="skeleton skeleton-meta" />
            </span>
          </li>
        ))}
      </ol>
    </div>
  );
}
