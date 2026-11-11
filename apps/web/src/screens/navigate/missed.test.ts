import { describe, expect, it } from "vitest";
import type { DeparturesPage } from "../../api/schemas";
import { derivedMissedDepartures, derivedWaitJourney, derivedWalkJourney, MISSED_STOP_ID, NEXT_249_AT } from "../../mocks/navigateMissed";
import { initialNavState } from "../../nav/engine";
import { buildSteps } from "../../nav/steps";
import { recordedJourneys, recordedTrips } from "../../nav/testdata";
import { afterExitRequest, destinationInput, exitArrival, missedRide, swapRide, nextSameRoute, waitJourney, waitRequest, walkBeforeRide, walkJourney, walkRequest } from "./missed";

const journey = recordedJourneys[2]!;
const steps = buildSteps(journey, recordedTrips);
const ride = steps[1]!; // bus 249 at 08:38
const departures = (derivedMissedDepartures().body as DeparturesPage).data;

describe("Bus didn't come: which ride", () => {
  it("the ride a walk leads to, or the current ride while waiting; never while riding", () => {
    expect(missedRide(steps, 0, "walking")).toBe(ride);
    expect(missedRide(steps, 1, "waiting")).toBe(ride);
    expect(missedRide(steps, 1, "riding")).toBeNull();
    expect(missedRide(steps, 10, "walking")).toBeNull(); // walk to the destination
    expect(missedRide(steps, 11, "arrived")).toBeNull();
    expect(initialNavState(steps, 0).phase).toBe("walking");
  });
});

describe("Bus didn't come: wait here", () => {
  it("the next departure of the same route at this stop, after the one that did not come", () => {
    const next = nextSameRoute(departures, ride);
    expect(next).toMatchObject({ scheduledDeparture: NEXT_249_AT, routeShortName: "249", stopId: MISSED_STOP_ID });
  });

  it("matches on the line number when an item has no route ID; none when only other lines leave", () => {
    const noRouteId = departures.map((item) => ({ ...item, routeId: null }));
    expect(nextSameRoute(noRouteId, ride)?.scheduledDeparture).toBe(NEXT_249_AT);
    expect(nextSameRoute(departures.filter((item) => item.routeShortName !== "249"), ride)).toBeNull();
  });

  it("the plan leaves from the stop at that departure; the journey that boards it gives the arrival", () => {
    const next = nextSameRoute(departures, ride)!;
    const request = waitRequest(journey, next, "he")!;
    expect(request.from).toEqual({ kind: "stop", stopId: MISSED_STOP_ID });
    expect(request.to).toEqual(destinationInput(journey));
    expect(Date.parse(request.departAt!)).toBe(Date.parse(NEXT_249_AT));
    expect(request.departAt).toMatch(/\+02:00$/);
    const wait = derivedWaitJourney();
    expect(waitJourney([wait], ride, next)).toBe(wait);
    // A plan whose first ride is another bus does not count as waiting for this one.
    expect(waitJourney([derivedWalkJourney()], ride, next)).toBeNull();
  });
});

describe("Bus didn't come: arrival at the exit from the next trip", () => {
  it("the first call at the exit stop after the call that departs here", () => {
    const trip = recordedTrips[ride.ride!.tripRef]!;
    const board = trip.calls.find((call) => call.stopId === MISSED_STOP_ID)!;
    const departure = { ...departures[0]!, callSequence: board.callSequence };
    expect(Date.parse(exitArrival(trip, departure, ride)!)).toBe(Date.parse(ride.scheduledArrival));
    const elsewhere = { ...ride, target: { ...ride.target, stopId: "mot:stop:nowhere" } };
    expect(exitArrival(trip, departure, elsewhere)).toBeNull();
  });
});

describe("Bus didn't come: wait here when no plan boards the next one", () => {
  it("swaps the ride to the next trip and follows it with a plan from the exit", () => {
    const next = nextSameRoute(departures, ride)!;
    const trip = recordedTrips[ride.ride!.tripRef]!;
    const exitAt = "2026-11-02T07:08:00Z";
    const rest = derivedWaitJourney(); // stands in for a plan from the exit stop
    const restFromExit = { ...rest, legs: rest.legs.slice(1) };
    const swapped = swapRide(journey, ride, next, trip, exitAt, restFromExit)!;
    expect(swapped.legs[0]!.transit!.engineTripId).toBe(next.tripRef);
    expect(swapped.legs[0]!.timing).toMatchObject({ scheduledDeparture: next.scheduledDeparture, scheduledArrival: exitAt });
    expect(swapped.legs.slice(1)).toEqual(restFromExit.legs);
    expect(swapped.timing.scheduledArrival).toBe(restFromExit.legs.at(-1)!.timing.scheduledArrival);
    expect(swapped.transfers).toBe(swapped.legs.filter((leg) => leg.kind === "transit").length - 1);
    // A ride that is not the last leg needs the plan after it; without one, no journey.
    expect(swapRide(journey, ride, next, trip, exitAt, null)).toBeNull();
    const request = afterExitRequest(journey, ride, exitAt, "he")!;
    expect(request.from).toEqual({ kind: "stop", stopId: ride.target.stopId });
    expect(request.departAt).toBe("2026-11-02T09:08:00+02:00");
  });
});

describe("Bus didn't come: walk to another stop", () => {
  it("the earliest journey whose first ride boards elsewhere; the walk before it", () => {
    const walk = derivedWalkJourney();
    expect(walkJourney([derivedWaitJourney(), walk], ride)).toBe(walk);
    expect(walkJourney([derivedWaitJourney()], ride)).toBeNull();
    expect(walkBeforeRide(walk)).toBe(180);
  });

  it("plans from the passenger's fix, else from the stop, at the time asked", () => {
    const at = Date.parse("2026-11-02T08:41:00+02:00");
    const fromStop = walkRequest(journey, ride, null, at, "he")!;
    expect(fromStop.from).toEqual({ kind: "coordinate", latitude: ride.from!.latitude, longitude: ride.from!.longitude });
    expect(fromStop.departAt).toBe("2026-11-02T08:41:00+02:00");
    const fromFix = walkRequest(journey, ride, { latitude: 32.07, longitude: 34.77, accuracyMeters: 5, at }, at, "en")!;
    expect(fromFix.from).toEqual({ kind: "coordinate", latitude: 32.07, longitude: 34.77 });
    expect(fromFix.lang).toBe("en");
  });
});
