import { act, fireEvent, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http } from "msw";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fixture } from "../../api/fixtures";
import type { Journey, Metadata } from "../../api/types";
import { he } from "../../i18n/he";
import { setLocationSource, type Fix, type LocationError, type LocationSource } from "../../lib/geolocation";
import { getMapState } from "../../map/scene";
import { respond } from "../../mocks/handlers";
import { server } from "../../mocks/node";
import { getActiveTrip, startActiveTrip } from "../../nav/activeTrip";
import { simulateJourney } from "../../nav/simulate";
import { recordedJourneys, recordedTrips } from "../../nav/testdata";
import recorded from "../../nav/testdata/recorded-oct31a-dizengoff-technion.json";
import { renderApp } from "../../shell/testUtils";
import { go } from "../../router";

const stopPositions = (recorded as unknown as { stopPositions: Record<string, { latitude: number; longitude: number }> }).stopPositions;
const STORAGE_KEY = "opentransit:activeTrip";

/** A location source the test drives by hand. */
function manualSource() {
  const handle: { onFix: ((fix: Fix) => void) | null; onError: ((e: LocationError) => void) | null; stops: number; watches: number } = {
    onFix: null,
    onError: null,
    stops: 0,
    watches: 0,
  };
  const source: LocationSource = {
    current: () => Promise.resolve({ ok: false, error: "unavailable" }),
    watch(onFix, onError) {
      handle.watches += 1;
      handle.onFix = onFix;
      handle.onError = onError;
      return () => {
        handle.stops += 1;
        handle.onFix = null;
      };
    },
  };
  return { source, handle };
}

let restoreSource: () => void = () => {};
let handle: ReturnType<typeof manualSource>["handle"];

beforeEach(() => {
  const made = manualSource();
  handle = made.handle;
  restoreSource = setLocationSource(made.source);
});
afterEach(() => {
  restoreSource();
  vi.useRealTimers();
});

function seed(journey: Journey, trips = recordedTrips, nav?: Record<string, unknown>) {
  startActiveTrip({ journey, meta: {} as Metadata, trips });
  if (nav) {
    const raw = JSON.parse(sessionStorage.getItem(STORAGE_KEY)!);
    raw.nav = nav;
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(raw));
  }
}

const card = () => document.querySelector<HTMLElement>(".step-card")!;
const rows = () => within(screen.getByRole("list")).getAllByRole("button");
const live = () => document.querySelector<HTMLElement>("[aria-live]")!;

/** Answer GET /v1/stops/{id} with the recorded positions (other stops: not found). */
function stopsWithPositions() {
  const base = fixture("recorded-stop");
  server.use(
    http.get("*/v1/stops/:stopId", ({ params }) => {
      const stopId = decodeURIComponent(String(params.stopId));
      const position = stopPositions[stopId];
      if (!position) return respond(fixture("synthetic-problem-stop-not-found"));
      const body = structuredClone(base.body) as { data: Record<string, unknown> };
      Object.assign(body.data, { stopId, ...position });
      return respond({ ...base, body });
    }),
  );
}

