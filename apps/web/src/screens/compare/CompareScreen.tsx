import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useLayoutEffect, useMemo, useRef, useState, type ReactNode, type RefObject } from "react";
import { getStatus } from "../../api/endpoints";
import { queryKeys } from "../../api/queries";
import { ApiFailure, unwrap } from "../../api/result";
import type { Journey } from "../../api/types";
import { ErrorState, TestDataBanner } from "../../components/states";
import { useI18n } from "../../i18n/I18nProvider";
import type { LocationError } from "../../lib/geolocation";
import { journeyToScene } from "../../map/fromJourney";
import { usePublishScene } from "../../map/scene";
import { sameJourney, startActiveTrip, useActiveTrip } from "../../nav/activeTrip";
import { choiceFromSaved, sameEndpoint, type Endpoint, type When } from "../../plan/draft";
import type { BuildResult } from "../../plan/journeyQuery";
import { usePlan } from "../../plan/PlanProvider";
import { cachedTrips, MARK_PAINTED, MARK_REQUEST, useJourneyRequest, useJourneys, useTrips } from "../../plan/queries";
import { earlierTime, laterTime, whenFromOverride } from "../../plan/shift";
import { go, hrefFor } from "../../router";
import { useLocalState } from "../../shell/localStore";
import { useSheet } from "../../shell/sheet";
import type { SavedPlace } from "../../storage/local";
import { CompareHeader } from "./CompareHeader";
import { draftScene } from "./journeyScene";
import { endpointLabel, formatShortDay, israelDate, type EndLabels } from "./labels";
import { OptionsChart, OptionsSkeleton } from "./OptionsChart";
import { RouteDetails, type TripState } from "./RouteDetails";
import { WhenChip, WhenPanel } from "./TimeControl";
import "./compare.css";

// Compare and Route details — C03, C04. One screen: a one-line header (from ← to, swap,
// time chip), the options, Earlier / Later right under them with one scheduled note, then
// the selected option's itinerary, with Start pinned at the bottom. It opens on the half
// sheet (the shell's default) so the route shows on the map above the options; tapping
// an option raises the sheet to full for its details, and the passenger can drag it down.

const tripRefsOf = (journey: Journey | undefined) =>
  journey ? journey.legs.flatMap((leg) => (leg.transit ? [leg.transit.engineTripId] : [])) : [];

/**
 * The scroll container's own padding, so the pinned Start bar can reach its edges
 * (full width, flush with the bottom) whatever the sheet's padding is.
 */
function useScrollPadding(ref: RefObject<HTMLElement | null>) {
  useLayoutEffect(() => {
    const element = ref.current;
    if (!element || typeof getComputedStyle === "undefined") return;
    let parent = element.parentElement;
    while (parent && !/(auto|scroll)/.test(getComputedStyle(parent).overflowY)) parent = parent.parentElement;
    if (!parent) return;
    const style = getComputedStyle(parent);
    element.style.setProperty("--compare-pad-end", style.paddingBlockEnd || style.paddingBottom || "0px");
    element.style.setProperty("--compare-pad-inline", style.paddingInlineStart || style.paddingLeft || "0px");
  }, [ref]);
}

function StartBar({ journey, onStart, disabled }: { journey: Journey; onStart: (resume: boolean) => void; disabled: boolean }) {
  const { t } = useI18n();
  const active = useActiveTrip();
  const resume = active !== null && sameJourney(active.journey, journey);
  return (
    <div className="compare-start">
      <button
        type="button"
        className="button button-primary compare-start-button"
        disabled={disabled}
        onClick={() => onStart(resume)}
      >
        {resume ? t("compare.resume") : t("compare.start")}
      </button>
    </div>
  );
}

function ShiftRow({ onEarlier, onLater, note }: { onEarlier: (() => void) | null; onLater: (() => void) | null; note?: string }) {
  const { t } = useI18n();
  return (
    <div className="compare-shift">
      <button type="button" className="shift-button" onClick={onEarlier ?? undefined} disabled={!onEarlier}>
        <span className="compare-flip" aria-hidden="true">
          →
        </span>
        {t("compare.earlier")}
      </button>
      {note && <p className="compare-note">{note}</p>}
      <button type="button" className="shift-button" onClick={onLater ?? undefined} disabled={!onLater}>
        {t("compare.later")}
        <span className="compare-flip" aria-hidden="true">
          ←
        </span>
      </button>
    </div>
  );
}

