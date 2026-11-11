import { act, fireEvent, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fixture } from "../../api/fixtures";
import type { DeparturesPage } from "../../api/schemas";
import type { Journey, JourneyRequest, JourneyResponse, Metadata } from "../../api/types";
import { he } from "../../i18n/he";
import { setLocationSource, type Fix, type LocationError, type LocationSource } from "../../lib/geolocation";
import { getMapState } from "../../map/scene";
import { respond } from "../../mocks/handlers";
import { derivedMissedDepartures, derivedMissedJourneys, MISSED_STOP_ID } from "../../mocks/navigateMissed";
import { server } from "../../mocks/node";
import { getActiveTrip, startActiveTrip } from "../../nav/activeTrip";
import { simulateJourney } from "../../nav/simulate";
import { recordedJourneys, recordedTrips } from "../../nav/testdata";
import recorded from "../../nav/testdata/recorded-oct31a-dizengoff-technion.json";
import { renderApp } from "../../shell/testUtils";
import { pinClock, RECORDED_NOW } from "../../test/clock";
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
  // The recorded journeys are dated 2 November 2026; read the wall clock and they expire.
  pinClock();
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

/** The one answer in the panel (or Bus didn't come). */
const answer = () => document.querySelector<HTMLElement>(".nav-answer, .nav-missed")!;
const title = () => screen.getByRole("heading", { level: 1 });
const kicker = () => answer().querySelector(".nav-kicker")?.textContent ?? null;
const check = () => answer().querySelector(".nav-check")?.textContent ?? null;
const button = (key: keyof typeof he) => screen.getByRole("button", { name: he[key] });
/** The checklist's rows. */
const rows = () => within(screen.getByRole("list", { name: /^(כל השלבים|All steps)$/ })).getAllByRole("button");
const current = () => rows().findIndex((row) => row.getAttribute("aria-current") === "step");
const live = () => document.querySelector<HTMLElement>("[aria-live]")!;
const stopRows = () => within(screen.getByRole("list", { name: he["nav.answer.stops"] })).getAllByRole("listitem").map((item) => item.textContent);

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

/** Bus didn't come: the derived departures and re-plans (src/mocks/navigateMissed.ts). */
function missedAnswers(options: { empty?: boolean; olderApi?: boolean; departuresFail?: boolean; walkEmpty?: boolean } = {}) {
  const requests: Array<JourneyRequest & { excludeTripRefs?: string[] }> = [];
  const departureUrls: string[] = [];
  server.use(
    http.get("*/v1/stops/:stopId/departures", ({ params, request }) => {
      departureUrls.push(request.url);
      if (decodeURIComponent(String(params.stopId)) !== MISSED_STOP_ID) return respond(fixture("recorded-departures-last-page"));
      // The engine was too slow (seen live under load, 11 November): the API answers 504.
      if (options.departuresFail) return new HttpResponse(null, { status: 504 });
      const found = derivedMissedDepartures();
      if (options.empty) (found.body as DeparturesPage).data = [];
      return respond(found);
    }),
    http.post("*/v1/journeys", async ({ request }) => {
      const body = (await request.json()) as JourneyRequest & { excludeTripRefs?: string[] };
      requests.push(body);
      // An API before PR #35 refuses the unknown field (extra="forbid": 422 invalid request).
      if (options.olderApi && body.excludeTripRefs) return respond(fixture("synthetic-problem-invalid-request"));
      const found = derivedMissedJourneys(body);
      if (options.empty || options.walkEmpty) Object.assign((found.body as JourneyResponse).data, { outcome: "no_route", journeys: [] });
      return respond(found);
    }),
  );
  return Object.assign(requests, { departureUrls });
}

