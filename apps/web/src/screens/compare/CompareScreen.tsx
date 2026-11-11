import { useLayoutEffect, useMemo, useRef, useState, type ReactNode, type RefObject } from "react";
import { Icon, type IconName } from "../../components/ds";
import { ErrorState, TestDataBanner } from "../../components/states";
import { useI18n } from "../../i18n/I18nProvider";
import type { LocationError } from "../../lib/geolocation";
import { useMedia, WIDE_QUERY } from "../../lib/media";
import { useTheme } from "../../lib/theme";
import { usePublishScene } from "../../map/scene";
import { choiceFromSaved, sameEndpoint, type Endpoint, type When } from "../../plan/draft";
import type { BuildResult } from "../../plan/journeyQuery";
import { usePlan } from "../../plan/PlanProvider";
import { earlierTime, laterTime, whenFromOverride } from "../../plan/shift";
import { go, hrefFor } from "../../router";
import { useLocalState } from "../../shell/localStore";
import { useSheet } from "../../shell/sheet";
import type { SavedPlace } from "../../storage/local";
import { Banner } from "./Banner";
import { ChooseHeader } from "./ChooseHeader";
import { chooseScene, draftScene, stepScene } from "./journeyScene";
import { formatShortDay, israelDate, splitFirstSentence, untilText } from "./labels";
import { OptionRow, OptionsSkeleton } from "./OptionRow";
import { RouteActions } from "./RouteScreen";
import { Timeline } from "./Timeline";
import { WhenChip, WhenPanel } from "./TimeControl";
import { useCompare, useNow, useScrollPadding } from "./useCompare";
import "./compare.css";

export { RouteScreen } from "./RouteScreen";

// Compare, step 1: Choose (board 2, approved 11 November 2026; replaces C03's chart). The
// map draws every option at once (journeyScene.ts chooseScene): the chosen one in colour,
// the others faded with their arrival time, which chooses them. The panel: the destination
// as the heading with the start under it and the time tag; one row per option in the API's
// order (departure ← arrival, how long until it leaves, the walk, the lines, the duration);
// then "פרטי המסלול", which opens the chosen option's route details (RouteScreen, #/route).
// Choosing never sends a request.

/** Earlier / Later as ghost buttons (no route: the calm result offers both). */
function ShiftRow({ onEarlier, onLater }: { onEarlier: (() => void) | null; onLater: (() => void) | null }) {
  const { t } = useI18n();
  return (
    <div className="compare-shift">
      <button type="button" className="ot-btn ot-btn--ghost" onClick={onEarlier ?? undefined} disabled={!onEarlier}>
        <Icon name="chevron" className="compare-earlier-icon" />
        {t("compare.earlier")}
      </button>
      <button type="button" className="ot-btn ot-btn--ghost" onClick={onLater ?? undefined} disabled={!onLater}>
        {t("compare.later")}
        <Icon name="chevron" />
      </button>
    </div>
  );
}

/** Saved and recent places as one-tap starting points (never the destination itself). */
function Suggestions({ exclude, onPick }: { exclude: Endpoint | null; onPick: (endpoint: Endpoint) => void }) {
  const { t } = useI18n();
  const local = useLocalState();
  const seen = new Set<string>();
  const places: { key: string; label: string; saved: SavedPlace; icon: IconName }[] = [];
  const add = (saved: SavedPlace | null, icon: IconName, label?: string) => {
    if (!saved) return;
    const endpoint: Endpoint = { type: "place", place: choiceFromSaved(saved) };
    const key = `${saved.latitude.toFixed(5)},${saved.longitude.toFixed(5)}`;
    if (seen.has(key) || sameEndpoint(endpoint, exclude)) return;
    seen.add(key);
    places.push({ key, label: label ?? saved.label, saved, icon });
  };
  add(local.home, "home", t("place.home"));
  add(local.work, "work", t("place.work"));
  local.recents.forEach((recent) => add(recent, "clock"));
  if (places.length === 0) return null;
  return (
    <ul className="ot-chips compare-places" aria-label={t("compare.suggested")}>
      {places.slice(0, 4).map(({ key, label, saved, icon }) => (
        <li key={key}>
          <button type="button" className="ot-chip" onClick={() => onPick({ type: "place", place: choiceFromSaved(saved) })}>
            <Icon name={icon} />
            <bdi>{label}</bdi>
          </button>
        </li>
      ))}
    </ul>
  );
}

