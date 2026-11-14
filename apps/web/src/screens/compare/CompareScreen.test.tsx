import { QueryClientProvider, type QueryClient } from "@tanstack/react-query";
import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http } from "msw";
import { useEffect, type ComponentType } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fixture } from "../../api/fixtures";
import { createQueryClient } from "../../api/queries";
import { I18nProvider } from "../../i18n/I18nProvider";
import type { Lang } from "../../i18n/messages";
import { setLocationSource } from "../../lib/geolocation";
import { getMapState, resetMapState, type MapTag } from "../../map/scene";
import { respond } from "../../mocks/handlers";
import { server } from "../../mocks/node";
import { endActiveTrip, getActiveTrip, resetActiveTripCache } from "../../nav/activeTrip";
import type { PlaceChoice, PlanDraft } from "../../plan/draft";
import { PlanProvider, usePlan } from "../../plan/PlanProvider";
import { reloadLocalState } from "../../shell/localStore";
import { SheetContext, type Snap } from "../../shell/sheet";
import { CompareScreen, RouteScreen } from "./CompareScreen";

// Compare as the approved boards (11 November 2026): Choose (every option on the map,
// option rows, "פרטי המסלול") and Step (route details at #/route: the timeline, a tapped
// leg framed on the map, "כל המסלול", save and "יוצאים לדרך"). Fixture-driven, Hebrew
// first, the key ones again in English. Scenarios are the MSW handlers'
// (src/mocks/handlers.ts). The clock is set to 08:03 on the fixtures' day (Date only),
// so the first option leaves "בעוד 4 דק׳".

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
  vi.useFakeTimers({ toFake: ["Date"], now: new Date("2026-10-01T08:03:00+03:00"), shouldAdvanceTime: true });
  sent = [];
  snaps = [];
  server.events.on("request:start", async ({ request }) => {
    const url = new URL(request.url);
    const body = request.method === "POST" ? ((await request.clone().json()) as Record<string, unknown>) : null;
    sent.push({ method: request.method, path: url.pathname, body });
  });
});