describe("Navigate: walking to the stop (board 4)", () => {
  it("where to, how far, and whether the bus is caught; the stop pin carries the line and countdown", () => {
    seed(recordedJourneys[2]!);
    renderApp("#/navigate");
    expect(kicker()).toBe("הולכים אל");
    expect(title()).toHaveTextContent("דיזנגוף סנטר/טשרניחובסקי");
    expect(answer().querySelector(".nav-sub")).toHaveTextContent("3 דק׳ הליכה · 170 מ׳ · תחנה 25564");
    expect(check()).toBe("מספיקיםלפי הלוח 08:38");
    // The map tag's facts are in the panel for whoever does not see the map.
    expect(answer()).toHaveTextContent("אוטובוס 249 לכיוון כפר סבא · תחנה מרכזית · יציאה 08:38 · בעוד 38 דק׳");
    // Over the map: end navigation and the arrival time.
    expect(button("nav.end")).toHaveClass("b-close");
    expect(document.querySelector(".nav-float--end")).toHaveTextContent("מגיעים 10:37");
    // Actions: "לא הגיע?" then "עליתי"; nothing else.
    const actions = document.querySelector<HTMLElement>(".nav-actions")!;
    expect(within(actions).getAllByRole("button").map((b) => b.textContent)).toEqual(["לא הגיע?", "עליתי"]);
    // The map: the walk and the bus ahead, the stop as a large selected pin, its tag.
    const scene = getMapState().scene;
    expect(scene.stopPins).toEqual([expect.objectContaining({ selected: true, ariaLabel: "דיזנגוף סנטר/טשרניחובסקי" })]);
    expect(scene.tags).toEqual([expect.objectContaining({ kind: "strong", text: "38 דק׳", line: expect.objectContaining({ label: "249" }) })]);
  }, 15_000); // the file's first render loads the screen chunks; a loaded runner needs more than 5 s

  it("says honestly when the walk will not make it by the timetable", () => {
    pinClock(new Date("2026-11-02T08:36:00+02:00"));
    seed(recordedJourneys[2]!);
    renderApp("#/navigate");
    expect(check()).toBe("לא מספיקיםלפי הלוח 08:38");
    expect(answer().querySelector(".nav-check--late")).not.toBeNull();
  });

  it("a ride that starts the journey: waiting at its stop, the countdown, then 'עליתי' boards on the same step", async () => {
    pinClock(new Date("2026-11-02T08:00:00+02:00"));
    seed(recordedJourneys[0]!);
    renderApp("#/navigate");
    expect(kicker()).toBe("מחכים בתחנה");
    expect(title()).toHaveTextContent("דיזנגוף סנטר/דיזנגוף");
    expect(answer()).toHaveTextContent("אוטובוס 8 לכיוון מסוף הטייסים · תחנה 25565");
    expect(check()).toBe("בעוד 12 דק׳לפי הלוח 08:12");
    await userEvent.click(button("nav.answer.boarded"));
    expect(current()).toBe(0);
    expect(answer()).toHaveAttribute("data-answer", "riding");
    expect(live()).toHaveTextContent("עליתם לאוטובוס 8");
    expect(JSON.parse(sessionStorage.getItem(STORAGE_KEY)!).nav.phase).toBe("riding");
  });

  it("the waiting countdown: minutes, leaving now, ago, and the day when far ahead", () => {
    const journey = recordedJourneys[0]!;
    seed(journey);
    for (const [at, text] of [
      ["2026-11-02T08:12:20+02:00", "יוצא עכשיו"],
      ["2026-11-02T08:16:00+02:00", "לפני 4 דק׳"],
      ["2026-11-01T08:00:00+02:00", "ביום ב׳, 2.11"],
    ] as const) {
      vi.setSystemTime(new Date(at));
      const view = renderApp("#/navigate");
      expect(check()).toBe(`${text}לפי הלוח 08:12`);
      view.unmount();
    }
  });
});

