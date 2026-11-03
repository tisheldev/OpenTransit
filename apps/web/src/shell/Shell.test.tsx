import { act, fireEvent, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { en } from "../i18n/en";
import { he } from "../i18n/he";
import { setLocationSource } from "../lib/geolocation";
import { getMapState } from "../map/scene";
import { go } from "../router";
import { renderApp, storedDraft } from "./testUtils";
import { defaultSnap, fullHeight, nearestSnap, stepSnap } from "./sheet";
import { backFallback } from "./Shell";

const sheet = () => document.querySelector(".sheet")!;
const handle = () => screen.getByRole("button", { name: /גודל הגיליון|Sheet size/ });

describe("shell", () => {
  it("renders the map layer, the sheet at half and reports its height as the map inset", () => {
    renderApp("#/");
    expect(screen.getByTestId("map-host")).toBeInTheDocument();
    expect(sheet()).toHaveAttribute("data-snap", "half");
    expect(getMapState().bottomInset).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: he["nav.locate"] })).toBeInTheDocument();
    // One attribution line, in the top band beside Back (not floating on the map).
    expect(screen.getAllByTestId("map-attribution")).toHaveLength(1);
    expect(screen.getByTestId("map-attribution")).toHaveClass("map-attribution-inline");
  });

  it("changes the snap with the handle: tap cycles, arrow keys step", async () => {
    renderApp("#/", { lang: "en" });
    expect(handle()).toHaveAccessibleName("Sheet size: half. Tap to change");
    await userEvent.click(handle());
    expect(sheet()).toHaveAttribute("data-snap", "full");
    await userEvent.click(handle());
    expect(sheet()).toHaveAttribute("data-snap", "peek");
    handle().focus();
    await userEvent.keyboard("{ArrowUp}");
    expect(sheet()).toHaveAttribute("data-snap", "half");
    await userEvent.keyboard("{ArrowDown}{ArrowDown}");
    expect(sheet()).toHaveAttribute("data-snap", "peek");
  });

  it("snaps a drag to the nearest point", () => {
    renderApp("#/");
    // jsdom has no layout: the drag starts from height 0 in a 768 px viewport.
    fireEvent.pointerDown(handle(), { button: 0, clientY: 760, pointerId: 1 });
    fireEvent.pointerMove(handle(), { clientY: 60, pointerId: 1 });
    expect(sheet()).toHaveClass("sheet-dragging");
    fireEvent.pointerUp(handle(), { clientY: 60, pointerId: 1 });
    expect(sheet()).not.toHaveClass("sheet-dragging");
    expect(sheet()).toHaveAttribute("data-snap", "full");
    expect(nearestSnap(600, 640)).toBe("full");
    expect(nearestSnap(230, 640)).toBe("peek");
    expect(stepSnap("full", 1)).toBe("full");
  });

  it("opens each route at its own snap: Compare and Navigate at half so the map shows", () => {
    expect(defaultSnap("home")).toBe("half");
    expect(defaultSnap("search")).toBe("full");
    expect(defaultSnap("compare")).toBe("half");
    expect(defaultSnap("navigate")).toBe("half");
    expect(defaultSnap("settings")).toBe("full");
    expect(defaultSnap("stop")).toBe("half");
    // The full sheet stops below the top band (banners, Back, attribution).
    expect(fullHeight(640, 60)).toBe(580);
    expect(fullHeight(640, 0)).toBeCloseTo(588.8);
  });

  it("shows Back off Home, moves focus to the new screen's heading, and Back returns", async () => {
    renderApp("#/");
    act(() => go({ name: "settings" }));
    const heading = await screen.findByRole("heading", { level: 1, name: he["screen.settings"] });
    await waitFor(() => expect(heading).toHaveFocus());
    expect(sheet()).toHaveAttribute("data-snap", "full");
    await userEvent.click(screen.getByRole("button", { name: he["nav.back"] }));
    await waitFor(() => expect(window.location.hash).toBe("#/"));
    expect(await screen.findByRole("heading", { level: 1 })).toHaveTextContent(he["home.title"]);
    expect(screen.queryByRole("button", { name: he["nav.back"] })).toBeNull();
  });

  it("Back on a deep link goes Home", async () => {
    renderApp("#/settings");
    await userEvent.click(screen.getByRole("button", { name: he["nav.back"] }));
    await waitFor(() => expect(window.location.hash).toBe("#/"));
  });

  it("every screen opens scrolled to its top", async () => {
    renderApp("#/settings");
    const content = document.querySelector<HTMLElement>(".sheet-content")!;
    content.scrollTop = 400;
    act(() => go({ name: "search", field: "home" }));
    await screen.findByRole("heading", { level: 1, name: he["search.title.home"] });
    expect(content.scrollTop).toBe(0);
    content.scrollTop = 250;
    await userEvent.click(screen.getByRole("button", { name: he["nav.back"] }));
    await screen.findByRole("heading", { level: 1, name: he["screen.settings"] });
    expect(content.scrollTop).toBe(0);
  });

  it("Settings is the gear in Home's handle row; Locate shows only where a position helps", async () => {
    renderApp("#/");
    const row = document.querySelector<HTMLElement>(".sheet-handle-row")!;
    expect(within(row).getByRole("link", { name: he["screen.settings"] })).toHaveAttribute("href", "#/settings");
    await userEvent.click(handle()); // full: no map left to locate on
    expect(screen.queryByRole("button", { name: he["nav.locate"] })).toBeNull();
    act(() => go({ name: "settings" }));
    await screen.findByRole("heading", { level: 1, name: he["screen.settings"] });
    expect(screen.queryByRole("button", { name: he["nav.locate"] })).toBeNull();
    expect(screen.queryByRole("link", { name: he["screen.settings"] })).toBeNull();
  });

  it("Locate on Home takes one fix on the tap and shows it on the map", async () => {
    const restore = setLocationSource({
      current: async () => ({ ok: true, fix: { latitude: 32.0753, longitude: 34.7749, accuracyMeters: 20, at: 0 } }),
      watch: () => () => {},
    });
    try {
      renderApp("#/");
      expect(getMapState().located).toBeNull();
      await userEvent.click(screen.getByRole("button", { name: he["nav.locate"] }));
      await waitFor(() => expect(getMapState().located).toEqual({ position: [34.7749, 32.0753], accuracyMeters: 20 }));
    } finally {
      restore();
    }
  });

  it("Locate says so when no position comes", async () => {
    const restore = setLocationSource({ current: async () => ({ ok: false, error: "timeout" }), watch: () => () => {} });
    try {
      renderApp("#/");
      await userEvent.click(screen.getByRole("button", { name: he["nav.locate"] }));
      expect(await screen.findByText(he["shell.locate.failed"])).toBeInTheDocument();
      expect(getMapState().located).toBeNull();
    } finally {
      restore();
    }
  });

  it("the From/To card opens Search for each field and swaps ends", async () => {
    renderApp("#/", { lang: "en" });
    await userEvent.click(screen.getByRole("button", { name: en["fromTo.to"] }));
    expect(window.location.hash).toBe("#/search/to");
    await waitFor(() => expect(screen.getByRole("searchbox")).toHaveFocus());
    await userEvent.type(screen.getByRole("searchbox"), "Dizengoff");
    const first = (await screen.findByTestId("search-results")).querySelector("button")!;
    await userEvent.click(first);
    await waitFor(() => expect(window.location.hash).toBe("#/compare"));
    act(() => go({ name: "home" }));
    // hashchange is async: wait for Home, or this finds Compare's own compact From/To swap.
    await screen.findByRole("heading", { level: 1, name: en["home.title"] });
    const swap = await screen.findByRole("button", { name: en["fromTo.swap"] });
    expect(swap).toBeEnabled();
    await userEvent.click(swap);
    await waitFor(() => expect(storedDraft()?.to).toEqual({ type: "myLocation" }));
    expect(screen.getByRole("button", { name: /^Where to\?\s*My location$/ })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /^Where from\?/ }));
    expect(window.location.hash).toBe("#/search/from");
  });

  it("the skip link focuses the screen", async () => {
    renderApp("#/settings");
    await userEvent.click(screen.getByText(he["app.skipToContent"]));
    expect(screen.getByRole("heading", { level: 1 })).toHaveFocus();
  });
});

