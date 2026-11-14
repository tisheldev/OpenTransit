import { useQueries } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { getTrip } from "../../api/endpoints";
import { useStopDepartures, useStopDetail, useStopDetails, useStopLines } from "../../api/queries";
import { ApiFailure, unwrap } from "../../api/result";
import type { Trip } from "../../api/schemas";
import { Empty, ErrorState, Loading } from "../../components/states";
import { useI18n } from "../../i18n/I18nProvider";
import { formatClock } from "../../lib/time";
import { emptyScene, usePublishScene, type LonLat, type MapPin, type MapRouteLeg, type MapScene, type MapTag } from "../../map/scene";
import { fromPosition, haversineMeters } from "../../nav/geo";
import type { PlaceChoice } from "../../plan/draft";
import { usePlan } from "../../plan/PlanProvider";
import { planKeys, TRIP_STALE_MS } from "../../plan/queries";
import { go } from "../../router";
import { toggleSavedStop, useIsStopSaved } from "../../storage/saved";
import { useBoardSheet } from "../line/boardSheet";
import { useLineKeyFor } from "../line/data";
import { StrokeIcon } from "../line/icons";
import { openLine } from "../line/intent";
import { walkMinutes } from "../line/lineModel";
import "../line/stopline.css";
import { initialLine } from "./intent";
import {
  callPosition,
  callsAhead,
  directionChevron,
  firstStretch,
  groupLines,
  patternAhead,
  patternFor,
  patternLine,
  routeAhead,
  routesOfLines,
  spotAround,
  tagLine,
  type Departure,
  type StopLine,
} from "./lines";
import { Badge, Distance, Due, useNow, withFigure } from "./parts";
import { usePassengerFix } from "./passenger";
import "./stop.css";

// A stop — board 7 (11 November 2026), reworked to the stops-and-lines canvas board Stop
// (3), 14 November 2026: the stop's name with its distance and walk, a star to save it, and
// "לנסוע מכאן" / "להגיע לכאן", which open Search or Choose with that end filled. Each line
// through the stop is a row with its next departure; a chosen line opens in place to its
// next three times and "כל התחנות" (the Line screen). The map: the stop's sign (marker G,
// bright), every line out of it faded along its pattern, the chosen line's whole pattern in
// full with its outline, its stops, a chevron for its direction and a tag at its far end.

/** The departures read: enough for every line in the next hour and a half. */
const STOP_WINDOW = { limit: 40, horizonMinutes: 90 };
/** Rows at most (one per line and direction). */
const MAX_LINES = 12;
/** Times shown under a chosen line (board 3: three). */
const NEXT_TIMES = 3;
/**
 * How far each line fans out of the stop before its tag (boards: to the map's edge), and
 * the shorter fans tried when that end is taken by another line's tag.
 */
const FAN_LENGTHS = [900, 600, 1200, 350];
const TAG_SPACING_METERS = 180;
/** Next stops ringed along the chosen line (each a stop lookup until trips carry coordinates). */
const RINGED_CALLS = 8;
/** The sheet's share of the screen on board 3 (548 of 844 px). */
const SHEET_SHARE = 548 / 844;

const failureState = (error: unknown) => (error instanceof ApiFailure ? error.state : "unexpected");
const tripData = (results: ReadonlyArray<{ data?: Trip }>) => results.map((result) => result.data?.data ?? null);

/** A chosen line's next times and the link to all its stops (board 3, opened in place). */
function LineTimes({ line, departures, stopId }: { line: StopLine; departures: readonly Departure[]; stopId: string }) {
  const { t, lang } = useI18n();
  const lineKey = useLineKeyFor(line.routeId, line.label);
  const key = lineKey.data ?? null;
  const times = departures
    .filter((item) => `${item.routeId ?? item.routeShortName}|${item.headsign ?? ""}` === line.key && Date.parse(item.scheduledDeparture) >= Date.parse(line.next))
    .slice(0, NEXT_TIMES);
  const open = (tripRef: string | null) => {
    if (key) openLine({ lineKey: key, stopId, routeId: line.routeId, tripRef });
  };
  return (
    <div className="stop-times" role="group" aria-label={t("stop.nextTimes", { line: line.label })}>
      {times.map((item) => (
        <button key={`${item.tripRef}|${item.scheduledDeparture}`} type="button" className="sl-chip num" disabled={!key} onClick={() => open(item.tripRef)}>
          {formatClock(item.scheduledDeparture, lang)}
        </button>
      ))}
      <button type="button" className="sl-link stop-times__all" disabled={!key} onClick={() => open(null)}>
        {t("stop.allStops")}
        <StrokeIcon name="forward" />
      </button>
    </div>
  );
}

