import { act, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { afterEach, describe, expect, it } from "vitest";
import { fixture } from "../../api/fixtures";
import type { Journey, Metadata } from "../../api/types";
import { en } from "../../i18n/en";
import { he } from "../../i18n/he";
import { locationSource, setLocationSource } from "../../lib/geolocation";
import { getMapState } from "../../map/scene";
import { respond } from "../../mocks/handlers";
import { server } from "../../mocks/node";
import { derivedDepartures, derivedNearbyDepartures } from "../../mocks/stopFixtures";
import { startActiveTrip } from "../../nav/activeTrip";
import { derivedJourneyFixtures } from "../compare/derivedFixtures";
import { defaultLocalState, saveLocalState, type SavedPlace } from "../../storage/local";
import { renderApp, storedDraft, wholeText } from "../../shell/testUtils";

// Home — board 1 (11 November 2026): the search field, Home and Work with their next
// departure, the stops near the passenger as pins with their next departure, the selected
// stop's departures, and the 5-minute walking ring when there is a fix.

const place = (id: string, label: string, latitude = 32.0757, longitude = 34.7748): SavedPlace => ({
  id,
  label,
  latitude,
  longitude,
  stopId: null,
  placeRefHint: null,
  savedAt: "2026-10-31T10:00:00+02:00",
});

function statusWith(change: (body: { data: Record<string, unknown>; meta: Record<string, unknown> }) => void) {
  const base = fixture("synthetic-status-ready");
  const body = structuredClone(base.body) as { data: Record<string, unknown>; meta: Record<string, unknown> };
  change(body);
  return respond({ ...base, body });
}

/** A fix the passenger already allowed (a replaced source counts as granted). */
function grantFix(latitude = 32.0753, longitude = 34.7749) {
  return setLocationSource({
    current: async () => ({ ok: true, fix: { latitude, longitude, accuracyMeters: 20, at: 0 } }),
    watch: () => () => {},
  });
}

let restore: (() => void) | null = null;
afterEach(() => {
  restore?.();
  restore = null;
});

const sheetContent = () => document.querySelector<HTMLElement>(".home")!;
const nearestStop = "דיזנגוף סנטר/דיזנגוף";

describe("Home", () => {
  it("first paint from storage only: the search field, unset Home and Work, no request before paint", async () => {
    let calls = 0;
    server.use(
      http.get("*/v1/status", () => {
        calls += 1;
        return statusWith((body) => void (body.meta.mode = "real"));
      }),
      http.get("*/v1/departures/nearby", ({ request }) => {
        calls += 1;
        return respond(derivedNearbyDepartures(new URL(request.url).searchParams.get("from")));
      }),
    );
    renderApp("#/");
    expect(calls).toBe(0);
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(he["home.title"]);
    expect(screen.getByRole("button", { name: he["home.search"] })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: new RegExp(he["home.setHome"]) })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: new RegExp(he["home.setWork"]) })).toBeInTheDocument();
    expect(screen.getByText(he["stop.scheduled"])).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: he["nav.back"] })).toBeNull();
    await waitFor(() => expect(calls).toBeGreaterThanOrEqual(2));
  });

  it("the search field opens Where to; an unset card opens Search to save that place", async () => {
    renderApp("#/");
    await userEvent.click(screen.getByRole("button", { name: he["home.search"] }));
    expect(window.location.hash).toBe("#/search/to");
    for (const [name, hash] of [
      [new RegExp(he["home.setHome"]), "#/search/home"],
      [new RegExp(he["home.setWork"]), "#/search/work"],
    ] as const) {
      window.history.replaceState({ otDepth: 0 }, "", "/#/");
      window.dispatchEvent(new HashChangeEvent("hashchange"));
      await userEvent.click(await screen.findByRole("button", { name }));
      expect(window.location.hash).toBe(hash);
    }
  });

  it("without a fix: the stops around the last place, the nearest selected, its departures as rows, no ring", async () => {
    saveLocalState({ ...defaultLocalState(), recents: [place("r0", "Recent 0", 32.0757, 34.7748)] });
    renderApp("#/");
    const heading = await screen.findByRole("heading", { level: 2, name: nearestStop });
    const section = heading.closest("section")!;
    const rows = await within(section).findAllByRole("button");
    expect(rows.map((row) => row.textContent)).toEqual(["172מסוף רדינג2 דק׳", "115מסוף רדינג5 דק׳", "8אוניברסיטת ת\"א9 דק׳", "5רכבת מרכז11 דק׳"]);
    // No fix: no distance, no ring, no puck; the map frames the stops.
    expect(within(section).queryByText(/מ׳/)).toBeNull();
    await waitFor(() => expect(getMapState().scene.stops?.known).toHaveLength(4));
    const scene = getMapState().scene;
    expect(scene).toMatchObject({ camera: "fit", ring: null, user: null, focus: { center: [34.7748, 32.0757], zoom: 16 } });
    // The stops layer draws them (marker G); the nearest is the chosen one.
    expect(scene.stops).toMatchObject({ mode: "full", chosenStopId: "mot:stop:13583" });
    expect(scene.stops!.known!.map((stop) => stop.stopId)).toEqual(["mot:stop:13583", "mot:stop:13561", "mot:stop:13560", "mot:stop:49938"]);
    // Each stop's next line for its tag (the layer shows a couple, the chosen stop's first).
    expect(scene.stops!.next!["mot:stop:13583"]).toMatchObject({ text: "2 דק׳", minutes: 2, line: { label: "172", operatorId: "5" } });
    // A sign or a tag opens its own stop.
    act(() => scene.stops!.onSelectStop!("mot:stop:13560"));
    await waitFor(() => expect(window.location.hash).toBe("#/stop/mot%3Astop%3A13560"));
  });

  it("with a fix already allowed: the walking ring and the puck around the passenger, and the stop's distance", async () => {
    restore = grantFix();
    renderApp("#/");
    await waitFor(() => expect(getMapState().scene.ring).toEqual({ center: [34.7749, 32.0753], radiusMeters: 400 }));
    expect(getMapState().scene.user).toEqual({ position: [34.7749, 32.0753], accuracyMeters: 20 });
    const heading = await screen.findByRole("heading", { level: 2, name: nearestStop });
    // About 36 m from the fix, rounded to tens.
    expect(heading.parentElement).toHaveTextContent(/40 מ׳$/);
  });

  it("one tap on any stop opens it; the nearest stop is the chosen one", async () => {
    renderApp("#/");
    await waitFor(() => expect(getMapState().scene.stops?.next?.["mot:stop:13560"]?.line.label).toBe("66"));
    const layer = getMapState().scene.stops!;
    expect(layer.chosenStopId).toBe("mot:stop:13583");
    act(() => layer.onSelectStop!("mot:stop:13560"));
    await waitFor(() => expect(window.location.hash).toBe("#/stop/mot%3Astop%3A13560"));
    act(() => layer.onSelectStop!("mot:stop:13583"));
    await waitFor(() => expect(window.location.hash).toBe("#/stop/mot%3Astop%3A13583"));
  });

  it("a departure row opens its stop with that line's route shown", async () => {
    renderApp("#/");
    const heading = await screen.findByRole("heading", { level: 2, name: nearestStop });
    const rows = await within(heading.closest("section")!).findAllByRole("button");
    await userEvent.click(rows[2]!);
    await waitFor(() => expect(window.location.hash).toBe("#/stop/mot%3Astop%3A13583"));
    const chosen = await screen.findByRole("button", { pressed: true });
    expect(chosen).toHaveTextContent(/^8אוניברסיטת ת"א/);
  });

  it("with saved places (English): a card plans to it, with the next ride toward it", async () => {
    // The derived journey re-timed so its first ride leaves in about four minutes.
    const answer = derivedJourneyFixtures["derived-journey-three"]();
    const body = structuredClone(answer.body) as { data: { journeys: Journey[] } };
    const journey = body.data.journeys[0]!;
    const ride = journey.legs.find((leg) => leg.kind === "transit")!;
    const shift = Date.now() + 4 * 60_000 - Date.parse(ride.timing.scheduledDeparture);
    ride.timing.scheduledDeparture = new Date(Date.parse(ride.timing.scheduledDeparture) + shift).toISOString();
    let sent: { results?: number; from?: unknown } | null = null;
    server.use(
      http.post("*/v1/journeys", async ({ request }) => {
        sent = (await request.json()) as typeof sent;
        return respond({ ...answer, body });
      }),
    );
    saveLocalState({ ...defaultLocalState(), settings: { lang: "en" }, home: place("home", "Dizengoff 50, Tel Aviv", 32.08, 34.79) });
    restore = grantFix();
    renderApp("#/", { lang: "en" });
    const card = screen.getByRole("button", { name: /^Home/ });
    await waitFor(() => expect(card).toHaveTextContent(new RegExp(`^Home${ride.transit!.routeShortName}in [45] min$`)));
    expect(sent).toMatchObject({ results: 1, from: { kind: "coordinate", latitude: 32.0753, longitude: 34.7749 } });
    expect(screen.getByRole("button", { name: new RegExp(en["home.setWork"]) })).toBeInTheDocument();
    await userEvent.click(card);
    expect(window.location.hash).toBe("#/compare");
    await waitFor(() => expect(storedDraft()?.to).toMatchObject({ type: "place", place: { label: "Dizengoff 50, Tel Aviv" } }));
  });

  it("a saved place's next ride is quietly left out when the journey fails", async () => {
    server.use(http.post("*/v1/journeys", () => HttpResponse.error()));
    saveLocalState({ ...defaultLocalState(), home: place("home", "בית", 32.08, 34.79) });
    restore = grantFix();
    renderApp("#/");
    const card = screen.getByRole("button", { name: he["place.home"] });
    await screen.findByRole("heading", { level: 2, name: nearestStop });
    expect(card).toHaveTextContent(/^בית$/);
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("one request for the stops and their departures; without that endpoint, the stops list and each stop's departures", async () => {
    let nearbyCalls = 0;
    const departureCalls: string[] = [];
    server.use(
      http.get("*/v1/departures/nearby", () => {
        nearbyCalls += 1;
        return respond(fixture("synthetic-problem-stop-not-found"));
      }),
      http.get("*/v1/stops/:stopId/departures", ({ request, params }) => {
        departureCalls.push(decodeURIComponent(String(params.stopId)));
        return respond(derivedDepartures(String(params.stopId), new URL(request.url).searchParams.get("from"), 12));
      }),
    );
    renderApp("#/");
    const heading = await screen.findByRole("heading", { level: 2, name: nearestStop });
    const rows = await within(heading.closest("section")!).findAllByRole("button");
    expect(rows.map((row) => row.textContent)).toEqual(["172מסוף רדינג2 דק׳", "115מסוף רדינג5 דק׳", "8אוניברסיטת ת\"א9 דק׳", "5רכבת מרכז11 דק׳"]);
    expect(nearbyCalls).toBe(1);
    expect([...departureCalls].sort()).toEqual(["mot:stop:13560", "mot:stop:13561", "mot:stop:13583", "mot:stop:49938"]);
    // The operator comes from each stop's routes when departures do not carry it.
    await waitFor(() => expect(getMapState().scene.stops?.next?.["mot:stop:13583"]?.line).toMatchObject({ label: "172", operatorId: "5" }));
  });

  it("says so when the nearby stops cannot be read, with a retry", async () => {
    server.use(http.get("*/v1/departures/nearby", () => respond(fixture("recorded-problem-not-ready"))));
    renderApp("#/");
    expect(await screen.findByRole("alert")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: he["state.retry"] })).toBeInTheDocument();
  });

  it("says so when there are no stops near the place", async () => {
    server.use(
      http.get("*/v1/departures/nearby", () => {
        const base = fixture("recorded-live-departures-nearby");
        return respond({ ...base, body: { ...(base.body as object), data: [] } });
      }),
    );
    renderApp("#/");
    expect(await screen.findByText(he["home.stops.none"])).toBeInTheDocument();
  });

  it("shows a resume card first when a trip is active", async () => {
    const journey = {
      legs: [],
      timing: { scheduledDeparture: new Date().toISOString(), scheduledArrival: new Date(Date.now() + 3600_000).toISOString() },
    } as unknown as Journey;
    startActiveTrip({ journey, meta: {} as Metadata, trips: {} });
    renderApp("#/");
    const resume = screen.getByRole("button", { name: he["home.activeTrip"] });
    expect(sheetContent().querySelector("button")).toBe(resume);
    expect(resume).toHaveAccessibleDescription(/^נסיעה פעילה · הגעה \d\d:\d\d$/);
    await userEvent.click(resume);
    expect(window.location.hash).toBe("#/navigate");
  });

  describe("when my location cannot work", () => {
    it("no secure context: Locate is hidden, no ring, and a saved place asks for the start next", async () => {
      saveLocalState({ ...defaultLocalState(), home: place("home", "בית שלי") });
      renderApp("#/", { location: "insecure" });
      expect(screen.queryByRole("button", { name: he["nav.locate"] })).toBeNull();
      expect(storedDraft()?.from).toBeNull();
      await screen.findByRole("heading", { level: 2, name: nearestStop });
      expect(getMapState().scene.ring).toBeNull();
      await userEvent.click(screen.getByRole("button", { name: he["place.home"] }));
      expect(window.location.hash).toBe("#/search/from");
    });

    it("denied: the plan starts from the last start chosen, and Home looks around it", async () => {
      saveLocalState({ ...defaultLocalState(), recents: [place("r1", "Dizengoff Center"), place("32.07000,34.78000", "Old start", 32.07, 34.78)] });
      localStorage.setItem("opentransit:lastOrigin", "32.07000,34.78000");
      let near: string | null = null;
      server.use(
        http.get("*/v1/departures/nearby", ({ request }) => {
          near = new URL(request.url).searchParams.get("near");
          return respond(derivedNearbyDepartures(null));
        }),
      );
      renderApp("#/", { location: "denied" });
      await waitFor(() => expect(storedDraft()?.from).toMatchObject({ type: "place", place: { label: "Old start" } }));
      expect(screen.queryByRole("button", { name: he["nav.locate"] })).toBeNull();
      await waitFor(() => expect(near).toBe("32.07,34.78"));
    });

    it("a refusal at the prompt during this visit switches the plan's start away from my location", async () => {
      renderApp("#/");
      expect(storedDraft()?.from ?? { type: "myLocation" }).toEqual({ type: "myLocation" });
      const denied = { code: 1, PERMISSION_DENIED: 1, POSITION_UNAVAILABLE: 2, TIMEOUT: 3, message: "denied" };
      Object.defineProperty(navigator, "geolocation", {
        configurable: true,
        value: { getCurrentPosition: (_ok: unknown, fail: (error: unknown) => void) => fail(denied) },
      });
      await act(async () => {
        await locationSource().current();
      });
      await waitFor(() => expect(storedDraft()?.from).toBeNull());
    });
  });

  it("shows the stale-data banner when the timetable is ageing", async () => {
    server.use(http.get("*/v1/status", () => statusWith((body) => void (body.meta.freshness = "aging"))));
    renderApp("#/");
    expect(await screen.findByText(wholeText(he["banner.staleData"]))).toBeInTheDocument();
  });

  it("says the timetable expired, and labels fixture data as test data", async () => {
    server.use(http.get("*/v1/status", () => respond(fixture("synthetic-status-expired"))));
    renderApp("#/", { lang: "en" });
    expect(await screen.findByText(wholeText(en["shell.expired"]))).toBeInTheDocument();
    expect(screen.getByText(wholeText(en["banner.testData"]))).toBeInTheDocument();
    expect(screen.queryByText(wholeText(en["banner.staleData"]))).toBeNull();
  });

  it("still renders offline, with a no-connection banner", async () => {
    server.use(http.get("*/v1/status", () => HttpResponse.error()));
    renderApp("#/");
    expect(await screen.findByText(wholeText(he["shell.offline"]))).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(he["home.title"]);
  });
});