describe("Navigate: on board (board 5)", () => {
  it("walking → 'עליתי' → on board: stops to the exit and the stops; 'ירדתי' goes on", async () => {
    seed(recordedJourneys[2]!);
    renderApp("#/navigate");
    await userEvent.click(button("nav.answer.boarded"));
    expect(current()).toBe(1);
    expect(live()).toHaveTextContent("שלב 2 מתוך 12");
    expect(answer()).toHaveAttribute("data-answer", "riding");
    expect(answer().querySelector(".nav-ride-line")).toHaveTextContent("249כפר סבא · תחנה מרכזית");
    expect(title()).toHaveTextContent("יורדים בעוד 8 תחנות");
    // Not measured from location: the count is by the timetable, and says so.
    expect(answer()).toHaveTextContent("לפי הלוח");
    // The stops: where the passenger is, the unnamed ones as their count (no names until
    // API-C1), the exit with "יורדים".
    expect(stopRows()).toEqual(["08:38אתם כאן: דיזנגוף סנטר/טשרניחובסקי", "7 תחנות", "08:48ת. רכבת תל אביב - סבידור/דרך נמיריורדים"]);
    // What comes after: the next bus, where it goes, when.
    const after = answer().querySelector<HTMLElement>(".nav-after")!;
    expect(after).toHaveTextContent(/^אחר כך825/);
    expect(after.querySelector(".nav-after-time")).toHaveTextContent("08:51");
    const actions = document.querySelector<HTMLElement>(".nav-actions")!;
    expect(within(actions).getAllByRole("button").map((b) => b.textContent)).toEqual(["ירדתי"]);
    // The map: the exit tagged "יורדים כאן", framed on what is left.
    expect(getMapState().scene.tags).toEqual([expect.objectContaining({ kind: "strong", text: "יורדים כאן" })]);
    expect(getMapState().scene.camera).toBe("fit");
    expect(getMapState().scene.fitTo?.length).toBeGreaterThan(1);

    await userEvent.click(button("nav.answer.alighted"));
    expect(current()).toBe(2);
    expect(kicker()).toBe("מעבר באותה תחנה");
    expect(title()).toHaveTextContent("ת. רכבת תל אביב - סבידור/דרך נמיר");
    expect(answer()).toHaveTextContent("3 דק׳ למעבר");
  });

  it("the primary action alone takes the trip through every step to Finish, which clears it and goes Home", async () => {
    seed(recordedJourneys[0]!);
    renderApp("#/navigate");
    const total = rows().length;
    for (let i = 0; i < 20 && current() < total - 1; i += 1) {
      await userEvent.click(document.querySelector<HTMLElement>(".nav-primary")!);
    }
    expect(current()).toBe(total - 1);
    expect(kicker()).toBe("הגעתם אל");
    expect(title()).toHaveTextContent("היעד");
    expect(JSON.parse(sessionStorage.getItem(STORAGE_KEY)!).nav.stepIndex).toBe(total - 1);
    // Arrived: Finish ends it; the close button is gone (Finish does it).
    expect(screen.queryByRole("button", { name: he["nav.end"] })).toBeNull();
    await userEvent.click(button("nav.finish"));
    expect(window.location.hash).toBe("#/");
    expect(sessionStorage.getItem(STORAGE_KEY)).toBeNull();
    expect(getActiveTrip()).toBeNull();
  });

  it("a ride without trip detail counts the minutes to the exit instead of stops", async () => {
    const journey = recordedJourneys[0]!;
    const missing = journey.legs[2]!.transit!.engineTripId;
    const trips = { ...recordedTrips };
    delete trips[missing];
    seed(journey, trips);
    renderApp("#/navigate");
    await userEvent.click(rows()[2]!);
    expect(title()).toHaveTextContent(/^יורדים בעוד (\d+ דק׳|בעוד .*|ב.*)$/);
    expect(stopRows()).toEqual(["08:21השלום", "09:24חוף הכרמליורדים"]);
    await waitFor(() => expect(getActiveTrip()?.tripsRequested).toEqual([missing]));
  });

  it("a rail platform is shown only when the API gives one (N3)", async () => {
    const journey = structuredClone(recordedJourneys[0]!);
    Object.assign(journey.legs[2]!.from, { platformCode: "3" });
    seed(journey);
    renderApp("#/navigate");
    await userEvent.click(button("nav.answer.boarded"));
    expect(answer().querySelector(".nav-after-text")).toHaveTextContent("רציף 3");
  });
});