describe("Navigate: step card per kind", () => {
  it("walk to stop, ride, same-stop transfer, walk to destination and arrive (journey 2)", async () => {
    seed(recordedJourneys[2]!);
    renderApp("#/navigate");
    // Walk to the stop: instruction, distance and time, the pole's code, the vehicle, its
    // scheduled departure and countdown. Times are scheduled, said once in the header.
    expect(card()).toHaveTextContent("שלב 1 מתוך 12 · זמנים מתוכננים");
    expect(card()).toHaveTextContent("הליכה אל דיזנגוף סנטר/טשרניחובסקי");
    expect(card()).toHaveTextContent("170 מ׳ · 3 דק׳ הליכה · תחנה 25564");
    expect(card()).toHaveTextContent("אוטובוס 249 לכיוון כפר סבא · תחנה מרכזית");
    expect(card()).toHaveTextContent("יציאה 08:38");
    expect(card()).not.toHaveTextContent("(מתוכנן)");
    // A bus never shows a platform (N3), known or not.
    expect(card()).not.toHaveTextContent("רציף");
    // Ride: the exit leads, with its time and a countdown; stops "to your exit", not "left".
    await userEvent.click(rows()[1]!);
    expect(card()).toHaveTextContent("אוטובוס 249");
    expect(card()).toHaveTextContent("לכיוון כפר סבא · תחנה מרכזית");
    expect(card().querySelector(".step-lead")).toHaveTextContent("ירידה ב־ת. רכבת תל אביב - סבידור/דרך נמיר");
    expect(card()).toHaveTextContent(/08:48 · (בעוד|לפני|עכשיו|ביום)/);
    expect(card()).toHaveTextContent("8 תחנות עד הירידה");
    expect(card()).not.toHaveTextContent("נשארו");
    expect(card()).toHaveTextContent("אחר כך: מעבר לאוטובוס 825 ב־08:51 · באותה תחנה · 3 דק׳ למעבר");
    // A zero-length transfer: change at the same stop, with the time to change.
    await userEvent.click(rows()[2]!);
    expect(card()).toHaveTextContent("מעבר באותה תחנה");
    expect(card()).toHaveTextContent("ת. רכבת תל אביב - סבידור/דרך נמיר · תחנה 24068 · 3 דק׳ למעבר");
    expect(card()).not.toHaveTextContent("10 מ׳");
    expect(card()).toHaveTextContent("אוטובוס 825");
    expect(card()).toHaveTextContent(/יציאה 08:51 · (בעוד|יוצא עכשיו|לפני|ביום)/);
    // A walking transfer between two stops of the same name: the stop code tells them apart.
    await userEvent.click(rows()[8]!);
    expect(card()).toHaveTextContent("מעבר: הליכה אל גרנד קניון/שמחה גולן");
    expect(card()).toHaveTextContent("230 מ׳ · 2 דק׳ הליכה · תחנה 42571 · 6 דק׳ למעבר");
    // Walk to the destination: the END placeholder is never shown.
    await userEvent.click(rows()[10]!);
    expect(card()).toHaveTextContent("הליכה אל היעד");
    expect(card()).toHaveTextContent("הגעה 10:37");
    expect(card()).not.toHaveTextContent("END");
    // Arrive: arrival time and Finish; End trip is gone (Finish does it).
    await userEvent.click(rows()[11]!);
    expect(card()).toHaveTextContent("הגעתם אל היעד");
    expect(card()).toHaveTextContent("הגעה 10:37");
    expect(screen.getByRole("button", { name: he["nav.finish"] })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: he["nav.end"] })).toBeNull();
  });

  it("a journey that starts on board: where to board, when it leaves, where to get off", () => {
    seed(recordedJourneys[0]!);
    renderApp("#/navigate");
    expect(card()).toHaveTextContent("אוטובוס 8 לכיוון מסוף הטייסים");
    expect(card()).toHaveTextContent("עלייה ב־דיזנגוף סנטר/דיזנגוף · תחנה 25565");
    expect(card()).toHaveTextContent(/יציאה 08:12 · (בעוד|יוצא עכשיו|לפני|ביום)/);
    expect(card()).toHaveTextContent("ירידה ב־ת. רכבת השלום · 08:18 · 4 תחנות עד הירידה");
    expect(card()).toHaveTextContent("אחר כך: מעבר לרכבת 156 ב־08:21 · 3 דק׳ למעבר");
  });

  it("a time-only transfer and a train (journey 1, English)", async () => {
    seed(recordedJourneys[1]!);
    renderApp("#/navigate", { lang: "en" });
    await userEvent.click(rows()[1]!);
    // Walking to a train: the station is named as one; its code is not shown.
    expect(card()).toHaveTextContent("Transfer: walk to השלום station");
    expect(card()).toHaveTextContent("Train 404 · Get off at חיפה מרכז");
    expect(card()).not.toHaveTextContent("stop 17046");
    await userEvent.click(rows()[2]!);
    // Rail: no empty line label and not named after the exit (that reads as its destination).
    expect(card()).toHaveTextContent("Train 404");
    expect(card()).not.toHaveTextContent("Train to");
    expect(card()).not.toHaveTextContent("towards 404");
    expect(card().querySelector(".step-lead")).toHaveTextContent("Get off at חיפה מרכז");
    // Platform unknown (API-C2): omitted, never "platform unknown".
    expect(card()).not.toHaveTextContent(/platform/i);
    await userEvent.click(rows()[3]!);
    expect(card()).toHaveTextContent("Transfer: walk to תחנת רכבת חיפה מרכז השמונה");
    expect(card()).toHaveTextContent("About 4 min walk · no street path available · stop 41540 · 4 min to change");
    expect(card()).toHaveTextContent("Bus 17");
  });

  it("a rail platform is shown only when the API gives one (N3)", async () => {
    const journey = structuredClone(recordedJourneys[0]!);
    Object.assign(journey.legs[2]!.from, { platformCode: "3" });
    Object.assign(journey.legs[0]!.from, { platformCode: "B" });
    seed(journey);
    renderApp("#/navigate");
    expect(card()).not.toHaveTextContent("רציף");
    await userEvent.click(rows()[1]!);
    expect(card()).toHaveTextContent(/יציאה 08:21 · .* · רציף 3/);
  });

  it("a ride without trip detail shows the exit stop and time, no stop count", async () => {
    const journey = recordedJourneys[0]!;
    const missing = journey.legs[2]!.transit!.engineTripId;
    const trips = { ...recordedTrips };
    delete trips[missing];
    seed(journey, trips);
    renderApp("#/navigate");
    await userEvent.click(rows()[2]!);
    expect(card()).toHaveTextContent("רכבת 156");
    expect(card()).not.toHaveTextContent("תחנות");
    expect(card()).toHaveTextContent("ירידה ב־חוף הכרמל");
    expect(card()).toHaveTextContent(/09:24 · (בעוד|לפני|עכשיו|ביום)/);
    // The missing trip was requested once (the fixture API does not know it).
    await waitFor(() => expect(getActiveTrip()?.tripsRequested).toEqual([missing]));
  });

  it("countdowns: minutes ahead, now, ago, and the day when far ahead", () => {
    const journey = recordedJourneys[2]!;
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(new Date("2026-11-02T08:26:00+02:00"));
    seed(journey);
    const view = renderApp("#/navigate");
    expect(card()).toHaveTextContent("יציאה 08:38 · בעוד 12 דק׳");
    view.unmount();
    vi.setSystemTime(new Date("2026-11-02T08:38:20+02:00"));
    renderApp("#/navigate").unmount();
    vi.setSystemTime(new Date("2026-11-02T08:42:00+02:00"));
    const late = renderApp("#/navigate");
    expect(card()).toHaveTextContent("יציאה 08:38 · לפני 4 דק׳");
    late.unmount();
    vi.setSystemTime(new Date("2026-11-01T08:00:00+02:00"));
    renderApp("#/navigate");
    expect(card()).toHaveTextContent("יציאה 08:38 · ביום ב׳, 2.11");
  });
});

