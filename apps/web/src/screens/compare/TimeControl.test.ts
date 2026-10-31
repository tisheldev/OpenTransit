import { describe, expect, it } from "vitest";
import { translate } from "../../i18n/messages";
import { shiftWall, whenSummary } from "./TimeControl";

const he = (key: Parameters<typeof translate>[1], values?: Record<string, string | number>) => translate("he", key, values);
const en = (key: Parameters<typeof translate>[1], values?: Record<string, string | number>) => translate("en", key, values);
const now = new Date("2026-10-31T20:00:00+02:00");

describe("time chip", () => {
  it("says now, or the mode and time with the day when it is not today", () => {
    expect(whenSummary({ mode: "now" }, he, "he", now)).toEqual({ head: "עכשיו", day: null });
    expect(whenSummary({ mode: "depart_at", wall: "2026-10-31T22:30", offset: "auto" }, he, "he", now)).toEqual({
      head: "יציאה 22:30",
      day: null,
    });
    expect(whenSummary({ mode: "arrive_by", wall: "2026-11-01T09:00", offset: "auto" }, he, "he", now)).toEqual({
      head: "הגעה עד 09:00",
      day: "מחר",
    });
    expect(whenSummary({ mode: "depart_at", wall: "2026-11-02T08:00", offset: "auto" }, he, "he", now)).toEqual({
      head: "יציאה 08:00",
      day: "יום ב׳, 2.11",
    });
    expect(whenSummary({ mode: "depart_at", wall: "2026-11-02T08:00", offset: "auto" }, en, "en", now)).toEqual({
      head: "Depart 08:00",
      day: "Mon 2 Nov",
    });
  });
});

describe("quick shifts", () => {
  it("move an Israel wall time across midnight and through the clock changes", () => {
    expect(shiftWall("2026-11-02T08:00", 15)).toBe("2026-11-02T08:15");
    expect(shiftWall("2026-10-31T23:50", 30)).toBe("2026-11-01T00:20");
    // Spring forward (27 Mar 2026, 02:00 → 03:00): 01:30 + 60 min is 03:30 on the wall.
    expect(shiftWall("2026-03-27T01:30", 60)).toBe("2026-03-27T03:30");
    // Autumn back (25 Oct 2026, 02:00 → 01:00): from the first 00:30, 60 min later is the first 01:30.
    expect(shiftWall("2026-10-25T00:30", 60)).toBe("2026-10-25T01:30");
  });
});