describe("Navigate: bus didn't come (board 6)", () => {
  it("'לא הגיע?' shows both choices with their departures and arrival times", async () => {
    const requests = missedAnswers();
    seed(recordedJourneys[2]!);
    renderApp("#/navigate");
    await userEvent.click(button("nav.answer.missed"));
    expect(title()).toHaveTextContent("ה־249 עוד לא הגיע");
    expect(answer()).toHaveTextContent("לפי הלוח 08:38");
    const walk = await screen.findByRole("button", { name: /הולכים ל־8/ }, { timeout: 5000 });
    const wait = await screen.findByRole("button", { name: /מחכים כאן ל־249/ }, { timeout: 5000 });
    expect(walk).toHaveTextContent("הולכים ל־83 דק׳ הליכה · יוצא 08:45מגיעים10:40");
    expect(wait).toHaveTextContent("מחכים כאן ל־249הבא 08:58מגיעים10:57");
    // The earlier arrival is marked, in words too (not by its border alone).
    expect(walk).toHaveClass("b-choice--on");
    expect(walk).toHaveAccessibleName(/מגיעים הכי מוקדם/);
    expect(wait).not.toHaveClass("b-choice--on");
    // Wait here: planned from the stop at the next 249; walk elsewhere: from the stop's place, now (08:00).
    expect(requests.find((r) => r.from.kind === "stop")).toMatchObject({ from: { stopId: MISSED_STOP_ID }, departAt: "2026-11-02T08:58:00+02:00" });
    expect(requests.find((r) => r.from.kind === "coordinate")?.departAt).toBe("2026-11-02T08:00:00+02:00");
    // Without the bus that did not come (excludeTripRefs), and departures asked by route (API PR #35).
    expect(requests.find((r) => r.from.kind === "coordinate")?.excludeTripRefs).toEqual([recordedJourneys[2]!.legs[1]!.transit!.engineTripId]);
    expect(new URL(requests.departureUrls.find((url) => url.includes(encodeURIComponent(MISSED_STOP_ID)) || url.includes(MISSED_STOP_ID))!).searchParams.get("routeId")).toBe(
      recordedJourneys[2]!.legs[1]!.transit!.routeId,
    );
    // The map: the missed line faded with its next one, the other stop selected with its departure.
    await waitFor(() => expect(getMapState().scene.stopPins?.find((pin) => pin.id === "other")?.selected).toBe(true));
    const tags = getMapState().scene.tags!.map((tag) => [tag.id, tag.kind, tag.text]);
    expect(tags).toEqual([
      ["missed", "faded", "הבא 08:58"],
      ["other", "strong", "08:45"],
      ["walk", "faded", "3 דק׳ הליכה"],
    ]);
    expect(getMapState().scene.route[0]).toMatchObject({ tone: "faded" });
  });

  it("a failed next-bus check is said as such, never as 'no other option', and can be retried", async () => {
    missedAnswers({ departuresFail: true, walkEmpty: true });
    seed(recordedJourneys[2]!);
    renderApp("#/navigate");
    await userEvent.click(button("nav.answer.missed"));
    expect(await screen.findByText("לא הצלחנו לבדוק מתי יוצא ה־249 הבא.", undefined, { timeout: 8000 })).toBeInTheDocument();
    expect(screen.queryByText("אין כרגע אפשרות אחרת לפי הלוח.")).toBeNull();
    // The check answers on a second try.
    missedAnswers({ walkEmpty: true });
    await userEvent.click(screen.getByRole("button", { name: "נסו שוב" }));
    expect(await screen.findByRole("button", { name: /מחכים כאן ל־249/ }, { timeout: 8000 })).toBeInTheDocument();
  });

  it("an API before excludeTripRefs refuses the field: the plan is asked again without it", async () => {
    const requests = missedAnswers({ olderApi: true });
    seed(recordedJourneys[2]!);
    renderApp("#/navigate");
    await userEvent.click(button("nav.answer.missed"));
    expect(await screen.findByRole("button", { name: /הולכים ל־8/ }, { timeout: 5000 })).toHaveTextContent("מגיעים10:40");
    const walks = requests.filter((r) => r.from.kind === "coordinate");
    expect(walks.map((r) => r.excludeTripRefs !== undefined)).toEqual([true, false]);
  });

  it("choosing 'walk to another stop' switches the trip to that plan", async () => {
    missedAnswers();
    seed(recordedJourneys[2]!);
    renderApp("#/navigate");
    await userEvent.click(button("nav.answer.missed"));
    await userEvent.click(await screen.findByRole("button", { name: /הולכים ל־8/ }, { timeout: 5000 }));
    await waitFor(() => expect(getActiveTrip()?.journey.id).toBe("derived-missed-walk"));
    expect(kicker()).toBe("הולכים אל");
    expect(title()).toHaveTextContent("דיזנגוף סנטר/דיזנגוף");
    expect(check()).toBe("מספיקיםלפי הלוח 08:45");
  });

  it("choosing 'wait here' switches to the next 249: waiting at the same stop", async () => {
    missedAnswers();
    seed(recordedJourneys[2]!);
    renderApp("#/navigate");
    await userEvent.click(button("nav.answer.missed"));
    await userEvent.click(await screen.findByRole("button", { name: /מחכים כאן ל־249/ }, { timeout: 5000 }));
    await waitFor(() => expect(getActiveTrip()?.journey.id).toBe("derived-missed-wait"));
    expect(kicker()).toBe("מחכים בתחנה");
    expect(title()).toHaveTextContent("דיזנגוף סנטר/טשרניחובסקי");
    expect(check()).toBe("בעוד 58 דק׳לפי הלוח 08:58");
  });

  it("'הגיע, עליתי': the bus came after all, on board the planned ride", async () => {
    missedAnswers();
    seed(recordedJourneys[2]!);
    renderApp("#/navigate");
    await userEvent.click(button("nav.answer.missed"));
    await userEvent.click(button("nav.missed.came"));
    expect(current()).toBe(1);
    expect(answer()).toHaveAttribute("data-answer", "riding");
    expect(getActiveTrip()?.journey.id).toBe(recordedJourneys[2]!.id);
  });

  it("no other option in the timetable: an honest empty state, and back to the step", async () => {
    missedAnswers({ empty: true });
    seed(recordedJourneys[2]!);
    renderApp("#/navigate");
    await userEvent.click(button("nav.answer.missed"));
    expect(await screen.findByText(he["nav.missed.none"])).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /מחכים כאן/ })).toBeNull();
    await userEvent.click(button("nav.missed.cancel"));
    expect(kicker()).toBe("הולכים אל");
  });
});

