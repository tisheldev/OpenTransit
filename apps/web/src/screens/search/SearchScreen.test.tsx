import { act, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { delay, http, HttpResponse } from "msw";
import { afterEach, describe, expect, it, vi } from "vitest";
import { fixture } from "../../api/fixtures";
import { en } from "../../i18n/en";
import { he } from "../../i18n/he";
import { getMapState, setMapCenter } from "../../map/scene";
import { derivedCategoryUnavailable, derivedPartialPlaces, respond } from "../../mocks/handlers";
import { server } from "../../mocks/node";
import { go } from "../../router";
import { lastOrigin } from "../../shell/localStore";
import { loadLocalState } from "../../storage/local";
import { renderApp, storedDraft, wholeText } from "../../shell/testUtils";
import { readableLocality } from "./choice";
import { setLocationSource } from "../../lib/geolocation";

let restoreLocation: (() => void) | null = null;
afterEach(() => {
  restoreLocation?.();
  restoreLocation = null;
});

/** Location already allowed (Search sends `near` only then), at Dizengoff Center. */
async function grantedLocation(): Promise<void> {
  const before = Object.getOwnPropertyDescriptor(navigator, "permissions");
  Object.defineProperty(navigator, "permissions", {
    configurable: true,
    value: { query: async () => ({ state: "granted" }) },
  });
  const restoreSource = setLocationSource({
    current: async () => ({ ok: true, fix: { latitude: 32.0753, longitude: 34.7749, accuracyMeters: 20, at: 0 } }),
    watch: () => () => {},
  });
  restoreLocation = () => {
    restoreSource();
    if (before) Object.defineProperty(navigator, "permissions", before);
    else delete (navigator as unknown as Record<string, unknown>).permissions;
  };
}

const input = () => screen.getByRole("searchbox", { name: /חיפוש|Search/ });

/** Count /v1/places requests and keep their URLs. */
function trackPlaces(answer: () => Response | Promise<Response> = () => respond(fixture("recorded-places-stop-he"))) {
  const urls: URL[] = [];
  server.use(
    http.get("*/v1/places", async ({ request }) => {
      urls.push(new URL(request.url));
      return answer();
    }),
  );
  return urls;
}

afterEach(() => vi.restoreAllMocks());

/** The rows' main buttons, in order (a stop row's second button opens its departures). */
const choices = (results: HTMLElement) => within(results).getAllByRole("button").filter((button) => !button.classList.contains("sx-clock"));

/** The first row whose name is exactly `name` (a stop's or another place's when `kind` says). */
function named(results: HTMLElement, name: string, kind?: "poi" | "stop"): HTMLElement {
  const found = choices(results).find((button) => {
    if (button.querySelector(".sx-nm")?.textContent !== name) return false;
    if (kind === "poi") return button.querySelector(".cv-lead") !== null;
    if (kind === "stop") return button.querySelector(".cv-sign") !== null;
    return true;
  });
  if (!found) throw new Error(`no result named ${name}`);
  return found;
}

describe("Search before typing", () => {
  it("focuses the field and lists Choose on map first, then My location (From only)", () => {
    renderApp("#/search/from");
    expect(input()).toHaveFocus();
    const rows = screen.getAllByRole("button").filter((button) => button.classList.contains("ot-row"));
    expect(rows[0]).toHaveTextContent(he["search.pickOnMap"]);
    expect(rows[1]).toHaveTextContent(he["place.myLocation"]);
  });

  it("shows My location without offering it when location cannot work, with the reason", async () => {
    renderApp("#/search/from", { location: "insecure" });
    expect(screen.queryByRole("button", { name: he["place.myLocation"] })).toBeNull();
    expect(screen.getByText(he["place.myLocation"]).closest("li")).toHaveAttribute("aria-disabled", "true");
    expect(screen.getByText(he["search.myLocation.insecure"])).toBeInTheDocument();
  });

  it("says permission is off when it was denied", async () => {
    renderApp("#/search/from", { location: "denied", lang: "en" });
    expect(await screen.findByText(en["search.myLocation.denied"])).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: en["place.myLocation"] })).toBeNull();
  });

  it("does not offer My location for To", () => {
    renderApp("#/search/to", { lang: "en" });
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(en["search.title.to"]);
    expect(screen.getByRole("button", { name: en["search.pickOnMap"] })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: en["place.myLocation"] })).toBeNull();
  });
});

