import { describe, expect, it } from "vitest";
import { en } from "../../i18n/en";
import { he } from "../../i18n/he";
import type { MessageKey } from "../../i18n/messages";
import { initialNavState, type NavState } from "../../nav/engine";
import { buildSteps } from "../../nav/steps";
import { recordedJourneys, recordedTrips } from "../../nav/testdata";
import {
  isSameStop,
  readableHeadsign,
  relativeText,
  rideName,
  ridePlatform,
  rideStopsText,
  rowText,
  stopCodeFor,
  thenText,
  transferWindowSeconds,
  walkTargetName,
  type T,
} from "./describe";

const tFor =
  (messages: Record<string, string>): T =>
  (key: MessageKey, values = {}) =>
    messages[key]!.replace(/\{(\w+)\}/g, (_, name: string) => String(values[name] ?? `{${name}}`));
const t = tFor(he);
const tEn = tFor(en);
const labels = { origin: "דיזנגוף סנטר", destination: "הטכניון" };

const j0 = buildSteps(recordedJourneys[0]!, recordedTrips);
const j1 = buildSteps(recordedJourneys[1]!, recordedTrips);
const j2 = buildSteps(recordedJourneys[2]!, recordedTrips);

describe("ride names", () => {
  it("buses by line and readable headsign; trains by number, never by the exit", () => {
    expect(rideName(j2[1]!, t)).toBe("אוטובוס 249");
    expect(readableHeadsign("כפר סבא_תחנה מרכזית")).toBe("כפר סבא · תחנה מרכזית");
    expect(rideName(j0[2]!, t)).toBe("רכבת 156");
    expect(rideName(j0[2]!, tEn)).toBe("Train 156");
  });

  it("a platform only for rail, only when known", () => {
    expect(ridePlatform(j0[2]!)).toBeNull();
    const withPlatform = { ...j0[2]!, ride: { ...j0[2]!.ride!, platform: "3" } };
    expect(ridePlatform(withPlatform)).toBe("3");
    const bus = { ...j0[0]!, ride: { ...j0[0]!.ride!, platform: "B" } };
    expect(ridePlatform(bus)).toBeNull();
  });

  it("stop codes for bus poles, not stations; stations named as such", () => {
    expect(stopCodeFor(j2[0]!.target, j2[1])).toBe("25564");
    expect(stopCodeFor(j0[1]!.target, j0[2])).toBeNull();
    expect(walkTargetName(j0[1]!, j0[2], labels, t)).toBe("תחנת הרכבת השלום");
    expect(walkTargetName(j0[3]!, j0[4], labels, t)).toBe("ת. רכבת חוף הכרמל");
  });
});

describe("stops on a ride (N4)", () => {
  const riding = (step: number, stopsLeft: number | null): NavState => ({ ...initialNavState(j2, 0), stepIndex: step, phase: "riding", stopsLeft });

  it("counts to the exit until progress is measured, then counts down", () => {
    expect(rideStopsText(j2[1]!, riding(1, 8), t)).toBe("8 תחנות עד הירידה");
    expect(rideStopsText(j2[1]!, riding(1, 2), t)).toBe("נשארו 2 תחנות");
    expect(rideStopsText(j2[1]!, riding(1, 1), t)).toBe("נשארה תחנה אחת");
    // Another step's state never counts this ride down.
    expect(rideStopsText(j2[1]!, riding(3, 2), t)).toBe("8 תחנות עד הירידה");
  });

  it("is hidden without trip detail (never guessed)", () => {
    const noDetail = buildSteps(recordedJourneys[0]!, {});
    expect(rideStopsText(noDetail[2]!, riding(2, null), t)).toBeNull();
  });
});

