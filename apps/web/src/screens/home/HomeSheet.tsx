import { useId, useMemo, type ReactNode } from "react";
import { ApiFailure } from "../../api/result";
import { CanvasBadge, CanvasIcon, StopSign } from "../../components/canvas";
import { ErrorState } from "../../components/states";
import { useI18n } from "../../i18n/I18nProvider";
import { formatClock } from "../../lib/time";
import { vehicleOf } from "../../lib/lines";
import { go } from "../../router";
import type { SavedSlot } from "../../shell/localStore";
import type { SavedLine, SavedPlace, SavedStop } from "../../storage/local";
import { openStop } from "../stop/intent";
import type { LatLon } from "../../nav/geo";
import { minutesTo, type StopLine } from "../stop/lines";
import { useNow } from "../stop/parts";
import type { HomeStops } from "./homeStops";
import { NEAR_WALK_MINUTES, nearLines, type NearLine } from "./nearLines";
import { useNextRide, type RideOrigin } from "./nextRide";
import { HOME_SAVED_MAX, savedLineNext, savedStopLines, useSavedDepartures, type StopNext } from "./savedDepartures";

// Home's sheet as drawn on the stops-and-lines canvas (board 1, 14 November 2026): the
// search field with its hint, the cards (Home, Work, then saved stops and lines, each with
// its next departure), and "Near you": each line's next departure across the stops within
// a 5-minute walk. The map and its scene stay in HomeScreen.tsx.

const failureState = (error: unknown) => (error instanceof ApiFailure ? error.state : "unexpected");

/** Minutes as a card or row says them: "עכשיו" once due, a clock time from an hour. */
function useMinutesText() {
  const { t, lang } = useI18n();
  return (instant: string, now: Date, bare = false): string => {
    const minutes = minutesTo(instant, now);
    if (minutes <= 0) return t("time.now");
    if (minutes >= 60) return formatClock(instant, lang);
    return bare ? String(minutes) : t("stop.minutes", { minutes });
  };
}

const badgeOf = (line: Pick<StopLine, "mode" | "label" | "operatorId" | "operatorName">) => ({
  mode: line.mode,
  label: line.label,
  operatorId: line.operatorId,
  operatorName: line.operatorName,
});

/**
 * The field as a button (canvas `.fld`): "לאן נוסעים?" with the hint "מקום, תחנה או קו".
 * Named by both, as shown (WCAG 2.5.3: the visible text is in the name).
 */
export function HomeSearchField() {
  const { t } = useI18n();
  return (
    <button type="button" className="hs-field" onClick={() => go({ name: "search", field: "to" })}>
      <CanvasIcon name="search" />
      <span className="hs-field__text">{t("home.search")}</span>{" "}
      <span className="hs-mu">{t("home.search.hint")}</span>
    </button>
  );
}

function Card({ title, sub, onClick }: { title: ReactNode; sub: ReactNode; onClick: () => void }) {
  return (
    <button type="button" className="hs-card" onClick={onClick}>
      <span className="hs-card__title">{title}</span>
      {sub !== null && <span className="hs-card__sub">{sub}</span>}
    </button>
  );
}

/** Home or Work: plan to it, with the next departure toward it; unset, set it. */
export function PlaceCard({
  slot,
  saved,
  origin,
  enabled,
  now,
  onTravel,
}: {
  slot: SavedSlot;
  saved: SavedPlace | null;
  origin: RideOrigin | null;
  enabled: boolean;
  now: Date;
  onTravel: (saved: SavedPlace) => void;
}) {
  const { t, lang } = useI18n();
  const next = useNextRide(saved, origin, lang, t("stop.train"), enabled).data ?? null;
  const title = t(slot === "home" ? "place.home" : "place.work");
  if (!saved) {
    return <Card title={title} sub={t(slot === "home" ? "home.setHome" : "home.setWork")} onClick={() => go({ name: "search", field: slot })} />;
  }
  const minutes = next ? minutesTo(next.departure, now) : null;
  const shown = next && minutes !== null && minutes > 0 && minutes < 100;
  // Each card is named by everything it shows ("בית 66 בעוד 4 דק׳"), so the name always
  // holds the visible text (speech input, WCAG 2.5.3).
  return (
    <Card
      title={title}
      sub={
        shown ? (
          <>
            <CanvasBadge line={next} />
            <span>{t("home.inMinutes", { minutes })}</span>
          </>
        ) : null
      }
      onClick={() => onTravel(saved)}
    />
  );
}

