import type { ReactNode } from "react";
import { useI18n } from "../../i18n/I18nProvider";
import type { Endpoint } from "../../plan/draft";
import { usePlan } from "../../plan/PlanProvider";
import { go } from "../../router";
import { endpointLabel } from "./labels";

// Compare's one-line header (C3): "from ← to" (each end opens Search for it), swap, and
// the time chip. It replaces the two-row From/To card so the options start higher.

function End({ field, endpoint }: { field: "from" | "to"; endpoint: Endpoint | null }) {
  const { t } = useI18n();
  const label = endpointLabel(endpoint, t);
  return (
    <button type="button" className={`ends-end ends-${field}`} onClick={() => go({ name: "search", field })}>
      <span className="visually-hidden">{t(field === "from" ? "compare.fromLabel" : "compare.toLabel")}: </span>
      {label ? (
        <bdi className="ends-name">{label}</bdi>
      ) : (
        <span className="ends-name ends-placeholder">{t(field === "from" ? "compare.fromPlaceholder" : "compare.toPlaceholder")}</span>
      )}
    </button>
  );
}

export function CompareHeader({ chip }: { chip: ReactNode }) {
  const { t } = useI18n();
  const { draft, swap } = usePlan();
  return (
    <div className="compare-header">
      <div className="ends" role="group" aria-label={t("compare.ends")}>
        <End field="from" endpoint={draft.from} />
        <span className="ends-arrow compare-flip" aria-hidden="true">
          ←
        </span>
        <End field="to" endpoint={draft.to} />
        <button
          type="button"
          className="ends-swap"
          aria-label={t("compare.swap")}
          disabled={draft.to === null || draft.from === null}
          onClick={swap}
        >
          <span aria-hidden="true">⇄</span>
        </button>
      </div>
      {chip}
    </div>
  );
}
