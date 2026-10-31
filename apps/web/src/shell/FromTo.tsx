import { useId } from "react";
import { useI18n } from "../i18n/I18nProvider";
import type { Endpoint } from "../plan/draft";
import { usePlan } from "../plan/PlanProvider";
import { go } from "../router";

// The From/To card (design: Home, wireframe "⇅ My location / Where to?"). Compare reuses
// the compact variant. Tapping a field opens Search for it; ⇅ swaps the two ends.

export function endpointLabel(endpoint: Endpoint, myLocation: string): string {
  return endpoint.type === "myLocation" ? myLocation : endpoint.place.label;
}

export function FromTo({ variant = "full" }: { variant?: "full" | "compact" }) {
  const { t } = useI18n();
  const { draft, swap } = usePlan();
  const labelId = useId();
  const from = draft.from === null ? null : endpointLabel(draft.from, t("place.myLocation"));
  const to = draft.to === null ? null : endpointLabel(draft.to, t("place.myLocation"));

  return (
    <div className={`from-to from-to-${variant}`} role="group" aria-labelledby={labelId}>
      <span id={labelId} className="visually-hidden">
        {t("fromTo.label")}
      </span>
      <div className="from-to-fields">
        <button
          type="button"
          className="from-to-field"
          onClick={() => go({ name: "search", field: "from" })}
        >
          <span className="from-to-dot from-to-dot-origin" aria-hidden="true" />
          <span className="from-to-text">
            {from === null ? (
              <span className="from-to-placeholder">{t("fromTo.from")}</span>
            ) : (
              <>
                <span className={variant === "full" ? "from-to-caption" : "visually-hidden"}>{t("fromTo.from")} </span>
                <bdi className="from-to-value">{from}</bdi>
              </>
            )}
          </span>
        </button>
        <button
          type="button"
          className="from-to-field"
          onClick={() => go({ name: "search", field: "to" })}
        >
          <span className="from-to-dot from-to-dot-destination" aria-hidden="true" />
          <span className="from-to-text">
            {to !== null && (
              <span className={variant === "full" ? "from-to-caption" : "visually-hidden"}>{t("fromTo.to")} </span>
            )}
            {to === null ? (
              <span className="from-to-placeholder">{t("fromTo.to")}</span>
            ) : (
              <bdi className="from-to-value">{to}</bdi>
            )}
          </span>
        </button>
      </div>
      <button
        type="button"
        className="icon-button from-to-swap"
        aria-label={t("fromTo.swap")}
        disabled={draft.to === null}
        onClick={swap}
      >
        <span aria-hidden="true">⇅</span>
      </button>
    </div>
  );
}
