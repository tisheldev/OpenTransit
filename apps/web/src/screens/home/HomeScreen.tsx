import { useEffect, useId, useMemo, useState } from "react";
import { ApiFailure } from "../../api/result";
import { Icon } from "../../components/ds";
import { Empty, ErrorState, Loading } from "../../components/states";
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
import { lastOrigin, useLocalState, type SavedSlot } from "../../shell/localStore";
import type { SavedPlace } from "../../storage/local";
import { openStop } from "../stop/intent";
import { groupLines, minutesTo, tagLine } from "../stop/lines";
import { Badge, Distance, Due, useNow, withFigure } from "../stop/parts";
import { usePassengerFix } from "../stop/passenger";
import { HOME_ROWS, useHomeStops, WALK_RING_METERS, type NearStop } from "./homeStops";
import { useNextRide, type RideOrigin } from "./nextRide";
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
/** An opened group asks for up to 12 stops around its centre (the nearby endpoint's most). */
const GROUP_STOPS = 12;

const failureState = (error: unknown) => (error instanceof ApiFailure ? error.state : "unexpected");

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

/** Home or Work: plan to it, with the next departure toward it; unset, set it. */
function PlaceCard({
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
  // Each card is named by everything it shows ("בית 66 בעוד 4 דק׳"), so the name always
  // holds the visible text (speech input, WCAG 2.5.3).
  if (!saved) {
    return (
      <button type="button" className="b-card" onClick={() => go({ name: "search", field: slot })}>
        <span className="b-card__title">{title}</span>
        <span className="b-card__next b-mu">{t(slot === "home" ? "home.setHome" : "home.setWork")}</span>
      </button>
    );
  }
  const minutes = next ? minutesTo(next.departure, now) : null;
  const shown = next && minutes !== null && minutes > 0 && minutes < 100;
  return (
    <button type="button" className="b-card" onClick={() => onTravel(saved)}>
      <span className="b-card__title">{title}</span>
      {shown && (
        <span className="b-card__next">
          <Badge line={next} />
          <span className="b-mu">{withFigure(t("home.inMinutes"), <bdi className="num b-big">{minutes}</bdi>)}</span>
        </span>
      )}
    </button>
  );
}

const stopName = (stop: NearStop) => stop.name ?? stop.code ?? stop.stopId;

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
  const nearby = useHomeStops(
    groupCentre ?? (away && area ? area : centre),
    painted,
    groupRadius !== null ? { radiusMeters: Math.round(groupRadius), stops: GROUP_STOPS } : null,
  );
  const { stops, departures } = nearby;
  const stopIds = useMemo(() => stops.map((stop) => stop.stopId), [stops]);
  // The panel lists the nearest stop's departures; any pin or tag opens its own stop in one
  // tap (user, 12 November 2026).
  const selectedIndex = 0;
  const selected = stops[selectedIndex] ?? null;

  // One row per line. Departures are asked from "now" and refreshed every minute, so a
  // departure already gone drops out with the next answer.
  const lines = useMemo(
    () =>
      stops.map((_, index) =>
        groupLines(departures[index] ?? [], nearby.routes[index] ?? [], {
          trainLabel: t("stop.train"),
          now: new Date(0),
          max: HOME_ROWS,
        }),
      ),
    [stops, departures, nearby.routes, t],
  );
  const names = useMemo(() => stops.map(stopName), [stops]);

  // The stops layer draws every stop (marker G); Home names the chosen one (the stop the
  // panel is about, or the row picked in an opened group) and gives the tags their next
  // line, from its one nearby answer. Any sign or tag opens its own stop in one tap.
  const scene = useMemo<MapScene>(() => {
    const next: Record<string, MapStopNext> = {};
    stops.forEach((stop, index) => {
      const line = lines[index]?.[0];
      if (!line) return;
      const minutes = minutesTo(line.next, now);
      next[stop.stopId] = { line: tagLine(line), minutes, text: minutes <= 0 ? t("time.now") : t("stop.minutes", { minutes }) };
    });
    const known: MapKnownStop[] = stops.map((stop) => ({ stopId: stop.stopId, name: stop.name, latitude: stop.latitude, longitude: stop.longitude }));
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
  }, [stops, stopIds, selected, lines, fix, centre, now, t, away, group]);
  usePublishScene(scene);

  const travelTo = (saved: SavedPlace) => {
    setTo({ type: "place", place: choiceFromSaved(saved) });
    // Without a start yet, ask for it next (Search From then opens Compare).
    go(draft.from === null ? { name: "search", field: "from" } : { name: "compare" });
  };

  const selectedLines = selected ? (lines[selectedIndex] ?? []) : [];
  const stopHeadingId = useId();

  // Board 9: an opened group fills the sheet with its stops (Back closes it).
  if (group) return <StopGroupList group={group} nearby={nearby} now={now} />;

  return (
    <div className="home">
      <h1 className="visually-hidden">{t("home.title")}</h1>

      {trip && <ActiveTripCard trip={trip} />}

      <button type="button" className="b-field" onClick={() => go({ name: "search", field: "to" })}>
        <Icon name="search" />
        {t("home.search")}
      </button>

      <section aria-label={t("home.saved")}>
        <div className="b-cards">
          <PlaceCard slot="home" saved={local.home} origin={origin} enabled={painted} now={now} onTravel={travelTo} />
          <PlaceCard slot="work" saved={local.work} origin={origin} enabled={painted} now={now} onTravel={travelTo} />
        </div>
      </section>

      {away && area && (
        <div className="b-head home-area">
          <h2>{t("stops.area")}</h2>
          {fix && <span className="b-mu">{t("stops.area.distance", { distance: formatDistance(haversineMeters(fix, area), lang) ?? "" })}</span>}
        </div>
      )}

      <section className="home-stop" aria-labelledby={selected ? stopHeadingId : undefined} aria-label={selected ? undefined : t("home.stops")}>
        {!painted || nearby.pending ? null : nearby.error ? (
          <ErrorState state={failureState(nearby.error)} onRetry={() => nearby.refetch()} />
        ) : !selected ? (
          <p className="b-mu home-none">{t("home.stops.none")}</p>
        ) : (
          <>
            <div className="b-head">
              <h2 id={stopHeadingId}>
                <bdi>{names[selectedIndex]}</bdi>
              </h2>
              {fix && <Distance meters={haversineMeters(fix, selected)} />}
            </div>
            {nearby.states[selectedIndex] === "pending" ? (
              <Loading />
            ) : nearby.states[selectedIndex] === "error" ? (
              <ErrorState state={failureState(nearby.errors[selectedIndex])} onRetry={() => nearby.refetch()} />
            ) : nearby.states[selectedIndex] === "unavailable" ? (
              <ErrorState state="temporarily_unavailable" />
            ) : selectedLines.length === 0 ? (
              <Empty kind="noDepartures" />
            ) : (
              <ul className="home-rows" aria-label={t("home.departures", { stop: names[selectedIndex]! })}>
                {selectedLines.map((line) => (
                  <li key={line.key}>
                    <button type="button" className="b-row" onClick={() => openStop(selected.stopId, line.key)}>
                      <Badge line={line} />
                      <span className="b-row__name">
                        <bdi>{line.headsign ?? ""}</bdi>
                      </span>
                      <Due instant={line.next} now={now} />
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </>
        )}
      </section>

      <p className="b-mu home-note">{t("stop.scheduled")}</p>
    </div>
  );
}
