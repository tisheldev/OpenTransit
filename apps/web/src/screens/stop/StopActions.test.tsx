import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { he } from "../../i18n/he";
import { getMapState } from "../../map/scene";
import { renderApp, storedDraft } from "../../shell/testUtils";

// A stop's actions — canvas board Stop (3), 14 November 2026: travel from or to it, save
// it, and a chosen line opened in place to its next three times and all its stops.

const STOP = "#/stop/mot%3Astop%3A13583";
const lines = () => screen.getByRole("list", { name: he["stop.lines"] });

describe("Stop actions", () => {
  it("לנסוע מכאן makes the stop the start and asks where to", async () => {
    const user = userEvent.setup();
    renderApp(STOP);
    await screen.findByRole("heading", { level: 1, name: "דיזנגוף סנטר/דיזנגוף" });
    await user.click(screen.getByRole("button", { name: he["stop.travelFrom"] }));
    await waitFor(() => expect(window.location.hash).toBe("#/search/to"));
    expect(storedDraft()!.from).toMatchObject({ type: "place", place: { kind: "stop", stopId: "mot:stop:13583", label: "דיזנגוף סנטר/דיזנגוף" } });
  });

  it("להגיע לכאן makes the stop the destination and compares from the start already chosen", async () => {
    const user = userEvent.setup();
    renderApp(STOP);
    await screen.findByRole("heading", { level: 1, name: "דיזנגוף סנטר/דיזנגוף" });
    await user.click(screen.getByRole("button", { name: he["stop.travelTo"] }));
    await waitFor(() => expect(window.location.hash).toBe("#/compare"));
    expect(storedDraft()!.to).toMatchObject({ type: "place", place: { stopId: "mot:stop:13583" } });
  });

  it("the star saves the stop on the device, and again removes it", async () => {
    const user = userEvent.setup();
    renderApp(STOP);
    await screen.findByRole("heading", { level: 1, name: "דיזנגוף סנטר/דיזנגוף" });
    const star = screen.getByRole("button", { name: he["stop.save"] });
    expect(star).toHaveAttribute("aria-pressed", "false");
    await user.click(star);
    expect(star).toHaveAttribute("aria-pressed", "true");
    expect(JSON.parse(localStorage.getItem("opentransit")!).savedStops).toEqual([
      expect.objectContaining({ stopId: "mot:stop:13583", name: "דיזנגוף סנטר/דיזנגוף" }),
    ]);
    await user.click(star);
    expect(star).toHaveAttribute("aria-pressed", "false");
  });

  it("a chosen line opens in place to its next three times and כל התחנות, which opens the line at this stop", async () => {
    const user = userEvent.setup();
    renderApp(STOP);
    await waitFor(() => expect(within(lines()).getAllByRole("button")).toHaveLength(6));
    // The stop is drawn as its sign (marker G).
    expect(getMapState().scene.stopPins![0]).toMatchObject({ look: "sign", selected: true });
    await user.click(within(lines()).getAllByRole("button")[2]!);
    const times = within(screen.getByRole("group", { name: "הזמנים הבאים של קו 8" }));
    // Line 8 leaves twice in the recorded departures window: two times (at most three).
    expect(times.getAllByRole("button").filter((b) => b.classList.contains("sl-chip")).map((b) => b.textContent)).toEqual([expect.stringMatching(/^\d\d:\d\d$/), expect.stringMatching(/^\d\d:\d\d$/)]);
    const all = times.getByRole("button", { name: he["stop.allStops"] });
    await waitFor(() => expect(all).toBeEnabled());
    await user.click(all);
    await waitFor(() => expect(window.location.hash).toBe("#/line/5%3A10008"));
    // The line opens at the stop the passenger came from, in that line's direction.
    await waitFor(() => expect(within(screen.getByRole("list", { name: he["line.stops"] })).getAllByRole("button")[0]).toHaveTextContent("22 תחנות קודמות · ממסוף הטייסים"));
    expect(screen.getByRole("button", { name: "לאוניברסיטת ת\"א" })).toHaveAttribute("aria-pressed", "true");
  });
});
