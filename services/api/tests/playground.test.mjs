import test from "node:test";
import assert from "node:assert/strict";
import { departureInstant, israelWallTime, tomorrowMorning } from "../src/opentransit/api/playground/time.mjs";

test("Israel departure uses the date's offset, independent of host timezone", () => {
  assert.equal(departureInstant("2026-10-01T08:00"), "2026-10-01T08:00:00+03:00");
  assert.equal(departureInstant("2026-10-26T08:00"), "2026-10-26T08:00:00+02:00");
  assert.equal(israelWallTime(new Date("2026-09-30T23:30:00Z")), "2026-10-01T02:30");
});

test("repeated autumn hour requires the passenger's explicit offset", () => {
  assert.throws(() => departureInstant("2026-10-25T01:30"), /occurs twice/);
  assert.equal(departureInstant("2026-10-25T01:30", "+03:00"), "2026-10-25T01:30:00+03:00");
  assert.equal(departureInstant("2026-10-25T01:30", "+02:00"), "2026-10-25T01:30:00+02:00");
});

test("missing spring hour and wrong seasonal offset are rejected", () => {
  assert.throws(() => departureInstant("2026-03-27T02:30"), /does not exist/);
  assert.throws(() => departureInstant("2026-10-01T08:00", "+02:00"), /does not match/);
});

test("invalid calendar values and timestamps cannot reach the API", () => {
  assert.throws(() => departureInstant("2026-02-30T08:00"));
  assert.throws(() => departureInstant("2026-10-01"));
  assert.throws(() => departureInstant("2026-10-01T25:00"));
});

test("default tomorrow is based on the Israel calendar across month and year boundaries", () => {
  assert.equal(tomorrowMorning(new Date("2026-09-30T23:30:00Z")), "2026-10-02T08:00");
  assert.equal(tomorrowMorning(new Date("2026-12-31T19:00:00Z")), "2027-01-01T08:00");
});
