import type { Journey, Leg } from "../../api/types";
import { operatorColour } from "../../lib/lines";
import { formatClock, type Lang } from "../../lib/time";
import { journeyToScene } from "../../map/fromJourney";
import { emptyScene, QUIET_STOPS, type LonLat, type MapPin, type MapRouteLeg, type MapScene, type MapTag } from "../../map/scene";
import { isRail } from "../../plan/chartLayout";
import type { Endpoint } from "../../plan/draft";
import type { ThemeName } from "../../styles/tokens";
import { boardingOf, boardingTag, placeName, shortBadgeLabel, type EndLabels, type T } from "./labels";

// What Compare draws (boards Choose and Step), composed from src/map/fromJourney.ts:
//
// Choose: every option at once. The chosen one in its operators' colours with a line badge
// on each ride, walking as ink dots and its stops ringed; the others faded in their own
// colours, each with a faded tag showing its arrival time, outlined in its main line's
// colour, that chooses it. The destination carries a strong tag with its name.
//
// Step: the chosen option alone, its rides with their badges. A tapped leg is framed
// (fitTo); the stop where the next ride is boarded is a large stop pin with a strong tag
// "בצד הזה · לכיוון …" (only "לכיוון …" until the API gives the side of the road).

const lonLat = (point: { latitude: number; longitude: number }): LonLat => [point.longitude, point.latitude];

/** Before an answer: pins for the ends already known (my location has no position yet). */
export function draftScene(from: Endpoint | null, to: Endpoint | null, ends: EndLabels): MapScene {
  const pins: MapPin[] = [];
  if (from?.type === "place") pins.push({ id: "origin", role: "origin", position: lonLat(from.place), label: ends.from });
  if (to?.type === "place") pins.push({ id: "destination", role: "destination", position: lonLat(to.place), label: ends.to });
  return pins.length === 0 ? emptyScene : { ...emptyScene, pins, camera: "fit" };
}

/** The points of a leg to frame: its line, or its two ends for a time-only walk. */
export function legPoints(leg: Leg): LonLat[] {
  const coords = (leg.geometry?.coordinates ?? []).filter(
    (point): point is [number, number] => typeof point[0] === "number" && typeof point[1] === "number",
  );
  return coords.length >= 2 ? coords.map(([lon, lat]) => [lon, lat] as LonLat) : [lonLat(leg.from), lonLat(leg.to)];
}

/** The middle of a leg's line, where its badge or its option's tag sits. */
function middle(leg: Leg): LonLat {
  const points = legPoints(leg);
  if (points.length === 2) {
    const [a, b] = points as [LonLat, LonLat];
    return [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2];
  }
  return points[Math.floor(points.length / 2)]!;
}

/** The ride an option is known by: its longest ride (or its only walk). */
function mainLeg(journey: Journey): Leg | undefined {
  const rides = journey.legs.filter((leg) => leg.kind === "transit");
  const pool = rides.length > 0 ? rides : journey.legs;
  return pool.reduce<Leg | undefined>((best, leg) => (!best || leg.durationSeconds > best.durationSeconds ? leg : best), undefined);
}

const lineOf = (leg: Leg) => ({ mode: leg.mode, operatorId: leg.transit?.operatorId, operatorName: leg.transit?.operatorName });

/** A ride's line on the map in this theme (as drawn by src/map/layers.ts), else its mode token. */
function lineColour(leg: Leg, theme: ThemeName): string {
  const colour = leg.kind === "transit" ? operatorColour(lineOf(leg)) : null;
  if (colour) return colour.line[theme];
  if (leg.kind !== "transit") return "var(--border-strong)";
  return isRail(leg) ? "var(--mode-rail)" : "var(--mode-bus)";
}

/** A badge on each ride of the chosen option (the map's own text labels are left off). */
function rideBadges(journey: Journey, t: T): MapTag[] {
  return journey.legs.flatMap((leg, index) =>
    leg.kind === "transit"
      ? [
          {
            id: `line-${index}`,
            position: middle(leg),
            kind: "plain" as const,
            anchor: "center" as const,
            line: { mode: leg.mode, label: shortBadgeLabel(leg, t), operatorId: leg.transit?.operatorId, operatorName: leg.transit?.operatorName },
          },
        ]
      : [],
  );
}