describe("Search requests", () => {
  it("waits for 2 characters and debounces typing into one request with lang and limit 10", async () => {
    const urls = trackPlaces();
    renderApp("#/search/to");
    await userEvent.type(input(), "ד");
    await new Promise((resolve) => setTimeout(resolve, 350));
    expect(urls).toHaveLength(0);
    expect(screen.getByText(he["search.minChars"])).toBeInTheDocument();
    await userEvent.type(input(), "יזנגוף");
    await screen.findByTestId("search-results");
    expect(urls).toHaveLength(1);
    expect(urls[0]!.searchParams.get("q")).toBe("דיזנגוף");
    expect(urls[0]!.searchParams.get("lang")).toBe("he");
    expect(urls[0]!.searchParams.get("limit")).toBe("10");
    expect(urls[0]!.searchParams.has("near")).toBe(false);
  });

  it("aborts the previous request when the text changes", async () => {
    const signals: AbortSignal[] = [];
    const realFetch = globalThis.fetch;
    vi.spyOn(globalThis, "fetch").mockImplementation((resource, init) => {
      if (String(resource).includes("/v1/places") && init?.signal) signals.push(init.signal);
      return realFetch(resource, init);
    });
    // The first answer is held until the next request has started, so it is still in
    // flight when the text changes (a fixed delay raced the debounce on a loaded machine).
    let release: () => void = () => {};
    const held = new Promise<void>((resolve) => (release = resolve));
    let calls = 0;
    trackPlaces(async () => {
      calls += 1;
      if (calls === 1) await held;
      return respond(fixture("recorded-places-stop-he"));
    });
    renderApp("#/search/to");
    await userEvent.type(input(), "די");
    await waitFor(() => expect(signals).toHaveLength(1));
    await userEvent.type(input(), "ז");
    await waitFor(() => expect(signals).toHaveLength(2));
    expect(signals[0]!.aborted).toBe(true);
    expect(signals[1]!.aborted).toBe(false);
    release();
    await screen.findByTestId("search-results");
  });

  it("keeps the previous results (dimmed, busy) while the next answer loads: no skeleton flash", async () => {
    let calls = 0;
    trackPlaces(async () => {
      calls += 1;
      if (calls > 1) await delay(300);
      return respond(fixture("recorded-places-stop-he"));
    });
    renderApp("#/search/to");
    await userEvent.type(input(), "דיזנגוף");
    await screen.findByTestId("search-results");
    await userEvent.type(input(), " ס");
    const previous = screen.getByTestId("search-results-previous");
    expect(previous).toHaveAttribute("aria-busy", "true");
    expect(within(previous).getAllByRole("button").length).toBeGreaterThan(0);
    expect(screen.queryByTestId("search-skeleton")).toBeNull();
    await screen.findByTestId("search-results");
    expect(screen.queryByTestId("search-results-previous")).toBeNull();
  });

  it("keeps the places list under one typed character, with a hint", async () => {
    renderApp("#/search/to");
    await userEvent.type(input(), "ד");
    expect(screen.getByText(he["search.minChars"])).toBeInTheDocument();
    expect(screen.getByRole("button", { name: he["search.pickOnMap"] })).toBeInTheDocument();
  });

  it("shows skeleton rows while typing, then announces the result count", async () => {
    trackPlaces(async () => {
      await delay(100);
      return respond(fixture("recorded-places-stop-he"));
    });
    renderApp("#/search/to");
    await userEvent.type(input(), "דיזנגוף");
    expect(screen.getByTestId("search-skeleton").querySelectorAll("li")).toHaveLength(4);
    await screen.findByTestId("search-results");
    expect(screen.queryByTestId("search-skeleton")).toBeNull();
    expect(screen.getByText("5 תוצאות")).toBeInTheDocument();
  });
});

