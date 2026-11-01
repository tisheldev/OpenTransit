import { QueryClientProvider, type QueryClient } from "@tanstack/react-query";
import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http } from "msw";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { fixture } from "../../api/fixtures";
import { createQueryClient } from "../../api/queries";
import { I18nProvider } from "../../i18n/I18nProvider";
import type { Lang } from "../../i18n/messages";
import { setLocationSource } from "../../lib/geolocation";
import { getMapState, resetMapState } from "../../map/scene";
import { respond } from "../../mocks/handlers";
import { server } from "../../mocks/node";
import { endActiveTrip, getActiveTrip, resetActiveTripCache } from "../../nav/activeTrip";
import type { PlaceChoice, PlanDraft } from "../../plan/draft";
import { PlanProvider, usePlan } from "../../plan/PlanProvider";
import { reloadLocalState } from "../../shell/localStore";
import { SheetContext, type Snap } from "../../shell/sheet";
import { CompareScreen } from "./CompareScreen";

// One fixture-driven test per Compare state (design: Compare "States"), Hebrew first,
// the key ones again in English. Scenarios are the MSW handlers' (src/mocks/handlers.ts).

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

const baseDraft: PlanDraft = {
  from: { type: "place", place: dizengoff },
  to: { type: "place", place: technion },
  when: { mode: "depart_at", wall: "2026-10-01T08:00", offset: "auto" },
};

interface Sent {
  method: string;
  path: string;
  body: Record<string, unknown> | null;
}
let sent: Sent[] = [];
let snaps: Snap[] = [];

beforeEach(() => {
  sent = [];
  snaps = [];
  server.events.on("request:start", async ({ request }) => {
    const url = new URL(request.url);
    const body = request.method === "POST" ? ((await request.clone().json()) as Record<string, unknown>) : null;
    sent.push({ method: request.method, path: url.pathname, body });
  });
});

afterEach(() => {
  server.events.removeAllListeners();
  endActiveTrip();
  resetActiveTripCache();
  resetMapState();
  reloadLocalState();
  window.location.hash = "";
});

const journeyPosts = () => sent.filter((r) => r.method === "POST" && r.path === "/v1/journeys");
const useScenario = (name: string) => localStorage.setItem("ot-fixture-scenario", name);

/** Shows the plan's current start, so a test can see what a prompt changed. */
function DraftProbe() {
  const { draft } = usePlan();
  return <span data-testid="draft-from">{draft.from?.type === "place" ? draft.from.place.label : String(draft.from?.type ?? null)}</span>;
}

function renderCompare(lang: Lang = "he", draft: PlanDraft = baseDraft, client: QueryClient = createQueryClient()) {
  const view = render(
    <QueryClientProvider client={client}>
      <I18nProvider initialLang={lang}>
        <SheetContext.Provider value={{ snap: "half", setSnap: (snap) => snaps.push(snap) }}>
          <PlanProvider initial={draft}>
            <CompareScreen />
            <DraftProbe />
          </PlanProvider>
        </SheetContext.Provider>
      </I18nProvider>
    </QueryClientProvider>,
  );
  return { ...view, client };
}

const options = () => within(screen.getByRole("list", { name: /אפשרויות נסיעה|Trip options/ })).getAllByRole("button");
const details = () => screen.getByRole("region", { name: /פרטי מסלול|Route details/ });
const stopCounts = () => within(details()).queryAllByText(/^\d+ (תחנות|stops)$/);

