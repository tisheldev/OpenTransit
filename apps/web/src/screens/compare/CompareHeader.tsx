import type { ReactNode } from "react";
import { Icon } from "../../components/ds";
import { useI18n } from "../../i18n/I18nProvider";
import type { Endpoint } from "../../plan/draft";
import { usePlan } from "../../plan/PlanProvider";
import { go } from "../../router";
import { endpointLabel } from "./labels";

// Compare's one-line header (C3; design: the sheet head's title and sub, kept on one line
// so every option fits on the half sheet): "from › to" in one field, where the
// destination reads as the title and the start as its quieter sub; each end opens Search
// for it; swap; then the time chip.

function End({ field, endpoint }: { field: "from" | "to"; endpoint: Endpoint | null }) {
  const { t } = useI18n();
  const label = endpointLabel(endpoint, t);
  return (
    <button type="button" className={`compare-ends__end compare-ends__${field}`} onClick={() => go({ name: "search", field })}>
      <span className="visually-hidden">{t(field === "from" ? "compare.fromLabel" : "compare.toLabel")}: </span>
      {label ? (
        <bdi className="compare-ends__name">{label}</bdi>
      ) : (
        <span className="compare-ends__name compare-ends__placeholder">
          {t(field === "from" ? "compare.fromPlaceholder" : "compare.toPlaceholder")}
        </span>
      )}
    </button>
  );
}

export function CompareHeader({ chip }: { chip: ReactNode }) {
  const { t } = useI18n();
  const { draft, swap } = usePlan();
  return (
    <div className="compare-header">
      <div className="compare-ends" role="group" aria-label={t("compare.ends")}>
        <End field="from" endpoint={draft.from} />
        <Icon name="chevron" size="sm" className="compare-ends__arrow" />
        <End field="to" endpoint={draft.to} />
        <button
          type="button"
          className="compare-ends__swap"
          aria-label={t("compare.swap")}
          disabled={draft.to === null || draft.from === null}
          onClick={swap}
        >
          <Icon name="swap" />
        </button>
      </div>
      {chip}
    </div>
  );
}
