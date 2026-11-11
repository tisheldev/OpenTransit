import { Fragment, type ReactNode } from "react";
import { useI18n } from "../../i18n/I18nProvider";
import { compactDuration } from "./labels";

// Small text pieces shared by the option rows and the route timeline (boards Choose and
// Step): every digit or time in <bdi class="num">, the reading-way arrow and chevron.

/** A text with each run of digits (times, minutes, metres, platforms) in <bdi class="num">. */
export function Nums({ text }: { text: string }) {
  const parts = text.split(/(\d+(?:[:.,]\d+)*)/);
  return (
    <>
      {parts.map((part, index) =>
        index % 2 === 1 ? (
          <bdi key={index} className="num">
            {part}
          </bdi>
        ) : (
          <Fragment key={index}>{part}</Fragment>
        ),
      )}
    </>
  );
}

/** A translated message with React nodes in its {placeholders}; the rest with its digits isolated. */
export function fill(template: string, nodes: Record<string, ReactNode>): ReactNode[] {
  return template.split(/(\{\w+\})/).map((part, index) => {
    const name = /^\{(\w+)\}$/.exec(part)?.[1];
    return <Fragment key={index}>{name !== undefined && name in nodes ? nodes[name] : <Nums text={part} />}</Fragment>;
  });
}

/** "+1" after a time on the next day (its own left-to-right run, so the sign stays in front). */
export function NextDay({ days }: { days: number }) {
  return (
    <sup className="compare-plus">
      <bdi dir="ltr">{`+${days}`}</bdi>
    </sup>
  );
}

/** "1:45 שע׳" / "41 דק׳": the number in signage figures, then the unit (boards). */
export function Duration({ seconds }: { seconds: number }) {
  const { t } = useI18n();
  const { value, unit } = compactDuration(seconds);
  return (
    <>
      <bdi className="num">{value}</bdi> {t(unit === "h" ? "compare.unit.h" : "compare.unit.min")}
    </>
  );
}

/** The arrow between departure and arrival: points the reading way (left in Hebrew). */
export function TimeArrow() {
  return (
    <svg className="compare-flip" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false">
      <path d="M19 12H5M11 6l-6 6 6 6" />
    </svg>
  );
}

/** The small chevron between the legs of an option row. */
export function LegChevron() {
  return (
    <svg className="compare-flip" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false">
      <path d="M14.5 6l-6 6 6 6" />
    </svg>
  );
}
