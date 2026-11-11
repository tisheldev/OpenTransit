import { describe, expect, it } from "vitest";
import type { Trip } from "../../api/schemas";
import type { Leg } from "../../api/types";
import { translate } from "../../i18n/messages";
import {
  badgeLabel,
  boardingOf,
  boardingTag,
  compactDuration,
  daysBetween,
  direction,
  formatShortDay,
  israelDate,
  placeName,
  platformOf,
  relativeDay,
  rideSpeech,
  rideName,
  shortBadgeLabel,
  stopCountOf,
  splitFirstSentence,
  stopsRidden,
  trainNumber,
  untilText,
} from "./labels";

const ends = { from: "המיקום שלי", to: "טכניון" };
const t = (key: Parameters<typeof translate>[1], values?: Record<string, string | number>) => translate("he", key, values);

const rail = (headsign: string | null, extra: Record<string, unknown> = {}): Leg =>
  ({
    kind: "transit",
    mode: "rail",
    from: { name: "השלום", stopId: "mot:stop:37350", ...extra },
    to: { name: "חוף הכרמל", stopId: "mot:stop:37376" },
    timing: { scheduledDeparture: "2026-11-02T08:21:00+02:00", scheduledArrival: "2026-11-02T09:24:00+02:00" },
    transit: { routeShortName: "", headsign, operatorName: "רכבת ישראל" },
  }) as unknown as Leg;

const bus = (headsign: string | null): Leg =>
  ({ ...rail(headsign), mode: "bus", transit: { routeShortName: "947", headsign, operatorName: "אגד" } }) as Leg;

describe("route labels", () => {
  it("replaces the engine's START / END with the passenger's labels", () => {
    expect(placeName("START", ends)).toBe("המיקום שלי");
    expect(placeName("END", ends)).toBe("טכניון");
    expect(placeName("השלום", ends)).toBe("השלום");
  });

  it("names a train by its operator and number, read from boarding to exit (never by the exit alone)", () => {
    expect(rideName(rail("156"), t)).toBe("רכבת ישראל");
    expect(badgeLabel(rail("156"), t)).toBe("רכבת 156");
    expect(shortBadgeLabel(rail("156"), t)).toBe("רכבת");
    expect(trainNumber(rail("156"))).toBe("156");
    expect(trainNumber(rail(null))).toBeNull();
    expect(badgeLabel(rail(null), t)).toBe("רכבת");
    expect(direction(rail("156"))).toBeNull();
    expect(rideSpeech(rail("156"), ends, t)).toBe("רכבת ישראל 156 מ־השלום אל חוף הכרמל");
    expect(rideSpeech(rail(null), ends, t)).toBe("רכבת ישראל מ־השלום אל חוף הכרמל");
    expect(rideName(rail("156"), t)).not.toContain("חוף הכרמל");
  });

  it("names a bus by number and readable headsign", () => {
    expect(badgeLabel(bus("חיפה_מרכזית חוף הכרמל"), t)).toBe("947");
    expect(shortBadgeLabel(bus("חיפה_מרכזית חוף הכרמל"), t)).toBe("947");
    // Board Step: the headsign beside the badge, without "לכיוון".
    expect(rideName(bus("חיפה_מרכזית חוף הכרמל"), t)).toBe("חיפה · מרכזית חוף הכרמל");
    expect(rideName(bus(null), t)).toBe("אגד");
    expect(rideSpeech(bus("חיפה_מרכזית חוף הכרמל"), ends, t)).toBe(
      "קו 947 לכיוון חיפה · מרכזית חוף הכרמל מ־השלום אל חוף הכרמל",
    );
  });

  it("shows a platform only when the API provides one", () => {
    expect(platformOf(rail("156"))).toBeNull();
    expect(platformOf(rail("156", { platformCode: "" }))).toBeNull();
    expect(platformOf(rail("156", { platformCode: "3" }))).toBe("3");
  });

  it("counts stops ridden from the trip's calls, or not at all", () => {
    const call = (ordinal: number, stopId: string, at: string | null) => ({
      callSequence: ordinal + 1,
      ordinal,
      stopId,
      scheduledArrival: at,
      scheduledDeparture: at,
      pickupType: 0,
      dropOffType: 0,
    });
    const trip = {
      calls: [
        call(0, "mot:stop:1", "2026-11-02T05:48:00Z"),
        call(4, "mot:stop:37350", "2026-11-02T06:21:00Z"),
        call(5, "mot:stop:2", "2026-11-02T06:40:00Z"),
        call(9, "mot:stop:37376", "2026-11-02T07:24:00Z"),
      ],
    } as unknown as Trip["data"];
    expect(stopsRidden(rail("156"), trip)).toBe(5);
    expect(stopsRidden(rail("156"), undefined)).toBeNull();
    expect(stopsRidden(rail("156"), { ...trip, calls: trip.calls.slice(0, 2) })).toBeNull();
  });
});