describe("Navigate: checklist (expanded sheet)", () => {
  it("every row has its scheduled time and a state in its name; rides say where to get off (N2)", () => {
    seed(recordedJourneys[2]!);
    renderApp("#/navigate");
    const list = rows();
    expect(list).toHaveLength(12);
    expect(list[0]).toHaveAccessibleName("השלב הנוכחי: 08:35 הליכה אל דיזנגוף סנטר/טשרניחובסקי · 3 דק׳");
    expect(list[1]).toHaveAccessibleName("בהמשך: 08:38 אוטובוס 249 · 8 תחנות, ירידה ב־ת. רכבת תל אביב - סבידור/דרך נמיר · 08:48");
    expect(list[2]).toHaveAccessibleName("בהמשך: 08:49 מעבר באותה תחנה");
    expect(list[11]).toHaveAccessibleName("בהמשך: 10:37 הגעה אל היעד");
    expect(list[1]!.querySelector(".checklist-time")).toHaveTextContent("08:38");
    expect(list[0]!.querySelector(".checklist-mark")).toHaveTextContent("●");
    expect(list[1]!.querySelector(".ot-steps__icon .ot-line")).toHaveTextContent("249");
    expect(list[0]!.querySelector(".ot-steps__icon .ot-i--walk")).not.toBeNull();
  });

  it("tapping a row jumps forward and back (corrects a wrong advance)", async () => {
    seed(recordedJourneys[0]!);
    renderApp("#/navigate");
    await userEvent.click(rows()[4]!);
    expect(rows()[4]).toHaveAttribute("aria-current", "step");
    expect(rows()[0]).toHaveAccessibleName(/^הושלם: /);
    await userEvent.click(rows()[1]!);
    expect(current()).toBe(1);
    expect(JSON.parse(sessionStorage.getItem(STORAGE_KEY)!).nav.stepIndex).toBe(1);
  });

  it("at the full sheet the floats give way and End navigation sits under the list", async () => {
    seed(recordedJourneys[0]!);
    renderApp("#/navigate");
    expect(document.querySelector(".nav-float")).not.toBeNull();
    fireEvent.click(screen.getByRole("button", { name: /גודל הגיליון|sheet/i }));
    expect(document.querySelector(".sheet")).toHaveAttribute("data-snap", "full");
    expect(document.querySelector(".nav-float")).toBeNull();
    expect(button("nav.end")).toHaveClass("nav-end-full");
  });
});

