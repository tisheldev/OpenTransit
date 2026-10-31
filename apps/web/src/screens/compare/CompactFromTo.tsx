import { useI18n } from "../../i18n/I18nProvider";
import { usePlan } from "../../plan/PlanProvider";
import { hrefFor } from "../../router";
import { endpointLabel } from "./labels";

// STAND-IN for S4's `src/shell/FromTo.tsx` with variant="compact": the coordinator swaps
// this one component for it. Two labels linking to Search, and a swap button.

export function CompactFromTo() {
  const { t } = useI18n();
  const { draft, swap } = usePlan();
  const from = endpointLabel(draft.from, t);
  const to = endpointLabel(draft.to, t);
  return (
    <nav className="compare-fromto" aria-label={t("compare.fromTo")}>
      <div className="compare-fromto-ends">
        <a href={hrefFor({ name: "search", field: "from" })}>
          <span className="compare-fromto-key">
            {t("compare.from")}
          </span>
          <bdi>{from}</bdi>
        </a>
        <a href={hrefFor({ name: "search", field: "to" })}>
          <span className="compare-fromto-key">
            {t("compare.to")}
          </span>
          <bdi>{to || t("compare.chooseTo")}</bdi>
        </a>
      </div>
      <button type="button" className="compare-swap" onClick={swap} disabled={draft.to === null} aria-label={t("compare.swap")}>
        <span aria-hidden="true">⇅</span>
      </button>
    </nav>
  );
}
