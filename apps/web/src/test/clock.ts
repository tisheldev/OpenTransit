import { vi } from "vitest";

/**
 * 2 November 2026, 08:00 Israel time: just before the first recorded journey in
 * `nav/testdata` leaves (08:12). The recorded fixtures are dated and an active trip expires
 * two hours after its arrival, so tests that start a trip from them must not read the wall
 * clock, or they fail once the calendar passes the fixture date.
 */
export const RECORDED_NOW = new Date("2026-11-02T08:00:00+02:00");

/**
 * Fake only `Date`, set to `at`. A later `vi.useFakeTimers({ toFake })` in the test keeps
 * that time while faking more; `vi.useRealTimers()` undoes it.
 */
export function pinClock(at: Date = RECORDED_NOW): void {
  vi.useFakeTimers({ toFake: ["Date"] });
  vi.setSystemTime(at);
}
