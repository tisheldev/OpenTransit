import { describe, expect, it } from "vitest";
import type { Trip } from "../../api/schemas";
import type { Leg } from "../../api/types";
import { translate } from "../../i18n/messages";
import { placeName, platformOf, stopsRidden, trainDestination, transitTitle } from "./labels";

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

describe("route labels", () => {
  it("replaces the engine's START / END with the passenger's labels", () => {
    expect(placeName("START", ends)).toBe("המיקום שלי");
    expect(placeName("END", ends)).toBe("טכניון");
    expect(placeName("השלום", ends)).toBe("השלום");
  });

  it("names a train by its destination: a text headsign, else where the leg ends (never the train number)", () => {
    expect(transitTitle(rail("156"), ends, t)).toBe("רכבת לחוף הכרמל");
    expect(trainDestination(rail("נהריה"), ends)).toBe("נהריה");
    expect(trainDestination(rail(null), ends)).toBe("חוף הכרמל");
  });

  it("names a bus by number and readable headsign", () => {
    const bus = { ...rail("חיפה_מרכזית חוף הכרמל"), mode: "bus", transit: { routeShortName: "947", headsign: "חיפה_מרכזית חוף הכרמל" } } as Leg;
    expect(transitTitle(bus, ends, t)).toBe("קו 947 לכיוון חיפה · מרכזית חוף הכרמל");
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
