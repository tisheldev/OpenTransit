import { describe, expect, it } from "vitest";
import type { Trip } from "../../api/schemas";
import type { Leg } from "../../api/types";
import { translate } from "../../i18n/messages";
import {
  chipLabel,
  daysBetween,
  direction,
  formatShortDay,
  israelDate,
  placeName,
  platformOf,
  relativeDay,
  rideSpeech,
  rideTitle,
  stopsRidden,
  trainNumber,
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
    expect(rideTitle(rail("156"), t)).toBe("רכבת ישראל");
    expect(chipLabel(rail("156"))).toBe("156");
    expect(trainNumber(rail("156"))).toBe("156");
    expect(trainNumber(rail(null))).toBeNull();
    expect(chipLabel(rail(null))).toBeNull();
    expect(direction(rail("156"))).toBeNull();
    expect(rideSpeech(rail("156"), ends, t)).toBe("רכבת ישראל 156 מ־השלום אל חוף הכרמל");
    expect(rideSpeech(rail(null), ends, t)).toBe("רכבת ישראל מ־השלום אל חוף הכרמל");
    expect(rideTitle(rail("156"), t)).not.toContain("חוף הכרמל");
  });

  it("names a bus by number and readable headsign", () => {
    expect(chipLabel(bus("חיפה_מרכזית חוף הכרמל"))).toBe("947");
    expect(rideTitle(bus("חיפה_מרכזית חוף הכרמל"), t)).toBe("לכיוון חיפה · מרכזית חוף הכרמל");
    expect(rideTitle(bus(null), t)).toBe("אגד");
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
