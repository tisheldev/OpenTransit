import { useMemo } from "react";
import type { Journey } from "../../api/types";
import { Bdi } from "../../components/states";
import { useI18n } from "../../i18n/I18nProvider";
import { formatDuration } from "../../lib/format";
import { layoutChart, RESERVED_ROWS, type ChartSegment } from "../../plan/chartLayout";
import { isWalkOnly, rankLabels } from "../../plan/rank";
import { optionSpeech, rankKey } from "./labels";

// The comparison chart (design: Compare, "Chart"; CU04, CU14). One row per journey in
// the API's order, a shared time axis with the earliest time on the inline start, rank
// labels in text. Selecting a row never sends a request. Read as a list of options.

function Segment({ segment, trainLabel }: { segment: ChartSegment; trainLabel: string }) {
  return (
    <span
      className={`chart-seg chart-seg-${segment.kind}${segment.rail ? " chart-seg-rail" : ""}`}
      style={{ insetInlineStart: `${segment.start * 100}%`, inlineSize: `${Math.max(segment.width * 100, 0.8)}%` }}
    >
      {segment.showLabel && <Bdi>{segment.rail ? trainLabel : segment.label}</Bdi>}
    </span>
  );
}

export function OptionsChart({
  journeys,
  selected,
  onSelect,
}: {
  journeys: readonly Journey[];
  selected: number;
  onSelect: (index: number) => void;
}) {
  const { t, lang } = useI18n();
  const layout = useMemo(() => layoutChart(journeys, lang), [journeys, lang]);
  const ranks = useMemo(() => rankLabels(journeys), [journeys]);
  if (!layout) return null;
  return (
    <div className="chart">
      <div className="chart-grid chart-axis" aria-hidden="true">
        <span />
        <span className="chart-track chart-ticks">
          {layout.ticks.map((tick) => (
            <span key={tick.at} className="chart-tick" style={{ insetInlineStart: `${tick.fraction * 100}%` }}>
              <Bdi>{tick.label}</Bdi>
            </span>
          ))}
        </span>
        <span />
      </div>
      <ol className="chart-rows" aria-label={t("compare.options")}>
        {layout.rows.map((row) => {
          const journey = journeys[row.index]!;
          const rank = ranks[row.index] ?? null;
          const isSelected = row.index === selected;
          return (
            <li key={`${row.index}-${row.journeyId}`}>
              <button
                type="button"
                className="chart-grid chart-row"
                aria-pressed={isSelected}
                onClick={() => onSelect(row.index)}
              >
                {/* The option is read as one sentence; the drawing beside it is hidden from it. */}
                <span className="visually-hidden">{optionSpeech(journey, row.index, rank, t, lang)}</span>
                <span className="chart-num" aria-hidden="true">
                  {row.index + 1}
                </span>
                <span className="chart-track" aria-hidden="true">
                  {row.segments.map((segment, index) => (
                    <Segment key={index} segment={segment} trainLabel={t("compare.train")} />
                  ))}
                </span>
                <span className="chart-meta" aria-hidden="true">
                  <Bdi>{formatDuration(row.durationSeconds, lang)}</Bdi>
                  {rank && <span className="chart-rank">{t(rankKey[rank])}</span>}
                  {isWalkOnly(journey) && <span className="chart-rank">{t("compare.walkOnly")}</span>}
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
export function ChartSkeleton() {
  const { t } = useI18n();
  return (
    <div className="chart chart-skeleton" role="status" aria-live="polite" aria-busy="true">
      <span className="visually-hidden">{t("compare.loading")}</span>
      <div className="chart-grid chart-axis" aria-hidden="true" />
      <ol className="chart-rows" aria-hidden="true">
        {Array.from({ length: RESERVED_ROWS }, (_, index) => (
          <li key={index} className="chart-grid chart-row chart-row-placeholder">
            <span className="chart-num" />
            <span className="chart-track">
              <span className="chart-seg chart-seg-skeleton" />
            </span>
            <span className="chart-meta" />
          </li>
        ))}
      </ol>
    </div>
  );
}
