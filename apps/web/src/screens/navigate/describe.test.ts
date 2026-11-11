import { describe, expect, it } from "vitest";
import { en } from "../../i18n/en";
import { he } from "../../i18n/he";
import type { MessageKey } from "../../i18n/messages";
import { buildSteps } from "../../nav/steps";
import { recordedJourneys, recordedTrips } from "../../nav/testdata";
import {
  badgeLabel,
  badgeMode,
  countdownMinutes,
  countdownText,
  isSameStop,
  makesIt,
  readableHeadsign,
  relativeText,
  rideName,
  ridePlatform,
  rowText,
  stopCodeFor,
  transferWindowSeconds,
  walkLeft,
  walkLeftText,
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

describe("walking (board 4)", () => {
  const walk = j2[0]!; // 172 m in 3 min to דיזנגוף סנטר/טשרניחובסקי, bus 249 at 08:38
  const ride = j2[1]!;

  it("without a fix, the walk as planned; with one, what is left at the step's own pace", () => {
    expect(walkLeft(walk, null)).toEqual({ meters: 172, seconds: 180, measured: false });
    expect(walkLeftText(walkLeft(walk, null), t, "he")).toBe("3 דק׳ הליכה · 170 מ׳");
    const atTarget = walkLeft(walk, { latitude: walk.target.latitude, longitude: walk.target.longitude });
    expect(atTarget).toMatchObject({ meters: 0, seconds: 0, measured: true });
    // A walk the journey gives no street path for says so, never a distance.
    expect(walkLeftText(walkLeft(j1[3]!, null), tEn, "en")).toBe("About 4 min walk · no street path available");
  });

  it("makes it only when the rest of the walk ends by the scheduled departure", () => {
    const departs = Date.parse(ride.scheduledDeparture);
    expect(makesIt(180, ride, departs - 180_000)).toBe(true);
    expect(makesIt(180, ride, departs - 179_000)).toBe(false);
  });

  it("the stop pin's countdown: minutes up to an hour, words otherwise", () => {
    const departs = Date.parse(ride.scheduledDeparture);
    expect(countdownText(ride.scheduledDeparture, departs - 4 * 60_000, t, "he", "departure")).toBe("4 דק׳");
    expect(countdownText(ride.scheduledDeparture, departs, t, "he", "departure")).toBe("יוצא עכשיו");
    expect(countdownText(ride.scheduledDeparture, departs + 3 * 60_000, t, "he", "departure")).toBe("לפני 3 דק׳");
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

describe("countdown and badges", () => {
  it("the countdown figure is whole minutes from one minute to an hour ahead, else none", () => {
    const at = "2026-11-02T08:38:00+02:00";
    const now = (iso: string) => Date.parse(iso);
    expect(countdownMinutes(at, now("2026-11-02T08:26:00+02:00"))).toBe(12);
    expect(countdownMinutes(at, now("2026-11-02T08:26:30+02:00"))).toBe(12);
    expect(countdownMinutes(at, now("2026-11-02T08:37:00+02:00"))).toBe(1);
    expect(countdownMinutes(at, now("2026-11-02T08:37:30+02:00"))).toBeNull();
    expect(countdownMinutes(at, now("2026-11-02T08:42:00+02:00"))).toBeNull();
    expect(countdownMinutes(at, now("2026-11-02T07:38:00+02:00"))).toBeNull();
  });

  it("badges come from the ride; nothing is guessed", () => {
    expect(badgeMode(j2[1]!)).toBe("bus");
    expect(badgeLabel(j2[1]!, t)).toBe("249");
    expect(badgeMode(j0[2]!)).toBe("rail");
    expect(badgeLabel(j0[2]!, t)).toBe("רכבת");
  });
});
