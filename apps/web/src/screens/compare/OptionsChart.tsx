import { useMemo } from "react";
import type { Journey } from "../../api/types";
import { Bdi } from "../../components/states";
import { useI18n } from "../../i18n/I18nProvider";
import { formatDistance } from "../../lib/format";
import { formatClock } from "../../lib/time";
import { layoutChart, RESERVED_ROWS, type ChartSegment } from "../../plan/chartLayout";
import { isWalkOnly, rankLabels } from "../../plan/rank";
import { compactDuration, daysBetween, formatShortDay, israelDate, optionSpeech, rankKey } from "./labels";

// The options as one chart on a shared time axis (design: LegBar; CU04, CU14; the user's
// variant B). One row per journey in the API's order (`ot-crow`): its duration and rank
// at the inline start, then its departure and arrival times over its bar (`ot-lbar`) on
// the axis, earliest on the inline start (the right in Hebrew). The times stay in every
// row (an earlier UX pass). Selecting a row never sends a request. Each row is read as
// one sentence; the drawing is hidden from it.

/**
 * A ride is drawn at least this share of the axis. The bars share their row with the
 * duration and rank (design: LegBar), so the axis is about 212 px wide at 360 px: this
 * keeps a three-digit line number legible (about 26 px) in its segment.
 */
const MIN_RIDE_FRACTION = 0.125;

/** "+1" after a time on the next day (its own left-to-right run, so the sign stays in front). */
export function NextDay({ days }: { days: number }) {
  return (
    <sup className="compare-plus">
      <bdi dir="ltr">{`+${days}`}</bdi>
    </sup>
  );
}

/** "1:45 שע׳" / "47 דק׳": the number in tabular figures, the unit smaller (design: LegBar). */
export function Duration({ seconds }: { seconds: number }) {
  const { t } = useI18n();
  const { value, unit } = compactDuration(seconds);
  return (
    <>
      <Bdi>{value}</Bdi> <small>{t(unit === "h" ? "compare.unit.h" : "compare.unit.min")}</small>
    </>
  );
}

/**
 * One leg on the bar: rides solid in their mode colour with the line when wide enough (a
 * train says "רכבת"), walks a dotted rule, waits a thin one. Placed by its share of the
 * axis from the inline start, with the design's 2 px gap at its end.
 */
function Segment({ segment, trainLabel }: { segment: ChartSegment; trainLabel: string }) {
  const kind = segment.kind === "transit" ? (segment.mode === "bus" ? "bus" : "rail") : segment.kind;
  const label = segment.rail ? trainLabel : segment.label;
  return (
    <span
      className={`ot-lbar__seg ot-lbar__seg--${kind}`}
      style={{
        insetInlineStart: `${segment.start * 100}%`,
        inlineSize: `max(2px, calc(${Math.max(segment.width * 100, 0.6)}% - 2px))`,
      }}
    >
      {segment.kind === "transit" && segment.showLabel && label && <Bdi>{label}</Bdi>}
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
  const layout = useMemo(() => layoutChart(journeys, lang, MIN_RIDE_FRACTION), [journeys, lang]);
  const ranks = useMemo(() => rankLabels(journeys), [journeys]);
  if (!layout) return null;
  // A time on another day than the one asked carries its day (e.g. Friday night → Saturday).
  const dayOf = (instant: string): string | null => (israelDate(instant) === askedDate ? null : formatShortDay(instant, lang));
  return (
    <div className="ot-chart compare-chart">
      <div className="ot-chart__axis compare-axis-wrap" aria-hidden="true">
        <div className="ot-axis compare-axis">
          {layout.ticks.map((tick) => (
            <span key={tick.at} className="compare-tick" style={{ insetInlineStart: `${tick.fraction * 100}%` }}>
              <Bdi>{tick.label}</Bdi>
            </span>
          ))}
        </div>
      </div>
      <ol className="compare-options" aria-label={t("compare.options")}>
        {layout.rows.map((row) => {
          const journey = journeys[row.index]!;
          const rank = ranks[row.index] ?? null;
          const walkOnly = isWalkOnly(journey);
          const departureDay = israelDate(row.departure);
          const overnight = daysBetween(departureDay, israelDate(row.arrival));
          const distance = walkOnly ? formatDistance(journey.walkingDistanceMeters ?? null, lang) : null;
          return (
            <li key={`${row.index}-${row.journeyId}`}>
              <button
                type="button"
                className="ot-crow compare-crow"
                aria-pressed={row.index === selected}
                onClick={() => onSelect(row.index)}
              >
                <span className="visually-hidden">{optionSpeech(journey, row.index, rank, t, lang, dayOf)}</span>
                <span className="compare-crow__lead" aria-hidden="true">
                  <b>
                    <Duration seconds={row.durationSeconds} />
                  </b>
                  {rank && <small>{t(rankKey[rank])}</small>}
                </span>
                <span className="compare-crow__main" aria-hidden="true">
                  <span className="compare-crow__times">
                    {departureDay !== askedDate && <span className="compare-day">{dayOf(row.departure)}</span>}
                    <Bdi>{formatClock(row.departure, lang)}</Bdi>
                    <span className="compare-dash">–</span>
                    <Bdi>{formatClock(row.arrival, lang)}</Bdi>
                    {overnight > 0 && <NextDay days={overnight} />}
                    {walkOnly && (
                      <span className="compare-crow__note">
                        <span>{t("compare.walkOnly")}</span>
                        {distance && (
                          <>
                            {" · "}
                            <Bdi>{distance}</Bdi>
                          </>
                        )}
                      </span>
                    )}
                  </span>
                  <span className="ot-lbar compare-lbar">
                    {row.segments.map((segment, index) => (
                      <Segment key={index} segment={segment} trainLabel={t("compare.train")} />
                    ))}
                  </span>
                </span>
              </button>
            </li>
          );
        })}
      </ol>
    </div>
  );
}

/** Loading: the chart's space for three rows is reserved so nothing jumps (design). */
export function OptionsSkeleton() {
  const { t } = useI18n();
  return (
    <div className="options-skeleton" role="status" aria-live="polite" aria-busy="true">
      <span className="visually-hidden">{t("compare.loading")}</span>
      <div className="ot-chart compare-chart" aria-hidden="true">
        <div className="ot-chart__axis compare-axis-wrap">
          <div className="ot-axis compare-axis" />
        </div>
        <ol className="compare-options">
          {Array.from({ length: RESERVED_ROWS }, (_, index) => (
            <li key={index} className="ot-crow compare-crow option-placeholder">
              <span className="compare-crow__lead">
                <span className="ot-skel compare-skel-lead" />
              </span>
              <span className="compare-crow__main">
                <span className="ot-skel compare-skel-times" />
                <span className="ot-lbar compare-lbar">
                  <span
                    className="ot-skel compare-skel-bar"
                    style={{ insetInlineStart: `${index * 8}%`, inlineSize: `${70 - index * 10}%` }}
                  />
                </span>
              </span>
            </li>
          ))}
        </ol>
      </div>
    </div>
  );
}