describe("history (Home → Search → Compare → Search → Compare)", () => {
  it("keeps Compare one entry: Back from Compare is Home in one tap, Back from Search returns to its opener", async () => {
    renderApp("#/");
    const pick = async (text: string) => {
      await userEvent.type(await screen.findByRole("searchbox"), text);
      await userEvent.click((await screen.findByTestId("search-results")).querySelector("button")!);
    };
    await userEvent.click(screen.getByRole("button", { name: he["fromTo.to"] }));
    await pick("דיזנגוף");
    await waitFor(() => expect(window.location.hash).toBe("#/compare"));
    // Compare → Search(from) → Back returns to Compare.
    await userEvent.click(await screen.findByRole("button", { name: new RegExp(`^${he["compare.fromLabel"]}:`) }));
    await waitFor(() => expect(window.location.hash).toBe("#/search/from"));
    await userEvent.click(screen.getByRole("button", { name: he["nav.back"] }));
    await waitFor(() => expect(window.location.hash).toBe("#/compare"));
    // Compare → Search(from) → choose: back on the same Compare entry.
    await userEvent.click(await screen.findByRole("button", { name: new RegExp(`^${he["compare.fromLabel"]}:`) }));
    await waitFor(() => expect(window.location.hash).toBe("#/search/from"));
    await pick("דיזנגוף");
    await waitFor(() => expect(window.location.hash).toBe("#/compare"));
    await waitFor(() => expect(storedDraft()?.from).toMatchObject({ type: "place" }));
    await userEvent.click(screen.getByRole("button", { name: he["nav.back"] }));
    await waitFor(() => expect(window.location.hash).toBe("#/"));
  });
});

describe("the sheet's setSnap", () => {
  it("on Compare: the screen's own snap applies once, then tap and drag on the handle stick", async () => {
    renderApp("#/compare");
    const start = sheet().getAttribute("data-snap");
    expect(["half", "full"]).toContain(start);
    await userEvent.click(handle());
    const afterTap = start === "full" ? "peek" : "full";
    expect(sheet()).toHaveAttribute("data-snap", afterTap);
    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(sheet()).toHaveAttribute("data-snap", afterTap);
    fireEvent.pointerDown(handle(), { button: 0, clientY: 700, pointerId: 1 });
    fireEvent.pointerMove(handle(), { clientY: 300, pointerId: 1 });
    fireEvent.pointerUp(handle(), { clientY: 300, pointerId: 1 });
    expect(sheet()).toHaveAttribute("data-snap", "half");
    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(sheet()).toHaveAttribute("data-snap", "half");
  });
});

describe("backFallback", () => {
  it("returns from Navigate to Compare and from everything else to Home", () => {
    expect(backFallback({ name: "navigate" })).toEqual({ name: "compare" });
    expect(backFallback({ name: "compare" })).toEqual({ name: "home" });
    expect(backFallback({ name: "search", field: "to" })).toEqual({ name: "home" });
  });
});
