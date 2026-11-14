import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { afterEach, describe, expect, it } from "vitest";
import { he } from "../../i18n/he";
import { setLocationSource } from "../../lib/geolocation";
import { getMapState } from "../../map/scene";
import { getActiveTrip } from "../../nav/activeTrip";
import { respond } from "../../mocks/handlers";
import { derivedPinnedJourney } from "../../mocks/rideFixtures";
import { server } from "../../mocks/node";
import { renderApp, storedDraft } from "../../shell/testUtils";

// A line (board 4) and Ride it (board 5), against the synthetic A2/A3 mocks built from the
// recorded lines through Dizengoff Center (src/mocks/lineFixtures.ts): line 8 of Dan, its
// recorded direction (to Tel Aviv University) and that direction reversed (to מסוף הטייסים).

const LINE = "#/line/5%3A10008";
const stopsList = () => screen.getByRole("list", { name: he["line.stops"] });
const rowTexts = () => within(stopsList()).getAllByRole("button").map((row) => row.textContent);

let restore: (() => void) | null = null;
afterEach(() => {
  restore?.();
  restore = null;
});

/** The passenger 40 m from Dizengoff Center (stop 13583, index 22 of the recorded pattern). */
function nearDizengoff() {
  restore = setLocationSource({
    current: async () => ({ ok: true, fix: { latitude: 32.0753, longitude: 34.7749, accuracyMeters: 20, at: 0 } }),
    watch: () => () => {},
  });
}

/** Journey requests sent (Ride it posts a pinned one). */
function journeyBodies(): Array<Record<string, unknown>> {
  const bodies: Array<Record<string, unknown>> = [];
  server.use(
    http.post("*/v1/journeys", async ({ request }) => {
      const body = (await request.json()) as Record<string, unknown>;
      bodies.push(body);
      return respond(derivedPinnedJourney(body as Parameters<typeof derivedPinnedJourney>[0]));
    }),
  );
  return bodies;
}

