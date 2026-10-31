import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render } from "@testing-library/react";
import { I18nProvider } from "../i18n/I18nProvider";
import { resetLocationDenial } from "../lib/geolocation";
import type { Lang } from "../i18n/messages";
import { resetMapState } from "../map/scene";
import { resetActiveTripCache } from "../nav/activeTrip";
import type { PlanDraft } from "../plan/draft";
import { PlanProvider } from "../plan/PlanProvider";
import { readSession } from "../storage/session";
import { reloadLocalState } from "./localStore";
import { Shell } from "./Shell";

// Test-only: render the whole shell at a route, with a fresh query client and stores.

export function testQueryClient(): QueryClient {
  return new QueryClient({ defaultOptions: { queries: { retry: false, refetchOnWindowFocus: false } } });
}

/**
 * What the browser offers for "my location" (jsdom has no Geolocation API). `prompt`: a
 * secure context with the API and no decision yet, like a first visit over https.
 * The fake never returns a position: tests that need one replace the location source.
 */
export type BrowserLocation = "prompt" | "insecure" | "unsupported" | "denied";

export function stubBrowserLocation(mode: BrowserLocation): void {
  resetLocationDenial();
  const define = (target: object, key: string, value: unknown) =>
    Object.defineProperty(target, key, { configurable: true, writable: true, value });
  define(window, "isSecureContext", mode !== "insecure");
  const unavailable = { code: 2, PERMISSION_DENIED: 1, POSITION_UNAVAILABLE: 2, TIMEOUT: 3, message: "test" };
  define(
    navigator,
    "geolocation",
    mode === "unsupported"
      ? undefined
      : {
          getCurrentPosition: (_ok: unknown, fail: (error: unknown) => void) => fail(unavailable),
          watchPosition: (_ok: unknown, fail: (error: unknown) => void) => (fail(unavailable), 1),
          clearWatch: () => {},
        },
  );
  define(
    navigator,
    "permissions",
    mode === "denied"
      ? { query: async () => ({ state: "denied", addEventListener: () => {}, removeEventListener: () => {} }) }
      : undefined,
  );
}

export function renderApp(
  hash: string,
  options: { lang?: Lang; fixtureMode?: boolean; queryClient?: QueryClient; location?: BrowserLocation } = {},
) {
  window.history.replaceState({ otDepth: 0 }, "", `/${hash}`);
  stubBrowserLocation(options.location ?? "prompt");
  reloadLocalState();
  resetMapState();
  resetActiveTripCache();
  const queryClient = options.queryClient ?? testQueryClient();
  const view = render(
    <QueryClientProvider client={queryClient}>
      <I18nProvider initialLang={options.lang ?? "he"}>
        <PlanProvider>
          <Shell fixtureMode={options.fixtureMode ?? false} />
        </PlanProvider>
      </I18nProvider>
    </QueryClientProvider>,
  );
  // Sync the router's history depth with the entry just set (depth 0: Back goes Home).
  act(() => {
    window.dispatchEvent(new HashChangeEvent("hashchange"));
  });
  return { ...view, queryClient };
}

export function storedDraft(): PlanDraft | null {
  return readSession("plan", (value): value is PlanDraft => typeof value === "object" && value !== null);
}
