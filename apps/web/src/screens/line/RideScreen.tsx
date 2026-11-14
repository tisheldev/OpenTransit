import { useQuery } from "@tanstack/react-query";
import { useMemo, useState, type CSSProperties } from "react";
import { planPinnedJourney, PINNED_TRIP_MISSED_BY_WALK, PINNED_TRIP_WALK_UNAVAILABLE, type PinnedJourneyRequest } from "../../api/lines";
import { ApiFailure, unwrap } from "../../api/result";
import type { LocationInput } from "../../api/types";
import { CanvasBadge } from "../../components/canvas";
import { ErrorState, Loading, TestDataBanner } from "../../components/states";
import { useI18n } from "../../i18n/I18nProvider";
import { formatDuration } from "../../lib/format";
import { formatClock, toIsraelIso } from "../../lib/time";
import { emptyScene, usePublishScene, type LonLat, type MapPin, type MapRouteLeg, type MapScene, type MapTag } from "../../map/scene";
import { haversineMeters } from "../../nav/geo";
import { startActiveTrip } from "../../nav/activeTrip";
import type { PlaceChoice } from "../../plan/draft";
import { usePlan } from "../../plan/PlanProvider";
import { useTrip } from "../../plan/queries";
import { go, hrefFor } from "../../router";
import { usePassengerFix } from "../stop/passenger";
import { useLine, useRouteDepartures, useStopLinesAll } from "./data";
import { StrokeIcon } from "./icons";
import { readRide, writeRide, type RideIntent } from "./intent";
import { useBoardSheet } from "./boardSheet";
import { directionsOf, lineDepartures, rideRows, stopTimes, walkMinutes } from "./lineModel";
import { useLineColour } from "./parts";
import "./line.css";
import "./stopline.css";

// Ride it — canvas board Ride (5), 14 November 2026: on a line the passenger picks a
// departure and taps the stop to get off at. The answer is a journey pinned to that trip
// (contract A3, `POST /v1/journeys` with `pinnedTrip`): a walk to the board stop, then the
// ride. "יוצאים לדרך" starts navigation on it as any planned journey does; "ולהמשיך משם…"
// makes the exit stop the start of a new plan and asks where to.

const SHEET_SHARE = 628 / 844;
const CHIPS = 3;

const failureState = (error: unknown) => (error instanceof ApiFailure ? error.state : "unexpected");

export function RideScreen() {
  const [ride, setRide] = useState<RideIntent | null>(() => readRide());
  useBoardSheet(SHEET_SHARE);
  if (!ride) return <RideExpired />;
  return (
    <Ride
      ride={ride}
      onChange={(next) => {
        writeRide(next);
        setRide(next);
      }}
    />
  );
}

function RideExpired() {
  const { t } = useI18n();
  usePublishScene(emptyScene);
  return (
    <div className="ride">
      <h1 className="visually-hidden">{t("screen.ride")}</h1>
      <p className="b-mu">{t("ride.expired")}</p>
      <a className="sl-link" href={hrefFor({ name: "home" })}>
        {t("screen.backHome")}
      </a>
    </div>
  );
}

