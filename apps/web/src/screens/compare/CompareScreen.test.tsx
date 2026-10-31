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
import { PlanProvider } from "../../plan/PlanProvider";
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

beforeEach(() => {
  sent = [];
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
  window.location.hash = "";
});

const journeyPosts = () => sent.filter((r) => r.method === "POST" && r.path === "/v1/journeys");
const useScenario = (name: string) => localStorage.setItem("ot-fixture-scenario", name);

function renderCompare(lang: Lang = "he", draft: PlanDraft = baseDraft, client: QueryClient = createQueryClient()) {
  const view = render(
    <QueryClientProvider client={client}>
      <I18nProvider initialLang={lang}>
        <PlanProvider initial={draft}>
          <CompareScreen />
        </PlanProvider>
      </I18nProvider>
    </QueryClientProvider>,
  );
  return { ...view, client };
}

const options = () => within(screen.getByRole("list", { name: /אפשרויות נסיעה|Trip options/ })).getAllByRole("button");

describe("Compare (Hebrew)", () => {
  it("reserves three chart rows while loading", () => {
    const { container } = renderCompare();
    expect(screen.getByRole("status")).toHaveAttribute("aria-busy", "true");
    expect(screen.getByRole("status")).toHaveTextContent("מחפשים מסלולים…");
    expect(container.querySelectorAll(".chart-row-placeholder")).toHaveLength(3);
  });

  it("shows three options in the API's order with rank labels, the first selected with its details", async () => {
    renderCompare();
    await waitFor(() => expect(options()).toHaveLength(3));
    const [first, second, third] = options();
    expect(first).toHaveAttribute("aria-pressed", "true");
    expect(first).toHaveAccessibleName("אפשרות 1, מומלץ, 105 דקות, יציאה 08:07, 2 החלפות");
    expect(second).toHaveAccessibleName(/^אפשרות 2, הכי מהיר, 104 דקות, יציאה 08:27/);
    expect(third).toHaveAccessibleName("אפשרות 3, 133 דקות, יציאה 08:19, 4 החלפות");
    expect(screen.getByText("הזמנים מתוכננים, לא בזמן אמת")).toBeInTheDocument();
    expect(screen.getByText("זמנים בזמן אמת והתראות אינם זמינים")).toBeInTheDocument();

    const details = screen.getByRole("region", { name: /פרטי מסלול/ });
    expect(within(details).getByText("רכבת לחוף הכרמל")).toBeInTheDocument();
    expect(within(details).getByText("קו 8 לכיוון מסוף הטייסים")).toBeInTheDocument();
    expect(within(details).getByText(/הליכה 5 דק׳ · 330 מ׳ אל טכניון/)).toBeInTheDocument();
    expect(details).not.toHaveTextContent("END");
    expect(details).not.toHaveTextContent("רציף");
    // Trip details arrive in the background: stop count and exit.
    await waitFor(() => expect(within(details).getAllByText(/\d+ תחנות ·/).length).toBe(3));
    expect(within(details).getByText(/ירידה ב־חוף הכרמל/)).toBeInTheDocument();

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

  it("swaps the details and the map when another option is tapped, without a request", async () => {
    const user = userEvent.setup();
    renderCompare();
    await waitFor(() => expect(options()).toHaveLength(3));
    const before = journeyPosts().length;
    await user.click(options()[1]!);
    expect(options()[1]).toHaveAttribute("aria-pressed", "true");
    expect(options()[0]).toHaveAttribute("aria-pressed", "false");
    const details = screen.getByRole("region", { name: /פרטי מסלול/ });
    // The derived option's transfer walk has no street path: time only.
    expect(within(details).getByText(/^הליכה כ־2 דק׳/)).toBeInTheDocument();
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
    expect(options()[0]).toHaveAccessibleName("אפשרות 1, מומלץ, הליכה בלבד, 18 דקות, יציאה 08:07");
    expect(within(options()[0]!).getByText("הליכה בלבד")).toBeInTheDocument();
    const details = screen.getByRole("region", { name: /פרטי מסלול/ });
    expect(within(details).getByText(/הליכה 18 דק׳ · 1.4 ק״מ אל טכניון/)).toBeInTheDocument();
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
    const details = screen.getByRole("region", { name: /פרטי מסלול/ });
    await waitFor(() => expect(within(details).getAllByText(/מספר התחנות אינו זמין/)).toHaveLength(3));
    expect(details).not.toHaveTextContent(/\d+ תחנות/);
    await user.click(screen.getByRole("button", { name: "התחלת ניווט" }));
    expect(window.location.hash).toBe("#/navigate");
    expect(getActiveTrip()?.trips).toEqual({});
  });

  it("starts navigation with the trips already fetched, then reads Resume for the active journey", async () => {
    const user = userEvent.setup();
    const { unmount, client } = renderCompare();
    await waitFor(() => expect(options()).toHaveLength(3));
    const details = screen.getByRole("region", { name: /פרטי מסלול/ });
    await waitFor(() => expect(within(details).getAllByText(/\d+ תחנות ·/)).toHaveLength(3));
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

  it("Later replaces the chart with options departing a minute after the latest shown", async () => {
    const user = userEvent.setup();
    renderCompare();
    await waitFor(() => expect(options()).toHaveLength(3));
    await user.click(screen.getByRole("button", { name: "מאוחר יותר" }));
    await waitFor(() => expect(journeyPosts()).toHaveLength(2));
    expect(journeyPosts()[1]!.body).toMatchObject({ departAt: "2026-10-01T08:28:00+03:00" });
    expect(journeyPosts()[1]!.body!.arriveBy).toBeUndefined();
    await waitFor(() => expect(options()).toHaveLength(3));
    await user.click(screen.getByRole("button", { name: "מוקדם יותר" }));
    await waitFor(() => expect(journeyPosts()).toHaveLength(3));
    expect(journeyPosts()[2]!.body).toMatchObject({ arriveBy: "2026-10-01T09:51:00+03:00" });
  });

  it("asks for a destination when there is none", () => {
    renderCompare("he", { ...baseDraft, to: null });
    expect(screen.getByText("עוד לא נבחר יעד.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "בחירת יעד" })).toHaveAttribute("href", "#/search/to");
    expect(screen.getByRole("link", { name: "חזרה לבית" })).toHaveAttribute("href", "#/");
    expect(journeyPosts()).toHaveLength(0);
  });

  it("asks for a starting point when location is denied", async () => {
    const restore = setLocationSource({ current: async () => ({ ok: false, error: "denied" }), watch: () => () => {} });
    try {
      renderCompare("he", { ...baseDraft, from: { type: "myLocation" } });
      expect(await screen.findByRole("alert")).toHaveTextContent("אין הרשאה למיקום");
      expect(screen.getByRole("link", { name: "בחירת נקודת מוצא" })).toHaveAttribute("href", "#/search/from");
      expect(journeyPosts()).toHaveLength(0);
    } finally {
      restore();
    }
  });

  it("refuses a time skipped by the clock change and asks which repeated hour", async () => {
    const user = userEvent.setup();
    renderCompare("he", { ...baseDraft, when: { mode: "now" } });
    await waitFor(() => expect(options()).toHaveLength(3));
    expect(journeyPosts()[0]!.body!.departAt).toMatch(/[+-]\d{2}:\d{2}$/);
    await user.click(screen.getByRole("radio", { name: "יציאה ב־" }));
    const picker = screen.getByLabelText("תאריך ושעה (שעון ישראל)");
    await user.clear(picker);
    await user.type(picker, "2026-03-27T02:30");
    await user.click(screen.getByRole("button", { name: "הצגה" }));
    expect(screen.getByRole("alert")).toHaveTextContent("השעה הזאת לא קיימת");
    await user.clear(picker);
    await user.type(picker, "2026-10-25T01:30");
    await user.click(screen.getByRole("button", { name: "הצגה" }));
    expect(screen.getByRole("alert")).toHaveTextContent("מופיעה פעמיים");
    await user.click(screen.getByRole("button", { name: /השנייה/ }));
    await waitFor(() => expect(journeyPosts().at(-1)!.body).toMatchObject({ departAt: "2026-10-25T01:30:00+02:00" }));
  });
});

describe("Compare (English)", () => {
  it("shows options, ranks and a train named by its destination", async () => {
    renderCompare("en");
    await waitFor(() => expect(options()).toHaveLength(3));
    expect(options()[0]).toHaveAccessibleName("Option 1, Recommended, 105 minutes, departs 08:07, 2 transfers");
    expect(options()[1]).toHaveAccessibleName(/^Option 2, Fastest/);
    expect(screen.getByText("Train to חוף הכרמל")).toBeInTheDocument();
    expect(screen.getByText("Times are scheduled, not live")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Start navigation" })).toBeInTheDocument();
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