function destinationTag(journey: Journey, ends: EndLabels): MapTag[] {
  const last = journey.legs[journey.legs.length - 1];
  const name = last ? placeName(last.to.name, ends) : "";
  return last && name && name !== "END" ? [{ id: "destination", position: lonLat(last.to), kind: "strong", text: name }] : [];
}

const unlabelled = (route: MapRouteLeg[]): MapRouteLeg[] => route.map((leg) => ({ ...leg, label: null }));

export interface SceneText {
  t: T;
  lang: Lang;
  theme: ThemeName;
}

export function chooseScene(
  journeys: readonly Journey[],
  chosen: number,
  ends: EndLabels,
  { t, lang, theme }: SceneText,
  onChoose: (index: number) => void,
): MapScene {
  const route: MapRouteLeg[] = [];
  const tags: MapTag[] = [];
  journeys.forEach((journey, index) => {
    if (index === chosen) return;
    route.push(...unlabelled(journeyToScene(journey).route).map((leg) => ({ ...leg, tone: "faded" as const })));
    const main = mainLeg(journey);
    if (!main) return;
    const time = formatClock(journey.timing.scheduledArrival, lang);
    tags.push({
      id: `option-${index}`,
      position: middle(main),
      kind: "faded",
      text: time,
      accent: lineColour(main, theme),
      ariaLabel: t("compare.map.option", { time }),
      onSelect: () => onChoose(index),
    });
  });
  const picked = journeys[chosen];
  if (!picked) return { ...emptyScene, route, tags, camera: "fit", stops: QUIET_STOPS };
  // The chosen option is drawn last, over the faded ones.
  const own = journeyToScene(picked, { originLabel: ends.from, destinationLabel: ends.to });
  route.push(...unlabelled(own.route));
  tags.push(...rideBadges(picked, t), ...destinationTag(picked, ends));
  return { route, pins: own.pins, user: null, camera: "fit", pick: false, tags, fitTo: null, stops: QUIET_STOPS };
}

/** The ride a leg leads to: itself, or the ride right after a walk; none after the last ride. */
export function boardingRide(journey: Journey, legIndex: number): Leg | null {
  const leg = journey.legs[legIndex];
  if (!leg) return null;
  if (leg.kind === "transit") return leg;
  const next = journey.legs[legIndex + 1];
  return next?.kind === "transit" ? next : null;
}

export function stepScene(journey: Journey, ends: EndLabels, focused: number | null, { t }: SceneText): MapScene {
  const own = journeyToScene(journey, { originLabel: ends.from, destinationLabel: ends.to });
  const tags = rideBadges(journey, t);
  const leg = focused === null ? undefined : journey.legs[focused];
  if (!leg) {
    return { route: unlabelled(own.route), pins: own.pins, user: null, camera: "fit", pick: false, tags: [...tags, ...destinationTag(journey, ends)], fitTo: null, stops: QUIET_STOPS };
  }
  const ride = boardingRide(journey, focused!);
  const stopPins = ride
    ? [{ id: "board", position: lonLat(ride.from), selected: true, ariaLabel: t("route.boardPin", { stop: placeName(ride.from.name, ends) }) }]
    : [];
  const tag = ride ? boardingTag(boardingOf(ride), t) : null;
  if (ride && tag) tags.push({ id: "board", position: lonLat(ride.from), kind: "strong", text: tag });
  if (!ride) tags.push(...destinationTag(journey, ends));
  return {
    route: unlabelled(own.route),
    pins: own.pins,
    user: null,
    camera: "fit",
    pick: false,
    tags,
    stopPins,
    fitTo: legPoints(leg),
    // "כל המסלול" floats over the top of the map while a leg is zoomed.
    topControls: true,
    // Stops only zoomed in close, quieter, so they never compete with the route (design, "During a journey").
    stops: QUIET_STOPS,
  };
}
