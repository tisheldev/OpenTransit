import { useId, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useStatus } from "../api/queries";
import { ApiFailure } from "../api/result";
import type { Meta } from "../api/schemas";
import { Bdi, ErrorState, Loading, StaleDataBanner, TestDataBanner } from "../components/states";
import { useI18n } from "../i18n/I18nProvider";
import { LANGS, type MessageKey } from "../i18n/messages";
import { formatDate } from "../lib/time";
import { hrefFor, type Route } from "../router";
import { clearAllLocalData } from "../storage/local";

// S0 placeholder screens. Home shows the data status from /v1/status so the API wiring
// is visible; Settings holds the language (direction) switch and clear-all. The map,
// sheet and real screens arrive in S3–S7.

const titles: Record<Route["name"], MessageKey> = {
  home: "screen.home",
  search: "screen.search",
  compare: "screen.compare",
  route: "screen.route",
  navigate: "screen.navigate",
  stop: "screen.stop",
  trip: "screen.trip",
  nearby: "screen.nearby",
  lines: "screen.lines",
  settings: "screen.settings",
  notFound: "screen.notFound",
};

function DataStatus({ fixtureMode }: { fixtureMode: boolean }) {
  const { t, lang } = useI18n();
  const status = useStatus();
  if (status.isPending) return <Loading label={t("status.checking")} />;
  if (status.isError) {
    const failure = status.error instanceof ApiFailure ? status.error : null;
    return (
      <ErrorState
        state={failure?.state ?? "unexpected"}
        retryAfterSeconds={failure?.error.kind === "problem" ? failure.error.retryAfterSeconds : null}
        onRetry={() => void status.refetch()}
      />
    );
  }
  const { data, meta } = status.data;
  // Without a generation, meta carries only a request ID and a null generationId.
  const generation = meta.generationId === null ? null : (meta as Meta);
  const coverage = generation?.coverage ?? null;
  const stale = generation !== null && generation.freshness !== "current";
  const testData = fixtureMode || generation?.mode === "fixture";
  return (
    <section className="data-status" aria-label={t("status.ready")}>
      {testData && <TestDataBanner />}
      {stale && <StaleDataBanner />}
      <p>{data.ready ? t("status.ready") : t("status.notReady")}</p>
      {coverage && (
        <p>
          {t("time.scheduled")} ·{" "}
          <Bdi>
            {t("status.coverage", { from: formatDate(coverage.from, lang), until: formatDate(coverage.until, lang) })}
          </Bdi>
        </p>
      )}
      <p>{t("banner.liveUnavailable")}</p>
    </section>
  );
}

function Settings() {
  const { t, lang, setLang } = useI18n();
  const queryClient = useQueryClient();
  const [cleared, setCleared] = useState(false);
  const groupId = useId();
  return (
    <>
      <fieldset className="segmented" aria-labelledby={groupId}>
        <legend id={groupId}>{t("settings.language")}</legend>
        {LANGS.map((option) => (
          <label key={option} lang={option}>
            <input type="radio" name="lang" value={option} checked={lang === option} onChange={() => setLang(option)} />
            {t(`settings.language.${option}`)}
          </label>
        ))}
      </fieldset>
      <p>
        <button
          type="button"
          className="button"
          onClick={() => {
            if (!window.confirm(t("settings.clearData.confirm"))) return;
            clearAllLocalData();
            queryClient.clear();
            setLang("he");
            setCleared(true);
          }}
        >
          {t("settings.clearData")}
        </button>
      </p>
      <p role="status" aria-live="polite">
        {cleared ? t("settings.clearData.done") : ""}
      </p>
    </>
  );
}

export function Screen({ route, fixtureMode }: { route: Route; fixtureMode: boolean }) {
  const { t } = useI18n();
  return (
    <main id="main" className="screen" tabIndex={-1}>
      <h1>{t(titles[route.name])}</h1>
      {route.name === "home" && (
        <>
          <DataStatus fixtureMode={fixtureMode} />
          <ul className="link-list">
            {(["search", "compare", "route", "navigate", "nearby", "lines", "settings"] as const).map((name) => (
              <li key={name}>
                <a href={hrefFor({ name })}>{t(titles[name])}</a>
              </li>
            ))}
          </ul>
        </>
      )}
      {route.name === "settings" && <Settings />}
      {route.name === "stop" && <Bdi>{route.stopId}</Bdi>}
      {route.name === "trip" && <Bdi>{route.tripRef}</Bdi>}
      {route.name !== "home" && route.name !== "settings" && (
        <>
          <p className="placeholder-note">{t("screen.placeholder")}</p>
          <a className="button" href={hrefFor({ name: "home" })}>
            {t("screen.backHome")}
          </a>
        </>
      )}
      {route.name === "settings" && (
        <a className="button" href={hrefFor({ name: "home" })}>
          {t("screen.backHome")}
        </a>
      )}
    </main>
  );
}
