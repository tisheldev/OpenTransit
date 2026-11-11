import { useEffect, useState, type ReactNode } from "react";
import { LineBadge } from "../../components/ds";
import { useI18n } from "../../i18n/I18nProvider";
import { formatDistance } from "../../lib/format";
import { formatClock } from "../../lib/time";
import { lineMode } from "../../map/layers";
import { minutesTo } from "./lines";

// Small pieces Home and the stop screen share (boards 1 and 7): a line's badge, "2 דק׳"
// with the figure set large, and a distance. Every figure is isolated in <bdi class="num">.

/** The current time, ticking so "in 4 min" stays true without a refetch. */
export function useNow(intervalMs = 20_000): Date {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const id = window.setInterval(() => setNow(new Date()), intervalMs);
    return () => window.clearInterval(id);
  }, [intervalMs]);
  return now;
}

/** A message with one {minutes} placeholder, the figure rendered in its place. */
export function withFigure(template: string, figure: ReactNode): ReactNode {
  const [before, after = ""] = template.split("{minutes}");
  return (
    <>
      {before}
      {figure}
      {after}
    </>
  );
}

const Big = ({ children }: { children: ReactNode }) => <bdi className="num b-big">{children}</bdi>;

/** When a departure leaves: "2 דק׳", "עכשיו" once due, its clock time beyond an hour. */
export function Due({ instant, now }: { instant: string; now: Date }) {
  const { t, lang } = useI18n();
  const minutes = minutesTo(instant, now);
  if (minutes <= 0) return <span className="b-mu b-due">{t("time.now")}</span>;
  if (minutes >= 60)
    return (
      <span className="b-mu b-due">
        <Big>{formatClock(instant, lang)}</Big>
      </span>
    );
  return <span className="b-mu b-due">{withFigure(t("stop.minutes"), <Big>{minutes}</Big>)}</span>;
}

/** "200 מ׳" with the number isolated. */
export function Distance({ meters }: { meters: number }) {
  const { lang } = useI18n();
  const text = formatDistance(meters, lang);
  if (!text) return null;
  const split = text.lastIndexOf(" ");
  return (
    <span className="b-mu">
      <bdi className="num">{text.slice(0, split)}</bdi>
      {text.slice(split)}
    </span>
  );
}

export interface BadgeLine {
  mode: string;
  label: string;
  operatorId?: string | null;
  operatorName?: string | null;
}

/** A line's badge in its operator's colour, with its vehicle. */
export function Badge({ line }: { line: BadgeLine }) {
  return (
    <LineBadge
      mode={lineMode(line.mode) === "rail" ? "rail" : "bus"}
      label={line.label}
      line={{ mode: line.mode, operatorId: line.operatorId, operatorName: line.operatorName }}
    />
  );
}
