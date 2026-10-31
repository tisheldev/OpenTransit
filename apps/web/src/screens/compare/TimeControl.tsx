import { useEffect, useId, useMemo, useRef, useState, type Ref } from "react";
import { useI18n } from "../../i18n/I18nProvider";
import { formatDuration } from "../../lib/format";
import { departureInstant, israelWallTime } from "../../lib/time";
import type { When } from "../../plan/draft";
import { daysBetween, formatShortDay, israelDate, relativeDay } from "./labels";

// Time control (design: Compare; CU03, CU12). One chip in the header says what is asked
// ("עכשיו" / "יציאה 08:00" / "הגעה עד 10:00 · מחר"); tapping it opens an inline panel:
// Now / Depart / Arrive by, a day (today, tomorrow, the next weeks), a time and quick
// +15 / +30 / +60. "Now" applies at once; the rest apply with one button. Times are
// Israel wall times: a time skipped by the spring change is refused with a message and a
// time repeated in autumn asks which offset. Never silently shifted.
//
// Why not one native datetime-local: on phones it opens a date picker first and a time
// picker second, and gives no "tomorrow" or "+30" shortcuts. A day list (native select:
// a wheel on phones) and a native time field are each one tap.

type Mode = When["mode"];
type Offset = "+03:00" | "+02:00";
export const DAYS_AHEAD = 28;
const QUICK_MINUTES = [15, 30, 60] as const;

/** The next whole five minutes, as an Israel wall time. */
function roundedNow(now = new Date()): string {
  return israelWallTime(new Date(Math.ceil(now.getTime() / 300_000) * 300_000));
}

/** Move an Israel wall time by whole minutes (through the instant, so DST is honoured). */
export function shiftWall(wall: string, minutes: number): string {
  const instant = departureInstant(wall, "auto");
  const base = instant.ok ? instant.instant : instant.candidates[0] ? `${wall}:00${instant.candidates[0]}` : null;
  if (!base) return wall;
  return israelWallTime(new Date(Date.parse(base) + minutes * 60_000));
}

/**
 * What the chip says, in two short lines so it shares the header line with from ← to:
 * "יציאה 08:00" over "מחר" / "יום ב׳, 2.11" (no second line for today or for now).
 */
export function whenSummary(
  when: When,
  t: ReturnType<typeof useI18n>["t"],
  lang: "he" | "en",
  now = new Date(),
): { head: string; day: string | null } {
  if (when.mode === "now") return { head: t("compare.when.now"), day: null };
  const date = when.wall.slice(0, 10);
  const distance = daysBetween(israelDate(now), date);
  const day =
    distance === 0
      ? null
      : distance === 1
        ? t("compare.when.chip.tomorrow")
        : formatShortDay(`${date}T12:00:00Z`, lang);
  const head = t(when.mode === "depart_at" ? "compare.when.chip.depart" : "compare.when.chip.arrive", {
    time: when.wall.slice(11, 16),
  });
  return { head, day };
}

/**
 * "+15 דק׳" on screen (the signed number its own left-to-right run, so the sign stays in
 * front); "15 דקות מאוחר יותר" to a screen reader.
 */
function QuickLabel({ minutes, lang, spoken }: { minutes: number; lang: "he" | "en"; spoken: string }) {
  const [number, ...unit] = formatDuration(minutes * 60, lang).split(" ");
  return (
    <>
      <span aria-hidden="true">
        <bdi dir="ltr" className="tabular">{`+${number}`}</bdi> {unit.join(" ")}
      </span>
      <span className="visually-hidden">{spoken}</span>
    </>
  );
}

export function WhenChip({
  when,
  open,
  onToggle,
  panelId,
  ref,
}: {
  when: When;
  open: boolean;
  onToggle: () => void;
  panelId: string;
  ref?: Ref<HTMLButtonElement>;
}) {
  const { t, lang } = useI18n();
  const { head, day } = whenSummary(when, t, lang);
  return (
    <button
      ref={ref}
      type="button"
      className="when-chip"
      aria-expanded={open}
      aria-controls={panelId}
      onClick={onToggle}
    >
      {/* The name is the visible text with a hidden lead-in: "שינוי השעה: יציאה 08:00, מחר". */}
      <span className="visually-hidden">{t("compare.changeTime")}:</span>{" "}
      <span className="when-chip-text">
        <span className="when-chip-head">{head}</span>
        {day && (
          <span className="when-chip-day">
            <span className="visually-hidden">,</span> {day}
          </span>
        )}
      </span>
      <span className="when-chip-caret" aria-hidden="true">
        ▾
      </span>
    </button>
  );
}

export interface WhenPanelProps {
  id: string;
  when: When;
  onChange: (when: When) => void;
  onClose: () => void;
  now?: Date;
}

