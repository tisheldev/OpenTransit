import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { he } from "../../i18n/he";
import { server } from "../../mocks/node";
import type { PlaceChoice, PlanDraft } from "../../plan/draft";
import { renderApp, storedDraft } from "../../shell/testUtils";
import { writeSession } from "../../storage/session";

// A journey's line opened in place (canvas board Journey, 6, 14 November 2026): in route
// details a ride's row opens to that line's next departures from its boarding stop (the
// journey's own first, chosen); choosing another re-plans to catch it; a link opens the
// whole line; stop names open the stop. Default fixtures: the recorded journeys from
// Dizengoff Center, the first riding line 8 (route 16076) from stop 13561; the line and its
// departures are the synthetic A2 mocks (src/mocks/lineFixtures.ts).

const dizengoff: PlaceChoice = {
  label: "דיזנגוף סנטר",
  locality: "תל אביב-יפו",
  kind: "stop",
  latitude: 32.0753,
  longitude: 34.7749,
  stopId: "mot:stop:13583",
  placeRef: null,
  refGenerationId: null,
};
const technion: PlaceChoice = { ...dizengoff, label: "טכניון", locality: "חיפה", kind: "pin", latitude: 32.7767, longitude: 35.0231, stopId: null };
const draft: PlanDraft = {
  from: { type: "place", place: dizengoff },
  to: { type: "place", place: technion },
  when: { mode: "depart_at", wall: "2026-10-01T08:00", offset: "auto" },
};

let posts: Array<Record<string, unknown>> = [];
beforeEach(() => {
  posts = [];
  server.events.on("request:start", async ({ request }) => {
    if (request.method === "POST" && new URL(request.url).pathname === "/v1/journeys") posts.push((await request.clone().json()) as Record<string, unknown>);
  });
});
afterEach(() => server.events.removeAllListeners());

const timeline = () => screen.getByRole("group", { name: he["route.steps"] });
const rides = () => [...timeline().querySelectorAll<HTMLElement>("button.compare-tl-leg[aria-expanded]")];

describe("Route details: a ride opened in place", () => {
  it("opens to the line's next departures from the boarding stop; another one re-plans to catch it", async () => {
    writeSession("plan", draft);
    const user = userEvent.setup();
    renderApp("#/route");
    await waitFor(() => expect(rides().length).toBeGreaterThan(0));
    const ride = rides()[0]!;
    expect(ride).toHaveAttribute("aria-expanded", "false");
    await user.click(ride);
    expect(ride).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByText("קו 8 מהתחנה הזו · אפשר לבחור נסיעה אחרת")).toBeInTheDocument();
    const times = within(screen.getByRole("group", { name: "הזמנים הבאים של קו 8" }));
    await waitFor(() => expect(times.getAllByRole("button")).toHaveLength(3));
    const chips = times.getAllByRole("button");
    expect(chips.map((chip) => chip.getAttribute("aria-pressed"))).toEqual(["true", "false", "false"]);
    // The journey's own ride first (its recorded 08:07).
    expect(chips[0]).toHaveTextContent("08:07");
    // The link to the whole line, once the line is known.
    expect(await screen.findByRole("button", { name: "כל התחנות של קו 8" })).toBeInTheDocument();

    const before = posts.length;
    await user.click(chips[2]!);
    // Re-planned to leave in time for that departure, and no earlier.
    await waitFor(() => expect(posts.length).toBe(before + 1));
    expect(storedDraft()!.when).toMatchObject({ mode: "depart_at" });
    const chosen = Date.parse(String(posts[posts.length - 1]!.departAt));
    expect(chosen).toBeGreaterThan(Date.parse(String(posts[0]!.departAt)));
  });

  it("the line link opens the Line screen at the boarding stop; a stop's name opens the stop", async () => {
    writeSession("plan", draft);
    const user = userEvent.setup();
    renderApp("#/route");
    await waitFor(() => expect(rides().length).toBeGreaterThan(0));
    await user.click(rides()[0]!);
    await user.click(await screen.findByRole("button", { name: "כל התחנות של קו 8" }));
    await waitFor(() => expect(window.location.hash).toBe("#/line/5%3A10008"));
    expect(await screen.findByRole("heading", { level: 1, name: "קו 8" })).toBeInTheDocument();

    window.history.back();
    await waitFor(() => expect(window.location.hash).toBe("#/route"));
    const stop = await screen.findByRole("button", { name: "דיזנגוף סנטר/דיזנגוף" });
    await user.click(stop);
    await waitFor(() => expect(window.location.hash).toBe("#/stop/mot%3Astop%3A13561"));
  });
});
