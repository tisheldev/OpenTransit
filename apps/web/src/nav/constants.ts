// Every navigation threshold in one place (design: Navigation engine, "Initial
// thresholds"). Initial values, to be tuned in S6 against simulated and real rides.

export const NAV_THRESHOLDS = {
  /** Ignore a fix whose reported accuracy is worse than this. */
  maxFixAccuracyMeters: 100,
  /** Ignore a fix older than this (relative to the caller's `now`). */
  maxFixAgeMs: 10_000,
  /** "At the boarding stop": within this of the stop (walk → waiting). */
  atStopMeters: 40,
  /** Boarding needs the stop to have been reached, or approached within this. */
  boardingNearStopMeters: 60,
  /** Boarding can be detected from this long before the scheduled departure. */
  boardingWindowBeforeDepartureMs: 60_000,
  /** Boarding detected: the fix is more than this from the boarding stop … */
  boardingAwayFromStopMeters: 120,
  /** … and within this of the ride leg's geometry. */
  boardingOnRideGeometryMeters: 80,
  /** Exit reached: within this of the exit stop. */
  exitReachedMeters: 50,
  /** Destination reached: within this of the final `to`. */
  destinationReachedMeters: 30,
  /** No accepted fix for this long → "location lost" hint (nothing advances). */
  locationLostAfterMs: 60_000,

  // Engine guards added in S6 (not in the design's table; same spirit).
  /** A ride fix farther than this from the leg geometry does not move ride progress. */
  rideCorridorMeters: 80,
  /** Exit reached also needs the fix no more than this behind the exit stop along the
   * ride, so a looping route passing near the exit early does not end the ride. */
  exitBehindToleranceMeters: 150,
} as const;

export type NavThresholds = typeof NAV_THRESHOLDS;
