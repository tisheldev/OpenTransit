import { useStatus } from "../../api/queries";
import { ApiFailure } from "../../api/result";
import type { Meta } from "../../api/schemas";
import { Bdi, ErrorState, Loading, StaleDataBanner, TestDataBanner } from "../../components/states";
import { useI18n } from "../../i18n/I18nProvider";
import { formatDate } from "../../lib/time";
import { hrefFor } from "../../router";

// CONTRACT STUB, replaced by slice S4 (S0 behaviour kept so the existing e2e stays green).
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

export function HomeScreen() {
  const { t } = useI18n();
  return (
    <>
      <h1>{t("screen.home")}</h1>
      <DataStatus fixtureMode={import.meta.env.MODE === "fixtures"} />
      <ul className="link-list">
        <li><a href={hrefFor({ name: "search", field: "to" })}>{t("screen.search")}</a></li>
        <li><a href={hrefFor({ name: "nearby" })}>{t("screen.nearby")}</a></li>
        <li><a href={hrefFor({ name: "settings" })}>{t("screen.settings")}</a></li>
      </ul>
    </>
  );
}
