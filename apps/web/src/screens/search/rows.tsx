import type { LineItem, Meta, PlaceCandidate } from "../../api/schemas";
import { CanvasBadge, CanvasIcon, PlaceLead, StopSign } from "../../components/canvas";
import { useI18n } from "../../i18n/I18nProvider";
import { formatDistance } from "../../lib/format";
import type { PlaceChoice } from "../../plan/draft";
import { go } from "../../router";
import { NextLinesInline } from "../home/HomeSheet";
import { walkMinutes } from "../home/nearLines";
import { openStop } from "../stop/intent";
import { groupLines, type Departure } from "../stop/lines";
import { choiceFromCandidate, isStreetLevel, readableLocality } from "./choice";

// Search's rows as drawn on the canvas (board 2, 14 November 2026). A line leads with its
// badge and opens the line; a stop leads with the stop sign, sets the journey end when
// tapped, and has a second 44 px button for its departures; a place leads with a quiet pin
// and says its kind in words. Each row's text is its accessible name.

/** Lines a stop row names (as drawn: two), only from the nearby answer Home holds. */
const STOP_ROW_LINES = 2;

const join = (parts: Array<string | null | undefined>) => parts.filter((part): part is string => !!part && part.trim() !== "").join(" · ");

/** "origin ↔ destination" of a line's first direction; the destination alone without an origin. */
export function lineEnds(line: LineItem): string {
  const first = line.directions[0];
  if (!first) return line.area ?? line.operatorName ?? "";
  const to = first.destinationName ?? first.headsign ?? "";
  return first.originName && to ? `${first.originName} ↔ ${to}` : to || (first.originName ?? "");
}

export function LineRow({ line }: { line: LineItem }) {
  const { t } = useI18n();
  const near = line.nearestStop ? t("search.line.near", { minutes: walkMinutes(line.nearestStop.distanceM) }) : null;
  return (
    <li>
      <button type="button" className="sx-row" onClick={() => go({ name: "line", lineKey: line.lineKey })}>
        <CanvasBadge
          line={{ mode: line.mode, label: line.shortName.trim() || t("stop.train"), operatorId: line.operatorId, operatorName: line.operatorName }}
        />
        <span className="sx-tx">
          <bdi className="sx-nm">{lineEnds(line)}</bdi>
          <span className="sx-sub">
            <bdi>{join([line.operatorName, line.area, near])}</bdi>
          </span>
        </span>
        <CanvasIcon name="chevron" />
      </button>
    </li>
  );
}

export function MoreLinesRow({ count, atLeast, onOpen }: { count: number; atLeast: boolean; onOpen: () => void }) {
  const { t } = useI18n();
  return (
    <li>
      <button type="button" className="sx-row sx-more" aria-expanded={false} onClick={onOpen}>
        {t(atLeast ? "search.lines.moreMany" : "search.lines.more", { count })}
      </button>
    </li>
  );
}

/** The name, tagged with its language when the API answered in the other one. */
function Name({ candidate }: { candidate: PlaceCandidate }) {
  const { lang } = useI18n();
  const other = candidate.languageUsed !== lang && /^[a-z]{2}$/.test(candidate.languageUsed);
  return (
    <bdi className="sx-nm" lang={other ? candidate.languageUsed : undefined}>
      {candidate.displayName}
    </bdi>
  );
}

export function StopRow({
  candidate,
  meta,
  distance,
  departures,
  now,
  withDepartures,
  onChoose,
}: {
  candidate: Extract<PlaceCandidate, { kind: "stop" | "station" }>;
  meta: Meta;
  distance: number | null;
  departures: readonly Departure[] | null;
  now: Date;
  /** The clock button (opening the stop) only where a journey end is being chosen. */
  withDepartures: boolean;
  onChoose: (choice: PlaceChoice) => void;
}) {
  const { t, lang } = useI18n();
  const code = candidate.stopCode ? t("place.stopCode", { code: candidate.stopCode }) : t(`place.${candidate.kind}`);
  const where = distance !== null ? formatDistance(distance, lang) : readableLocality(candidate.locality);
  const lines = departures ? groupLines(departures, [], { trainLabel: t("stop.train"), now, max: STOP_ROW_LINES }) : [];
  return (
    <li className="sx-row sx-row--stop">
      <button type="button" className="sx-main" onClick={() => onChoose(choiceFromCandidate(candidate, meta))}>
        <StopSign size="lead" station={candidate.kind === "station"} />
        <span className="sx-tx">
          <Name candidate={candidate} />
          <span className="sx-sub">
            <bdi>{join([code, where])}</bdi>
          </span>
          {lines.length > 0 && (
            <span className="sx-cs">
              <NextLinesInline lines={lines} now={now} />
            </span>
          )}
        </span>
      </button>
      {withDepartures && (
        <button
          type="button"
          className="sx-clock"
          aria-label={t("search.stop.departures", { stop: candidate.displayName })}
          onClick={() => openStop(candidate.id)}
        >
          <CanvasIcon name="clock" />
        </button>
      )}
    </li>
  );
}

export function PlaceRow({ candidate, meta, onChoose }: { candidate: Extract<PlaceCandidate, { kind: "poi" | "address" }>; meta: Meta; onChoose: (choice: PlaceChoice) => void }) {
  const { t } = useI18n();
  const locality = readableLocality(candidate.locality);
  return (
    <li>
      <button type="button" className="sx-row" onClick={() => onChoose(choiceFromCandidate(candidate, meta))}>
        <PlaceLead />
        <span className="sx-tx">
          <Name candidate={candidate} />
          <span className="sx-sub">
            <span className="sx-kind">{t(`place.${candidate.kind}`)}</span>
            {isStreetLevel(candidate) && <span className="place-tag">{t("place.streetLevel")}</span>}
            {locality && (
              <>
                {" · "}
                <bdi>{locality}</bdi>
              </>
            )}
          </span>
        </span>
      </button>
    </li>
  );
}