describe("Compare (Hebrew)", () => {
  it("reserves three option rows while loading", () => {
    const { container } = renderCompare();
    expect(screen.getByRole("status")).toHaveAttribute("aria-busy", "true");
    expect(screen.getByRole("status")).toHaveTextContent("מחפשים מסלולים…");
    expect(container.querySelectorAll(".option-placeholder")).toHaveLength(3);
  });

  it("shows three options in the API's order with times, rank labels and one note, the first selected with its itinerary", async () => {
    renderCompare();
    await waitFor(() => expect(options()).toHaveLength(3));
    const [first, second, third] = options();
    expect(first).toHaveAttribute("aria-pressed", "true");
    expect(first).toHaveAccessibleName("אפשרות 1, מומלץ, 105 דקות, יציאה 08:07, הגעה 09:52, 2 החלפות");
    expect(second).toHaveAccessibleName(/^אפשרות 2, הכי מהיר, 104 דקות, יציאה 08:27, הגעה 10:11/);
    expect(third).toHaveAccessibleName("אפשרות 3, 133 דקות, יציאה 08:19, הגעה 10:32, 4 החלפות");
    // Each row leads with its departure – arrival, then duration, transfers and walking.
    expect(within(first!).getByText("08:07")).toBeInTheDocument();
    expect(within(first!).getByText("09:52")).toBeInTheDocument();
    expect(within(first!).getByText("מומלץ")).toBeInTheDocument();
    expect(within(first!).getByText("1 שע׳ 45 דק׳")).toBeInTheDocument();
    expect(within(first!).getByText("2 החלפות")).toBeInTheDocument();
    // One short note, not two saying the same thing.
    expect(screen.getByText("זמנים מתוכננים · לא בזמן אמת")).toBeInTheDocument();
    expect(screen.queryByText("זמנים בזמן אמת והתראות אינם זמינים")).toBeNull();

    const route = details();
    // A train is Israel Railways with its number, read from where it is boarded to where
    // it is left; never "a train to <exit stop>".
    expect(within(route).getByText("רכבת ישראל")).toBeInTheDocument();
    expect(within(route).getByText("רכבת ישראל 156 מ־השלום אל חוף הכרמל.", { exact: false })).toBeInTheDocument();
    expect(route).not.toHaveTextContent("רכבת לחוף הכרמל");
    expect(within(route).getByText("לכיוון מסוף הטייסים")).toBeInTheDocument();
    // Exit stops at their arrival times, the engine's END as the passenger's label.
    const steps = within(route).getByRole("list", { name: "שלבי המסלול" });
    expect(steps).toHaveTextContent(/09:24ירידה: חוף הכרמל/);
    expect(steps).toHaveTextContent(/09:52הגעה: טכניון/);
    expect(within(route).getByText(/^הליכה 5 דק׳ · 330 מ׳$/)).toBeInTheDocument();
    expect(within(route).getByText("המתנה 7 דק׳")).toBeInTheDocument();
    expect(route).not.toHaveTextContent("END");
    expect(route).not.toHaveTextContent("רציף");
    // No links to the stop and trip screens (not built yet).
    expect(within(route).queryAllByRole("link")).toHaveLength(0);
    // Trip details arrive in the background: stop counts.
    await waitFor(() => expect(stopCounts()).toHaveLength(3));

    const request = journeyPosts()[0]!.body!;
    expect(request).toMatchObject({
      from: { kind: "stop", stopId: "mot:stop:13583" },
      to: { kind: "coordinate", latitude: 32.7767, longitude: 35.0231 },
      departAt: "2026-10-01T08:00:00+03:00",
      results: 3,
      lang: "he",
    });

    const scene = getMapState().scene;
    expect(scene.camera).toBe("fit");
    expect(scene.route).toHaveLength(6);
    expect(scene.pins.find((pin) => pin.role === "destination")?.label).toBe("טכניון");
  });

  it("opens on the sheet the shell chose, and raises it to full for the details when an option is tapped", async () => {
    const user = userEvent.setup();
    renderCompare();
    await waitFor(() => expect(options()).toHaveLength(3));
    expect(snaps).toEqual([]);
    await user.click(options()[0]!);
    expect(snaps).toEqual(["full"]);
  });

  it("swaps the details and the map when another option is tapped, without a request", async () => {
    const user = userEvent.setup();
    renderCompare();
    await waitFor(() => expect(options()).toHaveLength(3));
    const before = journeyPosts().length;
    await user.click(options()[1]!);
    expect(options()[1]).toHaveAttribute("aria-pressed", "true");
    expect(options()[0]).toHaveAttribute("aria-pressed", "false");
    // The derived option's transfer walk has no street path: time only.
    expect(within(details()).getByText(/^הליכה כ־2 דק׳$/)).toBeInTheDocument();
    expect(journeyPosts()).toHaveLength(before);
    expect(getMapState().scene.route[3]!.coordinates).toBeNull();
  });

  it("collapses to two rows and to one", async () => {
    useScenario("compare-two");
    const { unmount } = renderCompare();
    await waitFor(() => expect(options()).toHaveLength(2));
    unmount();
    useScenario("compare-one");
    renderCompare();
    await waitFor(() => expect(options()).toHaveLength(1));
    expect(options()[0]).toHaveAccessibleName(/^אפשרות 1, מומלץ/);
  });

  it("names the day of options that leave on another day than the one asked", async () => {
    renderCompare("he", { ...baseDraft, when: { mode: "depart_at", wall: "2026-09-30T23:30", offset: "auto" } });
    await waitFor(() => expect(options()).toHaveLength(3));
    expect(options()[0]).toHaveAccessibleName(/יציאה יום ה׳, 1\.10 08:07, הגעה יום ה׳, 1\.10 09:52/);
    expect(within(options()[0]!).getByText("יום ה׳, 1.10")).toBeInTheDocument();
    expect(within(details()).getByRole("heading")).toHaveTextContent("פרטי מסלול · יום ה׳, 1.10");
  });

  it("shows no route calmly with Earlier, Later and change time", async () => {
    useScenario("compare-no-route");
    const user = userEvent.setup();
    renderCompare();
    expect(await screen.findByText("לא נמצא מסלול")).toBeInTheDocument();
    expect(screen.queryByRole("alert")).toBeNull();
    expect(screen.getByRole("button", { name: "שינוי השעה" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "מאוחר יותר" }));
    await waitFor(() => expect(journeyPosts()).toHaveLength(2));
    expect(journeyPosts()[1]!.body).toMatchObject({ departAt: "2026-10-01T09:00:00+03:00" });
    // The chip now says what was asked.
    expect(screen.getByRole("button", { name: /^שינוי השעה: יציאה 09:00/ })).toBeInTheDocument();
  });

  it("shows the coverage dates outside the service window", async () => {
    useScenario("compare-outside-window");
    renderCompare();
    const alert = await screen.findByRole("alert");
    await waitFor(() => expect(alert).toHaveTextContent(/השעה שנבחרה מחוץ ללוח הזמנים. אפשר לבחור בין .*29.* ל־.*30/));
    expect(screen.getByRole("button", { name: "שינוי השעה" })).toBeInTheDocument();
  });

  it("offers a retry when the service is unavailable, and the retry replaces the error", async () => {
    let calls = 0;
    server.use(
      http.post("*/v1/journeys", () => {
        calls += 1;
        return respond(fixture(calls === 1 ? "recorded-problem-not-ready" : "recorded-journey-routes"));
      }),
    );
    const user = userEvent.setup();
    renderCompare();
    expect(await screen.findByRole("alert")).toHaveTextContent("השירות אינו זמין זמנית.");
    await user.click(screen.getByRole("button", { name: "נסו שוב" }));
    await waitFor(() => expect(options()).toHaveLength(1));
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("treats an engine timeout as unavailable", async () => {
    useScenario("compare-timeout");
    renderCompare();
    expect(await screen.findByRole("alert")).toHaveTextContent("השירות אינו זמין זמנית.");
    expect(screen.getByRole("button", { name: "נסו שוב" })).toBeEnabled();
  });

  it("honours Retry-After when rate limited", async () => {
    useScenario("compare-rate-limited");
    renderCompare();
    expect(await screen.findByRole("alert")).toHaveTextContent("יותר מדי בקשות");
    expect(screen.getByRole("button", { name: /אפשר לנסות שוב בעוד 1/ })).toBeDisabled();
    expect(await screen.findByRole("button", { name: "נסו שוב" }, { timeout: 3000 })).toBeEnabled();
  });

  it("says when OpenTransit cannot be reached", async () => {
    useScenario("compare-offline");
    renderCompare();
    expect(await screen.findByRole("alert")).toHaveTextContent("אין חיבור ל־OpenTransit");
  });

  it("labels a walk-only option", async () => {
    useScenario("compare-walk-only");
    renderCompare();
    await waitFor(() => expect(options()).toHaveLength(2));
    expect(options()[0]).toHaveAccessibleName("אפשרות 1, מומלץ, הליכה בלבד, 18 דקות, יציאה 08:07, הגעה 08:25");
    expect(within(options()[0]!).getByText("הליכה בלבד")).toBeInTheDocument();
    expect(within(options()[0]!).getByText("1.4 ק״מ")).toBeInTheDocument();
    expect(within(details()).getByText(/^הליכה 18 דק׳ · 1.4 ק״מ$/)).toBeInTheDocument();
  });

  it("sends a searched place as its coordinate, even with a placeRef", async () => {
    const searched: PlaceChoice = { ...technion, kind: "address", placeRef: "mot:place:v1:old", refGenerationId: "gen-now" };
    renderCompare("he", { ...baseDraft, to: { type: "place", place: searched } });
    await waitFor(() => expect(options()).toHaveLength(3));
    expect(journeyPosts().map((r) => (r.body!.to as { kind: string }).kind)).toEqual(["coordinate"]);
  });

  it("shows the route without stop counts when trip details fail, and Start still works", async () => {
    useScenario("compare-trip-failed");
    const user = userEvent.setup();
    renderCompare();
    await waitFor(() => expect(options()).toHaveLength(3));
    await waitFor(() => expect(within(details()).getAllByText(/מספר התחנות לא זמין/)).toHaveLength(3));
    expect(stopCounts()).toHaveLength(0);
    await user.click(screen.getByRole("button", { name: "התחלת ניווט" }));
    expect(window.location.hash).toBe("#/navigate");
    expect(getActiveTrip()?.trips).toEqual({});
  });

  it("starts navigation with the trips already fetched, then reads Resume for the active journey", async () => {
    const user = userEvent.setup();
    const { unmount, client } = renderCompare();
    await waitFor(() => expect(options()).toHaveLength(3));
    await waitFor(() => expect(stopCounts()).toHaveLength(3));
    await user.click(screen.getByRole("button", { name: "התחלת ניווט" }));
    expect(window.location.hash).toBe("#/navigate");
    const trip = getActiveTrip()!;
    expect(Object.keys(trip.trips)).toHaveLength(3);
    expect(trip.journey.id).toBe((fixture("recorded-journey-routes").body as { data: { journeys: { id: string }[] } }).data.journeys[0]!.id);
    unmount();
    renderCompare("he", baseDraft, client);
    expect(await screen.findByRole("button", { name: "חזרה לניווט" })).toBeInTheDocument();
    await user.click(options()[1]!);
    expect(screen.getByRole("button", { name: "התחלת ניווט" })).toBeInTheDocument();
  });

  it("Later and Earlier replace the options with a shifted request, right under the rows", async () => {
    const user = userEvent.setup();
    const { container } = renderCompare();
    await waitFor(() => expect(options()).toHaveLength(3));
    // Earlier / Later sit between the options and the details.
    const order = [...container.querySelectorAll(".options, .compare-shift, .route-details")].map((el) => el.className);
    expect(order).toEqual(["options", "compare-shift", "route-details"]);
    await user.click(screen.getByRole("button", { name: "מאוחר יותר" }));
    await waitFor(() => expect(journeyPosts()).toHaveLength(2));
    expect(journeyPosts()[1]!.body).toMatchObject({ departAt: "2026-10-01T08:28:00+03:00" });
    expect(journeyPosts()[1]!.body!.arriveBy).toBeUndefined();
    await waitFor(() => expect(options()).toHaveLength(3));
    await user.click(screen.getByRole("button", { name: "מוקדם יותר" }));
    await waitFor(() => expect(journeyPosts()).toHaveLength(3));
    expect(journeyPosts()[2]!.body).toMatchObject({ arriveBy: "2026-10-01T09:51:00+03:00" });
    expect(screen.getByRole("button", { name: /^שינוי השעה: הגעה עד 09:51/ })).toBeInTheDocument();
  });

  it("keeps the previous options, dimmed and not startable, while a new time loads; new ends do not", async () => {
    let release: () => void = () => {};
    let calls = 0;
    server.use(
      http.post("*/v1/journeys", async () => {
        calls += 1;
        if (calls > 1) await new Promise<void>((resolve) => (release = resolve));
        return respond(fixture("recorded-journey-routes"));
      }),
    );
    const user = userEvent.setup();
    const { container } = renderCompare();
    await waitFor(() => expect(options()).toHaveLength(1));
    const later = screen.getByRole("button", { name: "מאוחר יותר" });
    await user.click(later);
    await waitFor(() => expect(calls).toBe(2));
    // Still on screen, busy, and the button pressed keeps focus.
    expect(options()).toHaveLength(1);
    expect(container.querySelector(".compare-answer")).toHaveAttribute("aria-busy", "true");
    expect(screen.getByRole("button", { name: "התחלת ניווט" })).toBeDisabled();
    expect(document.activeElement).toBe(later);
    act(() => release());
    await waitFor(() => expect(container.querySelector(".compare-answer")).toHaveAttribute("aria-busy", "false"));
    expect(screen.getByRole("button", { name: "התחלת ניווט" })).toBeEnabled();
    // Swapping the ends is a different trip: the old answer is not kept.
    await user.click(screen.getByRole("button", { name: "החלפת מוצא ויעד" }));
    expect(container.querySelectorAll(".option-placeholder")).toHaveLength(3);
    act(() => release());
  });

  it("changes the time from the chip: depart, +30, show", async () => {
    const user = userEvent.setup();
    renderCompare();
    await waitFor(() => expect(options()).toHaveLength(3));
    const chip = screen.getByRole("button", { name: /^שינוי השעה: יציאה 08:00/ });
    expect(chip).toHaveAttribute("aria-expanded", "false");
    await user.click(chip);
    expect(chip).toHaveAttribute("aria-expanded", "true");
    const panel = screen.getByRole("form", { name: "מתי יוצאים?" });
    // While the time is being changed there is no Start under the panel.
    expect(screen.queryByRole("button", { name: "התחלת ניווט" })).toBeNull();
    expect(within(panel).getByLabelText("יום")).toHaveValue("2026-10-01");
    expect(within(panel).getByLabelText("שעה")).toHaveValue("08:00");
    await user.click(within(panel).getByRole("radio", { name: "הגעה עד" }));
    await user.click(within(panel).getByRole("button", { name: "30 דקות מאוחר יותר" }));
    expect(within(panel).getByLabelText("שעה")).toHaveValue("08:30");
    await user.click(within(panel).getByRole("button", { name: "הצגת אפשרויות" }));
    await waitFor(() => expect(journeyPosts()).toHaveLength(2));
    expect(journeyPosts()[1]!.body).toMatchObject({ arriveBy: "2026-10-01T08:30:00+03:00" });
    expect(screen.queryByRole("form")).toBeNull();
    expect(screen.getByRole("button", { name: /^שינוי השעה: הגעה עד 08:30/ })).toBeInTheDocument();
  });

  it("goes back to now in one tap", async () => {
    const user = userEvent.setup();
    renderCompare();
    await waitFor(() => expect(options()).toHaveLength(3));
    await user.click(screen.getByRole("button", { name: /^שינוי השעה/ }));
    await user.click(screen.getByRole("radio", { name: "עכשיו" }));
    await waitFor(() => expect(journeyPosts()).toHaveLength(2));
    expect(journeyPosts()[1]!.body!.departAt).toMatch(/[+-]\d{2}:\d{2}$/);
    expect(screen.getByRole("button", { name: "שינוי השעה: עכשיו" })).toBeInTheDocument();
  });

  it("asks where to when there is no destination", () => {
    renderCompare("he", { ...baseDraft, to: null });
    expect(screen.getByText("לאן נוסעים?")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "בחירת יעד" })).toHaveAttribute("href", "#/search/to");
    expect(screen.getByRole("link", { name: "חזרה לבית" })).toHaveAttribute("href", "#/");
    expect(journeyPosts()).toHaveLength(0);
  });

  it("asks calmly where from when no start is chosen, with saved and recent places one tap away", async () => {
    localStorage.setItem(
      "opentransit",
      JSON.stringify({
        version: 1,
        settings: { lang: "he" },
        home: { id: "home", label: "הבית ברמת גן", latitude: 32.08, longitude: 34.81, stopId: null, placeRefHint: null, savedAt: "2026-10-01T00:00:00Z" },
        work: null,
        favourites: [],
        recents: [
          // The destination itself is never offered as the start.
          { id: "r1", label: "טכניון", latitude: 32.7767, longitude: 35.0231, stopId: null, placeRefHint: null, savedAt: "2026-10-01T00:00:00Z" },
          { id: "r2", label: "דיזנגוף סנטר", latitude: 32.0753, longitude: 34.7749, stopId: "mot:stop:13583", placeRefHint: null, savedAt: "2026-10-01T00:00:00Z" },
        ],
      }),
    );
    reloadLocalState();
    const user = userEvent.setup();
    renderCompare("he", { ...baseDraft, from: null });
    expect(screen.getByText("מאיפה יוצאים?")).toBeInTheDocument();
    expect(screen.queryByRole("alert")).toBeNull();
    expect(screen.getByRole("link", { name: "בחירת נקודת מוצא" })).toHaveAttribute("href", "#/search/from");
    const places = within(screen.getByRole("list", { name: "מקומות שמורים ואחרונים" })).getAllByRole("button");
    expect(places.map((place) => place.textContent)).toEqual(["בית", "דיזנגוף סנטר"]);
    expect(journeyPosts()).toHaveLength(0);
    await user.click(places[1]!);
    expect(screen.getByTestId("draft-from")).toHaveTextContent("דיזנגוף סנטר");
    await waitFor(() => expect(options()).toHaveLength(3));
    expect(journeyPosts()[0]!.body).toMatchObject({ from: { kind: "stop", stopId: "mot:stop:13583" } });
  });

  it("asks for a starting point calmly when location is denied", async () => {
    const restore = setLocationSource({ current: async () => ({ ok: false, error: "denied" }), watch: () => () => {} });
    try {
      renderCompare("he", { ...baseDraft, from: { type: "myLocation" } });
      expect(await screen.findByText("אין הרשאה לגשת למיקום שלך.")).toBeInTheDocument();
      expect(screen.getByText("מאיפה יוצאים?")).toBeInTheDocument();
      expect(screen.queryByRole("alert")).toBeNull();
      expect(screen.getByRole("link", { name: "בחירת נקודת מוצא" })).toHaveAttribute("href", "#/search/from");
      // Denied cannot be retried from here; it is the browser's setting.
      expect(screen.queryByRole("button", { name: "ניסיון נוסף" })).toBeNull();
      expect(journeyPosts()).toHaveLength(0);
    } finally {
      restore();
    }
  });

  it("tries the location again when it was only unavailable", async () => {
    let calls = 0;
    const restore = setLocationSource({
      current: async () => {
        calls += 1;
        return calls === 1 ? { ok: false, error: "timeout" } : { ok: true, fix: { latitude: 32.08, longitude: 34.78, accuracyMeters: 10, at: 0 } };
      },
      watch: () => () => {},
    });
    try {
      const user = userEvent.setup();
      renderCompare("he", { ...baseDraft, from: { type: "myLocation" } });
      expect(await screen.findByText("לא הצלחנו לקבל את המיקום שלך.")).toBeInTheDocument();
      await user.click(screen.getByRole("button", { name: "ניסיון נוסף" }));
      await waitFor(() => expect(options()).toHaveLength(3));
      expect(journeyPosts()[0]!.body).toMatchObject({ from: { kind: "coordinate", latitude: 32.08, longitude: 34.78 } });
    } finally {
      restore();
    }
  });

  it("refuses a time skipped by the spring change", async () => {
    const user = userEvent.setup();
    renderCompare("he", { ...baseDraft, when: { mode: "depart_at", wall: "2026-03-27T01:00", offset: "auto" } });
    await waitFor(() => expect(options()).toHaveLength(3));
    await user.click(screen.getByRole("button", { name: /^שינוי השעה/ }));
    const time = screen.getByLabelText("שעה");
    await user.clear(time);
    await user.type(time, "02:30");
    await user.click(screen.getByRole("button", { name: "הצגת אפשרויות" }));
    expect(screen.getByRole("alert")).toHaveTextContent("השעה הזאת לא קיימת");
    expect(journeyPosts()).toHaveLength(1);
  });

  it("asks which repeated hour in autumn and sends the chosen offset", async () => {
    const user = userEvent.setup();
    renderCompare("he", { ...baseDraft, when: { mode: "depart_at", wall: "2026-10-25T00:30", offset: "auto" } });
    await waitFor(() => expect(options()).toHaveLength(3));
    await user.click(screen.getByRole("button", { name: /^שינוי השעה/ }));
    await user.click(screen.getByRole("button", { name: "60 דקות מאוחר יותר" }));
    expect(screen.getByLabelText("שעה")).toHaveValue("01:30");
    await user.click(screen.getByRole("button", { name: "הצגת אפשרויות" }));
    expect(screen.getByRole("alert")).toHaveTextContent("מופיעה פעמיים");
    await user.click(screen.getByRole("button", { name: /השנייה/ }));
    await waitFor(() => expect(journeyPosts().at(-1)!.body).toMatchObject({ departAt: "2026-10-25T01:30:00+02:00" }));
  });
});

