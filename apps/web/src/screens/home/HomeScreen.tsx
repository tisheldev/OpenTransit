import { useEffect, useId, useMemo, useState } from "react";
import { Icon } from "../../components/ds";
import { useI18n } from "../../i18n/I18nProvider";
import { formatDistance } from "../../lib/format";
import { formatClock } from "../../lib/time";
import { DEFAULT_CENTER } from "../../map/layers";
import { emptyScene, usePublishScene, type MapKnownStop, type MapScene, type MapStopNext } from "../../map/scene";
import { ZOOM_STOPS } from "../../map/stops/geometry";
import { closeStopGroup, openStopGroup, setMapAway, useOpenGroup, useSettledView } from "../../map/stops/view";
import { useActiveTrip, type ActiveTrip } from "../../nav/activeTrip";
import { haversineMeters } from "../../nav/geo";
import { choiceFromSaved } from "../../plan/draft";
import { usePlan } from "../../plan/PlanProvider";
import { go } from "../../router";
import { lastOrigin, useLocalState } from "../../shell/localStore";
import type { SavedPlace } from "../../storage/local";
import { openStop } from "../stop/intent";
import { groupLines, minutesTo, tagLine } from "../stop/lines";
import { useNow } from "../stop/parts";
import { usePassengerFix } from "../stop/passenger";
import { useHomeStops, WALK_RING_METERS } from "./homeStops";
import { HomeSheet } from "./HomeSheet";
import { type RideOrigin } from "./nextRide";
import { StopGroupList } from "./StopGroupList";
import "./home.css";

// Home — board 1 (user, 11 November 2026: "Stops near you are pins that carry their next
// departure. Tap a pin and the board below switches to that stop. The dashed ring marks a
// 5-minute walk."). It replaces C01's From/To fields, chips and recents. The panel: one
// search field, Home and Work with the next departure toward each, then the selected stop
// and its departures. Storage renders first; requests start after the first paint, and
// nothing waits for a location fix (without one, Home centres on the last place).

/**
 * Board 10: the map counts as panned away from the passenger (or Home's centre) once the
 * centre it settled on is farther than the 5-minute walk; then "Near you" becomes "In this
 * area" around that centre. A smaller move keeps the area where it was, so a nudge does
 * not ask again.
 */
const AWAY_METERS = WALK_RING_METERS;
const AREA_STEP_METERS = 150;

/** True after the first paint, so Home renders from storage before any request. */
function useAfterFirstPaint(): boolean {
  const [painted, setPainted] = useState(false);
  useEffect(() => {
    const id = window.setTimeout(() => setPainted(true), 0);
    return () => window.clearTimeout(id);
  }, []);
  return painted;
}

/** The engine names coordinate ends "START"/"END": never show those as a place. */
function journeyEndName(trip: ActiveTrip): string | null {
  if (trip.labels?.destination) return trip.labels.destination;
  const legs = trip.journey.legs as Array<{ to?: { name?: string | null } }>;
  const name = legs[legs.length - 1]?.to?.name?.trim();
  return name && name !== "END" && name !== "START" ? name : null;
}

/** The trip in progress leads, in the main button's colours. */
function ActiveTripCard({ trip }: { trip: ActiveTrip }) {
  const { t, lang } = useI18n();
  const detailId = useId();
  const place = journeyEndName(trip);
  const arrival = trip.journey.timing.scheduledArrival;
  const time = Number.isFinite(Date.parse(arrival)) ? formatClock(arrival, lang) : null;
  let detail: string | null = null;
  if (time) detail = place ? t("home.activeTrip.detail", { place, time }) : t("home.activeTrip.detailNoPlace", { time });
  return (
    <button
      type="button"
      className="active-trip"
      aria-describedby={detail ? detailId : undefined}
      onClick={() => go({ name: "navigate" })}
    >
      <Icon name="route" className="active-trip-icon" />
      <span className="active-trip-text">
        <span className="active-trip-title">{t("home.activeTrip")}</span>
        {detail && (
          <span id={detailId} className="active-trip-detail tabular" aria-hidden="true">
            <bdi>{detail}</bdi>
          </span>
        )}
      </span>
      <Icon name="chevron" className="active-trip-go" />
    </button>
  );
}