describe("Navigate: ending and leaving", () => {
  it("the close button ends navigation: storage cleared, watching stopped, Home without a resume row", async () => {
    seed(recordedJourneys[0]!);
    renderApp("#/navigate");
    expect(handle.watches).toBe(1);
    await userEvent.click(button("nav.end"));
    expect(handle.stops).toBeGreaterThanOrEqual(1);
    expect(handle.onFix).toBeNull();
    expect(sessionStorage.getItem(STORAGE_KEY)).toBeNull();
    expect(window.location.hash).toBe("#/");
    expect(screen.queryByRole("button", { name: he["home.activeTrip"] })).toBeNull();
  });

  it("Back keeps the trip; Home then offers to resume", async () => {
    seed(recordedJourneys[0]!);
    renderApp("#/navigate");
    await userEvent.click(button("nav.back"));
    await waitFor(() => expect(handle.stops).toBe(1));
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
  it("location denied → one short manual banner saying why; the actions still advance by hand", async () => {
    seed(recordedJourneys[2]!);
    renderApp("#/navigate");
    act(() => handle.onError!("denied"));
    expect(screen.getAllByText(new RegExp(he["nav.manual"]))).toHaveLength(1);
    expect(screen.getByRole("status")).toHaveTextContent(`${he["nav.loc.denied"]} · ${he["nav.manual"]}`);
    expect(JSON.parse(sessionStorage.getItem(STORAGE_KEY)!).nav.locationMode).toBe("manual");
    await userEvent.click(button("nav.answer.boarded"));
    expect(current()).toBe(1);
  });

  it("over plain HTTP the banner says location needs HTTPS (the browser refuses it there)", () => {
    seed(recordedJourneys[0]!);
    renderApp("#/navigate", { location: "insecure" });
    act(() => handle.onError!("denied"));
    expect(screen.getByRole("status")).toHaveTextContent(`${he["nav.loc.insecure"]} · ${he["nav.manual"]}`);
  });

  it("no accepted fix for 60 s → 'no location right now'; nothing advances", () => {
    vi.useFakeTimers({ toFake: ["setInterval", "clearInterval", "Date"] });
    seed(recordedJourneys[0]!);
    renderApp("#/navigate");
    expect(screen.queryByText(new RegExp(he["nav.lost"]))).toBeNull();
    act(() => vi.advanceTimersByTime(66_000));
    expect(screen.getByText(new RegExp(he["nav.lost"]))).toBeInTheDocument();
    expect(current()).toBe(0);
  });

  it("the map: framed without a fix; at the stop it follows the passenger at street level", () => {
    const journey = recordedJourneys[0]!;
    seed(journey);
    renderApp("#/navigate");
    expect(getMapState().scene.camera).toBe("fit");
    expect(getMapState().scene.stopPins?.[0]?.ariaLabel).toBe("דיזנגוף סנטר/דיזנגוף");
    const fixes = simulateJourney(journey);
    const before = getMapState().locateRequest;
    act(() => handle.onFix!({ ...fixes[0]!, at: Date.now() }));
    expect(getMapState().scene.camera).toBe("follow");
    expect(getMapState().locateRequest).toBe(before + 1);
    expect(getMapState().scene.user?.position).toEqual([fixes[0]!.longitude, fixes[0]!.latitude]);
    // The stored state never holds a position.
    expect(JSON.stringify(JSON.parse(sessionStorage.getItem(STORAGE_KEY)!).nav)).not.toContain(String(fixes[0]!.latitude));
  });

  it("on board the travelled part turns grey and the map frames what is left", async () => {
    const journey = recordedJourneys[0]!;
    seed(journey);
    renderApp("#/navigate");
    await userEvent.click(rows()[2]!);
    const onTrain = simulateJourney(journey).find((fix) => fix.at > Date.parse("2026-11-02T08:50:00+02:00"))!;
    const before = getMapState().locateRequest;
    act(() => handle.onFix!({ ...onTrain, at: Date.now() }));
    const scene = getMapState().scene;
    expect(scene.camera).toBe("fit");
    expect(scene.user?.position).toEqual([onTrain.longitude, onTrain.latitude]);
    expect(getMapState().locateRequest).toBe(before);
    expect(scene.route.filter((leg) => leg.mode.toLowerCase() === "rail").map((leg) => leg.tone)).toEqual(["travelled", "normal"]);
    expect(scene.fitTo).toContainEqual([onTrain.longitude, onTrain.latitude]);
  });

  it("cues show in the answer, are announced and vibrate (call positions fetched at Start)", async () => {
    stopsWithPositions();
    const vibrate = vi.fn(() => true);
    Object.defineProperty(navigator, "vibrate", { value: vibrate, configurable: true });
    const journey = recordedJourneys[0]!;
    seed(journey);
    renderApp("#/navigate");
    await waitFor(() => expect(Object.keys(getActiveTrip()?.callPositions ?? {})).toEqual(["0", "2", "4"]));
    // The two calls before each exit carry their names from the same answer.
    expect((getActiveTrip()!.callPositions!["2"] as { positions: Array<{ name?: string }> }).positions[0]!.name).toBe("דיזנגוף סנטר/דיזנגוף");
    const announced: string[] = [];
    let sawTwo = false;
    let sawMeasured = false;
    for (const fix of simulateJourney(journey)) {
      if (!handle.onFix) break; // arrived: watching stopped
      act(() => handle.onFix!(fix));
      const text = live().textContent ?? "";
      if (announced.at(-1) !== text) announced.push(text);
      if (kicker() === he["nav.cueTwo"]) {
        sawTwo = true;
        // The cue changes the words (with an icon), not a colour alone.
        expect(answer()).toHaveAttribute("data-cue", "two_stops");
        expect(answer().querySelector(".nav-kicker--cue .ot-i")).not.toBeNull();
        // Measured from location now: no "by the timetable".
        if (title().textContent?.endsWith("2 תחנות") && !answer().querySelector(".nav-by-timetable")) sawMeasured = true;
      }
    }
    expect(sawTwo).toBe(true);
    expect(sawMeasured).toBe(true);
    expect(announced.some((text) => text.includes(he["nav.cueTwo"]))).toBe(true);
    expect(announced.some((text) => text.includes(he["nav.cueNext"]))).toBe(true);
    expect(vibrate).toHaveBeenCalled();
    expect(kicker()).toBe("הגעתם אל");
    expect(handle.onFix).toBeNull();
    delete (navigator as unknown as { vibrate?: unknown }).vibrate;
  }, 60_000); // plays a whole journey of fixes through the screen (a scene per fix); loaded runners need far more than 5 s
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
    expect(screen.getByRole("note")).toHaveTextContent(/^מיקום מדומה, לא אמיתי · שעון \d\d:\d\d · פי 600$/);
    // Countdowns follow the simulated clock: playback starts a minute before the first departure.
    expect(screen.getByRole("note")).toHaveTextContent("שעון 08:11");
    expect(check()).toBe("בעוד 1 דק׳לפי הלוח 08:12");
    expect(getMapState().scene.user).not.toBeNull();
    const total = rows().length;
    const seen = new Set<number>();
    for (let i = 0; i < 1000 && kicker() !== "הגעתם אל"; i += 1) {
      act(() => vi.advanceTimersByTime(50));
      seen.add(current());
    }
    expect(kicker()).toBe("הגעתם אל");
    expect([...seen].sort((a, b) => a - b)).toEqual(Array.from({ length: total }, (_, i) => i));
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
    expect(current()).toBe(3);
    expect(kicker()).toBe("הולכים אל");
    expect(title()).toHaveTextContent("ת. רכבת חוף הכרמל");
    await new Promise((resolve) => setTimeout(resolve, 20));
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

  it("the same recorded trip a year after its date is expired (guards the pinned clock above)", async () => {
    pinClock(new Date(RECORDED_NOW.getTime() + 365 * 24 * 3600_000));
    seed(recordedJourneys[0]!);
    renderApp("#/navigate");
    await waitFor(() => expect(window.location.hash).toBe("#/"));
    expect(sessionStorage.getItem(STORAGE_KEY)).toBeNull();
    expect(getActiveTrip()).toBeNull();
    expect(screen.queryByRole("button", { name: he["nav.answer.boarded"] })).toBeNull();
  });
});

describe("Navigate: wake lock", () => {
  it("requests a screen wake lock while navigating and releases it on ending", async () => {
    const release = vi.fn(() => Promise.resolve());
    const request = vi.fn(() => Promise.resolve({ released: false, release }));
    Object.defineProperty(navigator, "wakeLock", { value: { request }, configurable: true });
    seed(recordedJourneys[0]!);
    renderApp("#/navigate");
    await waitFor(() => expect(request).toHaveBeenCalledWith("screen"));
    await userEvent.click(button("nav.end"));
    await waitFor(() => expect(release).toHaveBeenCalled());
    delete (navigator as unknown as { wakeLock?: unknown }).wakeLock;
  });

  it("without the Wake Lock API nothing happens", () => {
    seed(recordedJourneys[0]!);
    expect(() => renderApp("#/navigate")).not.toThrow();
  });
});
