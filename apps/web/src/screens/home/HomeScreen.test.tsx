import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { fixture } from "../../api/fixtures";
import type { Journey, Metadata } from "../../api/types";
import { en } from "../../i18n/en";
import { he } from "../../i18n/he";
import { respond } from "../../mocks/handlers";
import { server } from "../../mocks/node";
import { startActiveTrip } from "../../nav/activeTrip";
import { defaultLocalState, saveLocalState, type SavedPlace } from "../../storage/local";
import { renderApp, storedDraft } from "../../shell/testUtils";

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
    await userEvent.click(resume);
    expect(window.location.hash).toBe("#/navigate");
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