afterEach(() => {
  vi.useRealTimers();
  server.events.removeAllListeners();
  endActiveTrip();
  resetActiveTripCache();
  resetMapState();
  localStorage.removeItem("opentransit");
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

function renderScreen(
  Screen: ComponentType,
  lang: Lang = "he",
  draft: PlanDraft = baseDraft,
  client: QueryClient = createQueryClient(),
  selected = 0,
) {
  function Select({ index }: { index: number }) {
    const { selected: current, setSelected } = usePlan();
    useEffect(() => {
      if (current !== index) setSelected(index);
    }, [current, index, setSelected]);
    return null;
  }
  const view = render(
    <QueryClientProvider client={client}>
      <I18nProvider initialLang={lang}>
        <SheetContext.Provider value={{ snap: "half", setSnap: (snap) => snaps.push(snap), fitHalf: () => {} }}>
          <PlanProvider initial={draft}>
            {selected > 0 && <Select index={selected} />}
            <Screen />
            <DraftProbe />
          </PlanProvider>
        </SheetContext.Provider>
      </I18nProvider>
    </QueryClientProvider>,
  );
  return { ...view, client };
}
const renderCompare = (lang: Lang = "he", draft: PlanDraft = baseDraft, client?: QueryClient) => renderScreen(CompareScreen, lang, draft, client);
const renderRoute = (lang: Lang = "he", draft: PlanDraft = baseDraft, client?: QueryClient, selected = 0) =>
  renderScreen(RouteScreen, lang, draft, client, selected);

const options = () => within(screen.getByRole("list", { name: /אפשרויות נסיעה|Trip options/ })).getAllByRole("button");
const details = () => screen.getByRole("region", { name: /פרטי מסלול|Route details/ });
const legButtons = () => [...details().querySelectorAll<HTMLElement>("button.compare-tl-leg")];
/** Elements whose whole text (digits are in their own <bdi>) matches. */
const withText = (root: HTMLElement, selector: string, text: string | RegExp) =>
  [...root.querySelectorAll<HTMLElement>(selector)].filter((el) => (typeof text === "string" ? el.textContent === text : text.test(el.textContent ?? "")));
const stopCounts = () => withText(details(), ".compare-stops", /^\d+ (תחנות|stops)$/);
const scene = () => getMapState().scene;
/** Favourites as stored (storage/local.ts). */
const storedFavourites = () => (JSON.parse(localStorage.getItem("opentransit") ?? "{}") as { favourites?: unknown[] }).favourites ?? [];
const tag = (id: string): MapTag | undefined => scene().tags?.find((item) => item.id === id);

describe("Choose (Hebrew)", () => {
  it("reserves three option rows while loading", () => {
    const { container } = renderCompare();
    expect(screen.getByRole("status")).toHaveAttribute("aria-busy", "true");
    expect(screen.getByRole("status")).toHaveTextContent("מחפשים מסלולים…");
    expect(container.querySelectorAll(".option-placeholder")).toHaveLength(3);
  });

  it("shows the destination, the start and the time tag, then each option as one sentence", async () => {
    renderCompare();
    await waitFor(() => expect(options()).toHaveLength(3));
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("טכניון");
    expect(screen.getByRole("button", { name: /^מוצא: ?מדיזנגוף סנטר$/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^שינוי השעה: יציאה 08:00/ })).toHaveClass("b-tag");
    const [first, second, third] = options();
    expect(first).toHaveAttribute("aria-pressed", "true");
    expect(first).toHaveClass("b-op", "b-op--on");
    expect(first).toHaveAccessibleName("אפשרות 1, 105 דקות, יציאה 08:07, הגעה 09:52, 2 החלפות, קווים: 8, רכבת, 1, בעוד 4 דק׳");
    expect(second).toHaveAccessibleName(/^אפשרות 2, 104 דקות, יציאה 08:27, הגעה 10:11, .*בעוד 24 דק׳$/);
    expect(third).toHaveAccessibleName(/^אפשרות 3, 133 דקות, יציאה 08:19, הגעה 10:32, 4 החלפות/);
    // Line 1: departure ← arrival and the strong countdown on the chosen row, muted on the others.
    expect(within(first!).getByText("08:07")).toHaveClass("num");
    expect(within(first!).getByText("09:52")).toHaveClass("num");
    expect(first!.querySelector(".b-tag--strong")).toHaveTextContent("בעוד 4 דק׳");
    expect(second!.querySelector(".b-tag--strong")).toBeNull();
    expect(second!.querySelector(".b-op__l1 .b-mu")).toHaveTextContent("בעוד 24 דק׳");
    // Line 2: the line badges between chevrons, then the duration.
    expect([...first!.querySelectorAll(".ot-line")].map((badge) => badge.textContent)).toEqual(["8", "רכבת", "1"]);
    expect(first!.querySelector(".b-op__dur")).toHaveTextContent("1:45 שע׳");
    // One "scheduled" note, no chart and no rank labels.
    expect(screen.getAllByText(/מתוכנן/)).toHaveLength(1);
    expect(document.querySelector(".ot-lbar, .compare-chart")).toBeNull();
    expect(screen.queryByText("מומלץ")).toBeNull();
    expect(screen.getByRole("button", { name: "פרטי המסלול" })).toBeEnabled();

    const request = journeyPosts()[0]!.body!;
    expect(request).toMatchObject({
      from: { kind: "stop", stopId: "mot:stop:13583" },
      to: { kind: "coordinate", latitude: 32.7767, longitude: 35.0231 },
      departAt: "2026-10-01T08:00:00+03:00",
      results: 3,
      lang: "he",
    });
  });

  it("draws every option on the map: the chosen one in colour with its badges, the others faded with their arrival time", async () => {
    renderCompare();
    await waitFor(() => expect(options()).toHaveLength(3));
    const drawn = scene();
    expect(drawn.camera).toBe("fit");
    const faded = drawn.route.filter((leg) => leg.tone === "faded");
    const own = drawn.route.filter((leg) => leg.tone !== "faded");
    expect(own).toHaveLength(6);
    expect(faded.length).toBeGreaterThan(0);
    // The chosen option is drawn last (over the faded ones); no leg carries the map's own text label.
    expect(drawn.route.slice(-6)).toEqual(own);
    expect(drawn.route.every((leg) => leg.label === null)).toBe(true);
    // A line badge on each ride of the chosen option.
    expect(drawn.tags!.filter((item) => item.line).map((item) => item.line!.label)).toEqual(["8", "רכבת", "1"]);
    // The others: a faded tag with the arrival time that chooses it, outlined in its line colour.
    expect(tag("option-1")).toMatchObject({ kind: "faded", text: "10:11", ariaLabel: "האפשרות שמגיעה ב־10:11" });
    expect(tag("option-1")!.accent).toBeTruthy();
    expect(tag("option-2")).toMatchObject({ kind: "faded", text: "10:32" });
    expect(tag("option-0")).toBeUndefined();
    // The destination: a strong tag with its name, and its pin.
    expect(tag("destination")).toMatchObject({ kind: "strong", text: "טכניון" });
    expect(drawn.pins.find((pin) => pin.role === "destination")?.label).toBe("טכניון");
  });

  it("chooses by row without a request, and the map follows", async () => {
    const user = userEvent.setup();
    renderCompare();
    await waitFor(() => expect(options()).toHaveLength(3));
    const before = journeyPosts().length;
    await user.click(options()[1]!);
    expect(options()[1]).toHaveAttribute("aria-pressed", "true");
    expect(options()[0]).toHaveAttribute("aria-pressed", "false");
    expect(options()[1]!.querySelector(".b-tag--strong")).toHaveTextContent("בעוד 24 דק׳");
    expect(journeyPosts()).toHaveLength(before);
    expect(tag("option-1")).toBeUndefined();
    expect(tag("option-0")).toMatchObject({ text: "09:52" });
    // The chosen option keeps the sheet where it is (board Choose: half).
    expect(snaps).toEqual([]);
  });

  it("chooses by the faded tag on the map", async () => {
    renderCompare();
    await waitFor(() => expect(options()).toHaveLength(3));
    act(() => tag("option-2")!.onSelect!());
    expect(options()[2]).toHaveAttribute("aria-pressed", "true");
    expect(options()[0]).toHaveAttribute("aria-pressed", "false");
    expect(tag("option-2")).toBeUndefined();
    expect(tag("option-0")).toMatchObject({ kind: "faded", text: "09:52" });
  });

  it("opens route details with פרטי המסלול", async () => {
    const user = userEvent.setup();
    renderCompare();
    await waitFor(() => expect(options()).toHaveLength(3));
    await user.click(screen.getByRole("button", { name: "פרטי המסלול" }));
    expect(window.location.hash).toBe("#/route");
  });

  it("opens Search for the start from the line under the destination", async () => {
    const user = userEvent.setup();
    renderCompare();
    await user.click(screen.getByRole("button", { name: /^מוצא:/ }));
    expect(window.location.hash).toBe("#/search/from");
  });

  it("collapses to two rows and to one", async () => {
    useScenario("compare-two");
    const { unmount } = renderCompare();
    await waitFor(() => expect(options()).toHaveLength(2));
    unmount();
    useScenario("compare-one");
    renderCompare();
    await waitFor(() => expect(options()).toHaveLength(1));
    expect(options()[0]).toHaveAccessibleName(/^אפשרות 1, /);
    expect(scene().tags!.filter((item) => item.kind === "faded")).toHaveLength(0);
  });

  it("names the day of options that leave on another day than the one asked", async () => {
    renderCompare("he", { ...baseDraft, when: { mode: "depart_at", wall: "2026-09-30T23:30", offset: "auto" } });
    await waitFor(() => expect(options()).toHaveLength(3));
    expect(options()[0]).toHaveAccessibleName(/יציאה יום ה׳, 1\.10 08:07, הגעה יום ה׳, 1\.10 09:52/);
  });

  it("labels a walk-only option", async () => {
    useScenario("compare-walk-only");
    renderCompare();
    await waitFor(() => expect(options()).toHaveLength(2));
    expect(options()[0]).toHaveAccessibleName("אפשרות 1, הליכה בלבד, 18 דקות, יציאה 08:07, הגעה 08:25, בעוד 4 דק׳");
    expect(options()[0]!.querySelector(".b-op__l2")).toHaveTextContent("הליכה בלבד · 1.4 ק״מ");
  });

  it("shows no route calmly with Earlier, Later and change time", async () => {
    useScenario("compare-no-route");
    const user = userEvent.setup();
    renderCompare();
    expect(await screen.findByText("לא נמצא מסלול")).toBeInTheDocument();
    expect(screen.queryByRole("alert")).toBeNull();
    expect(screen.getByRole("button", { name: "שינוי השעה" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "פרטי המסלול" })).toBeNull();
    await user.click(screen.getByRole("button", { name: "מאוחר יותר" }));
    await waitFor(() => expect(journeyPosts()).toHaveLength(2));
    expect(journeyPosts()[1]!.body).toMatchObject({ departAt: "2026-10-01T09:00:00+03:00" });
    // The tag now says what was asked.
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

  it("sends a searched place as its coordinate, even with a placeRef", async () => {
    const searched: PlaceChoice = { ...technion, kind: "address", placeRef: "mot:place:v1:old", refGenerationId: "gen-now" };
    renderCompare("he", { ...baseDraft, to: { type: "place", place: searched } });
    await waitFor(() => expect(options()).toHaveLength(3));
    expect(journeyPosts().map((r) => (r.body!.to as { kind: string }).kind)).toEqual(["coordinate"]);
  });

  it("keeps the previous options, dimmed and not openable, while a new time loads", async () => {
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
    await user.click(screen.getByRole("button", { name: /^שינוי השעה/ }));
    await user.click(screen.getByRole("button", { name: "30 דקות מאוחר יותר" }));
    await user.click(screen.getByRole("button", { name: "הצגת אפשרויות" }));
    await waitFor(() => expect(calls).toBe(2));
    expect(options()).toHaveLength(1);
    expect(container.querySelector(".compare-answer")).toHaveAttribute("aria-busy", "true");
    expect(screen.getByRole("button", { name: "פרטי המסלול" })).toBeDisabled();
    act(() => release());
    await waitFor(() => expect(container.querySelector(".compare-answer")).toHaveAttribute("aria-busy", "false"));
    expect(screen.getByRole("button", { name: "פרטי המסלול" })).toBeEnabled();
  });

  it("changes the time from the tag: depart, +30, show", async () => {
    const user = userEvent.setup();
    renderCompare();
    await waitFor(() => expect(options()).toHaveLength(3));
    const chip = screen.getByRole("button", { name: /^שינוי השעה: יציאה 08:00/ });
    expect(chip).toHaveAttribute("aria-expanded", "false");
    await user.click(chip);
    expect(chip).toHaveAttribute("aria-expanded", "true");
    const panel = screen.getByRole("form", { name: "מתי יוצאים?" });
    // While the time is being changed there is no button under the panel.
    expect(screen.queryByRole("button", { name: "פרטי המסלול" })).toBeNull();
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

describe("Route details (Hebrew)", () => {
  it("shows the header and the timeline: stops with times, walks with minutes and metres, rides with badge, headsign and stops", async () => {
    renderRoute();
    const heading = await screen.findByRole("heading", { level: 1, name: /יציאה 08:07, הגעה 09:52/ });
    expect(heading).toHaveTextContent("08:07");
    expect(document.querySelector(".route-head__duration")).toHaveTextContent("1:45 שע׳");
    expect(document.querySelector(".route-head .b-tag--strong")).toHaveTextContent("בעוד 4 דק׳");
    const route = details();
    const timeline = within(route).getByRole("group", { name: "שלבי המסלול" });
    // Stops: a filled dot at the start, a square at the arrival; the engine's END as the passenger's label.
    expect(timeline.querySelector(".compare-tl-stop--origin .b-dot--filled")).not.toBeNull();
    expect(timeline.querySelector(".compare-tl-stop--destination .b-dot--end")).not.toBeNull();
    expect(timeline.querySelector(".compare-tl-stop--destination")).toHaveTextContent("09:52טכניון");
    expect(timeline).toHaveTextContent(/09:24חוף הכרמל/);
    expect(route).not.toHaveTextContent("END");
    expect(route).not.toHaveTextContent("רציף");
    // Rides: badge, headsign, a bar in the line colour; a train by its operator and number.
    expect(within(route).getByText("מסוף הטייסים")).toBeInTheDocument();
    expect(within(route).getByText("רכבת ישראל")).toBeInTheDocument();
    expect(within(route).getByText("רכבת 156")).toBeInTheDocument();
    expect(within(route).getByText("רכבת ישראל 156 מ־השלום אל חוף הכרמל.", { exact: false })).toBeInTheDocument();
    expect(route).not.toHaveTextContent("רכבת לחוף הכרמל");
    expect(timeline.querySelectorAll(".b-bar")).toHaveLength(3);
    // Walks: ink dots, minutes and metres; the wait before the next ride.
    expect(timeline.querySelectorAll(".b-dots")).toHaveLength(3);
    expect(withText(route, ".compare-walk", "הליכה 5 דק׳ · 330 מ׳")).toHaveLength(1);
    expect(withText(route, ".compare-wait", "המתנה 7 דק׳")).toHaveLength(1);
    // Every leg is a button; stop names are buttons that open the stop (board 6), not links.
    expect(legButtons()).toHaveLength(6);
    expect(within(route).queryAllByRole("link")).toHaveLength(0);
    // Trip details arrive in the background: stop counts.
    await waitFor(() => expect(stopCounts()).toHaveLength(3));
  });

  it("opens with the first leg on the map; tapping a leg zooms to it, with the boarding stop pinned", async () => {
    const user = userEvent.setup();
    renderRoute();
    await waitFor(() => expect(legButtons()).toHaveLength(6));
    const [ride, walk, rail, , , lastWalk] = legButtons();
    expect(ride).toHaveAttribute("aria-pressed", "true");
    expect(ride).toHaveClass("b-tl--on");
    expect(ride).toHaveTextContent("מוצג במפה");
    const leg = (i: number) => scene().route[i]!;
    const points = (i: number) => leg(i).coordinates ?? [leg(i).from, leg(i).to];
    expect(scene().fitTo).toEqual(points(0));
    // A ride's own boarding stop: a large pin and its strong tag (direction; the side once the API says).
    expect(scene().stopPins).toEqual([expect.objectContaining({ id: "board", position: leg(0).from, selected: true, ariaLabel: expect.stringMatching(/^תחנת העלייה: /) })]);
    expect(tag("board")).toMatchObject({ kind: "strong", text: "לכיוון מסוף הטייסים" });

    // A walk to a train: framed, the station pinned; a train known by number only has no direction tag.
    await user.click(walk!);
    expect(walk).toHaveAttribute("aria-pressed", "true");
    expect(ride).toHaveAttribute("aria-pressed", "false");
    expect(within(details()).getAllByText("מוצג במפה")).toHaveLength(1);
    expect(scene().fitTo).toEqual(points(1));
    expect(scene().stopPins?.[0]?.position).toEqual(leg(2).from);
    expect(tag("board")).toBeUndefined();
    await user.click(rail!);
    expect(scene().fitTo).toEqual(points(2));
    // The last walk leads to the destination: no boarding pin.
    await user.click(lastWalk!);
    expect(scene().fitTo).toEqual(points(5));
    expect(scene().stopPins).toEqual([]);
    // Each ride keeps its badge on the map.
    expect(scene().tags!.filter((item) => item.line)).toHaveLength(3);
  });

  it("כל המסלול zooms back out to the whole route", async () => {
    const user = userEvent.setup();
    renderRoute();
    await waitFor(() => expect(legButtons()).toHaveLength(6));
    const whole = screen.getByRole("button", { name: "כל המסלול" });
    await user.click(whole);
    expect(scene().fitTo).toBeNull();
    expect(scene().stopPins ?? []).toEqual([]);
    expect(legButtons().every((button) => button.getAttribute("aria-pressed") === "false")).toBe(true);
    expect(screen.queryByRole("button", { name: "כל המסלול" })).toBeNull();
    expect(screen.getByRole("heading", { level: 1 })).toHaveFocus();
    await user.click(legButtons()[3]!);
    expect(screen.getByRole("button", { name: "כל המסלול" })).toBeInTheDocument();
  });

  it("shows the option chosen on Choose, with its time-only walk", async () => {
    renderRoute("he", baseDraft, undefined, 1);
    expect(await screen.findByRole("heading", { level: 1, name: /יציאה 08:27, הגעה 10:11/ })).toBeInTheDocument();
    expect(withText(details(), ".compare-walk", "הליכה כ־2 דק׳")).toHaveLength(1);
  });

  it("starts navigation with the trips already fetched, then reads Resume for the active journey", async () => {
    const user = userEvent.setup();
    const { unmount, client } = renderRoute();
    await waitFor(() => expect(stopCounts()).toHaveLength(3));
    await user.click(screen.getByRole("button", { name: "יוצאים לדרך" }));
    expect(window.location.hash).toBe("#/navigate");
    const trip = getActiveTrip()!;
    expect(Object.keys(trip.trips)).toHaveLength(3);
    expect(trip.journey.legs).toHaveLength(6);
    unmount();
    renderRoute("he", baseDraft, client);
    expect(await screen.findByRole("button", { name: "חזרה לניווט" })).toBeInTheDocument();
  });

  it("shows the route without stop counts when trip details fail, and starting still works", async () => {
    useScenario("compare-trip-failed");
    const user = userEvent.setup();
    renderRoute();
    await waitFor(() => expect(within(details()).getAllByText("מספר התחנות לא זמין")).toHaveLength(3));
    expect(stopCounts()).toHaveLength(0);
    await user.click(screen.getByRole("button", { name: "יוצאים לדרך" }));
    expect(window.location.hash).toBe("#/navigate");
    expect(getActiveTrip()?.trips).toEqual({});
  });

  it("saves the destination as a favourite with the star, and removes it again", async () => {
    const user = userEvent.setup();
    renderRoute();
    const star = await screen.findByRole("button", { name: "שמירת היעד" });
    expect(star).toHaveAttribute("aria-pressed", "false");
    await user.click(star);
    expect(star).toHaveAttribute("aria-pressed", "true");
    expect(storedFavourites()).toEqual([expect.objectContaining({ label: "טכניון", latitude: 32.7767, longitude: 35.0231 })]);
    await user.click(star);
    expect(star).toHaveAttribute("aria-pressed", "false");
    expect(storedFavourites()).toEqual([]);
  });
});

describe("Compare (English)", () => {
  it("reads each option and the route details in English", async () => {
    const { unmount } = renderCompare("en");
    await waitFor(() => expect(options()).toHaveLength(3));
    expect(options()[0]).toHaveAccessibleName("Option 1, 105 minutes, departs 08:07, arrives 09:52, 2 transfers, lines: 8, Train, 1, in 4 min");
    expect(screen.getByRole("button", { name: /^From: ?from דיזנגוף סנטר$/ })).toBeInTheDocument();
    expect(screen.getAllByText(/Scheduled/)).toHaveLength(1);
    expect(screen.getByRole("button", { name: "Route details" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Change time: Depart 08:00" })).toBeInTheDocument();
    expect(journeyPosts()[0]!.body).toMatchObject({ lang: "en" });
    unmount();
    renderRoute("en");
    await waitFor(() => expect(legButtons()).toHaveLength(6));
    // The recorded answer's names are Hebrew; the words around them are English.
    expect(within(details()).getByText("רכבת ישראל")).toBeInTheDocument();
    expect(within(details()).getByText("Train 156")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Whole route" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Let's go" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Save the destination" })).toBeInTheDocument();
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
