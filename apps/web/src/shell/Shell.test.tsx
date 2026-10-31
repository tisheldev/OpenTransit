import { act, fireEvent, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { en } from "../i18n/en";
import { he } from "../i18n/he";
import { getMapState } from "../map/scene";
import { go } from "../router";
import { renderApp, storedDraft } from "./testUtils";
import { nearestSnap, stepSnap } from "./sheet";

const sheet = () => document.querySelector(".sheet")!;
const handle = () => screen.getByRole("button", { name: /גודל הגיליון|Sheet size/ });

describe("shell", () => {
  it("renders the map layer, the sheet at half and reports its height as the map inset", () => {
    renderApp("#/");
    expect(screen.getByTestId("map-host")).toBeInTheDocument();
    expect(sheet()).toHaveAttribute("data-snap", "half");
    expect(getMapState().bottomInset).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: he["nav.locate"] })).toBeInTheDocument();
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
    const swap = await screen.findByRole("button", { name: en["fromTo.swap"] });
    expect(swap).toBeEnabled();
    await userEvent.click(swap);
    await waitFor(() => expect(storedDraft()?.to).toEqual({ type: "myLocation" }));
    expect(screen.getByRole("button", { name: `To: ${en["place.myLocation"]}` })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /^From: / }));
    expect(window.location.hash).toBe("#/search/from");
  });

  it("the skip link focuses the screen", async () => {
    renderApp("#/settings");
    await userEvent.click(screen.getByText(he["app.skipToContent"]));
    expect(screen.getByRole("heading", { level: 1 })).toHaveFocus();
  });
});