describe("transfers", () => {
  it("same stop by ID or a zero-length walk; not a walk between two stops of one name", () => {
    expect(isSameStop(j2[2]!)).toBe(true); // 0 m, two stop IDs with one code
    expect(isSameStop(j2[4]!)).toBe(true); // the same stop ID
    expect(isSameStop(j2[8]!)).toBe(false); // 228 m
    expect(isSameStop(j1[3]!)).toBe(false); // time-only walk (distance unknown)
  });

  it("time to change is the next departure minus the previous arrival", () => {
    expect(transferWindowSeconds(j2, 2)).toBe(180);
    expect(transferWindowSeconds(j2, 6)).toBe(360);
    expect(transferWindowSeconds(j2, 0)).toBeNull(); // walk to the first stop
    expect(transferWindowSeconds(j2, 1)).toBeNull(); // a ride
  });

  it("the ride card says what follows", () => {
    expect(thenText(j2, 1, labels, t, "he")).toBe("אחר כך: מעבר לאוטובוס 825 ב־08:51 · באותה תחנה · 3 דק׳ למעבר");
    expect(thenText(j0, 0, labels, t, "he")).toBe("אחר כך: מעבר לרכבת 156 ב־08:21 · 3 דק׳ למעבר");
    expect(thenText(j2, 9, labels, t, "he")).toBe("אחר כך: הליכה אל הטכניון · 4 דק׳");
    expect(thenText(j2, 11, labels, t, "he")).toBeNull();
  });
});

describe("countdowns", () => {
  const at = "2026-11-02T08:38:00+02:00";
  const base = Date.parse(at);
  it.each([
    [-12 * 60_000, "בעוד 12 דק׳"],
    [-61_000, "בעוד 2 דק׳"],
    [-30_000, "יוצא עכשיו"],
    [30_000, "יוצא עכשיו"],
    [4 * 60_000, "לפני 4 דק׳"],
    [-26 * 3600_000, "ביום ב׳, 2.11"],
  ])("%d ms from the departure: %s", (offset, text) => {
    expect(relativeText(at, base + offset, t, "he", "departure")).toBe(text);
  });

  it("arrival says now; English reads naturally", () => {
    expect(relativeText(at, base, t, "he", "arrival")).toBe("עכשיו");
    expect(relativeText(at, base - 5 * 60_000, tEn, "en", "arrival")).toBe("in 5 min");
    expect(relativeText(at, base + 5 * 60_000, tEn, "en", "arrival")).toBe("5 min ago");
    expect(relativeText(at, base - 26 * 3600_000, tEn, "en", "arrival")).toBe("on Mon 2 Nov");
  });
});

describe("checklist rows (N2)", () => {
  it("time, what to do, and for rides where and when to get off", () => {
    expect(rowText(j2[0]!, labels, t, "he", j2[1])).toEqual({ time: "08:35", main: "הליכה אל דיזנגוף סנטר/טשרניחובסקי · 3 דק׳", sub: null });
    expect(rowText(j2[1]!, labels, t, "he")).toEqual({ time: "08:38", main: "אוטובוס 249 · 8 תחנות", sub: "ירידה ב־ת. רכבת תל אביב - סבידור/דרך נמיר · 08:48" });
    expect(rowText(j2[2]!, labels, t, "he").main).toBe("מעבר באותה תחנה");
    expect(rowText(j2[6]!, labels, t, "he").main).toBe("מעבר · 2 דק׳ הליכה");
    expect(rowText(j2[11]!, labels, t, "he")).toEqual({ time: "10:37", main: "הגעה אל הטכניון", sub: null });
    const noDetail = buildSteps(recordedJourneys[0]!, {});
    expect(rowText(noDetail[2]!, labels, t, "he").main).toBe("רכבת 156");
  });

  it("English isolates a Hebrew name so the time after it stays after it", () => {
    expect(rowText(j2[1]!, labels, tEn, "en").sub).toBe("Get off at ⁨ת. רכבת תל אביב - סבידור/דרך נמיר⁩ · 08:48");
    expect(rowText(j2[10]!, { origin: null, destination: "הטכניון" }, tEn, "en").main).toBe("Walk to ⁨הטכניון⁩ · 4 min");
    // Hebrew lines are right-to-left already: no marks added.
    expect(rowText(j2[1]!, labels, t, "he").sub).not.toMatch(/[⁨⁩]/);
  });
});