/** No starting point yet, or "my location" is unavailable: a calm question, not an error. */
function OriginPrompt({ error, onRetry, onPicked }: { error: LocationError | null; onRetry: () => void; onPicked: () => void }) {
  const { t } = useI18n();
  const { draft, setFrom } = usePlan();
  const pick = (endpoint: Endpoint) => {
    setFrom(endpoint);
    // The prompt goes away with the button in it: keep focus on the screen.
    onPicked();
  };
  return (
    <div className="compare-prompt" role="status">
      <Banner
        icon="pin"
        title={t("compare.askFrom")}
        text={error && t(error === "denied" ? "compare.location.denied" : "compare.location.unavailable")}
      />
      <div className="compare-actions">
        <a className="ot-btn ot-btn--primary" href={hrefFor({ name: "search", field: "from" })}>
          {t("compare.chooseFrom")}
        </a>
        {error !== null && error !== "denied" && error !== "unsupported" && (
          <button type="button" className="ot-btn ot-btn--secondary" onClick={onRetry}>
            {t("compare.location.retry")}
          </button>
        )}
      </div>
      <Suggestions exclude={draft.to} onPick={pick} />
    </div>
  );
}

function DestinationPrompt() {
  const { t } = useI18n();
  return (
    <div className="compare-prompt compare-missing" role="status">
      <Banner icon="pin" title={t("compare.askTo")} />
      <div className="compare-actions">
        <a className="ot-btn ot-btn--primary" href={hrefFor({ name: "search", field: "to" })}>
          {t("compare.chooseTo")}
        </a>
        <a className="ot-btn ot-btn--secondary" href={hrefFor({ name: "home" })}>
          {t("screen.backHome")}
        </a>
      </div>
    </div>
  );
}

function ChangeTime({ onClick }: { onClick: () => void }) {
  const { t } = useI18n();
  return (
    <button type="button" className="ot-btn ot-btn--secondary ot-btn--block" onClick={onClick}>
      <Icon name="clock" />
      {t("compare.changeTime")}
    </button>
  );
}

function TimeProblem({ result, onChangeTime }: { result: Extract<BuildResult, { reason: "time" }>; onChangeTime: () => void }) {
  const { t } = useI18n();
  const { first, rest } = splitFirstSentence(
    t(
      result.problem === "nonexistent"
        ? "compare.when.nonexistent"
        : result.problem === "invalid"
          ? "compare.when.invalid"
          : "compare.when.ambiguous",
    ),
  );
  return (
    <>
      <Banner tone="warning" icon="alert" title={first} text={rest} role="alert" />
      <ChangeTime onClick={onChangeTime} />
    </>
  );
}

/**
 * At the half sheet the options and "פרטי המסלול" must all be in view, whatever the
 * screen height or the fonts: the sheet is asked for the height from its top to the last
 * option plus the pinned bar (fitHalf), so it grows rather than hide a row.
 */
function useFitOptions(listRef: RefObject<HTMLElement | null>, barRef: RefObject<HTMLElement | null>, active: boolean) {
  const { snap, fitHalf } = useSheet();
  useLayoutEffect(() => {
    const list = listRef.current;
    if (!active || !list) return;
    const report = () => {
      const sheet = list.closest(".sheet");
      const scroller = list.closest(".sheet-content");
      if (snap !== "half" || !sheet || !scroller) return fitHalf(null);
      const bar = barRef.current?.getBoundingClientRect().height ?? 0;
      const needed = list.getBoundingClientRect().bottom - sheet.getBoundingClientRect().top + scroller.scrollTop + bar + 8;
      fitHalf(needed > 0 ? needed : null);
    };
    report();
    if (typeof ResizeObserver === "undefined") return () => fitHalf(null);
    const observer = new ResizeObserver(report);
    observer.observe(list);
    if (barRef.current) observer.observe(barRef.current);
    return () => {
      observer.disconnect();
      fitHalf(null);
    };
  }, [listRef, barRef, active, snap, fitHalf]);
}

