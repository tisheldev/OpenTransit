import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState, type ReactNode } from "react";
import { getStatus } from "../../api/endpoints";
import { queryKeys } from "../../api/queries";
import { ApiFailure, unwrap } from "../../api/result";
import type { Journey } from "../../api/types";
import { ErrorState, TestDataBanner } from "../../components/states";
import { useI18n } from "../../i18n/I18nProvider";
import { usePublishScene } from "../../map/scene";
import { sameJourney, startActiveTrip, useActiveTrip } from "../../nav/activeTrip";
import type { PlanDraft } from "../../plan/draft";
import type { BuildResult, TimeOverride } from "../../plan/journeyQuery";
import { usePlan } from "../../plan/PlanProvider";
import { cachedTrips, MARK_PAINTED, MARK_REQUEST, useJourneyRequest, useJourneys, useTrips } from "../../plan/queries";
import { earlierTime, laterTime } from "../../plan/shift";
import { go, hrefFor } from "../../router";
import { journeyToScene } from "../../map/fromJourney";
import { FromTo } from "../../shell/FromTo";
import { useSheet } from "../../shell/sheet";
import { draftScene } from "./journeyScene";
import { endpointLabel, type EndLabels } from "./labels";
import { ChartSkeleton, OptionsChart } from "./OptionsChart";
import { RouteDetails, type TripState } from "./RouteDetails";
import { TimeControl } from "./TimeControl";
import "./compare.css";

// Compare and Route details — C03, C04 (design: one screen: chart, the selected option's
// details, Earlier / Later, Start pinned). Sheet content: owns its <h1> and map scene.

type Editing = "depart_at" | "arrive_by" | null;

const tripRefsOf = (journey: Journey | undefined) =>
  journey ? journey.legs.flatMap((leg) => (leg.transit ? [leg.transit.engineTripId] : [])) : [];

function StartButton({ journey, onStart }: { journey: Journey; onStart: (resume: boolean) => void }) {
  const { t } = useI18n();
  const active = useActiveTrip();
  const resume = active !== null && sameJourney(active.journey, journey);
  return (
    <div className="compare-start">
      <button type="button" className="button button-primary" onClick={() => onStart(resume)}>
        {resume ? t("compare.resume") : t("compare.start")}
      </button>
    </div>
  );
}

function ShiftButtons({ onEarlier, onLater }: { onEarlier: (() => void) | null; onLater: (() => void) | null }) {
  const { t } = useI18n();
  return (
    <div className="compare-shift">
      <button type="button" className="button" onClick={onEarlier ?? undefined} disabled={!onEarlier}>
        {t("compare.earlier")}
      </button>
      <button type="button" className="button" onClick={onLater ?? undefined} disabled={!onLater}>
        {t("compare.later")}
      </button>
    </div>
  );
}

function BuildProblem({ result, onChangeTime }: { result: Exclude<BuildResult, { ok: true }>; onChangeTime: () => void }) {
  const { t } = useI18n();
  if (result.reason === "location") {
    return (
      <div className="state state-error" role="alert">
        <p>{t(result.error === "denied" ? "compare.location.denied" : "compare.location.unavailable")}</p>
        <a className="button" href={hrefFor({ name: "search", field: "from" })}>
          {t("compare.chooseFrom")}
        </a>
      </div>
    );
  }
  if (result.reason === "time") {
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
  return <MissingDestination />;
}

function MissingDestination() {
  const { t } = useI18n();
  return (
    <div className="state state-empty compare-missing" role="status">
      <p>{t("compare.missingTo")}</p>
      <a className="button" href={hrefFor({ name: "search", field: "to" })}>
        {t("compare.chooseTo")}
      </a>
      <a className="button" href={hrefFor({ name: "home" })}>
        {t("screen.backHome")}
      </a>
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
  // At 360 x 640 the chart and the start of the selected route only fit together on the
  // full sheet (design: Language and layout rules), so Compare opens it fully.
  const { setSnap } = useSheet();
  useEffect(() => setSnap("full"), [setSnap]);
  const [shift, setShift] = useState<{ draft: PlanDraft; time: TimeOverride } | null>(null);
  const [editing, setEditing] = useState<Editing>(null);
  const override = shift && shift.draft === draft ? shift.time : null;

  const ends: EndLabels = useMemo(
    () => ({ from: endpointLabel(draft.from, t), to: endpointLabel(draft.to, t) }),
    [draft.from, draft.to, t],
  );

  const built = useJourneyRequest(draft, lang, override);
  const result = built.data;
  const planned = result?.ok ? result : null;
  const journeys = useJourneys(planned);
  const answer = journeys.data;
  const list = useMemo(() => answer?.response.data.journeys ?? [], [answer]);
  const index = Math.min(selected, Math.max(0, list.length - 1));
  const chosen: Journey | undefined = list[index];

  // Trip details for the selected option only, fetched once the chart is on screen.
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

  // SP04 client work: request sent → chart painted (read by the @real test).
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

  const replaceWith = (time: TimeOverride | null) => {
    if (!time) return null;
    return () => {
      setSelected(0);
      setShift({ draft, time });
    };
  };

  const changeTime = () => setEditing(draft.when.mode === "arrive_by" ? "arrive_by" : "depart_at");

  const start = (resume: boolean) => {
    if (!chosen || !answer) return;
    if (!resume) startActiveTrip({ journey: chosen, meta: answer.response.meta, trips: cachedTrips(client, refs) });
    go({ name: "navigate" });
  };

  let body: ReactNode;
  if (draft.to === null) {
    body = <MissingDestination />;
  } else if (built.isPending || (planned && journeys.isPending)) {
    body = <ChartSkeleton />;
  } else if (result && !result.ok) {
    body = <BuildProblem result={result} onChangeTime={changeTime} />;
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
          <button type="button" className="button" onClick={changeTime}>
            {t("compare.changeTime")}
          </button>
        )}
      </>
    );
  } else if (answer && list.length === 0) {
    body = (
      <>
        <div className="state state-empty compare-no-route" role="status">
          <p>
            <strong>{t("compare.noRoute")}</strong>
          </p>
          <p>{t("compare.noRoute.hint")}</p>
        </div>
        <ShiftButtons
          onEarlier={replaceWith(earlierTime([], answer.sent))}
          onLater={replaceWith(laterTime([], answer.sent))}
        />
        <button type="button" className="button" onClick={changeTime}>
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
      <>
        {meta.mode === "fixture" && <TestDataBanner />}
        <OptionsChart journeys={list} selected={index} onSelect={setSelected} />
        <p className="compare-scheduled">{t("compare.scheduled")}</p>
        <RouteDetails journey={chosen} ends={ends} trips={trips} />
        <ShiftButtons onEarlier={replaceWith(earlierTime(list))} onLater={replaceWith(laterTime(list))} />
        {liveOff && <p className="compare-live-off">{t("banner.liveUnavailable")}</p>}
        <StartButton journey={chosen} onStart={start} />
      </>
    );
  } else {
    body = <ChartSkeleton />;
  }

  return (
    <div className="compare">
      <h1 className="visually-hidden">{t("screen.compare")}</h1>
      <FromTo variant="compact" />
      <TimeControl
        when={draft.when}
        onChange={(when) => {
          setWhen(when);
        }}
        editing={editing}
        onEditing={setEditing}
      />
      {body}
    </div>
  );
}
