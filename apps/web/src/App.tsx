import { QueryClientProvider, type QueryClient } from "@tanstack/react-query";
import { useEffect, useRef } from "react";
import { I18nProvider, useI18n } from "./i18n/I18nProvider";
import { useRoute } from "./router";
import { Screen } from "./screens/screens";

function Shell({ fixtureMode }: { fixtureMode: boolean }) {
  const { t } = useI18n();
  const route = useRoute();
  const first = useRef(true);

  // Move focus to the new screen's content on navigation (not on first load).
  useEffect(() => {
    if (first.current) {
      first.current = false;
      return;
    }
    document.getElementById("main")?.focus();
  }, [route.name]);

  return (
    <div className="app">
      <a className="skip-link" href="#main" onClick={(event) => {
        event.preventDefault();
        document.getElementById("main")?.focus();
      }}>
        {t("app.skipToContent")}
      </a>
      <header className="topbar">
        <a className="brand" href="#/">
          <span className="brand-mark" aria-hidden="true">
            OT
          </span>
          {t("app.name")}
        </a>
      </header>
      <Screen route={route} fixtureMode={fixtureMode} />
    </div>
  );
}

export function App({ queryClient, fixtureMode = false }: { queryClient: QueryClient; fixtureMode?: boolean }) {
  return (
    <QueryClientProvider client={queryClient}>
      <I18nProvider>
        <Shell fixtureMode={fixtureMode} />
      </I18nProvider>
    </QueryClientProvider>
  );
}
