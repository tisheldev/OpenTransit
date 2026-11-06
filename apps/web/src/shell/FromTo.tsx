import { useId } from "react";
import { Icon } from "../components/ds";
import { useI18n } from "../i18n/I18nProvider";
import type { Endpoint } from "../plan/draft";
import { usePlan } from "../plan/PlanProvider";
import { go } from "../router";

// The From/To card (design: TripFields). Tapping a field opens Search for it; the swap
// button reverses the two ends. Each field reads "Where from? <value>" to assistive
// technology; on screen the origin circle and destination square, joined by a dotted
// line, carry that, and an empty field shows its question.

export function endpointLabel(endpoint: Endpoint, myLocation: string): string {
  return endpoint.type === "myLocation" ? myLocation : endpoint.place.label;
}

function Field({ end, endpoint }: { end: "from" | "to"; endpoint: Endpoint | null }) {
  const { t } = useI18n();
  const question = t(end === "from" ? "fromTo.from" : "fromTo.to");
  return (
    <button
      type="button"
      className={`ot-trip__field from-to-field from-to-${end}${endpoint === null ? " ot-trip__field--empty" : ""}`}
      onClick={() => go({ name: "search", field: end })}
    >
      {endpoint === null ? (
        question
      ) : (
        <>
          <span className="visually-hidden">{question} </span>
          {endpoint.type === "myLocation" && <Icon name="locate" size="sm" className="from-to-icon" />}
          <span className="from-to-value">
            <bdi>{endpointLabel(endpoint, t("place.myLocation"))}</bdi>
          </span>
        </>
      )}
    </button>
  );
}

export function FromTo() {
  const { t } = useI18n();
  const { draft, swap } = usePlan();
  const labelId = useId();

  return (
    <div className="ot-trip from-to" role="group" aria-labelledby={labelId}>
      <span id={labelId} className="visually-hidden">
        {t("fromTo.label")}
      </span>
      <span className="ot-trip__dots" aria-hidden="true">
        <span className="ot-trip__dot" />
        <span className="ot-trip__link" />
        <span className="ot-trip__dot ot-trip__dot--to" />
      </span>
      <span className="ot-trip__fields">
        <Field end="from" endpoint={draft.from} />
        <Field end="to" endpoint={draft.to} />
      </span>
      <button type="button" className="ot-trip__swap" aria-label={t("fromTo.swap")} disabled={draft.to === null} onClick={swap}>
        <Icon name="swap" />
      </button>
    </div>
  );
}
