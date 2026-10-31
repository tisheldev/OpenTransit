import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render } from "@testing-library/react";
import { I18nProvider } from "../i18n/I18nProvider";
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

export function renderApp(hash: string, options: { lang?: Lang; fixtureMode?: boolean; queryClient?: QueryClient } = {}) {
  window.history.replaceState({ otDepth: 0 }, "", `/${hash}`);
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