export function CompareScreen() {
  const { t, lang } = useI18n();
  const theme = useTheme();
  const compare = useCompare();
  const { plan, ends, built, result, planned, journeys, answer, list, index, chosen, choose, refreshing, failure, coverage, askedDate, trips, start, resume } =
    compare;
  // Board 8: on a wide screen the chosen option opens its steps in place, with Step's actions.
  const wide = useMedia(WIDE_QUERY);
  const [focusedLeg, setFocusedLeg] = useState<number | null>(null);
  const { draft, setWhen } = plan;
  const now = useNow();
  const rootRef = useRef<HTMLDivElement>(null);
  const listRef = useRef<HTMLOListElement>(null);
  const barRef = useRef<HTMLDivElement>(null);
  useScrollPadding(rootRef);
  const [timeOpen, setTimeOpen] = useState(false);
  const chipRef = useRef<HTMLButtonElement>(null);
  /** Close the time panel and give focus back to the tag that opened it. */
  const closeTime = () => {
    setTimeOpen(false);
    chipRef.current?.focus({ preventScroll: true });
  };
  const panelId = "compare-when-panel";

  // A tapped step on the wide panel zooms the map to its leg, as on board 3; otherwise every option is drawn.
  const focusedChosen = wide && focusedLeg !== null && chosen !== undefined ? chosen : null;
  const scene = useMemo(
    () =>
      focusedChosen
        ? stepScene(focusedChosen, ends, focusedLeg, { t, lang, theme })
        : list.length > 0
          ? chooseScene(list, index, ends, { t, lang, theme }, choose)
          : draftScene(draft.from, draft.to, ends),
    [focusedChosen, focusedLeg, list, index, ends, t, lang, theme, choose, draft.from, draft.to],
  );
  usePublishScene(scene);

  const answered = answer !== undefined && chosen !== undefined;
  useFitOptions(listRef, barRef, answered && !timeOpen);

  const changeWhen = (when: When) => setWhen(when);
  const shiftTo = (time: ReturnType<typeof laterTime>) =>
    time
      ? () => {
          setTimeOpen(false);
          changeWhen(whenFromOverride(time));
        }
      : null;
  const openTime = () => setTimeOpen(true);
  const focusTop = () => rootRef.current?.querySelector<HTMLElement>("h1")?.focus({ preventScroll: true });

  // A time on another day than the one asked carries its day (e.g. Friday night → Saturday).
  const dayOf = (instant: string): string | null => (israelDate(instant) === askedDate ? null : formatShortDay(instant, lang));

  let body: ReactNode;
  let footer: ReactNode = null;
  if (draft.to === null) {
    body = <DestinationPrompt />;
  } else if (draft.from === null) {
    body = <OriginPrompt error={null} onRetry={compare.retryLocation} onPicked={focusTop} />;
  } else if (built.isPending || (planned && journeys.isPending)) {
    body = <OptionsSkeleton />;
  } else if (result && !result.ok) {
    body =
      result.reason === "time" ? (
        <TimeProblem result={result} onChangeTime={openTime} />
      ) : result.reason === "location" ? (
        <OriginPrompt error={result.error} onRetry={compare.retryLocation} onPicked={focusTop} />
      ) : result.reason === "missing_origin" ? (
        <OriginPrompt error={null} onRetry={compare.retryLocation} onPicked={focusTop} />
      ) : (
        <DestinationPrompt />
      );
  } else if (journeys.isError) {
    body = (
      <>
        <ErrorState
          state={failure?.state ?? "unexpected"}
          coverage={coverage}
          retryAfterSeconds={failure?.error.kind === "problem" ? failure.error.retryAfterSeconds : null}
          onRetry={() => void journeys.refetch()}
        />
        {failure?.state === "outside_window" && <ChangeTime onClick={openTime} />}
      </>
    );
  } else if (answer && list.length === 0) {
    body = (
      <>
        <Banner icon="info" title={t("compare.noRoute")} text={t("compare.noRoute.hint")} role="status" />
        <ShiftRow onEarlier={shiftTo(earlierTime([], answer.sent))} onLater={shiftTo(laterTime([], answer.sent))} />
        <ChangeTime onClick={openTime} />
      </>
    );
  } else if (answered) {
    const meta = answer.response.meta;
    body = (
      <div className="compare-answer" aria-busy={refreshing} data-refreshing={refreshing || undefined}>
        <span className="visually-hidden" role="status">
          {refreshing ? t("compare.loading") : ""}
        </span>
        {meta.mode === "fixture" && <TestDataBanner />}
        <ol ref={listRef} className="compare-options" aria-label={t("compare.options")}>
          {list.map((journey, i) => (
            <li key={`${i}-${journey.id}`}>
              <OptionRow
                journey={journey}
                index={i}
                chosen={i === index}
                until={untilText(journey.timing.scheduledDeparture, now, lang, t)}
                dayOf={dayOf}
                onChoose={(next) => {
                  setFocusedLeg(null);
                  choose(next);
                }}
              />
              {wide && i === index && (
                <section className="compare-inline-steps" aria-label={t("screen.route")}>
                  <Timeline journey={journey} ends={ends} trips={trips} focused={focusedLeg} onFocus={setFocusedLeg} />
                </section>
              )}
            </li>
          ))}
        </ol>
      </div>
    );
    // While the time is being changed the options are about to change: no button then.
    // While a new time's answer loads, the previous one stays, dimmed, and cannot be opened.
    footer = timeOpen ? null : wide ? (
      <div ref={barRef}>
        <RouteActions destination={draft.to} refreshing={refreshing} resume={resume} onStart={start} />
      </div>
    ) : (
      <div className="compare-start" ref={barRef}>
        <button type="button" className="b-btn b-btn--main compare-start__main" disabled={refreshing} onClick={() => go({ name: "route" })}>
          {t("compare.details")}
        </button>
      </div>
    );
  } else {
    body = <OptionsSkeleton />;
  }

  return (
    <div className="compare" ref={rootRef}>
      <ChooseHeader
        from={draft.from}
        to={draft.to}
        // Realtime is not built yet: every time shown is scheduled, said once here.
        note={answered ? t("time.scheduled") : null}
        chip={<WhenChip ref={chipRef} when={draft.when} open={timeOpen} onToggle={() => setTimeOpen((open) => !open)} panelId={panelId} />}
      />
      {timeOpen && <WhenPanel id={panelId} when={draft.when} onChange={changeWhen} onClose={closeTime} />}
      <div className="compare-body">{body}</div>
      {footer}
    </div>
  );
}