export function HomeScreen() {
  const { t, lang } = useI18n();
  const painted = useAfterFirstPaint();
  // Minutes on the map's tags: once a minute, so the map is not reframed more often.
  const now = useNow(60_000);
  const fix = usePassengerFix();
  const local = useLocalState();
  const trip = useActiveTrip();
  const { draft, setTo } = usePlan();

  // Where Home looks: the passenger, else the last start they chose, else the last place.
  const fallback = useMemo(() => {
    const origin = lastOrigin();
    if (origin) return { latitude: origin.latitude, longitude: origin.longitude, stopId: origin.stopId };
    const recent = local.recents[0];
    return recent ? { latitude: recent.latitude, longitude: recent.longitude, stopId: recent.stopId } : null;
  }, [local.recents]);
  const centre = useMemo(
    () => (fix ? { latitude: fix.latitude, longitude: fix.longitude } : (fallback ?? { latitude: DEFAULT_CENTER[1], longitude: DEFAULT_CENTER[0] })),
    [fix, fallback],
  );
  const origin: RideOrigin | null = fix ? { latitude: fix.latitude, longitude: fix.longitude, stopId: null } : fallback;

  // Board 10: panned away from the passenger, the sheet's stops follow the map ("In this
  // area"); board 9: an opened group asks around its stops. Still one nearby request.
  const settled = useSettledView();
  const group = useOpenGroup();
  const awayNow =
    !group &&
    settled !== null &&
    settled.zoom >= ZOOM_STOPS &&
    haversineMeters({ latitude: settled.center[1], longitude: settled.center[0] }, centre) > AWAY_METERS;
  const [area, setArea] = useState<{ latitude: number; longitude: number } | null>(null);
  if (!awayNow && area !== null) setArea(null);
  if (awayNow && settled) {
    const at = { latitude: settled.center[1], longitude: settled.center[0] };
    if (area === null || haversineMeters(area, at) > AREA_STEP_METERS) setArea(at);
  }
  const away = awayNow && area !== null;
  useEffect(() => setMapAway(away), [away]);
  useEffect(
    () => () => {
      setMapAway(false);
      closeStopGroup();
    },
    [],
  );
  const groupCentre = useMemo(() => (group ? { latitude: group.center[1], longitude: group.center[0] } : null), [group]);
  const groupRadius =
    group && groupCentre ? Math.min(1000, Math.max(...group.stops.map((stop) => haversineMeters(stop, groupCentre))) + 60) : null;
  // The one request: around the group, else the map's area, else the passenger.
  const nearby = useHomeStops(groupCentre ?? (away && area ? area : centre), painted, groupRadius !== null ? Math.round(groupRadius) : undefined);
  const { stops } = nearby;
  const stopIds = useMemo(() => stops.map((stop) => stop.stopId), [stops]);
  // The nearest stop's pin is the selected one; any pin or tag opens its own stop in one tap
  // (user, 12 November 2026). The sheet lists lines across the nearby stops (HomeSheet).
  const selectedIndex = 0;
  const selected = stops[selectedIndex] ?? null;

  // The stops layer draws every stop (marker G); Home names the chosen one (the stop the
  // panel is about, or the row picked in an opened group) and gives the tags their next
  // line, from its one nearby answer. Any sign or tag opens its own stop in one tap.
  const scene = useMemo<MapScene>(() => {
    // Every stop of the one nearby answer may carry a tag (the layer shows a couple).
    const next: Record<string, MapStopNext> = {};
    for (const entry of nearby.all) {
      const line = groupLines(entry.departures ?? [], entry.routes, { trainLabel: t("stop.train"), now: new Date(0), max: 1 })[0];
      if (!line) continue;
      const minutes = minutesTo(line.next, now);
      next[entry.stop.stopId] = { line: tagLine(line), minutes, text: minutes <= 0 ? t("time.now") : t("stop.minutes", { minutes }) };
    }
    const known: MapKnownStop[] = nearby.all.map(({ stop }) => ({ stopId: stop.stopId, name: stop.name, latitude: stop.latitude, longitude: stop.longitude }));
    const user = fix ? { position: [fix.longitude, fix.latitude] as [number, number], accuracyMeters: fix.accuracyMeters } : null;
    return {
      ...emptyScene,
      user,
      ring: fix ? { center: [fix.longitude, fix.latitude], radiusMeters: WALK_RING_METERS } : null,
      // Panned away or into a group, the camera is the passenger's: never reframed.
      camera: away || group ? "keep" : "fit",
      // Frame once per set of stops and position: the minutes on the tags tick every minute
      // and must not undo the passenger's own panning.
      cameraKey: `home:${stopIds.join(",")}:${fix ? `${fix.latitude.toFixed(4)},${fix.longitude.toFixed(4)}` : "none"}`,
      focus: { center: [centre.longitude, centre.latitude], zoom: 16 },
      stops: {
        mode: "full",
        chosenStopId: group ? group.picked : (selected?.stopId ?? null),
        next,
        known,
        onSelectStop: (stopId) => openStop(stopId),
        onOpenGroup: (members) => openStopGroup(members),
        openGroup: group ? group.stops.map((stop) => stop.stopId) : null,
      },
    };
  }, [nearby.all, stopIds, selected, fix, centre, now, t, away, group]);
  usePublishScene(scene);

  const travelTo = (saved: SavedPlace) => {
    setTo({ type: "place", place: choiceFromSaved(saved) });
    // Without a start yet, ask for it next (Search From then opens Compare).
    go(draft.from === null ? { name: "search", field: "from" } : { name: "compare" });
  };

  // Board 9: an opened group fills the sheet with its stops (Back closes it).
  if (group) return <StopGroupList group={group} nearby={nearby} now={now} />;

  return (
    <div className="home">
      <h1 className="visually-hidden">{t("home.title")}</h1>

      {trip && <ActiveTripCard trip={trip} />}

      <HomeSheet
        nearby={nearby}
        centre={away && area ? area : centre}
        origin={origin}
        painted={painted}
        homePlace={local.home}
        workPlace={local.work}
        savedStops={local.savedStops}
        savedLines={local.savedLines}
        onTravel={travelTo}
        area={away && area ? { distanceText: fix ? formatDistance(haversineMeters(fix, area), lang) : null } : null}
      />
    </div>
  );
}
