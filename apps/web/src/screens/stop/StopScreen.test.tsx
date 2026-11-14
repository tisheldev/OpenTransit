import { act, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http } from "msw";
import { afterEach, describe, expect, it } from "vitest";
import { fixture } from "../../api/fixtures";
import { en } from "../../i18n/en";
import { he } from "../../i18n/he";
import { setLocationSource } from "../../lib/geolocation";
import { getMapState } from "../../map/scene";
import { respond } from "../../mocks/handlers";
import { server } from "../../mocks/node";
import { derivedDepartures } from "../../mocks/stopFixtures";
import { renderApp } from "../../shell/testUtils";

// A stop — board 7 (11 November 2026): every line through it fans out on the map, each a
// row in the panel; tapping one shows its whole route with its direction.

const STOP = "#/stop/mot%3Astop%3A13583";
const lineRows = () => within(screen.getByRole("list", { name: he["stop.lines"] })).getAllByRole("button");

/** An API before PR #35: no lines endpoint (404). */
const withoutLines = () =>
  server.use(http.get("*/v1/stops/:stopId/lines", () => respond(fixture("synthetic-problem-stop-not-found"))));

let restore: (() => void) | null = null;
afterEach(() => {
  restore?.();
  restore = null;
});

describe("Stop", () => {
  it("names the stop and lists each line once with its next departure; every line fans out on the map", async () => {
    renderApp(STOP);
    expect(await screen.findByRole("heading", { level: 1, name: "דיזנגוף סנטר/דיזנגוף" })).toBeInTheDocument();
    await waitFor(() => expect(lineRows()).toHaveLength(6));
    expect(lineRows().map((row) => row.textContent)).toEqual([
      "172מסוף רדינג2 דק׳",
      "115מסוף רדינג5 דק׳",
      "8אוניברסיטת ת\"א9 דק׳",
      "5רכבת מרכז11 דק׳",
      "2נווה דן18 דק׳",
      "39מסוף רדינג23 דק׳",
    ]);
    expect(lineRows().every((row) => row.getAttribute("aria-pressed") === "false")).toBe(true);
    expect(screen.getByText(he["stop.scheduled"])).toBeInTheDocument();

    // Every line's pattern through the stop (the lines endpoint): one way out per direction,
    // faded, fading toward the map's edge and drawn out from the stop (user review, 14
    // November): five lines go north up the same street; 115 turns off west.
    await waitFor(() => expect(getMapState().scene.route).toHaveLength(2));
    const scene = getMapState().scene;
    expect(scene.route.every((leg) => leg.tone === "quiet" && leg.kind === "transit" && leg.fadeOut && leg.grow)).toBe(true);
    expect(scene.route.map((leg) => leg.operatorId)).toEqual(["5", "15"]);
    // North starts at the stop; 115 shares that street first, so it is drawn from where it
    // turns off (two translucent colours on one street would mix into a third).
    expect(scene.route[0]!.coordinates![0]).toEqual([34.77512, 32.075566]);
    expect(scene.route[1]!.coordinates![0]).not.toEqual([34.77512, 32.075566]);
    expect(scene.growKey!.startsWith("mot:stop:13583|")).toBe(true);
    // One tag per direction, pinned where its lines leave the map.
    expect(scene.tags!.map((tag) => [tag.kind, tag.line?.label ?? tag.lines?.map((line) => line.label), tag.text])).toEqual([
      ["faded", ["172", "8", "5", "2", "39"], undefined],
      ["faded", "115", "לכיוון מסוף רדינג"],
    ]);
    expect(scene.tags![0]).toMatchObject({ late: true });
    expect(scene.tags![0]!.ariaLabel).toBeUndefined();
    // A tag follows its whole way out from the stop (to the map's edge, else to its end).
    const fan115 = scene.route[1]!.coordinates!;
    const along = scene.tags![1]!.along!;
    expect(along[0]).toEqual([34.77512, 32.075566]);
    expect(along.at(-1)).toEqual(fan115.at(-1));
    expect(scene.tags![1]!.position).toEqual(fan115.at(-1));
    expect(scene.stopPins).toEqual([expect.objectContaining({ id: "mot:stop:13583", selected: true, position: [34.77512, 32.075566] })]);
    expect(scene).toMatchObject({ camera: "fit", user: null });
    expect(scene.fitTo!.length).toBeGreaterThan(2);
  });

  it("tapping a line shows its whole route with its direction, its stops and its end; tapping it again folds it back", async () => {
    renderApp(STOP);
    await waitFor(() => expect(getMapState().scene.route).toHaveLength(2));
    const row = lineRows()[2]!;
    await userEvent.click(row);
    expect(row).toHaveAttribute("aria-pressed", "true");
    expect(row).toHaveClass("b-row--on");
    const scene = getMapState().scene;
    const chosen = scene.route.find((leg) => leg.tone === "normal")!;
    expect(chosen).toMatchObject({ kind: "transit", label: null, operatorId: "5" });
    // The whole pattern, end to end (line 8 calls at 42 stops), and the camera frames it.
    expect(chosen.coordinates).toHaveLength(42);
    expect(scene.fitTo).toHaveLength(43);
    expect(scene.route.filter((leg) => leg.tone === "quiet")).toHaveLength(2);
    // A small ring at each of its other stops.
    expect(scene.pins).toHaveLength(41);
    expect(scene.pins.every((pin) => pin.role === "stop")).toBe(true);
    expect(scene.pins[0]).toMatchObject({ label: "מסוף הטייסים", position: [34.813778, 32.047685] });
    const direction = scene.tags!.find((tag) => tag.id === "direction")!;
    expect(direction).toMatchObject({ kind: "plain", anchor: "center", ariaLabel: "כיוון הנסיעה של קו 8" });
    // A chevron turned to the line's bearing (board Stop), not a text arrow.
    expect(direction.glyph).toMatchObject({ kind: "chevron" });
    expect(direction.glyph!.bearing).toBeGreaterThanOrEqual(0);
    const end = scene.tags!.find((tag) => tag.kind === "strong")!;
    expect(end).toMatchObject({ text: "אוניברסיטת ת\"א", line: { label: "8" }, ariaLabel: "קו 8 נוסע אל אוניברסיטת ת\"א" });
    expect(end.position).toEqual(chosen.coordinates![chosen.coordinates!.length - 1]);
    await userEvent.click(row);
    expect(row).toHaveAttribute("aria-pressed", "false");
    expect(getMapState().scene.route.every((leg) => leg.tone === "quiet")).toBe(true);
  });

  it("a direction's tag lists its lines in the panel and lights them; a one-line tag chooses its line", async () => {
    renderApp(STOP);
    await waitFor(() => expect(getMapState().scene.tags).toHaveLength(2));
    const [north, west] = getMapState().scene.tags!;
    act(() => north!.onSelect!());
    expect(lineRows().map((row) => row.textContent?.match(/^\d+/)?.[0])).toEqual(["172", "8", "5", "2", "39"]);
    expect(screen.getByText("5 קווים בכיוון הזה")).toBeInTheDocument();
    const lit = getMapState().scene;
    expect(lit.tags![0]!.kind).toBe("strong");
    expect(lit.route.map((leg) => leg.quietOpacity)).toEqual([0.9, undefined]);
    // The direction's lines grow once only: the key is the same.
    expect(lit.growKey).toBe(getMapState().scene.growKey);
    await userEvent.click(screen.getByRole("button", { name: "כל הקווים" }));
    expect(lineRows()).toHaveLength(6);
    act(() => west!.onSelect!());
    expect(lineRows()[1]).toHaveAttribute("aria-pressed", "true");
  });

  it("without the lines endpoint: the fans follow each line's next trip's shape", async () => {
    withoutLines();
    renderApp(STOP);
    // Lines 8 and 5 have a recorded trip shape in the fixtures; the others have none. They
    // leave the same way: one way out and one tag; the four lines without a shape get a tag each.
    await waitFor(() => expect(getMapState().scene.route).toHaveLength(1));
    expect(getMapState().scene.tags).toHaveLength(5);
    expect(getMapState().scene.tags!.filter((tag) => tag.along).map((tag) => tag.lines?.map((line) => line.label))).toEqual([["8", "5"]]);
    await userEvent.click(lineRows()[2]!);
    const chosen = getMapState().scene.route.find((leg) => leg.tone === "normal")!;
    // From where the stop meets the trip's shape to the shape's end.
    expect(chosen.coordinates![0]![0]).toBeCloseTo(34.77512, 3);
    expect(chosen.coordinates![0]![1]).toBeCloseTo(32.075566, 3);
    expect(chosen.coordinates!.length).toBeGreaterThan(20);
    expect(getMapState().scene.tags!.find((tag) => tag.id === "direction")).toBeDefined();
  });

  it("a line without a shape still gets its row and a tag, with no line drawn", async () => {
    withoutLines();
    renderApp(STOP);
    await waitFor(() => expect(getMapState().scene.route).toHaveLength(1));
    await userEvent.click(lineRows()[0]!);
    const scene = getMapState().scene;
    expect(scene.route.every((leg) => leg.tone === "quiet")).toBe(true);
    expect(scene.tags!.find((tag) => tag.kind === "strong")).toMatchObject({ line: { label: "172" }, text: "מסוף רדינג" });
    expect(scene.tags!.find((tag) => tag.id === "direction")).toBeUndefined();
  });

  it("rings the chosen line's next stops where the trip gives their coordinates", async () => {
    const base = fixture("recorded-trip-overnight");
    const body = structuredClone(base.body) as { data: { calls: Array<Record<string, unknown>> } };
    body.data.calls = body.data.calls.map((call, index) => ({ ...call, latitude: 32 + index / 1000, longitude: 34.77 }));
    const ref = (body.data as unknown as { tripRef: string }).tripRef;
    withoutLines();
    server.use(
      http.get("*/v1/trips/:tripRef", ({ params }) =>
        decodeURIComponent(String(params.tripRef)) === ref ? respond({ ...base, body }) : respond(fixture("recorded-problem-trip-not-found")),
      ),
    );
    renderApp(STOP);
    await waitFor(() => expect(lineRows()).toHaveLength(6));
    await userEvent.click(lineRows()[2]!);
    await waitFor(() => expect(getMapState().scene.pins).toHaveLength(8));
    const pins = getMapState().scene.pins;
    expect(pins.every((pin) => pin.role === "stop" && pin.position[0] === 34.77)).toBe(true);
    // In the order the line calls at them.
    expect(pins.map((pin) => pin.position[1])).toEqual([...pins.map((pin) => pin.position[1])].sort());
  });

  it("reads the departure's own operator and mode when the API sends them", async () => {
    server.use(
      http.get("*/v1/stops/:stopId/departures", ({ request }) => {
        const found = derivedDepartures("mot:stop:13583", new URL(request.url).searchParams.get("from"), 2);
        const body = structuredClone(found.body) as { data: Array<Record<string, unknown>> };
        body.data = body.data.map((item) => ({ ...item, operatorId: "2", operatorName: "רכבת ישראל", mode: "RAIL" }));
        return respond({ ...found, body });
      }),
    );
    renderApp(STOP);
    await waitFor(() => expect(lineRows()).toHaveLength(2));
    expect(lineRows()[0]!.querySelector(".cv-bdg")).toHaveAttribute("data-vehicle", "rail");
  });

  it("with a fix already allowed: the distance to the stop and the passenger on the map", async () => {
    restore = setLocationSource({
      current: async () => ({ ok: true, fix: { latitude: 32.0753, longitude: 34.7749, accuracyMeters: 20, at: 0 } }),
      watch: () => () => {},
    });
    renderApp(STOP);
    const heading = await screen.findByRole("heading", { level: 1, name: "דיזנגוף סנטר/דיזנגוף" });
    await waitFor(() => expect(heading.parentElement).toHaveTextContent(/40 מ׳ · 1 דק׳ הליכה$/));
    expect(getMapState().scene.user).toEqual({ position: [34.7749, 32.0753], accuracyMeters: 20 });
  });

  it("says there are no departures in the coming hours", async () => {
    server.use(
      http.get("*/v1/stops/:stopId/departures", () => {
        const found = derivedDepartures("mot:stop:13583", null, 0);
        return respond(found);
      }),
    );
    renderApp(STOP);
    expect(await screen.findByText(he["state.empty.noDepartures"])).toBeInTheDocument();
  });

  it("a stop that is not in the timetable says so, with the screen's title", async () => {
    renderApp("#/stop/mot%3Astop%3Anowhere", { lang: "en" });
    expect(await screen.findByRole("alert")).toHaveTextContent(en["error.not_found"]);
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(en["screen.stop"]);
  });
});