describe("Navigate: checklist", () => {
  it("every row has its scheduled time and a state in its name; rides say where to get off (N2)", () => {
    seed(recordedJourneys[2]!);
    renderApp("#/navigate");
    const list = rows();
    expect(list).toHaveLength(12);
    expect(list[0]).toHaveAccessibleName("השלב הנוכחי: 08:35 הליכה אל דיזנגוף סנטר/טשרניחובסקי · 3 דק׳");
    expect(list[1]).toHaveAccessibleName("בהמשך: 08:38 אוטובוס 249 · 8 תחנות, ירידה ב־ת. רכבת תל אביב - סבידור/דרך נמיר · 08:48");
    expect(list[2]).toHaveAccessibleName("בהמשך: 08:49 מעבר באותה תחנה");
    expect(list[11]).toHaveAccessibleName("בהמשך: 10:37 הגעה אל היעד");
    // Visible too: the time column and a state mark whose shape differs (not colour alone).
    expect(list[1]!.querySelector(".checklist-time")).toHaveTextContent("08:38");
    expect(list[0]!.querySelector(".checklist-mark")).toHaveTextContent("●");
  });
});

describe("Navigate: manual control", () => {
  it("Next step goes through every step to Finish, which clears the trip and goes Home", async () => {
    const journey = recordedJourneys[0]!;
    seed(journey);
    renderApp("#/navigate");
    const total = rows().length;
    for (let i = 1; i < total; i += 1) {
      await userEvent.click(screen.getByRole("button", { name: he["nav.next"] }));
      expect(rows()[i]).toHaveAttribute("aria-current", "step");
      expect(live()).toHaveTextContent(`שלב ${i + 1} מתוך ${total}`);
    }
    expect(JSON.parse(sessionStorage.getItem(STORAGE_KEY)!).nav.stepIndex).toBe(total - 1);
    expect(screen.queryByRole("button", { name: he["nav.next"] })).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: he["nav.finish"] }));
    expect(window.location.hash).toBe("#/");
    expect(sessionStorage.getItem(STORAGE_KEY)).toBeNull();
    expect(getActiveTrip()).toBeNull();
    expect(screen.queryByRole("button", { name: he["home.activeTrip"] })).toBeNull();
  });

  it("tapping a checklist row jumps forward and back (corrects a wrong advance)", async () => {
    seed(recordedJourneys[0]!);
    renderApp("#/navigate");
    await userEvent.click(rows()[4]!);
    expect(rows()[4]).toHaveAttribute("aria-current", "step");
    expect(rows()[0]).toHaveAccessibleName(/^הושלם: /);
    expect(rows()[5]).toHaveAccessibleName(/^בהמשך: /);
    await userEvent.click(rows()[1]!);
    expect(rows()[1]).toHaveAttribute("aria-current", "step");
    expect(rows()[1]).toHaveAccessibleName(/^השלב הנוכחי: /);
    expect(rows()[4]).not.toHaveAttribute("aria-current");
    expect(JSON.parse(sessionStorage.getItem(STORAGE_KEY)!).nav.stepIndex).toBe(1);
  });

  it("Next step is the only bottom action; End trip sits in the card header (N5)", () => {
    seed(recordedJourneys[0]!);
    renderApp("#/navigate");
    const actions = document.querySelector<HTMLElement>(".navigate-actions")!;
    expect(within(actions).getAllByRole("button")).toHaveLength(1);
    expect(within(actions).getByRole("button", { name: he["nav.next"] })).toBeInTheDocument();
    expect(within(card()).getByRole("button", { name: he["nav.end"] })).toBeInTheDocument();
  });

  it("End trip clears storage, stops watching and goes Home without a resume row", async () => {
    seed(recordedJourneys[0]!);
    renderApp("#/navigate");
    expect(handle.watches).toBe(1);
    await userEvent.click(screen.getByRole("button", { name: he["nav.end"] }));
    expect(handle.stops).toBeGreaterThanOrEqual(1);
    expect(handle.onFix).toBeNull();
    expect(sessionStorage.getItem(STORAGE_KEY)).toBeNull();
    expect(window.location.hash).toBe("#/");
    expect(screen.queryByRole("button", { name: he["home.activeTrip"] })).toBeNull();
  });

  it("Back keeps the trip; Home then offers to resume", async () => {
    seed(recordedJourneys[0]!);
    renderApp("#/navigate");
    await userEvent.click(screen.getByRole("button", { name: he["nav.back"] }));
    await waitFor(() => expect(handle.stops).toBe(1));
    // A deep link has no in-app history: Back falls back to Compare (design: App flow).
    await waitFor(() => expect(window.location.hash).toBe("#/compare"));
    expect(getActiveTrip()).not.toBeNull();
    act(() => go({ name: "home" }));
    expect(await screen.findByRole("button", { name: he["home.activeTrip"] })).toBeInTheDocument();
  });

  it("no active trip: a short message and a link Home", () => {
    renderApp("#/navigate");
    expect(screen.getByText(he["nav.noTrip"])).toBeInTheDocument();
    expect(screen.getByRole("link", { name: he["screen.backHome"] })).toHaveAttribute("href", "#/");
  });
});