function Ride({ ride, onChange }: { ride: RideIntent; onChange: (ride: RideIntent) => void }) {
  const { t, lang } = useI18n();
  const fix = usePassengerFix();
  const plan = usePlan();
  const [openAfter, setOpenAfter] = useState(false);

  const line = useLine(ride.lineKey);
  const item = line.data?.data ?? null;
  const stopLines = useStopLinesAll(ride.boardStopId);
  const direction = useMemo(
    () => (item && stopLines.data ? (directionsOf(item, stopLines.data.data).find((entry) => entry.routeId === ride.routeId) ?? null) : null),
    [item, stopLines.data, ride.routeId],
  );
  const stops = useMemo(() => direction?.stops ?? [], [direction]);
  const board = stops.findIndex((stop) => stop.stopId === ride.boardStopId);
  const alightAt = ride.alightStopId ? stops.findIndex((stop, index) => index > board && stop.stopId === ride.alightStopId) : -1;
  const alight = alightAt > board ? alightAt : null;
  const boardStop = board >= 0 ? stops[board]! : null;
  const alightStop = alight !== null ? stops[alight]! : null;

  const departuresQuery = useRouteDepartures(ride.boardStopId, ride.routeId);
  const departures = useMemo(
    () => lineDepartures(departuresQuery.data?.data ?? [], ride.routeId, new Date(departuresQuery.dataUpdatedAt)).slice(0, CHIPS),
    [departuresQuery.data, departuresQuery.dataUpdatedAt, ride.routeId],
  );
  // The departure chosen on the line, while it is still among the next ones; else the next.
  const tripRef = (ride.tripRef && departures.some((item) => item.tripRef === ride.tripRef) ? ride.tripRef : departures[0]?.tripRef) ?? null;
  const trip = useTrip(tripRef);
  const times = useMemo(() => stopTimes(stops, trip.data?.data ?? null), [stops, trip.data]);

  // The pinned journey: from the passenger (or the board stop) to the exit stop's point.
  const origin: LocationInput | null = fix
    ? { kind: "coordinate", latitude: Number(fix.latitude.toFixed(5)), longitude: Number(fix.longitude.toFixed(5)) }
    : boardStop
      ? { kind: "stop", stopId: boardStop.stopId }
      : null;
  const request: PinnedJourneyRequest | null =
    origin && tripRef && boardStop && alightStop
      ? {
          from: origin,
          to: { kind: "coordinate", latitude: alightStop.latitude, longitude: alightStop.longitude },
          departAt: toIsraelIso(new Date()),
          results: 1,
          lang,
          pinnedTrip: { tripRef, boardStopId: boardStop.stopId, alightStopId: alightStop.stopId },
        }
      : null;
  const requestKey = request ? { ...request, departAt: null } : null;
  const journeyQuery = useQuery({
    queryKey: ["pinnedJourney", requestKey],
    queryFn: async ({ signal }) => unwrap(await planPinnedJourney({ ...request!, departAt: toIsraelIso(new Date()) }, signal)),
    enabled: request !== null,
    staleTime: 60_000,
    retry: false,
  });
  const answer = journeyQuery.data ?? null;
  const journey = answer?.data.journeys[0] ?? null;
  const missed = answer?.meta.warnings?.includes(PINNED_TRIP_MISSED_BY_WALK) ?? false;
  const walkLeg = journey?.legs.find((leg) => leg.kind === "walk") ?? null;
  const rideLeg = journey?.legs.find((leg) => leg.kind === "transit") ?? null;
  const walkToStop = walkLeg ? Math.max(1, Math.ceil(walkLeg.durationSeconds / 60)) : fix && boardStop ? walkMinutes(haversineMeters(fix, boardStop)) : null;
  const colour = useLineColour(item);

  const scene = useMemo<MapScene>(() => {
    if (!item || !boardStop || stops.length < 2) return { ...emptyScene, camera: "keep" };
    const coordinates = stops.map((stop) => [stop.longitude, stop.latitude] as LonLat);
    const exit = alight ?? stops.length - 1;
    const leg = (points: LonLat[], tone: MapRouteLeg["tone"]): MapRouteLeg => ({
      kind: "transit",
      mode: item.mode,
      coordinates: points,
      from: points[0]!,
      to: points[points.length - 1]!,
      label: null,
      operatorId: item.operatorId,
      operatorName: item.operatorName,
      tone,
    });
    const route: MapRouteLeg[] = [];
    if (board > 0) route.push(leg(coordinates.slice(0, board + 1), "faded"));
    if (exit < stops.length - 1) route.push(leg(coordinates.slice(exit), "faded"));
    const ridden = (rideLeg?.geometry?.coordinates as LonLat[] | undefined) ?? coordinates.slice(board, exit + 1);
    route.push(leg(ridden, "normal"));
    const fitTo: LonLat[] = [...ridden];
    const walk = walkLeg?.geometry?.coordinates as LonLat[] | undefined;
    if (walkLeg && walk && walk.length >= 2) {
      route.push({ kind: "walk", mode: "WALK", coordinates: walk, from: walk[0]!, to: walk[walk.length - 1]!, label: null });
      fitTo.push(...walk);
    }
    const pins: MapPin[] = [];
    for (let index = board + 1; index < exit; index += 1) {
      pins.push({ id: `stop-${index}`, role: "stop", position: coordinates[index]!, label: stops[index]!.name ?? "" });
    }
    if (alight !== null) pins.push({ id: "exit", role: "destination", position: coordinates[alight]!, label: stops[alight]!.name ?? "" });
    const tags: MapTag[] = [];
    const departs = times[board];
    if (departs) {
      tags.push({ id: "board", position: coordinates[board]!, anchor: "below", kind: "plain", line: { mode: item.mode, label: item.shortName, operatorId: item.operatorId, operatorName: item.operatorName }, text: formatClock(departs, lang) });
    }
    if (alight !== null) {
      const arrives = times[alight];
      tags.push({ id: "exit-tag", position: coordinates[alight]!, anchor: "below", kind: "strong", text: arrives ? `${t("ride.getOff")} ${formatClock(arrives, lang)}` : t("ride.getOff") });
    }
    return {
      ...emptyScene,
      route,
      pins,
      tags,
      stopPins: [{ id: boardStop.stopId, position: coordinates[board]!, selected: true, look: "sign", ariaLabel: t("stop.pin", { stop: boardStop.name ?? "" }) }],
      user: fix ? { position: [fix.longitude, fix.latitude], accuracyMeters: fix.accuracyMeters } : null,
      camera: "fit",
      fitTo,
      cameraKey: `${ride.routeId}|${board}|${exit}|${walkLeg ? "walk" : ""}`,
    };
  }, [item, boardStop, stops, board, alight, rideLeg, walkLeg, times, fix, lang, t, ride.routeId]);
  usePublishScene(scene);

  const failed = line.isError ? line.error : stopLines.isError ? stopLines.error : null;
  if (failed) {
    return (
      <div className="ride">
        <h1 className="visually-hidden">{t("screen.ride")}</h1>
        <ErrorState state={failureState(failed)} onRetry={() => void (line.isError ? line.refetch() : stopLines.refetch())} />
      </div>
    );
  }
  if (!item || !direction || !boardStop) {
    return (
      <div className="ride">
        <h1 className="visually-hidden">{t("screen.ride")}</h1>
        {item && stopLines.data && (!direction || !boardStop) ? <p className="b-mu">{t("ride.expired")}</p> : <Loading />}
      </div>
    );
  }

  const rows = rideRows(stops.length, board, alight, openAfter);
  const choose = (index: number) => onChange({ ...ride, alightStopId: stops[index]!.stopId, tripRef });
  const start = () => {
    if (!journey || !answer) return;
    startActiveTrip({ journey, meta: answer.meta, trips: trip.data && tripRef ? { [tripRef]: trip.data.data } : {} });
    go({ name: "navigate" });
  };
  const continueFrom = () => {
    if (!alightStop) return;
    const place: PlaceChoice = {
      label: alightStop.name ?? "",
      locality: null,
      kind: "stop",
      latitude: alightStop.latitude,
      longitude: alightStop.longitude,
      stopId: alightStop.stopId,
      placeRef: null,
      refGenerationId: null,
    };
    plan.setFrom({ type: "place", place });
    plan.setTo(null);
    go({ name: "search", field: "to" });
  };

  const ridden = alight !== null ? alight - board : 0;
  const rideMinutes = rideLeg ? Math.round(rideLeg.durationSeconds / 60) : alight !== null && times[board] && times[alight] ? Math.round((Date.parse(times[alight]!) - Date.parse(times[board]!)) / 60_000) : null;

  return (
    <div className="ride" style={{ "--sl-line": colour } as CSSProperties}>
      <div className="sl-head">
        <CanvasBadge className="sl-badge-xl" line={{ label: item.shortName, mode: item.mode, operatorId: item.operatorId, operatorName: item.operatorName }} />
        <div className="sl-head__text">
          <h1>{t("line.towards", { place: direction.towards })}</h1>
          <span className="b-mu">
            <bdi>{t("ride.when", { stop: boardStop.name ?? "" })}</bdi>
          </span>
        </div>
      </div>
      <div className="ride-times" role="group" aria-label={t("ride.departures")}>
        {departures.map((item) => (
          <button key={item.tripRef} type="button" className="sl-chip" aria-pressed={item.tripRef === tripRef} onClick={() => onChange({ ...ride, tripRef: item.tripRef })}>
            {formatClock(item.scheduledDeparture, lang)}
          </button>
        ))}
      </div>
      {answer?.meta.mode === "fixture" && <TestDataBanner compact />}

      <ol className="sl-list" aria-label={t("line.stops")}>
        {rows.map((row) => {
          if (row.kind === "more") {
            return (
              <li key="more">
                <button type="button" className="sl-sr sl-sr--fold" aria-expanded={false} onClick={() => setOpenAfter(true)}>
                  <span className="sl-rl">
                    <i className="sl-ln sl-ln--after" />
                  </span>
                  <span className="sl-tx">
                    <span className="b-mu">{row.count === 1 ? t("line.more.one") : t("line.more", { n: row.count })}</span>
                  </span>
                  <StrokeIcon name="down" className="sl-fold-icon" />
                </button>
              </li>
            );
          }
          const stop = stops[row.index]!;
          const time = times[row.index];
          const name = <bdi>{stop.name}</bdi>;
          if (row.role === "board") {
            return (
              <li key={`stop-${row.index}`}>
                <div className="sl-sr ride-board">
                  <span className="sl-rl">
                    <i className={alight === null && row.index === stops.length - 1 ? "sl-ln sl-ln--start sl-ln--end" : "sl-ln sl-ln--start"} />
                    <i className="sl-dt sl-dt--big" />
                  </span>
                  <span className="sl-tx">
                    <span className="sl-nm sl-nm--strong">{name}</span>
                    <span className="b-mu">{walkToStop ? t("ride.boardWalk", { minutes: walkToStop }) : t("ride.board")}</span>
                  </span>
                  {time && <span className="sl-tm sl-tm--strong">{formatClock(time, lang)}</span>}
                </div>
              </li>
            );
          }
          if (row.role === "alight") {
            return (
              <li key={`stop-${row.index}`}>
                <button type="button" className="sl-sr sl-sr--on ride-exit" aria-pressed={true}>
                  <span className="sl-rl">
                    <i className="sl-ln sl-ln--end" />
                    {row.index < stops.length - 1 && <i className="sl-ln sl-ln--start sl-ln--after" />}
                    <i className="sl-dt sl-dt--big sl-dt--end" />
                  </span>
                  <span className="sl-tx">
                    <span className="sl-nm sl-nm--strong">{name}</span>
                    <span className="b-mu">
                      {t("ride.alight", { stops: ridden === 1 ? t("route.stops.one") : t("route.stops", { n: ridden }), minutes: rideMinutes ?? "–" })}
                    </span>
                  </span>
                  {time && <span className="sl-tm sl-tm--strong">{formatClock(time, lang)}</span>}
                </button>
              </li>
            );
          }
          const after = row.role === "after";
          return (
            <li key={`stop-${row.index}`}>
              <button type="button" className="sl-sr" aria-pressed={false} onClick={() => choose(row.index)}>
                <span className="sl-rl">
                  <i className={`sl-ln${after ? " sl-ln--after" : ""}${row.index === stops.length - 1 ? " sl-ln--end" : ""}`} />
                  <i className={`sl-dt${after ? " sl-dt--after" : ""}${row.index === stops.length - 1 ? " sl-dt--end" : ""}`} />
                </span>
                <span className="sl-tx">
                  <span className={after ? "sl-nm sl-nm--after" : "sl-nm"}>{name}</span>
                </span>
                {time && <span className="sl-tm">{formatClock(time, lang)}</span>}
              </button>
            </li>
          );
        })}
      </ol>

      <div className="ride-bar">
        {alight === null ? (
          <p className="b-mu">{t("ride.pick")}</p>
        ) : journeyQuery.isError ? (
          <ErrorState state={failureState(journeyQuery.error)} onRetry={() => void journeyQuery.refetch()} />
        ) : !answer ? (
          <Loading />
        ) : !journey ? (
          // No walk to the board stop within the walking limit (PINNED_TRIP_WALK_UNAVAILABLE).
          <p className="b-mu ride-warning" role="status">
            {answer.meta.warnings?.includes(PINNED_TRIP_WALK_UNAVAILABLE) ? t("ride.walkUnavailable") : t("ride.noJourney")}
          </p>
        ) : (
          <>
            <div className="ride-bar__times">
              <bdi className="ride-bar__figure">{formatClock(journey.timing.scheduledDeparture, lang)}</bdi>
              <span aria-hidden="true">{lang === "he" ? "←" : "→"}</span>
              <bdi className="ride-bar__figure">{formatClock(journey.timing.scheduledArrival, lang)}</bdi>
              <span className="b-mu">
                <bdi>
                  {walkLeg
                    ? t("ride.summaryWalk", { duration: formatDuration(journey.durationSeconds, lang), walk: formatDuration(walkLeg.durationSeconds, lang) })
                    : formatDuration(journey.durationSeconds, lang)}
                </bdi>
              </span>
            </div>
            {missed && (
              <p className="b-mu ride-warning" role="status">
                {t("ride.missed")}
              </p>
            )}
          </>
        )}
        <div className="ride-bar__actions">
          <button type="button" className="sl-btn ride-bar__start" disabled={!journey} onClick={start}>
            {t("compare.start")}
          </button>
          <button type="button" className="sl-btn sl-btn--secondary" disabled={alight === null} onClick={continueFrom}>
            {t("ride.continue")}
          </button>
        </div>
      </div>
    </div>
  );
}