describe("Line", () => {
  it("without a position: the line's header, both directions, the list from the first stop with the rest folded", async () => {
    renderApp(LINE);
    expect(await screen.findByRole("heading", { level: 1, name: "קו 8" })).toBeInTheDocument();
    const directions = within(await screen.findByRole("group", { name: he["line.directions"] })).getAllByRole("button");
    expect(directions.map((button) => [button.textContent, button.getAttribute("aria-pressed")])).toEqual([
      ["למסוף הטייסים", "true"],
      ["לאוניברסיטת ת\"א", "false"],
    ]);
    await waitFor(() => expect(screen.getByText("דן · אוטובוס · כל 12 דק׳ בערך")).toBeInTheDocument());
    const rows = rowTexts();
    expect(rows[0]).toMatch(/^מסוף אוניברסיטת ת''א\/הורדה/);
    expect(rows).toHaveLength(7);
    expect(rows[5]).toBe("36 תחנות נוספות");
    await waitFor(() => expect(rowTexts()[6]).toMatch(/^מסוף הטייסים\d\d:\d\d$/));
    expect(screen.getByText(he["line.note"])).toBeInTheDocument();

    // The whole route on the map, its stops, the end as a square, the first stop's sign and a chevron.
    const scene = getMapState().scene;
    expect(scene.route).toHaveLength(1);
    expect(scene.route[0]).toMatchObject({ kind: "transit", tone: "normal", operatorId: "5" });
    expect(scene.route[0]!.coordinates).toHaveLength(42);
    expect(scene.pins).toHaveLength(41);
    expect(scene.pins[scene.pins.length - 1]).toMatchObject({ role: "destination" });
    expect(scene.stopPins).toEqual([expect.objectContaining({ look: "sign", selected: true, ariaLabel: "התחנה מסוף אוניברסיטת ת''א/הורדה" })]);
    expect(scene.tags!.find((tag) => tag.id === "direction")!.glyph).toMatchObject({ kind: "chevron" });
    expect(scene.tags!.find((tag) => tag.id === "end")).toMatchObject({ kind: "strong", text: "מסוף הטייסים", line: { label: "8" } });
  });

  it("near the passenger: opens at the nearest stop with earlier stops folded; a train badge; the other direction", async () => {
    nearDizengoff();
    const user = userEvent.setup();
    renderApp(LINE);
    await waitFor(() => expect(rowTexts()[0]).toBe("19 תחנות קודמות · ממסוף אוניברסיטת ת''א/הורדה"));
    const here = within(stopsList()).getAllByRole("button")[1]!;
    expect(here).toHaveClass("sl-sr--on");
    await waitFor(() => expect(here).toHaveTextContent(/^דיזנגוף סנטר\/דיזנגוףהכי קרובה אליך · 1 דק׳ הליכהבעוד \d דק׳\d\d:\d\d · \d\d:\d\d$/));
    expect(getMapState().scene.stopPins![0]).toMatchObject({ id: "mot:stop:13583", look: "sign" });
    // Four stops to the station with its train badge, 17 folded, the terminus (as board 4).
    await waitFor(() => expect(within(stopsList()).getAllByRole("button")[5]).toHaveTextContent(/^ת\. רכבת השלוםרכבת\d\d:\d\d$/));
    const rows = rowTexts();
    expect(rows[6]).toBe("17 תחנות נוספות");
    expect(rows[7]).toMatch(/^מסוף הטייסים\d\d:\d\d$/);

    // The earlier stops open in place.
    await user.click(within(stopsList()).getAllByRole("button")[0]!);
    expect(rowTexts()[0]).toMatch(/^מסוף אוניברסיטת ת''א\/הורדה/);
    expect(rowTexts()).toHaveLength(19 + 1 + 4 + 1 + 1);

    // The other direction: its own nearest stop, the earlier ones folded again.
    await user.click(screen.getByRole("button", { name: "לאוניברסיטת ת\"א" }));
    expect(screen.getByRole("button", { name: "לאוניברסיטת ת\"א" })).toHaveAttribute("aria-pressed", "true");
    await waitFor(() => expect(rowTexts()[0]).toBe("22 תחנות קודמות · ממסוף הטייסים"));
    expect(rowTexts()[1]).toMatch(/^דיזנגוף סנטר\/דיזנגוף/);
  });

  it("saves the line on the device with its star, with the stop it was saved from", async () => {
    nearDizengoff();
    const user = userEvent.setup();
    renderApp(LINE);
    await waitFor(() => expect(rowTexts()[0]).toMatch(/תחנות קודמות/));
    const star = screen.getByRole("button", { name: he["line.save"] });
    expect(star).toHaveAttribute("aria-pressed", "false");
    await user.click(star);
    expect(star).toHaveAttribute("aria-pressed", "true");
    expect(JSON.parse(localStorage.getItem("opentransit")!).savedLines).toEqual([
      expect.objectContaining({ lineKey: "5:10008", shortName: "8", operatorId: "5", destinationName: "מסוף הטייסים", stopId: "mot:stop:13583" }),
    ]);
    await user.click(star);
    expect(star).toHaveAttribute("aria-pressed", "false");
  });

  it("an unknown line says so", async () => {
    renderApp("#/line/5%3A1");
    expect(await screen.findByRole("alert")).toBeInTheDocument();
  });
});