describe("Search results and states", () => {
  it("labels kinds, cleans stop localities and keeps foreign-language names tagged", async () => {
    trackPlaces(() => respond(fixture("recorded-places-poi-en")));
    renderApp("#/search/to");
    await userEvent.type(input(), "Dizengoff");
    const results = await screen.findByTestId("search-results");
    const first = named(results, "Meir Dizengoff");
    expect(first).toHaveTextContent("Meir Dizengoff");
    expect(first).toHaveTextContent(he["place.poi"]);
    expect(first.querySelector("bdi[lang='en']")).not.toBeNull();
    expect(readableLocality("רחוב: דיזנגוף 50 עיר: תל אביב יפו רציף:  קומה: ")).toBe("דיזנגוף 50, תל אביב יפו");
  });

  it("reads a stop as 'Stop <code> · street, city', without a separate kind word", async () => {
    renderApp("#/search/to");
    await userEvent.type(input(), "דיזנגוף");
    const results = await screen.findByTestId("search-results");
    const sub = choices(results)[0]!.querySelector(".sx-sub")!;
    expect(sub.textContent).toMatch(/^תחנה \d+\s*·\s/);
    expect(sub.querySelector(".kind-label")).toBeNull();
  });

  it("has one clear button, inside the field", async () => {
    renderApp("#/search/to", { lang: "en" });
    await userEvent.type(input(), "Di");
    const clear = screen.getByRole("button", { name: en["search.clear"] });
    expect(clear.closest(".sx-field")).not.toBeNull();
    await userEvent.click(clear);
    expect(input()).toHaveValue("");
    expect(input()).toHaveFocus();
  });

  it("tags a street-level address", async () => {
    renderApp("#/search/to", { lang: "en" });
    await userEvent.type(input(), "street dizengoff");
    const results = await screen.findByTestId("search-results");
    expect(within(results).getByText(en["place.streetLevel"])).toBeInTheDocument();
    expect(within(results).getByText(en["place.address"])).toBeInTheDocument();
  });

  it("shows zero matches as a calm empty success", async () => {
    renderApp("#/search/to");
    await userEvent.type(input(), "zzzz");
    expect(await screen.findByText(wholeText(he["state.empty.noMatches"]))).toBeInTheDocument();
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("shows a partial answer with an inline row per unavailable type", async () => {
    trackPlaces(() => respond(derivedPartialPlaces()));
    renderApp("#/search/to", { lang: "en" });
    await userEvent.type(input(), "Dizengoff");
    const results = await screen.findByTestId("search-results");
    expect(within(results).getByRole("note")).toHaveTextContent("Address: unavailable right now");
    expect(within(results).getAllByRole("button").length).toBeGreaterThan(0);
  });

  it("shows all categories unavailable as an error with retry", async () => {
    let calls = 0;
    trackPlaces(() => {
      calls += 1;
      return calls === 1 ? respond(derivedCategoryUnavailable()) : respond(fixture("recorded-places-stop-he"));
    });
    renderApp("#/search/to");
    await userEvent.type(input(), "דיזנגוף");
    expect(await screen.findByRole("alert")).toHaveTextContent(he["error.category_unavailable"]);
    await userEvent.click(screen.getByRole("button", { name: he["state.retry"] }));
    await screen.findByTestId("search-results");
    expect(calls).toBe(2);
  });

  it("honours Retry-After when rate limited", async () => {
    trackPlaces(() => respond(fixture("synthetic-problem-rate-limited"), { "Retry-After": "30" }));
    renderApp("#/search/to", { lang: "en" });
    await userEvent.type(input(), "Dizengoff");
    expect(await screen.findByRole("alert")).toHaveTextContent(en["error.rate_limited"]);
    expect(screen.getByRole("button", { name: /try again in 30/ })).toBeDisabled();
  });

  it("says it cannot reach OpenTransit when offline", async () => {
    trackPlaces(() => HttpResponse.error());
    renderApp("#/search/to");
    await userEvent.type(input(), "דיזנגוף");
    expect(await screen.findByRole("alert")).toHaveTextContent(he["error.network"]);
  });
});

describe("Lines, stops and places in one list (board 2, 14 November 2026)", () => {
  /** Count /v1/lines requests and keep their URLs (answered by the default handler). */
  function trackLines() {
    const urls: URL[] = [];
    server.events.on("request:start", ({ request }) => {
      const url = new URL(request.url);
      if (url.pathname === "/v1/lines") urls.push(url);
    });
    return urls;
  }
  afterEach(() => server.events.removeAllListeners());

  it("one digit searches lines only: exact number first, operators sharing it apart, four shown, then 'N more lines'", async () => {
    const places = trackPlaces();
    const lines = trackLines();
    renderApp("#/search/to");
    await userEvent.type(input(), "8");
    const results = await screen.findByTestId("search-results");
    expect(places).toHaveLength(0);
    expect(lines.map((url) => [url.searchParams.get("q"), url.searchParams.get("limit"), url.searchParams.has("lat")])).toEqual([["8", "50", false]]);
    const rows = choices(results);
    expect(rows.slice(0, 2).map((row) => row.textContent)).toEqual(["8מסוף רידינג ↔ מסוף הטייסיםדן · תל אביב-יפו", "8מרכזית המפרץ ↔ בת גליםאגד · חיפה"]);
    expect(rows.slice(2, 4).every((row) => /^8\d/.test(row.textContent ?? ""))).toBe(true);
    expect(rows[4]).toHaveTextContent(he["search.lines.more"].replace("{count}", "6"));
    expect(screen.queryByText(he["search.minChars"])).toBeNull();
    await userEvent.click(rows[4]!);
    expect(choices(results)).toHaveLength(10);
    expect(screen.queryByText(he["search.lines.more"].replace("{count}", "6"))).toBeNull();
  });

  it("a line row opens the line; with location already allowed it says how far its nearest stop is", async () => {
    // renderApp stubs location as "not asked yet"; allow it before Search mounts.
    renderApp("#/");
    await grantedLocation();
    act(() => go({ name: "search", field: "to" }));
    await userEvent.type(await screen.findByRole("searchbox"), "8");
    const first = () => choices(screen.getByTestId("search-results"))[0]!;
    await waitFor(() => expect(first()).toHaveTextContent(/^8מסוף רידינג ↔ מסוף הטייסיםדן · תל אביב-יפו · עוצר 1 דק׳ הליכה ממך$/));
    await userEvent.click(first());
    expect(window.location.hash).toBe("#/line/5%3A10008");
  });

  it("two characters or more of a number: lines and places, lines first", async () => {
    const places = trackPlaces();
    const lines = trackLines();
    renderApp("#/search/to");
    await userEvent.type(input(), "82");
    const results = await screen.findByTestId("search-results");
    expect(places.map((url) => url.searchParams.get("q"))).toEqual(["82"]);
    expect(lines.map((url) => url.searchParams.get("q"))).toEqual(["82"]);
    const rows = choices(results);
    expect(rows[0]).toHaveTextContent(/^82מסוף כרמלית ↔ חולון/);
    expect(rows.length).toBeGreaterThan(1);
  });

  it("setting Home offers no lines (a line is not a place): one digit still asks for more", async () => {
    const lines = trackLines();
    renderApp("#/search/home");
    await userEvent.type(input(), "8");
    expect(screen.getByText(he["search.minChars"])).toBeInTheDocument();
    await new Promise((resolve) => setTimeout(resolve, 350));
    expect(lines).toHaveLength(0);
  });

  it("says so when only lines were asked and they failed", async () => {
    server.use(http.get("*/v1/lines", () => respond(fixture("recorded-problem-not-ready"))));
    renderApp("#/search/to");
    await userEvent.type(input(), "8");
    expect(await screen.findByRole("alert")).toBeInTheDocument();
  });

  it("a stop row: the stop sign, its code and street; no departures unless Home already holds them", async () => {
    renderApp("#/search/to");
    await userEvent.type(input(), "דיזנגוף");
    const results = await screen.findByTestId("search-results");
    const stop = named(results, "דיזנגוף סנטר/דיזנגוף", "stop");
    expect(stop.querySelector(".sx-sub")).toHaveTextContent(/^תחנה 25609 · \S/);
    expect(stop.querySelector(".sx-cs")).toBeNull();
    const place = named(results, "דיזנגוף סנטר", "poi");
    expect(place.querySelector(".sx-sub")).toHaveTextContent(/^מקום · תל־אביב–יפו$/);
  });

  it("after Home: a stop row shows its next lines from Home's answer (no request of its own), and its clock opens the stop", async () => {
    const departures: string[] = [];
    server.events.on("request:start", ({ request }) => {
      if (/\/v1\/stops\/[^/]+\/departures/.test(new URL(request.url).pathname)) departures.push(request.url);
    });
    renderApp("#/");
    await screen.findByRole("list", { name: he["home.near.list"] });
    await userEvent.click(screen.getByRole("button", { name: `${he["home.search"]} ${he["home.search.hint"]}` }));
    await userEvent.type(await screen.findByRole("searchbox"), "דיזנגוף");
    const results = await screen.findByTestId("search-results");
    const stop = named(results, "דיזנגוף סנטר/דיזנגוף", "stop");
    expect(stop.querySelector(".sx-cs")).toHaveTextContent(/^1722115\d+ דק׳$/);
    expect(departures).toEqual([]);
    await userEvent.click(within(results).getAllByRole("button", { name: he["search.stop.departures"].replace("{stop}", "דיזנגוף סנטר/דיזנגוף") })[0]!);
    await waitFor(() => expect(window.location.hash).toBe("#/stop/mot%3Astop%3A13583"));
  });
});

describe("Choosing a place", () => {
  it("a stop fills To with its stopId, becomes a recent and opens Compare", async () => {
    renderApp("#/search/to");
    await userEvent.type(input(), "דיזנגוף");
    const results = await screen.findByTestId("search-results");
    await userEvent.click(choices(results)[0]!);
    expect(window.location.hash).toBe("#/compare");
    await waitFor(() =>
      expect(storedDraft()?.to).toMatchObject({
        type: "place",
        place: { kind: "stop", stopId: "mot:stop:13583", placeRef: null, label: "דיזנגוף סנטר/דיזנגוף" },
      }),
    );
    expect(loadLocalState().state.recents[0]).toMatchObject({ stopId: "mot:stop:13583" });
    expect(window.location.href).not.toContain("13583");
  });

  it("an address keeps its placeRef bound to the answer's generation and its coordinates", async () => {
    trackPlaces(() => respond(fixture("recorded-places-address-he")));
    renderApp("#/search/to");
    await userEvent.type(input(), "דיזנגוף 50");
    const results = await screen.findByTestId("search-results");
    await userEvent.click(choices(results)[0]!);
    const body = fixture("recorded-places-address-he").body as {
      data: Array<{ locationRef: { placeRef: string }; coordinates: { latitude: number } }>;
      meta: { generationId: string };
    };
    await waitFor(() =>
      expect(storedDraft()?.to).toMatchObject({
        place: {
          kind: "address",
          stopId: null,
          placeRef: body.data[0]!.locationRef.placeRef,
          refGenerationId: body.meta.generationId,
          latitude: body.data[0]!.coordinates.latitude,
        },
      }),
    );
  });

  it("From with no To yet goes back Home; My location is never a recent", async () => {
    renderApp("#/search/from");
    await userEvent.click(screen.getByRole("button", { name: he["place.myLocation"] }));
    await waitFor(() => expect(window.location.hash).toBe("#/"));
    expect(loadLocalState().state.recents).toHaveLength(0);
    expect(storedDraft()?.from).toEqual({ type: "myLocation" });
  });

  it("without a start, a destination asks for the start next; the start is remembered for next time", async () => {
    renderApp("#/search/to", { location: "unsupported" });
    await userEvent.type(input(), "דיזנגוף");
    await userEvent.click(choices(await screen.findByTestId("search-results"))[0]!);
    await waitFor(() => expect(window.location.hash).toBe("#/search/from"));
    expect(await screen.findByRole("heading", { level: 1 })).toHaveTextContent(he["search.title.from"]);
    await userEvent.type(input(), "דיזנגוף");
    await userEvent.click(named(await screen.findByTestId("search-results"), "דיזנגוף סנטר", "poi"));
    await waitFor(() => expect(window.location.hash).toBe("#/compare"));
    await waitFor(() => expect(storedDraft()?.from).toMatchObject({ type: "place", place: { label: "דיזנגוף סנטר" } }));
    expect(lastOrigin()).toMatchObject({ label: expect.stringContaining("דיזנגוף סנטר") });
  });

  it("Choose on map starts at the plan's place, at street level", async () => {
    renderApp("#/search/to");
    await userEvent.type(input(), "דיזנגוף");
    await userEvent.click(choices(await screen.findByTestId("search-results"))[0]!);
    await waitFor(() => expect(window.location.hash).toBe("#/compare"));
    act(() => go({ name: "search", field: "to" }));
    await userEvent.click(await screen.findByRole("button", { name: he["search.pickOnMap"] }));
    const to = storedDraft()!.to as { place: { latitude: number; longitude: number } };
    expect(getMapState().scene).toMatchObject({ pick: true, camera: "fit", focus: { center: [to.place.longitude, to.place.latitude], zoom: 15 } });
  });

  it("save mode Home stores the place and returns", async () => {
    renderApp("#/search/home", { lang: "en" });
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(en["search.title.home"]);
    await userEvent.type(input(), "Dizengoff");
    const results = await screen.findByTestId("search-results");
    await userEvent.click(choices(results)[0]!);
    await waitFor(() => expect(window.location.hash).toBe("#/"));
    expect(loadLocalState().state.home).toMatchObject({ id: "home", stopId: "mot:stop:13583" });
    expect(storedDraft()?.to ?? null).toBeNull();
  });

  it("save mode favourite asks for a name, defaulting to the label", async () => {
    renderApp("#/search/favourite");
    await userEvent.type(input(), "דיזנגוף");
    const results = await screen.findByTestId("search-results");
    await userEvent.click(named(results, "דיזנגוף סנטר", "poi"));
    const name = screen.getByLabelText(he["search.favourite.name"]);
    expect(name).toHaveValue("דיזנגוף סנטר");
    await userEvent.clear(name);
    await userEvent.type(name, "קניון");
    await userEvent.click(screen.getByRole("button", { name: he["search.favourite.save"] }));
    await waitFor(() => expect(window.location.hash).toBe("#/"));
    expect(loadLocalState().state.favourites).toEqual([expect.objectContaining({ label: "קניון" })]);
  });

  it("Choose on map drops the sheet to peek and confirms the map centre as a pin", async () => {
    renderApp("#/search/to", { lang: "en" });
    await userEvent.click(screen.getByRole("button", { name: en["search.pickOnMap"] }));
    expect(document.querySelector(".sheet")).toHaveAttribute("data-snap", "peek");
    expect(getMapState().scene.pick).toBe(true);
    const confirm = screen.getByRole("button", { name: en["search.pick.confirm"] });
    expect(confirm).toBeDisabled();
    act(() => setMapCenter([34.7818, 32.0853]));
    await userEvent.click(confirm);
    expect(window.location.hash).toBe("#/compare");
    await waitFor(() =>
      expect(storedDraft()?.to).toMatchObject({
        place: { kind: "pin", label: en["place.pin"], latitude: 32.0853, longitude: 34.7818, stopId: null, placeRef: null },
      }),
    );
    expect(getMapState().scene.pick).toBe(false);
  });

  it("refuses a pin outside the service area", async () => {
    renderApp("#/search/to");
    await userEvent.click(screen.getByRole("button", { name: he["search.pickOnMap"] }));
    act(() => setMapCenter([2.35, 48.85]));
    await userEvent.click(screen.getByRole("button", { name: he["search.pick.confirm"] }));
    expect(screen.getByRole("alert")).toHaveTextContent(he["search.pick.outside"]);
    expect(window.location.hash).toBe("#/search/to");
  });
});
