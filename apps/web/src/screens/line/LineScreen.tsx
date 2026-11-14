import { useMemo, useState, type CSSProperties } from "react";
import { ApiFailure } from "../../api/result";
import { LineBadge } from "../../components/ds";
import { ErrorState, Loading } from "../../components/states";
import { useI18n } from "../../i18n/I18nProvider";
import { formatClock } from "../../lib/time";
import { lineMode } from "../../map/layers";
import { emptyScene, usePublishScene, type LonLat, type MapPin, type MapScene, type MapTag } from "../../map/scene";
import { haversineMeters, type LatLon } from "../../nav/geo";
import { useTrip } from "../../plan/queries";
import { toggleSavedLine, useSavedLines } from "../../storage/saved";
import { directionChevron, minutesTo, shortHeadsign } from "../stop/lines";
import { openStop } from "../stop/intent";
import { useNow, withFigure } from "../stop/parts";
import { usePassengerFix } from "../stop/passenger";
import { useBoardSheet } from "./boardSheet";
import { useLine, useRailStations, useRouteDepartures, useRouteFirstStop, useStopLinesAll } from "./data";
import { StrokeIcon } from "./icons";
import { lineIntent, openRide } from "./intent";
import {
  anchorIndex,
  directionsOf,
  headwayMinutes,
  lineDepartures,
  paddedBounds,
  railAt,
  stopRows,
  stopTimes,
  walkMinutes,
  type Direction,
} from "./lineModel";
import { RailBadge, useLineColour, useModeName } from "./parts";
import "./line.css";
import "./stopline.css";

// A line — canvas board Line (4), 14 November 2026: the whole route on the map, a switch
// between its two directions (a list when it has more), and every stop with its time on the
// next trip, opening at the stop nearest the passenger with the earlier stops folded and
// the later ones folded beyond a few. Stops where a train can be caught carry the train
// badge. Tap a later stop to ride there (board 5); tap an earlier one to board there.

/** The sheet's share of the screen on board 4 (596 of 844 px). */
const SHEET_SHARE = 596 / 844;
/** Times after the first shown at the highlighted stop ("18:49 · 19:01"). */
const LATER_TIMES = 2;

const failureState = (error: unknown) => (error instanceof ApiFailure ? error.state : "unexpected");

