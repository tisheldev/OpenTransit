import type { UseQueryResult } from "@tanstack/react-query";
import { ApiFailure } from "../api/result";
import type { Meta, Status } from "../api/schemas";
import { StaleDataBanner, TestDataBanner } from "../components/states";
import { useI18n } from "../i18n/I18nProvider";
import { useOnline } from "./online";

// The shell's banner area (design: Home states, Cross-cutting rules): test data, stale
// or expired timetable, not ready, offline. At most one data banner plus the test label.

/** The status meta when a generation is loaded (without one, meta carries only an id). */
export function generationMeta(status: Status | undefined): Meta | null {
  if (!status || status.meta.generationId === null) return null;
  return status.meta as Meta;
}

export function Banners({ fixtureMode, status }: { fixtureMode: boolean; status: UseQueryResult<Status> }) {
  const { t } = useI18n();
  const online = useOnline();
  const meta = generationMeta(status.data);
  const failure = status.error instanceof ApiFailure ? status.error : null;
  const offline = !online || failure?.state === "network";
  const testData = fixtureMode || meta?.mode === "fixture";
  const expired = meta?.freshness === "expired" || status.data?.data.staticData === "expired";
  const stale = !expired && meta !== null && meta.freshness !== "current";
  const notReady =
    !offline &&
    !expired &&
    ((status.data !== undefined && !status.data.data.ready) || failure !== null);

  if (!testData && !offline && !expired && !stale && !notReady) return null;
  return (
    <div className="banners">
      {testData && <TestDataBanner />}
      {offline && (
        <div className="banner banner-stale" role="status">
          {t("shell.offline")}
        </div>
      )}
      {!offline && expired && (
        <div className="banner banner-stale" role="note">
          {t("shell.expired")}
        </div>
      )}
      {!offline && stale && <StaleDataBanner />}
      {notReady && (
        <div className="banner banner-stale" role="note">
          {t("status.notReady")}
        </div>
      )}
    </div>
  );
}