describe("Navigate: location", () => {
  it("location denied → one short manual banner saying why; steps still advance by hand", async () => {
    seed(recordedJourneys[0]!);
    renderApp("#/navigate");
    act(() => handle.onError!("denied"));
    expect(screen.getAllByText(new RegExp(he["nav.manual"]))).toHaveLength(1);
    expect(screen.getByRole("status")).toHaveTextContent(`${he["nav.loc.denied"]} · ${he["nav.manual"]}`);
    expect(JSON.parse(sessionStorage.getItem(STORAGE_KEY)!).nav.locationMode).toBe("manual");
    await userEvent.click(screen.getByRole("button", { name: he["nav.next"] }));
    expect(rows()[1]).toHaveAttribute("aria-current", "step");
  });

  it("over plain HTTP the banner says location needs HTTPS (the browser refuses it there)", () => {
    const secure = Object.getOwnPropertyDescriptor(window, "isSecureContext");
    Object.defineProperty(window, "isSecureContext", { value: false, configurable: true });
    seed(recordedJourneys[0]!);
    renderApp("#/navigate");
    act(() => handle.onError!("denied"));
    expect(screen.getByRole("status")).toHaveTextContent(`${he["nav.loc.insecure"]} · ${he["nav.manual"]}`);
    if (secure) Object.defineProperty(window, "isSecureContext", secure);
    else delete (window as unknown as { isSecureContext?: boolean }).isSecureContext;
  });

  it("no accepted fix for 60 s → 'no location right now'; nothing advances", () => {
    vi.useFakeTimers({ toFake: ["setInterval", "clearInterval", "Date"] });
    seed(recordedJourneys[0]!);
    renderApp("#/navigate");
    expect(screen.queryByText(new RegExp(he["nav.lost"]))).toBeNull();
    act(() => vi.advanceTimersByTime(66_000));
    expect(screen.getByText(new RegExp(he["nav.lost"]))).toBeInTheDocument();
    expect(rows()[0]).toHaveAttribute("aria-current", "step");
  });

  it("the map shows the current leg and you: fit without a fix, street level at the stop, follow on board", () => {
    const journey = recordedJourneys[0]!;
    seed(journey);
    renderApp("#/navigate");
    // No fix: the current leg (the first ride) and its ends, framed.
    expect(getMapState().scene.camera).toBe("fit");
    expect(getMapState().scene.route).toHaveLength(1);
    expect(getMapState().scene.route[0]!.active).toBe(true);
    expect(getMapState().scene.pins.map((pin) => pin.label)).toEqual(["דיזנגוף סנטר/דיזנגוף", "ת. רכבת השלום"]);
    // A fix at the stop (waiting): recentre on the passenger at street level (Locate).
    const fixes = simulateJourney(journey);
    const before = getMapState().locateRequest;
    act(() => handle.onFix!({ ...fixes[0]!, at: Date.now() }));
    expect(getMapState().scene.camera).toBe("keep");
    expect(getMapState().locateRequest).toBe(before + 1);
    expect(getMapState().scene.user?.position).toEqual([fixes[0]!.longitude, fixes[0]!.latitude]);
    // The stored state never holds a position.
    expect(JSON.stringify(JSON.parse(sessionStorage.getItem(STORAGE_KEY)!).nav)).not.toContain(String(fixes[0]!.latitude));
  });

  it("on board the ride stays framed while the dot moves along it", async () => {
    const journey = recordedJourneys[0]!;
    seed(journey);
    renderApp("#/navigate");
    await userEvent.click(rows()[2]!);
    const onTrain = simulateJourney(journey).find((fix) => fix.at > Date.parse("2026-11-02T08:40:00+02:00"))!;
    const before = getMapState().locateRequest;
    act(() => handle.onFix!({ ...onTrain, at: Date.now() }));
    expect(getMapState().scene.camera).toBe("fit");
    expect(getMapState().scene.user?.position).toEqual([onTrain.longitude, onTrain.latitude]);
    expect(getMapState().locateRequest).toBe(before);
    expect(getMapState().scene.route).toHaveLength(1);
    expect(getMapState().scene.route[0]!.mode.toLowerCase()).toBe("rail");
  });

  it("cues show in the card, are announced and vibrate (call positions fetched at Start)", async () => {
    stopsWithPositions();
    const vibrate = vi.fn(() => true);
    Object.defineProperty(navigator, "vibrate", { value: vibrate, configurable: true });
    const journey = recordedJourneys[0]!;
    seed(journey);
    renderApp("#/navigate");
    await waitFor(() => expect(Object.keys(getActiveTrip()?.callPositions ?? {})).toEqual(["0", "2", "4"]));
    const announced: string[] = [];
    let sawTwo = false;
    let sawLeftTwo = false;
    for (const fix of simulateJourney(journey)) {
      if (!handle.onFix) break; // arrived: watching stopped
      act(() => handle.onFix!(fix));
      const text = live().textContent ?? "";
      if (announced.at(-1) !== text) announced.push(text);
      if (card().textContent?.includes(he["nav.cueTwo"])) {
        sawTwo = true;
        // Progress is measured now: the count says "left" (N4).
        if (card().textContent?.includes("נשארו 2 תחנות")) sawLeftTwo = true;
      }
    }
    expect(sawTwo).toBe(true);
    expect(sawLeftTwo).toBe(true);
    expect(announced.some((text) => text.includes(he["nav.cueTwo"]))).toBe(true);
    expect(announced.some((text) => text.includes(he["nav.cueNext"]))).toBe(true);
    expect(vibrate).toHaveBeenCalled();
    expect(card()).toHaveTextContent("הגעתם אל היעד");
    // Arrived: location watching stopped.
    expect(handle.onFix).toBeNull();
    delete (navigator as unknown as { vibrate?: unknown }).vibrate;
  }, 30_000); // plays a whole journey of fixes through the screen; loaded runners need more than 5 s
});