/** Saved and recent places as one-tap starting points (never the destination itself). */
function Suggestions({ exclude, onPick }: { exclude: Endpoint | null; onPick: (endpoint: Endpoint) => void }) {
  const { t } = useI18n();
  const local = useLocalState();
  const seen = new Set<string>();
  const places: { key: string; label: string; saved: SavedPlace }[] = [];
  const add = (saved: SavedPlace | null, label?: string) => {
    if (!saved) return;
    const endpoint: Endpoint = { type: "place", place: choiceFromSaved(saved) };
    const key = `${saved.latitude.toFixed(5)},${saved.longitude.toFixed(5)}`;
    if (seen.has(key) || sameEndpoint(endpoint, exclude)) return;
    seen.add(key);
    places.push({ key, label: label ?? saved.label, saved });
  };
  add(local.home, t("place.home"));
  add(local.work, t("place.work"));
  local.recents.forEach((recent) => add(recent));
  if (places.length === 0) return null;
  return (
    <ul className="prompt-places" aria-label={t("compare.suggested")}>
      {places.slice(0, 4).map(({ key, label, saved }) => (
        <li key={key}>
          <button type="button" className="prompt-place" onClick={() => onPick({ type: "place", place: choiceFromSaved(saved) })}>
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
      <p className="prompt-title">{t("compare.askFrom")}</p>
      {error && <p className="prompt-hint">{t(error === "denied" ? "compare.location.denied" : "compare.location.unavailable")}</p>}
      <div className="prompt-actions">
        <a className="button button-primary" href={hrefFor({ name: "search", field: "from" })}>
          {t("compare.chooseFrom")}
        </a>
        {error !== null && error !== "denied" && error !== "unsupported" && (
          <button type="button" className="button" onClick={onRetry}>
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
      <p className="prompt-title">{t("compare.askTo")}</p>
      <div className="prompt-actions">
        <a className="button button-primary" href={hrefFor({ name: "search", field: "to" })}>
          {t("compare.chooseTo")}
        </a>
        <a className="button" href={hrefFor({ name: "home" })}>
          {t("screen.backHome")}
        </a>
      </div>
    </div>
  );
}

function TimeProblem({ result, onChangeTime }: { result: Extract<BuildResult, { reason: "time" }>; onChangeTime: () => void }) {
  const { t } = useI18n();
  return (
    <div className="state state-error" role="alert">
      <p>
        {t(
          result.problem === "nonexistent"
            ? "compare.when.nonexistent"
            : result.problem === "invalid"
              ? "compare.when.invalid"
              : "compare.when.ambiguous",
        )}
      </p>
      <button type="button" className="button" onClick={onChangeTime}>
        {t("compare.changeTime")}
      </button>
    </div>
  );
}

/** Coverage for OUTSIDE_SERVICE_WINDOW: the problem has none, so it comes from /v1/status. */
function useCoverage(enabled: boolean) {
  const status = useQuery({
    queryKey: queryKeys.status,
    queryFn: async ({ signal }) => unwrap(await getStatus(signal)),
    staleTime: 5 * 60_000,
    enabled,
  });
  const meta = status.data?.meta as { coverage?: { from: string; until: string } } | undefined;
  return meta?.coverage ?? null;
}

export function CompareScreen() {
  const { t, lang } = useI18n();
  const { draft, setWhen, selected, setSelected } = usePlan();
  const client = useQueryClient();
  const { setSnap } = useSheet();
  const rootRef = useRef<HTMLDivElement>(null);
  useScrollPadding(rootRef);
  const [timeOpen, setTimeOpen] = useState(false);
  const chipRef = useRef<HTMLButtonElement>(null);
  /** Close the time panel and give focus back to the chip that opened it. */
  const closeTime = () => {
    setTimeOpen(false);
    chipRef.current?.focus({ preventScroll: true });
  };
  const [attempt, setAttempt] = useState(0);
  const panelId = "compare-when-panel";

  const ends: EndLabels = useMemo(
    () => ({ from: endpointLabel(draft.from, t), to: endpointLabel(draft.to, t) }),
    [draft.from, draft.to, t],
  );

  const built = useJourneyRequest(draft, lang, null, attempt);
  const result = built.data;
  const planned = result?.ok ? result : null;
  const journeys = useJourneys(planned);
  const answer = journeys.data;
  const list = useMemo(() => answer?.response.data.journeys ?? [], [answer]);
  const index = Math.min(selected, Math.max(0, list.length - 1));
  const chosen: Journey | undefined = list[index];
  // The previous time's answer, shown until the new one arrives (same ends only).
  const refreshing = built.isPlaceholderData || journeys.isPlaceholderData;

  // Trip details for the selected option only, fetched once the options are on screen.
  const refs = useMemo(() => tripRefsOf(chosen), [chosen]);
  const tripQueries = useTrips(refs, chosen !== undefined);
  const trips: Record<string, TripState> = {};
  refs.forEach((ref, i) => {
    const query = tripQueries[i];
    trips[ref] = query?.data ? { status: "ok", trip: query.data.data } : query?.isError ? { status: "error" } : { status: "pending" };
  });

  const scene = useMemo(
    () =>
      chosen
        ? {
            ...journeyToScene(chosen, { originLabel: ends.from, destinationLabel: ends.to }),
            user: null,
            camera: "fit" as const,
            pick: false,
          }
        : draftScene(draft.from, draft.to, ends),
    [chosen, ends, draft.from, draft.to],
  );
  usePublishScene(scene);

  // SP04 client work: request sent → options painted (read by the @real test).
  useEffect(() => {
    if (!answer || typeof performance === "undefined" || !performance.getEntriesByName(MARK_REQUEST).length) return;
    performance.mark(MARK_PAINTED);
    try {
      performance.measure("ot:journeys:client", MARK_REQUEST, MARK_PAINTED);
    } catch {
      // marks cleared: nothing to measure
    }
  }, [answer]);

  const failure = journeys.error instanceof ApiFailure ? journeys.error : null;
  const coverage = useCoverage(failure?.state === "outside_window");

  const changeWhen = (when: When) => {
    setWhen(when);
  };
  const shiftTo = (time: ReturnType<typeof laterTime>) =>
    time
      ? () => {
          setTimeOpen(false);
          changeWhen(whenFromOverride(time));
        }
      : null;
  const openTime = () => setTimeOpen(true);
  const focusTop = () => rootRef.current?.querySelector<HTMLElement>("h1")?.focus({ preventScroll: true });

  const select = (next: number) => {
    setSelected(next);
    // The details need room: raise the sheet; the passenger can drag it back down.
    setSnap("full");
  };

  const start = (resume: boolean) => {
    if (!chosen || !answer) return;
    if (!resume) startActiveTrip({ journey: chosen, meta: answer.response.meta, trips: cachedTrips(client, refs) });
    go({ name: "navigate" });
  };

  // The day the request asked about: options on another day name it.
  const asked = answer?.sent.departAt ?? answer?.sent.arriveBy ?? null;
  const askedDate = asked ? israelDate(asked) : israelDate(new Date());

  let body: ReactNode;
  let footer: ReactNode = null;
  if (draft.to === null) {
    body = <DestinationPrompt />;
  } else if (draft.from === null) {
    body = <OriginPrompt error={null} onRetry={() => setAttempt((n) => n + 1)} onPicked={focusTop} />;
  } else if (built.isPending || (planned && journeys.isPending)) {
    body = <OptionsSkeleton />;
  } else if (result && !result.ok) {
    body =
      result.reason === "time" ? (
        <TimeProblem result={result} onChangeTime={openTime} />
      ) : result.reason === "location" ? (
        <OriginPrompt error={result.error} onRetry={() => setAttempt((n) => n + 1)} onPicked={focusTop} />
      ) : result.reason === "missing_origin" ? (
        <OriginPrompt error={null} onRetry={() => setAttempt((n) => n + 1)} onPicked={focusTop} />
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
        {failure?.state === "outside_window" && (
          <button type="button" className="button" onClick={openTime}>
            {t("compare.changeTime")}
          </button>
        )}
      </>
    );
  } else if (answer && list.length === 0) {
    body = (
      <>
        <div className="compare-prompt compare-no-route" role="status">
          <p className="prompt-title">{t("compare.noRoute")}</p>
          <p className="prompt-hint">{t("compare.noRoute.hint")}</p>
        </div>
        <ShiftRow onEarlier={shiftTo(earlierTime([], answer.sent))} onLater={shiftTo(laterTime([], answer.sent))} />
        <button type="button" className="button compare-change-time" onClick={openTime}>
          {t("compare.changeTime")}
        </button>
      </>
    );
  } else if (answer && chosen) {
    const meta = answer.response.meta;
    const caps = meta.capabilities as { realtime?: string; alerts?: string } | undefined;
    // Decided from meta.capabilities only (design: Constraints); missing means unavailable.
    const liveOff = !caps || caps.realtime === "not_enabled" || caps.alerts === "not_enabled";
    body = (
      <div className="compare-answer" aria-busy={refreshing} data-refreshing={refreshing || undefined}>
        <span className="visually-hidden" role="status">
          {refreshing ? t("compare.loading") : ""}
        </span>
        {meta.mode === "fixture" && <TestDataBanner />}
        <OptionsChart journeys={list} selected={index} onSelect={select} askedDate={askedDate} />
        <ShiftRow
          onEarlier={shiftTo(earlierTime(list))}
          onLater={shiftTo(laterTime(list))}
          note={t(liveOff ? "compare.scheduled" : "compare.scheduledOnly")}
        />
        <RouteDetails
          journey={chosen}
          ends={ends}
          trips={trips}
          day={israelDate(chosen.timing.scheduledDeparture) === askedDate ? null : formatShortDay(chosen.timing.scheduledDeparture, lang)}
        />
      </div>
    );
    // While the time is being changed the options are about to change: no Start then
    // (and the panel's own button is not hidden behind it on the half sheet). While a new
    // time's answer loads, the previous one stays, dimmed, and cannot be started.
    footer = timeOpen ? null : <StartBar journey={chosen} onStart={start} disabled={refreshing} />;
  } else {
    body = <OptionsSkeleton />;
  }

  return (
    <div className="compare" ref={rootRef}>
      <h1 className="visually-hidden" tabIndex={-1}>
        {t("screen.compare")}
      </h1>
      <CompareHeader
        chip={<WhenChip ref={chipRef} when={draft.when} open={timeOpen} onToggle={() => setTimeOpen((open) => !open)} panelId={panelId} />}
      />
      {timeOpen && <WhenPanel id={panelId} when={draft.when} onChange={changeWhen} onClose={closeTime} />}
      <div className="compare-body">{body}</div>
      {footer}
    </div>
  );
}
