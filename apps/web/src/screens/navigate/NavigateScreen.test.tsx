import { act, fireEvent, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http } from "msw";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fixture } from "../../api/fixtures";
import type { Journey, Metadata } from "../../api/types";
import { en } from "../../i18n/en";
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
    // Walk to the stop: instruction, distance, the vehicle, its scheduled time, platform unknown.
    expect(card()).toHaveTextContent("הליכה אל דיזנגוף סנטר/טשרניחובסקי");
    expect(card()).toHaveTextContent("170 מ׳ הליכה");
    expect(card()).toHaveTextContent("אוטובוס 249");
    expect(card()).toHaveTextContent("יציאה ב־08:38 (מתוכנן)");
    expect(card()).toHaveTextContent(he["nav.platformUnknown"]);
    expect(card()).toHaveTextContent("שלב 1 מתוך 12");
    // Ride: line, stops left, exit stop and time, what comes next.
    await userEvent.click(rows()[1]!);
    expect(card()).toHaveTextContent("אוטובוס 249");
    expect(card()).toHaveTextContent("לכיוון כפר סבא_תחנה מרכזית");
    expect(card()).toHaveTextContent(/נשארו \d+ תחנות/);
    expect(card()).toHaveTextContent("ירידה ב־ת. רכבת תל אביב - סבידור/דרך נמיר · 08:48 (מתוכנן)");
    expect(card()).toHaveTextContent("אחר כך: מעבר");
    // Transfer walk: walk to the next stop and the next vehicle with a countdown.
    await userEvent.click(rows()[2]!);
    expect(card()).toHaveTextContent("מעבר: הליכה אל ת. רכבת תל אביב - סבידור/דרך נמיר");
    expect(card()).toHaveTextContent("אוטובוס 825");
    expect(card()).toHaveTextContent(/בעוד|יוצא עכשיו|עברה/);
    // Walk to the destination: the END placeholder is never shown.
    await userEvent.click(rows()[10]!);
    expect(card()).toHaveTextContent("הליכה אל היעד");
    expect(card()).not.toHaveTextContent("END");
    // Arrive: arrival time and Finish.
    await userEvent.click(rows()[11]!);
    expect(card()).toHaveTextContent("הגעתם אל היעד");
    expect(card()).toHaveTextContent("הגעה ב־10:37 (מתוכנן)");
    expect(screen.getByRole("button", { name: he["nav.finish"] })).toBeInTheDocument();
  });

  it("a time-only transfer and a train (journey 1, English)", async () => {
    seed(recordedJourneys[1]!);
    renderApp("#/navigate", { lang: "en" });
    await userEvent.click(rows()[2]!);
    // Rail: no empty line label; named by where it goes.
    expect(card()).toHaveTextContent("Train to חיפה מרכז");
    expect(card()).not.toHaveTextContent("towards 404");
    await userEvent.click(rows()[3]!);
    expect(card()).toHaveTextContent("Transfer: walk to תחנת רכבת חיפה מרכז השמונה");
    expect(card()).toHaveTextContent("About 4 min walk · no street path available");
    expect(card()).toHaveTextContent("Bus 17");
    expect(card()).toHaveTextContent(en["nav.platformUnknown"]);
  });

  it("a ride without trip detail shows the exit stop and time, not stops left", async () => {
    const journey = recordedJourneys[0]!;
    const missing = journey.legs[2]!.transit!.engineTripId;
    const trips = { ...recordedTrips };
    delete trips[missing];
    seed(journey, trips);
    renderApp("#/navigate");
    await userEvent.click(rows()[2]!);
    expect(card()).toHaveTextContent("רכבת אל חוף הכרמל");
    expect(card()).toHaveTextContent(he["nav.stopsUnknown"]);
    expect(card()).toHaveTextContent("ירידה ב־חוף הכרמל · 09:24 (מתוכנן)");
    // The missing trip was requested once (the fixture API does not know it).
    await waitFor(() => expect(getActiveTrip()?.tripsRequested).toEqual([missing]));
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
    expect(getActiveTrip()).not.toBeNull();
    expect(await screen.findByRole("button", { name: he["home.activeTrip"] })).toBeInTheDocument();
  });

  it("no active trip: a short message and a link Home", () => {
    renderApp("#/navigate");
    expect(screen.getByText(he["nav.noTrip"])).toBeInTheDocument();
    expect(screen.getByRole("link", { name: he["screen.backHome"] })).toHaveAttribute("href", "#/");
  });
});

describe("Navigate: location", () => {
  it("location denied → one manual banner; steps still advance by hand", async () => {
    seed(recordedJourneys[0]!);
    renderApp("#/navigate");
    act(() => handle.onError!("denied"));
    expect(screen.getAllByText(he["nav.manual"])).toHaveLength(1);
    expect(JSON.parse(sessionStorage.getItem(STORAGE_KEY)!).nav.locationMode).toBe("manual");
    await userEvent.click(screen.getByRole("button", { name: he["nav.next"] }));
    expect(rows()[1]).toHaveAttribute("aria-current", "step");
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

  it("a fix is shown on the map (follow); no fix → fit", () => {
    seed(recordedJourneys[0]!);
    renderApp("#/navigate");
    expect(getMapState().scene.camera).toBe("fit");
    expect(getMapState().scene.route[0]!.active).toBe(true);
    const fix = simulateJourney(recordedJourneys[0]!)[0]!;
    act(() => handle.onFix!(fix));
    expect(getMapState().scene.camera).toBe("follow");
    expect(getMapState().scene.user?.position).toEqual([fix.longitude, fix.latitude]);
    // The stored state never holds a position.
    expect(JSON.stringify(JSON.parse(sessionStorage.getItem(STORAGE_KEY)!).nav)).not.toContain(String(fix.latitude));
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
    for (const fix of simulateJourney(journey)) {
      if (!handle.onFix) break; // arrived: watching stopped
      act(() => handle.onFix!(fix));
      const text = live().textContent ?? "";
      if (announced.at(-1) !== text) announced.push(text);
      if (card().textContent?.includes(he["nav.cueTwo"])) sawTwo = true;
    }
    expect(sawTwo).toBe(true);
    expect(announced.some((text) => text.includes(he["nav.cueTwo"]))).toBe(true);
    expect(announced.some((text) => text.includes(he["nav.cueNext"]))).toBe(true);
    expect(vibrate).toHaveBeenCalled();
    expect(card()).toHaveTextContent("הגעתם אל היעד");
    // Arrived: location watching stopped.
    expect(handle.onFix).toBeNull();
    delete (navigator as unknown as { vibrate?: unknown }).vibrate;
  });
});

describe("Navigate: simulated positions", () => {
  it("the labelled toggle plays the journey back and drives the screen through every step", async () => {
    vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout", "setInterval", "clearInterval", "Date"] });
    const journey = recordedJourneys[0]!;
    seed(journey);
    renderApp("#/navigate");
    fireEvent.change(screen.getByRole("combobox", { name: he["nav.sim.speed"] }), { target: { value: "600" } });
    fireEvent.click(screen.getByRole("checkbox", { name: he["nav.sim.toggle"] }));
    expect(screen.getByText(/מיקום מדומה — לא המיקום האמיתי שלכם/)).toBeInTheDocument();
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
  });
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