/**
 * A stop's next lines in one line (canvas: "[2] 1 [8] 2 דק׳"): each badge with its
 * minutes, the unit said once at the end. Used by a saved stop's card and Search's stop rows.
 */
export function NextLinesInline({ lines, now }: { lines: readonly StopLine[]; now: Date }) {
  const minutesText = useMinutesText();
  return (
    <>
      {lines.map((line, index) => (
        <span key={line.key} className="cv-pair">
          <CanvasBadge line={badgeOf(line)} />
          <span>{minutesText(line.next, now, index < lines.length - 1)}</span>
        </span>
      ))}
    </>
  );
}

/** A saved stop: the sign and its name; its next two lines with their minutes. */
export function SavedStopCard({ stop, next, now }: { stop: SavedStop; next: StopNext | undefined; now: Date }) {
  const { t } = useI18n();
  const lines = savedStopLines(next, now, t("stop.train"));
  return (
    <Card
      title={
        <>
          <StopSign size="chip" station={vehicleOf(stop.mode) !== "bus"} />
          <bdi className="hs-ellipsis">{stop.name}</bdi>
        </>
      }
      sub={lines.length > 0 ? <NextLinesInline lines={lines} now={now} /> : null}
      onClick={() => openStop(stop.stopId)}
    />
  );
}

/** A saved line: its badge and where it goes; its next departure and the stop it is caught at. */
export function SavedLineCard({ line, next, now }: { line: SavedLine; next: StopNext | undefined; now: Date }) {
  const { t } = useI18n();
  const minutesText = useMinutesText();
  const departure = savedLineNext(line, next, now, t("stop.train"));
  const label = line.shortName.trim() || t("stop.train");
  const place = line.destinationName ?? line.area ?? line.operatorName ?? "";
  let sub: string | null = line.operatorName;
  if (line.stopName) {
    const from = t("home.savedLine.fromOnly", { stop: line.stopName });
    const minutes = departure ? minutesTo(departure.next, now) : null;
    if (departure === null || minutes === null) sub = from;
    else if (minutes > 0 && minutes < 60) sub = t("home.savedLine.from", { minutes, stop: line.stopName });
    // Due now, or an hour or more away: "עכשיו · מ…", "14:05 · מ…".
    else sub = `${minutesText(departure.next, now)} · ${from}`;
  }
  return (
    <Card
      title={
        <>
          <CanvasBadge line={{ mode: line.mode, label, operatorId: line.operatorId, operatorName: line.operatorName }} />
          <bdi className="hs-ellipsis">{place}</bdi>
        </>
      }
      sub={sub === null ? null : <bdi className="hs-ellipsis">{sub}</bdi>}
      onClick={() => go({ name: "line", lineKey: line.lineKey })}
    />
  );
}