export function WhenPanel({ id, when, onChange, onClose, now = new Date() }: WhenPanelProps) {
  const { t, lang } = useI18n();
  const ids = useId();
  const formRef = useRef<HTMLFormElement>(null);

  // Opened from anywhere (the chip, or "change time" further down): bring it into view
  // and put focus on the chosen mode, so keyboard and screen-reader users land in it.
  useEffect(() => {
    const form = formRef.current;
    form?.scrollIntoView?.({ block: "nearest" });
    form?.querySelector<HTMLInputElement>("input[type=radio]:checked")?.focus({ preventScroll: true });
  }, []);
  const start = when.mode === "now" ? roundedNow(now) : when.wall;
  const [mode, setMode] = useState<Mode>(when.mode);
  const [day, setDay] = useState(start.slice(0, 10));
  const [time, setTime] = useState(start.slice(11, 16));
  const [problem, setProblem] = useState<null | { kind: "nonexistent" | "invalid" } | { kind: "ambiguous"; candidates: Offset[] }>(null);

  const today = israelDate(now);
  const days = useMemo(() => {
    const list = Array.from({ length: DAYS_AHEAD }, (_, i) => {
      const date = new Date(Date.parse(`${today}T12:00:00Z`) + i * 86_400_000).toISOString().slice(0, 10);
      return date;
    });
    if (!list.includes(day)) list.push(day);
    return list.sort();
  }, [today, day]);

  const dayLabel = (date: string) => {
    const distance = daysBetween(today, date);
    const short = formatShortDay(`${date}T12:00:00Z`, lang);
    return distance === 0 || distance === 1 ? `${relativeDay(date, today, lang, t)} · ${short}` : short;
  };

  const edit = (next: { day?: string; time?: string }) => {
    setProblem(null);
    if (next.day !== undefined) setDay(next.day);
    if (next.time !== undefined) setTime(next.time);
    if (mode === "now") setMode("depart_at");
  };

  const apply = (offset: "auto" | Offset = "auto") => {
    if (mode === "now") {
      onChange({ mode: "now" });
      onClose();
      return;
    }
    const wall = `${day}T${time}`;
    const result = departureInstant(wall, offset);
    if (result.ok) {
      setProblem(null);
      onChange({ mode, wall, offset });
      onClose();
      return;
    }
    if (result.reason === "ambiguous") setProblem({ kind: "ambiguous", candidates: result.candidates as Offset[] });
    else setProblem({ kind: result.reason === "nonexistent" ? "nonexistent" : "invalid" });
  };

  const modes: { mode: Mode; label: string }[] = [
    { mode: "now", label: t("compare.when.now") },
    { mode: "depart_at", label: t("compare.when.depart") },
    { mode: "arrive_by", label: t("compare.when.arrive") },
  ];

  return (
    <form
      ref={formRef}
      id={id}
      className="when-panel"
      aria-label={t("compare.when")}
      onKeyDown={(event) => {
        if (event.key !== "Escape") return;
        event.preventDefault();
        onClose();
      }}
      onSubmit={(event) => {
        event.preventDefault();
        apply();
      }}
    >
      <fieldset className="when-modes">
        <legend className="visually-hidden">{t("compare.when")}</legend>
        {modes.map((option) => (
          <label key={option.mode} className="when-mode">
            <input
              type="radio"
              name={`${ids}-mode`}
              value={option.mode}
              checked={mode === option.mode}
              onChange={() => {
                setProblem(null);
                if (option.mode === "now") {
                  onChange({ mode: "now" });
                  onClose();
                  return;
                }
                setMode(option.mode);
              }}
              className="visually-hidden"
            />
            {option.label}
          </label>
        ))}
      </fieldset>

      <fieldset className="when-fields">
        <legend className="visually-hidden">{t("compare.when.pick")}</legend>
        <label className="when-field when-field-day">
          <span className="when-field-label">{t("compare.when.day")}</span>
          <select value={day} onChange={(event) => edit({ day: event.target.value })}>
            {days.map((date) => (
              <option key={date} value={date}>
                {dayLabel(date)}
              </option>
            ))}
          </select>
        </label>
        <label className="when-field when-field-time">
          <span className="when-field-label">{t("compare.when.time")}</span>
          <input
            type="time"
            step={60}
            required
            value={time}
            onChange={(event) => edit({ time: event.target.value.slice(0, 5) })}
          />
        </label>
      </fieldset>

      <div className="when-quick">
        {QUICK_MINUTES.map((minutes) => (
          <button
            key={minutes}
            type="button"
            className="when-quick-button"
            onClick={() => {
              const next = shiftWall(`${day}T${time}`, minutes);
              edit({ day: next.slice(0, 10), time: next.slice(11, 16) });
            }}
          >
            <QuickLabel minutes={minutes} lang={lang} spoken={t("compare.when.plus", { n: minutes })} />
          </button>
        ))}
      </div>

      {problem && (
        <div className="when-problem" role="alert">
          {problem.kind === "ambiguous" ? (
            <>
              <p>{t("compare.when.ambiguous")}</p>
              {problem.candidates.map((offset) => (
                <button key={offset} type="button" className="button" onClick={() => apply(offset)}>
                  {t(`compare.when.offset.${offset}`)}
                </button>
              ))}
            </>
          ) : (
            <p>{t(problem.kind === "nonexistent" ? "compare.when.nonexistent" : "compare.when.invalid")}</p>
          )}
        </div>
      )}

      <button type="submit" className="button button-primary when-apply">
        {t("compare.when.apply")}
      </button>
    </form>
  );
}
