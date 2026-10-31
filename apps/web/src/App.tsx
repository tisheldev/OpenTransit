import { QueryClientProvider, type QueryClient } from "@tanstack/react-query";
import { I18nProvider } from "./i18n/I18nProvider";
import { PlanProvider } from "./plan/PlanProvider";
import { Shell } from "./shell/Shell";

export function App({ queryClient, fixtureMode = false }: { queryClient: QueryClient; fixtureMode?: boolean }) {
  return (
    <QueryClientProvider client={queryClient}>
      <I18nProvider>
        <PlanProvider>
          <Shell fixtureMode={fixtureMode} />
        </PlanProvider>
      </I18nProvider>
    </QueryClientProvider>
  );
}
