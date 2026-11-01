import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import type { Journey, Metadata } from "../../api/types";
import { en } from "../../i18n/en";
import { he } from "../../i18n/he";
import { getActiveTrip, startActiveTrip } from "../../nav/activeTrip";
import { writeSession } from "../../storage/session";
import { defaultLocalState, loadLocalState, saveLocalState, STORAGE_KEY, type SavedPlace } from "../../storage/local";
import { renderApp, storedDraft } from "../../shell/testUtils";

const place = (id: string, label: string): SavedPlace => ({
  id,
  label,
  latitude: 32.0757,
  longitude: 34.7748,
  stopId: null,
  placeRefHint: null,
  savedAt: "2026-10-31T10:00:00+02:00",
});

describe("Settings", () => {
  it("lists Home and Work as not set and opens Search to set them", async () => {
    renderApp("#/settings");
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(he["screen.settings"]);
    expect(screen.getAllByText(he["settings.notSet"])).toHaveLength(2);
    await userEvent.click(screen.getAllByRole("button", { name: he["settings.set"] })[0]!);
    expect(window.location.hash).toBe("#/search/home");
  });

  it("renames and deletes saved places (English)", async () => {
    saveLocalState({ ...defaultLocalState(), work: place("work", "Office"), favourites: [place("fav-1", "Mum")] });
    renderApp("#/settings", { lang: "en" });
    await userEvent.click(screen.getByRole("button", { name: "Rename Mum" }));
    const field = screen.getByLabelText("New name for Mum");
    await userEvent.clear(field);
    await userEvent.type(field, "Grandma");
    await userEvent.click(screen.getByRole("button", { name: en["settings.renameSave"] }));
    expect(screen.getByText("Grandma")).toBeInTheDocument();
    expect(loadLocalState().state.favourites[0]!.label).toBe("Grandma");
    await userEvent.click(screen.getByRole("button", { name: "Delete Office" }));
    expect(loadLocalState().state.work).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: "Delete Grandma" }));
    expect(loadLocalState().state.favourites).toEqual([]);
    expect(screen.getByText(en["settings.noFavourites"])).toBeInTheDocument();
  });

  it("clears all local data only on a second tap, with no dialog", async () => {
    saveLocalState({ ...defaultLocalState(), settings: { lang: "en" }, home: place("home", "Home street"), recents: [place("r", "Recent")] });
    writeSession("plan", { from: { type: "myLocation" }, to: { type: "place", place: { label: "X" } }, when: { mode: "now" } });
    const journey = {
      legs: [],
      timing: { scheduledDeparture: new Date().toISOString(), scheduledArrival: new Date(Date.now() + 3600_000).toISOString() },
    } as unknown as Journey;
    startActiveTrip({ journey, meta: {} as Metadata, trips: {} });
    const { queryClient } = renderApp("#/settings", { lang: "en" });
    await screen.findByText(en["settings.realtime"]);
    queryClient.setQueryData(["places", "דיזנגוף", "he", null], { cached: true });

    await userEvent.click(screen.getByRole("button", { name: en["settings.clearData"] }));
    expect(loadLocalState().state.home).not.toBeNull();
    expect(getActiveTrip()).not.toBeNull();
    const again = screen.getByRole("button", { name: en["settings.clearData.again"] });
    await userEvent.click(again);

    await waitFor(() => expect(document.documentElement.dir).toBe("rtl"));
    expect(screen.getByText(he["settings.clearData.done"])).toBeInTheDocument();
    expect(localStorage.getItem(STORAGE_KEY)).toBeNull();
    expect(getActiveTrip()).toBeNull();
    expect(storedDraft()?.to ?? null).toBeNull();
    expect(queryClient.getQueryCache().findAll({ queryKey: ["places"] })).toHaveLength(0);
    expect(screen.getAllByText(he["settings.notSet"])).toHaveLength(2);
  });

  it("can cancel the armed clear", async () => {
    saveLocalState({ ...defaultLocalState(), home: place("home", "Home street") });
    renderApp("#/settings");
    await userEvent.click(screen.getByRole("button", { name: he["settings.clearData"] }));
    await userEvent.click(screen.getByRole("button", { name: he["settings.cancel"] }));
    expect(screen.getByRole("button", { name: he["settings.clearData"] })).toBeInTheDocument();
    expect(loadLocalState().state.home).not.toBeNull();
  });

  it("switches language and direction without a restart", async () => {
    renderApp("#/settings");
    expect(document.documentElement.dir).toBe("rtl");
    await userEvent.click(screen.getByLabelText("English"));
    expect(document.documentElement.dir).toBe("ltr");
    expect(document.documentElement.lang).toBe("en");
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(en["screen.settings"]);
    expect(loadLocalState().state.settings.lang).toBe("en");
  });

  it("shows data status, unavailable live capabilities, attribution and version", async () => {
    renderApp("#/settings", { lang: "en" });
    expect(await screen.findByText(/Scheduled timetable from/)).toBeInTheDocument();
    expect(screen.getByText(/Freshness: current/)).toBeInTheDocument();
    expect(screen.getByText(en["settings.realtime"])).toBeInTheDocument();
    expect(screen.getByText(en["settings.alerts"])).toBeInTheDocument();
    expect(screen.getByText(en["settings.testData"])).toBeInTheDocument();
    expect(screen.getAllByText(en["settings.attribution.mot"]).length).toBeGreaterThan(0);
    expect(screen.getAllByText(en["settings.attribution.osm"]).length).toBeGreaterThan(0);
    expect(screen.getAllByText(en["settings.attribution.tiles"]).length).toBeGreaterThan(0);
    expect(screen.getByText(/^Version 0\.0\.0/)).toBeInTheDocument();
  });
});