export function LineScreen({ lineKey }: { lineKey: string }) {
  const { t, lang } = useI18n();
  const now = useNow();
  const fix = usePassengerFix();
  const [intent] = useState(() => lineIntent(lineKey));
  useBoardSheet(SHEET_SHARE);

  const line = useLine(lineKey);
  const item = line.data?.data ?? null;
  // The line's stops come from a stop's lines with every pattern: the stop the passenger
  // came from, else the first stop of the line's first route.
  const firstStop = useRouteFirstStop(intent?.stopId ? null : (item?.routeIds[0] ?? null));
  const sourceStop = intent?.stopId ?? firstStop.data ?? null;
  const stopLines = useStopLinesAll(sourceStop);
  const directions = useMemo(() => (item && stopLines.data ? directionsOf(item, stopLines.data.data) : []), [item, stopLines.data]);

  const [routeId, setRouteId] = useState<string | null>(intent?.routeId ?? null);
  const direction: Direction | null = directions.find((entry) => entry.routeId === routeId) ?? directions[0] ?? null;
  // Where the list opens: the passenger's nearest stop, else the stop they came from (or,
  // in the other direction, the one nearest to it across the road).
  const cameFrom = useMemo<LatLon | null>(() => {
    const id = intent?.stopId;
    const stop = id ? directions.flatMap((entry) => entry.stops).find((candidate) => candidate.stopId === id) : null;
    return stop ? { latitude: stop.latitude, longitude: stop.longitude } : null;
  }, [directions, intent]);
  const [boardAt, setBoardAt] = useState<{ routeId: string; index: number } | null>(null);
  const [open, setOpen] = useState<{ routeId: string | null; earlier: boolean; later: boolean }>({ routeId: null, earlier: false, later: false });
  const stops = useMemo(() => direction?.stops ?? [], [direction]);
  const anchor = direction
    ? boardAt?.routeId === direction.routeId
      ? boardAt.index
      : anchorIndex(stops, fix ?? cameFrom, [intent?.stopId])
    : 0;
  const anchorStop = stops[anchor] ?? null;
  const folds = open.routeId === direction?.routeId ? open : { earlier: false, later: false };

  const departuresQuery = useRouteDepartures(anchorStop?.stopId ?? null, direction?.routeId ?? null);
  const departures = useMemo(
    () => (direction ? lineDepartures(departuresQuery.data?.data ?? [], direction.routeId, new Date(departuresQuery.dataUpdatedAt)) : []),
    [departuresQuery.data, departuresQuery.dataUpdatedAt, direction],
  );
  const upcoming = departures.filter((item) => Date.parse(item.scheduledDeparture) >= now.getTime() - 30_000);
  const tripRef = (intent?.tripRef && upcoming.some((item) => item.tripRef === intent.tripRef) ? intent.tripRef : upcoming[0]?.tripRef) ?? null;
  const trip = useTrip(tripRef);
  const times = useMemo(() => stopTimes(stops, trip.data?.data ?? null), [stops, trip.data]);
  const headway = headwayMinutes(departures);
  const stations = useRailStations(useMemo(() => paddedBounds(stops), [stops]));
  const rail = useMemo(() => railAt(stops, stations.data?.data ?? []), [stops, stations.data]);

  const saved = useSavedLines().some((entry) => entry.lineKey === lineKey);
  const colour = useLineColour(item);
  const modeName = useModeName(item?.mode ?? "bus");

  const scene = useMemo<MapScene>(() => {
    if (!item || !direction || stops.length < 2) return { ...emptyScene, camera: "keep" };
    const coordinates = stops.map((stop) => [stop.longitude, stop.latitude] as LonLat);
    const last = stops.length - 1;
    const pins: MapPin[] = stops.flatMap((stop, index) =>
      index === anchor ? [] : [{ id: `stop-${index}-${stop.stopId}`, role: index === last ? ("destination" as const) : ("stop" as const), position: coordinates[index]!, label: stop.name ?? "" }],
    );
    const tags: MapTag[] = [];
    const ahead = coordinates.slice(Math.min(anchor, last - 1));
    const mark = directionChevron(ahead);
    if (mark) {
      tags.push({ id: "direction", position: mark.position, kind: "plain", anchor: "center", glyph: { kind: "chevron", bearing: mark.bearing }, ariaLabel: t("stop.direction", { line: item.shortName }) });
    }
    const end = coordinates[last]!;
    tags.push({
      id: "end",
      position: end,
      anchor: end[1] > (anchorStop?.latitude ?? end[1]) ? "below" : "above",
      kind: "strong",
      line: { mode: item.mode, label: item.shortName, operatorId: item.operatorId, operatorName: item.operatorName },
      text: direction.towards,
      ariaLabel: t("stop.line.end", { line: item.shortName, headsign: direction.towards }),
    });
    return {
      ...emptyScene,
      route: [
        {
          kind: "transit",
          mode: item.mode,
          coordinates,
          from: coordinates[0]!,
          to: end,
          label: null,
          operatorId: item.operatorId,
          operatorName: item.operatorName,
          tone: "normal",
        },
      ],
      pins,
      tags,
      stopPins: anchorStop
        ? [{ id: anchorStop.stopId, position: [anchorStop.longitude, anchorStop.latitude], selected: true, look: "sign", ariaLabel: t("stop.pin", { stop: anchorStop.name ?? "" }) }]
        : [],
      user: fix ? { position: [fix.longitude, fix.latitude], accuracyMeters: fix.accuracyMeters } : null,
      camera: "fit",
      fitTo: coordinates,
      cameraKey: `${lineKey}|${direction.routeId}`,
    };
  }, [item, direction, stops, anchor, anchorStop, fix, lineKey, t]);
  usePublishScene(scene);

  const failed = line.isError ? line.error : stopLines.isError ? stopLines.error : firstStop.isError ? firstStop.error : null;
  if (failed) {
    return (
      <div className="line">
        <h1 className="visually-hidden">{t("screen.line")}</h1>
        <ErrorState state={failureState(failed)} onRetry={() => void (line.isError ? line.refetch() : stopLines.isError ? stopLines.refetch() : firstStop.refetch())} />
      </div>
    );
  }
  if (!item || !direction) {
    return (
      <div className="line">
        <h1 className="visually-hidden">{item ? t("line.title", { line: item.shortName }) : t("screen.line")}</h1>
        {item && !line.isPending && !stopLines.isPending && directions.length === 0 && !firstStop.isPending ? <p className="b-mu">{t("line.notFound")}</p> : <Loading />}
      </div>
    );
  }

  const meta = [item.operatorName, modeName, headway ? t("line.every", { minutes: headway }) : null].filter(Boolean).join(" · ");
  const rows = stopRows(stops.length, anchor, folds);
  const last = stops.length - 1;
  const nearMeters = fix && anchorStop ? haversineMeters(fix, anchorStop) : null;
  const first = upcoming[0] ?? null;
  const later = upcoming.slice(1, 1 + LATER_TIMES);
  const setFold = (part: "earlier" | "later") => setOpen({ ...folds, routeId: direction.routeId, [part]: true });

  const tapStop = (index: number) => {
    const stop = stops[index]!;
    if (index > anchor && anchorStop) {
      openRide({ lineKey, routeId: direction.routeId, boardStopId: anchorStop.stopId, alightStopId: stop.stopId, tripRef });
    } else if (index < anchor) {
      setBoardAt({ routeId: direction.routeId, index });
    } else {
      openStop(stop.stopId);
    }
  };

  return (
    <div className="line" style={{ "--sl-line": colour } as CSSProperties}>
      <div className="sl-head">
        <LineBadge
          className="sl-badge-xl"
          mode={lineMode(item.mode) === "rail" ? "rail" : "bus"}
          label={item.shortName}
          line={{ mode: item.mode, operatorId: item.operatorId, operatorName: item.operatorName }}
        />
        <div className="sl-head__text">
          <h1>{t("line.title", { line: item.shortName })}</h1>
          <span className="b-mu">
            <bdi>{meta}</bdi>
          </span>
        </div>
        <button
          type="button"
          className="sl-icbtn"
          aria-label={t("line.save")}
          aria-pressed={saved}
          onClick={() =>
            toggleSavedLine({
              lineKey,
              shortName: item.shortName,
              operatorId: item.operatorId,
              operatorName: item.operatorName ?? "",
              mode: item.mode,
              headsign: direction.towards,
              savedAt: new Date().toISOString(),
            })
          }
        >
          <StrokeIcon name="star" filled={saved} />
        </button>
      </div>

      {directions.length > 1 && (
        <div className={directions.length > 2 ? "line-seg line-seg--list" : "line-seg"} role="group" aria-label={t("line.directions")}>
          {directions.map((entry) => (
            <button key={entry.routeId} type="button" aria-pressed={entry.routeId === direction.routeId} onClick={() => setRouteId(entry.routeId)}>
              {t("line.towards", { place: entry.towards })}
            </button>
          ))}
        </div>
      )}

      <ol className="sl-list" aria-label={t("line.stops")}>
        {rows.map((row) => {
          if (row.kind === "earlier") {
            const origin = shortHeadsign(stops[0]?.name) ?? stops[0]?.name ?? direction.origin;
            return (
              <li key="earlier">
                <button type="button" className="sl-sr sl-sr--fold" aria-expanded={false} onClick={() => setFold("earlier")}>
                  <span className="sl-rl">
                    <i className="sl-ln sl-ln--faint" />
                  </span>
                  <span className="sl-tx">
                    <span className="b-mu">{row.count === 1 ? t("line.earlier.one", { origin }) : t("line.earlier", { n: row.count, origin })}</span>
                  </span>
                  <StrokeIcon name="down" className="sl-fold-icon" />
                </button>
              </li>
            );
          }
          if (row.kind === "more") {
            return (
              <li key="more">
                <button type="button" className="sl-sr sl-sr--fold" aria-expanded={false} onClick={() => setFold("later")}>
                  <span className="sl-rl">
                    <i className="sl-ln sl-ln--faint" />
                  </span>
                  <span className="sl-tx">
                    <span className="b-mu">{row.count === 1 ? t("line.more.one") : t("line.more", { n: row.count })}</span>
                  </span>
                  <StrokeIcon name="down" className="sl-fold-icon" />
                </button>
              </li>
            );
          }
          const { index } = row;
          const stop = stops[index]!;
          const lineClass = ["sl-ln", index === 0 ? "sl-ln--start" : "", index === last ? "sl-ln--end" : ""].filter(Boolean).join(" ");
          const railKind = rail.get(stop.stopId);
          if (index === anchor) {
            return (
              <li key={`stop-${index}`}>
                <button type="button" className="sl-sr sl-sr--on line-here" onClick={() => tapStop(index)}>
                  <span className="sl-rl">
                    <i className={lineClass} />
                    <i className={`sl-dt sl-dt--big${index === last ? " sl-dt--end" : ""}`} />
                  </span>
                  <span className="sl-tx">
                    <span className="sl-tx sl-tx--row">
                      <span className="sl-nm sl-nm--strong">
                        <bdi>{stop.name}</bdi>
                      </span>
                      {railKind && <RailBadge kind={railKind} />}
                    </span>
                    {nearMeters !== null && nearMeters <= 2000 && (
                      <span className="b-mu">{withFigure(t("line.nearest"), <bdi className="num">{walkMinutes(nearMeters)}</bdi>)}</span>
                    )}
                  </span>
                  {first && (
                    <span className="line-here__when">
                      <span className="b-mu">{withFigure(t("line.in"), <b className="num line-here__figure">{minutesTo(first.scheduledDeparture, now)}</b>)}</span>
                      {later.length > 0 && <span className="b-mu num line-here__later">{later.map((item) => formatClock(item.scheduledDeparture, lang)).join(" · ")}</span>}
                    </span>
                  )}
                </button>
              </li>
            );
          }
          const time = times[index];
          return (
            <li key={`stop-${index}`}>
              <button type="button" className="sl-sr" onClick={() => tapStop(index)}>
                <span className="sl-rl">
                  <i className={lineClass} />
                  <i className={`sl-dt${index === last ? " sl-dt--end" : ""}`} />
                </span>
                <span className="sl-tx sl-tx--row">
                  <span className={index === last ? "sl-nm sl-nm--strong" : "sl-nm"}>
                    <bdi>{stop.name}</bdi>
                  </span>
                  {railKind && <RailBadge kind={railKind} />}
                </span>
                {time && index > anchor && <span className="sl-tm">{formatClock(time, lang)}</span>}
              </button>
            </li>
          );
        })}
      </ol>
      <p className="b-mu sl-note">{t("line.note")}</p>
    </div>
  );
}