export function StopScreen({ stopId }: { stopId: string }) {
  const { t, lang } = useI18n();
  const now = useNow();
  const fix = usePassengerFix();
  const plan = usePlan();
  const stop = useStopDetail(stopId);
  const departures = useStopDepartures(stopId, STOP_WINDOW);
  const [chosenKey, setChosenKey] = useState<string | null>(() => initialLine(stopId));
  const saved = useIsStopSaved(stopId);
  useBoardSheet(SHEET_SHARE);

  const detail = stop.data?.data ?? null;
  const name = detail ? (lang === "en" ? detail.translations.en : null) || detail.name || detail.code || t("screen.stop") : t("screen.stop");
  const point = useMemo(() => (detail ? { latitude: detail.latitude, longitude: detail.longitude } : null), [detail]);

  // Every line through the stop with its patterns' stops (API PR #35): the fans and the
  // chosen route are drawn from them. An API without the endpoint answers 404, and a line
  // it does not list falls back to its next trip's shape.
  const stopLines = useStopLines(stopId);
  const lineItems = stopLines.data?.data ?? null;
  const routes = useMemo(() => [...routesOfLines(lineItems ?? []), ...(detail?.routes ?? [])], [lineItems, detail]);

  // Grouped as of the answer's time (refreshed every minute), so the map is not redrawn
  // and reframed on every tick of the clock.
  const answeredAt = departures.dataUpdatedAt;
  const lines = useMemo(
    () => groupLines(departures.data?.data ?? [], routes, { trainLabel: t("stop.train"), now: new Date(answeredAt), max: MAX_LINES }),
    [departures.data, routes, t, answeredAt],
  );
  const patterns = useMemo(() => lines.map((line) => (lineItems ? patternFor(line, lineItems) : null)), [lines, lineItems]);
  // Lines without a pattern: their next trip, for its shape (shared with Compare's cache).
  const tripRefs = useMemo(
    () => (stopLines.isPending ? [] : lines.filter((_, index) => !patterns[index]).map((line) => line.tripRef)),
    [stopLines.isPending, lines, patterns],
  );
  const trips = useQueries({
    queries: tripRefs.map((tripRef) => ({
      queryKey: planKeys.trip(tripRef),
      queryFn: async ({ signal }: { signal?: AbortSignal }) => unwrap(await getTrip(tripRef, signal)),
      staleTime: TRIP_STALE_MS,
      retry: false,
    })),
    combine: tripData,
  });
  const chosen = lines.find((line) => line.key === chosenKey) ?? null;
  const chosenIndex = chosen ? lines.indexOf(chosen) : -1;
  const chosenPattern = chosenIndex >= 0 ? (patterns[chosenIndex] ?? null) : null;
  const chosenTrip = chosen && !chosenPattern ? (trips[tripRefs.indexOf(chosen.tripRef)] ?? null) : null;

  // Without a pattern, where the chosen line goes next: the trip's calls, by their own
  // coordinates or else the stops' own.
  const nextCalls = useMemo(() => (chosen && chosenTrip ? callsAhead(chosenTrip, chosen.callSequence, RINGED_CALLS) : []), [chosen, chosenTrip]);
  const lookedUp = useStopDetails(nextCalls.filter((call) => callPosition(call) === null).map((call) => call.stopId));

  const scene = useMemo<MapScene>(() => {
    if (!point) return { ...emptyScene, camera: "keep" };
    const route: MapRouteLeg[] = [];
    const tags: MapTag[] = [];
    const pins: MapPin[] = [];
    const fitTo: LonLat[] = [[point.longitude, point.latitude]];
    const leg = (line: StopLine, coordinates: LonLat[], tone: "normal" | "quiet"): MapRouteLeg => ({
      kind: "transit",
      mode: line.mode,
      coordinates,
      from: coordinates[0]!,
      to: coordinates[coordinates.length - 1]!,
      label: null,
      operatorId: line.operatorId,
      operatorName: line.operatorName,
      tone,
    });
    // A tag at the top end of a line hangs below its point and one at the bottom end above
    // it, so tags stay inside the frame rather than under the top band or the sheet.
    const anchorAt = (at: LonLat): "above" | "below" => (at[1] > point.latitude ? "below" : "above");
    const aheads = lines.map((line, index) => {
      const pattern = patterns[index];
      if (pattern) return patternAhead(pattern, point);
      return routeAhead(trips[tripRefs.indexOf(line.tripRef)]?.shape ?? null, point);
    });
    // Lines without a shape: their tags spread around the stop instead of at a fan's end.
    const shapeless = aheads.filter((ahead) => ahead === null).length;
    let spot = 0;
    const placed: LonLat[] = [];
    const roomAt = (at: LonLat) => placed.every((other) => haversineMeters(fromPosition(other), fromPosition(at)) >= TAG_SPACING_METERS);
    lines.forEach((line, index) => {
      if (line === chosen) {
        if (!aheads[index]) spot += 1;
        return;
      }
      const ahead = aheads[index];
      // Lines often share a street out of the stop: a fan whose end would land on another
      // tag is cut shorter, so each tag stays at its own fan's end and readable.
      let fan: LonLat[] | null = null;
      if (ahead) {
        for (const meters of FAN_LENGTHS) {
          fan = firstStretch(ahead, meters);
          if (roomAt(fan[fan.length - 1]!)) break;
        }
      }
      if (fan) {
        route.push(leg(line, fan, "quiet"));
        fitTo.push(...fan);
      }
      if (chosen) {
        // While a line's whole route is shown the map is framed on it, many kilometres
        // across: the other lines' tags would pile up on the stop and hide it and the
        // direction chevron. Their fans stay, faded; their rows stay in the panel.
        if (!fan) spot += 1;
        return;
      }
      const position = fan ? fan[fan.length - 1]! : spotAround(point, spot++, shapeless);
      placed.push(position);
      if (!fan) fitTo.push(position);
      tags.push({
        id: `line-${line.key}`,
        position,
        anchor: anchorAt(position),
        kind: "faded",
        line: tagLine(line),
        text: line.headsign ?? undefined,
        // Named by what it shows ("5 רכבת מרכז"), like the line's row in the panel.
        onSelect: () => setChosenKey(line.key),
      });
    });
    if (chosen) {
      const ahead = aheads[chosenIndex] ?? null;
      // Its whole route is what the passenger asked to see: the pattern from end to end
      // (else the trip's shape from the stop on).
      const whole = chosenPattern ? patternLine(chosenPattern) : ahead;
      const end = whole ? whole[whole.length - 1]! : spotAround(point, lines.slice(0, chosenIndex).filter((_, i) => !aheads[i]).length, shapeless);
      if (whole) {
        route.push(leg(chosen, whole, "normal"));
        fitTo.splice(1, fitTo.length - 1, ...whole);
      } else {
        fitTo.push(end);
      }
      if (chosenPattern) {
        chosenPattern.stops.forEach((stop, index) => {
          if (index === chosenPattern.stopIndex) return;
          pins.push({ id: `call-${index}-${stop.stopId}`, role: "stop", position: [stop.longitude, stop.latitude], label: stop.name ?? "" });
        });
      }
      if (ahead) {
        const mark = directionChevron(ahead);
        if (mark) {
          tags.push({
            id: "direction",
            position: mark.position,
            kind: "plain",
            anchor: "center",
            glyph: { kind: "chevron", bearing: mark.bearing },
            ariaLabel: t("stop.direction", { line: chosen.label }),
          });
        }
      }
      let looked = 0;
      nextCalls.forEach((call, index) => {
        const own = callPosition(call);
        const found = own ? null : lookedUp[looked++];
        const position: LonLat | null = own ?? (found ? [found.longitude, found.latitude] : null);
        if (position) pins.push({ id: `call-${index}-${call.stopId}`, role: "stop", position, label: found?.name ?? "" });
      });
      tags.push({
        id: `end-${chosen.key}`,
        position: end,
        anchor: anchorAt(end),
        kind: "strong",
        line: tagLine(chosen),
        text: chosen.headsign ?? undefined,
        ariaLabel: chosen.headsign
          ? t("stop.line.end", { line: chosen.label, headsign: chosen.headsign })
          : t("stop.line.endNoHeadsign", { line: chosen.label }),
      });
    }
    return {
      ...emptyScene,
      route,
      pins,
      tags,
      stopPins: [{ id: stopId, position: [point.longitude, point.latitude], selected: true, look: "sign", bearingDegrees: detail?.bearingDegrees, ariaLabel: t("stop.pin", { stop: name }) }],
      user: fix ? { position: [fix.longitude, fix.latitude], accuracyMeters: fix.accuracyMeters } : null,
      camera: "fit",
      fitTo,
    };
  }, [point, detail?.bearingDegrees, lines, patterns, tripRefs, trips, chosen, chosenIndex, chosenPattern, nextCalls, lookedUp, fix, name, stopId, t]);
  usePublishScene(scene);

  if (stop.isError) {
    return (
      <div className="stop">
        <h1 className="stop-title">{t("screen.stop")}</h1>
        <ErrorState state={failureState(stop.error)} onRetry={() => void stop.refetch()} />
      </div>
    );
  }

  const meters = fix && point ? haversineMeters(fix, point) : null;
  const place: PlaceChoice | null = detail
    ? { label: name, locality: null, kind: "stop", latitude: detail.latitude, longitude: detail.longitude, stopId, placeRef: null, refGenerationId: null }
    : null;
  // Board 3: "לנסוע מכאן" sets the start and asks where to (Search); "להגיע לכאן" sets the
  // destination and compares from the start already chosen (or asks where from).
  const travelFrom = () => {
    if (!place) return;
    plan.setFrom({ type: "place", place });
    go({ name: "search", field: "to" });
  };
  const travelTo = () => {
    if (!place) return;
    plan.setTo({ type: "place", place });
    go(plan.draft.from ? { name: "compare" } : { name: "search", field: "from" });
  };

  return (
    <div className="stop">
      <div className="stop-head">
        <div className="stop-head__text">
          <h1 className="stop-title">
            <bdi>{name}</bdi>
          </h1>
          {meters !== null && (
            <span className="b-mu stop-walk">
              <Distance meters={meters} />
              {" · "}
              {withFigure(t("stop.walkMinutes"), <bdi className="num">{walkMinutes(meters)}</bdi>)}
            </span>
          )}
        </div>
        <button
          type="button"
          className="sl-icbtn"
          aria-label={t("stop.save")}
          aria-pressed={saved}
          disabled={!detail}
          onClick={() =>
            detail &&
            toggleSavedStop({ stopId, name, code: detail.code, latitude: detail.latitude, longitude: detail.longitude, mode: (detail as { mode?: string | null }).mode ?? null })
          }
        >
          <StrokeIcon name="star" filled={saved} />
        </button>
      </div>
      <div className="stop-actions">
        <button type="button" className="sl-btn" disabled={!place} onClick={travelFrom}>
          {t("stop.travelFrom")}
        </button>
        <button type="button" className="sl-btn sl-btn--secondary" disabled={!place} onClick={travelTo}>
          {t("stop.travelTo")}
        </button>
      </div>
      {stop.isPending || departures.isPending ? (
        <Loading />
      ) : departures.isError ? (
        <ErrorState state={failureState(departures.error)} onRetry={() => void departures.refetch()} />
      ) : lines.length === 0 ? (
        <Empty kind="noDepartures" />
      ) : (
        <ul className="stop-lines" aria-label={t("stop.lines")}>
          {lines.map((line) => {
            const on = line.key === chosen?.key;
            return (
              <li key={line.key} className={on ? "stop-line stop-line--open" : "stop-line"}>
                <button
                  type="button"
                  className={on ? "b-row b-row--on" : "b-row"}
                  aria-pressed={on}
                  onClick={() => setChosenKey(on ? null : line.key)}
                >
                  <Badge line={line} />
                  <span className="b-row__name">
                    <bdi>{line.headsign ?? ""}</bdi>
                  </span>
                  <Due instant={line.next} now={now} />
                </button>
                {on && <LineTimes line={line} departures={departures.data?.data ?? []} stopId={stopId} />}
              </li>
            );
          })}
        </ul>
      )}
      <p className="b-mu stop-note">{t("stop.scheduled")}</p>
    </div>
  );
}
