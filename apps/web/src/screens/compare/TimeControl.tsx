import { useId, useState } from "react";
import { Bdi } from "../../components/states";
import { useI18n } from "../../i18n/I18nProvider";
import type { MessageKey } from "../../i18n/messages";
import { departureInstant, formatClock, formatDate, israelWallTime } from "../../lib/time";
import type { When } from "../../plan/draft";

// Time control (design: Compare; CU03, CU12): Now / Depart at / Arrive by with an inline
// picker in Israel wall time. A time skipped by the spring change is refused with a
// message; a time repeated in autumn asks which offset. Never silently shifted.

type Mode = When["mode"];
type Offset = "+03:00" | "+02:00";

const modeKey: Record<Mode, MessageKey> = { now: "time.now", depart_at: "time.departAt", arrive_by: "time.arriveBy" };
const MODES: Mode[] = ["now", "depart_at", "arrive_by"];

/** The next whole five minutes, as an Israel wall time (the picker's starting value). */
function defaultWall(now = new Date()): string {
  return israelWallTime(new Date(Math.ceil(now.getTime() / 300_000) * 300_000));
}

export interface TimeControlProps {
  when: When;
  onChange: (when: When) => void;
  /** Mode whose picker is open; null when closed. Lifted so "change time" can open it. */
  editing: Exclude<Mode, "now"> | null;
  onEditing: (mode: Exclude<Mode, "now"> | null) => void;
}

export function TimeControl({ when, onChange, editing, onEditing }: TimeControlProps) {
  const { t, lang } = useI18n();
  const id = useId();
  const [wall, setWall] = useState(() => (when.mode === "now" ? defaultWall() : when.wall));
  const [problem, setProblem] = useState<null | { kind: "nonexistent" | "invalid" } | { kind: "ambiguous"; candidates: Offset[] }>(null);

  const shown: Mode = editing ?? when.mode;

  const choose = (mode: Mode) => {
    setProblem(null);
    if (mode === "now") {
      onEditing(null);
      if (when.mode !== "now") onChange({ mode: "now" });
      return;
    }
    if (when.mode !== "now") setWall(when.wall);
    onEditing(mode);
  };

  const apply = (offset: "auto" | Offset = "auto") => {
    const mode = editing ?? (when.mode === "now" ? "depart_at" : when.mode);
    const result = departureInstant(wall, offset);
    if (result.ok) {
      setProblem(null);
      onEditing(null);
      onChange({ mode, wall, offset });
      return;
    }
    if (result.reason === "ambiguous") setProblem({ kind: "ambiguous", candidates: result.candidates as Offset[] });
    else setProblem({ kind: result.reason === "nonexistent" ? "nonexistent" : "invalid" });
  };

  const instant = when.mode === "now" ? null : departureInstant(when.wall, when.offset);
  const summary =
    instant?.ok === true ? `${formatClock(instant.instant, lang)} · ${formatDate(instant.instant, lang)}` : null;

  return (
    <div className="compare-when">
      <fieldset className="segmented compare-when-modes">
        <legend className="visually-hidden">{t("compare.when")}</legend>
        {MODES.map((mode) => (
          <label key={mode}>
            <input
              type="radio"
              name={`${id}-when`}
              value={mode}
              checked={shown === mode}
              onChange={() => choose(mode)}
              className="visually-hidden"
            />
            {t(modeKey[mode])}
          </label>
        ))}
      </fieldset>

      {editing === null && when.mode !== "now" && summary && (
        <button type="button" className="compare-when-summary" onClick={() => onEditing(when.mode as Exclude<Mode, "now">)}>
          <span className="visually-hidden">{t("compare.when.edit", { when: t(modeKey[when.mode]) })} </span>
          <Bdi>{summary}</Bdi> <span aria-hidden="true">✎</span>
        </button>
      )}

      {editing !== null && (
        <form
          className="compare-when-picker"
          onSubmit={(event) => {
            event.preventDefault();
            apply();
          }}
        >
          <label htmlFor={`${id}-wall`} className="visually-hidden">
            {t("compare.when.pick")}
          </label>
          <input
            id={`${id}-wall`}
            type="datetime-local"
            value={wall}
            step={60}
            required
            onChange={(event) => {
              setWall(event.target.value.slice(0, 16));
              setProblem(null);
            }}
          />
          <button type="submit" className="button">
            {t("compare.when.apply")}
          </button>
        </form>
      )}

      {problem && (
        <div className="compare-when-problem" role="alert">
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
    </div>
  );
}