describe("Navigate: simulated positions", () => {
  it("the labelled toggle plays the journey back and drives the screen through every step", async () => {
    vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout", "setInterval", "clearInterval", "Date"] });
    const journey = recordedJourneys[0]!;
    seed(journey);
    renderApp("#/navigate");
    // The tools are reached at the full sheet; switching on drops it to half for the map.
    fireEvent.click(screen.getByRole("button", { name: /גודל הגיליון|sheet/i }));
    expect(document.querySelector(".sheet")).toHaveAttribute("data-snap", "full");
    fireEvent.change(screen.getByRole("combobox", { name: he["nav.sim.speed"] }), { target: { value: "600" } });
    fireEvent.click(screen.getByRole("checkbox", { name: he["nav.sim.toggle"] }));
    expect(document.querySelector(".sheet")).toHaveAttribute("data-snap", "half");
    expect(screen.getByRole("note")).toHaveTextContent(/^◌ מיקום מדומה, לא אמיתי · שעון \d\d:\d\d · פי 600$/);
    // Countdowns follow the simulated clock (the device clock is days before the trip):
    // playback starts a minute before the first departure.
    expect(screen.getByRole("note")).toHaveTextContent("שעון 08:11");
    expect(card()).toHaveTextContent("יציאה 08:12 · בעוד 1 דק׳");
    expect(getMapState().scene.user).not.toBeNull();
    act(() => vi.advanceTimersByTime(50));
    expect(card()).toHaveTextContent("יציאה 08:12 · יוצא עכשיו");
    const total = rows().length;
    const seen = new Set<number>();
    for (let i = 0; i < 1000 && !card().textContent?.includes("הגעתם אל"); i += 1) {
      act(() => vi.advanceTimersByTime(50));
      seen.add(rows().findIndex((row) => row.getAttribute("aria-current") === "step"));
    }
    expect(card()).toHaveTextContent("הגעתם אל היעד");
    // Every step was current at some point (walks of two minutes included).
    expect([...seen].sort((a, b) => a - b)).toEqual(Array.from({ length: total }, (_, i) => i));
    // Simulated fixes never reach the device-location source.
    expect(handle.onFix).toBeNull();
  }, 30_000); // plays a whole journey back; slow CI runners need more than the 5 s default
});