describe("Compare (English)", () => {
  it("shows options, ranks and a train by its operator", async () => {
    renderCompare("en");
    await waitFor(() => expect(options()).toHaveLength(3));
    expect(options()[0]).toHaveAccessibleName("Option 1, Recommended, 105 minutes, departs 08:07, arrives 09:52, 2 transfers");
    expect(options()[1]).toHaveAccessibleName(/^Option 2, Fastest/);
    // The recorded answer's names are Hebrew; the words around them are English.
    expect(within(details()).getByText("רכבת ישראל")).toBeInTheDocument();
    expect(within(details()).getByText("towards מסוף הטייסים")).toBeInTheDocument();
    expect(screen.getByText("Scheduled times · not live")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Start navigation" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Change time: Depart 08:00, Thu 1 Oct" })).toBeInTheDocument();
    expect(journeyPosts()[0]!.body).toMatchObject({ lang: "en" });
  });

  it("shows no route and failures in English", async () => {
    useScenario("compare-no-route");
    const { unmount } = renderCompare("en");
    expect(await screen.findByText("No route found")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Earlier" })).toBeEnabled();
    unmount();
    useScenario("compare-unavailable");
    renderCompare("en");
    expect(await screen.findByRole("alert")).toHaveTextContent(/temporarily unavailable/i);
    await act(async () => {});
  });

  it("asks for a destination in English", () => {
    renderCompare("en", { ...baseDraft, to: null });
    expect(screen.getByRole("link", { name: "Choose a destination" })).toBeInTheDocument();
  });
});