/** "Near you": each line's next departure within the walk, naming its stop and the walk. */
export function NearLinesSection({
  rows,
  pending,
  error,
  onRetry,
  now,
}: {
  rows: readonly NearLine[];
  pending: boolean;
  error: unknown;
  onRetry: () => void;
  now: Date;
}) {
  const { t } = useI18n();
  const headingId = useId();
  return (
    <section className="hs-near" aria-labelledby={headingId}>
      <div className="hs-near__head">
        <h2 id={headingId}>{t("home.near.title")}</h2>
        <span className="hs-mu">{t("home.near.walk", { minutes: NEAR_WALK_MINUTES })}</span>
      </div>
      {pending ? null : error ? (
        <ErrorState state={failureState(error)} onRetry={onRetry} />
      ) : rows.length === 0 ? (
        <p className="hs-mu hs-none">{t("home.near.none")}</p>
      ) : (
        <ul className="hs-rows" aria-label={t("home.near.list")}>
          {rows.map((row) => (
            <li key={`${row.stop.stopId}|${row.line.key}`}>
              <button type="button" className="hs-row" onClick={() => openStop(row.stop.stopId, row.line.key)}>
                <CanvasBadge line={badgeOf(row.line)} />
                <span className="hs-row__text">
                  <bdi className="hs-row__name">{row.line.headsign ?? row.line.label}</bdi>
                  <span className="hs-mu hs-ellipsis">
                    <bdi>{t("home.near.from", { stop: row.stopName, minutes: row.walkMinutes })}</bdi>
                  </span>
                </span>
                <NearDue instant={row.line.next} now={now} />
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

/**
 * The whole sheet below the active-trip card: the field, the cards and "Near you", then
 * the timetable note. Storage renders first; departures fill in as they arrive.
 */
export function HomeSheet({
  nearby,
  centre,
  origin,
  painted,
  homePlace,
  workPlace,
  savedStops,
  savedLines,
  onTravel,
}: {
  nearby: HomeStops;
  centre: LatLon;
  origin: RideOrigin | null;
  painted: boolean;
  homePlace: SavedPlace | null;
  workPlace: SavedPlace | null;
  savedStops: readonly SavedStop[];
  savedLines: readonly SavedLine[];
  onTravel: (saved: SavedPlace) => void;
}) {
  const { t } = useI18n();
  const now = useNow();
  const trainLabel = t("stop.train");
  // Saved items after Home and Work, in the order saved: stops, then lines (as drawn).
  const shownStops = savedStops.slice(0, HOME_SAVED_MAX);
  const shownLines = savedLines.slice(0, Math.max(0, HOME_SAVED_MAX - shownStops.length));
  const next = useSavedDepartures(shownStops, shownLines, nearby.all, {
    enabled: painted,
    nearbySettled: !nearby.pending,
    now,
    trainLabel,
  });
  const rows = useMemo(() => nearLines(nearby.all, centre, { trainLabel, now }), [nearby.all, centre, trainLabel, now]);

  return (
    <>
      <HomeSearchField />

      <section aria-label={t("home.saved")}>
        <div className="hs-cards">
          <PlaceCard slot="home" saved={homePlace} origin={origin} enabled={painted} now={now} onTravel={onTravel} />
          <PlaceCard slot="work" saved={workPlace} origin={origin} enabled={painted} now={now} onTravel={onTravel} />
          {shownStops.map((stop) => (
            <SavedStopCard key={`stop:${stop.stopId}`} stop={stop} next={next.get(stop.stopId)} now={now} />
          ))}
          {shownLines.map((line) => (
            <SavedLineCard key={`line:${line.lineKey}`} line={line} next={line.stopId ? next.get(line.stopId) : undefined} now={now} />
          ))}
        </div>
      </section>

      <NearLinesSection
        rows={rows}
        pending={!painted || nearby.pending}
        error={nearby.error}
        onRetry={() => nearby.refetch()}
        now={now}
      />

      <p className="hs-mu hs-note">{t("stop.scheduled")}</p>
    </>
  );
}

/** The row's minutes (canvas `.due`): the figure in Barlow 20 px, the unit muted. */
function NearDue({ instant, now }: { instant: string; now: Date }) {
  const { t, lang } = useI18n();
  const minutes = minutesTo(instant, now);
  if (minutes <= 0) return <span className="hs-due">{t("time.now")}</span>;
  if (minutes >= 60)
    return (
      <span className="hs-due">
        <bdi className="hs-due__n">{formatClock(instant, lang)}</bdi>
      </span>
    );
  const [before, after = ""] = t("stop.minutes").split("{minutes}");
  return (
    <span className="hs-due">
      {before}
      <bdi className="hs-due__n">{minutes}</bdi>
      {after}
    </span>
  );
}