describe("days", () => {
  it("reads dates on the Israel calendar, whatever the host zone", () => {
    expect(israelDate("2026-11-06T22:30:00Z")).toBe("2026-11-07");
    expect(israelDate("2026-11-06T21:59:00Z")).toBe("2026-11-06");
    expect(daysBetween("2026-10-31", "2026-11-02")).toBe(2);
  });

  it("names today, tomorrow, then a short weekday and date", () => {
    expect(relativeDay("2026-10-31", "2026-10-31", "he", t)).toBe("היום");
    expect(relativeDay("2026-11-01", "2026-10-31", "he", t)).toBe("מחר");
    expect(relativeDay("2026-11-07", "2026-10-31", "he", t)).toBe("שבת, 7.11");
    expect(formatShortDay("2026-11-02T08:00:00+02:00", "en")).toBe("Mon 2 Nov");
  });
});

describe("design text", () => {
  it("writes durations compactly: minutes under an hour, then h:mm", () => {
    expect(compactDuration(47 * 60)).toEqual({ value: "47", unit: "min" });
    expect(compactDuration(59 * 60 + 1)).toEqual({ value: "1:00", unit: "h" });
    expect(compactDuration(6300)).toEqual({ value: "1:45", unit: "h" });
    expect(compactDuration(2 * 3600 + 5 * 60)).toEqual({ value: "2:05", unit: "h" });
  });

  it("splits a banner message into its bold first sentence and the rest", () => {
    expect(splitFirstSentence("אין חיבור ל־OpenTransit. בדקו את החיבור לאינטרנט.")).toEqual({
      first: "אין חיבור ל־OpenTransit.",
      rest: "בדקו את החיבור לאינטרנט.",
    });
    expect(splitFirstSentence("השירות אינו זמין זמנית.")).toEqual({ first: "השירות אינו זמין זמנית.", rest: "" });
    // A date's dots are not a sentence end.
    expect(splitFirstSentence("That time is outside the timetable. Choose between 1.10 and 30.10.").rest).toBe(
      "Choose between 1.10 and 30.10.",
    );
  });
});

describe("boarding side and direction", () => {
  it("says only the direction until the API gives the side of the road", () => {
    const boarding = boardingOf(bus("מסוף רידינג"));
    expect(boarding).toEqual({ side: null, direction: "מסוף רידינג", bearing: null });
    expect(boardingTag(boarding, t)).toBe("לכיוון מסוף רידינג");
  });

  it("fills in the side and the bearing from the API's boarding, naming the stop ridden to (board Step)", () => {
    const leg = { ...bus("מסוף רידינג"), to: { name: "סבידור מרכז", stopId: "s:2" }, boarding: { bearingDegrees: 30.8, stopSide: "right", towards: "מסוף רידינג", stopCount: 7 } } as unknown as Leg;
    const boarding = boardingOf(leg);
    expect(boarding).toEqual({ side: "right", direction: "סבידור מרכז", bearing: 30.8 });
    expect(boardingTag(boarding, t)).toBe("בצד הזה · לכיוון סבידור מרכז");
    // A side the API could not work out: the headsign alone.
    const unknown = { ...leg, boarding: { stopSide: null, stopSideUnavailableReason: "no_geometry" } } as unknown as Leg;
    expect(boardingTag(boardingOf(unknown), t)).toBe("לכיוון מסוף רידינג");
  });

  it("counts stops from the API, else its intermediate stops, else the trip detail", () => {
    const leg = bus("x");
    expect(stopCountOf({ ...leg, boarding: { stopCount: 7 } } as unknown as Leg, undefined)).toBe(7);
    expect(stopCountOf({ ...leg, intermediateStops: [{}, {}] } as unknown as Leg, undefined)).toBe(3);
    expect(stopCountOf(leg, undefined)).toBeNull();
  });

  it("says nothing for a train known only by its number", () => {
    expect(boardingTag(boardingOf(rail("156")), t)).toBeNull();
  });
});

describe("how long until an option leaves", () => {
  const now = new Date("2026-11-02T08:00:00+02:00");
  it("counts minutes, then hours, on the same Israel day; names another day", () => {
    expect(untilText("2026-11-02T08:04:20+02:00", now, "he", t)).toBe("בעוד 4 דק׳");
    expect(untilText("2026-11-02T08:00:20+02:00", now, "he", t)).toBe("עכשיו");
    expect(untilText("2026-11-02T09:35:00+02:00", now, "he", t)).toBe("בעוד 1:35 שע׳");
    expect(untilText("2026-11-03T08:10:00+02:00", now, "he", t)).toBe("מחר");
    expect(untilText("2026-11-02T08:04:20+02:00", now, "en", (key, values) => translate("en", key, values))).toBe("in 4 min");
  });
  it("says nothing once it has left", () => {
    expect(untilText("2026-11-02T07:59:00+02:00", now, "he", t)).toBeNull();
  });
});
