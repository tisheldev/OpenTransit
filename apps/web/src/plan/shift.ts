import type { Journey, JourneyRequest } from "../api/types";
import { israelWallTime, shiftMinutes } from "../lib/time";
import type { When } from "./draft";
import type { TimeOverride } from "./journeyQuery";

// Earlier / Later (design: Domain model; CU13). Each tap re-sends one shifted request and
// the new answer replaces the chart; nothing is merged. The API has no cursor.
//
// - Later: departAt = the latest shown departure + 1 minute.
// - Earlier: arriveBy = the earliest shown arrival − 1 minute.
// - With nothing shown (no route), the asked time moves by NO_ROUTE_STEP_MIN instead.
//
// Compare stores the shifted time as the plan's "when" (whenFromOverride), so the time
// chip always shows the time the options answer, and the request sent is the same.

export const NO_ROUTE_STEP_MIN = 60;

export function laterTime(journeys: readonly Journey[], asked: JourneyRequest | null = null): TimeOverride | null {
  if (journeys.length === 0) {
    const base = asked?.departAt ?? asked?.arriveBy;
    return base ? { departAt: shiftMinutes(base, NO_ROUTE_STEP_MIN) } : null;
  }
  const latest = Math.max(...journeys.map((j) => Date.parse(j.timing.scheduledDeparture)));
  return { departAt: shiftMinutes(new Date(latest).toISOString(), 1) };
}

export function earlierTime(journeys: readonly Journey[], asked: JourneyRequest | null = null): TimeOverride | null {
  if (journeys.length === 0) {
    const base = asked?.arriveBy ?? asked?.departAt;
    return base ? { arriveBy: shiftMinutes(base, -NO_ROUTE_STEP_MIN) } : null;
  }
  const earliest = Math.min(...journeys.map((j) => Date.parse(j.timing.scheduledArrival)));
  return { arriveBy: shiftMinutes(new Date(earliest).toISOString(), -1) };
}

/**
 * A shifted time as the plan's "when": the same instant as an Israel wall time with its
 * explicit offset, so a time repeated by the autumn change is never re-asked.
 */
export function whenFromOverride(time: TimeOverride): When {
  const instant = "departAt" in time ? time.departAt : time.arriveBy;
  const offset = instant.slice(-6);
  return {
    mode: "departAt" in time ? "depart_at" : "arrive_by",
    wall: israelWallTime(new Date(instant)),
    offset: offset === "+03:00" || offset === "+02:00" ? offset : "auto",
  };
}