describe("Navigate: restore and expiry", () => {
  it("reopening resumes at the stored step from storage, with no request", async () => {
    let requests = 0;
    server.events.on("request:start", () => void (requests += 1));
    const journey = recordedJourneys[0]!;
    seed(journey);
    const raw = JSON.parse(sessionStorage.getItem(STORAGE_KEY)!);
    raw.nav = { stepIndex: 3 };
    raw.callPositions = { "0": { status: "failed" }, "2": { status: "failed" }, "4": { status: "failed" } };
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(raw));
    renderApp("#/navigate");
    expect(rows()[3]).toHaveAttribute("aria-current", "step");
    expect(card()).toHaveTextContent("מעבר: הליכה אל ת. רכבת חוף הכרמל");
    await new Promise((resolve) => setTimeout(resolve, 20));
    // Only the shell's status request; nothing for the trip.
    expect(requests).toBeLessThanOrEqual(1);
    server.events.removeAllListeners();
  });

  it("an expired trip (2 h after arrival) is cleared and the app goes Home", async () => {
    const journey = structuredClone(recordedJourneys[0]!);
    journey.timing.scheduledArrival = "2026-10-01T09:00:00+03:00";
    seed(journey);
    renderApp("#/navigate");
    await waitFor(() => expect(window.location.hash).toBe("#/"));
    expect(sessionStorage.getItem(STORAGE_KEY)).toBeNull();
  });
});

describe("Navigate: wake lock", () => {
  it("requests a screen wake lock while navigating and releases it at End trip", async () => {
    const release = vi.fn(() => Promise.resolve());
    const request = vi.fn(() => Promise.resolve({ released: false, release }));
    Object.defineProperty(navigator, "wakeLock", { value: { request }, configurable: true });
    seed(recordedJourneys[0]!);
    renderApp("#/navigate");
    await waitFor(() => expect(request).toHaveBeenCalledWith("screen"));
    await userEvent.click(screen.getByRole("button", { name: he["nav.end"] }));
    await waitFor(() => expect(release).toHaveBeenCalled());
    delete (navigator as unknown as { wakeLock?: unknown }).wakeLock;
  });

  it("without the Wake Lock API nothing happens", () => {
    seed(recordedJourneys[0]!);
    expect(() => renderApp("#/navigate")).not.toThrow();
  });
});
