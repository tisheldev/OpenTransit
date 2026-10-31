import { act, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { fixture } from "../../api/fixtures";
import type { Journey, Metadata } from "../../api/types";
import { en } from "../../i18n/en";
import { he } from "../../i18n/he";
import { locationSource } from "../../lib/geolocation";
import { getMapState } from "../../map/scene";
import { respond } from "../../mocks/handlers";
import { server } from "../../mocks/node";
import { startActiveTrip } from "../../nav/activeTrip";
import type { PlaceChoice } from "../../plan/draft";
import { defaultLocalState, saveLocalState, type SavedPlace } from "../../storage/local";
import { writeSession } from "../../storage/session";
import { renderApp, storedDraft } from "../../shell/testUtils";

const choice: PlaceChoice = {
  label: "",
  locality: null,
  kind: "pin",
  latitude: 32,
  longitude: 34.8,
  stopId: null,
  placeRef: null,
  refGenerationId: null,
};

const place = (id: string, label: string, latitude = 32.0757): SavedPlace => ({
  id,
  label,
  latitude,
  longitude: 34.7748,
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

describe("Home", () => {
  it("first launch: From is my location, set-Home/Work chips, no recents, no request before paint", async () => {
    let statusCalls = 0;
    server.use(
      http.get("*/v1/status", () => {
        statusCalls += 1;
        return statusWith((body) => void (body.meta.mode = "real"));
      }),
    );
    renderApp("#/");
    expect(statusCalls).toBe(0);
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(he["home.title"]);
    expect(screen.getByRole("button", { name: /מאיפה\?\s*המיקום שלי/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: he["fromTo.to"] })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: he["fromTo.swap"] })).toBeDisabled();
    expect(screen.getByRole("button", { name: new RegExp(he["home.setHome"]) })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: new RegExp(he["home.setWork"]) })).toBeInTheDocument();
    expect(screen.getByText(he["home.noRecents"])).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: nameOf("nav.back") })).toBeNull();
    await waitFor(() => expect(statusCalls).toBe(1));
  });

  it("an empty Home chip opens Search to save Home; + opens it to save a favourite", async () => {
    renderApp("#/");
    await userEvent.click(screen.getByRole("button", { name: new RegExp(he["home.setHome"]) }));
    expect(window.location.hash).toBe("#/search/home");
    window.history.replaceState({ otDepth: 0 }, "", "/#/");
    window.dispatchEvent(new HashChangeEvent("hashchange"));
    await userEvent.click(await screen.findByRole("button", { name: he["home.addFavourite"] }));
    expect(window.location.hash).toBe("#/search/favourite");
  });

  it("with saved places (English): a filled chip sets To and goes to Compare", async () => {
    saveLocalState({
      ...defaultLocalState(),
      settings: { lang: "en" },
      home: place("home", "Dizengoff 50, Tel Aviv"),
      favourites: [place("fav-1", "Mum")],
    });
    renderApp("#/", { lang: "en" });
    expect(screen.getByRole("button", { name: /Mum/ })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: new RegExp(`^${en["place.home"]}`) }));
    expect(window.location.hash).toBe("#/compare");
    await waitFor(() => expect(storedDraft()?.to).toMatchObject({ type: "place", place: { label: "Dizengoff 50, Tel Aviv" } }));
  });

  it("lists at most 10 recents, newest first, and a recent goes to Compare", async () => {
    const recents = Array.from({ length: 10 }, (_, index) => place(`r${index}`, `Recent ${index}`, 32 + index / 100));
    saveLocalState({ ...defaultLocalState(), recents });
    renderApp("#/");
    const list = screen.getByRole("heading", { name: he["home.recents"] }).parentElement!;
    const rows = list.querySelectorAll("li button");
    expect(rows).toHaveLength(10);
    expect(rows[0]).toHaveTextContent("Recent 0");
    await userEvent.click(rows[2] as HTMLElement);
    expect(window.location.hash).toBe("#/compare");
    await waitFor(() => expect(storedDraft()?.to).toMatchObject({ place: { label: "Recent 2" } }));
  });

  it("shows a resume row at the top when a trip is active", async () => {
    const journey = {
      legs: [],
      timing: { scheduledDeparture: new Date().toISOString(), scheduledArrival: new Date(Date.now() + 3600_000).toISOString() },
    } as unknown as Journey;
    startActiveTrip({ journey, meta: {} as Metadata, trips: {} });
    renderApp("#/");
    const resume = screen.getByRole("button", { name: he["home.activeTrip"] });
    // First in the sheet, before the From/To card, with when it arrives.
    const content = document.querySelector(".home")!;
    expect(content.querySelector("button")).toBe(resume);
    expect(resume).toHaveAccessibleDescription(/^נסיעה פעילה · הגעה \d\d:\d\d$/);
    await userEvent.click(resume);
    expect(window.location.hash).toBe("#/navigate");
  });

  it("has no scheduled-times footnote (Compare carries it) and frames the map on the last place", () => {
    saveLocalState({ ...defaultLocalState(), recents: [place("r0", "Recent 0", 32.7767)] });
    renderApp("#/");
    expect(screen.queryByText(he["banner.liveUnavailable"])).toBeNull();
    expect(getMapState().scene).toMatchObject({ camera: "fit", pins: [], focus: { center: [34.7748, 32.7767], zoom: 13 } });
  });

  it("shows the plan's chosen ends on the map", () => {
    writeSession("plan", {
      from: { type: "place", place: { ...choice, label: "A", latitude: 32.07, longitude: 34.77 } },
      to: { type: "place", place: { ...choice, label: "B", latitude: 32.78, longitude: 35.02 } },
      when: { mode: "now" },
    });
    renderApp("#/");
    expect(getMapState().scene.pins.map((pin) => [pin.role, pin.label])).toEqual([
      ["origin", "A"],
      ["destination", "B"],
    ]);
  });

  describe("when my location cannot work", () => {
    it("no secure context: From starts empty, Locate is hidden, and a destination asks for the start next", async () => {
      saveLocalState({ ...defaultLocalState(), recents: [place("r0", "Recent 0")] });
      renderApp("#/", { location: "insecure" });
      expect(screen.getByRole("button", { name: he["fromTo.from"] })).toBeInTheDocument();
      expect(screen.queryByRole("button", { name: /המיקום שלי/ })).toBeNull();
      expect(screen.queryByRole("button", { name: he["nav.locate"] })).toBeNull();
      expect(storedDraft()?.from).toBeNull();
      await userEvent.click(screen.getByRole("button", { name: "Recent 0" }));
      expect(window.location.hash).toBe("#/search/from");
    });

    it("denied: the plan starts from the last start chosen instead of my location", async () => {
      saveLocalState({ ...defaultLocalState(), recents: [place("r1", "Dizengoff Center"), place("32.07570,34.77480", "Old start")] });
      localStorage.setItem("opentransit:lastOrigin", "32.07570,34.77480");
      renderApp("#/", { location: "denied" });
      expect(await screen.findByRole("button", { name: /^מאיפה\?\s*Old start$/ })).toBeInTheDocument();
      await waitFor(() => expect(storedDraft()?.from).toMatchObject({ type: "place", place: { label: "Old start" } }));
      expect(screen.queryByRole("button", { name: he["nav.locate"] })).toBeNull();
    });

    it("a refusal at the prompt during this visit switches From away from my location", async () => {
      renderApp("#/");
      expect(screen.getByRole("button", { name: /^מאיפה\?\s*המיקום שלי$/ })).toBeInTheDocument();
      // What a dismissed prompt looks like: the position request fails with PERMISSION_DENIED.
      const denied = { code: 1, PERMISSION_DENIED: 1, POSITION_UNAVAILABLE: 2, TIMEOUT: 3, message: "denied" };
      Object.defineProperty(navigator, "geolocation", {
        configurable: true,
        value: { getCurrentPosition: (_ok: unknown, fail: (error: unknown) => void) => fail(denied) },
      });
      await act(async () => {
        await locationSource().current();
      });
      expect(await screen.findByRole("button", { name: he["fromTo.from"] })).toBeInTheDocument();
      await waitFor(() => expect(storedDraft()?.from).toBeNull());
    });
  });

  it("shows the stale-data banner when the timetable is ageing", async () => {
    server.use(http.get("*/v1/status", () => statusWith((body) => void (body.meta.freshness = "aging"))));
    renderApp("#/");
    expect(await screen.findByText(he["banner.staleData"])).toBeInTheDocument();
  });

  it("says the timetable expired, and labels fixture data as test data", async () => {
    server.use(http.get("*/v1/status", () => respond(fixture("synthetic-status-expired"))));
    renderApp("#/", { lang: "en" });
    expect(await screen.findByText(en["shell.expired"])).toBeInTheDocument();
    expect(screen.getByText(en["banner.testData"])).toBeInTheDocument();
    expect(screen.queryByText(en["banner.staleData"])).toBeNull();
  });

  it("still renders offline, with a no-connection banner", async () => {
    server.use(http.get("*/v1/status", () => HttpResponse.error()));
    renderApp("#/");
    expect(await screen.findByText(he["shell.offline"])).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(he["home.title"]);
  });
});

function nameOf(key: keyof typeof he): string {
  return he[key];
}