describe("Ride it", () => {
  it("tap a later stop: the ride from the nearest stop, a pinned journey, the summary and both buttons", async () => {
    nearDizengoff();
    const bodies = journeyBodies();
    const user = userEvent.setup();
    renderApp(LINE);
    await user.click(await screen.findByRole("button", { name: "למסוף הטייסים" }));
    await waitFor(() => expect(within(stopsList()).getAllByRole("button")[5]).toHaveTextContent(/^ת\. רכבת השלום/));
    await user.click(within(stopsList()).getAllByRole("button")[5]!);

    await waitFor(() => expect(window.location.hash).toBe("#/ride"));
    expect(await screen.findByRole("heading", { level: 1, name: "למסוף הטייסים" })).toBeInTheDocument();
    expect(screen.getByText("מתי עולים בדיזנגוף סנטר/דיזנגוף?")).toBeInTheDocument();
    const chips = within(screen.getByRole("group", { name: he["ride.departures"] })).getAllByRole("button");
    await waitFor(() => expect(chips).toHaveLength(3));
    expect(chips.map((chip) => chip.getAttribute("aria-pressed"))).toEqual(["true", "false", "false"]);

    const list = within(screen.getByRole("list", { name: he["line.stops"] }));
    await waitFor(() => expect(list.getByText("יורדים כאן · 4 תחנות · 6 דק׳ נסיעה")).toBeInTheDocument());
    expect(list.getByText(/^עולים כאן · 1 דק׳ הליכה$/)).toBeInTheDocument();
    expect(list.getByText("17 תחנות נוספות")).toBeInTheDocument();

    // The journey pinned to the chosen trip, from the passenger to the exit stop's point.
    await waitFor(() => expect(bodies).toHaveLength(1));
    expect(bodies[0]).toMatchObject({
      from: { kind: "coordinate", latitude: 32.0753, longitude: 34.7749 },
      to: { kind: "coordinate" },
      pinnedTrip: { boardStopId: "mot:stop:13583", alightStopId: "mot:stop:12823" },
    });
    expect(String((bodies[0]!.pinnedTrip as { tripRef: string }).tripRef)).toMatch(/^derived-line~mot:route:16076~/);
    expect(await screen.findByText("8 דק׳ · כולל 1 דק׳ הליכה לתחנה")).toBeInTheDocument();

    // On the map: the board stop's sign, the ride drawn, the walk, the exit tagged.
    const scene = getMapState().scene;
    expect(scene.stopPins![0]).toMatchObject({ id: "mot:stop:13583", look: "sign", selected: true });
    expect(scene.route.filter((leg) => leg.tone === "faded")).toHaveLength(2);
    expect(scene.route.find((leg) => leg.kind === "walk")).toBeDefined();
    expect(scene.tags!.find((tag) => tag.id === "exit-tag")!.text).toMatch(/^יורדים כאן \d\d:\d\d$/);

    // Another departure: a new pinned journey on it.
    await user.click(chips[1]!);
    expect(chips[1]).toHaveAttribute("aria-pressed", "true");
    await waitFor(() => expect(bodies).toHaveLength(2));
    expect((bodies[1]!.pinnedTrip as { tripRef: string }).tripRef).not.toBe((bodies[0]!.pinnedTrip as { tripRef: string }).tripRef);

    // Start: navigation on the pinned journey.
    await user.click(screen.getByRole("button", { name: he["compare.start"] }));
    await waitFor(() => expect(window.location.hash).toBe("#/navigate"));
    expect(getActiveTrip()!.journey.legs.map((leg) => leg.kind)).toEqual(["walk", "transit"]);
  });

  it("ולהמשיך משם… plans on from the exit stop", async () => {
    sessionStorage.setItem(
      "opentransit:ride",
      JSON.stringify({ lineKey: "5:10008", routeId: "mot:route:16076", boardStopId: "mot:stop:13583", alightStopId: "mot:stop:12823", tripRef: null }),
    );
    const user = userEvent.setup();
    renderApp("#/ride");
    await user.click(await screen.findByRole("button", { name: he["ride.continue"] }));
    await waitFor(() => expect(window.location.hash).toBe("#/search/to"));
    expect(storedDraft()).toMatchObject({ from: { type: "place", place: { stopId: "mot:stop:12823", label: "ת. רכבת השלום" } }, to: null });
  });

  it("a walk the API cannot route: no journey, a message, no start", async () => {
    sessionStorage.setItem(
      "opentransit:ride",
      JSON.stringify({ lineKey: "5:10008", routeId: "mot:route:16076", boardStopId: "mot:stop:13583", alightStopId: "mot:stop:12823", tripRef: null }),
    );
    server.use(
      http.post("*/v1/journeys", async ({ request }) => {
        const found = derivedPinnedJourney((await request.json()) as Parameters<typeof derivedPinnedJourney>[0]);
        const body = found.body as { data: { outcome: string; journeys: unknown[] }; meta: { warnings: string[] } };
        return HttpResponse.json({ ...body, data: { ...body.data, outcome: "no_route", journeys: [] }, meta: { ...body.meta, warnings: ["PINNED_TRIP_WALK_UNAVAILABLE"] } });
      }),
    );
    renderApp("#/ride");
    expect(await screen.findByText(he["ride.walkUnavailable"])).toBeInTheDocument();
    expect(screen.getByRole("button", { name: he["compare.start"] })).toBeDisabled();
  });

  it("without a ride in this tab: says so", async () => {
    renderApp("#/ride");
    expect(await screen.findByText(he["ride.expired"])).toBeInTheDocument();
  });
});
