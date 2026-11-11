import type { ReactNode } from "react";
import { useI18n } from "../../i18n/I18nProvider";
import type { Endpoint } from "../../plan/draft";
import { go } from "../../router";
import { endpointLabel } from "./labels";
import { fill } from "./text";

// Choose's header (board Choose; also the wide panel's): the destination as the screen's
// heading, "מ<start>" in muted text under it (a button: it opens Search for the start),
// and the time tag at the inline end.

export function ChooseHeader({
  from,
  to,
  chip,
  note = null,
}: {
  from: Endpoint | null;
  to: Endpoint | null;
  chip: ReactNode;
  /** A quiet word after the start ("מתוכנן": every time shown is scheduled). */
  note?: string | null;
}) {
  const { t } = useI18n();
  const destination = endpointLabel(to, t);
  const start = endpointLabel(from, t);
  return (
    <div className="choose-head">
      <div className="choose-head__ends">
        <h1 className="choose-head__to" tabIndex={-1}>
          {destination ? <bdi>{destination}</bdi> : t("compare.toPlaceholder")}
        </h1>
        <span className="choose-head__sub b-mu">
          <button type="button" className="choose-head__from" onClick={() => go({ name: "search", field: "from" })}>
            <span className="visually-hidden">{t("compare.fromLabel")}: </span>
            {start ? fill(t("compare.fromName"), { place: <bdi>{start}</bdi> }) : t("compare.fromPlaceholder")}
          </button>
          {note && <span className="choose-head__note"> · {note}</span>}
        </span>
      </div>
      {chip}
    </div>
  );
}
